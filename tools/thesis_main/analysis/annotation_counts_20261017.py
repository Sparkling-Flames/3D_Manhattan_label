"""当前逐图独立标注人数：只执行作答/人员排除，不套图片或至少3人的分析门。"""
import json
from pathlib import Path

import pandas as pd

from ..data_prep.consolidate_research_input import load_current_bundle
from .descriptive_pool_gate_20261015 import build_pool_gate
from .descriptive_statistics_current_20261015 import ROOT, POINTER
from .b8l2_usage_coverage_20261016 import scene_flags
from .current_annotation_context_20261017 import load_scored_context

OUT=ROOT/'research/statistics/annotation_counts_20261017'
QUALITY_CONTEXT=ROOT/'research/quality/quality_b8l2_d10_20261017'


def count_annotations(gates,objects,images):
    annotations={o['object_id']:o for o in objects if o['object_kind']=='annotation'}
    assert len(gates)==len({r['object_id'] for r in gates})
    assert set(annotations)=={r['object_id'] for r in gates}
    image_map={r['image_id']:r for r in images}
    rows=[]
    for gate in gates:
        obj=annotations[gate['object_id']]
        disposition=obj['cleaning_disposition']
        removal=('pending' if disposition=='retained_pending' else
            'user_excluded' if disposition in ('historical_not_accepted','excluded_by_review') or
                any(r.endswith(':excluded') for r in gate['pool_vote_exclusion_reasons']) else 'nonindependent_or_other_hold')
        rows.append(dict(gate,image_code=image_map[gate['image_id']]['image_code'],
            cleaning_disposition=disposition,removal_group='' if gate['pool_vote_eligible'] else removal))
    records=pd.DataFrame(rows)
    output=[]
    for image,cell in records.groupby('image_id',sort=True):
        kept=cell[cell.pool_vote_eligible]
        row=dict(image_id=image,image_code=image_map[image]['image_code'],building_id=image_map[image]['building_id'],
            n_retained_workers=kept.worker_id.nunique(),n_retained_records=len(kept),n_raw_records=len(cell),
            n_removed_records=int((~cell.pool_vote_eligible).sum()),
            n_manual_semi_workers=kept.loc[kept.condition.isin(['manual','semi']),'worker_id'].nunique(),
            retained_worker_ids=sorted(kept.worker_id.unique()))
        for condition in ['manual','semi','oos']:
            row['n_'+condition+'_workers']=kept.loc[kept.condition.eq(condition),'worker_id'].nunique()
        for reason in ['user_excluded','pending','nonindependent_or_other_hold']:
            row['n_'+reason+'_records']=int(cell.removal_group.eq(reason).sum())
        output.append(row)
    images=pd.DataFrame(output).sort_values(['building_id','image_code']).reset_index(drop=True)
    retained=records[records.pool_vote_eligible].copy();removed=records[~records.pool_vote_eligible].copy()
    assert images.n_retained_records.sum()==len(retained)
    assert images.n_removed_records.sum()==len(removed)
    assert len(retained)+len(removed)==len(records)
    distribution=images.groupby('n_retained_workers').size().rename('n_images').reset_index()
    checks=dict(version='annotation_counts_20261017_v1',raw_records=len(records),raw_workers=records.worker_id.nunique(),
        inventory_images=len(images),retained_records=len(retained),retained_workers=retained.worker_id.nunique(),
        images_with_retained_annotations=int(images.n_retained_workers.gt(0).sum()),
        images_with_zero_retained_annotations=int(images.n_retained_workers.eq(0).sum()),
        image_worker_pairs=int(images.n_retained_workers.sum()),removed_records=len(removed),
        removal_groups=removed.removal_group.value_counts().to_dict(),
        retained_records_by_condition=retained.condition.value_counts().to_dict(),
        entirely_excluded_workers=sorted(set(records.worker_id)-set(retained.worker_id)),
        workers_per_image=dict(min=int(images.n_retained_workers.min()),max=int(images.n_retained_workers.max()),
            median=float(images.n_retained_workers.median())),
        min3_filter_applied=False,image_quality_or_reference_filter_applied=False)
    return dict(image_counts=images,removed_annotations=removed,retained_annotations=retained,
        people_count_distribution=distribution),checks


def image_flags(research,difficulty,hold_reasons,review=None,current_review=None):
    error=bool(research['gt_substantive_error_mark'] or difficulty['gt_error_excluded'])
    review=review or {}
    later_issue=bool(review.get('quality_reference_hold') and review['reference_status'] in (
        'user_confirmed_inaccurate_pending_revision','original_and_revised_gt_user_disputed'))
    return dict(current_gt_error=bool(difficulty['gt_error_excluded']),
        historical_gt_substantive_error=bool(research['gt_substantive_error_mark']),gt_error_union=error,
        later_explicit_reference_problem=later_issue,gt_reference_problem=error or later_issue,
        later_reference_status=review.get('reference_status',''),later_reference_source_message=review.get('source_message',''),
        gt_uncertainty=bool(research['gt_uncertainty_explicit_tag']),
        gt_detail_omission=bool(research['gt_detail_omission_mark']),
        current_issue_pending=difficulty['difficulty_analysis_exclusion']=='user_reported_issue_pending' or (current_review or {}).get('status')=='pending',
        applicability_pending=difficulty['difficulty_analysis_exclusion']=='special_applicability_pending',
        image_analysis_hold=bool(hold_reasons))


def add_image_statuses(tables,bundle,difficulty,pools,quality,reference_catalog):
    assert quality.object_id.is_unique
    assert set(quality.object_id)=={o['object_id'] for o in bundle['data']['objects'] if o['object_kind']=='annotation'}
    raw=pd.concat([tables['retained_annotations'],tables['removed_annotations']],ignore_index=True)
    indexed=quality.set_index('object_id').loc[raw.object_id]
    for field in ['image_id','worker_id','condition']:
        assert indexed[field].to_list()==raw[field].to_list(), 'quality context identity drift: '+field
    research={r['image_id']:r for r in bundle['research']['images']}
    difficulty={r['image_id']:r for r in difficulty}
    pool_map={p['image_id']:p for p in pools if p['condition']=='manual'}
    refs={r['image_id']:r for r in reference_catalog if r['current_target']}
    assert len(refs)==sum(r['current_target'] for r in reference_catalog)
    eligible=set(tables['retained_annotations'].object_id)
    metadata=bundle.get('quality_update',bundle.get('quality_review_metadata',{}))
    reviews={r['image_code']:r for r in metadata.get('image_decisions',[])}
    counts=quality[quality.object_id.isin(eligible)].groupby('image_id')
    rows=[]
    for row in tables['image_counts'].to_dict('records'):
        image=row['image_id'];r=research[image];d=difficulty[image];p=pool_map[image];ref=refs[image]
        flags=image_flags(r,d,p['image_exclusion_reasons'],reviews.get(row['image_code']),p.get('current_image_review'))
        scenes=scene_flags(dict(scene=d['scene'],doorway_status=d['doorway_status'],oos_subtype=d['oos_subtype']))
        q=counts.get_group(image) if image in counts.groups else quality.iloc[:0]
        pending_target=int(q.full_score_state.eq('pending_target').sum())
        pending_reference=int(q.full_score_state.eq('pending_reference').sum())
        types=[]
        if flags['gt_error_union']:types.append('明确GT实质问题标记')
        if flags['later_explicit_reference_problem']:types.append('后续明确参考不准确或争议')
        if flags['gt_uncertainty']:types.append('GT不确定标记')
        if flags['gt_detail_omission']:types.append('GT细节遗漏标记')
        rows.append(dict(row,**flags,scene=d['scene'],doorway_status=d['doorway_status'],oos_subtype=d['oos_subtype'],
            oos_quality_diagnostic_only=scenes['is_oos'],difficulty_class=d['current_class'],
            difficulty_exclusion=d['difficulty_analysis_exclusion'],image_hold_reasons=p['image_exclusion_reasons'],
            image_hold_evidence=p['image_hold_evidence'],gt_issue_types=types,
            image_comment=r['image_comment'],gt_evidence=r['gt_evidence'],
            difficulty_question=d['question'],difficulty_evidence=d['evidence'],
            current_target_id=ref['target_id'],reference_full_available=ref['full_reference_available'],
            n_retained_target_pending=pending_target,n_retained_reference_pending=pending_reference,
            n_current_quality_usable=int(q.quality_usable.sum()),
            no_retained_annotations=row['n_retained_workers']==0,
            any_condition_min3=max(row['n_manual_workers'],row['n_semi_workers'],row['n_oos_workers'])>=3))
    states=pd.DataFrame(rows)
    tables['image_counts']=states
    tables['image_statuses']=states.copy()
    tables['pending_excluded_images']=states[states.image_analysis_hold | states.current_issue_pending |
        states.applicability_pending | states.no_retained_annotations | states.n_pending_records.gt(0) |
        states.n_retained_target_pending.gt(0) | states.n_retained_reference_pending.gt(0)].copy()
    tables['gt_problem_images']=states[states.gt_reference_problem | states.gt_uncertainty | states.gt_detail_omission].copy()
    tables['reference_pending_images']=states[~states.reference_full_available | states.n_retained_target_pending.gt(0) |
        states.n_retained_reference_pending.gt(0)].copy()
    return dict(gt_error_marker_images=int(states.gt_error_union.sum()),
        explicit_gt_reference_problem_images=int(states.gt_reference_problem.sum()),
        current_gt_error_images=int(states.current_gt_error.sum()),historical_gt_error_images=int(states.historical_gt_substantive_error.sum()),
        gt_uncertainty_images=int(states.gt_uncertainty.sum()),gt_detail_omission_images=int(states.gt_detail_omission.sum()),
        gt_any_issue_images=len(tables['gt_problem_images']),image_analysis_hold_images=int(states.image_analysis_hold.sum()),
        current_issue_pending_images=int(states.current_issue_pending.sum()),applicability_pending_images=int(states.applicability_pending.sum()),
        incomplete_current_reference_images=int((~states.reference_full_available).sum()),
        retained_target_pending_images=int(states.n_retained_target_pending.gt(0).sum()),
        pending_excluded_or_limited_images=len(tables['pending_excluded_images']))


def main():
    bundle=load_current_bundle()
    context=load_scored_context(bundle)
    pointer=context['difficulty_pointer'];difficulty=context['difficulty_records']
    pools,gates=build_pool_gate(bundle,difficulty)
    tables,checks=count_annotations(gates,bundle['data']['objects'],bundle['data']['images'])
    quality=pd.DataFrame(context['quality_records'])
    references=context['reference_catalog']
    checks.update(add_image_statuses(tables,bundle,difficulty,pools,quality,references))
    checks.update(contract_version=bundle['manifest']['contract_version'],difficulty_context=pointer.get('version',pointer.get('details')),
        batch_admission_version=context['admission_version'],
        source='current contract -> manifest-backed load_current_bundle; no frozen-score population substitution',
        quality_status_context=context['score_context_version'],
        quality_records=int(quality.quality_usable.sum()),primary_metric='B8L2',parallel_metric='D10')
    OUT.mkdir(exist_ok=True)
    (OUT/'SOURCE_MANIFEST.json').write_text(json.dumps(dict(bundle_manifest=bundle['manifest'],
        difficulty_pointer=pointer,quality_context=str(QUALITY_CONTEXT.relative_to(ROOT)),
        batch_admission_version=context['admission_version'],
        quality_context_purpose='only image calculation status; not inventory counting gate'),
        ensure_ascii=False,indent=2),encoding='utf-8')
    for name,frame in tables.items():
        output=frame.copy()
        for col in output:output[col]=output[col].map(lambda x:json.dumps(x,ensure_ascii=False) if isinstance(x,(list,dict)) else x)
        output.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
    (OUT/'tables.json').write_text(json.dumps({k:json.loads(v.to_json(orient='records',force_ascii=False))
        for k,v in tables.items()},ensure_ascii=False,allow_nan=False),encoding='utf-8')
    (OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'FIELD_CONTRACT.json').write_text(json.dumps(dict(version=checks['version'],
        eligibility='existing pool_vote_eligible: retained, independent, no explicit excluded gates; not pool_analysis_eligible',
        worker_count='distinct worker_id per image, across all source conditions; per-condition distinct counts separately',
        oos='source condition oos shown separately; not automatically a normal layout or worker unmarkable choice',
        scope='all annotation-bearing images including zero remaining workers; no min3, geometry, GT/reference or score gate',
        removal_groups='exclusive user_excluded / pending / nonindependent_or_other_hold; detailed reasons may overlap',
        image_status='image analysis holds, GT error/uncertainty/detail, current issue, applicability, reference completeness and target binding are separate axes; partial removed answers do not exclude the image',
        gt_error='gt_error_union=original current/history marker union; gt_reference_problem additionally includes explicit 20261010 inaccurate/disputed reference decisions; neither OOS nor missing reference implies error',
        reference_status='declared current target and matched common B8L2/D10 pre-score binding; no scoring or reassignment',
        tables={k:dict(rows=len(v),columns=list(v.columns)) for k,v in tables.items()}),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
