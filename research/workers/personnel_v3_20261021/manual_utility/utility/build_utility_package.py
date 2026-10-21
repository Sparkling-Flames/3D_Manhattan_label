"""Compact utility delivery; original endpoints and reconstructible cache excluded."""
from pathlib import Path
import argparse,hashlib,json,zipfile
import pandas as pd
from prepare_training import HERE,atomic_json,atomic_csv,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['selection','final'],required=True);a=p.parse_args()
    excludes={'TRAINING_ENDPOINTS.csv.gz'}
    paths=[]
    for path in HERE.rglob('*'):
        if not path.is_file():continue
        rel=path.relative_to(HERE)
        if rel.parts[0] in ('superseded_pre_freeze_selection','__pycache__','logs'):continue
        if any(part.startswith('partial_') for part in rel.parts):continue
        if path.suffix in ('.zip','.partial') or path.name in excludes or path.name.startswith(('PACKAGE_','SELECTION_PACKAGE_','FINAL_PACKAGE_','SEMI_RESULTS_PACKAGE_','MANUAL_RESULTS_PACKAGE_')):continue
        if a.stage=='selection' and ('cross_panel_LOBO' in rel.parts or 'RESULT' in path.name or 'POLICY_EFFECTS' in path.name or 'PAIRED_POLICY' in path.name):continue
        if rel.parts[0]=='recovered_training_input' and path.name!='RECOVERY_RECEIPT.json':continue
        paths.append(path)
    paths=sorted(paths)
    manifest=pd.DataFrame([dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p)) for p in paths])
    prefix='SELECTION_PACKAGE' if a.stage=='selection' else 'FINAL_PACKAGE'
    mp=HERE/(prefix+'_MANIFEST.csv');atomic_csv(manifest,mp);paths.append(mp)
    name='HOHONET_v3_实际选队规则与冻结选择_20261021.zip' if a.stage=='selection' else 'HOHONET_v3_实际选择用途_完整结果与代码_20261021.zip'
    out=HERE/name;tmp=out.with_name(out.name+'.partial')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in paths:z.write(path,arcname=str(Path('utility')/path.relative_to(HERE)))
    with zipfile.ZipFile(tmp) as z:assert z.testzip() is None
    tmp.replace(out)
    atomic_json(dict(stage=a.stage,path=str(out),bytes=out.stat().st_size,sha256=sha(out),files=len(paths),
        excluded=['reconstructible TRAINING_ENDPOINTS cache','superseded pre-freeze selection','all historical/new endpoint inputs','duplicate archives'],
        entire_actual_endpoint_tables_referenced_in_composition_batches=True),HERE/(prefix+'_RECEIPT.json'))
    print(json.dumps(dict(path=str(out),bytes=out.stat().st_size,files=len(paths),sha256=sha(out)),ensure_ascii=False))

if __name__=='__main__':main()
