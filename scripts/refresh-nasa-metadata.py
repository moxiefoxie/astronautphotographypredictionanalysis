"""Refresh display metadata for the hosted photos from NASA, with bounded concurrency."""
import hashlib, json, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.nasa_metadata import parse_focal_length
path=ROOT/'backend/app/photo-metadata.json';metadata=json.loads(path.read_text())
ids=set(json.loads((ROOT/'src/sample-previews.json').read_text()))|set(json.loads((ROOT/'src/native-photo-catalog.json').read_text()))
cache=ROOT/'runtime/nasa-metadata';cache.mkdir(exist_ok=True)
def read(pid):
    mission,roll,frame=pid.split('-');url=f'https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission={mission}&roll={roll}&frame={frame}'
    file=cache/(pid+'.html')
    if not file.exists():
        r=httpx.get(url,timeout=20);r.raise_for_status();file.write_text(r.text)
    raw=file.read_text();focal=parse_focal_length(raw)
    if focal is None: return pid,None
    return pid,{'focal_length':focal,'focal_length_source':'NASA Gateway photo page','focal_length_source_url':url,
        'source_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'retrieved_at':datetime.now(timezone.utc).isoformat()}
with ThreadPoolExecutor(max_workers=3) as pool:
    futures={pid:pool.submit(read,pid) for pid in sorted(ids)}
    for pid,future in futures.items():
        try:
            _,data=future.result()
            if data:metadata[pid]=data
            else: print('No focal length:',pid,flush=True)
        except Exception as e: print('Unavailable:',pid,type(e).__name__,flush=True)
path.write_text(json.dumps(metadata,sort_keys=True,separators=(',',':'))+'\n')
print('Hosted photo coverage:',sum(pid in metadata for pid in ids),'/',len(ids))
