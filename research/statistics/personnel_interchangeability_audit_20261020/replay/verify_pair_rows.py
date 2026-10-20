from pathlib import Path
import pandas as pd,numpy as np,json
B=Path(__file__).resolve().parents[1];a=pd.read_csv(B/'unpacked/interchangeability_20261020/core_replay/EXPECTED_PAIRED_EVENTS.csv.gz');b=pd.read_csv(B/'audit_replay/core/REPLAYED_PAIRED_EVENTS.csv.gz');keys=['group','event_id'];a=a.sort_values(keys).reset_index(drop=True);b=b.sort_values(keys).reset_index(drop=True);fail=[];deltas={}
assert len(a)==len(b)==1819 and list(a)==list(b)
for c in a:
 if pd.api.types.is_numeric_dtype(a[c]) or pd.api.types.is_bool_dtype(a[c]):
  x=a[c].to_numpy(dtype=float);y=b[c].to_numpy(dtype=float);bad=~np.isclose(x,y,atol=1e-9,rtol=0,equal_nan=True)
  deltas[c]=float(np.nanmax(np.abs(x-y))) if np.isfinite(x-y).any()else None
 else:bad=~((a[c]==b[c])|(a[c].isna()&b[c].isna())).to_numpy()
 if bad.any():fail.append(dict(column=c,n=int(bad.sum()),rows=np.where(bad)[0].tolist()[:10]))
out=dict(all_passed=not fail,individual_paired_events_checked=len(a),columns_checked=len(a.columns),tolerance=1e-9,failures=fail,max_abs_difference_by_numeric_column=deltas,note='Independent row-by-row comparison in addition to the package core script aggregate comparison.');(B/'audit_replay/PAIRED_ROWS_INDEPENDENT.json').write_text(json.dumps(out,indent=2));print(out);assert not fail
