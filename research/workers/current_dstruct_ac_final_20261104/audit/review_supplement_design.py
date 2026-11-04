"""Independent, outcome-independent review of the frozen 22-cell AC supplement.

Uses current labels, registered members and source identities. It deliberately
does not open endpoint, scoring, geometry-analysis or labor-result files.
"""
from __future__ import annotations
from collections import Counter
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import random

import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
REPO=STUDY.parents[2]
SUP=STUDY/'supplement'
REG=STUDY/'registry'
LABEL=REPO/'research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/LABELS_ALL_LOBO.csv.gz'
POOL=REPO/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json'


def h(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def ws(v):
    return set() if pd.isna(v) or not str(v) else set(str(v).split('|'))


def main():
    spec=json.loads((SUP/'DESIGN.json').read_text(encoding='utf-8'))
    labels=pd.read_csv(LABEL)
    labels=labels[(labels.method=='TARGET_DSTRUCT_K3')&labels.known.eq(True)&(labels.heldout_building!='ALL')]
    lm={(r.heldout_building,r.worker_id):r.class_id for r in labels.itertuples()}
    pools={p['pool_id']:p for p in json.loads(gzip.decompress((SUP/'inputs/SELECTED_POOLS.json.gz').read_bytes()))['images']}
    source_pools={p['pool_id']:p for p in json.loads(POOL.read_text(encoding='utf-8'))['images'] if p['pool_id'] in pools}
    events=pd.read_csv(SUP/'EVENTS.csv.gz');requests=pd.read_csv(SUP/'REQUESTS.csv.gz')
    req={r['team_key']:r for r in requests.to_dict('records')}
    blocks=pd.read_csv(SUP/'BLOCKS.csv.gz')
    old=pd.read_csv(REG/'LEGAL_CURRENT_AC_EVENTS.csv.gz',low_memory=False)
    cap=pd.read_csv(REG/'CURRENT_AC_POOL_N_M_DIRECTION_CAPACITY.csv.gz',low_memory=False)
    cap=cap[(cap.scope=='primary')&cap.n.isin([14,20])&(cap.m==7)&(cap.source_class<cap.target_class)]
    feasible=cap[cap.feasible]
    missing=feasible[feasible.reused_unique_physical_pairs==0]
    expected_cells=set(missing[['pool_id','current_class_pair','n','m']].itertuples(index=False,name=None))
    actual_cells=set(events[['pool_id','pair','n','m']].itertuples(index=False,name=None))
    failures=[];checks=Counter()
    def check(ok,kind,detail=''):
        checks[kind]+=1
        if not ok:failures.append(dict(check=kind,detail=str(detail)))
    check(spec['seed']==202611041301,'frozen_seed')
    check(expected_cells==actual_cells,'exact_final_capacity_gap_cells')
    check(len(events)==704 and events.event_id.nunique()==704,'704_unique_method_events')
    check(events.physical_pair_key.nunique()==704,'704_unique_physical_pairs')
    check(len(requests)==1408 and requests.team_key.nunique()==1408,'1408_unique_team_requests')
    for name,digest in spec['design_sha256'].items():
        check(hashlib.sha256((SUP/name).read_bytes()).hexdigest()==digest,'frozen_design_bytes',name)
    for name,digest in spec['source_files'].items():
        check(hashlib.sha256((REPO/name).read_bytes()).hexdigest()==digest,'frozen_input_bytes',name)
    for pid,pool in pools.items():
        check(pool==source_pools[pid],'selected_pool_identical_to_source_snapshot',pid)
        check(pool['meta']['condition']=='manual' and pool['meta']['layer']=='ordinary_manual','ordinary_manual_source_pool',pid)
    check(old.current_ac_legal.all(),'only_final_legal_historical_events_used')
    physicals=[]
    for r in events.to_dict('records'):
        p=pools[r['pool_id']];meta=p['meta'];allw={o['worker_id'] for o in p['records']}
        D,X,Z,A,C=[ws(r[c]) for c in ['D','X','Z','A_workers','C_workers']]
        lookup={w:lm.get((r['building'],w),'unknown') for w in allw}
        check(D==A&C and X==A-C and Z==C-A,'exact_AC_partition',r['event_id'])
        check(not(D&X or D&Z or X&Z),'disjoint_D_X_Z',r['event_id'])
        check(A|C<=allw,'members_in_same_candidate_pool',r['event_id'])
        check(len(A)==len(C)==int(r['n']) and len(X)==len(Z)==int(r['m']),'same_n_equal_m',r['event_id'])
        check(set(lookup[w] for w in X)=={r['source_class']} and set(lookup[w] for w in Z)=={r['target_class']},'current_LOBO_pure_X_Z',r['event_id'])
        for cl in ['C1','C2','C3','unknown']:
            check(r['D_'+cl]==sum(lookup[w]==cl for w in D),'background_composition_exact',r['event_id']+':'+cl)
        check(json.loads(r['D_class_vector'])==dict(Counter(lookup[w] for w in D)),'background_vector_exact',r['event_id'])
        for col in ['image','image_id','building','reference_id','reference_version','condition','layer']:
            check(str(r[col])==str(meta[col]),'same_image_reference_condition',r['event_id']+':'+col)
        for arm,S in [('A',A),('C',C)]:
            tk=r[arm+'_team_key'];q=req[tk];own=[x for x in p['records'] if x['worker_id'] in S]
            check(tk==r['pool_id']+'__'+h(sorted(S))[:20],'native_team_key',tk)
            check(ws(q['member_workers'])==S and q['n']==len(S),'request_members',tk)
            check(ws(q['member_object_ids'])=={x['object_id'] for x in own},'request_original_objects',tk)
            check(q['reference_id']==r['reference_id'] and q['reference_version']==r['reference_version'],'request_reference_identity',tk)
            check(q['input_pool_sha256']==h(p) and q['input_selected_records_sha256']==h(own),'request_frozen_input_identity',tk)
        physicals.append(h([r['pool_id'],sorted([r['A_team_key'],r['C_team_key']])])[:24])
    check(len(set(physicals))==704,'independent_unordered_pair_dedup')
    check(not (set(physicals)&set(old.canonical_physical_pair_id)),'no_duplicate_legal_stock_pair')
    replay_rows=[]
    for (pid,pair,n,m),g in events.groupby(['pool_id','pair','n','m'],sort=True):
        p=pools[pid];b=p['meta']['building'];allw=sorted(r['worker_id'] for r in p['records'])
        s,t=pair.split('_');S=sorted(w for w in allw if lm.get((b,w),'unknown')==s);T=sorted(w for w in allw if lm.get((b,w),'unknown')==t)
        random_stream=random.Random(int(h([spec['seed'],pid,pair,int(n),int(m)])[:16],16))
        total=math.comb(len(S),int(m))*math.comb(len(T),int(m))
        if total<=16:
            chosen=list(itertools.product(itertools.combinations(S,int(m)),itertools.combinations(T,int(m))))
            random_stream.shuffle(chosen)
        else:
            chosen=[];seen=set()
            while len(chosen)<16:
                choice=(tuple(sorted(random_stream.sample(S,int(m)))),tuple(sorted(random_stream.sample(T,int(m)))))
                if choice not in seen:chosen.append(choice);seen.add(choice)
        expected=[];alloc=[]
        for bi,(X,Z) in enumerate(chosen):
            remainder=sorted(set(allw)-set(X)-set(Z));bcount=len(chosen)
            k=min(32//bcount+(bi<32%bcount),math.comb(len(remainder),int(n-m)))
            if math.comb(len(remainder),int(n-m))<=k:
                ds=list(itertools.combinations(remainder,int(n-m)));random_stream.shuffle(ds)
            else:
                ds=[];seen=set()
                while len(ds)<k:
                    D=tuple(sorted(random_stream.sample(remainder,int(n-m))))
                    if D not in seen:ds.append(D);seen.add(D)
            alloc.append(k)
            for D in ds:expected.append((tuple(D),tuple(X),tuple(Z)))
        observed=[(tuple(sorted(ws(r.D))),tuple(sorted(ws(r.X))),tuple(sorted(ws(r.Z)))) for r in g.itertuples()]
        replay_pass=expected==observed
        check(replay_pass,'deterministic_outcome_blind_replay',str((pid,pair,n,m)))
        check(len(set(expected))==len(expected),'no_repeated_block_background',str((pid,pair,n,m)))
        registered=blocks[(blocks.pool_id==pid)&(blocks.pair==pair)&(blocks.n==n)&(blocks.m==m)]
        check(len(registered)==len(chosen),'registered_XZ_block_count',str((pid,pair,n,m)))
        check(registered.selected_D_count.tolist()==alloc,'registered_D_allocation',str((pid,pair,n,m)))
        check(registered.selected_D_count.nunique()==1,'equal_block_weight_in_actual_cells',str((pid,pair,n,m)))
        replay_rows.append(dict(pool_id=pid,pair=pair,n=n,m=m,total_possible_XZ_blocks=total,selected_XZ_blocks=len(chosen),
                                D_per_selected_block='|'.join(map(str,sorted(set(alloc)))),physical_pairs=len(g),deterministic_replay_match=replay_pass,
                                all_selected_blocks_equal_D_count=len(set(alloc))==1))
    coverage=[]
    for (direction,n,m),g in feasible.groupby(['direction','n','m']):
        pair=g.current_class_pair.iloc[0];stock=g[g.reused_unique_physical_pairs>0]
        supplemental=events[(events.pair==pair)&(events.n==n)&(events.m==m)]
        union=set(stock.pool_id)|set(supplemental.pool_id)
        complete=union==set(g.pool_id)
        check(complete,'complete_core_registration_coverage',str((direction,n,m)))
        coverage.append(dict(scope='primary',direction=direction,n=n,m=m,feasible_images=g.image.nunique(),feasible_buildings=g.building.nunique(),
            historical_supported_images=stock.image.nunique(),supplemental_images=supplemental.image.nunique(),registered_union_images=len(union),
            all_feasible_pools_registered=complete,score_common_support='not_assessed_by_design_audit',reverse_is_same_physical_support=True))
    pd.DataFrame(replay_rows).to_csv(HERE/'SUPPLEMENT_INDEPENDENT_REPLAY_BY_CELL.csv',index=False)
    pd.DataFrame(coverage).to_csv(HERE/'CORE_REGISTRATION_COVERAGE_AFTER_SUPPLEMENT.csv',index=False)
    pd.DataFrame(failures,columns=['check','detail']).to_csv(HERE/'SUPPLEMENT_DESIGN_FAILURES.csv',index=False)
    receipt=dict(status='passed' if not failures else 'failed',reviewer='ac_event_legality independent of supplement author',
        frozen_seed=spec['seed'],frozen_source_commit=spec['source_commit'],method_events=len(events),physical_pairs=len(set(physicals)),unique_teams=len(requests),
        capacity_gap_cells=len(actual_cells),images=events.image.nunique(),buildings=events.building.nunique(),
        checks=dict(checks),failures=len(failures),all_22_cells_deterministic_replay=True if not failures else None,
        selected_XZ_block_count_distribution=pd.DataFrame(replay_rows).selected_XZ_blocks.value_counts().to_dict(),
        no_new_endpoint_or_Q_results_opened=True,no_scoring_or_geometry_result_used_in_selection_review=True,
        source_pool_content_unchanged=True if not failures else None,
        interpretation='Each selected X/Z pair has equal background count within its cell. Background allocation of 2,4,32 for 16,8,1 selected blocks preserves equal block weights and a 32-pair per-cell budget. This does not turn the whole reused study into a current-label uniform sample.',
        support_warning='Full registration coverage is not full scoreability. Status and paired-Q denominators belong to the separate endpoint/statistical audit.')
    (HERE/'SUPPLEMENT_DESIGN_INDEPENDENT_REVIEW.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
