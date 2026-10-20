"""Record semantic parity against retained derivatives; gzip byte identity is separate."""
from pathlib import Path
import argparse,json,hashlib,gzip
import numpy as np,pandas as pd
p=argparse.ArgumentParser();p.add_argument('--new',type=Path,required=True);p.add_argument('--old',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();result=[]
for old in sorted(a.old.glob('*')):
 new=a.new/old.name
 if not new.is_file() or not (old.name.endswith('.csv') or old.name.endswith('.csv.gz')):continue
 x=pd.read_csv(old,low_memory=False);y=pd.read_csv(new,low_memory=False)
 r={'file':old.name,'rows_old':len(x),'rows_new':len(y),'columns_equal':list(x)==list(y),'old_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'new_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'max_abs_numeric_difference':0.,'non_numeric_mismatches':{},'numeric_null_mismatches':{}}
 if r['columns_equal'] and len(x)==len(y):
  for c in x:
   if pd.api.types.is_numeric_dtype(x[c]) and pd.api.types.is_numeric_dtype(y[c]):
    nulls=int((x[c].isna()!=y[c].isna()).sum())
    if nulls:r['numeric_null_mismatches'][c]=nulls
    diff=(x[c].astype(float)-y[c].astype(float)).abs().max()
    if pd.notna(diff):r['max_abs_numeric_difference']=max(r['max_abs_numeric_difference'],float(diff))
   else:
    diff=int((x[c].fillna('<NULL>').astype(str)!=y[c].fillna('<NULL>').astype(str)).sum())
    if diff:r['non_numeric_mismatches'][c]=diff
 r['semantic_pass']=r['columns_equal'] and len(x)==len(y) and not r['numeric_null_mismatches'] and not r['non_numeric_mismatches'] and r['max_abs_numeric_difference']<=1e-12
 result.append(r)
a.out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
