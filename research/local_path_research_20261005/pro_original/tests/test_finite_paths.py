from pathlib import Path
import sys,json,copy,itertools,importlib.util
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT))
from finite_paths import *
from real_diagnostics import proxy,continuous_curve_difference,arc_value,stationary
D=json.loads((ROOT/'inputs/domain.json').read_text());PROBES={p['id']:p for p in json.loads((ROOT/'inputs/probes.json').read_text())}

@pytest.fixture(scope='module')
def candidates():
    data=json.loads((ROOT/'results/final/finite/all_candidates.json').read_text())
    return data

def test_candidate_domain_partition(candidates):
    assert len(candidates)==324
    assert sum(not c['geometry_valid'] for c in candidates)==180
    assert sum(c['geometry_valid'] and not c['admissible'] for c in candidates)==34
    assert sum(c['admissible'] for c in candidates)==110
    assert len(dedup_candidates([c for c in candidates if c['admissible']]))==70

def test_all_source_person_assignments_unique_and_preserved():
    assert len(D['independent_workers'])==7
    assert len(D['observed_person_assignments'])==7
    for r in D['observed_person_assignments']:
        for j,i in enumerate(r['choices']):
            assert r['worker'] in [x['worker'] for x in D['segments'][j]['paths'][i]['donors']]
        assert assemble(D,r['choices'])['geometry_valid']

def test_duplicate_geometry_is_not_duplicate_person():
    rs=D['observed_person_assignments'];a=next(r for r in rs if r['worker']=='W3');b=next(r for r in rs if r['worker']=='W4')
    assert a['worker']!=b['worker']
    assert assemble(D,a['choices'])['geometry_key']==assemble(D,b['choices'])['geometry_key']

def test_collinear_not_semantic_detail():
    a=assemble(D,[0,0,0,0,0,0]);b=assemble(D,[2,0,0,0,0,0])
    assert a['pair_count']+1==b['pair_count']
    assert a['geometry_key']==b['geometry_key']
    assert a['area_h2']==b['area_h2']

def test_mutually_exclusive_union_is_not_admissible():
    c=assemble(D,[0,0,0,1,1,0]);assert c['geometry_valid']
    assert not c['admissible'] and 'scope_exclusive' in c['violated_constraints']

def test_pairwise_compatibility_does_not_replace_threeway():
    for idx in itertools.combinations(range(3),2):
        v=[0]*6
        for i in idx:v[i]=1
        assert assemble(D,v)['admissible']
    assert not assemble(D,[1,1,1,0,0,0])['admissible']

def test_geometry_and_compatibility_failures_separate():
    assert not assemble(D,[0,0,2,0,0,0])['geometry_valid']
    bad=assemble(D,[0,0,0,0,2,0])
    assert 'anchor_mismatch:4' in bad['geometry_issues']
    assert bad['points'] is None and bad['nodes_xz_top'] is None
    assert bad['declared_paths_xz_top'][4][-1]==[-2.2,2,1.]

def test_path_max_not_just_vertices():
    a=np.array([[-1.,0.],[1.,0.]])
    b=np.array([[-1.,0.],[0.,1.],[1.,0.]])
    val,w=directed_path_distance(a,b,True)
    assert val==pytest.approx(np.sqrt(.5),abs=1e-10)
    assert w['source_parameter']==pytest.approx(.5)
    assert directed_path_distance(b,a)==pytest.approx(1.)

def test_path_distance_collinear_invariance():
    a=np.array([[0.,0.,0.],[2.,0.,0.]])
    b=np.array([[0.,0.,0.],[.2,0.,0.],[.9,0.,0.],[2.,0.,0.]])
    assert directed_path_distance(a,b)==0
    assert directed_path_distance(b,a)==0

def test_path_distance_nonfinite_rejected():
    with pytest.raises(ValueError):directed_path_distance([[0,0],[np.nan,1]],[[0,0],[1,1]])

def test_generated_edge_no_votes():
    c=assemble(D,[0,0,0,0,0,0]);e=[e for e in c['edges'] if e['segment']==5]
    assert len(e)==1 and not e[0]['donors']
    assert c['voting_role']=='candidate_not_an_independent_vote'

def test_top_only_change_visible_in_3d_not_bev():
    a=assemble(D,[0,0,0,0,0,0]);b=assemble(D,[0,0,0,2,0,0])
    assert a['area_h2']==b['area_h2']
    assert evidence_prediction(a,PROBES['e4']) is False
    assert evidence_prediction(b,PROBES['e4']) is True
    assert a['geometry_key']!=b['geometry_key']

def test_unknown_compatibility_not_auto_certified(candidates):
    t=assemble(D,[0,0,1,0,0,1]);e=[dict(id=k,source_group=k,status='observed',probe_id=k,value=evidence_prediction(t,p)) for k,p in PROBES.items()]
    r=policy_select(candidates,D,dict(kind='evidence',max_wrong_source_groups=0),e,PROBES)
    assert r['geometry_count']==1 and r['status']=='compatibility_unresolved'

def test_missing_is_not_negative(candidates):
    empty=policy_select(candidates,D,dict(kind='evidence',max_wrong_source_groups=0),[],PROBES)
    missing=[dict(id=k,source_group=k,status='missing',probe_id=k,value=None) for k in PROBES]
    r=policy_select(candidates,D,dict(kind='evidence',max_wrong_source_groups=0),missing,PROBES)
    assert r['candidate_ids']==empty['candidate_ids']
    assert r['geometry_count']==70

def test_error_free_measurements_conditional_upper(candidates):
    for w in json.loads((ROOT/'evaluation/synthetic_truth.json').read_text())['worlds']:
        t=assemble(D,w['choices']);e=[dict(id=k,source_group=k,status='observed',probe_id=k,value=evidence_prediction(t,p)) for k,p in PROBES.items()]
        r=policy_select(candidates,D,dict(kind='evidence',max_wrong_source_groups=0),e,PROBES)
        assert r['geometry_count']==1
        assert any(c['geometry_key']==json.loads(json.dumps(t['geometry_key'])) for c in candidates if c['id'] in r['candidate_ids'])

def test_json_geometry_key_regression(candidates):
    fresh=assemble(D,[0,0,0,0,0,0]);stored=next(c for c in candidates if c['choices']==[0,0,0,0,0,0])
    assert stored['geometry_key']==json.loads(json.dumps(fresh['geometry_key']))

def test_conflicts_not_resolved_by_identifier(candidates):
    t=assemble(D,[1,0,1,1,0,0]);e=[dict(id=k,source_group=k,status='observed',probe_id=k,value=evidence_prediction(t,p)) for k,p in PROBES.items()]
    e.append(dict(e[0],id='opposite',source_group='other',value=not e[0]['value']))
    r=policy_select(candidates,D,dict(kind='evidence',max_wrong_source_groups=0),e,PROBES)
    assert r['status']=='no_feasible_candidate'
    e[-1]['id']='sorts_first'
    assert policy_select(candidates,D,dict(kind='evidence',max_wrong_source_groups=0),e,PROBES)['status']=='no_feasible_candidate'

def test_group_duplicate_not_extra_evidence(candidates):
    t=assemble(D,[1,0,1,1,0,0]);e=[dict(id=k,source_group=k,status='observed',probe_id=k,value=evidence_prediction(t,p)) for k,p in PROBES.items()];e[0]['value']=not e[0]['value']
    p=dict(kind='evidence',max_wrong_source_groups=1);a=policy_select(candidates,D,p,e,PROBES)
    e.append(dict(e[0],id='duplicated_same_source'))
    b=policy_select(candidates,D,p,e,PROBES)
    assert a['candidate_ids']==b['candidate_ids']

def test_beyond_group_error_budget_excludes_truth(candidates):
    t=assemble(D,[1,0,1,1,0,0]);e=[dict(id=k,source_group=k,status='observed',probe_id=k,value=evidence_prediction(t,p)) for k,p in PROBES.items()];e[0]['value']=not e[0]['value'];e.append(dict(e[0],id='second',source_group='independent_wrong'))
    r=policy_select(candidates,D,dict(kind='evidence',max_wrong_source_groups=1),e,PROBES)
    assert r['status']=='multiple_candidates'
    assert not any(c['geometry_key']==json.loads(json.dumps(t['geometry_key'])) for c in candidates if c['id'] in r['candidate_ids'])

def test_one_error_soundness_all_codewords(candidates):
    codes={str(c['geometry_key']):[c['probe_predictions'][k] for k in PROBES] for c in candidates if c['admissible']}
    a=np.array(list(codes.values()),int)
    for i,x in enumerate(a):
        for j in range(len(PROBES)):
            y=x.copy();y[j]^=1
            assert ((a!=y).sum(1)<=1)[i]

def test_search_same_domain():
    sizes=[len(s['paths']) for s in D['segments']];a,aa=exhaustive_addition(sizes);b,bb=exhaustive_elimination(sizes)
    assert set(a)==set(b) and len(a)==324
    assert aa['visited_partial_states']==bb['visited_partial_states']==568
    assert aa['initialization_atoms']==6 and bb['initialization_atoms']==16

def test_objective_order_independent(candidates):
    for p in json.loads((ROOT/'inputs/policies.json').read_text())[:3]:
        a=policy_select(candidates,D,p);b=policy_select(candidates[::-1],D,p)
        assert set(a['candidate_ids'])==set(b['candidate_ids'])

def test_observation_worlds_indistinguishable(candidates):
    streams=json.loads((ROOT/'inputs/evidence_streams.json').read_text());p=dict(kind='evidence',max_wrong_source_groups=0)
    rr=[policy_select(candidates,D,p,s['claims'],PROBES)['candidate_ids'] for s in streams if s['mode']=='observations_only']
    assert len(rr)==4 and all(r==rr[0] for r in rr)

def test_no_truth_used_by_construct(tmp_path,monkeypatch):
    import run_research
    real_load=run_research.load
    def checked(p):
        assert 'evaluation' not in str(p) and 'truth' not in str(p)
        return real_load(p)
    monkeypatch.setattr(run_research,'load',checked)
    run_research.construct(tmp_path/'new')
    assert json.loads((tmp_path/'new/construction_summary.json').read_text())['truth_opened'] is False

def test_same_longitude_independent_projection_control():
    for im,rid,i in [('rPc6DW4iMge-06','R01557',6),('uNb9QFRL6hY-67','R02928',3)]:
        r=next(r for r in json.loads((ROOT/'inputs'/f'{im}.json').read_text())['records'] if r['id']==rid)
        top,bottom=proxy(r)
        for side,points in enumerate([top,bottom]):
            q=project(points)
            source=np.array(r['points']).reshape(-1,2,2)[:,side]
            assert np.max(abs(q[:,1]-source[:,1]))<1e-10
            result=continuous_curve_difference([points[i-1],points[i],points[(i+1)%len(points)]],[points[i-1],points[(i+1)%len(points)]])
            assert max(p['crosscheck_difference_px'] for p in result['pieces'])<1e-6

def test_stationary_extrema_against_independent_grid():
    rng=np.random.default_rng(505)
    for _ in range(25):
        a,b=rng.normal(size=(2,2));lo=rng.uniform(-np.pi,np.pi);hi=lo+rng.uniform(.02,2.5)
        ts=stationary(a,b,lo,hi);m=max(abs(arc_value(a,t)-arc_value(b,t)) for t in ts)
        grid=np.linspace(lo,hi,8193);mg=np.max(abs(arc_value(a,grid)-arc_value(b,grid)))
        assert m+1e-7>=mg
        assert m-mg<.001

def test_input_source_readonly(candidates):
    before=copy.deepcopy(D);policy_select(candidates,D,dict(kind='carrier_pareto'))
    assert D==before
