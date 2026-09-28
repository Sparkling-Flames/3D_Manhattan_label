"""Reproduce numerical outputs from bundled, hashed inputs. No source edits or network.
Usage: python code/run_all.py [--render]
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--render',action='store_true');a=ap.parse_args()
 for f in json.loads((R/'INPUT_MANIFEST.json').read_text())['files']:
  assert hashlib.sha256((R/f['path']).read_bytes()).hexdigest()==f['sha256'],f['path']
 (R/'results').mkdir(exist_ok=True)
 for script in ['local_points.py','precision_audit.py','review_audit.py','exemplar_cover.py','validate_and_summarize.py','same_person_time.py','no_borrowed_points.py']:
  result=subprocess.run([sys.executable,str(R/'code'/script)],capture_output=True,text=True)
  (R/'results'/('rerun_'+script+'.log')).write_text(result.stdout+'\n'+result.stderr)
  if result.returncode:raise RuntimeError(f'{script} failed; inspect rerun log')
  print('completed',script,flush=True)
 if a.render:
  for f in json.loads((R/'ORIGINAL_IMAGE_MANIFEST.json').read_text()):assert hashlib.sha256((R/f['path']).read_bytes()).hexdigest()==f['sha256']
  for script in ['visual_cases.py','annotate_visual_notes.py','point_witnesses.py']:
   subprocess.run([sys.executable,str(R/'code'/script)],check=True)
 else:
  (R/'results/visual_cases.json').write_bytes((R/'inputs/analyst_visual_observations.json').read_bytes())
  subprocess.run([sys.executable,str(R/'code/point_witnesses.py')],check=True)
 print('Complete. Reproduction is not independent semantic validation.')
if __name__=='__main__':main()
