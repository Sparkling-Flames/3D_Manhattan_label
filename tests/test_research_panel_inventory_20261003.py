import copy
import json

import pytest

from tools.thesis_main.analysis.research_panel_inventory_20261003 import (
    bind_difficulty, summarize_groups, worker_overlap, build,
)
from tools.thesis_main.analysis.research_round_20260929 import prepare_record


def test_inventory_keeps_missing_failures_and_real_people_separate():
    source = dict(schema='candidate_review_user_decisions_v5', decisions=[
        dict(image_id='a', difficulty='简单'), dict(image_id='b', difficulty='未定'),
        dict(image_id='outside', difficulty='困难')])
    labels = bind_difficulty(source, ['a', 'b', 'c'])
    assert labels == {'a': '简单', 'b': '未定', 'c': '未记录'}
    with pytest.raises(ValueError, match='duplicate_difficulty_image'):
        bind_difficulty(dict(source, decisions=source['decisions'] * 2), ['a'])

    def row(worker, image='a', ready=True, condition='manual', quality=True):
        return dict(id=image+worker+condition, image=image, condition=condition,
                    consensus_gate='main_candidate', worker=worker, independent=True,
                    consensus_candidate=True, quality_candidate=quality, bev_ok=ready)

    rows = [row('P1'), row('P2', ready=False), row('P1', condition='semi'),
            row('P2', condition='semi'), row('P1', image='b'), row('P2', image='b')]
    images = {i: dict(original_bev_ok=True, difficulty=labels[i], building=i, room=i) for i in ['a', 'b']}
    groups = summarize_groups(rows, images)
    a = next(g for g in groups if g['image']=='a' and g['condition']=='manual')
    assert (a['candidate_n'], a['candidate_bev_failed_n'], a['curve_ready']) == (2, 1, False)
    pairs = worker_overlap(rows, images)
    assert next(p for p in pairs if p['condition']=='manual')['common_images'] == 'b'
    assert next(p for p in pairs if p['condition']=='semi')['common_images'] == 'a'
    with pytest.raises(ValueError, match='duplicate_person_in_condition'):
        summarize_groups(rows + [dict(rows[0], id='duplicate')], images)


def test_preprocessed_order_preserves_pairs_and_confirmed_rings():
    record = dict(points=[[8, 2], [8, 9], [1, 2], [1, 9], [4, 2], [4, 9]],
                  source_point_indices=[0, 1, 2, 3, 4, 5], source_pair_indices=[0, 1, 2],
                  ring_confirmed=False)
    before = copy.deepcopy(record)
    prepared = prepare_record(record)
    assert prepared['source_pair_indices'] == [1, 2, 0]
    assert prepared['source_point_indices'] == [2, 3, 4, 5, 0, 1]
    assert record == before
    for special in [dict(record, ring_confirmed=True), dict(record, version='original')]:
        assert prepare_record(special)['points'] == record['points']
    malformed = copy.deepcopy(record); malformed['points'][1][0] = 7
    with pytest.raises(ValueError, match='preprocessed_shared_x_mismatch'):
        prepare_record(malformed)


def test_fixed_inventory_replay_and_output_contract(tmp_path):
    from pathlib import Path
    source = Path(__file__).parents[1]/'analysis_results/research_panel_inventory_20261003/input.json'
    snapshot = json.loads(source.read_text(encoding='utf-8'))
    result = build(snapshot, tmp_path)
    assert (result['images'], result['annotations'], result['candidate_n']) == (259, 3152, 2909)
    assert sum(result['difficulty'].values()) == 259
    assert len(result['candidate_geometry_failures']) == 6
    assert len(result['quality_geometry_failures']) == 1
    panels = json.loads((tmp_path/'next_panels.json').read_text(encoding='utf-8'))
    assert len(panels['a']['images']) == 45
    assert panels['a']['difficulty_counts'] == {'简单': 22, '中等': 13, '困难': 10}
    assert panels['a']['common_workers'] == []
    assert len(panels['b']['blocks']) == 1
    assert panels['b']['blocks'][0]['image_n'] == 10
    assert (tmp_path/'worker_coverage.csv').exists()
    assert json.loads((tmp_path/'field_contract.json').read_text(encoding='utf-8'))['schema'] == 'research_panel_inventory_v1'
