"""Connect portraits to uncertainty processes, not to an efficiency objective.

All targets are versioned finite-observation process quantities. Uses original
fixed building folds; internal scaler/PCA/parameters/layer choice train only.
These are follow-up analyses on previously seen data, NOT fresh validation.
"""
import argparse,collections,itertools,json,time
from pathlib import Path
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *
from tools.thesis_main.analysis.image_portrait.pro_predict import numeric_grid,CONFIGS

TARGETS=['stable_P','stable_D10','stable_G10','stable_multimode_G10','supported_multimodal','same_point_multimodal','late_novel_geometry_rate','late_support_promotions_rate','half_TV','half_future_uncovered','medoid_reference_abs_change']

def make_targets():
 st=pd.read_csv(OUT/'process/image_uncertainty_structure.csv');z=pd.read_csv(OUT/'process/image_state_probabilities.csv');cur=pd.read_csv(OUT/'process/image_growth_curves.csv.gz');rep=pd.read_csv(OUT/'process/replay_states.csv.gz');rows=[]
 for (image,arm,cut),g in st.groupby(['image_id','condition','cut']):
  r=g.iloc[0];meta=r.to_dict();meta['horizon']=r.n_valid
  a=z[(z.image_id==image)&(z.condition==arm)&(z.cut==cut)];c=cur[(cur.image_id==image)&(cur.condition==arm)&(cur.cut==cut)]
  for rule,name in [('P_pattern','stable_P'),('D10_distribution','stable_D10'),('G10_geometry','stable_G10')]:
   u=a[a.rule==rule];known=u[~u.state.str.startswith('cannot')].fraction.sum()
   meta[name]=u[u.state.isin(['observed_unified','stable_multicluster'])].fraction.sum() if known>0 else np.nan
   if rule=='G10_geometry':meta['stable_multimode_G10']=u[u.state=='stable_multicluster'].fraction.sum() if known>0 else np.nan
  meta['supported_multimodal']=float(r.n_supported_modes>=2) if r.n_valid>=2 else np.nan
  meta['same_point_multimodal']=float(r.same_topology_multimodality) if r.n_valid>=2 else np.nan
  if len(c) and r.n_valid>=4:
   half=max(2,int(np.ceil(r.n_valid/2)));mid=c[c.k==half].iloc[0];last=c[c.k==r.n_valid].iloc[0]
   u=rep[(rep.image_id==image)&(rep.condition==arm)&(rep.cut==cut)&(rep.rule=='P_pattern')];w=min(3,int(r.n_valid)-2)
   meta.update(late_novel_geometry_rate=u.late_new_geometry.mean()/w,late_support_promotions_rate=u.late_support_promotions.mean()/w,half_TV=mid.TV_full_observed,half_future_uncovered=1-mid.future_coverage,medoid_reference_abs_change=abs(last.largest_mode_medoid_reference_error-mid.largest_mode_medoid_reference_error))
  rows.append(meta)
 return csv('prediction/process_targets.csv',rows)

def matrices(t):
 ids=sorted(t.image_id.unique());n=len(ids);index={i:j for j,i in enumerate(ids)};fields=pd.read_csv(OUT/'images/evidence_layers.csv').set_index('image_id').reindex(ids);traits=pd.read_csv(FOUND/'A/interpretable_inputs.csv').set_index('image_id').reindex(ids);b=pd.read_csv(FOUND/'B/model_feedback.csv').set_index('image_id').reindex(ids)
 scene=pd.get_dummies(fields[['scene_human_adopted']].fillna('unknown'),dtype=float).to_numpy();ai=pd.get_dummies(traits[['floor_boundary','ceiling_boundary','connected_space','reflection_glass','low_contrast']].fillna('unknown'),dtype=float).to_numpy()
 bc=[c for c in b if c!='building' and c!='hohonet_raw_vs_exported_boundary_max_pixel_difference'];bx=b[bc].to_numpy(float);pc=b[['hohonet_point_count_mean','bi_enclosed_point_count_mean','bi_extended_point_count_mean']].to_numpy(float)
 feats={'N_only':np.empty((n,0)),'scene':scene,'scene_AI':np.column_stack([scene,ai]),'model_points':pc,'model_feedback':bx,'scene_feedback':np.column_stack([scene,bx])}
 cands=['C_hohonet_encoder_stage2_global','C_hohonet_encoder_stage4_global','C_hohonet_shared_global','C_hohonet_shared_local16','C_bilayout_fc_global','C_bilayout_fg_enclosed_global','C_bilayout_fg_extended_global','C_ulayout_compressed_global','C_ulayout_transformer_global','C_da3_layer5_global','C_da3_layer7_global','C_da3_layer9_global','C_da3_layer11_global']
 for name in cands:
  p=FOUND/'features'/(name+'.npz')
  if not p.exists():continue
  with np.load(p,allow_pickle=False) as a:
   im={i:j for j,i in enumerate(a['image_ids'].tolist())};feats[name]=a['X'][[im[i] for i in ids]]
 shared=feats['C_hohonet_shared_global'];feats['points_plus_shared']=np.column_stack([pc,shared]);feats['scene_feedback_shared']=np.column_stack([scene,bx,shared]);feats['scene_points']=np.column_stack([scene,pc])
 # Saved matrices are numeric derived inputs, and will be included in the ZIP.
 for name,x in feats.items():
  p=OUT/'prediction/portrait_matrices'/(name+'.npz');p.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(p,image_ids=np.asarray(ids),X=np.asarray(x,np.float32))
 js('prediction/portrait_matrix_schema.json',dict(image_ids=ids,features={name:dict(columns=x.shape[1],horizon_added_per_condition=True)for name,x in feats.items()},human_scene_provenance='spatial_classification.coarse_type plus spatial_field_sources; distinct from current_coarse and AI traits',no_observed_target_annotation_features=True))
 return ids,feats

def evaluate_family(name,X,ids,t,cut=.1,include_horizon=True):
 path=OUT/f'prediction/cold/{name}.csv.gz';innerpath=OUT/f'prediction/cold/{name}.inner.csv.gz'
 if path.exists() and innerpath.exists():return
 start=time.time();ix={i:j for j,i in enumerate(ids)};rows=[];innerrows=[];coverage=[];folds=[f for f in core.load(BUNDLE/'evaluation/folds.jsonl.gz') if f['design']=='leave_building']
 for arm,allg in t[t.cut==cut].groupby('condition'):
  patterns=collections.defaultdict(list)
  for target in TARGETS:patterns[tuple(allg[target].notna())].append(target)
  for mask,targets in patterns.items():
   q=allg[np.asarray(mask)].sort_values('image_id').reset_index(drop=True)
   if len(q)<3:continue
   x=np.column_stack([q.horizon.to_numpy(float),X[[ix[i]for i in q.image_id]]]) if include_horizon else X[[ix[i]for i in q.image_id]].astype(float);y=q[targets].to_numpy(float);buildings=q.building.to_numpy();good=np.isfinite(x).all(1);q=q[good].reset_index(drop=True);x=x[good];y=y[good];buildings=buildings[good];bs=sorted(set(buildings));cache={}
   for f in folds:
    test=np.flatnonzero(q.image_id.isin(f['test']).to_numpy());train=np.flatnonzero(q.image_id.isin(f['train']).to_numpy());b=f['fold_id'].split(':',1)[1]
    if not len(test):continue
    coverage.append(dict(feature=name,condition=arm,targets=';'.join(targets),fold_id=f['fold_id'],n_train=len(train),n_test=len(test),n_missing_predictors=int((~good).sum())))
    if not len(train):continue
    innererr=np.zeros((len(CONFIGS),len(targets)));den=0
    for vb in sorted(set(buildings[train])):
     keep=np.flatnonzero((buildings!=b)&(buildings!=vb));valid=np.flatnonzero(buildings==vb)
     if len(keep)<2 or not len(valid):continue
     key=tuple(sorted([b,vb]));kv=(key,vb)
     if kv not in cache:
      pred,_=numeric_grid(x,y,keep,valid,targets);cache[kv]=np.abs(pred-y[valid][None]).sum(1)
     innererr+=cache[kv];den+=len(valid)
    outer,_=numeric_grid(x,y,train,test,targets)
    if den:innererr/=den
    for j,target in enumerate(targets):
     for alg in ['ridge','knn']:
      ci=[k for k,c in enumerate(CONFIGS) if c['algorithm']==alg]
      best=min(ci,key=lambda k:(innererr[k,j],CONFIGS[k]['pca'] is not None,CONFIGS[k]['pca'] or 0,-CONFIGS[k]['parameter'] if alg=='ridge' else CONFIGS[k]['parameter'])) if den else ci[0]
      cfg=CONFIGS[best];innerrows.append(dict(feature=name,condition=arm,target=target,fold_id=f['fold_id'],algorithm=alg,selected_pca=cfg['pca'],selected_parameter=cfg['parameter'],inner_MAE=innererr[best,j] if den else np.nan,n_inner_images=den))
      for pos,k in enumerate(test):
       rows.append(dict(feature=name,condition=arm,cut=cut,target=target,fold_id=f['fold_id'],image_id=q.image_id.iloc[k],building=buildings[k],horizon=q.horizon.iloc[k],algorithm=alg,truth=y[k,j],prediction=outer[best,pos,j],absolute_error=abs(y[k,j]-outer[best,pos,j]),n_train=len(train),n_test=len(test),selected_pca=cfg['pca'],selected_parameter=cfg['parameter']))
     for base in ['constant','same_scene']:
      # This loop below handles each target image separately, including unseen scenes.
      for pos,k in enumerate(test):
       ss=train[q.scene.iloc[train].to_numpy()==q.scene.iloc[k]] if base=='same_scene' else train
       fallback=not len(ss);ss=ss if len(ss) else train;p=float(np.median(y[ss,j]));rows.append(dict(feature=name,condition=arm,cut=cut,target=target,fold_id=f['fold_id'],image_id=q.image_id.iloc[k],building=buildings[k],horizon=q.horizon.iloc[k],algorithm=base,truth=y[k,j],prediction=p,absolute_error=abs(y[k,j]-p),n_train=len(train),n_test=len(test),scene_fallback=fallback))
 csv(f'prediction/cold/{name}.csv.gz',rows);csv(f'prediction/cold/{name}.inner.csv.gz',innerrows);csv(f'prediction/cold/{name}.coverage.csv',coverage);print('COLD',name,'rows',len(rows),'seconds',round(time.time()-start,1),flush=True)

def combine():
 files=list((OUT/'prediction/cold').glob('*.csv.gz'));frames=[pd.read_csv(p)for p in files if '.inner.' not in p.name]
 a=pd.concat(frames,ignore_index=True);a=a[~(a.algorithm.isin(['constant','same_scene'])&(a.feature!='N_only'))]
 inn=pd.concat([pd.read_csv(p)for p in files if '.inner.' in p.name],ignore_index=True)
 # Layer selection uses INNER scores in the corresponding OUTER training fold.
 c=inn[inn.feature.str.startswith('C_')];selected=c.sort_values(['inner_MAE','feature']).groupby(['condition','target','fold_id','algorithm']).first().reset_index()
 rows=[]
 for r in selected.to_dict('records'):
  g=a[(a.condition==r['condition'])&(a.target==r['target'])&(a.fold_id==r['fold_id'])&(a.algorithm==r['algorithm'])&(a.feature==r['feature'])].copy();g['selected_layer']=r['feature'];g['feature']='C_training_selected';rows.append(g)
 if rows:a=pd.concat([a,*rows],ignore_index=True)
 csv('prediction/cold_all_predictions.csv.gz',a);csv('prediction/cold_training_layer_selection.csv',selected)
 summaries=[]
 for keys,g in a.groupby(['feature','algorithm','condition','target']):
  summaries.append(dict(zip(['feature','algorithm','condition','target'],keys),images=len(g),buildings=g.building.nunique(),image_MAE=g.absolute_error.mean(),building_macro_MAE=g.groupby('building').absolute_error.mean().mean()))
 csv('prediction/cold_score_summary.csv',summaries)
 comparisons=[]
 for condition in a.condition.unique():
  for target in a.target.unique():
   z=a[(a.condition==condition)&(a.target==target)];baselines=[('constant',z[(z.feature=='N_only')&(z.algorithm=='constant')]),('N_only',z[(z.feature=='N_only')&(z.algorithm=='ridge')]),('model_points',z[(z.feature=='model_points')&(z.algorithm=='ridge')]),('model_feedback',z[(z.feature=='model_feedback')&(z.algorithm=='ridge')])]
   for name,g in z[z.algorithm=='ridge'].groupby('feature'):
    for bn,b in baselines:
     if name==bn:continue
     m=g[['image_id','building','absolute_error']].merge(b[['image_id','absolute_error']],on='image_id',suffixes=('','_base'));m['delta']=m.absolute_error-m.absolute_error_base
     comparisons.append(dict(feature=name,baseline=bn,condition=condition,target=target,method_MAE=m.absolute_error.mean(),baseline_MAE=m.absolute_error_base.mean(),**paired_interval(m,'delta')))
 csv('prediction/cold_paired_increments.csv',comparisons)
 js('prediction/method.json',dict(folds='original25 leave-building; conservative-room scores are subsets of identical building exclusions',horizon='actual observed valid-person n is declared evaluation horizon, not image-derived difficulty; horizon-only baseline mandatory',target_labels='process_targets.csv, exploratory definitions only',training_selection='all21 existing scaler/PCA/ridge/KNN candidates inner leave-building; fixed layers AND inner-layer selector retained',source_split_warning='visual model train membership unknown; no external-visual-model claim',validation_status='follow-up on already viewed data, not independent confirmation',prediction_scope='no target annotation coordinates read in cold prediction; horizon known as design parameter',unknown_states='not silently labeled as non-convergence; stable probability targets missing when judgment blocked'))

def main():
 t=make_targets();ids,feats=matrices(t)
 for name,x in feats.items():evaluate_family(name,x,ids,t)
 combine()
if __name__=='__main__':main()
