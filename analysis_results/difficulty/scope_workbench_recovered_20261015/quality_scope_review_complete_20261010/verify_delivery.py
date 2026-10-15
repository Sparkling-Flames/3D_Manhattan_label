#!/usr/bin/env python3
"""Read-only SHA256/size verification of the restored research bundle."""
from pathlib import Path
import argparse,hashlib,json

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent); a=ap.parse_args()
    root=a.root.resolve(); manifest=json.loads((root/'MANIFEST_SHA256.json').read_text(encoding='utf-8')); errors=[]
    for name,meta in manifest['files'].items():
        p=(root/name).resolve()
        if root not in p.parents:errors.append({'path':name,'error':'unsafe path'});continue
        if not p.is_file():errors.append({'path':name,'error':'missing'});continue
        data=p.read_bytes()
        if len(data)!=meta['bytes'] or hashlib.sha256(data).hexdigest()!=meta['sha256']:errors.append({'path':name,'error':'hash or size mismatch'})
    extras=sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and str(p.relative_to(root)) not in manifest['files'] and p.name!='MANIFEST_SHA256.json' and not {'__pycache__','.pytest_cache'}.intersection(p.parts))
    print(json.dumps({'passed':not errors,'verified_files':len(manifest['files']),'errors':errors,'extra_files_not_in_release_manifest':extras,'scope':'Saved file bytes only; this command does not rerun calculations.'},ensure_ascii=False,indent=2));raise SystemExit(bool(errors))
if __name__=='__main__':main()
