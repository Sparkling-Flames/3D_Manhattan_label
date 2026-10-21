"""Compact completed-condition checkpoint; no duplicate historical selections."""
import argparse,json,zipfile
from pathlib import Path
import pandas as pd
from prepare_training import HERE,sha,atomic_csv,atomic_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--condition',choices=['manual','semi'],required=True);a=p.parse_args()
    files=[]
    for suffix in ('*.py','*.md'):
        files+=list(HERE.glob(suffix))
    files+=[p for p in HERE.glob(a.condition.upper()+'_*')
            if p.is_file() and p.suffix!='.partial' and 'RESULTS_PACKAGE' not in p.name]
    for name in ['FIGURE_POLICY_UTILITY_SHARED_SUPPORT.png','FIGURE_POLICY_UTILITY_SHARED_SUPPORT.svg',
                 'POLICY_FRONTIER_POINTS.csv','POLICY_FRONTIER_SHARED_PANELS.csv']:
        if (HERE/name).exists():files.append(HERE/name)
    for name in ['INTERACTION_FIELD_VALIDATION.json','FIELD_MAPPING_CORRECTION.json',
                 'TRAINING_CACHE_RECEIPT.json','TRAINING_SOURCE_INDEX.csv','TRAINING_COVERAGE.csv']:
        files.append(HERE/name)
    for path in (HERE/'cross_panel_LOBO'/a.condition).rglob('*'):
        if path.is_file() and path.suffix!='.partial':files.append(path)
    for name in ['PANEL_POLICY_RESULTS.csv.gz','PANEL_OBSERVED_OPPORTUNITIES.csv',
                 'POLICY_CLASS_COMPOSITIONS.csv.gz','EVALUATION_RECEIPT.json']:
        files+=list((HERE/'historical_only'/a.condition).glob('*/'+name))
    files=sorted({p for p in files if not any(x.startswith('.') or '.partial' in x for x in p.relative_to(HERE).parts)})
    assert all(p.exists() and p.suffix!='.partial' for p in files)
    mp=HERE/(a.condition.upper()+'_RESULTS_PACKAGE_MANIFEST.csv')
    atomic_csv(pd.DataFrame([dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p)) for p in files]),mp)
    files.append(mp)
    name=f'HOHONET_v3_{a.condition}_实际选择用途阶段结果_20261021.zip'
    out=HERE/name;tmp=out.with_name(name+'.partial')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in files:z.write(path,arcname=str(Path('utility')/path.relative_to(HERE)))
    with zipfile.ZipFile(tmp) as z:assert z.testzip() is None
    tmp.replace(out)
    receipt=dict(path=str(out),condition=a.condition,bytes=out.stat().st_size,sha256=sha(out),files=len(files),
        historical_selections_reference='HOHONET_v3_实际选队规则与冻结选择_20261021.zip',
        native_endpoints_reference='../composition/batches/',failure_rows_retained=True)
    atomic_json(receipt,HERE/(a.condition.upper()+'_RESULTS_PACKAGE_RECEIPT.json'))
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
