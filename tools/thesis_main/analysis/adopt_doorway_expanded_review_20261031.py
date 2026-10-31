"""Record full visual coverage and explicit decisions; unresolved answers retain prior eligibility."""
import copy
import json
import os
from collections import Counter
from pathlib import Path
from tools.thesis_main.analysis.render_doorway_expanded_review_20261031 import BASE, OUT, load
from tools.thesis_main.analysis.supplement_doorway_preparation_20261031 import floor


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def main():
    rows, cases, frozen = load()
    prior = read(BASE/'similarity_review_20261031/EFFECTIVE_SCREENING_LEDGER.json')['records']
    adopted = copy.deepcopy(prior)
    byid = {r['object_id']: r for r in adopted}
    original = {r['object_id']: r for r in read(BASE/'pro_delivery_independent_audit_20261031/CORRECTED_RECORD_LEDGER.json')}
    explicit = {}
    for batch in ['scope_recheck_20261031', 'scope_recheck40_20261031']:
        explicit.update(read(BASE/batch/'ADOPTED_USER_REVIEW.json')['decisions'])
    align = {r['image']: r for r in read(BASE/'curve_preparation_v21/full_review_20261031/ALIGNMENT_DECISIONS.json')}
    decisions = read(OUT/'VISUAL_DECISIONS.json')
    progress = read(OUT/'SCREENING_PROGRESS.json')
    assert progress['contact_review_complete'] and progress['detail_review_complete']
    assert progress['contact_sheets_viewed'] == list(range(44))
    assert progress['detail_sheets_viewed'] == list(range(27))
    assert set(map(int, decisions)) == set(progress['flagged_for_detail'])
    assert len(rows) == len({r['object_id'] for r in rows}) == 524
    assert {r['object_id'] for r in rows} == {r['object_id'] for r in prior if r['eligibility']=='保留'}
    reviews, items = [], []
    for i, r in enumerate(rows):
        oid = r['object_id']; source = original[oid]
        v = decisions.get(str(i), {'decision':'保留', 'reason':'原图联系表初筛：未发现与当前排除实例明确相同的局部碎片或跨侧孤立点问题；不代表几何精度无误。'})
        review = dict(index=i, object_id=oid, image=r['image'], worker=r['worker'], **v,
                      prior_record=copy.deepcopy(byid[oid]),
                      prior_human_scope=source['user_label'] if source['protected_adjudication'] else None,
                      prior_explicit_eligibility=explicit.get(oid),
                      level='detail_original_panorama' if str(i) in decisions else 'contact_original_panorama',
                      evidence=f'sheet_{i//12:02}.jpg', evidence_position=i%12+1,
                      scope_unchanged=True, ring_unchanged=True, individual_quality_not_used=True)
        if str(i) in decisions:
            pos=progress['flagged_for_detail'].index(i)
            review.update(detail_evidence=f'detail_sheet_{pos//4:02}.jpg', detail_position=pos%4+1)
        if v['decision']=='排除':
            byid[oid].update(eligibility='排除', decision_source='agent_expanded_visual_review_20261031',
                             exclusion_reason=v['reason'], prior_screening_record=review['prior_record'])
        if v['decision']=='待人工复核':
            byid[oid]['review_status']='pending_user_review_preserve_prior'
            photo=(BASE/cases[r['image']]['photo']).resolve(); points=frozen[oid]['points']
            assert photo.exists() and len(points)>=6 and len(points)%2==0
            history='此前已有人工空间裁决。' if source['protected_adjudication'] else ''
            if oid in explicit: history+='此前明确保留/排除裁决：'+explicit[oid]['eligibility']+'。'
            items.append(dict(object_id=oid, image=r['image'], worker=r['worker'],
                              previous_scope=r['scope'], first_review=source['first_reviewer_quality'],
                              reason=history+v['reason'], comparison=False,
                              photo=os.path.relpath(photo, OUT).replace('\\','/'), points=points,
                              floor=floor(points), spaces=align[r['image']]['space_polygons']))
        reviews.append(review)
    excluded=[r for r in reviews if r['decision']=='排除']
    holds={r['object_id'] for r in read(BASE/'pro_delivery_independent_audit_20261031/INDEPENDENT_HOLDS_13.json')}
    checks=dict(base=584, baseline_excluded=60, baseline_retained=524, visually_screened=len(reviews),
                detail_reviewed=len(decisions), new_excluded=len(excluded), pending_user=len(items),
                excluded=sum(r['eligibility']=='排除' for r in adopted),
                retained_including_pending=sum(r['eligibility']=='保留' for r in adopted),
                changed_prior_human_scope_records=sum(r['prior_human_scope'] is not None for r in excluded),
                changed_prior_explicit_keep_records=sum(r['prior_explicit_eligibility'] is not None for r in excluded),
                retained_historical_holds=sum(r['object_id'] in holds and r['eligibility']=='保留' for r in adopted),
                new_by_image=dict(Counter(r['image'] for r in excluded)))
    assert checks['new_excluded']==80 and checks['pending_user']==21
    assert checks['excluded']==140 and checks['retained_including_pending']==444
    write('VISUAL_REVIEW_RECORDS.json', reviews)
    write('ADOPTED_EXCLUSIONS.json', dict(authorization='用户授权同类再次排除，并授权复核既有明确保留记录；边界不确定项待用户复核', records=excluded, counts=checks, quality_scores_used=False, aggregate_533_result_known_before_review=True))
    write('EFFECTIVE_SCREENING_LEDGER.json', dict(schema='doorway_expanded_screening_v1', calculation_status='not_recomputed_pending_user21', records=adopted))
    write('PENDING_USER_REVIEW.json', items)
    write('CHECKS.json', checks)
    config=dict(key='doorway-expanded-boundary21-20261031-v1', filename='门洞全量复核_21份边界裁决_20261031.json', inferEligibility=True)
    (OUT/'review-data.js').write_text('const reviewConfig = '+json.dumps(config,ensure_ascii=False)+';\nconst reviewItems = '+json.dumps(items,ensure_ascii=False)+';\n',encoding='utf8')
    print(json.dumps(checks, ensure_ascii=False))


if __name__=='__main__':
    main()
