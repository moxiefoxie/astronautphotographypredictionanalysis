"""Transfer at most 100 Mediterranean photos to the user's APPA database.

Default is a local-only preflight. --apply requires a recovered destination with
verified disk headroom. No overlays, image bytes, jobs, or full-catalog transfer.
"""
import argparse
import hashlib
import json
import time
from sqlalchemy import select, create_engine, text
from sqlalchemy.dialects.postgresql import insert
from .db import Base, PROJECT, make_engine

DESTINATION_REF = 'qcjkgrelvnivgpfwrfan'
MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_SAMPLE_PHOTOS = 100


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def load_records(source, sample_size=100):
    if not 2 <= sample_size <= MAX_SAMPLE_PHOTOS:
        raise ValueError('Sample size must be between 2 and 100 photos')
    t = Base.metadata.tables
    with source.connect() as src:
        run = src.execute(select(t['prediction_runs']).where(t['prediction_runs'].c.kind == 'mediterranean_import')
                          .order_by(t['prediction_runs'].c.created_at.desc())).mappings().first()
        if not run:
            raise ValueError('Import the verified Mediterranean export locally first')
        estimates = [dict(r) for r in src.execute(select(t['estimates']).where(t['estimates'].c.run_id == run['id'])).mappings()]
        groups = {True: set(), False: set()}
        for row in estimates:
            groups[row['matchup_id'] is not None].add(row['photo_id'])
        if groups[True] & groups[False]:
            raise ValueError('Inconsistent reference eligibility across targets')
        rank = lambda pid: hashlib.sha256(('appa-sample-v1:' + pid).encode()).hexdigest()
        ids = sorted(groups[True], key=rank)[:sample_size//2] + sorted(groups[False], key=rank)[:sample_size-sample_size//2]
        if len(ids) != sample_size:
            raise ValueError('Not enough photos in both reference groups')
        chosen = [r for r in estimates if r['photo_id'] in set(ids)]
        if len(chosen) != sample_size * 2 or any({r['target'] for r in chosen if r['photo_id'] == pid} != {'chlor_a','kd_490'} for pid in ids):
            raise ValueError('Every sample photo must have exactly two target predictions')
        sample_id = 'med-sample-' + digest({'source_run':run['id'],'ids':sorted(ids),'version':1})[:24]
        sample_run = dict(run)
        sample_run['id'] = sample_id
        sample_run['provenance'] = {**run['provenance'], 'source_run_id':run['id'],
            'split_counts':{'test':sample_size},
            'sample':{'size':sample_size,'source_photos':len(groups[True])+len(groups[False]),
                'with_reference':sample_size//2,'inference_only':sample_size-sample_size//2,
                'method':'Deterministic SHA-256 rank within balanced reference-availability groups; demonstration sample, not a representative accuracy study.'}}
        for row in chosen:
            original_id = row['id']
            row['id'] = digest({'sample':sample_id,'source_estimate':original_id})
            row['run_id'] = sample_id
            row['evidence'] = {**row['evidence'],'source_estimate_id':original_id,'source_run_id':run['id'],'sample_run_id':sample_id}
        keys = {
            'photos':set(ids), 'model_versions':{r['model_id'] for r in chosen},
            'satellite_matchups':{r['matchup_id'] for r in chosen if r['matchup_id']},
            'catalog_snapshots':{r['evidence']['catalog_snapshot_id'] for r in chosen},
            'input_assets':{r['evidence']['input_asset_id'] for r in chosen}}
        records = {'prediction_runs':[sample_run], 'estimates':chosen}
        for name, wanted in keys.items():
            records[name] = [dict(r) for r in src.execute(select(t[name]).where(t[name].c.id.in_(wanted))).mappings()]
            if len(records[name]) != len(wanted):
                raise ValueError(f'Missing sample dependency in {name}')
        tables = {table:records[table.name] for table in Base.metadata.sorted_tables if table.name in records}
    total = sum(len(json.dumps(row).encode()) for rows in tables.values() for row in rows)
    if total > MAX_IMPORT_BYTES:
        raise ValueError('Sample exceeds 2 MiB payload budget; reduce sample size')
    return tables, total


def transfer(apply=False, sample_size=100):
    source = create_engine(f'sqlite:///{PROJECT / "runtime/dashboard.db"}')
    try:
        tables, total = load_records(source, sample_size)
    finally:
        source.dispose()
    report = {'applied':False, 'destination':DESTINATION_REF,'sample_photos':sample_size,
              'source_bytes':total,'max_source_bytes':MAX_IMPORT_BYTES,
              'tables':{t.name:len(rows) for t,rows in tables.items()},
              'omitted':['overlays','image bytes','jobs','annotations','calibrations','all unsampled photos']}
    # Preflight does not connect to or query the recovering cloud database.
    if not apply:
        return report
    target = make_engine()
    try:
        if target.dialect.name != 'postgresql':
            raise ValueError('Destination must be PostgreSQL')
        identity = (target.url.host or '') + ' ' + (target.url.username or '')
        if DESTINATION_REF not in identity:
            raise ValueError('Only the user-owned APPA Sample destination is permitted')
        with target.connect() as dest:
            if dest.scalar(text("select current_setting('transaction_read_only')")) != 'off':
                raise ValueError('Destination is read-only; no import attempted')
            size = dest.scalar(text('select pg_database_size(current_database())'))
            if size + total * 3 > 200 * 1024 * 1024:
                raise ValueError('Destination exceeds conservative sample database budget; no rows written')
        added = {}
        for table, rows in tables.items():
            added[table.name] = 0
            for start in range(0,len(rows),10):
                batch = rows[start:start+10]
                with target.begin() as dest:
                    prior = {r['id']:dict(r) for r in dest.execute(select(table).where(table.c.id.in_([r['id'] for r in batch]))).mappings()}
                    if any(r['id'] in prior and prior[r['id']] != r for r in batch):
                        raise ValueError(f'Conflicting {table.name} record; batch rolled back')
                    missing = [r for r in batch if r['id'] not in prior]
                    if missing:
                        dest.execute(insert(table),missing)
                        added[table.name] += len(missing)
                if missing:
                    time.sleep(1)
        return {**report,'applied':True,'added':added}
    finally:
        target.dispose()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--sample-size',type=int,default=100)
    args=parser.parse_args()
    print(json.dumps(transfer(args.apply,args.sample_size),indent=2))
