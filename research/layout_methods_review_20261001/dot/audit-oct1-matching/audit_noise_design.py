#!/usr/bin/env python3
"""Reconstruct controlled noise inputs only; no repeated optimizer experiment."""
import os,sys,json,csv
from pathlib import Path
from copy import deepcopy
import numpy as np
from shapely.geometry import Polygon
ROOT=Path(os.environ.get('RETURNED_ROOT','/workspace/scratch/a365811da80c/audit-oct1-inputs/returned/layout_methods_20261001'))
sys.path.insert(0,str(ROOT/'src'))
from geometry_core import reconstruct,from_floor
from real_inputs import get
OUT=Path(__file__).resolve().parent
rng=np.random.default_rng(61001);rows=[];exact=[]
for a,edge in [(get()[1][0],0),(get()[2][0],1)]:
    g=reconstruct(a);p,h=g['floor'],g['heights'];k=edge+1
    q=np.insert(p,k,(p[edge]+p[k])/2,axis=0);hq=np.insert(h,k,(h[edge]+h[k])/2)
    target=from_floor(q,hq);gg=reconstruct(target)
    top_orig=np.c_[p[:,0],h-1,p[:,1]];top_new=np.c_[gg['floor'][:,0],gg['heights']-1,gg['floor'][:,1]]
    exact.append({'record':a['id'],'floor_midpoint_error_h':float(np.linalg.norm(gg['floor'][k]-(p[edge]+p[k])/2)),
      'top_midpoint_error_h':float(np.linalg.norm(top_new[k]-(top_orig[edge]+top_orig[edge+1])/2)),
      'source_vertices':len(p),'inserted_edge':edge})
    for noise in (.25,.5,1,2,4):
        for rep in range(30):
            b=deepcopy(target);pairs=np.asarray(b['points']).reshape(-1,2,2)
            pairs[:,:,0]=(pairs[:,:,0]+rng.normal(0,noise,(len(pairs),1)))%1024
            pairs[:,:,1]+=rng.normal(0,noise,(len(pairs),2));b['points']=pairs.reshape(-1,2).tolist()
            bg=reconstruct(b)
            rows.append({'record':a['id'],'noise_px':noise,'rep':rep,'reason':bg['reason'],'wall_reason':bg['wall_reason'],'camera':bg['camera'],'kernel':bg['kernel']})
summary=[]
for record in sorted({x['record'] for x in rows}):
    for noise in (.25,.5,1,2,4):
        sub=[x for x in rows if x['record']==record and x['noise_px']==noise]
        summary.append({'record':record,'noise_px':noise,'n':len(sub),'invalid_footprints':sum(x['reason'] is not None for x in sub),
            'wall_ineligible':sum(x['wall_reason'] is not None for x in sub),'camera_outside_or_boundary':sum(x['camera'] in ('outside','boundary') for x in sub),'camera_status_unavailable':sum(x['camera']=='unavailable' for x in sub),
            'camera_kernel_false':sum(x['kernel'] is not None and not x['kernel'] for x in sub),'camera_kernel_unknown':sum(x['kernel'] is None for x in sub)})
csvrows=list(csv.DictReader(open(ROOT/'results/insertion_noise.csv')))
comparisons={}
for r in csvrows:
    key=(r['record'],r['noise_px'],r['rep']);comparisons.setdefault(key,{})[r['method']]=r
fields=('correct','wrong','missed','matched','expected','inserted_node_wrongly_matched')
agree=sum(all(d['unordered_bound'][f]==d['cyclic_bound'][f] for f in fields) for d in comparisons.values())
# Split-conflict output is repeated on every method row; it is a property of split alignment pair.
sub=[r for r in csvrows if r['record']=='R00705' and r['noise_px']=='4' and r['method']=='cyclic_bound']
correct=sum(int(r['correct']) for r in sub);expected=sum(int(r['expected']) for r in sub);conf=sum(int(r['split_pair_conflict']) for r in sub)
result={'exact_insertion':exact,'input_geometry_eligibility':summary,'invalid_input_details':[r for r in rows if r['reason']],
 'saved_output_identity_counts':{'paired_noise_instances':len(comparisons),'cyclic_vs_unordered_all_count_fields_identical':agree,
 'R00705_noise4':{'correct':correct,'expected':expected,'correct_coverage':correct/expected,'split_conflicts':conf,'repeats':len(sub)}}}
(OUT/'noise_design_audit.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
