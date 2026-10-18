import pandas as pd

from tools.thesis_main.analysis.worker_v1_composition_20261017 import (
    group_labels, policy_order, semi_state, reusable_geometry,
)


def test_qt_signs_and_missing_are_not_forced_into_four_cells():
    assert group_labels(1, True, -1, True) == ('higher', 'faster', 'higher_faster')
    assert group_labels(-1, True, 1, True) == ('lower', 'slower', 'lower_slower')
    assert group_labels(0, True, -1, True)[2] == 'unclassified'
    assert group_labels(1, True, float('nan'), False)[2] == 'unclassified'


def test_selection_uses_only_fold_labels_and_keeps_real_pool_members():
    profiles = {'A': {'Q_group': 'higher', 'QT_group': 'higher_faster'},
                'B': {'Q_group': 'lower', 'QT_group': 'lower_slower'}}
    order = policy_order(['A', 'B', 'C'], profiles, 'Q_higher_first', 4)
    assert order[0] == 'A'
    assert set(order) == {'A', 'B', 'C'} and len(order) == 3
    assert policy_order(['A', 'B', 'C'], profiles, 'random', 4) == policy_order(['C', 'A', 'B'], profiles, 'random', 4)


def test_unchanged_or_changed_does_not_automatically_mean_error_or_correction():
    assert semi_state('unchanged_coordinates', False, None) == 'unchanged_initial_correctness_unknown'
    assert semi_state('unchanged_coordinates', True, None) == 'confirmed_wrong_initialization_unrepaired'
    assert semi_state('changed_coordinates', True, None) == 'edited_correction_unknown'
    assert semi_state('changed_coordinates', True, 'not_corrected') == 'edited_error_remains_explicit_review'
    assert semi_state('unchanged_coordinates', False, 'initial_correct') == 'correct_initialization_preserved'


def test_reuse_never_reinstates_excluded_member_or_changed_geometry():
    assert reusable_geometry('A|B', {'A', 'B', 'C'})
    assert not reusable_geometry('A|X', {'A', 'B', 'C'})
    assert not reusable_geometry('A|A', {'A', 'B'})


def test_delivered_requests_are_leak_free_and_matched():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    out = root / 'research/workers/worker_v1_composition_20261017'
    data = json.loads((out / 'TEAM_REQUESTS.json').read_text(encoding='utf-8'))
    assert data['data_release'] == 'v1'
    teams = {r['request_id']: r for r in data['teams']}
    folds = json.loads((out / 'fold_training_ranges.json').read_text(encoding='utf-8'))
    for key, fold in folds.items():
        assert key not in fold['Q']['training_buildings']
        assert key not in fold['T_source']['training_buildings']
    for path in data['paths']:
        pool = set(path['source_pool_worker_ids'])
        assert len(pool) >= 3 and set(path['ordered_worker_ids']) == pool
        for k, request_id in enumerate(path['prefix_request_ids'], 1):
            team = teams[request_id]
            assert team['k'] == k and len(set(team['worker_ids'])) == k
            assert set(team['worker_ids']) <= pool
        assert len(path['matched_random_prefix_request_ids']) == len(pool)
    for image_id in {p['image_id'] for p in data['paths']}:
        endpoints = {p['prefix_request_ids'][-1] for p in data['paths'] if p['image_id'] == image_id}
        assert len(endpoints) == 1
    records = pd.read_csv(out / 'record_evidence.csv')
    assert len(records) == 3222 and records.worker_id.nunique() == 27
    assert not records.loc[records.is_oos, 'in_Q_training'].any()
    assert records.S_source_response.notna().sum() == 1083
    assert set(records.loc[records.historical_worker_exclusion, 'worker_id']) == {'W019', 'W026'}
    assert all(not ({'W019', 'W026'} & set(t['worker_ids'])) for t in teams.values())
    semi = records[records.condition.eq('semi')]
    assert len(semi) == 574
    assert not semi.loc[semi.model_edit_status.eq('changed_coordinates'), 'explicit_correction_success'].any()
    assert not records.loc[records.cleaning_disposition.eq('historical_not_accepted'), 'confirmed_person_error_exclusion'].any()
    joined = pd.read_csv(out / 'statistics_record_profiles.csv')
    assert len(joined) == 6444 and not joined.duplicated(['object_id', 'metric']).any()
