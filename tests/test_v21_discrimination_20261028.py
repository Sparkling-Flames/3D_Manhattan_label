import gzip,json
from tools.thesis_main.analysis import rescore_v21_discrimination_20261028 as m

def load_input():
    with gzip.open(m.TARGET/'INPUT_TEAMS.jsonl.gz','rt',encoding='utf8') as f:return [json.loads(line) for line in f]

def test_discrimination_coverage_and_event_identities():
    c=m.read(m.TARGET/'COVERAGE.json');items=load_input()
    assert c['geometry_teams_available']==len(items)==41142
    assert c['missing_event_teams']==0 and not c['geometry_conflicts']
    assert all(not x['missing_geometry'] and not x['missing_scalar'] for x in c['sources'].values())
    assert len({r['team_key'] for r in items})==len(items)
    assert all(len(set(r['member_workers']))==r['k'] and len(set(m.unpack(r['member_object_ids'])))==r['k'] for r in items)

def test_all_four_sources_reproduce_original_reference():
    old={r['target_id']:r for r in m.read(m.ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json')};samples={}
    for r in load_input():
        if r['original_score_status']!='complete_conditional' or r['original_reference_id'] not in old or not r['original_metrics']['B8L2']:continue
        for name,scalar,_ in m.SOURCES:
            if scalar in r['source_scalar']:samples.setdefault(name,r)
        if len(samples)==4:break
    assert len(samples)==4
    fr,gd=m.diagnostic_modules()
    with m.scoring_engine() as (engine,models):
        for r in samples.values():
            out=m.score(r,old[r['original_reference_id']],engine,models,fr,gd)
            assert abs(out['result']['B8L2']-float(r['original_metrics']['B8L2']))<1e-9
            assert abs(out['result']['D10']-float(r['original_metrics']['D10']))<1e-9
            v=r['original_metrics']['ref_node_recall_9']
            if v:assert abs(out['reference_dependent_diagnostics']['ref_node_recall_9']-float(v))<1e-9


def test_scored_teams_preserve_members_and_reference_diagnostics():
    checks=m.read(m.TARGET/'CHECKS.json');src={x['team_key']:x for x in load_input()};seen=set()
    for p in sorted((m.TARGET/'shards').glob('*.jsonl.gz')):
        with gzip.open(p,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);key=r['team_key'];assert key in src and key not in seen;seen.add(key)
                assert set(r['member_workers'])==set(src[key]['member_workers'])
                assert r['original_score_status']==src[key]['original_score_status']
                assert r['reference_dependent_diagnostics_status'] in ['complete','not_applicable_no_candidate']
                if r['rescore_state']=='complete_conditional':
                    assert all(r['result'].get(k) is not None for k in ['B8L2','D10','WQ','A10','omission','extension'])
                    assert r['reference_dependent_diagnostics']['ref_node_recall_9'] is not None
                    assert r['reference_dependent_diagnostics']['matched_ref_pair_fraction'] is not None
                if r['rescore_state']=='original_no_connection':assert r['result'] is None
    assert len(seen)==checks['teams']==len(src)


def test_boundary_matching_is_original_event_algorithm():
    import ast
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    source=(m.BASE/'02A/measure_events.py').read_text(encoding='utf8')
    node=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='refdiagnostic')
    namespace={'np':np,'linear_sum_assignment':linear_sum_assignment};exec(compile(ast.Module(body=[node],type_ignores=[]),'frozen_refdiagnostic','exec'),namespace)
    refs={x['target_id']:x for x in m.read(m.OUT/'reference_catalog.json')};r=next(x for x in load_input() if x['original_score_status']=='complete_conditional')
    ref=refs[r['reference_id']]['points_1024x512'];expected=namespace['refdiagnostic']({'geometry':r['geometry']},{'reference':{'points_1024x512':ref}})
    got=m.matched_boundaries(r['geometry']['points'],ref)
    for k,v in got.items():assert abs(v-expected[k])<1e-12
