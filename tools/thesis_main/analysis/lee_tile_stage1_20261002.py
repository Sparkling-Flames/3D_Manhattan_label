"""第一步：固定 BEV 表示、等权 tile 投票，只研究人数变化；不拟合人员或难度。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from itertools import combinations
import json
from pathlib import Path
import warnings
import zlib

import numpy as np
from shapely.errors import GEOSException
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union

from tools.thesis_main.analysis.audit_supervisor_gt_sensitivity_20260922 import region_mesh

ROOT = Path(__file__).resolve().parents[3]
METHODS = ('mv50', 'mv_strict')
GATES = {'main_candidate', 'oos_doorway_exploratory', 'stable_nonorthogonal_separate'}


def tile_consensus(records):
    """复用既有 region_mesh；没有 GT 接口，不合并人员、不删细小 tile。"""
    if not records:
        raise ValueError('empty_roster')
    for key in ('id', 'worker'):
        if len({r[key] for r in records}) != len(records):
            raise ValueError('duplicate_' + key)
    polygons = []
    for r in records:
        if r['footprint'] is None:
            raise ValueError('unavailable_footprint:' + r['id'])
        xy = np.asarray(r['footprint'], dtype=float)
        if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) < 3 or not np.isfinite(xy).all():
            raise ValueError('invalid_footprint:' + r['id'])
        p = Polygon(xy)
        if not p.is_valid or not np.isfinite(p.area) or p.area <= 0:
            raise ValueError('invalid_footprint:' + r['id'])
        polygons.append(p)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', RuntimeWarning)
        mesh = region_mesh(polygons)
        domain = unary_union(polygons)
        area = mesh['area']
        tolerance = 1e-9 * max(1., domain.area)
        if not np.isfinite(area).all() or np.any(area <= 0):
            raise ValueError('nonpositive_or_nonfinite_tile')
        if abs(area.sum() - domain.area) > tolerance:
            raise ValueError('tile_partition_area_mismatch')
        restored = mesh['votes'] @ area
        if np.any(abs(restored - np.array([p.area for p in polygons])) > tolerance):
            raise ValueError('tile_worker_area_mismatch')
        support = mesh['votes'].sum(axis=0)
        selections = dict(mv50=2 * support >= len(records), mv_strict=2 * support > len(records))
        regions = {method: unary_union([t for t, keep in zip(mesh['tiles'], selected) if keep])
                   for method, selected in selections.items()}
        if any(not g.is_valid or not np.isfinite(g.area) for g in regions.values()):
            raise ValueError('invalid_consensus_geometry')
    return dict(mesh=mesh, regions=regions, selections=selections,
                warnings=[str(w.message) for w in caught])


def region_iou(a, b):
    intersection = a.intersection(b).area
    tolerance = 1e-12 * max(1., a.area, b.area)
    if (not np.isfinite(intersection) or intersection < -tolerance
            or intersection > min(a.area, b.area) + tolerance):
        raise ValueError('nonfinite_or_inconsistent_intersection')
    union = a.area + b.area - intersection
    # 仅裁剪浮点舍入越界（本轮约1e-15），不移动坐标或修复几何。
    return float(np.clip(intersection / union, 0., 1.)) if union else 1.0


def _summary(values):
    valid = [v for v in values if v is not None]
    return (float(np.mean(valid)), float(np.quantile(valid, .1)), float(np.quantile(valid, .9))) if valid else (None, None, None)


def replay_group(group, *, permutations, seed):
    if permutations < 1:
        raise ValueError('positive_permutations_required')
    records = sorted(group['records'], key=lambda r: r['id'])
    for key in ('id', 'worker'):
        if len({r[key] for r in records}) != len(records):
            raise ValueError('duplicate_' + key)
    rng = np.random.default_rng(seed)
    by_id = {r['id']: r for r in records}
    references = {v: Polygon(p) for v, p in group['references'].items() if p is not None}
    if any(not p.is_valid or p.area <= 0 for p in references.values()):
        raise ValueError('invalid_reference_footprint')
    cache, rows, notices = {}, [], []
    for draw in range(permutations):
        order = rng.permutation(len(records))
        previous = dict.fromkeys(METHODS)
        for k in range(1, len(records) + 1):
            members = tuple(sorted(records[i]['id'] for i in order[:k]))
            if members not in cache:
                try:
                    cache[members] = tile_consensus([by_id[i] for i in members])
                except (ValueError, GEOSException) as exc:
                    cache[members] = dict(error=str(exc))
                for note in cache[members].get('warnings', []):
                    notices.append(dict(stage='tiling', members=list(members), message=note))
            result = cache[members]
            for method in METHODS:
                row = dict(draw=draw, k=k, method=method, members='|'.join(members),
                           status='unavailable' if 'error' in result else 'ok', reason=result.get('error'),
                           tile_count=None, area_h2=None, empty=None, original_iou=None,
                           manual_revision_iou=None, change_from_previous=None)
                if 'error' not in result:
                    region = result['regions'][method]
                    row.update(tile_count=len(result['mesh']['tiles']), area_h2=float(region.area), empty=region.is_empty)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always', RuntimeWarning)
                        for version, reference in references.items():
                            row[version + '_iou'] = region_iou(region, reference)
                        if previous[method] is not None:
                            row['change_from_previous'] = 1 - region_iou(region, previous[method])
                    for note in caught:
                        notices.append(dict(stage='evaluation', draw=draw, k=k, method=method,
                                            members=list(members), message=str(note.message)))
                    previous[method] = region
                else:
                    previous[method] = None
                rows.append(row)
    summary = []
    for method in METHODS:
        for k in range(1, len(records) + 1):
            observed = [r for r in rows if r['method'] == method and r['k'] == k]
            unique = {r['members']: r for r in observed if r['status'] == 'ok'}
            row = dict(method=method, k=k, roster_n=len(records), draws=len(observed),
                       valid_draws=sum(r['status'] == 'ok' for r in observed), unique_subsets=len(unique),
                       empty_subsets=sum(r['empty'] for r in unique.values()))
            for version in ('original', 'manual_revision'):
                values = [r[version + '_iou'] for r in unique.values()]
                row[version + '_n'] = sum(v is not None for v in values)
                for stat, value in zip(('mean', 'p10', 'p90'), _summary(values)):
                    row[version + '_' + stat] = value
            row['change_mean'] = _summary([r['change_from_previous'] for r in observed])[0]
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always', RuntimeWarning)
                distances = [1 - region_iou(cache[tuple(a.split('|'))]['regions'][method],
                                            cache[tuple(b.split('|'))]['regions'][method])
                             for a, b in combinations(unique, 2)]
            notices.extend(dict(stage='member_distance', k=k, method=method, message=str(w.message)) for w in caught)
            row['member_pairs'] = len(distances)
            row['member_distance_mean'] = float(np.mean(distances)) if distances else (0. if k == len(records) and unique else None)
            summary.append(row)
    full = cache.get(tuple(sorted(by_id)))
    features = []
    if full and 'error' not in full:
        roster = sorted(by_id)
        for i, tile in enumerate(full['mesh']['tiles']):
            members = [roster[j] for j in range(len(roster)) if full['mesh']['votes'][j, i]]
            features.append(dict(type='Feature', geometry=mapping(tile), properties=dict(
                tile=i, members=members, support=len(members), roster_n=len(roster), area_h2=tile.area,
                mv50=bool(full['selections']['mv50'][i]), mv_strict=bool(full['selections']['mv_strict'][i]))))
    return dict(rows=rows, summary=summary, warnings=notices, full_tiles=features,
                computed_unique_subsets=len(cache), failures=dict(Counter(v['error'] for v in cache.values() if 'error' in v)))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def write_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def run(input_path, out):
    data = json.loads(input_path.read_text(encoding='utf-8'))
    if data['schema'] != 'lee_tile_stage1_input_v1':
        raise ValueError('unsupported_input_schema')
    plan = data['plan']
    all_rows, summaries, coverage, features, notices = [], [], [], [], []
    for image in data['images']:
        groups = defaultdict(list)
        for r in image['annotations']:
            gate = r['main_consensus_gate']['status']
            if r['independent'] and r['consensus_eligible'] and gate in GATES:
                groups[r['condition'], gate].append(r)
        coverage.append(dict(image=image['code'], population=len(image['annotations']),
            candidate_records=sum(map(len, groups.values())),
            excluded_or_ineligible=len(image['annotations'])-sum(map(len, groups.values())),
            upstream_gates=dict(Counter(r['main_consensus_gate']['status'] for r in image['annotations'])),
            geometry_unavailable=sum(r['footprint'] is None for rs in groups.values() for r in rs)))
        for (condition, gate), records in sorted(groups.items()):
            identity = dict(image=image['code'], condition=condition, gate=gate)
            group = dict(code=image['code'], condition=condition, gate=gate, records=records,
                         references={r['version']: r['footprint'] for r in image['references']})
            seed = plan['seed'] + zlib.crc32('|'.join(identity.values()).encode())
            result = replay_group(group, permutations=plan['permutations'], seed=seed)
            all_rows.extend(dict(**identity, **r) for r in result['rows'])
            summaries.extend(dict(**identity, **r) for r in result['summary'])
            notices.extend(dict(**identity, **r) for r in result['warnings'])
            for feature in result['full_tiles']:
                feature['properties'].update(identity)
                features.append(feature)
            print(f"{image['code']}: n={len(records)}, subsets={result['computed_unique_subsets']}, failures={sum(result['failures'].values())}", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / 'replay.csv', all_rows)
    write_csv(out / 'summary.csv', summaries)
    write_json(out / 'coverage.json', coverage)
    write_json(out / 'warnings.json', notices)
    write_json(out / 'full_tiles.geojson', dict(type='FeatureCollection', features=features,
        coordinate_note='Local BEV XZ in common camera-height h, NOT geographic longitude/latitude.'))
    write_json(out / 'field_contract.json', dict(schema='lee_tile_stage1_results_v1',
        replay_fields=list(all_rows[0]), summary_fields=list(summaries[0]),
        k='当前组实际抽取的不同真人数；缺几何时整个前缀不可计算，不减小k或改分母',
        sampling='每图/condition/gate固定16个无放回排列；同k参考均值与p10/p90按采到的不同成员集等权，不是穷举或置信区间',
        member_distance='不同已采成员集融合区域之间的平均1-IoU；全员只有一个集合，0是确定性机制',
        change='相邻人数融合区域的1-IoU，按有效相邻排列步骤平均；失败不跨步连接',
        empty='合法空融合与非空GT的IoU为0；两个空融合间的IoU定义为1',
        numerical_bounds='交集需有限且不超过较小区域面积（面积容差1e-12*max(1,area_a,area_b)）；仅把浮点IoU越界舍入裁回[0,1]，不改几何',
        reference='两版固定参考分别报告；OOS/门洞/参考存疑不解释为人员错误，无GT不阻塞稳定性计算',
        warnings='数值警告显式保存；未修复/吸附/缓冲输入，不把警告隐藏成完全通过'))
    plot_curves(summaries, out)
    report(data, coverage, summaries, notices, out)


def plot_curves(rows, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    keys = sorted({(r['image'], r['condition'], r['gate']) for r in rows})
    for name, fields, ylabel in [('reference_curves', [('original_mean', 'Original reference'), ('manual_revision_mean', 'Revised reference')], 'BEV IoU (reference agreement)'),
                                  ('stability_curves', [('member_distance_mean', 'Member variation'), ('change_mean', 'Change on adding a person')], '1 - IoU')]:
        fig, axes = plt.subplots((len(keys)+2)//3, 3, figsize=(14, 3.1*((len(keys)+2)//3)), squeeze=False, layout='constrained')
        for ax, key in zip(axes.flat, keys):
            for method, style in [('mv50', '-'), ('mv_strict', '--')]:
                selected = sorted([r for r in rows if (r['image'], r['condition'], r['gate']) == key and r['method'] == method], key=lambda r:r['k'])
                for (field, label), color in zip(fields, ('#1969a6', '#d36e27')):
                    y = [r[field] if r[field] is not None else np.nan for r in selected]
                    ax.plot([r['k'] for r in selected], y, style, color=color, label=label+' / '+method,
                            linewidth=1.4, marker='o' if len(selected)==1 else None, markersize=4)
            ax.set_title(key[0]+' | '+key[1]+'\n'+key[2], fontsize=9)
            ax.set_xlabel('Distinct people k'); ax.set_ylabel(ylabel); ax.set_ylim(-.02, 1.02); ax.grid(alpha=.2)
            from matplotlib.ticker import MaxNLocator
            if len(selected) == 1:
                ax.set_xticks([1]); ax.set_xlim(.5, 1.5)
            else:
                ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        for ax in list(axes.flat)[len(keys):]: ax.set_visible(False)
        axes.flat[0].legend(fontsize=6)
        fig.savefig(out / (name+'.png'), dpi=140); plt.close(fig)


def report(data, coverage, summary, notices, out):
    lines = ['# Lee tile 第一阶段：固定方法的人数重放', '',
        '本轮只改变参与人数和具体成员。BEV底面表示、等权投票固定；mv_strict仅检查平票。未分类人员，未加入d_model、BiLayout、质心权重、三维总分或难度回归。', '',
        f"固定面板：{len(data['images'])}图，{sum(r['population'] for r in coverage)}份作答；{sum(r['candidate_records'] for r in coverage)}份独立共识候选；其余按既有资格保留在覆盖表。",
        f"每组{data['plan']['permutations']}个固定随机排列。每一当前k重新用当前成员切tile，不使用GT或未来成员生成分区。缓存只复用完全相同成员集。",
        '原始/人工修订参考分别评价；特殊场景和参考存疑的GT距离仅为参考一致性。图间不混成总体准确率，不检验难度显著性。', '',
        '| 图片 | 条件/资格 | 人数 | MV50：k=1 → 全员，原始参考IoU | 严格多数：全员IoU |', '|---|---|---:|---:|---:|']
    keys = sorted({(r['image'], r['condition'], r['gate']) for r in summary})
    fmt = lambda v: 'NA' if v is None else f'{v:.4f}'
    for key in keys:
        rs = [r for r in summary if (r['image'],r['condition'],r['gate']) == key]
        n = max(r['k'] for r in rs)
        first = next(r for r in rs if r['method']=='mv50' and r['k']==1)
        last = next(r for r in rs if r['method']=='mv50' and r['k']==n)
        strict = next(r for r in rs if r['method']=='mv_strict' and r['k']==n)
        lines.append(f"| {key[0]} | {key[1]} / {key[2]} | {n} | {fmt(first['original_mean'])} → {fmt(last['original_mean'])} | {fmt(strict['original_mean'])} |")
    lines += ['', '## 解释边界', '',
        '- k=1均值来自固定排列实际抽到的不同单人；不是每图全部单人的穷举均值。',
        '- ≥50%在两人时保留并集，>50%保留交集；偶数人数的起伏可能由平票规则产生，不能通过平滑隐藏。',
        '- 全员时成员集合唯一，成员差异降到0是机制属性，不证明接近GT、未来人员不再改变或达到质量上限。',
        '- p10/p90为采到的成员集分布，不是总体置信区间。当前小面板是开发材料，不是独立验证集。',
        '- 几何交集有限性与面积上界单独检查；仅把约浮点舍入量级的IoU越界裁回[0,1]，不改变输入或聚合几何。',
        '- 门洞交界可能含无法合理标注部分；OOS的GT未必适用。不能由这些图的参考距离直接推断人员能力。',
        f'- 捕获数值警告 {len(notices)} 条，见 warnings.json；未做坐标吸附、buffer修复或删除碎片。', '',
        '## 工件', '',
        '- replay.csv：完整排列前缀、成员、状态、参考距离和相邻变化。',
        '- summary.csv：每图/条件/资格/方法/人数摘要、失败覆盖和成员差异。',
        '- full_tiles.geojson：各组全员tile几何及支持者；为本地h单位坐标，不是地理经纬度。',
        '- coverage.json、field_contract.json、warnings.json：分母、口径与数值诊断。',
        '- reference_curves.png、stability_curves.png：逐图曲线，不混合不同图片面板。', '',
        '本轮没有原图视觉裁决，也没有证明tile优于相同定义的逐点多数投票。下一步先检查这些曲线及覆盖，再决定扩展图片或增加一类质量指标。']
    (out / 'REPORT.md').write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT/'research/lee_tile_stage1_20261002/input.json')
    parser.add_argument('--out', type=Path, default=ROOT/'analysis_results/lee_tile_stage1_20261002')
    args = parser.parse_args()
    run(args.input, args.out)
