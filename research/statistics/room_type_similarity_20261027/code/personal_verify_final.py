#!/usr/bin/env python3
"""Verify final single-writer personal outputs and a meaningful model replay."""
import os
for k in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ.setdefault(k,'1')
import argparse,gzip,json,hashlib,io
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.linear_model import Ridge
from personal import FrozenFeatures,rel_target,image_weights,centered_prediction

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--results',type=Path,required=True);a=ap.parse_args()
 d=pd.read_csv(a.inputs/'annotations.csv.gz',dtype={'object_id':str},low_memory=False)
 d=d[(d.condition=='manual')&(d.layer=='ordinary')&d.formal_quality&d.Q.notna()&d.D10.notna()].copy().reset_index(drop=True)
 d.room_type_model=d.room_type_model.fillna('__MISSING__');d.difficulty=d.difficulty.fillna('__UNKNOWN__')
 helds=sorted(set([sorted(d.building.unique())[0],d.groupby('building').size().idxmax()]))
 replay=[];keysets={}
 for oc in ['Q','D10','annotation_turn5']:
  t=d[d[oc].notna()].copy().reset_index(drop=True);t['relative']=rel_target(t,oc)
  P=pd.read_csv(a.results/f'OOF_{oc}.csv.gz',dtype={'object_id':str});assert len(P)==len(t)*7 and not P[['object_id','method']].duplicated().any()
  keysets[oc]=set(map(tuple,P[['object_id','method']].to_numpy()))
  assert np.max(abs(P.error-(P.predicted_relative-P.actual_relative)))<1e-10
  with gzip.open(a.results/f'MODELS_{oc}.jsonl.gz','rt') as f:models=[json.loads(l) for l in f]
  for row in models:
   if row['held_out_building'] not in helds:continue
   s=row['feature_schema'];tr=t[t.building!=row['held_out_building']];te=t[t.building==row['held_out_building']]
   feat=FrozenFeatures(tuple(s['parts']),s['numeric_cols']).fit(tr)
   m=Ridge(alpha=row['alpha'],fit_intercept=False,solver='lsqr',tol=1e-7,max_iter=2000).fit(feat.transform(tr),tr.relative,sample_weight=image_weights(tr))
   pred=centered_prediction(m.predict(feat.transform(te)),te)
   old=P[(P.method==row['method'])&(P.building==row['held_out_building'])].set_index('object_id').loc[te.object_id,'predicted_relative'].to_numpy()
   err=float(np.max(abs(old-pred)));ce=float(np.max(abs(m.coef_-np.asarray(row['coef']))))
   assert err<1e-8 and ce<1e-8
   replay.append({'outcome':oc,'held_out_building':row['held_out_building'],'method':row['method'],'alpha':row['alpha'],'target_rows':len(te),'max_pred_abs_error':err,'max_coefficient_abs_error':ce})
 assert keysets['Q']==keysets['D10']==keysets['annotation_turn5']
 checked=[]
 for directory in [a.results,a.results.parent/'personal_semi',a.results.parent/'personal_oldgate',a.results.parent/'personal_protected_purpose']:
  for f in sorted(directory.rglob('*')):
   if not f.is_file() or 'history_invalid_concurrent_outputs' in f.parts:continue
   if f.name.endswith('.csv') or f.name.endswith('.csv.gz'):
    q=pd.read_csv(f);checked.append({'path':str(f.relative_to(a.results.parent)),'rows':len(q),'fields':len(q.columns),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
   elif f.name.endswith('.jsonl.gz'):
    with gzip.open(f,'rt') as z:rows=[json.loads(x) for x in z]
    checked.append({'path':str(f.relative_to(a.results.parent)),'rows':len(rows),'type':'jsonl','sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 pd.DataFrame(replay).to_csv(a.results/'MODEL_REPLAY_CHECK.csv',index=False)
 receipt={'status':'complete','read_to_EOF':checked,'replay_models':len(replay),'selected_folds':helds,'selection_rule':'Lexicographically first and largest target-building record count, no outcome-based choice','max_prediction_abs_error':max(x['max_pred_abs_error'] for x in replay),
          'max_coefficient_abs_error':max(x['max_coefficient_abs_error'] for x in replay),'all_outcomes_same_object_method_support':True,
          'computed_source_commit':'b9bcec809fbaec8ab055931a1abb7baa5db44dac','adopted_latest_commit':'b2b0898b90bd631df37f1f2e75e8380800a43cf8','source_equivalence':'Root MAIN_UPDATE_SOURCE_CHECK.json: five core input Git blobs unchanged; this is not new external validation',
          'input_sha256':hashlib.sha256((a.inputs/'annotations.csv.gz').read_bytes()).hexdigest()}
 (a.results/'FINAL_VALIDATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 final=json.loads((a.results/'COMPLETE_FINAL.json').read_text());final.update(validation_receipt='FINAL_VALIDATION.json',model_replay_count=len(replay),computed_source_commit=receipt['computed_source_commit'],adopted_latest_commit=receipt['adopted_latest_commit'],latest_source_byte_equivalent=True)
 (a.results/'COMPLETE_FINAL.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in receipt.items() if k!='read_to_EOF'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
