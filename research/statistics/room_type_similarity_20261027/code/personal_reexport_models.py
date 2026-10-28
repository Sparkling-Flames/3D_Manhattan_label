#!/usr/bin/env python3
"""Re-export full OOF from complete frozen fitted five-feature models.
No fit, hyperparameter selection, or response eligibility is changed.
"""
import os,argparse,gzip,json,hashlib,shutil,time
from pathlib import Path
import numpy as np,pandas as pd
from personal import FrozenFeatures,centered_prediction,rel_target,history_table,save,summarize,repeatability,MODEL_FEATURES

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();p=a.out
 d=pd.read_csv(a.inputs/'annotations.csv.gz',dtype={'object_id':str},low_memory=False)
 d=d[(d.condition=='manual')&(d.layer=='ordinary')&d.formal_quality&d.Q.notna()&d.D10.notna()].copy()
 d['room_type_model']=d.room_type_model.fillna('__MISSING__');d['difficulty']=d.difficulty.fillna('__UNKNOWN__')
 full={};models_manifest=[]
 five=['ref_turn5','ref_short_edges','ref_min_horizontal_deg','ref_radius_p90_h','ref_H']
 for oc in ['Q','D10','annotation_turn5']:
  f=p/f'MODELS_{oc}.jsonl.gz'
  with gzip.open(f,'rt') as z:models=[json.loads(x) for x in z]
  assert len(models)==88 and len({(x['held_out_building'],x['method']) for x in models})==88
  assert all(x['feature_schema']['numeric_cols']==five for x in models)
  ft=pd.read_csv(p/f'FOLDS_{oc}.csv')
  mapped={(x['held_out_building'],x['method']):x for x in models}
  assert all(r.alpha==mapped[r.held_out_building,r.method]['alpha'] for r in ft.itertuples())
  if oc!='D10':
   cv=pd.read_csv(p/f'INNER_CV_{oc}.csv.gz')
   assert len(cv)==2200
   for key,g in cv.groupby(['held_out_building','method']):
    loss=g.groupby('alpha').apply(lambda q:np.average(q.image_mse,weights=q.validation_images),include_groups=False)
    assert loss.idxmin()==mapped[key]['alpha']
  full[oc]=mapped
  models_manifest.append({'outcome':oc,'rows':len(models),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'numeric_reference_predictors':five})
 hist=p/'history_invalid_concurrent_outputs';hist.mkdir(exist_ok=True)
 retained={'MODELS_Q.jsonl.gz','MODELS_D10.jsonl.gz','MODELS_annotation_turn5.jsonl.gz','FOLDS_Q.csv','FOLDS_D10.csv','FOLDS_annotation_turn5.csv','INNER_CV_Q.csv.gz','INNER_CV_annotation_turn5.csv.gz','METHOD_RECEIPT.json'}
 for f in list(p.iterdir()):
  if f.is_file() and f.name not in retained:shutil.move(str(f),str(hist/f.name))
 allP=[];allH=[]
 for oc,models in full.items():
  t=d[d[oc].notna()].copy().reset_index(drop=True);t['relative']=rel_target(t,oc);t=t[t.relative.notna()].copy()
  predictions=[];histories=[]
  for held in sorted(t.building.unique()):
   train=t[t.building!=held].copy();test=t[t.building==held].copy()
   hs=history_table(train,test,'relative');hs['outcome']=oc;histories.append(hs)
   bases={'zero':np.zeros(len(test)),
          'person_history':centered_prediction(hs.history_person_mean.fillna(0).to_numpy(),test),
          'same_purpose_history':centered_prediction(hs.history_same_purpose_mean.fillna(hs.history_person_mean).fillna(0).to_numpy(),test)}
   for method in MODEL_FEATURES:
    m=models[(held,method)];s=m['feature_schema'];f=FrozenFeatures(tuple(s['parts']),s['numeric_cols'])
    f.workers=s['workers'];f.wmap={x:i for i,x in enumerate(f.workers)};f.cats=s['categories'];f.means=s['means'];f.scales=s['scales'];f.medians=s['medians'];f.missing_cols=s['missing_cols']
    X=f.transform(test);coef=np.asarray(m['coef']);assert X.shape[1]==len(coef)
    bases[method]=centered_prediction(X@coef,test)
   for method,pred in bases.items():
    z=test[['object_id','image_key','image','building','worker_id','room_type_model','room_type_status','difficulty']].copy()
    z['outcome']=oc;z['method']=method;z['observed']=test[oc].to_numpy();z['actual_relative']=test.relative.to_numpy();z['predicted_relative']=pred
    z['error']=pred-z.actual_relative;z['absolute_error']=abs(z.error);z['squared_error']=z.error**2
    z['same_purpose_history_buildings']=hs.same_purpose_n_buildings.to_numpy();z['history_buildings']=hs.person_n_buildings.to_numpy();predictions.append(z)
  P=pd.concat(predictions,ignore_index=True);H=pd.concat(histories,ignore_index=True)
  assert len(P)==len(t)*7 and not P[['object_id','method']].duplicated().any()
  save(P,p/f'OOF_{oc}.csv.gz');save(H,p/f'HISTORY_SUPPORT_{oc}.csv.gz');allP.append(P);allH.append(H)
 P=pd.concat(allP);H=pd.concat(allH);summarize(P,p);repeatability(P,H,p)
 checks=[]
 for f in sorted(p.iterdir()):
  if f.is_file() and (f.name.endswith('.csv') or f.name.endswith('.csv.gz')):
   x=pd.read_csv(f);checks.append({'file':f.name,'rows':len(x),'fields':len(x.columns),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 receipt={'status':'complete','regeneration':'re-export from fully parsed saved five-reference-feature fitted models; no fitting and no hyperparameter change',
  'records':len(d),'images':d.image_key.nunique(),'buildings':d.building.nunique(),'people':d.worker_id.nunique(),'OOF_rows':len(P),
  'input_sha256':hashlib.sha256((a.inputs/'annotations.csv.gz').read_bytes()).hexdigest(),'models':models_manifest,'csv_EOF_checked':checks,
  'obsolete_output_dir_not_for_packaging':'history_invalid_concurrent_outputs',
  'initial_design_alias_correction':'Before final-model interpretation, resolved actual frozen field names ref_min_horizontal_deg and ref_radius_p90_h; two export writers overlapped, now both original fit processes confirmed exit0 and no process remains.',
  'former_fit_tool_sessions':[49443,42181],'active_fit_processes_before_regeneration':0,
  'baseline_peer_target':'excludes target person; other formally evaluable same-image responses used only as evaluation outcome',
  'target_predictions_centered_abs_max':float(P.groupby(['outcome','method','image_key']).predicted_relative.mean().abs().max())}
 (p/'COMPLETE_FINAL.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 print(pd.read_csv(p/'METHOD_SUMMARY.csv').to_string(index=False))
if __name__=='__main__':main()
