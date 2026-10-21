"""Package a completed continuation checkpoint without runtime caches."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser();ap.add_argument('checkpoint');a=ap.parse_args()
    if a.checkpoint=='reused':
        base=HERE/'batches'
        names=['REUSED_REQUESTS.json.gz','REUSED_ENDPOINT_SCALARS.csv.gz','REUSED_ENDPOINT_GEOMETRY.csv.gz','REUSED_RECEIPT.json']
        label='已算18374终点复用'
    elif a.checkpoint=='coverage':
        base=HERE
        receipt=json.loads((HERE/'coverage/N20_COMPLETION.json').read_text())
        if receipt['status']!='complete' or receipt['missing']!=0:raise ValueError('Incomplete continuation')
        names=['README_ZH.md','prepare_n20_design.py','run_n20_batches.py','package_checkpoint.py',
            'preregister_n20_coverage.py','finalize_n20_coverage.py','summarize_n20_scope.py',
            'DESIGN_FREEZE.json','SERIALIZATION_REPAIR_RECEIPT.json',
            'coverage/REGISTERED_COVERAGE_RECEIPT.json','coverage/N20_REGISTERED_GLOBAL_COVERAGE.csv',
            'coverage/N20_METHOD_COMPLETION.csv','coverage/UNIVERSE_FINAL_COVERAGE_AFTER_N20.csv.gz',
            'coverage/N20_COMPLETION.json','coverage/FROZEN_METHOD_K_SUMMARY.csv',
            'coverage/N20_POOL_K_AND_MEMBER_UNIVERSE.csv','coverage/N20_DISTINCT_MEMBER_UNION_BY_POOL.csv',
            'coverage/N20_DISTINCT_MEMBER_UNION_BY_CONDITION.csv',
            'coverage/N20_SCOPE_COUNTS.json','coverage/BATCH_EXECUTION_SUMMARY.csv',
            'coverage/N20_REMAINING_SCALE_ESTIMATE.csv',
            'coverage/本批计算与组合覆盖回执_20261021.md']
        label='全量完成覆盖与恢复代码'
    else:
        base=HERE/'batches'/a.checkpoint
        receipt=json.loads((base/'COMPLETION.json').read_text())
        if receipt['status']!='complete' or receipt['missing']!=0:raise ValueError('Incomplete checkpoint')
        names=['REQUESTS.json.gz','ENDPOINT_SCALARS.csv.gz','ENDPOINT_GEOMETRY.csv.gz','COMPLETION.json','EXECUTION.json']
        label=a.checkpoint
    files=[base/n for n in names]
    package_meta_base=HERE/'coverage' if a.checkpoint=='coverage' else base
    manifest=package_meta_base/'CHECKPOINT_MANIFEST.csv'
    with manifest.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['path','bytes','sha256'])
        for x in files:w.writerow([str(x.relative_to(base)),x.stat().st_size,hashlib.sha256(x.read_bytes()).hexdigest()])
    files.append(manifest)
    z=HERE/f'HOHONET_n20_{label}_20261021.zip'
    tmp=z.with_suffix('.zip.tmp')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as f:
        for x in files:f.write(x,x.relative_to(HERE))
    with zipfile.ZipFile(tmp) as f:
        if f.testzip() is not None:raise ValueError('ZIP integrity failure')
        for name in f.namelist():
            if name.endswith('.gz'):gzip.decompress(f.read(name))
    tmp.replace(z)
    out=dict(checkpoint=a.checkpoint,zip=str(z.resolve()),bytes=z.stat().st_size,
             sha256=hashlib.sha256(z.read_bytes()).hexdigest(),files=len(files),runtime_excluded=True)
    (package_meta_base/'CHECKPOINT_PACKAGE.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps(out,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
