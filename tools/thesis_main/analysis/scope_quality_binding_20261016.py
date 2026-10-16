"""展开所有受影响原作答，沿既有人工空间约束绑定；不评分、不裁剪作答。"""
import copy
import json
from collections import defaultdict
from pathlib import Path

from .descriptive_pool_gate_20261015 import build_pool_gate
from .difficulty_coarse_closeout_20261014 import same_floor

ROOT = Path(__file__).resolve().parents[3]
ROUTING_SOURCE = 'research/quality_pro_joint_archive_20261013/source/routing/inputs/prepared_input.json'
DECISIONS_SOURCE = 'research/quality_calibration_pro_handoff_20261011/USER_DECISIONS.json'


def load_routing_evidence():
    routing = json.loads((ROOT / ROUTING_SOURCE).read_text(encoding='utf-8-sig'))
    decisions = json.loads((ROOT / DECISIONS_SOURCE).read_text(encoding='utf-8-sig'))
    records = {r['record_id']: r for r in routing['records']}
    for decision in decisions['decisions']:
        rid = decision.get('record_id')
        if decision.get('reference_label') and rid in records:
            record = records[rid]
            routing['manual_overrides'][rid] = dict(record_id=rid, object_id=record['object_id'],
                selected_candidate_id=record['image_code'] + ':' + decision['reference_label'],
                source=DECISIONS_SOURCE, source_evidence=decision)
    return routing


def build_affected_records(bundle, difficulty_records, reference_catalog=None, routing_input=None, include_all_images=False,
                           resolve_multiple_spaces=False):
    """返回affected_records/record_targets/source_pools/image_spaces，均list[dict]。

    catalog每target含image_id/target_id/floor_xz_h/is_admitted_space_candidate等字段。
    已登记的人工A/B/C/D空间继承原审核准入；普通GT历史版本不自动新增空间。
    score_input_eligible仅指原作答几何可供评分，包含仅诊断对象，绝非统计准入。
    include_all_images=True展开全部图片；默认保留历史受影响范围，不依赖旧分数覆盖。
    resolve_multiple_spaces只由新版消费者启用历史局部/底面路由，冻结旧版回放保持原行为。
    """
    routing = routing_input if routing_input is not None else load_routing_evidence()
    affected = {r['image_id']: r for r in difficulty_records
                if include_all_images or r['selected']['role'] in ('confirmed_scope', 'user_revised_gt')}
    pools, gates = build_pool_gate(bundle, difficulty_records)
    pools = [r for r in pools if r['image_id'] in affected]
    gate_by_id = {r['object_id']: r for r in gates}
    legacy_images = {r['image_id']: r for r in routing['candidate_images']}
    legacy_records = {r['object_id']: r for r in routing['records']}
    catalog = {(r['image_id'], r['target_id']): r for r in (reference_catalog or [])}
    spaces_by_image, lookup = {}, {}
    for image, current in affected.items():
        current_id = current['target_version']
        spaces = []
        if current['selected']['role'] != 'user_revised_gt':
            for candidate in legacy_images.get(image, {}).get('candidates', []):
                spaces.append(dict(image_id=image, target_id=candidate['reference_object_id'],
                    floor_xz_h=candidate['floor_xz_h'],
                    is_admitted_space_candidate=candidate['admitted_for_routing'],
                    candidate_ids=[candidate['candidate_id']], source=ROUTING_SOURCE))
            for (iid, tid), row in catalog.items():
                if iid == image and row.get('is_admitted_space_candidate'):
                    existing = next((s for s in spaces if s['target_id'] == tid), None)
                    if not existing:
                        spaces.append(dict(image_id=image, target_id=tid, floor_xz_h=row['floor_xz_h'],
                            is_admitted_space_candidate=True, candidate_ids=[], source=row.get('sources', [])))
        matching = next((s for s in spaces if same_floor(s['floor_xz_h'], current['selected']['floor'])), None)
        if matching:
            old_id = matching['target_id']
            matching.update(target_id=current_id, is_admitted_space_candidate=True,
                            same_floor_alias_target_ids=[old_id])
        else:
            spaces.append(dict(image_id=image, target_id=current_id, floor_xz_h=current['selected']['floor'],
                is_admitted_space_candidate=True, candidate_ids=[], source='current_v3_declared_target'))
        # 只合并严格同环几何，不用IoU或质量挑选身份。
        merged = []
        for space in spaces:
            other = next((s for s in merged if same_floor(s['floor_xz_h'], space['floor_xz_h'])), None)
            if other:
                other['candidate_ids'] += space['candidate_ids']
                if space['target_id'] == current_id:
                    other['target_id'] = current_id
                other['is_admitted_space_candidate'] |= space['is_admitted_space_candidate']
            else:
                merged.append(space)
        for space in merged:
            space['current_target'] = space['target_id'] == current_id
            space['catalog_reference_available'] = (image, space['target_id']) in catalog
            space['full_reference_available'] = catalog.get((image, space['target_id']), {}).get('full_reference_available')
            for candidate_id in space['candidate_ids']:
                lookup[image, candidate_id] = space['target_id']
        spaces_by_image[image] = merged

    answers, pairs, prepared_cache = [], [], {}
    for obj in bundle['data']['objects']:
        if obj['object_kind'] != 'annotation' or obj['image_id'] not in affected:
            continue
        image, oid = obj['image_id'], obj['object_id']
        current, spaces = affected[image], spaces_by_image[image]
        old = legacy_records.get(oid)
        rid = old['record_id'] if old else ''
        manual = routing['manual_overrides'].get(rid)
        family = routing['manual_family_directives'].get(rid)
        allowed = {s['target_id'] for s in spaces if s['is_admitted_space_candidate']}
        geometry_equal = bool(old and all(obj.get(k) == old['source_object'].get(k) for k in
            ['image_id', 'worker_id', 'condition', 'points_1024x512', 'ordered_source_pair_indices']))
        chosen, status = '', 'pending_multiple_admitted_spaces'
        local_route = None
        if current['selected']['role'] == 'user_revised_gt':
            chosen, status = current['target_version'], 'fixed_current_gt_revision'
        elif (manual or family) and not geometry_equal:
            status = 'pending_manual_evidence_geometry_changed'
        elif manual:
            target = lookup.get((image, manual['selected_candidate_id']))
            if target in allowed:
                chosen, status = target, 'explicit_manual_target'
            else:
                status = 'pending_manual_target_not_admitted'
        else:
            if family:
                allowed &= {lookup.get((image, c)) for c in family['allowed_candidate_ids']}
                status = 'pending_manual_family_not_unique'
            if len(allowed) == 1:
                chosen, status = next(iter(allowed)), 'sole_admitted_space'
            elif resolve_multiple_spaces and len(allowed) > 1 and obj.get('points_1024x512'):
                from .scope_local_routing_20261017 import route_missing_space
                chosen, local_route = route_missing_space(obj['points_1024x512'], spaces, allowed, prepared_cache)
                status = ('manual_family_then_' if family else '') + (
                    local_route['route_reason'] if chosen else 'pending_local_route_' + local_route['status'])
        geometry = obj.get('geometry', {}).get('status', '')
        row = dict(object_id=oid, image_id=image, image_code=obj['image_code'], worker_id=obj['worker_id'],
            condition=obj['condition'], record_id=rid, current_target_id=current['target_version'],
            chosen_target_id=chosen, chosen_target_is_current=chosen == current['target_version'],
            binding_status=status, allowed_target_ids=sorted(allowed),
            manual_source=copy.deepcopy(manual), manual_family_source=copy.deepcopy(family),
            manual_evidence_geometry_unchanged=geometry_equal,
            local_routing_evidence=local_route,
            annotation_geometry_status=geometry, ring_confirmed=obj.get('ring_confirmed'),
            score_input_eligible=bool(obj.get('points_1024x512')) and geometry == 'surface_valid',
            annotation_modified=False, annotation_cropped=False, quality_used_for_binding=False,
            cleaning_disposition=obj['cleaning_disposition'], independent_vote_eligible=obj['independent_vote_eligible'],
            existing_main_quality_gate=copy.deepcopy(obj['main_quality_gate']),
            existing_worker_quality_gate=obj['worker_quality_gate'],
            person_quality_restriction_clear=(gate_by_id[oid]['pool_vote_eligible'] and
                obj['main_quality_gate']['status'] == 'candidate_pending_geometry' and
                obj['worker_quality_gate'] == 'candidate_pending_geometry'),
            **{k: v for k, v in gate_by_id[oid].items() if k not in ('object_id','image_id','worker_id','condition')})
        row['analysis_binding_eligible'] = bool(chosen) and row['pool_analysis_eligible']
        answers.append(row)
        for space in spaces:
            pairs.append(dict(object_id=oid, image_id=image, worker_id=obj['worker_id'], condition=obj['condition'],
                target_id=space['target_id'], current_target=space['current_target'],
                candidate_ids=space['candidate_ids'], is_admitted_space_candidate=space['is_admitted_space_candidate'],
                selected_by_binding=space['target_id'] == chosen, binding_status=status,
                allowed_by_manual_family=space['target_id'] in allowed,
                pool_analysis_eligible=row['pool_analysis_eligible'], pool_source_workers=row['pool_source_workers'],
                annotation_modified=False, annotation_cropped=False))
    support = defaultdict(set)
    for row in answers:
        if row['chosen_target_id'] and row['pool_vote_eligible']:
            support[row['image_id'], row['condition'], row['chosen_target_id']].add(row['worker_id'])
    image_spaces = []
    for pool in pools:
        for space in spaces_by_image[pool['image_id']]:
            workers = sorted(support[pool['image_id'], pool['condition'], space['target_id']])
            image_spaces.append(dict(space, condition=pool['condition'], n_pool_workers=pool['n_effective_workers'],
                n_space_bound_workers=len(workers), space_bound_worker_ids=workers,
                space_bound_min3=len(workers) >= 3, pool_analysis_eligible=pool['pool_analysis_eligible'],
                pool_exclusion_reasons=pool['pool_exclusion_reasons']))
    return dict(affected_records=answers, record_targets=pairs, source_pools=pools, image_spaces=image_spaces)
