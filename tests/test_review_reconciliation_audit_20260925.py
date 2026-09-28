import copy
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.review_reconciliation_audit_20260925 import audit, point_labels, verify_raw


ROOT = Path(__file__).resolve().parents[1]


def test_point_identity_survives_repairs_and_wrong_raw_export_is_rejected():
    raw = [[1., 2.], [1., 4.], [3., 2.], [3., 4.]]
    assert point_labels(raw, raw[:1] + raw[2:], 'confirmed_point_removed', {}, 1) == ['p1', 'p3', 'p4']
    labels = point_labels(raw, raw + [[5., 4.]], 'user_confirmed_add_point',
                          {'donor_id': 'new_94_1_2_W033', 'donor_raw_point_1based': 10})
    assert labels[:4] == ['p1', 'p2', 'p3', 'p4']
    assert '补点' in labels[4] and 'W033' in labels[4] and 'p10' in labels[4]
    with pytest.raises(ValueError, match='unexplained_effective_change'):
        point_labels(raw, [[8., 2.]] + raw[1:], 'unchanged', {})
    task = {'id': 1, 'project': 2, 'data': {'image': 'https://example.test/room.png', 'condition': 'manual'}}
    annotation = {'id': 3, 'completed_by': 4, 'result': [
        {'id': 'original-region', 'type': 'keypointlabels', 'original_width': 1024,
         'original_height': 512, 'image_rotation': 0, 'value': {'x': 10, 'y': 20}}]}
    source = dict(project=2, task=1, annotation=3, worker='W004', image_id='room', condition='manual')
    assert verify_raw(source, [[102.4, 102.4]], task, annotation) == ['original-region']
    wrong = copy.deepcopy(annotation)
    wrong['result'][0]['value']['x'] = 11
    with pytest.raises(ValueError, match='raw_coordinates_mismatch'):
        verify_raw(source, [[102.4, 102.4]], task, wrong)


def test_current_snapshot_full_audit_and_known_unapplied_repair():
    result = audit(ROOT)
    assert result['schema'] == 'review_reconciliation_audit_v1'
    assert result['failures'] == []
    summary = result['summary']
    assert summary['annotations'] == summary['raw_verified'] == 3019
    assert summary['raw_points'] == 31217
    assert summary['applied_repairs'] == 10
    assert summary['pairing_unavailable'] == 41
    assert summary['pairing_failure_reasons'] == {
        'unbalanced_top_bottom': 24, 'ambiguous_horizontal_assignment': 15,
        'empty_role_or_point_on_horizon': 2}
    rows = result['annotations']
    assert rows['9e5409147dcedaf906b7']['effective_point_labels'][10] == 'p12'
    assert rows['8ffe08f072e2b12e']['effective_point_labels'][7] == 'p8'
    assert '补点' in rows['new_94_3635_6925_W031']['effective_point_labels'][-1]
    assert rows['032cd152706166629e82']['repairs'][0]['status'] == 'proposed_not_applied'
    assert rows['f6bfdcf15004e457']['pairing']['reason'] == 'unbalanced_top_bottom'
    for cid in ['2293abd04e66d525f147', '846f35a4fc23776b55a2',
                '1f27c10411477390', '75507c55b020fe0f933f']:
        pairing = rows[cid]['pairing']
        assert pairing['reason'] == 'ambiguous_horizontal_assignment'
        assert len(pairing['candidates']) == 2
        assert all(c['diagnostic_only'] for c in pairing['candidates'])
    json.dumps(result, ensure_ascii=False, allow_nan=False)
