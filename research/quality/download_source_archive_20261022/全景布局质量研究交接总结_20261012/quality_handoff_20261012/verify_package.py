"""Read-only check of every payload file; Python standard library only."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
manifest=json.loads((root/'FILE_MANIFEST_SHA256.json').read_text(encoding='utf-8'))
for row in manifest['files']:
 p=root/row['path']; assert p.is_file(),f'Missing: {p}'
 b=p.read_bytes();assert len(b)==row['bytes'],f'Size mismatch: {p}'
 assert hashlib.sha256(b).hexdigest()==row['sha256'],f'Hash mismatch: {p}'
print(f"PASS: {len(manifest['files'])} files")
