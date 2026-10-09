import numpy as np
import pytest

from tools.thesis_main.analysis import difficulty_dmodel_20261009 as d


def reference():
    return {**{f'{head}_mean': np.zeros(2, dtype=np.float32) for head in ('global', 'local')},
            **{f'{head}_components': np.eye(2, dtype=np.float32) for head in ('global', 'local')},
            **{f'{head}_scale': np.ones(2, dtype=np.float32) for head in ('global', 'local')},
            **{f'reference_{head}': np.array([[i, 0] for i in range(6)], dtype=np.float32)
               for head in ('global', 'local')}}


def test_frozen_projection_knn_and_separate_combination():
    global_score, local_score = d.frozen_scores(np.array([[0, 0]], dtype=np.float32),
                                               np.array([[1, 0]], dtype=np.float32), reference())
    assert global_score == [2.0]
    assert local_score == pytest.approx([1.4])
    assert d.score_fields(3, 4) == dict(d_model_feat_static=3, d_model_feat_local_max_static=4,
                                      static_model_risk_score=5)


def test_nonfinite_or_nonpositive_scale_does_not_materialize():
    r = reference()
    r['global_scale'][0] = 0
    with pytest.raises(ValueError, match='invalid_frozen_scale'):
        d.frozen_scores(np.zeros((1, 2), dtype=np.float32), np.zeros((1, 2), dtype=np.float32), r)
    r = reference()
    with pytest.raises(ValueError, match='nonfinite_descriptor'):
        d.frozen_scores(np.array([[np.nan, 0]], dtype=np.float32), np.zeros((1, 2), dtype=np.float32), r)


def test_reproduction_gate_all_inputs_and_both_heads():
    rows = [dict(descriptor_relative_l2=0, global_match=True, local_match=True)] * 3
    assert d.reproduction_passed(rows)
    assert not d.reproduction_passed(rows[:2])
    assert not d.reproduction_passed(rows[:2] + [dict(rows[0], local_match=False)])
    assert not d.reproduction_passed(rows[:2] + [dict(rows[0], descriptor_relative_l2=0.001)])


def test_panel_selection_retains_old_and_missing_source_failure(tmp_path):
    rows = [dict(image_id='b_pano', image='B', subjective_label='简单', calibration_panel='ordinary_historical_panel'),
            dict(image_id='c_pano', image='C', subjective_label='困难', calibration_panel='special_panel')]
    assert d.select_missing(rows, {'b_pano'}) == []
    missing = d.select_missing(rows, set())
    assert [x['image_id'] for x in missing] == ['b_pano']
    with pytest.raises(FileNotFoundError, match='b_pano'):
        d.source_paths(missing, tmp_path)


def test_duplicate_panel_identity_is_not_silently_overwritten():
    row = dict(image_id='a', subjective_label='简单', calibration_panel='ordinary_historical_panel')
    with pytest.raises(ValueError, match='duplicate_panel_image'):
        d.select_missing([row, row], set())


def test_ordinal_ties_and_constant_groups_are_explicit():
    assert d.ordinal_association([3, 1, 1], [2, 0, 0]) == pytest.approx(1)
    assert d.ordinal_association([1, 2, 3], [0, 0, 0]) is None
    assert d.ordinal_association([1, 1, 1], [0, 1, 2]) is None


def test_room_counts_exclude_empty_ids_in_every_building():
    rows = [dict(building='A', room=''), dict(building='B', room=''),
            dict(building='A', room='G1'), dict(building='A', room='G1'),
            dict(building='B', room='G1')]
    assert d.room_counts(rows) == dict(n_rooms=2, n_room_unknown_images=2)
