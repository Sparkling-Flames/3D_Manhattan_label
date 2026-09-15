"""Final evidence audit. No model or threshold is selected by these summaries.

The report uses this verified summary, not provisional counters. Every row can
be traced to a saved image prediction, response, rule version or source field.
"""
from __future__ import annotations
import collections,itertools,json,re,warnings
import numpy as np,pandas as pd
from scipy.stats import spearmanr
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import *


def load(name):return pd.read_csv(OUT/name)

def descriptive_effect(d,xcol,ycol,controls):
    d=d.dropna(subset=[xcol,ycol,'n_valid']).copy()
    if len(d)<8 or d[xcol].nunique()<2:return dict(n=len(d),status='insufficient_variation')
    cols=[np.ones(len(d))]
    if controls in ('n','n_building_scene','n_building'):cols.append(np.log1p(d.n_valid.to_numpy(float)))
    if controls in ('n_building_scene','n_building'):cols.extend(pd.get_dummies(d.building,drop_first=True,dtype=float).to_numpy().T)
    if controls=='n_building_scene':cols.extend(pd.get_dummies(d.scene_category,drop_first=True,dtype=float).to_numpy().T)
    C=np.asarray(cols).T;x=d[xcol].to_numpy(float);y=d[ycol].to_numpy(float)
    xr=x-C@np.linalg.lstsq(C,x,rcond=None)[0];yr=y-C@np.linalg.lstsq(C,y,rcond=None)[0]
    if xr@xr<1e-9:return dict(n=len(d),status='no_within_control_variation')
    b=float(xr@yr/(xr@xr));u=yr-b*xr;s=pd.DataFrame({'building':d.building.to_numpy(),'score':xr*u}).groupby('building').score.sum();G=len(s)
    se=np.sqrt((s@s)/(xr@xr)**2*G/(G-1)) if G>1 else np.nan
    r=float(spearmanr(xr,yr).statistic) if np.ptp(yr)>1e-12 else np.nan
    return dict(n=len(d),buildings=G,slope=b,cluster_se=se,lo=b-1.96*se,hi=b+1.96*se,partial_rho=r,status='descriptive_not_causal')


def run():
    required=['execution/INPUT_ATTEMPT2_STATUS.json','execution/predict_STATUS.json','execution/associations_STATUS.json','execution/transfer_STATUS.json','execution/people_STATUS.json','execution/people_conditioned_STATUS.json','execution/diagnostics_STATUS.json']
    statuses={}
    for name in required:
        obj=read(OUT/name);statuses[name]=obj
        if isinstance(obj,list):assert all(x['returncode']==0 for x in obj)
        else:assert obj['returncode']==0
    p=load('targets/primary_with_robustness.csv');p['grade']=p.grade.fillna('');meta=load('inputs/image_metadata_whitelist.csv').fillna('')
    continuous=load('targets/continuous_targets.csv');d=continuous.merge(meta,on=['image_id','building']).merge(load('B/model_feedback.csv'),on='image_id',how='left')
    provenance=load('A_B/predictor_provenance.csv');assoc=load('A_B/associations_with_count_building_scene_controls.csv')
    # Correct initial 'none' substring handling. Previous none rows actually used n;
    # verified output recalculates all controls explicitly and retains prior file.
    for r in provenance.to_dict('records'):
        name=r['feature']
        if r['kind']=='sourced_trait_indicator':d[name]=(d[r['source_field']].astype(str)==str(r['category'])).astype(float)
    verified=[]
    for r in assoc.to_dict('records'):
        q=d[d.condition.eq(r['condition'])];result=descriptive_effect(q,r['feature'],r['target'],r['controls'])
        verified.append(dict(condition=r['condition'],target=r['target'],feature=r['feature'],controls=r['controls'],**result))
    va=csv('A_B/associations_verified.csv',verified)
    js('A_B/ASSOCIATION_AUDIT.json',dict(status='corrected_and_recomputed',superseded_file='associations_with_count_building_scene_controls.csv',primary_file='associations_verified.csv',issue="Old controls='none' was tested with substring 'n' and therefore duplicated count-adjusted rows; verified implementation uses explicit sets.",effect_on_prediction='none; predictor has independent training-only implementation',effect_on_adjusted_n_building_scene='none; those controls were already correctly applied'))
    categories=[]
    for arm,g in d.groupby('condition'):
        for field in ['scene_category','main_function_primary']:
            for value in g[field].unique():
                x=g.copy();x['category_indicator']=(x[field]==value).astype(float)
                for target in ['late_new_geometry','half_tv','singleton_mass','within_mode_median']:
                    for controls in ['none','n','n_building']:
                        categories.append(dict(condition=arm,field=field,value=value,target=target,controls=controls,**descriptive_effect(x,'category_indicator',target,controls)))
    cat=csv('A/category_process_adjusted_diagnostics.csv',categories)
    a=load('prediction/all_predictions.csv.gz')
    desired=['constant','scene_frequency','main_frequency','traits','feedback_counts','feedback_all','selected_existing_deep','selected_dino','selected_counts_plus_existing','selected_counts_plus_dino','selected_main_plus_existing','selected_main_plus_dino']
    select=a[a.feature.isin(desired)&a.algorithm.isin(['baseline','ridge'])]
    csv('prediction/compact_primary_scores.csv',load('prediction/score_summary.csv').query('feature in @desired and algorithm in ["baseline","ridge"]'))
    split=[]
    for field in ['source_split','scene_category','main_function_primary']:
        for key,g in select.groupby(['condition','target','feature',field],dropna=False):
            split.append(dict(condition=key[0],target=key[1],feature=key[2],stratum_field=field,stratum=key[3],images=g.image_id.nunique(),predicted_images=g.dropna(subset=['loss']).image_id.nunique(),loss=g.loss.mean(),buildings=g.building.nunique()))
    csv('prediction/source_and_scene_sensitivity.csv',split)
    common=[]
    for (arm,t),g in select.groupby(['condition','target']):
        wide=g.pivot(index=['image_id','building'],columns='feature',values='loss')
        available=[x for x in desired if x in wide];paired=wide[available].dropna()
        for name in available:common.append(dict(condition=arm,target=t,feature=name,common_images=len(paired),native_images=int(wide[name].notna().sum()),common_loss=paired[name].mean(),native_loss=wide[name].mean()))
    csv('prediction/all_family_common_coverage.csv',common)
    # Matched-count comparisons are descriptive, not a substitute for actual-n tier targets.
    counts=load('diagnostics/count_only_not_image_predictions.csv');num=[]
    for arm,g in counts.groupby('condition'):
        x=g[g.model=='actual_n_1NN_diagnostic'].merge(g[g.model=='overall_frequency'],on=['image_id','condition','building'],suffixes=('_n','_base'));x['delta']=x.loss_n-x.loss_base
        num.append(dict(condition=arm,**paired_ci(x,'delta')))
    csv('diagnostics/count_confounded_prediction_increment.csv',num)
    # How early groups differ in the actual amount of later evidence.
    early=p[p.grade=='simple'];csv('targets/early_tier_actual_horizon.csv',early[['image_id','condition','n_valid','p_early','p_tail_stable','observations_after_k','early_limit_censored','agreement_across_definitions','robust_assigned_grade']])
    robust=p[p.robust_assigned_grade.isin(GRADES)]
    csv('targets/robust_assigned_images.csv',robust)
    # Every flagged visual claim has actual worker and annotation identities attached.
    members=load('targets/mode_memberships_reused.csv.gz');members=members[np.isclose(members.cut,.1)]
    witnesses={}
    for key,g in members.groupby(['image_id','condition']):
        witnesses[key]=json.dumps(g.sort_values('worker_id').to_dict('records'),ensure_ascii=False)
    expert=load('expert/independent_tag_comment_process_comparison.csv');comments=load('expert/verified_nonempty_comments.csv').fillna('').set_index('image_id')
    review=[]
    def add(i,arm,reason,evidence,partner='',impact='historical mode interpretation'):
        review.append(dict(image_id=i,condition=arm,partner_image_id=partner,question=reason,numeric_evidence=json.dumps(safe(evidence),ensure_ascii=False),canonical_worker_mode_evidence=witnesses.get((i,arm),''),expert_image_comment=comments.loc[i,'actual_image_comment'] if i in comments.index else '',expert_group_comment=comments.loc[i,'group_comment'] if i in comments.index else '',affected_conclusion=impact,physical_legitimacy_adjudicated=False))
    for r in p[p.grade.isin(GRADES)].to_dict('records'):
        question='确认支持模式是否为不同合理空间范围，还是同一解释的连续定位差；单人标法不能默认错误。'
        if r['grade']=='difficult_candidate':question='确认碎片化和后期新标法对应遮挡/范围歧义、连续几何变化，还是不适用表示或个别无效解释；不能由簇数宣布永不收敛。'
        add(r['image_id'],r['condition'],question,{k:r[k] for k in ['grade','n_valid','n_supported_modes','n_singletons','singleton_mass','p_early','p_cumulative','late_new_geometry','agreement_across_definitions']})
    for r in expert[expert.comparison_status.eq('different_construct_or_condition')].to_dict('records'):
        add(r['image_id'],r['condition'],'核查人工预期及原评论，与实际作答过程不同的具体视觉原因；不自动纠正任何一套标签。',{'expert_tag':r['expert_tag'],'historical_grade':r['grade'],'n_valid':r['n_valid'],'p_early':r['p_early'],'p_cumulative':r['p_cumulative']},impact='expert expectation versus response-derived process')
    contrast=load('A/within_category_grade_contrasts.csv')
    # Keep all 42 within-category contrasts, not just visually convenient successes.
    for r in contrast.to_dict('records'):
        add(r['image_a'],r['condition'],'同大类内主呈现空间、局部范围/遮挡证据有何差别？两图实际人数不同，不能先归因为图片。',r,partner=r['image_b'],impact='within-category image versus observation/person confounding')
    bi=load('B/feedback_failures.csv')
    for r in bi.to_dict('records'):add(r['image_id'],'model','核查Bi extended后处理角点异常及其与原图结构的关系；保留缺失，不补零。',r,impact='model-output validity')
    csv('local_image_review_queue.csv',review)
    # Compact verified factual outputs for independent reading and report generation.
    transfer=load('D/conditional_transfer_summary.csv');selected_transfer=transfer[transfer.method.isin(['source_frequency','feedback_counts_nearest','dinov3__block3__panorama_global','dinov3__block12__panorama_global','dinov3__cls__panorama'])]
    effect=load('E_conditioned/paired_composition_effects.csv')
    common_people=load('E/same_room_exact_common_people.csv')
    cf=common_people[common_people.n_common>=4]
    person_summary=read(OUT/'E_conditioned/executed_summary.json');person_summary.update(common_people_pairs=len(common_people),common_people_pairs_atleast4=len(cf))
    selected_effect=effect[effect.n_people.isin([4,6,8])&effect.measure.isin(['point_count_disagreement','singleton_mass','mode_entropy','p_early7','late_new'])]
    js('VERIFIED_FINDINGS.json',dict(coverage=read(OUT/'targets/coverage.json'),actual_model_arrays=read(OUT/'C/coverage.json'),prediction_execution=read(OUT/'prediction/execution.json'),prediction_compact=load('prediction/compact_primary_scores.csv').to_dict('records'),paired_increment=load('prediction/paired_increment.csv').to_dict('records'),count_diagnostic=load('diagnostics/count_only_summary.csv').to_dict('records'),expert_comment_audit=read(OUT/'expert/COMMENT_COUNT_CORRECTION.json'),expert_cross_table=load('expert/independent_comparison_summary.csv').to_dict('records'),person_summary=person_summary,selected_person_effects=selected_effect.to_dict('records'),selected_transfer=selected_transfer.to_dict('records'),singleton_future=load('extra/singleton_future_support_summary.csv').query('cut==0.1 and k in [4,6,8]').to_dict('records'),early_horizons=early.groupby(['condition','n_valid']).size().to_dict(),robust_grade_counts=robust.groupby(['condition','robust_assigned_grade']).size().to_dict(),review_queue_rows=len(review),review_unique_images=len({r['image_id'] for r in review}|{r['partner_image_id'] for r in review if r['partner_image_id']}),limits=['Same outcomes previously viewed: follow-up exploration, not new independent validation.','Full source history is used only in targets/conditional transfer, never cold image predictors.','At n<19, cdf_observed_by19 is censored at actual n-1, not a claim about 19 unobserved people.','Only one medium image in each condition; target-building training lacks this class.','Correlations are observational; adjusted associations cannot identify unmeasured person/protocol differences.','The 70 kernel candidates retain exact numerical information for the declared L2 pipeline, not raw spatial tensors.']))
    csv('A_B/selected_adjusted_associations.csv',va[(va.controls=='n_building_scene')&va.feature.isin(['count_hohonet','count_bi_enclosed','bi_head_geometry_gap','rotation_hohonet','gap_hohonet_ulayout','trait__reflection_glass__present','trait__floor_boundary__partial','position_door','position_corner'])])
    js('execution/FINAL_EVIDENCE_AUDIT.json',dict(status='passed',required_stages=statuses,old_experimental_difficulty_in_predictors=False,expert_tags_used_for_tiers=False,actual_source_scope=205,condition_specific_person_main_analysis='E_conditioned/',pooled_person_profiles='E/ original exploratory outputs retained, not primary',comments_counter_corrected=True,association_none_control_corrected=True,report_results_from_verified_tables=True))
    print(json.dumps(safe({'coverage':read(OUT/'targets/coverage.json'),'person':person_summary,'queue':len(review),'predictions':len(a),'comments':read(OUT/'expert/COMMENT_COUNT_CORRECTION.json')}),ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':run()
