"""Independent numeric audit. Does not modify source or supplied results.
Usage: python audit.py --source /path/to/quality_deep_20261007 --expanded /path/to/expanded_input
Only comparison targets are imported from package; independent kernels below are new.
"""
from pathlib import Path
import json, sys, math, hashlib, collections, platform, os, argparse
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.metrics import roc_auc_score
HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('QUALITY_AUDIT_SOURCE',HERE.parents[1]/'unpacked/full/quality_deep_20261007')).resolve()
SOURCE=Path(os.environ.get('QUALITY_AUDIT_EXPANDED',HERE.parents[1]/'unpacked/expanded_input')).resolve()
OFFICIAL=Path(os.environ.get('QUALITY_AUDIT_OFFICIAL_OUTPUT',HERE/'official')).resolve()
target=None

def parse_config(description, choices):
 parser=argparse.ArgumentParser(description=description)
 parser.add_argument('--source',type=Path,default=ROOT,help='Path to extracted quality_deep_20261007 package')
 parser.add_argument('--expanded',type=Path,default=SOURCE,help='Path to extracted expanded upstream input')
 parser.add_argument('--official-output',type=Path,default=OFFICIAL,help='Existing fresh official reproduction directory')
 parser.add_argument('--checks',nargs='+',choices=['all']+choices,default=['all'],help='Run selected checks; default all')
 return parser.parse_args()

def configure(args):
 global ROOT,SOURCE,OFFICIAL,target
 ROOT=args.source.resolve();SOURCE=args.expanded.resolve();OFFICIAL=args.official_output.resolve()
 sys.path.insert(0,str(ROOT/'src'))
 import importlib
 target=importlib.import_module('components')


def save(name,v):
 (HERE/name).write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False))
def read(p):return json.loads(p.read_text())
def source_binding():
 p=read(ROOT/'inputs/panel.json')['images']; src=read(SOURCE/'current/panel.json')['images']; lookup={i['code']:i for i in src}
 cs=read(ROOT/'inputs/candidates.json')['states']; srccs=read(SOURCE/'analysis_results/adaptive_point_20261007/expanded/candidates.json')['states']
 inv=read(ROOT/'inputs/inventory.json');srcinv=read(SOURCE/'current/image_inventory.json')['images']
 out={'panel_exact_objects':sum(i==lookup[i['code']] for i in p),'panel_count':len(p),'candidate_exact_objects':sum(i in srccs for i in cs),'candidate_count':len(cs),'inventory_exact_objects':sum(i in srcinv for i in inv),'inventory_count':len(inv),'code':{}}
 for f,srcf in [('vendor/geometry.py','tools/label_studio/panorama_studio/geometry.py'),('vendor/arc_consensus.py','tools/thesis_main/analysis/layout_reliability_20261005/arc_consensus.py')]:
  x=(ROOT/f).read_bytes();y=(SOURCE/srcf).read_bytes();out['code'][f]={'same_bytes':x==y,'sha256':hashlib.sha256(x).hexdigest()}
 def included(a):return bool(a.get('independent') and a.get('consensus_eligible') and a.get('condition')=='manual' and a['main_consensus_gate']['status'] in {'main_candidate','oos_doorway_exploratory','stable_nonorthogonal_separate'})
 sel={s['image']:s for s in read(ROOT/'inputs/selection.json')}
 originals=[(im,a) for im in p for a in im['annotations'] if included(a) or (im['code']=='uNb9QFRL6hY-51' and a['independent'] and a['points'])]
 out['counts_independent']={'images':len(p),'buildings':len({i['building'] for i in p}),'input_records':sum(len(i['annotations']) for i in p),'eligible':sum(included(a) for i in p for a in i['annotations']),'originals':len(originals),'broad_images':sum(sel[i['code']]['panel']=='broad' for i in p),'broad_eligible':sum(included(a) for i in p if sel[i['code']]['panel']=='broad' for a in i['annotations']),'fusion_states':len(cs),'fusion_points':sum(bool(s['result'].get('candidate',{}).get('points')) for s in cs),'original_reference_rows':sum(len(i['references']) for i,a in originals)}
 out['counts_independent']['candidate_reference_rows']=sum(len(lookup[s['image']]['references']) for s in cs if s['result'].get('candidate',{}).get('points'))
 out['excluded_diagnostic_records']=[{'image':i['code'],'id':a['id'],'consensus_gate':a['main_consensus_gate'],'quality_gate':a['main_quality_gate']} for i,a in originals if not included(a)]
 save('source_binding.json',out)
 return out

def reproduction_diff():
 out={}
 for f in sorted(OFFICIAL.iterdir()):
  supplied=ROOT/'results'/f.name
  if not supplied.exists():continue
  if f.suffix=='.csv':
   a,b=pd.read_csv(supplied),pd.read_csv(f);mismatch=[];maxerr=0.
   if a.shape!=b.shape or list(a)!=list(b):out[f.name]={'shape_or_columns_differ':True};continue
   for col in a:
    if col=='elapsed_s':continue
    if pd.api.types.is_numeric_dtype(a[col]) and pd.api.types.is_numeric_dtype(b[col]) and not pd.api.types.is_bool_dtype(a[col]):
     x,y=a[col].to_numpy(dtype=float),b[col].to_numpy(dtype=float);finite=np.isfinite(x)&np.isfinite(y)
     d=float(np.max(abs(x[finite]-y[finite]))) if finite.any() else 0.;maxerr=max(maxerr,d)
     if not np.allclose(x,y,equal_nan=True,rtol=1e-10,atol=1e-10):mismatch.append({'column':col,'max_abs_difference':d})
    elif not a[col].fillna('<NA>').equals(b[col].fillna('<NA>')):mismatch.append({'column':col,'different_strings_or_bools':True})
   out[f.name]={'rows':len(a),'max_absolute_difference':maxerr,'mismatch':mismatch}
  elif f.name in ['summary.json','probe_results.json','new_geometry_checks.json']:
   out[f.name]={'exact_json_match':read(f)==read(supplied)}
 save('reproduction_diff.json',out);return out

def reconstruct(record):
 """Independent direct cotangent reconstruction, no package geometric primitives."""
 p=np.array(record['points']).reshape(-1,2,2);angle=2*np.pi*(p[:,1,0]/1024-.5)
 radius=1/np.tan(np.pi*(p[:,1,1]-256)/512)
 f=np.c_[radius*np.sin(angle),-np.ones(len(p)),-radius*np.cos(angle)]
 t=f.copy();t[:,1]=radius*np.tan(np.pi*(256-p[:,0,1])/512)
 return t,f

def scalar_distance(point,vertices,closed=True):
 """Explicit scalar branch oracle; no vectorized clamp reused from target."""
 best=math.inf
 for i in range(len(vertices) if closed else len(vertices)-1):
  aa=vertices[i];bb=vertices[(i+1)%len(vertices)];ee=bb-aa;dd=point-aa
  norm=float(np.dot(ee,ee));dot=float(np.dot(dd,ee))
  if norm==0 or dot<=0:dist=float(np.linalg.norm(dd))
  elif dot>=norm:dist=float(np.linalg.norm(point-bb))
  else:dist=float(np.linalg.norm(np.cross(dd,ee))/math.sqrt(norm))
  best=min(best,dist)
 return best

def independent_samples(v,n):
 lengths=[float(np.linalg.norm(v[(i+1)%len(v)]-v[i])) for i in range(len(v))]
 total=sum(lengths);result=[];j=0;cum=0.
 for k in range(n):
  pos=total*(k+.5)/n
  while j<len(v)-1 and pos>=cum+lengths[j]:cum+=lengths[j];j+=1
  alpha=(pos-cum)/lengths[j];result.append(v[j]*(1-alpha)+v[(j+1)%len(v)]*alpha)
 return np.array(result),total

def independent_curve(a,b,n=512):
 means=[]
 for x,y in [(a,b),(b,a)]:
  q,L=independent_samples(x,n);means.append(sum(scalar_distance(p,y) for p in q)/n)
 return sum(means)/2

def exact_heading(f):
 """Find global minimum of circular length-weighted squared axis residual.
 Enumerate every wrap breakpoint; each interval has a closed-form minimizer.
 """
 e=np.roll(f,-1,axis=0)-f;l=np.linalg.norm(e,axis=1);ang=np.arctan2(e[:,1],e[:,0]);period=np.pi/2
 breaks=np.unique(np.r_[0.,period,(ang+period/2)%period]);best=(math.inf,None)
 for lo,hi in zip(breaks[:-1],breaks[1:]):
  m=(lo+hi)/2;unwrapped=m+(ang-m+period/2)%period-period/2
  axis=np.clip(np.average(unwrapped,weights=l),lo,hi);r=(ang-axis+period/2)%period-period/2
  obj=np.average(r*r,weights=l)
  if obj<best[0]:best=(obj,axis)
 return math.sqrt(best[0])*180/np.pi,best[1]*180/np.pi

def numeric_kernel_checks():
 rng=np.random.default_rng(420621);maxerr=0.;tests=0
 for closed in [True,False]:
  for n in [2,3,8,20]:
   for rep in range(20):
    v=rng.normal(size=(n,3));q=rng.normal(size=(20,3))*3
    if rep%2==0:v[1]=v[0]
    a=target.segment_distances(q,v,closed);b=np.array([scalar_distance(x,v,closed) for x in q])
    maxerr=max(maxerr,float(np.max(abs(a-b))));tests+=len(q)
 panel=read(ROOT/'inputs/panel.json')['images'];metrics=pd.read_csv(ROOT/'results/metrics.csv');objs=read(ROOT/'results/objects.json')
 heading=[];reconstruction=[]
 for item in objs:
  if item['intrinsic']['geometry_status']!='ok':continue
  r=item['record'];a,b=reconstruct(r);x,y=target.paired_wall_proxy(r)
  reconstruction.append(float(max(abs(a-x).max(),abs(b-y).max())))
  rms,axis=exact_heading(b[:,[0,2]]);official=item['intrinsic'].get('direction_rms_deg')
  if official is not None:heading.append({'image':item['image'],'id':item['id'],'official_rms_deg':official,'global_min_rms_deg':rms,'difference_deg':official-rms,'axis_deg':axis})
 cases=[('uNb9QFRL6hY-18','R02846'),('uNb9QFRL6hY-18','R02843'),('X7HyMhZNoso-19','R01646'),('X7HyMhZNoso-19','R00916'),('2t7WUuJeko7-09','R00016')]
 curves=[]
 for imid,aid in cases:
  im=next(i for i in panel if i['code']==imid);a=next(a for a in im['annotations'] if a['id']==aid);g=im['references'][0];at,af=reconstruct(a);gt,gf=reconstruct(g)
  row=metrics[(metrics.image==imid)&(metrics.id==aid)&(metrics.reference_id==g['id'])].iloc[0]
  for name,x,y in [('top3d',at,gt),('floor3d',af,gf)]:
   val=independent_curve(x,y);curves.append({'image':imid,'id':aid,'side':name,'independent':val,'supplied':float(row[name+'_symmetric_mean_h']),'difference':val-float(row[name+'_symmetric_mean_h'])})
 out={'scalar_queries':tests,'max_segment_distance_error_h':maxerr,'objects_reconstructed':len(reconstruction),'max_reconstruction_error_h':max(reconstruction),'heading_tested':len(heading),'heading_max_rms_gap_deg':max(h['difference_deg'] for h in heading),'heading_suboptimal_over_1e_7':[h for h in heading if h['difference_deg']>1e-7],'independent_curve_checks':curves}
 pd.DataFrame(heading).to_csv(HERE/'independent_heading.csv',index=False);save('numeric_kernel_checks.json',out);return out

def predictor_audit():
 c=pd.read_csv(ROOT/'results/correction_metrics.csv');a=c[(c.panel=='broad')&(c.alpha==1)&(c.version=='original')&(c.status=='ok')].dropna(subset=['before_top_mae_deg','after_top_mae_deg','before_bottom_mae_deg','after_bottom_mae_deg']).copy()
 cols=['before_direction_rms_deg','before_flat_top_angular_rms_deg','max_endpoint_move_deg'];a=a.dropna(subset=cols)
 y=((a.after_iou-a.before_iou>1e-4)&(a.after_top_mae_deg-a.before_top_mae_deg<=.1)&(a.after_bottom_mae_deg-a.before_bottom_mae_deg<=.1)).astype(int).to_numpy();x=a[cols].to_numpy();buildings=a.building.to_numpy();p=np.zeros(len(a));prior=np.zeros(len(a));folds=[]
 for b in sorted(set(buildings)):
  train=buildings!=b;test=~train;mu=x[train].mean(0);std=x[train].std(0);std[std==0]=1
  X=np.c_[np.ones(sum(train)),(x[train]-mu)/std];Y=y[train]
  def fun(w):
   z=X@w;v=np.logaddexp(0,z).sum()-Y@z+np.dot(w[1:],w[1:])/2
   grad=X.T@(expit(z)-Y);grad[1:]+=w[1:];return v,grad
  fit=minimize(fun,np.zeros(4),jac=True,method='BFGS',options={'gtol':1e-9,'maxiter':1000})
  p[test]=expit(np.c_[np.ones(sum(test)),(x[test]-mu)/std]@fit.x);prior[test]=Y.mean();pt=expit(X@fit.x)
  folds.append({'building':b,'n_test':int(sum(test)),'positives':int(y[test].sum()),'train_prior':float(Y.mean()),'test_prob_mean':float(p[test].mean()),'train_auc':float(roc_auc_score(Y,pt)),'heldout_auc':float(roc_auc_score(y[test],p[test])) if len(set(y[test]))==2 else None,'coefficients':fit.x.tolist(),'gradient_norm':float(np.linalg.norm(fit.jac)),'heldout_mixed_class_pairs':int(sum(y[test]==1)*sum(y[test]==0))})
 a['label_independent']=y;a['probability_independent']=p;a['training_prior']=prior
 supplied=pd.read_csv(ROOT/'results/lobo_projection_gate.csv');joined=a.merge(supplied,left_on=['image','source_id'],right_on=['image','id'],suffixes=('','_saved'))
 denom=sum(f['heldout_mixed_class_pairs'] for f in folds);within=sum(f['heldout_auc']*f['heldout_mixed_class_pairs'] for f in folds if f['heldout_auc'] is not None)/denom
 out={'n':len(a),'positives':int(y.sum()),'independent_auc':float(roc_auc_score(y,p)),'independent_accuracy_n':int(sum((p>=.5)==y)),'independent_adopt_count':int(sum(p>=.5)),'majority_correct_n':int(sum((prior>=.5)==y)),'constant_training_prior_pooled_auc':float(roc_auc_score(y,prior)),'within_building_auc_pair_weighted':within,'within_building_mixed_pairs':denom,'total_positive_negative_pairs':int(sum(y==1)*sum(y==0)),'max_abs_probability_difference':float(abs(joined.probability_independent-joined.pred_probability).max()),'label_mismatches':int(sum(joined.label_independent!=joined.label)),'folds':folds}
 a.to_csv(HERE/'independent_lobo_predictions.csv',index=False);save('predictor_audit.json',out);return out

if __name__=='__main__':
 checks={'binding':source_binding,'comparison':reproduction_diff,'geometry':numeric_kernel_checks,'predictor':predictor_audit}
 args=parse_config(__doc__,list(checks));configure(args)
 for name,func in checks.items():
  if 'all' not in args.checks and name not in args.checks:continue
  print('RUN',func.__name__,flush=True);res=func();print(json.dumps(res,ensure_ascii=False,indent=2),flush=True)
