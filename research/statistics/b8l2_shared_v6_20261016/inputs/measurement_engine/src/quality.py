"""Independent closed-form WQ-LS08/current comparison; frozen geometry engine.
Not a learned human quality scale. The reference is supplied, never optimized here.
"""
from pathlib import Path
import sys,json,math
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
# A fixed research version: reject configuration drift instead of silently ignoring it.
PARAMS=json.loads((ROOT/'configs/WQ_LS08_UNCHANGED.json').read_text(encoding='utf-8'))['config']
EXPECTED={'combine':'loss_sum','iou_power':1.0,'boundary_scale':math.sqrt(32.0),
'direction_scale':math.sqrt(37.5),'direction_cap':1.5,'global_scale':0.8,'local_scale':0.25,
'boundary_power':2.0,'direction_power':2.0,'global_power':2.0,'local_power':2.0}
for key,value in EXPECTED.items():
    actual=PARAMS.get(key)
    if actual!=value and not (isinstance(actual,(int,float)) and isinstance(value,(int,float)) and math.isclose(actual,value,rel_tol=0,abs_tol=1e-12)):
        raise ValueError('Frozen WQ configuration drift: '+key)
sys.path.insert(0,str(ROOT/'engine'))
import audit_geometry as au, geometric_components as sp, strict_geometry as valid
import height_revision as hm, centered_height as center, traditional_metrics as trad
from prepare_inputs import geometry

def score(m):
 vals=[m.get(k) for k in ('iou_2d','S_bottom_deg','dir')]
 if any(v is None or not math.isfinite(float(v)) for v in vals):return dict(status='unavailable',WQ=None,current=None,floor_WQ=None)
 I,S,D=map(float,vals)
 if not(-1e-9<=I<=1+1e-9 and S>=0 and 0<=D<=45+1e-7):raise ValueError('metric_domain_error')
 I=min(1.,max(0.,I));B=S*S/32;Ld=1.5*D*D/(D*D+37.5);F=B+Ld
 full=all(m.get(k) is not None and math.isfinite(float(m[k])) and m[k]>=0 for k in ('Hmean','Hcenter'))
 G=(m['Hmean']/.8)**2 if full else None;L=(m['Hcenter']/.25)**2 if full else None;H=G+L if full else None
 f=100*I/(1+I*F);fc=100*I/(1+F)
 q=100*I/(1+I*(F+H)) if full else None;c=100*I/(1+F+H) if full else None
 return dict(status='complete' if full else 'floor_only',WQ=q,current=c,floor_WQ=f,floor_current=fc,boundary_loss=B,direction_loss=Ld,global_height_loss=G,local_height_loss=L,height_loss=H,height_drop_WQ=f-q if full else None,height_drop_current=fc-c if full else None,WQ_no_D=100*I/(1+I*(B+H)) if full else None,WQ_no_B=100*I/(1+I*(Ld+H)) if full else None,WQ_no_H=f if full else None,iou2d100=100*I)

def measure(a,g,floor_only=False):
 va=valid.validate_record(a,role='annotation');vg=valid.validate_record(g,role='reference')
 if not va['available'] or not vg['available']:
  return dict(status='unavailable',reasons=[role+':'+e['code'] for role,v in [('annotation',va),('reference',vg)] for e in v['errors']])
 areas=au.area_metrics(a,g);D=float(au.direction_residual(a,au.direction_axis(a)))
 m=dict(iou_2d=areas['iou'],S_bottom_deg=float(sp.spherical_sym_distance(a['bottom3d'],g['bottom3d'],2048)),dir=D,Hmean=None,Hcenter=None,iou_3d_corner_mean=None)
 if not floor_only:
  ah=hm.height_moments(a);gh=hm.height_moments(g);hc=center.centered_height_components(a,g,samples=4096,height_module=hm)
  t=trad.traditional_metrics_detailed(a,g,areas=areas,annotation_validation=va,reference_validation=vg)
  m.update(Hmean=abs(ah['height_mean_h']/gh['height_mean_h']-1),Hcenter=hc['Hcenter'],height_mean_ratio=ah['height_mean_h']/gh['height_mean_h'],iou_3d_corner_mean=t['hohonet_iou3d_vertex_mean'])
 return dict(status='complete' if not floor_only else 'floor_only',metrics=m,**{'scores':score(m)})

def dump(path,x):
 def norm(v):
  if isinstance(v,dict):return {str(k):norm(x) for k,x in v.items()}
  if isinstance(v,(list,tuple,np.ndarray)):return [norm(x) for x in v]
  if isinstance(v,np.generic):return norm(v.item())
  if isinstance(v,float) and not math.isfinite(v):return None
  return v
 Path(path).write_text(json.dumps(norm(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
