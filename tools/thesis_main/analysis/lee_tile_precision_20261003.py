"""固定人员池的离线人数均值补强；全员细分只作积分基底，不改变前缀投票。"""
from __future__ import annotations

import argparse
from collections import defaultdict
from itertools import combinations
import json
from math import comb, log, sqrt
from pathlib import Path
import warnings
import zlib

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .lee_tile_stage1_20261002 import (
    ROOT, GATES, METHODS, tile_consensus, region_iou, write_csv, write_json,
)

COUNT16 = np.array([i.bit_count() for i in range(65536)], dtype=np.uint8)


def exact_ks(n):
    return list(range(1, n+1)) if n <= 9 else sorted({1, 2, n-2, n-1, n})


def subset_mask(indices):
    return sum(1 << int(i) for i in indices)


def mc_bound(draws, comparisons, alpha=.05):
    if draws < 1 or comparisons < 0 or not 0 < alpha < 1:
        raise ValueError('invalid_precision_design')
    return sqrt(log(2*comparisons/alpha)/(2*draws)) if comparisons else 0.


def integration_basis(records, references):
    if not 1 <= len(records) <= 32:
        raise ValueError('bitmask_requires_1_to_32_distinct_people')
    result = tile_consensus(records)
    mesh = result['mesh']
    bits = np.left_shift(np.uint32(1), np.arange(len(records), dtype=np.uint32))
    raw_patterns = mesh['votes'].astype(np.uint32).T @ bits
    patterns, inverse = np.unique(raw_patterns, return_inverse=True)
    area = np.bincount(inverse, weights=mesh['area'])
    refs = {}; overlap = {}
    for version, points in references.items():
        if points is None:
            continue
        xy = np.asarray(points, float)
        if xy.ndim != 2 or xy.shape[1] != 2 or not np.isfinite(xy).all():
            raise ValueError('invalid_reference_coordinates:' + version)
        g = Polygon(xy)
        if not g.is_valid or not np.isfinite(g.area) or g.area <= 0:
            raise ValueError('invalid_reference_footprint:' + version)
        intersection = np.array([t.intersection(g).area for t in mesh['tiles']])
        if (not np.isfinite(intersection).all() or np.any(intersection < -1e-12)
                or np.any(intersection > mesh['area'] + 1e-10)):
            raise ValueError('invalid_cell_reference_intersection')
        refs[version] = g
        overlap[version] = np.bincount(inverse, weights=intersection, minlength=len(area))
    return dict(n=len(records), mesh=mesh, patterns=patterns, area=area,
                overlap=overlap, references=refs, warnings=result['warnings'])


def measure_masks(basis, masks, k, method):
    values = {v: [] for v in basis['references']}
    # ponytail: uint32 is enough for this <=24-person panel; fail above 32 instead of silently truncating.
    for start in range(0, len(masks), 512):
        both = masks[start:start+512, None] & basis['patterns'][None, :]
        votes = COUNT16[both & 65535] + COUNT16[both >> 16]
        keep = 2*votes >= k if method == 'mv50' else 2*votes > k
        a = np.einsum('ij,j->i', keep, basis['area'])
        for version, g in basis['references'].items():
            inter = np.einsum('ij,j->i', keep, basis['overlap'][version])
            iou = inter / (g.area + a - inter)
            if not np.isfinite(iou).all() or np.any(iou < -1e-12) or np.any(iou > 1+1e-12):
                raise ValueError('invalid_integrated_iou')
            values[version].append(np.clip(iou, 0, 1))
    return {v: np.concatenate(parts) for v, parts in values.items()}


def area_expectations(basis, k, method):
    n = basis['n']; support = np.array([int(p).bit_count() for p in basis['patterns']])
    threshold = (k+1)//2 if method == 'mv50' else k//2+1
    probability = {s: sum(comb(int(s), j)*comb(n-int(s), k-j)
                         for j in range(max(threshold, k-n+int(s)), min(int(s), k)+1))/comb(n, k)
                   for s in set(support)}
    q = np.array([probability[s] for s in support]); a = float(basis['area'] @ q)
    return {v: dict(expected_area_h2=a, expected_intersection_h2=float(basis['overlap'][v] @ q),
                   expected_omission_h2=float(g.area-basis['overlap'][v] @ q),
                   expected_extension_h2=float(a-basis['overlap'][v] @ q))
            for v, g in basis['references'].items()}


def validate_refinement(basis, records):
    """代表性前缀仍用原函数重新切片，对照形状和各参考IoU。"""
    maximum = 0.; notices = []
    for k in sorted({1, min(2, len(records)), max(1, len(records)//2), len(records)}):
        current = tile_consensus(records[:k]); notices.extend(current['warnings'])
        support = basis['mesh']['votes'][:k].sum(axis=0)
        for method in METHODS:
            selected = 2*support >= k if method == 'mv50' else 2*support > k
            offline = unary_union([t for t, keep in zip(basis['mesh']['tiles'], selected) if keep])
            error = current['regions'][method].symmetric_difference(offline).area
            maximum = max(maximum, error)
            if not np.isfinite(error) or error > 1e-9*max(1., float(basis['area'].sum())):
                raise ValueError('prefix_geometry_not_equivalent')
            got = measure_masks(basis, np.array([subset_mask(range(k))], dtype=np.uint32), k, method)
            for v, g in basis['references'].items():
                if abs(got[v][0]-region_iou(current['regions'][method], g)) > 1e-10:
                    raise ValueError('prefix_iou_not_equivalent')
    return maximum, notices


def run(input_path, out, draws=16384, seed=20261003):
    data = json.loads(input_path.read_text(encoding='utf-8'))
    if data['schema'] != 'lee_tile_stage1_input_v1':
        raise ValueError('unsupported_input_schema')
    groups = []; coverage = []
    for image in data['images']:
        parts = defaultdict(list)
        for r in image['annotations']:
            gate = r['main_consensus_gate']['status']
            if r['independent'] and r['consensus_eligible'] and gate in GATES:
                parts[r['condition'], gate].append(r)
        coverage.append(dict(image=image['code'], input_records=len(image['annotations']),
            candidate_records=sum(map(len, parts.values())), excluded_records=len(image['annotations'])-sum(map(len, parts.values()))))
        for (condition, gate), records in sorted(parts.items()):
            groups.append((dict(image=image['code'], condition=condition, gate=gate),
                           sorted(records, key=lambda r: r['id']),
                           {r['version']: r['footprint'] for r in image['references']}))
    comparisons = sum(2*(len(rs)-len(exact_ks(len(rs))))*sum(p is not None for p in refs.values())
                      for _, rs, refs in groups)
    bound = mc_bound(draws, comparisons)
    out.mkdir(parents=True, exist_ok=True)
    plan = dict(schema='lee_tile_precision_v1', status='started', input=input_path.relative_to(ROOT).as_posix() if input_path.is_relative_to(ROOT) else str(input_path),
        draws=draws, seed=seed, simultaneous_mc_comparisons=comparisons, family_alpha=.05,
        mean_error_bound=bound, target_mean_resolution=.02, precision_target_met=bound <= .02,
        scope='固定人员池、固定几何的离线均值；无总体抽样置信度、无量化分位数精度、无最佳人数判定',
        estimator='小组全枚举；大组k=1,2,N-2,N-1,N枚举，其余按独立均匀排列频次平均，不去重。',
        offline_basis='全员tile是当前子集区域指示函数的细分积分基底；子集选取与投票只读取该子集，不是在线预测。')
    write_json(out/'design.json', plan)  # 在任何曲线计算前写出固定设计，不根据结果调整批次数。
    summaries = []; support_rows = []; notices = []; checks = []; orders_saved = {}; rosters = []
    for index, (ident, records, refs) in enumerate(groups):
        n = len(records); key = f'g{index}'
        local_seed = seed + zlib.crc32('|'.join(ident.values()).encode())
        rng = np.random.default_rng(local_seed)
        orders = np.array([rng.permutation(n) for _ in range(draws)], dtype=np.uint8) if n>9 else np.empty((0,n),dtype=np.uint8)
        orders_saved[key] = orders
        rosters.append(dict(**ident, key=key, record_ids=[r['id'] for r in records], workers=[r['worker'] for r in records], seed=local_seed))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', RuntimeWarning)
            # 无效几何直接中止并保留已写设计；不删除人员后继续计算或发布成功摘要。
            basis = integration_basis(records, refs)
            difference, inner = validate_refinement(basis, records)
            notices.extend(dict(**ident, stage='tiling_or_prefix', message=s) for s in basis['warnings']+inner)
            checks.append(dict(**ident, n=n, tiles=len(basis['mesh']['tiles']), patterns=len(basis['patterns']),
                               max_prefix_symmetric_difference_h2=difference))
            p = np.array([int(b).bit_count()/n for b in basis['patterns']])
            d = float(basis['area'] @ (p*(1-p))); union = float(basis['area'].sum())
            support_rows.append(dict(**ident, n=n, raw_disagreement_h2=d, raw_disagreement_union=d/union,
                raw_pair_symmetric_difference_union=2*n/(n-1)*d/union if n>1 else None))
            prefix = np.bitwise_or.accumulate(np.left_shift(np.uint32(1), orders.astype(np.uint32)), axis=1)
            for k in range(1, n+1):
                exact = k in exact_ks(n)
                masks = np.array([subset_mask(s) for s in combinations(range(n), k)], dtype=np.uint32) if exact else prefix[:, k-1]
                for method in METHODS:
                    scores = measure_masks(basis, masks, k, method)
                    areas = area_expectations(basis, k, method)
                    for version, values in scores.items():
                        mean = float(values.mean()); radius = 0. if exact else bound
                        summaries.append(dict(**ident, method=method, version=version, n=n, k=k,
                            estimator='exact' if exact else 'mc', evaluated_draws=len(masks),
                            unique_subsets=len(np.unique(masks)), total_subsets=comb(n,k), iou_mean=mean,
                            mc_error_bound=radius, mean_lower=max(0.,mean-radius), mean_upper=min(1.,mean+radius),
                            **areas[version]))
            notices.extend(dict(**ident, stage='integration_or_validation', message=str(w.message)) for w in caught)
        print(f"{ident['image']}: n={n}, exact_k={exact_ks(n)}, MC draws={len(orders)}, checked", flush=True)
    write_csv(out/'curves.csv', summaries); write_csv(out/'raw_disagreement.csv', support_rows)
    write_json(out/'coverage.json', coverage); write_json(out/'warnings.json', notices)
    write_json(out/'validation.json', checks); write_json(out/'rosters.json', rosters)
    np.savez_compressed(out/'orders.npz', **orders_saved)
    write_json(out/'field_contract.json', dict(schema='lee_tile_precision_v1', curve_fields=list(summaries[0]),
        sampling_unit='固定池内均匀k子集；MC不同排列为独立抽样，重复子集保留出现频次，跨k/规则/参考共享排列',
        confidence='Hoeffding界+union bound：同时覆盖本运行所有MC参考均值，95%仅指计算抽样；精确点界0不代表总体无不确定性',
        missing='缺参考不生成该版本曲线；无效候选/参考直接报错，不改变资格分母；n=1原始人员对分歧为null',
        area='面积期望由超几何尾概率精算，不是平均IoU；单位h²，非实测米²',
        stability='本轮仅替换参考IoU均值；旧成员距离、增人Jaccard、分位数未获本轮精度保证',
        reproducibility='orders.npz按rosters.json的key及记录序号保存完整排列；枚举组合按记录序号字典序确定'))
    plot(summaries, out)
    plan['status'] = 'completed'
    write_json(out/'design.json', plan)
    return summaries


def plot(rows, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups = list(dict.fromkeys((r['image'],r['condition'],r['gate']) for r in rows))
    fig, axes = plt.subplots((len(groups)+2)//3, 3, figsize=(16, 3.5*((len(groups)+2)//3)), squeeze=False)
    for ax, key in zip(axes.flat, groups):
        panel = [r for r in rows if (r['image'],r['condition'],r['gate'])==key]
        for method, color in [('mv50','tab:blue'),('mv_strict','tab:orange')]:
            for version, style in [('original','-'),('manual_revision','--')]:
                series = [r for r in panel if r['method']==method and r['version']==version]
                if not series: continue
                x=[r['k'] for r in series]; y=[r['iou_mean'] for r in series]
                ax.plot(x,y,style,color=color,label=f'{method} / {version}',linewidth=1.2)
                ax.fill_between(x,[r['mean_lower'] for r in series],[r['mean_upper'] for r in series],color=color,alpha=.10)
                exact=[r for r in series if r['estimator']=='exact']
                ax.scatter([r['k'] for r in exact],[r['iou_mean'] for r in exact],color=color,s=15)
        if max(r['n'] for r in panel)==1: ax.set_xlim(.5,1.5); ax.set_xticks([1])
        ax.set(title=f'{key[0]} | {key[1]}',xlabel='Number of people',ylabel='Mean reference IoU',ylim=(0,1))
        ax.grid(alpha=.2); ax.legend(fontsize=6)
    for ax in list(axes.flat)[len(groups):]: ax.set_visible(False)
    fig.suptitle('Fixed-pool reference means: dots = exact; bands = simultaneous MC error bounds', fontsize=13)
    fig.tight_layout(rect=(0,0,1,.97)); fig.savefig(out/'reference_means.png',dpi=150); plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT/'research/lee_tile_stage1_20261002/input.json')
    parser.add_argument('--out', type=Path, default=ROOT/'analysis_results/lee_tile_precision_20261003')
    parser.add_argument('--draws', type=int, default=16384)
    args = parser.parse_args()
    run(args.input, args.out, args.draws)
