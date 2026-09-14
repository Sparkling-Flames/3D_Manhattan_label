"""冻结现代模型提取器；权重、空间大数组仅保存在本地 output。"""
from __future__ import annotations

import argparse
import json
import sys
import subprocess
import time
from zipfile import BadZipFile
from importlib.metadata import version
from pathlib import Path

import numpy as np
from PIL import Image

from tools.thesis_main.analysis.image_portrait.common import cube_faces, pool_spatial

ROOT = Path(__file__).resolve().parents[4]
LOCAL = ROOT / 'output/image_portrait_20260914_v1'
BUNDLE = ROOT / 'analysis_results/image_portrait_20260914_v1'
DINO_LAYERS = (3, 6, 9, 11, 12)
DA3_LAYERS = (5, 7, 9, 11)


def aligned_yaw(array: np.ndarray, yaw: int) -> np.ndarray:
    """Undo the positive input roll, keeping fractional predictions unchanged."""
    if yaw not in (0, 90, 180, 270) or array.shape[-1] % 4:
        raise ValueError('Yaw must be a quarter turn and width divisible by four')
    return np.roll(array, -yaw * array.shape[-1] // 360, axis=-1)


def summarize(features: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    result = {}
    complete_da3 = any('out_layer_' in key for key in features)
    for key, value in features.items():
        if complete_da3 and 'feat_layer_' in key:
            continue
        value = np.asarray(value, dtype=np.float32)
        if not np.isfinite(value).all():
            raise ValueError(f'Nonfinite feature: {key}')
        if value.ndim == 1:
            result[key + '_global'] = value
        else:
            result[key + '_global'], result[key + '_local16'] = pool_spatial(value)
    return result


def tensor(rgb, device, normalize=False):
    import torch
    x = torch.from_numpy(np.array(rgb, copy=True)).permute(2, 0, 1).float()[None] / 255
    if normalize:
        x = (x - torch.tensor([.485, .456, .406])[None, :, None, None]) / torch.tensor([.229, .224, .225])[None, :, None, None]
    return x.to(device)


def load_ulayout(device):
    from collections import defaultdict
    from typing import Any
    import torch
    import torchvision.models
    from omegaconf import DictConfig
    from omegaconf.base import ContainerMetadata, Metadata
    from omegaconf.nodes import AnyNode
    sys.path.insert(0, str(LOCAL / 'ulayout-src'))
    from model.Swim_Transformer.lgt_net import LGT_Net
    # Official constructor requests ImageNet weights, but the complete checkpoint replaces them.
    # Suppress that redundant download; strict checkpoint loading remains mandatory.
    original = torchvision.models.resnet50
    torchvision.models.resnet50 = lambda **kw: original(weights=None)
    try:
        model = LGT_Net(output_name='Horizon', decoder_name='SWG_Transformer', win_size=16, depth=8, dropout=0., ape='lr_parameter')
    finally:
        torchvision.models.resnet50 = original
    # Static checkpoint inspection found only these OmegaConf metadata containers.
    # Keep restricted deserialization; never enable arbitrary pickle execution.
    with torch.serialization.safe_globals([Metadata, Any, defaultdict, dict, ContainerMetadata, DictConfig, AnyNode]):
        state = torch.load(LOCAL / 'best_mp3d.pth', map_location='cpu', weights_only=True)
    model.load_state_dict(state['state_dict'], strict=True)
    model.eval().requires_grad_(False).to(device)
    return model


def ulayout(model, rgb, device):
    import torch
    features, geometry = {}, {}
    rgb = np.asarray(Image.fromarray(rgb).resize((1024, 512), Image.Resampling.BICUBIC))
    captures = {}
    handles = [model.feature_extractor.register_forward_hook(lambda m, i, o: captures.update(compressed=o)),
               model.transformer.register_forward_hook(lambda m, i, o: captures.update(transformer=o.transpose(1, 2)))]
    try:
        with torch.inference_mode():
            for yaw in (0, 90, 180, 270):
                bon, cor = model(tensor(np.roll(rgb, yaw * 1024 // 360, axis=1), device))
                for key, value in captures.items():
                    features[f'yaw{yaw}_{key}'] = aligned_yaw(value[0].float().cpu().numpy(), yaw)
                geometry[f'yaw{yaw}_boundary_radians'] = aligned_yaw(bon[0].float().cpu().numpy(), yaw)
                geometry[f'yaw{yaw}_boundary_pixels_float'] = (geometry[f'yaw{yaw}_boundary_radians'] / np.pi + .5) * 512
                geometry[f'yaw{yaw}_boundary_pixels_official_round'] = np.rint(geometry[f'yaw{yaw}_boundary_pixels_float']).astype(np.int32)
                geometry[f'yaw{yaw}_corner_logits'] = aligned_yaw(cor[0].float().cpu().numpy(), yaw)
    finally:
        for handle in handles:
            handle.remove()
    return features, geometry


def load_dinov3(device):
    import torch
    hf_dir = LOCAL / 'dinov3-hf'
    if (hf_dir / 'model.safetensors').is_file():
        from transformers import DINOv3ViTModel
        model, info = DINOv3ViTModel.from_pretrained(hf_dir, local_files_only=True, output_loading_info=True)
        if any(info.get(key) for key in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')):
            raise ValueError(f'DINOv3 strict load failed: {info}')
        if model.config.num_hidden_layers != 12 or model.config.hidden_size != 768 or model.config.patch_size != 16:
            raise ValueError('Expected DINOv3 ViT-B/16 architecture')
        return model.eval().requires_grad_(False).to(device)
    weights = LOCAL / 'dinov3-weights/dinov3_vitb16_pretrain_lvd1689m.pth'
    if not weights.is_file():
        raise FileNotFoundError(f'Official licensed DINOv3 weights required: {weights}')
    # Import only the backbone: hubconf also imports unrelated segmentation dependencies.
    sys.path.insert(0, str(LOCAL / 'dinov3-src'))
    from dinov3.hub.backbones import dinov3_vitb16
    model = dinov3_vitb16(pretrained=False)
    model.load_state_dict(torch.load(weights, map_location='cpu', weights_only=True), strict=True)
    return model.eval().requires_grad_(False).to(device)


def dinov3(model, rgb, device):
    import torch
    faces, _ = cube_faces(rgb, size=512)
    views = {'panorama': np.asarray(Image.fromarray(rgb).resize((1024, 512), Image.Resampling.BICUBIC)), **faces}
    features = {}
    with torch.inference_mode():
        for name, view in views.items():
            x = tensor(view, device, normalize=True)
            if hasattr(model, 'get_intermediate_layers'):
                values = model.get_intermediate_layers(x, n=[x - 1 for x in DINO_LAYERS], reshape=True, return_class_token=True, norm=True)
            else:
                captures, handles = {}, []
                def capture(layer):
                    def hook(module, inputs, output):
                        captures[layer] = model.norm(output)
                    return hook
                for layer in DINO_LAYERS:
                    handles.append(model.layer[layer - 1].register_forward_hook(capture(layer)))
                try:
                    model(pixel_values=x)
                    values = []
                    for layer in DINO_LAYERS:
                        output = captures[layer]
                        patch = output[:, 1 + model.config.num_register_tokens:]
                        patch = patch.reshape(1, x.shape[-2] // 16, x.shape[-1] // 16, 768).permute(0, 3, 1, 2)
                        values.append((patch, output[:, 0]))
                finally:
                    for handle in handles:
                        handle.remove()
            for layer, (patch, cls) in zip(DINO_LAYERS, values, strict=True):
                features[f'{name}_block{layer}_patch'] = patch[0].float().cpu().numpy()
                if layer == 12:
                    features[f'{name}_block12_cls'] = cls[0].float().cpu().numpy()
    return features, {}


def load_da3(device):
    from safetensors.torch import load_file
    sys.path.insert(0, str(LOCAL / 'da3-src/src'))
    from depth_anything_3.cfg import create_object, load_config
    config = load_config(str(LOCAL / 'da3-src/src/depth_anything_3/configs/da3-small.yaml'))
    model = create_object(config)
    state = load_file(str(LOCAL / 'da3-weights/model.safetensors'))
    if not all(key.startswith('model.') for key in state):
        raise ValueError('Unexpected DA3 official state dict namespace')
    state = {key[6:]: value for key, value in state.items()}
    # Safetensors removes duplicate storage. DA3 reuses one LayerNorm across four
    # auxiliary heads; restore only aliases proven to be the identical Parameter.
    aliases = {}
    for name, parameter in model.named_parameters(remove_duplicate=False):
        if name in state:
            aliases[id(parameter)] = state[name]
    for name, parameter in model.named_parameters(remove_duplicate=False):
        if name not in state and id(parameter) in aliases:
            state[name] = aliases[id(parameter)]
    model.load_state_dict(state, strict=True)
    return model.eval().requires_grad_(False).to(device)


def da3_views(model, views, device):
    import torch
    from unittest.mock import patch
    from depth_anything_3.utils.io.input_processor import InputProcessor
    from depth_anything_3.model.dinov2 import vision_transformer
    x, _, _ = InputProcessor()(views, process_res=504, sequential=True)
    if x.ndim == 4:
        x = x[None]
    selected = []
    head_features = {}
    def capture_head_inputs(module, inputs, output):
        for layer, pair in zip(DA3_LAYERS, output[0], strict=True):
            head_features[layer] = pair[0][0].detach().float().cpu().numpy()
    handle = model.backbone.register_forward_hook(capture_head_inputs)
    original_select = vision_transformer.select_reference_view
    def capture_reference(*args, **kwargs):
        result = original_select(*args, **kwargs)
        selected.append(int(result.item()))
        return result
    try:
        with patch.object(vision_transformer, 'select_reference_view', side_effect=capture_reference):
            with torch.inference_mode(), torch.autocast(device_type=device, dtype=torch.bfloat16, enabled=device == 'cuda'):
                result = model(x.to(device), export_feat_layers=list(DA3_LAYERS))
    finally:
        handle.remove()
    if len(selected) > 1:
        raise ValueError('Unexpected multiple reference selections')
    geometry = {k: v[0].float().cpu().numpy() for k, v in result.items() if torch.is_tensor(v)}
    features = {}
    for key, value in result['aux'].items():
        if selected:
            value = restore_reference_order(value, selected[0])
        for i, view in enumerate(value[0]):
            features[f'view{i}_{key}'] = view.float().cpu().numpy().transpose(2, 0, 1)
    for layer, values in head_features.items():
        for i, value in enumerate(values):
            if value.shape != (36 * 36, 768):
                raise ValueError(f'Unexpected complete DA3 out layer shape: {value.shape}')
            features[f'view{i}_out_layer_{layer}'] = value.reshape(36, 36, 768).transpose(2, 0, 1)
            np.testing.assert_array_equal(features[f'view{i}_out_layer_{layer}'][384:], features[f'view{i}_feat_layer_{layer}'])
    geometry['reference_view_index'] = np.asarray(selected or [0], dtype=np.int32)
    validate_da3_geometry(geometry, len(views))
    return features, geometry


def restore_reference_order(values, reference):
    """Official DA3 aux tensors need inverse view permutation; geometry already restored."""
    if values.shape[0] != 1 or not 0 <= reference < values.shape[1]:
        raise ValueError('Expected one batch with valid reference index')
    forward = [reference] + [i for i in range(values.shape[1]) if i != reference]
    return values[:, np.argsort(forward).tolist()]


def raw_features(features):
    # Full DA3 768-channel head input contains the exact normalized 384-channel
    # aux in its final half, verified at extraction. Do not duplicate raw storage.
    complete_da3 = any('out_layer_' in key for key in features)
    return {key: value.astype(np.float16) for key, value in features.items()
            if not (complete_da3 and 'feat_layer_' in key)}


def compact_da3_aux():
    """Losslessly remove redundant pooled aux from already-complete v2 exports."""
    report = dict(compacted_files=0, removed_bytes=0, legacy_or_unreadable_files=[], all_aux_bitwise_equal=True)
    columns = np.r_[384:768, 1152:1536]
    for path in sorted((BUNDLE / 'models/da3').rglob('*.features.npz')):
        try:
            with np.load(path, allow_pickle=False) as archive:
                arrays = {key: archive[key] for key in archive.files}
        except (OSError, ValueError, BadZipFile):
            report['legacy_or_unreadable_files'].append(str(path.relative_to(BUNDLE)))
            continue
        aux_keys = [key for key in arrays if 'feat_layer_' in key]
        if not aux_keys:
            continue
        if int(arrays.get('feature_schema_version', 0)) != 2:
            report['legacy_or_unreadable_files'].append(str(path.relative_to(BUNDLE)))
            continue
        for key in aux_keys:
            full = arrays[key.replace('feat_layer_', 'out_layer_')]
            if full[..., columns].tobytes() != arrays[key].tobytes():
                raise ValueError(f'Aux bitwise reconstruction mismatch: {path.name}:{key}')
        before = path.stat().st_size
        temporary = path.with_suffix('.tmp.npz')
        np.savez_compressed(temporary, **{key: value for key, value in arrays.items() if key not in aux_keys})
        temporary.replace(path)
        report['compacted_files'] += 1
        report['removed_bytes'] += before - path.stat().st_size
    (BUNDLE / 'models/da3/aux_compaction_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8', newline='\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'legacy_or_unreadable_files'}), flush=True)


def da3(model, rgb, device):
    faces, _ = cube_faces(rgb, size=512)
    features, geometry = {}, {}
    for name, face in faces.items():
        f, g = da3_views(model, [face], device)
        features.update({name + '_' + k: v for k, v in f.items()})
        geometry.update({name + '_' + k: v for k, v in g.items()})
    return features, geometry


def sampled_geometry(geometry):
    """Retain depth sample coordinates in the original processed camera grid."""
    result = {}
    for key, value in geometry.items():
        if value.ndim >= 3 and value.shape[-2] > 32:
            result[key + '_source_shape'] = np.asarray(value.shape)
            result[key + '_stride8'] = value[..., ::8, ::8]
            result[key + '_sample_x'] = np.arange(0, value.shape[-1], 8, dtype=np.float32)
            result[key + '_sample_y'] = np.arange(0, value.shape[-2], 8, dtype=np.float32)
        else:
            result[key] = value
    return result


def validate_da3_geometry(geometry, views):
    depth, poses, cameras = (geometry[k] for k in ('depth', 'extrinsics', 'intrinsics'))
    if depth.ndim != 3 or depth.shape[0] != views or poses.shape != (views, 3, 4) or cameras.shape != (views, 3, 3):
        raise ValueError('Invalid depth/camera shape')
    if geometry['depth_conf'].shape != depth.shape:
        raise ValueError('Confidence/depth shape mismatch')
    if not all(np.isfinite(v).all() for v in geometry.values()) or not (depth > 0).all():
        raise ValueError('Nonfinite output or nonpositive depth')
    if np.any(np.abs(np.linalg.det(cameras)) < 1e-8) or np.any(np.abs(np.linalg.det(poses[:, :3, :3])) < 1e-8):
        raise ValueError('Singular predicted camera')


def camera_consistency(geometry):
    """Unconstrained twelve-camera predictions checked against known six-face geometry."""
    _, projection = cube_faces(np.zeros((32, 64, 3), np.uint8), size=2)
    known = np.asarray([projection['camera_to_panorama'][name] for name in projection['order']])
    rotations = geometry['extrinsics'][:, :3, :3]
    translations = geometry['extrinsics'][:, :3, 3]
    centers = -np.linalg.solve(rotations, translations[..., None])[..., 0]
    panorama_rotations = np.linalg.inv(rotations) @ np.tile(known.transpose(0, 2, 1), (2, 1, 1))
    centers = centers.reshape(2, 6, 3)
    pano = panorama_rotations.reshape(2, 6, 3, 3)
    relative = pano[:, :, None].transpose(0, 1, 2, 4, 3) @ pano[:, None]
    angles = np.arccos(np.clip((np.trace(relative, axis1=-2, axis2=-1) - 1) / 2, -1, 1))
    return dict(same_capture_center_distances=np.linalg.norm(centers[:, :, None] - centers[:, None], axis=-1).astype(np.float32),
                same_capture_panorama_rotation_degrees=np.rad2deg(angles).astype(np.float32))


def reusable(feature_path, geometry_path, members, model, multiview=False, require_full_layers=True):
    """Validate identities and required numerical fields before resuming."""
    if not feature_path.is_file() or not geometry_path.is_file():
        return False
    if model == 'ulayout':
        bases = [f'yaw{yaw}_{layer}' for yaw in (0, 90, 180, 270) for layer in ('compressed', 'transformer')]
        required = [f'yaw{yaw}_{key}' for yaw in (0, 90, 180, 270) for key in ('boundary_radians','boundary_pixels_float','boundary_pixels_official_round','corner_logits')]
    elif model == 'da3':
        names = [f'view{i}' for i in range(12)] if multiview else [f'{face}_view0' for face in ('front', 'right', 'back', 'left', 'up', 'down')]
        kind = 'out_layer' if require_full_layers else 'feat_layer'
        bases = [f'{name}_{kind}_{layer}' for name in names for layer in DA3_LAYERS]
        geometry_keys = ['depth_stride8','depth_conf_stride8','depth_sample_x','depth_sample_y','intrinsics','extrinsics']
        required = geometry_keys + ['reprojection_candidates','same_capture_center_distances','same_capture_panorama_rotation_degrees'] if multiview else [f'{face}_{key}' for face in ('front','right','back','left','up','down') for key in geometry_keys]
    else:
        bases = [f'{name}_block{layer}_patch' for name in ('panorama','front','right','back','left','up','down') for layer in DINO_LAYERS]
        required = ['source_shape_hw']
    try:
        with np.load(feature_path, allow_pickle=False) as features, np.load(geometry_path, allow_pickle=False) as geometry:
            if features['image_ids'].tolist() != list(members) or geometry['image_ids'].tolist() != list(members):
                return False
            if model == 'da3' and require_full_layers and ('feature_schema_version' not in features or int(features['feature_schema_version']) != 2):
                return False
            if not all(key in geometry for key in required):
                return False
            if not all(base + '_global' in features and base + '_local16' in features for base in bases):
                return False
            if not all(features[base + '_local16'].shape == (16, features[base + '_global'].size) for base in bases):
                return False
            channels = 2048 if model == 'ulayout' else 768 if model == 'da3' and not require_full_layers else 1536
            if any(features[base + '_global'].shape != (channels,) for base in bases):
                return False
            if model == 'ulayout' and any(geometry[f'yaw{yaw}_boundary_radians'].shape != (2, 1024) for yaw in (0,90,180,270)):
                return False
            if model == 'dinov3' and any(f'{name}_block12_cls_global' not in features for name in ('panorama','front','right','back','left','up','down')):
                return False
            if model == 'da3':
                prefixes = [''] if multiview else [face + '_' for face in ('front','right','back','left','up','down')]
                count = 12 if multiview else 1
                for prefix in prefixes:
                    depth, cameras, poses = (geometry[prefix + key] for key in ('depth_stride8','intrinsics','extrinsics'))
                    if depth.shape != (count, 63, 63) or cameras.shape != (count, 3, 3) or poses.shape != (count, 3, 4):
                        return False
                    if not (depth > 0).all() or np.any(np.abs(np.linalg.det(cameras)) < 1e-8) or np.any(np.abs(np.linalg.det(poses[:,:3,:3])) < 1e-8):
                        return False
                if multiview and (geometry['reprojection_candidates'].ndim != 2 or geometry['reprojection_candidates'].shape[1] != 10):
                    return False
            return all(np.isfinite(data[key]).all() for data in (features, geometry) for key in data.files if key != 'image_ids')
    except (OSError, ValueError, KeyError, EOFError, BadZipFile):
        return False


def depth_reprojections(depth, extrinsics, intrinsics):
    """Cross-position geometric candidates, not observed visual correspondences.

    Sampled pixel centers keep original coordinates; nearest target depth verifies
    occlusion consistency. Both all-projectable and <=5% depth-agreement masks
    are retained so cloud analysis can change the exploratory tolerance.
    """
    if len(depth) != 12:
        raise ValueError('Expected two panorama positions, six faces each')
    records = []
    for source in range(12):
        yy, xx = np.mgrid[0:depth.shape[-2]:8, 0:depth.shape[-1]:8]
        z = depth[source, yy, xx].ravel()
        pixels = np.stack((xx.ravel(), yy.ravel(), np.ones(z.size)))
        camera = np.linalg.solve(intrinsics[source], pixels) * z
        ext = extrinsics[source]
        world = np.linalg.solve(ext[:3, :3], camera - ext[:3, 3:4])
        for target in range(6 if source < 6 else 0, 12 if source < 6 else 6):
            ext = extrinsics[target]
            target_camera = ext[:3, :3] @ world + ext[:3, 3:4]
            uvz = intrinsics[target] @ target_camera
            with np.errstate(divide='ignore', invalid='ignore'):
                uv = uvz[:2] / uvz[2:3]
            inside = (np.isfinite(uv).all(0) & np.isfinite(z) & (z > 0) &
                      (target_camera[2] > 0) & (uv[0] >= 0) &
                      (uv[0] < depth.shape[-1] - .5) & (uv[1] >= 0) &
                      (uv[1] < depth.shape[-2] - .5))
            indices = np.flatnonzero(inside)
            if not indices.size:
                continue
            xy = np.rint(uv[:, indices]).astype(int)
            reference = depth[target, xy[1], xy[0]]
            relative = np.abs(target_camera[2, indices] - reference) / np.maximum(np.abs(reference), 1e-6)
            records.append(np.column_stack((np.full(indices.size, source), pixels[:2, indices].T,
                           np.full(indices.size, target), uv[:, indices].T,
                           target_camera[2, indices], reference, relative,
                           np.isfinite(reference) & (reference > 0) & (relative <= .05))))
    return np.concatenate(records).astype(np.float32) if records else np.empty((0, 10), np.float32)


def supported_pairs(relations):
    """Fixed adjacent chain per supported display group; no output-based selection."""
    pairs = {}
    for row in relations:
        if row['relation_status'] != 'supported':
            continue
        members = sorted(set(row['image_ids']))
        for pair in zip(members, members[1:]):
            pairs.setdefault(pair, []).append(row['review_code'])
    return sorted(pairs.items())


def run_pairs(model, rows, device, limit=None):
    image_rows = {r['image_id']: r for r in rows}
    relations = [json.loads(line) for line in (BUNDLE / 'metadata/relationships.jsonl').read_text(encoding='utf-8').splitlines()]
    components = [json.loads(line) for line in (BUNDLE / 'evaluation/room_components.jsonl').read_text(encoding='utf-8').splitlines()]
    membership = {image: component for component in components for image in component['image_ids']}
    pairs = supported_pairs(relations)
    if limit:
        pairs = pairs[:limit]
    destination = BUNDLE / 'models/da3/multiview'
    raw_dir = LOCAL / 'raw/da3/multiview'
    destination.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    (destination / 'run_status.json').write_text(json.dumps(dict(status='running', expected_pairs=len(pairs)), indent=2), encoding='utf-8', newline='\n')
    status = []
    for number, (members, groups) in enumerate(pairs):
        started = time.monotonic()
        pair_id = f'pair{number:04d}'
        row = dict(pair_id=pair_id, image_ids=list(members), review_codes=groups,
                   face_order=['front', 'right', 'back', 'left', 'up', 'down'],
                   condition='two_capture_positions_twelve_faces')
        row['room_components'] = [dict(room_id=membership[image]['room_id'], status=membership[image]['status']) for image in members]
        row['main_room_evaluation_eligible'] = all(item['status'] == 'supported_component' for item in row['room_components'])
        try:
            if reusable(destination / (pair_id + '.features.npz'), destination / (pair_id + '.geometry.npz'), members, 'da3', multiview=True):
                row['status'] = 'reused'
            else:
                preserve_geometry = reusable(destination / (pair_id + '.features.npz'), destination / (pair_id + '.geometry.npz'), members, 'da3', multiview=True, require_full_layers=False)
                views = []
                for image_id in members:
                    rgb = np.asarray(Image.open(ROOT / image_rows[image_id]['path']).convert('RGB'))
                    faces, _ = cube_faces(rgb, size=512)
                    views.extend(faces.values())
                features, geometry = da3_views(model, views, device)
                if preserve_geometry:
                    with np.load(raw_dir / (pair_id + '.npz'), allow_pickle=False) as old:
                        geometry = {key: old[key] for key in geometry}
                np.savez(raw_dir / (pair_id + '.npz'), **raw_features(features), **geometry)
                np.savez_compressed(destination / (pair_id + '.features.npz'), image_ids=np.asarray(members), feature_schema_version=np.asarray(2), **summarize(features))
                sampled = sampled_geometry(geometry)
                sampled['reprojection_candidates'] = depth_reprojections(geometry['depth'], geometry['extrinsics'], geometry['intrinsics'])
                sampled.update(camera_consistency(geometry))
                if not preserve_geometry:
                    np.savez_compressed(destination / (pair_id + '.geometry.npz'), image_ids=np.asarray(members), **sampled)
                row['geometry_reused_for_feature_upgrade'] = preserve_geometry
                row['status'] = 'ok'
            with np.load(destination / (pair_id + '.geometry.npz'), allow_pickle=False) as saved:
                count = len(saved['reprojection_candidates'])
            row.update(forward_status='ok', correspondence_status='projectable_candidates' if count else 'no_overlap_unusable',
                       projectable_candidates=count)
            if not count:
                row['status'] = 'forward_ok_correspondence_unusable'
        except Exception as exc:
            row.update(status='failed', error=repr(exc))
        row['elapsed_seconds'] = round(time.monotonic() - started, 3)
        status.append(row)
        (destination / 'status.json').write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding='utf-8', newline='\n')
        print(f'da3 pair {number+1}/{len(pairs)} {row["status"]}', flush=True)
    summary = dict(status='completed_with_failures' if any(r['status'] == 'failed' for r in status) else 'complete',
                   expected_pairs=len(pairs), successful_pairs=sum(r.get('forward_status') == 'ok' for r in status),
                   pairs_with_projectable_candidates=sum(r.get('correspondence_status') == 'projectable_candidates' for r in status),
                   failed_pairs=sum(r['status'] == 'failed' for r in status))
    (destination / 'run_status.json').write_text(json.dumps(summary, indent=2), encoding='utf-8', newline='\n')


def manifest(model, device):
    source = {'ulayout': 'https://github.com/JonathanLee112/uLayout', 'dinov3': 'https://github.com/facebookresearch/dinov3', 'da3': 'https://github.com/ByteDance-Seed/Depth-Anything-3'}[model]
    revision = subprocess.check_output(['git', '-C', str(LOCAL / (model + '-src')), 'rev-parse', 'HEAD'], text=True).strip()
    _, projection = cube_faces(np.zeros((32, 64, 3), dtype=np.uint8), size=512)
    projection.pop('source_shape_hw')
    widths = {'ulayout': [256], 'dinov3': [32, 64], 'da3': [36]}[model]
    intervals = {str(width): [[int(part[0]), int(part[-1]) + 1] for part in np.array_split(np.arange(width), 16)] for width in widths}
    return dict(model=model, source=source, revision=revision, frozen=True, device=device,
                runtime_versions={name: version(name) for name in ('torch','torchvision','numpy','safetensors','transformers')},
                dinov3_backend=('Transformers DINOv3ViTModel' if (LOCAL / 'dinov3-hf/model.safetensors').is_file() else 'Meta dinov3.hub.backbones.dinov3_vitb16; restricted local torch.load; strict state_dict loading'),
                inference_dtype='bfloat16 autocast' if model == 'da3' and device == 'cuda' else 'float32',
                feature_storage_dtype='raw float16, pooled float32', geometry_dtype='float32',
                local_raw_container='Early raw NPZ files use compression; later raw NPZ are uncompressed for speed. Numerical values/dtypes and numpy.load interface identical; cloud NPZ always compressed.',
                candidates={'dinov3': list(DINO_LAYERS), 'da3': list(DA3_LAYERS), 'ulayout': ['compressed', 'transformer']},
                projection=projection, layer_indexing='DA3 zero-based; DINOv3 one-based',
                input_resize='uLayout panorama 1024x512 PIL BICUBIC; DINO panorama same and cubefaces512; DA3 cubefaces512 then official processor504',
                checkpoint_source={'ulayout':'https://drive.google.com/file/d/19PKz_VRkUPcJgxTmjL5jQVaNPqEups5I/view','da3':'https://huggingface.co/depth-anything/DA3-SMALL','dinov3':('https://huggingface.co/facebook/dinov3-vitb16-pretrain-lvd1689m' if (LOCAL / 'dinov3-hf/model.safetensors').is_file() else 'Meta official licensed download: dinov3_vitb16_pretrain_lvd1689m-73cec8be.pth')}[model],
                ulayout_postprocess='official radians -> pixel float -> round; official wrapper corner field is GT and is deliberately NOT exported; predicted corners unavailable',
                ulayout_corner_logits='Raw unused second model return; official training wrapper optimizes boundaries and ignores corner return. Do not interpret these logits as calibrated/trained corner confidence.',
                yaw='No yaw augmentation; panorama plus six fixed cubefaces' if model == 'dinov3' else 'input rolled +yaw, features and boundaries rolled -yaw to original coordinates',
                feature_fields='Spatial feature keys have global mean+population std(ddof=0) (2C), local16 image-x token bands (16,2C). DINO CLS is the direct768-vector, not mean+std. Cubeface bands use each perspective image own x, NOT panorama azimuth; up/down faces especially cannot be treated as ERP azimuth. Reproject via saved face rotation/K; compare projection conditions separately.',
                region_split_rule='numpy.array_split(token_width,16): remainder goes to earliest bands. DA3 W36 first4 bands have3 tokens, remaining12 have2. Equal width only if width divisible by16; no equal-angle claim.',
                region_token_intervals_half_open=intervals,
                feature_token_shapes={'ulayout':{'compressed':[1024,256],'transformer':[1024,256]},'dinov3':{'panorama_patch':[768,32,64],'cubeface_patch':[768,32,32],'cls':[768]},'da3':{'complete_out_layer':[768,36,36],'derived_aux_global_stream':[384,36,36]}}[model],
                geometry_sampling='DA3 stride8 retains original pixel coordinates and full-resolution intrinsics; no scaled intrinsics needed.',
                da3_processed_to_cube_pixel='512->504 official INTER_AREA resize; cube coordinate=(processed_coordinate+0.5)*512/504-0.5 for both axes. Cubeface ray geometry uses projection.intrinsics in 512 coordinates.',
                da3_scale='Relative depth and predicted poses, no metric scale claim. Each single-face inference has independent arbitrary scale; jointly inferred twelve-face conditions need not share the single-face scales. Align scale per corresponding face before single/multiview depth comparison. Camera intrinsics are predictions; known projection intrinsics separately retained.',
                da3_multiview_cameras='Twelve independently predicted cameras: no same-center or known six-face rotation constraints imposed. Two source capture positions do not imply physically verified two-pose output; same-capture center/rotation diagnostic matrices exported.',
                da3_aux_identity='Official backbone restores main outputs but not exported aux after reference selection. Adapter records reference_view_index and applies inverse permutation only to aux; geometry remains in official original input order.',
                da3_feature_schema_version=2,
                da3_layer_semantics='Primary out_layer_5/7/9/11: complete 768-channel decoder input [384 local,384 normalized global], already restored by official backbone. Official feat_layer_* aux is exactly last384 channels; duplicate storage omitted after equality validation. Raw aux=out_layer_[384:]; pooled global aux=concatenate(full[384:768],full[1152:1536]); local16 uses same column indices. All information retained without duplicate aux arrays.',
                geometric_validity='Finite/invertible predictions do not imply source-image visibility. Blur/occlusion may still receive predicted geometry and confidence; do not treat these as observed visual evidence.',
                multiview_pairing='lexicographically adjacent image_id chain per supported relationship group, deduplicated; review_codes retained, not independent rooms',
                reprojection_columns=['source_face','source_x','source_y','target_face','target_x','target_y','projected_depth','target_depth','relative_depth_error','depth_agreement_5pct'],
                reprojection_meaning='Predicted geometric candidates only, not image-observed matches; projected finite positive depths in bounds; agreement masks are exploratory, not GT.')


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--model', choices=('ulayout', 'dinov3', 'da3'), required=True)
    parser.add_argument('--device', choices=('cuda', 'cpu'), default='cuda')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--multiview', action='store_true')
    parser.add_argument('--compact-aux', action='store_true')
    args = parser.parse_args()
    if args.compact_aux:
        if args.model != 'da3':
            raise ValueError('Aux compaction is DA3 only')
        compact_da3_aux()
        return
    import torch
    torch.set_num_threads(4)
    rows = [json.loads(line) for line in (BUNDLE / 'metadata/images.jsonl').read_text(encoding='utf-8').splitlines()]
    if args.limit and not args.multiview:
        rows = rows[:args.limit]
    destination = BUNDLE / 'models' / args.model
    raw_dir = LOCAL / 'raw' / args.model
    destination.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    (destination / 'manifest.json').write_text(json.dumps(manifest(args.model, args.device), ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    run_dir = destination / 'multiview' if args.multiview else destination
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / 'run_status.json').write_text(json.dumps(dict(status='loading_model', expected_images=len(rows), multiview=args.multiview), indent=2), encoding='utf-8', newline='\n')
    try:
        model = globals()['load_' + args.model](args.device)
    except Exception as exc:
        blocked = {'status': 'blocked_before_inference', 'error': repr(exc), 'attempted_images': 0,
                   'expected_images': len(rows)}
        (run_dir / 'run_status.json').write_text(json.dumps(blocked, indent=2, ensure_ascii=False), encoding='utf-8', newline='\n')
        raise
    if args.multiview:
        if args.model != 'da3':
            raise ValueError('Multiview is implemented only for DA3')
        run_pairs(model, rows, args.device, args.limit)
        return
    (destination / 'run_status.json').write_text(json.dumps(dict(status='running', expected_images=len(rows)), indent=2), encoding='utf-8', newline='\n')
    status = []
    for i, row in enumerate(rows):
        started = time.monotonic()
        image_id = row['image_id']
        feature_path = destination / f'{image_id}.features.npz'
        geometry_path = destination / f'{image_id}.geometry.npz'
        if reusable(feature_path, geometry_path, [image_id], args.model):
            status.append({'image_id': image_id, 'status': 'reused'})
            continue
        try:
            preserve_geometry = args.model == 'da3' and reusable(feature_path, geometry_path, [image_id], args.model, require_full_layers=False)
            rgb = np.asarray(Image.open(ROOT / row['path']).convert('RGB'))
            features, geometry = globals()[args.model](model, rgb, args.device)
            if not all(np.isfinite(value).all() for value in geometry.values()):
                raise ValueError('Nonfinite geometry output')
            geometry['source_shape_hw'] = np.asarray(rgb.shape[:2])
            if preserve_geometry:
                with np.load(raw_dir / f'{image_id}.npz', allow_pickle=False) as old:
                    geometry = {key: old[key] for key in geometry}
            np.savez(raw_dir / f'{image_id}.npz', **raw_features(features), **geometry)
            summary = summarize(features)
            if args.model == 'da3':
                summary['feature_schema_version'] = np.asarray(2)
            np.savez_compressed(feature_path, image_ids=np.asarray([image_id]), **summary)
            # Raw DA3 depth is local; cloud gets deterministic stride-8 samples and original shape.
            if args.model == 'da3':
                geometry = sampled_geometry(geometry)
            if not preserve_geometry:
                np.savez_compressed(geometry_path, image_ids=np.asarray([image_id]), **geometry)
            status.append({'image_id': image_id, 'status': 'ok', 'geometry_reused_for_feature_upgrade': preserve_geometry})
        except Exception as exc:
            status.append({'image_id': image_id, 'status': 'failed', 'error': repr(exc)})
        status[-1]['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (destination / 'status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
        print(f'{args.model} {i+1}/{len(rows)} {status[-1]}', flush=True)
    (destination / 'status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    summary = dict(status='completed_with_failures' if any(r['status'] == 'failed' for r in status) else 'complete',
                   expected_images=len(rows), successful_images=sum(r['status'] in ('ok', 'reused') for r in status),
                   failed_images=sum(r['status'] == 'failed' for r in status))
    (destination / 'run_status.json').write_text(json.dumps(summary, indent=2), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
