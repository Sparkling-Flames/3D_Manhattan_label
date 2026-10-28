"""复用自然256已保存融合几何，按v2.1参考重测；旧标量单独保留。"""
import argparse
import gzip
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd
from .rebuild_v21_20261028 import OUT, ROOT, read
from .scope_quality_scoring_20261016 import scoring_engine, score_task
from .quality_b8l2_d10_20261017 import dual_scores

SOURCE=ROOT/'research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026'
TARGET=OUT/'population256_rescore'


def run_shard(spec):
    refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')}
    source=SOURCE/spec['geometry_file']
    destination=TARGET/spec['geometry_file'].replace('.geometry_compact.jsonl.gz','.v21_scores.jsonl.gz')
    receipt=destination.with_suffix('.receipt.json')
    if receipt.exists():
        meta=read(receipt)
        assert meta['reference_points']==refs[meta['reference_id']]['points_1024x512']
        with gzip.open(destination,'rt',encoding='utf-8') as f:
            assert sum(1 for line in f if json.loads(line))==meta['rows']
        return dict(rows=meta['rows'],reused=True,file=str(destination.relative_to(OUT)))
    destination.parent.mkdir(parents=True,exist_ok=True)
    tmp=destination.with_suffix('.writing')
    n=0;complete=0;deferred=0
    with scoring_engine() as (engine,models),gzip.open(source,'rt',encoding='utf-8') as incoming,gzip.open(tmp,'wt',encoding='utf-8') as output:
        for line in incoming:
            r=json.loads(line);ref=refs[r['reference_id']]
            assert r['pool_id']==spec['pool_id']
            geometry=r.get('geometry') or {};points=geometry.get('points')
            result=None
            if r['k']==2:
                state='design_deferred_k2';deferred+=1
            elif r.get('actual_consensus_failure'):
                state=r['endpoint_state']
            elif not points or not r.get('complete_evaluable'):
                state=r['endpoint_state']
            else:
                task=dict(object_id=r['team_key'],image_id=ref['image_id'],worker_id='team',condition='manual',
                    current_target_id=ref['target_id'],reference_version=ref['reference_version'],
                    annotation_points=points,reference_points=ref['points_1024x512'])
                result=score_task(task,engine,models)
                if result['score_status']=='complete':
                    result.update(dual_scores(result,models));complete+=1;state='scored'
                else:state='measurement_unavailable'
            value=dict(data_release='v2.1',team_key=r['team_key'],pool_id=r['pool_id'],k=r['k'],
                reference_id=ref['target_id'],reference_version=ref['reference_version'],
                geometry_source=spec['geometry_file'],geometry_line=n+1,geometry_reused=True,
                original_endpoint_state=r['endpoint_state'],endpoint_state=state,
                original_actual_consensus_failure=r.get('actual_consensus_failure'),result=result,
                reference_dependent_diagnostics_status='pending_recompute')
            output.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');n+=1
    assert n==spec['rows']
    tmp.replace(destination)
    receipt.write_text(json.dumps(dict(rows=n,complete=complete,deferred=deferred,reference_id=ref['target_id'],
        reference_points=ref['points_1024x512']),ensure_ascii=False,indent=2),encoding='utf-8')
    return dict(rows=n,reused=False,file=str(destination.relative_to(OUT)))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--jobs',type=int,default=4);parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')}
    old={r['target_id']:r for r in read(ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json')}
    changed={tid for tid,r in refs.items() if tid not in old or r['points_1024x512']!=old[tid]['points_1024x512']}
    pools=pd.read_csv(SOURCE/'design26/POOL_SAMPLING_PLAN.csv')
    ids=set(pools.loc[pools.reference_id.isin(changed),'pool_id'])
    index=pd.read_csv(SOURCE/'new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz')
    specs=index[index.pool_id.isin(ids)].to_dict('records')
    if args.limit:specs=specs[:args.limit]
    TARGET.mkdir(exist_ok=True)
    rows=[]
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures=[executor.submit(run_shard,s) for s in specs]
        for future in as_completed(futures):
            rows.append(future.result())
            if len(rows)%20==0:print('population shards',len(rows),'/',len(specs),flush=True)
    (TARGET/('PARTIAL_SHARDS.json' if args.limit else 'NEW208_SHARDS.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('done',len(rows),'shards',sum(r['rows'] for r in rows),'endpoints; old48 and other experiments remain separate')


if __name__=='__main__':main()
