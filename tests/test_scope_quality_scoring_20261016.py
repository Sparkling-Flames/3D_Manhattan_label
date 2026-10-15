from copy import deepcopy
import json
import zipfile

import pandas as pd
import pytest

from tools.thesis_main.analysis.scope_quality_scoring_20261016 import ARCHIVE, ROOT, score_records


def controls():
    with zipfile.ZipFile(ARCHIVE) as archive:
        objects = {r['object_id']: r for r in json.loads(archive.read(
            'source/historical_current_formal_loader_data.json'))['objects']}
        rows = json.loads(archive.read('results/all_scores.json'))['records']
        candidates = {c['candidate_id']: c for im in json.loads(archive.read(
            'source/routing_prepared.json'))['candidate_images'] for c in im['candidates']}
    ordinary = [r for r in rows if r['status'] == 'complete' and not r['candidate_id']][:2]
    routed = next(r for r in rows if r['status'] == 'complete' and r['candidate_id']
                  and candidates[r['candidate_id']]['points_1024x512'] is not None)
    tasks = []
    for row in ordinary + [routed]:
        reference = (candidates[row['candidate_id']]['points_1024x512'] if row['candidate_id']
                     else objects[row['reference_id']]['points_1024x512'])
        tasks.append(dict(object_id=row['object_id'], image_id=row['image_id'], worker_id=row['worker_id'],
            condition=row['condition'], current_target_id=row['reference_id'], reference_version='historical_control',
            annotation_points=objects[row['object_id']]['points_1024x512'], reference_points=reference))
    return tasks, ordinary + [routed]


def test_frozen_controls_reproduce_metrics_scores_and_leave_points_unchanged():
    tasks, expected = controls()
    original = deepcopy(tasks)
    measured = score_records(tasks)
    ab = pd.read_csv(ROOT / 'research/quality_ab_feedback_handoff_20261015/prior_AB/results/SCORES_1145.csv')
    by_id = ab.set_index('record_id')
    for result, old in zip(measured, expected):
        assert result['score_status'] == 'complete'
        for metric in ['iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter']:
            assert result[metric] == pytest.approx(old['metrics'][metric], abs=1e-8)
        assert result['IoU3D100'] == pytest.approx(old['IoU3D100'], abs=1e-8)
        for metric, column in [('WQ', 'Q_WQ'), ('A10', 'Q_A10'), ('B8L2', 'Q_B8L2')]:
            assert result[metric] == pytest.approx(by_id.loc[old['record_id'], column], abs=1e-8)
    assert tasks == original


def test_self_reference_keeps_intrinsic_direction_penalty_and_missing_top_cannot_be_full():
    task = controls()[0][0]
    task['reference_points'] = deepcopy(task['annotation_points'])
    result = score_records([task])[0]
    assert result['score_status'] == 'complete'
    assert result['IoU3D100'] == pytest.approx(100, abs=1e-8)
    assert result['WQ'] == pytest.approx(97.43613176827364, abs=1e-8)
    task['reference_points'] = None
    missing = score_records([task])[0]
    assert missing['score_status'] == 'unavailable'
    assert 'reference_full_points_missing' in missing['reasons']
    assert all(missing[k] is None for k in ['WQ', 'A10', 'B8L2', 'IoU3D100', 'Hmean', 'Hcenter'])
    task['reference_points'] = task['annotation_points']
    task['reference_full_available'] = False
    assert score_records([task])[0]['score_status'] == 'unavailable'
