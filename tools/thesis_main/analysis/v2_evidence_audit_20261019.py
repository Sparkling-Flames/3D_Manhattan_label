"""逐份回接v2证据；冻结坐标、参考、资格与评分保持不变。"""
import csv
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import Polygon

from .b8l2_calculation_status_20261016 import inspect_geometry
from .scope_quality_scoring_20261016 import scoring_engine

ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / 'research/data/releases/v2/analysis_input'
QUALITY = ROOT / 'research/quality/quality_workers_v2_20261019'
OLD = ROOT / 'research/workers/worker_v1_pro_integration_20261017'
OUT = ROOT / 'research/statistics/v2_evidence_audit_20261019'
ENGINE = ROOT / 'research/statistics/b8l2_shared_v6_20261016/inputs'
PRO_GEOMETRY = ROOT / 'inputs/local_reviews/personnel_quality_pro_20261017/study/reliability/initialization_geometry_574.json'
SOURCES = {}


def read(path):
    path = Path(path)
    SOURCES[path.relative_to(ROOT).as_posix()] = dict(bytes=path.stat().st_size)
    if path.suffix == '.gz':
        with gzip.open(path, 'rt', encoding='utf-8-sig') as stream:
            if path.name.endswith('.csv.gz'):
                return list(csv.DictReader(stream))
            return json.load(stream)
    if path.suffix == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))
    return json.loads(path.read_text(encoding='utf-8-sig'))


def index(rows, key='object_id'):
    result = {r[key]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError('duplicate evidence identity: ' + key)
    return result


def number(value):
    if value in ('', None):
        return None
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('nonfinite numeric evidence')
    return value


def truth(value):
    return value is True or value == 'True'


def same_points(a, b):
    return (a is not None and b is not None and len(a) == len(b)
            and all(len(p) == len(q) == 2 and max(abs(x-y) for x, y in zip(p, q)) <= 1e-6
                    for p, q in zip(a, b)))


def scope_evidence(obj, old):
    """图片OOS事实不授予人员裁定机会；只继承语义相容的明确历史裁定。"""
    response = obj.get('worker_scope_response')
    if response is None:
        response = old.get('worker_scope')
    if isinstance(response, list):
        response = response[0] if len(response) == 1 else None
    response = response if response in ('in_scope', 'out_of_scope') else None
    compatible = (truth(old.get('historical_gold_current_clear_compatible'))
                  and truth(old.get('raw_binding_verified'))
                  and old.get('historical_task_gold') == 'in_scope'
                  and obj.get('scene_oos_status') == 'not_oos'
                  and obj.get('scene_doorway_status') in ('none', 'not_recorded')
                  and obj.get('scene_category') in ('ordinary', 'clear'))
    return dict(response=response, response_recorded=response is not None,
        response_source=('user_processed_batch' if obj['object_id'].startswith('v2:new:') else 'v1_raw_binding_audit'),
        judgement_opportunity=compatible and response is not None,
        compatible_gold='in_scope' if compatible else None,
        correct=(response == 'in_scope') if compatible and response is not None else None,
        judgement_missing_reason=None if compatible else 'no_independently_bound_semantically_compatible_task_gold',
        image_oos_is_person_gold=False, historical_evidence=old or None)


def attribution(obj, quality, old, candidate):
    """保留相交原因；不把整体用途限制转成个人失误。"""
    review = obj.get('review_evidence', {})
    blockers = quality.get('quality_exclusion_reasons', [])
    personal_legacy = truth(old.get('legacy_explicit_person_error_exclusion'))
    personal_candidate = truth(candidate.get('pro_candidate_specific_reason'))
    context = dict(gt_substantive_error=bool(review.get('gt_substantive_error')),
        gt_detail_omission=bool(review.get('gt_detail_omission')),
        reference_incomplete='reference_not_full' in blockers,
        reference_unbound=not quality.get('chosen_target_id'),
        scene_or_policy_hold=any('hold' in r or 'oos' in r.lower() for r in blockers),
        pool_restriction=any('pool' in r or 'worker' in r for r in blockers),
        geometry_pending=obj.get('geometry', {}).get('status') != 'surface_valid')
    if personal_legacy:
        category = 'legacy_explicit_person_error_evidence'
    elif personal_candidate:
        category = 'specific_person_error_candidate_not_new_severity_gold'
    elif obj['cleaning_disposition'] != 'retained':
        category = 'excluded_attribution_not_independently_established'
    elif not quality['quality_usable']:
        category = 'analysis_purpose_or_context_restriction'
    else:
        category = 'no_adopted_person_error_evidence_not_proof_error_free'
    return dict(category=category, legacy_explicit_person_error=personal_legacy,
        historical_worker_exclusion=truth(old.get('historical_worker_exclusion')),
        specific_person_error_candidate=personal_candidate,
        broad_reviewer_nonacceptance=truth(candidate.get('pro_candidate_broad_nonacceptance')),
        independently_confirmed_severe_error=None, severity_status='not_independently_adjudicated_here',
        attribution_pending=truth(candidate.get('exclusion_attribution_pending')),
        context_factors=context, candidate_evidence=candidate or None,
        user_exclusion_reason=obj.get('exclusion_reason') or None,
        quality_blockers=blockers, review_verdict=review.get('verdict'))


def time_evidence(obj, quality, prior):
    source = number(quality.get('source_active_time_seconds'))
    if source is not None and source <= 0:
        raise ValueError('nonpositive active time: ' + obj['object_id'])
    new = obj['object_id'].startswith('v2:new:')
    same_target = (prior.get('reference_id') == quality.get('reference_id')
                   and prior.get('reference_version') == quality.get('reference_version'))
    target = number(prior.get('target_matched_time_seconds')) if same_target and quality['pool_analysis_eligible'] else None
    if new:
        target = None
    return dict(source_active_time_seconds=source, target_matched_time_seconds=target,
        source_kind='user_processed_reported_not_raw_log_replayed' if new else 'inherited_v1_audited_source',
        source_status='reported_processed' if new else prior.get('time_status', 'unknown'),
        raw_active_time_seconds=number(prior.get('raw_active_time_seconds')) if not new else None,
        source_file=obj['source']['path'] if new else prior.get('time_source_file'),
        source_binding='user_processed_object_id' if new else prior.get('time_binding'),
        source_rule=None if new else prior.get('time_rule_version'),
        source_missing_reason=None if source is not None else prior.get('time_status', 'no_audited_active_time'),
        target_missing_reason=None if target is not None else
            'new_batch_task_total_without_audited_target_specific_attribution' if new else
            'current_reference_changed' if not same_target else prior.get('target_time_interpretation', 'no_target_matched_time'),
        raw_logs_replayed_here=False, lead_time_used=False,
        collection_active_time=obj.get('collection_active_time'))


def semi_evidence(obj, init, correction, gains, recovered, frozen_proposal, quality=None):
    if obj['condition'] != 'semi':
        return dict(status='not_applicable', exact_initialization_bound=False,
                    confirmed_error_opportunity=False, reported_error_opportunity=False)
    reported = obj.get('semi_reported') or {}
    current_match = same_points(obj.get('points_1024x512'), recovered.get('current_final_points_1024x512'))
    proposal_match = (same_points(recovered.get('initial_points_1024x512'), frozen_proposal.get('initial_points'))
        and same_points(recovered.get('raw_final_points_1024x512'), frozen_proposal.get('final_points'))
        and same_points(obj.get('original_export_points'), frozen_proposal.get('final_points')))
    exact = bool(recovered and proposal_match and truth(init.get('initialization_source_verified')))
    new = obj['object_id'].startswith('v2:new:')
    if recovered and not proposal_match:
        raise ValueError('frozen initialization/final evidence mismatch: ' + obj['object_id'])
    opportunity = exact and truth(correction.get('confirmed_initialization_error_opportunity'))
    reported_opportunity = reported.get('error_specific_outcome') in ('unknown_after_edit', 'known_error_retained_unchanged')
    state = correction.get('error_specific_residual_state') if not new else reported.get('error_specific_outcome')
    edited = (init.get('recovered_edit_status') == 'changed_coordinates') if exact else (
        not reported['initialization_unchanged'] if reported.get('initialization_unchanged') is not None else None)
    alignment = bool(quality and exact and current_match and truth(gains.get('paired_score_available'))
        and gains.get('reference_id') == quality.get('reference_id')
        and gains.get('reference_version') == quality.get('reference_version')
        and all(number(gains.get('final_'+m)) is not None and quality.get('diagnostic_'+m) is not None
                and abs(number(gains['final_'+m])-quality['diagnostic_'+m]) <= 1e-9 for m in ('B8L2','D10')))
    attributable = alignment and truth(gains.get('worker_gain_attributable_under_current_view'))
    return dict(status='frozen_payload_and_proposal_bound' if exact else 'reported_flags_only_missing_initial_geometry',
        exact_initialization_bound=exact, initialization_evidence_level='frozen_proposal_plus_inherited_import_runtime_audit' if exact else 'user_processed_report',
        initialization_points=recovered.get('initial_points_1024x512'),
        raw_final_points=recovered.get('raw_final_points_1024x512'),
        historical_final_equals_current=current_match if recovered else None,
        screen_view_event_verified=False, independent_runtime_replay_here=False,
        current_final_comparable=bool(exact and current_match),
        edited=edited, confirmed_error_opportunity=opportunity,
        reported_error_opportunity=reported_opportunity,
        known_error_unchanged=bool(opportunity and truth(correction.get('known_error_unchanged'))) if exact else None,
        reported_known_error_unchanged=reported.get('known_error_unchanged'),
        error_specific_state=state,
        corrected_confirmed=False if opportunity and truth(correction.get('known_error_unchanged')) else None,
        edited_but_correction_unknown=bool(edited and (opportunity or reported_opportunity)),
        reported_flags=reported or None, initialization_audit=init or None,
        correction_evidence=correction or None,
        historical_paired_scores=gains or None,
        paired_scores_current_adopted=alignment,
        current_qualified_gain_available=bool(alignment and quality['quality_usable']),
        worker_attributable_gain_available=bool(attributable and quality['quality_usable']),
        current_initial_scores={m:number(gains.get('initial_'+m)) for m in ('B8L2','D10','IoU3D100')} if alignment else None,
        current_project_gain={m:number(gains.get('project_current_view_gain_'+m)) for m in ('B8L2','D10','IoU3D100')} if alignment else None,
        current_worker_attributable_gain={m:number(gains.get('worker_attributable_gain_'+m)) for m in ('B8L2','D10','IoU3D100')} if attributable else None,
        paired_score_limit='inherited measurements adopted only for matching current final geometry/reference/version/final scores; researcher repairs separately restrict worker-attributable gain',
        missing_reason=None if exact else 'no_exact_initialization_payload_or_per_submission_deployment_binding_in_received_batch')


def measurement_evidence(obj, quality, binding, reference, cache, engine):
    full = quality['score_status'] == 'complete'
    result = None
    if full:
        if cache is None or cache['result']['score_status'] != 'complete':
            raise ValueError('complete score without measurement evidence: ' + obj['object_id'])
        task = cache['task']
        if (task['annotation_points'] != obj['points_1024x512'] or
            task['reference_points'] != reference['points_1024x512'] or
            task['current_target_id'] != binding['chosen_target_id'] or
            task['reference_version'] != reference['reference_version']):
            raise ValueError('measurement geometry/reference drift: ' + obj['object_id'])
        result = cache['result']
        for metric in ('B8L2', 'D10'):
            if result[metric] != quality['diagnostic_' + metric]:
                raise ValueError('measurement score drift: ' + obj['object_id'])
        inspection = dict(full_input_available=True, floor_input_available=True, reasons=[],
                          input_geometry_status='full_computed_exact_cached_input')
        floor_iou, floor_reason = result['iou_2d'], None
    else:
        inspection = inspect_geometry(obj, engine)
        floor_iou, floor_reason = None, 'annotation_floor_unavailable'
        if inspection['floor_input_available']:
            floor_reason = 'reference_unbound' if reference is None else 'reference_floor_unavailable'
            if reference is not None:
                validation = engine.valid.validate_footprint(reference['floor_xz_h'], role='reference')
                if validation['available']:
                    a, b = Polygon(inspection['floor_xz_h']), Polygon(reference['floor_xz_h'])
                    floor_iou = a.intersection(b).area / a.union(b).area
                    floor_reason = None
    return dict(calculation_class='full' if full else 'floor_only' if floor_iou is not None else 'uncomputable',
        full_score_computed=full, same_reference_measurements=result,
        IoU3D100=result['IoU3D100'] if full else None,
        iou_3d_definition=result['iou_3d_definition'] if full else None,
        diagnostic_floor_iou=floor_iou, floor_missing_reason=floor_reason,
        geometry_inspection=inspection, existing_measurement_reasons=quality['measurement_reasons'],
        full_missing_reason=None if full else 'full_reference_unavailable' if reference and not reference['full_reference_available'] else
            'reference_unbound' if reference is None else 'full_measurement_unavailable_see_geometry_and_existing_reasons',
        floor_diagnostic_grants_quality_eligibility=False)


def write(path, value):
    path = Path(path)
    if path.suffix == '.gz':
        with gzip.open(path, 'wt', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n', encoding='utf-8')


def public_value(value):
    """发布匿名研究证据，删除源账户字段并清理本机绝对路径。"""
    private = {'source_account_id', 'account_id', 'completed_by', 'updated_by', 'username', 'email',
               'worker_name', 'person_name', 'full_name', 'real_name', 'annotator_id', 'reviewer'}
    if isinstance(value, dict):
        return {k: public_value(v) for k, v in value.items() if k not in private}
    if isinstance(value, list):
        return [public_value(v) for v in value]
    if isinstance(value, str):
        value = value.replace(str(ROOT), '.').replace(ROOT.as_posix(), '.')
        if re.match(r'^[A-Za-z]:[/\\]', value) or value.startswith('\\\\'):
            return '[non_repository_absolute_path_redacted]'
    return value


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = read(INPUT/'manifest.json')
    data = read(INPUT/'data.json.gz')
    objects = [o for o in data['objects'] if o['object_kind'] == 'annotation']
    quality = index(read(QUALITY/'quality_inventory.json'))
    bindings = index(read(QUALITY/'reference_bindings.json'))
    references = index(read(QUALITY/'reference_catalog.json'), 'target_id')
    difficulty = index(read(QUALITY/'difficulty_records.json'), 'image_id')
    images = index(data['images'], 'image_id')
    old = {name: index(read(OLD/(name+'.csv'))) for name in
        ('record_evidence', 'initialization_evidence', 'semi_correction_evidence', 'semi_initialization_scores',
         'scope_evidence', 'exclusion_candidate_evidence')}
    prior = index(read(ROOT/'research/quality/quality_b8l2_d10_20261017/shared_records.csv'))
    recovered = index(read(PRO_GEOMETRY))
    base_manifest = read(ROOT/manifest['base_manifest'])
    with gzip.open(ROOT/manifest['base_manifest'].rsplit('/',1)[0]/base_manifest['entrypoints']['data'], 'rt', encoding='utf-8') as stream:
        base_objects = index([o for o in json.load(stream)['objects'] if o['object_kind'] == 'annotation'])
    for obj in objects:
        if obj['object_id'] in base_objects:
            prior_obj = base_objects[obj['object_id']]
            for key in ('points_1024x512','before_preprocessing_points','preprocessed_points',
                        'repair_evidence','deleted_previous_point_indices','ordered_source_point_indices'):
                if obj.get(key) != prior_obj.get(key):
                    raise ValueError('v1 processed evidence not inherited: '+obj['object_id']+':'+key)
    proposal = {}
    for r in read(ROOT/'analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/proposal_response.csv.gz'):
        proposal[r['canonical_annotation_id']] = dict(initial_points=json.loads(r['initial_points_json']),
            final_points=json.loads(r['final_points_json']))
    comments = read(INPUT/'comments.json.gz')
    by_object, by_image = defaultdict(list), defaultdict(list)
    for c in comments['comments']:
        if c.get('object_id'):
            by_object[c['object_id']].append(c)
        elif c.get('image_id'):
            by_image[c['image_id']].append(c)
    path = QUALITY/'measurements.jsonl'
    SOURCES[path.relative_to(ROOT).as_posix()] = dict(bytes=path.stat().st_size)
    with path.open(encoding='utf-8') as stream:
        cache = {r['task']['object_id']: r for r in map(json.loads, stream)}
    assert len(objects) == len(index(objects)) == 10439
    assert set(index(objects)) == set(quality) == set(bindings)
    rows = []
    with scoring_engine(ENGINE/'measurement_engine.zip', ENGINE/'working_models.py') as (engine, _):
        for obj in objects:
            oid = obj['object_id']; q = quality[oid]; b = bindings[oid]
            ref = references.get(b['chosen_target_id']); d = difficulty[obj['image_id']]
            for evidence in (q, b, *(v[oid] for v in old.values() if oid in v)):
                if any(evidence.get(k) != obj[k] for k in ('worker_id', 'image_id', 'condition')):
                    raise ValueError('identity mismatch: ' + oid)
            oldrow = old['record_evidence'].get(oid, {})
            time = time_evidence(obj, q, prior.get(oid, {}))
            measurements = measurement_evidence(obj, q, b, ref, cache.get(oid), engine)
            scope = scope_evidence(obj, old['scope_evidence'].get(oid, {}))
            semi = semi_evidence(obj, old['initialization_evidence'].get(oid, {}),
                old['semi_correction_evidence'].get(oid, {}), old['semi_initialization_scores'].get(oid, {}),
                recovered.get(oid, {}), proposal.get(oid, {}), q)
            points = obj.get('points_1024x512')
            row = dict(object_id=oid, worker_id=obj['worker_id'], image_id=obj['image_id'],
                image_code=obj['image_code'], building_id=obj['building_id'], room_id=obj.get('room_id'),
                condition=obj['condition'], origin=q['origin'], data_release='v2',
                current_class=q['current_class'], scene=q['scene'], is_oos=q['is_oos'],
                is_doorway=obj.get('scene_doorway_status') not in ('none', 'not_recorded', None),
                cleaning_disposition=obj['cleaning_disposition'], quality_usable=q['quality_usable'],
                quality_use=q['quality_use'], pool_analysis_eligible=q['pool_analysis_eligible'],
                independent_vote_eligible=obj['independent_vote_eligible'],
                quality_exclusion_reasons=q['quality_exclusion_reasons'],
                B8L2=q['B8L2'], D10=q['D10'], diagnostic_B8L2=q['diagnostic_B8L2'], diagnostic_D10=q['diagnostic_D10'],
                source_active_time_seconds=time['source_active_time_seconds'],
                target_matched_time_seconds=time['target_matched_time_seconds'], time_evidence=time,
                reference_id=q['reference_id'], reference_version=q['reference_version'],
                binding_status=b['binding_status'], binding_evidence=b,
                reference_full_available=bool(ref and ref['full_reference_available']),
                reference_evidence=ref,
                raw_original_available=obj.get('original_export_points') is not None,
                original_points=obj.get('original_export_points'),
                received_processed_points=obj.get('before_preprocessing_points'),
                preprocessed_points=obj.get('preprocessed_points'), points_1024x512=points,
                point_count=len(points) if points is not None else None,
                received_point_count=len(obj['before_preprocessing_points']) if obj.get('before_preprocessing_points') is not None else None,
                original_point_count=len(obj['original_export_points']) if obj.get('original_export_points') is not None else None,
                declared_pair_count=len(obj['links_zero_based']) if obj.get('links_zero_based') is not None else None,
                geometry_status=obj['geometry']['status'], order_status=obj.get('order_status'), ring_confirmed=obj.get('ring_confirmed'),
                source_evidence=obj['source'],
                coordinate_evidence=dict(original_kind='embedded_v1_original_export' if obj.get('original_export_points') is not None else 'original_export_not_supplied',
                    received_kind='user_processed_batch' if oid.startswith('v2:new:') else 'v1_effective_processed_input',
                    preprocessing=obj.get('preprocessing'), preprocessing_status=obj['preprocessing_status'],
                    repair_evidence=obj.get('repair_evidence'), deleted_previous_point_indices=obj.get('deleted_previous_point_indices'),
                    original_export_indices=obj.get('original_export_indices'),
                    ordered_source_point_indices=obj.get('ordered_source_point_indices'),
                    ordered_source_pair_indices=obj.get('ordered_source_pair_indices'),
                    links_zero_based=obj.get('links_zero_based'), matterport_links_zero_based=obj.get('matterport_links_zero_based'),
                    order_status=obj.get('order_status'), ring_confirmed=obj.get('ring_confirmed'),
                    order_record=obj.get('order_record'), order_origins=obj.get('order_origins'),
                    provided_boundary_next_pair_indices=obj.get('provided_boundary_next_pair_indices'),
                    geometry=obj.get('geometry'), final_review=obj.get('final_review')),
                measurements=measurements, calculation_class=measurements['calculation_class'],
                IoU3D100=measurements['IoU3D100'], diagnostic_floor_iou=measurements['diagnostic_floor_iou'],
                scope_evidence=scope, semi_evidence=semi,
                exclusion_attribution=attribution(obj, q, oldrow, old['exclusion_candidate_evidence'].get(oid, {})),
                review_evidence=obj.get('review_evidence'),
                comments=by_object.get(oid, []), image_comments=by_image.get(obj['image_id'], []),
                image_evidence=dict(room_spatial_classification=images[obj['image_id']].get('room_spatial_classification'),
                    main_visual_space=images[obj['image_id']].get('main_visual_space'),
                    expected_annotation_extent=images[obj['image_id']].get('expected_annotation_extent'),
                    difficulty_record=d),
                fusion_or_cluster_membership_status='not_recomputed_for_v2_historical_results_not_inherited_as_v2')
            rows.append(row)
    write(OUT/'records.json.gz', public_value(dict(schema='v2_evidence_records_20261019_v1', records=rows)))
    coverage = dict(schema='v2_evidence_coverage_20261019_v1', inventory=len(rows),
        people=len({r['worker_id'] for r in rows}), images=len({r['image_id'] for r in rows}),
        origins=dict(Counter(r['origin'] for r in rows)), calculation=dict(Counter(r['calculation_class'] for r in rows)),
        quality_rows=sum(r['quality_usable'] for r in rows),
        quality_workers=len({r['worker_id'] for r in rows if r['quality_usable']}),
        quality_images=len({r['image_id'] for r in rows if r['quality_usable']}),
        raw_original_available=sum(r['raw_original_available'] for r in rows),
        source_time_available=sum(r['source_active_time_seconds'] is not None for r in rows),
        target_matched_time_available=sum(r['target_matched_time_seconds'] is not None for r in rows),
        source_time_by_kind=dict(Counter(r['time_evidence']['source_kind'] for r in rows if r['source_active_time_seconds'] is not None)),
        binding_status=dict(Counter(r['binding_status'] for r in rows)),
        unresolved_binding=sum(not r['reference_id'] for r in rows),
        v1_processed_objects_inherited_unchanged=len(base_objects),
        semi_inventory=sum(r['condition'] == 'semi' for r in rows),
        semi_exact_initialization_bound=sum(r['semi_evidence']['exact_initialization_bound'] for r in rows),
        semi_confirmed_error_opportunities=sum(r['semi_evidence']['confirmed_error_opportunity'] for r in rows),
        semi_reported_error_opportunities=sum(r['semi_evidence']['reported_error_opportunity'] for r in rows),
        semi_current_paired_scores=sum(r['semi_evidence'].get('paired_scores_current_adopted',False) for r in rows),
        semi_current_qualified_gains=sum(r['semi_evidence'].get('current_qualified_gain_available',False) for r in rows),
        semi_qualified_worker_attributable_gains=sum(r['semi_evidence'].get('worker_attributable_gain_available',False) for r in rows),
        scope_responses=sum(r['scope_evidence']['response_recorded'] for r in rows),
        scope_compatible_judgement_opportunities=sum(r['scope_evidence']['judgement_opportunity'] for r in rows),
        scope_correct=sum(r['scope_evidence']['correct'] is True for r in rows),
        specific_person_error_candidates=sum(r['exclusion_attribution']['specific_person_error_candidate'] for r in rows),
        legacy_explicit_person_error_records=sum(r['exclusion_attribution']['legacy_explicit_person_error'] for r in rows),
        attribution_categories=dict(Counter(r['exclusion_attribution']['category'] for r in rows)),
        independently_severe_error_adjudication_performed=False,
        n1_applied=False, v2_fusion_rerun=False, current_input_revision=manifest['effective_input_revision'])
    assert coverage['quality_rows'] == 7302 and coverage['calculation']['full'] == 9363
    write(OUT/'COVERAGE.json', coverage)
    write(OUT/'INPUTS.json', dict(input_manifest=INPUT.relative_to(ROOT).as_posix()+'/manifest.json', sources=SOURCES,
        coordinate_source='v2 effective data objects, inherited v1 processed revisions, no raw-export reload',
        no_input_writes=True, no_score_redefinition=True, no_simulation_inputs=True))
    write(OUT/'field_contract.json', dict(schema='v2_evidence_records_20261019_v1',
        container='records.json.gz top-level records list; one row per object_id including excluded records',
        identity=['object_id','worker_id','image_id','image_code','building_id','room_id','condition','origin'],
        top_level_fields=list(rows[0]),
        sections=['coordinate_evidence','binding_evidence','reference_evidence','measurements','time_evidence',
                  'scope_evidence','semi_evidence','exclusion_attribution','review_evidence','comments','image_evidence'],
        null_semantics='unknown/unavailable/not applicable with section-specific reason; never numeric zero imputation',
        calculation_class='full = existing exact-input cached full score; floor_only = valid declared bottom and bound reference polygon IoU; otherwise uncomputable',
        quality_usable='copied from current quality inventory; diagnostic calculability grants no eligibility',
        IoU3D100='existing frozen engine mean-height prism with corner-mean heights, scale 0-100; not continuous solid volume IoU',
        raw_original_available='embedded original export coordinates available in effective source; received user-processed points are not original export',
        target_matched_time_seconds='inherited audited target-specific value only when reference ID/version unchanged and pool eligible; new reported source time not automatically target time',
        semi='confirmed opportunities require bound frozen initialization and expert evidence; new report flags separate; editing is not confirmed correction',
        scope='historical per-task gold and semantic compatibility only; image OOS never used alone as gold',
        exclusion='candidate coding and legacy individual-error evidence separate; severity not newly adjudicated; overlapping context reasons retained',
        historical_semi_scores='inherited measures adopted only after current geometry/reference/version/final-score alignment; editing does not prove error-specific correction',
        duplicated_context='reference/image/review details repeat per object for standalone consumption; counts use object_id once'))
    print(json.dumps(coverage, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
