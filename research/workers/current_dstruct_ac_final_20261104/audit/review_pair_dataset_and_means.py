"""Independently verify canonical AC pairs, source scores and image weights.

Source scalar tables are used directly; the dataset builder is not imported.
Output means provide a separate baseline for the main statistics review.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
REPO=STUDY.parents[2]
ANA=STUDY/'analysis'
REG=STUDY/'registry'
B12=REPO/'research/workers/mixture_patterns_and_c13_half_20261104/c13_half'


def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def member_tuple(v):
    return tuple(sorted(str(v).split('|'))) if pd.notna(v) and str(v) else ()


def identity(r,arm=''):
    members=r[arm+'_workers'] if arm else r['member_workers']
    return (r['image'],r['condition'],r['reference_id'],r['reference_version'],member_tuple(members))


def numeq(a,b,tol=1e-9):
    if pd.isna(a) or pd.isna(b):return pd.isna(a) and pd.isna(b)
    return bool(np.isfinite(a) and np.isfinite(b) and abs(float(a)-float(b))<=tol)


def aggregate(d,version,support,cohort):
    v=d[d.common_Q].copy()
    if support=='original_common':v=v[v.original_common_Q]
    elif support=='new_common_after_order':v=v[v.new_common_Q]
    rows=[]
    for key,g in v.groupby(['scope','class_pair','n','m'],dropna=False):
        # Respect the supplement's pre-outcome two-stage sampling contract:
        # available D choices within each X/Z block, then equal X/Z blocks.
        # Historical stock remains conditional physical-pair weighting.
        cell=['pool_id','image','building']
        is_gap=g.analysis_cohort.eq('current_capacity_gap_supplement')
        old=g.loc[~is_gap].groupby(cell).agg(mean_dQ=('dQ','mean'),mean_abs_dQ=('abs_dQ','mean')).reset_index()
        new=g.loc[is_gap].groupby(cell+['block_id','background_id']).agg(mean_dQ=('dQ','mean'),mean_abs_dQ=('abs_dQ','mean')).reset_index()
        if len(new):
            new=new.groupby(cell+['block_id'])[['mean_dQ','mean_abs_dQ']].mean().reset_index()
            new=new.groupby(cell)[['mean_dQ','mean_abs_dQ']].mean().reset_index()
        pool=pd.concat([old,new],ignore_index=True)
        if pool.duplicated(cell).any():raise ValueError('Gap and legacy pools overlap within one condition')
        img=pool.groupby(['image','building'])[['mean_dQ','mean_abs_dQ']].mean().reset_index()
        bld=img.groupby('building')[['mean_dQ','mean_abs_dQ']].mean()
        r=dict(version=version,support=support,cohort=cohort,scope=key[0],class_pair=key[1],n=int(key[2]),m=int(key[3]),
            common_physical_pairs=len(g),pools=g.pool_id.nunique(),images=len(img),buildings=len(bld),
            image_equal_dQ=img.mean_dQ.mean(),image_equal_abs_dQ=img.mean_abs_dQ.mean(),
            building_equal_dQ=bld.mean_dQ.mean(),building_equal_abs_dQ=bld.mean_abs_dQ.mean(),
            positive_images=int((img.mean_dQ>1e-10).sum()),negative_images=int((img.mean_dQ< -1e-10).sum()),
            tie_images=int((img.mean_dQ.abs()<=1e-10).sum()),up_over1_images=int((img.mean_dQ>1).sum()),
            down_below_minus1_images=int((img.mean_dQ< -1).sum()),small_abs_atmost1_images=int((img.mean_dQ.abs()<=1).sum()),
            weighting='legacy_physical_pair_equal; gap_D_then_XZ_block_equal; then_pool_image_building')
        rows.append(r)
    return rows


def main():
    checks=Counter();failures=[]
    def check(ok,kind,detail=''):
        checks[kind]+=1
        if not ok and len(failures)<200:failures.append(dict(check=kind,detail=str(detail)))
    auto=pd.read_csv(ANA/'PHYSICAL_PAIRS_AUTOMATIC.csv.gz',low_memory=False)
    aux=pd.read_csv(ANA/'PHYSICAL_PAIRS_ASSISTED.csv.gz',low_memory=False)
    aliases=pd.read_csv(ANA/'PAIR_EVENT_ALIASES.csv.gz',low_memory=False)
    keys=['analysis_cohort','canonical_physical_pair_id']
    check(not auto.duplicated('canonical_physical_pair_id').any(),'one_row_per_unordered_physical_pair_across_cohorts')
    check(set(auto.canonical_physical_pair_id)==set(aux.canonical_physical_pair_id),'automatic_auxiliary_same_registered_pairs')
    ar=auto.set_index('canonical_physical_pair_id');hr=aux.set_index('canonical_physical_pair_id')
    check(len(auto)==33220,'33220_physical_pairs')
    check(len(aliases)==35524,'35524_method_leg_aliases')
    alias_n=aliases.groupby('canonical_physical_pair_id').size()
    check(ar.method_event_aliases.sort_index().equals(alias_n.sort_index()),'all_aliases_accounted_once')
    legacy=pd.read_csv(REG/'LEGAL_CURRENT_AC_EVENTS.csv.gz',low_memory=False)
    reused=pd.read_csv(REG/'REUSED_CURRENT_AC_PHYSICAL_PAIRS.csv.gz',low_memory=False)
    gap=pd.read_csv(STUDY/'supplement/EVENTS.csv.gz')
    expected=set(reused.canonical_physical_pair_id)|{digest([r.pool_id,sorted([r.A_team_key,r.C_team_key])])[:24] for r in gap.itertuples()}
    check(expected==set(ar.index),'exact_registry_and_supplement_pair_union')
    remapped=set(legacy.loc[legacy.current_direction_changed,'event_id'])
    observed_remap=auto[auto.current_direction_changed]
    check(set(observed_remap.original_event_id)==remapped and len(remapped)==43,'all_43_reclassified_directions_retained')
    # Recover Q once per physical team directly from source scalar tables.
    original=pd.read_csv(ANA/'LEGACY_TARGET_METRICS_AUTOMATIC.csv.gz',usecols=['event_id','A_team_key','C_team_key','A_B8L2','C_B8L2'],low_memory=False)
    endpoints={}
    for r in original.itertuples():
        for arm in ['A','C']:
            tk=getattr(r,arm+'_team_key');q=getattr(r,arm+'_B8L2')
            if tk in endpoints:check(numeq(endpoints[tk],q),'legacy_repeated_team_Q_consistency',tk)
            endpoints[tk]=q
    for path in [B12/'endpoints/ENDPOINT_SCALARS.csv.gz',STUDY/'supplement/endpoints/ENDPOINT_SCALARS.csv.gz']:
        source=pd.read_csv(path,usecols=['team_key','B8L2'],low_memory=False)
        for r in source.itertuples():
            if r.team_key in endpoints:check(numeq(endpoints[r.team_key],r.B8L2),'cross_source_exact_team_Q_consistency',r.team_key)
            endpoints[r.team_key]=r.B8L2
    approved=pd.read_csv(REPO/'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINT_SCORES.csv')
    approved_map={identity(r):r['B8L2'] for r in approved.to_dict('records')}
    max_auto_error=0.;max_aux_error=0.;approved_hit_pairs=set()
    for r in auto.to_dict('records'):
        hrow=hr.loc[r['canonical_physical_pair_id']]
        for arm,S in [('A',r['source_class_current']),('C',r['target_class_current'])]:
            key=r[arm+'_team_key'];q=endpoints[key]
            check(numeq(q,r['Q_'+arm]),'canonical_automatic_Q_matches_original_endpoint',r['canonical_physical_pair_id']+':'+arm)
            if pd.notna(q) and pd.notna(r['Q_'+arm]):max_auto_error=max(max_auto_error,abs(q-r['Q_'+arm]))
            ident=identity(r,arm)
            if ident in approved_map:
                expected_q=approved_map[ident];approved_hit_pairs.add(r['canonical_physical_pair_id'])
            else:expected_q=q
            check(numeq(expected_q,hrow['Q_'+arm]),'auxiliary_Q_matches_only_approved_order_overlay',r['canonical_physical_pair_id']+':'+arm)
            if pd.notna(expected_q) and pd.notna(hrow['Q_'+arm]):max_aux_error=max(max_aux_error,abs(expected_q-hrow['Q_'+arm]))
        check(numeq(r['dQ'],r['Q_C']-r['Q_A']),'signed_Q_is_C_minus_A',r['canonical_physical_pair_id'])
        check(numeq(r['abs_dQ'],abs(r['Q_C']-r['Q_A'])),'absolute_Q_from_same_pair',r['canonical_physical_pair_id'])
        check(bool(r['common_Q'])==(pd.notna(r['Q_A']) and pd.notna(r['Q_C'])),'no_zero_imputation_in_common_Q',r['canonical_physical_pair_id'])
    original_common=ar.common_Q
    new_common=(~ar.common_Q)&hr.common_Q
    check(int(original_common.sum())==32086,'automatic_common_pair_count')
    check(int(hr.common_Q.sum())==32127 and int(new_common.sum())==41,'auxiliary_common_support_41_new_pairs')
    for side in ['Q_A','Q_C','dQ']:
        check(np.allclose(ar.loc[original_common,side],hr.loc[original_common,side],rtol=0,atol=1e-10),'original_common_values_unchanged',side)
    check(set(hr.loc[hr.new_common_Q].index)==set(new_common[new_common].index),'new_common_flag_exact')
    # Verify canonical members, independently of retained source orientation.
    lm=pd.read_csv(REG/'CURRENT_DSTRUCT_LOBO_LABELS.csv.gz')
    labels={(r.heldout_building,r.worker_id):r.class_id if r.known else 'unknown' for r in lm.itertuples()}
    for r in auto.itertuples():
        X=member_tuple(r.X_workers);Z=member_tuple(r.Z_workers)
        check({labels.get((r.building,w),'unknown') for w in X}=={r.source_class_current},'canonical_X_current_class',r.canonical_physical_pair_id)
        check({labels.get((r.building,w),'unknown') for w in Z}=={r.target_class_current},'canonical_Z_current_class',r.canonical_physical_pair_id)
    rows=[]
    for version,d in [('automatic',auto),('manual_order_assisted',aux)]:
        supports=['original_common'] if version=='automatic' else ['original_common','new_common_after_order','expanded_common']
        cohorts=[(name,g.copy()) for name,g in d.groupby('analysis_cohort')]
        cohorts.append(('legacy_plus_registered_gap',d[d.analysis_cohort.isin(['legacy_current_label_conditional','current_capacity_gap_supplement'])
                                                        &d.scope.eq('primary')&d.n.isin([14,20])&d.m.eq(7)].copy()))
        for name,g in cohorts:
            for support in supports:rows.extend(aggregate(g,version,support,name))
    means=pd.DataFrame(rows)
    means.to_csv(HERE/'INDEPENDENT_IMAGE_BUILDING_Q_MEANS.csv',index=False)
    means[(means.scope=='primary')&means.n.isin([14,20])&(means.m==7)].to_csv(HERE/'INDEPENDENT_CORE_Q_MEANS.csv',index=False)
    pd.DataFrame(failures,columns=['check','detail']).to_csv(HERE/'PAIR_DATASET_INDEPENDENT_FAILURES.csv',index=False)
    receipt=dict(status='passed' if not failures else 'failed',checks=dict(checks),failures=len(failures),
        compared_physical_pairs=len(auto),method_leg_aliases=len(aliases),automatic_common_pairs=int(ar.common_Q.sum()),
        assisted_common_pairs=int(hr.common_Q.sum()),additional_common_pairs=int(new_common.sum()),approved_overlay_touched_physical_pairs=len(approved_hit_pairs),
        maximum_automatic_source_Q_error=max_auto_error,maximum_auxiliary_source_Q_error=max_aux_error,
        means_rows=len(means),cluster_bootstrap_not_repeated=True,formal_summary_comparison='pending_main_summary_publication')
    (HERE/'PAIR_DATASET_INDEPENDENT_REVIEW.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
