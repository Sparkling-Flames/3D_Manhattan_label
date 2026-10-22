"""Verify the delivery before running scripts that regenerate output files."""
from pathlib import Path
import json,hashlib
O=Path(__file__).resolve().parent
m=json.loads((O/'MANIFEST.json').read_text());bad=[]
for f in m['files']:
 p=O/f['path']
 if not p.is_file() or p.stat().st_size!=f['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=f['sha256']:bad.append(f['path'])
expected={x['path'] for x in m['files']}|{'MANIFEST.json','MANIFEST.sha256'}
extra=sorted(str(p.relative_to(O)) for p in O.rglob('*') if p.is_file() and str(p.relative_to(O)) not in expected)
print(json.dumps({'checked_files':len(m['files']),'mismatches':bad,'extra_files':extra},indent=2))
raise SystemExit(bool(bad))
