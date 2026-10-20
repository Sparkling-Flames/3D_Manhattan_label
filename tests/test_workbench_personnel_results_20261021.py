"""Display contract for archived personnel profiles/composition, no experiment replay."""
import json
import pytest

from tools.thesis_main.analysis import build_research_workbench_v2_20261019 as builder


def test_personnel_payload_preserves_scope_and_exact_saved_teams():
    path = builder.PAGE/'v2-resources/personnel_results.json'
    if not path.is_file():
        pytest.skip('Run the v2 workbench builder for the archived payload integration check.')
    data = builder.read(path)
    assert data['schema'] == 'personnel_results_display_v1'
    assert data['snapshot_id'] == builder.SNAPSHOT
    assert data['classification_status'] == 'new_classification_not_delivered'
    keys = [(r['worker_id'], r['condition'], r['origin'], r['panel']) for r in data['profiles']]
    assert len(keys) == len(set(keys)) == 182
    assert len(data['cases']) == 4
    assert sum(len(c['panels']) for c in data['cases']) == 12
    for case in data['cases']:
        source = (builder.ROOT/'research/workers/personnel_profiles_composition_20261020'/
                  'source/mechanisms/cases'/f"{case['case_id']}.json")
        assert case == builder.read(source)
        assert case['meta']['condition'] in ('manual', 'semi')
        for team in case['panels']:
            assert len(team['object_ids']) == team['state']['n']
            assert team['score']['reference_id'] == case['reference']['target_id']
    assert {r['domain'] for r in data['speed']} == {'allQ', 'above_peer_Q'}
    assert all('paired_events' in r for r in data['quality'])
    assert all('timed_comparisons' in r for r in data['speed'])
    assert all(p.startswith('research/') for p in data['tables_provenance'].values())
    assert 'Downloads' not in json.dumps(data, ensure_ascii=False)
    twin = (builder.PAGE/'v2-resources/personnel_results.js').read_text(encoding='utf-8')
    assert json.loads(twin.split(']= ', 1)[1].rsplit(';', 1)[0]) == data


def test_personnel_source_drift_is_rejected(tmp_path, monkeypatch):
    source = tmp_path/'research/workers/personnel_profiles_composition_20261020'
    source.mkdir(parents=True)
    (source/'profiles.csv').write_text('worker_id\nW100\n', encoding='utf-8')
    (source/'INTEGRATION.json').write_text(json.dumps(dict(
        schema='personnel_profiles_composition_integration_v1',
        kind='profiles_and_composition_not_personnel_classification',
        tables=[dict(id='profiles', path='profiles.csv', rows=2, columns=['worker_id'])])),
        encoding='utf-8')
    monkeypatch.setattr(builder, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='table drift'):
        builder.pack_personnel_results([], {})
