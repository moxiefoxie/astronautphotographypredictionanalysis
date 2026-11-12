"""Inference only: load trusted frozen checkpoints, never fit and never use satellite labels."""
import hashlib
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
from .db import WORKSPACE

ROOT = WORKSPACE / 'sammy_ocean_color_models'

def metadata_features(photo):
    dt = pd.to_datetime(photo.captured_at, utc=True, errors='coerce')
    lat, lon = photo.latitude, photo.longitude
    lon = np.radians(lon) if lon is not None and -180 <= lon <= 180 else np.nan
    output = {'latitude': lat if lat is not None and -90 <= lat <= 90 else np.nan,
              'longitude_sin': np.sin(lon), 'longitude_cos': np.cos(lon)}
    for name, value, period in [('season', dt.dayofyear if not pd.isna(dt) else np.nan, 365.25),
                                ('hour', dt.hour + dt.minute / 60 if not pd.isna(dt) else np.nan, 24)]:
        output[name + '_sin'] = np.sin(2 * np.pi * value / period)
        output[name + '_cos'] = np.cos(2 * np.pi * value / period)
    for key in ['cloud_percent', 'sun_elevation', 'sun_azimuth', 'focal_length']:
        output[key] = photo.metadata_json.get(key) if photo.metadata_json.get(key) is not None else np.nan
    if not 0 <= output['cloud_percent'] <= 100: output['cloud_percent'] = np.nan
    if not -90 <= output['sun_elevation'] <= 90: output['sun_elevation'] = np.nan
    output['focal_length'] = np.log1p(output['focal_length']) if output['focal_length'] > 0 else np.nan
    return output

class Predictor:
    def __init__(self):
        self.models = {}

    def predict(self, photo, versions):
        import joblib
        import torch
        from torchvision import transforms
        from threadpoolctl import threadpool_limits
        from .import_benchmark import sha
        # Paths only come from the trusted importer; HTTP callers cannot submit paths/URLs.
        path = Path(photo.local_image or '').resolve()
        if not path.is_relative_to(WORKSPACE) or not path.is_file():
            raise ValueError('Source image is not available in the worker workspace')
        with Image.open(path) as im:
            rgb_image = im.convert('RGB')
        # Manifest hashes are of decoded RGB bytes (the training pipeline's contract).
        pixel_hash = hashlib.sha256(str(rgb_image.size).encode() + rgb_image.tobytes()).hexdigest()
        if photo.image_sha256 and pixel_hash != photo.image_sha256:
            raise ValueError('Source image hash differs from the frozen input')
        meta = metadata_features(photo)
        sys.path.insert(0, str(WORKSPACE / 'quick_chl_kd_baseline'))
        from run_baseline import extract_image_features
        features = extract_image_features(rgb_image, .85)
        results = []
        for version in versions:
            if version.id not in self.models:
                for relative, expected in version.manifest['artifact_sha256'].items():
                    if sha(WORKSPACE / relative) != expected:
                        raise ValueError('Model or preprocessing code changed; register a new version')
                target = version.target
                if version.name == 'small_cnn_metadata':
                    sys.path.insert(0, str(ROOT))
                    from deep_models import SmallCNN
                    saved = torch.load(ROOT / 'checkpoints' / f'{target}_small_cnn.pt', map_location='cpu', weights_only=True)
                    network = SmallCNN(saved['metadata_width'])
                    network.load_state_dict(saved['state_dict'])
                    self.models[version.id] = (network.eval(), joblib.load(ROOT / 'checkpoints' / f'{target}_cnn_metadata.joblib'))
                else:
                    bundle = joblib.load(ROOT / 'checkpoints' / f'{target}_models.joblib')
                    item = bundle['candidates'][version.name]
                    if item['feature_set'] != 'rgb_metadata':
                        raise ValueError('Unsupported selected feature set')
                    self.models[version.id] = item['model']
            schema = version.manifest['feature_schema']
            m = np.array([[meta[c] for c in schema['metadata_columns']]], dtype='float32')
            if version.name == 'small_cnn_metadata':
                network, preprocessor = self.models[version.id]
                transform = transforms.Compose([transforms.Resize((96, 96)), transforms.ToTensor(),
                    transforms.Normalize([.485, .456, .406], [.229, .224, .225])])
                with torch.inference_mode():
                    log_value = network(transform(rgb_image).unsqueeze(0), torch.tensor(preprocessor.transform(m), dtype=torch.float32)).item()
            else:
                x = np.column_stack([np.array([[features[c] for c in schema['rgb_columns']]], dtype='float32'), m])
                with threadpool_limits(limits=4):
                    log_value = float(self.models[version.id].predict(x)[0])
            value = float(10 ** log_value)
            if not np.isfinite(value) or value <= 0:
                raise ValueError('Model returned a nonfinite or nonpositive estimate')
            results.append({'model_id': version.id, 'target': version.target, 'value': value,
                'evidence': {'source': 'checkpoint_inference', 'image_sha256': pixel_hash,
                    'input_metadata': {k: v if np.isfinite(v) else None for k, v in meta.items()},
                    'confidence': None, 'missing_metadata': [k for k, v in meta.items() if not np.isfinite(v)]}})
        return results
