"""Refine the two descriptively discordant raw-pair comparisons, not select a method."""
from pathlib import Path
import json
from quality import directed
from compression_study import dump
ROOT=Path(__file__).resolve().parents[1]
def run():
 inp=json.loads((ROOT/'inputs/7y3sRwLe3Va-04.json').read_text());rr={r['id']:r for r in inp['records']}
 g=next(x for x in json.loads((ROOT/'evaluation/references.json').read_text())['images'] if x['image']==inp['image'])['references'][0];rows=[]
 for a,b,step in [('R01300','R02365',.0005),('R01553','R02226',.005)]:
  ds=[]
  for key in [a,b]:
   A=directed(rr[key],g,1,step);B=directed(g,rr[key],1,step);ds.append(((A['mean_deg']+B['mean_deg'])/2,(A['mean_absolute_numerical_bound_deg']+B['mean_absolute_numerical_bound_deg'])/2))
  rows.append(dict(first=a,second=b,step_deg=step,arc_difference_deg=ds[0][0]-ds[1][0],difference_bound_deg=ds[0][1]+ds[1][1],difference_sign_resolved=abs(ds[0][0]-ds[1][0])>ds[0][1]+ds[1][1]))
 dump(ROOT/'results/metrics/refined_discordances.json',rows)
if __name__=='__main__':run()
