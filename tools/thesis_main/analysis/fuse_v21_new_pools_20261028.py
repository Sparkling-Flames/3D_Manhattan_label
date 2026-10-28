"""仅新增参考池的256条自然顺序；保持原生融合、去重团队和缺失状态。"""
import argparse
import gzip
import importlib.util
import json
import os
from pathlib import Path
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from .rebuild_v21_20261028 import ROOT, OUT, read

TARGET=OUT/'new_space_natural256'


def adapter():
    os.environ['HOHONET_REPO']=str(ROOT)
    path=ROOT/'research/same_room/same_room_current_classes_v2_20261023/code/engine/new_team_engine.py'
    spec=importlib.util.spec_from_file_location('v21_native_adapter',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module


def design(pool,seed):
    workers=sorted(r['worker_id'] for r in pool['records'])
    rng=np.random.default_rng(seed);orders=[];teams=set()
    for i in range(256):
        order=rng.permutation(workers).tolist();orders.append(dict(path_index=i,workers=order))
        for k in range(1,len(workers)+1):teams.add(tuple(sorted(order[:k])))
    return dict(pool_id=pool['pool_id'],seed=seed,paths=orders,teams=[list(t) for t in sorted(teams)])


def compute(payload):
    pool,seed,limit=payload
    directory=TARGET/pool['pool_id'];directory.mkdir(parents=True,exist_ok=True)
    plan=design(pool,seed);f=directory/'DESIGN.json'
    if f.exists():assert read(f)==plan,'续跑设计改变'
    else:f.write_text(json.dumps(plan,ensure_ascii=False),encoding='utf-8')
    context=directory/'INPUT.json'
    if context.exists():assert read(context)==pool,'续跑输入改变'
    else:context.write_text(json.dumps(pool,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    done=set();part=0
    for p in sorted(directory.glob('part_*.jsonl.gz')):
        with gzip.open(p,'rt',encoding='utf-8') as f:
            rows=[json.loads(line) for line in f]
        for r in rows:
            members=tuple(r['member_workers']);assert members not in done;done.add(members)
        part+=1
    wanted={tuple(t) for t in plan['teams']};assert done<=wanted
    pending=[list(t) for t in sorted(wanted-done)]
    if limit:pending=pending[:limit]
    native=adapter();buffer=[];computed=0
    def flush():
        nonlocal part
        if not buffer:return
        part+=1;p=directory/f'part_{part:05d}.jsonl.gz';tmp=p.with_suffix('.writing')
        with gzip.open(tmp,'wt',encoding='utf-8') as f:
            for row in buffer:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
        tmp.replace(p);buffer.clear()
    with native.Engine(full_state=False) as engine:
        for workers in pending:
            row=engine.evaluate(pool,workers)
            # 原生包装仅导出部分分项；补回同一次测量缓存中保存的全部分项。
            g=row.get('geometry')
            if g is not None:
                measured=engine.scorecache.get(engine.fr.digest([row['k']==2,row.get('nodes'),g]))
                if measured:row.update(measured)
            row.update(underlying_data_version='v2.1',data_release='v2.1',endpoint_origin='v21_new_space_natural256')
            buffer.append(native.gs.clean(row));computed+=1
            if len(buffer)>=50:flush()
            if computed%250==0:print(pool['pool_id'],'teams',len(done)+computed,'/',len(wanted),flush=True)
        flush()
    receipt=dict(pool_id=pool['pool_id'],requested=len(wanted),previous=len(done),computed=computed,
        complete=len(done)+computed==len(wanted),natural_orders=256,seed=seed)
    (directory/'CHECKS.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return receipt


def main():
    p=argparse.ArgumentParser();p.add_argument('--jobs',type=int,default=2);p.add_argument('--limit',type=int);p.add_argument('--pool')
    args=p.parse_args();TARGET.mkdir(exist_ok=True)
    deps={r['pool_id']:r for r in read(OUT/'pools/DEPENDENCIES.json')}
    pools=[r for r in read(OUT/'pools/INPUT_SNAPSHOT.json')['images'] if deps[r['pool_id']]['action']=='new_or_changed_pool']
    payloads=[(r,2026102800+i,args.limit) for i,r in enumerate(pools) if args.pool is None or r['pool_id']==args.pool]
    results=[]
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        for r in executor.map(compute,payloads):results.append(r);print(r,flush=True)
    (TARGET/('PARTIAL_CHECKS.json' if args.limit or args.pool else 'CHECKS.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
