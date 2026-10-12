from pathlib import Path
from tools.thesis_main.analysis.quality_candidate_matrix_20261012 import build


def test_matrix_preserves_review_scope_and_unmeasured_controls():
    study=Path(__file__).resolve().parents[1]/'research/quality_top_height_response_20261012'
    result=build(study)
    rows={r['name']:r for r in result['candidates']}
    assert len(rows)==13
    assert rows['relative2']['P04']['direction_agrees'] is False
    assert rows['relative4']['P04']['direction_agrees'] is True
    assert all(r['pairs'][p]['direction_agrees'] is None for r in rows.values() for p in ('C01','C02','C04'))
    assert rows['probe_local0125_noTop']['real_reference_control'] is None
    assert rows['relative4_weakTop']['real_reference_control']['increases']==11
    assert result['human_review']['pairs'][1]['height_3d_preference'] is None
    assert result['quartic_vs_mean1']['confirmed']['quartic_lower_score_than_mean1']==0
    assert result['quartic_vs_mean1']['all']['quartic_lower_score_than_mean1']==2
    a,b=result['P01_direction_ablation']
    assert a['original']>b['original'] and a['direction_zero']<b['direction_zero']
    assert not result['formal_score_changed']
