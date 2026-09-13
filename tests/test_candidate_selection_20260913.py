from tools.thesis_main.analysis.summarize_candidate_decisions_20260913 import (
    apply_confirmations, oos_disposition, plan_counts, read, ROOT,
)


def test_upper_endpoint_preserves_history_and_explicit_exceptions():
    reuse = dict(collection='仅复用历史', target_band='未定', note='')
    assert plan_counts(reuse, 24, 0)['planned_manual'] == 24
    new = dict(collection='需要新增标注', target_band='9–15人', note='补到12人')
    assert plan_counts(new, 5, 14)['new_needed'] == 7
    assert plan_counts(new, 24, 0)['planned_manual'] == 24
    new.update(target_band='16–20人', note='')
    result = plan_counts(new, 0, 19)
    assert result['planned_manual'] == 20 and result['new_needed'] == 20
    assert result['current_roster_cap'] == 19 and result['capacity_shortfall'] == 1
    assert result['spare_people_at_target'] == 0


def test_confirmation_preserves_original_and_oos_uses_scoped_evidence():
    original = read(ROOT/'analysis_results/candidate_selection_review_20260913_v1/用户审查原始记录.json')
    confirmations = read(ROOT/'analysis_results/candidate_selection_review_20260913_v2/本轮补充确认.json')
    effective = apply_confirmations(original, confirmations)
    assert next(g for g in original['groups'] if g['group'] == 'G165')['adoption'] == '待定'
    assert next(g for g in effective['groups'] if g['group'] == 'G165')['adoption'] == '建议采用'
    before = next(d for d in original['decisions'] if d['group'] == 'G027' and d['number'] == 11)
    after = next(d for d in effective['decisions'] if d['image_id'] == before['image_id'])
    assert before['selection'] == before['collection'] == '待定'
    assert after['selection'] == '采用' and after['collection'] == '仅复用历史'
    assert [d['note'] for d in original['decisions']] == [d['note'] for d in effective['decisions']]
    spatial = read(ROOT/'analysis_results/spatial_dimensions_review_20260913_v2/空间描述与历轮人工记录.json')
    events = {e['event_id']: e for e in spatial['oos_events']}
    images = {(i['building'], i['number']): i for i in spatial['images']}
    assert oos_disposition(images['pRbA3pwrgk9', 1], events)['disposition'] == '明确OOS排除'
    assert oos_disposition(images['q9vSo1VnCiC', 18], events)['disposition'] == 'OOS待核实'
    assert oos_disposition(images['7y3sRwLe3Va', 9], events)['disposition'] == '保留候选'
    # 提到同组其他图不能扩散OOS结论，G196的42疑似不传给61/82。
    assert oos_disposition(images['uNb9QFRL6hY', 42], events)['disposition'] == 'OOS待核实'
    for number in [61, 82]:
        assert oos_disposition(images['uNb9QFRL6hY', number], events)['disposition'] == '保留候选'
