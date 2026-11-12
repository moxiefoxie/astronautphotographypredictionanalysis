"""Read Johann's live catalog into append-only APPA source snapshots.

Default scope is existing APPA photo IDs, not the million-photo archive.
Requires a separate SOURCE_DATABASE_URL for Johann's project.
Never issues writes to public.astronaut_photos. Does not queue inference.
"""
import json
import os
from sqlalchemy import select, text, bindparam
from .db import Session, Photo, CatalogSnapshot, make_engine
from .import_mediterranean import SOURCE, digest


def sync_catalog(session_factory=Session, source_engine=None):
    url = os.environ.get('SOURCE_DATABASE_URL')
    if source_engine is None and not url:
        raise ValueError('Johann’s read-only SOURCE_DATABASE_URL is required; the app DATABASE_URL is a different project')
    source_engine = source_engine or make_engine(url)
    if source_engine.dialect.name != 'postgresql': raise ValueError('Source must be PostgreSQL')
    if 'zwdkkwbxlsrlqsqjfdht' not in ((source_engine.url.username or '')+' '+(source_engine.url.host or '')):
        raise ValueError('Source must be Johann’s Geolocation project')
    with session_factory() as s:
        ids = s.scalars(select(Photo.id).order_by(Photo.id)).all()
    added, found = 0, 0
    query = text('SELECT to_jsonb(p) AS data FROM public.astronaut_photos p WHERE photo_id IN :ids ORDER BY photo_id').bindparams(bindparam('ids', expanding=True))
    # Bounded primary-key lookups; no OFFSET scan or unrestricted archive copy.
    for start in range(0, len(ids), 250):
        with source_engine.connect() as c:
            c.execute(text('SET TRANSACTION READ ONLY'))
            c.execute(text("SET LOCAL statement_timeout = '30s'"))
            records = [row.data for row in c.execute(query, {'ids': ids[start:start+250]})]
        found += len(records)
        with session_factory.begin() as s:
            for row in records:
                snapshot_id = digest({'source': SOURCE, 'row': row})
                if not s.get(CatalogSnapshot, snapshot_id):
                    s.add(CatalogSnapshot(id=snapshot_id, photo_id=row['photo_id'], source=SOURCE, data=row))
                    added += 1
    return {'requested': len(ids), 'found': found, 'missing': len(ids)-found, 'new_snapshots': added,
            'source': SOURCE, 'canonical_metadata_changed': False, 'inference_queued': False}


if __name__ == '__main__':
    print(json.dumps(sync_catalog(), indent=2))
