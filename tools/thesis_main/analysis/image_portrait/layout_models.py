"""Frozen layout exports, four yaw phases; no human targets used."""
import argparse
import contextlib
import io
import json
import zipfile
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import torch

from tools.thesis_main.analysis.image_portrait.common import (
    ROOT, BUNDLE, LOCAL, YAW_DEGREES, read_images, save_json,
    pool_spatial, restore_yaw, restore_corners,
)
from tools.thesis_main.analysis.image_portrait.audit_outputs import check_npz


def complete_export(destination, status_path, image_id, model):
    if not destination.exists() or not status_path.exists():
        return False
    try:
        status = json.loads(status_path.read_text(encoding='utf8'))
        if status['image_id'] != image_id or status['model'] != model or status['status'] != 'ok':
            return False
        if sorted(p['yaw'] for p in status['phases'] if p['status']=='ok') != list(YAW_DEGREES):
            return False
        check_npz(destination)
        layers = ['encoder_stage2','encoder_stage4','compressed','refined','shared'] if model=='hohonet' else ['fc','fg_enclosed','fg_extended']
        post_keys = ['cor_id','y_bon_','y_cor_'] if model=='hohonet' else ['corners_extended','corners_enclosed']
        with np.load(destination, allow_pickle=False) as values:
            required = {f'yaw{yaw}__{layer}__{pool}' for yaw in YAW_DEGREES for layer in layers for pool in ['global','regions']}
            required.update(f'yaw{yaw}__post__{key}' for yaw in YAW_DEGREES for key in post_keys)
            return required.issubset(values.files)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, EOFError):
        return False


def guided_branches(calls):
    if len(calls) != 2:
        raise ValueError(f'expected two shared Transformer calls, got {len(calls)}')
    return {'fg_enclosed': calls[0].transpose(0, 2, 1),
            'fg_extended': calls[1].transpose(0, 2, 1)}


def load(name, bi_root):
    if name == 'hohonet':
        from tools.thesis_main.registry.hohonet_feature_backend import load_model
        model, _ = load_model(ROOT/'ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth',
                              ROOT/'config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml')
    else:
        sys.path.insert(0, str(bi_root))
        from unittest.mock import patch
        from models.bi_layout import Bi_Layout
        import torchvision.models
        original = torchvision.models.resnet50
        with patch.object(torchvision.models, 'resnet50', side_effect=lambda **kwargs: original(weights=None)):
            model = Bi_Layout(win_size=16, depth=8, rpe='lr_parameter_mirror',
                              feature_channel=512, height_compression_scale=16)
        checkpoint = torch.load(bi_root/'checkpoints/Bi_Layout_Net/mp3d/mp3d_best_model.pkl',
                                map_location='cpu', weights_only=True)
        model.load_state_dict(checkpoint['net'], strict=True)
        model.eval().cuda()
    model.requires_grad_(False)
    return model


def extract(model, name, tensor):
    features, calls, heights, handles = {}, [], {}, []
    def capture(key):
        def hook(module, inputs, output):
            if isinstance(output, dict):
                output = output['1D']
            features[key] = output.detach().cpu().numpy()
        return hook
    if name == 'hohonet':
        def encoder(module, inputs, outputs):
            for i in (1, 3):
                features[f'encoder_stage{i+1}'] = outputs[i].detach().cpu().numpy()
        handles.append(model.encoder.register_forward_hook(encoder))
        for key, module in [('compressed', model.decoder), ('refined', model.horizon_refine)]:
            handles.append(module.register_forward_hook(capture(key)))
    else:
        handles.append(model.feature_extractor.register_forward_hook(capture('fc')))
        handles.append(model.transformer.register_forward_hook(
            lambda m, i, o: calls.append(o.detach().cpu().numpy())))
        for key, module in [('height_extended', model.linear_ratio_output),
                            ('height_enclosed', model.linear_ratio_output_2)]:
            handles.append(module.register_forward_hook(capture(key)))
    try:
        with torch.inference_mode():
            if name == 'hohonet':
                latent = model.extract_feat(tensor)
                features['shared'] = latent['1D'].detach().cpu().numpy()
                output = model.call_modality('forward', latent)
            else:
                output = model(tensor)
                features.update(guided_branches(calls))
                for key in ('height_extended', 'height_enclosed'):
                    heights[key] = features.pop(key)[0]
            raw = {k: v[0].detach().cpu().numpy() for k, v in output.items()}
            raw.update(heights)
            post, warning = {}, io.StringIO()
            try:
                with contextlib.redirect_stderr(warning):
                    if name == 'hohonet':
                        post = model.call_modality('infer', latent)
                    else:
                        from postprocessing.post_process import post_process
                        from utils.conversion import xyz2uv
                        for head, key in [('extended', 'depth'), ('enclosed', 'new_depth')]:
                            if not (raw[key] > 0).all() or float(raw['ratio'][0]) <= 0:
                                raise ValueError('nonpositive depth or height ratio')
                            xyz = post_process(raw[key][None], type_name='manhattan')[0]
                            ceil = xyz.copy()
                            ceil[:, 1] = -float(raw['ratio'][0])
                            corners = np.stack((xyz2uv(ceil), xyz2uv(xyz)), 1).reshape(-1, 2)
                            post[f'corners_{head}'] = corners * [1024, 512] - .5
            except Exception as exc:
                warning.write(f'{type(exc).__name__}: {exc}')
    finally:
        for handle in handles:
            handle.remove()
    return {k: v[0] for k, v in features.items()}, raw, post, warning.getvalue()


def run(args):
    torch.set_num_threads(4)
    model = load(args.model, args.bi_root)
    out = BUNDLE/'models'/args.model
    out.mkdir(parents=True, exist_ok=True)
    local = LOCAL/args.model
    local.mkdir(parents=True, exist_ok=True)
    rows = read_images()[:args.limit or None]
    for index, row in enumerate(rows):
        image_id = row['image_id']
        destination = out/f'{image_id}.npz'
        status_path = out/f'{image_id}.json'
        if not args.overwrite and complete_export(destination, status_path, image_id, args.model):
            continue
        status = dict(image_id=image_id, model=args.model, yaw_degrees=list(YAW_DEGREES), phases=[])
        arrays = {}
        rgb = np.asarray(Image.open(ROOT/row['path']).convert('RGB').resize((1024, 512), Image.Resampling.BILINEAR), dtype=np.float32)/255
        tensor = torch.from_numpy(rgb.transpose(2,0,1).copy())[None].cuda()
        for yaw in YAW_DEGREES:
            phase_arrays = {}
            try:
                features, raw, post, warning = extract(model, args.model, tensor.roll(yaw*1024//360, -1))
                raw_local = {}
                for layer, feature in features.items():
                    raw_local[layer] = feature
                    global_pool, regions = pool_spatial(restore_yaw(feature, yaw))
                    phase_arrays[f'yaw{yaw}__{layer}__global'] = global_pool
                    phase_arrays[f'yaw{yaw}__{layer}__regions'] = regions
                    if layer == 'shared' and yaw == 0:
                        phase_arrays['legacy_single_phase_mean'] = feature.mean(-1).astype(np.float32)
                for key, value in raw.items():
                    if not np.isfinite(value).all():
                        raise ValueError(f'nonfinite {key}')
                    phase_arrays[f'yaw{yaw}__raw__{key}'] = restore_yaw(value, yaw) if value.shape[-1] > 1 else value
                for key, value in post.items():
                    if not np.isfinite(value).all():
                        raise ValueError(f'nonfinite postprocessed {key}')
                    phase_arrays[f'yaw{yaw}__post__{key}'] = restore_corners(value, yaw) if key == 'cor_id' or key.startswith('corners_') else restore_yaw(value, yaw)
                np.savez_compressed(local/f'{image_id}_yaw{yaw}.npz', **raw_local)
                arrays.update(phase_arrays)
                required = {'cor_id','y_bon_','y_cor_'} if args.model=='hohonet' else {'corners_extended','corners_enclosed'}
                post_ok = required.issubset(post)
                status['phases'].append(dict(yaw=yaw, status='ok' if post_ok else 'postprocess_failed',
                    forward_status='ok', postprocess_status='ok' if post_ok else 'failed', postprocess_warning=warning))
            except Exception as exc:
                status['phases'].append(dict(yaw=yaw, status='failed', error=f'{type(exc).__name__}: {exc}'))
        np.savez_compressed(destination, **arrays)
        status['status'] = 'ok' if all(p['status']=='ok' for p in status['phases']) else 'partial_or_failed'
        save_json(status_path, status)
        print(f'{args.model} {index+1}/{len(rows)} {image_id} {status["status"]}', flush=True)
    save_json(out/'run_config.json', dict(model=args.model, precision='float32', frozen=True,
        input_hw=[512,1024], resize='PIL.Image.Resampling.BILINEAR', input_rgb_range=[0,1],
        yaw_degrees=list(YAW_DEGREES), aligned_to_original=True,
        legacy_mean_semantics='old pooling on current preprocessing; archived historical values are in history/',
        feature_pool='channel mean/std global and 16 equal azimuth sectors',
        bi_head_order=['enclosed','extended'] if args.model=='bilayout' else None,
        raw_spatial_local_only=True, requested_count=len(rows)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['hohonet','bilayout'], required=True)
    parser.add_argument('--bi-root', type=Path, default=Path('D:/Work/Manhattan_3D/Bi_layout'))
    parser.add_argument('--limit', type=int)
    parser.add_argument('--overwrite', action='store_true')
    run(parser.parse_args())
