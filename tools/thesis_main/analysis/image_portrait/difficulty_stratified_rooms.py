"""Fixed supported-room leave-view TAG transfer, not convergence prediction."""
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_cv import *
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_results import measure,paired

def main():
 d=pd.read_csv(O/'images/labels106.csv');by={s:i for i,s in enumerate(d.image_id)};folds=load(B/'evaluation/folds.jsonl.gz');records=[];fail=[];audit=[]
 models=['dinov3__block3__panorama_mean','dinov3__block12__panorama_mean','dinov3__cls__panorama','feedback__point_counts'];xs={n:np.load(O/'cache'/f'{n}.npy').astype(float)for n in models}
 for f in folds:
  tr=np.array([by[s]for s in f['train']if s in by],int);te=np.array([by[s]for s in f['test']if s in by],int);audit.append(dict(fold_id=f['fold_id'],design=f['design'],n_train_tagged=len(tr),n_test_tagged=len(te),train_labels=np.bincount(d.y.to_numpy(int)[tr],minlength=3).tolist(),test_labels=np.bincount(d.y.to_numpy(int)[te],minlength=3).tolist()))
  if f['design']!='same_room_leave_view' or not len(te):continue
  if not len(tr):
   fail.append(dict(fold_id=f['fold_id'],image_id=d.image_id.iloc[te[0]],reason='no other labelled view in eligible supported component'));continue
  p=cat_probs(d,tr,te,'global');pred={'same_room_frequency':p}
  for name,X in xs.items():
   if name.startswith('dinov3'):
    a=X[tr]/np.maximum(np.linalg.norm(X[tr],axis=1,keepdims=True),1e-12);v=X[te]/np.maximum(np.linalg.norm(X[te],axis=1,keepdims=True),1e-12);jj=np.argmax(v@a.T,axis=1);pred[name+'__nn1']=prob(np.eye(3)[d.y.to_numpy(int)[tr[jj]]])
   else:
    q=grids(X,d,tr,te,modes=['global']);j=next(j for j,g in enumerate(GRID)if g['algorithm']=='ridge'and g['pca']==0 and g['alpha']==10);pred[name+'__fixed_ridge']=q[0,j]
  for name,pp in pred.items():
   for i,x in zip(te,pp):records.append(dict(image_id=d.image_id.iloc[i],building=d.building.iloc[i],room_id=f['room_id'],scene=d.scene_category.iloc[i],main_space=d.main_function_primary.iloc[i],y=int(d.y.iloc[i]),feature=name,baseline='same_room_history',algorithm='fixed',design='fixed_same_room_leave_view',p0=x[0],p1=x[1],p2=x[2],prediction=int(x.argmax()),rps=float(rps(x,int(d.y.iloc[i]))),brier=float(brier(x,int(d.y.iloc[i]))),n_history_views=len(tr),training_image_ids=';'.join(d.image_id.iloc[tr]),status='ok'))
 q=csv('rooms/same_room_tag_predictions.csv',records);csv('rooms/failures.csv',fail);csv('audit/fixed_fold_label_intersections.csv',audit)
 sc=[]
 for name,g in q.groupby('feature'):sc.append(dict(feature=name,**measure(g),n_components=g.room_id.nunique(),component_macro_rps=g.groupby('room_id').rps.mean().mean()))
 csv('rooms/same_room_tag_scores.csv',sc)
 outer=pd.read_csv(O/'cv/baselines.csv');pairs=[];a=q[q.feature=='same_room_frequency']
 for name in ['baseline__global','baseline__coarse','baseline__main']:pairs.append(paired(a,outer[outer.feature==name],'same-room tag history vs '+name+' outside building'))
 for name in models:
  b=q[q.feature.str.startswith(name)];pairs.append(paired(b,a,name+' vs same-room frequency'))
 csv('rooms/same_coverage_tag_transfer.csv',pairs)
 print('ROOMS',len(a),a.room_id.nunique(),'failed',len(fail),flush=True)
if __name__=='__main__':main()
