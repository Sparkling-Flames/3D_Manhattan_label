"""Deterministic v6 budgets and empirical, geometry-checked Manual edits."""
from __future__ import annotations

import csv
import numpy as np

from . import simulate_annotators as base
from .simulate_annotators_opt import apply_residual, trim_pairs

VERSION = 'difficulty_wild_35_v1'
VALID = 'basic_checks_passed_not_certified'
WILD_BUDGET = {'简单': (0, 2), '中等': (5, 7), '困难': (8, 20),
               '单列': (8, 20), '待修正GT': (8, 20), '待复核': (8, 20)}
ERROR_TYPES = ('partial_corner', 'missing_corner', 'scope_restricted')


def load_difficulty(path):
    with open(path, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    result = {}
    for row in rows:
        iid = row['image_id']
        if not iid or iid in result or row['difficulty_class'] not in WILD_BUDGET:
            raise ValueError('invalid_or_duplicate_difficulty:' + iid)
        if not row['difficulty_version'].endswith('_v6'):
            raise ValueError('difficulty_version_not_v6')
        for key in ('gt_error_excluded', 'reference_full_available', 'difficulty_analysis_eligible'):
            if row[key] not in ('True', 'False'):
                raise ValueError('invalid_boolean:' + key)
            row[key] = row[key] == 'True'
        result[iid] = row
    return result


def wild_count(difficulty, seed, need=None):
    if difficulty not in WILD_BUDGET:
        raise ValueError('unknown_difficulty:' + str(difficulty))
    rng = np.random.default_rng(seed)
    lo, hi = WILD_BUDGET[difficulty]
    n = int(rng.choice(3, p=[.5, .35, .15])) if difficulty == '简单' else int(rng.integers(lo, hi + 1))
    if need is not None:
        if need < 0:
            raise ValueError('negative_need')
        n = min(n, need)
    return n


def manual_counts(records):
    counts = {}
    for row in records:
        if row['condition'].lower() == 'manual':
            counts.setdefault(row['image_id'], set()).add(str(row['worker_id']))
    return {iid: len(workers) for iid, workers in counts.items()}


def continuous_subset(points, rng, target_pairs=None):
    pairs = np.asarray(points, float).reshape(-1, 2, 2)
    n = len(pairs)
    if n <= 3:
        raise ValueError('scope_restricted_requires_four_pairs')
    m = int(rng.integers(3, n)) if target_pairs is None else int(target_pairs)
    if not 3 <= m < n:
        raise ValueError('invalid_continuous_subset_size')
    for start in rng.permutation(n):
        keep = [(int(start) + j) % n for j in range(m)]
        candidate = pairs[keep].reshape(-1, 2)
        if base.geometry_status(candidate) == VALID:
            return candidate, keep
    raise ValueError('no_valid_continuous_subset')


def calibrate(donors):
    if not donors:
        raise ValueError('no_lower_training_donors')
    delta = np.concatenate([np.asarray(d['delta']).reshape(-1, 2, 2) for d in donors])
    deletions = [min(2, -d['count_offset']) for d in donors if d['count_offset'] < 0]
    amplitudes = [float(np.sqrt(np.mean(np.asarray(d['delta'],float)**2))) for d in donors]
    amplitudes = [a for a in amplitudes if a > 0]
    if not amplitudes:
        raise ValueError('no_nonzero_training_residual')
    return dict(cap=np.quantile(np.abs(delta), .95, axis=0).tolist(),
                quantile=.95, scale=1., deletion_counts=deletions,
                amplitude_iqr=np.quantile(amplitudes,[.25,.75]).tolist(),
                missing_frequency=len(deletions) / len(donors),
                source_annotation_ids=sorted({d['annotation_id'] for d in donors}),
                source_buildings=sorted({d['building_id'] for d in donors}))


def wild_edit(points, model, rng, severity, requested_types=None):
    """Use observed residual vectors; never repair failure by returning the model.

    severity carries a training donor's delta and the fold's empirical calibration.
    Returned pair indices refer to the input ring, including wraparound subsets.
    """
    original = np.asarray(points, float).reshape(-1, 2, 2)
    n = len(original)
    delta = np.asarray(severity['delta'], float).reshape(-1, 2, 2)
    if not len(delta) or not np.isfinite(delta).all():
        raise ValueError('invalid_empirical_delta')
    allowed = ['partial_corner']
    if n > 3 and severity.get('deletion_counts'):
        allowed.append('missing_corner')
    if n > 3:
        allowed.append('scope_restricted')
    if requested_types is not None:
        requested = list(requested_types)
        if not requested or any(t not in allowed for t in requested):
            raise ValueError('unsupported_requested_edit')
    else:
        weights = np.array([max(.05, severity.get('missing_frequency', .5)) if t == 'missing_corner' else 1. for t in allowed])
        count = int(rng.integers(1, len(allowed) + 1))
        requested = list(rng.choice(allowed, count, replace=False, p=weights / weights.sum()))
    failures = []
    for attempt in range(48):
        # Retry the requested combination first; later retain a genuine partial edit.
        types = requested if attempt < 24 else ['partial_corner']
        keep = list(range(n)); candidate = original.reshape(-1, 2).copy(); applied = []
        try:
            if 'scope_restricted' in types:
                size = int(rng.integers(4, n)) if 'missing_corner' in types and n > 4 else None
                candidate, keep = continuous_subset(candidate, rng, size)
                applied.append('scope_restricted')
            if 'missing_corner' in types and len(keep) > 3:
                remove = min(int(rng.choice(severity['deletion_counts'])), len(keep) - 3)
                if 'scope_restricted' in applied:
                    # Delete only at an interval boundary, preserving continuity.
                    keep = keep[remove:] if rng.integers(2) else keep[:-remove]
                    candidate = original[keep].reshape(-1, 2)
                else:
                    trimmed = trim_pairs(candidate, len(keep) - remove, rng)
                    if trimmed is None:
                        raise ValueError('missing_corner_geometry')
                    keep = [j for j in keep if any(np.array_equal(original[j], p) for p in trimmed.reshape(-1, 2, 2))]
                    candidate = trimmed
                applied.append('missing_corner')
            if 'partial_corner' in types:
                residual = np.zeros((len(keep), 2, 2))
                indices = rng.choice(len(keep), max(1, len(keep) // 2), replace=False)
                residual[indices] = delta[rng.integers(len(delta), size=len(indices))]
                residual[:, :, 0] = residual[:, :, 0].mean(axis=1, keepdims=True)
                scale = severity.get('scale', 1.) * .5 ** (attempt // 8)
                edited = apply_residual(candidate, {'delta': residual.tolist()},
                                        np.asarray(severity['cap']), scale, rng)
                if edited is None:
                    raise ValueError('partial_corner_geometry')
                candidate = edited; applied.append('partial_corner')
            if not applied or base.geometry_status(candidate) != VALID:
                raise ValueError('invalid_or_empty_edit')
            if np.array_equal(candidate, model) or np.array_equal(candidate, points):
                raise ValueError('unchanged_edit')
            return candidate, dict(wild_error_types=applied, requested_error_types=requested,
                                  kept_pair_indices=keep, edit_attempts=attempt + 1,
                                  edit_failures=failures, residual_scale=scale if 'partial_corner' in applied else None)
        except ValueError as exc:
            failures.append(str(exc))
    raise ValueError('wild_edit_exhausted:' + ','.join(sorted(set(failures))))
