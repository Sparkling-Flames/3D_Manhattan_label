"""Run in a new directory. No web, reference geometry or original photographs needed."""
from pathlib import Path
import argparse,sys,os,json
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from run_domains import main
from diagnostics import run as diagnose
from controls import all_control
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
p.add_argument('--stage',choices=['all','domains','diagnostics','controls'],default='all')
a=p.parse_args()
if a.stage=='all':
    a.out.mkdir(parents=True,exist_ok=False)
    main(ROOT,a.out/'domains');diagnose(ROOT,a.out/'diagnostics');all_control(ROOT,a.out/'controls')
elif a.stage=='domains':main(ROOT,a.out/'domains')
elif a.stage=='diagnostics':diagnose(ROOT,a.out/'diagnostics')
else:all_control(ROOT,a.out/'controls')
