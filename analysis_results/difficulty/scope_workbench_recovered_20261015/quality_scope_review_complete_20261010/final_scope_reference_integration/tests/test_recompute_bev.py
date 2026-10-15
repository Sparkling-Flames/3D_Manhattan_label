import copy
import json
import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recompute_bev import area_metrics, digest, floor_polygon, project_floor, read, run


def erp_points(floor):
    points = []
    for x, z in floor:
        u = math.atan2(x, -z)
        y = 256 + math.atan2(1, math.hypot(x, z)) * 512 / math.pi
        px = (u / (2 * math.pi) + 0.5) * 1024
        points += [[px, 170], [px, y]]
    return points


def test_identical_polygons():
    p = Polygon([[-1, -1], [1, -1], [1, 1], [-1, 1]])
    m = area_metrics(p, p)
    assert m['bev_iou'] == m['reference_coverage_fraction'] == 1
    assert m['reference_missing_fraction'] == m['annotation_outside_fraction'] == m['symmetric_difference_over_reference'] == 0


def test_partial_overlap_and_distinct_denominators():
    a = Polygon([[0, 0], [3, 0], [3, 2], [0, 2]])
    r = Polygon([[0, 0], [2, 0], [2, 2], [0, 2]])
    m = area_metrics(a, r)
    assert m['bev_iou'] == pytest.approx(2 / 3)
    assert m['annotation_outside_fraction'] == pytest.approx(1 / 3)
    assert m['excess_area_over_reference'] == pytest.approx(1 / 2)
    assert m['symmetric_difference_over_reference'] == pytest.approx(1 / 2)


def test_nonnested_sets_preserve_both_differences():
    a = Polygon([[-2, -1], [1, -1], [1, 1], [-2, 1]])
    r = Polygon([[-1, -1], [2, -1], [2, 1], [-1, 1]])
    m = area_metrics(a, r)
    assert m['outside_area_h2'] == m['missing_area_h2'] == 2
    assert m['bev_iou'] == .5


def test_projection_is_continuous_and_camera_height_normalized():
    p = [[-2, -1], [1, -1], [1, 3], [-2, 3]]
    actual, status = project_floor(erp_points(p))
    assert status == 'valid'
    for actual_point, expected_point in zip(actual.exterior.coords, p):
        assert actual_point == pytest.approx(expected_point, abs=1e-12)


def test_declared_order_not_sort_by_x():
    floor = [[-2, -1], [1, -1], [1, 1], [.5, 1], [.5, 2], [-2, 2]]
    points = erp_points(floor)
    actual, status = project_floor(points)
    assert status == 'valid'
    assert actual.symmetric_difference(Polygon(floor)).area < 1e-12
    assert [round(x, 10) for x, y in actual.exterior.coords[:-1]] == [x for x, y in floor]


@pytest.mark.parametrize('points,reason', [
    (None, 'invalid_pairs'), ([], 'invalid_pairs'), ([[1, 1]] * 5, 'invalid_pairs'),
    ([[1, 1], [1, 200]] * 3, 'floor_not_below_horizon'),
    ([[1, 1], [1, 512]] * 3, 'floor_not_below_horizon'),
    ([[1025, 1], [1, 300]] * 3, 'outside_canvas'),
    ([[1, 1], [1, float('nan')]] * 3, 'invalid_pairs'),
])
def test_invalid_projection_is_null(points, reason):
    polygon, status = project_floor(points)
    assert polygon is None and status == reason


def test_camera_boundary_is_not_interior():
    p, status = floor_polygon([[0, 0], [1, 0], [1, 1], [0, 1]])
    assert p is None and status == 'camera_not_inside'


def test_self_intersection_is_not_repaired():
    p, status = floor_polygon([[-1, -1], [1, 1], [1, -1], [-1, 1]])
    assert p is None and status == 'invalid_polygon'


def test_height_changes_do_not_change_floor_metrics():
    points = erp_points([[-1, -1], [1, -1], [1, 1], [-1, 1]])
    modified = copy.deepcopy(points)
    for point in modified[::2]:
        point[1] = 240
    a, _ = project_floor(points)
    b, _ = project_floor(modified)
    assert a.equals_exact(b, 0)


from recompute_bev import floor_change_kind, input_hashes, save, sha
import shutil


def copy_inputs(tmp_path):
    inputs = tmp_path / 'inputs'
    shutil.copytree(ROOT / 'inputs', inputs)
    return inputs


def seal_modified_fixture(inputs):
    formal = read(inputs / 'current_formal_subset.json')
    formal['raw_receipt_sha256'] = sha(inputs / 'raw_scope_return.json')
    formal['overlay_sha256'] = sha(inputs / 'normalized_confirmation_overlay.json')
    save(inputs / 'current_formal_subset.json', formal)
    manifest = read(inputs / 'input_manifest.json')
    manifest['files'] = input_hashes(inputs)
    save(inputs / 'input_manifest.json', manifest)


def test_actual_confirmation_scope_35_not_all_261():
    overlay = read(ROOT / 'inputs/normalized_confirmation_overlay.json')
    stats = read(ROOT / 'results/summary.json')
    assert len(overlay['records']) == 35
    assert stats['confirmed_images'] == 35 and stats['unconfirmed_receipt_images'] == 226
    assert stats['declared_alternative_spaces'] == 0
    assert sum(r['decision'] == 'allow' for r in overlay['records']) == 28
    assert sum(r['decision'] == 'full_gt' for r in overlay['records']) == 7
    assert all(r['top_boundary_pending'] and not r['reference_ready'] for r in overlay['records'])
    assert stats['assigned_room_batch_confirmed_images'] == 23
    assert stats['batch_policy_automatically_confirmed_images'] == 0


def test_no_floor_coordinate_change(tmp_path):
    run(ROOT / 'inputs', tmp_path)
    overlay = read(ROOT / 'inputs/normalized_confirmation_overlay.json')
    registry = read(tmp_path / 'reference_registry.json')['records']
    assert {(r['image_code'], r['region_id']): r['floor_xz_h'] for r in registry} == {(r['image_code'], r['region_id']): r['polygon'] for r in overlay['records']}
    assert all(r['new_top_coordinates'] is None for r in registry)


def test_overlay_hash_mismatch_is_fail_closed(tmp_path):
    inputs = copy_inputs(tmp_path)
    overlay = read(inputs / 'normalized_confirmation_overlay.json')
    overlay['records'][0]['polygon'][0][0] += 0.01
    save(inputs / 'normalized_confirmation_overlay.json', overlay)
    with pytest.raises(AssertionError, match='input_manifest_matches_bytes'):
        run(inputs, tmp_path / 'out')


def test_formal_gate_tampering_is_fail_closed(tmp_path):
    inputs = copy_inputs(tmp_path)
    formal = read(inputs / 'current_formal_subset.json')
    formal['images'][0]['annotations'][0]['main_quality_gate']['status'] = 'modified'
    save(inputs / 'current_formal_subset.json', formal)
    with pytest.raises(AssertionError, match='input_manifest_matches_bytes'):
        run(inputs, tmp_path / 'out')


def test_portable_replay_is_byte_identical(tmp_path):
    run(ROOT / 'inputs', tmp_path)
    for path in tmp_path.iterdir():
        assert path.read_bytes() == (ROOT / 'results' / path.name).read_bytes(), path.name


def test_all_formal_gates_and_records_preserved():
    snapshot = read(ROOT / 'inputs/current_formal_subset.json')
    rows = read(ROOT / 'results/record_metrics.json')
    current = {a['object_id']: a for im in snapshot['images'] for a in im['annotations']}
    assert len(current) == len(rows) == 429
    for r in rows:
        for key in ('worker_quality_gate', 'main_quality_gate', 'main_consensus_gate', 'cleaning_disposition', 'independent_vote_eligible', 'ordered_source_pair_indices', 'formal_object_sha256'):
            assert r[key] == current[r['object_id']][key]


def test_reference_only_views_do_not_enter_research_denominator():
    snapshot = read(ROOT / 'inputs/current_formal_subset.json')
    extra = [im for im in snapshot['images'] if not im['in_current_formal_corpus']]
    assert {im['image_code'] for im in extra} == {'q9vSo1VnCiC-21', 'q9vSo1VnCiC-25'}
    assert snapshot['current_formal_research_population_images'] == 259
    assert snapshot['current_formal_image_registry_count'] == 261
    assert snapshot['current_formal_existing_reference_only_images'] == 2
    assert all(im['annotations'] == [] for im in extra)
    assert all(im['reference_provenance']['raw_original_label_cor_available'] is False for im in extra)
    rows = read(ROOT / 'results/record_metrics.json')
    assert not any(r['image_code'] in {im['image_code'] for im in extra} for r in rows)


def test_prior_16_and_134_metrics_are_unchanged():
    previous = read(ROOT / 'results/previous_confirmed_floor_delta.json')
    assert len(previous) == 16
    assert all(r['exact_vertices_unchanged'] for r in previous)
    old = {r['record_id']: r for r in read(ROOT / 'inputs/prior_record_metrics.json')}
    new = {r['record_id']: r for r in read(ROOT / 'results/record_metrics.json')}
    assert len(old) == 134
    for key, row in old.items():
        assert new[key]['selected_gt_metrics'] == row['selected_gt_metrics']
        assert new[key]['original_gt_metrics'] == row['original_gt_metrics']
        assert new[key]['confirmed_spaces'][0]['confirmed_floor_metrics'] == row['confirmed_floor_metrics']


def test_invalid_rows_are_retained_with_reasons_and_nulls():
    rows = read(ROOT / 'results/record_metrics.json')
    invalid = [r for r in rows if r['geometry_status'] != 'valid']
    assert len(invalid) == 12
    for r in invalid:
        assert r['selected_gt_metrics'] is None and r['original_gt_metrics'] is None
        assert r['metrics_unavailable_reason']
        assert all(s['confirmed_floor_metrics'] is None for s in r['confirmed_spaces'])


def test_change_classification_uses_added_and_removed_not_net_area():
    a = Polygon([[-2, -1], [1, -1], [1, 1], [-2, 1]])
    b = Polygon([[-1, -1], [2, -1], [2, 1], [-1, 1]])
    c = floor_change_kind(a, b)
    assert c['net_area_change_h2'] == 0
    assert c['change_kind'] == 'mixed_addition_and_removal'
    assert c['added_outside_gt_area_h2'] == c['removed_from_gt_area_h2'] == 2


def test_change_tolerance_does_not_modify_areas():
    a = Polygon([[-1, -1], [1 + 1e-12, -1], [1 + 1e-12, 1], [-1, 1]])
    b = Polygon([[-1, -1], [1, -1], [1, 1], [-1, 1]])
    c = floor_change_kind(a, b)
    assert c['change_kind'] == 'equivalent_within_tolerance'
    assert c['added_outside_gt_area_h2'] > 0


def test_unb88_expansion_outside_gt_preserved():
    change = next(r for r in read(ROOT / 'results/floor_geometry_changes.json') if r['image_code'] == 'uNb9QFRL6hY-88')
    assert change['change_kind'] == 'expansion_only_within_tolerance'
    assert change['added_outside_gt_area_h2'] == pytest.approx(0.8338373345543549)
    assert not change['rounding_clipping_or_geometry_repair_performed']


def test_recovered_snapshot_source_order_preserved():
    for code in ('q9vSo1VnCiC-21', 'q9vSo1VnCiC-25'):
        source = read(ROOT / 'inputs/recovered' / (code + '.snapshot-record.json'))
        metadata = read(ROOT / 'inputs/recovered' / (code + '.json'))
        points = [[round(p['value']['x'] * 1024 / 100, 8), round(p['value']['y'] * 512 / 100, 8)]
                  for p in source['annotations'][0]['result'] if p['type'] == 'keypointlabels']
        assert points == metadata['original_reference_points_1024x512']


def add_explicit_alternative(inputs):
    overlay = read(inputs / 'normalized_confirmation_overlay.json')
    raw = read(inputs / 'raw_scope_return.json')
    primary = next(r for r in overlay['records'] if r['image_code'] == 'uNb9QFRL6hY-88')
    source = next(r for r in raw['records'] if r['image_code'] == primary['image_code'])
    d = copy.deepcopy(primary)
    d.update(region_id='alternative-test', region_name='显式替代测试', is_primary=False, is_active=False, decision='allow')
    # Alternative differs from primary. Both must be reported without scoring-based selection.
    d['polygon'] = d['cropped_floor_xz_h'] = copy.deepcopy(source['original_GT_floor_xz_h'])
    r = copy.deepcopy(source['space_regions']['regions'][0])
    r.update(region_id=d['region_id'], name=d['region_name'], polygon=d['polygon'], decision='allow')
    r['confirmed_version']['polygon'] = d['polygon']
    source['space_regions']['regions'].append(r)
    overlay['records'].append(d)
    save(inputs / 'raw_scope_return.json', raw)
    save(inputs / 'normalized_confirmation_overlay.json', overlay)
    seal_modified_fixture(inputs)


def test_multispace_keeps_declared_primary_and_no_best_score_selection(tmp_path):
    inputs = copy_inputs(tmp_path)
    add_explicit_alternative(inputs)
    run(inputs, tmp_path / 'out')
    rows = read(tmp_path / 'out/record_metrics.json')
    original = {r['record_id']: r for r in read(ROOT / 'results/record_metrics.json')}
    affected = [r for r in rows if r['image_code'] == 'uNb9QFRL6hY-88']
    assert affected and len(rows) == 429
    for r in affected:
        assert r['primary_space_region_id'] == 'primary'
        assert len(r['confirmed_spaces']) == 2
        primary = next(s for s in r['confirmed_spaces'] if s['is_primary'])
        assert primary == original[r['record_id']]['confirmed_spaces'][0]
    registry = read(tmp_path / 'out/reference_registry.json')['records']
    assert len(registry) == 36
    assert sum(not r['is_primary'] for r in registry) == 1
    assert read(tmp_path / 'out/validation.json')['best_reference_selection_performed'] is False


def test_unconfirmed_alternative_cannot_be_promoted(tmp_path):
    inputs = copy_inputs(tmp_path)
    add_explicit_alternative(inputs)
    raw = read(inputs / 'raw_scope_return.json')
    source = next(r for r in raw['records'] if r['image_code'] == 'uNb9QFRL6hY-88')
    source['space_regions']['regions'][-1]['floor_region_confirmed'] = False
    save(inputs / 'raw_scope_return.json', raw)
    seal_modified_fixture(inputs)
    with pytest.raises(AssertionError, match='raw_region_is_explicitly_confirmed'):
        run(inputs, tmp_path / 'out')


def test_duplicate_image_region_rejected(tmp_path):
    inputs = copy_inputs(tmp_path)
    overlay = read(inputs / 'normalized_confirmation_overlay.json')
    overlay['records'].append(copy.deepcopy(overlay['records'][0]))
    save(inputs / 'normalized_confirmation_overlay.json', overlay)
    seal_modified_fixture(inputs)
    with pytest.raises(AssertionError, match='unique_image_region_keys'):
        run(inputs, tmp_path / 'out')
