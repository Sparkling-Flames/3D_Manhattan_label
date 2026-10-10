#!/usr/bin/env python3
"""Independent finite-arc nearest-distance checks, offline and deterministic."""
import argparse
import math
from pathlib import Path

import numpy as np

from audit_geometry import write_csv, write_json
from geometric_components import spherical_point_to_arcs_distance, spherical_sym_distance, unit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    # Two vertices define the same minor arc twice; no polygon-area routine is used.
    arc=np.array([[1.,0.,0.],[0.,1.,0.]])
    cases=[
        ("arc_interior",[1,1,0],0.),
        ("normal_to_plane",[0,0,1],90.),
        ("outside_after_endpoint",[-1,0,0],90.),
        ("outside_before_endpoint",[0,-1,0],90.),
        ("arc_interior_nonzero",[1,1,1],math.degrees(math.atan(1/math.sqrt(2)))),
        ("antipodal_to_midpoint",[-1,-1,0],135.),
        ("endpoint_exact",[1,0,0],0.),
    ]
    rows=[]
    for name,p,expected in cases:
        observed=math.degrees(spherical_point_to_arcs_distance(np.array([p]),arc)[0])
        rows.append(dict(case_id=name,expected_deg=expected,observed_deg=observed,abs_error_deg=abs(expected-observed)))
    rng=np.random.default_rng(20261008)
    random_rows=[]
    for i in range(80):
        a=unit(rng.normal(size=3));normal=rng.normal(size=3)
        normal=unit(normal-np.dot(normal,a)*a);tangent=np.cross(normal,a)
        theta=float(rng.uniform(.01,np.pi-.01))
        b=a*np.cos(theta)+tangent*np.sin(theta)
        targets=np.array([a,b])*rng.uniform(.1,10,size=(2,1))
        points=unit(rng.normal(size=(25,3)))
        exact=spherical_point_to_arcs_distance(points,targets)
        phase=np.linspace(0,theta,8193)
        dense=a[None,:]*np.cos(phase)[:,None]+tangent[None,:]*np.sin(phase)[:,None]
        # Independently evaluate to dense points; the mesh half-step bounds its
        # excess over the exact curve minimum by triangle inequality on S2.
        dot=np.clip(points@dense.T,-1,1)
        brute=np.arccos(dot).min(axis=1)
        bound=theta/(2*(len(phase)-1))
        random_rows.append(dict(case_id=f"random_arc_{i:02d}",point_count=len(points),arc_length_deg=math.degrees(theta),
                                min_dense_minus_exact_deg=math.degrees(float((brute-exact).min())),
                                max_dense_minus_exact_deg=math.degrees(float((brute-exact).max())),
                                mesh_half_step_bound_deg=math.degrees(bound),
                                max_bound_violation_deg=math.degrees(float((brute-exact-bound).max()))))
    write_csv(out/"spherical_analytic_checks7.csv",rows)
    write_csv(out/"spherical_independent_dense_checks80.csv",random_rows)
    summary=dict(
        hand_cases=len(rows),random_arcs=len(random_rows),random_test_points=25*len(random_rows),seed=20261008,
        max_hand_case_abs_error_deg=max(r["abs_error_deg"] for r in rows),
        min_dense_minus_exact_deg=min(r["min_dense_minus_exact_deg"] for r in random_rows),
        max_mesh_bound_violation_deg=max(r["max_bound_violation_deg"] for r in random_rows),
        all_passed=max(r["abs_error_deg"] for r in rows)<1e-10 and min(r["min_dense_minus_exact_deg"] for r in random_rows)>-1e-8 and max(r["max_bound_violation_deg"] for r in random_rows)<1e-8,
        interpretation="Analytic endpoint and great-circle projection cases plus independent dense search within its provable mesh bound. This verifies distance calculation, not annotation quality calibration.")
    write_json(out/"spherical_distance_verification.json",summary)
    print(summary)


if __name__=="__main__":main()
