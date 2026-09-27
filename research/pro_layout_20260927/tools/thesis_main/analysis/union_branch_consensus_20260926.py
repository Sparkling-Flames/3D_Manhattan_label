"""并集减法的多分支探索：人数优先，几何诊断独立，不接收 GT。

并集是跨人角点身份集合，不连接成全局多边形。每个分支沿用其成员
观测到的循环邻接，删除不属于该分支的身份；只聚合簇内坐标。
"""
from collections import defaultdict
import math

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from tools.label_studio.panorama_studio.geometry import pixel_ray
from .structural_consensus_20260926 import geometry_diagnostics, match_ring


SCHEMA = 'union_branch_consensus_20260926_v1'


def _ring_key(ids):
    """仅规范循环起点及方向，保留邻接；相同点集不同连线不等价。"""
    ids = tuple(ids)
    return min(ids[i:] + ids[:i] for ids in (ids, ids[::-1]) for i in range(len(ids)))


def _rows(records):
    rows, workers, source_ids = [], set(), set()
    for record in sorted(records, key=lambda r: (str(r['worker']), str(r['id']))):
        worker, source_id = str(record['worker']), str(record['id'])
        if worker in workers:
            raise ValueError('duplicate_worker')
        if source_id in source_ids:
            raise ValueError('duplicate_source_id')
        workers.add(worker)
        source_ids.add(source_id)
        floor = np.asarray(record['floor'], float)
        match_ring(floor, floor)  # 复用有限坐标、至少三角点等输入校验。
        heights = np.asarray(record['heights'], float)
        if heights.shape != (len(floor),) or not np.isfinite(heights).all():
            raise ValueError('invalid_heights')
        row = dict(id=source_id, worker=worker, floor=floor, heights=heights,
                   order_status=record.get('order_status', 'given_ring_unreviewed'),
                   cluster_label=str(record['cluster_label']) if 'cluster_label' in record else None)
        if 'feature_ids' in record:
            ids = list(map(str, record['feature_ids']))
            if len(ids) != len(floor) or len(set(ids)) != len(ids):
                raise ValueError('invalid_explicit_feature_ids')
            row['feature_ids'] = ids
        else:
            if 'pairs' not in record:
                raise ValueError('missing_pairs_for_automatic_feature_identity')
            pairs = np.asarray(record['pairs'], float)
            if (pairs.shape != (len(floor), 2, 2) or not np.isfinite(pairs).all()
                    or np.any(pairs < 0) or np.any(pairs[..., 0] > 1024)
                    or np.any(pairs[..., 1] > 512) or np.any(pairs[:, 0, 1] >= pairs[:, 1, 1])):
                raise ValueError('invalid_pairs_1024x512_top_bottom')
            row['pairs'] = pairs
        rows.append(row)
    if rows and len({'feature_ids' in r for r in rows}) > 1:
        raise ValueError('mixed_explicit_and_automatic_feature_identity')
    if rows and any(r['cluster_label'] is not None for r in rows) and any(r['cluster_label'] is None for r in rows):
        raise ValueError('partially_provided_cluster_labels')
    return rows


def _feature_union(rows, tolerance):
    nodes = [(r, i) for r in rows for i in range(len(r['floor']))]
    explicit = 'feature_ids' in rows[0]
    distances = None
    if explicit:
        labels = [r['feature_ids'][i] for r, i in nodes]
    else:
        rays = np.array([[pixel_ray(*point, 1024, 512) for point in r['pairs'][i]] for r, i in nodes])
        dot = np.einsum('ied,jed->ije', rays, rays)
        distances = np.degrees(np.arccos(np.clip(dot, -1., 1.))).max(axis=2)
        np.fill_diagonal(distances, 0.)
        worker_ids = np.array([r['worker'] for r, _ in nodes])
        constrained = distances.copy()
        constrained[worker_ids[:, None] == worker_ids[None, :]] = 181.
        np.fill_diagonal(constrained, 0.)
        # complete-linkage 的最大成员间距保证不会把同人两个近角合成一个身份。
        # ponytail: O(总角点数²)距离矩阵；目前逐图众包规模适用，大规模再分块匹配。
        groups = fcluster(linkage(squareform(constrained, checks=False), method='complete'),
                          t=tolerance, criterion='distance')
        ordered = sorted(set(groups), key=lambda label: int(np.flatnonzero(groups == label)[0]))
        names = {label: f'f{i + 1:03d}' for i, label in enumerate(ordered)}
        labels = [names[label] for label in groups]
        for row in rows:
            row['feature_ids'] = [None] * len(row['floor'])
        for (row, index), label in zip(nodes, labels):
            row['feature_ids'][index] = label
    by_feature = defaultdict(list)
    for index, label in enumerate(labels):
        by_feature[label].append(index)
    features = []
    for label, indices in sorted(by_feature.items()):
        members = []
        for index in indices:
            row, corner = nodes[index]
            member = dict(source_id=row['id'], worker=row['worker'], corner_index=corner,
                          floor=row['floor'][corner].tolist(), height=float(row['heights'][corner]))
            if 'pairs' in row:
                member['pairs'] = row['pairs'][corner].tolist()
            members.append(member)
        features.append(dict(feature_id=label, support=len(members),
                             support_workers=sorted(m['worker'] for m in members), members=members,
                             maximum_pair_angle_deg=float(distances[np.ix_(indices, indices)].max())
                             if distances is not None else None))
    return features


def fit_union_branches(records, point_tol_deg=5., short_edge=.15, geometry_warn_deg=5.):
    """全部数据仅来自本次传入人员，不接收未来点集或参考布局。

    自动角点身份：上下端点球面角距的最大值，受同人不能合点的完全连接聚类。
    角度门限及告警门限均为未校准探索参数，不能解释为准确性判据。
    可显式提供 feature_ids 验证符号化假设；可提供全量 cluster_label，但同一
    label 必须有一致的保留身份与邻接。支持人数优先排序，几何不会覆盖人群票数。
    """
    if (not math.isfinite(point_tol_deg) or not 0 < point_tol_deg < 180
            or not math.isfinite(short_edge) or short_edge <= 0
            or not math.isfinite(geometry_warn_deg) or not 0 <= geometry_warn_deg <= 45):
        raise ValueError('invalid_parameters')
    rows = _rows(records)
    result = dict(schema_version=SCHEMA,
                  parameters=dict(point_tol_deg=point_tol_deg, short_edge=short_edge,
                                  geometry_warn_deg=geometry_warn_deg, tolerance_calibrated=False),
                  vote_denominator=len(rows), features=[], branches=[], assignments=[],
                  identity_metric='max(top_spherical_angle,bottom_spherical_angle); complete_linkage; same_worker_cannot_merge',
                  ranking='descending_exact_branch_people; deterministic_signature_tie_break; geometry_diagnostic_only',
                  limitations=['identity_tolerance_unvalidated', 'given_adjacency_preserved_not_repaired',
                               'exact_feature_signatures_can_fragment_under_noise',
                               'feature_identity_is_not_semantic_corner_certification',
                               'observed_branch_topology_only_not_all_possible_union_subsets',
                               'coordinate_median_is_not_Lee_tile_voting',
                               'geometry_plausibility_does_not_certify_scene_correctness'])
    if not rows:
        return dict(result, status='no_training_records')
    features = _feature_union(rows, point_tol_deg)
    union_ids = {f['feature_id'] for f in features}
    shared = {f['feature_id']: dict(
        floor=np.median([m['floor'] for m in f['members']], axis=0),
        height=float(np.median([m['height'] for m in f['members']])),
        support=f['support']) for f in features}
    result['features'] = features
    result['identity_source'] = 'explicit_feature_ids' if 'pairs' not in rows[0] else 'automatic_spherical_pairs'
    clusters = defaultdict(list)
    for row in rows:
        row['signature'] = _ring_key(row['feature_ids'])
        key = row['cluster_label'] if row['cluster_label'] is not None else row['signature']
        clusters[key].append(row)
    for members in clusters.values():
        if len({r['signature'] for r in members}) != 1:
            raise ValueError('cluster_label_contains_distinct_ring_signatures')
    sorted_clusters = sorted(clusters.values(), key=lambda members: (-len(members), members[0]['signature'], members[0]['id']))
    for rank, members in enumerate(sorted_clusters, 1):
        feature_ids = members[0]['signature']
        indices = [[r['feature_ids'].index(f) for f in feature_ids] for r in members]
        floors = np.array([r['floor'][idx] for r, idx in zip(members, indices)])
        heights = np.array([r['heights'][idx] for r, idx in zip(members, indices)])
        floor, height = np.median(floors, axis=0), np.median(heights, axis=0)
        geometry = geometry_diagnostics(floor, height, short_edge=short_edge)
        shared_floor = np.array([shared[f]['floor'] for f in feature_ids])
        shared_height = np.array([shared[f]['height'] for f in feature_ids])
        if geometry['polygon_status'] != 'valid' or geometry['zero_edges'] or geometry['ceiling_at_or_below_camera_corners']:
            geometry_status = 'invalid_3d_candidate'
        elif (not geometry['camera_inside'] or
              geometry['weighted_direction_residual_deg'] > geometry_warn_deg):
            geometry_status = 'geometry_review'
        else:
            geometry_status = 'no_flag_under_exploratory_checks'
        # 代表标注由簇内对齐角点距离总和选取，完全不看参考区域。
        medoid_cost = np.linalg.norm(floors[:, None] - floors[None, :], axis=3).mean(axis=2).sum(axis=1)
        medoid = int(np.argmin(medoid_cost))
        branch = dict(branch_id=f'b{rank:03d}', feature_ids=list(feature_ids),
                      deleted_feature_ids=sorted(union_ids - set(feature_ids)),
                      support=len(members), support_fraction=len(members) / len(rows),
                      support_workers=sorted(r['worker'] for r in members),
                      source_ids=[r['id'] for r in members], cluster_label=members[0]['cluster_label'],
                      floor=floor.tolist(), heights=height.tolist(), geometry=geometry,
                      geometry_status=geometry_status, parent_deletions=[],
                      representative_id=members[medoid]['id'], representative_worker=members[medoid]['worker'],
                      representative_floor=floors[medoid].tolist(), representative_heights=heights[medoid].tolist(),
                      representative_rule='minimum_sum_mean_aligned_floor_corner_distance_within_branch; no_reference',
                      order_statuses=sorted({r['order_status'] for r in members}),
                      aggregation='per_feature_coordinate_median_within_branch_only',
                      shared_feature_candidate=dict(
                          floor=shared_floor.tolist(), heights=shared_height.tolist(),
                          geometry=geometry_diagnostics(shared_floor, shared_height, short_edge=short_edge),
                          point_support_counts=[shared[f]['support'] for f in feature_ids],
                          evidence_scope='all_current_input_workers_sharing_each_retained_feature',
                          support_warning='point_support_is_not_whole_branch_support; cross_branch_medians_may_shift_the_candidate',
                          role='diagnostic_alternative_preserving_branch_topology_not_default_output'))
        result['branches'].append(branch)
        result['assignments'].extend(dict(source_id=r['id'], worker=r['worker'], branch_id=branch['branch_id'],
                                          feature_ids=r['feature_ids'], aligned_source_indices=idx)
                                     for r, idx in zip(members, indices))
    for child in result['branches']:
        kept = set(child['feature_ids'])
        parents = [p for p in result['branches'] if kept < set(p['feature_ids']) and
                   _ring_key([f for f in p['feature_ids'] if f in kept]) == tuple(child['feature_ids'])]
        # 只记录删除偏序中的直接父分支；不把父分支人数重复计为子分支支持。
        for parent in parents:
            if not any(kept < set(mid['feature_ids']) < set(parent['feature_ids']) and
                       _ring_key([f for f in parent['feature_ids'] if f in mid['feature_ids']]) == tuple(mid['feature_ids'])
                       for mid in parents):
                child['parent_deletions'].append(dict(parent_branch_id=parent['branch_id'],
                                                     deleted_feature_ids=sorted(set(parent['feature_ids']) - kept)))
    return dict(result, status='exploratory_branches_retained')
