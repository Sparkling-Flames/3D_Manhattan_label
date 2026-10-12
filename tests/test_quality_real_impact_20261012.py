from pathlib import Path
from tools.thesis_main.analysis.quality_real_impact_20261012 import build


def test_real_impact_keeps_duplicates_review_scope_and_score_parity():
    p=Path(__file__).resolve().parents[1]/'research/quality_top_height_response_20261012'
    out=build(p)
    assert out['strata']['confirmed']['records']==143
    assert out['strata']['confirmed']['coordinate_groups']==114
    assert out['strata']['confirmed']['same_reference_pairs']==641
    assert out['verification']['maximum_saved_score_delta']<1e-10
    assert out['known_anchors']['P02']['human_score_cutoff'] is None
    assert out['review']['prior_same_pair_review'] is False
    assert out['review']['answer'] is None
    assert out['review']['prior_image_exposure'] is True
