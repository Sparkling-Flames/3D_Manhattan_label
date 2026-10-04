import copy
import json
from pathlib import Path

import numpy as np
import pytest

from tools.thesis_main.analysis.layout_reliability_20261005.arc_consensus import project
from tools.thesis_main.analysis.local_structure_deletion_20261005 import delete_pair, enumerate_source, select_policies


def bump_record():
    p = np.array([[-2,-2],[2,-2],[2,2],[.2,2],[.2,2.4],[-.2,2.4],[-.2,2],[-2,2]])
    top = project(np.c_[p[:,0],np.ones(8),p[:,1]])
    bottom = project(np.c_[p[:,0],-np.ones(8),p[:,1]])
    return dict(id='bump',worker='w',points=np.stack([top,bottom],axis=1).reshape(-1,2).tolist(),
        ring_confirmed=True,order_status='confirmed',source_pair_indices=list(range(8)),
        source_point_indices=list(range(16)),source_point_labels=[f'p{i}' for i in range(16)])


def test_delete_preserves_confirmed_source_order_and_does_not_confirm_new_ring():
    p = Path(__file__).resolve().parents[1]/'research/layout_reliability_20261005/pro_original/inputs/rPc6DW4iMge-06.json'
    r = next(r for r in json.loads(p.read_text())['records'] if r['id']=='R01518')
    before = copy.deepcopy(r)
    c = delete_pair(r, 0)
    assert r == before
    assert c['points'] == r['points'][2:]
    assert c['source_pair_indices'] == r['source_pair_indices'][1:]
    assert c['ring_confirmed'] is False


def test_concave_deletion_can_expand_and_keeps_all_proposals():
    r = bump_record()
    rows = enumerate_source(r, [r], heading_deg=0.)
    assert len(rows) == 9
    c = next(c for c in rows if c['removed_pair_index']==3)
    assert c['added_area_h2'] > .3
    assert c['lost_area_h2'] < 1e-10
    assert c['floor_path_to_shortcut_max_h'] > 0
    assert c['top_proxy_path_to_shortcut_max_h'] == pytest.approx(c['floor_path_to_shortcut_max_h'])
    assert c['exact_observed_encoding_ids'] == []
    assert not c['candidate']['ring_confirmed']


def test_selection_keeps_ties_and_path_budget_does_not_read_gt():
    r = bump_record();r['target_GT'] = 'invalid deliberately unused'
    rows = enumerate_source(r, [r], heading_deg=0.)
    policies = select_policies(rows, budgets=(0.,.05))
    assert policies['path_budget_0h'] == ['bump:original']
    assert len(policies['direction_then_size']) >= 1
    assert policies['detail_protection']['status'] == 'not_run_missing_local_evidence'
    assert all('target_GT' not in row['candidate'] for row in rows)
    duplicate = dict(rows[0], id='same_geometry_different_hypothesis')
    tied = select_policies(rows+[duplicate], budgets=(0.,))
    assert tied['path_budget_0h'] == ['bump:original','same_geometry_different_hypothesis']


def test_invalid_deletion_remains_in_the_real_candidate_ledger():
    p = Path(__file__).resolve().parents[1]/'research/layout_reliability_20261005/pro_original/inputs/uNb9QFRL6hY-67.json'
    roster = json.loads(p.read_text())['records']
    r = next(r for r in roster if r['id']=='R02928')
    rows = enumerate_source(r,roster,heading_deg=0.)
    bad = next(row for row in rows if row['removed_pair_index']==0)
    assert len(rows) == 7
    assert bad['polygon_valid'] is False
    assert bad['added_area_h2'] is None
    assert len(bad['candidate']['points']) == 10
