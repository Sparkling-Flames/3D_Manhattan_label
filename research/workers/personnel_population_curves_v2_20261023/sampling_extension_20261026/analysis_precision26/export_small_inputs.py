#!/usr/bin/env python3
"""Export an independently readable six-pool finite subset; no new calculation."""
from pathlib import Path
import argparse, json, hashlib
import pandas as pd
from precision_core import save_csv, save_json


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', type=Path, required=True)
    root = ap.parse_args().root.resolve()
    out = root / 'analysis_precision26/small_exact_validation'
    inputs = out / 'inputs'; inputs.mkdir(exist_ok=True)
    pids = pd.read_csv(out / 'SMALL_POOLS_SUPPORT.csv').pool_id.tolist()
    prior = root / 'prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025'
    source = prior / 'new_endpoints/EXACT_MARGINAL_VALUES.csv.gz'
    finite = pd.read_csv(source, low_memory=False)
    finite = finite[finite.pool_id.isin(pids)].copy()
    assert len(finite) == 2234 and not finite.team_key.duplicated().any()
    files = [save_csv(finite, inputs / 'FINITE_TEAM_SCALARS_2234.csv.gz')]
    links, orders, origins = [], [], []
    for pid in pids:
        oldp = root / 'analysis_precision26/prior_pool_cache' / (pid + '.csv.gz')
        old = pd.read_csv(oldp, low_memory=False)
        old = old[old.stratum.isin(['old24', 'prior_new24'])]
        linkfields = ['pool_id', 'path_id', 'stratum', 'k', 'team_key', 'reference_id', 'reference_version']
        links.append(old[linkfields].copy())
        origins.append(dict(pool_id=pid, source_kind='old48_natural_prefixes', source=str(oldp.relative_to(root)), rows=len(old)))
        for stage, stratum in [(1, 'new104A'), (2, 'new104B')]:
            np = root / 'new_endpoints26' / ('stage' + str(stage)) / 'prefix_values' / (pid + '.csv.gz')
            nd = pd.read_csv(np, low_memory=False)
            nd = nd[nd.policy.eq('natural_random')].copy(); nd['stratum'] = stratum
            links.append(nd[linkfields].copy())
            origins.append(dict(pool_id=pid, source_kind=stratum + '_natural_prefixes', source=str(np.relative_to(root)), rows=len(nd)))
        op = root / 'design26/orders_by_pool' / (pid + '.csv.gz')
        od = pd.read_csv(op, dtype={'seed': str, 'master_seed': str}, low_memory=False)
        od = od[od.policy.eq('natural_random')].copy()
        assert len(od) == 208
        orders.append(od)
        origins.append(dict(pool_id=pid, source_kind='exact_new_natural_orders', source=str(op.relative_to(root)), rows=len(od)))
    links = pd.concat(links, ignore_index=True).sort_values(['pool_id', 'path_id', 'k'])
    orders = pd.concat(orders, ignore_index=True).sort_values(['pool_id', 'new_index'])
    assert len(links) == 12544 and links.path_id.nunique() == 1536
    assert len(orders) == 1248 and orders.path_id.nunique() == 1248
    assert set(links.team_key).issubset(finite.team_key)
    files.append(save_csv(links, inputs / 'NATURAL_PATH_TEAM_LINKS_12544.csv.gz'))
    files.append(save_csv(orders, inputs / 'NEW_NATURAL_ORDERS_1248.csv.gz'))
    files.append(save_csv(pd.DataFrame(origins), inputs / 'SOURCE_ROWS.csv'))
    source_metadata = dict(
        repository_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac',
        finite_source=str(source.relative_to(root)),
        finite_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        old24_source='repo/research/workers/personnel_population_curves_v2_20261023/stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz',
        prior_new24_source='inputs_cache26/precision25/NEW_PREFIX_VALUES_COMPACT.csv.gz',
        notes=['All input table rows are true saved rows; no missing original designs have been invented.',
               'Old48 orders can be reconstructed exactly from consecutive team memberships; their original seeds are not required or replaced.',
               'New-order seed columns are decimal strings, preserving unsigned 64-bit seed values.',
               'Every prefix occurrence is retained. A repeated team reuses a scalar, but keeps its sampling multiplicity.',
               'The six small pools add 1248 real independent orders and zero new fusion endpoints; all 2234 finite teams pre-existed.'],
        files=files)
    save_json(source_metadata, inputs / 'INPUT_PROVENANCE.json')
    print(json.dumps({k:v for k,v in source_metadata.items() if k == 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
