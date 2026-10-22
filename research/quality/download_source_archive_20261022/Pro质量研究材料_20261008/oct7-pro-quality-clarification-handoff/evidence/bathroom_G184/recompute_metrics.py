"""Small numeric replay from bundled selected_source.json; never edits source arrays."""
from pathlib import Path
import json,sys,numpy as np,pandas as pd
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'3d_compensation/vendor'))
from components_reused import intrinsic,compare
src=json.loads((O/'selected_source.json').read_text());s=src['scales'];rows=[]
for im in src['images']:
 for a in im['annotations']+im['references']:
  if a['id'] not in src['selected_ids'][im['code']] and a not in im['references']:continue
  intr=intrinsic(a)
  for ref in im['references']:
   row={'image':im['code'],'id':a['id'],'reference_id':ref['id'],**intr,**compare(a,ref)}
   if row.get('reference_status')=='ok':
    row['C']=row['centroid_distance_normalized'];row['LC_fixed']=1-row['iou']+.5*row['C'];row['area_ratio_to_GT']=row['area_h2']/row['reference_area_h2']
   if 'direction_rms_deg' in row and 'flat_top_angular_rms_deg' in row:
    row['J_fixed']=s['L']*(row['direction_rms_deg']/s['dir']+row['flat_top_angular_rms_deg']/s['flat'])/2
    if 'LC_fixed' in row:row['LCG_fixed']=row['LC_fixed']+.3*row['J_fixed']
   rows.append(row)
old=pd.read_csv(O/'selected_metrics.csv');checks=[]
for row in rows:
 prev=old[(old.id==row['id'])&(old.reference_id==row['reference_id'])].iloc[0]
 for key in ['iou','C','area_h2','area_ratio_to_GT','direction_rms_deg','flat_top_angular_rms_deg','LC_fixed','J_fixed','LCG_fixed']:
  a=row.get(key,float('nan'));b=prev.get(key,float('nan'))
  if pd.isna(a) and pd.isna(b):continue
  err=abs(a-b);assert err<1e-10,(row['id'],key,err)
  checks.append({'id':row['id'],'reference':row['reference_id'],'metric':key,'absolute_difference':err})
pd.DataFrame(rows).to_csv(O/'metrics_replayed.csv',index=False)
pd.DataFrame(checks).to_csv(O/'handoff_reproduction_checks.csv',index=False)
print(json.dumps({'rows':len(rows),'checks':len(checks),'max_absolute_difference':max(x['absolute_difference'] for x in checks)}))
