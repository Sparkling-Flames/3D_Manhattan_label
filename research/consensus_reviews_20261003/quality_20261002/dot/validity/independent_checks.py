"""Independent measurement-validity checks; no input/source modifications.
Run: PYTHONPATH=/workspace/scratch/a365811da80c/audit-oct1-deps python independent_checks.py
These are new synthetic geometries, not new real annotations or GT adjudications.
"""
from pathlib import Path
import sys, json, math, hashlib
sys.dont_write_bytecode=True
import numpy as np
from shapely.geometry import Polygon
SRC=Path(__file__).resolve().parent/'reference'
sys.path.insert(0,str(SRC))
import quality_core as q
OUT=Path(__file__).resolve().parent
results={}; checks=[]
def check(name,cond):
    assert cond,name
    checks.append({'name':name,'passed':bool(cond)})
def geom(p,h=3.,name='new_independent_synthetic'):
    return q.reconstruct(q.record_from_geometry(p,h,name))
def select(m):
    keys=['bev_iou','current_model_volume_iou','current_height_mean_a_h','current_height_rms_a_h','self_axis_rms_deg','boundary_mean_h','boundary_p95_h','boundary_sampled_max_h','wall_height_rmse_h','top_curve_rmse_px','bottom_curve_rmse_px','column_iou']
    return {k:m[k] for k in keys}
square=np.array([[-2.,-2],[2,-2],[2,2],[-2,2]])
g=geom(square)
# 1. A true horizontal-prism task, with errors confined to top or footprint.
a=geom(square*math.sqrt(1/.9));b=geom(square,4.5)
ma,mb=q.compare(a,g),q.compare(b,g)
results['valid_prism_ranking_reversal']={'footprint_error_A':select(ma),'top_only_error_B':select(mb),'analytic_true_volume_iou_A':.9,'analytic_true_volume_iou_B':2/3,'meaning':'BEV rightly prefers B for footprint; volume rightly prefers A for exact occupied-prism overlap. No universal order exists without the target.'}
check('top_only_error_invisible_to_BEV_bottom_and_plan_boundary',abs(mb['bev_iou']-1)<1e-12 and mb['bottom_curve_rmse_px']<1e-10 and mb['boundary_mean_h']<1e-10 and mb['top_curve_rmse_px']>40)
check('valid_volume_ranking_reversal',ma['bev_iou']<mb['bev_iou'] and ma['current_model_volume_iou']>mb['current_model_volume_iou'] and abs(ma['current_model_volume_iou']-.9)<1e-12 and abs(mb['current_model_volume_iou']-2/3)<1e-12)
check('perfect_model_self_fit_is_not_GT_quality',ma['current_height_rms_a_h']<1e-12 and mb['current_height_rms_a_h']<1e-12 and ma['self_axis_rms_deg']<1e-5 and mb['self_axis_rms_deg']<1e-5 and mb['current_model_volume_iou']<.7)
# 2. Narrow deep indentation: negligible area change, material boundary change.
notch=np.array([[-2,-2],[2,-2],[2,2],[.52,2],[.52,-1.8],[.5,-1.8],[.5,2],[-2,2]],float)
ng=geom(notch);nm=q.compare(g,ng)
results['thin_deep_notch_omission']={'metrics':select(nm),'analytic_bev_iou':1-.02*3.8/16,'notch_width_h':.02,'notch_depth_h':3.8,'boundary_lengths_h':[g.polygon.length,ng.polygon.length],'meaning':'Importance of these local walls is task-dependent; region area alone almost ignores them.'}
check('near_perfect_area_can_hide_large_boundary_error',nm['bev_iou']>.995 and nm['boundary_p95_h']>1 and nm['boundary_sampled_max_h']>1.4)
# 3. Known affine roof: area integral differs from perimeter mean even without an unknown interior.
tri=np.array([[-1,-1],[8,-1],[-1,2]],float);hs=3+.5*tri[:,0];tg=geom(tri,hs)
mean=q.current_height_stats(tg)['mean_h'];area=tg.polygon.area
true_mean=3+.5*tg.polygon.centroid.x
true_volume=area*true_mean;proxy=area*mean
results['known_affine_roof_volume']={'points':tri.tolist(),'height_formula':'3 + 0.5*x','area_h2':area,'area_centroid_x_h':tg.polygon.centroid.x,'area_mean_height_h':true_mean,'perimeter_mean_height_h':mean,'exact_volume_h3':true_volume,'flat_proxy_volume_h3':proxy,'relative_bias':proxy/true_volume-1}
check('perimeter_mean_is_not_area_mean_for_affine_roof',abs(proxy/true_volume-1)>.1)
# 4. Narrow top feature: cyclic-start phase affects finite sampling, not actual geometry or current perimeter height.
p=np.array([[-2,-2],[-1.99,-2],[-1.98,-2],[-1.97,-2],[2,-2],[2,2],[-2,2]],float)
h=np.array([3,3,5,3,3,3,3],float);sp=geom(p,h)
rot=geom(np.roll(p,-2,axis=0),np.roll(h,-2))
bs=q.boundary_metrics(sp,g,512);br=q.boundary_metrics(rot,g,512)
# Two ramps each length .01, squared 0->2 linear integral = 4*.01/3 each; perimeter 16.
exact_rms=math.sqrt((2*.01*4/3)/16)
convergence=[]
for n in [512,2048,8192,32768,131072]:
    s=q.boundary_metrics(sp,g,n);r=q.boundary_metrics(rot,g,n)
    convergence.append({'n':n,'original_phase_rmse_h':s['wall_height_rmse_h'],'rotated_phase_rmse_h':r['wall_height_rmse_h']})
results['arclength_sampling_phase']={'exact_continuous_height_rmse_h':exact_rms,'n512_original':bs,'n512_cyclic_start_changed':br,'same_perimeter_mean_height_h':[q.current_height_stats(sp)['mean_h'],q.current_height_stats(rot)['mean_h']],'convergence':convergence,'meaning':'Formal arclength functional is invariant; finite 512-sample diagnostic is an approximation with no height bound from the geometric distance bound.'}
check('finite_sample_height_diagnostic_not_cyclic_start_invariant',bs['wall_height_rmse_h']<1e-10 and br['wall_height_rmse_h']>.06)
check('high_resolution_restores_analytic_arclength_height',abs(convergence[-1]['original_phase_rmse_h']-exact_rms)<2e-5 and abs(convergence[-1]['rotated_phase_rmse_h']-exact_rms)<2e-5)
check('current_perimeter_mean_unaffected_by_cyclic_start',abs(q.current_height_stats(sp)['mean_h']-q.current_height_stats(rot)['mean_h'])<1e-12)
# 5. Nearest 2D wall selection jumps between neighboring wall heights.
slit=np.array([[-2,-2],[2,-2],[2,2],[.01,2],[.01,.5],[-.01,.5],[-.01,2],[-2,2]],float)
slith=np.array([3,3,3,5,5,2,2,3],float);sg=geom(slit,slith)
queries=np.array([[-1e-6,1.25],[1e-6,1.25]])
d,hh=q.nearest_boundary(queries,sg)
results['nearest_height_correspondence_jump']={'query_points':queries.tolist(),'displacement_h':float(np.linalg.norm(queries[1]-queries[0])),'nearest_distances_h':d.tolist(),'nearest_heights_h':hh.tolist(),'height_jump_h':float(abs(hh[1]-hh[0])),'meaning':'Point probes of the correspondence used by wall_height_rmse_h; short nearest distance is insufficient to certify wall identity.'}
check('arbitrarily_small_horizontal_change_can_switch_height_correspondence',float(abs(hh[1]-hh[0]))>2.9 and d.max()<.011)
# 6. First-order error covariance from shared bottom input, checked independently by finite differences.
a0=math.atan(.25);b0=math.atan(.5)
def f(a,b):
    r=1/math.tan(a);return np.array([r,1+r*math.tan(b)])
J=np.array([[-1/math.sin(a0)**2,0],[-math.tan(b0)/math.sin(a0)**2,(1/math.tan(a0))/math.cos(b0)**2]])
eps=1e-6;fd=np.column_stack([(f(a0+eps,b0)-f(a0-eps,b0))/(2*eps),(f(a0,b0+eps)-f(a0,b0-eps))/(2*eps)])
sigma=.25*math.pi/512;cov=J@np.diag([sigma*sigma,sigma*sigma])@J.T
corr=cov[0,1]/math.sqrt(cov[0,0]*cov[1,1])
results['shared_bottom_jacobian']={'radius_h':4,'height_h':3,'native_coordinate_sigma_px':.25,'jacobian_rH_alphaBeta':J.tolist(),'finite_difference_max_abs_error':float(np.max(np.abs(J-fd))),'output_covariance':cov.tolist(),'independent_input_output_correlation':float(corr),'meaning':'Even independent top/bottom angular errors yield correlated range/height consequences. This is illustrative noise, not an estimate from real annotator disagreement.'}
check('jacobian_matches_finite_difference_and_induces_correlation',float(np.max(np.abs(J-fd)))<1e-7 and corr>.85)
# 7. Geometry with entirely occluded branch. Same first-hit contours, different declared range.
# Main square [-2,2]^2; right arm x[2,4], y[1,2]; upward branch x[3,4], y[2,L].
# For y/x > 2/3, all branch rays hit the main square first. The branch starts at y=3.
def hidden_branch(L):
    return np.array([[-2,-2],[2,-2],[2,1],[4,1],[4,L],[3,L],[3,2],[-2,2]],float)
v1=geom(hidden_branch(4));v2=geom(hidden_branch(7));vm=q.compare(v1,v2)
# Also verify at far higher azimuth resolution, to avoid mere raster aliasing.
t1,b1=q.column_bounds(v1,65536);t2,b2=q.column_bounds(v2,65536)
results['hidden_range_vs_column_contours']={'metrics':select(vm),'areas_h2':[v1.polygon.area,v2.polygon.area],'high_resolution_max_top_difference_rad':float(np.max(np.abs(t1-t2))),'high_resolution_max_bottom_difference_rad':float(np.max(np.abs(b1-b2))),'meaning':'First-hit projection cannot supervise genuinely hidden declared range. This is a disclosed representation limit, not a bug.'}
check('first_hit_contours_can_ignore_hidden_range',vm['bev_iou']<.9 and np.max(np.abs(t1-t2))<1e-12 and np.max(np.abs(b1-b2))<1e-12)
# 8. Exact ties on a positive-length source edge: cyclic target encoding changes argmin.
rect=np.array([[-2.,-10],[2,-10],[2,10],[-2,10]])
recth=4+rect[:,0]
ls=np.array([[-1.,-2],[1,-2],[1,.5],[0,.5],[0,2.5],[-1,2.5]])
ra=geom(ls,2);rb=geom(rect,recth);rc=geom(np.roll(rect,-2,axis=0),np.roll(recth,-2))
roundtrip=[q.boundary_metrics(ra,x,512)['wall_height_rmse_h'] for x in [rb,rc]]
# Preserve exact, valid analytic geometry to expose the geometric tie, rather than tiny trig round-trip asymmetry.
ea=q.Geometry(ls,np.full(len(ls),2.),ra.pairs,Polygon(ls))
eb=q.Geometry(rect,recth,rb.pairs,Polygon(rect))
ec=q.Geometry(np.roll(rect,-2,axis=0),np.roll(recth,-2),rc.pairs,Polygon(rect))
tieconv=[]
for n in [512,2048,8192,32768]:
    tieconv.append({'n':n,'original_cycle_rmse_h':q.boundary_metrics(ea,eb,n)['wall_height_rmse_h'],'rotated_cycle_rmse_h':q.boundary_metrics(ea,ec,n)['wall_height_rmse_h']})
probes=np.array([[0.,1.],[0.,2.]])
results['positive_length_exact_nearest_tie']={'source_floor':ls.tolist(),'target_floor':rect.tolist(),'target_heights':recth.tolist(),'exact_geometry_convergence':tieconv,'exact_probe_heights_original':q.nearest_boundary(probes,eb)[1].tolist(),'exact_probe_heights_rotated':q.nearest_boundary(probes,ec)[1].tolist(),'ERP_roundtrip_n512':roundtrip,'analytic_limit_squared_RMSE_difference':16/13,'meaning':'argmin chooses first edge at ties. Positive-length tie produces persistent arbitrary correspondence. In this ERP round-trip example floating asymmetry masks the exact tie; no real-data reversal is claimed.'}
check('exact_nearest_tie_is_not_fixed_by_more_samples',tieconv[-1]['original_cycle_rmse_h']-tieconv[-1]['rotated_cycle_rmse_h']>.2)
results['checks']=checks
results['provenance']={'source_read_only':'reference/quality_core.py (unchanged copy of returned src/quality_core.py)','source_sha256':hashlib.sha256((SRC/'quality_core.py').read_bytes()).hexdigest(),'synthetic_only':True,'real_GT_reassessed':False,'source_modified':False}
(OUT/'independent_results.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
print(json.dumps(results,indent=2,allow_nan=False))
