#!/usr/bin/env python3
"""Frozen-score, retrospective validation-target sensitivity; no fitted weights.

Run: python run_experiment.py --source path/to/quality_compact_20261007 --out results_out
Original inputs are read only. All outputs live beside this file unless --out is set.
"""
from pathlib import Path
import argparse, itertools, json, sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
DEFAULT_SOURCE=HERE.parents[1]/'unpacked'/'quality_compact_20261007'
CORE=['L','C','U','B']
ORIGINAL_SCALE=CORE+['T','T_relative']
INTRINSIC=['direction_rms_deg','flat_top_angular_rms_deg']
FEATURES=CORE+['T','T_relative','LC','F']+INTRINSIC
ORIGINAL_SCHEMES=['S0','S1','S4','S5','S5_relative']
SCHEMES=ORIGINAL_SCHEMES+['LCn','LCn_T','LCn_G']
TOL={'L':1e-4,'C':1e-4,'U':.1,'B':.1,'T':.01,'F':.01}
PRED_TOL=1e-12
CONTRASTS=[(x,'S0') for x in SCHEMES if x!='S0']+[
 ('S5','S4'),('S5_relative','S4'),('LCn_T','LCn'),('LCn_G','LCn'),('LCn_T','S1'),('LCn_G','S1')]

def save_json(path, data):
 def clean(x):
  if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
  if isinstance(x,(list,tuple)): return [clean(v) for v in x]
  if isinstance(x,np.generic): return clean(x.item())
  if isinstance(x,float) and not np.isfinite(x): return None
  return x
 path.write_text(json.dumps(clean(data),ensure_ascii=False,indent=2)+'\n')

def pair_id(im,wa,wb): return f'{im}|{wa}|{wb}'

def dom(a,b,cols):
 # Deliberately preserve the original arithmetic, not a newly rounded delta test.
 return all(b[k]<=a[k]+TOL[k] for k in cols) and any(b[k]<a[k]-TOL[k] for k in cols)

def pareto(a,b,cols):
 ab,ba=dom(a,b,cols),dom(b,a,cols)
 if ab!=ba: return ('ordered',1 if ab else -1)
 if all(abs(a[k]-b[k])<=TOL[k] for k in cols):return ('tie',0)
 return ('incomparable',0)

def individual(a,b,k):
 if not np.isfinite(a[k]) or not np.isfinite(b[k]):return ('missing',0)
 delta=a[k]-b[k]
 return ('tie',0) if abs(delta)<=TOL[k] else ('ordered',int(np.sign(delta)))

def natural(a,b):
 return b.L<a.L-TOL['L'] and all(b[k]<=a[k]+TOL[k] for k in ['C','U','B']) and b['T']>a['T']+TOL['T']

def run(source,out):
 out.mkdir(parents=True,exist_ok=True)
 source=source.resolve()
 results=source if (source/'manual_scored.csv').is_file() else source/'results'
 d=pd.read_csv(results/'manual_scored.csv')
 q=d[d.primary_candidate & d.reference_version.eq('original')].dropna(subset=ORIGINAL_SCALE).copy()
 assert len(q)==1002 and q.image.nunique()==107
 assert not q.duplicated(['image','worker']).any()
 assert np.isfinite(q[FEATURES].to_numpy()).all()
 q[['image','building','id','worker']+FEATURES].to_csv(out/'frozen_eligible_records.csv',index=False)
 original=pd.read_csv(results/'broad_lobo_pairs.csv')
 original['pair_id']=[pair_id(*r) for r in original[['image','a_worker','b_worker']].itertuples(index=False,name=None)]
 original_pair_set=set(original.pair_id);original_images=set(original.image)
 saved_scales=pd.read_csv(results/'broad_lobo_scales.csv').set_index('held_building')
 pairdata={}
 for im,g in q.groupby('image'):
  for (_,a),(_,b) in itertools.combinations(g.sort_values('worker').iterrows(),2):
   pairdata.setdefault((a.worker,b.worker),[]).append(dict(image=im,building=a.building,**{k:float(a[k]-b[k]) for k in FEATURES}))
 pairframes={k:pd.DataFrame(v) for k,v in pairdata.items()}
 rows=[];target_rows=[];scales=[];max_scale_difference=0.
 natural_keys=set()
 natural_orig=pd.read_csv(results/'natural_3d_alerts.csv').query("reference_version == 'original'")
 for r in natural_orig.itertuples():natural_keys.add((r.image,tuple(sorted([r.from_id,r.to_id]))))
 recovered_natural=set()
 for held,test in q.groupby('building'):
  train=q[q.building.ne(held)]
  recomputed=train.groupby('image')[ORIGINAL_SCALE+INTRINSIC].median().median().clip(lower=1e-12)
  sd=float(np.abs(recomputed[ORIGINAL_SCALE]-saved_scales.loc[held,ORIGINAL_SCALE]).max())
  max_scale_difference=max(max_scale_difference,sd)
  assert sd<1e-12
  # Frozen original scales are consumed, rather than silently recalibrated.
  scale=recomputed.copy();scale[ORIGINAL_SCALE]=saved_scales.loc[held,ORIGINAL_SCALE]
  scales.append(dict(held_building=held,training_images=train.image.nunique(),training_records=len(train),**scale.to_dict()))
  for im,g in test.groupby('image'):
   for (_,a),(_,b) in itertools.combinations(g.sort_values('worker').iterrows(),2):
    pid=pair_id(im,a.worker,b.worker)
    tr=pairframes[(a.worker,b.worker)];tr=tr[tr.building.ne(held)]
    ok=len(tr)>=3 and tr.building.nunique()>=2
    nr=natural(a,b);rn=natural(b,a)
    if nr or rn:recovered_natural.add((im,tuple(sorted([a.id,b.id]))))
    row=dict(pair_id=pid,image=im,building=held,a_id=a.id,b_id=b.id,a_worker=a.worker,b_worker=b.worker,
      shared_train_images=len(tr),shared_train_buildings=tr.building.nunique(),supported=ok,
      in_original_83_images=im in original_images,in_original_3494_pairs=pid in original_pair_set,
      **{'heldout_delta_'+k:float(a[k]-b[k]) for k in FEATURES})
    if ok:
     dif=tr[FEATURES].mean();s4=sum(dif[k]/scale[k] for k in CORE);lcn=dif.L/scale.L+dif.C/scale.C
     scores={'S0':dif.L,'S1':dif.LC,'S4':s4,'S5':s4+dif['T']/scale['T'],
       'S5_relative':s4+dif.T_relative/scale.T_relative,'LCn':lcn,'LCn_T':lcn+dif['T']/scale['T'],
       'LCn_G':lcn+.5*(dif[INTRINSIC[0]]/scale[INTRINSIC[0]]+dif[INTRINSIC[1]]/scale[INTRINSIC[1]])}
     row.update(scores)
     for s,v in scores.items():row['pred_'+s]=0 if abs(v)<=PRED_TOL else int(np.sign(v))
    rows.append(row)
    targets={label:individual(a,b,k) for label,k in [('I','L'),('C','C'),('U','U'),('B','B'),('T','T'),('F','F')]}
    targets['LCUB_Pareto']=pareto(a,b,CORE)
    targets['LCUBT_Pareto']=pareto(a,b,CORE+['T'])
    core_status,core_sign=targets['LCUB_Pareto'];tstatus,tsign=targets['T']
    cf=bool(core_status=='ordered' and tstatus=='ordered' and core_sign!=tsign)
    targets['original_natural_conflict_core']=('ordered',1 if nr else -1) if nr or rn else ('outside_stratum',0)
    targets['original_natural_conflict_T']=('ordered',-1 if nr else 1) if nr or rn else ('outside_stratum',0)
    targets['LCUB_T_conflict_core']=('ordered',core_sign) if cf else ('outside_stratum',0)
    targets['LCUB_T_conflict_T']=('ordered',tsign) if cf else ('outside_stratum',0)
    for t,(status,sign) in targets.items():target_rows.append(dict(pair_id=pid,image=im,building=held,target=t,target_status=status,expected_sign=sign,supported=ok))
 pairs=pd.DataFrame(rows);targets=pd.DataFrame(target_rows)
 assert recovered_natural==natural_keys and len(natural_keys)==116
 pairs.to_csv(out/'all_pairs_predictions.csv',index=False)
 targets.to_csv(out/'all_pair_targets.csv',index=False)
 pd.DataFrame(scales).to_csv(out/'frozen_and_intrinsic_train_scales.csv',index=False)
 # Exact original-domain verification, independent of target extension.
 origlab=targets[targets.target.eq('LCUB_Pareto') & targets.target_status.eq('ordered') & targets.supported]
 assert set(origlab.pair_id)==original_pair_set
 verify=original.merge(pairs[['pair_id']+ORIGINAL_SCHEMES],on='pair_id',validate='many_to_one').merge(origlab[['pair_id','expected_sign']],on='pair_id',suffixes=('_original','_new'),validate='many_to_one')
 error=max(float(np.abs(z.score_difference-z[s]).max()) for s,z in verify.groupby('scheme'))
 assert error<1e-10
 assert verify.expected_sign_original.eq(verify.expected_sign_new).all()
 check_pred=np.array([r[r['scheme']] for _,r in verify.iterrows()])
 check_acc=np.where(np.abs(check_pred)<=PRED_TOL,.5,(np.sign(check_pred)==verify.expected_sign_new).astype(float))
 assert np.array_equal(check_acc,verify.correct.to_numpy())

 supported=pairs[pairs.supported].copy()
 panels={'all_supported_pairs':supported,
  'original_83_images':supported[supported.in_original_83_images],
  'original_3494_pairs':supported[supported.in_original_3494_pairs]}
 cover=[];summ=[];imgrows=[];bldrows=[];effectrows=[];effectbld=[];influence=[]
 rng=np.random.default_rng(20261007)
 for panel,panel_pairs in panels.items():
  tpanel=targets[targets.pair_id.isin(set(panel_pairs.pair_id))]
  for target,tg in tpanel.groupby('target'):
   ordered=tg[tg.target_status.eq('ordered')]
   status_counts=tg.target_status.value_counts()
   cr=dict(panel=panel,target=target,total_supported_pairs=len(tg),total_images=tg.image.nunique(),total_buildings=tg.building.nunique(),
    ordered_pairs=len(ordered),ordered_images=ordered.image.nunique(),ordered_buildings=ordered.building.nunique())
   for status in ['tie','incomparable','missing','outside_stratum']:cr[status+'_pairs']=int(status_counts.get(status,0))
   cr['ordered_fraction']=len(ordered)/len(tg)
   cover.append(cr)
   if not len(ordered):continue
   z=ordered.merge(panel_pairs[['pair_id']+['pred_'+s for s in SCHEMES]],on='pair_id',validate='one_to_one')
   for s in SCHEMES:
    pred=z['pred_'+s].to_numpy();expected=z.expected_sign.to_numpy()
    acc=np.where(pred==0,.5,(pred==expected).astype(float))
    az=z[['pair_id','image','building']].copy();az['accuracy']=acc;az['prediction_tie']=(pred==0).astype(float)
    im=az.groupby(['building','image']).agg(n_pairs=('accuracy','size'),accuracy=('accuracy','mean'),prediction_tie_rate=('prediction_tie','mean')).reset_index()
    bd=im.groupby('building').agg(n_images=('image','size'),n_pairs=('n_pairs','sum'),accuracy=('accuracy','mean'),prediction_tie_rate=('prediction_tie_rate','mean')).reset_index()
    for frame,accum in [(im,imgrows),(bd,bldrows)]:
     frame['panel']=panel;frame['target']=target;frame['scheme']=s;accum.append(frame)
    tieids=tg[tg.target_status.eq('tie')].pair_id
    ties=panel_pairs[panel_pairs.pair_id.isin(tieids)]
    summ.append(dict(panel=panel,target=target,scheme=s,buildings=len(bd),images=len(im),ordered_pairs=len(z),
      building_equal_accuracy=bd.accuracy.mean(),image_equal_accuracy=im.accuracy.mean(),pair_pooled_accuracy_not_headline=float(acc.mean()),
      ordered_prediction_ties=int((pred==0).sum()),target_tie_pairs=len(ties),
      predicted_ties_on_target_ties=int(ties['pred_'+s].eq(0).sum())))
   recent=pd.concat(bldrows[-len(SCHEMES):],ignore_index=True)
   wide=recent.pivot(index='building',columns='scheme',values='accuracy')
   counts=recent.drop_duplicates('building').set_index('building')[['n_images','n_pairs']]
   draws=rng.integers(len(wide),size=(10000,len(wide)))
   for model,baseline in CONTRASTS:
    effect=wide[model]-wide[baseline];vals=effect.to_numpy();mean=float(vals.mean())
    boots=vals[draws].mean(axis=1);bootlo,boothi=np.quantile(boots,[.025,.975])
    leave=[]
    for building,value in effect.items():
     others=effect.drop(building);loo=float(others.mean()) if len(others) else np.nan;leave.append(loo)
     effectbld.append(dict(panel=panel,target=target,model=model,baseline=baseline,building=building,
       n_images=int(counts.loc[building,'n_images']),n_pairs=int(counts.loc[building,'n_pairs']),
       model_accuracy=float(wide.loc[building,model]),baseline_accuracy=float(wide.loc[building,baseline]),paired_delta=float(value)))
     influence.append(dict(panel=panel,target=target,model=model,baseline=baseline,omitted_building=building,
       full_delta=mean,leave_one_observed_building_out_delta=loo,change_from_full=loo-mean,
       refitted_predictions=False))
    effectrows.append(dict(panel=panel,target=target,model=model,baseline=baseline,buildings=len(effect),
      paired_delta=mean,buildings_gain=int((effect>1e-12).sum()),buildings_loss=int((effect< -1e-12).sum()),buildings_tie=int((np.abs(effect)<=1e-12).sum()),
      descriptive_cluster_percentile_025=bootlo,descriptive_cluster_percentile_975=boothi,
      leave_one_building_min=np.nanmin(leave),leave_one_building_max=np.nanmax(leave),
      not_population_confidence_interval=True))
 coverage=pd.DataFrame(cover);summary=pd.DataFrame(summ);effects=pd.DataFrame(effectrows)
 coverage.to_csv(out/'target_coverage.csv',index=False)
 summary.to_csv(out/'target_score_summary.csv',index=False)
 pd.concat(imgrows,ignore_index=True).to_csv(out/'target_score_per_image.csv',index=False)
 pd.concat(bldrows,ignore_index=True).to_csv(out/'target_score_per_building.csv',index=False)
 effects.to_csv(out/'paired_effect_summary.csv',index=False)
 pd.DataFrame(effectbld).to_csv(out/'paired_effect_per_building.csv',index=False)
 pd.DataFrame(influence).to_csv(out/'leave_one_building_influence.csv',index=False)
 # Persist target-outcome composition and flip counts independently of score performance.
 statuses=targets.pivot(index='pair_id',columns='target',values='target_status')
 signs=targets.pivot(index='pair_id',columns='target',values='expected_sign')
 transitions=[]
 for panel,pp in panels.items():
  for target in ['I','C','U','B','T','F','LCUBT_Pareto']:
   for cs in ['ordered','tie','incomparable']:
    ids=pp.pair_id[pp.pair_id.map(statuses.LCUB_Pareto).eq(cs)]
    ss=statuses.loc[ids,target];sg=signs.loc[ids,target];cg=signs.loc[ids,'LCUB_Pareto']
    transitions.append(dict(panel=panel,source_LCUB_status=cs,target=target,pairs=len(ids),
      target_ordered=int(ss.eq('ordered').sum()),target_tie=int(ss.eq('tie').sum()),target_incomparable=int(ss.eq('incomparable').sum()),
      opposite_LCUB_order=int((ss.eq('ordered') & (sg!=cg)).sum()) if cs=='ordered' else np.nan))
 pd.DataFrame(transitions).to_csv(out/'target_transition_counts.csv',index=False)
 original_summary=pd.read_csv(results/'broad_lobo_summary.csv').set_index('scheme').building_equal_accuracy
 check_summary=summary[(summary.panel=='all_supported_pairs') & (summary.target=='LCUB_Pareto')].set_index('scheme').building_equal_accuracy
 summary_error=float(np.abs(check_summary[ORIGINAL_SCHEMES]-original_summary[ORIGINAL_SCHEMES]).max())
 assert summary_error<1e-12
 # No model-specific pair pruning is allowed.
 assert summary.groupby(['panel','target']).ordered_pairs.nunique().eq(1).all()
 manifest=dict(experiment='target_sensitivity',completed=True,source=str(source),
   frozen_eligible_records=len(q),frozen_eligible_images=q.image.nunique(),frozen_eligible_buildings=q.building.nunique(),
   possible_pairs=len(pairs),supported_pairs=len(supported),supported_images=supported.image.nunique(),supported_buildings=supported.building.nunique(),
   excluded_for_training_support=int((~pairs.supported).sum()),
   original_pairs_matched=len(original_pair_set),original_natural_conflicts_matched=len(natural_keys),
   original_score_difference_max_error=error,original_scale_max_error=max_scale_difference,original_summary_max_error=summary_error,
   all_schemes_share_target_denominators=True,intrinsic_complete_records=len(q),
   descriptive_bootstrap_replicates=10000,bootstrap_seed=20261007,
   completed_checks=['original eligibility','worker/image uniqueness','frozen scales','all original pair predictions and labels','original weighted summaries','116 original natural conflicts','identical model comparison denominators'],
   limits=['Historical reference-based numerical targets, not human overall-quality labels.','Eligibility is conditioned on metric availability; values from the held building are not used for training/calibration.','Leave-one-building influence deletes observed summary clusters; it does not refit models.','Bootstrap conditions on fitted predictions and the observed panel; no new-population or training uncertainty claim.','Original five scores frozen; LCn/LCn_T/LCn_G fixed exploratory additions declared before results.'])
 save_json(out/'EXECUTION.json',manifest)
 print(json.dumps(manifest,ensure_ascii=False,indent=2))
 print('\nALL-SUPPORTED TARGET SUMMARY (%)\n'+(100*summary[summary.panel.eq('all_supported_pairs')].pivot(index='target',columns='scheme',values='building_equal_accuracy')).round(3).to_string())
 print('\nTARGET COVERAGE\n'+coverage[coverage.panel.eq('all_supported_pairs')].to_string(index=False))
 print('\nPREDECLARED INCREMENTAL EFFECTS (fractions)\n'+effects[(effects.panel=='all_supported_pairs') & (((effects.model=='S5') & (effects.baseline=='S4')) | ((effects.model.isin(['LCn_T','LCn_G'])) & (effects.baseline=='LCn')))].to_string(index=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=DEFAULT_SOURCE,help='Extracted compact package root or its results directory');p.add_argument('--out',type=Path,default=HERE,help='Directory for generated experiment outputs')
 args=p.parse_args();run(args.source,args.out)
