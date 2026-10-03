"""Verify fixed-commit original sources without changing any bytes."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent.parent
manifest=json.loads((ROOT/'worker-audit-source-review/expected_source_manifest.json').read_text());out=[]
for item in manifest:
    p=ROOT/'worker-audit-original'/item['path'];raw=p.read_bytes()
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    out.append(dict(**item,bytes=len(raw),actual_git_blob=blob,matched=blob==item['expected_git_blob'],sha256=hashlib.sha256(raw).hexdigest()))
(ROOT/'worker-audit-source-review/source_manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('Verified',sum(x['matched'] for x in out),'/',len(out),'files against fixed commit 405f3041fdd76977f625d50c558c63dbf342699d')
assert all(x['matched'] for x in out),[x['path'] for x in out if not x['matched']]
