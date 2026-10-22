import json,sys,time
from pathlib import Path
import numpy as np,pandas as pd
from dataclasses import replace
from geomscore import *
from run_real import flat
O=Path(__file__).resolve().parents[1];R=O.parent
sys.path.insert(0,str(O/'legacy'))
import structure_quality as legacy
from synthetic_boundary import angular_boundary_mean

def square(s=2):return np.array([[-s,-s],[s,-s],[s,s],[-s,s]],float)
def geom(p,h=2):
 p=np.asarray(p,float);hs=np.broadcast_to(h,(len(p),)).astype(float)
 return dict(bottom3d=np.c_[p[:,0],-np.ones(len(p)),p[:,1]].tolist(),top3d=np.c_[p[:,0],hs-1,p[:,1]].tolist())
def rotate(g,deg):
 out={};th=np.deg2rad(deg);m=np.array([[np.cos(th),-np.sin(th)],[np.sin(th),np.cos(th)]])
 for key in ['bottom3d','top3d']:
  x=np.array(g[key]);x[:,[0,2]]=x[:,[0,2]]@m.T;out[key]=x.tolist()
 return out

def micro_steps(p,eps,all_corners=False):
 out=[]
 for i,x in enumerate(p):
  if all_corners or i==2:
   u=x-p[i-1];u=u/np.linalg.norm(u);v=p[(i+1)%len(p)]-x;v=v/np.linalg.norm(v)
   out.extend([x-eps*u,x-eps*u+eps*v,x+eps*v])
  else:out.append(x)
 return np.array(out)

def bump(depth=.3,width=.5,x0=0):
 return np.array([[-2,-2],[2,-2],[2,2],[x0+width/2,2],[x0+width/2,2+depth],[x0-width/2,2+depth],[x0-width/2,2],[-2,2]],float)
def erp(g):
 b=np.array(g['bottom3d']);t=np.array(g['top3d']);r=np.linalg.norm(b[:,[0,2]],axis=1)
 u=np.mod(np.arctan2(-b[:,0],b[:,2]),2*np.pi)/(2*np.pi)*1024
 out=np.empty((2*len(b),2));out[::2,0]=out[1::2,0]=u
 out[::2,1]=(.5-np.arctan2(t[:,1],r)/np.pi)*512;out[1::2,1]=(.5+np.arctan2(1,r)/np.pi)*512
 return out

def make_controls():
 r=geom(square());cases=[]
 def put(name,a,ref=r,family='',**extra):cases.append(dict(name=name,answer=a,reference=ref,family=family,**extra))
 put('identity',r,family='identity')
 for allc in [False,True]:
  for e in [.0001,.001,.005,.01,.02,.03,.06,.1,.2]:put(f"micro_{'four' if allc else 'one'}_{e:g}",geom(micro_steps(square(),e,allc)),family='micro_steps',epsilon_h=e)
 for d in [.001,.005,.01,.02,.03,.04,.06,.08,.15,.3,.6,1.]:
  put(f'omit_bump_{d:g}',r,geom(bump(d)),family='omit_detail',depth_h=d)
  put(f'add_bump_{d:g}',geom(bump(d)),r,family='extra_detail',depth_h=d)
 for yaw in [1,3,5,10,20,45]:put(f'yaw_{yaw}',rotate(r,yaw),family='yaw',yaw_deg=yaw)
 for scale in [.7,.9,1.05,1.2,1.5]:put(f'scale_{scale:g}',geom(square()*scale),family='scale',factor=scale)
 for tr in [.03,.1,.3,.8]:put(f'translate_{tr:g}',geom(square()+[tr,0]),family='translation')
 for shear in [.05,.15,.30,.5]:
  p=square()@np.array([[1,shear],[0,1]]).T;put(f'shear_{shear:g}',geom(p),family='shear')
  if shear==.15:
   put('nonorthogonal_reference_self',geom(p),geom(p),family='reference')
   put('straighten_nonorthogonal_reference',r,geom(p),family='reference')
 for h in [2.04,2.1,2.4,3.,4.,1.]:put(f'uniform_height_{h:g}',geom(square(),h),family='global_height')
 for amp in [.02,.05,.1,.2,.4,.8]:put(f'local_height_amp_{amp:g}',geom(square(),[2+amp,2-amp,2+amp,2-amp]),family='local_height')
 # Exact same-wall insertion: footprint and interpolated roof preserved.
 var=geom(square(),[1,2,3,2]);pv=np.insert(square(),1,(square()[0]+square()[1])/2,axis=0)
 put('same_wall_interpolated_top',geom(pv,[1,1.5,2,3,2]),var,family='representation')
 for n in [1,5,40]:
  p=np.vstack([square()[0]+(square()[1]-square()[0])*t for t in np.linspace(0,1,n+2)[:-1]]+[square()[1:]])
  put(f'same_wall_{n}_extra_pairs',geom(p),family='representation')
 # Exactly straight floor but a real extra roof kink must not disappear.
 put('same_floor_extra_top_peak',geom(pv,[2,2.8,2,2,2]),r,family='local_height')
 put('bump_wrong_wall',rotate(geom(bump(.3)),90),geom(bump(.3)),family='wrong_correspondence')
 put('bump_wrong_location',geom(bump(.3,x0=.9)),geom(bump(.3,x0=-.9)),family='wrong_correspondence')
 put('notch_to_bump',geom(bump(.3)),geom(bump(-.3)),family='wrong_correspondence')
 put('erase_deep_notch',r,geom(bump(-1.5,width=1.)),family='scope_change')
 # Equal two-pixel floor displacement at varying distance from horizon; ceiling pixels remain fixed.
 sens=[]
 for beta in [5,10,20,45]:
  rad=1/np.tan(np.deg2rad(beta));p=square(rad/np.sqrt(2));rg=geom(p);uv=erp(rg)
  for allc in [False,True]:
   alt=uv.copy();idx=np.arange(1,len(uv),2) if allc else [5];alt[idx,1]+=2;ag=from_erp(alt)
   name=f'ERP_bottom2px_beta{beta}_'+('all' if allc else 'one')
   put(name,ag,rg,family='erp_sensitivity',beta_deg=beta,all_corners=allc)
  sens.append(dict(beta_deg=beta,delta_px=2,delta_deg=2/512*180,r_before=rad,r_after=1/np.tan(np.deg2rad(beta+2/512*180)),relative_depth_change=(1/np.tan(np.deg2rad(beta+2/512*180)))/rad-1))
 pd.DataFrame(sens).to_csv(O/'results/ERP_depth_sensitivity.csv',index=False)
 return cases

def main():
 cases=make_controls();rows=[];details={}
 for c in cases:
  s=score_pair(c['answer'],c['reference']);d={k:v for k,v in c.items() if k not in ['answer','reference']};d.update(flat(s));details[c['name']]=s
  a=shell(c['answer']);r=shell(c['reference']);d['intrinsic_D']=legacy.direction_rms(a['p']);d['legacy_B']=np.nan;d['legacy_RCS']=np.nan;d['legacy_RCS_status']='height_not_replayed'
  if a['std']<1e-7 and r['std']<1e-7 and abs(a['mu']-r['mu'])<1e-7:
   sb=angular_boundary_mean(a['p'],r['p']);d['Sb_arc_analogue']=sb;d['legacy_B']=float(legacy.old_score(s['I'],sb,d['intrinsic_D'],0,0,'B8L2'))
   try:
    cs=legacy.structure(a['p'],r['p'],legacy.working_config())['C'];d['legacy_C']=cs;d['legacy_RCS']=legacy.candidate_score(s['I'],sb,0,0,cs,legacy.working_config());d['legacy_RCS_status']='computed_flat_height_arc_analogue'
   except Exception as exc:d['legacy_RCS_status']='failed:'+str(exc)
  rows.append(d)
 pd.DataFrame(rows).to_csv(O/'results/synthetic_scores.csv',index=False)
 (O/'inputs/synthetic_geometry.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2))
 (O/'results/synthetic_measurements.json').write_text(json.dumps(details,ensure_ascii=False,indent=2))
 df=pd.DataFrame(rows);names=['micro_one_0.001','micro_four_0.001','yaw_5','yaw_10','omit_bump_0.3','add_bump_0.3','scale_1.2','same_wall_interpolated_top','same_floor_extra_top_peak','nonorthogonal_reference_self','straighten_nonorthogonal_reference','erase_deep_notch']
 print(df[df.name.isin(names)][['name','I','intrinsic_D','QA','QB','QC','angle_RMS_deg','detail_loss','turning_deg','legacy_B','legacy_RCS','legacy_RCS_status']].to_string(index=False));print('n',len(df))
if __name__=='__main__':main()
