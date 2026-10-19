"""Freeze leave-building-out selection and finite personnel-composition requests."""
from __future__ import annotations
from collections import defaultdict,Counter
from itertools import combinations
import math
import numpy as np
import pandas as pd
from pool_io import OUT,ROOT,load_pools,save,save_gz,csv,read,sha,digest,canonical,clean
from register_design import sample_subsets

SEED=2026101903
KS=(8,12,16,24)
QUALITY_TOLERANCE=3.
AXES=('B8L2','D10')
DIFF={'简单':'easy','中等':'medium','困难':'hard'}
def rng_for(*args):return np.random.default_rng(int(digest([SEED,*args])[:16],16))
def istrue(value):return value is True or str(value)=='True'
def finite(value):return isinstance(value,(int,float,np.number)) and np.isfinite(value)

def allocation(groups,k,order,balanced=False):
    counts={c:0 for c in groups};remaining=k
    while remaining:
        before=remaining
        for c in order:
            take=min(1 if balanced else remaining,len(groups[c])-counts[c],remaining)
            counts[c]+=take;remaining-=take
            if not remaining:break
        assert before!=remaining,'allocation_capacity_failure'
    return {c:n for c,n in sorted(counts.items()) if n}

def main():
    path=ROOT/'work_v2_20261019/profiles/fold_profiles.csv';frame=pd.read_csv(path);records=clean(frame.to_dict('records'))
    assert len(records)==1320 and 'fine_dtype_B8L2' in frame
    frozen_profile_sha=sha(path);save_gz(OUT/'FOLD_PROFILE_SELECTION_SNAPSHOT.json.gz',dict(source_sha256=frozen_profile_sha,records=records))
    lookup={(r['heldout_building'],r['worker_id']):r for r in records};pools=[p for p in load_pools() if p['meta']['layer']=='ordinary_manual']
    requests=[];ledger=[];composition_ledger=[]
    def append(p,workers,**meta):
        rid='FWD_'+digest([p['pool_id'],meta,workers])[:24]
        requests.append(dict(request_id=rid,pool_id=p['pool_id'],worker_ids=workers,k=len(workers),**meta));return rid
    for p in pools:
        pid=p['pool_id'];b=p['meta']['building'];d=DIFF.get(p['meta']['difficulty']);workers=[r['worker_id'] for r in p['records']]
        prof={w:lookup[b,w] for w in workers};source={r['worker_id']:r for r in p['records']}
        eligible=[w for w in workers if istrue(prof[w]['Q_supported'])]
        assert p['meta']['difficulty_aligned'] and d is not None
        for origin in ('all','v1','new'):
            all_allowed=[w for w in eligible if origin=='all' or source[w]['origin']==origin]
            poolname='Q_history_supported_all_origins' if origin=='all' else 'Q_history_supported_origin_'+origin
            for axis in AXES if origin=='all' else ('B8L2',):
                q=lambda w:prof[w]['Q_effect_'+axis]
                theta=lambda w:prof[w]['theta_'+d+'_'+axis]
                ts=lambda w:prof[w]['T_source_effect']
                for k in KS:
                    if len(all_allowed)<k:
                        ledger.append(dict(pool_id=pid,k=k,selection_metric=axis,candidate_pool=poolname,status='candidate_pool_below_k',available=len(all_allowed)));continue
                    meta=dict(request_family='profile_policy',selection_metric=axis,candidate_pool=poolname,profile_training_excludes_building=b,selection_origin=origin)
                    def add(strategy,ws,**extra):
                        missing=sum(not istrue(prof[w]['difficulty_supported_'+d]) for w in ws)
                        return append(p,ws,strategy=strategy,selected_target_difficulty_unsupported_n=missing,
                            selected_source_T_unsupported_n=sum(not istrue(prof[w]['T_source_supported']) for w in ws),**meta,**extra)
                    ranked_q=sorted(all_allowed,key=lambda w:(-q(w),w));ranked_d=sorted(all_allowed,key=lambda w:(-theta(w),w))
                    add('Qfirst',ranked_q[:k]);add('QD_allhistory',ranked_d[:k])
                    if origin=='all':
                        diff_allowed=[w for w in all_allowed if istrue(prof[w]['difficulty_supported_'+d])]
                        if len(diff_allowed)>=k:
                            add('Qfirst_difficulty_supported',sorted(diff_allowed,key=lambda w:(-q(w),w))[:k],admissible_worker_ids=diff_allowed)
                            add('QD_supported',sorted(diff_allowed,key=lambda w:(-theta(w),w))[:k],admissible_worker_ids=diff_allowed)
                        else:ledger.append(dict(pool_id=pid,k=k,selection_metric=axis,candidate_pool=poolname,strategy='QD_supported',status='difficulty_supported_pool_below_k',available=len(diff_allowed)))
                    for base_name,ranked,score in [('QT',ranked_q,q),('QTD_allhistory',ranked_d,theta)]:
                        quality_cut=score(ranked[k-1])-QUALITY_TOLERANCE
                        candidates=[w for w in all_allowed if score(w)>=quality_cut and istrue(prof[w]['T_source_supported']) and finite(ts(w))]
                        if len(candidates)>=k:
                            ordered=sorted(candidates,key=lambda w:(ts(w),-score(w),w));add(base_name,ordered[:k],quality_cut=quality_cut,admissible_worker_ids=candidates)
                            add(base_name+'_quality_only_matched',sorted(candidates,key=lambda w:(-score(w),w))[:k],quality_cut=quality_cut,admissible_worker_ids=candidates)
                            if origin=='all':
                                origin_candidates=[w for w in candidates if istrue(prof[w]['T_source_origin_supported']) and finite(prof[w]['T_source_origin_effect'])]
                                if len(origin_candidates)>=k:
                                    add(base_name+'_origin_time_centered',sorted(origin_candidates,key=lambda w:(prof[w]['T_source_origin_effect'],-score(w),w))[:k],quality_cut=quality_cut,admissible_worker_ids=origin_candidates)
                        else:ledger.append(dict(pool_id=pid,k=k,selection_metric=axis,candidate_pool=poolname,strategy=base_name,status='known_T_within_quality_band_below_k',available=len(candidates),quality_cut=quality_cut))
                    # Same eligible candidate pool random baseline. Identical draw sets reused between B8 and D10 by design.
                    random=sample_subsets(sorted(all_allowed),k,4,rng_for('eligible_random',pid,origin,k))
                    for draw,ws in enumerate(random):add('eligible_random',list(ws),draw_id=draw)
                    ledger.append(dict(pool_id=pid,k=k,selection_metric=axis,candidate_pool=poolname,status='selection_defined',available=len(all_allowed)))
        # Same known people under all three schemes; unknown specialization is never a low category.
        common=[w for w in eligible if istrue(prof[w]['T_source_supported']) and prof[w]['QT_B8L2']!='unknown'
            and prof[w]['difficulty_type_B8L2']!='unknown' and 'unknown' not in prof[w]['fine_dtype_B8L2']]
        scheme_fields={'Q2':'Q2_B8L2','QT':'QT_B8L2','QTD_dtype':'fine_dtype_B8L2'}
        for k in KS:
            if len(common)<k:
                composition_ledger.append(dict(pool_id=pid,k=k,status='common_known_Q_T_dtype_pool_below_k',available=len(common)));continue
            for scheme,field in scheme_fields.items():
                groups=defaultdict(list)
                for w in common:groups[prof[w][field]].append(w)
                score_field='theta_'+d+'_B8L2' if scheme=='QTD_dtype' else 'Q_effect_B8L2'
                class_mean={c:float(np.median([prof[w][score_field] for w in ws])) for c,ws in groups.items()}
                high=sorted(groups,key=lambda c:(-class_mean[c],c));low=sorted(groups,key=lambda c:(class_mean[c],c));balanced=sorted(groups)
                definitions=[('class_balanced',allocation(groups,k,balanced,True)),('profile_priority',allocation(groups,k,high)),('reverse_profile_priority',allocation(groups,k,low))]
                for policy,vector in definitions:
                    vector_string=canonical(vector);seen=set()
                    for draw in range(4):
                        rng=rng_for('fixed_personnel_composition',pid,k,scheme,policy,draw)
                        ws=[]
                        for c,n in vector.items():ws.extend(rng.choice(sorted(groups[c]),n,replace=False).tolist())
                        ws=sorted(ws);seen.add(tuple(ws))
                        append(p,ws,request_family='profile_composition',strategy=policy,scheme=scheme,selection_metric='B8L2',
                            candidate_pool='common_known_Q_T_dtype',candidate_pool_n=len(common),composition=vector_string,draw_id=draw,
                            profile_training_excludes_building=b)
                    composition_ledger.append(dict(pool_id=pid,k=k,scheme=scheme,strategy=policy,status='computed_requests',
                        available=len(common),classes_in_pool=len(groups),composition=vector_string,requested_variants=4,unique_variants=len(seen)))
    assert len({r['request_id'] for r in requests})==len(requests)
    registration=dict(schema='v2_forward_composition_registration_v1',seed=SEED,k=list(KS),fold_profiles_sha256=frozen_profile_sha,
        dtype_extension_sha256=sha(ROOT/'work_v2_20261019/profiles/REGISTRATION_DTYPE_EXTENSION.json'),
        outcome_use='No corresponding forward fusion outcomes inspected to define selection/categories/sampling; pilot was runtime/input verification only.',
        amendment='QD_allhistory uses finite partial-pooling theta on the same Q-supported workers as Qfirst. QD_supported and same-pool Qfirst_difficulty_supported retain the local evidence gate. This isolates candidate-pool changes without treating weak local support as proven specialization.',
        Q_rule='Q_supported >=6 tasks and >=3 training buildings, all training excludes target building.',
        QT_rule='score >= kth highest score minus 3 B8 or D10 points, then supported finite source-time effect ascending; ties quality then worker ID. Fewer than k time-known candidates -> unavailable, no imputation.',
        matched_baselines='QT_quality_only_matched/QTD_allhistory_quality_only_matched choose quality from exactly the same known-T band; eligible_random uses identical Q-history-supported candidate pool.',
        T_sources='pooled source-relative T primary, origin-centered T sensitivity; source-old/new team restrictions separately labeled; target time never replaced by source time.',
        difficulty='Frozen observed target difficulty; QD partial pooling can shrink weak local estimates, while specialization labels and known dtype composition retain separate support gates.',
        composition='Q2,QT,QTD_dtype all on the same known-Q/T/dtype people per image; 3 finite count vectors (balanced, training-profile-priority, reverse priority), 4 uniform real member draws per vector. Class ordering by median LOBO beta, or target-difficulty theta for dtype; no target response Q or fusion quality.',
        metric_sensitivity='B8 vs D10 selection reruns separately; all selected real teams then scored under BOTH metrics. Fixed-team measurement and reselection distinguished.',
        counts=dict(requests=len(requests),unique_teams=len({(r['pool_id'],tuple(sorted(r['worker_ids']))) for r in requests}),families=dict(Counter(r['request_family'] for r in requests))))
    save(OUT/'FORWARD_REGISTRATION.json',registration);save_gz(OUT/'REQUESTS_FORWARD.json.gz',dict(schema='v2_fusion_requests_v1',registration_sha256=sha(OUT/'FORWARD_REGISTRATION.json'),requests=requests))
    csv(OUT/'FORWARD_SELECTION_COVERAGE.csv',ledger);csv(OUT/'COMPOSITION_SELECTION_COVERAGE.csv',composition_ledger)
    print(registration['counts'],flush=True)

if __name__=='__main__':main()
