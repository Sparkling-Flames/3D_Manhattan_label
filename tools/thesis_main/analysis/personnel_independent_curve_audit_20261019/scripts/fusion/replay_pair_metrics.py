import sys,json
from pathlib import Path
import pandas as pd,numpy as np
B=Path(__file__).resolve().parents[2]/'extracted/work_v2_20261019/fusion';O=Path(__file__).resolve().parent
sys.path.insert(0,str(B));from compare_fusions import ComparisonPool
from pool_io import load_pools
selected=json.loads((O/'REPLAY_SELECTION.json').read_text())['requests'][:44];want={frozenset(selected[i:i+2]) for i in range(0,44,2)};saved=[]
for d in pd.read_csv(B/'replacements.csv.gz',chunksize=20000,low_memory=False):
 for r in d[d.request_a.isin(selected)&d.request_b.isin(selected)].to_dict('records'):
  if frozenset([r['request_a'],r['request_b']]) in want:saved.append(r)
pools={p['pool_id']:p for p in load_pools()};out=[]
for row in saved:
 cp=ComparisonPool(pools[row['pool_id']]);actual=cp.pair(row['request_a'],row['request_b']);errs={}
 for k,v in actual.items():
  if k not in row:continue
  e=row[k]
  if v is None or v=='':match=pd.isna(e) or e==''
  elif isinstance(v,(int,float)) and not isinstance(v,bool):match=bool(np.isclose(v,e,rtol=1e-10,atol=1e-10))
  else:match=v==e
  if not match:errs[k]=dict(recomputed=v,saved=e)
 out.append(dict(pool_id=row['pool_id'],request_a=row['request_a'],request_b=row['request_b'],mismatches=errs))
(O/'PAIR_METRIC_REPLAY.json').write_text(json.dumps(dict(pairs=len(out),rows=out),indent=2));print('pairs',len(out),'mismatches',sum(bool(x['mismatches']) for x in out))
