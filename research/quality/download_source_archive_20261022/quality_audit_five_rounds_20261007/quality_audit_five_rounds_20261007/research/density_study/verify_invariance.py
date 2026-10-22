from core import *
from round_a import select
rows=[];replicate=[]
for c in select():
 r=c['record'];base=fit_boundary(r,starts=3)
 for mode,k in [('uniform',2),('uniform',4),('long',2),('long',4),('long',12),('short',12),('long_cluster',12)]:
  v,old=subdivision(r,mode,k);fit=fit_boundary(v,starts=3)
  z=dict(image=c['image'],kind=c['kind'],expression_id=r['id'],mode=mode,k=k,status=fit['status'],reason=fit.get('reason'))
  if base['status']=='ok' and fit['status']=='ok':
   z['original_vertex_move_max_h']=float(np.max(np.linalg.norm(base['floor']-fit['floor'][old],axis=1)))
   z.update(compare_shapes(fit['record'],base['record']))
  rows.append(z)
 source=up.analyze(comp.payload(r),coordinate_convention='continuous')['fit'];ours=fit_node(r)
 z=dict(image=c['image'],source_status=source['status'],replica_status=ours['status'])
 if source['status']=='ok' and ours['status']=='ok':z['max_floor_absolute_coordinate_delta_h']=float(np.max(abs(np.array(source['floor'])-ours['floor'])))
 replicate.append(z)
 save_csv('round_b_autoaxis_invariance.csv',rows);save_csv('equal_node_source_replication.csv',replicate)
 print(c['image'],flush=True)
