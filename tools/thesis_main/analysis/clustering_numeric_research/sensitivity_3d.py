"""Auxiliary raw-ray geometry sensitivity; no Manhattan fit, correction or depth weights."""
from __future__ import annotations
import math
import numpy as np,pandas as pd
from common import *

def geometry(top,bottom):
    alpha=np.pi/2-(float(top[1])+.5)*np.pi/512
    beta=(float(bottom[1])+.5)*np.pi/512-np.pi/2
    in_frame=0<=top[1]<512 and 0<=bottom[1]<512
    status='conditional_valid' if in_frame and 0<alpha<np.pi/2 and 0<beta<np.pi/2 else 'projection_assumptions_not_met'
    if status!='conditional_valid':return alpha,beta,np.nan,np.nan,status
    rho=1/np.tan(beta);height=1+rho*np.tan(alpha)
    return alpha,beta,float(rho),float(height),status

def perturb(top,bottom,kind,delta):
    a=np.array(top,float).copy();b=np.array(bottom,float).copy()
    if kind=='top_y':a[1]+=delta
    elif kind=='bottom_y':b[1]+=delta
    elif kind=='joint_x':a[0]=(a[0]+delta)%1024;b[0]=(b[0]+delta)%1024
    else:raise ValueError(kind)
    return a,b

def main():
    rows,raw,rec,elig,ap=records();res=[];bases=[]
    for cid,r in rec.items():
        if r['links'] is None:continue
        for j,(ti,bi) in enumerate(r['links']):
            a=r['p'][ti];b=r['p'][bi];alpha,beta,rho,height,status=geometry(a,b)
            dx=abs((a[0]-b[0]+512)%1024-512)
            base=dict(id=cid,worker=r['row']['worker_id'],image_id=r['row']['image_id'],building=r['row']['building_id'],condition=r['row']['raw_condition'],pair=j+1,original_top=int(ti)+1,original_bottom=int(bi)+1,top_x=float(a[0]),top_y=float(a[1]),bottom_x=float(b[0]),bottom_y=float(b[1]),top_elevation_deg=float(np.degrees(alpha)),bottom_depression_deg=float(np.degrees(beta)),radius_over_camera_height=rho,total_height_over_camera_height=height,baseline_status=status,top_bottom_dx_px=float(dx),near_horizon=abs(np.degrees(beta))<5,occlusion_status='not_rejudged_text_evidence_only',wall_connection_order='not_assumed')
            bases.append(base)
            for kind in ['top_y','bottom_y','joint_x']:
                for delta in [-10,-5,-1,1,5,10]:
                    aa,bb=perturb(a,b,kind,delta);_,_,rr,hh,st=geometry(aa,bb)
                    residual_top=float(angle_matrix([a],[aa])[0,0]);residual_bottom=float(angle_matrix([b],[bb])[0,0])
                    # Position of floor point changes with azimuth; no inferred polygon.
                    du=(bb[0]-b[0])*2*np.pi/1024
                    planar=np.sqrt(max(0.,rho*rho+rr*rr-2*rho*rr*np.cos(du))) if np.isfinite(rr) and np.isfinite(rho) else np.nan
                    res.append(dict(id=cid,pair=j+1,condition=base['condition'],perturbation=kind,delta_px=delta,top_direction_error_deg=residual_top,bottom_direction_error_deg=residual_bottom,max_direction_error_deg=max(residual_top,residual_bottom),radius_relative_change=rr/rho-1 if status==st=='conditional_valid' else np.nan,total_height_relative_change=hh/height-1 if status==st=='conditional_valid' else np.nan,floor_point_displacement_over_initial_radius=planar/rho if status==st=='conditional_valid' else np.nan,near_horizon=base['near_horizon'],baseline_status=status,perturbed_status=st,top_bottom_dx_px=dx))
    base=save('sensitivity3d/base_bound_pairs.csv.gz',bases);df=save('sensitivity3d/endpoint_perturbations.csv.gz',res)
    summary=[]
    for k,g in df.groupby(['condition','perturbation','delta_px','near_horizon']):
        ok=g[g.radius_relative_change.notna()];summary.append(dict(zip(['condition','perturbation','delta_px','near_horizon'],k),observations=len(g),valid_projections=len(ok),undefined_projections=len(g)-len(ok),direction_error_median=g.max_direction_error_deg.median(),abs_radius_change_median=ok.radius_relative_change.abs().median(),abs_radius_change_p90=ok.radius_relative_change.abs().quantile(.9),abs_radius_change_p99=ok.radius_relative_change.abs().quantile(.99),abs_height_change_median=ok.total_height_relative_change.abs().median()))
    save('sensitivity3d/conditional_sensitivity_summary.csv',summary)
    synthetic=[]
    for beta in [1,2,5,10,15,30,45,60]:
        for alpha in [10,30,50]:
            a=np.array([100.,(90-alpha)*512/180-.5]);b=np.array([100.,(90+beta)*512/180-.5]);_,_,rho,h,_=geometry(a,b)
            for kind in ['top_y','bottom_y','joint_x']:
                for delta in [-10,-5,-1,1,5,10]:
                    aa,bb=perturb(a,b,kind,delta);_,_,rr,hh,st=geometry(aa,bb)
                    synthetic.append(dict(alpha_deg=alpha,beta_deg=beta,perturbation=kind,delta_px=delta,radius_relative_change=rr/rho-1,height_relative_change=hh/h-1,status=st,max_direction_error_deg=max(angle_matrix([a],[aa])[0,0],angle_matrix([b],[bb])[0,0])))
    sy=save('sensitivity3d/synthetic_projection_probes.csv',synthetic)
    # Analytic derivatives compared with symmetric finite differences, in radians.
    der=[]
    for beta in np.radians([1,2,5,10,15,30,45,60]):
        step=1e-7;numer=(np.log(1/np.tan(beta+step))-np.log(1/np.tan(beta-step)))/(2*step);exact=-1/(np.sin(beta)*np.cos(beta))
        der.append(dict(beta_deg=np.degrees(beta),finite_difference=numer,analytic=exact,error=abs(numer-exact)))
    save('sensitivity3d/derivative_audit.csv',der)
    ok=df[df.radius_relative_change.notna()];top=ok[ok.perturbation=='top_y'];xx=ok[ok.perturbation=='joint_x']
    assert top.radius_relative_change.abs().max()<1e-12
    assert xx.radius_relative_change.abs().max()<1e-12 and xx.total_height_relative_change.abs().max()<1e-12
    audit=dict(bound_pairs=len(base),valid_baseline_pairs=int((base.baseline_status=='conditional_valid').sum()),near_horizon_pairs=int(base.near_horizon.sum()),perturbation_rows=len(df),top_y_radius_change_max=float(top.radius_relative_change.abs().max()),joint_x_radius_change_max=float(xx.radius_relative_change.abs().max()),analytic_derivative_max_error=max(x['error'] for x in der),camera_height=1.,camera_height_is_scale_unit_not_measured=True,ground_horizontal=True,ceiling_height_formula_conditional_on_corresponding_vertical_corner=True,unaligned_top_bottom_x_are_flagged_not_corrected=True,occlusion_not_newly_verified=True,raw_points_modified=False,used_in_clustering_weights=False)
    dump('SENSITIVITY_3D_AUDIT.json',audit)
    print(json.dumps(clean(audit),ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
