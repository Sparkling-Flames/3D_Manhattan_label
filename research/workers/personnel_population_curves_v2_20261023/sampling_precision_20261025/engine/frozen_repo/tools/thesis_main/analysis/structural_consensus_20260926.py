"""有整环支持约束的多模式结构共识原型，不接收 GT、IoU 或质心。

坐标单位为共同相机离地高度；只使用传入环，不推断/修正邻接。
最小/最大种子的加删搜索被观测整环约束，尚不是任意新拓扑发现器。
"""
from __future__ import annotations

from collections import defaultdict
import math

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.optimize import least_squares
from shapely.geometry import Point, Polygon
from shapely.validation import explain_validity

from tools.label_studio.panorama_studio.geometry import heading_frame


SCHEMA = 'structural_consensus_20260926_v1'


def _array(points):
    p = np.asarray(points, float)
    if p.ndim != 2 or p.shape[1:] != (2,) or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError('invalid_floor_coordinates')
    return p


def match_ring(a, b, point_tol=.20):
    """循环起点/反向等价；保留邻接。每个对应点的最大欧氏距离作门限。

    不作平移、旋转、尺度对齐，不比较面积。返回 b 对应到 a 的索引。
    点数不同不能完整匹配；精确共线加点也保留为不同表示，另作诊断。
    """
    a, b = _array(a), _array(b)
    if not math.isfinite(point_tol) or point_tol <= 0:
        raise ValueError('invalid_point_tol')
    if len(a) != len(b):
        return dict(matched=False, max_distance=None, rms_distance=None,
                    indices=None, reason='different_corner_count')
    options = []
    for direction in [1, -1]:
        for shift in range(len(b)):
            ids = (shift + direction*np.arange(len(b))) % len(b)
            distances = np.linalg.norm(a-b[ids], axis=1)
            options.append((float(distances.max()), float(np.sqrt(np.mean(distances**2))),
                            ids.tolist()))
    distance, rms, ids = min(options)
    return dict(matched=distance <= point_tol + 1e-12, max_distance=distance,
                rms_distance=rms, indices=ids, reason='within_tolerance' if distance <= point_tol+1e-12
                else 'corner_distance_exceeds_tolerance')


def score_candidate(floor, records, *, point_tol=.20):
    """每位独立人员至多一票；只查询整环支持，不生成或拟合候选。"""
    seen, supporters = set(), []
    for r in records:
        if r['worker'] in seen:
            raise ValueError('duplicate_worker')
        seen.add(r['worker'])
        if match_ring(floor, r['floor'], point_tol)['matched']:
            supporters.append(r['worker'])
    return dict(whole_ring_support=len(supporters), workers=supporters,
                status='supported_complete_ring' if supporters else 'unsupported_complete_ring')


def local_support(floor, records, *, point_tol=.20):
    """所有训练人员的局部票；边必须在该人员给定环中真实相邻。"""
    p = _array(floor)
    point_workers, edge_workers = [[] for _ in p], [[] for _ in p]
    seen = set()
    for r in records:
        if r['worker'] in seen:
            raise ValueError('duplicate_worker')
        seen.add(r['worker'])
        q = _array(r['floor'])
        distances = np.linalg.norm(p[:, None]-q[None], axis=2)
        close = distances <= point_tol+1e-12
        for i in range(len(p)):
            if close[i].any():
                point_workers[i].append(r['worker'])
            # 每人每条候选边至多一票；对应的是源环相邻点，不能任取两个近点。
            following = close[(i+1) % len(p)]
            if np.any(close[i] & (np.roll(following, -1) | np.roll(following, 1))):
                edge_workers[i].append(r['worker'])
    return dict(point_support_counts=list(map(len, point_workers)),
                edge_support_counts=list(map(len, edge_workers)),
                point_supporters=point_workers, edge_supporters=edge_workers,
                local_support_denominator=len(records),
                local_support_definition='all_train_unique_workers; corner_distance<=tol; edge_endpoints_adjacent_in_given_ring; reverse_allowed')


def geometry_diagnostics(floor, heights=None, *, short_edge=.15):
    p = _array(floor)
    edges = np.roll(p, -1, axis=0)-p
    lengths = np.linalg.norm(edges, axis=1)
    nonzero = lengths > 1e-10
    poly = Polygon(p)
    valid = poly.is_valid and poly.area > 1e-12
    frame = heading_frame(p) if nonzero.any() else None
    angles = np.arctan2(edges[:, 1], edges[:, 0])
    residuals = (np.degrees(np.abs((angles-frame+np.pi/4) % (np.pi/2)-np.pi/4))
                 if frame is not None else None)
    # 短边的方向对点噪声敏感，连续降低诊断/拟合权重，不删边、不放大匹配容差。
    weights = lengths**2/np.sqrt(lengths**2+short_edge**2)
    turns, collinear = [], []
    for i in range(len(p)):
        before, after = p[i]-p[i-1], p[(i+1) % len(p)]-p[i]
        denom = np.linalg.norm(before)*np.linalg.norm(after)
        turn = math.degrees(math.acos(float(np.clip(np.dot(before, after)/denom, -1, 1)))) if denom else None
        turns.append(turn)
        if turn is not None and turn <= 3:
            collinear.append(i)
    hs = np.asarray(heights, float) if heights is not None else None
    return dict(polygon_status='valid' if valid else 'invalid',
                polygon_reason='valid' if valid else explain_validity(poly) if not poly.is_valid else 'zero_area',
                camera_inside=bool(poly.contains(Point(0, 0))) if valid else None,
                heading_deg=math.degrees(frame) if frame is not None else None,
                direction_residual_deg=[float(x) if nz else None for x, nz in zip(residuals, nonzero)]
                if residuals is not None else [None]*len(p),
                weighted_direction_residual_deg=float(np.average(residuals, weights=weights))
                if weights.sum() else None,
                max_direction_residual_deg=float(residuals[nonzero].max()) if nonzero.any() else None,
                edge_lengths=lengths.tolist(), short_edges=np.flatnonzero(lengths < short_edge).tolist(),
                zero_edges=np.flatnonzero(~nonzero).tolist(), turn_deg=turns,
                near_collinear_corners=collinear,
                height_relative_mad=float(np.median(abs(hs-np.median(hs)))/abs(np.median(hs)))
                if hs is not None and abs(np.median(hs)) > 1e-10 else None,
                height_range=float(np.ptp(hs)) if hs is not None else None,
                ceiling_at_or_below_camera_corners=np.flatnonzero(hs <= 1).tolist() if hs is not None else [],
                height_status='available' if hs is not None else 'missing')


def _fit(members, reference, point_tol, geometry_weight, height_weight, short_edge):
    aligned = [match_ring(reference['floor'], r['floor'], point_tol)['indices'] for r in members]
    stack = np.array([np.asarray(r['floor'])[ids] for r, ids in zip(members, aligned)])
    median = np.median(stack, axis=0)
    heights = [np.asarray(r['heights'])[ids] for r, ids in zip(members, aligned) if r['heights'] is not None]
    height_median = np.median(heights, axis=0) if heights else None
    before = geometry_diagnostics(median, height_median, short_edge=short_edge)
    fitted = median.copy()
    optimizer = dict(status='disabled', success=True, message='geometry_weight_zero')
    if geometry_weight and not before['zero_edges']:
        frame = math.radians(before['heading_deg'])
        n = len(median)

        def residual(v):
            points = v[:-1].reshape(n, 2)
            edges = np.roll(points, -1, axis=0)-points
            lengths = np.linalg.norm(edges, axis=1)
            angles = np.arctan2(edges[:, 1], edges[:, 0])
            short_weight = lengths/np.sqrt(lengths**2+short_edge**2)
            direction = np.sin(2*(angles-v[-1]))/2 / math.radians(5)
            return np.r_[(points-median).ravel()/point_tol,
                         math.sqrt(geometry_weight)*short_weight*direction]

        initial = np.r_[median.ravel(), frame]
        bound = point_tol/2
        result = least_squares(residual, initial,
                               bounds=(np.r_[median.ravel()-bound, frame-np.pi/4],
                                       np.r_[median.ravel()+bound, frame+np.pi/4]),
                               max_nfev=100, ftol=1e-9, xtol=1e-9, gtol=1e-9)
        fitted = result.x[:-1].reshape(n, 2)
        optimizer = dict(status='soft_regularized', success=bool(result.success),
                         message=str(result.message), evaluations=int(result.nfev))
    elif geometry_weight:
        optimizer = dict(status='degenerate_edges_not_fitted', success=False, message='zero_edge')
    # 独立的弱高度一致性项；不把 top 高度误差强行改成 floor 位移。
    hs = ((height_median+height_weight*np.median(height_median))/(1+height_weight)
          if height_median is not None else None)
    return dict(floor=fitted.tolist(), heights=hs.tolist() if hs is not None else None,
                median_floor=median.tolist(), median_heights=height_median.tolist() if height_median is not None else None,
                geometry_before=before, geometry=geometry_diagnostics(fitted, hs, short_edge=short_edge),
                optimizer=optimizer, aligned_source_indices=aligned,
                maximum_fit_coordinate_shift=float(np.max(abs(fitted-median))))


def _edit_path(source, target, tol):
    """完整源环到受整环支持的目标：动态规划加/删及保留点的局部坐标拟合。

    只选择源环等价循环起点和方向，禁止重新排列边。每一步保留原始索引。
    """
    a, b = _array(source), _array(target)
    best = None
    for direction in [1, -1]:
        for shift in range(len(a)):
            ids = (shift+direction*np.arange(len(a))) % len(a)
            p = a[ids]
            d = np.full((len(a)+1, len(b)+1), np.inf)
            path = {}
            d[:, 0], d[0, :] = np.arange(len(a)+1), np.arange(len(b)+1)
            for i in range(1, len(a)+1):
                path[i, 0] = 'delete'
            for j in range(1, len(b)+1):
                path[0, j] = 'insert'
            for i in range(1, len(a)+1):
                for j in range(1, len(b)+1):
                    distance = float(np.linalg.norm(p[i-1]-b[j-1]))
                    options = [(d[i-1, j]+1, 'delete'), (d[i, j-1]+1, 'insert')]
                    if distance <= tol+1e-12:
                        options.append((d[i-1, j-1]+.25*distance/tol, 'keep_fit'))
                    d[i, j], path[i, j] = min(options)
            key = (float(d[-1, -1]), direction != 1, shift)
            if best is not None and key >= best[0]:
                continue
            actions, i, j = [], len(a), len(b)
            while i or j:
                action = path[i, j]
                item = {'action': action}
                if action in ['delete', 'keep_fit']:
                    item['source_index'] = int(ids[i-1])
                    i -= 1
                if action in ['insert', 'keep_fit']:
                    item['target_index'] = j-1
                    item['point'] = b[j-1].tolist()
                    j -= 1
                actions.append(item)
            best = key, list(reversed(actions))
    actions = best[1]
    executed = [a['point'] for a in actions if a['action'] != 'delete']
    return dict(actions=actions, inserted=sum(x['action'] == 'insert' for x in actions),
                deleted=sum(x['action'] == 'delete' for x in actions),
                kept=sum(x['action'] == 'keep_fit' for x in actions),
                reaches_target=bool(np.array_equal(executed, b)), result_floor=executed,
                cost=best[0][0])


def _extension_blocks(base, target, tol):
    """纯加点的已观测整环相对基环，返回每条原边上可共现的插点块。"""
    path = _edit_path(base, target, tol)
    if path['deleted'] or path['kept'] != len(base) or not path['inserted']:
        return None
    keeps = [a for a in path['actions'] if a['action'] == 'keep_fit']
    target = np.asarray(target)
    blocks = {}
    for previous, current in zip(keeps[-1:]+keeps[:-1], keeps):
        first, last = previous['target_index'], current['target_index']
        indices = []
        j = (first+1) % len(target)
        while j != last:
            indices.append(j)
            j = (j+1) % len(target)
        if not indices:
            continue
        a, b = previous['source_index'], current['source_index']
        if (a+1) % len(base) == b:
            blocks[b] = target[indices].tolist()
        elif (b+1) % len(base) == a:
            blocks[a] = target[indices[::-1]].tolist()
        else:
            return None
    return blocks


def _unsupported_local_unions(modes, train, tol):
    """受限反例搜索：把不同观测结构在不同基边的插点合并，再查整环支持。

    ponytail: 只枚举最少点基环的一对互不重叠插点块，复杂多块组合另作后续研究。
    """
    if len(modes) < 3:
        return []
    base = min(modes, key=lambda m: (m['n_corners'], m['mode_id']))
    extensions = [(m, _extension_blocks(base['median_floor'], m['median_floor'], tol))
                  for m in modes if m['n_corners'] > base['n_corners']]
    extensions = [(m, blocks) for m, blocks in extensions if blocks]
    rejected, seen = [], set()
    for i, (a, blocks_a) in enumerate(extensions):
        for b, blocks_b in extensions[i+1:]:
            if set(blocks_a) & set(blocks_b):
                continue
            blocks = blocks_a | blocks_b
            hybrid = [p for j, point in enumerate(base['median_floor']) for p in blocks.get(j, [])+[point]]
            key = tuple(np.round(hybrid, 9).ravel())
            if key in seen:
                continue
            seen.add(key)
            support = score_candidate(hybrid, train, point_tol=tol)
            if support['whole_ring_support'] == 0:
                rejected.append(dict(base_mode=base['mode_id'],
                                     source_modes=[a['mode_id'], b['mode_id']], floor=hybrid,
                                     proposal_status='rejected_no_whole_ring_support', **support,
                                     **local_support(hybrid, train, point_tol=tol)))
    return rejected


def fit_consensus(records, *, point_tol=.20, geometry_weight=.10, height_weight=.02,
                  short_edge=.15, heldout_workers=(), min_support=3):
    """完整结构分模式、稳健拟合、双种子局部加删、冻结模式留出支持验证。

    支持度不是正确率；自交/相机外/少数模式均保留，附状态。模式匹配只用 floor。
    exact-collinear 加点暂作为独立表示，不能将本原型模式数当空间真值簇数。
    """
    if (not all(math.isfinite(v) for v in [point_tol, geometry_weight, height_weight, short_edge])
            or point_tol <= 0 or short_edge <= 0 or min(geometry_weight, height_weight) < 0
            or not isinstance(min_support, int) or min_support < 1):
        raise ValueError('invalid_parameters')
    normalized, seen, seen_ids = [], set(), set()
    for r in sorted(records, key=lambda x: str(x['id'])):
        worker = str(r['worker'])
        if worker in seen:
            raise ValueError('duplicate_worker')
        seen.add(worker)
        if str(r['id']) in seen_ids:
            raise ValueError('duplicate_record_id')
        seen_ids.add(str(r['id']))
        points = _array(r['floor'])
        heights = r.get('heights')
        if heights is not None:
            heights = np.asarray(heights, float)
            if heights.shape != (len(points),) or not np.isfinite(heights).all():
                raise ValueError('invalid_heights')
        normalized.append(dict(id=str(r['id']), worker=worker, floor=points.tolist(),
                               heights=heights.tolist() if heights is not None else None,
                               order_status=r.get('order_status', 'unconfirmed_given_ring')))
    heldout_workers = set(map(str, heldout_workers))
    if not heldout_workers <= seen:
        raise ValueError('unknown_heldout_worker')
    train = [r for r in normalized if r['worker'] not in heldout_workers]
    test = [r for r in normalized if r['worker'] in heldout_workers]
    result = dict(schema_version=SCHEMA, status='ok' if train else 'no_training_records',
                  parameters=dict(point_tol=point_tol, geometry_weight=geometry_weight,
                                  height_weight=height_weight, short_edge=short_edge, min_support=min_support),
                  method='complete_ring_constrained_min_max_reconstruction_and_robust_fit',
                  ordering='input_adjacency_only_cyclic_start_and_reversal_equivalence',
                  units='camera_height', train_workers=[r['worker'] for r in train],
                  heldout_workers=[r['worker'] for r in test], modes=[], seed_paths=[],
                  unsupported_hybrids=[], input_diagnostics=[],
                  limitations=['point_count_sensitive_even_for_exact_collinear_redundancy',
                               'fixed_metric_tolerance_sensitive_to_far_horizon_depth',
                               'observed_complete_ring_constrained_reconstruction_not_unseen_topology_discovery',
                               'heldout_support_is_recurrence_not_geometric_truth',
                               'point_count_mode_can_contain_unresolved_input_order'])
    for r in normalized:
        result['input_diagnostics'].append(dict(id=r['id'], worker=r['worker'],
            heldout=r['worker'] in heldout_workers, order_status=r['order_status'],
            geometry=geometry_diagnostics(r['floor'], r['heights'], short_edge=short_edge)))
    if not train:
        result['heldout'] = dict(assignments=[], unmatched_workers=[r['worker'] for r in test], ambiguous_workers=[])
        return result
    by_count = defaultdict(list)
    for r in train:
        by_count[len(r['floor'])].append(r)
    groups = []
    for count in sorted(by_count):
        members = by_count[count]
        distances = [match_ring(a['floor'], b['floor'], point_tol)['max_distance']
                     for i, a in enumerate(members) for b in members[i+1:]]
        labels = fcluster(linkage(distances, method='complete'), point_tol, criterion='distance') if distances else [1]
        buckets = defaultdict(list)
        for label, r in zip(labels, members):
            buckets[int(label)].append(r)
        groups.extend(buckets.values())
    groups.sort(key=lambda g: (-len(g), len(g[0]['floor']), g[0]['id']))
    for number, members in enumerate(groups):
        medoid = min(members, key=lambda a: (sum(match_ring(a['floor'], b['floor'], point_tol)['rms_distance']
                                                    for b in members), a['id']))
        fitted = _fit(members, medoid, point_tol, geometry_weight, height_weight, short_edge)
        geom = fitted['geometry']
        suspicious = (geom['polygon_status'] != 'valid' or not geom['camera_inside'] or
                      bool(geom['ceiling_at_or_below_camera_corners']) or
                      geom['weighted_direction_residual_deg'] is None or geom['weighted_direction_residual_deg'] > 5)
        support = score_candidate(fitted['floor'], train, point_tol=point_tol)
        state = ('supported_geometry_review' if suspicious else 'supported_candidate') if support['whole_ring_support'] >= min_support else 'minority_candidate'
        mode = dict(mode_id=f'mode_{number+1:02}', n_corners=len(medoid['floor']), status=state,
                    train_support=support['whole_ring_support'], train_fraction=support['whole_ring_support']/len(train),
                    cluster_members=len(members), cluster_supporters=[r['worker'] for r in members],
                    source_ids=[r['id'] for r in members], supporters=support['workers'],
                    representative_id=medoid['id'], representative_floor=medoid['floor'],
                    candidate_whole_ring_support=support['whole_ring_support'],
                    candidate_supporters=support['workers'],
                    heldout_support=0, heldout_supporters=[],
                    **local_support(fitted['floor'], train, point_tol=point_tol),
                    **fitted)
        if not support['whole_ring_support']:
            mode['status'] = 'unsupported_fitted_candidate_review'
        elif support['whole_ring_support'] < len(members):
            mode['status'] = 'fitted_support_reduced_review'
        result['modes'].append(mode)
    for seed_kind, seed in [('minimum', min(train, key=lambda r: (len(r['floor']), r['id']))),
                            ('maximum', min(train, key=lambda r: (-len(r['floor']), r['id'])))]:
        for mode in result['modes']:
            result['seed_paths'].append(dict(seed_kind=seed_kind, seed_id=seed['id'],
                                            mode_id=mode['mode_id'],
                                            **_edit_path(seed['floor'], mode['floor'], point_tol)))
    assignments, unmatched, ambiguous = [], [], []
    for r in test:
        matches = [(m, match_ring(m['floor'], r['floor'], point_tol)) for m in result['modes']]
        matches = [(m, evidence) for m, evidence in matches if evidence['matched']]
        matches.sort(key=lambda item: (item[1]['max_distance'], item[1]['rms_distance'], item[0]['mode_id']))
        selected = matches[0][0] if matches else None
        if selected:
            selected['heldout_support'] += 1
            selected['heldout_supporters'].append(r['worker'])
        else:
            unmatched.append(r['worker'])
        if len(matches) > 1:
            ambiguous.append(r['worker'])
        assignments.append(dict(worker=r['worker'], id=r['id'],
                                matched_mode_ids=[m['mode_id'] for m, _ in matches],
                                assigned_mode_id=selected['mode_id'] if selected else None,
                                assignment='minimum_max_corner_distance_then_rms_then_mode_id',
                                max_distance=matches[0][1]['max_distance'] if matches else None))
    result['heldout'] = dict(assignments=assignments, unmatched_workers=unmatched, ambiguous_workers=ambiguous)
    result['unsupported_hybrids'] = _unsupported_local_unions(result['modes'], train, point_tol)
    return result
