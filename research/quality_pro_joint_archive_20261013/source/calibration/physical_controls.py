#!/usr/bin/env python3
"""Actual geometries matched by normalized 3D displacement, not by unlike units.

Budget = RMS displacement of the paired top+bottom boundary curves, sampled in
the ORIGINAL reference's arclength parametrization, divided by its mean height.
Matching this geometric budget is not asserted to establish equal perceived error.
"""
from __future__ import annotations
import argparse, copy, hashlib, importlib, json, math, sys
from pathlib import Path
import numpy as np
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent

def dump(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def digest(x):return hashlib.sha256(json.dumps(x,separators=(',',':'),sort_keys=True).encode()).hexdigest()
def edge_moments(values,weights):
    v=np.asarray(values,float);n=np.roll(v,-1)
    return float(np.dot(weights,(v+n)/2)),float(np.dot(weights,(v*v+v*n+n*n)/3))
def directions(p):
    e=np.roll(p,-1,axis=0)-p;lengths=np.linalg.norm(e,axis=1);w=lengths/lengths.sum()
    t=np.degrees(np.arctan2(e[:,1],e[:,0]));cuts=sorted(set([0.,90.]+((t+45)%90).tolist()))
    def res(a):return (t-a+45)%90-45
    candidates=cuts[:]
    for lo,hi in zip(cuts,cuts[1:]):
        mid=(lo+hi)/2;o=mid+np.dot(w,res(mid))
        if lo<=o<=hi:candidates.append(o)
    a=min(candidates,key=lambda z:np.dot(w,res(z)**2));r=np.abs(res(a))
    return dict(D_rms_deg=float(np.sqrt(np.dot(w,r*r))),axis_deg=float(a%90),
                moment4=float(np.dot(w,r**4)),excess2={str(int(t)):float(np.dot(w,np.maximum(r-t,0)**2)) for t in [2,5,10,15,20]},
                abs_residual_deg=r.tolist(),length_weight=w.tolist())

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=HERE.parent/'baseline')
    p.add_argument('--out',type=Path,default=HERE/'results/physical_controls.json');a=p.parse_args()
    source=a.source.resolve();sys.path.insert(0,str(source/'scripts'))
    adapter=importlib.import_module('score_frozen_geometry')
    settings=json.loads((source/'config/frozen_selected_candidates.json').read_text())['candidates']['P_tied_quad08']['parameters']
    rows=[];h=2.6
    for sid,hx,hz in [('small_square',1.,1.),('square',2.,2.),('large_square',4.,4.),('narrow',1.,4.)]:
      p0=np.array([[-hx,-hz],[hx,-hz],[hx,hz],[-hx,hz]])
      b=np.c_[p0[:,0],-np.ones(4),p0[:,1]];top=b.copy();top[:,1]=h-1
      g=dict(bottom3d=b.tolist(),top3d=top.tolist())
      lengths=np.linalg.norm(np.roll(p0,-1,axis=0)-p0,axis=1);weights=lengths/lengths.sum()
      x2=edge_moments(p0[:,0],weights)[1];z2=edge_moments(p0[:,1],weights)[1]
      local=np.array([-1.,1.,-1.,1.]);local-=edge_moments(local,weights)[0]
      local/=math.sqrt(edge_moments(local,weights)[1])
      for budget in [.02,.05,.1,.2]:
       for kind in ['shear','stretch','rotation','local_height','global_height_high','global_height_low']:
        a_b=b.copy();a_t=top.copy();parameter=None
        if kind=='shear':
            parameter=budget*h/math.sqrt(z2);new=p0.copy();new[:,0]+=parameter*p0[:,1]
            a_b[:,[0,2]]=a_t[:,[0,2]]=new
        elif kind=='stretch':
            parameter=budget*h/math.sqrt(x2);new=p0.copy();new[:,0]*=1+parameter
            a_b[:,[0,2]]=a_t[:,[0,2]]=new
        elif kind=='rotation':
            parameter=2*math.asin(budget*h/(2*math.sqrt(x2+z2)))
            rot=np.array([[math.cos(parameter),-math.sin(parameter)],[math.sin(parameter),math.cos(parameter)]])
            new=p0@rot.T;a_b[:,[0,2]]=a_t[:,[0,2]]=new
        elif kind=='local_height':a_t[:,1]+=math.sqrt(2)*budget*h*local
        else:a_t[:,1]+=(1 if kind=='global_height_high' else -1)*math.sqrt(2)*budget*h
        ann=dict(bottom3d=a_b.tolist(),top3d=a_t.tolist())
        # Exact edge-integrated squared 3D displacement on reference parameter.
        err=0.
        for original,changed in [(b,a_b),(top,a_t)]:
            delta=changed-original
            err+=sum(edge_moments(delta[:,j],weights)[1] for j in range(3))/2
        actual=math.sqrt(err)/h
        v=adapter.evaluate(ann,g,settings,samples=2048,height_samples=4096)
        rows.append(dict(case_id=f'{sid}:{kind}:{budget:g}',reference_case=sid,kind=kind,
                         target_budget=budget,actual_budget=actual,budget_error=actual-budget,
                         annotation_geometry=ann,reference_geometry=g,annotation_sha256=digest(ann),reference_sha256=digest(g),
                         parameter=parameter,minimum_whole_wall_height=float(np.min(a_t[:,1]-a_b[:,1])),
                         minimum_top_camera_clearance=float(a_t[:,1].min()),status=v['status'],
                         metrics=v.get('metrics'),official_iou3d=v.get('official_corner_mean_iou3d'),
                         direction_descriptor=directions(a_b[:,[0,2]]),human_quality_label=None))
    dump(a.out,dict(schema='matched_reference_boundary_displacement_controls_v1',rows=rows,
             geometry_sampling=dict(spherical_samples=2048,height_samples=4096),all_complete=all(r['status']=='available' for r in rows),
             budget_definition=__doc__,budget_max_error=max(abs(r['budget_error']) for r in rows),
             human_equivalence_claimed=False,reference_selection_performed=False))
    dependencies=[]
    for module in list(sys.modules.values()):
        path=getattr(module,'__file__',None)
        if path and Path(path).resolve().is_relative_to(source):
            fp=Path(path).resolve();dependencies.append(dict(path=str(fp.relative_to(source)),sha256=hashlib.sha256(fp.read_bytes()).hexdigest()))
    dump(a.out.with_name('physical_control_dependencies.json'),dict(frozen_python_modules=sorted(dependencies,key=lambda z:z['path']),
                 config='config/frozen_selected_candidates.json',additional_input_files=['inputs/calibration_records.json','inputs/old24_labels_preserved.json','evidence_audit/results/constraints.json']))
    print(json.dumps(dict(cases=len(rows),available=sum(r['status']=='available' for r in rows),budget_max_error=max(abs(r['budget_error']) for r in rows))))

if __name__=='__main__':main()
