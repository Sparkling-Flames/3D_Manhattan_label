#!/usr/bin/env python3
"""Portable, floor-only diagnostics. Never edits formal inputs or invents a ceiling."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
from collections import Counter, defaultdict
from pathlib import Path

import shapely
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def csvwrite(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                        for k, v in row.items()})


def floor_polygon(floor):
    if not isinstance(floor, list) or len(floor) < 3:
        return None, 'invalid_floor_vertex_count'
    if any(not isinstance(p, (list, tuple)) or len(p) != 2 or
           any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in p)
           for p in floor):
        return None, 'nonfinite_or_invalid_floor_coordinates'
    p = Polygon(floor)
    if not p.is_valid or p.area <= 0:
        return None, 'invalid_polygon'
    if not p.contains(Point(0, 0)):
        return None, 'camera_not_inside'
    return p, 'valid'


def project_floor(points):
    """Same continuous 1024x512 ERP convention as build_scope_review.py, in declared ring order."""
    if not isinstance(points, list) or len(points) < 6 or len(points) % 2:
        return None, 'invalid_pairs'
    if any(not isinstance(p, (list, tuple)) or len(p) != 2 or
           any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in p)
           for p in points):
        return None, 'invalid_pairs'
    if any(not 0 <= x <= 1024 or not 0 <= y <= 512 for x, y in points):
        return None, 'outside_canvas'
    floor = []
    for x, y in points[1::2]:
        u = (x / 1024 - 0.5) * 2 * math.pi
        v = (y / 512 - 0.5) * math.pi
        if not 0 < v < math.pi / 2:
            return None, 'floor_not_below_horizon'
        r = 1 / math.tan(v)
        floor.append([r * math.sin(u), -r * math.cos(u)])
    return floor_polygon(floor)


def area_metrics(a, reference):
    """Denominators are explicit; D = |A triangle R| / |R| is not 1 - IoU."""
    inter = a.intersection(reference).area
    outside = a.difference(reference).area
    missing = reference.difference(a).area
    union = a.union(reference).area
    return {
        'annotation_area_h2': a.area,
        'reference_area_h2': reference.area,
        'intersection_area_h2': inter,
        'union_area_h2': union,
        'annotation_area_over_reference': a.area / reference.area,
        'bev_iou': inter / union,
        'reference_coverage_fraction': inter / reference.area,
        'reference_missing_fraction': missing / reference.area,
        'annotation_outside_fraction': outside / a.area,
        'excess_area_over_reference': outside / reference.area,
        'missing_area_h2': missing,
        'outside_area_h2': outside,
        'symmetric_difference_over_reference': a.symmetric_difference(reference).area / reference.area,
    }


def input_hashes(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(Path(folder).rglob('*'))
            if p.is_file() and p.name != 'input_manifest.json'}


def confirmed_region_source(raw_record, region_id):
    """Region identity is declared by the user/editor, never optimized against a score."""
    matches = [r for r in raw_record['space_regions']['regions'] if r['region_id'] == region_id]
    if len(matches) != 1:
        raise AssertionError(('missing_or_duplicate_raw_region', raw_record['image_code'], region_id))
    return matches[0]


def metrics_delta(current, baseline):
    if current is None or baseline is None:
        return None
    return {k: current[k] - baseline[k] for k in (
        'bev_iou', 'reference_coverage_fraction', 'reference_missing_fraction',
        'annotation_outside_fraction', 'symmetric_difference_over_reference')}


def summary_stats(members, metric_key):
    values = [r[metric_key] for r in members if r[metric_key] is not None]
    keys = ('bev_iou', 'reference_coverage_fraction', 'reference_missing_fraction',
            'annotation_outside_fraction', 'symmetric_difference_over_reference')
    return {'n_valid_records': len(values),
            'record_weighted_means': {k: sum(v[k] for v in values) / len(values) if values else None for k in keys},
            'interpretation': 'record-level diagnostic summary only; not quality Q, worker votes, or independent-person estimates'}


def floor_change_kind(current, baseline, absolute_tolerance_h2=1e-9, relative_tolerance=1e-8):
    """Classify set additions/removals, not signed area change. Values remain unrounded."""
    added = current.difference(baseline).area
    removed = baseline.difference(current).area
    tolerance = absolute_tolerance_h2 + relative_tolerance * max(current.area, baseline.area)
    has_added, has_removed = added > tolerance, removed > tolerance
    kind = ('mixed_addition_and_removal' if has_added and has_removed else
            'expansion_only_within_tolerance' if has_added else
            'shrinkage_only_within_tolerance' if has_removed else 'equivalent_within_tolerance')
    return {'change_kind': kind, 'confirmed_area_h2': current.area, 'editing_gt_area_h2': baseline.area,
            'added_outside_gt_area_h2': added, 'removed_from_gt_area_h2': removed,
            'added_over_editing_gt_area': added / baseline.area,
            'removed_over_editing_gt_area': removed / baseline.area,
            'net_area_change_h2': current.area - baseline.area,
            'confirmed_over_editing_gt_area': current.area / baseline.area,
            'classification_area_tolerance_h2': tolerance,
            'classification_absolute_tolerance_h2': absolute_tolerance_h2,
            'classification_relative_tolerance': relative_tolerance,
            'rounding_clipping_or_geometry_repair_performed': False}


def run(input_dir, out):
    input_dir, out = Path(input_dir), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    overlay = read(input_dir / 'normalized_confirmation_overlay.json')
    formal = read(input_dir / 'current_formal_subset.json')
    raw = read(input_dir / 'raw_scope_return.json')
    prior_overlay = read(input_dir / 'prior_confirmation_overlay.json')
    prior_registry = read(input_dir / 'prior_reference_registry.json')['records']
    prior_record_metrics = read(input_dir / 'prior_record_metrics.json')
    checks = []

    def ck(name, ok, detail=None):
        checks.append({'check': name, 'passed': bool(ok), 'detail': detail})
        if not ok:
            raise AssertionError((name, detail))

    before = input_hashes(input_dir)
    manifest = read(input_dir / 'input_manifest.json')
    ck('input_manifest_schema', manifest['schema'] == 'scope_bev_input_manifest_v2')
    ck('input_manifest_matches_bytes', manifest['files'] == before)
    ck('overlay_schema', overlay['schema'] == 'manual_floor_scope_confirmation_overlay_v1')
    ck('formal_snapshot_schema', formal['schema'] == 'scope_formal_geometry_snapshot_v2')
    ck('raw_receipt_matches_extraction', sha(input_dir / 'raw_scope_return.json') == formal['raw_receipt_sha256'])
    ck('overlay_matches_extraction', sha(input_dir / 'normalized_confirmation_overlay.json') == formal['overlay_sha256'])
    ck('receipt_frozen_source_commit', raw['latest_scope_review_source_commit'] == formal['source_commit'])
    rows = overlay['records']
    ck('unique_image_region_keys', len(rows) == len({(r['image_code'], r['region_id']) for r in rows}))
    raw_map = {r['image_code']: r for r in raw['records']}
    raw_index = {r['image_code']: n for n, r in enumerate(raw['records'])}
    formal_images = {i['image_code']: i for i in formal['images']}
    decision_by_image = defaultdict(list)
    for d in rows:
        decision_by_image[d['image_code']].append(d)
    ck('formal_population_matches_confirmed_images', set(formal_images) == set(decision_by_image))
    ck('at_most_one_declared_primary_per_image', all(sum(d['is_primary'] for d in ds) <= 1 for ds in decision_by_image.values()))
    ck('unconfirmed_receipt_rows_not_promoted', set(formal_images).issubset(raw_map))
    assigned = set(raw['room_review_batch_policy']['assigned_image_codes'])
    ck('no_operation_policy_bounded_to_23_images', len(assigned) == 23)
    ck('policy_did_not_approve_unedited_all_images', set(raw['room_review_batch_policy']['applied_image_codes']).issubset(assigned))
    registry, image_summaries, records, space_records, groups, source_bindings = [], [], [], [], [], []
    floor_changes = []
    refs_by_key, geometry_by_code = {}, {}
    prior_by_code = {r['image_code']: r for r in prior_registry}
    baseline_record_by_id = {r['record_id']: r for r in prior_record_metrics}
    previous = []

    for code, ds in sorted(decision_by_image.items()):
        im, raw_record = formal_images[code], raw_map[code]
        selected, original = im['selected_gt'], im['original_gt']
        G, gs = project_floor(selected['points_1024x512'])
        O, os = project_floor(original['points_1024x512'])
        ck(code + ':baseline_floors_valid', gs == os == 'valid', [gs, os])
        ck(code + ':image_and_selected_reference_bound', im['image_id'] == raw_record['image_id'] and
           selected['object_id'] == raw_record['editing_reference_object_id'])
        ck(code + ':selected_reference_points_unchanged', selected['points_1024x512'] == raw_record['editing_reference_points_1024x512'])
        ck(code + ':historical_original_reference_unchanged', original['object_id'] == raw_record['historical_original_GT_object_id'] and
           original['points_1024x512'] == raw_record['historical_original_GT_points_1024x512'])
        geometry_by_code[code] = (G, O)
        image_refs = []
        for d in sorted(ds, key=lambda r: (not r['is_primary'], r['region_id'])):
            rid = d['region_id']
            region = confirmed_region_source(raw_record, rid)
            key = code + ':' + rid
            ck(key + ':floor_confirmation_only', d['floor_region_confirmed'] is True and d['completed'] is True and
               d['top_boundary_pending'] is True and d['reference_ready'] is False and d['formal_eligibility_changed'] is False)
            ck(key + ':raw_region_is_explicitly_confirmed', region.get('completed') is True and region.get('floor_region_confirmed') is True and region.get('decision') == d['decision'])
            ck(key + ':exact_received_floor', d['polygon'] == region['polygon'] == region['confirmed_version']['polygon'])
            ck(key + ':declared_primary_not_best_reference', d['is_primary'] == (rid == 'primary'))
            ck(key + ':selected_reference_bound', d['reference_object_id'] == selected['object_id'] and d['image_id'] == im['image_id'])
            T, ts = floor_polygon(d['polygon'])
            ck(key + ':confirmed_floor_valid', ts == 'valid', ts)
            existing = d['decision'] == 'full_gt'
            ck(key + ':recognized_decision', d['decision'] in ('allow', 'full_gt'))
            if existing:
                ck(key + ':full_gt_not_new_geometry', G.symmetric_difference(T).area / G.area < 1e-12)
            ref_id = key + ':floor:' + digest(d['polygon'])[:16]
            ref = {'image_code': code, 'image_id': im['image_id'], 'region_id': rid,
                   'region_name': d.get('region_name'), 'is_primary': d['is_primary'], 'is_active': d.get('is_active'),
                   'reference_id': ref_id, 'decision': d['decision'], 'new_floor_geometry': not existing,
                   'role': 'declared_primary_floor' if d['is_primary'] else 'declared_alternative_floor',
                   'selected_gt_object_id': selected['object_id'], 'selected_gt_kind': selected['object_kind'],
                   'original_gt_object_id': original['object_id'], 'original_gt_kind': original['object_kind'],
                   'original_geometry_source_status': original.get('geometry_source_status', 'formal_original_reference'),
                   'selected_differs_from_original': selected['object_id'] != original['object_id'],
                   'floor_xz_h': d['polygon'], 'floor_polygon_sha256': digest(d['polygon']),
                   'area_h2': T.area, 'perimeter_h': T.length, 'camera_inside': True,
                   'camera_distance_to_floor_boundary_h': T.boundary.distance(Point(0, 0)),
                   'confirmed_vs_selected_gt': area_metrics(T, G) if im['in_current_formal_corpus'] else None,
                   'confirmed_vs_original_gt': area_metrics(T, O) if im['in_current_formal_corpus'] else None,
                   'in_current_formal_corpus': im['in_current_formal_corpus'],
                   'n_research_annotations': len(im['annotations']),
                   'reference_only_reason': im['reference_only_reason'],
                   'top_boundary_pending': True, 'reference_ready': False, 'new_top_coordinates': None,
                   'formal_gt_changed': False, 'formal_eligibility_changed': False,
                   'target_assignment_policy': 'user-declared region identity; never chosen by best GT or annotation score',
                   'accepted_set_scoring_protocol': 'not_established_by_this_floor_confirmation',
                   'confirmation_origin': d.get('confirmation_origin'), 'confirmation_provenance': d.get('provenance')}
            registry.append(ref)
            floor_changes.append({'image_code': code, 'region_id': rid, 'is_primary': d['is_primary'],
                                  'decision': d['decision'], 'in_current_formal_corpus': im['in_current_formal_corpus'],
                                  'annotation_records': len(im['annotations']),
                                  'use': 'scope geometry registration only; no annotation score or eligibility' if not im['in_current_formal_corpus'] else 'scope geometry diagnostic',
                                  **floor_change_kind(T, G)})
            image_refs.append(ref)
            refs_by_key[(code, rid)] = (ref, T)
            region_index = next(n for n, r in enumerate(raw_record['space_regions']['regions']) if r['region_id'] == rid)
            source_bindings.append({'image_code': code, 'image_id': im['image_id'], 'region_id': rid, 'reference_id': ref_id,
                                    'receipt_sha256': before['raw_scope_return.json'],
                                    'receipt_json_pointer': '/records/' + str(raw_index[code]) + '/space_regions/regions/' + str(region_index),
                                    'receipt_floor_sha256': digest(region['polygon']),
                                    'formal_source_commit': formal['source_commit'],
                                    'editing_reference_object_id': selected['object_id'],
                                    'editing_reference_points_sha256': digest(selected['points_1024x512']),
                                    'original_reference_object_id': original['object_id'],
                                    'original_reference_points_sha256': digest(original['points_1024x512']),
                                    'original_geometry_source_status': ref['original_geometry_source_status'],
                                    'in_current_formal_corpus': im['in_current_formal_corpus'],
                                    'recovered_reference_provenance': im.get('reference_provenance')})
            if code in prior_by_code and d['is_primary']:
                prior = prior_by_code[code]
                P, ps = floor_polygon(prior['floor_xz_h'])
                ck(key + ':prior_floor_valid', ps == 'valid')
                previous.append({'image_code': code, 'region_id': rid,
                                 'prior_floor_sha256': prior['floor_polygon_sha256'], 'final_floor_sha256': ref['floor_polygon_sha256'],
                                 'exact_vertices_unchanged': prior['floor_xz_h'] == d['polygon'],
                                 'final_vs_previous_floor': area_metrics(T, P),
                                 'prior_confirmation_layer': 'latest_scope_reference_integration_20261010',
                                 'history_policy': 'retain both snapshots; no rewrite of previous package'})
        image_records, current_space_records = [], []
        for a in sorted(im['annotations'], key=lambda a: a['record_id']):
            A, status = project_floor(a['points_1024x512'])
            entry = {k: a[k] for k in ('record_id', 'object_id', 'worker_id', 'condition', 'cleaning_disposition',
                                     'independent_vote_eligible', 'worker_quality_gate', 'main_quality_gate', 'main_consensus_gate',
                                     'ring_confirmed', 'ordered_source_pair_indices', 'formal_object_sha256')}
            entry.update({'image_code': code, 'image_id': im['image_id'], 'geometry_status': status,
                          'population': 'all_formal_annotations_in_confirmed_images_no_new_eligibility',
                          'selected_gt_metrics': area_metrics(A, G) if A is not None else None,
                          'original_gt_metrics': area_metrics(A, O) if A is not None else None,
                          'confirmed_spaces': [], 'primary_space_region_id': None,
                          'metrics_unavailable_reason': None if A is not None else status})
            for d in sorted(ds, key=lambda r: (not r['is_primary'], r['region_id'])):
                ref, T = refs_by_key[(code, d['region_id'])]
                metrics = area_metrics(A, T) if A is not None else None
                space = {'region_id': d['region_id'], 'reference_id': ref['reference_id'], 'is_primary': d['is_primary'],
                         'decision': d['decision'], 'confirmed_floor_metrics': metrics,
                         'delta_confirmed_minus_selected': metrics_delta(metrics, entry['selected_gt_metrics']),
                         'metrics_unavailable_reason': entry['metrics_unavailable_reason']}
                entry['confirmed_spaces'].append(space)
                if d['is_primary']:
                    entry['primary_space_region_id'] = d['region_id']
                sr = {k: v for k, v in entry.items() if k not in ('confirmed_spaces', 'primary_space_region_id')}
                sr.update(space)
                space_records.append(sr)
                current_space_records.append(sr)
                if metrics is not None:
                    ck(a['record_id'] + ':' + d['region_id'] + ':area_identities',
                       abs(metrics['reference_coverage_fraction'] + metrics['reference_missing_fraction'] - 1) < 1e-10 and
                       abs(metrics['symmetric_difference_over_reference'] - metrics['reference_missing_fraction'] - metrics['excess_area_over_reference']) < 1e-10 and
                       -1e-12 <= metrics['bev_iou'] <= 1 + 1e-12)
                    if d['decision'] == 'full_gt':
                        ck(a['record_id'] + ':' + d['region_id'] + ':full_gt_unchanged',
                           max(abs(v) for v in space['delta_confirmed_minus_selected'].values()) < 1e-11)
                if code in prior_by_code and d['is_primary']:
                    old = baseline_record_by_id[a['record_id']]
                    ck(a['record_id'] + ':previous_16_image_metrics_exact',
                       metrics == old['confirmed_floor_metrics'] and entry['selected_gt_metrics'] == old['selected_gt_metrics'] and
                       entry['original_gt_metrics'] == old['original_gt_metrics'])
            records.append(entry)
            image_records.append(entry)
        grouped = defaultdict(list)
        for sr in current_space_records:
            grouped[(sr['region_id'], sr['condition'], sr['main_quality_gate']['status'], sr['main_consensus_gate']['status'],
                     sr['cleaning_disposition'], sr['independent_vote_eligible'])].append(sr)
        for keys, members in sorted(grouped.items()):
            valid = [r for r in members if r['confirmed_floor_metrics'] is not None]
            groups.append({'image_code': code, 'region_id': keys[0], 'condition': keys[1],
                           'main_quality_gate': keys[2], 'main_consensus_gate': keys[3],
                           'cleaning_disposition': keys[4], 'independent_vote_eligible': keys[5],
                           'n_records': len(members), 'n_distinct_workers': len({r['worker_id'] for r in members}),
                           'n_valid_geometry': len(valid), 'n_invalid_geometry': len(members) - len(valid),
                           'selected_gt_D_threshold_counts': {str(t): sum(r['selected_gt_metrics']['symmetric_difference_over_reference'] >= t for r in valid) for t in (.2, .3, .4)},
                           'confirmed_floor_D_threshold_counts': {str(t): sum(r['confirmed_floor_metrics']['symmetric_difference_over_reference'] >= t for r in valid) for t in (.2, .3, .4)},
                           'selected_gt_summary': summary_stats(members, 'selected_gt_metrics'),
                           'confirmed_floor_summary': summary_stats(members, 'confirmed_floor_metrics'),
                           'interpretation': 'diagnostic records; no eligibility release, quality Q, difficulty, majority or target assignment'})
        primary = next((r for r in image_refs if r['is_primary']), None)
        primary_rows = [r for r in current_space_records if r['is_primary']]
        image_summaries.append({'image_code': code, 'image_id': im['image_id'], 'in_current_formal_corpus': im['in_current_formal_corpus'],
                                'reference_only_reason': im['reference_only_reason'],
                                'confirmed_region_count': len(ds), 'primary_region_id': primary['region_id'] if primary else None,
                                'alternative_region_ids': [r['region_id'] for r in image_refs if not r['is_primary']],
                                'primary_decision': primary['decision'] if primary else None,
                                'n_records': len(image_records), 'n_distinct_workers': len({r['worker_id'] for r in image_records}),
                                'n_valid_geometry': sum(r['geometry_status'] == 'valid' for r in image_records),
                                'geometry_status_counts': dict(Counter(r['geometry_status'] for r in image_records)),
                                'condition_counts': dict(Counter(r['condition'] for r in image_records)),
                                'main_quality_gate_counts': dict(Counter(r['main_quality_gate']['status'] for r in image_records)),
                                'primary_confirmed_area_h2': primary['area_h2'] if primary else None,
                                'selected_gt_area_h2': G.area, 'original_gt_area_h2': O.area,
                                'primary_over_selected_area': primary['area_h2'] / G.area if primary and im['in_current_formal_corpus'] else None,
                                'selected_gt_summary': summary_stats(primary_rows, 'selected_gt_metrics'),
                                'primary_floor_summary': summary_stats(primary_rows, 'confirmed_floor_metrics'),
                                'top_boundary_pending': True, 'formal_eligibility_changed': False})
    ck('all_snapshot_annotations_accounted_for', len(records) == sum(len(i['annotations']) for i in formal['images']))
    ck('unique_annotation_rows_even_with_multiple_spaces', len(records) == len({r['record_id'] for r in records}))
    ck('all_space_annotation_pairs_accounted_for', len(space_records) == sum(len(im['annotations']) * len(decision_by_image[im['image_code']]) for im in formal['images']))
    ck('all_previous_16_confirmations_preserved', len(previous) == len(prior_overlay['records']) == 16 and all(r['exact_vertices_unchanged'] for r in previous))
    ck('zero_research_views_have_no_annotation_rows', all(im['in_current_formal_corpus'] or not im['annotations'] for im in formal['images']))
    ck('inputs_unchanged', before == input_hashes(input_dir))
    historical = []
    for old in formal['historical_three_floor_confirmations']['records']:
        ref, _ = refs_by_key[(old['image_code'], 'primary')]
        historical.append({'image_code': old['image_code'], 'old_polygon_sha256': digest(old['polygon']),
                           'final_polygon_sha256': ref['floor_polygon_sha256'],
                           'final_floor_differs_from_historical_experiment': old['polygon'] != ref['floor_xz_h'],
                           'old_experiment_remains_valid_for_its_frozen_input': True,
                           'old_T_Q_and_set_Q_are_final_confirmed_floor_results': False,
                           'recompute_full_Q_allowed_by_this_package': False,
                           'required_before_new_full_Q': 'separate top-boundary approval and scoring-protocol decision'})
    save(out / 'reference_registry.json', {'schema': 'confirmed_floor_reference_registry_v2', 'records': registry})
    save(out / 'source_bindings.json', {'schema': 'confirmed_floor_source_bindings_v1', 'records': source_bindings})
    save(out / 'record_metrics.json', records)
    invalid = [{k: r[k] for k in ('image_code', 'image_id', 'record_id', 'object_id', 'condition', 'geometry_status', 'metrics_unavailable_reason', 'main_quality_gate', 'main_consensus_gate')}
               for r in records if r['geometry_status'] != 'valid']
    save(out / 'unavailable_records.json', invalid)
    csvwrite(out / 'unavailable_records.csv', invalid)
    save(out / 'space_record_metrics.json', space_records)
    flat = []
    for row in space_records:
        names = ('selected_gt_metrics', 'original_gt_metrics', 'confirmed_floor_metrics', 'delta_confirmed_minus_selected')
        item = {k: v for k, v in row.items() if k not in names}
        for name in names:
            for key, value in (row[name] or {}).items():
                item[name + '__' + key] = value
        flat.append(item)
    csvwrite(out / 'space_record_metrics.csv', flat)
    csvwrite(out / 'record_metrics.csv', records)
    save(out / 'image_summary.json', image_summaries)
    csvwrite(out / 'image_summary.csv', image_summaries)
    save(out / 'condition_gate_summary.json', groups)
    csvwrite(out / 'condition_gate_summary.csv', groups)
    save(out / 'previous_confirmed_floor_delta.json', previous)
    save(out / 'historical_artifact_applicability.json', {
        'source_commit': formal['source_commit'], 'historical_experiment_path': 'research/quality_scope_comparison_20261010',
        'policy': 'Preserve old conditional Q as frozen history, never relabel as final floor results.', 'records': historical})
    stats = {'receipt_images': len(raw['records']), 'confirmed_images': len(image_summaries), 'confirmed_spaces': len(registry),
             'declared_primary_spaces': sum(r['is_primary'] for r in registry),
             'declared_alternative_spaces': sum(not r['is_primary'] for r in registry),
             'existing_gt_floor_decisions': sum(r['decision'] == 'full_gt' for r in registry),
             'modified_floor_decisions': sum(r['decision'] == 'allow' for r in registry),
             'previous_confirmed_images': len(previous), 'newly_confirmed_images': len(image_summaries) - len(previous),
             'unconfirmed_receipt_images': len(raw_map) - len(image_summaries),
             'research_images': sum(r['in_current_formal_corpus'] for r in image_summaries),
             'reference_only_images': [r['image_code'] for r in image_summaries if not r['in_current_formal_corpus']],
             'assigned_room_batch_images': len(assigned), 'assigned_room_batch_confirmed_images': len(assigned & set(decision_by_image)),
             'batch_policy_automatically_confirmed_images': len(raw['room_review_batch_policy']['applied_image_codes']),
             'annotation_records': len(records), 'space_annotation_pairs': len(space_records),
             'valid_geometry_records': sum(r['geometry_status'] == 'valid' for r in records),
             'geometry_status_counts': dict(Counter(r['geometry_status'] for r in records)),
             'condition_counts': dict(Counter(r['condition'] for r in records)),
             'main_quality_gate_counts': dict(Counter(r['main_quality_gate']['status'] for r in records)),
             'n_distinct_workers': len({r['worker_id'] for r in records}),
             'prior_134_record_metrics_byte_value_identical': len(baseline_record_by_id)}
    stats['modified_floor_change_kind_counts'] = dict(Counter(r['change_kind'] for r in floor_changes if r['decision'] == 'allow'))
    save(out / 'floor_geometry_changes.json', floor_changes)
    csvwrite(out / 'floor_geometry_changes.csv', floor_changes)
    save(out / 'summary.json', stats)
    validation = {'passed': all(c['passed'] for c in checks), 'check_count': len(checks), 'checks': checks,
                  'runtime': {'python': platform.python_version(), 'shapely': shapely.__version__},
                  'input_sha256': before, 'input_manifest_sha256': sha(input_dir / 'input_manifest.json'),
                  'source_commit': formal['source_commit'], 'statistics': stats,
                  'GT_modified': False, 'formal_eligibility_changed': False, 'full_3d_Q_recomputed': False,
                  'height_or_top_constructed': False, 'fusion_or_worker_curves_recomputed': False,
                  'best_reference_selection_performed': False,
                  'limitations': [
                      'BEV diagnostic units h/h^2, not meters; no automatic research gate changes.',
                      'Invalid annotation geometry yields null metrics plus reason, never zero scores or polygon repairs.',
                      'Reference-only recovered views have zero research records; no raw original label_cor claim.',
                      'Primary/alternative identities follow receipt region_id; all confirmed spaces are evaluated separately.',
                      'No best-of-reference score, union of regions, disjoint partition, majority or accepted-set Q.',
                      'All top boundaries remain pending; no new top coordinates or full 3D Q.',
                      'No-operation policy is bounded to assigned 23 images, and applied to zero additional rows in this receipt.',
                  ]}
    save(out / 'validation.json', validation)
    print(json.dumps(stats | {'passed': validation['passed'], 'check_count': len(checks)}, ensure_ascii=False, indent=2))
    return validation


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', type=Path, default=ROOT / 'inputs')
    p.add_argument('--out', type=Path, default=ROOT / 'results')
    args = p.parse_args()
    run(args.inputs, args.out)
