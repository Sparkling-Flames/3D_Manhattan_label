"""Same-initializer two-way FE and building-held-out Manual-Q transfer.

Main learning panel: current ordinary_primary Semi, no original holdout,
no personnel/context barriers, no researcher point repair. All source records
remain in descriptive ledgers. Native-order and special-reference variants are
diagnostics, never alternatives chosen to maximize a result.
"""
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
from paths import ROOT,REPO,OUT,STUDY
sys.path.insert(0,str(STUDY/'q'))
from analyze_q import fit_worker_effects,save_csv,save_json
SEED=20261017

def metric_summary(d,prediction_cols,meta):
 rows=[];brows=[]
 for name in prediction_cols:
  by=d.groupby('building_id')[['baseline_sqerr',name+'_sqerr']].mean()
  base=by.baseline_sqerr.to_numpy();err=by[name+'_sqerr'].to_numpy()
  lo=hi=None
  if len(by)>=5 and base.mean()>0:
   ix=np.random.default_rng(SEED).integers(0,len(by),(2000,len(by)))
   boots=1-err[ix].mean(1)/base[ix].mean(1);lo,hi=np.quantile(boots,[.025,.975])
  rows.append(dict(**meta,method=name,rows=len(d),workers=d.worker_id.nunique(),contexts=d.context_key.nunique(),buildings=len(by),
   baseline_building_mean_mse=base.mean(),method_building_mean_mse=err.mean(),building_equal_reduction=1-err.mean()/base.mean() if base.mean()>0 else None,
   improved_buildings=int((err<base).sum()),bootstrap95_low=lo,bootstrap95_high=hi,
   bootstrap_note='Exploratory building-cluster resampling of held-out errors; no profile refitting inside error-summary bootstrap.' if len(by)>=5 else 'Fewer than five buildings: no nominal interval reported.'))
  for b,g in by.iterrows():brows.append(dict(**meta,method=name,building_id=b,rows=int(d.building_id.eq(b).sum()),baseline_mse=g.baseline_sqerr,method_mse=g[name+'_sqerr'],difference=g[name+'_sqerr']-g.baseline_sqerr))
 return rows,brows

def predict_common(test,manual,semi,axis):
 qm=manual[manual.supported & manual.label.ne('unclassified')][['worker_id','effect','label']].copy()
 sm=semi[semi.supported & semi.label.ne('unclassified')][['worker_id','effect','label']].copy()
 for p in [qm,sm]:p['class_effect']=p.groupby('label').effect.transform('mean')
 qm=qm.rename(columns={c:'manual_'+c for c in ['effect','label','class_effect']})
 sm=sm.rename(columns={c:'semi_'+c for c in ['effect','label','class_effect']})
 d=test.merge(qm,on='worker_id').merge(sm,on='worker_id')
 d=d[d.groupby('context_key').worker_id.transform('nunique').ge(2)].copy()
 if d.empty:return d
 d['target']=d[axis]-d.groupby('context_key')[axis].transform('mean')
 d['baseline_sqerr']=d.target**2
 for method,col in [('manual_Q_transfer','manual_effect'),('manual_Q_signclass','manual_class_effect'),('semi_effect','semi_effect'),('semi_signclass','semi_class_effect')]:
  d[method+'_prediction']=d[col]-d.groupby('context_key')[col].transform('mean')
  d[method+'_sqerr']=(d.target-d[method+'_prediction'])**2
 return d

def main():
 s=pd.read_csv(OUT/'semi_scores_b8l2_d10.csv')
 gates=pd.DataFrame(json.loads((REPO/'research/workers/worker_b8l2_d10_20261017/admission_snapshot.json').read_text()))
 s=s.merge(gates[['object_id','personnel_barriers','context_barriers']],on='object_id',validate='one_to_one')
 fullq=pd.read_csv(STUDY/'q/worker_profiles_enriched.csv')
 fullq=fullq[fullq.axis.eq('B8L2')].set_index('worker_id')
 assert fullq.index.is_unique and len(fullq)==24
 qfold=pd.read_csv(STUDY/'q/fold_profiles_recomputed.csv')
 qfold=qfold[qfold.panel.eq('current')&qfold.axis.isin(['B8L2','D10'])]
 s['context_key']=s.initialization_context_key
 candidate=s[s.semi_profile_training_candidate]
 assert candidate.personnel_barriers.map(len).eq(0).all() and candidate.context_barriers.map(len).eq(0).all()
 assert candidate.independent_vote_eligible.all() and candidate.cleaning_disposition.eq('retained').all()
 ordinary=s[s.semi_ordinary_profile_training_candidate].copy()
 withspecial=s[s.semi_profile_training_candidate].copy()
 qualified=s[s.current_qualified_gain_available & s.current_quality_use.eq('ordinary_primary')].copy()
 assert len(ordinary)==409 and len(withspecial)==433 and len(qualified)==437
 variants={'ordinary_main':ordinary,'with_special_sensitivity':withspecial}
 profiles=[];diagnostics=[];predictions=[];equivalence=[]
 folds=sorted(qualified.building_id.unique())
 for variant,train in variants.items():
  for axis in ['B8L2','D10']:
   train=train.assign(**{axis:train['final_'+axis]})
   gaintrain=train.assign(**{axis:train['worker_attributable_gain_'+axis]})
   for fold in [None,*folds]:
    sf,diag=fit_worker_effects(train,axis,fold);gf,gdiag=fit_worker_effects(gaintrain,axis,fold)
    assert sf.worker_id.tolist()==gf.worker_id.tolist()
    maxdiff=float((sf.effect-gf.effect).abs().max())
    assert maxdiff<1e-9,(variant,axis,fold,maxdiff)
    equivalence.append(dict(panel=variant,axis=axis,fold=fold or 'full_descriptive',final_vs_gain_effect_max_abs=maxdiff))
    sf['panel']=variant;profiles.append(sf);diag['panel']=variant;diagnostics.append(diag)
    if fold is None:continue
    qf=qfold[qfold.axis.eq(axis)&qfold.fold.eq(fold)]
    assert not qf.empty,(axis,fold,'manual_Q_fold_missing')
    for cohort,test in [('development_lobo',ordinary[ordinary.building_id.eq(fold)]),('original_holdout',qualified[qualified.original_holdout&qualified.building_id.eq(fold)])]:
     if test.empty:continue
     test=test.assign(**{axis:test['final_'+axis]})
     d=predict_common(test,qf,sf,axis)
     if d.empty:continue
     d['panel']=variant;d['axis']=axis;d['cohort']=cohort;d['fold']=fold
     # Same initializer/reference subtracts a task constant, so gain and final
     # have exactly the same relative target on precisely these same rows.
     gain_target=d['worker_attributable_gain_'+axis]-d.groupby('context_key')['worker_attributable_gain_'+axis].transform('mean')
     assert float((gain_target-d.target).abs().max())<1e-9
     predictions.append(d)
 prof=pd.concat(profiles,ignore_index=True);pred=pd.concat(predictions,ignore_index=True)
 save_csv(OUT/'semi_fold_profiles.csv',prof)
 save_csv(OUT/'semi_fit_diagnostics.csv',diagnostics)
 save_csv(OUT/'semi_final_gain_effect_equivalence.csv',equivalence)
 columns=['object_id','worker_id','image_id','image_code','building_id','runtime_initialization_kind','context_key','panel','axis','cohort','fold','target','manual_label','semi_label','baseline_sqerr']+[m+x for m in ['manual_Q_transfer','manual_Q_signclass','semi_effect','semi_signclass'] for x in ['_prediction','_sqerr']]
 save_csv(OUT/'semi_lobo_predictions.csv',pred[columns])
 performance=[];bybuilding=[]
 for key,d in pred.groupby(['panel','axis','cohort']):
  a,b=metric_summary(d,['manual_Q_transfer','manual_Q_signclass','semi_effect','semi_signclass'],dict(zip(['panel','axis','cohort'],key)));performance+=a;bybuilding+=b
 save_csv(OUT/'semi_lobo_performance.csv',performance);save_csv(OUT/'semi_lobo_by_building.csv',bybuilding)
 strata=[]
 # Report identical fixed models by initializer origin. These are diagnostics,
 # not new classifiers or tuned initial-deficit thresholds.
 for key,d in pred[pred.panel.eq('ordinary_main')].groupby(['axis','cohort','runtime_initialization_kind']):
  a,_=metric_summary(d,['manual_Q_transfer','semi_effect'],dict(zip(['axis','cohort','initialization_kind'],key)));strata+=a
 save_csv(OUT/'semi_lobo_source_strata.csv',strata)
 descriptive=[]
 for pool,d in [('all_same_reference_scorable',s[s.paired_score_available]),('ordinary_current_attributable',qualified),('special_current_attributable',s[s.current_qualified_gain_available&s.current_quality_use.eq('special_conditional_only')])]:
  for kind,g in d.groupby('runtime_initialization_kind'):
   r=dict(pool=pool,initialization_kind=kind,n=len(g),workers=g.worker_id.nunique(),images=g.image_id.nunique(),buildings=g.building_id.nunique(),ring_existing_verified=int(g.initial_ring_status.eq('existing_confirmed_ring_exact_point_identity').sum()))
   for axis in ['B8L2','D10']:
    for pre in ['initial_','final_','worker_attributable_gain_','residual_score_deficit_']:r[pre+axis+'_mean']=g[pre+axis].mean()
   descriptive.append(r)
 save_csv(OUT/'semi_source_quality_summary.csv',descriptive)
 correction=pd.read_csv(OUT/'worker_correction_summary.csv').set_index('worker_id')
 allworkers=sorted(correction.index);rows=[]
 primaryprof=prof[prof.panel.eq('ordinary_main')]
 for w in allworkers:
  g=s[s.worker_id.eq(w)];d=qualified[qualified.worker_id.eq(w)]
  row=correction.loc[w].to_dict();row['worker_id']=w
  row.update(n_initial_scorable=int(g.initial_score_status.eq('complete').sum()),n_final_scorable=int(g.final_score_status.eq('complete').sum()),n_final_unscorable=int(g.final_score_status.ne('complete').sum()),
   n_pair_scorable=int(g.paired_score_available.sum()),n_unchanged_coordinates=int(g.recovered_edit_status.eq('unchanged_coordinates').sum()),n_changed_coordinates=int(g.recovered_edit_status.eq('changed_coordinates').sum()),
   n_restored_prior_not_checked=int(g.source_prior_not_checked.sum()),n_existing_ring_verified=int(g.initial_ring_status.eq('existing_confirmed_ring_exact_point_identity').sum()),n_native_ring_unconfirmed=int(g.initial_ring_status.eq('native_initialization_ring_unconfirmed').sum()),
   n_researcher_point_repairs=int(g.researcher_point_repair_applied.sum()),n_current_quality_final=int(g.current_quality_usable.sum()),n_current_quality_attributable=int(g.current_qualified_gain_available.sum()),
   n_ordinary_attributable=len(d),n_ordinary_training=int(g.semi_ordinary_profile_training_candidate.sum()),n_special_training=int(g.semi_special_profile_training_candidate.sum()),
   n_ordinary_original_holdout=int(d.original_holdout.sum()),ordinary_attributable_images=d.image_id.nunique(),ordinary_attributable_buildings=d.building_id.nunique())
  for axis in ['B8L2','D10']:
   for p in ['initial_','final_','worker_attributable_gain_','residual_score_deficit_']:row['ordinary_'+p+axis+'_mean']=d[p+axis].mean()
   row['ordinary_final_'+axis+'_p10']=d['final_'+axis].quantile(.1)
   row['ordinary_gain_'+axis+'_median']=d['worker_attributable_gain_'+axis].median()
   row['ordinary_gain_'+axis+'_positive_count']=int(d['worker_attributable_gain_'+axis].gt(1e-8).sum())
   row['ordinary_gain_'+axis+'_negative_count']=int(d['worker_attributable_gain_'+axis].lt(-1e-8).sum())
   p=primaryprof[primaryprof.worker_id.eq(w)&primaryprof.axis.eq(axis)];full=p[p.fold.eq('full_descriptive')];fs=p[~p.fold.eq('full_descriptive')&p.supported]
   if len(full):
    f=full.iloc[0];row.update({f'semi_{axis}_effect':f.effect,f'semi_{axis}_supported':f.supported,f'semi_{axis}_label':f.label,f'semi_{axis}_contexts':f.contexts,f'semi_{axis}_buildings':f.buildings})
   else:row.update({f'semi_{axis}_effect':None,f'semi_{axis}_supported':False,f'semi_{axis}_label':'unclassified',f'semi_{axis}_contexts':0,f'semi_{axis}_buildings':0})
   row.update({f'semi_{axis}_LOBO_supported_folds':len(fs),f'semi_{axis}_LOBO_effect_min':fs.effect.min(),f'semi_{axis}_LOBO_effect_max':fs.effect.max(),f'semi_{axis}_LOBO_positive_folds':int(fs.effect.gt(0).sum())})
  if w in fullq.index:
   q=fullq.loc[w];row.update(manual_Q_effect=q.effect,manual_Q_label=q.label,manual_Q_semi_sign_disagree=(q.label!=row['semi_B8L2_label']) if row['semi_B8L2_supported'] else None)
  else:row.update(manual_Q_effect=None,manual_Q_label='unclassified',manual_Q_semi_sign_disagree=None)
  row['semi_B8L2_D10_sign_disagree']=row['semi_B8L2_label']!=row['semi_D10_label']
  row['correction_evidence_candidate']='known_initial_defect_persisted_on_observed_tasks' if row['n_known_error_unchanged'] else 'no_unchanged_known_defect_observed_but_edit_outcomes_unknown' if row['n_initialization_error_opportunities'] else 'no_confirmed_initial_error_opportunity'
  rows.append(row)
 workers=pd.DataFrame(rows);save_csv(OUT/'worker_semi_summary.csv',workers)
 equivmax=max(x['final_vs_gain_effect_max_abs'] for x in equivalence)
 receipt=dict(data_release='v1',ordinary_training_rows=len(ordinary),ordinary_training_images=ordinary.image_id.nunique(),ordinary_training_contexts=ordinary.context_key.nunique(),ordinary_training_buildings=ordinary.building_id.nunique(),
  special_sensitivity_additional_rows=len(withspecial)-len(ordinary),ordinary_current_attributable_rows=len(qualified),original_holdout_rows=int(qualified.original_holdout.sum()),
  original_holdout_images=qualified[qualified.original_holdout].image_id.nunique(),original_holdout_buildings=qualified[qualified.original_holdout].building_id.nunique(),
  empty_personnel_and_context_barriers_asserted_for_all_training=True,no_researcher_point_repair_credited=True,
  final_gain_context_adjusted_effect_max_abs_difference=equivmax,
  manual_Q_vs_Semi_sign_changes=workers.loc[workers.manual_Q_semi_sign_disagree.eq(True),'worker_id'].tolist(),
  B8L2_D10_Semi_sign_changes=workers.loc[workers.semi_B8L2_D10_sign_disagree,'worker_id'].tolist(),
  main24_error_opportunities=int(workers.loc[workers.worker_id.isin(fullq.index),'n_initialization_error_opportunities'].sum()),
  main24_known_error_unchanged=int(workers.loc[workers.worker_id.isin(fullq.index),'n_known_error_unchanged'].sum()),
  limits=['Semi effects are exploratory task-adjusted application-specific diagnostics, with original eligibility unchanged.','Current task role held_or_diagnostic is preserved; 394 P1 candidates have no personnel/context barriers.','All gain summaries use compatible ring/reference measurement views; 413 inventory initializers have native ring without an exact-coordinate confirmed ring source. Screen rendering was not re-created.','Final and gain effects are algebraically redundant within exact image/condition/reference/initializer task contexts.','Relative held-out targets subtract peer means from held-out outcomes for evaluation; this does not provide absolute new-image quality prediction.','Original holdout is only two images in two buildings; retain it separately and do not claim population transport.','Class sign boundaries are inherited descriptive candidates; no search for thresholds or stable permanent worker populations was used.'])
 save_json(OUT/'semi_analysis_receipt.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
