"""Prepare cloud URLs and an upload manifest without changing local artifacts.

This command performs no network requests. Upload assets/details first and the
index last; verify object checksums before promoting the frontend.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return json.dumps(value, allow_nan=False, separators=(',', ':')).encode()


def prepare(source, output, base):
    if urlparse(base).scheme != 'https' or not urlparse(base).netloc:
        raise ValueError('An HTTPS object-storage prefix is required')
    base = base.rstrip('/')
    index = json.loads((source / 'release/index.json').read_text())
    if index['schema'] != 'appa-native-catalog-v1' or index['run']['state'] != 'complete':
        raise ValueError('Only a complete, verified catalog may be published')
    old_base = index['run']['asset_base_url'].rstrip('/')
    files = {}
    receipts = {}
    for path in (source / 'receipts').glob('*.json'):
        receipt = json.loads(path.read_text())
        if receipt['status'] == 'ready':
            if not all(receipt['checks'].values()):
                raise ValueError('Receipt checks failed')
            receipts[receipt['image_id']] = receipt
    if len(index['photos']) != len(receipts):
        raise ValueError('Catalog and ready receipt counts differ')

    def rewrite(value):
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        if isinstance(value, str) and value.startswith(old_base + '/'):
            return base + value[len(old_base):]
        return value

    def add(path, key, expected=None):
        size = path.stat().st_size
        sha = expected or digest(path.read_bytes())
        files[key] = {'source': str(path.resolve()), 'key': key, 'bytes': size, 'sha256': sha}

    output.mkdir(parents=True, exist_ok=True)
    photos = []
    for summary in index['photos']:
        receipt = receipts[summary['id']]
        for asset in receipt['files'].values():
            path = source / 'assets' / asset['file']
            if path.stat().st_size != asset['bytes']:
                raise ValueError('Asset size differs from verified receipt')
            add(path, 'assets/' + asset['file'], asset['sha256'])
        entry = summary['entry']
        relative = entry['detail_url'].removeprefix(old_base + '/')
        path = source / 'release' / relative
        if not path.resolve().is_relative_to((source / 'release').resolve()):
            raise ValueError('Invalid detail path')
        raw = path.read_bytes()
        if digest(raw) != entry['detail_sha256']:
            raise ValueError('Detail checksum differs from catalog')
        detail = rewrite(json.loads(raw))
        if detail['id'] != summary['id']:
            raise ValueError('Detail identity differs from catalog')
        raw = encode(detail)
        key = f'details/{summary["id"]}-{digest(raw)[:16]}.json'
        path = output / key
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
        add(path, key)
        photo = rewrite(summary)
        photo['entry'].update(detail_url=f'{base}/{key}', detail_sha256=digest(raw))
        photos.append(photo)
    run = {**index['run'], 'asset_base_url': base}
    for key, value in [('run.json', run), ('index.json', {**index, 'run': run, 'photos': photos})]:
        path = output / key
        path.write_bytes(encode(value))
        add(path, key)
    manifest = {'base_url': base, 'photos': len(photos), 'total_bytes': sum(f['bytes'] for f in files.values()),
                'publish_last': 'index.json', 'files': list(files.values())}
    (output / 'upload-manifest.private.json').write_bytes(encode(manifest))
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'} | {'objects': len(files)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    prepare(args.source, args.output, args.base_url)
