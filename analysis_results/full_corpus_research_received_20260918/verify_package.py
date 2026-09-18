"""Verify the restored package using only Python's standard library."""
from pathlib import Path
import hashlib,json,sys

def main()->int:
    root=Path(__file__).resolve().parent
    manifest=json.loads((root/'MANIFEST_SHA256.json').read_text(encoding='utf-8'))
    bad=[]
    for entry in manifest['files']:
        path=root/entry['path']
        if not path.is_file():bad.append((entry['path'],'missing'));continue
        h=hashlib.sha256()
        with path.open('rb')as f:
            for b in iter(lambda:f.read(1048576),b''):h.update(b)
        if path.stat().st_size!=entry['bytes']or h.hexdigest()!=entry['sha256']:bad.append((entry['path'],'mismatch'))
    print(json.dumps({'checked_files':len(manifest['files']),'all_passed':not bad,'problems':bad},ensure_ascii=False,indent=2))
    return 1 if bad else 0
if __name__=='__main__':sys.exit(main())
