"""Bound local-point experiment; leaves the released run and raw points untouched.

Run: python -m tools.thesis_main.analysis.clustering_release.local_points
  --root <verified study> --evidence <follow-up evidence> --out <new directory>
Sphere/image maximum endpoint distances x complete/actual-representative groups.
Human correspondences are a separate retrospective view, never training truth.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import release
from .history_analysis import fixed_mode_stats, next_uncovered
from .pipeline import read, sha, pointsha
from ..paired_split_research import study as st
from ..paired_split_research.release_review import verify_run, validate_review

CUTS = (6., 9., 12.)


def pixel_distance(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    dx = (a[:, None, 0]-b[None, :, 0]+512) % 1024-512
    return np.hypot(dx, a[:, None, 1]-b[None, :, 1])


def partition(d, ids, threshold, kind):
    """Canonical sorting also stabilizes ties under input-row permutation.

    Representative cover reuses RC2 audit_geometry.reps' greedy rule: most
    uncovered neighbours, smallest mean distance, then canonical identity.
    """
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate canonical identity')
    order = np.argsort(ids)
    d = np.round(np.asarray(d, float)[np.ix_(order, order)], 8)
    if d.shape != (len(ids), len(ids)) or not np.isfinite(d).all() or not np.allclose(d, d.T) or np.any(np.diag(d)):
        raise ValueError('Invalid distance matrix')
    if kind == 'complete':
        labels = release.cluster(d, threshold)
        groups = sorted((np.flatnonzero(labels == k) for k in set(labels)), key=lambda ix: ix[0])
        centres = [int(ix[np.argmin(np.round(d[np.ix_(ix, ix)].sum(1), 8))]) for ix in groups]
    elif kind == 'representative':
        left = set(range(len(ids))); groups = []; centres = []
        while left:
            ix = sorted(left)
            candidates = []
            for i in ix:
                close = [j for j in ix if d[i, j] <= threshold]
                candidates.append((-len(close), round(float(d[i, close].mean()), 8), i, close))
            _, _, i, close = min(candidates)
            centres.append(i); groups.append(np.array(close)); left.difference_update(close)
    else:
        raise ValueError('Unknown partition')
    labels = np.zeros(len(ids), int)
    for n, ix in enumerate(groups, 1):
        labels[order[ix]] = n
    return labels, [ids[order[i]] for i in centres]


def endpoint_rows(a, b, mapping=None):
    left, right = a['links'], b['links']
    if left is None or right is None or len(left) != len(right):
        raise ValueError('Complete equal-count pairs required')
    if mapping is not None:
        if sorted(mapping) != list(range(1, len(right)+1)):
            raise ValueError('Human mapping must be a complete bijection')
        right = right[np.asarray(mapping)-1]
    rows = []
    for j, role in enumerate(('top', 'bottom')):
        aa, bb = a['p'][left[:, j]], b['p'][right[:, j]]
        angles = np.diag(st.angular(aa, bb))
        pixels = np.diag(pixel_distance(aa, bb))
        for k, (p, q) in enumerate(zip(aa, bb)):
            rows.append(dict(role=role, a_point_1based=int(left[k, j])+1,
                             b_point_1based=int(right[k, j])+1,
                             dx_px=float((q[0]-p[0]+512) % 1024-512), dy_px=float(q[1]-p[1]),
                             sphere_deg=float(angles[k]), image_px=float(pixels[k])))
    return rows


def run(root, evidence, out):
    root, evidence, out = map(Path, (root, evidence, out))
    if out.resolve().is_relative_to(root.resolve()):
        raise ValueError('Experiment must not overwrite the frozen study')
    manifest = verify_run(root, numerical_only=True)
    notes = read(evidence/'latest_decisions.json')
    if notes['source_run_id'] != manifest['run_id']:
        raise ValueError('Human evidence belongs to another run')
    old_review = read(evidence/'review_manifest_16.json')
    decisions = validate_review(read(evidence/'user_review_16.json'), old_review['binding'],
                                [c['key'] for c in old_review['cases']])
    _, rows, _, _, _ = release.prepare(root)
    audit = pd.read_csv(root/'inputs/prior_response_audit.csv').set_index('id')
    rec, eligibility = st.prepare(rows, audit, st.accepted_map(root/'inputs', rows), 'min_horizontal')
    overrides = {}
    for h in notes['confirmed_correspondences']:
        a, b = rec[h['id_a']], rec[h['id_b']]
        if any(h['point_payload_sha_'+side] != pointsha(rec[h['id_'+side]]['p'].tolist()) for side in ('a', 'b')):
            raise ValueError('Human point version mismatch')
        if a['row']['image_id'] != b['row']['image_id'] or a['row']['raw_condition'] != b['row']['raw_condition']:
            raise ValueError('Cross-image or cross-condition mapping')
        endpoint_rows(a, b, h['pair_order_b_1based'])
        overrides[frozenset((a['id'], b['id']))] = h
    out.mkdir(parents=True, exist_ok=True)
    release.frame(out, 'eligibility.csv', eligibility)
    grouped = collections.defaultdict(list)
    for cid, r in rec.items():
        if r['links'] is not None:
            grouped[r['row']['image_id']+'|'+r['row']['raw_condition']].append(cid)
    pairs = []; endpoints = []; members = []; summaries = []; curves = []; profiles = []; groups = {}
    for key, ids in sorted(grouped.items()):
        ids.sort(); n = len(ids); rr = [rec[c] for c in ids]
        base = dict(key=key, code=rr[0]['audit']['code'], image_id=rr[0]['row']['image_id'],
                    condition=rr[0]['row']['raw_condition'], building=rr[0]['row']['building_id'], N=n)
        matrices = {m: np.full((n, n), 1e6) for m in ('sphere', 'image')}
        for d in matrices.values(): np.fill_diagonal(d, 0)
        changed = {}
        for i, j in itertools.combinations(range(n), 2):
            a, b = rr[i], rr[j]
            if len(a['p']) != len(b['p']):
                continue  # Hard count incompatibility, not a measured million-unit error.
            ep = endpoint_rows(a, b)
            diagnostic, maps = st.compare(a, b)
            values = {m: max(e['sphere_deg' if m == 'sphere' else 'image_px'] for e in ep) for m in matrices}
            for m, value in values.items(): matrices[m][i, j] = matrices[m][j, i] = value
            entry = dict(**base, id_a=ids[i], id_b=ids[j], worker_a=a['row']['worker_id'], worker_b=b['row']['worker_id'],
                         count=len(a['p']), sphere_deg=values['sphere'], image_px=values['image'],
                         split_fixed_deg=diagnostic['split_fixed'], split_cyclic_deg=diagnostic['split_cyclic'],
                         bound_free_deg=diagnostic['bound_free'], bound_cyclic_deg=diagnostic['bound_cyclic'],
                         correspondence_alert_9=values['sphere']>9 and diagnostic['bound_free']<=9)
            pairs.append(entry)
            endpoints.extend(dict(key=key, id_a=ids[i], id_b=ids[j], view='automatic', **e) for e in ep)
            human = overrides.get(frozenset((ids[i], ids[j])))
            if human:
                ea, eb = rec[human['id_a']], rec[human['id_b']]
                he = endpoint_rows(ea, eb, human['pair_order_b_1based'])
                changed[i, j] = {m: max(e['sphere_deg' if m == 'sphere' else 'image_px'] for e in he) for m in matrices}
                endpoints.extend(dict(key=key, id_a=human['id_a'], id_b=human['id_b'], view='human_correspondence', **e) for e in he)
        views = {'automatic': matrices, 'human_correspondence': {m:d.copy() for m,d in matrices.items()}}
        for (i, j), values in changed.items():
            for m, value in values.items(): views['human_correspondence'][m][i,j] = views['human_correspondence'][m][j,i] = value
        g = dict(**base, ids=ids, workers=[r['row']['worker_id'] for r in rr], labels={}, representatives={}, matrices={})
        tri = np.triu_indices(n, 1)
        for view, dd in views.items():
            g['matrices'][view] = {m:d.tolist() for m,d in dd.items()}
            for metric, d in dd.items():
                for nominal in CUTS:
                    cut = nominal if metric == 'sphere' else nominal*1024/360
                    near = np.round(d, 8)<=cut
                    expected_coverage = [next_uncovered(d, k, cut) for k in range(1,n)]
                    for kind in ('complete', 'representative'):
                        labels, centres = partition(d, ids, cut, kind)
                        method = f'{view}:{metric}:{kind}:{nominal:g}'
                        g['labels'][method] = labels.tolist(); g['representatives'][method] = centres
                        counts = collections.Counter(labels)
                        same = labels[:,None] == labels[None,:]
                        meta = dict(**base, view=view, metric=metric, partition=kind, nominal_cut=nominal,
                                    actual_cut=cut, distance_unit='degree' if metric=='sphere' else 'pixel_1024x512')
                        summaries.append(dict(**meta, clusters=len(counts), singleton_clusters=sum(v==1 for v in counts.values()),
                                              close_pairs_split=int((near & ~same)[tri].sum()),
                                              far_pairs_merged=int((~near & same)[tri].sum()),
                                              near_pairs=int(near[tri].sum()), manual_pair_overrides=len(changed) if view!='automatic' else 0))
                        for i,cid in enumerate(ids):
                            centre = centres[labels[i]-1]
                            alt = [c for c in centres if near[i, ids.index(c)]]
                            members.append(dict(**meta, id=cid, worker=rr[i]['row']['worker_id'], cluster=int(labels[i]),
                                                cluster_size=counts[labels[i]], representative=centre,
                                                alternative_representatives=';'.join(alt)))
                            profiles.append(dict(**meta, id=cid, worker=rr[i]['row']['worker_id'],
                                                 disagreement=(1-(near[i].sum()-1)/(n-1)) if n>1 else None,
                                                 no_close_peer=bool(near[i].sum()==1) if n>1 else None,
                                                 partition_singleton=counts[labels[i]]==1,
                                                 imputed=rr[i]['row']['imputed_point']))
                        for k in range(1,n+1):
                            curves.append(dict(**meta, k=k, next_real_person_uncovered=expected_coverage[k-1] if k<n else None,
                                               **fixed_mode_stats(labels,k)))
        groups[key] = g
    release.frame(out, 'pairwise.csv.gz', pairs)
    release.frame(out, 'endpoint_residuals.csv.gz', endpoints)
    release.frame(out, 'memberships.csv.gz', members)
    release.frame(out, 'partition_summary.csv', summaries)
    release.frame(out, 'exact_curves.csv.gz', curves)
    release.frame(out, 'worker_observations.csv.gz', profiles)
    release.writejson(out/'groups.json', groups)
    # Each image x condition needs a new whole-cluster check after method selection.
    coverage = []
    for iid, condition in sorted({(r['image_id'],r['raw_condition']) for r in rows}):
        key=iid+'|'+condition; rs=[r for r in rows if r['image_id']==iid and r['raw_condition']==condition]
        coverage.append(dict(key=key,image_id=iid,condition=condition,code=audit.loc[rs[0]['canonical_annotation_id'],'code'],
                             raw_records=len(rs),retained_records=sum(r['worker_id'] not in {'W019','W026'} for r in rs),
                             auto_bound_records=len(grouped[key]),prior_16_review=key in decisions,
                             original_image_checked='',specified_responses_checked='',whole_clusters_checked='',
                             checked_canonical_ids='',checked_method_version='',reviewer='',evidence_source='',
                             final_user_decision='',status='pending_after_method_selection'))
    release.frame(out, 'full_history_visual_coverage.csv', coverage)
    c=pd.DataFrame(curves)
    invariant=c.groupby(['key','view','metric','nominal_cut','k']).next_real_person_uncovered.nunique(dropna=False).max()==1
    assert invariant
    release.writejson(out/'CHECKS.json',dict(source_run_id=manifest['run_id'],raw_records=len(rows),
        retained_records=sum(r['worker_id'] not in {'W019','W026'} for r in rows),split_available=len(rec),
        bound_available=sum(r['links'] is not None for r in rec.values()),
        historical_images=len({r['image_id'] for r in rows}),historical_units=len(coverage),
        confirmed_mapping_pairs=len(overrides),coverage_partition_invariance=bool(invariant),
        raw_points_modified=False,full_visual_acceptance=False,final_method_selected=False,
        display_asset_verification='not part of numerical run; visual review builder still requires all images',
        prior_curves='retrospective_fixed_fullpool_labels; prefix replay remains Pro task',
        sentinel=1000000, sentinel_meaning='incompatible total count; not observed error'))
    release.writejson(out/'EXPERIMENT_MANIFEST.json',dict(schema='local_point_comparison_v1',source_run_id=manifest['run_id'],
        source_manifest_sha=sha(root/'RUN_MANIFEST.json'),evidence={p.name:sha(p) for p in sorted(evidence.glob('*.json'))},
        code={p.name:sha(p) for p in [Path(__file__),Path(st.__file__),Path(release.__file__)]},
        files={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='EXPERIMENT_MANIFEST.json'},
        primary_measurement='local original endpoints; no IoU or 3D weighting',
        coordinate_convention='1024x512; sphere retains existing +0.5 y pixel-centre; image uses differences',
        thresholds='6/9/12 degrees and 17.0667/25.6/34.1333 pixels are probes, not confirmed semantic thresholds',
        manual_view='retrospective only; unchanged automatic entries retained for unreviewed pairs'))
    return read(out/'CHECKS.json')


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(); print(json.dumps(run(a.root,a.evidence,a.out),ensure_ascii=False,indent=2))
