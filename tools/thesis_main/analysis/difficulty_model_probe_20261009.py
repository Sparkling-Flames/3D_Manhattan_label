"""本地HoHoNet重放：记录约束修改、回退和逆yaw对齐的模型稳定性。"""
import argparse
from collections import Counter
from pathlib import Path
import json
import time
from unittest.mock import patch

import numpy as np

from .research_artifact_io import ROOT, read_csv, write_csv, write_json

OUT = ROOT / 'analysis_results/objective_difficulty_20261009/hohonet_probe'
CHECKPOINT = ROOT / 'ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth'
CONFIG = ROOT / 'config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml'
SHIFTS = (0, 256, 512, 768)


def trace_inference(model, tensor, decoder=None):
    from lib.misc import post_proc
    decoder = decoder or post_proc.gen_ww
    calls = []
    def traced(*args, **kwargs):
        output = decoder(*args, **kwargs)
        calls.append(dict(force_cuboid=kwargs['force_cuboid'], peak_count=len(args[0]),
                          walls=output[1]))
        return output
    # 仅截取原解码器实际返回值，不复制后处理规则、不改变推理结果。
    with patch.object(post_proc, 'gen_ww', side_effect=traced):
        output = model.infer(tensor)
    general = next((c for c in calls if not c['force_cuboid']), None)
    actions = Counter(w.get('action', 'cuboid') for w in general['walls']) if general else Counter()
    trace = dict(decoder_calls=len(calls),
        fallback_used=bool(general and any(c['force_cuboid'] for c in calls)),
        raw_peak_count=general['peak_count'] if general else None,
        general_wall_count=len(general['walls']) if general else None,
        general_forced_change_count=actions['forced change'],
        general_forced_infer_count=actions['forced infer'],
        general_actions=dict(actions))
    return output, trace


def boundary_curve(corners, width=1024, height=512):
    from lib.misc.panostretch import pano_connect_points
    points = np.asarray(corners, float)
    if points.ndim != 2 or points.shape[1] != 2 or len(points)%2 or len(points)<8 or not np.isfinite(points).all():
        raise ValueError('invalid_boundary_corners')
    curves = []
    for endpoint, ring in enumerate((points[::2], points[1::2])):
        samples = np.concatenate([pano_connect_points(p, ring[(i+1)%len(ring)], z=-50 if endpoint==0 else 50, w=width, h=height)
                                  for i, p in enumerate(ring)])
        xs = np.rint(samples[:, 0]).astype(int)%width
        sums = np.bincount(xs, weights=samples[:, 1], minlength=width)
        counts = np.bincount(xs, minlength=width)
        if (counts == 0).any() or not np.isfinite(sums).all():
            raise ValueError('incomplete_spherical_boundary')
        low, high = np.full(width, np.inf), np.full(width, -np.inf)
        np.minimum.at(low, xs, samples[:, 1])
        np.maximum.at(high, xs, samples[:, 1])
        if np.max(high-low) > 1e-3:
            raise ValueError('multiple_boundary_values_at_same_yaw')
        curves.append(sums/counts)
    return np.asarray(curves)


def orbit_metrics(phases, shifts, height=512):
    if len(phases) != len(shifts) or not phases or shifts[0] != 0:
        raise ValueError('invalid_orbit')
    bon = np.stack([np.roll(r['y_bon_'], -s, axis=-1) for r, s in zip(phases, shifts)])
    cor = np.stack([np.roll(r['y_cor_'], -s, axis=-1) for r, s in zip(phases, shifts)])
    if not np.isfinite(bon).all() or not np.isfinite(cor).all():
        raise ValueError('nonfinite_raw_predictions')
    counts = [len(r['cor_id'])//2 for r in phases]
    return dict(raw_boundary_rotation_mae_deg=float(np.abs(bon[1:]-bon[0]).mean()*180/height),
        raw_corner_rotation_mae=float(np.abs(cor[1:]-cor[0]).mean()),
        final_pair_count_min=min(counts), final_pair_count_max=max(counts),
        final_pair_count_range=max(counts)-min(counts))


def phase_metrics(output, trace):
    from lib.misc import post_proc
    from shapely.geometry import Polygon, Point
    points = np.asarray(output['cor_id'])
    xy = post_proc.np_coor2xy(points[::2])
    finite = np.isfinite(xy).all()
    polygon = Polygon(xy) if finite and len(xy)>=3 else None
    valid = bool(polygon is not None and polygon.is_valid and polygon.area > 0)
    contains_camera = bool(valid and polygon.covers(Point(511.5, 255.5)))
    correction, correction_status = None, 'not_computable_invalid_final_polygon'
    if valid and contains_camera:
        try:
            fitted = boundary_curve(points)
            correction = float(np.abs(fitted-output['y_bon_']).mean()*180/512)
            correction_status = 'computable'
        except ValueError as exc:
            correction_status = str(exc)
    return dict(trace, final_pair_count=len(points)//2, final_polygon_valid=valid,
        final_polygon_contains_camera=contains_camera, boundary_correction_mae_deg=correction,
        boundary_correction_status=correction_status)


def save_replay(destination, rows, phase_rows, raw, layouts):
    write_csv(destination/'per_image.csv', rows)
    write_csv(destination/'per_phase.csv', [dict(r, general_actions=json.dumps(r.get('general_actions', {}))) for r in phase_rows])
    np.savez_compressed(destination/'raw_predictions.npz', **raw)
    write_json(destination/'layouts.json', layouts)


def image_path(image_id):
    paths = [ROOT/f'data/mp3d_layout/{split}/img/{image_id}.png' for split in ('test', 'valid')]
    available = [p for p in paths if p.exists()]
    if len(available) > 1:
        raise ValueError('ambiguous_model_image_split:' + image_id)
    if available:
        return available[0], 'layout_test_or_valid_png'
    jpeg = ROOT/f'data/mp3d_layout/img_v/{image_id}.jpg'
    return (jpeg, 'annotation_jpeg_fallback') if jpeg.exists() else (None, 'missing_image')


def run(limit=None):
    import torch
    from PIL import Image
    from tools.thesis_main.registry.hohonet_feature_backend import load_model
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    torch.set_num_threads(4)
    net, device = load_model(CHECKPOINT, CONFIG, device='cpu')
    parent = {r['image']: r for r in read_csv(OUT.parent/'stratified/features_and_scores.csv')}
    images = load_current_bundle()['research']['images']
    if limit is not None:
        selected = {r['image'] for r in read_csv(OUT.parent/'stratified/review_candidates.csv')[:limit]}
        images = [r for r in images if r['image_code'] in selected]
    destination = OUT if limit is None else OUT/'pilot'
    destination.mkdir(parents=True, exist_ok=True)
    rows, phase_rows, raw, layouts = [], [], {}, []
    started = time.perf_counter()
    with torch.inference_mode():
        for index, im in enumerate(images):
            code, iid = im['image_code'], im['image_id']
            path, source = image_path(iid)
            row = dict(image=code, image_id=iid, building=im['building_id'], room=im['room_id'],
                scene_stratum=parent[code]['scene_stratum'], subjective_label=parent[code]['subjective_label'],
                image_path=str(path) if path else '', image_source=source,
                archived_pair_count=int(parent[code]['hohonet_offline_pair_count']) if parent[code]['hohonet_offline_pair_count'] else None)
            phases, traces, errors = [], [], []
            if path is not None:
                x = torch.from_numpy(np.asarray(Image.open(path).convert('RGB'), dtype=np.float32)/255).permute(2,0,1)[None]
                # 所有图先按网络固定输入尺寸缩放，再用准确整数像素移位。
                x = torch.nn.functional.interpolate(x, size=(512,1024), mode='bilinear', align_corners=False)
                for shift in SHIFTS:
                    try:
                        output, trace = trace_inference(net, x.roll(shift, dims=-1))
                        if not all(np.isfinite(output[k]).all() for k in ('cor_id', 'y_bon_', 'y_cor_')):
                            raise ValueError('nonfinite_model_output')
                        diag = phase_metrics(output, trace)
                        phases.append(output)
                        traces.append(diag)
                        phase_rows.append(dict(image=code, shift=shift, status='ok', reason='', **diag))
                        raw[f'{iid}__{shift}__bon'] = output['y_bon_']
                        raw[f'{iid}__{shift}__cor'] = output['y_cor_']
                        layouts.append(dict(image=code, image_id=iid, shift=shift,
                                            points_1024x512=output['cor_id'].tolist(), diagnostics=diag))
                    except (AssertionError, ValueError, IndexError, RuntimeError) as exc:
                        errors.append(f'{shift}:{type(exc).__name__}:{exc}')
                        phase_rows.append(dict(image=code, shift=shift, status='failed', reason=errors[-1]))
            if len(phases)==len(SHIFTS):
                row.update(status='complete', failure='', **orbit_metrics(phases, SHIFTS),
                    phase0_pair_count=traces[0]['final_pair_count'],
                    phase0_fallback_used=traces[0]['fallback_used'],
                    fallback_phase_count=sum(r['fallback_used'] for r in traces),
                    phase0_forced_change_count=traces[0]['general_forced_change_count'],
                    phase0_forced_infer_count=traces[0]['general_forced_infer_count'],
                    phase0_boundary_correction_mae_deg=traces[0]['boundary_correction_mae_deg'])
                row['archived_count_equal'] = (row['phase0_pair_count']==row['archived_pair_count']) if row['archived_pair_count'] is not None else None
            else:
                row.update(status='incomplete_orbit', failure='|'.join(errors) if path else 'missing_image')
            rows.append(row)
            if (index+1)%10==0 or index+1==len(images):
                save_replay(destination, rows, phase_rows, raw, layouts)
                print(f'HoHoNet {index+1}/{len(images)} {time.perf_counter()-started:.1f}s', flush=True)
    completed = [r for r in rows if r['status']=='complete']
    summary = dict(images=len(rows), complete=len(completed), failed=len(rows)-len(completed),
        phase0_fallback_images=sum(r['phase0_fallback_used'] for r in completed),
        any_phase_fallback_images=sum(r['fallback_phase_count']>0 for r in completed),
        rotation_changes_pair_count_images=sum(r['final_pair_count_range']>0 for r in completed),
        archived_count_compared=sum(r.get('archived_count_equal') is not None for r in completed),
        archived_count_different=sum(r.get('archived_count_equal') is False for r in completed),
        elapsed_seconds=time.perf_counter()-started)
    write_json(destination/'summary.json', summary)
    contract = dict(schema='hohonet_difficulty_probe_20261009_v1', checkpoint=str(CHECKPOINT), config=str(CONFIG),
        model_loader='tools.thesis_main.registry.hohonet_feature_backend.load_model; strict local state_dict; pretrained=False',
        torch=torch.__version__, device=device, threads=4, input_size=[512,1024], shifts=SHIFTS,
        source='local test/valid PNG preferred; otherwise annotation JPG, each path recorded',
        population='all259 research images' if limit is None else 'top baseline residual pilot, not representative',
        trace='原模型infer，临时截取gen_ww实际调用/返回；一般解码后转force_cuboid才记fallback；forced change/infer按原action计数',
        boundary_correction='camera包含且有效的最终点原环按球面墙边重建单值每列上下边界，top z=-50/bottom z=+50；与raw y_bon像素差平均乘180/512。包含墙拟合/高度统一/回退的综合改变量，不是GT误差、非正交程度或遮挡比例',
        stability='对输入循环右移0/256/512/768后推理，raw bon/cor反向左移对齐，平均非零相位到0的绝对差；只测该模型对yaw的稳定性',
        limitations='后处理约束不是独立真实结构；重放fallback不是历史实际初始化证据；低变化不证明容易或正确。未按主观/GT调参，标签只在推理后分组。',
        summary=summary)
    write_json(destination/'field_contract.json', contract)
    lines=['# HoHoNet：约束前输出与重放诊断', '', '2026-10-09。本地ep300模型重放，不修改原模型或旧分数。', '',
        f"{summary['images']}图，四相位完整{summary['complete']}图；相位0四角回退{summary['phase0_fallback_images']}图，任一相位回退{summary['any_phase_fallback_images']}图；旋转后点对数变化{summary['rotation_changes_pair_count_images']}图。", '',
        f"与旧模型点数比较{summary['archived_count_compared']}图，差异{summary['archived_count_different']}图；差异保留，不覆盖旧结果。", '',
        '## 指标意义', '',
        '- 原峰数、一般解码墙数、强制改向／插入墙、四角回退：来自实际后处理调用，不能推断真实角数或遮挡。',
        '- boundary correction：raw上下边界到最终球面边界的平均角度变化，反映模型约束调整，不等于图像到真实空间的误差。',
        '- rotation MAE：yaw逆对齐后的raw边界／角点响应差，测模型不稳定；不能作为人的不确定性或正确率。',
        '- raw_predictions.npz与layouts.json保存各图四相位原输出与最终点；失败相位单列，不删图凑完整。', '',
        '本轮不据这些信号自动改难度档、不更换模型checkpoint、不按GT选结果。训练清单核查与实际checkpoint训练历史是不同证据。', '',
        '复算：`.venv/Scripts/python.exe -m tools.thesis_main.analysis.difficulty_model_probe_20261009`。', '']
    (destination/'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pilot', type=int)
    run(parser.parse_args().pilot)
