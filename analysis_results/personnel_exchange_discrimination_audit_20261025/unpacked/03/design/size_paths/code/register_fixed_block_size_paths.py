#!/usr/bin/env python3
"""Outcome-free background-growth paths with fixed original X7/Y7/Z7.

Reads registered anchors, their registered n10/m7 events, frozen labels and the
actual pool inventory only. It never opens fusion results or runs fusion.
"""
from __future__ import annotations
from pathlib import Path
import collections,gzip,hashlib,json,math,os
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'design/size_paths'
SOURCE=ROOT/'design/target_omissions'
SNAPSHOT=ROOT/'recovery/prior_population/research/workers/personnel_population_curves_v2_20261023/inputs/INPUT_SNAPSHOT.json.gz'
SEED=2026102521

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def random_rank(value):return digest([SEED,'fixed_XYZ_background_order',value])
def people(value):return sorted(set(str(value).split('|'))-{''})
def team_key(pid,ws):return pid+'__'+digest(sorted(ws))[:20]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read_json(path):
    with (gzip.open(path,'rt') if str(path).endswith('.gz') else open(path)) as f:return json.load(f)
def save_bytes(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.partial')
    with temp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
def save_csv(df,path):
    data=df.to_csv(index=False).encode('utf-8-sig')
    if str(path).endswith('.gz'):data=gzip.compress(data,compresslevel=5,mtime=0)
    save_bytes(path,data)
def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if hasattr(value,'item'):return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value
def save_json(value,path):
    data=json.dumps(clean(value),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if str(path).endswith('.gz'):data=gzip.compress(data,compresslevel=5,mtime=0)
    save_bytes(path,data)
def vector(members,mapping,classes):
    counts=collections.Counter(mapping.get(w,'unknown') for w in members)
    return '|'.join(f'{c}:{counts[c]}' for c in classes)
def class_vector_counts(capacities):
    poly=[1]
    for cap in capacities:
        nxt=[0]*(len(poly)+cap)
        for i,v in enumerate(poly):
            for j in range(cap+1):nxt[i+j]+=v
        poly=nxt
    return poly

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    anchors=pd.read_csv(SOURCE/'ANCHORS.csv.gz')
    assert len(anchors)==286 and not anchors.anchor_id.duplicated().any()
    labels=pd.read_csv(SOURCE/'FROZEN_LABELS.csv.gz')
    labels['known']=labels.known.astype(str).str.lower().eq('true')
    mapping={(m,b):g.set_index('worker_id').class_id.to_dict() for (m,b),g in labels[labels.known].groupby(['method','heldout_building'])}
    pools={p['pool_id']:p for p in read_json(SNAPSHOT)['images']}
    ledgers={}
    for path in sorted(anchors.paired_m7_ledger.unique()):
        d=pd.read_csv(ROOT/path,low_memory=False);assert not d.event_id.duplicated().any();ledgers[path]=d.set_index('event_id')
    events=[];paths=[];steps=[];baseline=[];usages=[];requests={};n10requests={};beyondrequests={};inventory=[]
    for anchor in anchors.sort_values(['pool_id','method','anchor_index']).to_dict('records'):
        parent=ledgers[anchor['paired_m7_ledger']].loc[anchor['paired_m7_event_id']].to_dict()
        parent['event_id']=anchor['paired_m7_event_id']
        assert int(parent['n'])==10 and int(parent['m'])==7
        pid=anchor['pool_id'];pool=pools[pid];meta=pool['meta'];ws=sorted(r['worker_id'] for r in pool['records']);N=len(ws)
        assert meta['layer']=='ordinary_manual'
        lm=mapping[(anchor['method'],anchor['building'])]
        D0,X,Y,Z=[people(parent[key]) for key in ['D','X','Y','Z']]
        assert len(D0)==3 and len(X)==len(Y)==len(Z)==7 and len(set(D0+X+Y+Z))==24
        assert set(D0+X+Y+Z)<=set(ws)
        assert all(lm[w]==parent['source_class'] for w in X+Y) and all(lm[w]==parent['target_class'] for w in Z)
        assert Z==people(anchor['Z7_panel'])
        remaining=sorted(set(ws)-set(D0+X+Y+Z))
        entering=sorted(remaining,key=lambda w:random_rank([anchor['anchor_id'],parent['event_id'],pid,w]))
        remaining_class_counts=collections.Counter(lm.get(w,'unknown') for w in remaining)
        possible_class_vectors=class_vector_counts(remaining_class_counts.values())
        max_n=N-14;assert max_n==10+len(entering)
        classes=sorted(set(lm.get(w,'unknown') for w in ws))
        pathid=digest(['size_path',SEED,anchor['anchor_id'],parent['event_id'],entering])[:24]
        source_n=sum(lm.get(w)==parent['source_class'] for w in ws);target_n=sum(lm.get(w)==parent['target_class'] for w in ws)
        path=dict(parent_anchor_id=anchor['anchor_id'],path_id=pathid,pool_id=pid,image=meta['image'],building=meta['building'],
            method=parent['method'],phase=parent['phase'],source_class=parent['source_class'],target_class=parent['target_class'],
            parent_n=10,parent_m=7,parent_event_id=parent['event_id'],parent_stage=parent['stage'],parent_ledger=anchor['paired_m7_ledger'],
            pool_n=N,min_n=10,max_n=max_n,m=7,D0='|'.join(D0),X='|'.join(X),Y='|'.join(Y),Z='|'.join(Z),
            background_entry_order='|'.join(entering),remaining_people_n=len(entering),background_order_replicates=1,
            background_order_seed=SEED,n_values='|'.join(map(str,range(10,max_n+1))),
            remaining_class_capacity='|'.join(f'{c}:{v}' for c,v in sorted(remaining_class_counts.items())),
            all_feasible_n_on_this_fixed_block_path=True,all_background_permutations=False,
            feasible_background_permutations=str(math.factorial(len(entering))))
        for arm in 'ABC':
            path['n10_'+arm+'_team_key']=parent[arm+'_team_key']
        paths.append(path)
        previous=None
        for n in range(10,max_n+1):
            entrant='' if n==10 else entering[n-11]
            D=sorted(D0+entering[:n-10]);teams={arm:sorted(D+block) for arm,block in [('A',X),('B',Y),('C',Z)]}
            assert len(set(D+X+Y+Z))==n+14
            assert len(D)==n-7 and all(len(members)==n for members in teams.values())
            event={k:v for k,v in parent.items() if not k.startswith(('feasible_','planned_'))}
            event.update(event_id=digest(['fixed_block_size_event',SEED,pathid,n,D,X,Y,Z])[:24],stage='size_paths',design='strict_disjoint_ABC',
                design_variant='fixed_X7_Y7_Z7_add_one_common_background_person',n=n,m=7,pool_n=N,feasible=True,
                source_capacity=source_n,target_capacity=target_n,background_replicate=0,block_replicate=anchor['anchor_index'],
                D='|'.join(D),X='|'.join(X),Y='|'.join(Y),Z='|'.join(Z),
                original_D3='|'.join(D0),background_added_members='|'.join(entering[:n-10]),
                background_id=digest([pid,D])[:20],block_id=parent['block_id'],
                background_target_n=sum(lm.get(w)==parent['target_class'] for w in D),
                background_source_n=sum(lm.get(w)==parent['source_class'] for w in D),background_unknown_n=sum(w not in lm for w in D),
                D_class_vector=vector(D,lm,classes),replacement_fraction=7/n,source_block_fraction=7/source_n,
                source_team_block_fraction=7/(7+sum(lm.get(w)==parent['source_class'] for w in D)),
                actual_m_AB=7,actual_m_AC=7,actual_m_BC=7,seat_net_change_l1=14,
                seat_delta_AC=f"{parent['source_class']}:-7|{parent['target_class']}:+7",
                parent_anchor_id=anchor['anchor_id'],anchor_id=anchor['anchor_id'],path_id=pathid,
                parent_event_id=parent['event_id'],parent_ledger=anchor['paired_m7_ledger'],parent_stage=parent['stage'],parent_n=10,parent_m=7,
                previous_event_id='' if previous is None else previous['event_id'],previous_n=None if previous is None else previous['n'],
                entrant_worker=entrant,entrant_class='' if not entrant else lm.get(entrant,'unknown'),
                path_step=n-10,nominal_minimum_support=math.ceil(n/2),parity=n%2,
                nominal_threshold_change=None if previous is None else math.ceil(n/2)-math.ceil(previous['n']/2),
                target_block_alone_can_meet_threshold_if_unanimous=7>=math.ceil(n/2),
                additional_D_votes_needed_if_Z7_unanimous=max(0,math.ceil(n/2)-7),
                feasible_D_sets_given_original_D3_XYZ=str(math.comb(len(remaining),n-10)),
                feasible_D_class_vectors_given_original_D3_XYZ=possible_class_vectors[n-10],
                registered_D_sets_on_this_path=1,
                background_order_seed=SEED,background_order='|'.join(entering),
                n10_endpoints_referenced=True,n_changes_from_previous=previous is not None,m_changes_from_previous=False,
                condition='manual',layer=meta['layer'],fixed_XYZ_across_n=True)
            event['background_target_min']=event['background_target_n'];event['background_target_max']=event['background_target_n']
            for arm,members in teams.items():
                key=team_key(pid,members);event[arm+'_team_key']=key;event[arm+'_members']='|'.join(members);event[arm+'_class_vector']=vector(members,lm,classes)
                event['n10_'+arm+'_team_key']=parent[arm+'_team_key']
                if n==10:assert key==parent[arm+'_team_key'] and members==people(parent[arm+'_members'])
                if previous is not None:
                    earlier=set(people(previous[arm+'_members']));assert set(members)-earlier=={entrant} and earlier<=set(members)
                request=dict(pool_id=pid,team_key=key,worker_ids=members)
                requests[key]=request
                (n10requests if n==10 else beyondrequests)[key]=request
                usages.append(dict(event_id=event['event_id'],path_id=pathid,parent_anchor_id=anchor['anchor_id'],pool_id=pid,method=parent['method'],phase=parent['phase'],n=n,m=7,arm=arm,team_key=key,reference_n10_endpoint=n==10))
            assert event['A_class_vector']==event['B_class_vector']
            for a,b in [('A','B'),('A','C'),('B','C')]:assert len(set(teams[a])-set(teams[b]))==7 and len(set(teams[b])-set(teams[a]))==7
            baseline.append(dict(event_id=event['event_id'],path_id=pathid,parent_anchor_id=anchor['anchor_id'],pool_id=pid,method=parent['method'],phase=parent['phase'],
                n=n,m=7,n10_event_id=parent['event_id'],n10_event_ledger=anchor['paired_m7_ledger'],delta_n=n-10,delta_m=0,
                **{arm+'_team_key':event[arm+'_team_key'] for arm in 'ABC'},**{'n10_'+arm+'_team_key':parent[arm+'_team_key'] for arm in 'ABC'}))
            if previous is not None:
                steps.append(dict(event_id=event['event_id'],previous_event_id=previous['event_id'],path_id=pathid,parent_anchor_id=anchor['anchor_id'],
                    pool_id=pid,method=parent['method'],phase=parent['phase'],building=meta['building'],difficulty=meta['difficulty'],
                    previous_n=previous['n'],n=n,previous_m=7,m=7,delta_n=1,delta_m=0,entrant_worker=entrant,entrant_class=lm.get(entrant,'unknown'),
                    n_changed=True,m_changed=False,fixed_XYZ=True,nominal_threshold_before=math.ceil(previous['n']/2),nominal_threshold_after=math.ceil(n/2),
                    nominal_threshold_change=math.ceil(n/2)-math.ceil(previous['n']/2),
                    pair_design='same_XYZ_grow_same_D_by_one_person_in_all_three_arms',
                    **{arm+'_team_key':event[arm+'_team_key'] for arm in 'ABC'},**{'previous_'+arm+'_team_key':previous[arm+'_team_key'] for arm in 'ABC'},
                    added_people_per_arm=1,removed_people_per_arm=0,actual_m_AB=7,actual_m_AC=7,actual_m_BC=7))
            events.append(event);previous=event
        inventory.append(dict(path,events_generated=max_n-9,transitions_generated=max_n-10,feasible=True,registered_all_n=True))
    ev=pd.DataFrame(events);pathdf=pd.DataFrame(paths);pairdf=pd.DataFrame(steps)
    assert not ev.event_id.duplicated().any();assert len(pathdf)==286
    assert ev.groupby('path_id').n.apply(lambda values:list(values)==list(range(10,int(values.max())+1))).all()
    assert ev.groupby('path_id')[['X','Y','Z','block_id']].nunique().eq(1).all().all()
    assert ev.m.eq(7).all();assert not set(n10requests)&set(beyondrequests)
    save_csv(ev,OUT/'EVENTS_EXACT.csv.gz');save_json(list(requests.values()),OUT/'REQUESTS.json.gz')
    save_json(list(beyondrequests.values()),OUT/'NEW_SIZE_REQUESTS.json.gz');save_json(list(n10requests.values()),OUT/'EXISTING_N10_REQUESTS.json.gz')
    save_csv(pathdf,OUT/'ANCHOR_PATHS.csv.gz');save_csv(pairdf,OUT/'PAIR_LINKS.csv.gz');save_csv(pd.DataFrame(baseline),OUT/'BASELINE_N10_LINKS.csv.gz')
    save_csv(pd.DataFrame(usages),OUT/'ENDPOINT_REQUEST_USAGE.csv.gz');save_csv(pd.DataFrame(inventory),OUT/'CAPACITY_AND_ATTEMPTS.csv.gz')
    # Preserve the exact already-registered labels and role definitions.
    for name in ['FROZEN_LABELS.csv.gz','FOLD_ROLE_CENTERS.csv.gz','IMAGE_PHASE_ASSIGNMENT.csv']:
        save_bytes(OUT/name,(SOURCE/name).read_bytes())
    coverage=ev.groupby(['method','phase','n'],dropna=False).agg(events=('event_id','size'),anchors=('parent_anchor_id','nunique'),images=('pool_id','nunique'),buildings=('building','nunique')).reset_index();save_csv(coverage,OUT/'COVERAGE_BY_METHOD_PHASE_N.csv')
    source_paths=[SOURCE/'ANCHORS.csv.gz',SOURCE/'FROZEN_LABELS.csv.gz',SNAPSHOT]+[ROOT/p for p in ledgers]
    status=dict(stage='size_paths',seed=SEED,underlying_data='v2',anchors=len(pathdf),events=len(ev),transitions=len(pairdf),
        images=ev.pool_id.nunique(),buildings=ev.building.nunique(),methods=sorted(ev.method.unique()),
        n_min=int(ev.n.min()),n_max=int(ev.n.max()),m=7,unique_required_endpoints=len(requests),unique_referenced_n10_endpoints=len(n10requests),
        unique_beyond_n10_endpoints=len(beyondrequests),new_fusion_run=False,
        n_path='Every feasible integer n=10..N-14; X7/Y7/Z7 and original D3 fixed; remaining actual workers enter D one at a time.',
        background_sampling='One SHA256-rank permutation of all remaining workers per existing anchor. No outcomes used. Existing anchors already span members/backgrounds.',
        requests='REQUESTS is all unique required sets, with existing n10 keys preserved. NEW_SIZE_REQUESTS contains only n>10; it is not a declaration of cache misses.',
        phase_source='Original registered n10/m7 event phase and historical-role fields copied unchanged.',
        endpoint_identity='Exact native team_key(pool_id, sorted worker_ids), identical at n10 to original registered keys.',
        interpretation='Fixed blocks identify the joint background-growth and vote-threshold process. Adding one common person and changing n occur together; this is not an isolated pure-threshold intervention.',
        enumeration_scope='All feasible n on each of 286 fixed single-order paths; not all remaining-person permutations, all D sets or all pool compositions.',
        validation=dict(strict_disjoint_ABC=True,actual_m_always_7=True,fixed_XYZ=True,original_D3_preserved=True,n10_members_and_keys_exact=True,
                        every_step_adds_same_one_person_to_ABC=True,no_n_gap=True,all_labels_copied_from_registered_source=True),
        sources={str(p.relative_to(ROOT)):sha(p) for p in source_paths},code_sha256=sha(__file__))
    save_json(status,OUT/'DESIGN.json');print(json.dumps(status,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
