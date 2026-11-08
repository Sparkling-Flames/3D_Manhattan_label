"""Verify the delivered file manifest and snapshot-to-asset checksums."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'));errors=[]
for entry in manifest['files']:
    path=(root/entry['path']).resolve()
    if not path.is_relative_to(root):errors.append('Unsafe path: '+entry['path']);continue
    if not path.is_file():errors.append('Missing: '+entry['path']);continue
    if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:errors.append('Changed: '+entry['path'])
for path in sorted((root/'snapshots').glob('*/*.json')):
    s=json.loads(path.read_text(encoding='utf-8'));asset=root/'assets'/path.parent.name/s['asset_filename']
    if not asset.is_file() or hashlib.sha256(asset.read_bytes()).hexdigest()!=s['asset_sha256']:errors.append('Snapshot asset mismatch: '+str(path.relative_to(root)))
print(json.dumps({'passed':not errors,'checked_files':len(manifest['files']),'snapshots':len(list((root/'snapshots').glob('*/*.json'))),'errors':errors},ensure_ascii=False,indent=2))
sys.exit(bool(errors))
