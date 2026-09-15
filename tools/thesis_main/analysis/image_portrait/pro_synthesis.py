"""Train-only layer selection and cross-route synthesis of executed predictions.

Outer scores never select a candidate. Historical fixed-reference distances are
kept out of the inductive layer selector. Post-hoc fixed-candidate rankings remain
explicitly descriptive. Paired uncertainty resamples buildings, not people/orders.
"""
import collections,itertools,json
from pathlib import Path
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait.pro_core import *
from tools.thesis_main.analysis.image_portrait.pro_statistics import building_bootstrap


def layer_selection():
    reg=json.loads((OUT/'features/registry.json').read_text());missing=[n for n in reg if not(OUT/'prediction'/f'{n}.csv.gz').exists()]
    if missing:raise RuntimeError('Incomplete fixed candidates: '+str(missing))
    current=[n for n,r in reg.items()if r['family']=='C'];extra=[n for n,r in reg.items()if r['family']=='C_exploratory'];historical=[n for n,r in reg.items()if r['model']=='historical_hohonet']
    groups={'current_prespecified_all':current,'current_plus_new_pooling':current+extra,'historical_inductive_layers':historical}
    for model in ['hohonet','bilayout','ulayout','da3']:
        groups['current_'+model]=[n for n in current if reg[n]['model']==model]
        groups['expanded_'+model]=[n for n in current+extra if reg[n]['model']==model]
    groups['current_global']=[n for n in current if reg[n]['pool'] in ['global','mean','six_face_mean']]
    groups['current_local']=[n for n in current if 'local16' in reg[n]['pool']]
    allnames=set(n for ns in groups.values()for n in ns);inners=pd.concat([pd.read_csv(OUT/'prediction'/f'{n}.inner.csv.gz')for n in sorted(allnames)],ignore_index=True)
    # Same stable tie rule, then simpler original dimension/name for layer ties.
    inners['pca_rank']=inners.pca.map(lambda x:0 if pd.isna(x) or str(x)=='None'else int(float(x)));inners['param_rank']=np.where(inners.algorithm=='ridge',-inners.parameter,inners.parameter);inners['dimensions']=inners.feature.map(lambda n:reg[n]['dimensions'])
    predictions={n:pd.read_csv(OUT/'prediction'/f'{n}.csv.gz')for n in allnames};rows=[];selections=[]
    for group,names in groups.items():
        q=inners[inners.feature.isin(names)].dropna(subset=['inner_MAE']).sort_values(['inner_MAE','pca_rank','param_rank','dimensions','feature']);chosen=q.groupby(['condition','target','outer_building','algorithm'],as_index=False).first()
        for row in chosen.itertuples():
            selections.append(dict(selector=group,condition=row.condition,target=row.target,heldout_building=row.outer_building,algorithm=row.algorithm,feature=row.feature,inner_MAE=row.inner_MAE,pca=row.pca,parameter=row.parameter,inner_images=row.inner_images,dimensions=row.dimensions,candidate_count=len(names)))
            p=predictions[row.feature];p=p[(p.condition==row.condition)&(p.target==row.target)&(p.building==row.outer_building)&(p.algorithm==row.algorithm)&p.design.isin(['leave_building','leave_supported_room_conservative'])].copy();p['selected_feature']=p.feature;p['feature']='SEL_'+group;rows.append(p)
    output=pd.concat(rows,ignore_index=True);write_csv('C/training_selected_layers.csv',selections);write_csv('prediction/selected_layers.csv.gz',output)
    # A fixed equal-weight ensemble, no fit/weight optimization on heldout people.
    for alg in ['ridge','knn']:
        names=['SEL_current_'+m for m in ['hohonet','bilayout','ulayout','da3']]
        g=output[(output.algorithm==alg)&output.feature.isin(names)].dropna(subset=['prediction']);index=['condition','target','design','fold_id','room_id','image_id','building']
        ens=g.groupby(index,dropna=False).agg(prediction=('prediction','mean'),truth=('truth','first'),n_models=('feature','nunique')).reset_index();ens=ens[ens.n_models==4];ens['absolute_error']=abs(ens.prediction-ens.truth);ens['feature']='ENSEMBLE_four_train_selected_models';ens['algorithm']=alg;ens['status']='four_available_equal_weights';rows.append(ens)
    write_csv('prediction/selected_layers.csv.gz',pd.concat(rows,ignore_index=True))
    summary=[]
    for key,g in pd.concat(rows,ignore_index=True).groupby(['feature','algorithm','condition','target','design']):
        v=g.dropna(subset=['prediction']);summary.append(dict(feature=key[0],algorithm=key[1],condition=key[2],target=key[3],design=key[4],n_target_images=g.image_id.nunique(),n_prediction_images=v.image_id.nunique(),image_MAE=v.absolute_error.mean(),building_macro_MAE=v.groupby('building').absolute_error.mean().mean(),room_macro_MAE=v.groupby('room_id').absolute_error.mean().mean()))
    write_csv('C/training_selected_score_summary.csv',summary)


def paired_family_comparisons():
    files=['baselines','A_all_traits','B_feedback','AB_traits_feedback','ABC_traits_feedback_shared','ABCN_actual_people_count','ABCP_crossfit_worker_composition','ABCC_historical_context','selected_layers']
    a=pd.concat([pd.read_csv(OUT/'prediction'/f'{n}.csv.gz')for n in files],ignore_index=True);rows=[]
    comparisons=[('A_all_traits','baseline'),('B_feedback','baseline'),('AB_traits_feedback','A_all_traits'),('AB_traits_feedback','B_feedback'),('ABC_traits_feedback_shared','AB_traits_feedback'),('ABCN_actual_people_count','ABC_traits_feedback_shared'),('ABCP_crossfit_worker_composition','ABCN_actual_people_count'),('ABCP_crossfit_worker_composition','ABC_traits_feedback_shared'),('ABCC_historical_context','ABCN_actual_people_count'),('SEL_current_prespecified_all','baseline'),('SEL_current_prespecified_all','B_feedback'),('SEL_current_plus_new_pooling','SEL_current_prespecified_all'),('SEL_current_local','SEL_current_global'),('ENSEMBLE_four_train_selected_models','SEL_current_prespecified_all')]
    for method,base in comparisons:
        for key,g in a[a.feature==method].groupby(['algorithm','condition','target','design']):
            q=a[(a.feature==base)&(a.algorithm==('constant_median'if base=='baseline' else key[0]))&(a.condition==key[1])&(a.target==key[2])&(a.design==key[3])]
            paired=g.merge(q[['image_id','fold_id','prediction','absolute_error']],on=['image_id','fold_id'],suffixes=('','_base')).dropna(subset=['prediction','prediction_base']);paired['delta']=paired.absolute_error-paired.absolute_error_base
            im=paired.groupby(['building','image_id'],as_index=False)[['delta','absolute_error','absolute_error_base']].mean();ci=building_bootstrap(im,'delta')
            rows.append(dict(method=method,baseline=base,algorithm=key[0],condition=key[1],target=key[2],design=key[3],n_images=len(im),n_buildings=im.building.nunique(),method_MAE=im.absolute_error.mean(),baseline_MAE=im.absolute_error_base.mean(),paired_MAE_delta=im.delta.mean(),relative_MAE_reduction=1-im.absolute_error.mean()/im.absolute_error_base.mean()if im.absolute_error_base.mean()>0 else np.nan,CI_low=ci[0],CI_high=ci[1],building_macro_delta=im.groupby('building').delta.mean().mean(),macro_CI_low=ci[2],macro_CI_high=ci[3]))
    write_csv('cross_route/family_increment_paired.csv',rows)


def room_history_transfer():
    rows=[];s=[]
    names=['baselines','A_all_traits','B_feedback','ABC_traits_feedback_shared','C_hohonet_shared_global','C_bilayout_fg_enclosed_global','C_da3_layer11_global']
    for name in names:
        a=pd.read_csv(OUT/'prediction'/f'{name}.csv.gz');a=a.dropna(subset=['prediction']);a=a[a.condition.isin(['manual','semi'])]
        for key,g in a[a.design=='same_room_leave_view'].groupby(['feature','algorithm','condition','target']):
            out=a[(a.design=='leave_building')&(a.feature==key[0])&(a.algorithm==key[1])&(a.condition==key[2])&(a.target==key[3])];p=g.merge(out[['image_id','prediction','absolute_error']],on='image_id',suffixes=('','_outside_building'));p['delta']=p.absolute_error-p.absolute_error_outside_building;rows.append(p)
            z=p.groupby(['building','image_id'],as_index=False)[['delta','absolute_error','absolute_error_outside_building']].mean();ci=building_bootstrap(z,'delta')
            s.append(dict(feature=key[0],algorithm=key[1],condition=key[2],target=key[3],n_images=len(z),n_rooms=p.room_id.nunique(),n_buildings=z.building.nunique(),within_room_MAE=z.absolute_error.mean(),outside_building_MAE=z.absolute_error_outside_building.mean(),paired_MAE_delta=z.delta.mean(),CI_low=ci[0],CI_high=ci[1]))
    write_csv('D/history_same_room_vs_outside_building.csv',s);write_csv('D/history_transfer_image_predictions.csv.gz',pd.concat(rows,ignore_index=True))
    # All genuine common-person view contrasts, irrespective of unchanged ratings.
    c=pd.read_csv(OUT/'A/same_room_common_workers.csv');contrast=[]
    for target in ['quality','time','scope_non_normal']:
        q=c.dropna(subset=[target+'_delta']).copy();v=q.groupby(['building','room_id','image_a','image_b'],as_index=False).agg(n_workers=('worker_id','nunique'),median_signed_difference=(target+'_delta','median'),mean_absolute_difference=(target+'_delta',lambda x:abs(x).mean()))
        v['endpoint']=target;contrast.append(v)
    write_csv('D/common_person_view_outcome_differences.csv',pd.concat(contrast,ignore_index=True))


def composition_contrasts():
    a=pd.read_csv(OUT/'E/composition_image_results.csv.gz');rows=[]
    metrics=['mean_median_reference_error','mean_total_active_seconds','mean_point_disagreement','mean_same_point_geometry_dispersion','mean_observed_population_coverage']
    # AB vs (AA+BB)/2 keeps number=2 and equal marginal class representation.
    for key,g in a[(a.people==2)&(a.k==2)].groupby(['condition','information']):
        q=g[g.pattern.isin(['AA','AB','BB'])].pivot(index=['image_id','building'],columns='pattern',values=metrics+['n_combinations','all_type_support_fraction'])
        for metric in metrics:
            if not all((metric,p)in q for p in ['AA','AB','BB']):continue
            z=q.loc[:,[(metric,p)for p in ['AA','AB','BB']]].dropna();z.columns=['AA','AB','BB'];z=z.reset_index();z['baseline']=(z.AA+z.BB)/2;z['delta']=z.AB-z.baseline
            linear_identity=metric in ['mean_median_reference_error','mean_total_active_seconds']
            if linear_identity:
                # With all2-person subsets, both metrics are linear in individual
                # values. Numerical epsilon is not an interaction effect.
                assert np.nanmax(np.abs(z.delta),initial=0)<1e-8
                z['delta']=0.0
            # Per-image combination means are the observations, not each subset.
            ci=building_bootstrap(z,'delta');rows.append(dict(condition=key[0],information=key[1],people=2,comparison='AB_minus_half_AA_half_BB',metric=metric,linear_identity_by_definition=linear_identity,n_images=len(z),n_buildings=z.building.nunique(),heterogeneous_mean=z.AB.mean(),matched_marginal_pure_mean=z.baseline.mean(),difference=z.delta.mean(),CI_low=ci[0],CI_high=ci[1]))
    write_csv('E/fixed_number_marginal_matched_compositions.csv',rows)
    base=pd.read_csv(OUT/'E/real_worker_combinations.csv.gz');s=[]
    for arm,g in base.groupby('condition'):
        for metric in ['median_reference_error','total_active_seconds','point_count_disagreement','same_point_geometry_dispersion','observed_population_coverage']:
            q=g.copy()
            if metric=='total_active_seconds':q=q[q.time_complete]
            if metric=='median_reference_error':q=q[q.quality_complete]
            im=q.groupby(['building','image_id','people'])[metric].mean().unstack('people')
            for n1,n2 in [(2,3),(3,4),(2,4)]:
                z=im[[n1,n2]].dropna().reset_index();z['delta']=z[n2]-z[n1];ci=building_bootstrap(z,'delta');s.append(dict(condition=arm,metric=metric,from_people=n1,to_people=n2,n_images=len(z),n_buildings=z.building.nunique(),from_mean=z[n1].mean(),to_mean=z[n2].mean(),difference=z.delta.mean(),CI_low=ci[0],CI_high=ci[1]))
    write_csv('E/number_effect_same_images.csv',s)
    ex=pd.read_csv(OUT/'E/requested_pattern_real_examples.csv.gz');caps=ex.groupby(['condition','pattern'],as_index=False).agg(saved_real_examples=('combo_id','size'),distinct_images=('image_id','nunique'),distinct_workers_union=('workers',lambda v:len(set(';'.join(v).split(';')))),examples_supported_types=('type_supported','sum'));write_csv('E/requested_composition_examples_coverage.csv',caps)


def selected_worker_summary():
    a=pd.read_csv(OUT/'E/training_selected_type_predictions.csv.gz');b=pd.read_csv(OUT/'E/heldout_image_contrasts.csv.gz');b=b[b.algorithm=='continuous_blocks_ridge10'];m=pd.read_csv(OUT/'E/Q_median2_predictions.csv.gz');a=pd.concat([a,b,m],ignore_index=True);rows=[]
    for key,g in a.groupby(['panel','information','algorithm','axis']):
        z=g.groupby(['image_id','building'],as_index=False)[['baseline_MAE','method_MAE','baseline_MSE','method_MSE']].mean();z['delta']=z.method_MAE-z.baseline_MAE;ci=building_bootstrap(z,'delta')
        rows.append(dict(panel=key[0],information=key[1],algorithm=key[2],axis=key[3],n_images=len(z),n_buildings=z.building.nunique(),baseline_MAE=z.baseline_MAE.mean(),method_MAE=z.method_MAE.mean(),delta=z.delta.mean(),CI_low=ci[0],CI_high=ci[1],relative_MSE_reduction=1-z.method_MSE.mean()/z.baseline_MSE.mean()if z.baseline_MSE.mean()>0 else np.nan))
    write_csv('E/selected_and_continuous_paired_summary.csv',rows)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['selection','other','all'],default='all');a=p.parse_args()
    if a.stage in ['selection','all']:layer_selection();paired_family_comparisons()
    if a.stage in ['other','all']:room_history_transfer();composition_contrasts();selected_worker_summary()
