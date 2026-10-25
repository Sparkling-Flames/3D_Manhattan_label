#!/usr/bin/env python3
"""Register direct AC tails beyond strict ABC capacity; no results read/fused."""
from __future__ import annotations
import collections,gzip,hashlib,json,math,os
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'design/size_paths'
OUT=ROOT/'design/large_team_ac_tail'
SEED=2026102528

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def people(v):return sorted(set(str(v).split('|'))-{''})
def team_key(pid,ws):return pid+'__'+digest(sorted(ws))[:20]
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if hasattr(v,'item'):return clean(v.item())
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def write_bytes(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.partial')
 with t.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 os.replace(t,p)
def save_csv(d,p):
 b=d.to_csv(index=False).encode('utf-8-sig')
 if str(p).endswith('.gz'):b=gzip.compress(b,compresslevel=5,mtime=0)
 write_bytes(p,b)
def save_json(d,p):
 b=(json.dumps(clean(d),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
 if str(p).endswith('.gz'):b=gzip.compress(b,compresslevel=5,mtime=0)
 write_bytes(p,b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def vector(ws,mapping,classes):
 c=collections.Counter(mapping.get(w,'unknown') for w in ws)
 return '|'.join(f'{k}:{c[k]}' for k in classes)

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 original=pd.read_csv(SOURCE/'EVENTS_EXACT.csv.gz',low_memory=False)
 labels=pd.read_csv(SOURCE/'FROZEN_LABELS.csv.gz')
 labels['known']=labels.known.astype(str).str.lower().eq('true')
 lm={(m,b):g.set_index('worker_id').class_id.to_dict() for (m,b),g in labels[labels.known].groupby(['method','heldout_building'])}
 tails=original.sort_values('n').groupby('path_id').tail(1).sort_values(['pool_id','method','parent_anchor_id'])
 assert len(tails)==286
 events=[];paths=[];steps=[];usage=[];base_links=[];req={};new_req={};existing={}
 for parent in tails.to_dict('records'):
  D0,X,Y,Z=[people(parent[c]) for c in ['D','X','Y','Z']]
  pool=sorted(D0+X+Y+Z);N=int(parent['pool_n']);mapping=lm[(parent['method'],parent['building'])]
  assert len(pool)==len(set(pool))==N and len(X)==len(Y)==len(Z)==7
  assert int(parent['n'])==N-14
  assert all(mapping[w]==parent['source_class'] for w in X+Y)
  assert all(mapping[w]==parent['target_class'] for w in Z)
  order=sorted(Y,key=lambda w:digest([SEED,'source_class_enters_large_AC_background',parent['path_id'],w]))
  pathid=digest(['large_team_direct_AC_tail',SEED,parent['path_id'],order])[:24]
  classes=sorted(set(mapping.get(w,'unknown') for w in pool))
  min_n=N-14;max_n=N-7
  path=dict(path_id=pathid,strict_size_path_id=parent['path_id'],parent_anchor_id=parent['parent_anchor_id'],
   strict_tail_event_id=parent['event_id'],pool_id=parent['pool_id'],image=parent['image'],building=parent['building'],
   method=parent['method'],phase=parent['phase'],difficulty=parent['difficulty'],source_class=parent['source_class'],target_class=parent['target_class'],
   pool_n=N,min_n=min_n,max_n=max_n,m=7,D0='|'.join(D0),X='|'.join(X),Z='|'.join(Z),
   original_Y7='|'.join(Y),source_background_entry_order='|'.join(order),background_order_seed=SEED,
   all_possible_Y_orders=math.factorial(7),registered_Y_orders=1,registered_all_n=True,
   strict_A_team_key=parent['A_team_key'],strict_C_team_key=parent['C_team_key'],
   same_class_B_control_available=False,condition='manual',layer=parent['layer'])
  paths.append(path);prev=None
  for k in range(8):
   n=min_n+k;D=sorted(D0+order[:k]);entrant='' if k==0 else order[k-1]
   event={c:v for c,v in parent.items() if c not in ['Y','actual_m_AB','actual_m_BC'] and not c.startswith(('B_','n10_B_','feasible_D_','previous_'))}
   # Remove stale strict-ABC path fields: the original Y block now enters D.
   for c in ['fixed_XYZ_across_n','background_added_members','background_order','n10_endpoints_referenced']:
    event.pop(c,None)
   event.update(event_id=digest(['direct_AC_tail_event',SEED,pathid,n,D,X,Z])[:24],
    path_id=pathid,strict_size_path_id=parent['path_id'],strict_tail_event_id=parent['event_id'],
    parent_event_id=parent['event_id'],parent_ledger='design/size_paths/EVENTS_EXACT.csv.gz',parent_stage='size_paths',parent_n=min_n,
    design='direct_disjoint_AC',design_variant='fixed_X7_Z7_original_Y7_enters_common_D',stage='large_team_ac_tail',
    n=n,m=7,path_step=k,tail_step=k,tail_min_n=min_n,tail_max_n=max_n,feasible=True,
    D='|'.join(D),X='|'.join(X),Z='|'.join(Z),original_Y7='|'.join(Y),original_strict_tail_D='|'.join(D0),
    source_Y_entered='|'.join(order[:k]),source_Y_not_yet_entered='|'.join(order[k:]),
    source_background_entry_order='|'.join(order),background_order_seed=SEED,
    background_id=digest([parent['pool_id'],D])[:20],D_class_vector=vector(D,mapping,classes),
    background_target_n=sum(mapping.get(w)==parent['target_class'] for w in D),
    background_source_n=sum(mapping.get(w)==parent['source_class'] for w in D),
    background_unknown_n=sum(w not in mapping for w in D),
    replacement_fraction=7/n,actual_m_AC=7,seat_net_change_l1=14,
    source_team_block_fraction=7/(7+sum(mapping.get(w)==parent['source_class'] for w in D)),
    entrant_worker=entrant,entrant_class='' if not entrant else mapping[entrant],entrant_role='' if not entrant else 'source',
    previous_event_id='' if prev is None else prev['event_id'],previous_n=None if prev is None else prev['n'],
    n_changes_from_previous=prev is not None,m_changes_from_previous=False,
    nominal_minimum_support=math.ceil(n/2),parity=n%2,
    nominal_threshold_change=None if prev is None else math.ceil(n/2)-math.ceil(prev['n']/2),
    additional_D_votes_needed_if_Z7_unanimous=max(0,math.ceil(n/2)-7),
    target_block_alone_can_meet_threshold_if_unanimous=7>=math.ceil(n/2),
    feasible_Y_background_sets_this_step=math.comb(7,k),feasible_Y_background_class_vectors_this_step=1,registered_background_sets_this_step=1,
    fixed_XZ_across_n=True,same_class_B_control_available=False,evaluation_pairs='AC',
    strict_tail_endpoint_reference=k==0,strict_tail_A_team_key=parent['A_team_key'],strict_tail_C_team_key=parent['C_team_key'])
   event['background_target_min']=event['background_target_n'];event['background_target_max']=event['background_target_n']
   arms={'A':sorted(D+X),'C':sorted(D+Z)}
   assert len(D)==n-7 and len(set(D+X+Z))==n+7 and not(set(D)&set(X+Z))
   for arm,ws in arms.items():
    assert len(ws)==len(set(ws))==n
    key=team_key(parent['pool_id'],ws);event[arm+'_team_key']=key;event[arm+'_members']='|'.join(ws);event[arm+'_class_vector']=vector(ws,mapping,classes)
    if k==0:assert key==parent[arm+'_team_key']
    if prev is not None:assert set(ws)-set(people(prev[arm+'_members']))=={entrant}
    request=dict(pool_id=parent['pool_id'],team_key=key,worker_ids=ws);req[key]=request
    (existing if k==0 else new_req)[key]=request
    usage.append(dict(event_id=event['event_id'],path_id=pathid,parent_anchor_id=parent['parent_anchor_id'],pool_id=parent['pool_id'],method=parent['method'],phase=parent['phase'],n=n,m=7,tail_step=k,arm=arm,team_key=key,strict_tail_endpoint_reference=k==0))
   assert len(set(arms['A'])-set(arms['C']))==len(set(arms['C'])-set(arms['A']))==7
   base_links.append(dict(event_id=event['event_id'],path_id=pathid,pool_id=parent['pool_id'],method=parent['method'],phase=parent['phase'],n=n,m=7,
    strict_size_path_id=parent['path_id'],strict_tail_event_id=parent['event_id'],strict_tail_n=min_n,delta_n_from_strict_tail=k,delta_m=0,
    A_team_key=event['A_team_key'],C_team_key=event['C_team_key'],strict_tail_A_team_key=parent['A_team_key'],strict_tail_C_team_key=parent['C_team_key']))
   if prev is not None:
    steps.append(dict(event_id=event['event_id'],previous_event_id=prev['event_id'],path_id=pathid,parent_anchor_id=parent['parent_anchor_id'],
     pool_id=parent['pool_id'],image=parent['image'],building=parent['building'],difficulty=parent['difficulty'],method=parent['method'],phase=parent['phase'],
     n=n,previous_n=prev['n'],m=7,previous_m=7,delta_n=1,delta_m=0,tail_step=k,entrant_worker=entrant,entrant_class=mapping[entrant],entrant_role='source',
     nominal_threshold_before=math.ceil(prev['n']/2),nominal_threshold_after=math.ceil(n/2),nominal_threshold_change=math.ceil(n/2)-math.ceil(prev['n']/2),
     fixed_XZ=True,same_class_B_control_available=False,pair_design='same_XZ_one_original_Y_person_enters_both_A_C',
     A_team_key=event['A_team_key'],C_team_key=event['C_team_key'],previous_A_team_key=prev['A_team_key'],previous_C_team_key=prev['C_team_key']))
   events.append(event);prev=event
  assert set(people(prev['D'])+X+Z)==set(pool)
 ev=pd.DataFrame(events);pa=pd.DataFrame(paths);st=pd.DataFrame(steps)
 assert len(ev)==286*8 and len(st)==286*7 and not ev.event_id.duplicated().any()
 assert ev.groupby('path_id')[['X','Z']].nunique().eq(1).all().all()
 assert not set(existing)&set(new_req)
 save_csv(ev,OUT/'EVENTS_EXACT.csv.gz');save_csv(pa,OUT/'ANCHOR_PATHS.csv.gz');save_csv(st,OUT/'PAIR_LINKS.csv.gz')
 save_csv(pd.DataFrame(base_links),OUT/'STRICT_TAIL_LINKS.csv.gz');save_csv(pd.DataFrame(usage),OUT/'ENDPOINT_REQUEST_USAGE.csv.gz')
 save_json(list(req.values()),OUT/'REQUESTS.json.gz');save_json(list(new_req.values()),OUT/'NEW_TAIL_REQUESTS.json.gz');save_json(list(existing.values()),OUT/'EXISTING_STRICT_TAIL_REQUESTS.json.gz')
 save_csv(ev.groupby(['method','phase','n'],dropna=False).agg(events=('event_id','size'),paths=('path_id','nunique'),images=('pool_id','nunique'),buildings=('building','nunique')).reset_index(),OUT/'COVERAGE_BY_METHOD_PHASE_N.csv')
 for name in ['FROZEN_LABELS.csv.gz','FOLD_ROLE_CENTERS.csv.gz','IMAGE_PHASE_ASSIGNMENT.csv']:
  write_bytes(OUT/name,(SOURCE/name).read_bytes())
 receipt=dict(stage='large_team_ac_tail',underlying_data='v2',seed=SEED,paths=len(pa),events=len(ev),transitions=len(st),images=ev.pool_id.nunique(),buildings=ev.building.nunique(),
  n_min=int(ev.n.min()),n_max=int(ev.n.max()),m=7,unique_required_endpoints=len(req),referenced_strict_tail_endpoints=len(existing),n_above_tail_registered_endpoint_sets=len(new_req),
  fusion_run=False,outcome_files_read=False,design='Direct AC only: X7/Z7 fixed; original Y7 enters D one at a time in a SHA256-rank permutation; B not defined.',
  strict_limit='Original strict ABC ends at n=N-14. AC tail covers n=N-14..N-7, and can use n28 when N35. This is not n28 strict ABC.',
  scope='All feasible n along each registered order, not all 7! Y orders or all concrete member sets.',
  comparison='Estimate signed CA, absolute AC geometry/quality change, per-arm scale path, time and failures; no within-vs-cross amplitude claim without B.',
  endpoint_note='New tail request file is a registration subset, not a declaration of cache misses. Exact deterministic endpoints are deduplicated by pool and member set.',
  inputs={str(SOURCE/p):sha(SOURCE/p) for p in ['EVENTS_EXACT.csv.gz','FROZEN_LABELS.csv.gz']},code_sha256=sha(__file__))
 save_json(receipt,OUT/'DESIGN.json')
 manifest=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='FILE_MANIFEST.csv' and '__pycache__' not in str(p)]
 save_csv(pd.DataFrame(manifest),OUT/'FILE_MANIFEST.csv');print(json.dumps(clean(receipt),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
