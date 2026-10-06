import json,itertools,argparse
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser(description='Exhaustively verify all right-band subset gates from audit_e9z output.')
parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parent)
args=parser.parse_args()
OUT=args.out.resolve()
A=json.loads((OUT/'e9z_audit.json').read_text());rs=A['right_observations'];p=np.array([r['points'] for r in rs])
def distances(points):
 lon=2*np.pi*(points[:,0]/1024-.5);lat=np.pi*(.5-points[:,1]/512)
 r=np.c_[np.cos(lat)*np.sin(lon),np.sin(lat),-np.cos(lat)*np.cos(lon)]
 return np.rad2deg(np.arccos(np.clip(r@r.T,-1,1)))
top,bottom=distances(p[:,0]),distances(p[:,1]);paired=np.maximum(top,bottom)
results=[]
for side,d in [('paired',paired),('top',top),('bottom',bottom)]:
 for t in (5,9,12):
  feasible=[]
  for n in range(1,9):
   for indices in itertools.combinations(range(8),n):
    diameter=float(d[np.ix_(indices,indices)].max())
    if diameter<=t:feasible.append(dict(size=n,ids=[rs[i]['id'] for i in indices],indices=list(indices),diameter_deg=diameter))
  size=max(s['size'] for s in feasible)
  results.append(dict(side=side,threshold_deg=t,subsets_tested=255,feasible_count=len(feasible),maximum_size=size,maximum_cliques=[s for s in feasible if s['size']==size],majority_feasible_count=sum(s['size']>=4 for s in feasible)))
# Minimal required fixed complete-link diameter to obtain any four observed right-band observations.
min4={side:min((dict(diameter_deg=float(d[np.ix_(inds,inds)].max()),ids=[rs[i]['id'] for i in inds]) for inds in itertools.combinations(range(8),4)),key=lambda x:x['diameter_deg']) for side,d in [('paired',paired),('top',top),('bottom',bottom)]}
data=dict(schema='e9z_exhaustive_right_band_gate_v1',interpretation='Right-band membership is coordinate based, not a newly certified shared semantic identity. All 255 nonempty subsets checked; each worker unique. Feasibility is necessary for complete-link groups, not sufficient for full competing partition or physical correctness.',results=results,min_four_diameter=min4)
(OUT/'e9z_clique_gate_audit.json').write_text(json.dumps(data,ensure_ascii=False,indent=2));print(json.dumps(data,indent=2))
