"""Bounded-memory verification of saved prefix/endpoint links, without fusion.

Checks delivery completeness rather than re-running the scientific experiment.
The origin/status table keeps deferred two-person prefixes separate from failures.
"""
import argparse
import collections
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--results', required=True)
    p.add_argument('--orders', required=True)
    a = p.parse_args()
    out = Path(a.results)
    completion = json.loads((out / 'COMPLETION.json').read_text())
    orders = pd.read_csv(a.orders, keep_default_na=False)
    endpoint_keys = set()
    origin = collections.Counter()
    status = collections.Counter()
    layer_status = collections.Counter()
    formula_max = 0.0
    formula_n = 0
    scalar_n = 0
    needed = ['team_key', 'pool_id', 'k', 'pool_n', 'condition', 'layer',
              'endpoint_origin', 'B8L2', 'D10', 'B8_formula_residual',
              'geometry_available', 'complete_evaluable']
    for d in pd.read_csv(out / 'ENDPOINT_SCALARS.csv.gz', usecols=needed, chunksize=20000):
        keys = set(d.team_key)
        assert len(keys) == len(d) and not keys.intersection(endpoint_keys)
        endpoint_keys.update(keys)
        scalar_n += len(d)
        origin.update(d.endpoint_origin.fillna('UNKNOWN'))
        for r in d.itertuples(index=False):
            state = 'policy_deferred_k2' if r.k == 2 else ('scorable' if pd.notna(r.B8L2) else 'unscorable_nonpolicy')
            status[(str(r.endpoint_origin), state)] += 1
            layer_status[(r.condition, r.layer, state)] += 1
        z = d.B8_formula_residual.dropna().abs()
        if len(z):
            formula_max = max(formula_max, float(z.max()))
            formula_n += len(z)
        assert d.loc[d.k.eq(2), 'B8L2'].isna().all()
    path_counts = collections.Counter()
    path_seen = collections.defaultdict(set)
    path_min = {}
    path_max = {}
    full_keys = collections.defaultdict(set)
    prefix_status = collections.Counter()
    used = set()
    prefix_n = 0
    cols = ['pool_id', 'path_id', 'k', 'pool_n', 'team_key', 'policy', 'B8L2']
    for d in pd.read_csv(out / 'PREFIX_RESULTS.csv.gz', usecols=cols, chunksize=20000):
        assert set(d.team_key).issubset(endpoint_keys)
        assert not d.duplicated(['path_id', 'k']).any()
        used.update(d.team_key)
        prefix_n += len(d)
        path_counts.update(d.path_id)
        for pid, g in d.groupby('path_id', sort=False):
            values = set(g.k.astype(int))
            assert not path_seen[pid].intersection(values)
            path_seen[pid].update(values)
            path_min[pid] = min(path_min.get(pid, np.inf), int(g.k.min()))
            path_max[pid] = max(path_max.get(pid, 0), int(g.k.max()))
        for r in d.loc[d.k.eq(d.pool_n)].itertuples(index=False):
            full_keys[r.pool_id].add(r.team_key)
        for (policy, is2, scored), n in d.groupby(['policy', d.k.eq(2), d.B8L2.notna()]).size().items():
            state = 'policy_deferred_k2' if is2 else ('scorable' if scored else 'unscorable_nonpolicy')
            prefix_status[(policy, state)] += int(n)
    assert used == endpoint_keys
    assert scalar_n == completion['unique_endpoints']
    assert prefix_n == completion['prefix_rows']
    assert len(path_counts) == len(orders) == completion['paths']
    assert set(path_counts) == set(orders.path_id)
    assert all(path_min[k] == 1 and path_counts[k] == path_max[k] for k in path_counts)
    assert all(path_seen[k] == set(range(1, path_max[k] + 1)) for k in path_counts)
    assert all(len(v) == 1 for v in full_keys.values())
    record = dict(
        source_commit='72a44e80c344975962e1071bd54d894dd86bb4b4', data_release='v2',
        orders=len(orders), prefix_rows=prefix_n, unique_endpoint_rows=scalar_n,
        pools=len(full_keys), missing_endpoint_links=0, duplicate_endpoint_rows=0,
        complete_integer_prefix_catalogue=True, k2='registered, deferred by frozen policy; no score imputed',
        one_full_pool_member_set_each=True, all_full_pool_policies_share_endpoint=True,
        origins=dict(origin), B8_formula_diagnostic_rows=formula_n,
        B8_formula_max_absolute_residual=formula_max,
        extra_fusions_in_this_verification=0, extra_scores_in_this_verification=0)
    (out / 'DELIVERY_VERIFICATION.json').write_text(json.dumps(record, ensure_ascii=False, indent=2))
    pd.DataFrame([dict(endpoint_origin=o, state=s, endpoints=n) for (o,s),n in status.items()]).to_csv(out / 'ENDPOINT_ORIGIN_STATUS.csv', index=False)
    pd.DataFrame([dict(condition=c, layer=l, state=s, endpoints=n) for (c,l,s),n in layer_status.items()]).to_csv(out / 'ENDPOINT_LAYER_STATUS.csv', index=False)
    pd.DataFrame([dict(policy=p, state=s, prefixes=n) for (p,s),n in prefix_status.items()]).to_csv(out / 'PREFIX_POLICY_STATUS.csv', index=False)
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
