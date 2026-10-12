from tools.thesis_main.analysis.quality_frozen_fusion_rescore_20261013 import select_reference, project


def test_reference_ambiguity_and_unavailable_projection_stay_null():
    assert select_reference('im', {'im': {'ref_a', 'ref_b'}}) == (None, 'ambiguous_reference')
    assert select_reference('missing', {}) == (None, 'missing_reference')
    assert select_reference('im', {'im': {'ref_a'}}) == ('ref_a', 'unique_package_reference')
    geometry, state = project([[0, 100], [0, 256], [300, 100], [300, 300], [600, 100], [600, 300]])
    assert geometry is None
    assert state['status'] == 'unavailable'
