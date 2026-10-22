from pathlib import Path
import pandas as pd,numpy as np,json
R=Path(__import__('os').environ['PRO_PACKAGE']).resolve();O=Path(__file__).resolve().parent
a=pd.read_csv(R/'results/baseline_and_all_B_parameters.csv');rows=[]
for kind in ['changed_identity','missing_score','changed_boolean']:
 b=a.copy()
 if kind=='changed_identity':b.loc[0,'object_id']='WRONG_OBJECT'
 elif kind=='missing_score':b.loc[0,'B8L2_original']=np.nan
 else:
  # A real boolean result column is ignored by the reproduce.py numerical comparison.
  a=pd.read_csv(R/'results/normalized_scores891.csv');b=a.copy();b.loc[0,'answer_camera_inside']=not bool(a.loc[0,'answer_camera_inside'])
 num=[k for k in a.columns if pd.api.types.is_numeric_dtype(a[k]) and pd.api.types.is_numeric_dtype(b[k]) and a[k].dtype!='bool']
 errs=(a[num]-b[num]).abs();maxerr=float(np.nanmax(errs.to_numpy())) if len(num) else 0
 rows.append({'case':kind,'same_shape_columns':a.shape==b.shape and list(a.columns)==list(b.columns),'max_numeric_absolute_difference':maxerr,'would_raise_numeric_difference':maxerr>1e-9,'all_columns_semantically_equal':a.equals(b)})
(O/'replay_validator_robustness.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
