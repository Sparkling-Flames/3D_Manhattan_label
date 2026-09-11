"""Independent review of worker reference performance and Semi behavior.
Read-only empirical audit. No implicit old qualification filters or new human labels.
Run: python code/worker_audit.py --repo /path/to/repository --out results
"""
from __future__ import annotations
import argparse,gzip,json,hashlib,math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.cluster.hierarchy import linkage,cut_tree
from scipy.stats import spearmanr

SEED=20260909
CURRENT={str(i) for i in [1,2,6,8,10,11,12,13,15,17,*range(28,38)]}

def lines(p):
 with (gzip.open(p,'rt',encoding='utf-8') if str(p).endswith('.gz') else open(p,encoding='utf-8-sig')) as f:return [json.loads(s) for s in f if s.strip()]
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(out,name,d):
 out.mkdir(exist_ok=True,parents=True)
 (d if isinstance(d,pd.DataFrame) else pd.DataFrame(d)).to_csv(out/name,index=False,float_format='%.12g',compression={'method':'gzip','mtime':0} if name.endswith('.gz') else None)
def unit(p):
 p=np.asarray(p,float)
 if p.ndim!=2 or p.shape[1]!=2 or len(p)==0 or not np.isfinite(p).all():raise ValueError('invalid pointset')
 a=p[:,0]*2*np.pi/1024;e=np.pi/2-p[:,1]*np.pi/512
 return np.c_[np.cos(e)*np.cos(a),np.cos(e)*np.sin(a),np.sin(e)]
def metric(a,b,c):
 x,y=unit(a),unit(b);ang=np.rad2deg(np.arctan2(np.linalg.norm(np.cross(x[:,None],y[None,:]),axis=2),np.clip(x@y.T,-1,1)))
 cost=np.minimum(ang,c);i,j=linear_sum_assignment(cost)
 return float((cost[i,j].sum()+c*abs(len(x)-len(y)))/max(len(x),len(y)))

def fit(d):
 """Direct within-image fixed-effect normal equations; connected components audited."""
 d=d[np.isfinite(d.value)].copy();d=d[d.groupby('context_key').worker_id.transform('nunique')>=2]
 workers=sorted(d.worker_id.unique());wi={w:j for j,w in enumerate(workers)};A=np.zeros((len(workers),len(workers)));b=np.zeros(len(workers))
 for _,g in d.groupby('context_key',sort=False):
  ix=np.array([wi[w] for w in g.worker_id]); y=g.value.to_numpy(float)
  if len(np.unique(ix))!=len(ix):raise ValueError('duplicate worker context')
  A[np.ix_(ix,ix)]+=np.eye(len(ix))-1/len(ix);b[ix]+=y-y.mean()
 if not workers:return pd.Series(dtype=float)
 if np.linalg.matrix_rank(A,tol=1e-8)!=len(workers)-1:raise ValueError('disconnected support')
 beta=np.linalg.lstsq(A,b,rcond=1e-10)[0];beta-=beta.mean()
 return pd.Series(beta,index=workers)

def cv(d,training=None):
 rr=[];source=d if training is None else training
 for b,test in d.groupby('building_id'):
  train=source[source.building_id!=b]
  try:p=fit(train)
  except ValueError:continue
  for ctx,g in test[test.worker_id.isin(p.index)].groupby('context_key'):
   if len(g)<2:continue
   y=g.value.to_numpy(float);y-=y.mean();pred=g.worker_id.map(p).to_numpy();pred-=pred.mean()
   labels=(p>p.median()).astype(int);groupmean=p.groupby(labels).mean();coarse=g.worker_id.map(labels).map(groupmean).to_numpy();coarse-=coarse.mean()
   for i,r in enumerate(g.to_dict('records')):
    rr.append({k:r[k] for k in ['worker_id','image_id','context_key','building_id']}|dict(target=y[i],continuous=pred[i],coarse=coarse[i],base_loss=y[i]**2,continuous_loss=(y[i]-pred[i])**2,coarse_loss=(y[i]-coarse[i])**2))
 return pd.DataFrame(rr)

def summarize(d,keys):
 rr=[];by=[]
 for key,g in d.groupby(keys):
  key=key if isinstance(key,tuple) else (key,);meta=dict(zip(keys,key));b=g.groupby('building_id')[['base_loss','continuous_loss','coarse_loss']].mean()
  row=meta|dict(rows=len(g),images=g.image_id.nunique(),workers=g.worker_id.nunique(),buildings=len(b))
  for model in ['continuous','coarse']:
   row[model+'_record_gain']=1-g[model+'_loss'].mean()/g.base_loss.mean();row[model+'_building_gain']=1-b[model+'_loss'].mean()/b.base_loss.mean()
  rr.append(row);by.append(b.reset_index().assign(**meta))
 return pd.DataFrame(rr),pd.concat(by,ignore_index=True)

def split_stability(d,metric_name,cohort):
 from sklearn.metrics import adjusted_rand_score
 rng=np.random.default_rng(SEED);builds=sorted(d.building_id.unique());result=[]
 for rep in range(120):
  bs=set(rng.permutation(builds)[:len(builds)//2])
  try:a=fit(d[d.building_id.isin(bs)]);b=fit(d[~d.building_id.isin(bs)])
  except ValueError:continue
  common=sorted(set(a.index)&set(b.index));aa=a.loc[common];bb=b.loc[common]
  if len(common)<4:continue
  # Group thresholds from each training half; only common workers enter the agreement assessment.
  la=(aa>a.median()).astype(int);lb=(bb>b.median()).astype(int)
  result.append(dict(metric=metric_name,cohort=cohort,replicate=rep,common_workers=len(common),rank_rho=spearmanr(aa,bb).statistic,coarse_ARI=adjusted_rand_score(la,lb),label_agreement=float(np.mean(la==lb)),split_A=';'.join(sorted(bs))))
 return result

def hierarchy(man,sem,forced=None):
 common=sorted(set(man.index)&set(sem.index));m=man.loc[common];s=sem.loc[common];coarse=(m>m.median()).astype(int)
 X=np.c_[np.ones(len(m)),m];b=np.linalg.lstsq(X,s,rcond=None)[0];linear=X@b;res=s.to_numpy()-linear
 quadratic=np.c_[X,m*m]@np.linalg.lstsq(np.c_[X,m*m],s,rcond=None)[0]
 labels=pd.Series(index=common,dtype=str)
 for c in [0,1]:
  ids=np.flatnonzero(coarse.to_numpy()==c);z=res[ids]
  if len(ids)<4 or len(np.unique(z))<2:labs=np.zeros(len(ids),int)
  else:
   labs=cut_tree(linkage(z[:,None],method='ward'),n_clusters=2).ravel()
   if np.bincount(labs).min()<2:labs=np.zeros(len(ids),int)
   else:
    ordered=sorted(np.unique(labs),key=lambda k:np.mean(z[labs==k]));labmap={v:i for i,v in enumerate(ordered)};labs=np.array([labmap[k] for k in labs])
  labels.iloc[ids]=[f'{c}.{l}' for l in labs]
 if forced is not None:labels=forced.reindex(common);assert labels.notna().all()
 d=pd.DataFrame(dict(worker_id=common,manual=m.to_numpy(),semi=s.to_numpy(),linear=linear,quadratic=quadratic,residual=res,label=labels.to_numpy()))
 d['layer']=d.linear+d.groupby('label').residual.transform('mean');return d

def semi_cv(man,semi):
 output=[];members=[]
 for cohort,people in [('all26',set(man.worker_id)),('current20',CURRENT)]:
  for pool in ['all_initializations','without_synthetic']:
   a=man[man.worker_id.isin(people)];s=semi[semi.worker_id.isin(people)]
   if pool=='without_synthetic':s=s[s.source_group!='trap_synthetic_disjoint_source']
   for cap in [30,60]:
    for b in sorted(s.building_id.unique()):
     mf=fit(a[a.building_id!=b].assign(value=lambda q:q['ospa'+str(cap)]));tr=s[s.building_id!=b];te=s[s.building_id==b]
     ef=fit(tr.assign(value=lambda q:q['edit_ospa'+str(cap)]));h=hierarchy(mf,ef)
     members.append(h.assign(cohort=cohort,pool=pool,cap=cap,building_id=b))
     for outcome in ['edit','final_via_edit_labels']:
      field=('edit' if outcome=='edit' else 'final')+'_ospa'+str(cap)
      if outcome!='edit':
       ff=fit(tr[tr[field].notna()].assign(value=lambda q:q[field]));fitrow=hierarchy(mf,ff,h.set_index('worker_id').label)
      else:fitrow=h
      t=te[te[field].notna()].merge(fitrow,on='worker_id',validate='many_to_one')
      t=t[t.groupby('context_key').worker_id.transform('size')>=2].copy()
      t['target']=t[field]-t.groupby('context_key')[field].transform('mean')
      for model in ['linear','quadratic','layer','semi']:
       t[model+'_pred']=t[model]-t.groupby('context_key')[model].transform('mean');t[model+'_loss']=(t.target-t[model+'_pred'])**2
      t['base_loss']=t.target**2
      cols=['canonical_annotation_id','worker_id','image_id','building_id','context_key','source_group','target','base_loss',*[m+'_pred' for m in ['linear','quadratic','layer','semi']],*[m+'_loss' for m in ['linear','quadratic','layer','semi']]]
      output.append(t[cols].assign(cohort=cohort,pool=pool,cap=cap,outcome=outcome))
 return pd.concat(output,ignore_index=True),pd.concat(members,ignore_index=True)

def semi_summary(d):
 rr=[];bb=[];rng=np.random.default_rng(SEED+1)
 for key,g in d.groupby(['cohort','pool','cap','outcome']):
  meta=dict(zip(['cohort','pool','cap','outcome'],key));b=g.groupby('building_id')[[m+'_loss' for m in ['base','linear','quadratic','layer','semi']]].mean()
  row=meta|dict(rows=len(g),images=g.image_id.nunique(),workers=g.worker_id.nunique(),buildings=len(b))
  for m in ['linear','quadratic','layer','semi']:row[m+'_vs_zero_gain']=1-b[m+'_loss'].mean()/b.base_loss.mean()
  row['layer_vs_manual_quadratic_gain']=1-b.layer_loss.mean()/b.quadratic_loss.mean();row['continuous_semi_vs_layer_gain']=1-b.semi_loss.mean()/b.layer_loss.mean()
  # Paired building resampling of fixed out-of-building predictions; not refit/full new-worker CI.
  delta=(b.layer_loss-b.quadratic_loss).values;draw=rng.choice(delta,(4000,len(delta)),replace=True).mean(1)
  row.update(delta_MSE=delta.mean(),conditional_low=np.quantile(draw,.025),conditional_high=np.quantile(draw,.975),buildings_improved=int((delta<0).sum()))
  rr.append(row);bb.append(b.reset_index().assign(**meta))
 return pd.DataFrame(rr),pd.concat(bb,ignore_index=True)

def main(repo,out):
 root=Path(repo);out=Path(out);ar=root/'analysis_results';viewpath=ar/'confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz';view=lines(viewpath)
 oldpath=ar/'confirmed_point_calculation_view_20260909_v1/calculation_view.jsonl.gz';old={r['canonical_annotation_id']:r for r in lines(oldpath)}
 rp=ar/'worker_reference_feasibility_20260909_v1/reference_ledger.jsonl';refs={r['image_id']:r for r in lines(rp)}
 # Actual imports and raw exports are checked read-only; only hashes/IDs enter outputs.
 files={viewpath,rp,oldpath};cache={};qa=[];changes=[];measured=[]
 for r in view:
  path=root/r['raw_export_path'];files.add(path)
  if path not in cache:
   data=json.loads(path.read_text(encoding='utf-8-sig'));cache[path]={(str(t['id']),str(a['id'])):a for t in data for a in t.get('annotations',[])}
  ident=r['annotation_identity'].split('|');a=cache[path][(ident[-3],ident[-1])]
  owner=a.get('completed_by');owner=owner.get('id',owner.get('pk')) if isinstance(owner,dict) else owner
  assert str(owner)==str(r['worker_id'])==ident[-2],r['canonical_annotation_id']
  points=[[k['value']['x']*1024/100,k['value']['y']*512/100] for k in a['result'] if k.get('type')=='keypointlabels']
  assert np.shape(points)==np.shape(r['raw_points_1024x512']) and np.allclose(points,r['raw_points_1024x512'],atol=1e-7,rtol=0),r['canonical_annotation_id']
  qa.append(dict(canonical_annotation_id=r['canonical_annotation_id'],raw_coordinate_match=True,raw_path=r['raw_export_path'],raw_annotation_id=ident[-1]))
  prev=old[r['canonical_annotation_id']]
  if prev['effective_points_1024x512']!=r['effective_points_1024x512']:changes.append({k:r[k] for k in ['canonical_annotation_id','worker_id','image_id','raw_condition','processing_status','calculation_included']})
  ref=refs[r['image_id']];row={k:r[k] for k in ['canonical_annotation_id','worker_id','image_id','building_id','context_key','raw_condition','assistance_exposure','processing_status','calculation_included','imputed_point']}
  row.update(reference_basis=ref['basis'],reference_allowed=ref['score_allowed'],reference_hold=ref['hold_reason'],scope_status=ref.get('scope_status',''),scored=bool(r['calculation_included'] and ref['score_allowed']))
  for cap in [30,60]:row['ospa'+str(cap)]=metric(r['effective_points_1024x512'],ref['points_1024x512'],cap) if row['scored'] else np.nan
  measured.append(row)
 m=pd.DataFrame(measured);save(out,'raw_identity_checks.csv',qa);save(out,'changed_calculation_records.csv',changes);save(out,'reviewed_reference_measurements.csv.gz',m)
 save(out,'reference_support.csv',m.groupby(['assistance_exposure','scored','reference_basis','scope_status']).agg(rows=('worker_id','size'),images=('image_id','nunique'),workers=('worker_id','nunique')).reset_index())
 source=m[(m.assistance_exposure=='none')&m.scored].copy();source['context_key']=source.image_id
 assert not source.duplicated(['image_id','worker_id']).any()
 # Manual/unassisted performance: measured dimension, not an inferred attitude.
 pred=[];stab=[]
 for cohort,people in [('all26',set(source.worker_id)),('current20',CURRENT),('without19_26',set(source.worker_id)-{'19','26'})]:
  for refset in ['all_accepted_references','reviewed_reference_only']:
   s=source[source.worker_id.isin(people)]
   if refset=='reviewed_reference_only':s=s[s.reference_basis=='reviewed_reference']
   for cap in [30,60]:
    d=s.assign(value=s['ospa'+str(cap)]);p=cv(d)
    if not p.empty:pred.append(p.assign(cohort=cohort,reference_set=refset,cap=cap))
    if refset=='all_accepted_references':stab+=split_stability(d,str(cap),cohort)
 pr=pd.concat(pred,ignore_index=True);su,bu=summarize(pr,['cohort','reference_set','cap']);save(out,'manual_lobo_predictions.csv.gz',pr);save(out,'manual_lobo_summary.csv',su);save(out,'manual_lobo_buildings.csv',bu);save(out,'manual_disjoint_building_stability.csv',stab)
 # Before/after geometry shifts, matched only on common scored records.
 original=pd.read_csv(ar/'worker_reference_feasibility_20260909_v1/response_measurements.csv.gz',dtype={'worker_id':str});j=m.merge(original[['canonical_annotation_id','ospa30','ospa60']],on='canonical_annotation_id',suffixes=['_new','_old'],validate='one_to_one')
 for cap in [30,60]:j['delta'+str(cap)]=j['ospa'+str(cap)+'_new']-j['ospa'+str(cap)+'_old']
 save(out,'reference_measurement_update_changes.csv',j[(abs(j.delta30)>1e-9)| (j.ospa30_new.isna()!=j.ospa30_old.isna())])
 sp=ar/'semi_subtype_exploration_20260909_v1/semi_response_features.csv';saved=pd.read_csv(sp,dtype={'worker_id':str});proppath=ar/'uncertainty_cloud_inputs_20260906_v1/facts/proposal_response.csv.gz';props=pd.read_csv(proppath,dtype=str,keep_default_na=False).set_index('canonical_annotation_id');files.update([sp,proppath]);vmap={r['canonical_annotation_id']:r for r in view};sem=[]
 for row in saved.to_dict('records'):
  r=vmap[row['canonical_annotation_id']];initial=json.loads(props.loc[r['canonical_annotation_id'],'initial_points_json']);final=r['effective_points_1024x512'];ref=refs[r['image_id']]
  assert final is not None
  z={k:row[k] for k in ['canonical_annotation_id','worker_id','image_id','building_id','context_key','source_group']}
  for cap in [30,60]:
   z['edit_ospa'+str(cap)]=metric(initial,final,cap)
   z['initial_ospa'+str(cap)]=metric(initial,ref['points_1024x512'],cap) if ref['score_allowed'] else np.nan
   z['final_ospa'+str(cap)]=metric(final,ref['points_1024x512'],cap) if ref['score_allowed'] else np.nan
  z['final_point_count']=len(final);z['initial_point_count']=len(initial);sem.append(z)
 semi=pd.DataFrame(sem);save(out,'reviewed_semi_features.csv',semi)
 # Triangle bound: edit amplitude can be forced near final error by near-reference initialization.
 cols=[]
 for context,g in semi.groupby('context_key'):
  before=g.initial_ospa30.iloc[0];width=(g.edit_ospa30-g.final_ospa30).abs().max()
  if np.isfinite(before):assert width<=before+1e-7
  cols.append(dict(context_key=context,image_id=g.image_id.iloc[0],source_group=g.source_group.iloc[0],rows=len(g),initial_reference_ospa30=before,max_abs_edit_minus_final=width))
 save(out,'semi_triangle_redundancy.csv',cols)
 spr,sfm=semi_cv(source,semi);ss,sb=semi_summary(spr);save(out,'semi_revised_predictions.csv.gz',spr);save(out,'semi_revised_summary.csv',ss);save(out,'semi_revised_buildings.csv',sb);save(out,'semi_revised_fold_members.csv',sfm)
 # Baseline-table reconstruction checks from saved predictions, no geometry changes.
 archived=pd.read_csv(ar/'semi_subtype_exploration_20260909_v1/heldout_predictions.csv.gz');checks=[]
 summary=pd.read_csv(ar/'semi_subtype_exploration_20260909_v1/validation_summary.csv')
 for r in summary.to_dict('records'):
  g=archived
  for k in ['cohort','pool','metric','outcome']:g=g[g[k]==r[k]]
  b=g.groupby('building_id')[['layer_sqerr','manual_quadratic_prediction_sqerr']].mean();gain=1-b.layer_sqerr.mean()/b.manual_quadratic_prediction_sqerr.mean()
  checks.append(dict(cohort=r['cohort'],pool=r['pool'],metric=r['metric'],outcome=r['outcome'],saved=r['manual_plus_fine_vs_quadratic_building_gain'],recomputed=gain,error=gain-r['manual_plus_fine_vs_quadratic_building_gain']))
 assert max(abs(c['error']) for c in checks)<1e-10
 save(out,'semi_archived_table_checks.csv',checks)
 save(out,'worker_input_manifest.csv',[dict(path=str(p.relative_to(root)),sha256=digest(p),bytes=p.stat().st_size) for p in sorted(files)])
 (out/'WORKER_QA.json').write_text(json.dumps(dict(raw_records_checked=len(qa),raw_exports=len(cache),changed_calculation_records=len(changes),scored_unassisted=len(source),semi_rows=len(semi),new_human_labels=0,new_neural_runs=0,manual_model='image intercept plus continuous worker; building held out',caveat='reference-relative point-set fidelity is not verified rule compliance or attitude; intervals conditional on stored workers'),indent=2))
 print(su.to_string(index=False));print(ss[ss.cohort=='current20'].to_string(index=False));print('WORKER DONE',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.repo,a.out)
