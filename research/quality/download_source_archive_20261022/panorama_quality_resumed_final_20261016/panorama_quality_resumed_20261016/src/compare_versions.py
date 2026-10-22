"""Compare score outputs only on identical object / fixed-target / geometry sets.
Reference changes, missing scores and dropped rows are explicit, not algorithm gains.
Accepts JSONL from score_manifest.py; does not mutate either input.
"""
from pathlib import Path
import argparse,json
import pandas as pd
KEYS=['object_id','image_id','current_target_id','reference_id','answer_sha256','reference_sha256']
def compare(old,new,column):
 a=pd.DataFrame(old);b=pd.DataFrame(new)
 for df in [a,b]:
  if df.object_id.duplicated().any():raise ValueError('duplicate_object_id')
  for k in KEYS:
   if k not in df:raise ValueError('missing_identity_column:'+k)
 merged=a.merge(b,on='object_id',how='outer',suffixes=('_old','_new'),indicator=True)
 rows=[]
 for _,r in merged.iterrows():
  status='same_input'
  if r['_merge']!='both':status=str(r['_merge'])
  elif any(r[k+'_old']!=r[k+'_new'] for k in KEYS if k!='object_id'):status='changed_target_or_geometry'
  x=r.get(column+'_old');y=r.get(column+'_new')
  if status=='same_input' and (pd.isna(x) or pd.isna(y)):status='missing_score_not_zero'
  rows.append(dict(object_id=r.object_id,status=status,old=x,new=y,delta=float(y-x) if status=='same_input' else None))
 return pd.DataFrame(rows)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--old',required=True);p.add_argument('--new',required=True);p.add_argument('--column',required=True);p.add_argument('--output',required=True);args=p.parse_args()
 if Path(args.output).exists():raise SystemExit('Refusing overwrite')
 load=lambda f:[json.loads(x) for x in Path(f).read_text().splitlines() if x.strip()]
 compare(load(args.old),load(args.new),args.column).to_csv(args.output,index=False)
