import csv
import json
from pathlib import Path
import pytest
from tools.thesis_main.analysis.prepare_quality_scope_review_20261010 import FIRST, route, representatives, polygon

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis_results/quality_scope_human_review_20261010'

def test_representatives_are_area_selected_not_score_selected():
    rows=[dict(record_id='B',annotation_area_over_gt='.7',Q='100'),dict(record_id='A',annotation_area_over_gt='.2',Q='0'),dict(record_id='C',annotation_area_over_gt='1.1',Q='50')]
    assert [r['record_id'] for r in representatives(rows)]==['A','B','C']
    for r in rows:r['Q']='-999'
    assert [r['record_id'] for r in representatives(rows)]==['A','B','C']
    assert representatives([])==[]

def test_routes_preserve_controls_and_holds():
    assert all(route(c)=='first_round_3' for c in FIRST)
    assert route('pRbA3pwrgk9-02')=='fixed_gt_glass_or_mixed_control'
    assert route('q9vSo1VnCiC-29')=='existing_hold_no_reactivation'
    assert route('wc2JMjhGNzB-26')=='excess_or_mixed_not_simple_crop'
    assert route('uNb9QFRL6hY-54')=='same_space_depth_control'

def test_published_reconciliation_has_no_human_decisions():
    with (OUT/'candidate_reconciliation_24.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    assert len(rows)==len({r['image_code'] for r in rows})==24
    assert sum(r['old_algorithm_base']=='True' for r in rows)==16
    assert sum(r['visual_extent_candidate']=='True' for r in rows)==13
    assert sum(r['old_algorithm_base']==r['visual_extent_candidate']=='True' for r in rows)==5
    assert [r['image_code'] for r in rows if r['review_queue']=='first_round_3']==FIRST
    assert all(not r[k] for r in rows for k in ['human_range_decision','human_closure_location','human_note'])
    v=json.loads((OUT/'validation.json').read_text())
    assert v['exact_geometry_records_rechecked']==283 and v['geometry_failures']==[]
    assert not any(v[k] for k in ['Q_recomputed','GT_modified','eligibility_modified','human_decisions_applied'])

def test_horizon_invalid_is_not_zero_geometry():
    with pytest.raises(ValueError):polygon([[0,1],[0,256]]*4)
