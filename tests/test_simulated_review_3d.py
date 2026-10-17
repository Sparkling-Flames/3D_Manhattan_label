import copy
import json

import numpy as np
from PIL import Image

from tools.label_studio.panorama_studio.geometry import project_pixel
from tools.thesis_main.analysis.simulated_annotators_3d import reconstruct_for_review
from tools.thesis_main.analysis.render_simulated_annotators import load_cases, periodic_segments


FLOOR = [(-2, -3), (3, -3), (3, 2), (-2, 2)]


def points(scale=1):
    return [project_pixel([x * scale, y * scale, z * scale], 1024, 512)
            for x, z in FLOOR for y in (1.5, -1)]


def test_relative_reconstruction_round_trips_raw_rays():
    source = dict(points=points(), ring_confirmed=True)
    before = copy.deepcopy(source)
    g = reconstruct_for_review(source, 'models')
    assert g['status'] == 'available'
    np.testing.assert_allclose(g['floor'], [[x, -1, z] for x, z in FLOOR], atol=1e-12)
    np.testing.assert_allclose(g['top'], [[x, 1.5, z] for x, z in FLOOR], atol=1e-12)
    for ring, offset in [(g['top'], 0), (g['floor'], 1)]:
        for xyz, pixel in zip(ring, source['points'][offset::2]):
            np.testing.assert_allclose(project_pixel(xyz, 1024, 512), pixel, atol=1e-10)
    assert source == before


def test_world_scale_is_not_inferred_from_angles():
    a = reconstruct_for_review(dict(points=points()), 'models')
    b = reconstruct_for_review(dict(points=points(4)), 'models')
    np.testing.assert_allclose(a['floor'], b['floor'])
    np.testing.assert_allclose(a['top'], b['top'])
    assert a['camera_height'] == 1


def test_seam_endpoints_are_periodically_equivalent():
    p = points()
    p[0][0], p[1][0] = 0, 0
    a = reconstruct_for_review(dict(points=p), 'models')
    p[0][0], p[1][0] = 1024, 1024
    b = reconstruct_for_review(dict(points=p), 'models')
    np.testing.assert_allclose(a['floor'], b['floor'], atol=1e-12)
    np.testing.assert_allclose(a['top'], b['top'], atol=1e-12)
    segments = list(periodic_segments([1020, 100], [4, 100]))
    assert len(segments) == 2
    assert all(abs(b[0] - a[0]) <= 8 for a, b in segments)


def test_independent_top_ray_preserves_slanted_pair():
    p = points()
    p[0][0] += 10
    g = reconstruct_for_review(dict(points=p), 'synthetic')
    assert 'vertical_pair_mismatch' in g['issues']
    assert g['status'] == 'wireframe_warning'
    assert not np.allclose(np.array(g['floor'])[0, [0, 2]], np.array(g['top'])[0, [0, 2]])
    np.testing.assert_allclose(project_pixel(g['top'][0], 1024, 512), p[0])


def test_self_crossing_ring_is_shown_without_reordering():
    pair = np.array(points()).reshape(-1, 2, 2)
    crossed = pair[[0, 2, 1, 3]].reshape(-1, 2).tolist()
    g = reconstruct_for_review(dict(points=crossed), 'human')
    assert g['status'] == 'wireframe_warning'
    assert 'invalid_footprint' in g['issues']
    assert 'ring_order_unconfirmed' in g['issues']
    assert 'adjacent_pairing_unverified' in g['issues']
    np.testing.assert_allclose(np.array(g['floor'])[:, [0, 2]], np.array(FLOOR)[[0, 2, 1, 3]])


def test_wrong_top_hemisphere_keeps_floor_available():
    p = points()
    p[0][1] = 300
    g = reconstruct_for_review(dict(points=p), 'models')
    assert g['status'] == 'floor_only'
    assert 'wrong_hemisphere' in g['issues']
    assert g['top'][0] is None
    assert all(x is not None for x in g['floor'])


def test_near_horizon_floor_is_unavailable_without_clamping():
    p = points()
    p[1][1] = 256.01
    g = reconstruct_for_review(dict(points=p), 'models')
    assert g['status'] == 'unavailable'
    assert 'near_horizon' in g['issues']
    assert g['floor'][0] is None


def test_bad_source_array_is_explicitly_unavailable():
    for p in ([], points()[:-1], [[float('nan'), 10]] * 8):
        g = reconstruct_for_review(dict(points=p), 'human')
        assert g['status'] == 'unavailable'
        assert g['issues'] == ['invalid_point_array']


def test_old_review_input_gets_optional_3d_without_source_writeback(tmp_path):
    image = tmp_path / 'image.png'
    Image.new('RGB', (1024, 512)).save(image)
    payload = dict(cases=[dict(image_id='test', image_path=str(image),
                              models=[dict(name='legacy model', points=points())],
                              human=[], synthetic=[])])
    path = tmp_path / 'review_cases.json'
    original = json.dumps(payload)
    path.write_text(original)
    cases = load_cases(tmp_path)
    assert cases[0]['models'][0]['geometry3d']['status'] == 'wireframe_warning'
    assert cases[0]['models'][0]['points'] == payload['cases'][0]['models'][0]['points']
    assert path.read_text() == original


def test_current_loader_verified_pair_ids_are_preserved():
    row = dict(points=points(), ring_confirmed=True, pairing_verified=True, source_pair_indices=[7, 2, 9, 1])
    g = reconstruct_for_review(row, 'human')
    assert g['status'] == 'available'
    assert g['pairing_status'] == 'current_loader_verified'
    assert g['source_pair_indices'] == [7, 2, 9, 1]
    row['source_pair_indices'] = [7, 7, 9, 1]
    assert reconstruct_for_review(row, 'human')['issues'] == ['invalid_source_pair_identity']
