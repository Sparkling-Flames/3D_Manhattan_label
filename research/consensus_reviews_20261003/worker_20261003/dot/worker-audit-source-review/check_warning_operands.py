"""Re-evaluate original warned operands, preserving vertices and precision."""
import json,sys,warnings
from pathlib import Path
import numpy as np,shapely
from shapely import from_wkb
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parent.parent
events=json.loads((ROOT/'worker-audit-source-review/warning_operands.json').read_text())['events']
data=json.loads((ROOT/'worker-audit-original/analysis_results/worker_profiles_20261003/input.json').read_text())
images={im['code']:im for im in data['images']};checks=[]
for event in events:
    im=images[event['image']];r=next(r for r in im['annotations'] if r['id']==event['record_ids'][0])
    direct=Polygon(r['footprint']);a,b=map(lambda h:from_wkb(bytes.fromhex(h)),[event['a_wkb'],event['b_wkb']])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',RuntimeWarning)
        checks.append(dict(image=event['image'],k=event['k'],method=event['method'],source_polygon_equals_current=direct.equals(a),symmetric_difference=a.symmetric_difference(b).area,reverse_symmetric_difference=b.symmetric_difference(a).area,two_sided_difference=a.difference(b).area+b.difference(a).area,area_difference=abs(a.area-b.area),source_to_current_area=direct.symmetric_difference(a).area,source_to_offline_area=direct.symmetric_difference(b).area,reference_iou_deltas={r['version']:abs((lambda g:a.intersection(g).area/a.union(g).area)(Polygon(r['footprint']))-(lambda g:b.intersection(g).area/b.union(g).area)(Polygon(r['footprint']))) for r in im['references']}))
    checks[-1]['warnings']=[str(w.message) for w in caught]
out=dict(environment=dict(python=sys.version,numpy=np.__version__,shapely=shapely.__version__,geos=shapely.geos_version_string),checks=checks)
path=ROOT/'worker-audit-source-review'/('warning_checks_'+shapely.__version__+'.json')
path.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps(out,indent=2))
