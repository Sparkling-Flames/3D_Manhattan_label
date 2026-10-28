"""Rescore previously saved exchange geometries against v2.1 targets; never fuse."""
import argparse,csv,gzip,json,math
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
from .rebuild_v21_20261028 import ROOT,OUT,read
from .scope_quality_scoring_20261016 import scoring_engine
from .wall_consensus_quality_20261015 import measured
from .quality_b8l2_d10_20261017 import dual_scores

TARGET=OUT/'exchange_endpoint_rescore'
SOURCES={
 'closure':'research/workers/personnel_exchange_closure_20261022/delivery/endpoints/ALL_REQUIRED_ENDPOINT_',
 'background_gradient':'research/workers/personnel_exchange_adoption_followup_20261022/structure_followup/background_gradient/ENDPOINT_',
 'direct_ac':'research/workers/personnel_mixture_comparison_20261022/direct_ac/USED_ENDPOINT_',
}
METRICS=['B8L2','D10','WQ','A10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','nodes','ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9']

def object_ids(value):
    if not value:return set()
    return set(json.loads(value) if value.startswith('[') else value.split('|'))

def rows(path,ids):
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['pool_id'] in ids:yield r

def inventory():
    TARGET.mkdir(parents=True,exist_ok=True)
    ids={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_geometry_rescore'}
    pools={r['pool_id']:r for r in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')}
    assert ids<=set(pools)
    items={};summary={}
    for name,prefix in SOURCES.items():
        geometry={};scalar={}
        for r in rows(ROOT/(prefix+'GEOMETRY.csv.gz'),ids):
            key=r['team_key'];assert key not in geometry;geometry[key]=r
        for r in rows(ROOT/(prefix+'SCALARS.csv.gz'),ids):
            key=r['team_key'];assert key not in scalar;scalar[key]=r
        missing_geom=sorted(scalar.keys()-geometry.keys());missing_scalar=sorted(geometry.keys()-scalar.keys())
        summary[name]=dict(geometry_rows=len(geometry),scalar_rows=len(scalar),missing_geometry=missing_geom,missing_scalar=missing_scalar,status_counts=dict(Counter(r['score_status'] for r in geometry.values())))
        for key,g in geometry.items():
            if key not in scalar:continue
            sc=scalar[key];
            for field in ['pool_id','k','score_status','complete_evaluable','reference_id']:
                assert g[field]==sc[field],(name,key,field,g[field],sc[field])
            assert set(g['member_workers'].split('|'))==set(sc['member_workers'].split('|'))
            assert len(set(g['member_workers'].split('|')))==int(g['k'])
            assert len(object_ids(sc.get('member_object_ids','')))==int(g['k'])
            tid=pools[g['pool_id']]['meta']['reference_id'];assert tid in refs
            item=dict(team_key=key,pool_id=g['pool_id'],k=int(g['k']),member_workers=g['member_workers'].split('|'),member_object_ids=sc.get('member_object_ids'),reference_id=tid,original_reference_id=g['reference_id'],original_reference_version=g['reference_version'],original_score_status=g['score_status'],original_complete_evaluable=g['complete_evaluable']=='True',original_metrics={c:sc.get(c) for c in METRICS},geometry=json.loads(g['geometry_json']) if g['geometry_json'] else None,source_geometry=[prefix+'GEOMETRY.csv.gz'],source_scalar=[prefix+'SCALARS.csv.gz'])
            if key in items:
                previous=items[key]
                for field in ['pool_id','k','member_workers','reference_id','original_reference_id','original_score_status','original_complete_evaluable','geometry']:
                    assert previous[field]==item[field],(key,field,'conflicting sources')
                assert object_ids(previous['member_object_ids'])==object_ids(item['member_object_ids']),(key,'conflicting object IDs')
                previous['source_geometry']+=item['source_geometry'];previous['source_scalar']+=item['source_scalar']
            else:items[key]=item
    with gzip.open(TARGET/'INPUT_TEAMS.jsonl.gz','wt',encoding='utf8') as f:
        for key in sorted(items):f.write(json.dumps(items[key],ensure_ascii=False,allow_nan=False)+'\n')
    receipt=dict(affected_pools=len(ids),unique_teams=len(items),sources=summary,deduplicated_source_rows=sum(x['geometry_rows'] for x in summary.values())-len(items),no_fusion=True)
    (TARGET/'COVERAGE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)
    if any(x['missing_geometry'] or x['missing_scalar'] for x in summary.values()):raise ValueError('incomplete source joins; see COVERAGE.json')

def update_working(result,models):
    fields=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
    if all(result.get(k) is not None for k in fields):
        values=[result[k] for k in fields]
        wq=float(models.score(*values,models.MODELS['WQ']))
        assert result.get('WQ') is not None and math.isclose(result['WQ'],wq,rel_tol=0,abs_tol=1e-10)
        result['A10']=float(models.score(*values,models.MODELS['A10']))

def add_working_scores():
    paths=sorted((TARGET/'shards').glob('*.jsonl.gz'));assert paths
    count=0
    with scoring_engine() as (_,models):
        for path in paths:
            with gzip.open(path,'rt',encoding='utf8') as f: data=[json.loads(x) for x in f]
            for row in data:
                if row['result'] is not None:
                    update_working(row['result'],models)
                    count+=int('A10' in row['result'])
            tmp=path.with_suffix('.working')
            with gzip.open(tmp,'wt',encoding='utf8') as f:
                for row in data:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
            tmp.replace(path)
    check=read(TARGET/'CHECKS.json');check['full_working_model_scores']=count;check['working_score_fields']=['WQ','A10','B8L2','D10'];(TARGET/'CHECKS.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('working A10 derived for',count,'teams',flush=True)

def score_one(r,ref,engine,models):
    g=r['geometry'];status=r['original_score_status'];result=None
    if status=='two_person_deferred': state='design_deferred_k2'
    elif not g:state='geometry_missing'
    elif status=='no_connection':state='original_no_connection'
    else:
        nodes=len(g.get('feature_ids') or g.get('footprint') or [])
        state0=dict(n=r['k'],candidate=g,node_consensus=dict(nodes=[None]*nodes))
        result=measured(engine,state0,dict(floor=ref['floor_xz_h'],points=ref['points_1024x512']))
        fields=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
        if all(result.get(k) is not None for k in fields):
            result.update(dual_scores(result,models));update_working(result,models)
        state=result['score_status']
    return {k:r[k] for k in ['team_key','pool_id','k','member_workers','member_object_ids','original_reference_id','original_reference_version','original_score_status','original_complete_evaluable','original_metrics','source_geometry','source_scalar']} | dict(data_release='v2.1',reference_id=ref['target_id'],reference_version=ref['reference_version'],geometry_reused=bool(g),rescore_state=state,result=result,reference_dependent_diagnostics_status='pending_recompute',reference_dependent_diagnostics={'ref_node_recall_5':None,'ref_node_recall_9':None,'ref_edge_recall_5':None,'ref_edge_recall_9':None},new_fusion=False)

def shard(payload):
    number,items=payload;path=TARGET/'shards'/f'{number:05d}.jsonl.gz';refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')}
    if path.exists():raise FileExistsError(f'Existing shard requires explicit clean rebuild: {path}')
    result=[]
    with scoring_engine() as (engine,models):
        for item in items:result.append(score_one(item,refs[item['reference_id']],engine,models))
    tmp=path.with_suffix('.writing')
    with gzip.open(tmp,'wt',encoding='utf8') as f:
        for r in result:f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
    tmp.replace(path);return len(result)

def run(jobs):
    (TARGET/'shards').mkdir(parents=True,exist_ok=True)
    with gzip.open(TARGET/'INPUT_TEAMS.jsonl.gz','rt',encoding='utf8') as f:items=[json.loads(x) for x in f]
    blocks=[(i//200,items[i:i+200]) for i in range(0,len(items),200)];total=0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futures=[ex.submit(shard,b) for b in blocks]
        for i,f in enumerate(as_completed(futures),1):
            total+=f.result()
            if i%10==0:print('exchange shards',i,'/',len(blocks),'rows',total,flush=True)
    states=Counter();missing=[];pools=set();transitions=Counter();by_source={};working=0
    for n,_ in blocks:
        with gzip.open(TARGET/'shards'/f'{n:05d}.jsonl.gz','rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);states[r['rescore_state']]+=1;pools.add(r['pool_id']);transitions[(r['original_score_status'],r['rescore_state'])]+=1
                for source in r['source_geometry']:by_source.setdefault(source,Counter())[r['rescore_state']]+=1
                working+=int(bool(r['result'] and r['result'].get('A10') is not None))
                if r['rescore_state']=='geometry_missing':missing.append(r['team_key'])
    ids={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_geometry_rescore'}
    check=dict(teams=len(items),rows=total,shards=len(blocks),states=dict(states),missing_geometry_keys=missing,reference_dependent_diagnostics='pending_recompute',no_fusion=True,full_working_model_scores=working,working_score_fields=['WQ','A10','B8L2','D10'],source_pools_with_endpoints=len(pools),affected_pool_ids_without_endpoints_in_three_sources=sorted(ids-pools),original_to_rescore_state=[dict(original=a,rescore=b,count=n) for (a,b),n in sorted(transitions.items())],states_by_source={k:dict(v) for k,v in by_source.items()})
    assert total==len(items)
    (TARGET/'CHECKS.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(check,ensure_ascii=False),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--part',choices=['inventory','score','working'],required=True);ap.add_argument('--jobs',type=int,default=4);a=ap.parse_args()
    if a.part=='inventory':inventory()
    elif a.part=='score':run(a.jobs)
    else:add_working_scores()
