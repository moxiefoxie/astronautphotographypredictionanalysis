"""Bounded append-only model release; default is an offline preflight.

Stage before activation so frontend evidence can be deployed first. No photos,
images, overlays, schema changes, deletions, or historical estimate updates.
"""
import argparse
import json
from pathlib import Path
from sqlalchemy import select, text, update
from .db import Base, make_engine, utcnow
from .confidence import saved_confidence
from .transfer import DESTINATION_REF

MAX_BYTES = 512 * 1024
NAMES = ('model_versions', 'prediction_runs', 'estimates')


def read_release(path):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError('Release exceeds the 512 KiB budget')
    data = json.loads(raw)
    if data['version'] != 1 or data['destination'] != DESTINATION_REF:
        raise ValueError('Unexpected release destination or version')
    if [len(data[n]) for n in NAMES] != [1, 1, 100]:
        raise ValueError('Release must contain one model, one run and 100 estimates')
    model = data['model_versions'][0]; run = data['prediction_runs'][0]
    if run['status'] != 'pending_release' or run['completed_at'] is not None:
        raise ValueError('Release must be staged before activation')
    if len({e['photo_id'] for e in data['estimates']}) != 100:
        raise ValueError('Release must contain 100 distinct sample photos')
    for name in NAMES:
        columns = set(Base.metadata.tables[name].columns.keys())
        if any(set(row) != columns for row in data[name]):
            raise ValueError(f'Unexpected fields in {name}')
    for e in data['estimates']:
        if e['target'] != data['target'] or e['model_id'] != model['id'] or e['run_id'] != run['id']:
            raise ValueError('Estimate model/run/target mismatch')
    return data, len(raw)


def release(path, apply=False, activate=False):
    data, size = read_release(path)
    report = {'destination': DESTINATION_REF, 'target': data['target'], 'bytes': size,
              'rows': {n: len(data[n]) for n in NAMES}, 'applied': False}
    if not apply:
        if activate: raise ValueError('Activation requires --apply')
        return report
    engine = make_engine()
    try:
        identity = (engine.url.host or '') + ' ' + (engine.url.username or '')
        if engine.dialect.name != 'postgresql' or DESTINATION_REF not in identity:
            raise ValueError('Only the user-owned APPA Sample destination is permitted')
        tables = Base.metadata.tables
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL statement_timeout = '20s'"))
            dbsize = conn.scalar(text('select pg_database_size(current_database())'))
            if dbsize + size * 3 > 200 * 1024 * 1024:
                raise ValueError('Destination exceeds conservative disk budget')
            ids = set(conn.scalars(select(tables['photos'].c.id)))
            if ids != {e['photo_id'] for e in data['estimates']}:
                raise ValueError('Release does not match the current 100-photo sample')
            # All crops, source snapshots and optional references must pre-exist.
            for name, wanted in [('input_assets', {e['evidence']['input_asset_id'] for e in data['estimates']}),
                                 ('catalog_snapshots', {e['evidence']['catalog_snapshot_id'] for e in data['estimates']}),
                                 ('satellite_matchups', {e['matchup_id'] for e in data['estimates'] if e['matchup_id']})]:
                found = set(conn.scalars(select(tables[name].c.id).where(tables[name].c.id.in_(wanted))))
                if found != wanted: raise ValueError(f'Missing existing dependency: {name}')
            added = {}
            for name in NAMES:
                table = tables[name]; rows = data[name]
                prior = {r['id']: dict(r) for r in conn.execute(select(table).where(table.c.id.in_([r['id'] for r in rows]))).mappings()}
                for row in rows:
                    existing = prior.get(row['id'])
                    if existing and name == 'prediction_runs' and existing['status'] == 'complete':
                        existing = {**existing, 'status': 'pending_release', 'completed_at': None}
                    if existing is not None and existing != row:
                        raise ValueError(f'Conflicting immutable record in {name}')
                missing = [r for r in rows if r['id'] not in prior]
                if missing: conn.execute(table.insert(), missing)
                added[name] = len(missing)
            # Verify exact saved floats, feature proofs and reference-free serving
            # in the transaction; any mismatch rolls back this entire small release.
            from sqlalchemy.orm import Session
            from .db import Estimate, Photo, ModelVersion, InputAsset
            supported = {True: 0, False: 0}
            with Session(bind=conn) as session:
                # Keep strong references so the identity map can serve verification
                # without hundreds of repeated network queries to the pooler.
                models = session.scalars(select(ModelVersion).where(ModelVersion.id == data['model_versions'][0]['id'])).all()
                photos = {p.id: p for p in session.scalars(select(Photo).where(Photo.id.in_(ids))).all()}
                assets = session.scalars(select(InputAsset).where(InputAsset.id.in_({e['evidence']['input_asset_id'] for e in data['estimates']}))).all()
                estimates = {e.id: e for e in session.scalars(select(Estimate).where(Estimate.run_id == data['prediction_runs'][0]['id'])).all()}
                for row in data['estimates']:
                    e = estimates[row['id']]
                    if e.value != row['value'] or e.evidence != row['evidence']:
                        raise ValueError('Estimate did not round-trip exactly')
                    confidence = saved_confidence(session, e, photos[e.photo_id])
                    if not confidence: raise ValueError('Missing confidence contract')
                    if confidence['status'] == 'available': supported[e.matchup_id is not None] += 1
                    elif confidence['reason'] != 'Too little reliable held-out evidence supports this confidence level.':
                        raise ValueError(confidence['reason'])
            if activate:
                run = tables['prediction_runs']
                conn.execute(update(run).where(run.c.id == data['prediction_runs'][0]['id'], run.c.status == 'pending_release')
                             .values(status='complete', completed_at=utcnow()))
            status = conn.scalar(select(tables['prediction_runs'].c.status).where(tables['prediction_runs'].c.id == data['prediction_runs'][0]['id']))
        return {**report, 'applied': True, 'added': added, 'status': status, 'database_bytes_before': dbsize,
                'confidence_with_reference': supported[True], 'confidence_without_reference': supported[False]}
    finally:
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path'); parser.add_argument('--apply', action='store_true'); parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    print(json.dumps(release(args.path, args.apply, args.activate), indent=2))
