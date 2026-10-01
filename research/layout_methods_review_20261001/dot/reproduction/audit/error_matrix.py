#!/usr/bin/env python3
"""Explicit input-error probes; statuses are observations, not an asserted original contract."""
import sys,json,copy,warnings,pathlib,csv,contextlib,io,argparse
import numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--work',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1]);args=parser.parse_args()
ROOT=args.work.resolve();sys.path.insert(0,str(ROOT/'returned_copy/src'))
from geometry_core import from_floor,reconstruct
from run_replication import measure
BASE=from_floor([[-2,-2],[2,-2],[2,2],[-2,2]])
def pair_change(side,axis,value):
 r=copy.deepcopy(BASE);r['points'][side][axis]=value;return r
cases=[('valid_control',BASE),('bottom_wrong_hemisphere',pair_change(1,1,200)),('bottom_near_horizon',pair_change(1,1,256.5)),('top_wrong_hemisphere',pair_change(0,1,300)),('top_near_horizon',pair_change(0,1,255.5)),('vertical_pair_mismatch',pair_change(0,0,BASE['points'][0][0]+1)),('self_intersecting_footprint',from_floor([[-2,-2],[2,2],[2,-2],[-2,2]])),('repeated_vertex',from_floor([[-2,-2],[2,-2],[2,-2],[2,2],[-2,2]])),('camera_outside',from_floor([[2,2],[4,2],[4,4],[2,4]])),('camera_boundary',from_floor([[-2,-2],[0,-2],[0,2],[-2,2]])),('nan_x',pair_change(0,0,float('nan'))),('infinite_bottom_y',pair_change(1,1,float('inf')))]
for name,pts in [('odd_point_count',BASE['points'][:-1]),('empty_points',[]),('only_two_pairs',BASE['points'][:4])]:
 r=copy.deepcopy(BASE);r['points']=pts;cases.append((name,r))
r=copy.deepcopy(BASE);r['coordinate_convention']='unrecognized';cases.append(('unknown_coordinate_convention',r))
rows=[]
for name,rec in cases:
 row={'case':name}
 with warnings.catch_warnings(record=True) as captured:
  warnings.simplefilter('always')
  try:
   geo=reconstruct(rec);row.update(reconstruct_returned=True,bev_reason=geo['reason'],wall_reason=geo['wall_reason'],camera=geo['camera']);m=measure(rec,BASE);row['measure']=m
   row['status']='returned_results_or_reason'
  except Exception as e:row.update(status='exception',exception_type=type(e).__name__,exception_text=str(e))
  row['warnings']=[str(w.message) for w in captured]
 rows.append(row)
expected={'bottom_wrong_hemisphere':('wrong_hemisphere','wrong_hemisphere'),'bottom_near_horizon':('near_horizon','near_horizon'),'top_wrong_hemisphere':(None,'wrong_hemisphere'),'top_near_horizon':(None,'near_horizon'),'vertical_pair_mismatch':(None,'vertical_pair_mismatch'),'self_intersecting_footprint':('invalid_footprint','invalid_footprint'),'repeated_vertex':('invalid_footprint','invalid_footprint'),'camera_outside':(None,'camera_not_strictly_inside'),'camera_boundary':(None,'camera_not_strictly_inside')}
for row in rows:
 if row['case'] in expected:row['expected_reason_probe_pass']=(row.get('bev_reason'),row.get('wall_reason'))==expected[row['case']]
(ROOT/'audit/error_handling.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
with (ROOT/'audit/error_handling.csv').open('w',newline='') as f:
 fields=['case','status','bev_reason','wall_reason','camera','exception_type','exception_text','expected_reason_probe_pass'];w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
print(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False))
