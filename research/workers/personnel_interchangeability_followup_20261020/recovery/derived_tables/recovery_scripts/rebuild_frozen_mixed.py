"""Recover one omitted mixed-history paired table without any model fitting."""
from pathlib import Path
import json,time,subprocess,hashlib,shutil,sys
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[1];W=R/'native_rebuild';B=W/'audit_learning';O=Path(__file__).resolve().parent;F=B/'corner_fit_mixed';PY=W/'venv/bin/python';t=time.perf_counter()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
expected=json.load(open(R/'UNAVAILABLE_FILES.json'));target=[x for x in expected if x['path'].endswith('corner_fit_mixed/paired_random_building.csv.gz')];assert len(target)==1
original=O/'original_retained';original.mkdir(exist_ok=True)
for name in ['inner_cv_building.csv','inner_cv_summary.csv','paired_random_draws.csv','paired_random_summary.csv','METHOD_MANIFEST.json','worker_labels.csv','fold_labels.csv']:
 p=original/name
 if not p.exists():shutil.copy2(F/name,p)
 if name.endswith('.json') or name.endswith('labels.csv'):assert sha(p)==sha(F/name)
frozen={name:sha(F/name) for name in ['METHOD_MANIFEST.json','worker_labels.csv','fold_labels.csv']};frozen['eight_building_QT_features.csv']=sha(B/'eight_building_QT_features.csv')
(O/'INPUT_FREEZE.json').write_text(json.dumps({'target':target[0],'frozen_inputs':frozen,'no_refit':True},indent=2))
while not (W/'restored/RESTORATION_RECEIPT.json').exists():time.sleep(15)
assert json.load(open(W/'restored/RESTORATION_RECEIPT.json'))['files_verified']==3844
print('Restoration verified; actual H20 native replay and legacy extraction begin.',flush=True)
def run(name,args):
 with (O/(name+'.log')).open('w') as log:
  z=subprocess.run([str(PY),*map(str,args)],cwd=W,stdout=log,stderr=subprocess.STDOUT)
 if z.returncode:raise RuntimeError(name+' failed; see log')
legacy=subprocess.Popen([str(PY),str(B/'extract_corner_history.py'),'--jobs','2'],cwd=W,stdout=open(O/'legacy_extract.log','w'),stderr=subprocess.STDOUT)
run('h20_native',[W/'unpacked/analysis/composition/fusion_runner.py','--restored',W/'restored','--requests',W/'unpacked/interchangeability_20261020/history_panel/history_requests.json.gz','--out',W/'audit_replay/history_native','--jobs','2'])
assert legacy.wait()==0
run('h20_extract',[B/'extract_corner_h20.py','--jobs','2'])
assert len(list((B/'corner_history').glob('*.csv.gz')))==79 and len(list((B/'corner_h20').glob('*.csv.gz')))==81
run('frozen_evaluation',[B/'evaluate_saved_corner_fit.py','--tier','mixed'])
checks=[]
for name,keys in [('inner_cv_building.csv',['method_id','fold','building']),('inner_cv_summary.csv',['method_id']),('paired_random_draws.csv',['method_id','baseline','draw']),('paired_random_summary.csv',['method_id','baseline'])]:
 a=pd.read_csv(original/name).sort_values(keys).reset_index(drop=True);b=pd.read_csv(F/name).sort_values(keys).reset_index(drop=True);assert a.shape==b.shape and a.columns.tolist()==b.columns.tolist(),name
 worst=0.;tested=0
 for col in a:
  if pd.api.types.is_numeric_dtype(a[col]):
   assert np.array_equal(a[col].isna(),b[col].isna()),(name,col,'missingness')
   valid=a[col].notna();diff=np.abs(a.loc[valid,col].to_numpy(float)-b.loc[valid,col].to_numpy(float));worst=max(worst,float(diff.max()) if len(diff) else 0.);assert np.allclose(a[col],b[col],rtol=1e-10,atol=1e-12,equal_nan=True),(name,col,worst);tested+=len(a)
  else:assert a[col].fillna('<NA>').equals(b[col].fillna('<NA>')),(name,col)
 checks.append({'file':name,'rows':len(a),'columns':len(a.columns),'numeric_cells':tested,'max_absolute_error':worst,'keys_and_missingness_exact':True,'passed':True})
for name in ['METHOD_MANIFEST.json','worker_labels.csv','fold_labels.csv']:assert sha(F/name)==frozen[name]
assert sha(B/'eight_building_QT_features.csv')==frozen['eight_building_QT_features.csv']
q=pd.read_csv(F/'paired_random_building.csv.gz');assert len(q)==2520 and not q.duplicated(['method_id','fold','baseline','draw','building']).any();assert q.method_id.nunique()==6 and q.fold.nunique()==5
receipt={'target':target[0]['path'],'original_expected_sha256':target[0]['sha256'],'rebuilt_sha256':sha(F/'paired_random_building.csv.gz'),'compressed_bytes':(F/'paired_random_building.csv.gz').stat().st_size,'rows':len(q),'candidate_count':q.method_id.nunique(),'fold_count':q.fold.nunique(),'frozen_inputs_unchanged':True,'no_model_refit':True,'retained_summary_checks':checks,'scientific_conclusions_unchanged':True,'reconstruction_type':'fresh exact frozen fusion + original corner extraction + saved-label evaluation','hash_note':'Gzip header timestamp and serialization can change compressed hash. Original missing row-level table is unavailable for byte or full-cell comparison; retained CV/draw/final aggregates are compared exhaustively, not merely headline values.','seconds':time.perf_counter()-t,'recovery_script_sha256':sha(Path(__file__)),'script_hashes':{n:sha(B/n) for n in ['extract_corner_history.py','extract_corner_h20.py','evaluate_saved_corner_fit.py','learn_corner_types.py']}}
(O/'MIXED_PAIRED_RECOVERY_RECEIPT.json').write_text(json.dumps(receipt,indent=2));shutil.copy2(F/'paired_random_building.csv.gz',O/'paired_random_building.csv.gz');print(json.dumps(receipt),flush=True)
