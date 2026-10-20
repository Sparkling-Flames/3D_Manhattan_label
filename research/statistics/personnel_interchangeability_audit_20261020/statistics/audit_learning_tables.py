"""Independent final-table aggregation and descriptive building bootstrap.
Call only after RUN_RECEIPT.json is present. No model execution.
"""
import argparse,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);assert (a.input/'RUN_RECEIPT.json').exists()
f=pd.read_csv(a.input/'inner_cv_building.csv');reported=pd.read_csv(a.input/'inner_cv_summary.csv');metrics=[c for c in f if c not in ['method_id','fold','building'] and pd.api.types.is_numeric_dtype(f[c])];calc=f.groupby('method_id')[metrics].mean();reported=reported.set_index('method_id');err=abs(calc-reported[metrics]).max().max();assert err<1e-10
pr=pd.read_csv(a.input/'paired_random_building.csv.gz');dm=[c for c in pr if c.startswith(('candidate_','baseline_','delta_'))];draw=pr.groupby(['method_id','baseline','draw'])[dm].mean().sort_index();rd=pd.read_csv(a.input/'paired_random_draws.csv').set_index(['method_id','baseline','draw']).sort_index();err2=abs(draw-rd[dm]).max().max();assert err2<1e-10
for c in [x for x in dm if x.startswith('delta_')]:
 tail=c[6:];d=pr['candidate_'+tail]-pr['baseline_'+tail];assert np.allclose(d,pr[c],atol=1e-10,equal_nan=True)
rows=[];rng=np.random.default_rng(20261020)
# Average random draws inside building first, then equal buildings.
# This tests expected random benchmark, NOT40 independent validation samples.
for (mid,base),g in pr.groupby(['method_id','baseline']):
 m=[c for c in dm if c.startswith('delta_')];b=g.groupby('building')[m].mean()
 for c in m:
  x=b[c].dropna().to_numpy();d=x[rng.integers(0,len(x),(50000,len(x)))].mean(axis=1) if len(x)>=3 else np.array([np.nan]);rows.append(dict(method_id=mid,baseline=base,metric=c,buildings=len(x),draws=g.draw.nunique(),estimate=x.mean() if len(x) else np.nan,ci025=np.quantile(d,.025),ci975=np.quantile(d,.975),building_min=x.min() if len(x) else np.nan,building_max=x.max() if len(x) else np.nan))
pd.DataFrame(rows).to_csv(a.output/'LEARNING_PAIRED_BUILDING_BOOTSTRAP.csv',index=False)
calc.to_csv(a.output/'INDEPENDENT_INNER_SUMMARY.csv');draw.to_csv(a.output/'INDEPENDENT_PAIRED_DRAWS.csv')
r=dict(inner_rows=len(f),paired_rows=len(pr),inner_aggregate_max_error=float(err),paired_draw_max_error=float(err2),all_paired_arithmetic_pass=True,interpretation='Expected random comparison averages draws inside building, not treating draws as independent participants. Descriptive resampling of inner-CV observed buildings; shared fold training, selection, scarce units and reused v2 remain.',inputs={x:hashlib.sha256((a.input/x).read_bytes()).hexdigest() for x in ['inner_cv_building.csv','inner_cv_summary.csv','paired_random_building.csv.gz','paired_random_draws.csv','RUN_RECEIPT.json']})
(a.output/'LEARNING_STATS_RECEIPT.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
