"""Limited building-held-out scope diagnostics on explicitly adjudicated tasks.

No unknown task is a negative. Main current-compatible endpoint is false
rejection of a clear, historically adjudicated in-scope Manual task. Historical
protocol endpoints stay labelled historical. Linear task-adjusted rejection
effects are converted to clipped probabilities only for Brier diagnostics.
"""
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
from paths import ROOT,REPO,OUT,STUDY
sys.path.insert(0,str(STUDY/'q'))
from analyze_q import fit_worker_effects,save_csv,save_json

def main():
 f=pd.read_csv(OUT/'scope_object_ledger.csv').fillna({'historical_later_hold':''})
 q=pd.read_csv(STUDY/'q/worker_profiles_enriched.csv');workers=set(q.worker_id)
 f=f[f.worker_id.isin(workers)]
 assert len(workers)==24
 panels={'current_clear_manual':(f[f.condition.eq('manual')&f.current_clear_in_scope_adjudicated],'current_compatible_outcome'),
  'current_clear_semi':(f[f.condition.eq('semi')&f.current_clear_in_scope_adjudicated],'current_compatible_outcome'),
  'historical_manual':(f[f.condition.eq('manual')&f.historical_eligible],'historical_outcome'),
  'historical_oos':(f[f.condition.eq('oos')&f.historical_eligible],'historical_outcome'),
  'historical_semi':(f[f.condition.eq('semi')&f.historical_eligible],'historical_outcome'),
  'narrow_historical_representation_oos':(f[f.historical_representation_oos_narrow],'narrow_historical_representation_outcome')}
 profiles=[];preds=[];coverage=[];fits=[]
 for name,(d,col) in panels.items():
  d=d[d[col].isin(['false_rejection','false_acceptance','correct_acceptance','correct_rejection'])].copy()
  d['scope_error']=d[col].isin(['false_rejection','false_acceptance']).astype(float)
  d['context_key']=d.scope_context_key
  train=d[~d.original_holdout].copy()
  coverage.append(dict(panel=name,rows=len(d),workers=d.worker_id.nunique(),contexts=d.context_key.nunique(),buildings=d.building_id.nunique(),errors=int(d.scope_error.sum()),
   unknown_responses_removed=0,original_holdout_rows=int(d.original_holdout.sum()),data_role='current-compatible explicit adjudication' if name=='current_clear_manual' else 'limited or historical-protocol diagnostic'))
  for fold in [None,*sorted(d.building_id.unique())]:
   p,diag=fit_worker_effects(train,'scope_error',fold);p['panel']=name;diag['panel']=name;profiles.append(p);fits.append(diag)
   if fold is None:continue
   p=p[p.supported].copy()
   if p.empty:continue
   baseline=float(train.loc[train.building_id.ne(fold),'scope_error'].mean())
   p['class_effect']=p.groupby('label').effect.transform('mean')
   test=d[d.building_id.eq(fold)].merge(p[['worker_id','effect','class_effect','label']],on='worker_id')
   if test.empty:continue
   test['baseline_probability']=baseline;test['effect_probability']=(baseline+test.effect).clip(0,1);test['class_probability']=(baseline+test.class_effect).clip(0,1)
   for m in ['baseline','effect','class']:test[m+'_brier']=(test.scope_error-test[m+'_probability'])**2
   test['fold']=fold;test['panel']=name;preds.append(test)
 save_csv(OUT/'scope_validation_coverage.csv',coverage);save_csv(OUT/'scope_fold_profiles.csv',pd.concat(profiles,ignore_index=True));save_csv(OUT/'scope_fit_diagnostics.csv',fits)
 pred=pd.concat(preds,ignore_index=True)
 save_csv(OUT/'scope_lobo_predictions.csv',pred[['object_id','worker_id','image_id','image_code','building_id','panel','fold','scope_error','effect','label','original_holdout']+[m+x for m in ['baseline','effect','class'] for x in ['_probability','_brier']]])
 perf=[];buildingrows=[]
 for panel,d in pred.groupby('panel'):
  for method in ['effect','class']:
   by=d.groupby('building_id')[['baseline_brier',method+'_brier']].mean();base=by.baseline_brier.to_numpy();e=by[method+'_brier'].to_numpy()
   ci=[None,None]
   if len(by)>=5:
    rng=np.random.default_rng(20261017);ix=rng.integers(0,len(by),(2000,len(by)));boot=1-e[ix].mean(1)/base[ix].mean(1);ci=np.quantile(boot,[.025,.975]).tolist()
   perf.append(dict(panel=panel,method=method,rows=len(d),workers=d.worker_id.nunique(),images=d.image_id.nunique(),buildings=len(by),errors=int(d.scope_error.sum()),baseline_building_equal_brier=base.mean(),method_building_equal_brier=e.mean(),building_equal_reduction=1-e.mean()/base.mean(),improved_buildings=int((e<base).sum()),bootstrap95_low=ci[0],bootstrap95_high=ci[1]))
   for b,g in by.iterrows():buildingrows.append(dict(panel=panel,method=method,building_id=b,baseline_brier=g.baseline_brier,method_brier=g[method+'_brier'],difference=g[method+'_brier']-g.baseline_brier))
 save_csv(OUT/'scope_lobo_performance.csv',perf);save_csv(OUT/'scope_lobo_by_building.csv',buildingrows)
 unsupported=[x for x in coverage if x['panel'] not in set(pred.panel)]
 receipt=dict(data_release='v1',validation_membership='24 current Manual-Q workers; all their judged scope responses retained regardless of final layout acceptance',
  unchanged_support_requirement='at least 6 distinct task contexts and 3 buildings outside the held building',
  no_supported_LOBO_panels=[x['panel'] for x in unsupported],
  unsupported_reason='current_clear_semi has only three contexts; narrow representation OOS has six total, so every building holdout leaves fewer than six.',
  limits=['Scope gold is task-specific. Historical protocol outcomes are not promoted to current whole-space correctness.','Probabilities are clipped outside-building global task-error rate plus two-way task-adjusted worker effect; no probability calibration fitting or threshold search.','Brier results describe this small selected task panel only; intervals are building-bootstrap diagnostics of held-out errors, not population guarantees.','No scope classifier is used to re-admit excluded votes or to impose extra deductions on a duplicate severe-error event.'])
 save_json(OUT/'scope_validation_receipt.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
