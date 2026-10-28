import csv,gzip,json
from tools.thesis_main.analysis import rescore_v21_same_room_20261028 as m

def load_items(name):
    with gzip.open(m.TARGET/name,'rt',encoding='utf8') as f:return [json.loads(line) for line in f]

def test_coverage_and_missing_are_explicit():
    c=m.read(m.TARGET/'COVERAGE.json');a=load_items('INPUT_TEAMS.jsonl.gz');missing=load_items('MISSING_GEOMETRY.jsonl.gz')
    assert len(a)==c['geometries_available'] and len(missing)==c['geometries_missing']
    assert len({r['team_key'] for r in a+missing})==len(a)+len(missing)
    assert all(r['member_set_key']=='|'.join(sorted(r['member_workers'])) and len(r['member_workers'])==r['k'] for r in a+missing)
    assert not c['locator_missing_files'] and not c['precision_extension_missing_files'] and not c['current_conflicts']
    with gzip.open(m.TARGET/'CURRENT_CLASS_PANEL_LINKS.csv.gz','rt',encoding='utf8',newline='') as f:assert sum(1 for _ in csv.DictReader(f))==c['matching_panel_links']

def test_original_reference_sample_scores_and_diagnostics():
    old={x['target_id']:x for x in m.read(m.ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json')};samples=[];pools=set()
    for r in load_items('INPUT_TEAMS.jsonl.gz'):
        if r['pool_id'] not in pools and r['original_score_status']=='complete_conditional' and r['original_reference_id'] in old and r['original_metrics']['B8L2'] and r['original_metrics']['ref_node_recall_5']:
            samples.append(r);pools.add(r['pool_id'])
            if len(samples)==4:break
    assert len(samples)==4
    fr,gd=m.diagnostic_modules()
    with m.scoring_engine() as (engine,models):
        for r in samples:
            x=m.score(r,old[r['original_reference_id']],engine,models,fr,gd)
            assert abs(float(r['original_metrics']['B8L2'])-x['result']['B8L2'])<1e-9
            for k in ['ref_node_recall_5','ref_edge_recall_9','diag_corner_recall_05','diag_wall_coverage_03']:
                if r['original_metrics'].get(k):assert abs(float(r['original_metrics'][k])-x['reference_dependent_diagnostics'][k])<1e-9


def test_reference_diagnostics_match_native_adapter():
    from tools.thesis_main.analysis.fuse_v21_new_pools_20261028 import adapter
    native=adapter().Engine(full_state=False);fr,gd=m.diagnostic_modules()
    old={x['target_id']:x for x in m.read(m.ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json')}
    r=next(x for x in load_items('INPUT_TEAMS.jsonl.gz') if x['original_score_status']=='complete_conditional' and x['original_reference_id'] in old)
    ref=old[r['original_reference_id']];g=r['geometry']
    assert fr.reference_structure(g['points'],ref['points_1024x512'])==native.fr.reference_structure(g['points'],ref['points_1024x512'])
    x=gd.diagnose(g['footprint'],ref['floor_xz_h']);y=native.sg.signature(dict(team_key=r['team_key'],geometry=g),ref['floor_xz_h'],{})
    for k in ['diag_status','diag_corner_recall_05','diag_wall_coverage_03','diag_wall_coverage_05']:assert x[k]==y[k]


def test_saved_scores_and_reference_diagnostic_coverage():
    checks=m.read(m.TARGET/'CHECKS.json');items={r['team_key']:r for r in load_items('INPUT_TEAMS.jsonl.gz')};seen=set()
    for path in sorted((m.TARGET/'shards').glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf8') as f:
            for line in f:
                row=json.loads(line);key=row['team_key'];assert key not in seen and key in items;seen.add(key)
                assert row['member_set_key']==items[key]['member_set_key']
                assert row['reference_dependent_diagnostics_status'] in ('complete','not_applicable_no_candidate')
                if row['rescore_state']=='complete_conditional':
                    assert row['result']['B8L2'] is not None and row['result']['D10'] is not None
                    assert row['reference_dependent_diagnostics']['ref_node_recall_9'] is not None
                if row['rescore_state']=='original_no_connection':
                    assert row['result'] is None and row['reference_dependent_diagnostics_status']=='not_applicable_no_candidate'
    assert len(seen)==checks['rows']==len(items)


def test_large_block_event_links_retain_exact_members():
    c=m.read(m.TARGET/'COVERAGE.json');members={r['team_key']:set(r['member_workers']) for r in load_items('INPUT_TEAMS.jsonl.gz') if r['study']=='large_block'};count=0
    with gzip.open(m.TARGET/'LARGE_BLOCK_EVENT_LINKS.csv.gz','rt',encoding='utf8',newline='') as f:
        for row in csv.DictReader(f):
            count+=1
            for letter in 'ABC':
                expected=set(m.unpack(row[letter+'_members']))
                for side in 'ab':
                    key=row[f'team_key_{letter}_{side}']
                    if key in members:assert members[key]==expected
    assert count==c['large_block_affected_event_links'] and c['large_block_cross_view_members_verified']
