import json,hashlib,math,zipfile,collections
from pathlib import Path
from shapely.geometry import Polygon
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[3]);ap.add_argument('--bundle',type=Path);args=ap.parse_args()
R=args.repo/'research';F=R/'quality_four_space_recompute_20261011';H=R/'quality_calibration_pro_handoff_20261011';V=R/'quality_review30_20261011/results';checks={}
h=lambda b:hashlib.sha256(b).hexdigest()
a=json.loads((F/'inputs/library/空间范围人工审核_2026-10-11.json').read_bytes());old=json.loads((F/'inputs/previous/quality_review30_receipt.json').read_bytes());seed=json.loads((F/'inputs/previous/editor_seed_data.json').read_text());rows=json.loads((F/'results/floor_recompute_20.json').read_text())['rows'];frozen={x['record_id']:x for x in json.loads((F/'inputs/frozen_components_20.json').read_text())}
checks['new_receipt_sha256']=h((F/'inputs/library/空间范围人工审核_2026-10-11.json').read_bytes());assert checks['new_receipt_sha256']=='754507bd4774baacdb2a8f4336b6a7af84387e4c39f2db39515180b4e9b4276e'
assert h((F/'inputs/previous/quality_review30_receipt.json').read_bytes())=='8e26b9cd8fa4fc1f978fb0b71453e2142878eca667cd5c525dd913d8077ad35c';assert a['historical_feedback']==old;checks['raw_receipts_and_history']='pass'
schema=json.loads((V/'receipt_schema_anonymous.json').read_text());assert schema['dataset_id']==old['dataset_id'];assert schema['display_order']==old['display_order'];assert [(x['case_id'],x['case_type']) for x in schema['rows']]==[(x['case_id'],x['case_type']) for x in old['answers']];checks['receipt_binding']='pass';checks['quality_labels']=dict(collections.Counter(x['absolute_quality'] for x in old['answers'] if x['case_type']=='quality'))
rs=a['records'][0]['space_regions']['regions'];P={k:Polygon(x['polygon']) for k,x in zip('ABCD',rs)};assert all(g.is_valid and not g.is_empty and g.area>0 for g in P.values());assert all(x['confirmed_version']['polygon']==x['polygon'] and x['top_boundary_pending'] for x in rs[2:]);checks['CD_confirmed_floor_only']='pass'
maxerr=0
for x in seed['images'][0]['annotations']:
 pts=[]
 for u,v in x['points'][1::2]:
  t=(u/1024-.5)*2*math.pi;r=1/math.tan((v/512-.5)*math.pi);pts.append((r*math.sin(t),-r*math.cos(t)))
 g=Polygon(pts);assert g.is_valid and not g.is_empty
 row=next(y for y in rows if y['record_id']==x['record_id']);assert row['object_id']==x['object_id'];assert h(json.dumps(x['points'],separators=(',',':')).encode())==row['current_points_sha256'];f=frozen[x['record_id']]
 assert row['frozen_Q']==f['Q'] and row['frozen_D_degrees']==f['dir'] and row['frozen_F_degrees']==f['flat'];assert row['new_full_Q'] is None and row['new_full_3d_IoU'] is None
 for k,p in P.items():
  maxerr=max(maxerr,abs(g.intersection(p).area/g.union(p).area-row[k+'_iou']))
assert maxerr<1e-12;checks['all_80_max_iou_difference']=maxerr;checks['all_20_frozen_Q_D_F_unchanged']=True;checks['formal_included_n']=sum(x['frozen_primary_included'] for x in rows);assert checks['formal_included_n']==18;checks['excluded_or_hold']=[x['record_id'] for x in rows if not x['frozen_primary_included']]
t=json.loads((H/'T03_projection_check.json').read_text());G=json.loads((V/'selected_geometry_private.json').read_text())['geometries'];S=json.loads((V/'selection_private.json').read_text());case=next(x for x in S['records'] if x['case_id']=='T03');ag=G[case['object_id']];gg=G[case['reference_object_id']]
for x in t['pairs']:
 ay=ag['points'][2*(x['annotation_pair']-1)+1][1];gy=gg['points'][2*(x['reference_pair']-1)+1][1];assert ay==x['annotation_floor_y'] and gy==x['GT_floor_y'];v=(1/math.tan((ay/512-.5)*math.pi))/(1/math.tan((gy/512-.5)*math.pi))-1;assert abs(v-x['radius_relative_error'])<1e-12
checks['T03_source_coordinates_and_projection']='pass'
manifest=json.loads((F/'FILE_MANIFEST_SHA256.json').read_text());bad=[];missing=[]
for x in manifest['files']:
 p=F/x['path']
 if not p.exists():missing.append(x['path'])
 elif h(p.read_bytes())!=x['sha256'] or p.stat().st_size!=x['bytes']:bad.append(x['path'])
checks['repo_manifest_hash_mismatches']=bad;checks['repo_manifest_untracked_entries']=missing
if args.bundle:
 assert h(args.bundle.read_bytes())=='56d9fdf4fd9a0ac9e6c96d508f66ebdf96c21544d314e9cee25348195dfa375d', 'Expected original Library version1 bundle bytes'
 with zipfile.ZipFile(args.bundle) as z:
  assert z.testzip() is None;mf=json.loads(z.read('FILE_MANIFEST_SHA256.json'));errors=[x['path'] for x in mf['files'] if h(z.read(x['path']))!=x['sha256'] or len(z.read(x['path']))!=x['bytes']];assert not errors;checks['library_v1_bundle_files_verified']=len(mf['files'])
else:checks['library_v1_bundle_files_verified']='not run; pass --bundle for original Library version1'
checks['scope']='Numerical/content audit at 3c416cd; original four archives metadata only, no claim of full internal archive validation; no final algorithm calibration.'
print(json.dumps(checks,ensure_ascii=False,indent=2))
