#!/usr/bin/env python3
"""Finite fixed-XYZ background experiment, frozen real-v2 fusion and labels.

Two outcome-independent pre-registered XYZ anchors per feasible image; enumerate
ALL 14 backgrounds of size 13 remaining after the disjoint three seven-person
blocks. This is a full finite background census for the registered blocks,
not all possible XYZ blocks in the original personnel pool.
"""
from pathlib import Path
import argparse,itertools,json,os,sys
import pandas as pd
HERE=Path(__file__).resolve().parent
OLD=HERE.parents[1]/'personnel_exchange_closure_20261022'
sys.path[:0]=[str(OLD/'structure'),str(OLD)]
import register_structure as rs
import run_native_closure as adapter
from analyze_existing import save
gs=rs.gs
OUT=HERE/'background_gradient'
NATIVE=OUT/'native'

def write_json(p,obj):
    adapter.durable_save(p,obj)

def register():
    OUT.mkdir(parents=True,exist_ok=True)
    # Registration reads memberships, capacities and histories only, not Q.
    reg=pd.read_csv(OLD/'structure/EVENTS_REGISTERED.csv.gz',keep_default_na=False)
    cap=pd.read_csv(OLD/'structure/CAPACITY_AND_COVERAGE.csv.gz',keep_default_na=False)
    cap=cap[cap.source_domain.eq('all_formal')&cap.source_role.eq('TURN/K3/E2')&cap.m.eq(7)&cap.status.eq('available')]
    cap=cap[cap.N.eq(35)&cap.source_capacity.gt(14)&cap.target_capacity.gt(7)]
    labs=pd.read_csv(OLD/'structure/CLASS_LABELS_REUSED.csv.gz',keep_default_na=False)
    labs=labs[labs.known.astype(str).str.lower().isin(['true','1'])]
    labels={b:dict(zip(g.worker_id,g.coarse_label)) for b,g in labs.groupby('heldout_building')}
    pools=gs.pool_lookup();cache=adapter.cache_index()
    rows=[];anchors=[];requests={};capacity=[]
    for r in cap.to_dict('records'):
        pid=r['pool_id'];pool=pools[pid];lab=labels[r['building']]
        W=sorted({z['worker_id'] for z in pool['records']}&lab.keys());assert len(W)==35
        G=reg[reg.pool_id.eq(pid)&reg.study_group.eq('main_n20')&reg.source_role.eq('TURN/K3/E2')&reg.m.eq(7)&reg.source_pair_index.eq(0)&reg.target_block_index.eq(0)&reg.deep_member_panel.eq(True)]
        G=G.sort_values(['background_index','event_id']).head(2)
        assert len(G)==2
        for anchor_index,a in enumerate(G.to_dict('records')):
            X=tuple(a['outgoing_block_X'].split('|'));Y=tuple(a['same_count_block_Y'].split('|'));Z=tuple(a['changed_count_block_Z'].split('|'))
            U=sorted(set(W)-set(X+Y+Z));assert len(U)==14
            aid=rs.h('followup-fixed-XYZ-D',a['event_id'])[:24]
            an=dict(anchor_id=aid,anchor_index=anchor_index,pool_id=pid,image=r['image'],building=r['building'],difficulty=r['difficulty'],n=20,m=7,
                source_role=r['source_role'],target_role=r['target_role'],source_class=r['source_class'],target_class=r['target_class'],
                old_anchor_event=a['event_id'],X='|'.join(X),Y='|'.join(Y),Z='|'.join(Z),background_universe='|'.join(U),
                background_universe_source=sum(lab[w]==r['source_class'] for w in U),background_universe_target=sum(lab[w]==r['target_class'] for w in U),
                full_backgrounds=14,full_pool_unordered_ABC=r['possible_unordered_XY_ABC'])
            anchors.append(an)
            for i,D in enumerate(itertools.combinations(U,13)):
                omitted=next(w for w in U if w not in D)
                panel=rs.h('followup-fixed-XYZ-D-panel',aid,D)[:24]
                ev=rs.event(pool['meta'],'V3_BEHAVIOR','coarse',lab,lab,D+X,D+Y,D+Z,panel_id=panel,source_domain='all_formal',anchor_id=aid,
                    design_scope='fixed_XYZ_complete_14_choose_13_background_census',event_mode='fixed_XYZ_background_gradient_ABC')
                ev.update(study_group='fixed_XYZ_background_gradient',cell_id=r['cell_id'],m=7,source_class=r['source_class'],target_class=r['target_class'],
                    source_role=r['source_role'],target_role=r['target_role'],source_semantics='常规表达',target_semantics='较多转折',
                    background_index=i,background_stratum='|'.join(str(sum(lab[w]==c for w in D)) for c in [r['source_class'],r['target_class']])+'|'+str(sum(lab[w] not in [r['source_class'],r['target_class']] for w in D)),
                    omitted_worker=omitted,omitted_class=lab[omitted],anchor_index=anchor_index,old_anchor_event=a['event_id'],
                    selection_partition='outcome_independent_registered_member_background_extension',background_target_seats=sum(lab[w]==r['target_class'] for w in D),
                    background_source_seats=sum(lab[w]==r['source_class'] for w in D),background_other_seats=sum(lab[w] not in [r['source_class'],r['target_class']] for w in D))
                assert ev['m_AB']==ev['m_AC']==ev['m_BC']==ev['composition_turnover_AC']==7
                rows.append(ev)
                for arm in 'ABC':
                    key=ev['team_'+arm]
                    requests.setdefault(key,dict(team_key=key,pool_id=pid,image=r['image'],building=r['building'],condition='manual',difficulty=r['difficulty'],layer='ordinary_manual',
                        n=20,member_workers=ev[arm+'_member_workers'],pool_input_sha256=gs.digest(pool),cached=key in cache,cache_source=cache.get(key,'')))
        capacity.append(dict(pool_id=pid,image=r['image'],building=r['building'],N=35,source_capacity=r['source_capacity'],target_capacity=r['target_capacity'],other_capacity=r['other_capacity'],
            registered_XYZ_anchors=2,possible_backgrounds_per_anchor=14,registered_backgrounds_per_anchor=14,registered_ABC_events=28,
            full_pool_unordered_ABC=r['possible_unordered_XY_ABC'],scope='两个历史预登记XYZ锚点；各锚点剩余14选13的全部背景；未穷尽全部XYZ'))
    E=pd.DataFrame(rows);R=pd.DataFrame(requests.values());A=pd.DataFrame(anchors)
    assert len(cap)==39 and len(A)==78 and len(E)==1092
    save('background_gradient/EVENTS_REGISTERED.csv.gz',E)
    save('background_gradient/ANCHORS_EXACT.csv',A)
    save('background_gradient/ENDPOINT_REQUESTS.csv.gz',R)
    save('background_gradient/FINITE_COVERAGE.csv',pd.DataFrame(capacity))
    write_json(OUT/'REGISTRATION.json',dict(status='registered_before_new_endpoint_evaluation',data='real_v2',source_commit='cf053a6e31d17393c0e8216ce15660fa37b8b7bb',
        prior_research_base='8bfd3e476bd5ae6edc1424e2c8ea07dd2f69a235',images=E.image.nunique(),buildings=E.building.nunique(),XYZ_anchors=len(A),events=len(E),
        unique_endpoints=len(R),cached=int(R.cached.sum()),new_native_required=int((~R.cached).sum()),
        selection='在全部39个n20/m7有两个可行目标类背景席位的图中，各取原登记first-two deep background、source_pair=0、target_block=0，不读目标结果；每个XYZ锚点穷举14个D',
        exact_finite_scope='全部78×14个D已登记；具体XYZ仅两个锚点/图，未穷尽全池块组合',
        comparison='固定XYZ/n/m，任意两个D实际只换1人；按换出/换入是否同类区分背景席位变化与同构成成员变化',
        frozen_label_sha256=rs.sha(OLD/'structure/CLASS_LABELS_REUSED.csv.gz'),input_snapshot_sha256=rs.sha(rs.INPUT_FILE),registration_code_sha256=rs.sha(__file__)))
    print(json.dumps(gs.read(OUT/'REGISTRATION.json'),ensure_ascii=False),flush=True)

def configure_native():
    old_native=adapter.NATIVE
    old_reused=adapter.reused_rows
    old_cache_index=adapter.cache_index
    original_cache=old_cache_index()
    # Read exact saved rows into a tiny new cache, without changing old files.
    req=pd.read_csv(OUT/'ENDPOINT_REQUESTS.csv.gz',keep_default_na=False)
    for pid,g in req.groupby('pool_id'):
        p=NATIVE/'reused'/(pid+'.json.gz')
        keys=set(g.loc[g.team_key.isin(original_cache),'team_key'])
        if p.exists():continue
        rr=old_reused(pid,keys)
        write_json(p,dict(pool_id=pid,teams=list(rr.values()),source='exact_prior_frozen_endpoints',native_calls=0))
    adapter.NATIVE=NATIVE
    def lookup():
        out={k:original_cache[k] for k in req.team_key if k in original_cache}
        for f in (NATIVE/'batches').glob('*/ENDPOINT_SCALARS.csv.gz'):
            if (f.parent/'COMPLETION.json').exists():out.update((k,str(f)) for k in pd.read_csv(f,usecols=['team_key']).team_key)
        return out
    def reused(pid,keys):
        p=NATIVE/'reused'/(pid+'.json.gz')
        rows={r['team_key']:r for r in gs.read(p)['teams'] if r['team_key'] in keys}
        assert keys<=rows.keys()
        return rows
    adapter.cache_index=lookup;adapter.reused_rows=reused;adapter.configure()

def run():
    configure_native()
    if not (NATIVE/'background_PLAN.json').exists():adapter.frozen.plan(str(OUT/'ENDPOINT_REQUESTS.csv.gz'),'background',600)
    for b in pd.read_csv(NATIVE/'background_BATCH_PLAN.csv').batch_id:
        adapter.frozen.run(b,3)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['register','run']);a=p.parse_args()
    if a.action=='register':register()
    else:run()
