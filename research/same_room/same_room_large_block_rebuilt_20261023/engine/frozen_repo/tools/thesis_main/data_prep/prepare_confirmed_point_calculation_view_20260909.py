"""核对原始版本，应用明确确认的逐份修复；保留原始点与补点来源。"""
import argparse
import csv
import gzip
import json
from collections import Counter
from pathlib import Path

from tools.thesis_main.analysis.audit_building_convergence_20260908 import (
    ordered_points, read_csv, require_same_points, source_annotation_index, truth, unique,
)
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry_for_c1_calculation
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import unit_points

BASE = 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
OUTPUT = 'analysis_results/confirmed_point_calculation_view_20260909_v1'
AUDIT = 'analysis_results/rq1_corrections_20260826/c1_geometry_repair_audit.csv'
RULES = {
    '63001f819a4a6b408ae2': dict(identity='C1|0|67|3239|32|6372', image='wc2JMjhGNzB_c7c84bf01a834489ad11d8450a7dc2bc', count=9, drop=4, candidates=1),
    '9e5409147dcedaf906b7': dict(identity='C1|0|71|3322|2|6140', image='uNb9QFRL6hY_fd8d4da92ec14b668ed3d2986616bd14', count=17, drop=10, candidates=1),
    'ba5291230a2bbae1658b': dict(identity='C1|0|72|3398|13|6247', image='uNb9QFRL6hY_ce88ee8b7ee84fca92c13ab16599d90e', count=9, drop=6, candidates=1),
    '837d51d499c08b0e0765': dict(identity='C1|0|71|3354|2|6147', image='UwV83HsGsw3_0f1385fc03994285ad8253b49516d77b', count=15, drop=None, candidates=4),
}


def apply_view(meta, points):
    """调用者须先核对所选版本的原始坐标；返回独立副本，不配对或排序。"""
    raw = [list(p) for p in points]
    effective = [p[:] for p in raw]
    rule = RULES.get(meta['canonical_annotation_id'])
    status = 'unconfirmed_odd_unchanged' if len(raw) % 2 else 'unchanged'
    dropped = None
    if rule:
        if (meta['annotation_identity'] != rule['identity'] or meta['image_id'] != rule['image']
                or len(raw) != rule['count']):
            raise ValueError('Confirmed identity/count mismatch')
        check = normalize_geometry_for_c1_calculation(raw)
        if (check['orphan_candidate_count'] != rule['candidates']
                or check['dropped_point_index'] != rule['drop']):
            raise ValueError('Confirmed repair no longer reproduces')
        dropped = rule['drop']
        if dropped is None:
            effective = None
            status = 'confirmed_ambiguous_excluded'
        else:
            effective = [p[:] for i, p in enumerate(raw) if i != dropped]
            status = 'confirmed_point_removed'
    reason = 'ambiguous_extra_or_missing_pair' if effective is None else ''
    if effective is not None:
        try:
            unit_points(effective)
        except ValueError as exc:
            reason = str(exc)
    return dict(meta, raw_points_1024x512=raw, effective_points_1024x512=effective,
                raw_point_count=len(raw), effective_point_count=None if effective is None else len(effective),
                processing_status=status, dropped_point_index_zero_based=dropped,
                calculation_included=not bool(reason), exclusion_reason=reason,
                unassisted_manual_included=not bool(reason) and meta['assistance_exposure'] == 'none',
                distance_recompute_required=status == 'confirmed_point_removed',
                confirmation_source='user_explicit_four_record_table_20260909' if rule else '',
                legacy_repair_audit_source=AUDIT if rule else '')


def apply_review(row, decision):
    """只消费精确身份、坐标已核对的用户决定，不自动寻找误点。"""
    raw = row['raw_points_1024x512']
    for key in ('canonical_annotation_id', 'image_id', 'worker_id'):
        if str(row[key]) != str(decision[key]):
            raise ValueError('Review identity mismatch: ' + key)
    if len(raw) != decision.get('raw_count', decision.get('effective_point_count')):
        raise ValueError('Review count mismatch')
    if 'annotation_identity' in decision and row['annotation_identity'] != decision['annotation_identity']:
        raise ValueError('Review identity mismatch')
    index = decision.get('candidate_index_zero_based')
    if index is not None and (not 0 <= index < len(raw) or raw[index] != decision['candidate_point']):
        raise ValueError('Review coordinate mismatch')
    instruction = decision.get('user_decision', {'action': 'exclude_response_temporarily'})
    action = instruction['action']
    effective = [p[:] for p in raw]
    applied = dict(decision, user_decision=dict(instruction, application_status='applied_to_calculation_view'))
    result = dict(row, confirmation_source='user_review_20260909', review_decision=applied)
    if action == 'remove_confirmed_point':
        if index is None:
            raise ValueError('Missing confirmed point index')
        effective.pop(index)
        result.update(processing_status='confirmed_point_removed', dropped_point_index_zero_based=index)
    elif action == 'add_confirmed_point':
        if not instruction['imputed_not_original_worker_response']:
            raise ValueError('Missing imputation provenance')
        added = list(instruction['added_coordinate_1024x512'])
        unit_points([added])
        effective.append(added)
        result.update(processing_status='confirmed_point_added', imputed_point=True,
                      imputation_provenance=instruction)
    elif action == 'exclude_response_temporarily':
        effective = None
        result.update(processing_status='confirmed_response_excluded')
    elif action != 'leave_unchanged':
        raise ValueError('Unknown review action: ' + action)
    reason = 'user_confirmed_individual_exclusion' if effective is None else ''
    if effective is not None:
        unit_points(effective)
    result.update(effective_points_1024x512=effective,
                  effective_point_count=None if effective is None else len(effective),
                  calculation_included=not bool(reason), exclusion_reason=reason,
                  unassisted_manual_included=not bool(reason) and row['assistance_exposure'] == 'none',
                  distance_recompute_required=action in ('remove_confirmed_point', 'add_confirmed_point'))
    return result


def build(root, out, decisions_path=None):
    root, out = Path(root), Path(out)
    annotations = read_csv(root / BASE / 'annotations.csv.gz')
    by_id = unique(annotations, 'canonical_annotation_id')
    versions = [json.loads(line) for line in (root / BASE / 'raw_annotation_versions.jsonl').read_text(encoding='utf-8').splitlines()]
    selected = unique([r for r in versions if truth(r['selected_canonical_version'])], 'canonical_annotation_id')
    if set(by_id) != set(selected) or not set(RULES) <= set(by_id):
        raise ValueError('Canonical/version coverage mismatch')
    legacy = read_csv(root / AUDIT)
    decisions, manifest = {}, None
    if decisions_path is not None:
        manifest = json.loads(Path(decisions_path).read_text(encoding='utf-8'))
        if manifest['remaining_single_candidate_judgments'] or manifest['pending_added_point_positions']:
            raise ValueError('Unresolved review decisions')
        for d in manifest['point_decisions']:
            cid = d['canonical_annotation_id']
            if cid in decisions or cid in RULES:
                raise ValueError('Duplicate or overlapping review decision')
            decisions[cid] = d
        for d in manifest['temporary_exclusions']:
            cid = d['canonical_annotation_id']
            if cid in decisions:
                if decisions[cid]['user_decision']['action'] != 'exclude_response_temporarily':
                    raise ValueError('Conflicting exclusion')
            else:
                decisions[cid] = d
        if not set(decisions) <= set(by_id):
            raise ValueError('Review canonical coverage mismatch')
    exports, rows, audit = {}, [], []
    for cid, a in by_id.items():
        v = selected[cid]
        for key in ('stage', 'block_index', 'project_id', 'runtime_task_id', 'worker_id', 'raw_annotation_id', 'base_task_id', 'raw_condition'):
            if a[key] != v[key]:
                raise ValueError('Selected version identity mismatch: ' + key)
        if a['raw_export_path'] != v['source_path']:
            raise ValueError('Selected source mismatch')
        path = v['source_path']
        if path not in exports:
            exports[path] = source_annotation_index(json.loads((root / path).read_text(encoding='utf-8-sig')))
        _, original = exports[path][(v['runtime_task_id'], v['worker_id'], v['raw_annotation_id'])]
        points = v['points_1024x512']
        require_same_points(ordered_points(original['result']), points)
        meta = {k: a[k] for k in ('canonical_annotation_id', 'annotation_identity', 'image_id', 'building_id', 'context_key', 'stage', 'block_index', 'worker_id', 'raw_condition', 'assistance_exposure')}
        meta.update(raw_annotation_version_id=v['raw_annotation_version_id'], raw_export_path=path,
                    coordinate_width=1024, coordinate_height=512)
        row = apply_view(meta, points)
        row.update(imputed_point=False, imputation_provenance=None, review_decision=None)
        if cid in decisions:
            row = apply_review(row, decisions[cid])
        rows.append(row)
        if cid in RULES:
            match = [r for r in legacy if all(r[old] == a[new] for old, new in (
                ('project_id', 'project_id'), ('runtime_task_id', 'runtime_task_id'), ('worker_id', 'worker_id'),
                ('annotation_id', 'raw_annotation_id'), ('base_task_id', 'image_id'), ('condition', 'raw_condition')))]
            rule = RULES[cid]
            if (len(match) != 1 or int(match[0]['raw_point_count']) != rule['count']
                    or int(match[0]['orphan_candidate_count']) != rule['candidates']
                    or match[0]['dropped_point_index'] != ('' if rule['drop'] is None else str(rule['drop']))
                    or truth(match[0]['repair_applied']) != (rule['drop'] is not None)):
                raise ValueError('Legacy repair evidence mismatch')
            audit.append({k: val for k, val in row.items() if not k.endswith('points_1024x512')})
            audit[-1].update(orphan_candidate_count=rule['candidates'],
                             dropped_coordinate_json=json.dumps(points[rule['drop']]) if rule['drop'] is not None else '')
        elif cid in decisions:
            audit.append({k: val for k, val in row.items() if not k.endswith('points_1024x512')})
    out.mkdir(parents=True, exist_ok=True)
    with gzip.open(out / 'calculation_view.jsonl.gz', 'wt', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    with (out / 'confirmed_processing_audit.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in audit for k in r)))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                         for k, v in r.items()} for r in audit)
    qa = dict(canonical_count=len(rows), lineage_count=len(versions), source_exports_checked=len(exports),
              statuses=dict(Counter(r['processing_status'] for r in rows)),
              calculation_included=sum(r['calculation_included'] for r in rows),
              exclusion_reasons=dict(Counter(r['exclusion_reason'] for r in rows if r['exclusion_reason'])),
              index_base=0, source_point_order_checked=True, full_stability_recomputed=False,
              reviewed_decisions=len(decisions), imputed_responses=sum(r['imputed_point'] for r in rows),
              worker_exclusions_applied=False)
    if manifest is not None:
        (out / 'confirmed_user_decisions.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'verification.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    return rows, audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path)
    parser.add_argument('--decisions', type=Path)
    args = parser.parse_args()
    build(args.root, args.output or args.root / OUTPUT, args.decisions)
