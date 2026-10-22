"""Independent adversarial EBC2 tests; source is imported read-only."""
from pathlib import Path
import sys,json,math,os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import numpy as np
from dataclasses import replace
ROOT=Path(__import__('os').environ['PRO_PACKAGE']).resolve()
sys.path.insert(0,str(ROOT/'src'))
from envelope_quality import normalized_pair,NormalizedConfig,shell,samples,Config
from controls import geom,transform,redundant
OUT=Path(__file__).resolve().parent;rows=[];cases={}
fields=['status','reason','I','boundary_coverage','position_only_coverage','answer_boundary_credit','reference_boundary_credit','score_l2','Hmean','Hcenter','Hcenter_tie_lower','height_tie_fraction_AG','height_tie_fraction_GA','samples_AG','samples_GA','reference_size_h']
def score(name,a,r,c=NormalizedConfig()):
 q=normalized_pair(a,r,c);row={'name':name,**{k:q.get(k) for k in fields}}
 for side,g in [('answer',a),('reference',r)]:
  s=shell(g);row[side+'_perimeter']=s['L'];row[side+'_vertices']=len(s['p']);row[side+'_area']=s['poly'].area
 rows.append(row);cases[name]={'answer':a,'reference':r,'config':c.__dict__};print(json.dumps(row),flush=True);return q
sq=geom([[-2,-2],[2,-2],[2,2],[-2,2]])
# (1) Near-wall tie tolerance is origin/ring-start dependent.
def slit(width):
 return geom([[-2,-2],[2,-2],[2,2],[width,2],[width,0],[0,0],[0,2],[-2,2]],[2,2,2,2,2,5,5,2])
for eps in [0.1,0.01,0.001,1e-5,1e-6,5e-7,2e-7]:
 for roll in [0,4]:
  g=transform(slit(eps),roll=roll);score(f'slit_self_width{eps}_roll{roll}',g,g)
for shift in [(0,0),(4.123,-2.71),(1e4,-1e4),(1e8,-1e8)]:
 for roll in [0,4]:
  g=transform(slit(5e-7),roll=roll,shift=shift);score(f'slit_self_shift{shift}_roll{roll}',g,g)
for scale in [.01,.1,1,10,100]:
 g=transform(slit(5e-7),roll=4,scale=scale);score(f'slit_self_scale{scale}',g,g)
# Actual tolerance from production expression at two ring starts.
tolerances=[]
for roll in [0,4]:
 s=shell(transform(slit(5e-7),roll=roll));cfg=Config(step_h=.0025*np.sqrt(s['poly'].area));p,_,_,_,_=samples(s,cfg);pp=p-s['p'][0];qq=s['p']-s['p'][0]
 v=128*np.finfo(float).eps*max(1,float(np.max(np.sum(pp*pp,axis=1))),float(np.max(np.sum(qq*qq,axis=1))))
 tolerances.append({'roll':roll,'distance2_roundoff':v,'sqrt_roundoff':np.sqrt(v),'slit_distance2':(5e-7)**2})
# (2) Periodic serrations: period in arclength equals tangent window.
def serrated(n,top=1,amplitude=None):
 dx=3.8/(2*n);amp=np.sqrt((.08/2)**2-dx**2) if amplitude is None else amplitude
 x=np.linspace(-1.9,1.9,2*n+1);z=np.array([-2+amp*(i%2) for i in range(2*n+1)])
 return geom([[-2,-2],*np.column_stack((x,z)).tolist(),[2,-2],[2,top],[-2,top]])
base=geom([[-2,-2],[2,-2],[2,1],[-2,1]])
score('serration_baseline',base,sq)
for n in [50,100,200,400]:
 a=serrated(n)
 for factor in ([1,2,4] if n<=200 else [1,2]):score(f'serration_n{n}_step1over{factor}',a,sq,NormalizedConfig(step_side=.0025/factor))
# Same N but small perturbation of physical bump size changes smoothing resonances.
for factor in [.8,.9,.95,1,1.05,1.1,1.2]:
 amp=math.sqrt(.04**2-(3.8/200)**2)*factor
 score(f'serration_n100_amplitude_factor{factor}',serrated(100,amplitude=amp),sq,NormalizedConfig(step_side=.000625))
# (3) Positive sanity checks, including nonorthogonal + nonflat reference self and redundancy.
non=geom([[-2,-2],[2,-2],[3,2],[0,1],[-2,2]],[1.5,2.1,2.9,1.8,2.4])
score('nonorth_nonflat_self',non,non)
score('full_3d_redundancy',redundant(non),non)
for yaw in [0,37,90,173]:score(f'nonorth_joint_yaw{yaw}',transform(sq,angle=yaw),transform(non,angle=yaw))
for scale in [.1,1,10]:score(f'relative_scale{scale}',transform(sq,scale=scale),transform(non,scale=scale))
# Closely adjacent opposite normals receive less oriented credit than position-only.
adj=transform(sq,shift=(3.9,0));score('opposite_wall_normals',adj,sq)
# Uniform height and footprint component pooling is correct.
for h in [1,2,3]:score(f'uniform_height{h}',geom([[-2,-2],[2,-2],[2,2],[-2,2]],h),sq)
# (4) Real fixed pairs: minimum distances and observed near-tie conditions, all references self.
pairs=json.loads((ROOT/'inputs/fixed_pairs.json').read_text());refs={p['reference_id']:p['reference'] for p in pairs}
real_self=[]
for rid,g in refs.items():
 q=normalized_pair(g,g);real_self.append({'reference_id':rid,'status':q['status'],'score_l2':q.get('score_l2'),'tie_fraction':q.get('height_tie_fraction_AG')})
(OUT/'audit_results.json').write_text(json.dumps({'tests':rows,'tolerances':tolerances,'real_reference_self':real_self},indent=2))
(OUT/'audit_cases.json').write_text(json.dumps(cases,indent=2))
print('DONE',len(rows),'tests,',len(real_self),'actual reference self checks')
