#!/usr/bin/env python3
"""Frozen, outcome-independent large-team structure-class replacement study.

Existing V3_BEHAVIOR LOBO labels are reused, never fitted here. Exact TURN/K3
roles E2/E3 are aligned by the saved training-centroid role map. Every feasible
background class-count vector is registered at n20, with extra concrete-member
and background replication. A linked-n supplement holds X/Y/Z fixed and nests
D; a new-source-only supplement gives an interpretable recorded-time support.

This file performs NO native fusion or target-score lookup. Endpoints are sent
to the parent study's central cache/evaluator. Every pool is checkpointed.
"""
from __future__ import annotations
import collections, gzip, hashlib, itertools, json, math, os, sys
from pathlib import Path
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
V3=ROOT/'research/workers/personnel_useful_taxonomy_v3_20261021'
PRIOR=ROOT/'research/workers/personnel_effective_exchange_conditions_20261022'
sys.path.insert(0,str(V3/'composition'))
from design_matched_events import event, gs

SEED='HOHONET-real-v2-structure-large-team-closure-20261022-v1'
METHOD='V3_BEHAVIOR'
ROLE_FILE=PRIOR/'screening/CLASS_TRAINING_ROLE_MAP.csv.gz'
LABEL_FILE=V3/'taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz'
INPUT_FILE=gs.FUSION/'INPUT_SNAPSHOT.json.gz'

def h(*v):
    return hashlib.sha256(json.dumps([SEED,*v],sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def choose(n,k): return math.comb(n,k) if 0<=k<=n else 0
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,rows):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    d=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    raw=d.to_csv(index=False).encode('utf-8-sig')
    if p.name.endswith('.gz'):raw=gzip.compress(raw,compresslevel=5,mtime=0)
    q=p.with_name(p.name+'.partial');q.write_bytes(raw);os.replace(q,p)
    return {'path':str(p.relative_to(HERE)),'rows':len(d),'sha256':sha(p),'bytes':len(raw)}
def save(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(gs.clean(obj),ensure_ascii=False,indent=2).encode()
    q=p.with_name(p.name+'.partial');q.write_bytes(raw);os.replace(q,p)
def unrank(ws,k,rank):
    ws=sorted(ws);out=[];start=0
    assert 0<=rank<choose(len(ws),k)
    for left in range(k,0,-1):
        for i in range(start,len(ws)-left+1):
            count=choose(len(ws)-i-1,left-1)
            if rank<count:out.append(ws[i]);start=i+1;break
            rank-=count
    return tuple(out)
def strata_for(S,T,O,b,m):
    return [(s,t,b-s-t,choose(len(S),s)*choose(len(T),t)*choose(len(O),b-s-t))
            for s in range(min(b,len(S)-2*m)+1)
            for t in range(min(b-s,len(T)-m)+1)
            if choose(len(O),b-s-t)]
def background(S,T,O,stratum,rank):
    s,t,o,total=stratum;ct,co=choose(len(T),t),choose(len(O),o)
    assert 0<=rank<total
    rs,rem=divmod(rank,ct*co);rt,ro=divmod(rem,co)
    return tuple(sorted(unrank(S,s,rs)+unrank(T,t,rt)+unrank(O,o,ro)))
def all_count_vectors(cap,n):
    cats=sorted(cap);out=[]
    def visit(i,left,acc):
        if i==len(cats):
            if left==0:out.append(tuple(acc))
            return
        for k in range(min(cap[cats[i]],left)+1):visit(i+1,left-k,acc+[k])
    visit(0,n,[])
    return cats,out

def balanced_subsets(ws,m,k,seed):
    """Outcome-free member-frequency balancing within a deterministic rank pool."""
    ws=sorted(ws);total=choose(len(ws),m)
    if total<=max(k,96):candidates=list(itertools.combinations(ws,m))
    else:
        ranks=set()
        for j in range(160):ranks.add(int(h('subset-rank',seed,j),16)%total)
        candidates=[unrank(ws,m,r) for r in sorted(ranks)]
    selected=[];used=collections.Counter()
    while candidates and len(selected)<k:
        x=min(candidates,key=lambda q:(sum((used[w]+1)**2-used[w]**2 for w in q),
                         max([len(set(q)&set(v)) for v in selected] or [0]),h('subset-tie',seed,q)))
        candidates.remove(x);selected.append(x);used.update(x)
    return selected,total

def balanced_pairs(ws,m,k,seed):
    """Distinct unordered disjoint X/Y pairs, then a frozen random orientation.

    No mirrored A/B events are created merely to increase event counts.
    """
    ws=sorted(ws);total=choose(len(ws),m)*choose(len(ws)-m,m)//2
    candidates=set()
    if total<=160:
        for x in itertools.combinations(ws,m):
            for y in itertools.combinations(sorted(set(ws)-set(x)),m):
                candidates.add(tuple(sorted((x,y))))
    else:
        for j in range(256):
            union=unrank(ws,2*m,int(h('source-union',seed,j),16)%choose(len(ws),2*m))
            x=unrank(union,m,int(h('source-split',seed,j),16)%choose(2*m,m))
            y=tuple(sorted(set(union)-set(x)));candidates.add(tuple(sorted((x,y))))
    candidates=sorted(candidates);selected=[];used=collections.Counter();selected_blocks=set()
    while candidates and len(selected)<k:
        pair=min(candidates,key=lambda q:(sum((used[w]+1)**2-used[w]**2 for w in q[0]+q[1]),
                    sum(v in selected_blocks for v in q),h('pair-tie',seed,q)))
        candidates.remove(pair);used.update(pair[0]+pair[1]);selected_blocks.update(pair)
        if int(h('orientation',seed,pair),16)%2:pair=pair[::-1]
        selected.append(pair)
    return selected,total

def selected_backgrounds(S,T,O,b,m,cell,deep_n):
    """Every feasible class-count stratum, plus up to six concrete deep panels."""
    strata=strata_for(S,T,O,b,m);out=[];seen=set()
    ordered=sorted(strata,key=lambda q:h('deep-stratum-order',cell,q[:3]))
    # One rank for every feasible count vector is the exact configuration census.
    for q in strata:
        rank=int(h('background-rank',cell,q[:3],0),16)%q[3]
        bg=background(S,T,O,q,rank);seen.add(bg)
        out.append(dict(stratum=q,rank=rank,bg=bg,deep=False,replicate=0))
    deep=[]
    for q in ordered[:deep_n]:
        row=next(r for r in out if r['stratum']==q);row['deep']=True;deep.append(row)
    j=1
    while len(deep)<min(deep_n,sum(q[3] for q in strata)):
        made=False
        for q in ordered:
            if len(deep)>=deep_n:break
            rank=int(h('background-rank',cell,q[:3],j),16)%q[3]
            # Resolve a repeated rank within a finite stratum, without retries forever.
            used={r['rank'] for r in out if r['stratum']==q}
            if len(used)>=q[3]:continue
            while rank in used:rank=(rank+1)%q[3]
            bg=background(S,T,O,q,rank)
            assert bg not in seen;seen.add(bg)
            row=dict(stratum=q,rank=rank,bg=bg,deep=True,replicate=j)
            out.append(row);deep.append(row);made=True
        if not made:break
        j+=1
    return out,strata

def register():
    pools=gs.pool_lookup()
    lobo=pd.read_csv(LABEL_FILE,keep_default_na=False)
    lobo=lobo[(lobo.method==METHOD)&(lobo.condition=='manual')]
    known=lobo.known.astype(str).str.lower().isin(['true','1'])
    maps={b:dict(zip(g.worker_id,g.coarse_label)) for b,g in lobo[known & lobo.heldout_building.ne('ALL')].groupby('heldout_building')}
    roles=pd.read_csv(ROLE_FILE,keep_default_na=False)
    roles=roles[(roles.method_id==METHOD)&(roles.condition=='manual')&(roles.tier=='coarse')]
    rolemap={b:{r.role_id:r._asdict() for r in g.itertuples(index=False)} for b,g in roles.groupby('heldout_building')}
    used_buildings=set();teams={};capacities=[];panels=[];parts=[];all_events=[];stratum_coverage=[];inclusion=[]
    n_paths=[];attempts=[]
    for pid,pool in sorted(pools.items()):
        meta=pool['meta']
        if meta['layer']!='ordinary_manual':continue
        labels=maps.get(meta['building'],{});rr=rolemap.get(meta['building'],{})
        if not all(x in rr for x in ['TURN/K3/E2','TURN/K3/E3']):
            attempts.append(dict(pool_id=pid,image=meta['image'],building=meta['building'],status='other_training_selected_family_or_K',n20_registered=False));continue
        # Check saved role membership against the original, frozen LOBO label table.
        for r in rr.values():
            assert {w for w,c in labels.items() if c==r['raw_class_id']}==set(r['members'].split('|'))
        used_buildings.add(meta['building']);pevents=[]
        for source_role,target_role in [('TURN/K3/E2','TURN/K3/E3'),('TURN/K3/E3','TURN/K3/E2')]:
            source,target=rr[source_role]['raw_class_id'],rr[target_role]['raw_class_id']
            for domain in ['all_formal','new_only_time_supplement']:
                workers=sorted({r['worker_id'] for r in pool['records'] if domain=='all_formal' or r['origin']=='new'} & labels.keys())
                S=sorted(w for w in workers if labels[w]==source);T=sorted(w for w in workers if labels[w]==target)
                O=sorted(set(workers)-set(S)-set(T));N=len(workers);n=20
                maxm=min(n,len(S)//2,len(T),(N-n)//2)
                requested_m=sorted({4,7,maxm}) if domain=='all_formal' else [4]
                for m in requested_m:
                    if m<4:continue
                    cell=h('cell',pid,source_role,target_role,domain,n,m)[:22]
                    strata=strata_for(S,T,O,n-m,m) if m<=maxm else []
                    total_bg=sum(q[3] for q in strata)
                    cats,vectors=all_count_vectors(collections.Counter(labels[w] for w in workers),n)
                    base={k:meta[k] for k in ['pool_id','image','building','condition','difficulty','layer']}
                    base.update(cell_id=cell,method_id=METHOD,tier='coarse',n=n,m=m,source_class=source,target_class=target,
                        source_role=source_role,target_role=target_role,source_semantics='常规表达' if source_role.endswith('E2') else '较多转折',
                        target_semantics='常规表达' if target_role.endswith('E2') else '较多转折',source_domain=domain,
                        N=N,source_capacity=len(S),target_capacity=len(T),other_capacity=len(O),max_feasible_m=maxm,
                        possible_backgrounds=str(total_bg),possible_background_count_vectors=len(strata),
                        all_n20_class_count_vectors=len(vectors),all_n20_member_sets=str(choose(N,n)),
                        training_turn_difference=float(rr[target_role]['centroid_turn_history'])-float(rr[source_role]['centroid_turn_history']),
                        unknown_workers='|'.join(sorted({r['worker_id'] for r in pool['records']}-labels.keys())),
                        status='available' if total_bg else 'insufficient_joint_capacity')
                    capacities.append(base)
                    if not total_bg:continue
                    # Sum the exact unordered-XY physical ABC population over all D.
                    possible_triples=sum(q[3]*choose(len(S)-q[0],m)*choose(len(S)-q[0]-m,m)//2*choose(len(T)-q[1],m) for q in strata)
                    base['possible_unordered_XY_ABC']=str(possible_triples)
                    deep_n=6 if domain=='all_formal' else 2
                    chosen,strata=selected_backgrounds(S,T,O,n-m,m,cell,deep_n)
                    cell_events=[];deep_panels=[]
                    for bi,bb in enumerate(chosen):
                        bg=bb['bg'];sleft=sorted(set(S)-set(bg));tleft=sorted(set(T)-set(bg));q=bb['stratum']
                        panel=h('background-panel',cell,bg)[:22]
                        pairs,total_pairs=balanced_pairs(sleft,m,4 if bb['deep'] else 1,(cell,panel))
                        targets,total_targets=balanced_subsets(tleft,m,4 if bb['deep'] else 1,(cell,panel))
                        pbase=dict(base,panel_id=panel,background_index=bi,common_background='|'.join(bg),
                            background_stratum='|'.join(map(str,q[:3])),background_rank=str(bb['rank']),
                            stratum_possible_backgrounds=str(q[3]),deep_member_panel=bb['deep'],
                            source_unordered_pairs_possible=str(total_pairs),source_pairs_registered=len(pairs),
                            target_blocks_possible=str(total_targets),target_blocks_registered=len(targets),
                            events_registered=len(pairs)*len(targets),concrete_background_replication=bb['replicate'])
                        panels.append(pbase)
                        if bb['deep']:deep_panels.append((panel,bg,pairs,targets,q))
                        for pi,(X,Y) in enumerate(pairs):
                            for zi,Z in enumerate(targets):
                                ev=event(meta,METHOD,'coarse',labels,labels,bg+X,bg+Y,bg+Z,panel_id=panel,source_domain=domain,
                                    anchor_id=f'p{pi}_z{zi}',design_scope='n20_exact_count_vectors_with_member_replication',event_mode='pure_class_block_ABC')
                                ev.update(cell_id=cell,source_class=source,target_class=target,source_role=source_role,target_role=target_role,
                                    source_semantics=base['source_semantics'],target_semantics=base['target_semantics'],
                                    source_pair_index=pi,target_block_index=zi,background_index=bi,
                                    background_stratum=pbase['background_stratum'],deep_member_panel=bb['deep'],
                                    study_group='main_n20' if domain=='all_formal' else 'new_only_n20_recorded_time',
                                    selection_partition='primary' if bi%3 else 'held_background_check',linked_n_path_id='',m=m)
                                assert ev['m_AB']==ev['m_AC']==ev['m_BC']==ev['composition_turnover_AC']==m
                                cell_events.append(ev)
                        for role,blocks in [('source',sum(([x,y] for x,y in pairs),[])),('target',targets)]:
                            count=collections.Counter(w for block in blocks for w in block)
                            universe=sleft if role=='source' else tleft
                            for w in universe:inclusion.append(dict(cell_id=cell,panel_id=panel,worker_id=w,block_role=role,
                                registered_block_appearances=count[w],eligible_for_panel=True,source_domain=domain))
                    base['registered_backgrounds']=len(chosen);base['registered_unordered_XY_ABC']=len(cell_events)
                    base['unregistered_backgrounds']=str(total_bg-len(chosen))
                    base['unregistered_unordered_XY_ABC']=str(possible_triples-len(cell_events))
                    for q in strata:
                        pp=[p for p in panels if p['cell_id']==cell and p['background_stratum']=='|'.join(map(str,q[:3]))]
                        stratum_coverage.append(dict(cell_id=cell,source_domain=domain,n=n,m=m,
                            source_role=source_role,target_role=target_role,background_stratum='|'.join(map(str,q[:3])),
                            possible_backgrounds=str(q[3]),registered_backgrounds=len(pp),registered_events=sum(p['events_registered'] for p in pp),
                            count_vector_covered=True,source_count_A=q[0]+m,target_count_A=q[1],other_count_A=q[2],
                            source_count_C=q[0],target_count_C=q[1]+m,other_count_C=q[2]))
                    pevents.extend(cell_events)
                    # Linked-n paths: two distinct saved n20 backgrounds, fixed X/Y/Z.
                    # m4/m7 are the ratio anchors; capacity-specific max m is already in n20.
                    if domain=='all_formal' and m in (4,7):
                        for li,(panel,bg,pairs,targets,q) in enumerate(deep_panels[:2]):
                            X,Y=pairs[0];Z=targets[0];used=set(X+Y+Z)
                            base_order=sorted(bg,key=lambda w:h('nested-D-inner',cell,li,w))
                            extra_order=sorted(set(workers)-used-set(bg),key=lambda w:h('nested-D-extra',cell,li,w))
                            full_order=base_order+extra_order;max_n=len(full_order)+m
                            path_id=h('linked-n',cell,li,X,Y,Z)[:22]
                            n_values=sorted({v for v in [12,16,20,21,24,max_n] if m<=v<=max_n})
                            for nn in n_values:
                                D=tuple(sorted(full_order[:nn-m]));npanel=h('n-path-panel',path_id,nn)[:22]
                                ev=event(meta,METHOD,'coarse',labels,labels,D+X,D+Y,D+Z,panel_id=npanel,source_domain=domain,
                                    anchor_id=path_id,design_scope='same_blocks_nested_background_n_path',event_mode='linked_n_pure_class_block_ABC')
                                ev.update(cell_id=cell,source_class=source,target_class=target,source_role=source_role,target_role=target_role,
                                    source_semantics=base['source_semantics'],target_semantics=base['target_semantics'],
                                    source_pair_index=0,target_block_index=0,background_index=li,
                                    background_stratum='|'.join(str(sum(w in cat for w in D)) for cat in (S,T,O)),
                                    deep_member_panel=False,study_group='linked_n',selection_partition='linked_background_check',
                                    linked_n_path_id=path_id,linked_n_reference_panel=panel,linked_n_reference_n=20,m=m)
                                pevents.append(ev)
                            n_paths.append(dict(linked_n_path_id=path_id,cell_id=cell,pool_id=pid,image=meta['image'],building=meta['building'],
                                source_role=source_role,target_role=target_role,m=m,n_values='|'.join(map(str,n_values)),
                                X='|'.join(X),Y='|'.join(Y),Z='|'.join(Z),nested_D_order='|'.join(full_order),reference_panel=panel))
        if pevents:
            assert len({e['event_id'] for e in pevents})==len(pevents)
            for ev in pevents:
                for a in 'ABC':
                    key=ev['team_'+a];ws=ev[a+'_member_workers'].split('|')
                    if key not in teams:
                        teams[key]=dict(team_key=key,**{k:meta[k] for k in ['pool_id','image','building','condition','difficulty','layer']},
                            n=ev['n'],member_workers='|'.join(ws),pool_input_sha256=gs.digest(pool),
                            first_study_group=ev['study_group'],first_cell_id=ev['cell_id'])
            parts.append(write(HERE/'registered_pools'/f'{h(pid)[:20]}.csv.gz',pevents));all_events.extend(pevents)
            print(json.dumps(dict(pool=pid,saved_events=len(pevents),total_events=len(all_events),unique_endpoints=len(teams))),flush=True)
    # Final compact tables are indexes over already saved, complete pool event files.
    outputs=[]
    for name,rows in [('EVENTS_REGISTERED.csv.gz',all_events),('ENDPOINT_REQUESTS.csv.gz',list(teams.values())),
            ('CAPACITY_AND_COVERAGE.csv.gz',capacities),('BACKGROUND_PANELS.csv.gz',panels),
            ('COUNT_VECTOR_COVERAGE.csv.gz',stratum_coverage),('MEMBER_BLOCK_INCLUSION.csv.gz',inclusion),
            ('LINKED_N_PATHS.csv.gz',n_paths),('OTHER_FOLD_FAMILIES_NOT_REGISTERED.csv',attempts),('POOL_PARTS.csv',parts)]:
        outputs.append(write(HERE/name,rows))
    outputs.append(write(HERE/'CLASS_LABELS_REUSED.csv.gz',lobo[lobo.heldout_building.isin(used_buildings|{'ALL'})]))
    outputs.append(write(HERE/'CLASS_ROLES_REUSED.csv',roles[roles.heldout_building.isin(used_buildings|{'ALL'})]))
    E=pd.DataFrame(all_events);C=pd.DataFrame(capacities);P=pd.DataFrame(panels)
    summary=E.groupby(['study_group','source_role','target_role','n','m']).agg(events=('event_id','size'),images=('image','nunique'),buildings=('building','nunique'),backgrounds=('panel_id','nunique')).reset_index()
    outputs.append(write(HERE/'REGISTERED_SUPPORT.csv',summary))
    receipt=dict(status='frozen_before_target_endpoint_evaluation',data_release='real_v2',research_round='closure_20261022',
        seed=SEED,source_main='8bfd3e476bd5ae6edc1424e2c8ea07dd2f69a235',
        previous_findings_retained='old exact TURN/K3 E2→E3 n10/m7; not recomputed by this registration',
        labels='unchanged original LOBO V3_BEHAVIOR; same raw class numbers never assumed comparable across buildings; exact training roles used',
        selected_directions=['TURN/K3/E2→TURN/K3/E3','TURN/K3/E3→TURN/K3/E2'],
        main_n=20,requested_m='4,7 and largest feasible m>=4; deduplicated per cell',
        configuration_policy='Every feasible n20 pure-block background class-count vector for each selected direction/domain/n/m; not all n20 unconstrained vectors or all concrete teams.',
        member_policy='Six distinct deep backgrounds per all-formal cell if available, 4 disjoint unordered source pairs and 4 target blocks. Additional count vectors get one pair and one target. Hash candidate pools are greedily balanced for member appearances.',
        orientation='One frozen random A/B orientation per unordered source pair. No mirrored events added.',
        linked_n='Two actual n20 deep backgrounds per m4/m7 cell; identical X/Y/Z; D nested across supported 12/16/20/21/24/max n. n20 endpoints reused.',
        time_supplement='new-origin-only n20/m4, all feasible count vectors; two deep backgrounds; separate from all-formal effects',
        interpretation='Internal v2 checks on outcome-independent newly selected teams/backgrounds; not a new external blind dataset.',
        eligibility='ordinary_manual formal frozen pool only; doorway/special scope not pooled into primary estimates',
        unique_endpoint_requests=len(teams),registered_events=len(E),unique_physical_triples=E.physical_triple_id.nunique(),
        selected_images=E.image.nunique(),selected_buildings=E.building.nunique(),
        selected_n_values=sorted(map(int,E.n.unique())),selected_m_values=sorted(map(int,E.m.unique())),
        n20_available_cells=int(C.status.eq('available').sum()),n20_registered_backgrounds=len(P),
        n20_feasible_count_vectors=int(C.loc[C.status.eq('available'),'possible_background_count_vectors'].sum()),
        n20_registered_count_vectors=len(stratum_coverage),native_calls=0,
        inputs=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in [INPUT_FILE,LABEL_FILE,ROLE_FILE]],
        outputs=outputs,script_sha256=sha(Path(__file__)))
    save(HERE/'DESIGN_FREEZE.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['inputs','outputs']},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':register()
