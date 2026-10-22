#!/usr/bin/env python3
"""Audit all admitted v1 parameter configurations; no fitting or input changes."""
from pathlib import Path
import argparse, itertools, json
import numpy as np
import pandas as pd

p=argparse.ArgumentParser()
p.add_argument('--results',type=Path,default=Path('../quality_return_1057_files/layout_quality_research_v1_repro/results/scoring'))
p.add_argument('--output',type=Path,default=Path('.'))
a=p.parse_args(); a.output.mkdir(exist_ok=True,parents=True)
d=pd.read_csv(a.results/'research_scores36.csv')
c=pd.read_csv(a.results/'candidate_enumeration.csv')
c=c[(c.family=='product_with_height') & c.soft_response_band.eq(True)]
I=d.iou.to_numpy(); S=d.S_rms_deg.to_numpy(); H=d.height_mean_relative_error.to_numpy()
D=d.dir.to_numpy(); F=d.flat.to_numpy(); base=d.score_research_v1.to_numpy()
q=[]
for x in c.itertuples():
    q.append(100*I/(1+(S/x.boundary_half_scale)**2+(H/x.height_relative_half)**2)
             *(1-x.intrinsic_max_discount/2*(D**2/(D**2+x.direction_half_deg**2)
                                           +F**2/(F**2+x.flatness_half_deg**2))))
q=np.asarray(q); records=[]
for i,j in itertools.combinations(range(len(d)),2):
    gap=base[i]-base[j]; gaps=q[:,i]-q[:,j]
    records.append(dict(a=d.review_id[i],b=d.review_id[j],gap=gap,
                        min_gap=gaps.min(),max_gap=gaps.max(),
                        reversed=bool((gap*gaps<0).any())))
pairs=pd.DataFrame(records)
pairs.to_csv(a.output/'acceptable340_pair_stability.csv',index=False)
ranges=d[['review_id','score_research_v1']].copy()
ranges['min340']=q.min(0);ranges['max340']=q.max(0)
ranges.to_csv(a.output/'acceptable340_score_ranges.csv',index=False)
summary={'n_acceptable':len(c),
 'parameter_ranges':{k:sorted(c[k].unique().tolist()) for k in
  ['boundary_half_scale','direction_half_deg','flatness_half_deg','intrinsic_max_discount','height_relative_half']},
 'n_all_pairs':len(pairs),'n_stable':int((~pairs.reversed).sum()),
 'max_baseline_gap_reversed':float(pairs[pairs.reversed].gap.abs().max()),
 'n_reversed_gap_ge2':int(((pairs.gap.abs()>=2)&pairs.reversed).sum()),
 'n_reversed_gap_ge5':int(((pairs.gap.abs()>=5)&pairs.reversed).sum()),
 'max_absolute_change':float(np.max(abs(q-base)))}
(a.output/'acceptable340_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))
