import numpy as np
import pytest

from tools.thesis_main.analysis.local_point_research.pair_pilot import compare_pairs


def test_binding_is_distinct_from_independent_endpoints():
    points = [[100,100],[100,400],[300,100],[300,400]]
    proper, crossed = [[1,2],[3,4]], [[1,4],[3,2]]
    same = compare_pairs(points,points,proper,proper)
    changed = compare_pairs(points,points,proper,crossed)
    assert same['bound_bottleneck_deg'] == pytest.approx(0,abs=1e-10)
    assert changed['separate_bottleneck_deg'] == pytest.approx(0,abs=1e-10)
    assert changed['bound_bottleneck_deg'] > 12
    shifted = np.array(points,float);shifted[:,0]=(shifted[:,0]+950)%1024
    assert compare_pairs(shifted,shifted,proper,crossed)['bound_bottleneck_deg'] == pytest.approx(changed['bound_bottleneck_deg'])
    with pytest.raises(ValueError):compare_pairs(points,points,[[1,2],[1,4]],proper)


def test_count_gate_and_permutation():
    a = [[100,100],[100,400],[300,100],[300,400]]
    b = a+[[301,100],[301,400]]
    r = compare_pairs(a,b,[[1,2],[3,4]],[[1,2],[3,4],[5,6]])
    assert r['bound_bottleneck_deg'] is None and not r['same_count']
    assert all(x['bound_matched_pairs']==2 and not x['strict_compatible'] for x in r['radii'])
    p = [a[i] for i in [2,0,3,1]]
    assert compare_pairs(a,p,[[1,2],[3,4]],[[2,4],[1,3]])['bound_bottleneck_deg'] == pytest.approx(0,abs=1e-10)


def test_six_image_evidence_keeps_source_identity_and_blank_decisions():
    from tools.thesis_main.analysis.local_point_research.pair_pilot import build_evidence
    from tools.thesis_main.analysis.local_point_research.local_points import load
    rows,_=load();source={r['canonical_annotation_id']:r for r in rows};evidence=build_evidence()
    assert len(evidence)==6 and len({r['key'] for r in evidence})==6
    for r in evidence:
        assert r['user_decision'] is None
        for side in ['a','b']:
            original=source[r['id_'+side]]
            assert original['worker_id']==r['worker_'+side] and original['raw_condition']==r['condition']
            assert original['effective_points_1024x512']==r['points_'+side]
        for c in r['comparisons']:
            if c['same_count']:
                assert c['bound_bottleneck_deg']>=c['separate_bottleneck_deg']-1e-9
            else:
                assert c['bound_bottleneck_deg'] is None and not any(t['strict_compatible'] for t in c['radii'])
