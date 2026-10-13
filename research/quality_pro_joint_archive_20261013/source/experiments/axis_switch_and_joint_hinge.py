#!/usr/bin/env python3
"""Axis-switch counterexample plus continuous composite direction alternative."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from structural_features import direction_descriptors,jointly_optimized_hinge
from export_real_descriptors import read,write,sha


def polygon(w):
    theta=np.radians([0.,20.,60.,180.,200.,240.])
    length=np.array([w,.3,.7-w]*2)
    edge=length[:,None]*np.column_stack([np.cos(theta),np.sin(theta)])
    p=np.vstack([np.zeros(2),np.cumsum(edge,axis=0)])[:-1]
    p-=p.mean(axis=0)
    return p


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--descriptors',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=Path(__file__).parent/'results');args=ap.parse_args()
    cases=[]
    for eps in (-1e-3,-1e-5,-1e-7,-1e-9,0.,1e-9,1e-7,1e-5,1e-3):
        p=polygon(7./60.+eps);d=direction_descriptors(p)
        cases.append({'length_weight_w':7./60.+eps,'epsilon':eps,'floor_ring':p.tolist(),
            'descriptor':d,'jointly_optimized_hinge':jointly_optimized_hinge(d,10.,2.)})
    rows=[]
    data=read(args.descriptors)
    for r in data['rows']:
        row={'record_id':r['record_id'],'status':r['status'],'annotation_geometry_sha256':r['annotation_geometry_sha256'],'values':{}}
        if r['status']=='available':
            for threshold in (5.,10.,15.):
                for gamma in (.5,2.,8.):
                    row['values'][f't{threshold:g}_g{gamma:g}']=jointly_optimized_hinge(r,threshold,gamma)
        rows.append(row)
    sampled_checks=[]
    # An independent dense-grid upper bound checks exact minima, including the
    # analytical switching example and 12 geometries selected by record order.
    to_check=[(str(c['epsilon']),c['descriptor']) for c in cases]
    rr=[r for r in data['rows'] if r['status']=='available']
    to_check += [(rr[i]['record_id'],rr[i]) for i in np.linspace(0,len(rr)-1,12).round().astype(int)]
    axis=np.linspace(0.,90.,36001,endpoint=False)
    for name,d in to_check:
        theta=np.asarray(d['edge_direction_deg']);w=np.asarray(d['length_weight'])
        r=(theta[None,:]-axis[:,None]+45.)%90.-45.
        objective=((r*r+2.*np.maximum(abs(r)-10.,0.)**2)*w).sum(axis=1)
        exact=jointly_optimized_hinge(d,10.,2.)
        sampled_checks.append({'case':name,'exact_deg2':exact['value_deg2'],'dense_grid_min_deg2':float(objective.min()),
                               'exact_minus_dense_grid':exact['value_deg2']-float(objective.min())})
    assert max(x['exact_minus_dense_grid'] for x in sampled_checks)<1e-8
    minus=next(c for c in cases if c['epsilon']==-1e-9);plus=next(c for c in cases if c['epsilon']==1e-9)
    summary={'n_real_descriptors':len(rows),'n_hinge_configs':9,'n_counterexamples':len(cases),
        'n_grid_checks':len(sampled_checks),'grid_axis_spacing_deg':90./36001,
        'near_switch_D_difference_deg':abs(minus['descriptor']['D_rms_deg']-plus['descriptor']['D_rms_deg']),
        'near_switch_M4_difference_deg4':abs(minus['descriptor']['weighted_abs_moments_deg_power']['p4']-plus['descriptor']['weighted_abs_moments_deg_power']['p4']),
        'near_switch_L2_axis_hinge_difference_deg2':abs(minus['jointly_optimized_hinge']['L2_selected_axis_value_deg2']-plus['jointly_optimized_hinge']['L2_selected_axis_value_deg2']),
        'near_switch_joint_min_hinge_difference_deg2':abs(minus['jointly_optimized_hinge']['value_deg2']-plus['jointly_optimized_hinge']['value_deg2']),
        'n_real_L2_axis_ties':sum(r.get('axis_tie_count',1)>1 for r in data['rows']),
        'max_dense_grid_minus_exact':max(-x['exact_minus_dense_grid'] for x in sampled_checks),
        'descriptors_sha256':sha(args.descriptors),'structural_features_sha256':sha(Path(__file__).parent/'structural_features.py')}
    write(args.out/'joint_hinge_descriptors.json',{'summary':summary,'rows':rows})
    write(args.out/'axis_switch_counterexample.json',{'summary':summary,'cases':cases,'grid_checks':sampled_checks})
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
