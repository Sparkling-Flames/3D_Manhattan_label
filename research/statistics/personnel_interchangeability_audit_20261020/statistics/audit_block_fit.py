"""Independent block learner final-table arithmetic, fit ledger and uncertainty."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent.parent;I=R/'audit_learning/block_fit';O=R/'audit_statistics/block_fit';O.mkdir(exist_ok=True)
f=pd.read_csv(I/'inner_cv_building.csv');rep=pd.read_csv(I/'inner_cv_summary.csv').set_index('method_id');cs=[c for c in rep if c in f and c!='fold'];err=(f.groupby('method_id')[cs].mean()-rep[cs]).abs().max().max();assert err<1e-10
p=pd.read_csv(I/'paired_building.csv.gz');rep2=pd.read_csv(I/'paired_summary.csv').set_index(['method_id','baseline']);cs2=[c for c in rep2 if c in p and c not in ['fold','draw']];err2=(p.groupby(['method_id','baseline'])[cs2].mean()-rep2[cs2]).abs().max().max();assert err2<1e-10
for c in [c for c in p if c.startswith('delta_')]:assert np.allclose(p[c],p['candidate_'+c[6:]]-p['baseline_'+c[6:]],equal_nan=True,atol=1e-10)
l=json.load(open(I/'FIT_LEDGER.json'));assert len(l)==24
for z in l:
 assert np.isfinite(z['objective']) and z['risk_scale']>0 and z['accepted_moves']<=30
 trace=[v['objective'] for v in z['trace']];assert all(a>b+1e-12 for a,b in zip(trace,trace[1:]));assert not trace or abs(trace[-1]-z['objective'])<1e-12
rows=[];rng=np.random.default_rng(20261020)
for (mid,base),g in p.groupby(['method_id','baseline']):
 for c in [c for c in p if c.startswith('delta_')]:
  b=g.groupby('building')[c].mean().dropna().to_numpy();boot=b[rng.integers(0,len(b),(50000,len(b)))].mean(axis=1) if len(b)>=3 else np.array([np.nan]);rows.append(dict(method_id=mid,baseline=base,metric=c,buildings=len(b),estimate=b.mean(),ci025=np.quantile(boot,.025),ci975=np.quantile(boot,.975),positive_buildings=int((b>0).sum()),negative_buildings=int((b<0).sum())))
pd.DataFrame(rows).to_csv(O/'PAIRED_BUILDING_BOOTSTRAP.csv',index=False)
r=dict(inner_rows=len(f),paired_rows=len(p),inner_max_error=float(err),paired_max_error=float(err2),all_paired_arithmetic=True,finite_objective_starts=len(l),all_traces_strictly_decreasing=True,inputs={x:hashlib.sha256((I/x).read_bytes()).hexdigest() for x in ['inner_cv_building.csv','paired_building.csv.gz','FIT_LEDGER.json','RUN_RECEIPT.json']},caveat='Aggregation and ledger audit; does not independently refit. Building bootstrap descriptive, correlated folds and training selection remain.')
(O/'RECEIPT.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
print(pd.DataFrame(rows).query("metric in ['delta_within_distance','delta_gap_distance','delta_within_allanchors_valid_distance','delta_within_allanchors_different_count']").to_string(index=False))
