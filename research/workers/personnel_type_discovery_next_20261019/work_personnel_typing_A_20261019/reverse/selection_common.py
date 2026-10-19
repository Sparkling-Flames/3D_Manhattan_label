"""Shared, frozen training-side selection utilities for personnel typing Part A.

No test-building outcome is accepted by fit_calibrator; callers supply a train frame.
The grouping/weighting target is image means followed by building means. Multiple
backgrounds and repeated k requests are not independent training observations.
"""
from __future__ import annotations
import hashlib
import math
from typing import Iterable
import numpy as np
import pandas as pd

SEED = 20261019
PRIOR_BUILDINGS = 2.0


def inner_building_groups(buildings: Iterable[str], seed: int = SEED, n_groups: int = 3):
    """Deterministic hash ordering, then round robin; independent of outcomes."""
    ordered = sorted(set(map(str, buildings)), key=lambda b: (hashlib.sha256(f'{seed}|{b}'.encode()).hexdigest(), b))
    return {b: i % n_groups for i, b in enumerate(ordered)}


def attach_relation(events: pd.DataFrame, labels: dict, domain: str = 'global') -> pd.Series:
    """labels may map worker -> class, or (difficulty, worker) -> class."""
    if domain == 'global':
        a = events.worker_a.map(labels)
        b = events.worker_b.map(labels)
    else:
        a = pd.Series([labels.get((str(d), str(w))) for d, w in zip(events.difficulty, events.worker_a)], index=events.index)
        b = pd.Series([labels.get((str(d), str(w))) for d, w in zip(events.difficulty, events.worker_b)], index=events.index)
    known = a.notna() & b.notna() & a.ne('unknown') & b.ne('unknown')
    out = pd.Series('unknown', index=events.index, dtype='object')
    out.loc[known & a.eq(b)] = 'within'
    out.loc[known & a.ne(b)] = 'between'
    return out


def _building_means(frame: pd.DataFrame, keys: list[str], outcome: str):
    # A pool may share image_id; main layer is one frozen task per image. Pool_id
    # remains in delivered data, but image is the support unit, not request count.
    f = frame.copy()
    f[outcome] = pd.to_numeric(f[outcome], errors='coerce')
    f = f[f[outcome].notna()]
    image = f.groupby(keys + ['building', 'image_id'], dropna=False)[outcome].mean().reset_index()
    return image.groupby(keys + ['building'], dropna=False)[outcome].mean().reset_index()


def fit_calibrator(train: pd.DataFrame, relation: pd.Series, outcome: str = 'stable_main'):
    """Within/between probability, conditional on k and frozen difficulty.

    Cell rates are building-equal. Relation-specific rates shrink by two equivalent
    training buildings to the cell baseline. Unknown personnel receive baseline.
    Baseline fallback is same k, then global. No individual test outcomes are read.
    """
    f = train.copy()
    f['relation'] = relation.reindex(f.index).fillna('unknown')
    f['k'] = f['k'].astype(int)
    f['difficulty'] = f['difficulty'].astype(str)
    base = _building_means(f, ['k', 'difficulty'], outcome)
    base_k = _building_means(f, ['k'], outcome)
    base_all = _building_means(f, [], outcome)
    p_global = float(base_all[outcome].mean()) if len(base_all) else 0.5
    cells = {(int(k), str(d)): float(g[outcome].mean()) for (k, d), g in base.groupby(['k', 'difficulty'])}
    k_rate = {int(k): float(g[outcome].mean()) for k, g in base_k.groupby('k')}
    rel = _building_means(f[f.relation != 'unknown'], ['k', 'difficulty', 'relation'], outcome)
    rates, supports = {}, {}
    for (k, d, r), g in rel.groupby(['k', 'difficulty', 'relation']):
        key = (int(k), str(d), str(r))
        prior = cells.get(key[:2], k_rate.get(int(k), p_global))
        n = len(g)
        rates[key] = float((g[outcome].sum() + PRIOR_BUILDINGS * prior) / (n + PRIOR_BUILDINGS))
        supports[key] = int(n)
    return {'global': p_global, 'k': k_rate, 'cells': cells, 'rates': rates, 'support': supports}


def predict_calibrator(calibrator: dict, frame: pd.DataFrame, relation: pd.Series):
    return np.array([calibrator['rates'].get((int(k), str(d), str(r)), calibrator['cells'].get((int(k), str(d)), calibrator['k'].get(int(k), calibrator['global']))) for k, d, r in zip(frame.k, frame.difficulty, relation)], dtype=float)


def building_brier(frame: pd.DataFrame, predicted, outcome: str = 'stable_main'):
    f = frame[['building', 'image_id', outcome]].copy()
    f[outcome] = pd.to_numeric(f[outcome], errors='coerce')
    f['brier'] = (np.asarray(predicted) - f[outcome].to_numpy(dtype=float)) ** 2
    f = f[f[outcome].notna()]
    return _building_means(f, [], 'brier')[['building', 'brier']]


def one_se_choice(building_scores: pd.DataFrame, complexity: pd.DataFrame):
    """Choose simplest within one SE of best mean; all candidates use same buildings.

    complexity columns: method_id, complexity_order (numeric), tie_order (numeric).
    The SE uses held-out training buildings, not number of background requests.
    """
    s = building_scores.groupby('method_id').brier.agg(['mean', 'std', 'count']).reset_index()
    s['se'] = s['std'].fillna(0) / np.sqrt(s['count'].clip(lower=1))
    s = s.merge(complexity, on='method_id', validate='one_to_one')
    best = s.sort_values(['mean', 'complexity_order', 'tie_order', 'method_id']).iloc[0]
    threshold = float(best['mean'] + best['se'])
    s['within_one_se'] = s['mean'] <= threshold + 1e-15
    chosen = s[s.within_one_se].sort_values(['complexity_order', 'tie_order', 'mean', 'method_id']).iloc[0]
    s['selected'] = s.method_id.eq(chosen.method_id)
    s['best_mean'] = float(best['mean'])
    s['one_se_threshold'] = threshold
    return str(chosen.method_id), s
