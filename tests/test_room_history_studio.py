import json
import pytest
from tools.thesis_main.analysis.build_room_history_studio import partition_view


def test_partition_keeps_singletons_and_rejects_count_mismatch():
    rows = [dict(canonical_annotation_id=i, worker_id=i, calculation_included=True, effective_point_count=n)
            for i, n in [('a', 8), ('b', 8), ('c', 12)]]
    variants = [dict(source=dict(canonical_annotation_id=r['canonical_annotation_id'])) for r in rows]
    saved = dict(partition_status='unique', enumeration_truncated='False',
                 candidate_partitions_json=json.dumps([[['a', 'b'], ['c']]]))
    assert partition_view(rows, variants, saved)['candidates'] == [[[0, 1], [2]]]
    saved['candidate_partitions_json'] = json.dumps([[['a', 'c'], ['b']]])
    with pytest.raises(AssertionError, match='点数不同'):
        partition_view(rows, variants, saved)
    assert partition_view([], variants)['candidates'] == []
