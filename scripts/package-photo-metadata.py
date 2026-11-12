"""Join saved NASA frame metadata by exact photo ID, without changing model inputs."""
import csv
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
ids = set(json.loads((ROOT/'src/native-photo-catalog.json').read_text()))
with sqlite3.connect(f'file:{ROOT}/runtime/dashboard.db?mode=ro', uri=True) as connection:
    ids.update(r[0] for r in connection.execute('select id from photos'))
for name in ['mediterranean_20261102/raw/photos.csv', 'high_density_20261109/raw/photos.csv']:
    with (WORKSPACE/name).open() as stream:
        ids.update(r['photo_id'] for r in csv.DictReader(stream))
existing = ROOT/'backend/app/photo-metadata.json'
metadata = {k:v for k,v in json.loads(existing.read_text()).items() if v.get('focal_length_source_url')} if existing.exists() else {}
sources = {}
for path in sorted((WORKSPACE/'frames').glob('*.ndjson')):
    used = False
    for line in path.open():
        row = json.loads(line)
        pid = '-'.join(str(row.get('frames.'+k, '')) for k in ['mission', 'roll', 'frame'])
        if pid not in ids: continue
        try: focal = float(row.get('frames.fclt', ''))
        except (ValueError, TypeError): continue
        if not 0 < focal < 10000: continue
        if pid in metadata and metadata[pid].get('focal_length_source_url'): continue
        if pid in metadata and metadata[pid]['focal_length'] != focal:
            raise ValueError(f'Conflicting focal lengths: {pid}')
        metadata[pid] = {'focal_length': focal, 'focal_length_source': 'NASA Gateway frames.fclt (saved catalog)', 'source_file': path.name}
        used = True
    if used: sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
(ROOT/'backend/app/photo-metadata.json').write_text(json.dumps(metadata, sort_keys=True, separators=(',', ':'))+'\n')
(ROOT/'docs/photo-metadata-provenance.json').write_text(json.dumps({'matched_photos': len(metadata), 'source_sha256': sources, 'purpose': 'Display-only NASA metadata enrichment; frozen inference inputs are unchanged.'}, indent=2)+'\n')
print(f'Packaged focal lengths for {len(metadata)} of {len(ids)} catalog photos')
