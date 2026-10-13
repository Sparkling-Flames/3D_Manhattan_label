"""核对普通manual开发候选的参考覆盖；不赋予新资格或替换GT。"""
from collections import Counter, defaultdict
import json
from pathlib import Path

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/quality_reference_coverage_20261013'
# Keep the five reference-conflicted records in this audit's original denominator.
REFERENCE_HOLD_IDS = {'R01700','R02020','R01081','R00795','R00806'}


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def main():
    admission = read('research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')
    prefix = 'research/quality_pro_joint_archive_20261013/source/'
    search_input = read(prefix+'calibration/inputs/search_inputs.json')
    search = {r['id']: r for r in search_input['rows']}
    old = read('research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012/inputs/calibration_records.json')
    old = {r['id']: r for r in old['rows']}
    prepared = read(prefix+'routing/inputs/prepared_input.json')
    candidates = {r['image_id']: r for r in prepared['candidate_images']}
    routes = {r['record_id']: r for r in read(prefix+'routing/results/routes.json')['rows']}
    data = load_current_bundle()['data']
    images = {r['image_id']: r for r in data['images']}
    objects = {r['object_id']: r for r in data['objects']}
    rows = []
    for r in admission['records']:
        if r['role'] != 'manual_development_candidate' and r['record_id'] not in REFERENCE_HOLD_IDS:
            continue
        image = images[r['image_id']]
        frozen = search.get(r['record_id'])
        refs = []
        for version, ref in r['available_reference_versions'].items():
            obj = objects[ref['object_id']]
            refs.append(dict(version=version, object_id=ref['object_id'], restrictions=ref['restrictions'],
                geometry_status=obj['geometry']['status'], pairing_available=bool(obj['links_zero_based']),
                recorded_reference_gate=obj['worker_quality_gate']))
        reusable = [x for x in refs if not x['restrictions'] and x['geometry_status']=='surface_valid' and x['pairing_available']]
        layer = ('frozen_explicit_applicability' if frozen['applicability_confirmed'] else 'frozen_conditional_applicability') if frozen else 'outside_frozen_metrics'
        gate = old[r['record_id']]['gate'] if frozen else None
        if frozen:
            action = 'reuse_frozen_conditional_scores' if gate['new_descriptive_development_allowed'] and not gate['barriers'] and not gate['explicit_exposure_barriers'] else 'reconcile_historical_gate'
        elif r['source_geometry_status'] != 'surface_valid':
            action = 'annotation_geometry_not_ready'
        elif len(reusable)==1:
            action = 'compute_single_existing_reference_conditionally'
        elif len(reusable)>1:
            action = 'compute_each_existing_reference_separately'
        else:
            action = 'reference_geometry_or_restriction_hold'
        space = candidates.get(r['image_id'])
        route = routes.get(r['record_id'])
        rows.append(dict(record_id=r['record_id'], object_id=r['object_id'], image_id=r['image_id'],
            image_code=r['image_code'], building_id=image['building_id'], room_id=image['room_id'],
            layer=layer, action=action, source_geometry_status=r['source_geometry_status'],
            frozen_reference_object_id=frozen['reference_object_id'] if frozen else None,
            historical_descriptive_gate=gate,
            current_personnel_barriers=r['personnel_barriers'], current_context_barriers=r['context_barriers'],
            existing_references=refs, reusable_reference_ids=[x['object_id'] for x in reusable],
            scope_record=dict(oos_status=image['oos_status'],doorway_status=image['doorway_status'],
                scope_explicit_tag=image['scope_explicit_tag'],scope_existing_ledger=image['scope_existing_ledger'],
                scope_comment_candidate=image['scope_comment_candidate']),
            multispace_candidates=[{k:c.get(k) for k in ('candidate_id','reference_object_id','candidate_kind','admitted_for_routing','full_reference_available','top_status','restriction')}
                for c in space['candidates']] if space else [],
            multispace_route={k:route.get(k) for k in ('status','selected_candidate_id','selected_full_status','selected_top_status','uncertainty')} if route else None,
            new_reference_acceptance=False, newly_authorized_calibration=False))
    def coverage(rr):
        return dict(records=len(rr),images=len({r['image_id'] for r in rr}),buildings=len({r['building_id'] for r in rr}),
            actions=dict(Counter(r['action'] for r in rr)),
            reusable_reference_counts=dict(Counter(len(r['reusable_reference_ids']) for r in rr)),
            multispace_records=sum(bool(r['multispace_candidates']) for r in rr),
            multispace_images=len({r['image_id'] for r in rr if r['multispace_candidates']}),
            oos_statuses=dict(Counter(r['scope_record']['oos_status'] for r in rr)),
            source_geometry_statuses=dict(Counter(r['source_geometry_status'] for r in rr)))
    layers = {k:coverage([r for r in rows if r['layer']==k]) for k in sorted({r['layer'] for r in rows})}
    by_image = defaultdict(list)
    by_building = defaultdict(list)
    for r in rows:
        by_image[r['image_code']].append(r)
        by_building[r['building_id']].append(r)
    def group(rr):
        return dict(coverage(rr),layers=dict(Counter(r['layer'] for r in rr)),record_ids=[r['record_id'] for r in rr])
    # These close the requested population and prevent silent qualification upgrades.
    assert len(rows)==1332 and len({r['record_id'] for r in rows})==1332
    assert {k:v['records'] for k,v in layers.items()}==dict(frozen_explicit_applicability=71,frozen_conditional_applicability=503,outside_frozen_metrics=758)
    assert all(not r['current_personnel_barriers'] for r in rows)
    assert all(not r['current_context_barriers'] for r in rows if r['record_id'] not in REFERENCE_HOLD_IDS)
    assert {r['record_id'] for r in rows if r['action']=='reference_geometry_or_restriction_hold'}==REFERENCE_HOLD_IDS
    assert all(not r['new_reference_acceptance'] and not r['newly_authorized_calibration'] for r in rows)
    current = {r['record_id']:r for r in admission['records']}
    latest_grade_audit = {r['record_id']:r for r in admission['grade_admission']}
    grades = [dict(record_id=g['id'],case_id=g['case_id'],
        applicability_confirmed=search[g['id']]['applicability_confirmed'],
        scope_confounded_latest=g['scope_confounded_latest'],
        historical_descriptive_gate=old[g['id']]['gate'],
        current_source_cohort=current[g['id']]['source_cohort'],current_role=current[g['id']]['role'],
        label_barriers=latest_grade_audit[g['id']]['label_barriers']) for g in search_input['grades']]
    result = dict(schema='quality_reference_coverage_20261013_v1', layers=layers, records=rows, old24=grades,
        images={k:group(rr) for k,rr in sorted(by_image.items())},
        buildings={k:group(rr) for k,rr in sorted(by_building.items())},
        policy='仅盘点条件重评分机会；旧applicability=false不是参考错误。保留逐参考版本结果，不用最大分选择GT，不修改拟合或人员资格。')
    OUT.mkdir(exist_ok=True,parents=True)
    (OUT/'COVERAGE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(layers,ensure_ascii=False))


if __name__=='__main__':
    main()
