"""Personnel profiles, separately by annotation condition; no new scoring or votes.

Run: python build_profiles.py --repo /path/to/repo --out /path/to/results
The source inputs remain authoritative. Derived summaries never grant eligibility.
"""
from pathlib import Path
import argparse, gzip, json
from itertools import combinations
import numpy as np
import pandas as pd


def load_records(repo):
    path=repo/'research/statistics/v2_integrated_analysis_20261019/tables.json.gz'
    with gzip.open(path,'rt',encoding='utf-8') as f:
        payload=json.load(f)
    d=pd.DataFrame(payload['tables']['quality__shared_records'])
    del payload
    d=d[~d.is_oos].copy()
    d['panel']=np.where(d.is_doorway,'doorway','ordinary')
    d['Q_panel']=d.quality_use.map({'ordinary_primary':'ordinary','doorway_quality':'doorway','special_conditional_only':'special'})
    d['task_key']=d[['image_id','condition','chosen_target_id','reference_version']].fillna('<missing>').astype(str).agg('|'.join,axis=1)
    d['time_task_key']=d[['task_key','origin','time_source_kind']].fillna('<missing>').astype(str).agg('|'.join,axis=1)
    q=d.quality_usable & d.chosen_target_id.notna()
    for metric in ('B8L2','D10'):
        g=d.loc[q].groupby('task_key')[metric]
        n=g.transform('count'); total=g.transform('sum')
        d.loc[q,metric+'_peer_recomputed']=d.loc[q,metric]-(total-d.loc[q,metric])/(n-1).replace(0,np.nan)
        d.loc[q,metric+'_rank_recomputed']=100*(g.rank(method='average')-1)/(n-1).replace(0,np.nan)
    t=d.pool_analysis_eligible & d.source_active_time_seconds.gt(0)&d.chosen_target_id.notna()
    d.loc[t,'log_source_time']=np.log(d.loc[t,'source_active_time_seconds'])
    g=d.loc[t].groupby('time_task_key').log_source_time
    n=g.transform('size'); total=g.transform('sum')
    d.loc[t,'log_time_peer_recomputed']=d.loc[t,'log_source_time']-(total-d.loc[t,'log_source_time'])/(n-1).replace(0,np.nan)
    return d


def history_features(d,out):
    """Tasks are nested in buildings; leave-building residual summaries cannot use a target score."""
    rows=[]
    all_buildings=sorted(d.building_id.unique())
    for target in all_buildings:
        history=d[d.building_id.ne(target)]
        for (worker,condition,origin,panel),g in history.groupby(['worker_id','condition','origin','panel']):
            q=g[g.quality_usable & g.Q_panel.eq(panel)]
            t=g[g.log_time_peer_recomputed.notna()]
            source_t=g[g.pool_analysis_eligible & g.source_active_time_seconds.gt(0)]
            z=dict(target_building=target,worker_id=worker,condition=condition,origin=origin,panel=panel,
                n_inventory=len(g),n_history_images=g.image_id.nunique(),n_history_buildings=g.building_id.nunique(),
                n_quality=len(q),n_quality_images=q.image_id.nunique(),n_quality_buildings=q.building_id.nunique(),
                Q_mean=q.B8L2.mean(),Q_q10=q.B8L2.quantile(.1),Q_sd=q.B8L2.std(),
                Q_peer=q.B8L2_peer_recomputed.mean(),Q_rank=q.B8L2_rank_recomputed.mean(),
                D10_mean=q.D10.mean(),D10_peer=q.D10_peer_recomputed.mean(),
                n_time=len(t),n_time_images=t.image_id.nunique(),n_time_buildings=t.building_id.nunique(),
                log_time_peer=t.log_time_peer_recomputed.mean(),relative_time=np.exp(t.log_time_peer_recomputed.mean()),
                source_time_median=source_t.source_active_time_seconds.median(),source_time_mean=source_t.source_active_time_seconds.mean(),
                n_source_time=len(source_t),n_target_time=int(g.target_matched_time_seconds.notna().sum()),
                time_source_kind='|'.join(sorted(g.time_source_kind.dropna().unique())),
                n_source_independent=int(g.source_pool_eligible.sum()),n_pool_eligible=int(g.pool_analysis_eligible.sum()),
                n_cleaning_excluded=int(g.cleaning_disposition.isin(['excluded_by_review','historical_not_accepted']).sum()),
                selection_history='all_available_other_buildings_not_chronological_prospective')
            z['Q_supported_8images_3buildings']=z['n_quality_images']>=8 and z['n_quality_buildings']>=3
            z['T_supported_8images_3buildings']=z['n_time_images']>=8 and z['n_time_buildings']>=3
            rows.append(z)
    f=pd.DataFrame(rows)
    f.to_csv(out/'lobo_features.csv',index=False)
    return f


def first_diagnostics(d,out):
    fields=['object_id','worker_id','condition','origin','image_id','image_code','building_id','panel','Q_panel','quality_use','quality_usable',
      'task_key','time_task_key','chosen_target_id','reference_id','reference_version',
      'cleaning_disposition','source_pool_eligible','pool_analysis_eligible','independent_vote_eligible','image_quality_gate',
      'quality_exclusion_reasons','scope_response','scope_opportunity','scope_correct','difficulty_class','difficulty_reference_match',
      'scene','doorway_status','B8L2','D10','B8L2_peer_recomputed','B8L2_rank_recomputed','source_active_time_seconds',
      'target_matched_time_seconds','time_source_kind','log_time_peer_recomputed']
    print('non-OOS inventory',len(d),'images',d.image_id.nunique(),'workers',d.worker_id.nunique(),flush=True)
    print(d.groupby(['condition','origin','panel']).agg(n=('worker_id','size'),workers=('worker_id','nunique'),quality=('quality_usable','sum'),source_eligible=('source_pool_eligible','sum'),pool_eligible=('pool_analysis_eligible','sum')).to_string(),flush=True)
    print('peer recompute maxdiff',np.nanmax(abs(d.B8L2_peer_recomputed-d.B8L2_peer_residual)),flush=True)
    print('time recompute maxdiff',np.nanmax(abs(d.log_time_peer_recomputed-d.source_log_time_peer_residual)),flush=True)
    print('cleaning x eligibility',pd.crosstab(d.cleaning_disposition,[d.source_pool_eligible,d.pool_analysis_eligible]).to_string(),flush=True)
    d[fields].to_csv(out/'record_index.csv.gz',index=False,compression='gzip')


def worker_effect(g,value,task='task_key'):
    """OLS worker effects after exactly eliminating task fixed effects.

    Moore-Penrose solution centers effects within each connected component.
    Every observation retains its original weight; no reference score is changed.
    """
    g=g[g[value].notna()].copy()
    if not len(g):return pd.Series(dtype=float)
    counts=pd.crosstab(g[task],g.worker_id)
    n=counts.sum(axis=1).to_numpy(float)
    C=counts.to_numpy(float)
    A=np.diag(C.sum(axis=0))-C.T@(C/n[:,None])
    centered=g[value]-g.groupby(task)[value].transform('mean')
    b=centered.groupby(g.worker_id).sum().reindex(counts.columns).to_numpy(float)
    effect=np.linalg.lstsq(A,b,rcond=1e-10)[0]
    return pd.Series(effect,index=counts.columns)


def residualize(g,value,task='task_key'):
    beta=worker_effect(g,value,task)
    after=g[value]-g.worker_id.map(beta)
    return after-after.groupby(g[task]).transform('mean')


def add_geometry_and_evidence(d,repo):
    geom=pd.read_csv(repo/'research/difficulty/difficulty_mechanisms_v2_20261020/record_conditions.csv.gz',low_memory=False)
    extra=['personal_comparison','personal_sample','reference_sample','pair_n_peer_delta','short_turn_edges_peer_delta',
        'near_straight_nodes_5deg_peer_delta','log_area_peer_delta','log_height_peer_delta','short_turn_edges','near_straight_nodes_5deg',
        'corner_delta','unmatched_ref_9','unmatched_ref_12','bottom_bias_9','omission','extension','log_area_ratio',
        'ref_vertices','ref_turn5','ref_H','ref_short_edges','reduced','mechanism','annotation_turn5']
    d=d.merge(geom[['object_id']+extra],on='object_id',how='left',validate='one_to_one')
    ev=d.exclusion_attribution
    d['excluded_by_review']=d.cleaning_disposition.eq('excluded_by_review')
    d['historical_not_accepted']=d.cleaning_disposition.eq('historical_not_accepted')
    d['cleaning_excluded']=d.excluded_by_review|d.historical_not_accepted
    d['legacy_person_error']=ev.map(lambda v:v['legacy_explicit_person_error'])
    d['person_error_candidate']=ev.map(lambda v:v['specific_person_error_candidate'])
    d['exclusion_category']=ev.map(lambda v:v['category'])
    d['exclusion_reason']=ev.map(lambda v:v['user_exclusion_reason'])
    d['scope_judged']=d.scope_opportunity.eq(True)
    d['semi_edited']=d.semi_evidence.map(lambda v:v.get('edited'))
    d['semi_edited_outcome_unknown']=d.semi_evidence.map(lambda v:v.get('edited_but_correction_unknown'))
    return d


def profiles(d,out):
    rows=[];diffrows=[];mechrows=[]
    for (worker,condition,origin,panel),g in d.groupby(['worker_id','condition','origin','panel']):
        q=g[g.quality_usable&g.Q_panel.eq(panel)]
        t=g[g.log_time_peer_recomputed.notna()]
        time=g[g.pool_analysis_eligible&g.source_active_time_seconds.gt(0)]
        geom=g[g.personal_comparison.eq(True)]
        excluded=g[g.cleaning_excluded]
        row=dict(worker_id=worker,condition=condition,origin=origin,panel=panel,
          n_inventory=len(g),n_images=g.image_id.nunique(),n_buildings=g.building_id.nunique(),
          n_quality=len(q),n_quality_all_uses=int(g.quality_usable.sum()),n_special_quality=int((g.quality_usable&g.Q_panel.eq('special')).sum()),
          n_quality_images=q.image_id.nunique(),n_quality_buildings=q.building_id.nunique(),
          n_source_independent=int(g.source_pool_eligible.sum()),n_pool_eligible=int(g.pool_analysis_eligible.sum()),
          n_pool_only_restricted=int((g.source_pool_eligible&~g.pool_analysis_eligible).sum()),
          n_cleaning_excluded=len(excluded),n_excluded_images=excluded.image_id.nunique(),n_excluded_buildings=excluded.building_id.nunique(),
          cleaning_excluded_rate=len(excluded)/len(g),excluded_image_rate=excluded.image_id.nunique()/g.image_id.nunique(),
          n_excluded_by_review=int(g.excluded_by_review.sum()),n_historical_not_accepted=int(g.historical_not_accepted.sum()),
          n_pending=int(g.cleaning_disposition.eq('retained_pending').sum()),n_legacy_person_error=int(g.legacy_person_error.sum()),
          n_person_error_candidate=int(g.person_error_candidate.sum()),
          n_quality_missing_in_pool=int((g.pool_analysis_eligible&~g.quality_usable).sum()),
          Q_mean=q.B8L2.mean(),Q_median=q.B8L2.median(),Q_q10=q.B8L2.quantile(.1),Q_sd=q.B8L2.std(),
          Q_peer=q.B8L2_peer_recomputed.mean(),Q_peer_q10=q.B8L2_peer_recomputed.quantile(.1),
          Q_rank=q.B8L2_rank_recomputed.mean(),Q_low_rank20_n=int(q.B8L2_rank_recomputed.le(20).sum()),
          Q_low_rank20_rate=q.B8L2_rank_recomputed.le(20).mean() if len(q) else np.nan,
          D10_mean=q.D10.mean(),D10_q10=q.D10.quantile(.1),D10_peer=q.D10_peer_recomputed.mean(),
          source_time_n=len(time),source_time_median=time.source_active_time_seconds.median(),source_time_q90=time.source_active_time_seconds.quantile(.9),
          source_time_mean=time.source_active_time_seconds.mean(),n_time=len(t),n_time_buildings=t.building_id.nunique(),
          log_time_peer=t.log_time_peer_recomputed.mean(),relative_time=np.exp(t.log_time_peer_recomputed.mean()),
          target_time_n=int(g.target_matched_time_seconds.notna().sum()),target_time_median=g.target_matched_time_seconds.median(),
          time_source_kind='|'.join(sorted(g.time_source_kind.dropna().unique())),
          n_geometry=len(geom),pair_peer=geom.pair_n_peer_delta.mean(),short_turn_peer=geom.short_turn_edges_peer_delta.mean(),
          straight_peer=geom.near_straight_nodes_5deg_peer_delta.mean(),log_area_peer=geom.log_area_peer_delta.mean(),log_height_peer=geom.log_height_peer_delta.mean(),
          n_scope_response=int(g.scope_response.notna().sum()),n_scope_out=int(g.scope_response.eq('out_of_scope').sum()),
          n_scope_judged=int(g.scope_judged.sum()),n_scope_correct=int(g.scope_correct.eq(True).sum()),
          confirmed_error_opportunities=int(g.semi_confirmed_error_opportunity.sum()),
          confirmed_error_unchanged=int((g.semi_confirmed_error_opportunity&g.semi_known_error_unchanged.eq(True)).sum()),
          reported_error_opportunities=int(g.semi_reported_error_opportunity.sum()),
          reported_error_unchanged=int((g.semi_reported_error_opportunity&g.semi_reported_known_error_unchanged.eq(True)).sum()),
          semi_edited_n=int(g.semi_edited.eq(True).sum()),semi_edit_observed_n=int(g.semi_edited.notna().sum()),
          semi_edited_error_outcome_unknown_n=int(g.semi_edited_outcome_unknown.eq(True).sum()),
          semi_exact_initializations=int(g.semi_exact_initialization.sum()),
          semi_current_gain_n=int(g.semi_worker_gain_B8L2.notna().sum()),semi_current_worker_gain_mean=g.semi_worker_gain_B8L2.mean(),
          unknown_difficulty_n=int(g.difficulty_class.isin(['待复核','待修正GT']).sum()),
          unresolved_scene_n=int(g.scene.str.contains('pending|suspected|not_recorded',regex=True).sum()))
        for level,label in [('简单','easy'),('中等','medium'),('困难','hard')]:
            v=q[q.difficulty_reference_match & q.difficulty_class.eq(level)]
            vt=t[t.difficulty_reference_match&t.difficulty_class.eq(level)]
            vg=geom[geom.difficulty_reference_match&geom.difficulty_class.eq(level)]
            row.update({label+'_n':len(v),label+'_buildings':v.building_id.nunique(),
              label+'_Q_mean':v.B8L2.mean(),label+'_Q_peer':v.B8L2_peer_recomputed.mean(),
              label+'_Q_q10':v.B8L2.quantile(.1),label+'_time_n':len(vt),label+'_time_median':vt.source_active_time_seconds.median(),
              label+'_log_time_peer':vt.log_time_peer_recomputed.mean(),label+'_geometry_n':len(vg),
              label+'_short_turn_peer':vg.short_turn_edges_peer_delta.mean(),label+'_pair_peer':vg.pair_n_peer_delta.mean()})
            diffrows.append(dict(worker_id=worker,condition=condition,origin=origin,panel=panel,difficulty=level,
              n=len(v),images=v.image_id.nunique(),buildings=v.building_id.nunique(),Q_mean=v.B8L2.mean(),Q_peer=v.B8L2_peer_recomputed.mean(),
              n_time=len(vt),time_median=vt.source_active_time_seconds.median(),log_time_peer=vt.log_time_peer_recomputed.mean(),
              n_geometry=len(vg),short_turn_peer=vg.short_turn_edges_peer_delta.mean(),pair_peer=vg.pair_n_peer_delta.mean()))
        row['hard_minus_easy_Q']=row['hard_Q_mean']-row['easy_Q_mean']
        row['hard_minus_easy_peer']=row['hard_Q_peer']-row['easy_Q_peer']
        row['Q_supported']=row['n_quality_images']>=8 and row['n_quality_buildings']>=3
        row['T_supported']=row['n_time']>=8 and row['n_time_buildings']>=3
        row['hard_supported']=row['hard_n']>=3 and row['hard_buildings']>=2
        rows.append(row)
        for mechanism,mg in geom[geom.reference_sample.eq(True)].groupby('mechanism'):
            mq=mg[mg.quality_usable&mg.Q_panel.eq(panel)]
            mt=mg[mg.log_time_peer_recomputed.notna()]
            mechrows.append(dict(worker_id=worker,condition=condition,origin=origin,panel=panel,mechanism=mechanism,
              n_geometry=len(mg),n_images=mg.image_id.nunique(),n_buildings=mg.building_id.nunique(),
              reduced_n=int(mg.reduced.eq(True).sum()),reduced_rate=mg.reduced.eq(True).mean(),
              short_turn_peer=mg.short_turn_edges_peer_delta.mean(),pair_peer=mg.pair_n_peer_delta.mean(),
              quality_n=len(mq),Q_mean=mq.B8L2.mean(),Q_peer=mq.B8L2_peer_recomputed.mean(),
              time_n=len(mt),time_median=mt.source_active_time_seconds.median(),log_time_peer=mt.log_time_peer_recomputed.mean()))
    p=pd.DataFrame(rows)
    for (condition,panel),g in d[d.quality_usable&d.Q_panel.eq(d.panel)].groupby(['condition','panel']):
        f=worker_effect(g,'B8L2')
        mask=p.condition.eq(condition)&p.panel.eq(panel)
        p.loc[mask,'Q_task_worker_effect']=p.loc[mask,'worker_id'].map(f)
    for (condition,origin,panel),g in d[d.log_time_peer_recomputed.notna()].groupby(['condition','origin','panel']):
        f=worker_effect(g,'log_source_time','time_task_key')
        mask=p.condition.eq(condition)&p.origin.eq(origin)&p.panel.eq(panel)
        p.loc[mask,'T_task_worker_effect']=p.loc[mask,'worker_id'].map(f)
    p.to_csv(out/'worker_profiles.csv',index=False)
    pd.DataFrame(diffrows).to_csv(out/'worker_difficulty.csv',index=False)
    pd.DataFrame(mechrows).to_csv(out/'worker_mechanisms.csv',index=False)
    reason_fields=['worker_id','condition','origin','panel','difficulty_class','exclusion_category','cleaning_disposition','exclusion_reason']
    d[~d.pool_analysis_eligible|~d.quality_usable].groupby(reason_fields,dropna=False).agg(
      n_objects=('object_id','size'),n_images=('image_id','nunique'),n_buildings=('building_id','nunique')).reset_index().to_csv(out/'worker_exclusion_reasons.csv',index=False)
    return p


def quality_model_check(d,lobo,out):
    effects=[]
    for target in sorted(d.building_id.unique()):
        for (condition,panel),g in d[d.building_id.ne(target)&d.quality_usable&d.Q_panel.eq(d.panel)].groupby(['condition','panel']):
            beta=worker_effect(g,'B8L2')
            for worker,value in beta.items():effects.append(dict(target_building=target,condition=condition,panel=panel,worker_id=worker,Q_task_worker_effect=value))
    e=pd.DataFrame(effects)
    lobo=lobo.merge(e,on=['target_building','condition','panel','worker_id'],how='left',validate='one_to_one')
    lobo.to_csv(out/'lobo_features.csv',index=False)
    q=d[d.quality_usable&d.Q_panel.eq(d.panel)].merge(lobo.rename(columns={'target_building':'building_id'}),
      on=['building_id','worker_id','condition','origin','panel'],suffixes=('','_history'),how='left',validate='many_to_one')
    q=q[q.Q_supported_8images_3buildings.eq(True)]
    metrics=['Q_mean','Q_peer','Q_rank','Q_task_worker_effect'];rows=[]
    for key,g in q.groupby(['image_id','image_code','building_id','condition','panel','task_key']):
        g=g.dropna(subset=metrics)
        if len(g)<3:continue
        for metric in metrics:
            a=g[metric].to_numpy(float);b=g.B8L2.to_numpy(float)
            dx=a[:,None]-a[None,:];dy=b[:,None]-b[None,:];ii=np.triu_indices(len(g),1)
            agree=(np.sign(dx[ii])*np.sign(dy[ii])+1)/2
            rows.append(dict(image_id=key[0],image_code=key[1],building_id=key[2],condition=key[3],panel=key[4],
              metric=metric,n_workers=len(g),spearman=g[metric].corr(g.B8L2,method='spearman'),pair_order_agreement=np.mean(agree)))
    r=pd.DataFrame(rows);r.to_csv(out/'quality_model_lobo_images.csv',index=False)
    r.groupby(['condition','panel','metric']).agg(images=('image_id','nunique'),buildings=('building_id','nunique'),
      mean_spearman=('spearman','mean'),mean_pair_order_agreement=('pair_order_agreement','mean')).reset_index().to_csv(out/'quality_model_lobo_summary.csv',index=False)
    return lobo,r


def pair_search(d,out):
    pairs=[];selected_records=[]
    for (condition,origin,panel),g in d[d.quality_usable&d.Q_panel.eq(d.panel)&d.source_active_time_seconds.gt(0)].groupby(['condition','origin','panel']):
        for a,b in combinations(sorted(g.worker_id.unique()),2):
            left=g[g.worker_id.eq(a)];right=g[g.worker_id.eq(b)]
            z=left.merge(right,on='task_key',suffixes=('_a','_b'),validate='one_to_one')
            if len(z)<5:continue
            logratio=np.log(z.source_active_time_seconds_b/z.source_active_time_seconds_a)
            qdelta=z.B8L2_b-z.B8L2_a
            pairs.append(dict(worker_a=a,worker_b=b,condition=condition,origin=origin,panel=panel,
              n_images=z.image_id_a.nunique(),n_buildings=z.building_id_a.nunique(),Q_a=z.B8L2_a.mean(),Q_b=z.B8L2_b.mean(),
              Q_b_minus_a=qdelta.mean(),Q_b_minus_a_median=qdelta.median(),Q_b_better_fraction=qdelta.gt(0).mean(),
              time_a_median=z.source_active_time_seconds_a.median(),time_b_median=z.source_active_time_seconds_b.median(),
              paired_time_ratio_b_over_a=np.exp(logratio.median()),paired_geomean_time_ratio_b_over_a=np.exp(logratio.mean()),
              slower_b_fraction=logratio.gt(0).mean(),
              short_turn_a=z.short_turn_edges_a.mean(),short_turn_b=z.short_turn_edges_b.mean(),
              pair_count_a=z.pair_count_a.mean(),pair_count_b=z.pair_count_b.mean()))
            if condition=='manual' and panel=='ordinary' and (a,b)==('W109','W112'):
                keep=['task_key','object_id_a','object_id_b','image_id_a','image_code_a','building_id_a','B8L2_a','B8L2_b',
                  'source_active_time_seconds_a','source_active_time_seconds_b','short_turn_edges_a','short_turn_edges_b','pair_count_a','pair_count_b']
                z[keep].to_csv(out/'W109_W112_paired_records.csv',index=False)
    p=pd.DataFrame(pairs);p.to_csv(out/'matched_person_pairs.csv',index=False)
    return p


def time_associations(d,out):
    rows=[];perimage=[]
    for (condition,origin,panel),g in d[d.log_time_peer_recomputed.notna()].groupby(['condition','origin','panel']):
        for outcome in ['B8L2','short_turn_edges','pair_n_peer_delta','bottom_bias_9']:
            z=g[g[outcome].notna()].copy()
            if outcome=='B8L2':z=z[z.quality_usable&z.Q_panel.eq(panel)]
            else:z=z[z.personal_comparison.eq(True)]
            if len(z)<30:continue
            x=residualize(z,'log_source_time','time_task_key');y=residualize(z,outcome,'time_task_key')
            slope=(x@y)/(x@x) if x@x>0 else np.nan
            rows.append(dict(condition=condition,origin=origin,panel=panel,outcome=outcome,n=len(z),images=z.image_id.nunique(),
              workers=z.worker_id.nunique(),buildings=z.building_id.nunique(),within_worker_and_task_slope_per_log_second=slope,
              outcome_change_per_time_doubling=slope*np.log(2),correlation=x.corr(y),interpretation='observational_fixed_effect_association_not_causal_time_benefit'))
    pd.DataFrame(rows).to_csv(out/'time_conditional_associations.csv',index=False)


def associations(p,out):
    rows=[]
    for (condition,origin,panel),g in p[p.Q_supported&p.T_supported].groupby(['condition','origin','panel']):
        for a,b in [('Q_mean','Q_peer'),('Q_peer','Q_rank'),('Q_peer','Q_task_worker_effect'),('Q_peer','Q_q10'),
          ('Q_peer','Q_sd'),('Q_peer','relative_time'),('Q_peer','short_turn_peer'),('relative_time','short_turn_peer'),
          ('relative_time','cleaning_excluded_rate'),('Q_peer','cleaning_excluded_rate'),('Q_peer','D10_peer')]:
            z=g[[a,b]].dropna()
            rows.append(dict(condition=condition,origin=origin,panel=panel,metric_a=a,metric_b=b,n_workers=len(z),spearman=z[a].corr(z[b],method='spearman')))
    pd.DataFrame(rows).to_csv(out/'profile_correlations.csv',index=False)


def additional_outputs(d,p,lobo,out):
    rows=[]
    for x in lobo[['target_building','worker_id','condition','origin','panel']].to_dict('records'):
        g=d[d.worker_id.eq(x['worker_id'])&d.condition.eq(x['condition'])&d.origin.eq(x['origin'])&d.panel.eq(x['panel'])&
            d.building_id.ne(x['target_building'])&d.quality_usable&d.Q_panel.eq(d.panel)&d.difficulty_reference_match]
        for level,label in [('简单','easy'),('中等','medium'),('困难','hard')]:
            q=g[g.difficulty_class.eq(level)]
            x.update({label+'_n':len(q),label+'_buildings':q.building_id.nunique(),label+'_Q_mean':q.B8L2.mean(),label+'_Q_peer':q.B8L2_peer_recomputed.mean()})
        x['hard_minus_easy_peer']=x['hard_Q_peer']-x['easy_Q_peer']
        x['hard_minus_easy_Q']=x['hard_Q_mean']-x['easy_Q_mean']
        rows.append(x)
    pd.DataFrame(rows).to_csv(out/'lobo_difficulty_features.csv',index=False)
    special=d[d.quality_usable&d.Q_panel.eq('special')]
    special.groupby(['worker_id','condition','origin'],dropna=False).agg(n_quality=('object_id','size'),images=('image_id','nunique'),
      Q_mean=('B8L2','mean'),D10_mean=('D10','mean'),Q_peer=('B8L2_peer_recomputed','mean')).reset_index().to_csv(out/'special_quality_profiles.csv',index=False)
    cols=['object_id','worker_id','condition','origin','image_id','image_code','building_id','quality_usable','B8L2','reference_id',
       'semi_confirmed_error_opportunity','semi_known_error_unchanged','semi_reported_error_opportunity','semi_reported_known_error_unchanged',
       'semi_edited','semi_exact_initialization']
    d[d.semi_confirmed_error_opportunity|d.semi_reported_error_opportunity][cols].to_csv(out/'semi_error_opportunity_index.csv',index=False)
    cols=['worker_id','origin','n_quality','Q_mean','Q_peer','Q_q10','Q_peer_q10','source_time_median','relative_time','n_time',
      'hard_n','hard_Q_mean','hard_Q_peer','hard_minus_easy_peer','n_inventory','n_cleaning_excluded','n_excluded_by_review',
      'n_historical_not_accepted','cleaning_excluded_rate','short_turn_peer','n_geometry','n_scope_response','n_scope_out','n_scope_judged',
      'n_scope_correct','confirmed_error_opportunities','confirmed_error_unchanged','reported_error_opportunities','reported_error_unchanged']
    for cond in ['manual','semi']:
        p[p.condition.eq(cond)&p.panel.eq('ordinary')][cols].to_csv(out/('ordinary_'+cond+'_profiles_small.csv'),index=False)
    # Direct shared-task pair descriptions, including condition/difficulty counterexamples.
    paired=[]
    for (condition,panel),g in d[d.quality_usable&d.Q_panel.eq(d.panel)&d.worker_id.isin(['W109','W112'])].groupby(['condition','panel']):
        a=g[g.worker_id.eq('W109')];b=g[g.worker_id.eq('W112')]
        z=a.merge(b,on='task_key',suffixes=('_a','_b'),validate='one_to_one')
        for level in ['all','简单','中等','困难']:
            v=z if level=='all' else z[z.difficulty_reference_match_a&z.difficulty_class_a.eq(level)]
            if not len(v):continue
            delta=v.B8L2_b-v.B8L2_a
            bybuilding=delta.groupby(v.building_id_a).mean()
            ratio=v.source_active_time_seconds_b/v.source_active_time_seconds_a
            paired.append(dict(condition=condition,panel=panel,difficulty=level,n_images=len(v),n_buildings=v.building_id_a.nunique(),
              Q_W109=v.B8L2_a.mean(),Q_W112=v.B8L2_b.mean(),delta_Q=delta.mean(),delta_Q_building_equal=bybuilding.mean(),
              W112_better_images=int(delta.gt(0).sum()),W112_better_buildings=int(bybuilding.gt(0).sum()),
              time_W109_median=v.source_active_time_seconds_a.median(),time_W112_median=v.source_active_time_seconds_b.median(),
              paired_time_ratio_median=np.exp(np.log(ratio).median()),short_turn_W109=v.short_turn_edges_a.mean(),short_turn_W112=v.short_turn_edges_b.mean(),
              pair_count_W109=v.pair_count_a.mean(),pair_count_W112=v.pair_count_b.mean()))
    pd.DataFrame(paired).to_csv(out/'W109_W112_common_task_summary.csv',index=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    d=load_records(args.repo);first_diagnostics(d,args.out)
    f=history_features(d,args.out)
    print('saved',args.out/'lobo_features.csv',len(f),flush=True)
    d=add_geometry_and_evidence(d,args.repo)
    p=profiles(d,args.out);print('profile rows',len(p),flush=True)
    f,q=quality_model_check(d,f,args.out);print('held-building quality comparisons',len(q),flush=True)
    pairs=pair_search(d,args.out);print('matched worker pairs',len(pairs),flush=True)
    time_associations(d,args.out);associations(p,args.out);additional_outputs(d,p,f,args.out)

if __name__=='__main__':main()
