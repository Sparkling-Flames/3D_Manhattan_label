"""Conditional source-history transfer, distinguished from image-only prediction.

Fixed supported room components; same-scene other-building is conservative
cross-room evidence. Same-building is explicitly a diagnostic baseline. No
relation or neighbor is chosen using target outcomes. All neighbor IDs retained.
"""
from __future__ import annotations
import itertools
from tools.thesis_main.analysis.image_portrait.image_links_followup_common import *
from tools.thesis_main.analysis.image_portrait.image_links_followup_predict import GRADE1,GRADE2,CONT
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import cluster_static,one_replay
NNS=['dinov3__block3__panorama_mean','dinov3__block12__panorama_mean','dinov3__cls__panorama','dinov3__block12__faces_global']

def run():
 d=pd.read_csv(OUT/'targets/per_image_versions_and_process.csv');rooms=[r for r in readj(B/'evaluation/room_components.jsonl')if r['status']=='supported_component'];membership={i:r['room_id']for r in rooms for i in r['image_ids']};reg={r['feature']:r for r in readj(V1/'kernels/registry.json')};matrices={}
 for name in NNS:
  z=np.load(V1/'kernels'/reg[name]['file']);matrices[name]=(z['K'],{i:j for j,i in enumerate(z['image_ids'].tolist())})
 records=[];coverage=[]
 for arm,g in d.groupby('condition'):
  for target in ['grade_v1','candidate_v2',*CONT]:
   col='grade_v1'if target=='grade_v1'else 'review_draft_grade'if target=='candidate_v2'else target;mapping=GRADE1 if target=='grade_v1'else GRADE2;cat=target in ['grade_v1','candidate_v2'];q=g[g[col].isin(mapping)].copy()if cat else g.dropna(subset=[col]).copy();q=q.sort_values('image_id').reset_index(drop=True)
   if not len(q):continue
   ids=q.image_id.to_numpy();ys=np.eye(3)[q[col].map(mapping).to_numpy(int)]if cat else q[[col]].to_numpy(float);build=q.building.to_numpy();scenes=q.scene_category.fillna('unknown').to_numpy();main=q.main_function_primary.fillna('unknown').to_numpy()
   for j,row in q.iterrows():
    i=row.image_id;room=membership.get(i);same=np.array([membership.get(x)==room for x in ids])if room else np.zeros(len(q),bool);same[j]=False
    pools={'supported_same_room':np.flatnonzero(same),'same_scene_other_building':np.flatnonzero((build!=build[j])&(scenes==scenes[j])),'same_mainspace_other_building':np.flatnonzero((build!=build[j])&(main==main[j])),'all_other_building':np.flatnonzero(build!=build[j]),'same_building_diagnostic':np.flatnonzero((build==build[j])&(np.arange(len(q))!=j))}
    for design,src in pools.items():
     allroom=np.r_[src,j]if design=='supported_same_room'else np.array([j]);mixed='mixed'if cat and len(np.unique(ys[allroom].argmax(1)))>1 else 'uniform'if cat and design=='supported_same_room'else 'not_categorical_room'
     for method in ['source_frequency_or_median','uniform_random_source_expectation',*NNS]:
      base=dict(image_id=i,building=row.building,condition=arm,target=target,design=design,information='source_history_allowed',method=method,room_id=room or '',room_label_structure=mixed,source_count=len(src),source_ids=';'.join(ids[src]),actual_neighbor_id='',source_distinct_buildings=len(set(build[src])),target_n_valid=row.n_valid,source_min_n_valid=q.n_valid.iloc[src].min()if len(src)else np.nan,source_max_n_valid=q.n_valid.iloc[src].max()if len(src)else np.nan,truth=int(ys[j].argmax())if cat else ys[j,0])
      if not len(src):records.append(dict(base,status='no_eligible_source_history',loss=np.nan));continue
      if design in ['all_other_building','same_scene_other_building','same_mainspace_other_building']:assert np.all(build[src]!=build[j])
      if method=='source_frequency_or_median':p=ys[src].mean(0)if cat else np.median(ys[src],axis=0)
      elif method=='uniform_random_source_expectation':
       # Expected loss of drawing one real source, not a fitted consensus.
       loss=float(np.mean(np.sum((ys[src]-ys[j])**2,axis=1)))if cat else float(np.mean(np.abs(ys[src]-ys[j])));acc=float(np.mean(ys[src].argmax(1)==ys[j].argmax()))if cat else np.nan
       records.append(dict(base,status='ok',loss=loss,correct=acc,prediction=np.nan));continue
      else:
       K,ix=matrices[method];available=np.array([k for k in src if ids[k]in ix],int)
       if i not in ix or not len(available):records.append(dict(base,status='missing_model_array_for_source_or_target',loss=np.nan));continue
       k=available[np.argmax(K[ix[i],[ix[ids[x]]for x in available]])];base['actual_neighbor_id']=ids[k];base['neighbor_cosine']=K[ix[i],ix[ids[k]]];base['source_model_available_count']=len(available);p=ys[k]
      base.update(status='ok',loss=float(np.sum((p-ys[j])**2))if cat else float(np.abs(p-ys[j]).mean()),prediction=int(p.argmax())if cat else p[0])
      if cat:base.update(p_simple=p[0],p_medium=p[1],p_difficult=p[2],correct=float(p.argmax()==ys[j].argmax()),rps=float(np.mean((p.cumsum()[:2]-ys[j].cumsum()[:2])**2)))
      records.append(base)
 out=csv('D/conditional_predictions_with_neighbors.csv.gz',records);csv('D/coverage_and_failures.csv',out.groupby(['condition','target','design','method','status']).size().reset_index(name='target_images'));scores=[];pairs=[]
 for key,g in out.groupby(['condition','target','design','method']):
  for subset in ['all_available','mixed_room','uniform_room']:
   a=g.dropna(subset=['loss']);a=a[a.room_label_structure.eq('mixed'if subset=='mixed_room'else 'uniform')]if subset!='all_available'else a
   if not len(a):continue
   scores.append(dict(zip(['condition','target','design','method'],key),subset=subset,images=len(a),buildings=a.building.nunique(),components=a.room_id.nunique(),image_loss=a.loss.mean(),building_macro_loss=a.groupby('building').loss.mean().mean(),accuracy=a.correct.mean()if 'correct'in a else np.nan))
 for key,g in out.groupby(['condition','target','design']):
  baseline=g[g.method.eq('source_frequency_or_median')]
  for method in NNS:
   z=g[g.method.eq(method)].merge(baseline,on=['image_id','building'],suffixes=('_new','_base'));z['delta']=z.loss_new-z.loss_base
   for subset in ['all_available','mixed_room']:
    a=z if subset=='all_available'else z[z.room_label_structure_new.eq('mixed')]
    if a.delta.notna().any():pairs.append(dict(zip(['condition','target','design'],key),method=method,subset=subset,**paired(a)))
 csv('D/conditional_summary.csv',scores);csv('D/conditional_paired_increment.csv',pairs)
 # Conditional and pure-image methods differ in both sources and inputs: paired
 # loss is descriptive, never a randomized marginal view effect.
 pp=pd.read_csv(OUT/'prediction/all_predictions.csv.gz');pp=pp[pp.algorithm.isin(['ridge','baseline'])&pp.feature.isin(['constant','scene_frequency','feedback_counts','feedback_all','selected_dino'])];compare=[]
 for key,g in out[(out.design=='supported_same_room')&out.method.isin(['source_frequency_or_median','dinov3__block12__panorama_mean'])].groupby(['condition','target','method']):
  for feat,h in pp[(pp.condition==key[0])&(pp.target==key[1])].groupby('feature'):
   z=g.merge(h,on=['image_id','building'],suffixes=('_source','_image'));z['delta']=z.loss_source-z.loss_image
   if z.delta.notna().any():compare.append(dict(condition=key[0],target=key[1],method=key[2],pure_image_feature=feat,**paired(z)))
 csv('D/source_history_vs_image_only_common_coverage.csv',compare)
 js('D/method.json',dict(same_room='fixed supported components excluding entire ambiguous overlaps',cross_room='same semantic scene/mainspace in other building; not same-building assumed similarity',same_building='diagnostic only, not independent-room evidence',neighbor_selection='fixed per-image L2 similarity; no outcomes used to choose neighbor, actual ID retained',categorical_probability='source empirical frequency and NN one-hot, no unequal smoothing',uniform_sources='expected loss of choosing a uniformly random real source',reviewed_labels='not provided; algorithm candidates only',no_physical_DA3_correspondence=True,ordered_layers=NNS))
 common_people(rooms,d)
 print('TRANSFER',len(out),'rows',len(scores),'scores',flush=True)

def common_people(rooms,d):
 pools=groups();records=[]
 for room in rooms:
  for arm in ['manual','semi','oos_geometry']:
   ids=[i for i in room['image_ids']if(i,arm)in pools]
   for a,b in itertools.combinations(ids,2):
    r,da,pa,wa,ca=pools[a,arm];s,db,pb,wb,cb=pools[b,arm];common=sorted(set(wa)&set(wb));pair=a+'|'+b
    if len(common)<2:continue
    st=[];cids=[]
    for i,dm,pc,w,cid in [(a,da,pa,wa,ca),(b,db,pb,wb,cb)]:
     ix=np.array([list(w).index(x)for x in common]);x=cluster_static(dm[np.ix_(ix,ix)],pc[ix],.1)[0]
     if len(common)>=4:
      ss,_,_=one_replay(dm[np.ix_(ix,ix)],pc[ix],.1,80,pair,arm,False);rr=pd.DataFrame(ss);x.update(full_by8=np.mean(rr.full_onset_no_gate<=8),core_by19=np.mean(rr.core_onset_10<=19),core_tail=rr.core_tail_10.mean(),late_quarter_new=rr.late_quarter_new.mean())
     st.append(x);cids.append(';'.join(cid[ix]))
    row=dict(image_a=a,image_b=b,condition=arm,building=a.split('_')[0],room_id=room['room_id'],common_n=len(common),common_workers=';'.join(common),canonical_ids_a=cids[0],canonical_ids_b=cids[1],orders=80 if len(common)>=4 else 0)
    for col in ['total_clusters','supported_clusters','singletons','singleton_share','point_count_disagreement','within_cluster_median','full_by8','core_by19','core_tail','late_quarter_new']:
     row[col+'_a']=st[0].get(col,np.nan);row[col+'_b']=st[1].get(col,np.nan);row[col+'_absolute_difference']=abs(row[col+'_a']-row[col+'_b'])
    records.append(row)
 c=csv('D/exact_common_people_across_views.csv',records);rows=[]
 for arm,g in c[c.common_n>=4].groupby('condition'):
  for col in [x for x in c if x.endswith('_absolute_difference')]:
   q=g.dropna(subset=[col]);rows.append(dict(condition=arm,metric=col,paired_views=len(q),components=q.room_id.nunique(),mean_absolute_difference=q[col].mean(),nonzero_pairs=int((q[col]>1e-12).sum())))
 csv('D/exact_common_people_summary.csv',rows)
if __name__=='__main__':run()
