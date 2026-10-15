"""Verify the exact saved delivery, offline, without changing its files."""
import hashlib, json
from pathlib import Path
root = Path(__file__).resolve().parent
manifest = json.loads((root / 'MANIFEST_SHA256.json').read_text(encoding='utf-8'))
errors = []
for name, expected in manifest['files'].items():
    p = root / name
    if not p.is_file():
        errors.append(f'Missing: {name}'); continue
    raw = p.read_bytes()
    if len(raw) != expected['bytes'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
        errors.append(f'Mismatch: {name}')
extras = sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and str(p.relative_to(root)) not in manifest['files'] and p.name != 'MANIFEST_SHA256.json' and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts)
print(json.dumps({'ok': not errors, 'verified_files': len(manifest['files']), 'errors': errors, 'extra_files_not_covered': extras}, ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
