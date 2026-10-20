"""Separate discovery endpoint extraction; never used in fitting the new labels."""
import sys,json,time,argparse,os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
BASE=Path(__file__).resolve().parent; ROOT=Path(os.environ.get('INTERCHANGEABILITY_WORK_ROOT',BASE.parent))
sys.path.insert(0,str(ROOT/'audit_learning'))
import extract_corner_history as history
history.OUT=BASE/'discovery_endpoints';history.OUT.mkdir(exist_ok=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--jobs',type=int,default=2);a=p.parse_args()
 split=json.loads((history.P/'analysis/composition/SPLIT.json').read_text());buildings=set(split['discovery_buildings'])
 pools=sorted(p.name for p in (history.A/'comparisons').iterdir() if p.name.split('-',1)[0] in buildings)
 t=time.perf_counter()
 with ProcessPoolExecutor(max_workers=a.jobs) as e:
  for row in e.map(history.process,pools):print(json.dumps(row),flush=True)
 print(json.dumps(dict(pools=len(pools),elapsed_seconds=time.perf_counter()-t)),flush=True)
