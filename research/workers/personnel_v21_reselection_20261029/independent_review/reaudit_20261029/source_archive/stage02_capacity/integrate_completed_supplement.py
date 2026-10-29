"""Join completed new scalars to exact events and close the capacity funnel.

Old and new stage identities remain explicit. New-only, reused-only and merged
results are not represented as independent experiments.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from audit_large_blocks import image_stats

ROOT=Path(__file__).resolve().parent.parent
REPO=ROOT/'repo'
BASE=REPO/'research/workers/personnel_v21_reselection_20261029'
NEW=ROOT/'HOHONET_v21_reaudit_20261029/stage03_new_abc'
OUT=ROOT/'audit_capacity/completed_supplement'
METHODS=['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3','OPPSTRUCT_K3','OPPJOINT_K3','OPPJOINT_K4']

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    receipt=json.loads((NEW/'endpoints/RUN_RECEIPT.json').read_text())
    assert receipt['all_complete']
    ne=pd.read_csv(NEW/'EVENTS_EXACT.csv.gz',low_memory=False)
    ss=pd.read_csv(NEW/'endpoints/ENDPOINT_SCALARS.csv.gz',low_memory=False).set_index('team_key')
    req=pd.read_csv(NEW/'REQUESTS.csv.gz')
    assert ss.index.is_unique and set(ss.index)==set(req.team_key)
    ne['design']='ABC';ne['evidence_stage']='new_supplement';ne['stages']='new_supplement';ne['stage']='new_supplement'
    ne['source_design']=str(NEW/'EVENTS_EXACT.csv.gz')
    for arm in 'ABC':
        ne[arm+'_Q']=ne[arm+'_team_key'].map(ss.B8L2)
        ne[arm+'_executed']=ne[arm+'_team_key'].isin(ss.index)
        for field in ['score_status','geometry_reason','complete_evaluable','connection_available','nodes','minimum_support','node_supports']:
            ne[arm+'_'+field]=ne[arm+'_team_key'].map(ss[field])
    ne['executed']=ne[['A_executed','B_executed','C_executed']].all(axis=1)
    valid3=ne[['A_Q','B_Q','C_Q']].notna().all(axis=1)
    ne['Q_CA']=ne.C_Q-ne.A_Q;ne['Q_CB']=ne.C_Q-ne.B_Q
    ne['Q_within']=(ne.B_Q-ne.A_Q).abs().where(valid3)
    ne['Q_cross']=((ne.C_Q-ne.A_Q).abs()+(ne.C_Q-ne.B_Q).abs()).div(2).where(valid3)
    ne['Q_gap']=ne.Q_cross-ne.Q_within
    roles=pd.read_csv(BASE/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz')
    newroles=pd.read_csv(ROOT/'audit_classification/results/CLASS_CENTERS_ALL_LOBO.csv.gz')
    for name,col in [('challenge_turn_rank_asc','m_challenge_turn_n'),('q_rank_asc','m_all_B8L2')]:
        newroles[name]=newroles.groupby(['method','heldout_building'])[col].rank(method='dense')
    roles=pd.concat([roles,newroles],ignore_index=True).set_index(['method','heldout_building','class_id'])
    def rd(row):
        axis='challenge_turn_rank_asc' if 'STRUCT' in row.method else 'q_rank_asc'
        s=roles.loc[(row.method,row.building,row.source_class)];t=roles.loc[(row.method,row.building,row.target_class)]
        return f'{axis}:{int(s[axis])}/{int(s.k)}->{int(t[axis])}/{int(t.k)}'
    ne['audit_role_direction']=[rd(r) for r in ne.itertuples()]
    ne.to_csv(OUT/'NEW_EVENTS_INDEPENDENT_Q_AND_STATUS.csv.gz',index=False,encoding='utf-8-sig')
    old=pd.read_csv(ROOT/'audit_capacity/results/ALL_EXECUTED_EVENTS_Q_AND_IDENTITIES.csv.gz',low_memory=False)
    old=old[old.method.isin(METHODS)&old.scope.eq('primary')&old.layer.eq('ordinary_manual')&old.design.eq('ABC')].copy()
    old['evidence_stage']='existing_reused'
    combined=pd.concat([old,ne],ignore_index=True)
    identity=['method','pool_id','n','m','A_team_key','B_team_key','C_team_key']
    duplicates=int(combined.duplicated(identity).sum())
    combined=combined.drop_duplicates(identity).copy()
    combined.to_csv(OUT/'COMPETITIVE_OLD_AND_NEW_EVENTS_Q.csv.gz',index=False,encoding='utf-8-sig')
    overlap=pd.read_csv(NEW/'EXISTING_ENDPOINT_OVERLAPS.csv')
    replay=[]
    metrics=['B8L2','D10','IoU3D100','nodes','geometry_area_h2','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']
    for path,g in overlap.groupby('source'):
        orig=pd.read_csv(ROOT/path,usecols=lambda c:c=='team_key' or c in metrics).set_index('team_key')
        for tk in g.team_key:
            for metric in metrics:
                a,b=orig.at[tk,metric],ss.at[tk,metric]
                okay=(pd.isna(a) and pd.isna(b)) or (pd.notna(a) and pd.notna(b) and np.isclose(a,b,atol=1e-8,rtol=1e-8))
                replay.append(dict(team_key=tk,metric=metric,old=a,new=b,match=okay,source=path))
    replay=pd.DataFrame(replay)
    replay.to_csv(OUT/'EIGHT_REPLAYED_ENDPOINTS_PARITY.csv',index=False,encoding='utf-8-sig')
    assert replay['match'].all()
    cap=pd.read_csv(ROOT/'audit_capacity/extended_capacity/ALL_MANUAL_POOL_METHOD_CAPACITY.csv.gz')
    cap=cap[cap.method.isin(METHODS)&cap.scope.eq('primary')&cap.layer.eq('ordinary_manual')]
    # Include the broad bridge for each method so comparison support is visible.
    grid=[(14,7),(20,7),(12,8),(16,8),(12,4)]
    funnels=[];poolrows=[]
    for method,g in cap.groupby('method'):
        for n,m in grid:
            ev=combined[combined.method.eq(method)&combined.n.eq(n)&combined.m.eq(m)]
            oldev=old[old.method.eq(method)&old.n.eq(n)&old.m.eq(m)]
            newev=ne[ne.method.eq(method)&ne.n.eq(n)&ne.m.eq(m)]
            total=g.pool_n.ge(n+2*m);hist=g.labelled_n.ge(3*m);fits=total&g.class_max_m_ABC.ge(m)
            reg=set(ev.pool_id);executed=set(ev.loc[ev.executed,'pool_id']);cb=set(ev.loc[ev.Q_CB.notna(),'pool_id']);gap=set(ev.loc[ev.Q_gap.notna(),'pool_id'])
            funnels.append(dict(method=method,n=n,m=m,legal_pools=len(g),legal_images=g.image.nunique(),legal_buildings=g.building.nunique(),
                total_n_sufficient_pools=int(total.sum()),historical_3m_sufficient_pools=int((total&hist).sum()),class_feasible_pools=int(fits.sum()),
                class_feasible_images=g.loc[fits,'image'].nunique(),class_feasible_buildings=g.loc[fits,'building'].nunique(),
                total_n_insufficient_pools=int((~total).sum()),historical_insufficient_after_n_pools=int((total&~hist).sum()),
                class_distribution_insufficient_after_history_pools=int((total&hist&~fits).sum()),
                old_registered_pools=oldev.pool_id.nunique(),new_registered_pools=newev.pool_id.nunique(),combined_registered_pools=len(reg),
                combined_executed_pools=len(executed),Q_CB_evaluable_pools=len(cb),Q_gap_evaluable_pools=len(gap),
                feasible_not_registered_pools=int((fits&~g.pool_id.isin(reg)).sum()),
                Q_CB_unscorable_registered_pools=len(reg-cb),Q_gap_unscorable_registered_pools=len(reg-gap),
                old_events=len(oldev),new_events=len(newev),combined_events=len(ev)))
            for r,en,eh,fit in zip(g.to_dict('records'),total,hist,fits):
                pid=r['pool_id'];reason='pool_N_insufficient' if not en else 'history_below_3m' if not eh else 'class_distribution_insufficient' if not fit else 'not_registered' if pid not in reg else 'not_executed' if pid not in executed else 'Q_CB_unscorable' if pid not in cb else 'Q_CB_evaluable'
                poolrows.append(dict(r,n=n,m=m,final_reason=reason,old_registered=pid in set(oldev.pool_id),new_registered=pid in set(newev.pool_id),
                                     Q_CB_evaluable=pid in cb,Q_gap_evaluable=pid in gap))
    pd.DataFrame(funnels).to_csv(OUT/'FINAL_COMPETITIVE_N_M_FUNNEL.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(poolrows).to_csv(OUT/'FINAL_COMPETITIVE_POOL_LEVEL_FUNNEL.csv.gz',index=False,encoding='utf-8-sig')
    directed=pd.read_csv(ROOT/'audit_capacity/extended_capacity/ALL_MANUAL_DIRECTED_CAPACITY.csv.gz')
    cellkeys=['method','pool_id','source_class','target_class','n','m'];coverage_check=[]
    for n,m in [(14,7),(20,7),(12,8),(16,8)]:
        eligible=directed[directed.method.isin(METHODS)&directed.scope.eq('primary')&directed.layer.eq('ordinary_manual')&directed.pool_n.ge(n+2*m)&directed.source_capacity.ge(2*m)&directed.target_capacity.ge(m)].copy()
        eligible['n']=n;eligible['m']=m
        expected=set(map(tuple,eligible[cellkeys].to_numpy()))
        got=set(map(tuple,combined[combined.n.eq(n)&combined.m.eq(m)][cellkeys].to_numpy()))
        coverage_check.append(dict(n=n,m=m,expected_direction_pool_cells=len(expected),executed_direction_pool_cells=len(got),missing=len(expected-got),outside_feasibility=len(got-expected)))
        assert expected==got
    (OUT/'EXHAUSTIVE_DIRECTION_COVERAGE_CHECK.json').write_text(json.dumps(dict(rows=coverage_check,total_missing=sum(r['missing'] for r in coverage_check)),indent=2))
    summaries=[];by_pool=[]
    keys=['method','audit_role_direction','n','m']
    for stage,frame in [('new_supplement_only',ne),('existing_reused_only',old),('combined_coverage',combined)]:
        for k,g in frame.groupby(keys):
            r=dict(zip(keys,k),evidence_stage=stage,events=len(g),pools=g.pool_id.nunique(),images=g.image.nunique(),buildings=g.building.nunique())
            for metric in ['Q_CA','Q_CB','Q_within','Q_cross','Q_gap']:
                r.update({metric+'_'+name:value for name,value in image_stats(g,metric).items()})
            summaries.append(r)
        po=frame.groupby(keys+['pool_id','image','building'])[['Q_CA','Q_CB','Q_within','Q_cross','Q_gap']].mean().reset_index()
        po['evidence_stage']=stage;by_pool.append(po)
    pd.DataFrame(summaries).to_csv(OUT/'INDEPENDENT_Q_DIRECTION_N_M_RESULTS.csv',index=False,encoding='utf-8-sig')
    pd.concat(by_pool,ignore_index=True).to_csv(OUT/'INDEPENDENT_Q_BY_DIRECTED_POOL.csv.gz',index=False,encoding='utf-8-sig')
    pairs=pd.read_csv(ROOT/'audit_capacity/new_registration_audit/INDEPENDENT_FIXED_XYZ_NESTED_N_PAIRS.csv.gz')
    idx=ne.set_index('event_id')
    for end,field in [('small','event_small'),('large','event_large')]:
        for arm in 'ABC':pairs[arm+'_'+end+'_Q']=pairs[field].map(idx[arm+'_Q'])
    pairs['audit_role_direction']=pairs.event_small.map(idx.audit_role_direction)
    ok=pairs[['B_small_Q','B_large_Q','C_small_Q','C_large_Q']].notna().all(axis=1)
    pairs['delta_C']=(pairs.C_large_Q-pairs.C_small_Q).where(ok)
    pairs['delta_B']=(pairs.B_large_Q-pairs.B_small_Q).where(ok)
    pairs['delta_net_CB']=pairs.delta_C-pairs.delta_B
    pairs.to_csv(OUT/'INDEPENDENT_NESTED_N_Q_EFFECTS.csv.gz',index=False,encoding='utf-8-sig')
    nested=[]
    for k,g in pairs.groupby(['method','audit_role_direction','n_small','n_large','m']):
        r=dict(zip(['method','audit_role_direction','n_small','n_large','m'],k),registered_pairs=len(g))
        for metric in ['delta_C','delta_B','delta_net_CB']:
            r.update({metric+'_'+name:value for name,value in image_stats(g,metric).items()})
        nested.append(r)
    pd.DataFrame(nested).to_csv(OUT/'INDEPENDENT_NESTED_N_Q_RESULTS.csv',index=False,encoding='utf-8-sig')
    measured=pd.read_csv(NEW/'metrics/EVENT_METRICS.csv.gz',usecols=lambda c:c=='event_id' or c in ['B8L2_CA','B8L2_CB','B8L2_within','B8L2_cross','B8L2_gap','A_failed','B_failed','C_failed'])
    paired=measured.merge(ne[['event_id','Q_CA','Q_CB','Q_within','Q_cross','Q_gap','A_Q','B_Q','C_Q']],on='event_id',validate='one_to_one')
    parity=dict(events=len(paired),all_ids_match=set(measured.event_id)==set(ne.event_id),metrics={})
    for native,independent in [('B8L2_CA','Q_CA'),('B8L2_CB','Q_CB'),('B8L2_within','Q_within'),('B8L2_cross','Q_cross'),('B8L2_gap','Q_gap')]:
        a,b=paired[native].to_numpy(),paired[independent].to_numpy()
        okay=np.isclose(a,b,rtol=1e-9,atol=1e-9,equal_nan=True)
        parity['metrics'][native]=dict(match=bool(okay.all()),max_abs_error=float(np.nanmax(abs(a-b))),missing_mismatch=int((np.isnan(a)!=np.isnan(b)).sum()))
        assert okay.all()
    for arm in 'ABC':
        okay=paired[arm+'_Q'].isna().eq(paired[arm+'_failed'].astype(bool))
        parity[arm+'_missing_Q_flag_matches']=bool(okay.all());assert okay.all()
    (OUT/'INDEPENDENT_METRIC_PARITY.json').write_text(json.dumps(parity,indent=2))
    check=dict(new_events=len(ne),new_requested_endpoints=len(ss),endpoints_with_Q=int(ss.B8L2.notna().sum()),
               endpoints_without_Q=int(ss.B8L2.isna().sum()),replayed_existing_endpoints=len(overlap),truly_new_physical_endpoints=len(ss)-len(overlap),
               all_8_replay_metrics_agree=bool(replay['match'].all()),new_vs_old_duplicate_event_identities=duplicates,
               new_events_Q_CB_evaluable=int(ne.Q_CB.notna().sum()),new_events_Q_gap_evaluable=int(ne.Q_gap.notna().sum()),
               final_class_feasible_not_registered_four_main_grid_pools=int(pd.DataFrame(funnels).query('m >= 7').feasible_not_registered_pools.sum()),
               aggregation='pool then image then building; new-only and coverage-combined values separate',
               nested_four_endpoint_common_Q=True)
    (OUT/'COMPLETED_SUPPLEMENT_AUDIT.json').write_text(json.dumps(check,ensure_ascii=False,indent=2))
    print(json.dumps(check,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
