"""共同24人×10图画像及外建筑校准的固定4人构成探索；不定义正式人员类型。"""
from __future__ import annotations

import argparse
from itertools import combinations
import json
from pathlib import Path
import warnings

import numpy as np
from scipy.stats import rankdata
from shapely.geometry import Polygon

from .lee_tile_stage1_20261002 import ROOT, METHODS, region_iou, write_csv, write_json
from .lee_tile_precision_20261003 import (
    COUNT16, integration_basis, measure_masks, subset_mask, validate_refinement,
)

OUT = ROOT/'analysis_results/worker_profiles_20261003'
INVENTORY = ROOT/'analysis_results/research_panel_inventory_20261003'
# 沿用layout_metric_probe_20260926的既有网格；不选择最优权重。
LAMBDAS = (0, .25, .5, 1, 2)


def area_metrics(points, reference):
    polygons = []
    for p in (points, reference):
        xy = np.asarray(p, float)
        if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) < 3 or not np.isfinite(xy).all():
            raise ValueError('invalid_coordinates')
        g = Polygon(xy)
        if not g.is_valid or not np.isfinite(g.area) or g.area <= 0:
            raise ValueError('invalid_polygon')
        polygons.append(g)
    a, b = polygons
    d = a.centroid.distance(b.centroid)
    return dict(iou=region_iou(a, b), centroid_distance_h=float(d),
                centroid_normalized=float(d/np.sqrt(b.area)), area_h2=float(a.area),
                reference_area_h2=float(b.area), centroid_dx_h=a.centroid.x-b.centroid.x,
                centroid_dz_h=a.centroid.y-b.centroid.y)


def correlation(a, b):
    x, y = rankdata(a), rankdata(b)
    return float(np.corrcoef(x, y)[0, 1]) if np.std(x) and np.std(y) else None


def calibrate(iou, buildings, target):
    """只接收质量矩阵，目标建筑所有行都先隔离；上/下半仅是本折相对组。"""
    train = np.array([b != target for b in buildings])
    if not train.any() or train.all() or iou.ndim != 2 or iou.shape[0] != len(buildings):
        raise ValueError('invalid_lobo_panel')
    if not np.isfinite(iou).all() or iou.shape[1] % 2:
        raise ValueError('invalid_lobo_scores')
    mean = iou[train].mean(axis=0)
    ordered = np.sort(mean)
    mid = len(mean)//2
    if np.isclose(ordered[mid-1], ordered[mid], rtol=0, atol=1e-12):
        raise ValueError('cutoff_tie_requires_unassigned_group')
    higher = mean > (ordered[mid-1]+ordered[mid])/2
    balanced = np.mean([iou[np.array(buildings)==b].mean(axis=0)
                        for b in sorted(set(buildings)-{target})], axis=0)
    return dict(mean=mean, higher=higher, train_indices=np.flatnonzero(train).tolist(),
                building_equal_mean=balanced)


def composition_stats(basis, masks, members, higher, method):
    """全枚举子集的条件均值/离散度；区域差异是两次独立抽组的对称差面积期望。"""
    k = members.shape[1]
    count = higher[members].sum(axis=1)
    values = measure_masks(basis, masks, k, method)
    selected_totals = np.zeros((k+1, len(basis['patterns'])))
    for start in range(0, len(masks), 512):
        both = masks[start:start+512, None] & basis['patterns'][None, :]
        votes = COUNT16[both & 65535] + COUNT16[both >> 16]
        keep = 2*votes >= k if method == 'mv50' else 2*votes > k
        for h in range(k+1):
            selected_totals[h] += keep[count[start:start+512] == h].sum(axis=0)
    rows = []
    for h in range(k+1):
        chosen = count == h
        n = int(chosen.sum())
        if not n:
            continue
        q = selected_totals[h]/n
        pair_area = float(2*basis['area'] @ (q*(1-q)))
        for version, scores in values.items():
            v = scores[chosen]
            rows.append(dict(k=k, higher_n=h, lower_n=k-h, subset_n=n,
                method=method, version=version, iou_mean=float(v.mean()), iou_sd=float(v.std()),
                iou_p10=float(np.quantile(v, .1)), iou_p90=float(np.quantile(v, .9)),
                iou_min=float(v.min()), iou_max=float(v.max()),
                member_symdiff_h2=pair_area, member_symdiff_union=pair_area/float(basis['area'].sum()),
                mc_error_bound=0.))
    return rows, values


def panel_records(data, block):
    if data['schema'] != 'lee_tile_stage1_input_v1':
        raise ValueError('unsupported_input_schema')
    images = sorted(data['images'], key=lambda i: i['code'])
    if [i['code'] for i in images] != sorted(block['images']):
        raise ValueError('image_panel_mismatch')
    workers = sorted(block['workers'].split('|'))
    groups = []
    for im in images:
        rs = [r for r in im['annotations'] if r['condition']=='manual' and r['independent']
              and r['consensus_eligible'] and r['main_consensus_gate']['status']=='main_candidate']
        rs.sort(key=lambda r: r['worker'])
        if [r['worker'] for r in rs] != workers or len({r['id'] for r in rs}) != len(workers):
            raise ValueError('nonrectangular_or_duplicate_worker_panel:'+im['code'])
        if any(not r['quality_candidate'] or r['main_quality_gate']['status']!='candidate_pending_geometry'
               or r['footprint'] is None for r in rs):
            raise ValueError('quality_or_geometry_unavailable:'+im['code'])
        refs = {r['version']:r['footprint'] for r in im['references']}
        if refs.get('original') is None or any(p is None for p in refs.values()):
            raise ValueError('reference_unavailable:'+im['code'])
        groups.append((im, rs, refs))
    return workers, groups


def run(data, block, out):
    workers, groups = panel_records(data, block)
    buildings = [im['building'] for im, _, _ in groups]
    metrics, notices = [], []
    for im, rs, refs in groups:
        for r in rs:
            for version, p in refs.items():
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always', RuntimeWarning)
                    m = area_metrics(r['footprint'], p)
                notices.extend(dict(image=im['code'], stage='metrics', message=str(w.message)) for w in caught)
                metrics.append(dict(image=im['code'], building=im['building'], worker=r['worker'],
                                    record_id=r['id'], version=version, **m))
    write_csv(out/'answer_metrics.csv', metrics)
    by_cell = {(r['image'], r['worker'], r['version']):r for r in metrics}
    matrices = {}; selections = []
    for policy in ('original', 'revised_where_available'):
        for field in ('iou', 'centroid_distance_h', 'centroid_normalized'):
            matrix = np.array([[by_cell[im['code'], w,
                'manual_revision' if policy=='revised_where_available' and 'manual_revision' in refs else 'original'][field]
                for w in workers] for im, _, refs in groups])
            matrices[policy, field] = matrix
            write_csv(out/f'matrix_{policy}_{field}.csv',
                      [dict(image=im['code'], building=im['building'], **dict(zip(workers, row)))
                       for (im, _, _), row in zip(groups, matrix)])
        for im, _, refs in groups:
            selections.append(dict(policy=policy, image=im['code'], version='manual_revision'
                if policy=='revised_where_available' and 'manual_revision' in refs else 'original'))
    write_csv(out/'reference_policy.csv', selections)
    profiles, sensitivities, folds, assignments, calibration = [], [], [], [], {}
    for policy in ('original', 'revised_where_available'):
        iou = matrices[policy, 'iou']; centroid = matrices[policy, 'centroid_normalized']
        rank_iou = rankdata(-iou.mean(axis=0)); centered = iou-iou.mean(axis=1, keepdims=True)
        for j, worker in enumerate(workers):
            profiles.append(dict(policy=policy, worker=worker, image_n=len(groups),
                mean_iou=float(iou[:, j].mean()), median_iou=float(np.median(iou[:, j])),
                across_image_iou_sd=float(iou[:, j].std()), mean_image_centered_iou=float(centered[:, j].mean()),
                image_centered_iou_sd=float(centered[:, j].std()),
                mean_centroid_h=float(matrices[policy, 'centroid_distance_h'][:, j].mean()),
                mean_centroid_normalized=float(centroid[:, j].mean()), descriptive_iou_rank=float(rank_iou[j])))
        for target in sorted(set(buildings)):
            fit = calibrate(iou, buildings, target)
            calibration[policy, target] = fit
            train = fit['train_indices']; test = [j for j, b in enumerate(buildings) if b==target]
            held = iou[test].mean(axis=0)
            folds.append(dict(policy=policy, target_building=target, train_image_n=len(train),
                train_building_n=len(set(buildings))-1, target_image_n=len(test),
                train_images='|'.join(groups[j][0]['code'] for j in train),
                target_images='|'.join(groups[j][0]['code'] for j in test),
                train_target_iou_spearman=correlation(fit['mean'], held),
                image_vs_building_weight_spearman=correlation(fit['mean'], fit['building_equal_mean']),
                target_higher_minus_lower_single_iou=float(held[fit['higher']].mean()-held[~fit['higher']].mean())))
            ordered = np.sort(fit['building_equal_mean']); mid = len(workers)//2
            balanced_tie = np.isclose(ordered[mid-1], ordered[mid], rtol=0, atol=1e-12)
            balanced_cut = (ordered[mid-1]+ordered[mid])/2
            for j, worker in enumerate(workers):
                assignments.append(dict(policy=policy, target_building=target, worker=worker,
                    calibration_mean_iou=float(fit['mean'][j]), calibration_rank=float(rankdata(-fit['mean'])[j]),
                    relative_half='higher' if fit['higher'][j] else 'lower',
                    building_equal_higher=None if balanced_tie else bool(fit['building_equal_mean'][j]>balanced_cut)))
            for weight in LAMBDAS:
                loss = (1-iou[train])+weight*centroid[train]
                ranks = rankdata(loss.mean(axis=0)); base = rankdata(-fit['mean'])
                for j, worker in enumerate(workers):
                    sensitivities.append(dict(policy=policy, target_building=target, worker=worker,
                        weight=weight, calibration_loss_mean=float(loss[:, j].mean()),
                        loss_rank=float(ranks[j]), rank_change_from_iou=float(ranks[j]-base[j])))
    write_csv(out/'worker_profiles.csv', profiles)
    write_csv(out/'lobo_folds.csv', folds); write_csv(out/'lobo_assignments.csv', assignments)
    write_csv(out/'weight_sensitivity.csv', sensitivities)
    # ponytail: exact C(24,4)=10626 is small; larger k needs a declared sampling budget, not silent subsampling.
    members = np.array(list(combinations(range(len(workers)), 4)), dtype=np.uint8)
    masks = np.array([subset_mask(s) for s in members], dtype=np.uint32)
    arrays = dict(members=members, masks=masks)
    rows, checks = [], []
    for index, (im, rs, refs) in enumerate(groups):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', RuntimeWarning)
            basis = integration_basis(rs, refs)
            difference, inner = validate_refinement(basis, rs)
            checks.append(dict(image=im['code'], max_prefix_symmetric_difference_h2=difference))
            notices.extend(dict(image=im['code'], stage='tiling_or_prefix', message=s) for s in basis['warnings']+inner)
            for policy in ('original', 'revised_where_available'):
                higher = calibration[policy, im['building']]['higher']
                for method in METHODS:
                    current, values = composition_stats(basis, masks, members, higher, method)
                    rows.extend(dict(image=im['code'], building=im['building'], calibration_policy=policy, **r) for r in current)
                    if policy == 'original':
                        for version, scores in values.items():
                            arrays[f'g{index}_{method}_{version}'] = scores
            notices.extend(dict(image=im['code'], stage='integration', message=str(w.message)) for w in caught)
        print(f"{im['code']}: 24 people, {len(members)} exact 4-person subsets", flush=True)
    write_csv(out/'composition_exact.csv', rows)
    np.savez_compressed(out/'subsets.npz', **arrays)
    write_json(out/'rosters.json', dict(workers=workers, groups=[dict(key=f'g{j}', image=im['code'],
        building=im['building'], record_ids=[r['id'] for r in rs]) for j, (im, rs, _) in enumerate(groups)]))
    write_json(out/'warnings.json', notices); write_json(out/'validation.json', checks)
    paired = {im['code'] for im, _, refs in groups if 'manual_revision' in refs}
    aggregates = []
    for cohort, images in [('all10', {im['code'] for im, _, _ in groups}), ('paired4', paired)]:
        for policy in ('original', 'revised_where_available'):
            for version in ('original', 'manual_revision') if cohort=='paired4' else ('original',):
                for method in METHODS:
                    for h in range(5):
                        part = [r for r in rows if r['image'] in images and r['calibration_policy']==policy
                                and r['version']==version and r['method']==method and r['higher_n']==h]
                        if len(part) != len(images):
                            raise ValueError('incomplete_fixed_composition_panel')
                        aggregates.append(dict(cohort=cohort, image_n=len(images), calibration_policy=policy,
                            version=version, method=method, higher_n=h, lower_n=4-h,
                            **{key:float(np.mean([r[key] for r in part])) for key in
                               ('iou_mean', 'iou_sd', 'member_symdiff_union')}))
    write_csv(out/'composition_summary.csv', aggregates)
    summary = dict(status='completed', image_n=len(groups), worker_n=len(workers), building_n=len(set(buildings)),
        metrics_n=len(metrics), paired_reference_images=sorted(paired), subsets_per_image=len(members),
        composition_rows=len(rows), warnings_n=len(notices),
        iou_centroid_loss_spearman=correlation(1-matrices['original', 'iou'].mean(axis=0), matrices['original', 'centroid_normalized'].mean(axis=0)),
        reference_policy_profile_spearman=correlation(matrices['original', 'iou'].mean(axis=0), matrices['revised_where_available', 'iou'].mean(axis=0)),
        lobo_folds=folds)
    write_json(out/'summary.json', summary)
    write_json(out/'field_contract.json', dict(schema='worker_profiles_composition_v1',
        metrics_fields=list(metrics[0]), profile_fields=list(profiles[0]), fold_fields=list(folds[0]),
        assignment_fields=list(assignments[0]), weight_fields=list(sensitivities[0]), composition_fields=list(rows[0]),
        centroid='区域面积质心；距离h、除以sqrt(GT面积)无量纲；dx/dz为各图相机坐标，不跨图平均方向',
        profile='图片等权；排名仅描述当前完整块。跨图SD含图片与人图交互，不全归因个人不稳定。',
        calibration='每目标建筑整栋隔离；外建筑图片等权平均IoU分上/下12人。本折相对组非稳定人员类型，边界并列报错不任意切分。',
        reference_policy='original为全10原GT；revised_where_available是4图换修订、6图仍原GT的明确混合敏感性，非10图修订真值。留出建筑的任何版本GT都不参与校准。',
        weighting='lambda=(0,.25,.5,1,2)只报告排名敏感性；不选最终权重，不用于本轮融合或人员分组。',
        composition='固定4人穷举10626子集；每种构成内所有子集等权。IoU SD/p10/p90描述固定池成员替换差异，非总体CI。',
        member_area='两次独立均匀抽取同构成子集（允许两次相同）区域对称差期望2 sum(area*q*(1-q))；归一化除同图全员并集面积。不是平均1-IoU；不依赖GT。',
        aggregates='同图固定构成后图片等权；mean(iou_sd)为平均图内SD，非组均值标准误或汇总总体SD。',
        subset_storage='subsets.npz members/masks共用；g序号对应rosters；g_method_version是与members逐行对应的IoU，无去重抽样。',
        failure='完整共同块不可计算则中止并保留设计/源，不删人、不补点、不改顺序。',
        scope='不拟合稳定性停止阈值、人员正式类型或新难度；无视觉审核，无独立验证集。'))
    figures(workers, groups, matrices, assignments, aggregates, out)


def figures(workers, groups, matrices, assignments, aggregates, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), layout='constrained')
    for ax, field, title in zip(axes, ('iou', 'centroid_normalized'), ('Original-reference IoU', 'Area-centroid distance / sqrt(reference area)')):
        artist = ax.imshow(matrices['original', field], aspect='auto', cmap='viridis',
                           vmin=0, vmax=1 if field=='iou' else None)
        ax.set(xticks=range(len(workers)), xticklabels=workers, yticks=range(len(groups)),
               yticklabels=[g[0]['code'] for g in groups], title=title)
        ax.tick_params(axis='x', rotation=90, labelsize=8); ax.tick_params(axis='y', labelsize=8)
        fig.colorbar(artist, ax=ax, shrink=.8)
    fig.suptitle('Same 24 people on 10 images; descriptive metrics, not validated worker classes')
    fig.savefig(out/'quality_matrices.png', dpi=150); plt.close(fig)
    targets = sorted({r['target_building'] for r in assignments})
    rank = np.array([[next(r['calibration_rank'] for r in assignments if r['policy']=='original'
                    and r['target_building']==b and r['worker']==w) for w in workers] for b in targets])
    fig, ax = plt.subplots(figsize=(12, 4.5), layout='constrained')
    a = ax.imshow(rank, aspect='auto', vmin=1, vmax=24, cmap='viridis_r')
    ax.set(xticks=range(len(workers)), xticklabels=workers, yticks=range(len(targets)), yticklabels=targets,
           title='Calibration rank after excluding each target building (1 = higher IoU)')
    ax.tick_params(axis='x', rotation=90); fig.colorbar(a, ax=ax)
    fig.savefig(out/'lobo_ranks.png', dpi=150); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), layout='constrained')
    for method, style in [('mv50', 'o-'), ('mv_strict', 's--')]:
        rs = [r for r in aggregates if r['cohort']=='all10' and r['calibration_policy']=='original' and r['method']==method]
        for ax, field, title in zip(axes, ('iou_mean', 'iou_sd', 'member_symdiff_union'),
                ('Reference IoU: image-equal mean', 'Within-image IoU SD: image-equal mean', 'Expected member area difference / union')):
            ax.plot([r['higher_n'] for r in rs], [r[field] for r in rs], style, label=method)
            ax.set(title=title, xlabel='Number from higher calibration half (total = 4)', xticks=range(5))
            ax.grid(alpha=.2); ax.legend()
    fig.suptitle('Exact fixed-4-person composition; groups calibrated outside target building; no population CI')
    fig.savefig(out/'composition.png', dpi=150); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--input', type=Path, help='重放本目录固定input，读取相邻block.json')
    args = parser.parse_args(); out = args.out
    if (out/'design.json').exists():
        raise ValueError('output_exists_use_new_directory')
    out.mkdir(parents=True, exist_ok=True)
    block = json.loads(((args.input.parent/'block.json') if args.input else INVENTORY/'next_panels.json').read_text(encoding='utf-8'))
    if not args.input:
        block = block['b']['blocks'][0]
    write_json(out/'design.json', dict(status='started', stage='S3-B and S4 pilot',
        contract='consensus_research_20260923_v1', block=block, lambda_grid=LAMBDAS, fixed_k=4,
        grouping='outside-target-building mean original IoU; equal halves; mixed-reference sensitivity separate',
        inference='exact finite-pool description; no significance test, trained worker taxonomy or weight selection'))
    write_json(out/'block.json', block)
    if args.input:
        data = json.loads(args.input.read_text(encoding='utf-8'))
        write_json(out/'input.json', data)
        write_json(out/'source_binding.json', json.loads((args.input.parent/'source_binding.json').read_text(encoding='utf-8')))
    else:
        from .lee_difficulty_20261003 import collect
        data = collect(out, chosen=block['images'], stage='S3-B', max_k=None)
    run(data, block, out)
    design = json.loads((out/'design.json').read_text(encoding='utf-8'))
    write_json(out/'design.json', dict(design, status='completed'))


if __name__ == '__main__':
    main()
