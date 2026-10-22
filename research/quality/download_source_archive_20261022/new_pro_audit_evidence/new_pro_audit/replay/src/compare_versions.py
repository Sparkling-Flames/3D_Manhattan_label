"""Compare scores only when answer, fixed reference, target, eligibility and geometry agree.
Changed reference/catalog/eligibility is reported separately, never called an algorithm gain.
"""
import argparse,json
from pathlib import Path
import pandas as pd
FIELDS=['reference_id','current_target_id','answer_sha256','reference_sha256','eligibility_version','reference_catalog_sha256']
def compare(left,right,out):
 a=pd.read_csv(left,dtype={'object_id':str}).set_index('object_id');b=pd.read_csv(right,dtype={'object_id':str}).set_index('object_id')
 if not a.index.is_unique or not b.index.is_unique:raise ValueError('duplicate object_id; compare explicit cohorts separately')
 for c in FIELDS+['status','QA','QB','QC']:
  if c not in a or c not in b:raise ValueError('missing audit field '+c)
 rows=[]
 for oid in sorted(set(a.index)|set(b.index)):
  z={'object_id':oid}
  if oid not in a.index:z.update(comparison_status='added',changed_fields='')
  elif oid not in b.index:z.update(comparison_status='removed',changed_fields='')
  else:
   x=a.loc[oid];y=b.loc[oid];changed=[k for k in FIELDS if str(x[k])!=str(y[k])]
   if changed:z.update(comparison_status='input_or_reference_or_eligibility_changed',changed_fields=';'.join(changed))
   elif x.status!='ok' or y.status!='ok':z.update(comparison_status='not_jointly_evaluable',changed_fields='')
   else:z.update(comparison_status='same_input_delta',changed_fields='',**{'delta_'+k:float(y[k]-x[k]) for k in ['QA','QB','QC']})
  rows.append(z)
 out=Path(out)
 if out.exists():raise FileExistsError('choose a new comparison output')
 out.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(out,index=False)
 print(pd.DataFrame(rows).comparison_status.value_counts().to_json());return rows
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--left',required=True);ap.add_argument('--right',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();compare(a.left,a.right,a.out)
