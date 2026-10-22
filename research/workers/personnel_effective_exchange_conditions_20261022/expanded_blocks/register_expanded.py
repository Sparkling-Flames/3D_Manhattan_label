#!/usr/bin/env python3
"""Outcome-independent finite expansion of the three historical conditions.

Two distinct feasible backgrounds are selected by exact combinatorial rank,
without enumerating millions of backgrounds. Within each background every
registered source and target block is enumerated. m5/m6 use all m-of-2m
source subsets; m7/m9 use every one-per-pair source subset. B is the exact
complement of A in the registered source reservoir. Native endpoints are
deduplicated globally; event files are saved after every image/direction.
"""
from __future__ import annotations
import collections, hashlib, itertools, json, math, os, sys
from pathlib import Path
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import pandas as pd
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from run_native import gs,write_csv,prior,V3,REPO
sys.path.insert(0,str(V3/'composition'))
from design_matched_events import label_maps,event

SEED='HOHONET-real-v2-effective-conditions-20261022-background-and-members-v1'
SCHEMES=[('A2_relation','single',17,9),('M_structure','fine',10,5),
         ('M_structure','fine',10,6),('V3_BEHAVIOR','coarse',10,7)]

def digest(*x):return hashlib.sha256(json.dumps([SEED,*x],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def choose(n,k):return math.comb(n,k) if 0<=k<=n else 0
def unrank(ws,k,rank):
    """Lexicographic exact k-subset unranking, zero indexed."""
    ws=sorted(ws);out=[];start=0
    assert 0<=rank<choose(len(ws),k)
    for left in range(k,0,-1):
        for i in range(start,len(ws)-left+1):
            count=choose(len(ws)-i-1,left-1)
            if rank<count:out.append(ws[i]);start=i+1;break
            rank-=count
    return out

def background_strata(S,T,O,b,m):
    out=[]
    for s in range(min(b,len(S)-2*m)+1):
        for t in range(min(b-s,len(T)-m)+1):
            o=b-s-t
            c=choose(len(S),s)*choose(len(T),t)*choose(len(O),o)
            if c:out.append((s,t,o,c))
    return out

def background_at(S,T,O,strata,rank):
    for s,t,o,count in strata:
        if rank>=count:rank-=count;continue
        ct,co=choose(len(T),t),choose(len(O),o)
        rs,remain=divmod(rank,ct*co);rt,ro=divmod(remain,co)
        return sorted(unrank(S,s,rs)+unrank(T,t,rt)+unrank(O,o,ro))
    raise ValueError('background rank out of range')

def register():
    maps,_=label_maps();pools=gs.pool_lookup()
    roles=pd.read_csv(HERE.parent/'screening/CLASS_TRAINING_ROLE_MAP.csv.gz',keep_default_na=False)
    rolemap={(r.method_id,r.tier,r.condition,r.heldout_building,r.raw_class_id):r._asdict() for r in roles.itertuples(index=False)}
    seeds=pd.read_csv(HERE.parent/'screening/PRIORITY_SEED_EVENTS.csv.gz',keep_default_na=False)
    seedm=pd.to_numeric(seeds.m_AB,errors='coerce').fillna(pd.to_numeric(seeds.m_AC,errors='coerce')).astype(int)
    seedkeys=set(zip(seeds.method_id,seeds.n.astype(int),seedm,seeds.pool_id))
    allteams={};capacity=[];panels=[];parts=[];total_events=0
    for pid,pool in sorted(pools.items()):
        meta=pool['meta'];cond=meta['condition'];building=meta['building']
        if cond!='manual':continue
        for method,tier,n,m in SCHEMES:
            labels,parents=maps.get((method,tier,cond,building),({},{}))
            ws=sorted({r['worker_id'] for r in pool['records']} & labels.keys())
            byclass={c:sorted(w for w in ws if labels[w]==c) for c in sorted({labels[w] for w in ws})}
            for source,S in byclass.items():
                for target,T in byclass.items():
                    if source==target:continue
                    if method=='M_structure' and (source,target)!=('M01','M00'):continue
                    O=sorted(set(ws)-set(S)-set(T));b=n-m
                    strata=background_strata(S,T,O,b,m) if len(S)>=2*m and len(T)>=m and len(ws)>=n+2*m else []
                    total_bg=sum(q[3] for q in strata)
                    cellid=digest(pid,method,tier,n,m,source,target)[:20]
                    base={k:meta[k] for k in ['pool_id','image','building','condition','difficulty','layer']}
                    base.update(cell_id=cellid,method_id=method,tier=tier,n=n,m=m,
                        source_class=source,target_class=target,N=len(ws),source_capacity=len(S),target_capacity=len(T),
                        unknown_workers='|'.join(sorted({r['worker_id'] for r in pool['records']}-labels.keys())),
                        possible_backgrounds=total_bg,registered_backgrounds=min(2,total_bg),
                        unregistered_backgrounds=max(0,total_bg-2),
                        overlap_priority_seed_image=(method,n,m,pid) in seedkeys,
                        status='available' if total_bg else 'insufficient_joint_capacity')
                    r0=rolemap.get((method,tier,cond,building,source),{})
                    r1=rolemap.get((method,tier,cond,building,target),{})
                    base.update(source_role=r0.get('role_id',source),target_role=r1.get('role_id',target),selected_family=r0.get('selected_family',''))
                    a=pd.to_numeric(r0.get('centroid_turn_history'),errors='coerce');z=pd.to_numeric(r1.get('centroid_turn_history'),errors='coerce')
                    base['training_turn_difference']=z-a
                    base['training_turn_direction']='increase' if z>a else 'decrease' if z<a else 'unknown_or_equal'
                    capacity.append(base)
                    if not total_bg:continue
                    ranks=[]
                    for bi in range(min(2,total_bg)):
                        rank=int(digest('background-rank',cellid,bi),16)%total_bg
                        while rank in ranks:rank=(rank+1)%total_bg
                        ranks.append(rank)
                    part_events=[]
                    for bi,rank in enumerate(ranks):
                        bg=background_at(S,T,O,strata,rank);sb=set(bg)
                        sr=sorted(sorted(set(S)-sb,key=lambda w:digest('source-reservoir',cellid,bi,w))[:2*m])
                        tr=sorted(sorted(set(T)-sb,key=lambda w:digest('target-reservoir',cellid,bi,w))[:m+1])
                        assert len(sr)==2*m and len(tr)>=m
                        ordered=sorted(sr,key=lambda w:digest('source-pair',cellid,bi,w))
                        pairs=[ordered[2*i:2*i+2] for i in range(m)]
                        sourceblocks=list(itertools.combinations(sr,m)) if m<=6 else [tuple(sorted(pairs[i][a] for i,a in enumerate(bits))) for bits in itertools.product((0,1),repeat=m)]
                        targets=list(itertools.combinations(tr,m))
                        panelid=f'exchange20261022_{cellid}_bg{bi}'
                        full_source_n=choose(len(set(S)-sb),m)
                        full_target_n=choose(len(set(T)-sb),m)
                        # Ordered A/B disjoint blocks and C target block in the full pool.
                        full_abc=full_source_n*choose(len(set(S)-sb)-m,m)*full_target_n
                        panel=dict(base,panel_id=panelid,background_index=bi,background_exact_rank=rank,
                            common_background='|'.join(bg),source_reservoir='|'.join(sr),target_reservoir='|'.join(tr),
                            paired_source_slots=json.dumps(pairs,separators=(',',':')) if m>=7 else '',
                            member_design='all_m_of_2m' if m<=6 else 'all_one_per_frozen_pair',
                            full_source_blocks=full_source_n,full_target_blocks=full_target_n,
                            registered_source_blocks=len(sourceblocks),registered_target_blocks=len(targets),
                            possible_oriented_ABC_full_background=str(full_abc),registered_oriented_ABC=len(sourceblocks)*len(targets),
                            unregistered_oriented_ABC_full_background=str(full_abc-len(sourceblocks)*len(targets)),
                            possible_source_class_configurations=1,possible_target_class_configurations=1,
                            registered_endpoint_configurations=2,all_orders_enumerated=False)
                        panels.append(panel)
                        allsr=set(sr)
                        for xi,X in enumerate(sourceblocks):
                            Y=sorted(allsr-set(X))
                            A=sorted(bg+list(X));B=sorted(bg+Y)
                            for zi,Z in enumerate(targets):
                                C=sorted(bg+list(Z))
                                ev=event(meta,method,tier,labels,parents,A,B,C,panel_id=panelid,
                                    source_domain='all_formal_label_known',anchor_id=f'x{xi}_z{zi}',
                                    design_scope='within_parent_fine_change' if method=='M_structure' else 'pure_class_direction',
                                    event_mode='expanded_finite_member_census')
                                ev.update(cell_id=cellid,source_class=source,target_class=target,
                                    source_role=base['source_role'],target_role=base['target_role'],selected_family=base['selected_family'],
                                    training_turn_difference=base['training_turn_difference'],training_turn_direction=base['training_turn_direction'],
                                    background_index=bi,member_design=panel['member_design'],overlap_priority_seed_image=base['overlap_priority_seed_image'],
                                    registered_source_blocks=len(sourceblocks),registered_target_blocks=len(targets),
                                    underlying_data_version='v2')
                                assert ev['m_AB']==ev['m_AC']==ev['m_BC']==ev['composition_turnover_AC']==m
                                if method=='M_structure':assert ev['within_parent_fine_change']
                                part_events.append(ev)
                                for workers in (A,B,C):
                                    key=gs.team_key(pid,workers)
                                    if key not in allteams:allteams[key]=dict(team_key=key,pool_id=pid,n=n,member_workers='|'.join(workers))
                    path=HERE/'design_parts'/f'{method}_n{n}_m{m}'/(cellid+'.csv.gz')
                    receipt=write_csv(path,part_events)
                    total_events+=len(part_events)
                    parts.append(dict(cell_id=cellid,method_id=method,n=n,m=m,pool_id=pid,image=meta['image'],building=building,
                        path=str(path.relative_to(REPO)),events=len(part_events),sha256=receipt['sha256'],bytes=receipt['bytes']))
                    gs.save(HERE/'REGISTRATION_PROGRESS.json',dict(cells=len(parts),events=total_events,unique_teams=len(allteams)))
                    print(json.dumps(dict(cell=cellid,method=method,m=m,events=len(part_events),teams_so_far=len(allteams))),flush=True)
    write_csv(HERE/'CAPACITY_ALL_ATTEMPTS.csv.gz',capacity)
    write_csv(HERE/'REGISTERED_MEMBER_PANELS.csv.gz',panels)
    write_csv(HERE/'REGISTERED_EVENT_PARTS.csv',parts)
    write_csv(HERE/'ALL_TEAMS_REGISTERED.csv.gz',pd.DataFrame(allteams.values()).sort_values(['pool_id','team_key']))
    summary=[]
    for (method,n,m),g in pd.DataFrame(panels).groupby(['method_id','n','m']):
        summary.append(dict(method_id=method,n=int(n),m=int(m),images=g.image.nunique(),buildings=g.building.nunique(),
            directions=g.cell_id.nunique(),backgrounds=len(g),registered_events=int(g.registered_oriented_ABC.sum()),
            source_design='all_m_of_2m' if m<=6 else 'all_one_per_frozen_pair',
            new_relative_seed_images=g[~g.overlap_priority_seed_image].image.nunique()))
    write_csv(HERE/'REGISTRATION_SUMMARY.csv',summary)
    gs.save(HERE/'DESIGN_FREEZE.json',dict(status='frozen_before_new_endpoint_evaluation',underlying_data_version='v2',
        seed=SEED,schemes=SCHEMES,unique_teams=len(allteams),oriented_events=total_events,cells=len(parts),panels=len(panels),
        selection='All capacity-feasible images and directed classes for the four predeclared scheme/n/m cells. Two distinct feasible backgrounds chosen by exact integer rank and frozen hash, or all if fewer. Within background, source 2m reservoir and target at most m+1 reservoir chosen by frozen hash. Full m-of-2m source census for m5,m6; full one-per-pair census for m7,m9; full target m-subset census. B is complementary source block. Target outcomes not read.',
        not_a_full_pool_member_census=True,all_feasible_directions_in_registered_schemes=True,
        all_failures_to_be_retained=True,ordinary_doorway_special_layers_retained_separately=True,
        endpoint_request_sha256=prior.sha(HERE/'ALL_TEAMS_REGISTERED.csv.gz'),
        event_part_index_sha256=prior.sha(HERE/'REGISTERED_EVENT_PARTS.csv'),summary=summary))
    print(json.dumps(dict(status='registered',unique_teams=len(allteams),oriented_events=total_events,summary=summary),ensure_ascii=False),flush=True)

if __name__=='__main__':register()
