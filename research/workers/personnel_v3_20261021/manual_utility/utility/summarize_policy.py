"""Building-balanced policy effects and coarse/fine/continuous comparisons."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from prepare_training import HERE,atomic_csv,atomic_json
from policy_study import METRICS

SEED=2026102192
BASE_FIELDS=['failure_rate','ordinary_failure_rate','failure_delta_pp','time_percent_vs_uniform',
 'time_seconds_delta','time_seconds','ordinary_time_seconds','expected_changed_members_vs_uniform',
 'loss_gt5_vs_random_success_probability','loss_gt10_vs_random_success_probability',
 'failure_or_loss_gt5_vs_random_success_probability','failure_or_loss_gt10_vs_random_success_probability',
 'loss_gt5_delta_pp','loss_gt10_delta_pp','failure_or_loss_gt5_delta_pp','failure_or_loss_gt10_delta_pp']
BASE_FIELDS += [key+suffix for key in ['below_four','connection_unavailable','location_unresolved',
    'order_tied','complete_floor_failure'] for suffix in ['_rate','_delta_pp']]
FIELDS=BASE_FIELDS+METRICS+['delta_'+m for m in METRICS]
META=['regime','condition','family','policy']

def macro_many(g,fields):
    """One wide aggregation per slice; retain each outcome's missing support.

    Resample available buildings for each common missingness pattern, exactly
    matching the previous outcome-wise bootstrap without repeated groupbys.
    """
    fields=[f for f in fields if f in g and g[f].notna().any()]
    if not fields:return {},pd.DataFrame()
    byimage=g.groupby(['building','image'],sort=True)[fields].mean()
    b=byimage.groupby(level='building',sort=True).mean()
    image_n=byimage.notna().sum();panel_n=g[fields].notna().sum()
    groups={}
    for f in fields:groups.setdefault(tuple(b[f].notna().to_numpy()),[]).append(f)
    results={}
    for mask,cols in groups.items():
        values=b.loc[np.array(mask),cols].to_numpy(float);n=len(values)
        if n>1:
            r=np.random.default_rng(SEED)
            draw=r.integers(n,size=(2000,n))
            boot=values[draw].mean(axis=1)
            bounds=np.quantile(boot,[.025,.975],axis=0)
        else:bounds=np.full((2,len(cols)),np.nan)
        means=values.mean(axis=0);positive=(values>1e-10).sum(axis=0);negative=(values<-1e-10).sum(axis=0)
        for j,f in enumerate(cols):
            results[f]=dict(mean=float(means[j]),low95=float(bounds[0,j]),high95=float(bounds[1,j]),
                buildings=n,images=int(image_n[f]),panels=int(panel_n[f]),
                positive_buildings=int(positive[j]),negative_buildings=int(negative[j]))
    return results,b

def slices(d):
    yield 'all','all',d
    for n,g in d.groupby('n'):yield 'n',str(n),g
    for v,g in d.groupby('source_domain'):yield 'source_domain',v,g
    for v,g in d.groupby('difficulty'):yield 'difficulty',v,g
    for (n,source),g in d.groupby(['n','source_domain']):yield 'n_source',f'{n}/{source}',g
    if 'all_candidates_time_compatible' in d:
        timed=d[d.all_candidates_time_compatible.fillna(False)]
        if len(timed):
            yield 'joint_time_support','all_compatible',timed
            for n,g in timed.groupby('n'):yield 'n_joint_time_support',str(n),g
    if 'policy_can_discriminate' in d:
        for flag,g in d.groupby('policy_can_discriminate'):yield 'selection_opportunity',str(bool(flag)),g

def members_change(a,b,n):
    aa=json.loads(a);bb=json.loads(b)
    return float(n-sum(v*bb.get(w,0) for w,v in aa.items()))

def main():
    paths=sorted(HERE.glob('*/*/*/PANEL_POLICY_RESULTS.csv.gz'))
    if not paths:raise RuntimeError('No completed evaluations')
    parts=[pd.read_csv(p,low_memory=False) for p in paths]
    allrows=pd.concat(parts,ignore_index=True)
    assert not allrows.duplicated(META+['panel_id']).any()
    atomic_csv(allrows,HERE/'ALL_PANEL_POLICY_RESULTS.csv.gz')
    summaryparts=[];buildingparts=[]
    for vals,d in allrows.groupby(META):
        common=dict(zip(META,vals))
        summary=[];brows=[]
        for sk,sv,g in slices(d):
            stats,b=macro_many(g,FIELDS)
            for field,r in stats.items():
                summary.append(dict(common,slice_kind=sk,slice_value=sv,outcome=field,**r))
                if sk=='all':
                    brows += [dict(common,outcome=field,building=key,value=value) for key,value in b[field].dropna().items()]
        summaryparts.append(pd.DataFrame(summary));buildingparts.append(pd.DataFrame(brows))
    fullsummary=pd.concat(summaryparts,ignore_index=True)
    summary_rows=len(fullsummary)
    atomic_csv(fullsummary,HERE/'POLICY_EFFECTS_SUMMARY.csv.gz')
    keyoutcomes=['delta_B8L2','delta_D10','failure_delta_pp','time_percent_vs_uniform',
                 'time_seconds_delta','failure_or_loss_gt5_delta_pp','failure_or_loss_gt10_delta_pp']
    atomic_csv(fullsummary[fullsummary.slice_kind.isin(['all','n','source_domain','difficulty','joint_time_support','n_joint_time_support'])&
        fullsummary.outcome.isin(keyoutcomes)],HERE/'KEY_POLICY_EFFECTS.csv')
    atomic_csv(pd.concat(buildingparts,ignore_index=True),HERE/'POLICY_EFFECTS_BUILDINGS.csv')
    del summaryparts,buildingparts,fullsummary
    pairs=[]
    for goal in ('quality','balanced'):
        for a,b in [('class_fine','class_coarse'),('class_coarse','QT'),('class_fine','QT'),
                    ('class_coarse','source'),('class_fine','source'),
                    ('class_coarse_interaction','source'),('class_fine_interaction','source'),
                    ('QT_class_coarse','QT'),('QT_class_fine','QT'),('QT_continuous_structure','QT'),
                    ('QT_class_fine','QT_continuous_structure'),('continuous_structure','QT')]:
            pairs.append((a+'__'+goal,b+'__'+goal))
        for a,b in [('class_coarse','exact_continuous'),('class_fine','exact_continuous'),
                    ('exact_continuous_class_fine','exact_continuous'),('exact_continuous','QT_continuous_structure')]:
            pairs.append((a+'__'+goal,b+'__'+goal))
        for a,b in [('class_coarse_interaction','class_coarse'),('class_fine_interaction','class_fine'),
                    ('class_fine_interaction','class_coarse_interaction'),('QT_interaction','QT'),
                    ('exact_continuous_interaction','exact_continuous'),
                    ('class_coarse_interaction','exact_continuous_interaction'),
                    ('class_fine_interaction','exact_continuous_interaction'),
                    ('exact_continuous_interaction_class_fine','exact_continuous_interaction'),
                    ('QT_continuous_structure_interaction','QT_interaction'),
                    ('class_fine_interaction','QT_continuous_structure_interaction')]:
            pairs.append((a+'__'+goal,b+'__'+goal))
    pairs += [('history_Q','ordinary_uniform'),('history_T','ordinary_uniform'),
              ('QT__balanced','history_T'),('QT__quality','history_Q')]
    contrastparts=[];eventparts=[]
    for vals,d in allrows.groupby(['regime','condition','family']):
        meta=dict(zip(['regime','condition','family'],vals))
        for new,base in pairs:
            contrasts=[]
            a=d[d.policy.eq(new)];b=d[d.policy.eq(base)]
            if not len(a) or not len(b):continue
            key=['panel_id','building','image','difficulty','n','source_domain']
            cols=key+[f for f in FIELDS if f in d]+['selected_worker_inclusion_probabilities','selected_teams','selection_distribution_sha256','all_candidates_time_compatible']
            z=a[cols].merge(b[cols],on=key,validate='one_to_one',suffixes=('_new','_baseline'))
            z['all_candidates_time_compatible']=z.all_candidates_time_compatible_new&z.all_candidates_time_compatible_baseline
            z['expected_changed_members_between_policies']=[members_change(x,y,n) for x,y,n in zip(z.selected_worker_inclusion_probabilities_new,z.selected_worker_inclusion_probabilities_baseline,z.n)]
            z['relative_time_percent_between_policies']=100*(z.time_seconds_new/z.time_seconds_baseline-1)
            z['policy_choice_distribution_identical']=z.selection_distribution_sha256_new.eq(z.selection_distribution_sha256_baseline)
            for field in FIELDS:
                if field+'_new' in z:z['contrast_'+field]=z[field+'_new']-z[field+'_baseline']
            z['new_policy']=new;z['baseline']=base
            for k,v in meta.items():z[k]=v
            eventparts.append(z)
            fields=['contrast_'+f for f in FIELDS if 'contrast_'+f in z]+['expected_changed_members_between_policies','relative_time_percent_between_policies']
            for sk,sv,g in slices(z):
                stats,_=macro_many(g,fields)
                for field,r in stats.items():
                    contrasts.append(dict(meta,new_policy=new,baseline=base,slice_kind=sk,slice_value=sv,outcome=field,**r))
            contrastparts.append(pd.DataFrame(contrasts))
    atomic_csv(pd.concat(eventparts,ignore_index=True),HERE/'PAIRED_POLICY_EVENTS.csv.gz')
    fullcontrast=pd.concat(contrastparts,ignore_index=True);contrast_rows=len(fullcontrast)
    atomic_csv(fullcontrast,HERE/'PAIRED_POLICY_SUMMARY.csv.gz')
    atomic_csv(fullcontrast[fullcontrast.slice_kind.isin(['all','joint_time_support'])&
        fullcontrast.outcome.isin(['contrast_'+f for f in keyoutcomes]+['relative_time_percent_between_policies'])],HERE/'KEY_PAIRED_POLICY_EFFECTS.csv')
    del contrastparts,eventparts,fullcontrast
    # Across classification methods compare only identical actual candidate sets.
    # Their training eligibility may differ, and is retained in each FITS table.
    methodrows=[];methodparts=[];methodcoverage=[]
    methodpairs=[('new_behavior','old_structure'),('new_joint','old_structure'),
                 ('new_joint','new_behavior'),('new_joint','old_multivariate')]
    for (regime,condition),d in allrows.groupby(['regime','condition']):
        for new,base in methodpairs:
            for policy in ['class_coarse__quality','class_fine__quality','class_coarse__balanced','class_fine__balanced',
                           'QT_class_fine__quality','QT_class_fine__balanced',
                           'class_coarse_interaction__quality','class_fine_interaction__quality',
                           'class_coarse_interaction__balanced','class_fine_interaction__balanced']:
                methods=[]
                a=d[d.family.eq(new)&d.policy.eq(policy)];b=d[d.family.eq(base)&d.policy.eq(policy)]
                if not len(a) or not len(b):continue
                keys=['panel_id','building','image','difficulty','n','source_domain']
                cols=keys+[f for f in FIELDS if f in d]+['candidate_support_sha256','all_candidates_time_compatible',
                     'selected_worker_inclusion_probabilities','selection_distribution_sha256']
                z=a[cols].merge(b[cols],on=keys,validate='one_to_one',suffixes=('_new','_baseline'))
                same=z.candidate_support_sha256_new.eq(z.candidate_support_sha256_baseline)
                methodcoverage.append(dict(regime=regime,condition=condition,new_family=new,baseline_family=base,
                    policy=policy,new_panels=len(a),baseline_panels=len(b),both_panels=len(z),
                    identical_candidate_panels=int(same.sum()),excluded_different_candidates=int((~same).sum())))
                z=z.loc[same].copy()
                if not len(z):continue
                z['all_candidates_time_compatible']=z.all_candidates_time_compatible_new&z.all_candidates_time_compatible_baseline
                for field in FIELDS:
                    if field+'_new' in z:z['contrast_'+field]=z[field+'_new']-z[field+'_baseline']
                z['expected_changed_members_between_policies']=[members_change(x,y,n) for x,y,n in zip(z.selected_worker_inclusion_probabilities_new,z.selected_worker_inclusion_probabilities_baseline,z.n)]
                z['relative_time_percent_between_policies']=100*(z.time_seconds_new/z.time_seconds_baseline-1)
                z['policy_choice_distribution_identical']=z.selection_distribution_sha256_new.eq(z.selection_distribution_sha256_baseline)
                meta=dict(regime=regime,condition=condition,new_family=new,baseline_family=base,policy=policy)
                for k,v in meta.items():z[k]=v
                methodrows.append(z)
                fields=['contrast_'+f for f in FIELDS if 'contrast_'+f in z]+['expected_changed_members_between_policies','relative_time_percent_between_policies']
                for sk,sv,g in slices(z):
                    stats,_=macro_many(g,fields)
                    for field,r in stats.items():methods.append(dict(meta,slice_kind=sk,slice_value=sv,outcome=field,**r))
                methodparts.append(pd.DataFrame(methods))
    atomic_csv(pd.concat(methodrows,ignore_index=True),HERE/'PAIRED_METHOD_EVENTS.csv.gz')
    fullmethods=pd.concat(methodparts,ignore_index=True)
    atomic_csv(fullmethods,HERE/'PAIRED_METHOD_SUMMARY.csv.gz')
    atomic_csv(fullmethods[fullmethods.slice_kind.isin(['all','joint_time_support'])&
        fullmethods.outcome.isin(['contrast_'+f for f in keyoutcomes]+['relative_time_percent_between_policies'])],HERE/'KEY_PAIRED_METHOD_EFFECTS.csv')
    atomic_csv(pd.DataFrame(methodcoverage),HERE/'PAIRED_METHOD_COVERAGE.csv')
    coverage=allrows[allrows.policy.eq('ordinary_uniform')].groupby(['regime','condition','family'],as_index=False).agg(
        panels=('panel_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),
        candidate_references=('common_candidates','sum'),fully_supported_panels=('all_registered_members_common','sum'),
        time_complete_panels=('all_candidates_time_compatible','sum'),n_min=('n','min'),n_max=('n','max'))
    atomic_csv(coverage,HERE/'POLICY_COVERAGE.csv')
    atomic_json(dict(input_files=len(paths),panel_policy_rows=len(allrows),summary_rows=summary_rows,
        contrast_rows=contrast_rows,coverage=coverage.to_dict('records'),
        ordinary='uniform actual sets in same common-support fixed-background panel',
        tie_policy='uniform all objective maxima, epsilon=1e-9',
        confidence='2000 building bootstrap; panel then image then building equal',
        probability_loss_reference='independent uniform successful candidate from same finite panel',
        time='sum source seconds; full common-candidate complete compatible-time panels only'),
        HERE/'SUMMARY_RECEIPT.json')
    print(coverage.to_string(index=False),flush=True)

if __name__=='__main__':main()
