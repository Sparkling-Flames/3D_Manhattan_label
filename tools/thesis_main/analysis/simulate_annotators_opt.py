"""Optimised annotator simulator: calibration experiments on top of v1.

Keeps tools/thesis_main/analysis/simulate_annotators.py untouched and reuses its
fit/evaluation. Changes tested here (each switchable):

  no_x_collapse  keep independent top/bottom endpoint x residuals (v1 averages x)
  cap            per-endpoint |dx| cap (v1 fixed 8px; donors show p95 20-50px)
  scale          global jitter scale multiplier for calibration
  count          sample the target pair count from the template worker's
                 empirical distribution and pick/trim the model base to match

All outputs are local-only experiments; nothing is written to tracked inputs.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import numpy as np

from tools.thesis_main.analysis import simulate_annotators as s1

FAMILIES = s1.FAMILIES


def normalize_worker_id(value):
    value = str(value).strip()
    if value[:1].upper() == 'W':
        value = value[1:]
    return str(int(value)) if value.isdigit() else value


def fit_holdout(human, models, building):
    """Fit using training buildings; counts include all eligible manual answers."""
    training = [dict(h, worker_id=normalize_worker_id(h['worker_id']))
                for h in human if h['building_id'] != building]
    learned = s1.fit(training, models)
    learned['worker_pair_counts'] = {}
    for h in training:
        learned['worker_pair_counts'].setdefault(h['worker_id'], []).append(len(h['points']) // 2)
    learned['pooled_pair_counts'] = [len(h['points']) // 2 for h in training]
    assert building not in learned['training_buildings']
    return learned


def _donors_by(learned):
    by = collections.defaultdict(list)
    for d in learned['donors']:
        by[(d['worker_id'], d['family'], d['point_count'])].append(d)
    return by


def worker_counts(human, worker_id):
    counts = [len(h['points']) // 2 for h in human if h['worker_id'] == worker_id]
    return counts


def apply_residual(base, donor, cap, scale, rng):
    """Apply one donor residual with per-endpoint x and y preserved."""
    delta = np.asarray(donor['delta'], dtype=float).reshape(-1, 2, 2) * scale
    delta = np.clip(delta, -cap, cap)
    candidate = np.asarray(base, dtype=float).reshape(-1, 2, 2) + delta
    candidate[:, :, 0] %= 1024
    candidate[:, :, 1] = np.clip(candidate[:, :, 1], 0, 511.999)
    if np.any(candidate[:, 0, 1] >= candidate[:, 1, 1]):
        return None
    flat = candidate.reshape(-1, 2)
    if s1.geometry_status(flat) != 'basic_checks_passed_not_certified':
        return None
    return flat


def trim_pairs(base, target_pairs, rng):
    """Delete random pairs until target count; base stays valid."""
    p = np.asarray(base, float).reshape(-1, 2, 2)
    if target_pairs < 3 or p.shape[0] <= target_pairs:
        return None
    for _ in range(12):
        keep = np.sort(rng.choice(p.shape[0], size=target_pairs, replace=False))
        candidate = p[keep].reshape(-1, 2)
        if s1.geometry_status(candidate) == 'basic_checks_passed_not_certified':
            return candidate
    return None


def simulate_v2(bank, learned, worker_ids, method, seed, image_id, *,
                no_x_collapse=False, cap=8.0, scale=1.0, count_mode=False,
                worker_profile_map=None, tries=1, fixed_family=None):
    """Target input is a frozen model bank only; no target human labels accepted."""
    donors_by = _donors_by(learned)
    rows = []
    for index, worker in enumerate(worker_ids):
        # Separate random streams keep corresponding draws paired across ablations.
        family_rng = np.random.default_rng(s1.seed_for(seed, worker, 'family'))
        count_rng = np.random.default_rng(s1.seed_for(seed, worker, 'count'))
        rng = np.random.default_rng(s1.seed_for(seed, worker, 'residual'))
        profile_worker = normalize_worker_id((worker_profile_map or {}).get(worker, worker))
        profile_found = profile_worker in learned['profiles']
        if fixed_family is not None:
            family = fixed_family
        elif method == 'hohonet':
            family = 'HoHoNet'
        else:
            probabilities = ([1 / 3] * 3 if method == 'uniform' else
                             learned['profiles'].get(profile_worker, learned['pooled']) if method == 'worker'
                             else learned['pooled'])
            family = FAMILIES[int(family_rng.choice(3, p=probabilities))]
        if family not in bank:
            raise ValueError(f'Missing model family: {family}')
        base_family = family
        if count_mode:
            counts = worker_counts_bankless(bank, learned, profile_worker)
            target = int(count_rng.choice(counts)) if counts else len(bank[family]['points']) // 2
            # Prefer an exact count, then the closest larger model that can be trimmed.
            chosen = None
            fams = [family] + [f for f in FAMILIES if f != family]
            for f in fams:
                if f not in bank:
                    continue
                n = len(bank[f]['points']) // 2
                if n == target:
                    chosen = (f, target)
                    break
            if chosen is None:
                best = None
                for f in fams:
                    if f in bank:
                        n = len(bank[f]['points']) // 2
                        if n >= target and (best is None or n < best[1]):
                            best = (f, n)
                chosen = best
            if chosen is None:
                chosen = max(((f, len(bank[f]['points']) // 2) for f in fams if f in bank), key=lambda x: x[1])
            family, base_pairs = chosen
            base = np.asarray(bank[family]['points'], float)
            trimmed = trim_pairs(base, target, count_rng)
            if trimmed is not None:
                base = trimmed
            count_status = ('sampled' if len(base) // 2 == target else
                            'unsupported_addition' if base_pairs < target else 'trim_geometry_rejected')
        else:
            base = np.asarray(bank[family]['points'], float)
            target = len(base) // 2
            count_status = 'base_count'
        eligible = [d for d in learned['donors'] if d['family'] == family and d['point_count'] == len(base)]
        personal = [d for d in donors_by.get((profile_worker, family, len(base)), [])
                    if d['worker_id'] == profile_worker]
        if method == 'worker' and len(personal) >= 3:
            pool, source = personal, 'personal_empirical_residual'
        else:
            pool, source = eligible, 'pooled_empirical_residual'
        candidate = None
        donor = None
        applied = False
        attempts = 0
        if pool:
            weights = np.array([d['weight'] for d in pool])
            weights = weights / weights.sum()
            for _ in range(tries):
                attempts += 1
                d = pool[int(rng.choice(len(pool), p=weights))]
                if no_x_collapse:
                    cand = apply_residual(base, d, cap, scale, rng)
                else:
                    cand = apply_residual_xmean(base, d, cap, scale)
                if cand is not None:
                    candidate, donor, applied = cand, d, True
                    break
        if not applied:
            candidate = base.copy()
            source += '_rejected'
        fallback = ('profile_missing' if not profile_found else
                    'insufficient_personal_donors' if len(personal) < 3 else None)
        rows.append(dict(simulation_id=f'{image_id}:{method}:{seed}:{index:03}', image_id=image_id,
                         method=method, synthetic=True, name=f'S{index + 1:03} / {method}',
                         simulated_worker_id=worker, source_worker_profile_id=profile_worker, model_family=family,
                         profile_found=profile_found, profile_fallback_reason=fallback,
                         personal_donor_count=len(personal), residual_applied=applied,
                         residual_attempts=attempts,
                         residual_fallback_reason=None if applied else ('no_matching_donors' if not pool else 'geometry_rejected'),
                         model_copy=bool(np.array_equal(candidate, np.asarray(bank[family]['points']))),
                         model_layout_id=bank[family]['layout_id'], points=candidate.tolist(),
                         geometry_status=s1.geometry_status(candidate), residual_source=source,
                         conservative_mode=False, max_jitter_px=cap, jitter_scale=scale,
                         count_mode=count_mode, count_status=count_status, target_pairs=target,
                         residual_donor_annotation_id=donor['annotation_id'] if donor else None,
                         residual_donor_image_id=donor['image_id'] if donor else None,
                         residual_donor_building_id=donor['building_id'] if donor else None,
                         scope_status='not_simulated', review_required=True))
    return rows


def worker_counts_bankless(bank, learned, profile_worker):
    counts = list(learned.get('worker_pair_counts', {}).get(normalize_worker_id(profile_worker), []))
    if len(counts) < 3:
        counts = list(learned.get('pooled_pair_counts', []))
    if not counts:
        counts = [len(bank[f]['points']) // 2 for f in FAMILIES if f in bank]
    return counts


def apply_residual_xmean(base, donor, cap, scale):
    """v1-style application (x averaged across endpoints) for ablation."""
    delta = np.asarray(donor['delta'], dtype=float).reshape(-1, 2, 2) * scale
    delta = np.clip(delta, -cap, cap)
    delta[:, :, 0] = delta[:, :, 0].mean(axis=1, keepdims=True)
    candidate = np.asarray(base, dtype=float).reshape(-1, 2, 2) + delta
    candidate[:, :, 0] %= 1024
    candidate[:, :, 1] = np.clip(candidate[:, :, 1], 0, 511.999)
    if np.any(candidate[:, 0, 1] >= candidate[:, 1, 1]):
        return None
    flat = candidate.reshape(-1, 2)
    if s1.geometry_status(flat) != 'basic_checks_passed_not_certified':
        return None
    return flat


def diagnostics(rows):
    return dict(
        residual_acceptance_rate=float(np.mean([r.get('residual_applied', False) for r in rows])),
        model_copy_rate=float(np.mean([r.get('model_copy', False) for r in rows])),
        profile_missing_rate=float(np.mean([not r.get('profile_found', True) for r in rows])),
        count_mismatch_rate=float(np.mean([len(r['points']) // 2 != r.get('target_pairs', len(r['points']) // 2) for r in rows])),
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--seed', type=int, default=20260915)
    ap.add_argument('--replicates', type=int, default=3)
    ap.add_argument('--min-human', type=int, default=16)
    ap.add_argument('--synthetic-workers', type=int, default=50)
    ap.add_argument('--variant', default='all')
    ap.add_argument('--cap', type=float, default=24.0)
    ap.add_argument('--scale', type=float, default=1.5)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit('Output exists; use a new directory')
    if args.replicates < 1 or args.synthetic_workers < 2 or args.min_human < 2 or args.cap <= 0 or args.scale <= 0:
        raise SystemExit('Require positive cap/scale, replicates >= 1, workers/min-human >= 2')
    common = dict(no_x_collapse=False, cap=8., scale=1., count_mode=False, tries=1)
    variants = {
        'legacy_baseline': None,
        'hohonet_control': dict(common, method='worker', fixed_family='HoHoNet'),
        'family_mixture': dict(common, method='worker'),
        'independent_endpoints': dict(common, method='worker', no_x_collapse=True),
        'cap24': dict(common, method='worker', no_x_collapse=True, cap=args.cap),
        'scaled': dict(common, method='worker', no_x_collapse=True, cap=args.cap, scale=args.scale),
        'count': dict(common, method='worker', no_x_collapse=True, cap=args.cap, scale=args.scale, count_mode=True),
        'count_paired': dict(common, method='worker', count_mode=True),
    }
    if args.variant != 'all':
        if args.variant not in variants:
            raise SystemExit('Unknown variant: ' + args.variant)
        variants = {args.variant: variants[args.variant]}
    human, models, images, exclusions = s1.load_inputs()
    grouped = collections.defaultdict(list)
    for h in human:
        grouped[h['image_id']].append(h)
    complete = {iid for iid, bank in models.items() if all(k in bank for k in FAMILIES)}
    targets = sorted(iid for iid, rows in grouped.items() if len(rows) >= args.min_human and iid in complete)
    buildings = sorted({images[i]['building_id'] for i in targets})
    if not targets:
        raise SystemExit('No evaluation targets')
    args.output.mkdir(parents=True)
    metrics, folds = [], []
    # Cache unchanged human/human and cross-set distances within each image.
    # Comparison remains the original v1 metric, including its failure denominator.
    with open(args.output / 'holdout_simulations.jsonl', 'w', encoding='utf-8') as output:
        for building in buildings:
            learned = fit_holdout(human, models, building)
            roster, profile_map = s1.make_simulated_roster(
                sorted(learned['profiles']), args.synthetic_workers, s1.seed_for(args.seed, 'profiles', building))
            folds.append(dict(held_out_building=building, training_buildings=learned['training_buildings'],
                              training_annotation_ids=learned['training_annotation_ids']))
            print('Holdout', building, flush=True)
            for iid in [i for i in targets if images[i]['building_id'] == building]:
                for rep in range(args.replicates):
                    for variant, kw in variants.items():
                        seed = s1.seed_for(args.seed, iid, 'paired_ablation', rep)
                        if kw is None:
                            generated = s1.simulate(models[iid], learned, roster, 'worker',
                                s1.seed_for(args.seed, iid, 'worker_conservative', rep), iid,
                                conservative=True, worker_profile_map=profile_map)
                            for r in generated:
                                r['residual_applied'] = r['residual_donor_annotation_id'] is not None and r['residual_source'].endswith('_clipped')
                                r['model_copy'] = bool(np.array_equal(r['points'], models[iid][r['model_family']]['points']))
                        else:
                            options = dict(kw)
                            method = options.pop('method')
                            generated = simulate_v2(models[iid], learned, roster, method, seed, iid,
                                                    worker_profile_map=profile_map, **options)
                        for r in generated:
                            assert r['residual_donor_building_id'] != building
                            r.update(held_out_building=building, replicate=rep, variant=variant,
                                     partition='building_holdout',
                                     simulation_id=f"{r['simulation_id']}:{variant}")
                            output.write(json.dumps(r, allow_nan=False) + '\n')
                        metrics.append(dict(image_id=iid, building_id=building, variant=variant, replicate=rep,
                            **s1.comparison([h['points'] for h in grouped[iid]], generated), **diagnostics(generated)))
    s1.write_csv(args.output / 'evaluation.csv', metrics)
    keys = [k for k in metrics[0] if k.endswith(('_deg', '_tv', '_rate'))]
    summary, building_metrics = {}, []
    for variant in variants:
        rows = [r for r in metrics if r['variant'] == variant]
        bvals = []
        for building in buildings:
            br = [r for r in rows if r['building_id'] == building]
            b = dict(building_id=building, variant=variant, image_count=len({r['image_id'] for r in br}),
                     **{k: float(np.mean([r[k] for r in br])) for k in keys})
            bvals.append(b)
            building_metrics.append(b)
        summary[variant] = dict(image_weighted={k: float(np.mean([r[k] for r in rows])) for k in keys},
                               building_weighted={k: float(np.mean([r[k] for r in bvals])) for k in keys})
    s1.write_csv(args.output / 'building_evaluation.csv', building_metrics)
    s1.dump(args.output / 'folds.json', folds)
    paths = [s1.REVIEWED, s1.INPUT / 'models/layouts.jsonl', s1.INPUT / 'images.csv']
    s1.dump(args.output / 'summary.json', dict(schema='empirical_annotator_simulation_opt_v2',
        seed=args.seed, replicates=args.replicates, min_human=args.min_human,
        synthetic_workers=args.synthetic_workers, evaluation_images=len(targets),
        evaluation_buildings=len(buildings), variants=variants, metric_summary=summary, excluded=exclusions,
        input_sha256={str(p.relative_to(s1.ROOT)): s1.digest(p) for p in paths},
        source_code_sha256=s1.digest(Path(__file__)),
        protocol='legacy_baseline reproduces v1; remaining variants share per-worker random streams and one residual attempt'))
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
