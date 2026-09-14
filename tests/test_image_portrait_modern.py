import numpy as np
import pytest

from tools.thesis_main.analysis.image_portrait.modern_models import aligned_yaw, summarize, depth_reprojections, supported_pairs, sampled_geometry, validate_da3_geometry, camera_consistency, reusable, restore_reference_order


def test_yaw_float_coordinates_and_feature_contract(tmp_path):
    original = np.arange(64, dtype=np.float32).reshape(2, 32) / 7
    for yaw in (0, 90, 180, 270):
        shifted = np.roll(original, yaw * 32 // 360, axis=-1)
        np.testing.assert_array_equal(aligned_yaw(shifted, yaw), original)
    pooled = summarize({'test': original, 'cls': original[:, 0]})
    assert pooled['test_local16'].shape == (16, 4)
    assert pooled['test_global'].shape == (4,)
    assert pooled['cls_global'].shape == (2,)
    path = tmp_path / 'features.npz'
    np.savez_compressed(path, image_ids=np.asarray(['image']), **pooled)
    with np.load(path, allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved['test_local16'], pooled['test_local16'])
    with pytest.raises(ValueError, match='Nonfinite'):
        summarize({'invalid': np.full((2, 32), np.nan)})


def test_multiview_identity_and_original_pixel_coordinates():
    depth = np.ones((12, 40, 40), np.float32) * 2
    poses = np.tile(np.eye(4, dtype=np.float32), (12, 1, 1))
    intrinsics = np.tile(np.eye(3, dtype=np.float32), (12, 1, 1))
    points = depth_reprojections(depth, poses, intrinsics)
    assert points.shape == (12 * 6 * 25, 10)
    np.testing.assert_allclose(points[:, 1:3], points[:, 4:6])
    assert (points[:, 9] == 1).all()
    sampled = sampled_geometry({'depth': depth, 'intrinsics': intrinsics})
    np.testing.assert_array_equal(sampled['depth_sample_x'], [0, 8, 16, 24, 32])
    np.testing.assert_array_equal(sampled['intrinsics'], intrinsics)
    relations = [{'relation_status': 'supported', 'review_code': 'G1', 'image_ids': ['c', 'a', 'b']},
                 {'relation_status': 'pending', 'review_code': 'G2', 'image_ids': ['a', 'd']}]
    assert supported_pairs(relations) == [(('a', 'b'), ['G1']), (('b', 'c'), ['G1'])]
    geometry = dict(depth=depth, depth_conf=depth.copy(), extrinsics=poses[:, :3], intrinsics=intrinsics)
    validate_da3_geometry(geometry, 12)
    diagnostics = camera_consistency(geometry)
    assert diagnostics['same_capture_center_distances'].shape == (2, 6, 6)
    np.testing.assert_array_equal(diagnostics['same_capture_center_distances'], 0)
    geometry['intrinsics'][0] = 0
    with pytest.raises(ValueError, match='Singular'):
        validate_da3_geometry(geometry, 12)


def test_resume_rejects_misbound_and_incomplete_files(tmp_path):
    feature, geometry = tmp_path/'feature.npz', tmp_path/'geometry.npz'
    np.savez_compressed(feature, image_ids=np.asarray(['wrong']))
    np.savez_compressed(geometry, image_ids=np.asarray(['wrong']))
    assert not reusable(feature, geometry, ['requested'], 'ulayout')
    assert not reusable(feature, geometry, ['wrong'], 'ulayout')


def test_da3_aux_reference_order_is_restored():
    original = np.arange(12)[None, :, None]
    for ref in range(12):
        reordered = original[:, [ref] + [i for i in range(12) if i != ref]]
        np.testing.assert_array_equal(restore_reference_order(reordered, ref), original)
