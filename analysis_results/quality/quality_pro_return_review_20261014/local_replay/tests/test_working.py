"""Numerical and provenance tests, not human-validity certificates."""
import sys,copy,math
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from core import *
from mechanisms import geo,align_for_diagnostic
C=read(ROOT/'configs/ordinary_frozen.json')['config']

def mm(**kw):return dict(dict(iou_2d=.8,S_bottom_deg=2.,dir=5.,Hmean=.1,Hcenter=.05),**kw)

def test_closed_form():
    m=mm();H=(.1/.8)**2+(.05/.25)**2;B=4/32;D=1.5*25/(25+37.5)
    assert components(m,C)['score']==pytest.approx(100/(1/.8+B+D+H),abs=1e-12)

def test_zero_overlap():
    v=components(mm(iou_2d=0),C);assert v['score']==0 and v['floor_score']==0

def test_perfect_neutral():
    assert components(mm(iou_2d=1,S_bottom_deg=0,dir=0,Hmean=0,Hcenter=0),C)['score']==100

@pytest.mark.parametrize('key', ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter'])
def test_component_monotonic(key):
    vals=np.linspace(.01,.99,31) if key=='iou_2d' else np.linspace(0,20,31) if key=='dir' else np.linspace(0,10,31) if key=='S_bottom_deg' else np.linspace(0,1,31)
    q=np.array([components(mm(**{key:float(x)}),C)['score'] for x in vals])
    assert np.all(np.diff(q)>=-1e-10) if key=='iou_2d' else np.all(np.diff(q)<=1e-10)

@pytest.mark.parametrize('key',['Hmean','Hcenter'])
@pytest.mark.parametrize('value',[None,float('nan'),float('inf'),-1.])
def test_height_missing_not_zero(key,value):
    v=components(mm(**{key:value}),C)
    assert v['score'] is None and v['floor_score'] is not None
    assert v['status'] in ('floor_only','height_unavailable')

@pytest.mark.parametrize('key,value',[('iou_2d',-1),('iou_2d',2),('dir',30),('S_bottom_deg',181),('dir',float('nan'))])
def test_bad_floor_unavailable(key,value):
    v=components(mm(**{key:value}),C);assert v['score'] is None and v['status']=='unavailable'

def test_current_dominance_is_algebra_not_evidence():
    rng=np.random.default_rng(12)
    for _ in range(100):
        m=mm(iou_2d=float(rng.uniform(0,1)),S_bottom_deg=float(rng.uniform(0,20)),dir=float(rng.uniform(0,25)),Hmean=float(rng.uniform(0,.8)),Hcenter=float(rng.uniform(0,.3)))
        a,b=components(m,BASE),components(m,C)
        assert 0<=a['score']<=b['score']+1e-10<=100*m['iou_2d']+1e-9
        K=a['boundary_loss']+a['direction_loss']+a['height_loss'];I=m['iou_2d']
        expected=100*I*K*(1-I)/((1+I*K)*(1+K))
        assert b['score']-a['score']==pytest.approx(expected,abs=1e-11)

@pytest.mark.parametrize('key,value',[('iou_2d',.5),('S_bottom_deg',5),('dir',20),('Hmean',.4),('Hcenter',.2)])
def test_neutral_single_factor_preserved(key,value):
    m=mm(iou_2d=1,S_bottom_deg=0,dir=0,Hmean=0,Hcenter=0);m[key]=value
    assert components(m,C)['score']==pytest.approx(components(m,BASE)['score'],abs=1e-10)

def test_loss_decomposition_no_reference_selection():
    a,b=components(mm(),BASE),components(mm(),C)
    for k in ['boundary_loss','direction_loss','global_height_loss','local_height_loss']:assert a[k]==b[k]
    assert b['reference_selected_by_this_function'] is False and b['human_grade'] is None

def test_snapshot_boundaries():
    co=read(INPUT/'data/cohorts.json');assert [len(co[k]) for k in ['ordinary','severe','doorway','historical_only']]==[574,9,217,10]
    assert sum(r['scene_layer']['ordinary_status_is_explicit'] for r in co['ordinary'])==207
    assert len({r['record_id'] for k in ['ordinary','severe','doorway','historical_only'] for r in co[k]})==810
    assert not any(r['original_holdout'] for r in co['ordinary']+co['severe'])
    assert sum(r['status']=='held' for r in co['doorway'])==92
    assert {r['worker_id'] for r in co['severe']}=={'W029','W032','W034','W037'}
    assert all(r['formal_personnel_gate']=='excluded' for r in co['severe'])

def test_received_amendments_not_full_orders():
    a=read(INPUT/'human_review/quality_pro_review_20261014_amendment_01.json')
    assert {r['case_id'] for r in a['cases']}=={'Q02','Q03'}
    assert all(r['complete_quality_order']=='not_established' for r in a['cases'])
    assert all(r['use_prior_answer_as_complete_quality_constraint'] is False for r in a['cases'])

def test_stage2_final_identical_to_stage1():
    a=read(ROOT/'configs/ordinary_frozen.json');b=read(ROOT/'configs/WORKING_FINAL.json')
    assert a['config']==b['config'] and b['parameter_changes_after_ordinary_freeze']=={}
    assert a['doorway_rows_used_for_this_selection']==0
    assert b['ordinary_max_delta_from_frozen']==0 and b['ordinary_hashes_verified']

def test_source_byte_manifest():
    m=read(ROOT/'evidence/frozen_source_hashes.json')
    assert len(m['records'])==119
    assert all(sha(INPUT/r['path'])==r['sha256'] for r in m['records'])

def test_all_objects_and_pairing_audited():
    a=read(ROOT/'results/object_and_input_audit.json')
    assert a['objects']==907 and a['statuses']=={'rebuilt_and_equal':902,'unavailable_preserved':5}
    assert a['max_geometry_error']<1e-10 and a['max_preprocessing_error']<1e-10

def test_all_primary_metrics_reconstructed():
    for phase,n in [('ordinary',593),('doorway',125)]:
        s=read(ROOT/f'results/{phase}_reconstruction.json')['summary']
        assert s['count']==n and not s['failures']
        assert max(s['max_metric_difference'].values())<1e-8
    assert read(ROOT/'results/control_reconstruction.json')['count']==151

def test_held_and_q01_no_false_worker_quality():
    rr=read(ROOT/'results/effective_use_ledger.json')['records'];h=[r for r in rr if r['status']=='held']
    assert len(h)==92 and all(r['working_Q'] is None and r['iou3d_pct'] is None for r in h)
    q=next(r for r in rr if r['record_id']=='R03332')
    assert q['working_Q'] is not None and q['same_target_worker_quality_Q'] is None and not q['stage2_regression_eligible']
    assert sum(r['stage2_regression_eligible'] for r in rr)==117

@pytest.mark.parametrize('theta',[15,30,45,60,75,90])
def test_exact_rms_rhombus(theta):
    t=np.radians(theta);u=np.array([1,0]);v=np.array([np.cos(t),np.sin(t)])
    p=np.array([(-u-v)/2,(u-v)/2,(u+v)/2,(-u+v)/2]);d=profile(geo(p))
    assert d['D']==pytest.approx(.5*min(theta,90-theta),abs=1e-10)
    assert d['D']==pytest.approx(d['D_equal_edge'],abs=1e-10)

def test_l2_fixed_axis_not_l1():
    theta=30
    assert np.sqrt((0+theta**2+0+theta**2)/4)==pytest.approx(theta/math.sqrt(2))
    assert theta/math.sqrt(2)!=theta/2

def test_collinear_and_ring_invariance():
    p=np.array([[-2,-2],[2,-2],[2,1],[.5,1],[.5,3],[-.5,3],[-.5,1],[-2,1]])
    g=geo(p);split=np.insert(p,1,(p[0]+p[1])/2,axis=0)
    for q in [split,p[::-1],np.roll(p,3,axis=0)]:assert profile(geo(q))['D']==pytest.approx(profile(g)['D'],abs=1e-9)
    assert profile(g)['D']<1e-9

def test_spherical_seam_rotation_invariance():
    a=geo([[-2,-2],[2,-2],[2,1],[-2,1]]);g=geo([[-2,-2],[2,-2],[2,2],[-2,2]])
    theta=.94;rot=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
    def rotate(k):
        q=copy.deepcopy(k)
        for field in ['bottom3d','top3d']:
            p=np.array(q[field]);p[:,[0,2]]=p[:,[0,2]]@rot.T;q[field]=p.tolist()
        return q
    da=sp.spherical_sym_distance(a['bottom3d'],g['bottom3d'],2048)
    db=sp.spherical_sym_distance(rotate(a)['bottom3d'],rotate(g)['bottom3d'],2048)
    assert da==pytest.approx(db,abs=1e-8)

def test_normal_replacement_size_confound():
    p=np.array([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])
    a,g=geo(p*.6),geo(p)
    assert profile(a)['D']<1e-8 and normal_distance(a,g)['N_nearest_deg']>35
    assert diagnostics(a,g)['N_ray_deg']<1e-8

def test_ray_does_not_hide_lost_coverage():
    s=read(ROOT/'results/ordinary_candidate_summary.json')
    assert s['ray_normal_hill']['layers']['ordinary']['available']==525
    assert s['current_hill08']['layers']['ordinary']['available']==574

def test_dense_bottom_complete_q():
    rows=read(ROOT/'results/mechanism_controls.json')['dense_bottom'];assert len(rows)==112
    assert sum(r['status']=='complete' for r in rows)==108
    groups={}
    for r in rows:groups.setdefault((tuple(r['shape']),r['mode'],r['sign']),[]).append(r)
    for rr in groups.values():
        q=[r['scores']['loss_sum']['score'] for r in rr if r['status']=='complete']
        assert np.max(np.diff(q))<=1e-8

def test_j04_restoration_is_diagnostic_copy_only():
    j=read(ROOT/'results/J04_interventions.json');a=np.array(j['original_points']);ref=np.array(j['aligned_reference'])
    assert np.argmax(abs(a[1::2,1]-ref[1::2,1]))==0
    assert j['records'][0]['metrics']['dir']<2.21
    assert all(r['not_used_as_annotation_or_fit_row'] for r in j['records'])
    co=read(INPUT/'data/cohorts.json');objs={o['object_id']:o for o in read(INPUT/'data/objects.json')['objects']};r=next(r for r in co['ordinary'] if r['record_id']=='R03274')
    assert objs[r['object_id']]['points_1024x512']==j['original_points']

def test_frozen_iou_prism_local_height_blindspot():
    g=geo([[-2,-2],[2,-2],[2,2],[-2,2]]);a=copy.deepcopy(g)
    for i,delta in enumerate([.52,-.52,.52,-.52]):a['top3d'][i][1]+=delta
    m=full_measure(a,g,with_diagnostics=False)['metrics']
    assert m['iou_3d_corner_mean']==pytest.approx(1.,abs=1e-10)
    assert m['Hcenter']>.11 and components(m,C)['score']<83

def test_preferences_not_blind_certification():
    s=read(ROOT/'results/ordinary_candidate_summary.json')['loss_sum']['evidence']
    assert s['P01_margin']>0 and len(s['weak_grade_inversions'])==0
    assert read(ROOT/'configs/ordinary_frozen.json')['formal_algorithm_changed'] is False
