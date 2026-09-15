"""Evidence-led draft thresholds for user adjudication, never final labels.

This follows explicit expert feedback after seeing earlier results. No prediction
is fitted, no formal protocol is changed, and no expert tags are used by grade().
"""
from __future__ import annotations
import collections,itertools,json,math
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import OUT,PREV,B,ROOT,js,csv,sd,cluster,cluster_static,one_replay,readj

def few_limit(n,policy='count_band'):
 if policy=='fixed10pct':return int(math.floor(n*.10+1e-9))
 if policy=='absolute2':return min(2,max(0,n-2))
 if policy=='count_band':return 0 if n<4 else 1 if n<=8 else 2 if n<=16 else 3
 if policy=='count_band_lenient':return 0 if n<4 else 1 if n<=8 else 2 if n<=16 else 4
 raise ValueError(policy)

def grade(r,policy='count_band',max_total=6,early_k=8,late_h=19,medium_kind='cluster',jlimit=.85,hard_total=10,hard_f1=4,late_new=.15):
 n=int(r['n_valid']);M=int(r['total_clusters']);S=int(r['supported_clusters']);f1=int(r['singletons']);cap=few_limit(n,policy)
 if n<4:return '', 'too_few_valid_people'
 pearly=r.get(f'full_p_by_{early_k}',np.nan)
 if S in (1,2)and M<=3 and f1<=cap and pearly>=.8:return 'simple_candidate','early_full_pattern_stable_in_observed_valid_pool'
 few=2<=S<=4 and M<=max_total and f1<=cap and r['min_supported_loo_jaccard']>=jlimit
 pc=r.get(f'core15_p_by_{late_h}',np.nan)
 if few:
  if medium_kind=='cluster':return 'medium_candidate','supported_clusters_repeat;proportion_stability_reported_separately'
  if pc>=.8:return 'medium_candidate','supported_core_cumulative_stability_passed'
  return '', 'few_reproducible_clusters_but_process_not_confirmed'
 changing=r.get('late_quarter_new',np.nan)>=late_new and r.get('core_tail_15',np.nan)<.8
 if n>=10 and M>=hard_total and f1>=hard_f1 and changing:return 'difficult_candidate','many_total_clusters_many_singletons_and_observed_late_change'
 if S>=5 and r.get('core_tail_15',np.nan)>=.8:return '', 'many_supported_clusters_with_stable_core_not_never_convergent'
 if n<10:return '', 'short_horizon_or_unconfirmed_multi_pattern'
 if f1>cap:return '', 'singleton_rich_boundary;not_automatically_difficult'
 return '', 'order_partition_or_count_boundary'

def summarize_replays(rr):
 vals=[]
 for key,g in rr.groupby(['image_id','condition','cut'],sort=False):
  n=int(g.n_valid.iloc[0]);a=dict(zip(['image_id','condition','cut'],key),orders=len(g),actual_n=n)
  for nm,col in [('full','full_onset_no_gate'),('core10','core_onset_10'),('core15','core_onset_15'),('core20','core_onset_20')]:
   v=g[col].to_numpy();q=v[np.isfinite(v)];a[nm+'_p_any']=len(q)/len(v);a[nm+'_onset_median_conditional']=float(np.median(q))if len(q)else np.nan
   for k in [2,3,4,5,6,7,8,10,12,15,18,19]:
    a[f'{nm}_p_by_{k}']=float(np.mean(v<=min(k,n-1)));a[f'{nm}_requested_{k}_exceeds_observation']=k>n-1
  for col in ['full_tail_no_gate','core_tail_10','core_tail_15','core_tail_20','late_quarter_new','late_half_new','late_quarter_structure','late_quarter_repartition','half_tv_all','half_tv_core']:
   a[col]=float(g[col].mean())
  vals.append(a)
 return pd.DataFrame(vals)

def main():
 s=pd.read_csv(OUT/'structure/per_image_all_cuts.csv');rr=pd.read_csv(OUT/'process/per_order_onsets.csv.gz');p=summarize_replays(rr)
 ex=pd.read_csv(PREV/'expert/independent_tags106.csv').fillna('');old=pd.read_csv(PREV/'targets/primary_with_robustness.csv')
 md=pd.read_csv(PREV/'inputs/image_metadata_whitelist.csv');meta=[c for c in ['image_id','scene_category','main_function_primary','functional_fine_type','room_id','room_status','boundary_floor','occlusion','mirror']if c in md.columns]
 x=s.merge(p,on=['image_id','condition','cut'],how='left').merge(ex,on='image_id',how='left').merge(old[['image_id','condition','grade','status_x','p_cumulative','p_any_stable']],on=['image_id','condition'],how='left').rename(columns={'grade':'previous_grade','status_x':'previous_status','p_cumulative':'previous_cdf_by19','p_any_stable':'previous_any'})
 x=x.merge(md[meta],on='image_id',how='left')
 # No outcome imputation: lack of replay remains NaN/blank, not an unstable zero.
 csv('process/per_image_growth_summary.csv',x)
 allpol=[]
 for policy,m,kind in itertools.product(['fixed10pct','absolute2','count_band','count_band_lenient'],[6,7],['cluster','process']):
  for _,r in x[x.cut==.1].iterrows():
   label,status=grade(r,policy=policy,max_total=m,medium_kind=kind)
   allpol.append(dict(image_id=r.image_id,condition=r.condition,n_valid=r.n_valid,total_clusters=r.total_clusters,supported_clusters=r.supported_clusters,singletons=r.singletons,singleton_policy=policy,singleton_limit=few_limit(int(r.n_valid),policy),max_total=m,medium_kind=kind,grade_candidate=label,status=status))
 pol=csv('proposal/policy_comparison_per_image.csv',allpol)
 csv('proposal/policy_coverage.csv',pol.groupby(['condition','singleton_policy','max_total','medium_kind','grade_candidate'],dropna=False).size().reset_index(name='image_condition_units'))
 base=x[x.cut==.1].copy();recs=[]
 for _,r in base.iterrows():
  label,why=grade(r);dyn,why2=grade(r,medium_kind='process');d=r.to_dict()
  d.update(draft_grade=label,draft_reason=why,strict_process_grade=dyn,strict_process_reason=why2,singleton_count_limit=few_limit(int(r.n_valid)),valid_only=r.n_excluded>0)
  # Boundary/limited evidence are not additional ordinal difficulty classes.
  d['semantic_status']='requires_local_review'if r.supported_clusters>=2 else 'not_adjudicated'
  d['evidence_qualifier']='short_observed_pool'if r.n_valid<10 else 'weak_same_point_cluster_separation'if bool(r.get('weakly_separated_supported_pair',False))else 'none_of_these_flags'
  recs.append(d)
 out=pd.DataFrame(recs)
 cutlabels=[]
 for _,r in x.iterrows():
  if pd.isna(r.get('orders',np.nan)):continue
  z,w=grade(r);cutlabels.append(dict(image_id=r.image_id,condition=r.condition,cut=r.cut,draft_grade=z,status=w))
 cs=csv('proposal/geometry_threshold_grades.csv',cutlabels)
 stability=[]
 for key,g in cs[cs.cut.isin([.075,.10,.125])].groupby(['image_id','condition']):
  if len(g)!=3:continue
  vals=g.draft_grade.fillna('').tolist();stability.append(dict(image_id=key[0],condition=key[1],nearby_cuts_evaluated=3,nearby_all_same_grade=len(set(vals))==1,nearby_grade_pattern=';'.join(vals),nearby_same_assigned_grade=bool(vals[0] and len(set(vals))==1)))
 out=out.merge(pd.DataFrame(stability),on=['image_id','condition'],how='left')
 out['user_final_grade']='';out['user_decision_reason']='';out['user_cluster_semantics']='';out['user_singleton_assessment']=''
 csv('proposal/per_image_draft_for_user.csv',out)
 csv('proposal/old_difficult_reassessment.csv',out[out.previous_grade=='difficult_candidate'])
 csv('expert/all106_with_history_status.csv',ex.merge(out,on='image_id',how='left',suffixes=('','_replay')))
 csv('expert/medium_hard_historical_comparison.csv',out[out.expert_tag.isin(['中等','困难'])])
 csv('expert/high_support_anchor_comparison.csv',out[out.expert_tag.isin(['中等','困难'])&(out.n_valid>=10)])
 csv('expert/tag_vs_previous_grade.csv',out[out.expert_tag.notna()].groupby(['condition','expert_tag','previous_grade'],dropna=False).size().reset_index(name='images'))
 csv('expert/tag_vs_draft_grade.csv',out[out.expert_tag.notna()].groupby(['condition','expert_tag','draft_grade'],dropna=False).size().reset_index(name='images'))
 csv('proposal/early_k.csv',[dict(image_id=r.image_id,condition=r.condition,k=k,grade=grade(r,early_k=k)[0],n_valid=r.n_valid,cut=.1)for _,r in base.iterrows()for k in range(2,9)])
 csv('proposal/late_h.csv',[dict(image_id=r.image_id,condition=r.condition,h=h,grade=grade(r,late_h=h,medium_kind='process')[0],n_valid=r.n_valid,cut=.1,requested_h_exceeds_observation=h>r.n_valid-1)for _,r in base.iterrows()for h in[10,12,15,18,19]])
 # Exact absolute acceptance of fixed proportion exposes n=19 vs n=20 discontinuity.
 csv('proposal/singleton_threshold_by_n.csv',[dict(n=n,fixed10pct=few_limit(n,'fixed10pct'),absolute2=few_limit(n,'absolute2'),count_band=few_limit(n),lenient=few_limit(n,'count_band_lenient'),one_person_fraction=1/n)for n in range(2,25)])
 # Focus finite-pool prefix distributions: each image remains one inferential unit.
 trace=pd.read_csv(OUT/'process/focus_order_trace.csv.gz');agg=[]
 for key,g in trace[trace.k.isin([4,6,8,10,12,16,20])].groupby(['image_id','condition','k']):
  a=dict(zip(['image_id','condition','k'],key));a['orders']=len(g)
  for col in ['total_clusters','supported_clusters','singletons','tv_all','tv_core']:
   a[col+'_mean']=g[col].mean();a[col+'_p10']=g[col].quantile(.1);a[col+'_p90']=g[col].quantile(.9)
  a['p_fixed10pct_accepts']=np.mean(g.singletons<=np.floor(.1*g.k));a['p_count_band_accepts']=np.mean(g.singletons<=few_limit(int(key[2])))
  agg.append(a)
 rare=pd.DataFrame(agg).merge(ex[['image_id','expert_tag']],on='image_id',how='left')
 csv('process/reclustered_common_n_focused.csv',rare)
 # User-visible queue lists actual people/medoid IDs and fixed pair contexts.
 cl=pd.read_csv(OUT/'structure/per_cluster_stability.csv');mem=pd.read_csv(OUT/'structure/real_mode_memberships.csv.gz');queue=[]
 ids=set(out[out.expert_tag.isin(['中等','困难'])].image_id)|set(out[out.previous_grade=='difficult_candidate'].image_id)
 for _,r in out[out.image_id.isin(ids)].iterrows():
  modes=cl[(cl.image_id==r.image_id)&(cl.condition==r.condition)&(cl.cut==.1)]
  mm=mem[(mem.image_id==r.image_id)&(mem.condition==r.condition)&(mem.cut==.1)]
  reason=[]
  if r.weakly_separated_supported_pair:reason.append('同点数支持簇之间多数配对仍在兼容阈值内：是连续定位波动被切开，还是不同范围解释？')
  if r.singletons:reason.append('逐一核查单人标法：合理少数解释、范围选择、定位偏差或确实无效？不得仅按人数否定。')
  if r.n_excluded:reason.append('存在单列无效作答；有效子集结论能否代表该图，已确认修正是否准确？')
  if r.expert_tag=='困难'and r.supported_clusters>=2:reason.append('原困难预期指不能统一为一个答案，还是连多个模式的分布都不稳定？')
  if r.n_valid<10:reason.append('观察人数较少：只判断现有标法含义，不据此裁决永不稳定。')
  queue.append(dict(image_id=r.image_id,condition=r.condition,expert_tag=r.expert_tag,previous_grade=r.previous_grade,draft_grade=r.draft_grade,n_valid=r.n_valid,total_clusters=r.total_clusters,supported_clusters=r.supported_clusters,singletons=r.singletons,sizes_descending=r.sizes_descending,questions='；'.join(reason),affected_conclusion='初步中等/困难边界；模式数量的语义有效性；支持核心与整体分布是否混淆',canonical_ids=';'.join(mm.canonical_annotation_id.astype(str)),workers=';'.join(mm.worker_id.astype(str)),mode_medoid_ids=';'.join(modes.medoid_canonical_id.astype(str)),user_verdict=''))
 csv('local_image_review_queue.csv',queue)
 config=dict(stage='post-hoc evidence-informed proposed rubric; user final decision pending',expert_grades='comparison/context only; not algorithm inputs; after feedback not independent validation',primary_cut=.10,sensitivity_cuts=[.05,.075,.10,.125,.15,.20],simple='1-2 supported, <=3 total, count-band singletons, full-pattern by k<=8 >=.8; actual observed horizon kept',medium_structural='2-4 supported, <=6 total, count-band singletons, min conditional LOO Jaccard>=.85; NOT evidence of full distribution convergence',medium_process='same plus core cumulative by min(h,n-1)>=.8, h=10/12/15/18/19',count_band='n4-8:<=1; n9-16:<=2; n17-24:<=3; proposed, not literature-validated',difficult='n>=10, total>=10, f1>=4, late-quarter new geometry>=.15, core-tail15<.8; conditionally fragmented, never nonconvergence theorem',avoid_forced_grade=True,all_grades_provisional=True,weak_cluster_separation='cross compatible >.5 yields separate semantic caution; no silent merging',source_window='finite historical people pool, not chronological acquisition',large_models_refit=False)
 js('proposal/METHOD_AND_USER_DECISION.json',config)
 js('SUMMARY.json',dict(primary_coverage=out.groupby(['condition','draft_grade'],dropna=False).size().reset_index(name='images').to_dict('records'),strict_process=out.groupby(['condition','strict_process_grade'],dropna=False).size().reset_index(name='images').to_dict('records'),old_hard_changes=out[out.previous_grade=='difficult_candidate'].groupby(['condition','draft_grade'],dropna=False).size().reset_index(name='images').to_dict('records'),expert_overlap=out[out.expert_tag.notna()].groupby(['condition','expert_tag']).size().reset_index(name='images').to_dict('records'),review_cases=len(queue),review_images=len(set(q['image_id']for q in queue))))
 print(out.groupby(['condition','draft_grade']).size().to_string());print(out[out.previous_grade=='difficult_candidate'][['image_id','draft_grade','draft_reason']].to_string(index=False))
if __name__=='__main__':main()
