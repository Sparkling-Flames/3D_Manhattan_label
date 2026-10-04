"""Ledger-only coverage calculations. Does not rerun raw geometries or change gates."""
from pathlib import Path
import os, math
import pandas as pd
ROOT=Path(os.environ.get('WORKER_RESEARCH_ROOT',Path(__file__).resolve().parents[1]))
d=pd.read_csv(ROOT/'inputs/high_support_inventory_excerpt.csv');m=d[d.condition=='manual']
assert len(m)==47 and m.curve_ready.sum()==44 and (m.curve_ready&m.reference_quality_compatible).sum()==33
cols=['condition','curve_ready','consensus_gate','reference_quality_compatible']
d.groupby(cols,dropna=False).agg(images=('image','size'),responses=('candidate_n','sum')).reset_index().to_csv(ROOT/'results/high_support_scope_summary.csv',index=False)
rows=[]
for _,r in d[d.candidate_bev_failed_n>0].iterrows():
 for k in range(1,int(r.candidate_n)+1):
  n=int(r.candidate_n);bad=int(r.candidate_bev_failed_n);p=math.comb(n-bad,k)/math.comb(n,k) if k<=n-bad else 0.
  rows.append(dict(image=r.image,condition=r.condition,n=n,failed_n=bad,k=k,computable_probability=p,interpretation='fixed_pool_individual_BEV_failures_only'))
pd.DataFrame(rows).to_csv(ROOT/'results/method_coverage_by_k.csv',index=False)
rows=[]
for k in range(1,21):
 values=[]
 for _,r in m.iterrows():
  n=int(r.candidate_n);bad=int(r.candidate_bev_failed_n);values.append(math.comb(n-bad,k)/math.comb(n,k) if k<=n-bad else 0.)
 rows.append(dict(k=k,fixed_images=47,expected_computable_fraction=sum(values)/47,expected_failed_fraction=1-sum(values)/47))
pd.DataFrame(rows).to_csv(ROOT/'results/fixed47_coverage_by_k.csv',index=False)
print('Ledger audited: 47 Manual / 44 computable / 33 reference main; 17 Semi; 9 separate OOS-condition pools.')
