"""Strict image-only process prediction. No target valid-person count as input.
Previous known-horizon analyses remain saved and explicitly conditional; actual
valid n is not automatically available before annotations have been inspected.
"""
import concurrent.futures,json
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *
from tools.thesis_main.analysis.image_portrait import convergence_v2_prediction as cp
NAMES=['scene','scene_AI','model_points','model_feedback','C_hohonet_shared_global','C_da3_layer11_global','points_plus_shared']

def strict_writer(path, values):
 p=OUT/'strict_cold'/path;p.parent.mkdir(parents=True,exist_ok=True);d=values if isinstance(values,pd.DataFrame)else pd.DataFrame(values);d.to_csv(p,index=False,float_format='%.12g');return d

def run_one(name):
 t=pd.read_csv(OUT/'prediction/process_targets.csv')
 with np.load(OUT/'prediction/portrait_matrices'/(name+'.npz'),allow_pickle=False)as z:ids=z['image_ids'].tolist();x=z['X']
 cp.OUT=OUT/'strict_cold';cp.csv=strict_writer
 cp.evaluate_family(name,x,ids,t,include_horizon=False)

def finish():
 fs=[pd.read_csv(OUT/'strict_cold/prediction/cold'/(n+'.csv.gz'))for n in NAMES];d=pd.concat(fs,ignore_index=True);d=d[~(d.algorithm.isin(['constant','same_scene'])&(d.feature!='scene'))];csv('strict_cold/predictions.csv.gz',d)
 summ=[]
 for key,g in d.groupby(['feature','algorithm','condition','target']):summ.append(dict(feature=key[0],algorithm=key[1],condition=key[2],target=key[3],n=len(g),buildings=g.building.nunique(),MAE=g.absolute_error.mean(),building_macro_MAE=g.groupby('building').absolute_error.mean().mean()))
 csv('strict_cold/score_summary.csv',summ);rows=[]
 for (arm,target),g in d.groupby(['condition','target']):
  for bn,b in [('constant',g[(g.feature=='scene')&(g.algorithm=='constant')]),('model_points',g[(g.feature=='model_points')&(g.algorithm=='ridge')]),('scene',g[(g.feature=='scene')&(g.algorithm=='ridge')])]:
   for name,a in g[g.algorithm=='ridge'].groupby('feature'):
    if name==bn:continue
    z=a[['image_id','building','absolute_error']].merge(b[['image_id','absolute_error']],on='image_id',suffixes=('','_base'));z['delta']=z.absolute_error-z.absolute_error_base;rows.append(dict(condition=arm,target=target,feature=name,baseline=bn,method_MAE=z.absolute_error.mean(),baseline_MAE=z.absolute_error_base.mean(),**paired_interval(z,'delta')))
 csv('strict_cold/paired_increments.csv',rows)
 js('strict_cold/method.json',dict(no_target_annotations=True,no_actual_valid_n_predictor=True,no_target_person_scores=True,targets='Versioned finite-process outcomes at each image actual n; endpoint evaluation still depends on observed horizon.',fixed_features=NAMES,selection='same original25 building folds, inner21 scaler/PCA/Ridge/KNN grid',not_selected_by_current_outer_scores=True,relation_to_prior='The earlier prediction/ analysis conditions on actual valid n; it is NOT strictly image-only. Keep both, never silently substitute.',followup_not_fresh_confirmation=True))

if __name__=='__main__':
 with concurrent.futures.ProcessPoolExecutor(max_workers=3)as ex:list(ex.map(run_one,NAMES))
 finish();print('STRICT COLD DONE',flush=True)
