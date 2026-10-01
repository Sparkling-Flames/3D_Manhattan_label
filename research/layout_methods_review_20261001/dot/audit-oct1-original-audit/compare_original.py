"""Read-only comparison of immutable Stage2 snapshot and returned independent package.

Run: PYTHONPATH=../audit-oct1-deps python -B compare_original.py
No original or returned input/result files are written.
"""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import argparse
import csv
import hashlib
import json
import math
import sys
import warnings

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--original',type=Path,default=ROOT/'audit-oct1-original')
parser.add_argument('--returned',type=Path,default=ROOT/'audit-oct1-inputs/returned/layout_methods_20261001')
parser.add_argument('--out',type=Path,default=HERE)
args=parser.parse_args()
ORIGINAL=args.original.resolve()
RETURNED=args.returned.resolve()
OUTPUT=args.out.resolve(); OUTPUT.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(ORIGINAL),str(RETURNED/'src')]
import numpy as np
import geometry_core as returned_core
from run_replication import measure as returned_measure
from tools.thesis_main.analysis import layout_metric_response_20261001 as official
from tools.thesis_main.analysis.verify_layout_metric_snapshot_20261001 import verify_embedded,_compare
from tools.thesis_main.analysis.research_round_20260929 import reconstruct as official_reconstruct,declared_column_wall_mask

def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(name,obj):(OUTPUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
snapshot=load(ORIGINAL/'analysis_results/layout_metric_response_20261001/results.json')
ret_syn=load(RETURNED/'inputs/synthetic_74.json')
ret_real=load(RETURNED/'inputs/real_excerpts.json')
out={}
out['official_embedded']=verify_embedded(snapshot)

# Independently execute inventory and CSV portions without hiding the official
# full verifier's failure on an absent requirements.txt in the published commit.
manifest=load(ORIGINAL/'MANIFEST.json')
expected={x['path'] for x in manifest['files']}
actual={p.relative_to(ORIGINAL).as_posix() for p in ORIGINAL.rglob('*') if p.is_file()}-{'MANIFEST.json'}
out['inventory']={'missing':sorted(expected-actual),'unexpected':sorted(actual-expected),
 'wrong_size':[dict(path=x['path'],expected=x['bytes'],actual=(ORIGINAL/x['path']).stat().st_size)
 for x in manifest['files'] if (ORIGINAL/x['path']).exists() and (ORIGINAL/x['path']).stat().st_size!=x['bytes']]}
assert out['inventory']=={'missing':['requirements.txt'],'unexpected':[],'wrong_size':[]}
contract=load(ORIGINAL/'analysis_results/layout_metric_response_20261001/field_contract.json')
_compare(snapshot['plan'],load(ORIGINAL/'analysis_results/layout_metric_response_20261001/experiment_plan.json'),'plan_file')
csv_checks={}
for kind in ('synthetic','real'):
 with (ORIGINAL/f'analysis_results/layout_metric_response_20261001/{kind}_metrics.csv').open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f);rows=list(reader);fields=reader.fieldnames
 assert fields==contract['csv_fields'][kind]
 assert len(rows)==len(snapshot[kind])
 for i,(row,saved) in enumerate(zip(snapshot[kind],rows)):
  flat=official._flat(row)
  expected_row={key:json.dumps(flat[key],ensure_ascii=False) if isinstance(flat.get(key),(dict,list)) else str(flat[key]) if flat.get(key) is not None else '' for key in fields}
  _compare(expected_row,saved,f'{kind}_csv[{i}]')
 csv_checks[kind]={'rows':len(rows),'fields':len(fields),'exact_match':True}
out['original_csv']=csv_checks
out['source_hashes']={'count':len(load(HERE/'source_hashes.json')),'all_git_blob_match':all(x['git_blob_match'] for x in load(HERE/'source_hashes.json'))}

# Return package retained three real coordinate excerpts, not three people per image.
real_checks=[]
for a,b in ret_real:
 row=next(x for x in snapshot['real'] if x['id']==a['id'] and x['reference_id']==b['id'])
 entry={'image':row['image'],'a':a['id'],'b':b['id'],'reference_version':row['reference_version'],'records':[]}
 for side,r in [('a',a),('b',b)]:
  original=row[side]
  common=set(r)&set(original)
  same=[k for k in sorted(common) if original[k]==r[k]]
  changed={k:{'original':original[k],'returned':r[k]} for k in sorted(common) if original[k]!=r[k]}
  assert r['points']==original['points']
  assert r['id']==original['id'] and r['ring_confirmed']==original['ring_confirmed']
  entry['records'].append({'side':side,'exact_points':True,'point_rows':len(r['points']),'matching_shared_keys':same,'changed_shared_fields':changed,'omitted_fields':sorted(set(original)-set(r)),'added_fields':sorted(set(r)-set(original))})
 real_checks.append(entry)
out['real_excerpts']=real_checks
out['real_panel']={'rows':len(snapshot['real']),'images':len({x['image'] for x in snapshot['real']}),'selected_personnel_records':len({x['id'] for x in snapshot['real']}),'personnel_count_per_image':dict(Counter({image:len({x['id'] for x in snapshot['real'] if x['image']==image}) for image in {x['image'] for x in snapshot['real']}})),'real_comparisons':sum(x['b'] is not None for x in snapshot['real']),'missing_reference_rows':sum(x['b'] is None for x in snapshot['real']),'available_reference_versions':dict(Counter(x['reference_version'] for x in snapshot['real'] if x['b'] is not None))}

# Synthetic coordinates: compare generated transcription against authoritative
# embedded inputs, without assuming byte identity or label identity.
syn_checks=[]
for i,(r,o) in enumerate(zip(ret_syn,snapshot['synthetic'])):
 assert (r['family'],r['case'],r['amplitude'])==(o['family'],o['case'],o['amplitude'])
 assert [[a==b for b in r['b']['source_pair_indices']] for a in r['a']['source_pair_indices']]==[[a==b for b in o['b']['source_pair_indices']] for a in o['a']['source_pair_indices']]
 e={'index':i,'case':r['case'],'amplitude':r['amplitude'],'sides':[]}
 for side in ('a','b'):
  p,q=np.array(r[side]['points']),np.array(o[side]['points'])
  assert p.shape==q.shape and np.allclose(p,q,rtol=0,atol=2e-12)
  e['sides'].append({'side':side,'max_abs_coordinate_delta_px':float(abs(p-q).max()),'exact_coordinates':bool(np.array_equal(p,q)), 'labels_exact':r[side]['source_pair_indices']==o[side]['source_pair_indices'], 'label_renames':[[a,b] for a,b in zip(o[side]['source_pair_indices'],r[side]['source_pair_indices']) if a!=b]})
 syn_checks.append(e)
out['synthetic_inputs']={'pairs':len(syn_checks),'sides':2*len(syn_checks),'max_abs_coordinate_delta_px':max(s['max_abs_coordinate_delta_px'] for e in syn_checks for s in e['sides']),'exact_coordinate_sides':sum(s['exact_coordinates'] for e in syn_checks for s in e['sides']),'label_renamed_sides':sum(not s['labels_exact'] for e in syn_checks for s in e['sides']),'details':syn_checks}

metric_map={'bev_iou':('bev','bev_range_iou'),'area_a':('bev','area_a_h2'),'area_b':('bev','area_b_h2'),'coverage_a':('bev','coverage_of_a'),'coverage_b':('bev','coverage_of_b'),'centroid':('bev','centroid_distance_h'),'boundary_mean':('boundary','boundary_mean_distance'),'boundary_p95':('boundary','boundary_p95_distance'),'boundary_sampled_max':('boundary','boundary_sampled_max'),'boundary_step_bound':('boundary','sampled_max_upper_error_bound_h')}
for w in (512,1024):
 metric_map[f'column_iou_{w}']=('column',f'{w}x{w//2}','iou')
 metric_map[f'diff_pixels_{w}']=('column',f'{w}x{w//2}','differing_pixels')
def get(d,path):
 for k in path:d=d.get(k) if isinstance(d,dict) else None
 return d
def compare_metrics(ret,orig,entry):
 mismatches=[];maxdelta={};available=0
 for key,path in metric_map.items():
  a,b=ret.get(key),get(orig,path)
  if a is None and b is None:continue
  if a is None or b is None:mismatches.append({'field':key,'returned':a,'original':b});continue
  delta=abs(a-b);maxdelta[key]=delta;available+=1
  good=a==b if key.startswith('diff_pixels') else math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-10)
  if not good:mismatches.append({'field':key,'returned':a,'original':b,'delta':delta})
 return dict(entry,compared_fields=available,max_abs_deltas=maxdelta,mismatches=mismatches)

# Direct cross-implementation comparisons include all 15 real comparisons,
# extending the returned package's stated three-real scope safely.
comparisons=[];mask_checks=[]
for kind,rows in [('synthetic',snapshot['synthetic']),('real',[x for x in snapshot['real'] if x['b'] is not None])]:
 for i,row in enumerate(rows):
  entry={'kind':kind,'index':i,'case':row.get('case'), 'id':row.get('id'),'amplitude':row.get('amplitude')}
  ret=returned_measure(row['a'],row['b'])
  comparisons.append(compare_metrics(ret,row['metrics'],entry))
  for side in ('a','b'):
   rec=row[side];g1=official_reconstruct(rec,coordinate_convention=rec.get('coordinate_convention','continuous'));g2=returned_core.reconstruct(rec)
   for w in (512,1024):
    try:a=declared_column_wall_mask(g1,w,w//2)
    except ValueError:a=None
    try:b=returned_core.column_mask(g2,w)
    except ValueError:b=None
    different=None if a is None or b is None else int((a^b).sum())
    mask_checks.append(dict(entry,side=side,width=w,original_available=a is not None,returned_available=b is not None,differing_pixels=different))
out['cross_implementation']={'comparisons':len(comparisons),'compared_numeric_fields':sum(x['compared_fields'] for x in comparisons),'mismatch_rows':[x for x in comparisons if x['mismatches']],'maximum_deltas':{key:max((x['max_abs_deltas'].get(key,0) for x in comparisons),default=0) for key in metric_map},'mask_checks':len(mask_checks),'available_masks':sum(x['differing_pixels'] is not None for x in mask_checks),'mask_mismatch_rows':[x for x in mask_checks if x['original_available']!=x['returned_available'] or x['differing_pixels'] not in (None,0)]}
assert not out['cross_implementation']['mismatch_rows']
assert not out['cross_implementation']['mask_mismatch_rows']
dump('cross_implementation_details.json',{'metrics':comparisons,'masks':mask_checks})

# Verify delivered numeric CSVs against official outputs, not just independent
# code versus its own outputs.
saved_checks=[]
for name,kind in [('snapshot_74_independent.csv','synthetic'),('real_recomputed.csv','real')]:
 with (RETURNED/'results'/name).open() as f:rows=list(csv.DictReader(f))
 for i,r in enumerate(rows):
  official_row=snapshot['synthetic'][i] if kind=='synthetic' else next(x for x in snapshot['real'] if x['id']==r['a'] and x['reference_id']==r['b'])
  nums={k:float(v) if not k.startswith('diff_pixels') else int(v) for k,v in r.items() if k in metric_map and v!=''}
  saved_checks.append(compare_metrics(nums,official_row['metrics'],{'file':name,'row':i}))
out['delivered_vs_original']={'rows':len(saved_checks),'compared_fields':sum(x['compared_fields'] for x in saved_checks),'mismatch_rows':[x for x in saved_checks if x['mismatches']],'maximum_deltas':{key:max((x['max_abs_deltas'].get(key,0) for x in saved_checks),default=0) for key in metric_map}}
assert not out['delivered_vs_original']['mismatch_rows']

# Explicit guard-contract differences. These are out of the supplied valid
# experiment domain and must not be mistaken for invalidating those results.
base=deepcopy(snapshot['synthetic'][0]['b'])
def setval(rec,path,value):
 x=rec
 for k in path[:-1]:x=x[k]
 x[path[-1]]=value
mutations=[('top_y_negative',lambda r:setval(r,['points',0,1],-1.)),('top_y_nan',lambda r:setval(r,['points',0,1],float('nan'))),('top_at_pole',lambda r:setval(r,['points',0,1],0.)),('duplicate_pair_identity',lambda r:setval(r,['source_pair_indices',1],r['source_pair_indices'][0])),('unknown_phase',lambda r:r.update(coordinate_convention='unknown')),('periodic_x_outside_image',lambda r:[setval(r,['points',i,0],r['points'][i][0]+1024) for i in (0,1)]),('missing_points',lambda r:r.update(points=None)),('odd_point_count',lambda r:r['points'].pop())]
guards=[]
for name,mutation in mutations:
 r=deepcopy(base);mutation(r)
 e={'case':name}
 for which,fn in [('original',lambda:official.measure(r,base,synthetic=False)),('returned',lambda:returned_measure(r,base))]:
  try:
   with warnings.catch_warnings(record=True) as ws:
    warnings.simplefilter('always');v=fn()
   if which=='original':e[which]={'bev':v['bev'],'column_1024':v['column']['1024x512'],'warnings':[str(x.message) for x in ws]}
   else:e[which]={'bev_iou':v.get('bev_iou'),'bev_reason':v.get('bev_reason'),'column_iou_1024':v.get('column_iou_1024'),'column_reason_1024':v.get('column_reason_1024'),'warnings':[str(x.message) for x in ws]}
  except Exception as ex:e[which]={'exception':type(ex).__name__,'message':str(ex)}
 guards.append(e)
out['guard_contract_probes']=guards
dump('comparison_summary.json',out)
print(json.dumps({k:v for k,v in out.items() if k not in ('synthetic_inputs','real_excerpts','guard_contract_probes')},ensure_ascii=False,indent=2))
print('synthetic_inputs_summary',json.dumps({k:v for k,v in out['synthetic_inputs'].items() if k!='details'}))
print('guard_contract_probes',json.dumps(guards,ensure_ascii=False,indent=2))
