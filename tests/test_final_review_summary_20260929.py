import json
from collections import Counter
from tools.thesis_main.analysis.final_review_summary_20260929 import OUT, ROOT, read, rows, collect_comments
from tools.thesis_main.analysis.receive_order_review_20260928 import validate_return


def test_final_population_and_room_export():
    summary=read(OUT/'summary.json');assert summary['annotations']==3152 and summary['images']==259
    assert sum(summary['annotation_order_states'].values())==3152
    assert summary['annotation_order_states']==dict(confirmed=1265,four_pairs_default_skip=1308,excluded=218,not_triggered=312,user_no_recall=44,pairing_deferred=5)
    assert summary['confirmed_orders']==1295 and summary['manual_gt_confirmed']==30
    assert next(b for b in summary['batches'] if b['batch']=='after_pairing23')['changes']==dict(adjacency_changed=13,unchanged=10)
    objects={o['object_id']:o for o in read(ROOT/'analysis_results/pairing_applied_20260929/preprocessed_source.json')['objects']}
    returned=read(OUT/'received_orders.json');validate_return(returned,objects)
    package=read(OUT/'同房汇集_Matterport.json');entries=[e for r in package['rooms'] for e in r['objects']]
    assert len(entries)==len({e['object_id'] for e in entries})==3441
    for e in entries:
        if e['points_1024x512'] is None:assert e['preprocessing_status']=='unavailable';continue
        o=objects[e['object_id']];assert e['points_1024x512']==[o['preprocessed_points'][j] for i in e['ordered_source_pair_indices'] for j in o['links_zero_based'][i]]
        if e['order_status']=='human_confirmed':assert e['ordered_source_pair_indices']==returned['records'][e['object_id']]['order']
    target=next(e for e in entries if e['object_id']=='new_93_3587_7182_W010')
    assert target['order_status']=='human_confirmed' and set(target['geometry']['unusable_pair_ids'])=={2,3}
    assert target['geometry']['issues']==['wrong_hemisphere']
    assert summary['room_registry_groups']==260 and sum(summary['original_room_classification'].values())==260


def test_classification_separation_and_evidence():
    images=rows('analysis_results/final_review_summary_20260929/逐图分类及覆盖.csv')
    assert len(images)==259
    assert Counter(r['oos_status'] for r in images)['confirmed']==24
    assert sum(r['doorway_status'] in {'difficult','annotatable'} for r in images)==19
    assert sum(r['scope_existing_ledger']=='true' for r in images)==79
    assert sum(r['detail_existing_ledger']=='true' for r in images)==46
    assert all(r['coverage']=='not_exhaustively_reviewed_for_scope_or_detail' for r in images)
    assert next(r for r in images if r['image_code']=='2t7WUuJeko7-07')['doorway_status']=='difficult'
    inventory=rows('analysis_results/final_review_summary_20260929/全量3152份最终台账.csv')
    assert next(r for r in inventory if r['object_id']=='8f2f8f8bfdaec3360646')['cleaning_disposition']=='retained'
    evidence=rows('analysis_results/final_review_summary_20260929/空间与细节_评语候选明细.csv')
    assert any(r['current_cleaning_disposition']=='excluded_by_review' for r in evidence)
    assert len({(r['object_kind'],r['object_id'],r['comment']) for r in evidence})==len(evidence)
    assert all(r['evidence_level']=='comment_candidate_not_new_verdict' for r in evidence)
