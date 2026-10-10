#!/usr/bin/env python3
"""Verify the published release's file hashes (Python standard library only)."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
errors=[];count=0
for line in (root/'CHECKSUMS_SHA256.txt').read_text(encoding='utf-8').splitlines():
    expected,name=line.split('  ',1);p=(root/name).resolve();count+=1
    if root not in p.parents:errors.append({'file':name,'reason':'unsafe path'});continue
    if not p.is_file():errors.append({'file':name,'reason':'missing'});continue
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    if h.hexdigest()!=expected:errors.append({'file':name,'reason':'SHA256 mismatch'})
print(json.dumps({'passed':not errors,'verified_files':count,'errors':errors},ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
