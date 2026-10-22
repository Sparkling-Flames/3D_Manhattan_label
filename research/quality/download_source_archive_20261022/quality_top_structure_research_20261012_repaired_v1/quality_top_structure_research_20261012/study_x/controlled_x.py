#!/usr/bin/env python3
"""Small deterministic controls for shared-x information loss and resampling.
No probability model, human labels, or fitted parameters are generated.
"""
from __future__ import annotations
import argparse,copy,json,math,pathlib,sys
import numpy as np
from audit_representation import save_json,save_csv,wrap,BASE
from raw_boundary_experiment import rays

def pix(xyz):
    p=np.asarray(xyz,float);u=np.arctan2(p[:,0],-p[:,2]);v=np.arctan2(p[:,1],np.linalg.norm(p[:,[0,2]],axis=1))
    return np.c_[((u/(2*np.pi)+.5)*1024)%1024,(.5-v/np.pi)*512]
def pts(g):
    p=np.empty((2*len(g['bottom3d']),2));p[::2]=pix(g['top3d']);p[1::2]=pix(g['bottom3d']);return p
def midpoints(p):
    p=np.asarray(p,float).copy();delta=wrap(p[1::2,0]-p[::2,0])
    if np.any(abs(delta)>=512-1e-8):raise ValueError('ambiguous_antipodal_midpoint')
    mids=(p[::2,0]+delta/2)%1024;p[::2,0]=p[1::2,0]=mids;return p
def reconstruct_shared(p):
    p=midpoints(p);f=p[1::2];t=p[::2]
    if np.any((f[:,1]<=256)|(f[:,1]>=512)):raise ValueError('floor_ray_not_below_horizon')
    rad=1/np.tan(np.pi*(f[:,1]/512-.5));u=(f[:,0]/1024-.5)*2*np.pi
    b=np.c_[rad*np.sin(u),-np.ones(len(f)),-rad*np.cos(u)];up=b.copy();up[:,1]=rad*np.tan(np.pi*(.5-t[:,1]/512))
    return dict(top3d=up.tolist(),bottom3d=b.tolist(),points=p.tolist())
def raw_auxiliary_embedding(p):
    """For re-vertexing only: pair top horizontal radius = its floor radius.
    Not a unique 3-D reconstruction and never scored as valid room geometry.
    """
    p=np.asarray(p,float);rho=1/np.tan(np.pi*(p[1::2,1]/512-.5));u=(p[:,0]/1024-.5)*2*np.pi
    rad=np.repeat(rho,2);y=rad*np.tan(np.pi*(.5-p[:,1]/512))
    xyz=np.c_[rad*np.sin(u),y,-rad*np.cos(u)]
    return dict(top3d=xyz[::2].tolist(),bottom3d=xyz[1::2].tolist())
def insert_same_edge(g,edge,n):
    r={}
    for k in ['top3d','bottom3d']:
        arr=np.asarray(g[k]);j=(edge+1)%len(arr);new=[]
        for i,x in enumerate(arr):
            new.append(x)
            if i==edge:
                new.extend((1-t)*arr[i]+t*arr[j] for t in np.linspace(0,1,n+2)[1:-1])
        r[k]=np.asarray(new).tolist()
    return r

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--previous',default='previous_research/quality_calibration_research_20261011');ap.add_argument('--out',default='study_x/results');a=ap.parse_args();out=pathlib.Path(a.out)
    sys.path.insert(0,str(pathlib.Path(a.previous)/BASE/'frozen/scope_engine/core'))
    from quality_v11 import score_geometry
    from geometric_components import spherical_sym_distance
    from strict_geometry import validate_record
    g=dict(bottom3d=[[-3.,-1.,-2.],[4.,-1.,-2.],[4.,-1.,3.],[-3.,-1.,3.]],top3d=[[-3.,1.2,-2.],[4.,1.2,-2.],[4.,1.2,3.],[-3.,1.2,3.]])
    p=pts(g);cases=[]
    def add(name,q,ref=g,**kw):cases.append(dict(case_id=name,raw_points=np.asarray(q).tolist(),reference=ref,**kw))
    add('exact_reference',p)
    q=p.copy();q[:,0]=(q[:,0]+3)%1024;add('all_pairs_common_x_plus3',q,description='真实共同旋转，成对残差仍为0')
    q=p.copy();q[:2,0]=(q[:2,0]+3)%1024;add('one_pair_common_x_plus3',q,description='同一对两端同向3px定位变化')
    for d in [3,8,20]:
        q=p.copy();q[0,0]=(q[0,0]-d)%1024;q[1,0]=(q[1,0]+d)%1024
        add('one_pair_opposite_'+str(d),q,description='两端反向，均值严格不变')
    q=p.copy();q[0,0]=(q[0,0]+6)%1024;add('one_top_only_plus6',q,description='与共同+3px共享x结果相同，但原始端点错误不同')
    q=p.copy();q[1,1]+=3;add('one_bottom_y_plus3',q,description='真实竖直定位变化；X不响应')
    q=p.copy();q[0,0]=(q[0,0]-256)%1024;q[1,0]=(q[1,0]+256)%1024;add('antipodal_pair_rejected',q,description='不合法中点，拒绝而非生成几何')
    shift=2-p[0,0];sp=p.copy();sp[:,0]=(sp[:,0]+shift)%1024;sg=reconstruct_shared(sp)
    sq=sp.copy();sq[0,0]=(sq[0,0]-6)%1024;sq[1,0]=(sq[1,0]+6)%1024;add('seam_opposite_6',sq,ref=sg,description='首对1020px/8px，中点2px；算术中点514px错误')
    local=next(c for c in cases if c['case_id']=='one_pair_opposite_8');rg=raw_auxiliary_embedding(local['raw_points'])
    good=insert_same_edge(rg,1,40);bad=insert_same_edge(rg,0,40)
    add('same_raw_curves_40_good_edge_points',pts(good),description='同一原始上下线段按相同t插入40个共线点；未动错误角')
    add('same_raw_curves_40_bad_edge_points',pts(bad),description='同一原始上下线段在带错位边按相同t插入40个共线点；检查投影非交换性')
    save_json(out/'controlled_x_design.json',dict(synthetic=True,not_person_error_distribution=True,cases=cases))
    rows=[];details=[]
    for c in cases:
        raw=np.asarray(c['raw_points']);delta=wrap(raw[1::2,0]-raw[::2,0]);rr=rays(raw)
        rt=spherical_sym_distance(rr[::2],c['reference']['top3d']);rb=spherical_sym_distance(rr[1::2],c['reference']['bottom3d'])
        r=dict(case_id=c['case_id'],n_pairs=len(raw)//2,synthetic=True,X_rms_deg=float(np.sqrt(np.mean(delta**2)))*360/1024,
               X_max_deg=float(np.max(abs(delta)))*360/1024,raw_S_top_deg=rt,raw_S_bottom_deg=rb,raw_S_rms_deg=math.hypot(rt,rb)/math.sqrt(2),
               status='unavailable',Q=None)
        try:
            gg=reconstruct_shared(raw);sc=score_geometry(gg,c['reference']);m=sc['metrics'];r.update(status=sc['status'],Q=sc['quality_score'],
               **{k:m.get(k) for k in ['iou_2d','iou_3d_corner_mean','S_top_deg','S_bottom_deg','boundary_rms_deg','Hstar','dir','flat']})
            details.append(dict(case_id=c['case_id'],shared_geometry=gg,score=sc))
        except ValueError as exc:r['reason']=str(exc)
        rows.append(r)
    by={r['case_id']:r for r in rows};orig=by['one_pair_opposite_8'];good=by['same_raw_curves_40_good_edge_points'];bad=by['same_raw_curves_40_bad_edge_points']
    same=by['one_pair_common_x_plus3'];top=by['one_top_only_plus6']
    checks=dict(opposite_projection_Q_unchanged=all(abs(by['one_pair_opposite_'+str(d)]['Q']-by['exact_reference']['Q'])<1e-10 for d in [3,8,20]),
       one_top_and_common_shared_Q_identical=abs(same['Q']-top['Q'])<1e-10,
       antipodal_rejected=by['antipodal_pair_rejected']['Q'] is None,
       seam_midpoint_correct=abs(by['seam_opposite_6']['Q']-by['exact_reference']['Q'])<1e-9,
       redundant_good_edge_raw_S_invariant=max(abs(orig[k]-good[k]) for k in ['raw_S_top_deg','raw_S_bottom_deg'])<1e-10,
       redundant_bad_edge_raw_S_invariant=max(abs(orig[k]-bad[k]) for k in ['raw_S_top_deg','raw_S_bottom_deg'])<1e-10,
       redundant_good_edge_Xmax_invariant=abs(orig['X_max_deg']-good['X_max_deg'])<1e-10,
       redundant_good_edge_Xrms_diluted=good['X_rms_deg']<orig['X_rms_deg']/3)
    report=dict(checks=checks,n_controls=len(rows),
       revertex_good_edge=dict(original_pairs=orig['n_pairs'],new_pairs=good['n_pairs'],X_rms_before=orig['X_rms_deg'],X_rms_after=good['X_rms_deg'],
           Xmax_before=orig['X_max_deg'],Xmax_after=good['X_max_deg'],rawS_before=orig['raw_S_rms_deg'],rawS_after=good['raw_S_rms_deg'],Q_before=orig['Q'],Q_after=good['Q']),
       revertex_bad_edge=dict(X_rms_before=orig['X_rms_deg'],X_rms_after=bad['X_rms_deg'],Xmax_before=orig['X_max_deg'],Xmax_after=bad['X_max_deg'],
           rawS_before=orig['raw_S_rms_deg'],rawS_after=bad['raw_S_rms_deg'],Q_before=orig['Q'],Q_after=bad['Q']),
       interpretation='Mean projection has a real null space. X detects anti-directional pair gaps, not all localisation/structure errors. Equal-pair RMS can be diluted by redundant correct pairs. Raw spherical curve distance is subdivision invariant in these exact controls. No severity threshold follows.')
    save_csv(out/'controlled_x_results.csv',rows);save_json(out/'controlled_x_details.json',details);save_json(out/'controlled_x_summary.json',report)
    assert all(checks.values()),checks
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
