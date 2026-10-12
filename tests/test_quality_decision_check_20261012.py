from pathlib import Path
from copy import deepcopy
import pytest
from tools.thesis_main.analysis.quality_top_height_response_20261012 import analytic_case,profile_moments,read_json
from tools.thesis_main.analysis.quality_local_profile_20261012 import exact_same_floor_centered
from tools.thesis_main.analysis.quality_decision_check_20261012 import perturb_reference,run


def test_real_reference_perturbation_preserves_floor_and_exact_centered_error():
    g=analytic_case(1,.03)['annotation'];before=deepcopy(g)
    for phase in [-1,1]:
        a=perturb_reference(g,1.2,.1,phase)
        assert g==before and a['bottom3d']==g['bottom3d']
        assert profile_moments(a)['mean']/profile_moments(g)['mean']==pytest.approx(1.2)
        assert exact_same_floor_centered(a,g)==pytest.approx(.1)


def test_bounded_run_preserves_domains_and_review_provenance():
    p=Path(__file__).resolve().parents[1]/'research/quality_top_height_response_20261012'
    out=run(read_json(p/'inputs.json'),read_json(p/'protocol.json'),read_json(p/'results.json'),read_json(p/'decision_check_design.json'))
    assert len(out['references'])==16
    assert len(out['comparisons'])==64
    assert len(out['review_pairs'])==2
    assert all(pair['answer'] is None for pair in out['review_pairs'])
    assert all(row['applicability_confirmed'] for p in out['review_pairs'] for row in p['records'])
    assert all(c['effects'] is None for c in out['controls'] if c['status']!='available')
    assert out['verification']['maximum_Hcenter_target_error']<1e-12
