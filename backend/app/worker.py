"""Run independently from the web API: python -m app.worker [--once]."""
import argparse
import logging
import time
import sys
import importlib.metadata
from .db import Session, initialize, Photo, ModelVersion, Run
from .queue import claim, finish

def run_one(predictor, session_factory=Session, overlay_predictor=None):
    job = claim(session_factory)
    if not job: return None
    try:
        with session_factory() as s:
            photo = s.get(Photo, job.photo_id)
            versions = [s.get(ModelVersion, mid) for mid in job.model_ids]
        started = time.perf_counter()
        outputs = predictor.predict(photo, versions)
        packages = {}
        for package in ['numpy', 'pandas', 'Pillow', 'joblib', 'scikit-learn', 'scipy', 'torch', 'torchvision']:
            try: packages[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError: packages[package] = None
        runtime = {'python': sys.version.split()[0], 'packages': packages, 'duration_seconds': time.perf_counter() - started}
        for output in outputs:
            output['evidence']['runtime'] = runtime
        accepted = finish(job, outputs, session_factory=session_factory)
        logging.info('Job %s completion accepted=%s', job.id, accepted)
        if accepted and overlay_predictor:
            try:
                overlay_predictor.generate(photo, session_factory)
                overlay_status = 'complete'
            except Exception:
                logging.exception('Spatial artifact generation failed for %s; retry with app.overlays', photo.id)
                overlay_status = 'failed; retry with app.overlays'
            with session_factory.begin() as s:
                run = s.get(Run, job.run_id)
                run.provenance = {**run.provenance, 'overlay_status': overlay_status}
    except Exception as exc:
        # Local logs keep diagnostic detail; the read API never exposes filesystem paths.
        logging.exception('Job %s failed', job.id)
        finish(job, error=f'{type(exc).__name__}: inference failed; inspect worker logs', session_factory=session_factory)
    return job.id

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    initialize()
    from .inference import Predictor
    predictor = Predictor()
    from .overlays import OverlayPredictor
    overlay_predictor = OverlayPredictor()
    while True:
        completed = run_one(predictor, overlay_predictor=overlay_predictor)
        if args.once: break
        if completed is None: time.sleep(2)
