"""冻结旧LHFeat/PCA/5NN，只在复现通过后补普通历史面板缺图。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

from .research_artifact_io import ROOT, read_csv, write_csv, write_json
from ..registry import hohonet_feature_backend as backend

STATIC = ROOT / 'analysis_results/c2b_validation_static_20260802_v16/static'
MANIFEST = STATIC / 'c2_feature_freeze_manifest.json'
OLD_SCORES = STATIC / 'c2b_static_model_risk.csv'
PANEL = ROOT / 'analysis_results/objective_difficulty_20261009/stratified/features_and_scores.csv'
OUT = ROOT / 'analysis_results/objective_difficulty_20261009/d_model_expansion'
CHECKPOINT = ROOT / 'ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth'
CONFIG = ROOT / 'config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml'
IMAGE_DIR = ROOT / 'data/mp3d_layout/img_v'
DESCRIPTOR_RELATIVE_L2 = 1e-4
SCORE_ATOL = 1e-3
SCORE_RTOL = 1e-4
FIELDS = ('d_model_feat_static', 'd_model_feat_local_max_static', 'static_model_risk_score')


def score_fields(global_score, local_score):
    return dict(zip(FIELDS, (global_score, local_score, math.hypot(global_score, local_score))))


def frozen_scores(global_descriptors, local_descriptors, reference):
    """Exact frozen float32 projection and original five-neighbour mean."""
    scores = []
    for head, descriptors in (('global', global_descriptors), ('local', local_descriptors)):
        if not np.isfinite(descriptors).all():
            raise ValueError('nonfinite_descriptor:' + head)
        scale = reference[head + '_scale']
        if not np.isfinite(scale).all() or (scale <= 0).any():
            raise ValueError('invalid_frozen_scale:' + head)
        transformed = ((descriptors - reference[head + '_mean']) @ reference[head + '_components'].T) / scale
        matrix = reference['reference_' + head]
        if len(matrix) < 5 or not np.isfinite(matrix).all():
            raise ValueError('invalid_frozen_reference:' + head)
        values = []
        for vector in transformed:
            distances = np.linalg.norm(matrix - vector[None], axis=1)
            values.append(float(np.mean(np.partition(distances, 4)[:5])))
        scores.append(values)
    return tuple(scores)


def reproduction_passed(rows):
    return len(rows) == 3 and all(np.isfinite(row['descriptor_relative_l2']) and
                                  row['descriptor_relative_l2'] <= DESCRIPTOR_RELATIVE_L2 and
                                  row['global_match'] and row['local_match'] for row in rows)


def select_missing(rows, old_ids):
    panel = [row for row in rows if row['subjective_label'] in ('简单', '中等', '困难') and
             row['calibration_panel'] == 'ordinary_historical_panel']
    if len({row['image_id'] for row in panel}) != len(panel):
        raise ValueError('duplicate_panel_image')
    return [row for row in panel if row['image_id'] not in old_ids]


def source_paths(rows, directory=IMAGE_DIR):
    paths = [directory / (row['image_id'] + '.jpg') for row in rows]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(str(path))
    return paths


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def frozen_identity():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    for path, key in ((CHECKPOINT, 'checkpoint_sha256'),
                      (Path(manifest['feature_cache_path']), 'reference_feature_sha256'),
                      (Path(manifest['candidate_descriptor_cache_path']), 'candidate_descriptor_cache_sha256')):
        if sha256(path) != manifest[key]:
            raise ValueError('frozen_identity_mismatch:' + str(path))
    config = CONFIG.read_bytes()
    matched = 'exact_bytes'
    if hashlib.sha256(config).hexdigest() != manifest['config_sha256']:
        # Historical checkout was CRLF; permit only this byte-for-byte equivalence.
        config = config.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        matched = 'historical_crlf_equivalent'
        if hashlib.sha256(config).hexdigest() != manifest['config_sha256']:
            raise ValueError('frozen_identity_mismatch:' + str(CONFIG))
    (OUT / 'frozen_config.yaml').write_bytes(config)
    return manifest, matched


def extract(paths, name, device):
    start = time.perf_counter()
    descriptors, audit = backend.extract_orbit_descriptors(paths, CHECKPOINT, OUT / 'frozen_config.yaml',
                                                          device=device, off_grid_sample_count=0)
    global_vectors = np.stack([descriptors[path.resolve().as_posix()][0] for path in paths])
    local_vectors = np.stack([descriptors[path.resolve().as_posix()][1] for path in paths])
    np.savez_compressed(OUT / (name + '.npz'), paths=[p.resolve().as_posix() for p in paths],
                        global_descriptors=global_vectors, local_descriptors=local_vectors)
    return global_vectors, local_vectors, dict(device=audit['device'], dtype=audit['dtype'],
                                              physical_batch_size=4, image_count=len(paths),
                                              elapsed_seconds=time.perf_counter() - start)


def reference_overlap():
    from ..data_prep.consolidate_research_input import load_current_bundle
    reference = read_csv(STATIC / 'c2b_reference_image_file_listing.csv')
    reference_buildings = {Path(row['path']).stem.split('_')[0] for row in reference}
    images = load_current_bundle()['research']['images']
    buildings = {row['building_id'] for row in images}
    return dict(reference_image_count=len(reference), reference_building_count=len(reference_buildings),
                research_image_count=len(images), research_building_count=len(buildings),
                overlapping_buildings=sorted(reference_buildings & buildings),
                reference_role='frozen training_no_occ listing; 1647 images',
                limitation='清单不重合不证明checkpoint训练与epoch选择历史独立。')


def ordinal_association(values, labels):
    from scipy.stats import rankdata
    if len(set(labels)) < 2 or len(set(values)) < 2:
        return None
    return float(np.corrcoef(rankdata(values), rankdata(labels))[0, 1])


def room_counts(rows):
    return dict(n_rooms=len({(r['building'], r['room']) for r in rows if r['room']}),
                n_room_unknown_images=sum(not r['room'] for r in rows))


def retrospective():
    """固定总体、exact点数×遮挡及预定近点数补充；无参数搜索。"""
    structure_path = OUT.parent / 'structure_classification/images.csv'
    structure = {r['image_id']: r for r in read_csv(structure_path)}
    labels = {r['image_id']: r['subjective_label'] for r in read_csv(PANEL)}
    rows = read_csv(OUT / 'panel_scores.csv')
    for row in rows:
        selected = structure[row['image_id']]
        if (row['building'], row['room']) != (selected['building'], selected['room']):
            raise ValueError('retrospective_identity_mismatch:' + row['image_id'])
        row['selected_gt_pair_count'] = int(selected['selected_gt_pair_count'])
        row['structural_occlusion'] = selected['structural_occlusion']
        row['historical_label'] = labels[row['image_id']]
        row['label_ordinal'] = {'简单': 0, '中等': 1, '困难': 2}[row['historical_label']]
    contract = dict(label_role='historical_not_blind; no estimator training or calibration',
                    main_strata='exact selected GT pair count × structural occlusion',
                    supplementary_strata=['4', '6-8', '>=10'],
                    uncertainty='building cluster percentile bootstrap, fixed seed 20261009, 1000 repetitions',
                    minimum_for_association=dict(images=6, buildings=3, distinct_labels=2),
                    minimum_valid_bootstrap_repetitions_for_ci=950,
                    room_count_definition='distinct (building, nonempty room); empty room reported as n_room_unknown_images',
                    missing_or_constant='N/A; no zero imputation', fields=list(FIELDS),
                    gt_reference_source=str(structure_path), panel_source=str(PANEL))
    write_json(OUT / 'retrospective_contract.json', contract)
    write_csv(OUT / 'retrospective_inputs.csv', rows)
    groups = [('overall', 'all', rows)]
    for count, occlusion in sorted({(r['selected_gt_pair_count'], r['structural_occlusion']) for r in rows}):
        groups.append(('exact', f'{count}/{occlusion}', [r for r in rows if
                      (r['selected_gt_pair_count'], r['structural_occlusion']) == (count, occlusion)]))
    for low, high, name in ((4, 4, '4'), (6, 8, '6-8'), (10, float('inf'), '>=10')):
        for occlusion in ('False', 'True'):
            group = [r for r in rows if low <= r['selected_gt_pair_count'] <= high and r['structural_occlusion'] == occlusion]
            if group:
                groups.append(('near_supplementary', name + '/' + occlusion, group))
    result = []
    rng = np.random.default_rng(20261009)
    for grouping, key, group in groups:
        buildings = sorted({r['building'] for r in group})
        y = [r['label_ordinal'] for r in group]
        ready = len(group) >= 6 and len(buildings) >= 3 and len(set(y)) >= 2
        indices = {building: [i for i, r in enumerate(group) if r['building'] == building] for building in buildings}
        bootstrap_indices = [sum((indices[b] for b in rng.choice(buildings, size=len(buildings), replace=True)), [])
                             for _ in range(1000)] if ready else []
        for field in FIELDS:
            values = [float(r[field]) for r in group]
            correlation = ordinal_association(values, y) if ready else None
            bootstrap = [ordinal_association([values[i] for i in ids], [y[i] for i in ids]) for ids in bootstrap_indices]
            bootstrap = [value for value in bootstrap if value is not None]
            ci = np.quantile(bootstrap, [.025, .975]).tolist() if len(bootstrap) >= 950 else [None, None]
            result.append(dict(grouping=grouping, stratum=key, metric=field, n_images=len(group),
                               n_buildings=len(buildings), **room_counts(group),
                               label_simple=y.count(0), label_medium=y.count(1), label_hard=y.count(2),
                               metric_median=float(np.median(values)), spearman=correlation,
                               cluster_ci_low=ci[0], cluster_ci_high=ci[1], valid_bootstrap_reps=len(bootstrap),
                               uncertainty_status='available' if ci[0] is not None else 'N/A_insufficient_nonconstant_cluster_resamples',
                               status='computable' if correlation is not None else 'N/A_insufficient_or_constant'))
    write_csv(OUT / 'retrospective_associations.csv', result)
    overall = [r for r in result if r['grouping'] == 'overall']
    counts = room_counts(rows)
    report = f'\n## 限定历史对照\n\n112图、{len(set(r["building"] for r in rows))}建筑、{counts["n_rooms"]}声明房间；另{counts["n_room_unknown_images"]}图房间未知，空room不计入声明房间。标签为既有人工历史标签，含既有模型／标注观察，非盲法验证。固定exact GT点数×结构遮挡为主控制；[4]、[6–8]、[>=10]×遮挡仅补充。每组报告样本、建筑、声明房间、房间未知图数及标签分布；少于6图／3建筑或标签常量记N/A。\n\n'
    for row in overall:
        report += f'- {row["metric"]}：Spearman={row["spearman"]:.3f}，建筑cluster 1000次95%区间[{row["cluster_ci_low"]:.3f}, {row["cluster_ci_high"]:.3f}]。\n'
    report += '\n分层结果见retrospective_associations.csv；未拟合权重、阈值或难度模型。置信区间仅反映此历史面板建筑抽样，不能消除历史标签／参考GT／checkpoint选择偏差；不证明特征为独立图片难度。\n'
    four_point = next(r for r in result if r['grouping'] == 'exact' and r['stratum'] == '4/False')
    report += f'\n最大exact组为4点且无结构遮挡：{four_point["n_images"]}图、{four_point["n_buildings"]}建筑、{four_point["n_rooms"]}声明房间；另{four_point["n_room_unknown_images"]}图房间未知。仅简单50／中等18，没有困难标签。global关联降至约0.238，区间跨零；local与历史hypot约0.270／0.253，区间较宽。其它exact组仅2–10图；例如6点无遮挡只有3建筑，很多建筑重抽样导致标签常量，有效重复不足950时区间记N/A。高点数组常为困难常量，不能估计组内关联。总体正相关不能据此认定已独立识别图片难度。\n'
    report_path = OUT / 'REPORT.md'
    base = report_path.read_text(encoding='utf-8').split('\n## 限定历史对照')[0]
    report_path.write_text(base + report, encoding='utf-8')
    print(json.dumps(overall), flush=True)


def run(expand=False, device='auto'):
    OUT.mkdir(parents=True, exist_ok=True)
    tolerances = dict(descriptor_relative_l2_max=DESCRIPTOR_RELATIVE_L2, score_atol=SCORE_ATOL,
                      score_rtol=SCORE_RTOL, sample_selection='first three frozen candidate-cache paths; not score-selected')
    write_json(OUT / 'predeclared_tolerances.json', tolerances)
    try:
        manifest, config_match = frozen_identity()
        reference = np.load(manifest['feature_cache_path'])
        candidate = np.load(manifest['candidate_descriptor_cache_path'])
        old = {r['image_id']: r for r in read_csv(OLD_SCORES)}
        paths = [Path(p) for p in candidate['paths'][:3]]
        global_vectors, local_vectors, audit = extract(paths, 'reproduction_descriptors', device)
        gs, ls = frozen_scores(global_vectors, local_vectors, reference)
        cache_gs, cache_ls = frozen_scores(candidate['global_descriptors'][:3], candidate['local_descriptors'][:3], reference)
        rows = []
        for i, path in enumerate(paths):
            previous = old[path.stem]
            row = dict(image_id=path.stem, image_path=path.as_posix(),
                       descriptor_relative_l2=backend.relative_l2((candidate['global_descriptors'][i], candidate['local_descriptors'][i]),
                                                                 (global_vectors[i], local_vectors[i])),
                       global_match=bool(np.isclose(gs[i], float(previous[FIELDS[0]]), atol=SCORE_ATOL, rtol=SCORE_RTOL)),
                       local_match=bool(np.isclose(ls[i], float(previous[FIELDS[1]]), atol=SCORE_ATOL, rtol=SCORE_RTOL)),
                       global_old=float(previous[FIELDS[0]]), local_old=float(previous[FIELDS[1]]),
                       global_replayed=gs[i], local_replayed=ls[i], cache_global=cache_gs[i], cache_local=cache_ls[i])
            rows.append(row)
        passed = reproduction_passed(rows)
        receipt = dict(status='passed' if passed else 'blocked_reproduction', tolerances=tolerances,
                       config_identity=config_match, model_audit=audit, rows=rows,
                       reference_listing_overlap=reference_overlap())
        write_json(OUT / 'reproduction.json', receipt)
        print(json.dumps(receipt, ensure_ascii=False), flush=True)
        if not passed:
            write_json(OUT / 'blocked.json', receipt)
            return
        if not expand:
            return
        missing = select_missing(read_csv(PANEL), set(old))
        paths = source_paths(missing)
        write_json(OUT / 'expansion_inputs.json', [dict(image_id=r['image_id'], image=r['image'],
                   image_path=p.as_posix(), source_role='original_candidate_img_v_jpeg') for r, p in zip(missing, paths)])
        global_vectors, local_vectors, audit = extract(paths, 'expanded_descriptors', device)
        gs, ls = frozen_scores(global_vectors, local_vectors, reference)
        expanded = [dict(image_id=row['image_id'], image=row['image'], building=row['building'], room=row['room'],
                         image_path=path.as_posix(), **score_fields(g, l), source_role='frozen_estimator_missing_panel_supplement')
                    for row, path, g, l in zip(missing, paths, gs, ls)]
        write_csv(OUT / 'supplement.csv', expanded)
        combined = []
        for row in read_csv(PANEL):
            if row['calibration_panel'] != 'ordinary_historical_panel' or row['subjective_label'] not in ('简单', '中等', '困难'):
                continue
            values = old.get(row['image_id']) or next(r for r in expanded if r['image_id'] == row['image_id'])
            combined.append(dict(image_id=row['image_id'], image=row['image'], building=row['building'], room=row['room'],
                                 **{k: float(values[k]) for k in FIELDS},
                                 value_origin='historical_unchanged' if row['image_id'] in old else 'reproduced_supplement',
                                 image_path=(IMAGE_DIR / (row['image_id'] + '.jpg')).as_posix()))
        write_csv(OUT / 'panel_scores.csv', combined)
        write_json(OUT / 'expansion_run.json', dict(status='completed', old_panel_count=len(combined)-len(expanded),
                   supplement_count=len(expanded), panel_count=len(combined), model_audit=audit,
                   reference_listing_overlap=reference_overlap(), fields=list(FIELDS)))
        (OUT / 'REPORT.md').write_text(
            f'# 冻结旧d_model补缺\n\n3图复现按事先容差通过；普通历史面板{len(combined)}图，原值{len(combined)-len(expanded)}图原样保留，补{len(expanded)}图。\n\n'
            'global为LHFeat逐通道mean/std的四相位均值，local_max为逐通道max的四相位均值；各自经旧PCA和scale变换至1647固定reference的5NN均距。历史风险仅两者hypot，不混称单一d_model。\n\n'
            '输入沿用img_v JPEG，PIL RGB/255、无resize；不能将其视为新research PNG同源实算。模型、冻结PCA、scale、reference及旧缓存未修改；未重训、重拟合或选参数。既有标签仅定义这次补缺面板，未进入描述符、参考、距离或复现选择。\n\n'
            '1647参考图48建筑与259研究图22建筑清单无交集；不证明checkpoint训练或epoch选择历史独立。此特征是固定历史参照下的图像分布偏离，不是经验证的几何复杂度、遮挡或置信度。\n', encoding='utf-8')
        write_json(OUT / 'field_contract.json', dict(schema_version='frozen_dmodel_supplement_v1', fields={
            FIELDS[0]: 'global LHFeat mean/std, frozen PCA/scale, mean five nearest reference Euclidean distances',
            FIELDS[1]: 'local channel max, frozen PCA/scale, mean five nearest reference Euclidean distances',
            FIELDS[2]: 'historical hypot(global,local); retain separate semantics',
            'value_origin': 'historical_unchanged or reproduced_supplement'}, source=str(IMAGE_DIR),
            old_values_overwritten=False, source_cache_modified=False, preprocessing='PIL RGB float32 /255; no resize; four phases 0,.25,.5,.75 physical batch=4'))
        print('Expansion completed: ' + str(audit), flush=True)
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        write_json(OUT / 'blocked.json', dict(status='blocked', reason=str(error), tolerances=tolerances))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expand', action='store_true')
    parser.add_argument('--device', default='auto')
    parser.add_argument('--retrospective-only', action='store_true')
    args = parser.parse_args()
    if args.retrospective_only:
        retrospective()
    else:
        run(args.expand, args.device)
