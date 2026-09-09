import pytest

from tools.thesis_main.analysis.audit_building_convergence_20260908 import (
    ordered_points, require_same_points, source_annotation_index, require_partition_coverage,
)


def test_raw_points_preserve_export_sequence_and_reject_a_reorder():
    results = [
        {'type': 'keypointlabels', 'value': {'x': 80, 'y': 70}},
        {'type': 'choices', 'value': {'choices': ['unknown']}},
        {'type': 'keypointregion', 'value': {'x': 20, 'y': 30}},
    ]
    points = ordered_points(results)
    assert points == [[819.2, 358.4], [204.8, 153.6]]
    require_same_points(points, points)
    with pytest.raises(ValueError, match='coordinate/order'):
        require_same_points(points, list(reversed(points)))
    with pytest.raises(ValueError, match='keypoint'):
        ordered_points([{'type': 'keypointlabels', 'value': {'x': 20}}])


def test_raw_identity_retains_versions_and_rejects_duplicate_export_identity():
    task = {'id': 10, 'annotations': [
        {'id': 21, 'task': 10, 'completed_by': {'id': 7}},
        {'id': 22, 'task': 10, 'completed_by': 7},
    ]}
    result = source_annotation_index([task])
    assert set(result) == {('10', '7', '21'), ('10', '7', '22')}
    with pytest.raises(ValueError, match='duplicate raw'):
        source_annotation_index([task, task])


def test_explicit_uncomputable_partition_is_not_missing_members_or_consensus():
    partitions = {'p': {'member_count': '0', 'cluster_count': '0', 'partition_status': 'not_evaluable'}}
    require_partition_coverage(partitions, {})
    partitions['p']['member_count'] = '23'
    with pytest.raises(ValueError, match='Missing partition members'):
        require_partition_coverage(partitions, {})
