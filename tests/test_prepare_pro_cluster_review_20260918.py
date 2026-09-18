import numpy as np
from tools.thesis_main.analysis.prepare_pro_cluster_review_20260918 import partition


def test_complete_linkage_does_not_turn_a_compatibility_chain_into_one_cluster():
    distance = np.array([[0, .05, .2], [.05, 0, .05], [.2, .05, 0]])
    labels = partition(distance, [8, 8, 8], .1)
    assert len(set(labels)) == 2
    assert labels[0] != labels[2]
    # Equal geometry cannot merge different point counts under the audited method.
    assert len(set(partition([[0, 0], [0, 0]], [8, 10], .1))) == 2


def test_supplement_preserves_old_geometry_and_separates_pending_export():
    import copy, json, pytest
    from pathlib import Path
    from tools.thesis_main.analysis.prepare_pro_cluster_review_20260918 import enrich, export_delta
    root = Path(__file__).resolve().parents[1]
    bundle = json.loads((root / 'analysis_results/pro_cluster_review_20260918/data.json').read_text(encoding='utf-8'))
    original = copy.deepcopy(bundle)
    visual = [dict(image_id=c['image_id'], code=c['code'], observer='test', original_viewed=True,
                   overlay_coverage=[], observations='实际图像观察', limits='非最终裁决',
                   category=['complement'], issues=[]) for c in bundle['cases']]
    old = [dict(id=1, annotations=[dict(id=2, completed_by=2, result=[
        dict(id='point', type='keypointlabels', value=dict(x=10, y=761))])])]
    new = copy.deepcopy(old)
    new[0]['annotations'][0]['result'][0]['value']['y'] = 76.1
    delta = export_delta(old, new)
    assert delta['changes'][0]['changed_point_result_ids'] == ['point']
    assert delta['changes'][0]['kind'] == 'coordinate_correction'
    assert old[0]['annotations'][0]['result'][0]['value']['y'] == 761
    result = enrich(bundle, visual, delta)
    for before, after in zip(original['cases'], result['cases']):
        assert before['responses'] == after['responses']
        assert before['groups'] == after['groups']
        assert before['reviews'] == after['reviews']
        assert after['visual_review']['original_viewed']
    assert result['pending_export_update']['applied_to_geometry'] is False
    with pytest.raises(ValueError, match='39'):
        enrich(original, visual[:-1], delta)
    broken = copy.deepcopy(new)
    broken[0]['annotations'][0]['completed_by'] = 3
    with pytest.raises(ValueError, match='owner'):
        export_delta(old, broken)


def test_user_research_update_keeps_frozen_results_and_verbatim_notes():
    import copy, json, pytest
    from pathlib import Path
    from tools.thesis_main.analysis.prepare_pro_cluster_review_20260918 import incorporate_user_review
    root = Path(__file__).resolve().parents[1]
    bundle = json.loads((root / 'analysis_results/pro_cluster_review_20260918/data.json').read_text(encoding='utf-8'))
    review = json.loads((root / 'analysis_results/human_review_reconciliation_20260918/用户_39图最终裁决_原始.json').read_text(encoding='utf-8-sig'))
    context = json.loads((root / 'analysis_results/pro_cluster_review_20260918/研究对象澄清_用户原话.json').read_text(encoding='utf-8'))
    before = copy.deepcopy(bundle)
    result = incorporate_user_review(bundle, review, context)
    assert result['user_review_original'] == review
    for old, new in zip(before['cases'], result['cases']):
        for key in ('responses', 'groups', 'reviews'):
            assert new[key] == old[key]
        assert new['user_adjudications'] == [r for r in review['decisions'] if r['image_id'] == new['image_id']]
    assert result['pending_export_update'] == before['pending_export_update']
    assert result['research_request']['point_count_policy'] == 'open_to_discussion_for_annotation_partition_not_space_identity'
    assert 'fixed_constraint' not in result['research_request']
    assert result['review_ingestion']['confirmed_repairs_applied'] == 0
    bad = copy.deepcopy(review)
    bad['decisions'][1] = bad['decisions'][0]
    with pytest.raises(ValueError, match='identity'):
        incorporate_user_review(bundle, bad, context)
    bad = copy.deepcopy(review)
    bad['decisions'][0]['condition'] = 'wrong'
    with pytest.raises(ValueError, match='identity'):
        incorporate_user_review(bundle, bad, context)
