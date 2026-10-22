#!/usr/bin/env python3
"""Independent data-v1 audit of published personnel Q/T; no geometry/eligibility edits.

The estimator uses a constrained least-squares system after projecting out exact
task intercepts. It is intentionally self contained and does not import the
repository's fitting code. Building bootstrap draws are fixed before outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

DATA_RELEASE = 'v1'
SEED = 20261017
BOOTSTRAPS = 2000
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPO = Path(os.environ.get('PANORAMA_REPO', SCRIPT_DIR.parents[1] / 'repo'))


def save_csv(path, data):
    d = pd.DataFrame(data).copy()
    for col in d:
        if d[col].map(lambda x: isinstance(x, (list, dict))).any():
            d[col] = d[col].map(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x)
    d.to_csv(path, index=False, encoding='utf-8-sig')


def normalize(obj):
    if isinstance(obj, dict): return {str(k): normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)): return [normalize(x) for x in obj]
    if isinstance(obj, np.ndarray): return normalize(obj.tolist())
    if isinstance(obj, np.generic): return normalize(obj.item())
    if isinstance(obj, float) and not np.isfinite(obj): return None
    return obj


def save_json(path, value):
    path.write_text(json.dumps(normalize(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def label(effect, supported):
    if not supported or not np.isfinite(effect) or effect == 0: return 'unclassified'
    return 'above_pool' if effect > 0 else 'below_pool'


def margin_label(effect, supported):
    if not supported or not np.isfinite(effect): return 'unclassified'
    return 'relative_high' if effect > 2 else 'relative_low' if effect < -2 else 'boundary'


def informative(frame, axis):
    d = frame[np.isfinite(frame[axis])].copy()
    return d[d.groupby('context_key').worker_id.transform('nunique').ge(2)].copy()


def make_sufficient(frame, axis):
    d = informative(frame, axis)
    assert not d.duplicated(['context_key', 'worker_id']).any()
    assert d.groupby('context_key').building_id.nunique().eq(1).all()
    workers = sorted(d.worker_id.unique()); buildings = sorted(d.building_id.unique())
    wi = {w: j for j, w in enumerate(workers)}; bi = {b: j for j, b in enumerate(buildings)}
    m = len(workers)
    A = np.zeros((len(buildings), m, m)); b = np.zeros((len(buildings), m))
    n = np.zeros((len(buildings), m)); raw = np.zeros((len(buildings), m))
    for _, task in d.groupby('context_key', sort=False):
        ix = np.array([wi[w] for w in task.worker_id]); bj = bi[task.building_id.iloc[0]]
        y = task[axis].to_numpy(float); size = len(ix)
        # The task-level projection is I - 11'/size. No difficulty bins and no shrinkage.
        A[bj][np.ix_(ix, ix)] += np.eye(size) - np.ones((size, size)) / size
        b[bj, ix] += y - y.mean()
        n[bj, ix] += 1; raw[bj, ix] += y
    return dict(frame=d, workers=workers, buildings=buildings, A=A, b=b, n=n, raw=raw)


def solve_sufficient(s, weights=None):
    if weights is None: weights = np.ones(len(s['buildings']))
    A = np.einsum('i,ijk->jk', weights, s['A']); rhs = np.einsum('i,ij->j', weights, s['b'])
    m = len(s['workers'])
    presence = weights @ s['n']
    if m < 2 or (presence == 0).any():
        return None, dict(status='missing_workers', rank=None, min_positive_eigenvalue=None)
    eig = np.linalg.eigvalsh(A); positive = eig > max(eig.max(), 1.) * 1e-10
    rank = int(positive.sum())
    if rank != m - 1:
        return None, dict(status='disconnected_graph', rank=rank, min_positive_eigenvalue=None)
    # Solve the sum-zero constrained normal equation directly, independently of
    # the published eigenvector pseudoinverse implementation.
    K = np.zeros((m + 1, m + 1)); K[:m, :m] = A; K[m, :m] = 1; K[:m, m] = 1
    beta = np.linalg.solve(K, np.r_[rhs, 0.])[:m]
    beta[np.abs(beta) < 1e-12] = 0.
    return beta, dict(status='usable', rank=rank,
        min_positive_eigenvalue=float(eig[positive].min()), max_eigenvalue=float(eig.max()),
        normal_equation_max_abs=float(np.abs(A @ beta - rhs).max()),
        sum_effects=float(beta.sum()))


def fit_worker_effects(frame, axis, heldout=None):
    """Return (profiles, diagnostics); input needs context_key, worker_id, building_id, axis."""
    train = frame[frame.building_id.ne(heldout)].copy() if heldout is not None else frame.copy()
    s = make_sufficient(train, axis)
    beta, diag = solve_sufficient(s)
    rows = []
    for j, worker in enumerate(s['workers']):
        g = s['frame'][s['frame'].worker_id.eq(worker)]
        n, b = g.context_key.nunique(), g.building_id.nunique()
        supported = bool(beta is not None and n >= 6 and b >= 3)
        effect = beta[j] if beta is not None else np.nan
        rows.append(dict(worker_id=worker, effect=effect, supported=supported, fit_status=diag['status'],
            contexts=n, buildings=b, training_buildings=sorted(g.building_id.unique()), label=label(effect, supported),
            Q_margin_2=margin_label(effect, supported) if axis in ['B8L2', 'D10'] else 'not_applicable', axis=axis,
            fold=heldout if heldout is not None else 'full_descriptive'))
    diag.update(axis=axis, fold=heldout or 'full_descriptive', rows=len(s['frame']),
        workers=len(s['workers']), tasks=s['frame'].context_key.nunique(), buildings=len(s['buildings']))
    return pd.DataFrame(rows), diag


def relative_predictions(test, fit, axis, time_fit=None):
    """Published relative-target estimand, reconstructed independently."""
    p = fit[fit.supported & fit.label.ne('unclassified')].copy()
    p['class_effect'] = p.groupby('label').effect.transform('mean')
    cols = ['worker_id', 'effect', 'label', 'class_effect']
    if time_fit is not None:
        t = time_fit[time_fit.supported & time_fit.label.ne('unclassified')]
        p = p.merge(t[['worker_id', 'label']].rename(columns={'label': 'time_label'}), on='worker_id')
        p['QT_label'] = p.label + '|' + p.time_label
        p = p[p.groupby('QT_label').worker_id.transform('size').ge(2)].copy()
        p['QT_effect'] = p.groupby('QT_label').effect.transform('mean')
        cols += ['QT_effect', 'QT_label']
    d = test.merge(p[cols], on='worker_id', validate='many_to_one')
    d = d[d.groupby('context_key').worker_id.transform('size').ge(2)].copy()
    d['target'] = d[axis] - d.groupby('context_key')[axis].transform('mean')
    for method, col in [('continuous', 'effect'), ('class', 'class_effect')] + ([('QT', 'QT_effect')] if time_fit is not None else []):
        d[method + '_prediction'] = d[col] - d.groupby('context_key')[col].transform('mean')
        d[method + '_sqerr'] = (d.target - d[method + '_prediction']) ** 2
    d['baseline_sqerr'] = d.target ** 2
    return d


def baseline_worker_effects(train, axis):
    d = train.copy()
    d['difficulty_residual'] = d[axis] - d.groupby('difficulty_class')[axis].transform('mean')
    d['peer_residual'] = d[axis] - d.groupby('context_key')[axis].transform('mean')
    return d.groupby('worker_id').agg(raw_mean=(axis, 'mean'),
        difficulty_only=('difficulty_residual', 'mean'), peer_centered_mean=('peer_residual', 'mean'))


def add_baselines(pred, train, axis):
    means = baseline_worker_effects(train, axis)
    d = pred.merge(means, on='worker_id', validate='many_to_one')
    for method in means.columns:
        d[method + '_prediction'] = d[method] - d.groupby('context_key')[method].transform('mean')
        d[method + '_sqerr'] = (d.target - d[method + '_prediction']) ** 2
    return d


def summarize_predictions(predictions, grouping=('panel', 'axis', 'comparison')):
    summaries = []; buildings_out = []
    for key, d in predictions.groupby(list(grouping), dropna=False):
        meta = dict(zip(grouping, key if isinstance(key, tuple) else (key,)))
        methods = [c[:-6] for c in d if c.endswith('_sqerr') and c != 'baseline_sqerr' and d[c].notna().all()]
        cols = ['baseline_sqerr'] + [m + '_sqerr' for m in methods]
        by = d.groupby('building_id')[cols].mean()
        counts = d.groupby('building_id').size()
        rng = np.random.default_rng(SEED)
        boots = rng.integers(0, len(by), size=(BOOTSTRAPS, len(by)))
        baseline = by.baseline_sqerr.to_numpy(); base_draws = baseline[boots].mean(1)
        for method in methods:
            e = by[method + '_sqerr'].to_numpy()
            reductions = 1 - e[boots].mean(1) / base_draws
            jackknife = [1 - np.delete(e, j).mean() / np.delete(baseline, j).mean() for j in range(len(by))] if len(by) > 1 else [np.nan]
            summaries.append(dict(**meta, method=method, rows=len(d), workers=d.worker_id.nunique(),
                contexts=d.context_key.nunique(), buildings=len(by), baseline_building_mean_mse=baseline.mean(),
                method_building_mean_mse=e.mean(), building_equal_reduction=1-e.mean()/baseline.mean(),
                pooled_reduction=1-d[method + '_sqerr'].sum()/d.baseline_sqerr.sum(),
                improved_buildings=int((e < baseline).sum()), bootstrap_95_low=np.quantile(reductions, .025),
                bootstrap_95_high=np.quantile(reductions, .975), delete_building_reduction_min=np.nanmin(jackknife),
                delete_building_reduction_max=np.nanmax(jackknife)))
            for j, building in enumerate(by.index):
                buildings_out.append(dict(**meta, method=method, building_id=building, rows=int(counts[building]),
                    baseline_mse=baseline[j], method_mse=e[j], reduction=1-e[j]/baseline[j], mse_difference=e[j]-baseline[j]))
    return pd.DataFrame(summaries), pd.DataFrame(buildings_out)


def paired_model_comparisons(predictions):
    comparisons = [('continuous', 'raw_mean'), ('continuous', 'difficulty_only'), ('continuous', 'peer_centered_mean'),
        ('continuous', 'class'), ('QT', 'class'), ('QT_class', 'Q_class'), ('QT_class', 'T_class')]
    rows = []
    for key, d in predictions.groupby(['panel', 'axis', 'comparison']):
        meta = dict(zip(['panel', 'axis', 'comparison'], key))
        for a, b in comparisons:
            cols = [a + '_sqerr', b + '_sqerr', 'baseline_sqerr']
            if any(c not in d or not d[c].notna().all() for c in cols): continue
            by = d.groupby('building_id')[cols].mean()
            diff = by[b + '_sqerr'].to_numpy() - by[a + '_sqerr'].to_numpy()
            baseline = by.baseline_sqerr.to_numpy()
            ix = np.random.default_rng(SEED).integers(0, len(by), size=(BOOTSTRAPS, len(by)))
            draws = diff[ix].mean(1) / baseline[ix].mean(1)
            rows.append(dict(**meta, method_a=a, method_b=b, rows=len(d), buildings=len(by),
                a_better_buildings=int((diff > 0).sum()), a_advantage_baseline_scaled=diff.mean()/baseline.mean(),
                paired_bootstrap95_low=np.quantile(draws, .025), paired_bootstrap95_high=np.quantile(draws, .975),
                interpretation='Positive means method_a has lower building-equal MSE; shared building resamples and common rows.'))
    return pd.DataFrame(rows)


def task_network(frame, folds):
    pairs = []; diagnostics = []
    workers = sorted(frame.worker_id.unique())
    for fold in [None, *folds]:
        d = frame[frame.building_id.ne(fold)] if fold is not None else frame
        task_sets = {w: set(g.context_key) for w, g in d.groupby('worker_id')}
        shares = []
        for a, b in combinations(workers, 2):
            common = task_sets.get(a, set()) & task_sets.get(b, set()); shares.append(len(common))
            if fold is None:
                pairs.append(dict(worker_a=a, worker_b=b, shared_tasks=len(common),
                    shared_buildings=d[d.context_key.isin(common)].building_id.nunique()))
        _, dg = fit_worker_effects(frame, 'B8L2', fold)
        dg.update(all_worker_common_tasks=len(set.intersection(*task_sets.values())),
            pair_shared_min=min(shares), pair_shared_median=float(np.median(shares)),
            pair_shared_max=max(shares), pairs_with_no_direct_overlap=sum(n == 0 for n in shares),
            minimum_task_workers=int(d.groupby('context_key').worker_id.nunique().min()))
        diagnostics.append(dg)
    return pd.DataFrame(pairs), pd.DataFrame(diagnostics)


def absolute_tables(ledger, quality):
    rows = []
    pools = dict(ordinary_manual_all=ledger[ledger.quality_usable & ledger.condition.eq('manual') & ledger.quality_use.eq('ordinary_primary')],
        ordinary_manual_training=quality,
        ordinary_manual_original_holdout=ledger[ledger.quality_usable & ledger.condition.eq('manual') & ledger.quality_use.eq('ordinary_primary') & ledger.admission_original_holdout],
        doorway_manual=ledger[ledger.quality_usable & ledger.condition.eq('manual') & ledger.quality_use.eq('doorway_quality')],
        ordinary_semi=ledger[ledger.quality_usable & ledger.condition.eq('semi') & ledger.quality_use.eq('ordinary_primary')],
        special_conditional_semi=ledger[ledger.quality_usable & ledger.condition.eq('semi') & ledger.quality_use.eq('special_conditional_only')])
    for name, pool in pools.items():
        for worker, g in pool.groupby('worker_id'):
            for axis in ['B8L2', 'D10']:
                y = g[axis].dropna()
                rows.append(dict(worker_id=worker, pool=name, axis=axis, n=len(y), images=g.image_id.nunique(),
                    buildings=g.building_id.nunique(), mean=y.mean(), median=y.median(), p10=y.quantile(.1),
                    p25=y.quantile(.25), p75=y.quantile(.75), minimum=y.min(), maximum=y.max(), sd=y.std(),
                    status='descriptive_observed_task_mix_not_competence_ranking'))
    cover = ledger.groupby('worker_id').agg(n_submissions=('object_id', 'size'), all_images=('image_id', 'nunique'),
        all_buildings=('building_id', 'nunique'), n_quality_usable=('quality_usable', 'sum'), n_Q_train=('in_Q_training', 'sum'),
        n_OOS=('is_oos', 'sum'), n_doorway_flag=('is_doorway', 'sum'), source_time_available=('source_active_time_seconds', 'count'),
        target_time_available=('target_matched_time_seconds', 'count')).reset_index()
    cover['n_not_quality_usable'] = cover.n_submissions - cover.n_quality_usable
    statuses = ledger.groupby(['worker_id', 'primary_reason'], dropna=False).size().unstack(fill_value=0).add_prefix('reason__').reset_index()
    return pd.DataFrame(rows), cover.merge(statuses, on='worker_id', validate='one_to_one')


def bootstrap_profiles(quality, axis):
    s = make_sufficient(quality, axis); n_b = len(s['buildings'])
    weights = np.random.default_rng(SEED).multinomial(n_b, np.full(n_b, 1/n_b), size=BOOTSTRAPS)
    effects = []; means = []; audit = []
    for j, w in enumerate(weights):
        beta, diag = solve_sufficient(s, w)
        audit.append(dict(axis=axis, replicate=j, status=diag['status'], rank=diag['rank'],
            absent_workers=int(((w @ s['n']) == 0).sum())))
        if beta is not None:
            effects.append(beta); means.append((w @ s['raw']) / (w @ s['n']))
    effects = np.asarray(effects); means = np.asarray(means)
    rows = []
    for j, worker in enumerate(s['workers']):
        lo, hi = np.quantile(effects[:, j], [.025, .975]); rawlo, rawhi = np.quantile(means[:, j], [.025, .975])
        rows.append(dict(worker_id=worker, axis=axis, bootstrap_valid=len(effects), bootstrap_requested=BOOTSTRAPS,
            effect_ci95_low=lo, effect_ci95_high=hi, mean_ci95_low=rawlo, mean_ci95_high=rawhi,
            bootstrap_effect_positive_fraction=float((effects[:, j] > 0).mean()),
            effect_interval_excludes_zero=bool(lo > 0 or hi < 0),
            uncertainty_note='building_percentile_interval_conditional_on_observed_pool_and_cleaned_scores_not_multiple_comparison_adjusted'))
    return pd.DataFrame(rows), pd.DataFrame(audit)


def disjoint_halves(quality, axis):
    buildings = sorted(quality.building_id.unique()); workers = sorted(quality.worker_id.unique())
    rng = np.random.default_rng(20261014); rows = []
    for repeat in range(50):
        bs = rng.permutation(buildings); halves = [set(bs[:len(bs)//2]), set(bs[len(bs)//2:])]
        ps = [fit_worker_effects(quality[quality.building_id.isin(h)], axis)[0].set_index('worker_id') for h in halves]
        for worker in workers:
            labs = [p.loc[worker, 'label'] if worker in p.index else 'unclassified' for p in ps]
            comp = 'unclassified' not in labs
            rows.append(dict(axis=axis, repeat=repeat, worker_id=worker, label_a=labs[0], label_b=labs[1],
                comparable=comp, same_direction=(labs[0] == labs[1]) if comp else np.nan,
                half_a='|'.join(sorted(halves[0])), half_b='|'.join(sorted(halves[1]))))
    return pd.DataFrame(rows)


def time_class_validation(time_panel, folds, qfits, tfits):
    rows = []
    for qaxis in ['B8L2', 'D10']:
        for building in sorted(time_panel.building_id.unique()):
            t = tfits[tfits.fold.eq(building) & tfits.supported & tfits.label.ne('unclassified')].copy()
            q = qfits[qfits.axis.eq(qaxis) & qfits.fold.eq(building) & qfits.supported & qfits.label.ne('unclassified')]
            t = t.merge(q[['worker_id', 'label']].rename(columns={'label': 'Q_label'}), on='worker_id')
            t['QT_label'] = t.Q_label + '|' + t.label
            t = t[t.groupby('QT_label').worker_id.transform('size').ge(2)].copy()
            t['T_class_effect'] = t.groupby('label').effect.transform('mean')
            t['Q_class_effect'] = t.groupby('Q_label').effect.transform('mean')
            t['QT_class_effect'] = t.groupby('QT_label').effect.transform('mean')
            d = time_panel[time_panel.building_id.eq(building)].merge(t[['worker_id', 'effect', 'T_class_effect', 'Q_class_effect', 'QT_class_effect']], on='worker_id')
            d = d[d.groupby('context_key').worker_id.transform('size').ge(2)].copy()
            d['target'] = d.T_source - d.groupby('context_key').T_source.transform('mean')
            d['baseline_sqerr'] = d.target ** 2
            for method, col in [('T_continuous', 'effect'), ('T_class', 'T_class_effect'), ('Q_class', 'Q_class_effect'), ('QT_class', 'QT_class_effect')]:
                d[method + '_prediction'] = d[col] - d.groupby('context_key')[col].transform('mean')
                d[method + '_sqerr'] = (d.target - d[method + '_prediction']) ** 2
            d['panel'] = 'T_source_matched_QT'; d['axis'] = 'T_source'; d['comparison'] = qaxis + '_QT_on_time'
            rows.append(d)
    return pd.concat(rows, ignore_index=True)


def main(args):
    repo = Path(args.repo).resolve()
    source = Path(args.source).resolve() if args.source else repo / 'research/workers/worker_b8l2_d10_20261017'
    out = Path(args.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    required = ['quality_panel.csv', 'fold_profiles.csv', 'personnel_ledger.csv', 'predictions.csv', 'T_source_panel.csv', 'T_target_panel.csv']
    hashes = {fn: sha256(source / fn) for fn in required}
    q = pd.read_csv(source / 'quality_panel.csv'); old = pd.read_csv(source / 'fold_profiles.csv')
    ledger = pd.read_csv(source / 'personnel_ledger.csv'); oldpred = pd.read_csv(source / 'predictions.csv')
    times = {name: pd.read_csv(source / (name + '_panel.csv')) for name in ['T_source', 'T_target']}
    assert len(q) == 1048 and q.object_id.is_unique and q.context_key.nunique() == 87
    assert q.condition.eq('manual').all() and q.quality_usable.all() and ~q.is_oos.any() and ~q.is_doorway.any()
    assert not q.admission_original_holdout.any() and q.profile_allowed.all()
    assert set(ledger.loc[ledger.in_Q_training, 'object_id']) == set(q.object_id)
    rebuilt_context = q[['image_id', 'condition', 'reference_id', 'reference_version']].apply(lambda row: json.dumps(row.tolist()), axis=1)
    assert rebuilt_context.eq(q.context_key).all()
    assert not q.duplicated(['worker_id', 'context_key']).any()
    print('INPUT VERIFIED: 1048 ordinary Manual / 24 workers / 87 exact task contexts / 19 buildings.', flush=True)

    all_buildings = sorted(set(ledger.building_id) | set(old.fold) - {'full_descriptive'})
    fits = []; diagnostics = []; predictions = []
    for panel, data, axes in [('current', q, ['B8L2', 'D10']), *[(n, times[n], [n]) for n in times]]:
        for axis in axes:
            for b in [None, *all_buildings]:
                f, dg = fit_worker_effects(data, axis, b); f['panel'] = panel; fits.append(f)
                dg['panel'] = panel; diagnostics.append(dg)
                if b is None or b not in set(data.building_id): continue
                pred = relative_predictions(data[data.building_id.eq(b)], f, axis)
                if panel == 'current': pred = add_baselines(pred, data[data.building_id.ne(b)], axis)
                pred['panel'] = panel; pred['axis'] = axis; pred['comparison'] = 'Q_only'; predictions.append(pred)
    fits = pd.concat(fits, ignore_index=True)
    for axis in ['B8L2', 'D10']:
        for tn in times:
            for b in sorted(q.building_id.unique()):
                test = q[q.building_id.eq(b)]
                if tn == 'T_target': test = test[test.target_matched_time_seconds.notna()]
                f = fits[fits.panel.eq('current') & fits.axis.eq(axis) & fits.fold.eq(b)]
                tf = fits[fits.panel.eq(tn) & fits.axis.eq(tn) & fits.fold.eq(b)]
                pred = relative_predictions(test, f, axis, tf)
                pred = add_baselines(pred, q[q.building_id.ne(b)], axis)
                pred['panel'] = 'current'; pred['axis'] = axis; pred['comparison'] = 'QT_' + tn; predictions.append(pred)
    pred = pd.concat(predictions, ignore_index=True)
    keys = ['panel', 'axis', 'fold', 'worker_id']
    original_subset = old[old.panel.isin(['current', 'T_source', 'T_target'])]
    bridge = original_subset.merge(fits, on=keys, suffixes=('_published', '_recomputed'), validate='one_to_one')
    assert len(bridge) == len(original_subset)
    bridge['effect_delta'] = bridge.effect_recomputed - bridge.effect_published
    assert bridge.effect_delta.abs().max() < 1e-9
    assert bridge.supported_published.eq(bridge.supported_recomputed).all()
    assert bridge.label_published.eq(bridge.label_recomputed).all()
    assert bridge.contexts_published.eq(bridge.contexts_recomputed).all() and bridge.buildings_published.eq(bridge.buildings_recomputed).all()
    save_csv(out / 'profile_reproduction_bridge.csv', bridge[keys + ['effect_published', 'effect_recomputed', 'effect_delta', 'supported_published', 'supported_recomputed']])
    pk = ['object_id', 'panel', 'axis', 'comparison']
    original_pred = oldpred[oldpred.panel.isin(['current', 'T_source', 'T_target'])]
    cols = ['target', 'continuous_prediction', 'class_prediction', 'QT_prediction', 'baseline_sqerr', 'continuous_sqerr', 'class_sqerr', 'QT_sqerr']
    pb = original_pred.merge(pred[pk + cols], on=pk, suffixes=('_published', '_recomputed'), validate='one_to_one')
    assert len(pb) == len(original_pred)
    prediction_max_errors = {}
    for c in cols:
        a, b = pb[c + '_published'], pb[c + '_recomputed']
        assert a.isna().eq(b.isna()).all()
        delta = (a - b).abs().max(); prediction_max_errors[c] = float(delta)
        assert delta < 1e-7
    print('REPRODUCTION VERIFIED:', len(bridge), 'profile rows;', len(pb), 'prediction rows; maximum effect error', bridge.effect_delta.abs().max(), flush=True)
    save_csv(out / 'fold_profiles_recomputed.csv', fits)
    save_csv(out / 'fit_diagnostics.csv', diagnostics)

    # Reuse preserved original holdout only as a separately named diagnostic.
    held = ledger[ledger.quality_usable & ledger.condition.eq('manual') & ledger.quality_use.eq('ordinary_primary') & ledger.admission_original_holdout].copy()
    held['context_key'] = held[['image_id', 'condition', 'reference_id', 'reference_version']].apply(lambda row: json.dumps(row.tolist()), axis=1)
    heldpred = []
    for axis in ['B8L2', 'D10']:
        for b, test in held.groupby('building_id'):
            f = fits[fits.panel.eq('current') & fits.axis.eq(axis) & fits.fold.eq(b)]
            d = relative_predictions(test, f, axis)
            d = add_baselines(d, q[q.building_id.ne(b)], axis)
            d['panel'] = 'preserved_original_holdout'; d['axis'] = axis; d['comparison'] = 'Q_only'; heldpred.append(d)
    heldpred = pd.concat(heldpred, ignore_index=True)
    pred = pd.concat([pred, heldpred], ignore_index=True)
    timepred = time_class_validation(times['T_source'], all_buildings,
        fits[fits.panel.eq('current')], fits[fits.panel.eq('T_source')])
    pred = pd.concat([pred, timepred], ignore_index=True)
    keep = ['object_id', 'worker_id', 'image_id', 'building_id', 'context_key', 'panel', 'axis', 'comparison', 'target']
    keep += [c for c in pred if c.endswith('_prediction') or c.endswith('_sqerr')]
    save_csv(out / 'predictions_recomputed.csv', pred[keep])
    summ, by = summarize_predictions(pred); save_csv(out / 'validation_summary.csv', summ); save_csv(out / 'validation_by_building.csv', by)
    save_csv(out / 'paired_model_comparisons.csv', paired_model_comparisons(pred))
    exclusions = []
    for panel, frame, axes in [('current', q, ['B8L2', 'D10']), ('preserved_original_holdout', held, ['B8L2', 'D10']),
        *[(name, data, [name]) for name, data in times.items()]]:
        for axis in axes:
            evaluated = set(pred.loc[pred.panel.eq(panel) & pred.axis.eq(axis) & pred.comparison.eq('Q_only'), 'object_id'])
            for r in frame[~frame.object_id.isin(evaluated)].itertuples():
                pf = fits[fits.panel.eq('current' if panel == 'preserved_original_holdout' else panel) & fits.axis.eq(axis)
                    & fits.fold.eq(r.building_id) & fits.worker_id.eq(r.worker_id)]
                why = 'no_training_worker_effect' if pf.empty else 'insufficient_training_support' if not pf.supported.iloc[0] else 'fewer_than_two_evaluable_same_context_peers'
                exclusions.append(dict(panel=panel, axis=axis, object_id=r.object_id, worker_id=r.worker_id, image_id=r.image_id,
                    building_id=r.building_id, reason=why))
    save_csv(out / 'evaluation_exclusions.csv', exclusions)
    print('VALIDATION CALCULATED:', len(pred), 'rows across explicitly separated estimands/panels.', flush=True)

    absolute, coverage = absolute_tables(ledger, q); save_csv(out / 'absolute_quality_by_worker.csv', absolute); save_csv(out / 'worker_coverage.csv', coverage)
    comp = q.groupby(['worker_id', 'difficulty_class']).agg(n=('object_id', 'size'), images=('image_id', 'nunique'),
        buildings=('building_id', 'nunique'), B8L2_mean=('B8L2', 'mean'), D10_mean=('D10', 'mean')).reset_index()
    comp['worker_task_fraction'] = comp.n / comp.worker_id.map(q.worker_id.value_counts()); save_csv(out / 'worker_task_composition.csv', comp)
    pairs, graph = task_network(q, all_buildings); save_csv(out / 'worker_pair_overlap.csv', pairs); save_csv(out / 'network_by_fold.csv', graph)
    intervals = []; boot_audits = []; halves = []
    for axis in ['B8L2', 'D10']:
        ci, audit = bootstrap_profiles(q, axis); intervals.append(ci); boot_audits.append(audit)
        halves.append(disjoint_halves(q, axis))
    intervals = pd.concat(intervals, ignore_index=True); halves = pd.concat(halves, ignore_index=True)
    save_csv(out / 'worker_intervals.csv', intervals); save_csv(out / 'bootstrap_audit.csv', pd.concat(boot_audits, ignore_index=True)); save_csv(out / 'disjoint_halves_recomputed.csv', halves)
    full = fits[fits.fold.eq('full_descriptive') & fits.panel.eq('current')].merge(intervals, on=['worker_id', 'axis'], validate='one_to_one')
    original_folds = fits[fits.panel.eq('current') & fits.fold.isin(q.building_id.unique())]
    st = original_folds.groupby(['worker_id', 'axis']).agg(LOBO_folds=('fold', 'size'),
        LOBO_supported=('supported', 'sum'), LOBO_effect_min=('effect', 'min'), LOBO_effect_max=('effect', 'max'),
        LOBO_positive_folds=('effect', lambda x: int((x > 0).sum())),
        LOBO_above_margin_folds=('effect', lambda x: int((x > 2).sum())),
        LOBO_below_margin_folds=('effect', lambda x: int((x < -2).sum()))).reset_index()
    hs = halves.groupby(['worker_id', 'axis']).agg(half_comparable=('comparable', 'sum'), half_agreement=('same_direction', 'mean')).reset_index()
    full = full.merge(st, on=['worker_id', 'axis']).merge(hs, on=['worker_id', 'axis'])
    full['LOBO_same_sign_fraction'] = np.where(full.effect > 0, full.LOBO_positive_folds, full.LOBO_folds-full.LOBO_positive_folds) / full.LOBO_folds
    means = absolute[absolute.pool.eq('ordinary_manual_training')].drop(columns='pool')
    full = full.merge(means, on=['worker_id', 'axis'], suffixes=('', '_observed'))
    task_baselines = []
    common_task_intercepts = {}
    for axis in ['B8L2', 'D10']:
        ix = full.axis.eq(axis)
        full.loc[ix, 'raw_mean_rank'] = full.loc[ix, 'mean'].rank(ascending=False)
        full.loc[ix, 'Q_effect_rank'] = full.loc[ix, 'effect'].rank(ascending=False)
        full.loc[ix, 'raw_centered_effect'] = full.loc[ix, 'mean'] - full.loc[ix, 'mean'].mean()
        raw = baseline_worker_effects(q, axis)
        full.loc[ix, 'difficulty_only_effect'] = full.loc[ix, 'worker_id'].map(raw.difficulty_only)
        full.loc[ix, 'peer_centered_mean_effect'] = full.loc[ix, 'worker_id'].map(raw.peer_centered_mean)
        betas = full.loc[ix].set_index('worker_id').effect
        task_frame = q[['context_key', 'worker_id', 'building_id', 'image_id', axis]].copy()
        task_frame['worker_effect'] = task_frame.worker_id.map(betas)
        task_frame['after_worker'] = task_frame[axis] - task_frame.worker_effect
        alphas = task_frame.groupby('context_key').after_worker.mean()
        task_frame['task_intercept'] = task_frame.context_key.map(alphas)
        task_frame['fit_residual'] = task_frame[axis] - task_frame.task_intercept - task_frame.worker_effect
        mix = task_frame.groupby('worker_id').task_intercept.mean()
        residual_mean = task_frame.groupby('worker_id').fit_residual.mean()
        assert residual_mean.abs().max() < 1e-8
        common_alpha = float(alphas.mean())
        common_task_intercepts[axis] = common_alpha
        full.loc[ix, 'actual_task_intercept_mean'] = full.loc[ix, 'worker_id'].map(mix)
        full.loc[ix, 'common_task_intercept'] = common_alpha
        full.loc[ix, 'common_task_standardized_prediction'] = common_alpha + full.loc[ix, 'effect']
        full.loc[ix, 'task_mix_shift_vs_common'] = full.loc[ix, 'actual_task_intercept_mean'] - common_alpha
        full.loc[ix, 'decomposition_residual'] = full.loc[ix, 'mean'] - full.loc[ix, 'effect'] - full.loc[ix, 'actual_task_intercept_mean']
        task_summary = task_frame.groupby('context_key').agg(image_id=('image_id', 'first'), building_id=('building_id', 'first'),
            workers=('worker_id', 'nunique'), task_intercept=('task_intercept', 'first'), observed_score_mean=(axis, 'mean'),
            mean_worker_effect=('worker_effect', 'mean')).reset_index()
        task_summary['axis'] = axis; task_baselines.append(task_summary)
    save_csv(out / 'task_baselines.csv', pd.concat(task_baselines, ignore_index=True))
    full['rank_change_from_raw'] = full.raw_mean_rank - full.Q_effect_rank
    full['raw_sign'] = np.where(full.raw_centered_effect > 0, 'above_observed_worker_mean', 'below_observed_worker_mean')
    full['raw_relative_sign_disagree'] = (full.raw_centered_effect > 0) != (full.effect > 0)
    t = fits[fits.panel.eq('T_source') & fits.fold.eq('full_descriptive')][['worker_id', 'effect', 'supported', 'contexts', 'buildings']].rename(columns={
        'effect': 'T_effect', 'supported': 'T_supported', 'contexts': 'T_contexts', 'buildings': 'T_buildings'})
    full = full.merge(t, on='worker_id', how='left')
    full['T_label'] = np.where(full.T_supported.eq(True), np.where(full.T_effect < 0, 'faster', 'slower'), 'unclassified')
    full['QT_label'] = np.where(full.T_label.eq('unclassified'), full.label + '|time_unknown', full.label + '|' + full.T_label)
    full['T_exp_effect'] = np.exp(full.T_effect)
    tlobo = fits[fits.panel.eq('T_source') & fits.fold.isin(times['T_source'].building_id.unique())].groupby('worker_id').agg(
        T_LOBO_folds=('fold', 'size'), T_LOBO_supported=('supported', 'sum'), T_LOBO_effect_min=('effect', 'min'),
        T_LOBO_effect_max=('effect', 'max'), T_LOBO_faster_folds=('effect', lambda x: int((x < 0).sum()))).reset_index()
    full = full.merge(tlobo, on='worker_id', how='left')
    save_csv(out / 'worker_profiles_enriched.csv', full)
    time_rows = []
    for tn, tpanel in times.items():
        seconds = 'source_active_time_seconds' if tn == 'T_source' else 'target_matched_time_seconds'
        for worker, g in tpanel.groupby('worker_id'):
            time_rows.append(dict(panel=tn, worker_id=worker, n=len(g), images=g.image_id.nunique(), buildings=g.building_id.nunique(),
                mean_seconds=g[seconds].mean(), median_seconds=g[seconds].median(), p10_seconds=g[seconds].quantile(.1),
                p90_seconds=g[seconds].quantile(.9), total_seconds=g[seconds].sum(),
                source_definition='active_time_only_log1p_model;source_task_duration_is_not_target_matched_duration'))
    save_csv(out / 'time_by_worker.csv', time_rows)
    low = q[q.B8L2 <= q.groupby('worker_id').B8L2.transform(lambda x: x.quantile(.1))].copy()
    save_csv(out / 'worker_low_tail_records.csv', low[['object_id', 'worker_id', 'image_id', 'image_code', 'building_id',
        'reference_id', 'reference_version', 'B8L2', 'D10', 'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter', 'difficulty_class']])

    old_halves = source / 'disjoint_halves.csv'
    half_reproduction = None
    if old_halves.exists():
        oh = pd.read_csv(old_halves); hk = ['axis', 'repeat', 'worker_id']
        hb = oh.merge(halves, on=hk, suffixes=('_published', '_recomputed'), validate='one_to_one')
        assert len(hb) == len(halves)
        assert hb.comparable_published.eq(hb.comparable_recomputed).all()
        assert hb.label_a_published.eq(hb.label_a_recomputed).all() and hb.label_b_published.eq(hb.label_b_recomputed).all()
        half_reproduction = dict(rows=len(hb), exact_label_match=True)
    assert {fn: sha256(source / fn) for fn in required} == hashes
    git_head = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True, capture_output=True)
    receipt = dict(data_release=DATA_RELEASE, repository_head=git_head.stdout.strip() if git_head.returncode == 0 else None,
        metric_versions=dict(B8L2=q.B8L2_version.unique().tolist(), D10=q.D10_version.unique().tolist()),
        input_version=q.input_version.unique().tolist(), snapshot_version=q.snapshot_version.unique().tolist(),
        source_directory=str(source), source_sha256=hashes, formula_or_eligibility_changed=False,
        independent_estimator='sum-zero KKT solve of exact task-intercept projected least squares; no shrinkage',
        full_Q_rows=len(q), workers=q.worker_id.nunique(), tasks=q.context_key.nunique(), buildings=q.building_id.nunique(),
        original_profile_rows_checked=len(bridge), max_abs_effect_reproduction_error=bridge.effect_delta.abs().max(),
        original_prediction_rows_checked=len(pb), prediction_max_abs_errors=prediction_max_errors,
        fold_graph_usable=graph.fit_status.eq('usable').all() if 'fit_status' in graph else graph.status.eq('usable').all(),
        original_holdout_available=len(held), original_holdout_images=held.image_id.nunique(), original_holdout_buildings=held.building_id.nunique(),
        original_holdout_evaluated_per_metric=heldpred.groupby('axis').size().to_dict(),
        bootstrap_requested=BOOTSTRAPS, bootstrap_seed=SEED, original_half_reproduction=half_reproduction,
        common_task_intercepts=common_task_intercepts,
        limitations=['Original holdout previously visible to project; this is preservation and diagnostic replay, not a new blind validation.',
            'Relative MSE evaluates within-task deviations; no absolute score for an unseen task is predicted.',
            'The common-task standardized prediction equals one constant plus Q effect; it is not independent evidence or observed absolute output.',
            'Bootstrap intervals condition on this finite worker pool and current reference/cleaning definitions; no simultaneous inference correction.',
            'Scores missing/excluded are not zeros and reliability evidence is handled separately.'])
    save_json(out / 'RUN_RECEIPT.json', receipt)
    print(json.dumps(normalize(receipt), ensure_ascii=False, indent=2), flush=True)
    print(summ[(summ.panel == 'current') & (summ.comparison == 'Q_only')][['axis', 'method', 'rows', 'buildings', 'building_equal_reduction', 'bootstrap_95_low', 'bootstrap_95_high']].to_string(index=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default=str(DEFAULT_REPO), help='Repository root; alternatively set PANORAMA_REPO.')
    parser.add_argument('--source', default=None, help='Optional explicit published personnel input directory.')
    parser.add_argument('--out', default=str(SCRIPT_DIR), help='Output directory (default: beside this script).')
    main(parser.parse_args())
