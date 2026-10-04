"""Size-of-violation diagnostic only; does NOT add votes or change a guarantee.
Uniform 65536-longitude sample is reported as sampled, not an exact extremum.
"""
from pathlib import Path
import json,numpy as np,pandas as pd
from arc_consensus import Ring,TAU
ROOT=Path(__file__).resolve().parents[1]
def run():
 rows=[]
 for image in ['2t7WUuJeko7-06','7y3sRwLe3Va-04']:
  rr=json.loads((ROOT/'inputs'/f'{image}.json').read_text())['records'];n=len(rr);t=n//2+1;L=2*t-n
  u=(np.arange(65536)+.5)/65536*TAU;S=np.array([Ring(r).evaluate(u) for r in rr])
  for p in sorted((ROOT/'results/compression').glob(image+'_*px.json')):
   c=json.loads(p.read_text());C=Ring(c).evaluate(u)
   gap=np.maximum.reduce([np.zeros_like(S[:,0]),S[:,0]-C[0],C[1]-S[:,1]])
   needed=np.partition(gap,L-1,axis=0)[L-1]
   row=dict(image=image,policy=c['compression_policy'],epsilon_px=c['epsilon_px'],sample_n=len(u),required_relaxation_max_sample_px=float(needed.max()),required_relaxation_mean_sample_px=float(needed.mean()),required_relaxation_max_sample_x=float(u[np.argmax(needed)]/TAU*1024),interpretation='minimum equal top/bottom inclusion slack for L witnesses; not extra support, not a quality error')
   for tol in [0,.01,.05,.1,.25,.5]:row[f'fraction_still_below_bound_at_slack_{tol:g}px']=float(np.mean(needed>tol+1e-8))
   rows.append(row)
 pd.DataFrame(rows).to_csv(ROOT/'results/metrics/witness_relaxation_samples.csv',index=False)
if __name__=='__main__':run()
