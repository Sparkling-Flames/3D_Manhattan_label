from core import *
from round_a import select
fields=['direction_rms_deg','flat_top_angular_rms_deg','height_mean_h','height_internal_rms_h','height_internal_relative_rms','height_max_deviation_h','max_depth_sensitivity_h_per_Cpx']
rows=[]
for c in select():
 r=c['record'];base=comp.intrinsic(r)
 for mode,k in [('uniform',2),('uniform',4),('long',2),('long',4),('long',12),('short',12),('long_cluster',12)]:
  v,_=subdivision(r,mode,k);new=comp.intrinsic(v)
  z=dict(image=c['image'],expression_id=r['id'],kind=c['kind'],mode=mode,k=k,status=new['geometry_status'])
  for field in fields:
   if field in base and field in new:z['delta_'+field]=new[field]-base[field]
  rows.append(z)
save_csv('round_a_raw_intrinsic_invariance.csv',rows)
print({field:max(abs(r.get('delta_'+field,0)) for r in rows) for field in fields})
