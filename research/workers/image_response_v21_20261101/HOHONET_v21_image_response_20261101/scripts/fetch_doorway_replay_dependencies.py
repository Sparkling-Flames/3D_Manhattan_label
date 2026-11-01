#!/usr/bin/env python3
"""Read-only pinned-code dependency retrieval for three diagnostic replays."""
import ast,concurrent.futures,hashlib,json,os,ssl,urllib.request,urllib.error
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'stage04_doorway_cases/replay_engine'
COMMIT='e1873bfadc1d0e61499809c91fba9dc39c717f83'
REPO='Sparkling-Flames/3D_Manhattan_label'
CTX=ssl.create_default_context(cafile=os.environ.get('REQUESTS_CA_BUNDLE'))
SEEDS=['tools.thesis_main.analysis.consensus_delivery_20261008',
       'tools.thesis_main.analysis.wall_consensus_v1_process_20261017',
       'tools.thesis_main.analysis.scope_quality_scoring_20261016',
       'tools.thesis_main.analysis.wall_consensus_quality_20261015',
       'tools.thesis_main.analysis.quality_b8l2_d10_20261017',
       'tools.thesis_main.analysis.clustering_release.pipeline',
       'tools.thesis_main.analysis.clustering_release.local_points']

def fetch_module(mod):
    rel=mod.replace('.','/')+'.py';dest=DEST/rel
    known=[dest,ROOT/'source/repo'/rel,ROOT/'stage00_doorway_sources/source'/rel,
           ROOT/'stage00_manual_sources/repo'/rel]
    data=None;origin='pinned_github'
    for p in known:
        if p.exists():data=p.read_bytes();origin='already_pinned_local';break
    if data is None:
        url=f'https://raw.githubusercontent.com/{REPO}/{COMMIT}/{rel}'
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'HOHONET-diagnostic-replay'}),context=CTX,timeout=60) as f:data=f.read()
        except urllib.error.HTTPError as e:
            if e.code==404:return mod,None,[],{'path':rel,'status':'not_module_404'}
            raise
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    tree=ast.parse(data.decode('utf-8-sig'));deps=set()
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            deps.update(x.name for x in node.names if x.name.startswith(('tools.','lib.')))
        elif isinstance(node,ast.ImportFrom):
            if node.level:
                pkg=mod.split('.')[:-1]
                prefix=pkg[:len(pkg)-(node.level-1)]
                target='.'.join(prefix+([node.module] if node.module else []))
            else:target=node.module or ''
            if target.startswith(('tools.','lib.')):
                if target in ['tools.thesis_main.analysis','tools.thesis_main.data_prep','tools.thesis_main.analysis.clustering_release','tools.label_studio.panorama_studio','lib.misc']:
                    deps.update(target+'.'+x.name for x in node.names if x.name!='*')
                elif node.module:deps.add(target)
                else:deps.update(target+'.'+x.name for x in node.names)
    return mod,data,sorted(deps),{'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'origin':origin,'status':'saved'}

def main():
    pending=set(SEEDS);seen=set();receipt=[]
    while pending:
        batch=sorted(pending-seen);pending=set()
        if not batch:break
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as e:
            results=list(e.map(fetch_module,batch))
        for mod,data,deps,meta in results:
            seen.add(mod);receipt.append(meta);pending.update(set(deps)-seen)
        print('code_modules',len(seen),'pending',len(pending),flush=True)
    engine='research/statistics/b8l2_shared_v6_20261016/inputs/measurement_engine.zip'
    dest=DEST/engine;dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists():
        with urllib.request.urlopen(urllib.request.Request(f'https://raw.githubusercontent.com/{REPO}/{COMMIT}/{engine}',headers={'User-Agent':'HOHONET-diagnostic-replay'}),context=CTX,timeout=60) as f:dest.write_bytes(f.read())
    receipt.append({'path':engine,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'status':'saved'})
    working='research/statistics/b8l2_shared_v6_20261016/inputs/working_models.py'
    p=DEST/working;p.write_bytes((ROOT/'stage00_doorway_sources/source'/working).read_bytes())
    receipt.append({'path':working,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'status':'saved'})
    (ROOT/'stage04_doorway_cases/REPLAY_CODE_FETCH_RECEIPT.json').write_text(json.dumps({'source_commit':COMMIT,'files':receipt},ensure_ascii=False,indent=2))
    print('fetched',sum(x['status']=='saved' for x in receipt),'files',flush=True)
if __name__=='__main__':main()
