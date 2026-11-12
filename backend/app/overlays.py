"""Offline, reproducible experimental maps. No semantic or uncertainty claims."""
import argparse
import base64
import hashlib
import io
import json
import sys
import zlib
from pathlib import Path
from sqlalchemy import select
from .db import WORKSPACE, Session, Photo, Overlay, initialize
from .import_benchmark import sha

class OverlayPredictor:
    def __init__(self):
        import joblib
        import numpy as np
        import pandas as pd
        root = WORKSPACE / 'sammy_ocean_color_models'
        sys.path.insert(0, str(root))
        from pixel_heatmaps import load_pixel_rgb, predict_pixel_map
        self.load_rgb, self.predict_map = load_pixel_rgb, predict_pixel_map
        self.models = {}
        manifest = pd.read_csv(root / 'results/manifest.csv')
        for target in ['chlor_a', 'kd_490']:
            checkpoint = root / 'results/pixel_experiment' / f'{target}_pixel_models.joblib'
            bundle = joblib.load(checkpoint)
            hashes = {p.name: sha(p) for p in [checkpoint, root / 'pixel_heatmaps.py', Path(__file__), root / 'results/manifest.csv']}
            version = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
            scale = np.quantile(np.log10(manifest.loc[manifest.split.eq('train'), target]), [.02, .98]).tolist()
            self.models[target] = (bundle['candidates'][bundle['selected']], version, {
                'name': bundle['selected'], 'artifact_sha256': hashes, 'display_log10_range': scale,
                'scale_source': 'Training photo labels: 2nd–98th percentiles; fixed across photos',
                'units': 'mg/m³' if target == 'chlor_a' else 'm⁻¹', 'status': 'experimental',
                'pixel_accuracy_validated': False, 'semantic_mask': False,
                'limitations': 'Photo-label-trained RGB map from a separate model. Does not spatially explain the main estimate. Transparent pixels exclude only very dark or saturated RGB; land, cloud and glint may remain.',
                'coordinate_system': 'Decoded source image pixels, normalized x/y; no geographic registration',
            })

    def generate(self, photo, session_factory=Session):
        import numpy as np
        from PIL import Image
        from matplotlib import colormaps
        path = Path(photo.local_image or '').resolve()
        if not path.is_relative_to(WORKSPACE) or not path.is_file():
            raise ValueError('Source image unavailable')
        with Image.open(path) as image:
            source = image.convert('RGB')
        digest = hashlib.sha256(str(source.size).encode() + source.tobytes()).hexdigest()
        if not photo.image_sha256 or digest != photo.image_sha256:
            raise ValueError('Source image hash mismatch')
        rgb = self.load_rgb(path)
        preview = io.BytesIO()
        Image.fromarray(np.round(rgb * 255).astype('uint8')).save(preview, format='PNG')
        count = 0
        for target, (candidate, version, metadata) in self.models.items():
            oid = hashlib.sha256(json.dumps([photo.id, digest, target, version]).encode()).hexdigest()
            with session_factory() as s:
                if s.get(Overlay, oid): continue
            values, keep = self.predict_map(candidate, rgb)
            valid = keep & np.isfinite(values)
            low, high = metadata['display_log10_range']
            rgba = colormaps['viridis'](np.clip(np.nan_to_num((values-low)/(high-low)), 0, 1), bytes=True)
            rgba[..., 3] = np.where(valid, 255, 0)
            png = io.BytesIO(); Image.fromarray(rgba).save(png, format='PNG')
            grid = np.round(values, 5).astype(object)
            grid[~np.isfinite(values)] = None
            compressed_grid = base64.b64encode(zlib.compress(json.dumps(grid.tolist(), separators=(',', ':')).encode())).decode()
            with session_factory.begin() as s:
                if s.get(Overlay, oid): continue
                s.add(Overlay(id=oid, photo_id=photo.id, target=target, image_sha256=digest, model_version=version,
                    manifest={**metadata, 'width': values.shape[1], 'height': values.shape[0],
                              'source_width': source.width, 'source_height': source.height,
                              'retained_fraction': float(valid.mean())},
                    payload={'png_base64': base64.b64encode(png.getvalue()).decode(),
                             'source_png_base64': base64.b64encode(preview.getvalue()).decode(), 'grid_zlib_base64': compressed_grid}))
            count += 1
        return count

def generate_many(ids=None, limit=None):
    predictor = OverlayPredictor()
    with Session() as s:
        query = select(Photo).order_by(Photo.captured_at.desc(), Photo.id)
        if ids: query = query.where(Photo.id.in_(ids))
        if limit: query = query.limit(limit)
        photos = s.scalars(query).all()
    failed, total = [], 0
    for n, photo in enumerate(photos, 1):
        try: total += predictor.generate(photo)
        except Exception as exc:
            failed.append(photo.id); print(f'{photo.id}: {type(exc).__name__}', flush=True)
        if n % 100 == 0: print(json.dumps({'processed': n, 'added': total, 'failed': len(failed)}), flush=True)
    return {'processed': len(photos), 'added': total, 'failed': failed}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--photo-id', action='append')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args(); initialize()
    print(json.dumps(generate_many(args.photo_id, args.limit)))
