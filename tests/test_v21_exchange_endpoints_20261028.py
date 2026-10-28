import gzip,json
from tools.thesis_main.analysis import rescore_v21_exchange_endpoints_20261028 as m

def test_exchange_source_coverage_and_identity():
    c=m.read(m.TARGET/'COVERAGE.json')
    assert c['unique_teams']==11561 and c['deduplicated_source_rows']==34
    assert all(not s['missing_geometry'] and not s['missing_scalar'] for s in c['sources'].values())
    with gzip.open(m.TARGET/'INPUT_TEAMS.jsonl.gz','rt',encoding='utf8') as f: items=[json.loads(x) for x in f]
    assert len({r['team_key'] for r in items})==len(items)==c['unique_teams']
    assert all(len(set(r['member_workers']))==r['k'] and len(m.object_ids(r['member_object_ids']))==r['k'] for r in items)

def test_preserved_failure_and_floor_only():
    with gzip.open(m.TARGET/'INPUT_TEAMS.jsonl.gz','rt',encoding='utf8') as f:
        items=[json.loads(x) for x in f]
    refs={r['target_id']:r for r in m.read(m.OUT/'reference_catalog.json')}
    sample={}
    for r in items:
        if r['original_score_status'] in ('no_connection','below_four','complete_conditional'):
            sample.setdefault(r['original_score_status'],r)
    assert len(sample)==3
    with m.scoring_engine() as (engine,models):
        out={k:m.score_one(r,refs[r['reference_id']],engine,models) for k,r in sample.items()}
    assert out['no_connection']['rescore_state']=='original_no_connection' and out['no_connection']['result'] is None
    assert out['below_four']['rescore_state']=='below_four'
    assert out['below_four']['result'].get('B8L2') is None
    assert out['complete_conditional']['result']['B8L2'] is not None
    assert out['complete_conditional']['result']['D10'] is not None
    assert out['complete_conditional']['result']['A10'] is not None
    assert out['complete_conditional']['result']['WQ'] is not None
    assert out['complete_conditional']['result']['omission'] is not None
    assert out['complete_conditional']['result']['extension'] is not None
    assert all(v is None for v in out['complete_conditional']['reference_dependent_diagnostics'].values())
    assert all(x['member_workers']==sample[k]['member_workers'] for k,x in out.items())


def test_completed_exchange_results_keep_status_and_reference_boundaries():
    c=m.read(m.TARGET/'CHECKS.json'); assert c['rows']==c['teams']==11561
    assert c['full_working_model_scores']==c['states']['complete_conditional']
    seen=set();states={}
    for path in sorted((m.TARGET/'shards').glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);assert r['team_key'] not in seen;seen.add(r['team_key'])
                assert len(r['member_workers'])==r['k']
                assert r['reference_dependent_diagnostics_status'] in ('complete','not_applicable_no_candidate')
                if r['reference_dependent_diagnostics_status']=='complete':assert r['reference_dependent_diagnostics']['ref_node_recall_9'] is not None
                if r['rescore_state']=='original_no_connection':assert r['result'] is None and not r['original_complete_evaluable']
                if r['rescore_state']=='complete_conditional':
                    assert all(r['result'].get(k) is not None for k in ['B8L2','D10','WQ','A10','WQ_no_B','WQ_no_D','WQ_no_H','omission','extension'])
                states[r['rescore_state']]=states.get(r['rescore_state'],0)+1
    assert len(seen)==c['teams'] and states==c['states']


def test_saved_geometry_reproduces_original_scores_on_original_reference():
    with gzip.open(m.TARGET/'INPUT_TEAMS.jsonl.gz','rt',encoding='utf8') as f:
        r=next(x for x in map(json.loads,f) if x['original_score_status']=='complete_conditional' and x['original_metrics']['B8L2'] and x['original_metrics']['D10'])
    refs={x['target_id']:x for x in m.read(m.ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json')}
    with m.scoring_engine() as (engine,models):out=m.score_one(r,refs[r['original_reference_id']],engine,models)
    for k in ['B8L2','D10']:assert abs(out['result'][k]-float(r['original_metrics'][k]))<1e-9


def test_enrichment_keeps_sample_scores_exactly():
    samples={r['team_key']:r['result'] for r in m.read(m.TARGET/'DIAGNOSTICS_BASELINE_SAMPLE.json')};found={}
    for path in sorted((m.TARGET/'shards').glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line)
                if r['team_key'] in samples:found[r['team_key']]=r['result']
    assert found==samples and len(found)==20
    d=m.read(m.TARGET/'DIAGNOSTICS_CHECKS.json');assert d['rows']==11561 and d['status']['complete']==11428


def test_enriched_diagnostics_match_native_and_original_reference():
    from tools.thesis_main.analysis.rescore_v21_same_room_20261028 import diagnostic_modules
    from tools.thesis_main.analysis.fuse_v21_new_pools_20261028 import adapter
    with gzip.open(m.TARGET/'INPUT_TEAMS.jsonl.gz','rt',encoding='utf8') as f:
        r=next(x for x in map(json.loads,f) if x['original_score_status']=='complete_conditional' and x['original_metrics']['ref_node_recall_5'])
    old={x['target_id']:x for x in m.read(m.ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json')};ref=old[r['original_reference_id']]
    fr,gd=diagnostic_modules();native=adapter().Engine(full_state=False);g=r['geometry']
    a=fr.reference_structure(g['points'],ref['points_1024x512']);assert a==native.fr.reference_structure(g['points'],ref['points_1024x512'])
    assert abs(a['ref_node_recall_5']-float(r['original_metrics']['ref_node_recall_5']))<1e-9
    x=gd.diagnose(g['footprint'],ref['floor_xz_h']);y=native.sg.signature(dict(team_key=r['team_key'],geometry=g),ref['floor_xz_h'],{})
    assert all(x[k]==y[k] for k in ['diag_status','diag_corner_recall_05','diag_wall_coverage_03','diag_wall_coverage_05'])
