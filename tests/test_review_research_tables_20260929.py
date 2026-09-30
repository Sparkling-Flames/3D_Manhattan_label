from collections import Counter

from tools.thesis_main.analysis.build_review_research_tables_20260929 import build, mentions


def test_research_tables_counts_and_evidence_boundaries():
    d = build()
    a = d['annotations']; s = d['summary']
    assert len(a) == len({r['object_id'] for r in a}) == 3152
    assert s['research_images'] == 259 and s['confirmed_order_objects'] == 1295
    assert s['gt_mark_images'] == dict(gt_substantive_error_mark=6, gt_detail_omission_mark=20)
    assert s['focus_worker_excluded'] == dict(W034=17, W037=29)
    assert s['retained_geometry'] == dict(surface_valid=2921, pairing_unavailable=5, representation_limited=8)
    trap = [r for r in a if r['trap_status']=='confirmed_trap']
    assert Counter(r['model_edit_status'] for r in trap) == dict(unchanged_coordinates=36, changed_coordinates=252)
    assert Counter(r['trap_status'] for r in a if r['model_edit_status']=='unchanged_coordinates') == dict(confirmed_trap=36, confirmed_nontrap=31, unknown=33)
    assert sum(r['explicit_model_influence'] for r in a) == 4
    changed = [r for r in d['cross_tables']['order_changes_by_kind'] if r['dimensions']['change']=='adjacency_changed']
    assert {r['dimensions']['object_kind']:r['n'] for r in changed} == dict(annotation=148, gt_manual_revision=6)
    for table in d['cross_tables'].values():
        for row in table:
            assert row['n'] == len(row['ids']) == len(set(row['ids']))
    assert sum(r['n'] for r in d['cross_tables']['trap_model_outcomes']) == 3152
    assert len(d['pairing_representation_transitions']) == 34
    assert all(not r['point_simplification_applied'] for r in a)
    assert all(r['model_outcome']=='correction_success_not_established' for r in a if r['model_edit_status']=='unchanged_coordinates')
    assert any(r['exclusion_reason_detail']=='unknown_or_nonspecific' for r in d['focus_worker_exclusions'])
    assert d['curve_order_examples'][-1]['image_code'] is None
    # 否定句保留为词面线索，函数不输出原因裁决或自动清洗结果。
    assert mentions(['没有标圆柱'])[0] == dict(topic='cylinder', comment='没有标圆柱', matched_terms=['圆柱'])
