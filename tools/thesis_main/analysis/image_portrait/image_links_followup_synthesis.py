"""Cross-route evidence and counterexamples, never automatic human adjudication."""
from __future__ import annotations
import itertools
from tools.thesis_main.analysis.image_portrait.image_links_followup_common import *
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import cluster_static,one_replay

def run():
 d=pd.read_csv(OUT/'targets/per_image_versions_and_process.csv');meta=d.drop_duplicates('image_id').set_index('image_id');pools=groups();st=[]
 for(i,c),(r,dm,pc,w,ci)in pools.items():
  x,cl,sp,l=cluster_static(dm,pc,.1);st.append(dict(image_id=i,condition=c,**x))
 static=csv('extra/full_structure_recalculated.csv',st);z=d.drop(columns=[x for x in static if x not in ['image_id','condition']],errors='ignore').merge(static,on=['image_id','condition']);med=z[z.review_draft_grade.eq('medium_candidate')].copy();med['support_modes_equal_count_strata']=med.supported_clusters.eq(med.supported_point_counts);med['weak_geometry_separation']=med.max_cross_compatible_share>.5;csv('extra/medium_identifiability.csv',med);csv('extra/medium_identifiability_summary.csv',med.groupby('condition').agg(images=('image_id','nunique'),count_strata_only=('support_modes_equal_count_strata','sum'),weak_separation=('weak_geometry_separation','sum'),full_tail_mean=('full_tail_no_gate','mean'),core_tail_mean=('core_tail_10','mean'),median_people=('n_valid','median')).reset_index())
 # Version comparison uses matched images and identical scoring, never translates old RPS into Brier.
 scores=pd.read_csv(OUT/'prediction/score_summary.csv');short=scores[scores.feature.isin(['constant','scene_frequency','main_frequency','feedback_counts','feedback_all','selected_existing','selected_dino','selected_counts_existing','selected_counts_dino','main_plus::feedback_all'])&scores.algorithm.isin(['ridge','baseline'])];csv('prediction/key_results.csv',short)
 pr=pd.read_csv(OUT/'prediction/all_predictions.csv.gz',low_memory=False);comparisons=[]
 for (arm,target),g in pr[(pr.algorithm.isin(['ridge','baseline']))].groupby(['condition','target']):
  for new,old in [('feedback_counts','constant'),('feedback_all','constant'),('feedback_all','feedback_counts'),('selected_counts_dino','selected_counts_existing'),('main_plus::feedback_all','constant'),('selected_dino','constant')]:
   m=g[g.feature.eq(new)].merge(g[g.feature.eq(old)],on=['image_id','building'],suffixes=('_new','_old'));m['delta']=m.loss_new-m.loss_old
   if len(m):comparisons.append(dict(condition=arm,target=target,new=new,baseline=old,**paired(m)))
 csv('extra/paired_common_coverage_comparisons.csv',comparisons)
 # Overall training-assessed profile differences, summarized within picture conditions.
 cont=pd.read_csv(OUT/'E/continuous_equal_count_compositions.csv');effects=[];imageeffects=[]
 for (arm,axis,n),g in cont.groupby(['condition','axis','n_people']):
  for metric in ['point_count_disagreement','singleton_share','mode_entropy','full_by8','core_by19','core_tail','late_quarter_new','heldout_geometry_coverage']:
   a=g[g.composition.eq('lower')].merge(g[g.composition.eq('higher')],on=['image_id','building'],suffixes=('_lower','_higher'));a['delta']=a[metric+'_lower']-a[metric+'_higher'];a=a.merge(meta[['floor_boundary','scene_category','main_function_primary','doorway']],left_on='image_id',right_index=True)
   for r in a[['image_id','building','floor_boundary','scene_category','main_function_primary','doorway','delta']].to_dict('records'):imageeffects.append(dict(condition=arm,axis=axis,n_people=n,metric=metric,**r))
   for field in ['floor_boundary','scene_category','main_function_primary']:
    for label,q in a.groupby(field,dropna=False):effects.append(dict(condition=arm,axis=axis,n_people=n,metric=metric,field=field,label=label,**paired(q)))
 csv('E/picture_condition_person_effects.csv',effects);csv('E/picture_condition_person_effects_per_image.csv',imageeffects)
 # Descriptive composition interactions with pre-existing trait; no causal or confirmatory interpretation.
 ix=pd.DataFrame(imageeffects);inter=[]
 for (arm,axis,n,metric),g in ix.groupby(['condition','axis','n_people','metric']):
  levels=set(g.floor_boundary.dropna());
  if not {'partial','present'}<=levels:continue
  a=g[g.floor_boundary.isin(['partial','present'])];bs=sorted(a.building.unique());rng=np.random.default_rng(SEED)
  aa=a.groupby(['building','floor_boundary']).delta.agg(['sum','count']).unstack('floor_boundary').reindex(bs).fillna(0)
  v=aa.reindex(columns=pd.MultiIndex.from_tuples([('sum','partial'),('count','partial'),('sum','present'),('count','present')])).fillna(0).to_numpy();chosen=rng.integers(len(bs),size=(1200,len(bs)));tot=v[chosen].sum(1);ok=(tot[:,1]>0)&(tot[:,3]>0);boot=(tot[ok,0]/tot[ok,1]-tot[ok,2]/tot[ok,3]).tolist()
  means=a.groupby('floor_boundary').delta.mean();inter.append(dict(condition=arm,axis=axis,n_people=n,metric=metric,partial_images=int(a.floor_boundary.eq('partial').sum()),visible_images=int(a.floor_boundary.eq('present').sum()),partial_minus_visible=means['partial']-means['present'],lo=np.quantile(boot,.025)if boot else np.nan,hi=np.quantile(boot,.975)if boot else np.nan,buildings=len(bs)))
 csv('E/picture_person_interaction_exploratory.csv',inter)
 # Types: subgroup stability, pooled stability, and differing memberships retained.
 growth=pd.read_csv(OUT/'E/actual_type_growth.csv.gz');merges=[]
 for key,g in growth[growth.requested_groups.eq(2)].groupby(['image_id','condition','building','family']):
  union=g[g.type_id.eq(0)];sub=g[g.type_id.ne(0)]
  if len(union)!=1 or len(sub)!=2 or (sub.n_people<4).any():continue
  u=union.iloc[0];sub=sub.sort_values('type_id');aa,bb=sub.iloc[0],sub.iloc[1];uniform=bool((sub.supported_clusters==1).all());bothcore=bool((sub.core_tail>=.8).all());code='other'
  if bothcore and uniform and u.supported_clusters>=2 and u.core_tail>=.8:code='two_uniform_types_pooled_stable_multimode_candidate'
  elif bothcore and uniform and u.supported_clusters==1 and u.core_tail>=.8:code='two_uniform_types_pooled_uniform'
  elif bothcore and u.supported_clusters>=2 and u.core_tail>=.8:code='subtypes_and_pool_have_supported_multimode'
  elif bothcore and u.core_tail<.8:code='cores_stable_separately_pool_not_stable'
  merges.append(dict(zip(['image_id','condition','building','family'],key),a_workers=aa.workers,b_workers=bb.workers,a_n=aa.n_people,b_n=bb.n_people,a_supported=aa.supported_clusters,b_supported=bb.supported_clusters,pooled_supported=u.supported_clusters,a_core_tail=aa.core_tail,b_core_tail=bb.core_tail,pooled_core_tail=u.core_tail,pooled_late_new=u.late_quarter_new,description=code))
 merges=csv('E/subtypes_to_pooled_growth.csv',merges);csv('E/subtypes_to_pool_summary.csv',merges.groupby(['condition','description']).agg(family_image_rows=('image_id','size'),distinct_images=('image_id','nunique')).reset_index())
 combos=pd.read_csv(OUT/'E/real_combinations_fixed_future2.csv.gz');ex=[]
 for sig in ['AA','AB','AAB','ACD','AABC','ABCD']:
  a=combos[combos.actual_types.eq(sig)if sig=='ACD'else combos.signature.eq(sig)];a=a[a.all_types_training_supported]
  for _,r in a.drop_duplicates(['image_id','condition']).head(4).iterrows():ex.append(dict(requested_pattern=sig,**r.to_dict()))
 csv('E/requested_real_combination_examples.csv',ex)
 # Select review questions by numerical evidence only, not invented visual facts.
 queue=[]
 def add(i,c,why,evidence,question,affected):
  rr,dm,pc,w,ci=pools[i,c];x,cl,_,lab=cluster_static(dm,pc,.1);queue.append(dict(image_id=i,condition=c,scene=meta.loc[i,'scene_category'],main_space=meta.loc[i,'main_function_primary'],trigger=why,numerical_evidence=evidence,canonical_ids=';'.join(ci),workers=';'.join(w),representative_canonical_ids=';'.join(ci[r['medoid_index']]for r in cl),numeric_cluster_sizes=x.get('sizes_descending',''),location='整图；具体争议角点请按canonical叠加定位，未由云端目视确认',question=question,affected_conclusion=affected,user_decision='',user_reason=''))
 for _,r in med.iterrows():
  if r.weak_geometry_separation:add(r.image_id,r.condition,'medium_partition_weak_separation',f'cross-compatible={r.max_cross_compatible_share:.4f}; min sub80={r.min_sub80_jaccard:.4f}','这些同点数数值簇是否表示不同空间范围，还是连续坐标波动被完整链接算法切分？','中等结构候选的语义和聚类可识别性')
 for(i,c),(r,dm,pc,w,ci)in pools.items():
  if c=='oos_geometry':
   q=z[(z.image_id==i)&(z.condition==c)].iloc[0];add(i,c,'recovered_OOS_geometry',f'n={len(w)}; clusters={q.total_clusters}; singleton={q.singletons}; quarter-new={q.late_quarter_new:.4f}','在已有Scope协议下，这些best-effort几何分别尝试表达什么？是否出现协议闭合或表示不适用，而非一般标注困难？','OOS几何解释，不能由数值稳定改写in-scope资格')
 quadr=pd.read_csv(OUT/'B/outside_building_quadrants.csv');quadr['quadrant']='model_'+quadr.model_bucket+'_human_'+quadr.human_bucket;quadr['endpoint']=quadr.target
 if 'quadrant'in quadr:
  for _,r in quadr[quadr.quadrant.isin(['model_low_human_high','model_high_human_low'])&quadr.target.ne('core_tail_10')].sort_values('n_valid',ascending=False).groupby(['condition','endpoint','quadrant']).head(2).iterrows():
   if(r.image_id,r.condition)in pools:add(r.image_id,r.condition,str(r.quadrant),str({k:r[k]for k in r.index if k not in ['image_id','building','condition']}),'模型反馈和人工过程不一致来自可见局部结构、空间范围解释，还是模型后处理偏差？','模型反馈的可解释性反例')
 trans=pd.read_csv(OUT/'D/conditional_predictions_with_neighbors.csv.gz');mixed=trans[(trans.target=='candidate_v2')&(trans.design=='supported_same_room')&(trans.method=='dinov3__block12__panorama_mean')&(trans.room_label_structure=='mixed')]
 for _,r in mixed.iterrows():
  add(r.image_id,r.condition,'same_room_different_candidates',f'neighbor={r.actual_neighbor_id}; true={r.truth}; source prediction={r.prediction}','同房两个视角的主空间、边界可见位置或有效观察人员有什么实质差别？不要把关系相同直接当过程相同。','同房候选迁移的边界')
 q=pd.DataFrame(queue).drop_duplicates(['image_id','condition','trigger']);csv('local_image_review_queue.csv',q)
 js('audit/completion.json',dict(routes=dict(A='executed existing evidence associations, within-scene controls',B='executed three layout feedback and nine recovered OOS inherited feedback',C='executed 155 candidates/combinations, 70 current kernels205;33 inherited OOS candidates9;DINO9 not retrieved',D='executed same-room, cross-building same-scene and same-mainspace, actual neighbors, common-worker views',E='executed16families capacity2..12; real groups2/4; same-person combinations and condition-specific continuous axes'),reviewed_labels='none supplied; no user adjudication invented',visual_revision='none supplied; no new pixels read',old_scores='not renamed; both V1/V2 refitted with stated scoring and L2 kernel processing',new_cloud_tasks=0,old_records_untouched=True,review_rows=len(q),review_distinct_images=q.image_id.nunique(),study_input=INPUT_COMMIT))
 print('SYNTHESIS',len(q),'review questions',q.image_id.nunique(),'images',flush=True)
if __name__=='__main__':run()
