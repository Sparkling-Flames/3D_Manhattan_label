"""Reproduce the numerical studies and available review outputs in a new directory."""
from pathlib import Path
import argparse,subprocess,sys,os,json
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--figures',action='store_true');a=p.parse_args()
if a.output.exists():raise FileExistsError('Output must not exist; previous results are immutable')
a.output.mkdir(parents=True);logs=a.output/'logs';logs.mkdir()
env=os.environ.copy();env.update(PYTHONHASHSEED='0',PYTHONUTF8='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1',AB_TEST_RESULTS=str((a.output/'results').resolve()))
commands=[('study',[sys.executable,'-B',str(ROOT/'run_study.py'),'--output',str(a.output/'results')]),
 ('extensions',[sys.executable,'-B',str(ROOT/'run_extensions.py'),'--output',str(a.output/'results')]),
 ('review',[sys.executable,'-B',str(ROOT/'build_review.py'),'--results',str(a.output/'results'),'--review',str(a.output/'review')]),
 ('tests',[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',str(ROOT/'tests')])]
if a.figures:commands.append(('figures',[sys.executable,'-B',str(ROOT/'plot_results.py'),'--results',str(a.output/'results'),'--figures',str(a.output/'figures')]))
receipt=[]
for name,cmd in commands:
 with (logs/(name+'.log')).open('w',encoding='utf-8') as f:res=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=env,cwd=ROOT)
 receipt.append(dict(stage=name,returncode=res.returncode))
 if res.returncode:raise RuntimeError(f'Stage {name} failed. See {logs/name}.log')
(a.output/'REPLAY_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
