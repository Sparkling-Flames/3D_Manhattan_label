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


def test_fixture_has_exact_16_and_13_new_floor_alternatives():
    overlay = read(ROOT / 'inputs/normalized_confirmation_overlay.json')
    assert len(overlay['records']) == 16
    assert sum(r['decision'] == 'allow' for r in overlay['records']) == 13
    assert sum(r['decision'] == 'full_gt' for r in overlay['records']) == 3
    assert all(r['top_boundary_pending'] and not r['reference_ready'] for r in overlay['records'])


def test_no_floor_coordinate_change(tmp_path):
    run(ROOT / 'inputs', tmp_path)
    overlay = read(ROOT / 'inputs/normalized_confirmation_overlay.json')
    registry = read(tmp_path / 'reference_registry.json')['records']
    assert {r['image_code']: r['floor_xz_h'] for r in registry} == {r['image_code']: r['polygon'] for r in overlay['records']}
    assert all(r['new_top_coordinates'] is None for r in registry)


def test_overlay_hash_mismatch_is_fail_closed(tmp_path):
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    for name in ('raw_scope_return.json', 'current_formal_subset.json', 'normalized_confirmation_overlay.json', 'input_manifest.json'):
        (inputs / name).write_bytes((ROOT / 'inputs' / name).read_bytes())
    overlay = read(inputs / 'normalized_confirmation_overlay.json')
    overlay['records'][0]['polygon'][0][0] += 0.01
    (inputs / 'normalized_confirmation_overlay.json').write_text(json.dumps(overlay))
    with pytest.raises(AssertionError, match='input_manifest_matches_bytes'):
        run(inputs, tmp_path / 'out')


def test_formal_gate_tampering_is_fail_closed(tmp_path):
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    for path in (ROOT / 'inputs').glob('*.json'):
        (inputs / path.name).write_bytes(path.read_bytes())
    formal = read(inputs / 'current_formal_subset.json')
    formal['images'][0]['annotations'][0]['main_quality_gate']['status'] = 'modified'
    (inputs / 'current_formal_subset.json').write_text(json.dumps(formal))
    with pytest.raises(AssertionError, match='input_manifest_matches_bytes'):
        run(inputs, tmp_path / 'out')


def test_portable_replay_is_byte_identical(tmp_path):
    run(ROOT / 'inputs', tmp_path)
    for path in tmp_path.iterdir():
        assert path.read_bytes() == (ROOT / 'results' / path.name).read_bytes(), path.name


def test_all_formal_gates_preserved():
    snapshot = read(ROOT / 'inputs/current_formal_subset.json')
    rows = read(ROOT / 'results/record_metrics.json')
    current = {a['object_id']: a for im in snapshot['images'] for a in im['annotations']}
    assert len(current) == len(rows)
    for r in rows:
        for key in ('main_quality_gate', 'main_consensus_gate', 'cleaning_disposition', 'independent_vote_eligible', 'ordered_source_pair_indices'):
            assert r[key] == current[r['object_id']][key]
