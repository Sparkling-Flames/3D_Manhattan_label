"""BiLayout全研究图原序底面和raw双头探查；不读取人工标签或GT评价。"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BACKEND = Path('D:/Work/Manhattan_3D/Bi_layout')
EXPORT = BACKEND/'exports/mp3d_dual_predictions'
OUT = ROOT/'analysis_results/objective_difficulty_20261009/bilayout_probe'
BRANCHES = {'extended': 'depth', 'enclosed': 'new_depth'}
CONFIG = BACKEND/'src/config/mp3d.yaml'
CHECKPOINT = BACKEND/'checkpoints/Bi_Layout_Net/mp3d/mp3d_best_model.pkl'
RESEARCH_SOURCE = ROOT/'analysis_results/objective_difficulty_20261009/hohonet_probe/per_image.csv'


def depth_gap(extended, enclosed):
    """相对L1双头差异及有符号平均差；不是概率、置信度、遮挡比例。"""
    result = dict(status='ok', relative_gap=None, signed_extended_minus_enclosed=None)
    if extended is None or enclosed is None:
        result['status'] = 'missing'
        return result
    a, b = np.asarray(extended), np.asarray(enclosed)
    if a.shape != (256,) or b.shape != (256,):
        result['status'] = 'shape_mismatch'
    elif not np.isfinite(a).all() or not np.isfinite(b).all():
        result['status'] = 'nonfinite'
    elif np.any(a <= 0) or np.any(b <= 0):
        result['status'] = 'nonpositive_depth'
    else:
        scale = float(np.mean((a+b)/2))
        result.update(relative_gap=float(np.mean(np.abs(a-b)))/scale,
                      signed_extended_minus_enclosed=float(np.mean(a-b))/scale)
    return result


def inverse_yaw(depth, input_roll_pixels):
    depth = np.asarray(depth)
    if depth.shape != (256,) or input_roll_pixels % 4:
        raise ValueError('yaw_requires_integer_depth_bins_1024px_256depth')
    return np.roll(depth, -(input_roll_pixels//4))


def _audit():
    # 沿用已有审计器，保留原点序；不重新拟合或x排序修环。
    from tools.thesis_main.analysis.prepare_uncertainty_visual_review import helpers
    return helpers()[0]


def floor_comparison(extended_path, enclosed_path, audit=None):
    audit = audit or _audit()
    row = dict(floor_gap=None)
    polygons = {}
    for head, path in [('extended', extended_path), ('enclosed', enclosed_path)]:
        path = Path(path)
        row[head+'_pair_count'] = None
        if not path.is_file():
            row[head+'_status'] = 'missing_file'
            continue
        points = np.loadtxt(path, ndmin=2)
        row[head+'_pair_count'] = len(points)//2 if len(points)%2 == 0 else None
        try:
            polygons[head] = audit.footprint(points)
            row[head+'_status'] = 'ok'
        except (ValueError, IndexError, TypeError) as error:
            row[head+'_status'] = str(error)
    if len(polygons) == 2:
        row['floor_gap'] = audit.dp(polygons['extended'], polygons['enclosed'])
    return row


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def write_csv(path, rows):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prepare():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    bundle = load_current_bundle()
    index = {}
    for split in ('val', 'test'):
        with (EXPORT/split/'manifest.csv').open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                if row['pano_id'] in index:
                    raise ValueError('duplicate_bilayout_image:' + row['pano_id'])
                index[row['pano_id']] = row
    rows, inputs = [], []
    audit = _audit()
    for im in sorted(bundle['research']['images'], key=lambda r:r['image_id']):
        iid = im['image_id']
        source = index.get(iid)
        meta = dict(image_id=iid, image=im['image_code'], building=im['building_id'])
        if source is None:
            raise ValueError('research_image_missing_bilayout_export:' + iid)
        paths = {head: EXPORT/source[head+'_corners_px_path'] for head in BRANCHES}
        row = dict(**meta, export_status=source['status'], split=source['split'],
            **floor_comparison(paths['extended'], paths['enclosed'], audit),
            extended_source=str(paths['extended']), enclosed_source=str(paths['enclosed']),
            manifest_source=str(EXPORT/source['split']/'manifest.csv'))
        rows.append(row)
        inputs.append(dict(**meta, split=source['split'],
            image_source=str(BACKEND/'src/dataset/mp3d/image'/f'{iid}.png')))
    write_csv(OUT/'geometry.csv', rows)
    write_json(OUT/'inputs.json', dict(schema='bilayout_probe_input_20261009_v1', images=inputs))
    write_report()
    print(json.dumps(dict(images=len(rows), floor_computable=sum(r['floor_gap'] is not None for r in rows))), flush=True)


def _backend():
    import torch
    import torchvision.models
    sys.path.insert(0, str(BACKEND))
    spec = importlib.util.spec_from_file_location('bilayout_export_probe', BACKEND/'scripts/export_mp3d_dual_predictions.py')
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    original_resnet = torchvision.models.resnet50
    def no_download_resnet(*args, **kwargs):
        kwargs.pop('pretrained', None)
        kwargs['weights'] = None
        return original_resnet(*args, **kwargs)
    # 完整checkpoint将严格覆盖网络权重，构造时不需要下载ImageNet初始化。
    torchvision.models.resnet50 = no_download_resnet
    def reject_download(*args, **kwargs):
        raise RuntimeError('network_download_disabled_for_probe')
    torch.hub.download_url_to_file = reject_download
    torch.hub.load_state_dict_from_url = reject_download
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    cfg = exporter.merge_from_file(str(CONFIG))
    try:
        model, _ = exporter.load_model(cfg, CHECKPOINT, device)
    finally:
        torchvision.models.resnet50 = original_resnet
    return exporter, model, device


def research_source_inputs(original, hoho_rows):
    """严格连接研究图身份，只投影源图路径；不读取标签作为模型输入。"""
    sources = {}
    for row in hoho_rows:
        if row['image_id'] in sources:
            raise ValueError('duplicate_research_source_image:' + row['image_id'])
        sources[row['image_id']] = row
    if len({row['image_id'] for row in original}) != len(original) or set(sources) != {row['image_id'] for row in original}:
        raise ValueError('research_source_population_mismatch')
    result = []
    for row in original:
        source = sources[row['image_id']]
        if any(row[key] != source[key] for key in ('image','building')):
            raise ValueError('research_source_identity_mismatch:' + row['image_id'])
        path = Path(source['image_path'])
        if not path.is_file():
            raise FileNotFoundError(path)
        result.append(dict(row, external_image_source=row['image_source'], image_source=str(path)))
    return result


def raw_probe(limit=None, yaw=False, research_source=False):
    import torch
    inputs = json.loads((OUT/'inputs.json').read_text(encoding='utf-8'))['images']
    output = OUT/'research_source' if research_source else OUT
    if research_source:
        if yaw:
            raise ValueError('research_source_mode_has_no_yaw_probe')
        with RESEARCH_SOURCE.open(encoding='utf-8-sig',newline='') as stream:
            inputs = research_source_inputs(inputs,list(csv.DictReader(stream)))
        write_json(output/'inputs.json',dict(schema='bilayout_probe_research_source_input_20261009_v1',
            source=str(RESEARCH_SOURCE),identity_match='exact same image_id set, image code and building; all files exist',
            images=inputs))
    if yaw:
        # 不看难度/GT/人员表现；按建筑排序等距选12建筑，各取ID最小图。
        bybuilding = {}
        for row in inputs:
            bybuilding.setdefault(row['building'], row)
        buildings = sorted(bybuilding)
        selected = np.linspace(0, len(buildings)-1, min(12,len(buildings))).round().astype(int)
        inputs = [bybuilding[buildings[i]] for i in selected]
        write_json(OUT/'yaw_selection.json', dict(rule='sorted building equally spaced 12; smallest image_id per building; no labels/GT/worker outcomes', images=inputs, input_roll_pixels=[128,256]))
    elif limit is not None:
        inputs = inputs[:limit]
    start = time.perf_counter()
    exporter, model, device = _backend()
    print(f'model loaded device={device} seconds={time.perf_counter()-start:.2f}', flush=True)
    rows = []
    for i, meta in enumerate(inputs):
        started = time.perf_counter()
        image = exporter.read_image(meta['image_source'], shape=[512,1024])[...,:3]
        if image.shape != (512,1024,3):
            raise ValueError('invalid_image_shape:' + meta['image_id'])
        base_path = output/'raw'/f"{meta['image_id']}.npz"
        base_path.parent.mkdir(parents=True, exist_ok=True)
        def predict(roll):
            tensor = torch.from_numpy(np.roll(image,roll,axis=1).transpose(2,0,1)[None].copy()).to(device)
            with torch.inference_mode():
                result = model(tensor)
            return {key:result[key][0].detach().cpu().numpy() for key in ('depth','new_depth','ratio')}
        base = predict(0)
        np.savez_compressed(base_path, **base)
        gap = depth_gap(base['depth'], base['new_depth'])
        ratio = float(np.asarray(base['ratio']).reshape(-1)[0])
        row = dict(**meta, status=gap['status'], relative_gap=gap['relative_gap'],
            signed_extended_minus_enclosed=gap['signed_extended_minus_enclosed'],
            ratio=ratio if np.isfinite(ratio) else None,
            ratio_status='ok' if np.isfinite(ratio) and ratio>0 else 'nonfinite_or_nonpositive',
            raw_source=str(base_path), seconds=None)
        if yaw:
            for roll in (128,256):
                shifted_path = OUT/'raw_yaw'/f"{meta['image_id']}_roll{roll}.npz"
                shifted_path.parent.mkdir(parents=True,exist_ok=True)
                shifted = predict(roll)
                np.savez_compressed(shifted_path, **shifted)
                for head,key in BRANCHES.items():
                    stat = depth_gap(base[key], inverse_yaw(shifted[key],roll))
                    row[f'{head}_roll{roll}_relative_gap'] = stat['relative_gap']
                    row[f'{head}_roll{roll}_status'] = stat['status']
        row['seconds'] = time.perf_counter()-started
        rows.append(row)
        if i == 0 or (i+1)%25 == 0 or i+1 == len(inputs):
            print(f'{i+1}/{len(inputs)} image={meta["image"]} elapsed={time.perf_counter()-start:.2f}',flush=True)
    name = 'yaw.csv' if yaw else 'raw_pilot.csv' if limit else 'raw.csv'
    write_csv(output/name, rows)
    write_json(output/(name.removesuffix('.csv')+'_run.json'),dict(
        checkpoint=str(CHECKPOINT), config=str(CONFIG), backend=str(BACKEND),
        branch_mapping=BRANCHES, n=len(rows), device=device, torch=torch.__version__,
        numpy=np.__version__, seconds=time.perf_counter()-start,
        preprocessing='original exporter read_image; RGB/255; AREA resize only if needed; no GT',
        network_download_disabled=True, checkpoint_load='strict',
        source_mode='same_research_images_as_hohonet' if research_source else 'external_bilayout_dataset_copy',
        research_source_table=str(RESEARCH_SOURCE) if research_source else None,
        fixed_reference_training_overlap='not_independently_verified',
        outputs='unfitted 256-bin radial depth heads and shared predicted ratio; not probability/confidence'))
    if research_source:
        write_json(output/'field_contract.json',dict(schema='bilayout_research_source_raw_20261009_v1',
            population='same259 image_id as base inputs.json and HoHoNet per_image.csv; file existence + code/building exact match',
            source_table=str(RESEARCH_SOURCE),input='inputs.json',outputs=name,raw_arrays='raw/*.npz',
            branch_mapping=BRANCHES,checkpoint=str(CHECKPOINT),config=str(CONFIG),
            relative_gap='mean(abs(extended-enclosed))/mean((extended+enclosed)/2); positive finite 256 heads only',
            signed='mean(extended-enclosed)/same denominator; direction retained',
            preprocessing='Bi original read_image RGB/255; OpenCV INTER_AREA resize when needed; same source bytes as HoHo, model-specific preprocessing retained',
            unknown='checkpoint training/selection overlap not independently verified',
            purpose='same-source re-inference; external dataset copy prior results preserved as historical source-difference diagnostics',
            no_yaw='no new same-source yaw; earlier external-source yaw remains separate',
            interpretation='model head discrepancy, not calibrated confidence/human difficulty/occlusion'))
        valid = [row for row in rows if row['status']=='ok']
        gaps = np.asarray([row['relative_gap'] for row in valid])
        lines = ['# BiLayout统一研究原图重放','',
            f'按HoHoNet per_image.csv的image_path严格连接并重推{len(rows)}图，正有限双头有效{len(valid)}图。', '',
            f'相对双头差中位数{float(np.median(gaps)):.6f}，P90 {float(np.quantile(gaps,.9)):.6f}。', '',
            '输入是相同研究原图源文件；保留Bi原RGB/255和AREA缩放，不承诺两模型张量预处理完全相同。', '',
            '此目录与既有external dataset copy重放及yaw分离；旧图像来源诊断继续保留。原副本差异不全部解释为水平旋转。', '',
            'raw/*.npz保存depth/new_depth两个256维数组和ratio。字段公式见field_contract.json，运行耗时与backend见raw_run.json。', '',
            '未计算新的yaw，不用人工标签或GT调参；双头变化不直接等同人类标注难度或遮挡。']
        (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def write_report():
    def read_csv(name):
        path = OUT/name
        return list(csv.DictReader(path.open(encoding='utf-8-sig',newline=''))) if path.exists() else []
    geometry, raw, yaw = read_csv('geometry.csv'), read_csv('raw.csv'), read_csv('yaw.csv')
    def distribution(rows,key):
        values = np.asarray([float(r[key]) for r in rows if r[key] != ''])
        return dict(n=len(values), zero=int(np.sum(values==0)),
            median=float(np.median(values)) if len(values) else None,
            p90=float(np.quantile(values,.9)) if len(values) else None,
            maximum=float(np.max(values)) if len(values) else None)
    summary = dict(geometry=distribution(geometry,'floor_gap'),
        raw_head_gap=distribution(raw,'relative_gap'),
        yaw={key:distribution(yaw,key) for head in BRANCHES for roll in (128,256)
             for key in [f'{head}_roll{roll}_relative_gap']} if yaw else {})
    write_json(OUT/'summary.json',summary)
    contract = dict(schema='difficulty_bilayout_probe_20261009_v1',
        population='current load_current_bundle research.images; all 259; no scene/difficulty exclusion',
        input='inputs.json', geometry='geometry.csv', raw='raw.csv', yaw='yaw.csv',
        branches=BRANCHES, model_config=str(CONFIG), model_checkpoint=str(CHECKPOINT),
        postprocessed_export=str(EXPORT), geometry_metric='existing audit.footprint/dp; source-order BEV 1-IoU at camera floor height normalization; no repair',
        raw_relative_gap='mean(abs(extended-enclosed))/mean((extended+enclosed)/2), positive finite 256-bin heads only',
        raw_signed='mean(extended-enclosed)/same denominator; positive means extended mean depth larger',
        yaw_alignment='input horizontal positive roll 128/256 px; inverse depth np.roll by -32/-64 bins before relative-gap comparison',
        missing='None/empty CSV for missing, invalid, nonfinite, nonpositive; genuine equal positive heads yield zero',
        interpretation='model head variation/equivariance; not confidence, occlusion, human annotation difficulty or validated objective score',
        boundary='fixed downloaded checkpoint; supplied split building separation is not proof of actual checkpoint training/selection independence',
        provenance='backend export_split/run_metadata + no-download runtime; no source edits, no training, no human difficulty/GT input')
    write_json(OUT/'field_contract.json',contract)
    lines = ['# BiLayout图片难度候选信号探查','',
        '本支只计算模型输出自身的几何、双头差异和旋转变化，不将这些直接命名为真人难度或置信度。','',
        f'- 原序底面覆盖：{len(geometry)}图；双头可比较{sum(r["floor_gap"] != "" for r in geometry)}图。退化和不可计算保留空值，不重新排序。',
        f'- raw双头：{len(raw)}图；有效正值256维双头{sum(r["status"]=="ok" for r in raw)}图。两数组和ratio保存在raw/，没有曼哈顿拟合。',
        f'- 旋转试点：{len(yaw)}图，按建筑排序等距选12建筑，每建筑取ID最小图；不参考人工标签或作答。128/256px滚动后按-32/-64 bins逆对齐，单列yaw.csv。','',
        'extended对应depth；enclosed对应new_depth。相对双头差是平均绝对差除以两头平均深度，有符号差保留平均方向；不设难度阈值。','',
        '既有导出是Manhattan后处理角点。两头在原序底面不可计算时，raw深度仍可能存在，这不构成修复成功或可标性认证。','',
        '供给的MP3D split清单为train1647/val190/test458，清单建筑互斥；本研究图val76/test183。它只说明清单身份，不证明下载checkpoint真实训练、预训练或选参未见目标。','',
        '未改外部repo、未训练或下载；未以人工标签调参。结果是候选测量，尚待与独立人员作答表现和主观感受对照。']
    failed = [r for r in geometry if r['floor_gap'] == '']
    if failed:
        lines += ['', '## 底面不可比较图','', '|图片|extended点对/状态|enclosed点对/状态|', '|---|---|---|']
        for row in failed:
            lines.append(f'|{row["image"]}|{row["extended_pair_count"]} / {row["extended_status"]}|{row["enclosed_pair_count"]} / {row["enclosed_status"]}|')
        lines += ['', 'raw双头是否有效另读raw.csv；不把有效raw深度称为角点修复。']
    if raw:
        lines += ['', f'raw双头相对差中位数 {summary["raw_head_gap"]["median"]:.6f}，P90 {summary["raw_head_gap"]["p90"]:.6f}；仅描述模型差异。']
    if yaw:
        lines += ['', '## 旋转变化分布','', '|分支与像素滚动|图数|相对差中位数|P90|', '|---|---:|---:|---:|']
        for key,value in summary['yaw'].items():
            lines.append(f'|{key}|{value["n"]}|{value["median"]:.6f}|{value["p90"]:.6f}|')
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',action='store_true')
    parser.add_argument('--yaw',action='store_true')
    parser.add_argument('--limit',type=int)
    parser.add_argument('--report',action='store_true')
    parser.add_argument('--research-source',action='store_true',help='严格使用HoHoNet replay研究原图，另存research_source/，不覆盖external副本结果')
    args = parser.parse_args()
    if args.raw or args.yaw or args.research_source:
        raw_probe(args.limit,args.yaw,args.research_source)
    elif args.report:
        write_report()
    else:
        sys.path.insert(0,str(ROOT))
        prepare()
