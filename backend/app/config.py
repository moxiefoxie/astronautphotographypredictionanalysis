"""Load literal local KEY=VALUE settings without shell execution or interpolation."""
import os
from pathlib import Path

KEYS = {'DATABASE_URL', 'NASA_WORKSPACE', 'RUNTIME_DIR', 'OPERATOR_API_KEY', 'ALLOWED_ORIGINS', 'DB_AUTO_CREATE', 'INFERENCE_ENABLED'}

def load_local_settings(project: Path):
    path = project / '.env'
    if os.environ.get('VERCEL') or not path.is_file():
        return
    for line in path.read_text().splitlines():
        key, separator, value = line.strip().partition('=')
        key = key.strip()
        if not separator or key not in KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] in {'"', "'"} and value[-1] == value[0]:
            value = value[1:-1]
        if value:
            os.environ.setdefault(key, value)
