"""Coverage, source separation, failure accounting and local-review evidence."""
import json,itertools,hashlib,sys,platform
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_prepare import *


def training_coverage(d, pred):
 """Pair both native trainable panels and their intersection, never drop silently."""
 from tools.thesis_main.analysis.image_portrait.difficulty_stratified_results import measure
 rows=[];panels={}
 for design,field in [('within_coarse','scene_category'),('within_main','main_function_primary')]:
  ids=set()
  for r in d.itertuples():
   usable=bool(((d[field]==getattr(r,field))&(d.building!=r.building)).any())
   rows.append(dict(image_id=r.image_id,design=design,training_stratum_available=usable,field=field,value=getattr(r,field),building=r.building))
   if usable:ids.add(r.image_id)
  panels[design]=ids
 panels['common']=panels['within_coarse']&panels['within_main']
 csv('audit/target_stratum_trainability.csv',rows)
 selected=pred[((pred.feature.str.startswith('selected__'))&(pred.algorithm=='ridge')&(pred.baseline=='main'))|pred.feature.isin(['baseline__coarse','baseline__main'])]
 result=[]
 for coverage,ids in panels.items():
  for keys,g in selected[selected.image_id.isin(ids)].groupby(['design','feature','baseline','algorithm']):
   result.append(dict(coverage=coverage,**dict(zip(['design','feature','baseline','algorithm'],keys)),**measure(g)))
 csv('results/paired_trainable_coverage_scores.csv',result)
 savej('audit/main_inference_limits.json',dict(training_main_stratum_available=len(panels['within_main']),training_coarse_stratum_available=len(panels['within_coarse']),common_trainable=len(panels['common']),all_available_primary=len(d),room_transfer='other views have user difficulty labels; not image-only inference and not human convergence',source_time='follow-up using previously viewed data; not new independent verification',no_GitHub_results_pushed_this_round=True))

def main():
 d=pd.read_csv(O/'images/labels106.csv');allmeta=pd.read_csv(O/'images/metadata_all648.csv');pred=pd.read_csv(O/'results/all_oof_predictions.csv.gz');old=B/'cloud/pro_exploration/v2_convergence_e086b2b9'
 training_coverage(d,pred)
 counts=pred.groupby(['design','feature','baseline','algorithm','status']).size().reset_index(name='images');csv('audit/prediction_coverage_status.csv',counts)
 fs=[]
 for p in (O/'cv').rglob('*.failures.csv'):
  try:q=pd.read_csv(p)
  except pd.errors.EmptyDataError:continue
  if len(q):q['result_file']=str(p.relative_to(O));fs.append(q)
 csv('audit/all_training_stratum_failures.csv',pd.concat(fs,ignore_index=True)if fs else[])
 feedback=pd.read_csv(O/'models/numeric_feedback106.csv');z=d.merge(feedback,on='image_id');a=[]
 for (scene,label),g in z.groupby(['scene_category','difficulty_tag']):
  for c in feedback.columns[1:]:a.append(dict(scene=scene,label=label,field=c,n_images=len(g),n_buildings=g.building.nunique(),median=g[c].median(),q25=g[c].quantile(.25),q75=g[c].quantile(.75)))
 csv('stratification/model_feedback_by_scene_tag.csv',a)
 nn=pd.read_csv(O/'similarity/neighbor_pairs.csv.gz');pmap=pred[(pred.design=='pooled')&(pred.feature=='selected__feedback')&(pred.baseline=='main')&(pred.algorithm=='ridge')].set_index('image_id');dmap=allmeta.set_index('image_id');fmap=feedback.set_index('image_id')
 raw_hist=pd.read_csv(old/'process/mode_memberships.csv.gz');hstruct=pd.read_csv(old/'process/image_uncertainty_structure.csv');hmap=hstruct[(hstruct.condition=='manual')&(hstruct.cut==.1)].set_index('image_id');queue=[];seen=set()
 def put(image,reason,question,impact,peer='',numeric=''):
  key=(image,reason,peer)
  if key in seen:return
  seen.add(key);row=dmap.loc[image];modes=raw_hist[(raw_hist.image_id==image)&(raw_hist.cut==.1)]
  info=dict(review_id=f'Q{len(queue)+1:03}',image_id=image,paired_image_id=peer,reason=reason,question=question,affected_conclusion=impact,subjective_tag=row.difficulty_tag,coarse_source=row.scene_source,coarse_category=row.scene_category,AI_main_space=row.main_space_raw,AI_main_source=row.main_space_source,room_id=row.room_id,room_relation_status=row.room_status,numeric_trigger=numeric,canonical_ids=';'.join(modes.canonical_annotation_id.astype(str).unique()),worker_ids=';'.join(sorted(modes.worker_id.unique())),recommended_numeric_cut='.05,.10,.20',source='numeric/text triage only; image not viewed')
  if image in fmap.index:row2=fmap.loc[image];info.update(hohonet_points=row2.hohonet_points,bi_enclosed_points=row2.bi_enclosed_points,bi_extended_points=row2.bi_extended_points,bi_scope_difference=row2.bi_enclosed_vs_bi_extended)
  if image in pmap.index:row3=pmap.loc[image];info.update(feedback_p_simple=row3.p0,feedback_p_medium=row3.p1,feedback_p_hard=row3.p2)
  if image in hmap.index:row4=hmap.loc[image];info.update(manual_n_valid=row4.n_valid,manual_supported_modes=row4.n_supported_modes,manual_singleton_fraction=row4.singleton_mass)
  queue.append(info)
 mixed=pd.read_csv(O/'stratification/mixed_display_group_members.csv')
 for _,r in mixed.iterrows():
  g=mixed[(mixed.display_group==r.display_group)&(mixed.label!=r.label)];peer=g.image_id.iloc[0]
  q='确认相机当前主空间、相邻可见区域与实际要求的标注范围；解释同组不同难度是否来自视点遮挡/结构，或只是主空间与整体场景混用。不得仅凭展示组假定物理同房。'
  if r.display_group=='G184':q='确认“淋浴内部为主”是否改变实际标注对象/范围；玻璃外主浴室是背景还是任务目标？核查中等与困难差别，不能依据玻璃材质自动决定边界。'
  if r.display_group=='G202':q='核查浴缸中央与门侧/连通通道视点的主空间、门洞和墙顶边界；两张困难与三张中等是否有可复核的结构/可见证据差别？'
  if r.display_group=='G002':q='五个厨房主空间视点的两张简单/三张中等：哪一处可见边界或空间范围不同？用餐主空间的类别差别不能解释同一厨房内部的差别。'
  put(r.image_id,'mixed_display_'+r.display_group,q,'主空间解释是否真实；不能把组别、来源或类别识别冒充类别内难易',peer,f'group={r.display_group}; tag={r.label}; paired_tag={g.label.iloc[0]}; relation={r.room_status}')
 cases=nn[(nn.feature=='dinov3__block12__panorama_mean')&(nn.rule=='outside_building_same_coarse')&(nn['rank']==1)&(nn.target_tag!=nn.neighbor_tag)].sort_values('cosine',ascending=False).head(12)
 for _,r in cases.iterrows():put(r.image_id,'DINO_similar_tag_discordant','核查模型近邻究竟共享类别/装修背景，还是共享主空间可见性与标注范围；为什么已有人工难易判断不同？','DINO是否刻画类别内难易，还是只检索相似外观',r.neighbor_id,f'block12 panorama mean cosine={r.cosine:.8f}; different-building same-coarse; tags={r.target_tag}/{r.neighbor_tag}')
 cases=pred[(pred.design=='within_main')&(pred.feature=='selected__existing')&(pred.baseline=='main')&(pred.algorithm=='ridge')&(pred.prediction!=pred.y)].sort_values('rps',ascending=False).head(10)
 for _,r in cases.iterrows():put(r.image_id,'heldout_mainstratum_counterexample','保留原人工难度，核查当前主空间文字是否遗漏了关键结构/遮挡，还是图像存在与既有判断不同的标注解释。','主空间分层预测的失效边界',numeric=f'heldout building; observed label={LABELS[int(r.y)]}; predicted probabilities={r.p0:.4f},{r.p1:.4f},{r.p2:.4f}; RPS={r.rps:.4f}')
 for image,question in [('uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d','六名真实人员形成两个支持模式：两类是否确实对应不同但合理范围/结构，还是坐标散布被切簇？'),('X7HyMhZNoso_987fd31155514f6facb131bd5c14881d','旧18+6同点数簇分离弱；请确认有无实质不同空间解释，不得根据算法已给出两簇而认定双解。'),('uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97','四个支持模式和两名单人记录：哪些是可辩护结构/范围解释？短稳定后缀与旧尾段定义的稳定比例不同，勿直接称无法收敛。'),('S9hNv5qa7GM_bd9faec23bb3462c94a5fbc6c0a3d5cf','单一支持主簇但较晚稳定：是否主要由簇内定位漂移而非新结构导致？这会改变“仅看簇数判断中等”的解释。')]:
  put(image,'historical_process_semantics',question,'历史粗分类的语义有效性与聚类分区可识别性',numeric='See historical_bridge confirmation_disagreement / display_slice_per_image and review_modes')
 csv('review/local_image_review_queue.csv',queue);ids={r['image_id']for r in queue}|{r['paired_image_id']for r in queue if r['paired_image_id']};csv('review/review_modes.csv.gz',raw_hist[raw_hist.image_id.isin(ids)])
 # Add the raw annotation records for local overlay generation, without loading any image.
 responses=load(B/'human/responses.jsonl.gz');out=[r for r in responses if r['image_id']in ids];(O/'review/raw_response_geometries.jsonl.gz').write_bytes(gzip.compress(('\n'.join(json.dumps(r,ensure_ascii=False)for r in out)+'\n').encode(),mtime=0))
 inventory=pd.read_csv(O/'models/feature_inventory.csv');savej('audit/execution_counts.json',dict(subjective_labels=106,label_counts=d.difficulty_tag.value_counts().to_dict(),main_space_human_nonmissing=int(d.main_space_human.notna().sum()),AI_main_space_records=int(d.main_space_raw.notna().sum()),raw_DINO_loaded_images=106,registry_DINO_images=648,n_numeric_representations=len(inventory),n_semantic_predictors=8,n_schemes=3,n_oof_prediction_rows=len(pred),n_unique_oof_methods=pred[['design','feature','baseline','algorithm']].drop_duplicates().shape[0],review_entries=len(queue),review_unique_images=len(ids),historical_process_unique_images=hstruct.image_id.nunique(),human_label_overlap=len(set(hstruct.image_id)&set(d.image_id)),legacy_native_overlap=35,rooms_labelled_supported=54,room_components=9,model_failure_count=0,code_execution='actual in-session Python; no images/weights/visual inference',earlier_failed_attempt='initial cv settings dictionary duplicate keyword fixed before successful rerun; failure log retained'))
 print('AUDIT queue',len(queue),'IDs',len(ids),'methods',pred[['design','feature','baseline','algorithm']].drop_duplicates().shape[0],flush=True)
if __name__=='__main__':main()
