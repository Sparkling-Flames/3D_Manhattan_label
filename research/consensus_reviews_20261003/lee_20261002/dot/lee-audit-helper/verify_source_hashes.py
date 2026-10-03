import json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent.parent
manifest=json.loads((root/'lee-audit-helper/SOURCE_MANIFEST.json').read_text())
for item in manifest['files']:
 data=(root/'lee-audit-original'/item['path']).read_bytes()
 assert len(data)==item['bytes'],item['path']
 assert hashlib.sha256(data).hexdigest()==item['sha256'],item['path']
 assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==item['git_sha1'],item['path']
print(f"Verified {len(manifest['files'])} immutable source/input/result files at {manifest['commit']}")
