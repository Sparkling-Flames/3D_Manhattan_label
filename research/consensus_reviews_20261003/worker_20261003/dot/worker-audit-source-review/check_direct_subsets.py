"""Fresh four-person tiling checks, separate from full-pool integration."""
from pathlib import Path
import csv,json,sys,warnings
import numpy as np,shapely
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'worker-audit-original'))
from tools.thesis_main.analysis.worker_profiles_20261003 import panel_records
from tools.thesis_main.analysis.lee_tile_stage1_20261002 import tile_consensus,region_iou
base=ROOT/'worker-audit-original/analysis_results/worker_profiles_20261003'
workers,groups=panel_records(json.loads((base/'input.json').read_text()),json.loads((base/'block.json').read_text()))
a=list(csv.DictReader((base/'lobo_assignments.csv').open(encoding='utf-8-sig')))
npz=np.load(base/'subsets.npz');members=npz['members'];checks=[];notices=[]
for index,(im,rs,refs) in enumerate(groups):
    higher=np.array([next(r['relative_half']=='higher' for r in a if r['policy']=='original' and r['target_building']==im['building'] and r['worker']==w) for w in workers])
    h=higher[members].sum(axis=1)
    for count in [0,2,4]:
        j=int(np.flatnonzero(h==count)[0]);selection=members[j]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',RuntimeWarning)
            direct=tile_consensus([rs[int(i)] for i in selection])
            for method in ['mv50','mv_strict']:
                for version,points in refs.items():
                    got=region_iou(direct['regions'][method],Polygon(points));saved=float(npz[f'g{index}_{method}_{version}'][j])
                    checks.append(dict(image=im['code'],subset_index=j,higher_n=count,workers=[workers[int(i)] for i in selection],method=method,version=version,saved=saved,direct=got,abs_delta=abs(saved-got)))
        notices.extend(dict(image=im['code'],subset_index=j,message=m) for m in direct['warnings']+[str(w.message) for w in caught])
out=dict(environment=dict(python=sys.version,numpy=np.__version__,shapely=shapely.__version__,geos=shapely.geos_version_string),count=len(checks),max_abs_delta=max(r['abs_delta'] for r in checks),warnings=notices,checks=checks)
(ROOT/'worker-audit-source-review/direct_subset_checks.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='checks'},indent=2))
