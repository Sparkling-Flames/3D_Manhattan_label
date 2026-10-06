"""Read-only scientific probes of the delivered spherical short-path kernel.

All synthetic coordinates are independently constructed here, not supplied as
new GT or substituted into the delivery's production input or outputs.
"""
import sys, json, math, argparse
from pathlib import Path
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--delivery',type=Path,default=Path('../oct6-structure-intake/extracted/structure_paths_20261006'))
parser.add_argument('--out',type=Path,default=Path('.'))
a=parser.parse_args();sys.path.insert(0,str(a.delivery.resolve()/'src'))
from frechet import rays,spherical_distance_interval,spherical_check,arc_length,angle

def project(P):
    P=np.asarray(P,float);n=np.linalg.norm(P,axis=-1)
    return np.c_[((np.arctan2(P[:,0],-P[:,2])/(2*np.pi)+.5)%1)*1024,
                 (.5-np.arcsin(P[:,1]/n)/np.pi)*512]
def floor_path(f):
    f=np.asarray(f,float)
    return np.stack([project(np.c_[f[:,0],np.full(len(f),1.2),f[:,1]]),
                     project(np.c_[f[:,0],-np.ones(len(f)),f[:,1]])],axis=1)
def area(f):
    f=np.asarray(f,float)
    return abs(float(np.sum(f[:,0]*np.roll(f[:,1],-1)-f[:,1]*np.roll(f[:,0],-1)))/2)
def save(name,data):
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2))

rows=[]
for far in [40.,200.,1000.]:
    A=floor_path([[-10,-20],[10,-20]])
    B=floor_path([[-10,-20],[0,-far],[10,-20]])
    base=[[-10,-20],[10,-20],[10,10],[-10,10]]
    donor=[[-10,-20],[0,-far],[10,-20],[10,10],[-10,10]]
    z={'synthetic_truth':'different range; not inferred by metric',
       'base_depth_h':20,'donor_apex_depth_h':far,
       'same_endpoints':bool(np.array_equal(A[[0,-1]],B[[0,-1]])),
       'base_pair_count':2,'donor_pair_count':3,
       'footprint_addition_h2':area(donor)-area(base),'footprint_loss_h2':0.,
       'base_ring_area_h2':area(base),'donor_ring_area_h2':area(donor),
       'base_path':A.tolist(),'donor_path':B.tolist(),'boundaries':{}}
    for side,j in [('top',0),('bottom',1)]:
        P=rays(A[:,j]);Q=rays(B[:,j]);z['boundaries'][side]={
          'distance':spherical_distance_interval(P,Q,.25),
          'check_5deg':spherical_check(P,Q,5),
          'source_lengths_deg':[arc_length(P),arc_length(Q)]}
        assert z['boundaries'][side]['check_5deg']['status']=='accept'
        assert max(z['boundaries'][side]['source_lengths_deg'])<120
    rows.append(z)
save('angular_gate_range_counterexample.json',rows)

# Both boundaries trace nearly identical scalar arcs, but traverse them at
# incompatible rates under an explicit paired-path parameterization. We do not
# claim this parameterization is the delivery's missing physical wall contract.
P=np.array([[[500.,100.],[500.,370.]],[[502.,140.],[502.,330.]]])
Q=np.array([[[500.,100.],[500.,370.]],[[501.,140.],[501.,370.]],[[502.,140.],[502.,330.]]])
side_distances={}
for side,j in [('top',0),('bottom',1)]:
    side_distances[side]={
       'distance':spherical_distance_interval(rays(P[:,j]),rays(Q[:,j]),.05),
       'gate_5deg':spherical_check(rays(P[:,j]),rays(Q[:,j]),5)}
# Common normalized arclength within each paired original edge.
# A dense bound plus a Lipschitz safety term brackets the closest joint match
# to the obligatory Q middle pair. Distance-to-fixed-point is 1-Lipschitz, so
# max(top,bottom) varies at most max(side arc lengths) times delta_t.
N=100000;t=np.linspace(0,1,N+1);ds=[];L=[]
for j in [0,1]:
    V=rays(P[:,j]);v=rays(Q[1:2,j])[0]
    theta=np.radians(angle(V[0],V[1]));L.append(float(np.degrees(theta)))
    C=(np.sin((1-t)*theta)[:,None]*V[0]+np.sin(t*theta)[:,None]*V[1])/np.sin(theta)
    ds.append(angle(C,v))
d=np.maximum(*ds);k=int(np.argmin(d));err=max(L)/(2*N)
joint={'scope':'explicit common normalized side-arclength parameterization only; not a proposed production definition',
       'P':P.tolist(),'Q':Q.tolist(),'independent_side_results':side_distances,
       'mandatory_middle_pair_best_joint_error_deg':{'lower':float(d[k]-err),'upper':float(d[k]),'parameter_t':float(t[k]),'grid_safety_bound':err},
       'interpretation':'Independent upper and lower Frechet passes do not certify this shared paired traversal. A physical joint parameter contract remains to be defined.'}
assert all(s['gate_5deg']['status']=='accept' for s in side_distances.values())
assert joint['mandatory_middle_pair_best_joint_error_deg']['lower']>5
save('separate_boundary_joint_parameter_counterexample.json',joint)
print(json.dumps({'range_cases':[{k:z[k] for k in ['base_depth_h','donor_apex_depth_h','footprint_addition_h2']} for z in rows], 'joint_minimum':joint['mandatory_middle_pair_best_joint_error_deg'],'side_distances':side_distances},indent=2))

# Stronger, representation-faithful paired-curve definition: top and bottom
# both lie on their original great-circle arc at the SAME longitude. The
# chosen paths have monotone longitude and no pole/antipodal ambiguities.
u0,u1=2*np.pi*(np.array([500.,502.])/1024-.5)
u=np.linspace(u0,u1,N+1);ds=[];speeds=[]
for j in [0,1]:
    v=np.pi*(.5-P[:,j,1]/512)
    # Intersection of the great-circle plane with longitude u.
    f=(np.tan(v[0])*np.sin(u1-u)+np.tan(v[1])*np.sin(u-u0))/np.sin(u1-u0)
    lat=np.arctan(f)
    V=np.c_[np.cos(lat)*np.sin(u),np.sin(lat),-np.cos(lat)*np.cos(u)]
    ds.append(angle(V,rays(Q[1:2,j])[0]))
    # Conservative global bound on |d latitude / d longitude|:
    # |f'/(1+f^2)| <= (|tan(v0)|+|tan(v1)|)/sin(u1-u0).
    # Unit-sphere speed <= sqrt(1 + derivative_bound^2).
    b=(abs(np.tan(v[0]))+abs(np.tan(v[1])))/abs(np.sin(u1-u0))
    speeds.append(float(np.sqrt(1+b*b)))
d=np.maximum(*ds);k=int(np.argmin(d))
err=max(speeds)*(u1-u0)/(2*N)*180/np.pi
joint_shared_x={
   'scope':'P and Q paired curves use actual top/bottom minor great-circle arcs at common longitude within every source edge; this constructed example is longitude-monotone',
   'P':P.tolist(),'Q':Q.tolist(),'independent_side_results':side_distances,
   'mandatory_Q_middle_pair':Q[1].tolist(),
   'necessary_joint_frechet_lower_bound_deg':float(d[k]-err),
   'best_middle_pair_match_upper_deg':float(d[k]),
   'best_matching_P_x_px':float((u[k]/(2*np.pi)+.5)*1024),
   'grid_intervals':N,'conservative_grid_safety_deg':float(err),
   'proof':'Every surjective continuous monotone traversal of Q must visit its original middle pair. P at that moment is somewhere on its shared-x paired curve. The minimum over ALL such P positions of max(top angle,bottom angle) lower-bounds EVERY joint coupling. Sampling this scalar minimum with a global Lipschitz bound gives the stated lower bound; this is ordinary floating-point evaluation, not formal interval arithmetic.',
   'interpretation':'Independent boundary Frechet passes do not certify existence of a shared paired traversal even when both curves preserve source paired x. This is a control of the representation boundary, not a criticism of an unimplemented joint metric.'}
assert joint_shared_x['necessary_joint_frechet_lower_bound_deg']>5
save('shared_x_joint_path_counterexample.json',joint_shared_x)
print(json.dumps({'shared_x_joint_lower_deg':joint_shared_x['necessary_joint_frechet_lower_bound_deg'], 'shared_x_grid_safety_deg':err},indent=2))
