"""Package only the verified 100-photo sample as small static display previews.

Run with the existing Pillow/SQLAlchemy environment and DATABASE_URL=sqlite://.
No remote reads or database writes. These JPEGs are for display, not inference.
"""
import hashlib
import io
import json
from pathlib import Path
from PIL import Image
from sqlalchemy import create_engine
from app.db import PROJECT, WORKSPACE
from app.transfer import load_records

records, _ = load_records(create_engine(f'sqlite:///{PROJECT / "runtime/dashboard.db"}'))
assets = next(rows for table, rows in records.items() if table.name == 'input_assets')
assert len(assets) == 100
output = PROJECT / 'public/sample-previews'
output.mkdir(parents=True, exist_ok=True)
manifest = {}
total = 0
for asset in assets:
    path = Path(asset['local_path']).resolve()
    assert path.is_relative_to(WORKSPACE) and path.is_file(), asset['photo_id']
    original = path.read_bytes()
    with Image.open(io.BytesIO(original)) as image:
        rgb = image.convert('RGB')
        file_hash = hashlib.sha256(original).hexdigest()
        pixel_hash = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        # Both hash conventions exist in the frozen Mediterranean manifests.
        assert asset['image_sha256'] in {file_hash, pixel_hash}, asset['photo_id']
        rgb.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        preview = io.BytesIO()
        rgb.save(preview, format='JPEG', quality=85, optimize=True)
        content = preview.getvalue()
        assert len(content) < 512 * 1024, asset['photo_id']
        digest = hashlib.sha256(content).hexdigest()
        filename = f'{asset["photo_id"]}-{digest[:16]}.jpg'
        (output / filename).write_bytes(content)
        total += len(content)
        manifest[asset['photo_id']] = {'url': f'/sample-previews/{filename}',
            'asset_id': asset['id'], 'source_sha256': asset['image_sha256'],
            'preview_sha256': digest, 'width': rgb.width, 'height': rgb.height}
assert total < 15 * 1024 * 1024, 'Static sample exceeds its display-asset budget'
(PROJECT / 'src/sample-previews.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
print(json.dumps({'photos': len(manifest), 'preview_bytes': total, 'verified_source_hashes': True}))
