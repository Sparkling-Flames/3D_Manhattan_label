"""Self-contained text/numerical delivery for a new cloud conversation."""
import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from .pipeline import REPO, read, sha


def build(folder):
    folder=Path(folder)
    manifest=read(folder/'results/EXPERIMENT_MANIFEST.json')
    for name,expected in manifest['files'].items():
        if sha(folder/'results'/name)!=expected: raise ValueError('Result drift: '+name)
    files={}
    for directory in ('rc2_received','results','evidence'):
        for p in sorted((folder/directory).rglob('*')):
            if p.is_file() and p.suffix in {'.json','.jsonl','.csv','.gz','.py','.md','.txt'}:
                files[p.relative_to(folder).as_posix()]=p
    for p in (folder/'rc2_received/sources/current/tools').rglob('*.py'):
        files['tools/'+p.relative_to(folder/'rc2_received/sources/current/tools').as_posix()]=p
    for name in ('local_points.py','local_points_review.py','local_points_package.py'):
        files['tools/thesis_main/analysis/clustering_release/'+name]=Path(__file__).with_name(name)
    for name in ('release_review.py','release_review_panel.js'):
        files['tools/thesis_main/analysis/paired_split_research/'+name]=REPO/'tools/thesis_main/analysis/paired_split_research'/name
    for name in ('README.md','LOCAL_REVIEW.md','RC2_COMPARISON.json'):
        files[name]=folder/name
    files['PRO_TASK.md']=REPO/'docs/thesis_main/Pro新对话_局部点位分簇与影响核查_20260920.md'
    files['MENTOR_AND_USER_CONTEXT.md']=REPO/'analysis_results/pro_next_round_20260920/来源核对与最新要求.md'
    files['tests/test_local_point_comparison.py']=REPO/'tests/test_local_point_comparison.py'
    files['tests/test_clustering_release_review.py']=REPO/'tests/test_clustering_release_review.py'
    for name in ('真人标注不确定性研究_当前状态.md','相似场景标注稳定性分析SOP.md','分簇工作版_统一数据入口_20260920.md'):
        files['docs/'+name]=REPO/'docs/thesis_main'/name
    current=folder/'rc2_received/sources/current/study'
    if sha(current/'RUN_MANIFEST.json')!=manifest['source_manifest_sha']:
        raise ValueError('RC2 source differs from local comparison run')
    for name,expected in manifest['evidence'].items():
        if sha(folder/'evidence'/name)!=expected: raise ValueError('Evidence drift: '+name)
    for name,expected in manifest['code'].items():
        paths=[p for key,p in files.items() if key.startswith('tools/') and p.name==name]
        if len(paths)!=1 or sha(paths[0])!=expected: raise ValueError('Experiment implementation drift: '+name)
    info={'schema':'local_point_delivery_v1','source_run_id':manifest['source_run_id'],
          'files':{name:sha(p) for name,p in sorted(files.items())},
          'raw_logs_or_credentials':False,'original_images':False,'full_visual_acceptance':False}
    target=folder/'pro_local_points_20260920.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for name,p in sorted(files.items()):z.write(p,name)
        z.writestr('DELIVERY_MANIFEST.json',json.dumps(info,ensure_ascii=False,indent=2))
    (folder/'DELIVERY_MANIFEST.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return {'path':str(target),'files':len(files)+1,'bytes':target.stat().st_size}


def verify_delivery(folder):
    folder=Path(folder).resolve()
    temporary=tempfile.TemporaryDirectory(prefix='hohonet-local-point-replay-')
    target=Path(temporary.name).resolve()
    assert target.is_relative_to(Path(tempfile.gettempdir()).resolve()) and target.name.startswith('hohonet-local-point-replay-')
    try:
        with zipfile.ZipFile(folder/'pro_local_points_20260920.zip') as z:
            if not all((target/n).resolve().is_relative_to(target) for n in z.namelist()):
                raise ValueError('Archive path escapes extraction directory')
            z.extractall(target)
        delivery=read(target/'DELIVERY_MANIFEST.json')
        for name,expected in delivery['files'].items():
            if sha(target/name)!=expected: raise ValueError('Archive drift: '+name)
        env=os.environ.copy();env.pop('PYTHONPATH',None)
        cmd=[sys.executable,'-X','utf8','-B','-m','tools.thesis_main.analysis.clustering_release.local_points',
             '--root','rc2_received/sources/current/study','--evidence','evidence','--out','verification']
        result=subprocess.run(cmd,cwd=target,env=env,capture_output=True,text=True,encoding='utf8',timeout=360)
        if result.returncode: raise RuntimeError(result.stdout+'\n'+result.stderr)
        checked=[]
        for p in (target/'results').iterdir():
            if not p.is_file() or p.name=='EXPERIMENT_MANIFEST.json': continue
            q=target/'verification'/p.name
            a,b=p.read_bytes(),q.read_bytes()
            if p.suffix=='.gz':a,b=gzip.decompress(a),gzip.decompress(b)
            if a!=b: raise ValueError('Isolated rerun differs: '+p.name)
            checked.append(p.name)
        a=read(target/'results/EXPERIMENT_MANIFEST.json');b=read(target/'verification/EXPERIMENT_MANIFEST.json')
        assert {k:v for k,v in a.items() if k!='files'}=={k:v for k,v in b.items() if k!='files'}
        info=dict(delivery_files_verified=len(delivery['files']),result_files_equal=sorted(checked),differences=[],
                  gzip_header_excluded_from_content_equality=True,outside_repository_replay=True,return_code=0)
        (folder/'ISOLATED_REPLAY.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
        return info
    finally:
        assert target.is_relative_to(Path(tempfile.gettempdir()).resolve()) and target.name.startswith('hohonet-local-point-replay-')
        temporary.cleanup()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--verify',action='store_true')
    a=p.parse_args();print(verify_delivery(a.folder) if a.verify else build(a.folder))
