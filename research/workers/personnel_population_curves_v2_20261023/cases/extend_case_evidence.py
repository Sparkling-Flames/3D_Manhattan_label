"""Add small source-observation, edge and LOBO-role links to saved case states.

This does not run fusion or scoring. Reference assignment is descriptive and
must not be interpreted as a semantic adjudication or an engine correspondence.
"""
import sys
from pathlib import Path
sys.path.insert(0, '/tmp/hohonet_deps')
from build_cases import OUT, read, csvsave, angular, np, pd, linear_sum_assignment


def main():
    all_edges, all_raw, all_roles, steps = [], [], [], []
    primary_steps = {
        'UwV83HsGsw3-12': [3, 4, 5, 6, 7, 28],
        'pa4otMbVnkk-09': [3, 4, 5, 6, 7, 35],
        'UwV83HsGsw3-09': [10, 20, 33],
        'uNb9QFRL6hY-60': [7, 8, 9, 10, 11, 20, 33],
        'B6ByNegPMKs-33': [10, 20, 31],
    }
    for folder in sorted(OUT.iterdir()):
        if not (folder/'CASE_GEOMETRY.json.gz').exists():
            continue
        obj = read(folder/'CASE_GEOMETRY.json.gz')
        pool, case = obj['pool'], obj['case']
        image = case['image']
        votes = pd.read_csv(folder/'CASE_VOTES.csv')
        labels = pd.read_csv(folder/'LOBO_MEMBER_LABELS.csv')
        paths = pd.read_csv(folder/'PATH_SCALARS.csv')
        path = paths[paths.path_id.eq(case['path_id'])]
        ref = np.array(pool['reference']['points_1024x512'], float)
        edges, raw, roles = [], [], []
        for ks, state in obj['states'].items():
            k = int(ks)
            if state is None:
                continue
            vv = votes[votes.k.eq(k)].set_index('feature_id')
            ring = state.get('ring_diagnostics', {})
            for e in ring.get('edges', []):
                x, y = e['feature_ids']
                edges.append(dict(case=image, pool_id=pool['pool_id'], k=k,
                    from_group=x, to_group=y,
                    from_reference_corner=vv.loc[x, 'reference_corner'],
                    to_reference_corner=vv.loc[y, 'reference_corner'],
                    direct_support=e['direct_support'], projected_support=e['projected_support'],
                    direct_workers='|'.join(e['direct_workers']),
                    projected_workers='|'.join(e['projected_workers']),
                    source_ring_policy=ring.get('policy'),
                    ring_confirmed=ring.get('ring_confirmed'),
                    ring_tied_best=ring.get('tied_best')))
        nmax = max(map(int, obj['states']))
        full = votes[votes.k.eq(nmax)].copy()
        # Keep every source pair, including unassigned extras and large residuals.
        for record in pool['records']:
            pp = np.array(record['points'], float).reshape(-1, 2, 2)
            tc, bc = angular(pp[:, 0], ref[::2]), angular(pp[:, 1], ref[1::2])
            cc = np.maximum(tc, bc)
            ii, jj = linear_sum_assignment(cc)
            matching = {i: j for i, j in zip(ii, jj)}
            for i, pair in enumerate(pp):
                j = matching.get(i)
                raw.append(dict(case=image, pool_id=pool['pool_id'], condition=case['condition'],
                    worker_id=record['worker_id'], object_id=record['id'], pair_index=i,
                    source_pairs=len(pp), x_top_px=pair[0, 0], y_top_px=pair[0, 1],
                    x_bottom_px=pair[1, 0], y_bottom_px=pair[1, 1],
                    reference_corner=j+1 if j is not None else None,
                    top_error_deg=tc[i, j] if j is not None else None,
                    bottom_error_deg=bc[i, j] if j is not None else None,
                    max_error_deg=cc[i, j] if j is not None else None,
                    reference_diagnostic_only=True))
        for method, ml in labels.groupby('method'):
            for lab, cl in ml.groupby('fine_label'):
                ids = set(cl.worker_id)
                # Group centers below describe this image's actual pool members,
                # not the full training-fold cluster; exact labels remain saved.
                center = {f: cl[f].mean() for f in ['turn_history', 'short_history',
                    'redundancy_history', 'q_history', 't_history']}
                for vr in full[full.reference_corner.notna()].itertuples():
                    supporting = ids & set(vr.workers.split('|'))
                    roles.append(dict(case=image, pool_id=pool['pool_id'],
                        condition=case['condition'], heldout_building=pool['meta']['building'],
                        method=method, fine_label=lab, reference_corner=int(vr.reference_corner),
                        full_pool_k=nmax, full_pool_feature_id=vr.feature_id,
                        full_pool_group_support=vr.support, full_pool_selected=vr.selected,
                        full_pool_threshold=vr.threshold,
                        group_reference_max_error_deg=vr.reference_pair_max_error_deg,
                        class_available_n=len(ids), class_supporting_n=len(supporting),
                        class_supporting_fraction=len(supporting)/len(ids),
                        class_members='|'.join(sorted(ids)), supporting_members='|'.join(sorted(supporting)),
                        center_scope='actual pool subset of heldout fold labels', **center))
        for k in primary_steps[image]:
            row = path[path.k.eq(k)].iloc[0].to_dict()
            vv = votes[votes.k.eq(k)]
            row.update(case=image, threshold=int(vv.threshold.iloc[0]),
                key_corner_ref=4 if image.endswith('-12') else (8 if image.endswith('-60') else None))
            if row['key_corner_ref']:
                v = vv[vv.reference_corner.eq(row['key_corner_ref'])].iloc[0]
                row.update(key_corner_votes=v.support, key_corner_selected=v.selected,
                    key_corner_workers=v.workers)
            steps.append(row)
        csvsave(folder/'CASE_EDGES.csv', pd.DataFrame(edges))
        csvsave(folder/'CASE_RAW_REFERENCE_PAIRS.csv', pd.DataFrame(raw))
        csvsave(folder/'CLASS_LOCAL_SUPPORT.csv', pd.DataFrame(roles))
        all_edges.extend(edges); all_raw.extend(raw); all_roles.extend(roles)
        print('Saved edge/raw/class links: '+image, flush=True)
    csvsave(OUT/'CASE_EDGES.csv', pd.DataFrame(all_edges))
    csvsave(OUT/'CASE_RAW_REFERENCE_PAIRS.csv', pd.DataFrame(all_raw))
    csvsave(OUT/'CLASS_LOCAL_SUPPORT.csv', pd.DataFrame(all_roles))
    csvsave(OUT/'KEY_PREFIX_MECHANISMS.csv', pd.DataFrame(steps))


if __name__ == '__main__':
    main()
