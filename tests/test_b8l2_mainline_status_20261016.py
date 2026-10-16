from tools.thesis_main.analysis.b8l2_mainline_status_20261016 import summarize, room_pairs


def row(oid, image, worker, condition, quality, time=None):
    return dict(object_id=oid, image_id=image, image_code=image, worker_id=worker,
                condition=condition, B8L2=quality, IoU3D100=quality,
                active_time_seconds=time, target_matched_time_seconds=time,
                difficulty_class='简单')


def test_missing_quality_is_not_zero_and_conditions_stay_separate():
    rows = [row('a', 'im', 'w1', 'manual', 80, 10),
            row('b', 'im', 'w2', 'manual', None, 30),
            row('c', 'im', 'w1', 'semi', 20, None)]
    result = {r['condition']: r for r in summarize(rows, ['condition'])}
    assert result['manual']['B8L2_mean'] == 80
    assert result['manual']['n_quality_missing'] == 1
    assert result['manual']['n_quality_target_time_common'] == 1
    assert result['semi']['B8L2_mean'] == 20
    assert result['semi']['active_time_seconds_mean'] is None


def test_image_equal_mean_differs_from_answer_mean():
    rows = [row('a', 'im1', 'w1', 'manual', 100),
            row('b', 'im1', 'w2', 'manual', 100),
            row('c', 'im2', 'w1', 'manual', 0)]
    result = summarize(rows, ['condition'])[0]
    assert result['B8L2_mean'] == 200 / 3
    assert result['B8L2_image_equal_mean'] == 50


def test_room_comparison_uses_direct_relation_and_same_condition_worker():
    rows = [row('a', 'im1', 'w1', 'manual', 90),
            row('b', 'im2', 'w1', 'manual', 70),
            row('c', 'im2', 'w1', 'semi', 20)]
    relations = [dict(image_a='im1', image_b='im2', relation='confirmed_comparable', candidate_ids='r'),
                 dict(image_a='im1', image_b='im3', relation='candidate_unconfirmed', candidate_ids='x')]
    result = room_pairs(rows, relations)
    manual = next(r for r in result if r['condition'] == 'manual')
    assert manual['common_worker_delta_mean'] == -20
    assert manual['n_common_scored_workers'] == 1
    assert all(r['image_b'] != 'im3' for r in result)
