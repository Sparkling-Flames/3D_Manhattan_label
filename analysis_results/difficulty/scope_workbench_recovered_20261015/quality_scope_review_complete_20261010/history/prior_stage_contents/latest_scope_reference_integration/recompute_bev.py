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


def run(input_dir, out):
    input_dir, out = Path(input_dir), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    overlay_path = input_dir / 'normalized_confirmation_overlay.json'
    formal_path = input_dir / 'current_formal_subset.json'
    raw_path = input_dir / 'raw_scope_return.json'
    overlay, formal, raw = map(read, [overlay_path, formal_path, raw_path])
    raw_map = {r['image_code']: r for r in raw['records']}
    before = {p.name: sha(p) for p in (overlay_path, formal_path, raw_path)}
    checks = []

    def ck(name, ok, detail=None):
        checks.append({'check': name, 'passed': bool(ok), 'detail': detail})
        if not ok:
            raise AssertionError((name, detail))

    manifest = read(input_dir / 'input_manifest.json')
    ck('input_manifest_schema', manifest['schema'] == 'scope_bev_input_manifest_v1')
    ck('input_manifest_matches_bytes', manifest['files'] == before)
    ck('overlay_schema', overlay['schema'] == 'manual_floor_scope_confirmation_overlay_v1')
    ck('formal_snapshot_schema', formal['schema'] == 'scope_formal_geometry_snapshot_v1')
    ck('raw_receipt_matches_extraction', sha(raw_path) == formal['raw_receipt_sha256'])
    ck('overlay_matches_extraction', sha(overlay_path) == formal['overlay_sha256'])
    rows = overlay['records']
    ck('exactly_16_distinct_images', len(rows) == len({r['image_code'] for r in rows}) == 16)
    ck('three_existing_gt_decisions_and_thirteen_alternatives',
       Counter(r['decision'] for r in rows) == {'full_gt': 3, 'allow': 13})
    formal_images = {i['image_code']: i for i in formal['images']}
    ck('formal_population_matches_overlay', set(formal_images) == {r['image_code'] for r in rows})
    records, registry, summaries, all_groups, previous_deltas = [], [], [], [], []
    for decision in sorted(rows, key=lambda r: r['image_code']):
        code = decision['image_code']
        im, source = formal_images[code], raw_map[code]
        selected, original = im['selected_gt'], im['original_gt']
        ck(code + ':floor_confirmation_only', decision['floor_region_confirmed'] is True and
           decision['completed'] is True and decision['top_boundary_pending'] is True and
           decision['reference_ready'] is False and decision['formal_eligibility_changed'] is False)
        ck(code + ':exact_received_floor', decision['polygon'] == source['cropped_floor_xz_h'] == source['polygon'])
        ck(code + ':selected_reference_bound', decision['reference_object_id'] == selected['object_id'] ==
           source['editing_reference_object_id'] and decision['image_id'] == im['image_id'])
        ck(code + ':selected_reference_points_unchanged', selected['points_1024x512'] == source['editing_reference_points_1024x512'])
        ck(code + ':historical_original_reference_unchanged', original['object_id'] == source['historical_original_GT_object_id'] and
           original['points_1024x512'] == source['historical_original_GT_points_1024x512'])
        G, gs = project_floor(selected['points_1024x512'])
        O, os = project_floor(original['points_1024x512'])
        T, ts = floor_polygon(decision['polygon'])
        ck(code + ':all_reference_floors_valid', gs == os == ts == 'valid', [gs, os, ts])
        is_alternative = decision['decision'] == 'allow'
        if not is_alternative:
            ck(code + ':full_gt_is_not_new_geometry', G.symmetric_difference(T).area / G.area < 1e-12)
        reference_id = (code + ':manual_floor:' + digest(decision['polygon'])[:16]) if is_alternative else selected['object_id']
        ref = {
            'image_code': code, 'image_id': im['image_id'], 'decision': decision['decision'],
            'reference_id': reference_id, 'new_floor_alternative': is_alternative,
            'role': 'confirmed_manual_floor_alternative' if is_alternative else 'confirmed_existing_selected_gt_floor',
            'selected_gt_object_id': selected['object_id'], 'selected_gt_kind': selected['object_kind'],
            'original_gt_object_id': original['object_id'], 'original_gt_kind': original['object_kind'],
            'selected_differs_from_original': selected['object_id'] != original['object_id'],
            'floor_xz_h': decision['polygon'], 'floor_polygon_sha256': digest(decision['polygon']),
            'area_h2': T.area, 'perimeter_h': T.length,
            'confirmed_vs_selected_gt': area_metrics(T, G),
            'confirmed_vs_original_gt': area_metrics(T, O),
            'camera_inside': True, 'camera_distance_to_floor_boundary_h': T.boundary.distance(Point(0, 0)),
            'top_boundary_pending': True, 'reference_ready': False, 'new_top_coordinates': None,
            'accepted_set_scoring_protocol': 'not_established_by_this_floor_confirmation',
            'formal_gt_changed': False, 'formal_eligibility_changed': False,
            'diagnostic_use': 'BEV_only; not a formal reference replacement or scope routing decision',
            'confirmation_provenance': decision.get('provenance'),
        }
        registry.append(ref)
        if decision['provenance']['confirmation_basis'] == 'explicit_user_message_adopts_updated_draft_despite_missing_button':
            prior = next(r['snapshot'] for r in decision['previous_confirmation_history'] if r['role'] == 'site_prior_confirmed_review')
            P, ps = floor_polygon(prior['polygon'])
            ck(code + ':prior_confirmed_floor_available', ps == 'valid')
            previous_deltas.append({
                'image_code': code, 'prior_polygon_sha256': digest(prior['polygon']),
                'latest_polygon_sha256': digest(decision['polygon']),
                'exact_vertices_changed': prior['polygon'] != decision['polygon'],
                'prior_area_h2': P.area, 'latest_area_h2': T.area,
                'latest_minus_prior_area_h2': T.area - P.area,
                'latest_vs_prior_metrics': area_metrics(T, P),
                'prior_confirmation_message_id': prior.get('confirmation_message_id'),
                'latest_confirmation_message_id': decision.get('confirmation_message_id'),
                'history_policy': 'retain prior snapshot; latest exact floor supersedes prior only for current BEV diagnostics',
            })
        image_records = []
        for a in sorted(im['annotations'], key=lambda a: a['record_id']):
            A, status = project_floor(a['points_1024x512'])
            entry = {
                'image_code': code, 'image_id': im['image_id'], 'record_id': a['record_id'],
                'object_id': a['object_id'], 'worker_id': a['worker_id'], 'condition': a['condition'],
                'cleaning_disposition': a['cleaning_disposition'],
                'independent_vote_eligible': a['independent_vote_eligible'],
                'main_quality_gate': a['main_quality_gate'], 'main_consensus_gate': a['main_consensus_gate'],
                'ring_confirmed': a['ring_confirmed'], 'ordered_source_pair_indices': a['ordered_source_pair_indices'],
                'formal_object_sha256': a['formal_object_sha256'],
                'population': 'all_formal_annotations_in_these_16_images_no_new_eligibility',
                'geometry_status': status, 'decision': decision['decision'], 'reference_id': reference_id,
                'selected_gt_metrics': area_metrics(A, G) if A is not None else None,
                'original_gt_metrics': area_metrics(A, O) if A is not None else None,
                'confirmed_floor_metrics': area_metrics(A, T) if A is not None else None,
                'delta_confirmed_minus_selected': None,
            }
            if A is not None:
                entry['delta_confirmed_minus_selected'] = {
                    k: entry['confirmed_floor_metrics'][k] - entry['selected_gt_metrics'][k]
                    for k in ('bev_iou', 'reference_coverage_fraction', 'reference_missing_fraction',
                              'annotation_outside_fraction', 'symmetric_difference_over_reference')}
                for tag in ('selected_gt_metrics', 'original_gt_metrics', 'confirmed_floor_metrics'):
                    m = entry[tag]
                    ck(a['record_id'] + ':' + tag + ':area_identities',
                       abs(m['reference_coverage_fraction'] + m['reference_missing_fraction'] - 1) < 1e-10 and
                       abs(m['symmetric_difference_over_reference'] - m['reference_missing_fraction'] - m['excess_area_over_reference']) < 1e-10 and
                       -1e-12 <= m['bev_iou'] <= 1 + 1e-12)
                if not is_alternative:
                    ck(a['record_id'] + ':full_gt_metrics_unchanged',
                       max(abs(v) for v in entry['delta_confirmed_minus_selected'].values()) < 1e-11)
            records.append(entry)
            image_records.append(entry)
        groups = defaultdict(list)
        for row in image_records:
            groups[(row['condition'], row['main_quality_gate']['status'], row['main_consensus_gate']['status'],
                    row['cleaning_disposition'], row['independent_vote_eligible'])].append(row)
        for keys, members in sorted(groups.items()):
            valid = [r for r in members if r['confirmed_floor_metrics'] is not None]
            all_groups.append({
                'image_code': code, 'condition': keys[0], 'main_quality_gate': keys[1],
                'main_consensus_gate': keys[2], 'cleaning_disposition': keys[3], 'independent_vote_eligible': keys[4],
                'n_records': len(members), 'n_distinct_workers': len({r['worker_id'] for r in members}),
                'n_valid_geometry': len(valid), 'n_invalid_geometry': len(members) - len(valid),
                'selected_gt_D_threshold_counts': {str(t): sum(r['selected_gt_metrics']['symmetric_difference_over_reference'] >= t for r in valid) for t in (.2, .3, .4)},
                'confirmed_floor_D_threshold_counts': {str(t): sum(r['confirmed_floor_metrics']['symmetric_difference_over_reference'] >= t for r in valid) for t in (.2, .3, .4)},
                'interpretation': 'diagnostic counts only; no majority decision, eligibility release, quality, or difficulty label',
            })
        valid = [r for r in image_records if r['confirmed_floor_metrics'] is not None]
        summaries.append({
            'image_code': code, 'decision': decision['decision'], 'new_floor_alternative': is_alternative,
            'selected_gt_kind': selected['object_kind'], 'selected_differs_from_original': selected['object_id'] != original['object_id'],
            'n_records': len(image_records), 'n_distinct_workers': len({r['worker_id'] for r in image_records}),
            'n_valid_geometry': len(valid), 'geometry_status_counts': dict(Counter(r['geometry_status'] for r in image_records)),
            'main_quality_gate_counts': dict(Counter(r['main_quality_gate']['status'] for r in image_records)),
            'confirmed_area_h2': T.area, 'selected_gt_area_h2': G.area, 'original_gt_area_h2': O.area,
            'confirmed_over_selected_area': T.area / G.area,
            'confirmed_outside_selected_fraction': T.difference(G).area / T.area,
            'confirmed_selected_bev_iou': T.intersection(G).area / T.union(G).area,
            'top_boundary_pending': True, 'formal_eligibility_changed': False,
        })
    ck('all_snapshot_annotations_accounted_for', len(records) == sum(len(i['annotations']) for i in formal['images']))
    ck('all_record_ids_unique', len(records) == len({r['record_id'] for r in records}))
    ck('exactly_five_previous_confirmed_floor_updates', len(previous_deltas) == 5 and all(r['exact_vertices_changed'] for r in previous_deltas))
    ck('inputs_unchanged', before == {p.name: sha(p) for p in (overlay_path, formal_path, raw_path)})
    latest = {r['image_code']: r for r in rows}
    historical = []
    for old in formal['historical_three_floor_confirmations']['records']:
        current = latest[old['image_code']]
        historical.append({
            'image_code': old['image_code'], 'old_polygon_sha256': digest(old['polygon']),
            'latest_polygon_sha256': digest(current['polygon']),
            'latest_floor_differs_from_historical_experiment': old['polygon'] != current['polygon'],
            'old_experiment_remains_valid_for_its_frozen_input': True,
            'old_T_Q_and_set_Q_are_current_confirmed_floor_results': False,
            'recompute_full_Q_allowed_by_this_package': False,
            'required_before_new_full_Q': 'separate top-boundary approval and scoring-protocol decision',
        })
    ck('all_three_old_experiment_floors_are_historical_now', len(historical) == 3 and all(r['latest_floor_differs_from_historical_experiment'] for r in historical))
    save(out / 'previous_confirmed_floor_delta.json', previous_deltas)
    save(out / 'historical_artifact_applicability.json', {
        'source_commit': formal['source_commit'],
        'historical_experiment_path': 'research/quality_scope_comparison_20261010',
        'historical_confirmation_path': formal['historical_three_floor_confirmation_path'],
        'policy': 'Preserve the old experiment as frozen history; do not relabel its conditional T Q, set Q, routing or figures as outputs for the latest floor vertices.',
        'records': historical,
    })
    save(out / 'reference_registry.json', {'schema': 'confirmed_floor_reference_registry_v1', 'records': registry})
    save(out / 'record_metrics.json', records)
    flat = []
    for row in records:
        item = {k: v for k, v in row.items() if k not in ('selected_gt_metrics', 'original_gt_metrics', 'confirmed_floor_metrics', 'delta_confirmed_minus_selected')}
        for key in ('selected_gt_metrics', 'original_gt_metrics', 'confirmed_floor_metrics', 'delta_confirmed_minus_selected'):
            for name, value in (row[key] or {}).items():
                item[key + '__' + name] = value
        flat.append(item)
    csvwrite(out / 'record_metrics.csv', flat)
    save(out / 'image_summary.json', summaries)
    csvwrite(out / 'image_summary.csv', summaries)
    save(out / 'condition_gate_summary.json', all_groups)
    csvwrite(out / 'condition_gate_summary.csv', all_groups)
    validation = {
        'passed': all(c['passed'] for c in checks), 'check_count': len(checks), 'checks': checks,
        'runtime': {'python': platform.python_version(), 'shapely': shapely.__version__},
        'input_sha256': before, 'input_manifest_sha256': sha(input_dir / 'input_manifest.json'),
        'source_commit': formal['source_commit'],
        'images': len(summaries), 'existing_gt_floor_decisions': 3, 'manual_floor_alternatives': 13,
        'annotation_records': len(records), 'valid_geometry_records': sum(r['geometry_status'] == 'valid' for r in records),
        'geometry_status_counts': dict(Counter(r['geometry_status'] for r in records)),
        'GT_modified': False, 'formal_eligibility_changed': False, 'full_3d_Q_recomputed': False,
        'height_or_top_constructed': False, 'fusion_or_worker_curves_recomputed': False,
        'source_receipt_validation': 'Consumed normalized separately validated receipt; does not replace receipt validation.',
        'limitations': [
            'Diagnostic BEV geometry only, in camera-height units h and h^2, not meters.',
            'All formal annotation records are retained, including historical/excluded/held and invalid geometry.',
            'Invalid geometry produces null metrics, never implicit zeros or repaired polygons.',
            'No sort-by-x, buffer(0), clipping to GT, silent snapping, height guessing, or reference optimization.',
            'Three full_gt decisions confirm existing selected floors; they are not three new alternatives.',
            'All 16 top-boundary pending flags are preserved; full_gt does not create new top approval.',
            'No automatic target assignment, accepted-set scoring, Q, eligibility release, or difficulty classification.',
        ],
    }
    save(out / 'validation.json', validation)
    print(json.dumps({k: v for k, v in validation.items() if k not in ('checks', 'limitations', 'input_sha256')}, ensure_ascii=False, indent=2))
    return validation


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', type=Path, default=ROOT / 'inputs')
    p.add_argument('--out', type=Path, default=ROOT / 'results')
    args = p.parse_args()
    run(args.inputs, args.out)
