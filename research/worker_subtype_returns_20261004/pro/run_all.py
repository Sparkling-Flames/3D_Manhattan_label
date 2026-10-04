"""Reproduce all numerical results into a NEW directory without overwriting sources."""
from pathlib import Path
import argparse, os, shutil, subprocess, sys, json, platform

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parent;out=a.out.resolve()
 if out.exists():raise SystemExit('Output already exists. Choose a new directory; existing results are never overwritten.')
 out.mkdir(parents=True);shutil.copytree(root/'inputs',out/'inputs');(out/'results').mkdir();(out/'logs').mkdir()
 env=dict(os.environ,WORKER_RESEARCH_ROOT=str(out),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONUTF8='1')
 commands=[['audit_inputs.py'],['coverage_experiments.py'],['profile_experiments.py'],['nested_profiles.py']]
 for name in ['one_image_geometry.json','rpc_geometry.json']:
  commands.extend([[f,'--input',name] for f in ['shape_experiments.py','annotation_distribution.py','six_person_experiments.py']])
 commands.append(['calibration_propagation.py'])
 for i,args in enumerate(commands):
  command=[sys.executable,'-X','utf8',str(root/'src'/args[0]),*args[1:]]
  print('Running',args,flush=True)
  with (out/'logs'/f'{i:02d}_{Path(args[0]).stem}.txt').open('w',encoding='utf-8') as f:
   subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 import numpy, scipy, pandas, shapely, sklearn
 (out/'environment.json').write_text(json.dumps(dict(python=platform.python_version(),numpy=numpy.__version__,scipy=scipy.__version__,pandas=pandas.__version__,shapely=shapely.__version__,sklearn=sklearn.__version__),indent=2)+'\n')
 print('Completed:',out)
if __name__=='__main__':main()
