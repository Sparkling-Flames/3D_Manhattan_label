import importlib.util
from itertools import combinations
from pathlib import Path
import json

import numpy as np
import pytest


PATH = Path(__file__).resolve().parents[1] / "tools/thesis_main/analysis/analyze_uncertainty_handoff.py"
spec = importlib.util.spec_from_file_location("handoff_analysis", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_historical_mapping_preserves_values_and_is_not_twice_applied():
    p = np.array([[622,100],[622,400],[902,100],[902,400],
                  [351,100],[351,400],[167,100],[167,400]], float)
    original = p.copy()
    ids = mod.historical_pair_ids(p)
    assert ids == [6,7,4,5,0,1,2,3]
    assert sorted(ids) == list(range(8))
    assert np.array_equal(p, original)
    assert mod.historical_pair_ids(p[ids]) == list(range(8))
    assert ids != list(range(8))  # Mapping targets the original array, not an already sorted array.


def test_historical_mapping_does_not_drop_unpaired_points_or_repair_roles():
    with pytest.raises(ValueError, match="unpaired"):
        mod.historical_pair_ids([[0,100],[200,400],[400,100],[600,400]])
    with pytest.raises(ValueError, match="unpaired_point"):
        mod.historical_pair_ids([[0,100],[180,400],[360,100],[540,400],[720,100],[900,400]])
    p = [[10,257],[10,300],[300,100],[300,400],[700,100],[700,400]]
    assert mod.historical_pair_ids(p) == list(range(6))  # Same-hemisphere pair remains explicit.


def test_fixed_partition_capture_matches_exhaustive_enumeration():
    labels = [0,0,0,1,1,2]
    for k in range(1,7):
        observed = np.mean([len({labels[i] for i in s}) for s in combinations(range(6),k)])
        assert mod.expected_clusters([3,2,1], k) == pytest.approx(observed)
    assert mod.expected_clusters([3,2,1],6) == 3
    assert mod.expected_clusters([3,2,1],7) is None
    assert mod.expected_clusters([0,3,0],2) == 1


def test_delivered_local_candidates_and_review_requests_preserve_source_points():
    records = json.loads((mod.OUTPUT/'local_export_annotation_matches.json').read_text(encoding='utf-8'))
    candidate = next(r for r in records if r['annotation_id']==6154)
    assert candidate['annotation_identity']=='C1|0|72|3388|2|6154'
    assert candidate['condition']=='semi' and candidate['ground_truth'] is False
    for r in [candidate, *json.loads((mod.OUTPUT/'targeted_order_review.json').read_text(encoding='utf-8'))]:
        tasks=json.loads((mod.ROOT/r['source']).read_text(encoding='utf-8-sig'))
        task=next(t for t in tasks if t['id']==r['task_id'])
        ann=next(a for a in task['annotations'] if a['id']==r['annotation_id'])
        kp=[p for p in ann['result'] if p['type']=='keypointlabels']
        assert r['raw_keypoint_ids']==[p['id'] for p in kp]
        assert r['points_1024x512']==[[p['value']['x']*10.24,p['value']['y']*5.12] for p in kp]
    requests=json.loads((mod.OUTPUT/'targeted_order_review.json').read_text(encoding='utf-8'))
    assert {r['case_id'] for r in requests}=={'V07','V31'}
    assert all(r['agent_proposed_order'] is None for r in requests)
    for r in requests:
        if r['user_corner_pairs_in_boundary_order'] is not None:
            assert sorted(np.array(r['user_corner_pairs_in_boundary_order']).ravel())==list(range(len(r['points_1024x512'])))


def test_delivered_analysis_denominators_and_unresolved_semantics():
    import pandas as pd
    c=pd.read_csv(mod.OUTPUT/'cluster_count_validity_sensitivity.csv')
    assert set(c[c.invalid_partition_placeholders_excluded].contexts)=={65}
    assert set(c[~c.invalid_partition_placeholders_excluded].zero_placeholder_rows)=={7}
    s=pd.read_csv(mod.OUTPUT/'fixed_partition_capture_summary.csv')
    assert set(s[s.cohort=='same_partitions_current20_N20'].partitions)=={51}
    b=json.loads((mod.OUTPUT/'human_scope_identity_bindings.json').read_text(encoding='utf-8'))
    assert all(r['final_geometry_adjudication'] is None and not r['whole_cluster_semantics_verified'] for r in b['bindings'])


def test_user_bottom_order_requires_unique_complete_vertical_pairs():
    points=[[10,100],[10,400],[300,100],[300,400],[700,400],[700,100]]
    assert mod.user_bottom_order(points,[4,1,3])==[5,4,0,1,2,3]
    with pytest.raises(ValueError,match='complete'):
        mod.user_bottom_order(points,[1,3])
    with pytest.raises(ValueError,match='bottom'):
        mod.user_bottom_order(points,[0,3,4])


def test_distribution_recovery_and_mixture_match_exhaustive_subsets():
    # The third historical cluster is absent from the current pool.
    target=np.array([1,1,1])/3
    for k in [1,2,3]:
        values=[]
        for selected in combinations([0,0,1],k):
            counts=np.bincount(selected,minlength=3)
            values.append([abs(counts/k-target).sum()/2,target[counts==0].sum()])
        got=mod.distribution_recovery([[2,1,0]],[k],[1,1,1])
        assert got['expected_tv']==pytest.approx(np.mean(values,axis=0)[0])
        assert got['expected_missing_mass']==pytest.approx(np.mean(values,axis=0)[1])
    # Independent draws from two disjoint rosters, combined exactly once.
    got=mod.distribution_recovery([[2,1,0],[0,1,1]],[2,1],[2,2,1])
    expected=[]
    for first in combinations([0,0,1],2):
        for second in combinations([1,2],1):
            q=np.bincount(first+second,minlength=3)/3
            expected.append(abs(q-np.array([2,2,1])/5).sum()/2)
    assert got['expected_tv']==pytest.approx(np.mean(expected))


def test_confirmed_nonstar_layout_is_not_rejected_as_invalid_manhattan_geometry():
    c=json.loads((mod.OUTPUT/'confirmed_20260908/user_confirmations.json').read_text(encoding='utf-8'))
    audit,_=mod.helpers()
    for r in c:
        assert np.array_equal(np.asarray(r['raw_points'])[r['raw_point_ids']],r['derived_points'])
        assert sorted(r['raw_point_ids'])==list(range(len(r['raw_points'])))
        assert audit.footprint(r['derived_points']).is_valid
        with pytest.raises(ValueError,match='non_single_valued_or_nonstar_boundary'):
            audit.band(r['derived_points'])
