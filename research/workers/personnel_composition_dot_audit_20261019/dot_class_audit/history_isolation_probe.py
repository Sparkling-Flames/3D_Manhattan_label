import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import sys,json,gzip,hashlib
from pathlib import Path
import pandas as pd,numpy as np
base=Path('/workspace/shared/composition_audit_20261019'); package=base/'extracted/personnel_composition_study_20261019/analysis';repo=base/'source_repository';out=base/'dot_class_audit'
sys.path.insert(0,str(package/'forward'));import build_forward as fwd
_,fn=fwd.upstream_functions(repo);hist=fwd.read_history(json.loads((package/'composition/SPLIT.json').read_text()));ev=json.load(gzip.open(repo/fwd.RECORD_SOURCE,'rt'))['records'];d=fwd.flatten(ev);ex=fn['extra_frame'](ev);workers=sorted(d.loc[d.quality_usable,'worker_id'].unique());a,meta=fn['_training_features'](d,ex,workers,hist,'B8L2');a,_=fwd.conditional_features(d,a,hist,fn,'B8L2')
# Independently delete every nonhistory row, not merely numeric values; keep fixed roster.
b,meta2=fn['_training_features'](d[d.building_id.isin(hist)].copy(),ex[ex.building_id.isin(hist)].copy(),workers,hist,'B8L2');b,_=fwd.conditional_features(d[d.building_id.isin(hist)].copy(),b,hist,fn,'B8L2');pd.testing.assert_frame_equal(a,b,check_exact=True)
source_expected=json.loads((package/'forward/results/feature_fit_receipt.json').read_text())['source_hashes'];hashes={rel:{'actual':hashlib.sha256((repo/rel).read_bytes()).hexdigest(),'expected':sha} for rel,sha in source_expected.items()}
report={'test':'Delete all nonhistory rows before all estimators; retain fixed 60-person roster','deleted_records':int((~d.building_id.isin(hist)).sum()),'history_records':int(d.building_id.isin(hist).sum()),'all_features_identical':True,'fitted_columns':len(a.columns),'workers':len(workers),'source_hashes':hashes,'all_source_hashes_match':all(v['actual']==v['expected'] for v in hashes.values())};(out/'HISTORY_ISOLATION_PROBE.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
