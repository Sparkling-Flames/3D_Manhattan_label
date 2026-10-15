import sys,json,math,subprocess,shutil,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quality import score,read,geometry,measure
from closeout_checks import subdivision
from model_regression import mkfloor

@pytest.mark.parametrize('I',[0.,.05,.2,.5,.8,1.])
@pytest.mark.parametrize('D',[0.,5.,20.,45.])
def test_scalar_formula(I,D):
 m=dict(iou_2d=I,S_bottom_deg=2.,dir=D,Hmean=.1,Hcenter=.03);r=score(m);K=4/32+1.5*D**2/(D**2+37.5)+(.1/.8)**2+(.03/.25)**2
 assert r['WQ']==pytest.approx(100*I/(1+I*K));assert 0<=r['current']<=r['WQ']<=100

def test_perfect_and_missing():
 m=dict(iou_2d=1.,S_bottom_deg=0.,dir=0.,Hmean=0.,Hcenter=0.);assert score(m)['WQ']==100
 m['Hcenter']=None;r=score(m);assert r['WQ'] is None and r['floor_WQ']==100
 m['iou_2d']=None;assert score(m)['status']=='unavailable'
@pytest.mark.parametrize('key,val',[('iou_2d',1.1),('iou_2d',-.1),('dir',46),('dir',-1),('S_bottom_deg',-1)])
def test_domains(key,val):
 m=dict(iou_2d=.9,S_bottom_deg=1.,dir=3.,Hmean=.1,Hcenter=.1);m[key]=val
 with pytest.raises(ValueError):score(m)

def test_whole_population():
 d=read(ROOT/'results/recovered_admission_3152.json');assert d['summary']['records']==3152;assert d['summary']['holdout']==282;assert not d['differences'];assert d['summary']['ready_overlap_checked']==810
 f=pd.read_csv(ROOT/'results/ALL_3152_LEDGER.csv');assert f.record_id.nunique()==3152;assert f.WQ.notna().sum()==1145;assert f[f.stage=='oos'].WQ.isna().all();assert f[f.original_holdout].WQ.isna().all()
 assert f[(f.WQ.isna())&f.floor_WQ.notna()].shape[0]==217
 assert (f[f.score_status=='held'].WQ.isna()).all();assert f[(f.worker_id.isin(['W019','W026']))].WQ.isna().all()

def test_input_reconstruction():
 a=read(ROOT/'results/INPUT_RECONSTRUCTION_AUDIT.json');assert not a['errors'];assert a['objects']==3441;assert a['raw_x_available']==3023;assert not a['native_loader_run']

def test_pair_population_and_parity():
 a=read(ROOT/'results/all_scores.json');assert not a['failures'];assert a['summary']['pair_records']==1610;assert a['summary']['full_pairs']==1393;assert a['summary']['floor_pairs']==217
 for r in a['records']:
  if r['status']=='complete':assert r['IoU3D100'] is not None and r['scores']['WQ'] is not None
  else:assert r['scores']['WQ'] is None and r['IoU3D100'] is None
 for p in a['parity']:assert max(p['errors'].values())<1e-8

def test_route_and_height_not_borrowed():
 a=read(ROOT/'results/all_scores.json');routes={x['record_id']:x for x in read(ROOT/'source/routing_429.json')['rows']};candidates={c['candidate_id']:c for im in read(ROOT/'source/routing_prepared.json')['candidate_images'] for c in im['candidates']}
 for rid,r in a['canonical'].items():
  if r.get('binding')=='existing_route_preserved':assert r['pair_key'][1]==candidates[routes[rid]['selected_candidate_id']]['reference_object_id']
 f=pd.read_csv(ROOT/'results/ALL_3152_LEDGER.csv');z=f[f.score_status=='floor'];assert z.Hmean.isna().all() and z.Hcenter.isna().all()
 assert f[f.record_id=='R03332'].iloc[0].same_target_quality_hold
 assert f[f.record_id=='R00977'].iloc[0].latest_step_reference_pending

def test_previous_working_parity():
 a=read(ROOT/'results/FROZEN_MODEL_REGRESSION.json');assert a['prior_numeric_rows_compared']==718;assert a['maximum_previous_WQ_difference']<1e-8

def test_all_controls():
 a=read(ROOT/'results/CONTROLS_REMEASURED_151.json');assert len(a)==151;assert all(r['status']=='complete' for r in a)
 r={x['record_id']:x for x in a};assert r['rhombus:45']['metrics']['dir']>r['rhombus:30']['metrics']['dir'];assert r['rhombus:45']['scores']['WQ']>r['rhombus:30']['scores']['WQ']

def test_subdivision_is_not_new_geometry():
 p=mkfloor([[-1,-1],[1,-1],[1,1],[-1,1]]);before=json.dumps(p);q=subdivision(p,0,3);assert json.dumps(p)==before;assert len(q['bottom3d'])==7
 a=read(ROOT/'results/MECHANISM_CHECK_SUMMARY.json');assert a['WQ_subdivision_remeasured_records']==49;assert abs(a['subdivision_WQ_change']['min'])<1e-8;assert a['subdivision_IoU_change']['n_ge1']==149
 s=a['synthetic_subdivision'];assert s[0]['metrics']['iou_3d_corner_mean']==pytest.approx(1);assert s[1]['metrics']['iou_3d_corner_mean']==pytest.approx(25/26);assert s[0]['scores']['WQ']==pytest.approx(s[1]['scores']['WQ'])

def test_negative_control_not_human_label():
 a=read(ROOT/'results/FROZEN_MODEL_REGRESSION.json')['negative_controls'];assert a[0]['scores']['WQ']==pytest.approx(62.5);assert a[0]['metrics']['iou_3d_corner_mean']==pytest.approx(1);assert a[1]['metrics']['dir']==pytest.approx(0);assert a[1]['scores']['WQ']>90

def test_downstream_not_independent_trials():
 s=read(ROOT/'results/COMPARISON_SUMMARY.json');assert s['ordinary']['records']==962;assert s['ordinary']['WQ_IoU_reversals']==1388;assert s['ordinary']['WQ_current_reversals']==75;assert not s['ordinary']['independent_pairs'];assert not s['workers']['formal_worker_classes_changed'];assert s['workers']['rank_third_changes_WQ_IoU']==7
 t=read(ROOT/'results/TEAM_SELECTION_DIAGNOSTIC.json');assert t['summary']['3']['targets']==48;assert all(not r['read_target_scores_for_selection'] for r in t['records'])

def test_fusion_no_algorithm_or_scope_promotion():
 a=read(ROOT/'results/FUSION_220_RESULTS.json');s=a['summary'];assert (s['endpoints'],s['full'],s['floor_only'],s['unavailable'])==(220,144,1,75);assert s['formal_qualified']==0 and s['point_rebuilt']==60
 assert all(not r['formal_comparison_eligible'] and not r['fusion_recomputed'] for r in a['records']);assert s['auto_assisted_nonidentical']==5 and s['auto_assisted_direction_reversals']==1

def test_latest_review_is_not_blind():
 a=read(ROOT/'source/latest_feedback_projection.json');assert len(a['cases'])==8;assert a['all_cases_prior_score_exposure'];assert not a['used_to_fit_new_parameters'];b={r['case_id']:r for r in a['cases']};assert b['Q02']['overall']=='B_slight' and b['Q02']['floor']=='scope';assert b['L01']['height']=='B_slight'

def test_review_queue_and_bindings():
 q=read(ROOT/'review/CANDIDATE_QUEUE.json');assert q['summary']['cases']==25;assert q['selection_before_photo_filter'];assert not q['blind_test_claimed'];d=read(ROOT/'review/DISPLAY_DATA.json');assert len(d)==25
 text=json.dumps(d);assert 'selection_reason' not in text and 'IoU3D100' not in text and 'WQ' not in text
 for r in q['cases']:assert all(b['record_id'] for b in r['bindings'])

def test_html_js_syntax():
 if not shutil.which('node'):pytest.skip('node not installed; optional JS syntax test')
 s=(ROOT/'review/REVIEW.html').read_text();js=s.split('<script>',1)[1].split('</script>',1)[0]
 with tempfile.TemporaryDirectory() as td:
  p=Path(td)/'check.js';p.write_text(js);r=subprocess.run(['node','--check',str(p)],capture_output=True,text=True);assert r.returncode==0,r.stderr

def test_official_pixel_center_bridge():
 from quality import trad
 a=mkfloor([[-1,-2],[2,-2],[2,3],[-1,3]],h=2.6)
 c=trad.frozen_to_hohonet_pixels(a)
 vf=(.5-(c[1::2,1]+.5)/512)*np.pi;vt=(.5-(c[::2,1]+.5)/512)*np.pi
 official_h=1.6+(-1.6/np.tan(vf))*np.tan(vt)
 assert np.max(abs(official_h/1.6-(np.array(a['top3d'])[:,1]+1)))<1e-12
