"""Observe warned symmetric-difference operands without altering upstream geometry."""
from pathlib import Path
import inspect,json,sys,warnings
import numpy as np,shapely
from shapely.geometry.base import BaseGeometry

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'worker-audit-original'))
from tools.thesis_main.analysis.worker_profiles_20261003 import panel_records
from tools.thesis_main.analysis.lee_tile_precision_20261003 import integration_basis,validate_refinement
source=ROOT/'worker-audit-original/analysis_results/worker_profiles_20261003'
data=json.loads((source/'input.json').read_text());block=json.loads((source/'block.json').read_text())
workers,groups=panel_records(data,block)
im,rs,refs=next(g for g in groups if g[0]['code']=='e9zR4mvMWw7-19')
events=[];original=BaseGeometry.symmetric_difference
def observed(a,b,*args,**kwargs):
    frame=inspect.currentframe().f_back
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',RuntimeWarning)
        result=original(a,b,*args,**kwargs)
    if caught:
        k=frame.f_locals.get('k');method=frame.f_locals.get('method')
        events.append(dict(image=im['code'],file=Path(frame.f_code.co_filename).name,function=frame.f_code.co_name,line=frame.f_lineno,k=k,method=method,record_ids=[r['id'] for r in rs[:k]] if k else None,workers=[r['worker'] for r in rs[:k]] if k else None,a_valid=a.is_valid,b_valid=b.is_valid,a_area=a.area,b_area=b.area,result_area=result.area,result_valid=result.is_valid,a_wkb=a.wkb_hex,b_wkb=b.wkb_hex,messages=[str(w.message) for w in caught]))
    for w in caught:warnings.warn(str(w.message),w.category)
    return result
BaseGeometry.symmetric_difference=observed
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always',RuntimeWarning)
    basis=integration_basis(rs,refs)
    delta,inner=validate_refinement(basis,rs)
BaseGeometry.symmetric_difference=original
out=dict(environment=dict(python=sys.version,numpy=np.__version__,shapely=shapely.__version__,geos=shapely.geos_version_string),scope='Current B-line e9zR4mvMWw7-19 only; unchanged source validate_refinement',events=events,max_geometry_delta=delta,inner=inner,caught=[str(w.message) for w in caught])
(ROOT/'worker-audit-source-review/warning_operands.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
print(json.dumps({**out,'events':[{k:v for k,v in e.items() if not k.endswith('wkb')} for e in events]},indent=2))
