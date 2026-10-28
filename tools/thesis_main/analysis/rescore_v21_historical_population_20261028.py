"""旧自然/策略及精确边际的现存几何重评分，保留源指针和真实失败。"""
import gzip
import io
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd
from .rebuild_v21_20261028 import ROOT, OUT, read
from .scope_quality_scoring_20261016 import scoring_engine
from .wall_consensus_quality_20261015 import measured
from .quality_b8l2_d10_20261017 import dual_scores

BASE=ROOT/'research/workers/personnel_population_curves_v2_20261023'
TARGET=OUT/'historical_population_rescore'


def process(payload):
    label,number,items=payload
    refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')}
    path=TARGET/f'{label}_{number:05d}.jsonl.gz'
    if path.exists():
        with gzip.open(path,'rt',encoding='utf-8') as f:saved=[json.loads(line) for line in f]
        assert [r['team_key'] for r in saved]==[r['team_key'] for r in items]
        return len(saved)
    results=[]
    with scoring_engine() as (engine,models):
        for r in items:
            ref=refs[r['reference_id']];g=r.get('geometry');result=None
            if g is not None:
                state=dict(n=r['k'],candidate=g,node_consensus=dict(nodes=[None]*r['nodes']))
                result=measured(engine,state,dict(floor=ref['floor_xz_h'],points=ref['points_1024x512']))
                needed=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
                if all(result.get(k) is not None for k in needed):result.update(dual_scores(result,models))
            results.append(dict(data_release='v2.1',team_key=r['team_key'],pool_id=r['pool_id'],k=r['k'],
                reference_id=ref['target_id'],reference_version=ref['reference_version'],
                geometry_source=r['geometry_source'],geometry_index=r['geometry_index'],
                original_score_status=r['old_status'],geometry_reused=True,result=result))
    tmp=path.with_suffix('.writing')
    with gzip.open(tmp,'wt',encoding='utf-8') as f:
        for r in results:f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
    tmp.replace(path)
    return len(results)


def main():
    TARGET.mkdir(exist_ok=True)
    deps=read(OUT/'pools/DEPENDENCIES.json');ids={r['pool_id'] for r in deps if r['action']=='reuse_geometry_rescore'}
    pools={r['pool_id']:r for r in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    fields=['team_key','pool_id','k','nodes','score_status']
    pieces=sorted((BASE/'results').glob('ENDPOINT_SCALARS.csv.gz.part*'))
    compressed=io.BytesIO(b''.join(p.read_bytes() for p in pieces));scalars={}
    for df in pd.read_csv(compressed,compression='gzip',usecols=fields,chunksize=50000):
        scalars.update({r['team_key']:r for r in df[df.pool_id.isin(ids)].to_dict('records')})
    compressed.close()
    path=BASE/'results/ENDPOINT_GEOMETRY.json.gz'
    with gzip.open(path,'rt',encoding='utf-8') as f:old=json.load(f)
    items=[];present=set()
    for i,r in enumerate(old):
        if r['team_key'] not in scalars:continue
        s=scalars[r['team_key']];present.add(r['team_key'])
        items.append(dict(r,k=int(s['k']),nodes=int(s['nodes']) if pd.notna(s['nodes']) else 0,
            reference_id=pools[r['pool_id']]['meta']['reference_id'],old_status=s['score_status'],
            geometry_source=path.relative_to(ROOT).as_posix(),geometry_index=i))
    del old
    missing=sorted(set(scalars)-present)
    deferred=[dict(team_key=k,pool_id=scalars[k]['pool_id'],k=2,
        data_release='v2.1',score_status='two_person_deferred',result=None,
        reason='原设计暂缓两人评分；无几何不视为真实融合失败')
        for k in missing if int(scalars[k]['k'])==2 and scalars[k]['score_status']=='two_person_deferred']
    (TARGET/'PRESERVED_DEFERRED.json').write_text(json.dumps(deferred,ensure_ascii=False,indent=2),encoding='utf-8')
    (TARGET/'OLD_GEOMETRY_COVERAGE.json').write_text(json.dumps(dict(affected_scalar_teams=len(scalars),geometry_teams=len(items),missing_team_keys=missing),indent=2),encoding='utf-8')
    payloads=[('old',i//250,items[i:i+250]) for i in range(0,len(items),250)]
    prior=BASE/'sampling_precision_20261025/new_endpoints/table_shards/NEW_ENDPOINT_GEOMETRY_COMPACT'
    batch=[];count=0
    for path in sorted(prior.glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for i,line in enumerate(f):
                r=json.loads(line)
                if r['pool_id'] not in ids:continue
                g=r.get('geometry') or {}
                batch.append(dict(r,k=int(r['k']),nodes=len(g.get('footprint') or []),old_status=r['score_status'],
                    geometry_source=path.relative_to(ROOT).as_posix(),geometry_index=i))
                if len(batch)==250:
                    payloads.append(('precision',count,batch));count+=1;batch=[]
    if batch:payloads.append(('precision',count,batch))
    total=0
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures=[executor.submit(process,p) for p in payloads]
        for i,future in enumerate(as_completed(futures),1):
            total+=future.result()
            if i%30==0:print('historical shards',i,'/',len(futures),flush=True)
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(shards=len(payloads),rows=total,missing_old_geometry=len(missing),
        policy_deferred_without_geometry=len(deferred),unresolved_missing=len(missing)-len(deferred),complete=len(missing)==len(deferred)),indent=2),encoding='utf-8')
    print('historical completed',total,'missing geometry',len(missing))


if __name__=='__main__':main()
