import pandas as pd
import pytest

from tools.thesis_main.analysis.audit_quality_returns_20261107 import mean_prism_iou, summarize, effective_turns


def test_final_ratings_and_unknown_pair_denominator():
    rows = []
    for reviewer, values, valid in [('one', [0, 2], True), ('two', [None, 1], True), ('self', [2, 0], False)]:
        for side, final, q in zip(['left', 'right'], values, [10., 90.]):
            rows.append(dict(reviewer=reviewer, case_id='Q001', side=side, final=final,
                             initial=2 if side == 'left' else 0, valid=valid,
                             Q=q, D10=q, IoU=q, image='building-01', difficulty='easy'))
    result, _, pairs = summarize(pd.DataFrame(rows))
    assert result['ratings'] == 3
    assert result['complete_pair_judgments'] == 1
    assert result['distinct_grade_pairs'] == 1
    assert result['distinct_grade_direction_agreement']['Q'] == 1
    assert pairs.iloc[0].mean_grade_difference == 2
    single, _, _ = summarize(pd.DataFrame(rows).query("reviewer == 'one'"))
    assert single['rater_pair_exact_grade_agreement'] is None


def test_prism_uses_corner_mean_height():
    floor = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
    reference = dict(floor=floor, bottom3d=[[x, -1, z] for x, z in floor],
                     top3d=[[x, 1, z] for x, z in floor])
    candidate = dict(reference, top3d=[[x, h, z] for (x, z), h in zip(floor, [0.5, 1.5, 1.5, 0.5])])
    assert mean_prism_iou(candidate, reference) == pytest.approx(100.)


def test_effective_turns_ignores_collinear_extra_point():
    assert effective_turns([[-1, -1], [0, -1], [1, -1], [1, 1], [-1, 1]]) == 4
