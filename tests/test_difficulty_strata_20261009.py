import pytest

from tools.thesis_main.analysis.difficulty_strata_20261009 import (
    merge_scene_reviews, classify_scene, attach_applicability, strata_summary,
)


def image(oos='not_recorded', door='not_recorded'):
    return dict(image='a', image_id='id-a', oos_status=oos, doorway_status=door)


def test_blank_review_preserves_axes_and_oos_doorway_overlap():
    original = {'a': image('confirmed', 'difficult')}
    reviews = [('review.json', dict(decisions=[dict(image_code='a', image_id='id-a',
        updated_at='2026-10-09', oos='', doorway='', note='')]))]
    merged, changes = merge_scene_reviews(original, reviews)
    assert merged['a']['oos_status'] == 'confirmed'
    assert merged['a']['doorway_status'] == 'difficult'
    assert classify_scene(merged['a']) == 'oos_and_doorway'
    assert changes == []
    assert original['a'] == image('confirmed', 'difficult')
    confirmed = [('presence.json', dict(decisions=[dict(reviews[0][1]['decisions'][0], doorway='是')]))]
    repeated, _ = merge_scene_reviews(original, confirmed)
    assert repeated['a']['doorway_source'] == 'presence.json'
    assert repeated['a']['doorway_annotation_source'] != 'presence.json'


def test_latest_axis_changes_are_logged_without_inventing_doorway_difficulty():
    decision = dict(image_code='a', image_id='id-a', updated_at='2026-10-09',
                    oos='否', doorway='是', note='门洞')
    merged, changes = merge_scene_reviews({'a': image('confirmed', 'none')},
                                         [('latest.json', dict(decisions=[decision]))])
    assert merged['a']['oos_status'] == 'not_oos'
    assert merged['a']['doorway_status'] == 'present_unknown'
    assert {c['axis'] for c in changes} == {'oos_status', 'doorway_status'}
    assert merged['a']['doorway_source'] == 'latest.json'
    with pytest.raises(ValueError, match='identity'):
        merge_scene_reviews({'a': image()}, [('bad.json', dict(decisions=[dict(decision, image_id='wrong')]))])


def test_unrecorded_is_not_clear_and_special_candidate_is_not_deployable():
    assert classify_scene(image()) == 'unflagged'
    assert classify_scene(image('not_oos', 'none')) == 'clear'
    assert classify_scene(image('not_recorded', 'pending')) == 'doorway_pending'
    ordinary = dict(image(), baseline_score=20., subjective_calibrated_candidate_score=25.)
    special = dict(image('confirmed', 'annotatable'), baseline_score=20.,
                   subjective_calibrated_candidate_score=25.)
    a, b = attach_applicability([ordinary, special])
    assert a['calibration_panel'] == 'ordinary_historical_panel'
    assert a['scene_review_status'] == 'unflagged_not_certified_normal'
    assert b['baseline_score'] == 20.
    assert b['subjective_calibrated_candidate_score'] is None
    assert b['calibration_panel'] == 'special_diagnostic_only'
    assert b['doorway_status'] == 'annotatable'


def test_axis_summary_does_not_mix_holdout_and_special_score_references():
    base = dict(building='b', subjective_label='简单', hohonet_offline_pair_count=4,
                d_model_feat_static=20., bilayout_floor_gap=0., baseline_score=70.,
                subjective_calibrated_candidate_score=75.)
    rows = attach_applicability([dict(image('not_oos', 'none'), **base),
        dict(image('not_oos', 'annotatable'), **base)])
    rows[1]['image'] = 'special'
    _, metrics = strata_summary(rows, {'a': dict(label=0, baseline_score=10., calibrated_score=20.)})
    selected = [r for r in metrics if r['axis']=='oos_status' and r['group']=='not_oos']
    assert len(selected) == 3
    assert {r['evaluation_panel'] for r in selected} == {'ordinary_historical_panel', 'special_diagnostic_only'}
    assert all(r['n']==1 for r in selected)
