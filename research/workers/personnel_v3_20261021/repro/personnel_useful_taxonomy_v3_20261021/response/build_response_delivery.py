#!/usr/bin/env python3
"""Package completed response outputs without duplicating runtime/endpoints."""
from pathlib import Path
import hashlib, json, os, zipfile
import pandas as pd

HERE=Path(__file__).resolve().parent
V3=HERE.parent

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    primary=[];decomp=[]
    for condition in ('manual','semi'):
        for domain in ('geometry_common','qt_common'):
            root=HERE/condition/domain
            assert json.loads((root/'COMPLETION.json').read_text())['status']=='complete'
            p=pd.read_csv(root/'PREDICTION_SUMMARY.csv')
            primary.append(p[p.stratum.eq('all')])
            decomp.append(pd.read_csv(root/'DECOMPOSITION_SUMMARY.csv'))
    pd.concat(primary,ignore_index=True).to_csv(HERE/'COMPLETED_RESPONSE_PRIMARY_RESULTS.csv',index=False,encoding='utf-8-sig')
    pd.concat(decomp,ignore_index=True).to_csv(HERE/'COMPLETED_RESPONSE_DECOMPOSITION.csv',index=False,encoding='utf-8-sig')
    names=['PANEL_PREDICTION.csv.gz','PREDICTION_BUILDINGS.csv','PREDICTION_SUMMARY.csv',
           'PANEL_CONFIGURATION_DECOMPOSITION.csv.gz','DECOMPOSITION_SUMMARY.csv',
           'FITTED_MODELS.csv.gz','SUPPORT.csv','COMPLETION.json','EXECUTION_ENGINE_RECEIPT.json']
    files=[]
    for domain in ('geometry_common','qt_common'):
        for n in names:
            p=HERE/'manual'/domain/n
            if p.exists():files.append(p)
        files.extend(sorted((HERE/'manual'/domain/'building_batches').glob('*_COMPLETE.json')))
    for n in ['analyze_responses.py','build_response_delivery.py','DESIGN_FROZEN_ZH.md',
              'MODEL_REPRESENTATION_AMENDMENT.json','EXECUTION_EQUIVALENCE_SWITCH.json',
              'MANUAL_RESPONSE_FINDINGS_ZH.md','COMPLETED_RESPONSE_PRIMARY_RESULTS.csv',
              'COMPLETED_RESPONSE_DECOMPOSITION.csv']:
        files.append(HERE/n)
    fast=V3/'integration/taxonomy_adoption_synthesis'
    files.append(fast/'run_response_fast.py')
    files.extend(sorted((fast/'fast_validation').rglob('*EQUIVALENCE_RECEIPT.json')))
    rows=[dict(path=str(p.relative_to(V3)),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    manifest=HERE/'MANUAL_RESPONSE_MANIFEST.json'
    manifest.write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    pack=HERE/'HOHONET_v3_Manual_粗细类与连续特征完整面板结果_20261021.zip'
    tmp=pack.with_suffix('.zip.partial')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[manifest]:z.write(p,str(p.relative_to(V3)))
    with zipfile.ZipFile(tmp) as z:assert z.testzip() is None
    with tmp.open('rb') as f:os.fsync(f.fileno())
    os.replace(tmp,pack)
    receipt=dict(status='complete',package=str(pack),bytes=pack.stat().st_size,sha256=sha(pack),
                 files=len(files)+1,new_fusion_calls=0,all_four_condition_domain_outputs_complete=True,
                 primary_rows=sum(len(p) for p in primary),decomposition_rows=sum(len(p) for p in decomp))
    (HERE/'MANUAL_RESPONSE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
