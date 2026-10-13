"""全量作答用途审计：校准例外不恢复人员资格，包外记录不视为排除。"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
import zipfile

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.data_prep.project_public_research_20260929 import project
from tools.thesis_main.analysis.quality_calibration_cohorts_20261013 import source_cohort, select_evidence

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/quality_data_admission_audit_20261013'
HOLDOUT_MEMBER = 'quality_top_structure_research_20261012/previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010/results/room_holdout_manifest.csv'
SEVERE_MEMBER = 'quality_top_structure_research_20261012/study_severe/results/ledger_115.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def scene_barriers(scene):
    value=scene['scene']
    if value in ('oos','oos_and_doorway','oos_pending','doorway_difficult','doorway_annotatable'):
        return ['special_scene_separate_from_calibration:'+value]
    return []


def decide_use(cohort, personnel_barriers, context_barriers, numeric_barriers, reviewed_severe):
    source_ok = cohort in ('manual_priority', 'semi_nontrap_changed_candidate')
    # Only a reviewed severe calibration receipt can waive record/personnel exclusion.
    waivable = ('excluded_worker:', 'cleaning:', 'formal_gate:excluded', 'not_independent_vote')
    remaining = [r for r in personnel_barriers if not r.startswith(waivable)]
    exception = reviewed_severe and bool(personnel_barriers) and not remaining
    if not source_ok or context_barriers or (personnel_barriers and not exception):
        role = 'held_or_diagnostic'
    elif exception:
        role = 'severe_exception_candidate'
    else:
        role = 'manual_development_candidate' if cohort == 'manual_priority' else 'semi_secondary_candidate'
    ready = role != 'held_or_diagnostic' and not numeric_barriers
    return dict(role=role, personnel_gate_compatible=not personnel_barriers,
                full_q_calibration_ready=ready, severe_exception=exception,
                formal_eligibility_newly_granted=False)


def filter_search(search, allowed, grade_holds=()):
    evidence = select_evidence(search['grades'], search['constraints'], allowed)
    evidence['grades'] = [g for g in evidence['grades'] if g['id'] not in grade_holds and not g.get('scope_confounded_latest', False)]
    return {**search, 'rows': [r for r in search['rows'] if r['id'] in allowed],
            **evidence}


def conditional_development_allowed(gate, reviewed_severe, severe_geometry_ready):
    """旧显式适用子层标志不是条件开发授权；严重例外须逐份有证据。"""
    if 'new_descriptive_development_allowed' in gate:
        return bool(gate['new_descriptive_development_allowed'] and not gate['barriers']
                    and not gate['explicit_exposure_barriers'])
    return bool(gate['old_review_gate_preserved'] and reviewed_severe and severe_geometry_ready
                and gate['metadata']['evidence_layer']=='new_severe_conditional_development')


def audit(package, history_zip):
    bundle = load_current_bundle()
    objects = {o['object_id']: o for o in bundle['data']['objects']}
    annotations = {r['object_id']: r for r in bundle['research']['annotations']}
    images = {r['image_id']: r for r in bundle['data']['images']}
    scene_path=ROOT/'analysis_results/difficulty_scope_preferred_20261011/current_259.csv'
    with scene_path.open(encoding='utf-8-sig',newline='') as f:
        scenes={r['image_id']:r for r in csv.DictReader(f)}
    ids = project(bundle['data'])[1]['records']
    contract = read(ROOT/'docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json')
    excluded_workers = set(contract['data']['existing_worker_exclusions'])
    search = read(package/'calibration/inputs/search_inputs.json')
    frozen = {r['object_id']: r for r in search['rows']}
    frozen_source_path = ROOT/'research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012/inputs/current_formal_loader_data.json'
    existing_rows = {r['id']: r for r in read(frozen_source_path.parent/'calibration_records.json')['rows']}
    previous_objects = {o['object_id']: o for o in read(frozen_source_path)['objects']}
    feedback = read(ROOT/'research/quality_severe_feedback_20261011/feedback_overlay.json')
    severe = {r['object_id']: r for r in feedback['records']}
    latest = read(ROOT/'research/quality_joint_calibration_feedback_20261013/USER_FEEDBACK.json')
    grade_holds = {rid: c['case_id'] for c in latest['case_feedback']
                   if c['scope']=='overall_severity_not_pairwise' and c['judgment']=='borderline'
                   for rid in c['record_ids']}
    with zipfile.ZipFile(history_zip) as archive:
        holdout_bytes = archive.read(HOLDOUT_MEMBER)
        holdout = {r['record_id']: r for r in csv.DictReader(io.StringIO(holdout_bytes.decode('utf-8-sig')))}
        historical_severe = json.loads(archive.read(SEVERE_MEMBER))
    severe_context = {r['object_id']: r for r in historical_severe}
    image_holds = {r['image_id'] for r in historical_severe
                   if 'existing_image_wide_analysis_hold' in r['applicability_barriers']}
    registry = read(ROOT/'research/quality_next_stage_handoff_20261010/reference_exclusion_registry_20261010.json')
    ref_restrictions = {}
    for kind in ('confirmed_reference_exclusions', 'preserved_user_analysis_holds', 'reference_evidence_conflicts_primary_research_quarantine'):
        for r in registry[kind]:
            for v in r['gt_versions']:
                ref_restrictions.setdefault(v['gt_object_id'], []).append(kind+':'+r['classification'])
    routes = {r['object_id']: r for r in read(package/'routing/results/routes.json')['rows']}
    records = []
    for oid, source in annotations.items():
        obj = objects[oid]; rid = ids[oid]; prior = frozen.get(oid); h = holdout[rid]
        if h['image_code'] != source['image_code']:
            raise ValueError('holdout_identity_mismatch:'+rid)
        if prior and (prior['id'] != rid or any(prior[k] != source[k] for k in ('condition','worker_id','image_id'))):
            raise ValueError('search_identity_mismatch:'+rid)
        cohort = source_cohort(source)
        label = severe.get(oid); hist = severe_context.get(oid)
        reviewed_severe = bool(label and label['effective_review_status'] == 'reviewed_severe')
        existing_gate = existing_rows[rid]['gate'] if prior else None
        development_allowed = bool(prior and conditional_development_allowed(
            existing_gate, reviewed_severe, hist is not None and hist['full_Q_calibration_ready']))
        personnel = []
        if source['worker_id'] in excluded_workers: personnel.append('excluded_worker:'+source['worker_id'])
        if source['cleaning_disposition'] != 'retained': personnel.append('cleaning:'+source['cleaning_disposition'])
        if source['worker_quality_gate'] != 'candidate_pending_geometry': personnel.append('formal_gate:'+source['worker_quality_gate'])
        if not source['independent_vote_eligible']: personnel.append('not_independent_vote')
        if obj['borrowed_point_provenance']: personnel.append('borrowed_point_provenance')
        context = scene_barriers(scenes[source['image_id']])
        if h['held_out_of_sample_and_future_calibration'].lower() == 'true': context.append('original_holdout')
        if source['image_id'] in image_holds: context.append('existing_image_wide_analysis_hold')
        if hist: context.extend('severe_screen:'+x for x in hist['applicability_barriers'])
        reference_id = prior['reference_object_id'] if prior else None
        if reference_id: context.extend('reference_excluded:'+x for x in ref_restrictions.get(reference_id, []))
        available_refs = images[source['image_id']]['references']
        if not prior and available_refs and all(ref_restrictions.get(v) for v in available_refs.values()):
            context.append('all_existing_full_reference_versions_restricted')
        if prior and not development_allowed:
            context.append('no_existing_conditional_development_authority')
        numeric = []
        if obj['geometry']['status'] != 'surface_valid': numeric.append(obj['geometry']['status'])
        if not obj['links_zero_based']: numeric.append('pairing_unavailable')
        if not prior:
            numeric.extend(['outside_frozen_metrics', 'fixed_reference_binding_not_audited_in_922'])
        else:
            for target in (oid, reference_id):
                for field in ('before_preprocessing_points','preprocessed_points','points_1024x512','links_zero_based','ordered_source_point_indices'):
                    if objects[target].get(field) != previous_objects[target].get(field):
                        numeric.append('snapshot_drift:'+target+':'+field)
        record = dict(record_id=rid, object_id=oid, image_id=source['image_id'], image_code=source['image_code'],
            current_scene_review={k:scenes[source['image_id']][k] for k in ('scene','oos_subtype','doorway_status','classification_basis')},
            worker_id=source['worker_id'], condition=source['condition'], source_cohort=cohort,
            trap_status=source['trap_status'], model_edit_status=source['model_edit_status'],
            cleaning_disposition=source['cleaning_disposition'], current_personnel_gate=source['worker_quality_gate'],
            source_geometry_status=obj['geometry']['status'], geometry_issues=obj['geometry']['issues'],
            in_pro_922=prior is not None, reference_object_id=reference_id,
            explicit_applicability_subset=prior['applicability_confirmed'] if prior else None,
            existing_conditional_development_allowed=development_allowed,
            existing_development_gate=existing_gate,
            final_reference_acceptance_newly_granted=False,
            scored_input='processed_mean_x_geometry', raw_input_penalty_included=False,
            available_reference_versions={k:dict(object_id=v, restrictions=ref_restrictions.get(v, [])) for k,v in available_refs.items()},
            original_room_group=h['room_group'], original_holdout='original_holdout' in context,
            exposure='included_in_joint_development_package' if prior else 'not_certified_unexposed',
            severe_review=label, severe_historical_full_q_ready=hist['full_Q_calibration_ready'] if hist else None,
            personnel_barriers=personnel, context_barriers=sorted(set(context)), numeric_barriers=sorted(set(numeric)),
            **decide_use(cohort, personnel, context, numeric, reviewed_severe))
        if oid in routes:
            route=routes[oid]
            record['multi_space_diagnostic']={k:route.get(k) for k in ('record_id','status','selected_candidate_id','selected_top_status','selected_full_status','uncertainty')}
        records.append(record)
    if set(holdout) != {r['record_id'] for r in records}: raise ValueError('full_population_mismatch')
    by_id = {r['record_id']:r for r in records}
    primary = {r['record_id'] for r in records if r['role']=='manual_development_candidate' and r['full_q_calibration_ready']}
    secondary = {r['record_id'] for r in records if r['role']=='semi_secondary_candidate' and r['full_q_calibration_ready']}
    exceptions = {r['record_id'] for r in records if r['role']=='severe_exception_candidate' and r['full_q_calibration_ready']}
    graded = []
    for grade in search['grades']:
        row=by_id[grade['id']]
        label_barriers = ['latest_borderline_receipt:'+grade_holds[grade['id']]] if grade['id'] in grade_holds else []
        if grade.get('scope_confounded_latest', False): label_barriers.append('scope_confounded_latest')
        source_barriers = ['source_not_primary:'+row['source_cohort']] if row['source_cohort']!='manual_priority' else []
        graded.append(dict(case_id=grade['case_id'], record_id=grade['id'], source_cohort=row['source_cohort'],
            main_calibration_allowed=grade['id'] in primary and not label_barriers,
            secondary_calibration_allowed=grade['id'] in secondary and not label_barriers,
            label_barriers=label_barriers,
            reasons=source_barriers+row['personnel_barriers']+row['context_barriers']+row['numeric_barriers']+label_barriers,
            original_grade=grade['grade']))
    constraints=[]
    for c in search['constraints']:
        members=[by_id[r] for r in c['record_ids']]
        constraints.append(dict(constraint_id=c['constraint_id'], record_ids=c['record_ids'],
            main_calibration_allowed=set(c['record_ids']) <= primary,
            member_roles=[r['role'] for r in members], member_cohorts=[r['source_cohort'] for r in members]))
    count = lambda rows, field: dict(Counter(r[field] for r in rows))
    summary = dict(all_annotations=len(records), conditions=count(records,'condition'),
        pro_922_conditions=count([r for r in records if r['in_pro_922']],'condition'),
        outside_pro_conditions=count([r for r in records if not r['in_pro_922']],'condition'),
        source_cohorts=count(records,'source_cohort'), roles=count(records,'role'),
        roles_manual=count([r for r in records if r['condition']=='manual'],'role'),
        original_holdout=sum(r['original_holdout'] for r in records),
        main_full_q_ready=len(primary), secondary_full_q_ready=len(secondary), exception_full_q_ready=len(exceptions),
        explicit_applicability_manual_subset=sum(r['record_id'] in primary and r['explicit_applicability_subset'] is True for r in records),
        old24_main_admitted=sum(r['main_calibration_allowed'] for r in graded),
        constraints_main_admitted=sum(r['main_calibration_allowed'] for r in constraints),
        excluded_workers={w:dict(records=len(rr:=[r for r in records if r['worker_id']==w]),
             reviewed_severe=sum(bool(r['severe_review'] and r['severe_review']['effective_review_status']=='reviewed_severe') for r in rr),
             severe_candidates=sum(r['role']=='severe_exception_candidate' for r in rr),
             full_q_ready=sum(r['full_q_calibration_ready'] for r in rr)) for w in sorted(excluded_workers)},
        joint_rows_with_personnel_exclusion=[r['record_id'] for r in records if r['in_pro_922'] and r['current_personnel_gate']=='excluded'])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'original_room_holdout_manifest.csv').write_bytes(holdout_bytes)
    save(OUT/'FULL_ADMISSION.json',dict(schema='quality_full_data_admission_20261013_v3', summary=summary, records=records,
        primary_calibration_ids=sorted(primary), secondary_calibration_ids=sorted(secondary), severe_exception_ids=sorted(exceptions),
        grade_admission=graded, constraint_admission=constraints,
        source_paths=dict(package=str(package), history_zip=str(history_zip), holdout_member=HOLDOUT_MEMBER,
            severe_member=SEVERE_MEMBER, snapshot=str(frozen_source_path), current_scene_review=str(scene_path)),
        policy='新用途审计，不改变原正式gate。ready仅指有既有授权的条件开发数值层，不代表最终适用认证、独立验证或等级已校准。旧applicability=false不是参考错误；原始诊断不合入处理后Q。严重例外不能越过参考、配对或留出限制。'))
    view=filter_search(search, primary, grade_holds)
    view['admission_policy']='manual_primary_after_full_population_audit; weak existing human labels only; no new grade or independent validation'
    save(OUT/'MANUAL_PRIMARY_SEARCH_INPUTS.json', view)
    save(OUT/'SEVERE_EXCEPTIONS.json',dict(records=[r for r in records if r['worker_id'] in excluded_workers or r['role']=='severe_exception_candidate']))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--history-zip', type=Path, required=True)
    args=parser.parse_args()
    audit(args.package, args.history_zip)
