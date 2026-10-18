import pytest

from tools.thesis_main.analysis.build_worker_composition_view_20261018 import pack_geometry, pack_pools


def test_geometry_binds_exact_member_set_and_preserves_unavailable_output():
    pool = {'records': [{'id': 'R1', 'worker_id': 'W1'}, {'id': 'R2', 'worker_id': 'W2'}]}
    request = {'worker_ids': ['W2', 'W1']}
    state = {'subset': 'R1|R2', 'automatic': {'candidate': {'points': None, 'status': 'no_ring'},
                                          'ring_diagnostics': {'reason': 'missing_edges'}}}
    result = pack_geometry(request, pool, state)
    assert result['candidate']['points'] is None
    assert result['ring_diagnostics']['reason'] == 'missing_edges'
    with pytest.raises(ValueError, match='member binding'):
        pack_geometry({'worker_ids': ['W1']}, pool, state)


def test_geometry_does_not_upgrade_automatic_ring_to_human_confirmation():
    pool = {'records': [{'id': 'R1', 'worker_id': 'W1'}]}
    candidate = {'points': [[2, 3], [2, 300]], 'ring_confirmed': False, 'geometry_status': 'ok'}
    state = {'subset': 'R1', 'automatic': {'candidate': candidate}}
    assert pack_geometry({'worker_ids': ['W1']}, pool, state)['candidate'] == candidate


def test_display_refuses_duplicate_or_missing_request_coverage(tmp_path):
    with pytest.raises(ValueError, match='duplicate display request'):
        pack_pools([], [{'request_id': 'a'}, {'request_id': 'a'}], tmp_path)
    with pytest.raises(ValueError, match='coverage mismatch'):
        pack_pools([{'request_id': 'a'}], [], tmp_path)
