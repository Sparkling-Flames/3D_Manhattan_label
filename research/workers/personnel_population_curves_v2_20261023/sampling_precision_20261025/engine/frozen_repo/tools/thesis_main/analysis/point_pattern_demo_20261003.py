"""当前人员整份标注的探索分组及完整上下点中心；不读取GT或选最大簇。

build_patterns(records, thresholds=(5.,))返回每个阈值的展示数据：
clusters保存人员、原代表、对应索引及candidate；不可用作答保留为显式单例。
candidate.points沿代表的既定环交替保存top/bottom，footprint只为诊断/展示。
5°是未校准探索门限，不是语义等价或质量门限；不同点数保守分开。
"""
from __future__ import annotations

import numpy as np

from .paired_split_research.study import angular, cyclic, cluster
from .research_round_20260929 import reconstruct


def _pairs(record):
    if record['points'] is None:
        return None, 'pairing_unavailable'
    p = np.asarray(record['points'], float)
    if p.ndim != 2 or p.shape[1:] != (2,) or len(p) < 6 or len(p) % 2 or not np.isfinite(p).all():
        return None, 'invalid_point_array'
    if np.any(p < 0) or np.any(p[:, 0] > 1024) or np.any(p[:, 1] > 512):
        return None, 'coordinates_outside_continuous_canvas'
    p = p.reshape(-1, 2, 2)
    identities = record.get('source_pair_indices')
    if identities is not None and (len(identities) != len(p) or len(set(identities)) != len(identities)):
        return None, 'invalid_source_pair_identity'
    dx = (p[:, 0, 0]-p[:, 1, 0]+512) % 1024-512
    if np.any(abs(dx) > 1e-8) or np.any(p[:, 0, 1] >= p[:, 1, 1]):
        return None, 'invalid_preprocessed_top_bottom_pair'
    return p, None


def _alignment(a, b):
    """复用球面角距/循环瓶颈匹配；只适配C坐标和反向遍历，不改物理邻接。"""
    if a is None or b is None or len(a) != len(b):
        return dict(distance_deg=181., indices=None, ambiguous=False)
    # 历史angular输入P坐标；C-.5在内存中等价，原点与已预处理x不写回。
    cost = np.maximum(angular(a[:, 0]-.5, b[:, 0]-.5),
                      angular(a[:, 1]-.5, b[:, 1]-.5))
    options = []
    for order in (np.arange(len(b)), np.arange(len(b))[::-1]):
        distance, shift, margin = cyclic(cost[:, order])
        indices = order[(np.arange(len(b))+shift) % len(b)].tolist()
        options.append((distance, indices, margin))
    options.sort(key=lambda x: (x[0], x[1]))
    best, second = options
    ambiguous = best[2] <= 1e-9 or (abs(best[0]-second[0]) <= 1e-9 and best[1] != second[1])
    return dict(distance_deg=best[0], indices=best[1], ambiguous=bool(ambiguous))


def _unavailable(reason):
    return dict(status='unavailable', reason=reason, points=None, footprint=None,
                geometry_status='unavailable', geometry_issues=[])


def _candidate(records, pairs, representative):
    ref = records[representative]
    if pairs[representative] is None:
        return _unavailable(_pairs(ref)[1]), []
    alignments = []
    for i, r in enumerate(records):
        aligned = (dict(indices=list(range(len(pairs[i]))), distance_deg=0., ambiguous=False)
                   if i == representative else _alignment(pairs[representative], pairs[i]))
        alignments.append(dict(id=r['id'], worker=r['worker'], **aligned))
    if any(a['indices'] is None or a['ambiguous'] for a in alignments):
        return _unavailable('ambiguous_or_unavailable_corner_correspondence'), alignments
    if len(records) == 1:
        points = np.asarray(ref['points'], float).copy()
    else:
        stack = np.array([p[a['indices']] for p, a in zip(pairs, alignments)])
        anchor = pairs[representative][:, 0, 0]
        # ponytail: small equal-count demo only; no cross-count corner/path inference.
        x = (anchor + np.median((stack[:, :, 0, 0]-anchor+512) % 1024-512, axis=0)) % 1024
        center = np.median(stack, axis=0)
        center[:, :, 0] = x[:, None]
        points = center.reshape(-1, 2)
    maps = []
    for r, a in zip(records, alignments):
        source = r.get('source_pair_indices')
        maps.append(dict(id=r['id'], worker=r['worker'], indices=a['indices'],
                         source_pair_indices=[source[j] for j in a['indices']] if source is not None else None))
    value = dict(points=points.tolist(), order_status='derived_from_representative_ring',
                 ring_confirmed=False, source_pair_indices=None, source_point_indices=None,
                 source_point_labels=None)
    if len(records) == 1:
        for key in ('source_pair_indices', 'source_point_indices', 'source_point_labels'):
            value[key] = ref.get(key)
    geometry = reconstruct(value, coordinate_convention='continuous')
    floor = geometry['floor']
    projectable = floor is not None and geometry['heights'] is not None and geometry['wall_top_available']
    value.update(status=('ok' if geometry['status'] == 'ok' else 'geometry_review') if projectable else 'unavailable',
                 reason=geometry['reason'], footprint=floor.tolist() if floor is not None else None,
                 geometry_status=geometry['status'], geometry_issues=geometry.get('issues', []),
                 geometry_polygon_valid=geometry['polygon_valid'],
                 point_support_counts=[len(records)]*(len(points)//2), source_pair_maps=maps,
                 representative=ref['id'], center_method='continuous_ERP_periodic_x_and_top_bottom_coordinate_medians',
                 source_order_status=ref.get('order_status'), source_ring_confirmed=ref.get('ring_confirmed'))
    return value, alignments


def build_patterns(records, thresholds=(5.0,)):
    """仅传当前k人的作答；原点/确认环不变，返回可JSON序列化的分簇展示。"""
    records = sorted(records, key=lambda r: str(r['id']))
    if any('worker' not in r for r in records):
        raise ValueError('annotations_only_no_reference_records')
    if len({str(r['id']) for r in records}) != len(records):
        raise ValueError('duplicate_annotation_id')
    if len({str(r['worker']) for r in records}) != len(records):
        raise ValueError('duplicate_worker')
    thresholds = tuple(float(t) for t in thresholds)
    if not thresholds or any(not np.isfinite(t) or not 0 < t < 180 for t in thresholds):
        raise ValueError('invalid_exploratory_threshold')
    pairs, reasons = zip(*[_pairs(r) for r in records]) if records else ([], [])
    n = len(records)
    distances = np.zeros((n, n))
    for i in range(n):
        for j in range(i+1, n):
            distances[i, j] = distances[j, i] = _alignment(pairs[i], pairs[j])['distance_deg']
    result = []
    for threshold in thresholds:
        labels = cluster(distances, threshold) if n else []
        groups = [np.flatnonzero(labels == k).tolist() for k in sorted(set(labels))]
        groups.sort(key=lambda ids: (-len(ids), str(records[ids[0]]['id'])))
        output = []
        for number, ids in enumerate(groups, 1):
            local = distances[np.ix_(ids, ids)]
            representative = int(np.argmin(local.sum(axis=1)))
            members = [records[i] for i in ids]
            candidate, aligned = _candidate(members, [pairs[i] for i in ids], representative)
            output.append(dict(id=f'pattern_{number:02d}', members=[r['id'] for r in members],
                workers=[r['worker'] for r in members], support=len(ids), support_fraction=len(ids)/n,
                representative=members[representative]['id'], pair_count=len(pairs[ids[0]]) if pairs[ids[0]] is not None else None,
                diameter_deg=float(local.max()), input_status='unavailable' if reasons[ids[0]] else 'ok',
                input_reason=reasons[ids[0]], candidate=candidate, alignment=aligned))
        whole = (output[0]['candidate'] if len(output) == 1 else
                 _unavailable('multiple_annotation_patterns_no_cross_structure_fusion' if n else 'no_annotations'))
        result.append(dict(threshold_deg=threshold, k=n, clusters=output, all_members_candidate=whole,
            method=dict(distance='equal-pair-count cyclic/reversal minimum maximum spherical top/bottom endpoint angle',
                        grouping='complete_linkage_whole_annotations', threshold_calibrated=False,
                        threshold_origin='historical 2.5/5/10 degree exploratory probes, default 5; not selected using these demo outcomes',
                        centre='GT-free original medoid as seam/identity anchor; coordinate medians in continuous ERP',
                        interpretation='conservative annotation-expression groups; collinear extra corners also separate',
                        point_support_counts='number of member observations contributing to each aligned pair estimate; not votes at the generated centre or whole-pool corner support',
                        representative='minimum_sum_within_group_annotation_distance; annotation_id_breaks_ties',
                        scope='current members only; no GT, no maximum-cluster selection, no cross-pattern point fusion')))
    return result
