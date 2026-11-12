"""Database-backed jobs with bounded retries, expiring leases, and fenced completion."""
import time
import math
import uuid
from sqlalchemy import select, update, and_, or_
from sqlalchemy.exc import IntegrityError
from .db import Session, Job, Run, Photo, ModelVersion, Estimate, utcnow

MAX_ATTEMPTS = 3
LEASE_SECONDS = 600

def enqueue(photo_id, model_ids, key, session_factory=Session):
    def existing(s):
        previous = s.scalar(select(Job).where(Job.idempotency_key == key))
        if previous and (previous.photo_id != photo_id or sorted(previous.model_ids) != sorted(model_ids)):
            raise ValueError('Idempotency key was already used with different inputs')
        return previous
    try:
        with session_factory.begin() as s:
            previous = existing(s)
            if previous: return previous
            if not s.get(Photo, photo_id): raise LookupError('Photo not found')
            models = [s.get(ModelVersion, mid) for mid in model_ids]
            if any(m is None for m in models) or len({m.target for m in models}) != len(models):
                raise ValueError('Choose one registered model version per target')
            if any(m.manifest.get('serving_enabled') is False for m in models):
                raise ValueError('This model has saved predictions only; its worker adapter is not validated')
            contract = s.get(Photo, photo_id).metadata_json.get('input_contract')
            if contract and any(m.manifest.get('benchmark') != contract for m in models):
                raise ValueError('Model does not support this photo input contract')
            run_id = str(uuid.uuid4())
            s.add(Run(id=run_id, kind='inference', status='queued', provenance={'model_ids': model_ids, 'photo_id': photo_id}))
            s.flush()
            job = Job(id=str(uuid.uuid4()), idempotency_key=key, photo_id=photo_id, run_id=run_id,
                      model_ids=model_ids, status='queued', attempts=0)
            s.add(job)
            s.flush()
            return job
    except IntegrityError:
        with session_factory() as s:
            previous = existing(s)
            if previous: return previous
        raise

def claim(session_factory=Session, now=None):
    now = time.time() if now is None else now
    eligible = or_(Job.status == 'queued', and_(Job.status == 'running', Job.lease_until < now))
    with session_factory.begin() as s:
        expired = s.scalars(select(Job).where(eligible, Job.attempts >= MAX_ATTEMPTS)).all()
        for job in expired:
            job.status, job.error, job.updated_at = 'failed', 'Retry limit reached after interrupted work', utcnow()
            s.get(Run, job.run_id).status = 'failed'
            s.get(Run, job.run_id).completed_at = utcnow()
        candidate = s.scalar(select(Job).where(eligible, Job.attempts < MAX_ATTEMPTS).order_by(Job.created_at).limit(1))
        if not candidate: return None
        token = str(uuid.uuid4())
        # Compare-and-swap protects SQLite as well as PostgreSQL concurrent claimers.
        result = s.execute(update(Job).where(Job.id == candidate.id, eligible, Job.attempts == candidate.attempts).values(
            status='running', lease_token=token, lease_until=now + LEASE_SECONDS,
            attempts=Job.attempts + 1, updated_at=utcnow(), error=None).execution_options(synchronize_session=False))
        if result.rowcount != 1: return None
        s.get(Run, candidate.run_id).status = 'running'
        s.expire(candidate)
        s.refresh(candidate)
        return candidate

def finish(job, outputs=None, error=None, session_factory=Session):
    with session_factory.begin() as s:
        result = s.execute(update(Job).where(Job.id == job.id, Job.status == 'running', Job.lease_token == job.lease_token,
                Job.lease_until > time.time()).values(status='failed' if error else 'complete',
                error=error, lease_until=None, lease_token=None, updated_at=utcnow()).execution_options(synchronize_session=False))
        if result.rowcount != 1: return False  # Old worker cannot overwrite a reclaimed job.
        run = s.get(Run, job.run_id)
        run.status, run.completed_at = ('failed' if error else 'complete'), utcnow()
        if not error:
            if not outputs or len(outputs) != len(job.model_ids) or {o['model_id'] for o in outputs} != set(job.model_ids):
                raise ValueError('Worker did not produce the requested model outputs')
            for output in outputs:
                version = s.get(ModelVersion, output['model_id'])
                if output['target'] != version.target or not math.isfinite(output['value']) or output['value'] <= 0:
                    raise ValueError('Invalid target or estimate returned by worker')
                # Preserve benchmark exposure: rerunning training images does not make them held out.
                photo = s.get(Photo, job.photo_id)
                same_input = Estimate.photo_id == job.photo_id
                if photo.image_sha256:
                    same_input = or_(same_input, Photo.image_sha256 == photo.image_sha256)
                prior = s.scalar(select(Estimate).join(Photo).where(same_input,
                    Estimate.model_id == output['model_id']).order_by(Estimate.created_at).limit(1))
                s.add(Estimate(id=str(uuid.uuid4()), photo_id=job.photo_id, run_id=job.run_id,
                    matchup_id=prior.matchup_id if prior and prior.photo_id == job.photo_id else None, target=output['target'], model_id=output['model_id'],
                    value=output['value'], role=prior.role if prior else 'unseen_inference',
                    split=prior.split if prior else None, scene_group=prior.scene_group if prior else None,
                    evidence=output['evidence']))
        return True
