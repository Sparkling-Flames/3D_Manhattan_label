"""Wait for complete frozen measurements, then finalize two read-only analyses."""
import json,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
receipt=root/'stage04_metrics/MEASUREMENT_RECEIPT.json'
while True:
    if receipt.exists():
        try:
            if json.loads(receipt.read_text()).get('complete'):break
        except json.JSONDecodeError:pass
    time.sleep(10)
out=root/'stage05_main'
with (out/'FINAL_SUMMARY_LOG.txt').open('w') as f:
    subprocess.run([sys.executable,str(root/'code/summarize_ac_effects.py'),'--metrics',str(root/'stage04_metrics'),
      '--links',str(root/'stage01_registered/DESIGN_LINKS.csv.gz'),'--out',str(out)],check=True,stdout=f,stderr=subprocess.STDOUT)
assert json.loads((out/'SUMMARY_RECEIPT.json').read_text())['complete']
with (out/'FINAL_CONTEXT_LOG.txt').open('w') as f:
    subprocess.run([sys.executable,str(root/'code/summarize_context_and_common_pools.py')],check=True,stdout=f,stderr=subprocess.STDOUT)
print(json.dumps({'main':json.loads((out/'SUMMARY_RECEIPT.json').read_text()),'context':json.loads((root/'stage05_context_common/ANALYSIS_RECEIPT.json').read_text())},ensure_ascii=False))
