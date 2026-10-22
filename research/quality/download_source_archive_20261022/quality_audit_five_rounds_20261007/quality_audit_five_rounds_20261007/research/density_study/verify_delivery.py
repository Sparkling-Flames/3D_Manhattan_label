from core import *
import pandas as pd
A=pd.read_csv(OUT/'round_a_density.csv');B=pd.read_csv(OUT/'round_b_density.csv');S=pd.read_csv(OUT/'round_c_fit_status.csv');R=pd.read_csv(OUT/'round_c_reference_comparisons.csv')
checks={
 'a_has_105_controls':len(A)==105,
 'a_fixed_axis_assignments_identical':bool(A.same_axis_assignments.all()),
 'a_input_geometry_unchanged':float(A.input_top3d_symmetric_mean_h.max())<1e-10 and float(A.input_floor3d_symmetric_mean_h.max())<1e-10,
 'b_has_105_controls':len(B)==105,
 'b_fixed_axis_numerically_invariant':float(B.original_vertex_move_max_h.max())<1e-8,
 'b_preserves_nodes_and_expression':bool(B.all_nodes_retained.all() and B.source_expression_unchanged.all()),
 'c_has_433_times_2_attempts':len(S)==866,
 'c_has_226_images_22_buildings':S.image.nunique()==226 and S.building.nunique()==22,
 'c_success_preserves_nodes_and_expression':bool(S[S.status=='ok'].nodes_preserved.all() and S[S.status=='ok'].expression_preserved.all()),
 'c_reference_versions_separate':set(R.reference_version)=={'original','manual_revision'},
 'c_raw_original_ref_before_fit':len(R[R.reference_version=='original'])==int(sum(S.status=='ok')),
 'c_no_duplicate_fit_attempt_keys':not S.duplicated(['expression_id','method']).any(),
 'c_no_duplicate_reference_keys':not R.duplicated(['expression_id','method','reference_id']).any(),
 'c_before_after_deltas_correct':all(np.allclose(R['after_'+k]-R['before_'+k],R['delta_'+k],equal_nan=True) for k in ['iou','top_mae_deg','bottom_mae_deg','top3d_symmetric_mean_h','floor3d_symmetric_mean_h','omission_ref','extension_ref']),
}
# A portable explicit path import and a fresh solver smoke test.
f=np.array([[-3.,-1.,-2.],[3.,-1.,-2.],[3.,-1.,2.],[-3.,-1.,2.]])
t=f.copy();t[:,1]=1.5;r=record(t,f,{'id':'delivery_smoke'},'analytic_control');q=fit_boundary(r)
checks['fresh_analytic_solver_smoke']=q['status']=='ok' and boundary_loss(r,q['record'])<1e-20
save_json('verification.json',dict(checks=checks,all_pass=all(checks.values())))
print(json.dumps(checks,indent=2));assert all(checks.values())
