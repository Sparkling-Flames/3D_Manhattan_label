"""Reproduce the fixed 4570812 sidecar without network or production writes.
Usage: python -X utf8 -B tools/thesis_main/analysis/clustering_numeric_research/run_all.py --out results_recomputed --jobs 4
This entry is intentionally pinned to this source snapshot, not a new-batch importer.
"""
from __future__ import annotations
import argparse,os,sys,json,hashlib,zipfile,subprocess,time
from pathlib import Path
CODE=Path(__file__).resolve().parent
REPO=CODE.parents[3]
ROOT=REPO/'analysis_results/clustering_numeric_received_20260920'
SOURCE_SHA='47e446e38021acb38008ccf6594f60671852712252a7a966c5c1a72b81dd7158'
GIT_BLOB='9cf824b5a77deeccd45b569d5f8727b29810a36a'

def extract_snapshot(archive:Path,destination:Path):
    b=archive.read_bytes()
    if hashlib.sha256(b).hexdigest()!=SOURCE_SHA:raise ValueError('Source ZIP SHA-256 mismatch; do not mix versions')
    if hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()!=GIT_BLOB:raise ValueError('Source Git blob mismatch')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError('Source ZIP CRC failed')
        root=destination.resolve()
        for name in z.namelist():
            path=(root/name).resolve()
            if path!=root and root not in path.parents:raise ValueError('Unsafe archive member')
        # Existing extraction is validated byte-for-byte for every original member.
        if root.exists():
            for info in z.infolist():
                if info.is_dir():continue
                p=root/info.filename
                if not p.is_file() or hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256(z.read(info)).digest():raise ValueError(f'Existing source is not identical: {info.filename}')
        else:z.extractall(root)
    return root

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',default='results_recomputed');p.add_argument('--jobs',type=int,default=4);p.add_argument('--audit-only',action='store_true');p.add_argument('--source-work',default='work/source');a=p.parse_args()
    out=Path(a.out);out=out if out.is_absolute() else ROOT/out
    if out.exists() and any(out.iterdir()):raise FileExistsError('Output directory must be new/empty; old results are never silently reused')
    out.mkdir(parents=True,exist_ok=True)
    source=Path(a.source_work);source=source if source.is_absolute() else ROOT/source
    source=extract_snapshot(ROOT/'inputs/source_snapshot.zip',source)
    env=dict(os.environ,CLUSTER_SOURCE=str(source),CLUSTER_OUT=str(out),CLUSTER_JOBS=str(max(1,a.jobs)),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join([str(source),str(CODE)]))
    steps=[]
    def run(name,cmd,cwd=ROOT):
        print(f'Running {name}',flush=True);start=time.monotonic()
        with (out/(name+'.log')).open('w',encoding='utf-8') as f:subprocess.run(cmd,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        steps.append(dict(step=name,command=cmd,exit_code=0,elapsed_seconds=time.monotonic()-start))
        print(f'Completed {name}',flush=True)
    py=[sys.executable,'-X','utf8','-B']
    run('source_replay',py+['-m','tools.thesis_main.analysis.clustering_release.local_points','--root',str(source/'rc2_received/sources/current/study'),'--evidence',str(source/'evidence'),'--out',str(out/'source_replay')],source)
    scripts=['audit_numeric'] if a.audit_only else ['audit_numeric','prefix_replay','personnel_effects','review_cases','sensitivity_3d','diagnostics','model_bridge','personnel_prefix']
    for name in scripts:run(name,py+[str(CODE/f'{name}.py')])
    if not a.audit_only:run('tests_run',py+['-m','pytest',str(REPO/'tests/test_clustering_numeric_research.py'),str(source/'tests/test_local_point_comparison.py'),str(source/'tests/test_clustering_release_review.py'),'-q','-p','no:cacheprovider'])
    code_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(CODE.glob('*.py'))}
    (out/'RUN_EXECUTION.json').write_text(json.dumps(dict(source_sha256=SOURCE_SHA,source_git_blob=GIT_BLOB,code_files=code_files,mode='audit-only' if a.audit_only else 'full',steps=steps),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Recomputation complete. Original source and delivered results were not overwritten.',flush=True)
if __name__=='__main__':main()
