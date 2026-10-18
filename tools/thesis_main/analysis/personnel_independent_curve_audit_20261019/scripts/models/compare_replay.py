from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,sys
R=Path('/workspace/shared/personnel_v2_audit_20261018');S=R/'extracted/work_v2_20261019/profiles';O=R/'independent/models';rows=[]
for fn in ['records_flat.csv','full_profiles.csv','fold_profiles.csv','nested_fold_features.csv','paired_model_comparison.csv','fine_information_controls.csv','fine_dtype_membership.csv','fine_dtype_stability.csv','v1_existing_effect_replication.csv','v1_original_separate_difficulty_replay.csv']:
 a=pd.read_csv(S/fn);b=pd.read_csv(O/'replay'/fn);common=list(a.columns.intersection(b.columns));shape=a.shape==b.shape;err=0.;equal=True
 for c in common:
  if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c]):
   x=a[c].to_numpy(float);y=b[c].to_numpy(float)
   if x.shape!=y.shape:equal=False;continue
   equal &= bool(np.allclose(x,y,atol=1e-9,rtol=1e-9,equal_nan=True));e=np.abs(x-y);err=max(err,float(np.nanmax(e)) if np.isfinite(e).any() else 0.)
  else: equal &= a[c].fillna('__NA__').equals(b[c].fillna('__NA__'))
 rows.append({'file':fn,'same_shape':shape,'all_common_columns_match_tolerance_1e-9':equal,'max_numeric_error':err})
(O/'REPLAY_COMPARISON.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
