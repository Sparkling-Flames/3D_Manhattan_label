#!/usr/bin/env python3
"""Replay the frozen research experiment into a NEW directory; no repository writes.
Raw-loader acquisition is separate (src/prepare.py requires the pinned repository).
This offline replay uses the fully specified/hash-pinned derived geometry manifest.
"""
from pathlib import Path
import argparse,shutil,subprocess,sys,json,hashlib,time
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parent

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--resume',action='store_true');args=ap.parse_args();out=Path(args.output).resolve()
 if out.exists() and not args.resume:raise SystemExit('Output exists; use --resume only for an interrupted replay')
 if args.resume:
  if not (out/'RUN_PROGRESS.json').exists():raise SystemExit('No saved replay progress')
  for folder in ['src','vendor','inputs','tests']:
   for file in (ROOT/folder).rglob('*'):
    if file.is_file() and '__pycache__' not in str(file) and '.pytest_cache' not in str(file):
     target=out/file.relative_to(ROOT)
     if not target.exists() or file.read_bytes()!=target.read_bytes():raise SystemExit('Resume source/input mismatch: '+str(file))
 else:
  out.mkdir(parents=True);(out/'results').mkdir();(out/'logs').mkdir()
  for folder in ['src','vendor','inputs','tests']:shutil.copytree(ROOT/folder,out/folder,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
 steps=['recompute_baseline.py','run_new.py','run_normalized.py','controls.py','coarsening_replay.py','scope_audit.py','crop_reference_controls.py','doorway_stress.py','numerical_audit.py','analyze.py']
 records=json.loads((out/'RUN_PROGRESS.json').read_text()) if args.resume else []
 done={r['script'] for r in records if r['returncode']==0}
 for s in steps:
  if s in done:continue
  t=time.time()
  with (out/'logs'/f'{s}.log').open('w') as f:p=subprocess.run([sys.executable,str(out/'src'/s)],stdout=f,stderr=subprocess.STDOUT)
  records.append({'script':s,'returncode':p.returncode,'seconds':time.time()-t});print(s,p.returncode,flush=True)
  (out/'RUN_PROGRESS.json').write_text(json.dumps(records,indent=2))
  if p.returncode:raise SystemExit('Replay step failed: '+s)
 p=subprocess.run([sys.executable,'-m','pytest','-q',str(out/'tests')],capture_output=True,text=True);(out/'logs/tests.log').write_text(p.stdout+p.stderr)
 if p.returncode:raise SystemExit('Tests failed')
 files=['baseline_and_all_B_parameters.csv','new_scores891.csv','normalized_scores891.csv','controls_all_scores.csv','coarsening_replay14.csv','crop_reference_controls.csv','doorway_conditional_stress.csv','difficulty_all_versions.csv','comment24_all_versions.csv','invariance5346.csv','quadrature_refinement891.csv']
 differences={}
 for f in files:
  a=pd.read_csv(ROOT/'results'/f);b=pd.read_csv(out/'results'/f)
  if a.shape!=b.shape or list(a.columns)!=list(b.columns):raise ValueError('replay_shape_difference:'+f)
  num=[k for k in a.columns if pd.api.types.is_numeric_dtype(a[k]) and pd.api.types.is_numeric_dtype(b[k]) and a[k].dtype!='bool']
  errs=(a[num]-b[num]).abs();maxerr=float(np.nanmax(errs.to_numpy())) if len(num) else 0
  differences[f]={'rows':len(a),'max_numeric_absolute_difference':maxerr,'csv_bytes_identical':(ROOT/'results'/f).read_bytes()==(out/'results'/f).read_bytes()}
  if maxerr>1e-9:raise ValueError('replay_numeric_difference:'+f)
 summary={'status':'passed','steps':records,'files':differences,'tests_output':p.stdout,'scope':'complete offline frozen-manifest replay; not a second network acquisition or independent validation'}
 (out/'REPLAY_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
