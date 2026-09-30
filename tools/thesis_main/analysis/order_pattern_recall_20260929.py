"""改前几何的顺序漏召回研究；不修改审核状态或分析资格。"""
from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path

import numpy as np

from .finalize_review_20260928 import dump, read, write_csv
from .order_review_20260928 import diagnose_points
from .build_order_gt_screened_20260928 import NO_RECALL

ROOT = Path(__file__).resolve().parents[3]
RULES = ('any_acute', 'consecutive_acute', 'dense_two_pairs_24px',
         'dense_three_pairs_24px', 'near_bearing_depth_jump', 'recall_union')


def ring_relation(before, after):
    """固定点对身份上的无向闭环；起点和遍历方向不改变邻接。"""
    if (not before or any(type(v) is not int for v in list(before) + list(after))
            or len(set(before)) != len(before) or len(set(after)) != len(after)
            or set(before) != set(after)):
        raise ValueError('invalid_pair_permutation')
    if list(before) == list(after):
        return 'unchanged'
    edges = lambda order: {tuple(sorted((v, order[(i + 1) % len(order)]))) for i, v in enumerate(order)}
    return 'equivalent' if edges(before) == edges(after) else 'adjacency_changed'


def initial_order(obj, seed):
    identity = list(range(len(obj['links_zero_based'])))
    if obj['object_id'] in seed:
        order = list(seed[obj['object_id']]['order'])
    elif obj['object_kind'] == 'gt_manual_revision':
        order = sorted(identity, key=lambda i: obj['preprocessed_points'][obj['links_zero_based'][i][0]][0])
    else:
        order = identity
    ring_relation(identity, order)
    return order


def prechange_features(obj, order):
    """只接受改前排列。像素宽1024、相机高度1；顶部深度不是独立测量。"""
    links, points = obj.get('links_zero_based'), obj.get('preprocessed_points')
    result = dict(feature_status='pairing_unavailable', pair_count=len(links or []),
                  any_acute=False, acute_count=0, min_acute_angle_deg=None,
                  consecutive_acute=False, crossing_count=0, dense_two_pairs_24px=False,
                  dense_three_pairs_24px=False, min_periodic_gap_px=None,
                  max_depth_ratio_within_24px=None, near_bearing_depth_jump=False,
                  curve_max_abs_latitude_deg=None, min_edge_range_over_median_vertex_range=None)
    if obj['preprocessing_status'] != 'ready':
        return result
    if points is None or links is None:
        raise ValueError('ready_source_missing_points_or_pairs:' + obj['object_id'])
    ring_relation(list(range(len(links))), order)
    p = np.asarray(points, float)
    if (p.ndim != 2 or p.shape[1] != 2 or not np.isfinite(p).all()
            or any(len(pair) != 2 or any(type(i) is not int for i in pair) for pair in links)
            or sorted(i for pair in links for i in pair) != list(range(len(p)))):
        raise ValueError('invalid_source_geometry:' + obj['object_id'])
    pairs = np.asarray([links[i] for i in order], int)
    top, bottom = p[pairs[:, 0]], p[pairs[:, 1]]
    if np.any(np.abs((top[:, 0] - bottom[:, 0] + 512) % 1024 - 512) > 1e-6):
        raise ValueError('source_not_shared_x:' + obj['object_id'])
    metrics, status = diagnose_points(p.tolist(), pairs.tolist())
    result.update(feature_status=status, any_acute=bool(metrics['acute_vertices']),
                  acute_count=len(metrics['acute_vertices']),
                  min_acute_angle_deg=min(metrics['acute_angles_degrees'].values(), default=None),
                  consecutive_acute=metrics['consecutive_acute'], crossing_count=len(metrics['crossings']),
                  dense_three_pairs_24px=bool(metrics['dense_pair_groups']))
    xs = top[:, 0] % 1024
    angular_order = np.argsort(xs, kind='stable')
    gap = (np.roll(xs[angular_order], -1) - xs[angular_order]) % 1024
    result.update(min_periodic_gap_px=float(gap.min()), dense_two_pairs_24px=bool(np.any(gap <= 24)))
    if status != 'ok':
        return result
    radius = -1 / np.tan(np.pi * (.5 - bottom[:, 1] / 512))
    radial = radius[angular_order]
    ratio = np.maximum(radial / np.roll(radial, -1), np.roll(radial, -1) / radial)
    close_ratio = ratio[gap <= 24]
    result.update(max_depth_ratio_within_24px=float(close_ratio.max()) if len(close_ratio) else None,
                  near_bearing_depth_jump=bool(np.any((gap <= 24) & (ratio >= 1.5))))
    # 与 geometry.py 的水平地面及 paired-floor 深度代理一致，不做 Manhattan 拟合。
    u = 2 * np.pi * (xs / 1024 - .5)
    floor = np.column_stack((radius * np.sin(u), -np.ones(len(u)), -radius * np.cos(u)))
    ceiling = floor.copy()
    ceiling[:, 1] = radius * np.tan(np.pi * (.5 - top[:, 1] / 512))
    latitudes, horizontal_ranges = [], []
    for vertices in (floor, ceiling):
        samples = vertices[:, None, :] + (np.roll(vertices, -1, axis=0) - vertices)[:, None, :] * np.linspace(0, 1, 65)[None, :, None]
        horizontal = np.linalg.norm(samples[:, :, [0, 2]], axis=2)
        horizontal_ranges.append(float(horizontal.min()))
        latitudes.append(float(np.degrees(np.abs(np.arctan2(samples[:, :, 1], horizontal))).max()))
    result.update(curve_max_abs_latitude_deg=max(latitudes),
                  min_edge_range_over_median_vertex_range=min(horizontal_ranges) / float(np.median(radius)))
    return result


def candidate_reason(row):
    if row['object_kind'] != 'annotation':
        return 'gt_separate_analysis'
    if row['cleaning_disposition'] in {'excluded_by_review', 'historical_not_accepted'}:
        return 'excluded'
    if row['current_status'] == 'confirmed':
        return 'already_confirmed'
    if row.get('image_code') in NO_RECALL:
        return 'user_no_recall_image'
    if row['current_status'] == 'pairing' or row['feature_status'] == 'pairing_unavailable':
        return 'pairing_deferred'
    if row['feature_status'] != 'ok':
        return 'geometry_unavailable'
    if row['pair_count'] <= 4 and not row['explicit_order_evidence']:
        return 'four_pairs_without_human_order_evidence'
    if (row['explicit_order_evidence'] or row['any_acute'] or row['dense_three_pairs_24px']
            or row['near_bearing_depth_jump']):
        return 'candidate'
    return 'no_rule_hit'


def _read_context():
    csv.field_size_limit(32 * 1024 * 1024)
    with (ROOT / 'analysis_results/order_gt_screened_20260928/逐对象筛选.csv').open(encoding='utf-8-sig') as handle:
        previous = {r['object_id']: r['state'] for r in csv.DictReader(handle)}
    with (ROOT / 'analysis_results/order_candidates_20260928/全量排序初筛.csv').open(encoding='utf-8-sig') as handle:
        explicit = {r['object_id'] for r in csv.DictReader(handle) if json.loads(r['explicit_order_evidence'])}
    history = read(ROOT / 'analysis_results/order_gt_screened_20260928/received_orders.json')['history']
    return previous, explicit, history


def _evaluation(rows, cohort, stratum, rule):
    positives = [r for r in rows if r['order_change'] == 'adjacency_changed']
    negatives = [r for r in rows if r['order_change'] in {'unchanged', 'equivalent'}]
    hit = lambda r: r[rule] if rule != 'recall_union' else r['any_acute'] or r['dense_three_pairs_24px'] or r['near_bearing_depth_jump']
    tp, fp = sum(bool(hit(r)) for r in positives), sum(bool(hit(r)) for r in negatives)
    return dict(cohort=cohort, stratum=stratum, rule=rule, image_count=len({r['image_id'] for r in rows}),
                changed=len(positives), unchanged_or_equivalent=len(negatives), changed_hit=tp, unchanged_hit=fp,
                observed_changed_coverage=tp / len(positives) if positives else None,
                observed_unchanged_hit_rate=fp / len(negatives) if negatives else None,
                observed_hit_changed_fraction=tp / (tp + fp) if tp + fp else None)


def _scene_group(row):
    doorway = row['scene_doorway_status'] in {'difficult', 'annotatable', 'confirmed_unspecified'}
    oos = row['scene_oos_status'] == 'confirmed'
    if doorway and oos:
        return 'doorway_and_oos'
    if doorway:
        return 'doorway'
    if oos:
        return 'oos'
    return 'ordinary' if row['scene_category'] == 'ordinary' else 'scene_not_confirmed_ordinary'


def _distributions(rows, cohort, stratum):
    reports = []
    for feature in ('pair_count', 'acute_count', 'min_acute_angle_deg', 'min_periodic_gap_px',
                    'max_depth_ratio_within_24px', 'curve_max_abs_latitude_deg',
                    'min_edge_range_over_median_vertex_range'):
        values = [r[feature] for r in rows if r[feature] is not None]
        quantiles = np.quantile(values, [.1, .25, .5, .75, .9]).tolist() if values else [None] * 5
        reports.append(dict(cohort=cohort, stratum=stratum, feature=feature, count=len(values), missing=len(rows) - len(values),
                            **dict(zip(('q10', 'q25', 'median', 'q75', 'q90'), quantiles))))
    return reports


def analyze_patterns(objects, records, seed, origins, out):
    """调用者先完成绑定校验；origins 是 oid -> 本轮实际更新者(user/yizheng)列表。"""
    previous, explicit, history = _read_context()
    for oid, reviewers in origins.items():
        if oid not in objects or oid not in records or not reviewers or set(reviewers) - {'user', 'yizheng'}:
            raise ValueError('invalid_current_review_origin:' + oid)
    rows = []
    for oid, obj in sorted(objects.items()):
        if oid != obj['object_id']:
            raise ValueError('object_identity_mismatch:' + oid)
        if obj['object_kind'] == 'annotation' and oid not in previous:
            raise ValueError('missing_previous_inventory:' + oid)
        record = records.get(oid, {})
        status = record.get('status', 'unreviewed')
        if status not in {'confirmed', 'draft', 'pending', 'pairing', 'unreviewed'}:
            raise ValueError('invalid_review_status:' + oid)
        ready = obj['preprocessing_status'] == 'ready'
        before = initial_order(obj, seed) if ready else []
        change = ring_relation(before, record['order']) if ready and record else 'not_confirmed'
        row = dict(object_id=oid, object_kind=obj['object_kind'], image_id=obj['image_id'],
                   image_code=obj['image_code'], worker_id=obj.get('worker_id', ''),
                   condition=obj.get('condition', ''), cleaning_disposition=obj.get('cleaning_disposition', 'reference'),
                   worker_quality_gate=obj.get('worker_quality_gate', 'reference'),
                   scene_category=obj.get('scene_category', 'reference'),
                   scene_doorway_status=obj.get('scene_doorway_status', 'not_recorded'),
                   scene_oos_status=obj.get('scene_oos_status', 'not_recorded'),
                   previous_queue_state=previous.get(oid, 'gt_reference'), current_status=status,
                   current_reviewers=list(origins.get(oid, [])), order_change=change,
                   initial_order=before, final_order=record.get('order'),
                   initial_order_basis='previous_round_record' if oid in seed else 'shared_x_ascending' if obj['object_kind'] == 'gt_manual_revision' else 'fixed_pair_identity',
                   explicit_order_evidence=oid in explicit, **prechange_features(obj, before))
        row['scene_group'] = _scene_group(row)
        row['candidate_reason'] = candidate_reason(row)
        row['rule_hits'] = [rule for rule in RULES[:-1] if row[rule]]
        rows.append(row)
    primary = [r for r in rows if 'user' in r['current_reviewers'] and r['object_kind'] == 'annotation' and r['current_status'] == 'confirmed']
    crosscheck = [r for r in rows if 'yizheng' in r['current_reviewers'] and r['object_kind'] == 'annotation' and r['current_status'] == 'confirmed']
    positive_images = {r['image_id'] for r in primary if r['order_change'] == 'adjacency_changed'}
    primary_ids = {r['object_id'] for r in primary}
    # 固定规则无训练参数；图片整体进入一个组，不能将同图人员随机拆开。
    folds = {iid: i % 5 for i, iid in enumerate(sorted({r['image_id'] for r in primary}))}
    for row in rows:
        row['image_fold'] = folds.get(row['image_id'])
        row['control_group'] = ('positive' if row['order_change'] == 'adjacency_changed' else
                                'same_image_control' if row['image_id'] in positive_images else
                                'other_ordinary_control' if row['scene_category'] == 'ordinary' else 'other_scene_control') if row['object_id'] in primary_ids else 'not_primary_control'
    evaluations, distributions = [], []
    for name, cohort in [('user_current', primary), ('yizheng_crosscheck', crosscheck)]:
        strata = {'all': cohort}
        positive_image_pair_counts = {(r['image_id'], r['pair_count']) for r in cohort if r['order_change'] == 'adjacency_changed'}
        matched = [r for r in cohort if (r['image_id'], r['pair_count']) in positive_image_pair_counts]
        strata['same_image_and_pair_count_matched'] = matched
        for count in sorted({r['pair_count'] for r in matched}):
            strata['same_image_matched:pair_count=' + str(count)] = [r for r in matched if r['pair_count'] == count]
        for field in ('scene_doorway_status', 'scene_oos_status', 'control_group'):
            for value in sorted({r[field] for r in cohort}):
                strata[field + '=' + value] = [r for r in cohort if r[field] == value]
        for label, match in [('pairs_le4', lambda n: n <= 4), ('pairs_5_8', lambda n: 5 <= n <= 8), ('pairs_ge9', lambda n: n >= 9)]:
            strata[label] = [r for r in cohort if match(r['pair_count'])]
        for stratum, values in strata.items():
            evaluations.extend(_evaluation(values, name, stratum, rule) for rule in RULES)
        for stratum in ('all', 'same_image_and_pair_count_matched'):
            for label, changed in [('changed', True), ('unchanged_or_equivalent', False)]:
                values = [r for r in strata[stratum] if (r['order_change'] == 'adjacency_changed') == changed]
                distributions.extend(_distributions(values, name, stratum + ':' + label))
        for group in sorted({r['control_group'] for r in cohort}):
            distributions.extend(_distributions([r for r in cohort if r['control_group'] == group], name, group))
    grouped = [_evaluation([r for r in primary if r['image_fold'] == fold], 'user_current', 'image_fold=' + str(fold), rule)
               for fold in sorted(set(folds.values())) for rule in RULES]
    historical = []
    for oid, entries in history.items():
        if oid not in objects or objects[oid]['object_kind'] != 'annotation':
            continue
        obj = objects[oid]
        for entry in entries:
            if entry['reviewer'] != 'user' or entry['record']['status'] != 'confirmed':
                continue
            before = list(range(len(obj['links_zero_based'])))
            if ring_relation(before, entry['record']['order']) != 'adjacency_changed':
                continue
            historical.append(dict(object_id=oid, image_id=obj['image_id'], image_code=obj['image_code'],
                                   historical_order=entry['record']['order'], **prechange_features(obj, before)))
    candidates = sorted((r for r in rows if r['candidate_reason'] == 'candidate'),
                        key=lambda r: (r['previous_queue_state'] != 'not_selected', -len(r['rule_hits']), r['image_code'], r['worker_id']))
    summarize = lambda values: dict(Counter(r['order_change'] for r in values))
    summary = dict(schema='order_pattern_recall_20260929_v1', feature_coordinate_source='preprocessed_shared_x_before_this_round',
                   primary_user=summarize(primary), primary_user_images=len({r['image_id'] for r in primary}),
                   primary_changed_images=len(positive_images), yizheng_crosscheck=summarize(crosscheck),
                   historical_user_changed_supplement=len(historical),
                   gt_current_by_reviewer={reviewer: summarize([r for r in rows if r['object_kind'] == 'gt_manual_revision' and reviewer in r['current_reviewers'] and r['current_status'] == 'confirmed']) for reviewer in ('user', 'yizheng')},
                   object_count=len(rows), annotation_count=sum(r['object_kind'] == 'annotation' for r in rows),
                   feature_status_counts=dict(Counter(r['feature_status'] for r in rows)),
                   candidate_count=len(candidates), candidate_not_in_previous_queue=sum(r['previous_queue_state'] == 'not_selected' for r in candidates),
                   candidate_counts_by_scene_group=dict(Counter(r['scene_group'] for r in candidates)),
                   candidate_counts_by_doorway=dict(Counter(r['scene_doorway_status'] for r in candidates)),
                   candidate_counts_by_oos=dict(Counter(r['scene_oos_status'] for r in candidates)),
                   skip_counts=dict(Counter(r['candidate_reason'] for r in rows)),
                   parameters=dict(acute_degrees=45, periodic_window_px=24, minimum_depth_ratio=1.5, image_groups=5,
                                   automatic_recall_min_pair_count=5, four_pair_override='explicit_human_order_evidence_only'),
                   rules_selected_using_outcomes=False, formal_analysis_connected=False,
                   primary_rule_results=[r for r in evaluations if r['cohort'] == 'user_current' and r['stratum'] == 'all'],
                   same_image_pair_count_rule_results=[r for r in evaluations if r['cohort'] == 'user_current' and r['stratum'] == 'same_image_and_pair_count_matched'],
                   limitations=['已确认未改序是操作对照，不等于独立证实的真阴性。',
                                '样本来自原始GT预筛；覆盖率只描述已审核样本，不能估计全3152份漏检率。',
                                '固定阈值为探索性规则；图片分组只检查跨图片稳定性，没有训练或自动选阈值。',
                                '一正记录单列交叉核对，不视为独立验证集。',
                                '3D及曲线共享相机高度1、水平地面、顶部借用地面深度等假设，不是独立几何真值。',
                                '曲线极点、camera_visibility_unresolved、门洞和OOS均不能自动判定顺序错误。'])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, values, fields in [('顺序规律_全量特征.csv', rows, list(rows[0]) if rows else ['object_id']),
                                ('顺序规律_规则评估.csv', evaluations, list(_evaluation([], '', '', 'any_acute'))),
                                ('顺序规律_按图片分组.csv', grouped, list(_evaluation([], '', '', 'any_acute'))),
                                ('顺序规律_连续特征分布.csv', distributions, list(_distributions([], '', '')[0])),
                                ('遗漏候选.csv', candidates, list(rows[0]) if rows else ['object_id']),
                                ('顺序规律_历史本人改序补充.csv', historical, ['object_id', 'image_id', 'image_code', 'historical_order'])]:
        if values:
            write_csv(out / name, values)
        else:
            with (out / name).open('w', encoding='utf-8-sig', newline='') as handle:
                csv.DictWriter(handle, fieldnames=fields).writeheader()
    dump(out / '顺序规律_summary.json', summary)
    (out / '顺序规律_研究说明.md').write_text(
        '# 顺序漏召回研究\n\n'
        '主样本采用用户本轮实际更新的确认记录；已有起始排列优先，起点移动和整体反向另列。'
        '一正仅作交叉核对；历史本人改序为补充。人工GT单列。所有特征取改前坐标与排列。\n\n'
        '规则固定为锐角<45°、周期24px内两对/三对、24px内相邻方位的地面深度比≥1.5。'
        '召回使用任意锐角、三对密集或近方位深度跳变的并集；两对密集单独报告，不单独召回。'
        '4对及以下默认不自动召回，明确人工顺序证据除外。已确认、明确排除与配对问题不进入候选。\n\n'
        '按图片划分5组检查固定规则，并分别报告同图对照、普通图对照、点对数、门洞和OOS。'
        'same_image_and_pair_count_matched只包含同一图片、相同点对数的阳性与操作对照；进一步逐点对数分层。'
        'control_group单组行仅为描述，其阳性组/对照组不单独计算分类性能。连续分布中的最小锐角只覆盖有<45°锐角的对象，其他记为空。'
        '曲线是3D直线段的全景投影；仅改变环序时端点不变。曲线接近极点为描述字段，不作判错输入。\n\n'
        '## 用户本轮固定规则结果\n\n'
        '|规则|改序命中/改序数|未改或等价命中/对照数|\n|---|---:|---:|\n'
        + ''.join(f"|{r['rule']}|{r['changed_hit']}/{r['changed']}|{r['unchanged_hit']}/{r['unchanged_or_equivalent']}|\n" for r in summary['primary_rule_results'])
        + '\n'
        + '\n'.join('- ' + note for note in summary['limitations']) + '\n', encoding='utf-8')
    return summary
