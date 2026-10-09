import numpy as np
import pytest

from tools.thesis_main.analysis.difficulty_bilayout_probe_20261009 import (
    BRANCHES, depth_gap, inverse_yaw, floor_comparison,
    research_source_inputs,
)


def test_equal_positive_heads_are_zero_not_missing():
    result = depth_gap(np.ones(256), np.ones(256))
    assert result == dict(status='ok', relative_gap=0., signed_extended_minus_enclosed=0.)
    assert BRANCHES == {'extended': 'depth', 'enclosed': 'new_depth'}


@pytest.mark.parametrize('bad,status', [(None, 'missing'), (np.zeros(256), 'nonpositive_depth'),
                                      (np.full(256, np.nan), 'nonfinite'), (np.ones(128), 'shape_mismatch')])
def test_invalid_depth_remains_missing(bad, status):
    result = depth_gap(bad, np.ones(256))
    assert result['status'] == status
    assert result['relative_gap'] is None


def test_signed_head_difference_retains_direction():
    result = depth_gap(np.full(256, 2.), np.ones(256))
    assert result['relative_gap'] == pytest.approx(2/3)
    assert result['signed_extended_minus_enclosed'] == pytest.approx(2/3)
    assert depth_gap(np.ones(256), np.full(256, 2.))['signed_extended_minus_enclosed'] == pytest.approx(-2/3)


def test_yaw_reversal_matches_input_roll_direction():
    depth = np.arange(256.) + 1
    shifted = np.roll(depth, 64)
    assert np.array_equal(inverse_yaw(shifted, 256), depth)
    with pytest.raises(ValueError, match='integer_depth_bins'):
        inverse_yaw(depth, 1)


def test_floor_invalid_or_missing_is_not_zero(tmp_path):
    missing = floor_comparison(tmp_path/'a', tmp_path/'b')
    assert missing['floor_gap'] is None
    assert missing['extended_status'] == 'missing_file'
    for name in ['a', 'b']:
        np.savetxt(tmp_path/name, [[10, 100], [10, 400]])
    invalid = floor_comparison(tmp_path/'a', tmp_path/'b')
    assert invalid['floor_gap'] is None
    assert invalid['extended_status'] == 'odd_or_insufficient'


def test_floor_source_order_same_polygon_is_zero(tmp_path):
    points = [[128, 100], [128, 400], [384, 100], [384, 400],
              [640, 100], [640, 400], [896, 100], [896, 400]]
    for name in ['a', 'b']:
        np.savetxt(tmp_path/name, points)
    result = floor_comparison(tmp_path/'a', tmp_path/'b')
    assert result['floor_gap'] == 0.
    assert result['extended_pair_count'] == 4


def test_self_intersection_does_not_get_x_sorted_into_valid_ring(tmp_path):
    points = [[128, 100], [128, 400], [640, 100], [640, 400],
              [384, 100], [384, 400], [896, 100], [896, 400]]
    for name in ['a', 'b']:
        np.savetxt(tmp_path/name, points)
    result = floor_comparison(tmp_path/'a', tmp_path/'b')
    assert result['floor_gap'] is None
    assert result['extended_status'] == 'invalid_original_order_polygon'


def test_research_source_join_uses_exact_id_and_drops_labels(tmp_path):
    image = tmp_path/'same.png'
    image.write_bytes(b'fixture')
    original = [dict(image_id='a', image='A', building='B', image_source='external.png', split='test')]
    hoho = [dict(image_id='a', image='A', building='B', image_path=str(image), subjective_label='困难')]
    result = research_source_inputs(original,hoho)
    assert result[0]['image_source'] == str(image)
    assert result[0]['external_image_source'] == 'external.png'
    assert 'subjective_label' not in result[0]
    assert original[0]['image_source'] == 'external.png'


def test_research_source_mismatch_and_missing_files_fail(tmp_path):
    original = [dict(image_id='a', image='A', building='B', image_source='external.png', split='test')]
    with pytest.raises(ValueError,match='research_source_population_mismatch'):
        research_source_inputs(original,[])
    hoho = [dict(image_id='a', image='A', building='B', image_path=str(tmp_path/'missing.png'))]
    with pytest.raises(FileNotFoundError):
        research_source_inputs(original,hoho)
    with pytest.raises(ValueError,match='duplicate_research_source_image'):
        research_source_inputs(original,hoho+hoho)
    hoho[0]['building'] = 'wrong'
    with pytest.raises(ValueError,match='research_source_identity_mismatch'):
        research_source_inputs(original,hoho)
