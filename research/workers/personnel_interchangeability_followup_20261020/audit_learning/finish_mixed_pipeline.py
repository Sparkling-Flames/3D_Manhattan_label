"""Finish finite registered history reconstruction and fits; resumable outputs."""
import time,subprocess,sys,json
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
expected=81
while True:
 count=len(list((ROOT/'audit_replay/history_native/pools').glob('*.json.gz')))
 with (BASE/'h20_extract_finish.log').open('a') as log:
  result=subprocess.run([sys.executable,BASE/'extract_corner_h20.py','--available','--jobs','3'],stdout=log,stderr=subprocess.STDOUT)
 if result.returncode:raise SystemExit('H20 extraction failed; inspect h20_extract_finish.log')
 if (BASE/'H20_EXTRACTION_RECEIPT.json').exists():break
 print(json.dumps({'native_pools_at_start':count,'expected':expected,'waiting_for_frozen_replay':True}),flush=True)
 time.sleep(20)
for filename,output,receipt,args in [
 ('refit_original_new2.py','original_new2_refit.log',BASE/'ORIGINAL_RNEW2_FULL_REFIT_RECEIPT.json',[]),
 ('learn_corner_types.py','mixed_corner_fit.log',BASE/'corner_fit_mixed/RUN_RECEIPT.json',['--tier','mixed']),
 ('summarize_corner_labels.py','mixed_label_sensitivity.log',BASE/'corner_fit_mixed/inner_fit_label_sensitivity_summary.csv',['--tier','mixed'])]:
 if receipt.exists():print('Already completed '+filename,flush=True);continue
 with (BASE/output).open('w') as log:r=subprocess.run([sys.executable,BASE/filename,*args],stdout=log,stderr=subprocess.STDOUT)
 if r.returncode:raise SystemExit(filename+' failed; inspect '+output)
 print('Completed '+filename,flush=True)
