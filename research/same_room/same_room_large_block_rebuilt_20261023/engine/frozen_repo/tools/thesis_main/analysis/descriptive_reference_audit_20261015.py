"""逐图核对当前目标与旧评分输入/参考，不评分、不授予分析资格。"""
import json
import zipfile
from pathlib import Path

import numpy as np

from .difficulty_coarse_closeout_20261014 import floor, same_floor
from .difficulty_target_integration_20261015 import compare_floor

ROOT = Path(__file__).resolve().parents[3]
SCORING_SOURCE = 'research/quality/quality_joint_closeout_review_20261015/pro_closeout_delta.zip'
SCORING_MEMBER = 'source/historical_current_formal_loader_data.json'
DETAILS_SOURCE = 'research/difficulty/difficulty_review_update_20261015/current_259.json'
GEOMETRY_FIELDS = ['points_1024x512', 'ordered_source_point_indices', 'ordered_source_pair_indices']


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def load_scoring_snapshot():
    with zipfile.ZipFile(ROOT / SCORING_SOURCE) as archive:
        return json.loads(archive.read(SCORING_MEMBER))


def scope_sources(bundle):
    """每个已确认目标的独立来源和指针，不以本日四图替代旧33图。"""
    sources = {}
    registry = 'analysis_results/scope_difficulty_audit_20261011/reference_registry_snapshot.json'
    for i, row in enumerate(read_json(registry)['records']):
        sources[row['reference_id']] = dict(
            image_id=row['image_id'], floor=row['floor_xz_h'], source=registry,
            pointer=f'/records/{i}', receipt=json.dumps(row.get('confirmation_provenance', {}), ensure_ascii=False))
    delta = 'research/quality/quality_scope_model_handoff_20261015/TWO_IMAGE_SCOPE_DELTA.json'
    document = read_json(delta)
    for i, row in enumerate(document['records']):
        sources[row['new_floor_candidate_id']] = dict(
            image_id=row['image_id'], floor=row['new_floor_polygon_xz_h'], source=delta,
            pointer=f'/records/{i}', receipt=json.dumps(dict(source_receipt=document['source_receipt'],
                pointer=row['source_receipt_pointer'], confirmed_at=row['confirmed_at']), ensure_ascii=False))
    for i, row in enumerate(bundle.get('floor_scope_update', {}).get('records', [])):
        sources[row['reference_id']] = dict(
            image_id=row['image_id'], floor=row['floor_xz_h'],
            source='analysis_results/research_input_20260929/floor_scope_update_20261015.json',
            pointer=f'/records/{i}', receipt=json.dumps(dict(source_receipt=row['source_receipt'],
                pointer=row['source_pointer'], confirmed_at=row['confirmed_at']), ensure_ascii=False))
    for path in ['research/difficulty/difficulty_user_revision_20261015/user_revised_gt.json',
                 'research/difficulty/difficulty_review_update_20261015/x8F5xyUWy9e-03_user_gt.json']:
        row = read_json(path)
        sources[row['reference_id']] = dict(image_id=row['image_id'], source=path, pointer='',
            receipt=row['source'], floor=floor(row['points_1024x512']).tolist(),
            points=row['points_1024x512'])
    return sources


def geometry_unchanged(current, historical):
    return bool(current and historical and
                all(current.get(field) == historical.get(field) for field in GEOMETRY_FIELDS))


def truth(value):
    return value is True or value == 'True'


def audit_references(bundle, difficulty_records, old_records, *, sources=None, historical=None):
    historical = load_scoring_snapshot() if historical is None else historical
    old_objects = {row['object_id']: row for row in historical['objects']}
    objects = {row['object_id']: row for row in bundle['data']['objects']}
    if len(objects) != len(bundle['data']['objects']):
        raise ValueError('duplicate current object_id')
    sources = scope_sources(bundle) if sources is None else sources
    whole_data_equal = bundle['data'] == historical
    targets, target_by_id, points_by_target = [], {}, {}
    for index, difficulty in enumerate(difficulty_records):
        image_id, target_id = difficulty['image_id'], difficulty['target_version']
        selected = difficulty['selected']
        if selected['target_id'] != target_id or image_id in target_by_id:
            raise ValueError('difficulty target identity mismatch / duplicate image')
        provenance = sources.get(target_id)
        target_object = objects.get(target_id)
        if selected['role'] == 'selected_gt' and target_object:
            source = target_object.get('source', target_id)
            provenance = dict(image_id=target_object['image_id'], floor=floor(target_object['points_1024x512']).tolist(),
                source=source.get('path', target_id) if isinstance(source, dict) else source,
                pointer='', receipt='formal loader reference',
                points=target_object['points_1024x512'])
        verified = bool(provenance and provenance['image_id'] == image_id and
                        same_floor(selected['floor'], provenance['floor']))
        points = provenance.get('points') if verified else None
        pending = truth(difficulty.get('top_boundary_pending'))
        complete = bool(points and not pending)
        points_by_target[target_id] = points if complete else None
        row = dict(image_id=image_id, image=difficulty['image'], current_target_id=target_id,
            current_class=difficulty['current_class'], target_role=selected['role'],
            new_space_target=selected['role'] == 'confirmed_scope',
            full_current_target_geometry_available=complete,
            space_scope_confirmed=truth(difficulty.get('space_scope_confirmed')),
            top_boundary_pending=pending, target_source_verified=verified,
            target_source=provenance['source'] if provenance else '',
            target_source_pointer=provenance['pointer'] if provenance else '',
            target_receipt_provenance=provenance['receipt'] if provenance else '',
            difficulty_details_source=DETAILS_SOURCE, difficulty_details_pointer=f'/records/{index}',
            current_target_floor=json.dumps(selected['floor']),
            reference_status=difficulty.get('reference_status', ''),
            gt_error_excluded=truth(difficulty.get('gt_error_excluded')),
            difficulty_analysis_eligible=truth(difficulty.get('difficulty_analysis_eligible')),
            difficulty_analysis_exclusion=difficulty.get('difficulty_analysis_exclusion', ''),
            target_geometry_status=('complete_explicit_reference' if complete else
                                    'whole_space_scope_top_geometry_pending' if pending else 'target_geometry_unverified'))
        targets.append(row)
        target_by_id[image_id] = row

    bindings = []
    seen = set()
    for old in old_records:
        object_id, image_id, reference_id = old['object_id'], old['image_id'], old.get('reference_id', '')
        if object_id in seen:
            raise ValueError('duplicate old object_id')
        seen.add(object_id)
        target = target_by_id[image_id]
        obj, ref = objects.get(object_id), objects.get(reference_id)
        input_equal = geometry_unchanged(obj, old_objects.get(object_id))
        reference_equal = geometry_unchanged(ref, old_objects.get(reference_id))
        input_available = bool(obj and obj.get('points_1024x512'))
        identity_equal = bool(obj and all(obj.get(key) == old[key] for key in ['image_id', 'worker_id', 'condition']))
        reference_image_equal = bool(ref and ref['image_id'] == image_id)
        selected_floor = json.loads(target['current_target_floor'])
        relation, area = compare_floor(selected_floor, floor(ref['points_1024x512'])) if reference_image_equal else ('reference_missing_or_wrong_image', None)
        points = points_by_target[target['current_target_id']]
        target_coordinates_equal = bool(points and ref and
            np.array_equal(np.asarray(points), np.asarray(ref['points_1024x512'])))
        full_reference = bool(target['target_source_verified'] and target_coordinates_equal and reference_equal and
                              reference_image_equal and relation in ('same_vertices', 'same_footprint'))
        scored = any(old.get(key, '') not in ('', None) and str(old[key]) != 'nan' for key in ['WQ', 'A10', 'B8L2', 'IoU3D100'])
        reasons = []
        if target['gt_error_excluded']: reasons.append('known_gt_error_unresolved')
        if not identity_equal: reasons.append('annotation_identity_mismatch_or_missing')
        if not input_equal: reasons.append('annotation_geometry_changed_or_missing')
        if not input_available: reasons.append('annotation_geometry_unavailable')
        if not reference_equal: reasons.append('scored_reference_geometry_changed_or_missing')
        if not target['target_source_verified']: reasons.append('current_target_source_unverified')
        if target['top_boundary_pending']: reasons.append('top_geometry_pending')
        if relation not in ('same_vertices', 'same_footprint'): reasons.append('target_floor_changed_or_unknown')
        if not target_coordinates_equal: reasons.append('complete_target_coordinates_not_equal_or_unavailable')
        if not scored: reasons.append('no_existing_full_quality_scores')
        reuse = bool(scored and full_reference and input_equal and input_available and identity_equal and not target['gt_error_excluded'])
        status = ('excluded_gt_error' if target['gt_error_excluded'] else 'reusable_same_full_reference' if reuse else
                  'no_existing_full_quality_scores' if not scored else 'requires_reference_resolution_or_rescore')
        # 原用途、角色、hold与人员/场景限制全部保留；几何可复用不表示获准分析。
        bindings.append(dict(old, **{key: value for key, value in target.items() if key not in ('image', 'image_id')},
            current_image=target['image'], historical_use_panel=old.get('use_panel', ''),
            old_reference_id=reference_id, reference_id_equal=reference_id == target['current_target_id'],
            input_geometry_unchanged=input_equal, reference_geometry_unchanged=reference_equal,
            input_geometry_available=input_available,
            annotation_identity_unchanged=identity_equal, target_floor_relation=relation,
            relative_area_difference=area, complete_target_coordinates_equal=target_coordinates_equal,
            full_reference_compatible=full_reference, existing_full_quality_available=scored,
            reuse_full_quality=reuse, quality_audit_status=status, reasons='|'.join(reasons),
            scoring_source=SCORING_SOURCE + ':' + SCORING_MEMBER,
            whole_loader_data_equal_scoring_snapshot=whole_data_equal,
            formal_eligibility_granted_by_this_audit=False))
    return targets, bindings
