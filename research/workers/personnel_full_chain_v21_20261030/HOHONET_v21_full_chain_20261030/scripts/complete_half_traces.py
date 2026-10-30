"""Cache-first trace completion for saved half-team events and exact contexts.

Only missing diagnostics for existing teams are replayed. Class labels, inputs,
MV50, source point order and scoring remain frozen. Core saved outcomes remain
authoritative and replay parity is required before interpretation.
"""
from __future__ import annotations
import os
for x in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[x]='1'
from pathlib import Path
import concurrent.futures,gzip,hashlib,json,math,sys,time
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parent;OUT=ROOT/'stage01_half_team'
SOURCE=ROOT/'source'
sys.path.insert(0,str(SOURCE/'research/workers/personnel_v21_reselection_20261029/experiment'))
from benchmark_engine import load_engine

def read(p):
    with (gzip.open(p,'rt',encoding='utf-8-sig') if str(p).endswith('.gz') else open(p,encoding='utf-8-sig')) as f:return json.load(f)
def clean(v):
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,(np.bool_,)):return bool(v)
    if isinstance(v,(float,np.floating)):return float(v) if math.isfinite(v) else None
    if isinstance(v,np.integer):return int(v)
    return v
def write(p,v):
    p.parent.mkdir(exist_ok=True,parents=True);data=json.dumps(clean(v),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if p.name.endswith('.gz'):data=gzip.compress(data,compresslevel=5,mtime=0)
    t=p.with_name(p.name+'.writing');t.write_bytes(data);t.replace(p)
def parity(before,after,request,pool):
    assert after['team_key']==request['team_key'] and after['pool_id']==pool['pool_id']
    assert set(after['member_workers'])==set(request['members'].split('|'))
    assert after['reference_id']==before['reference_id']==pool['meta']['reference_id']
    assert after['reference_version']==before['reference_version']==pool['meta']['reference_version']
    assert after['score_status']==before['score_status'],(request['team_key'],after['score_status'],before['score_status'])
    differences={}
    fields=['B8L2','D10','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','nodes','minimum_support','geometry_area_h2','height_mean_h','centroid_x_h','centroid_z_h','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','boundary_loss','direction_loss','height_loss','ref_node_recall_5','ref_edge_recall_5']
    for field in fields:
        x=before.get(field);y=after.get(field)
        if pd.isna(x):
            if field in ['B8L2','D10']:assert y is None or pd.isna(y),(field,x,y)
        else:
            assert y is not None and not pd.isna(y),(field,x,y)
            d=abs(float(x)-float(y));assert d<1e-7,(request['team_key'],field,x,y,d)
            differences[field]=d
    fs=after.get('full_state');assert fs and fs['n']==int(request['n'])
    assert fs['minimum_support']==math.ceil(int(request['n'])/2)
    return {'team_key':request['team_key'],'compared_fields':len(differences),'maximum_scalar_difference':max(differences.values(),default=0),'differences':differences,'score_status_identical':True,'geometry_validation':'saved geometry scalar invariants and frozen input/engine; full replay geometry retained; no claim that an unavailable old full geometry was compared'}

def worker(payload):
    pool,requests,before=payload;native=load_engine(SOURCE);rows=[]
    with native.Engine(full_state=True) as engine:
        for req in requests:
            key=req['team_key'];p=OUT/'trace_endpoints'/(key+'.json.gz')
            if p.exists():continue
            row=engine.evaluate(pool,req['members'].split('|'));g=row.get('geometry')
            if g is not None:
                extra=engine.scorecache.get(engine.fr.digest([row['k']==2,row.get('nodes'),g]))
                if extra:row.update(extra)
            check=parity(before[key],row,req,pool)
            row.update(data_release='v2.1',underlying_data_version='v2.1',current_repository_commit='13a7861334749805a86dc19e9ea79fcaa71020c0',trace_only_replay_existing_team=True,new_physical_team=False,trace_parity=check,trace_acquisition='missing_trace_replayed_existing_endpoint')
            write(p,row);rows.append(check)
    print(json.dumps({'pool':pool['pool_id'],'new_trace_replays':len(rows)}),flush=True)
    return rows

def main():
    requests=pd.read_csv(OUT/'TEAM_REQUESTS.csv');requests=requests[requests.mechanism_required]
    want=set(requests.team_key);rm=requests.set_index('team_key').to_dict('index');before=pd.read_csv(OUT/'SAVED_ENDPOINT_SCALARS.csv.gz',low_memory=False).set_index('team_key').to_dict('index')
    pools={p['pool_id']:p for p in read(SOURCE/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json')['images']}
    cache_paths=set()
    for base in [WS/'repo/research/workers/personnel_v21_reselection_20261029',WS/'HOHONET_v21_reaudit_20261029/stage04_cases',WS/'HOHONET_v21_AC_population_20261029/stage06_cases']:
        for p in base.rglob('*.json.gz'):
            if any('trace' in x for x in p.parts):cache_paths.add(p)
    hits={};failures=[]
    for p in sorted(cache_paths):
        try:j=read(p)
        except Exception as exc:failures.append({'path':str(p),'error':repr(exc)});continue
        values=j.get('arms',{}).values() if isinstance(j,dict) and 'arms' in j else [j]
        for row in values:
            if not isinstance(row,dict) or row.get('team_key') not in want or not row.get('full_state'):continue
            k=row['team_key'];req={'team_key':k,**rm[k]};check=parity(before[k],row,req,pools[req['pool_id']])
            dest=OUT/'trace_endpoints'/(k+'.json.gz')
            if not dest.exists():
                row.update(trace_acquisition='reused_existing_full_trace',trace_source=str(p),trace_parity=check,new_physical_team=False)
                write(dest,row)
            hits[k]=str(p)
    missing=requests[~requests.team_key.map(lambda k:(OUT/'trace_endpoints'/(k+'.json.gz')).exists())]
    write(OUT/'TRACE_CACHE_COVERAGE.json',{'searched_existing_trace_files':len(cache_paths),'cached_matching_teams':len(hits),'requested_teams':len(want),'already_present_in_this_study':len(want)-len(missing),'missing_trace_existing_teams':len(missing),'cache_hits':hits,'read_failures':failures,'new_experimental_teams':0})
    print('cache',len(hits),'missing trace',len(missing),flush=True)
    payloads=[(pools[pid],g.to_dict('records'),{k:before[k] for k in g.team_key}) for pid,g in missing.groupby('pool_id')]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as ex:
        for _ in ex.map(worker,payloads):pass
    parity_rows=[]
    for req in requests.to_dict('records'):
        j=read(OUT/'trace_endpoints'/(req['team_key']+'.json.gz'));c=parity(before[req['team_key']],j,req,pools[req['pool_id']]);c['acquisition']=j['trace_acquisition'];parity_rows.append(c)
    write(OUT/'TRACE_PARITY_FULL.json.gz',parity_rows)
    events=pd.read_csv(OUT/'ALL_EXCEPTION_EVENTS_AND_20_7_CONTEXT.csv.gz',low_memory=False)
    labels=pd.read_csv(SOURCE/'research/data/releases/v2.1/final_classification_downstream/USED_FINAL_LOBO_LABELS.csv.gz');labels=labels[labels.method=='TARGET_DSTRUCT_K3']
    lm={(x['heldout_building'],x['worker_id']):x for x in labels.to_dict('records')}
    for pid in sorted(set(requests.pool_id)):
        pool=pools[pid];pool['frozen_lobo_labels']={r['worker_id']:lm.get((pool['meta']['building'],r['worker_id'])) for r in pool['records']}
        write(OUT/'case_inputs'/(pid+'.json.gz'),pool)
    index=[]
    for row in events.to_dict('records'):
        index.append({k:row[k] for k in ['event_id','image','building','pool_id','n','m','D','X','Y','Z','A_team_key','B_team_key','C_team_key','gap_A','gap_sym','CB']})
    pd.DataFrame(index).to_csv(OUT/'MECHANISM_EVENT_INDEX.csv',index=False,encoding='utf-8-sig')
    receipt={'all_required_teams':len(want),'all_exception_images':events.image.nunique(),'event_cases_including_20_7_context':len(events),'full_state_complete':True,'reused_existing_full_traces':sum(x['acquisition']=='reused_existing_full_trace' for x in parity_rows),'trace_replays_existing_teams':sum(x['acquisition']=='missing_trace_replayed_existing_endpoint' for x in parity_rows),'new_physical_teams':0,'maximum_scalar_difference':max(x['maximum_scalar_difference'] for x in parity_rows),'source_scope':'ordinary Manual primary target; exact existing teams; no class/target/reference/fusion changes'}
    write(OUT/'TRACE_COMPLETION.json',receipt);print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
