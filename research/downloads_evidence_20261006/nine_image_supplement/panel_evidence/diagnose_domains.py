"""Independent B6By 120-degree endpoint-domain calculation; reads only input."""
import json,argparse
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--handoff',type=Path,required=True,help='Extracted handoff directory containing inputs.json')
parser.add_argument('--out',type=Path,required=True,help='Output directory for the domain diagnosis JSON')
args=parser.parse_args()
SRC=args.handoff.resolve()
OUT=args.out.resolve()
OUT.mkdir(parents=True,exist_ok=True)
inputs=json.loads((SRC/'inputs.json').read_text())
im=next(x for x in inputs['images'] if x['image']=='B6ByNegPMKs-33')
def angular(a,b):
    # Source coordinates are continuous 1024x512; no pixel-center half offset.
    a=np.asarray(a,float);b=np.asarray(b,float)
    du=((a[0]-b[0]+512)%1024-512)*(2*np.pi/1024)
    va=(a[1]/512-.5)*np.pi;vb=(b[1]/512-.5)*np.pi
    h=np.sin((va-vb)/2)**2+np.cos(va)*np.cos(vb)*np.sin(du/2)**2
    h=np.clip(h,0.,1.)
    return float(np.degrees(2*np.arctan2(np.sqrt(h),np.sqrt(1-h))))
records=[];blocked=[];longs=[]
for r in im['records']:
    p=np.array(r['points']).reshape(-1,2,2);n=len(p)
    arcs=[max(angular(p[i,0],p[(i+1)%n,0]),angular(p[i,1],p[(i+1)%n,1])) for i in range(n)]
    records.append({'record':r['id'],'max_top_bottom_incident_edge_deg':arcs})
    longs.extend(v for v in arcs if v>120)
    blocked.extend((r['id'],i) for i in range(n) if arcs[(i-1)%n]>120 or arcs[i]>120)
assert len(blocked)==92 and len(longs)==46
res={'definition':'First incident source edge exceeds 120deg on at least one paired boundary, so no source-vertex/turn-event endpoint within cumulative <=120deg exists in that direction under the ordered minor-arc model. Conditional on supplied rings, not a ring correctness judgment.','records':records,'blocked_focals':blocked,'total_focals':92,'long_edges':len(longs),'long_edge_range_deg':[min(longs),max(longs)]}
(OUT/'B6By_domain_diagnosis.json').write_text(json.dumps(res,indent=2)+'\n')
print('Blocked focals',len(blocked),'of 92; long edges',len(longs),'range',min(longs),max(longs))
