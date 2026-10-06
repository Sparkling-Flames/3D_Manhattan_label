from __future__ import annotations
import json,copy
from pathlib import Path
import numpy as np
from frechet import (rays,angle,polygonal_arc,continuous_decide,euclidean_distance,
    spherical_check,spherical_distance_interval,discrete_distance)
from run import dump,ROOT
from baseline import nodes_from_records,distances
from structure import PathBank

def project(P):
    a=np.asarray(P,float);n=np.linalg.norm(a,axis=-1)
    return np.c_[((np.arctan2(a[:,0],-a[:,2])/(2*np.pi)+.5)%1)*1024,
                 (.5-np.arcsin(np.clip(a[:,1]/n,-1,1))/np.pi)*512]
def path_from_floor(f,top_height=1.2):
    f=np.asarray(f,float);top=project(np.c_[f[:,0],np.full(len(f),top_height),f[:,1]])
    bot=project(np.c_[f[:,0],-np.ones(len(f)),f[:,1]])
    return np.stack([top,bot],axis=1)
def record(rid,f):
    q=path_from_floor(f);n=len(q)
    return dict(id=rid,worker=rid,points=q.reshape(-1,2).tolist(),condition='manual',image='synthetic_control',
        evidence_kind='synthetic_control_not_person',independent=True,consensus_eligible=True,
        source_pair_indices=list(range(n)),source_point_indices=list(range(2*n)),ring_confirmed=True,
        order_status='given_synthetic_order')

def run_controls(out):
    folder=Path(out)/'controls';folder.mkdir(exist_ok=False)
    config=json.loads((ROOT/'config.json').read_text())
    a=path_from_floor([[-1,-2],[1,-2]])
    controls={
      'collinear_2_vs_3':(a,path_from_floor([[-1,-2],[0,-2],[1,-2]]),'same_geometric_path_different_segmentation'),
      'short_protrusion_2_vs_3':(a,path_from_floor([[-1,-2],[0,-2.7],[1,-2]]),'different_geometric_path_truth_not_inferred_from_geometry'),
      'narrow_protrusion_2_vs_3':(path_from_floor([[-.01,-2],[.01,-2]]),
          path_from_floor([[-.01,-2],[0,-2.7],[.01,-2]]),'narrow_different_path_not_allowed_to_be_silently_deleted'),
      'same_lower_different_upper_targets':(path_from_floor([[-1,-2],[1,-2]],.4),a,
          'two_synthetic_upper_targets_same_bottom'),
    }
    # Close repeated structures crossing the panorama seam: identity ambiguity
    # is provided only for evaluating this synthetic control.
    p=np.array([[[1008.,140.],[1008.,380.]],[[1020.,135.],[1020.,385.]],[[8.,140.],[8.,380.]]])
    q=p.copy();q[:,:,0]=(q[:,:,0]+8)%1024
    controls['near_seam_distinct_repeated_motifs']=(p,q,'different_synthetic_identities_despite_close_same_shape')
    results=[]
    for name,(a,b,truth) in controls.items():
        row={'case':name,'path_a':a.reshape(-1,2).tolist(),'path_b':b.reshape(-1,2).tolist(),
             'given_control_label_not_construction_input':truth,'geometry':{},'gate_checks':{}}
        for s,j in [('top',0),('bottom',1)]:
            A=rays(a[:,j]);B=rays(b[:,j]);row['geometry'][s]=spherical_distance_interval(A,B,.25)
            row['gate_checks'][s]={str(t):spherical_check(A,B,t) for t in [5,9,12]}
        row['all_input_points_retained']=True
        results.append(row)
    dump(folder/'decisive_path_controls.json',results)
    # Source-path budget is a different issue from kernel subdivision invariance.
    square=[[-2,-2],[2,-2],[2,2],[-2,2]]
    r0=record('A',square)
    # Add three collinear points in each edge: focal corner0 is unchanged.
    dense=[]
    for p,q in zip(np.array(square),np.roll(np.array(square),-1,axis=0)):
        dense.extend((p+t*(q-p)).tolist() for t in [0,.25,.5,.75])
    r1=record('B',dense);rs=[r0,r1];ns=nodes_from_records(rs);ix={(n['id'],n['pair_index']):i for i,n in enumerate(ns)}
    D=distances(ns);bank=PathBank(rs,ns,config)
    z=bank.witness(ix[('A',0)],ix[('B',0)],'pair',5,D)
    dump(folder/'fixed_hop_subdivision_counterexample.json',{'records':rs,'result':z,
        'interpretation':'kernel is subdivision invariant in ideal geometry; fixed one/two-edge anchor proposal is not. Source points must remain, and absent anchor cannot establish different structure.'})
    # Independent dense discrete upper bound brackets the continuous PL distance.
    rng=np.random.default_rng(260106);checks=[]
    for rep in range(30):
        P=np.cumsum(rng.normal(size=(3,2)),axis=0);Q=np.cumsum(rng.normal(size=(4,2)),axis=0)
        lo,hi=euclidean_distance(P,Q)
        def dense(X):
            z=[X[0]]
            for a,b in zip(X[:-1],X[1:]):z.extend(a+t*(b-a) for t in np.arange(1,101)/100)
            return np.array(z)
        PP,QQ=dense(P),dense(Q);disc=float(discrete_distance(PP,QQ))
        step=max(np.linalg.norm(np.diff(PP,axis=0),axis=1).max(),np.linalg.norm(np.diff(QQ,axis=0),axis=1).max())
        checks.append({'case':rep,'continuous_interval':[lo,hi],'dense_discrete':disc,'max_edge':float(step),
            'within_conservative_bound':bool(disc+1e-7>=lo and disc<=hi+2*step+1e-7)})
    assert all(r['within_conservative_bound'] for r in checks)
    dump(folder/'independent_kernel_check.json',checks)
    # Same metric set, seam shift and input reversal invariance of short curves.
    invariance=[]
    for name,(a,b,truth) in controls.items():
        for side,j in [('top',0),('bottom',1)]:
            orig=spherical_distance_interval(rays(a[:,j]),rays(b[:,j]),.5)
            for shift in [37.,512.,1001.]:
                aa=a.copy();bb=b.copy();aa[:,:,0]=(aa[:,:,0]+shift)%1024;bb[:,:,0]=(bb[:,:,0]+shift)%1024
                v=spherical_distance_interval(rays(aa[::-1,j]),rays(bb[::-1,j]),.5)
                overlap=max(orig['lower_deg'],v['lower_deg'])<=min(orig['upper_deg'],v['upper_deg'])+1e-7
                assert overlap
                invariance.append({'case':name,'side':side,'shift_px':shift,'overlapping_bounds':bool(overlap)})
    dump(folder/'curve_seam_and_reversal_checks.json',invariance)
if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--out',required=True);run_controls(a.parse_args().out)
