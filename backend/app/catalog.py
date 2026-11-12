"""Trusted local catalog ingestion and batch queuing for photos without satellite labels.

This CLI is for operators, not an HTTP file-upload endpoint. Source files stay local.
"""
import argparse
import csv
import hashlib
import json
import re
import uuid
from pathlib import Path
from datetime import datetime
from sqlalchemy import select
from .db import WORKSPACE, Session, Photo, ModelVersion, initialize
from .import_benchmark import number
from .queue import enqueue

ID = re.compile(r'^(ISS\d{3})-([A-Z0-9]+)-(\d+)$')

def ingest(path, session_factory=Session):
    from PIL import Image
    with Path(path).open(newline='') as f:
        records = list(csv.DictReader(f))
    if not records or len(records) > 10000: raise ValueError('Provide 1–10,000 catalog rows per import')
    source_hash = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    prepared = []
    seen = set()
    for r in records:
        image_id = r['image_id']
        match = ID.fullmatch(image_id)
        if not match or image_id in seen: raise ValueError('Invalid or duplicate NASA image ID')
        seen.add(image_id)
        source = (WORKSPACE / r['local_image']).resolve()
        if not source.is_relative_to(WORKSPACE) or not source.is_file():
            raise ValueError('Each source image must exist under NASA_WORKSPACE')
        if source.suffix.lower() not in {'.png', '.jpg', '.jpeg'}: raise ValueError('PNG or JPEG source required')
        with Image.open(source) as im:
            if min(im.size) < 32 or im.width * im.height > 40_000_000:
                raise ValueError('Image dimensions outside supported limits')
            rgb = im.convert('RGB')
            digest = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        captured = r.get('captured_at') or r.get('photo_datetime')
        if captured:
            dt = datetime.fromisoformat(captured.replace('Z', '+00:00'))
            if dt.utcoffset() is None: raise ValueError('Photo time must include a UTC offset')
            from datetime import timezone
            captured = dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
        lat, lon = number(r.get('latitude')), number(r.get('longitude'))
        if lat is not None and not -90 <= lat <= 90: raise ValueError('Latitude out of range')
        if lon is not None and not -180 <= lon <= 180: raise ValueError('Longitude out of range')
        meta = {key: number(r.get(key)) for key in ['cloud_percent', 'sun_elevation', 'sun_azimuth', 'focal_length']}
        if meta['cloud_percent'] is not None and not 0 <= meta['cloud_percent'] <= 30:
            raise ValueError('Known cloud cover must be 0–30%, matching the benchmark eligibility rule')
        if meta['sun_elevation'] is not None and not 0 < meta['sun_elevation'] <= 90:
            raise ValueError('Only daylight images are supported by this catalog importer')
        for key in ['scene_group', 'calibration_domain', 'independence_review']:
            if r.get(key): meta[key] = r[key].strip()
        meta['catalog_source_sha256'] = source_hash
        meta['domain_review'] = 'Operator must verify ocean content; no validated automatic water mask'
        mission, roll, frame = match.groups()
        prepared.append(Photo(id=image_id, mission=mission, captured_at=captured, latitude=lat, longitude=lon,
            local_image=str(source), image_sha256=digest, metadata_json=meta,
            thumbnail_url=f'https://eol.jsc.nasa.gov/DatabaseImages/ESC/small/{mission}/{image_id}.JPG',
            image_url=f'https://eol.jsc.nasa.gov/DatabaseImages/ESC/large/{mission}/{image_id}.JPG',
            original_url=f'https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission={mission}&roll={roll}&frame={frame}'))
    added = 0
    with session_factory.begin() as s:
        for photo in prepared:
            prior = s.get(Photo, photo.id)
            if prior:
                if prior.image_sha256 != photo.image_sha256: raise ValueError('Existing photo ID has different image bytes')
                continue
            s.add(photo); added += 1
    return {'added': added, 'photo_ids': [p.id for p in prepared]}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    ingest_parser = sub.add_parser('ingest'); ingest_parser.add_argument('csv')
    queue_parser = sub.add_parser('queue')
    queue_parser.add_argument('--image-id', action='append', required=True)
    queue_parser.add_argument('--model-id', action='append', required=True)
    queue_parser.add_argument('--batch-key', required=True, help='Reuse exactly this key to resume without duplicates')
    args = p.parse_args(); initialize()
    if args.command == 'ingest': print(json.dumps(ingest(args.csv), indent=2))
    else:
        for photo_id in args.image_id:
            key = hashlib.sha256(json.dumps([args.batch_key, photo_id, sorted(args.model_id)]).encode()).hexdigest()
            job = enqueue(photo_id, args.model_id, key)
            print(json.dumps({'photo_id': photo_id, 'job_id': job.id, 'status': job.status}))
