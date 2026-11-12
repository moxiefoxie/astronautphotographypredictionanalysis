"""Read a newly provisioned APPA credential without terminal echo; save only locally."""
import getpass
import json
import os
from pathlib import Path
from urllib.parse import quote

data=json.loads(getpass.getpass('APPA runtime configuration JSON (hidden): '))
ref='qcjkgrelvnivgpfwrfan'
if data['project_ref'] != ref: raise ValueError('Wrong destination project')
host=data['host']
if not host.endswith('.supabase.com'): raise ValueError('Unexpected pooler host')
url=f'postgresql://appa_runtime.{ref}:{quote(data["password"],safe="")}@{host}:6543/postgres?sslmode=require'
path=Path(__file__).resolve().parents[1]/'.env'
original=path.read_text() if path.exists() else ''
backup=path.with_name('.env.before-appa-runtime')
if not backup.exists():
    backup.write_text(original); backup.chmod(0o600)
lines=[l for l in original.splitlines() if not l.startswith(('DATABASE_URL=','DB_AUTO_CREATE='))]
lines += [f'DATABASE_URL="{url}"','DB_AUTO_CREATE=0']
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as f: f.write('\n'.join(lines)+'\n')
path.chmod(0o600)
print('Scoped APPA runtime connection saved to ignored .env; previous configuration backed up.')
