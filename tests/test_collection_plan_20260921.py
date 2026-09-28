from collections import Counter, defaultdict

from tools.thesis_main.analysis.build_collection_plan_20260921 import allocate
from tools.thesis_main.analysis.extend_collection_plan_20260921 import fit


def test_allocation_respects_exposure_capacity_and_distinct_people():
    images = [dict(image_id='a', code='a', room='r', scene='s', need_now=20),
              dict(image_id='b', code='b', room='r', scene='s', need_now=8)]
    seen = defaultdict(set, a={1, 2, 6, 8, 10}, b={1, 2, 6, 8, 10, 12, 13, 15, 17})
    rows, slots = allocate(images, seen, newcomer_cap=2, old_cap=1)
    assert len(slots) == 25
    assert Counter(r['image_id'] for r in rows) == {'a': 20, 'b': 8}
    assert len({(r['slot'], r['image_id']) for r in rows}) == 28
    assert all(r['worker_id'] is None or r['worker_id'] not in seen[r['image_id']] for r in rows)
    assert max(Counter(r['slot'] for r in rows).values()) <= 2


def test_newcomer_minimum_and_w18_is_existing_not_anonymous():
    images = [dict(image_id=str(i), code=str(i), room='r', scene='s', need=15,
                   phase=1, review_status='test', reason='test') for i in range(70)]
    seen = defaultdict(set, {str(i): {18} for i in range(20)})
    rows, quotas = fit(images, seen, w18_tasks=50, old_tasks=20)
    assert len(quotas) == 25
    assert quotas['W018'] == 50
    assert len([s for s in quotas if s.startswith('新人')]) == 15
    assert all(q >= 50 for s, q in quotas.items() if s.startswith('新人'))
    assert all(r['image_id'] not in {str(i) for i in range(20)} for r in rows if r['worker_id']==18)
    assert len({(r['slot'], r['image_id']) for r in rows}) == len(rows)
    seen['20'].add(18)
    assert fit(images, seen, w18_tasks=50, old_tasks=20) is None  # 仅49张未接触图，不能把已接触图冒充新任务。


def test_w18_existing_sample_credit_removes_new_quota():
    images = [dict(image_id=str(i), code=str(i), room='r', scene='s', need=15,
                   phase=1, review_status='test', reason='test') for i in range(62)]
    rows, quotas = fit(images, defaultdict(set), w18_tasks=0, old_tasks=20)
    assert quotas['W018'] == 0
    assert all(q == 50 for s, q in quotas.items() if s.startswith('新人'))
    assert not any(r['worker_id'] == 18 for r in rows)


def test_latest_workloads():
    images = [dict(image_id=str(i), code=str(i), room='r', scene='s', need=15,
                   phase=1, review_status='test', reason='test') for i in range(70)]
    rows, quotas = fit(images, defaultdict(set))
    assert quotas['W018'] == 20
    assert all(q == 30 for s,q in quotas.items() if s.startswith('W') and s!='W018')
    assert all(q >= 50 for s,q in quotas.items() if s.startswith('新人'))
    assert len(rows) == 1050


def test_v4_semi_and_october_preserve_current_assignments(tmp_path, monkeypatch):
    import json
    from tools.thesis_main.analysis import extend_collection_plan_20260921 as plan
    monkeypatch.setattr(plan, 'OUT', tmp_path)
    plan.main()
    result = json.loads((tmp_path/'统计与安排.json').read_text(encoding='utf-8'))
    prior = plan.read('analysis_results/collection_plan_20260921_v3/统计与安排.json')
    assert {(a['slot'],a['image_id']) for a in result['assignments']} == {
        (a['slot'],a['image_id']) for a in prior['assignments']}
    assert result['baseline_stats']['after_september']['people_images'] == 3529
    assert result['baseline_stats']['after_september']['images'] == 297
    semi = result['semi']
    assert Counter(a['slot'] for a in semi['assignments']) == {f'新人{i:02d}':10 for i in range(1,16)}
    assert len({(a['slot'],a['image_id']) for a in semi['assignments']}) == 150
    assert not ({r['image_id'] for r in semi['images']} &
                {r['image_id'] for r in result['images']+result['october']})
    source = {t['data']['base_task_id']:t for t in plan.read(semi['images'][0]['source_import'])}
    assert all(r['original_predictions']==source[r['image_id']]['predictions'] for r in semi['images'])
    assert Counter(r['source_type'] for r in semi['images']) == {'control_natural':5,'trap_natural':5}
    inventory = {r['image_id']:r for r in plan.read('analysis_results/collection_plan_20260921/统计与安排.json')['images']}
    for row in result['october']:
        allocated = {a['slot'] for a in result['assignments'] if a['image_id']==row['image_id']}
        assert set(row['avoid_september_slots']) == allocated
        assert set(row['avoid_workers']) == set(inventory[row['image_id']]['planning_workers']) | {
            int(s[1:]) for s in allocated if s.startswith('W')}
        assert '新人16' not in row['avoid_september_slots']
    holds = [r for r in result['images'] if r['phase']==3 and r['selection_holds']]
    assert len(holds)==20 and sum(r['need'] for r in holds)==261
    rooms = {r['room']:r for r in result['room_coverage']}
    assert rooms['G090']['covered_views']==6 and rooms['G090']['common_all_covered_views']==0
    assert rooms['G078']['covered_views']==4 and rooms['G078']['common_all_covered_views']==0
