#!/usr/bin/env python3
"""Create a small classification delivery, keeping source-stage identities.

This package contains no original image collection, old fusion cache or venv.
The three illustrative figures are copies of the parent study's new evidence.
"""
import csv,hashlib,json,zipfile
from pathlib import Path
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
EXCLUDE={'SEMI_REDUNDANCY_GROUP_RECORD_OPPORTUNITIES.csv'}
ARCHIVE='HOHONET_人员分类与楼外原答证据_v3_20261021.zip'

def main():
    freeze=json.loads((HERE/'LABEL_FREEZE.json').read_text())
    for name,want in freeze['files'].items():
        got=hashlib.sha256((HERE/name).read_bytes()).hexdigest()
        assert got==want,(name,got,want)
    files=[p for p in HERE.iterdir() if p.is_file() and p.name not in EXCLUDE and p.suffix not in ['.log','.zip','.partial']
           and p.name not in ['DELIVERY_MANIFEST.csv','DELIVERY_RECEIPT.json']]
    images=sorted((ROOT/'evidence/figures').glob('V3_RAW_*/raw_three_views.png'))
    files+=images
    manifest=[]
    for p in sorted(files):
        rows=None
        if '.csv' in p.suffixes:
            rows=len(pd.read_csv(p))
        manifest.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,rows=rows,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            stage='new_frozen_labels' if p.name in freeze['files'] else 'new_annotation_case' if p in images else 'new_discovery_or_raw_validation'))
    with (HERE/'DELIVERY_MANIFEST.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(manifest[0]));w.writeheader();w.writerows(manifest)
    files.append(HERE/'DELIVERY_MANIFEST.csv')
    dest=HERE/ARCHIVE
    with zipfile.ZipFile(dest.with_suffix('.zip.partial'),'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(files):z.write(p,p.relative_to(ROOT))
    dest.with_suffix('.zip.partial').replace(dest)
    with zipfile.ZipFile(dest) as z:assert z.testzip() is None
    receipt=dict(archive=ARCHIVE,bytes=dest.stat().st_size,files=len(files),
        sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),standalone_report='taxonomy/REPORT_ZH.md',
        standalone_personnel=['taxonomy/MANUAL_LABELS_EXPLAINED.csv','taxonomy/SEMI_LABELS_EXPLAINED.csv'],
        excludes=['development_checkpoints','__pycache__','logs','original image collection','original evidence database','historical full-team caches'])
    (HERE/'DELIVERY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
