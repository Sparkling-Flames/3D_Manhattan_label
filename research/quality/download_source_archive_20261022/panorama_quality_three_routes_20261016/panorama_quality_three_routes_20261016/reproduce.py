"""Recompute in a NEW directory, preserving shipped outputs.
python reproduce.py --out /tmp/gqs_replay
python reproduce.py --out /tmp/gqs_full --full  # includes parameter/invariance/refinement audits
"""
import argparse,json,shutil,subprocess,sys,time
from pathlib import Path
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--full',action='store_true');a=ap.parse_args();out=Path(a.out).resolve()
if out.exists():raise SystemExit('Choose an output directory that does not exist.')
if ROOT in out.parents:raise SystemExit('Replay output must be outside the supplied study folder.')
out.mkdir(parents=True)
for name in ['src','legacy','frozen_repo','inputs']:shutil.copytree(ROOT/name,out/name,ignore=shutil.ignore_patterns('__pycache__'))
for name in ['config.json','RUN_MANIFEST.json']:shutil.copy2(ROOT/name,out/name)
(out/'results').mkdir();(out/'figures').mkdir()
commands=[['src/prepare_inputs.py'],['-m','unittest','discover','-s','src','-p','test_*.py','-v'],['src/run_real.py'],['src/run_controls.py'],['src/run_ablation.py'],['src/score_manifest.py','--out','results/versioned244.csv'],['src/compare_versions.py','--left','results/versioned244.csv','--right','results/versioned244.csv','--out','results/version_self_comparison.csv']]
if a.full:commands.append(['src/run_robustness.py'])
log=[]
for i,cmd in enumerate(commands):
 r=subprocess.run([sys.executable]+cmd,cwd=out,capture_output=True,text=True);(out/'results'/f'replay_{i:02d}.log').write_text(r.stdout+'\n'+r.stderr);log.append(dict(command=cmd,returncode=r.returncode))
 if r.returncode:raise RuntimeError(f'Replay failed {cmd}: {r.stderr[-2000:]}')
parity={}
for name,key in [('current244_scores.csv','object_id'),('synthetic_scores.csv','name')]:
 l=pd.read_csv(ROOT/'results'/name).set_index(key);r=pd.read_csv(out/'results'/name).set_index(key);assert set(l.index)==set(r.index)
 parity[name]={k:float(np.max(abs(l[k]-r.loc[l.index,k]))) for k in ['QA','QB','QC']}
 assert max(parity[name].values())<1e-8
(out/'REPLAY_SUMMARY.json').write_text(json.dumps(dict(full=a.full,commands=log,score_parity=parity),indent=2));print(json.dumps(parity,indent=2))
