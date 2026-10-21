#!/usr/bin/env python3
"""Readable members, opportunity support, auxiliary domains, role contrasts."""
import json,itertools
import numpy as np
import pandas as pd
import discover_behavior_classes as b

def main():
    labs=pd.read_csv(b.HERE/'ALL_METHOD_LABELS_ALL_DATA.csv')
    lobo=pd.read_csv(b.HERE/'ALL_METHOD_LABELS_LOBO.csv.gz')
    x=b.load();x['pair_n']=x.turn_n+x.near_straight_nodes_5deg
    old=pd.read_csv(b.REPO/'research/workers/personnel_global_composition_20261021/multivariate/continuous_features_lobo.csv.gz')
    old=old[old.heldout_building.eq('ALL')].drop(columns=['heldout_building'])
    auxiliary=[c for c in old if c not in ['worker_id','condition','origin','metric']]
    profiles=labs.merge(old[['condition','worker_id']+auxiliary],on=['condition','worker_id'],how='left',suffixes=('','_old'),validate='many_to_one')
    # Counts have an opportunity meaning; no missing event becomes a negative.
    support=[]
    for (cond,w),g in x[x.behavior_usable & x.layer.eq('ordinary')].groupby(['condition','worker_id']):
        non=g[g.near_straight_nodes_5deg.gt(0)]
        support.append(dict(condition=cond,worker_id=w,behavior_images=g.image_id.nunique(),behavior_buildings=g.building_id.nunique(),
            redundancy_images=non.image_id.nunique(),redundancy_buildings=non.building_id.nunique(),
            redundancy_nodes=int(non.near_straight_nodes_5deg.sum()),
            redundant_repeat_status='observed_in_at_least_2_buildings' if non.building_id.nunique()>=2 else 'one_building_only' if len(non) else 'not_observed',
            simple_images=g[~g.complex_opportunity].image_id.nunique(),complex_images=g[g.complex_opportunity].image_id.nunique(),
            ordinary_quality_records=int(g.B8L2.notna().sum()),formal_vote_records=int(g.independent_vote_eligible.sum())))
    profiles=profiles.merge(pd.DataFrame(support),on=['condition','worker_id'],how='left',suffixes=('','_observed'))
    b.save(profiles,'PERSONNEL_LABELS_EXPLAINED.csv')
    means=['q_effect','q_absolute_mean','q_absolute_p10','q_downside_old','t_effect','t_tail','source_time_median_seconds',
           'hard_minus_easy','medium_minus_easy','scope_out_effect','scope_gold_n','scope_gold_correct_n',
           'semi_edit_effect','semi_error_nonedit_effect']
    support_flags={**{k:'Q_supported' for k in ['q_effect','q_absolute_mean','q_absolute_p10','q_downside_old']},
        **{k:'T_supported' for k in ['t_effect','t_tail','source_time_median_seconds']},
        'hard_minus_easy':'D_supported','medium_minus_easy':'D_supported','scope_out_effect':'scope_supported',
        'semi_edit_effect':'semi_edit_supported','semi_error_nonedit_effect':'semi_error_nonedit_supported'}
    means=[c for c in means if c in profiles]
    rows=[]
    for (method,cond,co,fi),g in profiles.groupby(['method','condition','coarse_label','fine_label']):
        r=dict(method=method,condition=cond,coarse_label=co,fine_label=fi,n_members=len(g),members='|'.join(g.worker_id),
            known=bool(g.known.all()),selected_family=g.selected_family.iloc[0])
        for col in means:
            values=g.loc[g[support_flags[col]].eq(True),col] if col in support_flags else g[col]
            r[col+'_mean']=values.mean();r[col+'_people']=int(values.notna().sum())
        r['scope_gold_opportunities']=int(g.scope_gold_n.fillna(0).sum())
        r['scope_gold_correct']=int(g.scope_gold_correct_n.fillna(0).sum())
        r['scope_adjudicated_accuracy']=r['scope_gold_correct']/r['scope_gold_opportunities'] if r['scope_gold_opportunities'] else np.nan
        r['members_repeated_redundancy']=int(g.redundancy_buildings.ge(2).sum())
        rows.append(r)
    b.save(pd.DataFrame(rows),'CLASS_AUXILIARY_DOMAINS.csv')

    # Every target uses the centroid from its own outside-building fit. IDs from
    # different outer folds are not treated as the same categorical role.
    role_rows=[]
    for (method,cond,building),g in lobo[lobo.known].groupby(['method','condition','heldout_building']):
        for tier in ['coarse_label','fine_label']:
            for role,field in [('turn_expression','turn_history'),('redundant_segmentation','redundancy_history'),('scale_height','height_history'),('recorded_time','t_history')]:
                if field not in g or g[field].isna().all():continue
                med=g.groupby(tier)[field].mean().dropna().sort_values()
                if len(med)<2:continue
                lo,hi=med.index[0],med.index[-1]
                for w in g.worker_id:
                    r=g[g.worker_id.eq(w)].iloc[0]
                    if r[tier] not in [lo,hi]:continue
                    role_rows.append(dict(method=method,condition=cond,heldout_building=building,worker_id=w,tier=tier,role=role,
                        role_group='high' if r[tier]==hi else 'low',training_class=r[tier],training_centroid_low=med.iloc[0],training_centroid_high=med.iloc[-1]))
    roles=pd.DataFrame(role_rows);b.save(roles,'OUTER_CLASS_ROLE_MAP.csv.gz')
    d=x[x.behavior_usable].merge(roles,left_on=['condition','worker_id','building_id'],right_on=['condition','worker_id','heldout_building'],validate='many_to_many')
    metrics=b.RAW+['B8L2','D10','log_time_peer_delta']
    panels=[]
    group=['method','condition','tier','role','layer','image_id','reference_id']
    for key,g in d.groupby(group,dropna=False):
        for source in ['all','new','v1']:
            z=g if source=='all' else g[g.origin.eq(source)]
            lo,hi=z[z.role_group.eq('low')],z[z.role_group.eq('high')]
            if min(lo.worker_id.nunique(),hi.worker_id.nunique())<2:continue
            r=dict(zip(group,key));r.update(source=source,building_id=g.building_id.iloc[0],image_code=g.image_code.iloc[0],
                complex_opportunity=bool(g.complex_opportunity.iloc[0]),difficulty=str(g.difficulty.iloc[0]),
                low_class=g[g.role_group.eq('low')].training_class.iloc[0],high_class=g[g.role_group.eq('high')].training_class.iloc[0],
                low_members='|'.join(sorted(lo.worker_id.unique())),high_members='|'.join(sorted(hi.worker_id.unique())),
                n_low=lo.worker_id.nunique(),n_high=hi.worker_id.nunique())
            for m in metrics:
                aa,bb=lo[m].dropna(),hi[m].dropna()
                r[m+'_n_low']=len(aa);r[m+'_n_high']=len(bb)
                r[m+'_difference']=bb.mean()-aa.mean() if min(len(aa),len(bb))>=2 else np.nan
            panels.append(r)
    pp=pd.DataFrame(panels);b.save(pp,'OUTER_CLASS_ROLE_PANELS.csv.gz')
    summary=[]
    group=['method','condition','tier','role','layer','source']
    for extra in [[],['complex_opportunity']]:
        for key,g in pp.groupby(group+extra,dropna=False):
            r=dict(zip(group+extra,key));r['complex_opportunity']=r.get('complex_opportunity','all')
            r.update(panels=len(g),images=g.image_id.nunique(),buildings=g.building_id.nunique())
            for m in metrics:
                col=m+'_difference';values=g.groupby(['building_id','image_id'])[col].mean().groupby('building_id').mean().dropna()
                r[m+'_difference']=values.mean();r[m+'_buildings']=len(values);r[m+'_positive_buildings']=int(values.gt(0).sum())
                if len(values):
                    rng=np.random.default_rng(2026102141);boot=np.mean(rng.choice(values,size=(2000,len(values)),replace=True),axis=1)
                    r[m+'_ci_lo']=np.quantile(boot,.025);r[m+'_ci_hi']=np.quantile(boot,.975)
            summary.append(r)
    b.save(pd.DataFrame(summary),'OUTER_CLASS_ROLE_SUMMARY.csv')
    b.js('CLASS_INTERPRETATION_CONTRACT.json',dict(
        all_data='descriptive member lists, actual number of visible opportunities, raw nonzero count is not a semantic error rate',
        roles='high minus low historical class-centroid groups within each outer fit; >=2 workers per group in same image/reference, IDs are never compared across buildings',
        source='same-source contrasts separately; all-source total role effect is evaluated first',
        auxiliary='domain means include only people whose original corresponding support flag is true; missing opportunities remain unknown; scope correctness is pooled only over adjudicated opportunities',
        opportunities='complex panel = median actual worker noncollinear count >=6; not GT and not proof of necessary detail',
        semi='own final expression; edited/unchanged auxiliary evidence does not reconstruct unavailable initialization',
        quality='original frozen quality gates, B8L2/D10 only; behavior includes suspended-score images',
        inventory='non-OOS, ordinary fit; doorway and special_conditional only external descriptive contrasts'))
    print('Saved class explanations, support and role-based contrasts',len(pp),flush=True)

if __name__=='__main__':main()
