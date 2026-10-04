"""Resolve first-pass harness findings transparently, retaining raw failure evidence."""
from pathlib import Path
import json,sys,argparse
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,default=Path(__file__).resolve().parents[1]/'author_bundle');parser.add_argument('--evidence',type=Path,default=Path(__file__).resolve().parent);parser.add_argument('--old-evidence',type=Path,default=Path(__file__).resolve().parent/'overlay-old-geos/overlay_resolution.json');args=parser.parse_args();p=args.evidence;b=args.bundle
x=json.loads((p/'results/audit_results.json').read_text());r=json.loads((p/'overlay_resolution.json').read_text());old=json.loads(args.old_evidence.read_text())
# run_all intentionally regenerates 41, while rpc_input_crosscheck is restore-time evidence.
f=pd.read_csv(b/'results/rpc_input_crosscheck.csv');d=json.loads((b/'inputs/rpc_geometry.json').read_text());rr={q['worker']:q for q in d['records']};g=Polygon(d['reference']['footprint']);m=pd.read_csv(b/'inputs/matrix_original_iou.csv').set_index('image');checks=[]
for _,row in f.iterrows():
 z=rr[row.worker];poly=Polygon(z['footprint']);iou=poly.intersection(g).area/poly.union(g).area
 checks.append(dict(worker=row.worker,id_match=z['id']==row.record_id,valid_match=bool(row.valid)==poly.is_valid,iou_error=abs(iou-row.computed_iou),matrix_error=abs(row.source_matrix_iou-m.loc[d['image'],row.worker]),area_error=abs(poly.area-row.computed_area)))
pd.DataFrame(checks).to_csv(p/'results/rpc_provenance_crosscheck_independent.csv',index=False)
assert len(checks)==24 and all(q['id_match'] and q['valid_match'] and max(q['iou_error'],q['matrix_error'],q['area_error'])<2e-12 for q in checks)
assert x['replay_comparison']['counts']==dict(exact_bytes=37,exact_arrays=4,missing=1)
assert r['union_preservation']==dict(any_input_contains_probe=True,unary_union_contains_probe=False)
assert r['six_only_tile']['versus_full_tile_symdiff']==0
assert all(q['versus_full_tile_symdiff']<2e-12 for q in r['union_orders'])
assert all(q['versus_full_tile_symdiff']<2e-12 for q in r['consensus_orders'][1:])
assert all(q['versus_full_tile_symdiff']<2e-12 for q in old['consensus_orders'])
assert sum(q['inside'] for q in r['decimal70_point_votes'])==3
assert all(q['valid'] for q in r['validity'])
assert len(x['conclusion']['failures'])==2
x['first_pass_conclusion']=x.pop('conclusion')
x['resolved_findings']=[dict(finding='One result file absent from run_all',resolution='rpc_input_crosscheck.csv is an input-restoration provenance artifact, not one of the 41 run_all products. Its 24 ID/validity/IoU/matrix/area rows were independently verified.',status='documented boundary'),dict(finding='First direct geometry comparator differs on one sampled six-person set',resolution=r['resolution'],status='auditor comparator GEOS numerical path limitation; not observed source-code bug',fixture='overlay_failure_fixture.json',current_environment=r['environment'],old_environment=old['environment'],unary_union_iou=r['consensus_orders'][0]['iou'],tile_iou=r['full_tile']['iou'],symdiff_area=r['lost_region']['area'])]
x['conclusion']=dict(status='REPRODUCED_WITH_DOCUMENTED_GEOMETRY_COMPARATOR_LIMITATION',author_tests='35/35 passed',full_pipeline='11 stages completed once continuously; 41 numerical results exactly matched',independent_checks='480 matrix scores; 490 excerpt fields; 438 ledger fields; 16 holdout perturbations; 5760 finite-pool cases; 269192 real six-person identity sets under 2 rules',unresolved_author_numerical_failures=[],geometry_comparator_limit='Full all-subset re-enumeration shares planar-arrangement design; independent direct overlay on samples encountered one reproducible GEOS3.13.1 unary_union path defect, resolved by alternate order, binary union, six-only tiling and old GEOS on that fixture. Do not claim every implementation is bitwise reliable.',limits=x['first_pass_conclusion']['limits'])
(p/'audit_final_results.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(x['conclusion'],ensure_ascii=False,indent=2))
