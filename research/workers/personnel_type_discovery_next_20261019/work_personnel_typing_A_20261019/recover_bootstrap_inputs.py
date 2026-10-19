#!/usr/bin/env python3
"""Preserve current-main bytes and restore archive's older source pin separately."""
from pathlib import Path
import hashlib, json, shutil, urllib.request, urllib.parse
ROOT=Path(__file__).resolve().parent.parent
CURRENT=ROOT/'main_personnel_A_20261019'
OUT=ROOT/'work_personnel_typing_A_20261019'
DEST=OUT/'frozen_source_82c6164b'
PIN='82c6164b0d4630de5316199c92aa405930973168'
rows=json.loads((CURRENT/'research/workers/pro_personnel_v2_archive_20261019/SOURCE_FILES.json').read_text())
receipt=[]
for row in rows:
    src=CURRENT/row['path'];data=src.read_bytes()
    origin='current-main-identical'
    if hashlib.sha256(data).hexdigest()!=row['sha256']:
        url=f'https://raw.githubusercontent.com/Sparkling-Flames/3D_Manhattan_label/{PIN}/'+urllib.parse.quote(row['path'])
        data=urllib.request.urlopen(url,timeout=120).read(); origin='archive-pinned-history'
    assert hashlib.sha256(data).hexdigest()==row['sha256'],row['path']
    p=DEST/row['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    receipt.append(dict(row,restored_origin=origin))
(OUT/'input/FROZEN_SOURCE_RECOVERY.json').write_text(json.dumps({'frozen_source_pin':PIN,'current_main_preserved':True,'files':receipt},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'files_verified':len(receipt),'history_only':[r['path'] for r in receipt if r['restored_origin']=='archive-pinned-history']},ensure_ascii=False))
