import pytest

from tools.thesis_main.analysis.build_worker_exchangeability_view_20261018 import bind_pairs


def test_display_preserves_pair_direction_and_rejects_multiple_replacements():
    design = [{'comparison_id': 'P', 'request_a': 'A', 'request_b': 'B', 'swap_kind': 'same_class'}]
    teams = [{'request_id': 'A', 'image_id': 'I', 'worker_ids': ['W1', 'W2', 'W3']},
             {'request_id': 'B', 'image_id': 'I', 'worker_ids': ['W1', 'W2', 'W4']}]
    result = bind_pairs(design, [dict(design[0], B8L2_delta='')], teams)
    assert result[0]['B8L2_delta'] == ''
    with pytest.raises(ValueError, match='pair binding'):
        bind_pairs(design, [dict(design[0], request_a='B', request_b='A')], teams)
    teams[1]['worker_ids'] = ['W1', 'W4', 'W5']
    with pytest.raises(ValueError, match='one replacement'):
        bind_pairs(design, [dict(design[0])], teams)


def test_display_requires_every_declared_pair():
    with pytest.raises(ValueError, match='coverage'):
        bind_pairs([{'comparison_id': 'P'}], [], [])
