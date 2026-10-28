"""沿用冻结的整路径bootstrap，更新受影响池；未变池结果保持可复用。"""
import argparse
import importlib.util
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
import numpy as np
from .prepare_v21_natural_inputs_20261028 import EXT, PRIOR, TARGET as INPUT, repair_new_space_deferred
from .rebuild_v21_20261028 import OUT

TARGET = OUT / 'natural_analysis'


def save_csv(frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not len(frame.columns):
        assert path.name.endswith('__intervals.csv.gz')
        frame = pd.DataFrame(columns=['pool_id', 'cohort', 'interval', 'k_from', 'k_to'])
    frame.to_csv(path, index=False, encoding='utf-8-sig')
    assert len(pd.read_csv(path, low_memory=False)) == len(frame)
    return dict(file=str(path), rows=len(frame), fields=len(frame.columns))


def process(path):
    sys.path.insert(0, str(EXT / 'analysis_precision26'))
    import precision_core as core
    import analyze_natural as native
    native.bootstrap_weights = core.bootstrap_weights
    # A one-person pool has a full endpoint but no population-growth interval.
    native.weighted_intervals = lambda a,w,s,defs: core.weighted_intervals(a,w,s,defs) if defs else np.empty((len(w),0,len(core.IMETRICS)))
    spec = importlib.util.spec_from_file_location('v21_blocks', EXT / 'engine26/derive_frozen_blocks.py')
    blocks = importlib.util.module_from_spec(spec); spec.loader.exec_module(blocks)
    core._FROZEN_BLOCKS = blocks
    native.save_csv = save_csv
    native.save_json = lambda obj, p: p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    native.COHORTS['original24'] = ['old24']
    native.COHORTS['new_space256'] = ['new_space256']
    native.STRATUM_COUNTS['new_space256'] = 256
    d = pd.read_csv(path, low_memory=False)
    new_space = d.stratum.eq('new_space256').all()
    if repair_new_space_deferred(d):
        d.to_csv(path, index=False, encoding='utf-8-sig')
    flags = core.numeric(d.policy_deferred)
    assert flags.isin([0, 1]).all() and flags.eq(1).equals(d.k.eq(2)), 'invalid deferred flags'
    pid = d.pool_id.iloc[0]
    exact_paths = d.path_id.str.contains('__exact_permutation_', regex=False).all()
    if exact_paths:
        n = int(d.pool_n.iloc[0])
        assert d.path_id.nunique() == math.factorial(n)
        assert all(g.team_key.nunique() == math.comb(n, int(k)) for k, g in d.groupby('k'))
        d['stratum'] = 'exact_permutation'
        native.COHORTS['exact_permutation'] = ['exact_permutation']
        native.STRATUM_COUNTS['exact_permutation'] = math.factorial(n)
        native.bootstrap_weights = lambda pid, name, count, B, master: np.ones((B, count))
    done = TARGET / 'pool_checkpoints' / (pid + '__DONE.json')
    if done.exists():
        receipt = json.loads(done.read_text(encoding='utf-8'))
        assert receipt['input_rows'] == len(d) and receipt['bootstrap'] == 2000
        if not new_space or receipt.get('deferred_schema') == 'explicit_k2_v1':
            return pid
    exact = pd.read_csv(PRIOR / 'analysis_precision/new_results/EXACT_FINITE_MARGINAL_STATISTICS.csv')
    exact_keys = set(map(tuple, exact[exact.exact_complete.eq(True) & exact.k.ne(2)][['pool_id', 'k']].to_numpy()))
    for c in set(core.RAW + core.COMP + core.BOOL).intersection(d.columns):
        d[c] = core.numeric(d[c])
    native.per_pool(pid, d, TARGET, 2000, 2026102607, 2, exact_keys)
    if new_space:
        receipt = json.loads(done.read_text(encoding='utf-8'))
        receipt['deferred_schema'] = 'explicit_k2_v1'
        done.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    if exact_paths:
        curves = TARGET / 'pool_checkpoints' / (pid + '__curves.csv.gz')
        c = pd.read_csv(curves)
        c['precision_target'] = 'complete_finite_permutation_population'
        c['Q_sd_population'] = d.groupby('k').B8L2.std(ddof=0).reindex(c.k).to_numpy()
        for field in c:
            if 'MCSE' in field or field.endswith('_boot_se'):
                c[field] = c[field].where(c[field].isna(), 0.)
            if field.startswith('Q_mean_t95_'):
                c[field] = c.Q_mean
            if field in ['P10_order_low', 'P10_order_high', 'P10_curve_Bonferroni_low', 'P10_curve_Bonferroni_high']:
                c[field] = c.Q_p10_inverse_cdf
            if field in ['P10_order_halfwidth', 'P10_linear_boot_halfwidth']:
                c[field] = c[field].where(c[field].isna(), 0.)
            for prefix in ['failure', 'actual_consensus_failure', 'output_unscoreable']:
                if field.startswith(prefix + '_') and any(term in field for term in ['CP_', 'Wilson_']):
                    c[field] = c[prefix + '_rate']
        save_csv(c, curves)
        components = TARGET / 'pool_checkpoints' / (pid + '__components.csv.gz')
        c = pd.read_csv(components); c['MCSE'] = c['MCSE'].where(c['mean'].isna(), 0.)
        save_csv(c, components)
    return pid


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--pool'); args = parser.parse_args()
    TARGET.mkdir(exist_ok=True)
    files = [INPUT / (args.pool + '.csv.gz')] if args.pool else sorted(INPUT.glob('*.csv.gz'))
    with ProcessPoolExecutor(max_workers=2) as executor:
        for i, pid in enumerate(executor.map(process, files), 1):
            print('natural analysis', i, '/', len(files), pid, flush=True)
    if not args.pool:
        for stem in ['curves', 'intervals', 'components', 'status', 'curve_bands', 'curve_band_summary', 'path_strata']:
            frames = [pd.read_csv(p, low_memory=False, dtype={'bootstrap_stratum_seed': str})
                      for p in sorted((TARGET / 'pool_checkpoints').glob('*__' + stem + '.csv.gz'))]
            save_csv(pd.concat(frames, ignore_index=True), TARGET / ('UPDATED_' + stem.upper() + '.csv.gz'))


if __name__ == '__main__':
    main()
