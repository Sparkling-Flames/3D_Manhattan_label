"""同一绑定循环距离下比较完整链接与硬直径全局亲近度；离线人工审查。"""
import itertools
import json

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from .worker_annotation_similarity_20261018 import ROOT, SNAPSHOT, IMAGES, RECORD_FIELDS, analyze_images, cluster

PAGE = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'
OUT = ROOT / 'research/statistics/cluster_review_20261018'


def objective(d, groups, cut):
    return float(sum(max(0., 1 - d[a, b] / cut) ** 2
                     for g in groups for a, b in itertools.combinations(g, 2)))


def affinity_partition(d, cut):
    """Same-cluster binary variables plus all transitivity triangles, as September candidate."""
    n = len(d)
    if n < 2:
        return [[i] for i in range(n)], dict(optimal=True, status=0, gap=0.)
    edges = list(itertools.combinations(range(n), 2))
    idx = {e: k for k, e in enumerate(edges)}
    triples = list(itertools.combinations(range(n), 3))
    a = lil_matrix((3 * len(triples), len(edges)))
    for t, (i, j, k) in enumerate(triples):
        ids = [idx[i, j], idx[i, k], idx[j, k]]
        for z in range(3):
            for q in range(3):
                a[3*t+z, ids[q]] = -1 if q == z else 1
    near = np.array([d[i, j] <= cut for i, j in edges], float)
    weights = np.array([max(0., 1-d[i, j]/cut)**2 for i, j in edges])
    result = milp(-weights, integrality=np.ones(len(edges)), bounds=Bounds(0, near),
                  constraints=LinearConstraint(a.tocsr(), -np.inf, 1) if triples else None,
                  options=dict(time_limit=60., mip_rel_gap=0.))
    if result.x is None:
        raise RuntimeError('No feasible partition: ' + result.message)
    parent = list(range(n))
    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for value, (i, j) in zip(result.x, edges):
        if value > .5:
            parent[root(j)] = root(i)
    groups = [[i for i in range(n) if root(i) == r] for r in sorted({root(i) for i in range(n)})]
    assert all(d[i, j] <= cut for g in groups for i, j in itertools.combinations(g, 2))
    assert all((root(i) == root(j)) == (value > .5) for value, (i, j) in zip(result.x, edges))
    return groups, dict(optimal=result.status == 0, status=int(result.status), gap=float(result.mip_gap),
                        message=result.message)


def build():
    snapshot = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    images = [p for p in snapshot['images'] if p['image'] in IMAGES]
    assert len(images) == 8
    pairs, _ = analyze_images(images)
    gallery = json.loads((ROOT / 'research/statistics/annotation_gallery_20261017/gallery.json').read_text(encoding='utf-8'))
    photos = {p['image_id']: p for p in gallery['images']}
    payload = dict(schema='cluster_review_20261018_v1', source=str(SNAPSHOT.relative_to(ROOT)),
                   revision=snapshot['analysis_revision'], distance='bound_cyclic_max_endpoint_degrees',
                   cuts=[6, 9, 12], images=[])
    for image in sorted(images, key=lambda p: p['image']):
        records = sorted([{k: r[k] for k in RECORD_FIELDS if k in r} for r in image['records']],
                         key=lambda r: (r['worker_id'], r['object_id']))
        n = len(records)
        by_id = {r['object_id']: i for i, r in enumerate(records)}
        matrix = np.full((n, n), np.nan)
        np.fill_diagonal(matrix, 0)
        pp = []
        for row in (r for r in pairs if r['image_code'] == image['image']):
            i, j = by_id[row['object_id_a']], by_id[row['object_id_b']]
            d = row['structure_bound_cyclic_deg']
            if d is not None:
                matrix[i, j] = matrix[j, i] = d
            pp.append(dict(a=i, b=j, d=d, reason=row['structure_reason'],
                           shift=row['bound_cyclic_shift_a_to_b'], margin=row['bound_cyclic_shift_margin_deg']))
        photo = photos[image['image_id']]
        path = next(p for p in (photo.get('original_path'), photo.get('thumbnail_path')) if p and (ROOT / p).is_file())
        item = dict(image_code=image['image'], photo='../../../'+path, records=records, pairs=pp, states=[])
        counts = [len(r['points'])//2 for r in records]
        for cut in payload['cuts']:
            groups = dict(complete=[], affinity=[])
            statuses = []
            for count in sorted(set(counts)):
                ids = [i for i, c in enumerate(counts) if c == count]
                d = matrix[np.ix_(ids, ids)]
                assert np.isfinite(d).all()
                labels = cluster(d, cut)
                groups['complete'].extend([[ids[z] for z in range(len(ids)) if labels[z] == label]
                                           for label in sorted(set(labels))])
                gg, status = affinity_partition(d, cut)
                groups['affinity'].extend([[ids[z] for z in g] for g in gg])
                statuses.append(dict(pair_count=count, **status))
            for gs in groups.values():
                gs.sort(key=lambda g: tuple(records[i]['worker_id'] for i in g))
                assert sorted(i for g in gs for i in g) == list(range(n))
                assert all(len({counts[i] for i in g}) == 1 for g in gs)
            scores = {m: objective(matrix, gs, cut) for m, gs in groups.items()}
            if all(s['optimal'] for s in statuses):
                assert scores['affinity'] >= scores['complete'] - 1e-7
            item['states'].append(dict(cut=cut, groups=groups, objective=scores, solver=statuses))
        payload['images'].append(item)
    OUT.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    (OUT / 'review.json').write_text(encoded, encoding='utf-8')
    (PAGE / 'cluster-review-data.js').write_text('window.CLUSTER_REVIEW='+encoded+';\n', encoding='utf-8')
    summary = dict(images=len(images), records=sum(len(i['records']) for i in payload['images']),
                   states=sum(len(i['states']) for i in payload['images']),
                   all_optimal=all(s['optimal'] for i in payload['images'] for st in i['states'] for s in st['solver']))
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    build()
