"""Recovery orchestration only; executes the preserved frozen science scripts."""
from pathlib import Path
import subprocess,json,time,hashlib,sys
R=Path(__file__).resolve().parent
P=R/'venv/bin/python'
while not (R/'restored/RESTORATION_RECEIPT.json').exists(): time.sleep(10)
receipt=json.loads((R/'restored/RESTORATION_RECEIPT.json').read_text())
assert receipt['files_verified']==3844
print('INPUT_RESTORATION_VERIFIED',receipt,flush=True)
def launch(script,log):
 f=(R/log).open('w')
 return subprocess.Popen([str(P),str(script)],stdout=f,stderr=subprocess.STDOUT,cwd=R)
a=launch(R/'rebuild_corner_outputs.py','native_replay.log')
b=launch(R.parent/'mixed_pair_recovery/rebuild_frozen_mixed.py','mixed_replay.log')
cdf=None
while a.poll() is None or b.poll() is None or (cdf is not None and cdf.poll() is None):
 if cdf is None and (R/'recomputed/history_block_metrics/COMMON_LIBRARY_RECEIPT.json').exists():
  cdf=launch(R/'audit_statistics/block_tolerance_cdf.py','cdf_recovery.log');print('CDF_STARTED',flush=True)
 time.sleep(10)
if cdf is None and a.returncode==0:
 cdf=launch(R/'audit_statistics/block_tolerance_cdf.py','cdf_recovery.log');cdf.wait()
result={'native_returncode':a.returncode,'mixed_returncode':b.returncode,'cdf_returncode':cdf.returncode if cdf else None}
(R/'EXECUTION_RESULT.json').write_text(json.dumps(result,indent=2));print(result,flush=True)
assert result=={'native_returncode':0,'mixed_returncode':0,'cdf_returncode':0}
