"""Audit exact small input blobs and numerical geometry excerpts, without claiming full-bundle validation."""
from pathlib import Path
import os,json,hashlib,platform
import numpy as np,pandas as pd,scipy,shapely,sklearn
from finite_pool import make_basis
ROOT=Path(os.environ.get('WORKER_RESEARCH_ROOT',Path(__file__).resolve().parents[1]))
expected={'matrix_original_iou.csv':'85a4f601dc32ca9a93b9668223acd401190b49d0','matrix_revised_where_available_iou.csv':'493173aa20638ee9fb9c25b81e9a01080350fafe','one_image_geometry.json':'d435129575849339e264867e2f9c797084b31a26'}
checks=[]
for name,sha in expected.items():
 b=(ROOT/'inputs'/name).read_bytes();actual=hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest();assert actual==sha
 checks.append(dict(file=name,bytes=len(b),git_blob=actual,exact_blob_match=True,sha256=hashlib.sha256(b).hexdigest()))
mat=pd.read_csv(ROOT/'inputs/matrix_original_iou.csv').set_index('image');geo=[]
for f in ['one_image_geometry.json','rpc_geometry.json']:
 d=json.loads((ROOT/'inputs'/f).read_text());basis=make_basis(d['records'],d['reference']);assert len(d['records'])==24
 for i,r in enumerate(d['records']):
  score=basis.iou(basis.subset([i],'mv50'));target=float(mat.loc[d['image'],r['worker']]);assert abs(score-target)<1e-12
  geo.append(dict(image=d['image'],worker=r['worker'],record_id=r['id'],computed_iou=score,source_matrix_iou=target,absolute_difference=abs(score-target)))
pd.DataFrame(geo).to_csv(ROOT/'results/input_geometry_crosscheck.csv',index=False)
(ROOT/'results/input_audit.json').write_text(json.dumps(dict(source_commit='ad12d64d3567235e5691f9142d045df63b38b4e4',exact_inputs=checks,geometry_records_crosschecked=48,max_geometry_score_difference=max(x['absolute_difference'] for x in geo),full_current_bundle_verified=False,original_images_available=False,notes=['rpc_geometry.json and high_support_inventory_excerpt.csv are numerical/categorical excerpts, not byte-identical full source files.','Agreement with saved scores does not certify original images, labels, independence causality or the reference.']),ensure_ascii=False,indent=2)+'\n')
(ROOT/'environment.json').write_text(json.dumps(dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,pandas=pd.__version__,shapely=shapely.__version__,sklearn=sklearn.__version__),indent=2)+'\n')
print('Three exact blobs verified; 48 floor polygons crosschecked; full bundle NOT verified.')
