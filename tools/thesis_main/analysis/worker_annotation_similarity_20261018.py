"""八图原作答距离与条件性结构分簇；不使用GT、人员质量或融合输出。"""
import argparse
import csv
import io
import itertools
import json
from pathlib import Path

import numpy as np

from .paired_split_research.study import angular, cyclic, cluster
from .research_round_20260929 import reconstruct
from .wall_consensus_population_20261014 import footprint

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = ROOT / 'research/fusion/worker_composition_fusion_20261018/input_snapshot.json'
OUT = ROOT / 'research/workers/worker_exchangeability_20261018'
IMAGES = {'7y3sRwLe3Va-04', 'B6ByNegPMKs-11', 'UwV83HsGsw3-09', 'X7HyMhZNoso-13',
          'q9vSo1VnCiC-13', 'rPc6DW4iMge-06', 'uNb9QFRL6hY-21', 'wc2JMjhGNzB-15'}
RECORD_FIELDS = ('id', 'object_id', 'worker_id', 'points', 'source_pair_indices',
                 'ring_confirmed', 'order_used', 'order_status')


def geometry(record):
    reconstructed = reconstruct(record, coordinate_convention='continuous')
    poly = footprint(reconstructed['floor'])
    points = np.asarray(record['points'], float)
    valid = (points.ndim == 2 and points.shape[1:] == (2,) and len(points) >= 6
             and len(points) % 2 == 0 and np.isfinite(points).all() and (points >= 0).all()
             and (points[:, 0] <= 1024).all() and (points[:, 1] < 512).all())
    count = len(points) // 2 if points.ndim == 2 and len(points) % 2 == 0 else None
    return dict(poly=poly, p=points, pair_count=count, structure_available=bool(valid),
                reason='' if poly is not None else reconstructed.get('reason', 'invalid_declared_footprint'),
                structure_reason='' if valid else 'invalid_current_paired_points')


def analyze_images(images):
    pair_rows, memberships = [], []
    for image in sorted(images, key=lambda item: item['image']):
        # 仅投影当前原作答字段，快照所附参考、质量和融合信息不传入计算。
        records = [{key: row[key] for key in RECORD_FIELDS if key in row}
                   for row in image['records']]
        records.sort(key=lambda row: (row['worker_id'], row['object_id']))
        n = len(records)
        assert len({r['worker_id'] for r in records}) == n
        assert len({r['object_id'] for r in records}) == n
        geometries = [geometry(row) for row in records]
        range_distances, structure_distances = [np.full((n, n), np.nan) for _ in range(2)]
        for matrix in (range_distances, structure_distances):
            np.fill_diagonal(matrix, 0.)
        meta = dict(image_code=image['image'], image_id=image['image_id'],
                    building_id=image['building'], condition=image['condition'])
        for i, j in itertools.combinations(range(n), 2):
            a, b = records[i], records[j]
            ga, gb = geometries[i], geometries[j]
            available = ga['poly'] is not None and gb['poly'] is not None
            distance = intersection = union = None
            if available:
                intersection = ga['poly'].intersection(gb['poly']).area
                union = ga['poly'].area + gb['poly'].area - intersection
                raw = 1. - intersection / union
                assert -1e-12 <= raw <= 1. + 1e-12
                distance = float(np.clip(raw, 0., 1.))
                range_distances[i, j] = range_distances[j, i] = distance
            same_count = ga['pair_count'] == gb['pair_count']
            structure_available = ga['structure_available'] and gb['structure_available'] and same_count
            structure_distance = shift = margin = None
            if structure_available:
                p, q = ga['p'], gb['p']
                cost = np.maximum(angular(p[::2], q[::2]), angular(p[1::2], q[1::2]))
                structure_distance, shift, margin = cyclic(cost)
                reverse = cyclic(np.maximum(angular(q[::2], p[::2]), angular(q[1::2], p[1::2])))[0]
                assert abs(structure_distance - reverse) < 1e-10
                structure_distances[i, j] = structure_distances[j, i] = structure_distance
            pair_rows.append(dict(**meta, object_id_a=a['object_id'], object_id_b=b['object_id'],
                worker_id_a=a['worker_id'], worker_id_b=b['worker_id'], record_id_a=a['id'], record_id_b=b['id'],
                distance_floor_1_minus_iou=distance, available=available,
                reason='' if available else '|'.join(x for x in [ga['reason'], gb['reason']] if x),
                pair_count_a=ga['pair_count'], pair_count_b=gb['pair_count'], same_pair_count=same_count,
                intersection_area_h2=intersection, union_area_h2=union,
                structure_bound_cyclic_deg=structure_distance, structure_available=structure_available,
                structure_reason='' if structure_available else ('different_pair_count' if not same_count
                    else '|'.join(x for x in [ga['structure_reason'], gb['structure_reason']] if x)),
                bound_cyclic_shift_a_to_b=shift, bound_cyclic_shift_margin_deg=margin))

        methods = [
            ('range_similarity_complete', [.1, .2, .3], range_distances,
             [i for i, g in enumerate(geometries) if g['poly'] is not None], 'unitless'),
            ('annotation_structure_bound_cyclic_complete', [6., 9., 12.], structure_distances,
             [i for i, g in enumerate(geometries) if g['structure_available']], 'deg')]
        for method, cuts, distances, valid, unit in methods:
            is_range = method == 'range_similarity_complete'
            # 不同点对数不进入同一个结构距离矩阵，缺失也不编码为共同簇。
            subpools = [valid] if is_range else [
                [i for i in valid if geometries[i]['pair_count'] == count]
                for count in sorted({geometries[i]['pair_count'] for i in valid})]
            previous_count = n + 1
            for cut in cuts:
                groups, reverse_same = [], True
                for indices in (pool for pool in subpools if pool):
                    matrix = distances[np.ix_(indices, indices)]
                    assert np.isfinite(matrix).all()
                    labels = cluster(matrix, cut)
                    current = [sorted(indices[z] for z in range(len(indices)) if labels[z] == label)
                               for label in sorted(set(labels))]
                    groups.extend(current)
                    reverse = cluster(matrix[::-1, ::-1], cut)
                    reverse_groups = [sorted(indices[::-1][z] for z in range(len(indices)) if reverse[z] == label)
                                      for label in sorted(set(reverse))]
                    reverse_same = reverse_same and sorted(current) == sorted(reverse_groups)
                groups.sort(key=lambda group: tuple(records[i]['worker_id'] for i in group))
                assert len(groups) <= previous_count
                previous_count = len(groups)
                group_for = {i: group for group in groups for i in group}
                id_for = {i: index + 1 for index, group in enumerate(groups) for i in group}
                for i, record in enumerate(records):
                    group = group_for.get(i)
                    available = group is not None
                    diameter = medoid = cluster_id = None
                    if available:
                        matrix = distances[np.ix_(group, group)]
                        diameter = float(matrix.max())
                        assert diameter <= cut + 1e-10
                        if not is_range:
                            assert len({geometries[z]['pair_count'] for z in group}) == 1
                        medoid = group[int(np.argmin(matrix.sum(axis=1)))]
                        prefix = 'RS' if is_range else 'AS'
                        cluster_id = f"{image['image']}|{method}|{cut:g}|{prefix}{id_for[i]:02d}"
                    memberships.append(dict(**meta, object_id=record['object_id'], worker_id=record['worker_id'],
                        record_id=record['id'], pair_count=geometries[i]['pair_count'], method=method,
                        threshold=cut, threshold_unit=unit, cluster_id=cluster_id,
                        cluster_size=len(group) if available else None, cluster_diameter=diameter,
                        cluster_medoid_worker_id=records[medoid]['worker_id'] if available else None,
                        cluster_available=available, floor_available=geometries[i]['poly'] is not None,
                        structure_available=geometries[i]['structure_available'],
                        reason='' if available else geometries[i]['reason' if is_range else 'structure_reason'],
                        partition_unchanged_under_reverse_input=reverse_same, order_status=record.get('order_status'),
                        ring_confirmed=record.get('ring_confirmed'), order_used=record.get('order_used')))
    return pair_rows, memberships


def csv_bytes(rows):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return ('\ufeff' + buffer.getvalue()).encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--check', action='store_true', help='重算并逐字节核对已有两表，不写文件')
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding='utf-8-sig'))
    images = [image for image in snapshot['images'] if image['image'] in IMAGES]
    assert len(images) == len(IMAGES) and {image['image'] for image in images} == IMAGES
    pairs, memberships = analyze_images(images)
    for name, rows in [('annotation_pair_distances.csv', pairs), ('annotation_clusters.csv', memberships)]:
        payload = csv_bytes(rows)
        if args.check:
            assert (args.out / name).read_bytes() == payload, f'交付结果不一致：{name}'
        else:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / name).write_bytes(payload)
    print(json.dumps(dict(mode='checked' if args.check else 'written', images=len(images),
                          pairs=len(pairs), memberships=len(memberships), out=str(args.out)), ensure_ascii=False))


if __name__ == '__main__':
    main()
