"""Rerun fixed-building predictions against V1, V2 and V2 continuous outcomes.

L2 kernels are reused, NOT old fitted predictions. Every centering/PCA/alpha/k
and layer choice is fitted inside training buildings. Unknown grades are not
classes. Coverage and failures are retained. All findings are exploratory reuse.
"""
from __future__ import annotations
import argparse,itertools,time,traceback,concurrent.futures
from scipy.stats import spearmanr
from tools.thesis_main.analysis.image_portrait.image_links_followup_common import *
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_predict import Provider as OldProvider,center_scale,grid,CONFIGS
GRADE1={'simple':0,'medium':1,'difficult_candidate':2}
GRADE2={'simple_candidate':0,'medium_candidate':1,'difficult_candidate':2}
# Grade names are asserted at preparation; no reinterpretation of unknowns.
CONT=['full_p_by_8','core10_p_by_19','core_tail_10','late_quarter_new','half_tv_all','within_cluster_median','singleton_share']
class Provider(OldProvider):
 def fields(self,name):
  if name=='traits':return ['floor_boundary','ceiling_boundary','connected_space','reflection_glass','low_contrast','doorway']
  if name=='scene_traits':return ['scene_category',*self.fields('traits')]
  if name=='main_traits':return ['main_function_primary',*self.fields('traits')]
  return super().fields(name)

def load_tasks():
 d=pd.read_csv(OUT/'targets/per_image_versions_and_process.csv');tasks=[]
 assert d[d.condition.eq('manual')].review_draft_grade.isin(GRADE2).sum()==61
 assert d[d.condition.eq('semi')].review_draft_grade.isin(GRADE2).sum()==14
 for arm,g in d.groupby('condition'):
  if arm=='oos_geometry':continue # explicit separate geometric study, no absent-embedding imputation
  base=g.sort_values('image_id').reset_index(drop=True)
  for target,col,mapping in [('grade_v1','grade_v1',GRADE1),('candidate_v2','review_draft_grade',GRADE2)]:
   t=base[base[col].isin(mapping)].copy().reset_index(drop=True)
   if len(t):tasks.append((arm,target,t,np.eye(3)[t[col].map(mapping).to_numpy(int)],True))
  for target in CONT:
   t=base.dropna(subset=[target]).copy().reset_index(drop=True)
   if len(t):tasks.append((arm,target,t,t[[target]].to_numpy(float),False))
 return tasks

def probabilities(pred,frequency):
 p=np.clip(pred,0,1);s=p.sum(-1,keepdims=True)
 return np.divide(p,s,out=np.broadcast_to(frequency,p.shape).copy(),where=s>1e-12)

def loss(pred,y,categorical):return np.sum((pred-y)**2,axis=-1)if categorical else np.mean(np.abs(pred-y),axis=-1)

def record(task,feature,alg,q,j,p,Y,**kw):
 arm,target,_,_,cat=task;y=Y[j];ok=np.isfinite(p).all()
 d=dict(image_id=q.image_id.iloc[j],building=q.building.iloc[j],condition=arm,target=target,feature=feature,algorithm=alg,information='pure_image',design='fixed_leave_building',status='ok'if ok else 'missing_predictor_or_training',loss=float(loss(p,y,cat))if ok else np.nan,truth=int(y.argmax())if cat else float(y[0]),prediction=int(np.argmax(p))if cat and ok else float(p[0])if ok else np.nan)
 if cat:
  d.update(p_simple=p[0],p_medium=p[1],p_difficult=p[2],correct=float(np.argmax(p)==np.argmax(y))if ok else np.nan,rps=float(np.mean((np.cumsum(p)[:2]-np.cumsum(y)[:2])**2))if ok else np.nan)
 d.update(kw);return d

def baselines(tasks):
 out=[];coverage=[]
 for task in tasks:
  arm,t,q,Y,cat=task;build=q.building.to_numpy()
  for b in sorted(set(build)):
   tr=np.flatnonzero(build!=b);te=np.flatnonzero(build==b)
   coverage.append(dict(condition=arm,target=t,building=b,test_images=len(te),training_images=len(tr),training_classes=';'.join(map(str,np.unique(Y[tr].argmax(1))))if cat else '',test_classes=';'.join(map(str,np.unique(Y[te].argmax(1))))if cat else ''))
   for name,col in [('constant',None),('scene_frequency','scene_category'),('main_frequency','main_function_primary'),('fine_frequency','fine_ai')]:
    for j in te:
     use=tr if col is None else tr[q.iloc[tr][col].fillna('unknown').to_numpy()==str(q.iloc[j][col])];fallback=not len(use)
     if fallback:use=tr
     p=Y[use].mean(0)if cat else np.median(Y[use],axis=0)
     out.append(record(task,name,'baseline',q,j,p,Y,n_train=len(use),unseen_stratum=fallback,inner_loss=np.nan,inner_n=0,pca='None',parameter=np.nan))
 csv('prediction/baselines.csv.gz',out);csv('prediction/fold_coverage.csv',coverage)

def evaluate(name,task):
 arm,target,q,Y,cat=task;provider=Provider(q.image_id.tolist());good=provider.valid(name);build=q.building.to_numpy();bs=sorted(set(build));cache={};rows=[];inner=[]
 def fit(excluded):
  key=tuple(sorted(excluded))
  if key not in cache:
   tr=np.flatnonzero(~np.isin(build,key)&good);te=np.flatnonzero(np.isin(build,key)&good)
   if len(tr):
    K=provider.kernel(name,tr);pr=grid(K,Y,tr,te,False)
    if cat:pr=probabilities(pr,Y[tr].mean(0))
   else:pr=np.full((len(CONFIGS),len(te),Y.shape[1]),np.nan)
   cache[key]=(te,pr,len(tr))
  return cache[key]
 for b in bs:
  te,pp,nt=fit([b]);score=np.zeros(len(CONFIGS));den=0
  for bi in bs:
   if bi==b:continue
   ix,pr,ntr=fit([b,bi]);m=(build[ix]==bi)&np.isfinite(pr).all(axis=(0,2))
   if not ntr or not m.any():continue
   score+=loss(pr[:,m],Y[ix[m]][None],cat).sum(1);den+=int(m.sum())
  score=score/den if den else np.full(len(CONFIGS),np.nan)
  for alg in ['ridge','knn']:
   cand=[k for k,c in enumerate(CONFIGS)if c['algorithm']==alg];sel=min(cand,key=lambda c:(score[c],c))if den else next(c for c in cand if CONFIGS[c]['pca']is None and CONFIGS[c]['parameter']==(10 if alg=='ridge'else 1));cfg=CONFIGS[sel]
   for pos,j in enumerate(te):rows.append(record(task,name,alg,q,j,pp[sel,pos],Y,n_train=nt,inner_loss=score[sel],inner_n=den,pca='None'if cfg['pca']is None else cfg['pca'],parameter=cfg['parameter'],n_target_valid=q.n_valid.iloc[j]))
   for j in np.flatnonzero((build==b)&~good):rows.append(record(task,name,alg,q,j,np.full(Y.shape[1],np.nan),Y,n_train=nt,inner_loss=np.nan,inner_n=den,pca='None',parameter=np.nan,n_target_valid=q.n_valid.iloc[j]))
  for k,cfg in enumerate(CONFIGS):inner.append(dict(feature=name,condition=arm,target=target,outer_building=b,inner_loss=score[k],inner_n=den,**cfg))
 return rows,inner

def run_feature(name):
 start=time.monotonic();stem=name.replace('::','___');p=OUT/'prediction/candidates'/(stem+'.csv.gz')
 if p.exists():return dict(feature=name,status='reused_current_run_cache')
 try:
  rows=[];inners=[]
  for task in load_tasks():
   a,b=evaluate(name,task);rows+=a;inners+=b
  csv('prediction/candidates/'+stem+'.csv.gz',rows);csv('prediction/inner/'+stem+'.csv.gz',inners)
  return dict(feature=name,status='executed',seconds=time.monotonic()-start,rows=len(rows))
 except Exception:return dict(feature=name,status='failed',error=traceback.format_exc())

def candidates():
 names=[r['feature']for r in readj(V1/'kernels/registry.json')]
 simple=['scene','main_space','fine_human','fine_ai','traits','positions','scene_traits','main_traits','feedback_counts','feedback_heads','feedback_rotation','feedback_between','feedback_all']
 return simple+names+['counts_plus::'+n for n in names]+['main_plus::feedback_all','main_plus::feedback_counts']

def summarize():
 frames=[pd.read_csv(OUT/'prediction/baselines.csv.gz')]
 for p in (OUT/'prediction/candidates').glob('*.csv.gz'):frames.append(pd.read_csv(p))
 d=pd.concat(frames,ignore_index=True);regs={r['feature']:r['family']for r in readj(V1/'kernels/registry.json')}
 pools={'selected_existing':[n for n,f in regs.items()if f!='dinov3'],'selected_dino':[n for n,f in regs.items()if f=='dinov3'],'selected_all':list(regs),'selected_counts_existing':['counts_plus::'+n for n,f in regs.items()if f!='dinov3'],'selected_counts_dino':['counts_plus::'+n for n,f in regs.items()if f=='dinov3']}
 selected=[];selrows=[]
 for label,ns in pools.items():
  for key,g in d[d.feature.isin(ns)].groupby(['condition','target','algorithm','building']):
   sc=g.groupby('feature').agg(score=('inner_loss','first'),n=('inner_n','first'));sc=sc[sc.n==sc.n.max()]
   best=sc.score.fillna(np.inf).sort_values(kind='stable').index[0];z=g[g.feature.eq(best)].copy();z['selected_candidate']=best;z['feature']=label;selected.append(z);selrows.append(dict(pool=label,condition=key[0],target=key[1],algorithm=key[2],building=key[3],candidate=best,inner_loss=sc.loc[best,'score'],inner_n=sc.loc[best,'n']))
 if selected:d=pd.concat([d,*selected],ignore_index=True)
 csv('prediction/all_predictions.csv.gz',d);csv('C/training_only_layer_selection.csv',selrows);out=[]
 for keys,g in d.groupby(['condition','target','feature','algorithm']):
  a=g.dropna(subset=['loss']);r=dict(zip(['condition','target','feature','algorithm'],keys),total_images=len(g),predicted_images=len(a),buildings=a.building.nunique(),image_loss=a.loss.mean(),building_macro_loss=a.groupby('building').loss.mean().mean(),metric='multiclass_Brier_sum'if keys[1]in ['candidate_v2','grade_v1']else 'MAE')
  if keys[1]in ['candidate_v2','grade_v1']:
   r.update(accuracy=a.correct.mean(),rps=a.rps.mean(),**{f'recall_{i}':a.loc[a.truth.eq(i),'correct'].mean()for i in [0,1,2]})
  else:r['spearman']=spearmanr(a.truth,a.prediction).statistic if a.truth.nunique()>1 and a.prediction.nunique()>1 else np.nan
  out.append(r)
 csv('prediction/score_summary.csv',out);pairs=[]
 compare=[('feedback_counts','constant'),('feedback_all','feedback_counts'),('traits','scene'),('scene_traits','scene'),('main_traits','main_space'),('main_plus::feedback_all','main_frequency'),('selected_existing','feedback_counts'),('selected_dino','feedback_counts'),('selected_counts_existing','feedback_counts'),('selected_counts_dino','feedback_counts'),('selected_all','selected_existing')]
 for (a,t),g in d[d.algorithm.isin(['ridge','baseline'])].groupby(['condition','target']):
  for new,old in compare:
   z=g[g.feature.eq(new)].merge(g[g.feature.eq(old)],on=['image_id','building'],suffixes=('_new','_old'));z['delta']=z.loss_new-z.loss_old
   if len(z):pairs.append(dict(condition=a,target=t,new=new,baseline=old,**paired(z)))
 csv('prediction/paired_increment.csv',pairs)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=3);ap.add_argument('--limit',type=int);ap.add_argument('--summarize',action='store_true');a=ap.parse_args()
 if a.summarize:summarize()
 else:
  tasks=load_tasks();baselines(tasks);ns=candidates()[:a.limit];done=[]
  with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers)as pool:
   for r in pool.map(run_feature,ns):done.append(r);print(json.dumps(r),flush=True);js('prediction/execution_progress.json',done)
  js('prediction/method.json',dict(configurations=CONFIGS,target_versions=['grade_v1_unmodified','candidate_v2_unreviewed'],new_fit=True,numerical_inputs='exact prior L2 Gram matrices for 205 images, not fitted old predictions',new_oos_arrays_in_deep=0,missing_oos_deep_images=9,failed=[r for r in done if r['status']=='failed'],requested_features=len(ns),preprocessing='per-image L2; all centering, kernel variance scaling, PCA and hyperparameters training-side',classification='three-class Brier primary; RPS descriptive secondary; unknown not a class',traits_duplicate_removed='corner_occlusion removed when using floor_boundary',repeated_historical_exploration=True));summarize()
