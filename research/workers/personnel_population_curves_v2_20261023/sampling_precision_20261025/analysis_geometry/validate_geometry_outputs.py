"""Read final delivered geometry tables through EOF; verify actual saved bytes."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import pandas as pd
from PIL import Image
from safe_io import atomic_bytes,install_safe_csv_writer
install_safe_csv_writer()

EXPECTED={
    'GEOMETRY_PATH_PRECISION.csv.gz':108470,
    'GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz':36340,
    'GEOMETRY_UNCOMPUTED_LINKS.csv.gz':0,
    'EXACT_GEOMETRY_MARGINALS.csv':3035,
    'EXACT_GEOMETRY_UNCOMPUTED_LINKS.csv.gz':0,
    'GEOMETRY_FIXED157_INTERVAL_IMAGE.csv':1884,
    'GEOMETRY_FIXED157_INTERVAL_BUILDING.csv':264,
    'GEOMETRY_FIXED157_INTERVAL_MAIN.csv':12,
    'VFUA_35_LEAVE_ONE_OUT_AND_FULL.csv':36,
    'VFUA_N34_EXACT_SAMPLED_PATHS.csv':96,
    'RARE_SUCCESS_EXACT_TEAMS.csv.gz':69,
    'RARE_SUCCESS_REGISTERED_PATHS.csv':192,
    'RARE_SUCCESS_SUPPORT_SUMMARY.csv':10,
    'RARE_SUCCESS_ONLY_EVALUABLE_TEAMS.csv':2,
    'MISSED_FAILURE_CANDIDATE_SCAN.csv':194,
    'WC2_46_EXACT_28_TEAMS_AND_FREQUENCIES.csv':28,
    'WC2_46_REGISTERED_PATHS.csv':96,
    'WC2_46_BATCH_P10_AND_WEIGHTS.csv':7,
}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='.');a=ap.parse_args()
    root=Path(a.root).resolve();rows=[];errors=[]
    for folder in ['results','figures','case_VFua_04','case_missed_failure','case_WC2_46_P10']:
        for p in sorted((root/folder).glob('*')):
            if not p.is_file() or p.name.startswith('OLD_NATURAL_'):continue
            item=dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            try:
                if p.name.endswith(('.csv','.csv.gz')):
                    opener=gzip.open if p.suffix=='.gz' else open
                    with opener(p,'rt',encoding='utf-8',newline='') as f:
                        reader=csv.reader(f,strict=True);header=next(reader);n=0
                        for row in reader:
                            n+=1
                            if len(row)!=len(header):raise ValueError(f'CSV field count at row {n}: {len(row)} != {len(header)}')
                    item.update(kind='csv',rows=n,columns=len(header),fields=header,read_to_eof=True)
                    if p.name in EXPECTED and n!=EXPECTED[p.name]:raise ValueError(f'Expected {EXPECTED[p.name]} rows; found {n}')
                elif p.name.endswith(('.json','.json.gz')):
                    opener=gzip.open if p.suffix=='.gz' else open
                    with opener(p,'rt',encoding='utf-8') as f:obj=json.load(f)
                    item.update(kind='json',read_to_eof=True)
                elif p.suffix=='.png':
                    with Image.open(p) as im:im.load();item.update(kind='png',width=im.width,height=im.height,full_pixels_read=True)
                elif p.suffix=='.pdf':
                    import fitz
                    doc=fitz.open(p)
                    for page in doc:page.get_pixmap()
                    item.update(kind='pdf',pages=len(doc),pages_rendered=True)
                else:continue
                item['valid']=True
            except Exception as exc:
                item.update(valid=False,error=str(exc));errors.append(item)
            rows.append(item)
    checks=[]
    for name,keys in [
        ('GEOMETRY_PATH_PRECISION.csv.gz',['pool_id','cohort','k','metric']),
        ('GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz',['pool_id','cohort','k_from','k_to','metric']),
        ('EXACT_GEOMETRY_MARGINALS.csv',['pool_id','k','metric'])]:
        try:
            d=pd.read_csv(root/'results'/name,usecols=keys)
            count=int(d.duplicated(keys).sum());checks.append(dict(path='results/'+name,key=keys,duplicates=count))
            if count:errors.append(dict(path=name,error='Duplicate composite keys'))
        except Exception as exc:errors.append(dict(path=name,error=str(exc)))
    receipt=dict(files=rows,composite_key_checks=checks,error_count=len(errors),errors=errors,
                 note='Validated actual final saved files through EOF, including gzip trailer/CRC; this does not replace final ZIP-entry readback by the packager.')
    atomic_bytes(root/'GEOMETRY_OUTPUT_READBACK_RECEIPT.json',json.dumps(receipt,ensure_ascii=False,indent=2).encode())
    print('Validated',len(rows),'files; errors',len(errors),flush=True)
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
