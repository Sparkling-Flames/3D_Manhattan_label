"""Exploratory annotator simulation from frozen model proposals and human records.

No model inference, target annotation conditioning, or production annotation writes.
Run from the repository root with python -m tools.thesis_main.analysis.simulate_annotators.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
REVIEWED = ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz'
METHODS = ('hohonet', 'uniform', 'pooled', 'worker')
FAMILIES = ('HoHoNet', 'Bi-enclosed', 'Bi-extended')


def read_jsonl(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def write_csv(path, rows):
    if not rows:
        return
    with open(path, 'w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def seed_for(seed, *parts):
    text = '|'.join(map(str, (seed,) + parts))
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], 'big')


def parsed(points):
    """Basic parseability only, with original endpoint and pair order retained."""
    p = np.asarray(points, dtype=float)
    return (p.ndim == 2 and p.shape[1] == 2 and len(p) >= 6 and len(p) % 2 == 0
            and np.isfinite(p).all() and (p >= 0).all()
            and (p[:, 0] <= 1024).all() and (p[:, 1] <= 512).all())


def rays(points):
    p = np.asarray(points, dtype=float)
    u = (p[:, 0] / 1024 - .5) * (2 * np.pi)
    v = (.5 - p[:, 1] / 512) * np.pi
    return np.stack((np.cos(v) * np.sin(u), np.sin(v), -np.cos(v) * np.cos(u)), axis=-1)


def distance(a, b):
    """Symmetric spherical nearest-keypoint angle in degrees, on unordered sets.

    Exploratory point-set metric, not the repository's q, mask IoU, or correctness.
    Human export order does not assert ceiling/floor roles.
    """
    ar, br = rays(a), rays(b)
    angles = np.degrees(np.arccos(np.clip(ar @ br.T, -1, 1)))
    return float(.5 * (angles.min(axis=0).mean() + angles.min(axis=1).mean()))


def align_pairs(reference, points):
    """Match explicitly paired endpoints for residual calculation only.

    Same consecutive-pair x tolerance as the repository's raw-order pairing.
    Endpoint roles use y within each unambiguous pair. Hungarian assignment maps
    donor pairs onto model pairs without sorting x or rewriting source records.
    """
    r = np.asarray(reference, float).reshape(-1, 2, 2)
    p = np.asarray(points, float).reshape(-1, 2, 2)
    if r.shape != p.shape:
        raise ValueError('Pair counts must match for residual transfer')
    dx = np.abs((p[:, 0, 0] - p[:, 1, 0] + 512) % 1024 - 512)
    if (dx >= 51.2).any() or (np.abs(p[:, 0, 1] - p[:, 1, 1]) < 1).any():
        raise ValueError('Consecutive source pairing is not unambiguous')
    p = np.array([q if q[0, 1] < q[1, 1] else q[::-1] for q in p])
    rr, pr = rays(r.reshape(-1, 2)).reshape(-1, 2, 3), rays(p.reshape(-1, 2)).reshape(-1, 2, 3)
    cost = np.arccos(np.clip(np.einsum('ikd,jkd->ijk', rr, pr), -1, 1)).mean(axis=-1)
    row_indices, col_indices = linear_sum_assignment(cost)
    aligned = np.empty_like(p)
    aligned[row_indices] = p[col_indices]
    return aligned.reshape(-1, 2)


def residual(reference, points):
    delta = align_pairs(reference, points) - np.asarray(reference)
    delta[:, 0] = (delta[:, 0] + 512) % 1024 - 512
    return delta


def geometry_status(points):
    """Engineering diagnostics only; does not certify Manhattan or scope correctness."""
    if not parsed(points):
        return 'unparseable_or_out_of_bounds'
    p = np.asarray(points)
    issues = []
    if (p[::2, 1] >= 256).any() or (p[1::2, 1] <= 256).any():
        return 'wrong_hemisphere'
    bottom = rays(p[1::2])
    if (np.abs(bottom[:, 1]) < np.sin(np.radians(.5))).any():
        return 'near_horizon'
    floor = -bottom[:, (0, 2)] / bottom[:, 1, None]
    poly = Polygon(floor)
    if not poly.is_valid or poly.area < 1e-8:
        issues.append('invalid_floor_polygon')
    dx = (p[::2, 0] - p[1::2, 0] + 512) % 1024 - 512
    if (np.abs(dx) > 2).any():
        issues.append('vertical_pair_mismatch_gt_2px')
    return '|'.join(issues) or 'basic_checks_passed_not_certified'


def load_inputs():
    """Reuse the confirmed point view and current exploration worker exclusions."""
    exclusions = Counter()
    human = []
    for row in read_jsonl(REVIEWED):
        if row['assistance_exposure'] != 'none':
            exclusions['assisted_response'] += 1
        elif str(row['worker_id']) in {'19', '26'}:
            exclusions['worker_19_or_26'] += 1
        elif not row['unassisted_manual_included']:
            exclusions['not_in_reviewed_calculation'] += 1
        elif not parsed(row['effective_points_1024x512']):
            exclusions['basic_parse_failure'] += 1
        else:
            human.append(dict(image_id=row['image_id'], building_id=row['building_id'],
                              worker_id=str(row['worker_id']), annotation_id=row['canonical_annotation_id'],
                              points=row['effective_points_1024x512'], processing_status=row['processing_status']))
    identities = [(h['image_id'], h['worker_id']) for h in human]
    if len(identities) != len(set(identities)):
        raise ValueError('Repeated image-worker records require an explicit version decision')
    models = defaultdict(dict)
    for row in read_jsonl(INPUT / 'models/layouts.jsonl'):
        if row['source_role'] not in {'offline_ep300_replay', 'offline_dual_prediction'}:
            continue
        name = 'HoHoNet' if row['model_family'] == 'HoHoNet' else 'Bi-' + row['head']
        if not parsed(row['points_1024x512']):
            exclusions['model_basic_parse_failure'] += 1
            continue
        if name in models[row['image_id']]:
            raise ValueError('Duplicate model source')
        models[row['image_id']][name] = dict(name=name, layout_id=row['layout_id'],
                                          points=row['points_1024x512'])
    with open(INPUT / 'images.csv', encoding='utf-8', newline='') as stream:
        images = {r['image_id']: r for r in csv.DictReader(stream)}
    return human, dict(models), images, dict(exclusions)


def fit(training, models, shrinkage=8.):
    """Learn probabilistic model-family affinity and empirical residual donors.

    Affinities are descriptive proximity, not verified semantic intent. Ties share
    credit, so identical model heads cannot acquire artificial labels from argmin.
    """
    counts = defaultdict(lambda: np.zeros(3))
    global_counts = np.ones(3)  # Symmetric smoothing for empty/rare families.
    donors = []
    used = []
    for row in training:
        bank = models.get(row['image_id'], {})
        if not all(k in bank for k in FAMILIES):
            continue
        costs = np.array([distance(row['points'], bank[k]['points']) for k in FAMILIES])
        # Fixed 5-degree count penalty, never selected using held-out outcomes.
        costs += np.array([5 * abs(len(row['points']) - len(bank[k]['points'])) /
                           max(len(row['points']), len(bank[k]['points'])) for k in FAMILIES])
        ties = np.flatnonzero(np.isclose(costs, costs.min(), atol=1e-7, rtol=0))
        weights = np.zeros(3)
        weights[ties] = 1 / len(ties)
        counts[row['worker_id']] += weights
        global_counts += weights
        used.append(row['annotation_id'])
        for i in ties:
            base = bank[FAMILIES[i]]['points']
            if len(base) == len(row['points']):
                try:
                    delta = residual(base, row['points']).tolist()
                except ValueError:
                    continue  # Retained for family preference and evaluation, not invented as a donor.
                donors.append(dict(worker_id=row['worker_id'], family=FAMILIES[i],
                                   image_id=row['image_id'], building_id=row['building_id'],
                                   annotation_id=row['annotation_id'], weight=1 / len(ties),
                                   delta=delta, point_count=len(base)))
    pooled = global_counts / global_counts.sum()
    profiles = {worker: ((n + shrinkage * pooled) / (n.sum() + shrinkage)).tolist()
                for worker, n in counts.items()}
    return dict(pooled=pooled.tolist(), profiles=profiles, donors=donors,
                profile_counts={w: int(round(n.sum())) for w, n in counts.items()},
                training_annotation_ids=sorted(used),
                training_buildings=sorted({r['building_id'] for r in training}), shrinkage=shrinkage)


def fit_holdout(human, models, held_out_building):
    training = [h for h in human if h['building_id'] != held_out_building]
    learned = fit(training, models)
    assert held_out_building not in learned['training_buildings']
    assert all(d['building_id'] != held_out_building for d in learned['donors'])
    return learned


def conservative_delta(base, donor_delta, max_jitter_px):
    delta = np.asarray(donor_delta, dtype=float).reshape(-1, 2, 2)
    delta = np.clip(delta, -max_jitter_px, max_jitter_px)
    delta[:, :, 0] = delta[:, :, 0].mean(axis=1, keepdims=True)
    candidate = np.asarray(base, dtype=float).reshape(-1, 2, 2) + delta
    candidate[:, :, 0] %= 1024
    candidate[:, :, 1] = np.clip(candidate[:, :, 1], 0, 511.999)
    if np.any(candidate[:, 0, 1] >= candidate[:, 1, 1]):
        return np.asarray(base, dtype=float), False
    if geometry_status(candidate.reshape(-1, 2)) != 'basic_checks_passed_not_certified':
        return np.asarray(base, dtype=float), False
    return candidate.reshape(-1, 2), True


def simulate(bank, learned, worker_ids, method, seed, image_id, *, conservative=False,
             max_jitter_px=8., worker_profile_map=None):
    """Target input is a frozen model bank only; no target human labels accepted."""
    rng = np.random.default_rng(seed)
    rows = []
    for index, worker in enumerate(worker_ids):
        profile_worker = (worker_profile_map or {}).get(worker, worker)
        if conservative:
            family = 'HoHoNet'
        elif method == 'hohonet':
            family = 'HoHoNet'
        else:
            probabilities = ([1 / 3] * 3 if method == 'uniform' else
                             learned['profiles'].get(profile_worker, learned['pooled']) if method == 'worker'
                             else learned['pooled'])
            family = FAMILIES[int(rng.choice(3, p=probabilities))]
        base = np.asarray(bank[family]['points'], float)
        candidate = base.copy()
        donor = None
        source = 'no_residual'
        if conservative or method in {'worker', 'pooled'}:
            eligible = [d for d in learned['donors'] if d['family'] == family and d['point_count'] == len(base)]
            personal = [d for d in eligible if d['worker_id'] == profile_worker]
            if method == 'worker' and len(personal) >= 3:
                eligible, source = personal, 'personal_empirical_residual'
            elif eligible:
                source = 'pooled_empirical_residual'
            if eligible:
                weights = np.array([d['weight'] for d in eligible])
                donor = eligible[int(rng.choice(len(eligible), p=weights / weights.sum()))]
                if conservative:
                    candidate, accepted = conservative_delta(base, donor['delta'], max_jitter_px)
                    source = source + ('_clipped' if accepted else '_rejected')
                else:
                    candidate += np.asarray(donor['delta'])
                    candidate[:, 0] %= 1024
        rows.append(dict(simulation_id=f'{image_id}:{method}:{seed}:{index:03}', image_id=image_id,
                         method=method, synthetic=True, name=f'S{index + 1:03} / {method}',
                         simulated_worker_id=worker, source_worker_profile_id=profile_worker, model_family=family,
                         model_layout_id=bank[family]['layout_id'], points=candidate.tolist(),
                         geometry_status=geometry_status(candidate), residual_source=source,
                         conservative_mode=conservative, max_jitter_px=max_jitter_px if conservative else None,
                         residual_donor_annotation_id=donor['annotation_id'] if donor else None,
                         residual_donor_image_id=donor['image_id'] if donor else None,
                         residual_donor_building_id=donor['building_id'] if donor else None,
                         scope_status='not_simulated', review_required=True))
    return rows


def make_simulated_roster(profile_ids, count, seed):
    if not profile_ids:
        raise ValueError('At least one learned worker profile is required')
    rng = np.random.default_rng(seed)
    worker_ids = [f'sim_{index + 1:03}' for index in range(count)]
    source_ids = [str(profile_ids[int(rng.integers(0, len(profile_ids)))]) for _ in worker_ids]
    return worker_ids, dict(zip(worker_ids, source_ids))


def comparison(human_points, generated):
    """Invalid outputs remain in denominators and receive maximum angular loss."""
    hp = human_points
    gp = [r['points'] for r in generated]
    valid = [parsed(g) for g in gp]
    cross = np.array([[distance(h, g) if ok else 180. for g, ok in zip(gp, valid)] for h in hp])
    pair_h = [distance(a, b) for i, a in enumerate(hp) for b in hp[i + 1:]]
    pair_g = [distance(a, b) if valid[i] and valid[j] else 180.
              for i, a in enumerate(gp) for j, b in enumerate(gp) if j > i]
    hc, gc = Counter(len(h) // 2 for h in hp), Counter(len(g) // 2 if ok else -1 for g, ok in zip(gp, valid))
    tv = .5 * sum(abs(hc[k] / len(hp) - gc[k] / len(gp)) for k in hc.keys() | gc.keys())
    return dict(human_count=len(hp), synthetic_count=len(gp), corner_count_tv=float(tv),
                human_to_sim_nearest_deg=float(cross.min(axis=1).mean()),
                sim_to_human_nearest_deg=float(cross.min(axis=0).mean()),
                symmetric_coverage_deg=float(.5 * (cross.min(axis=1).mean() + cross.min(axis=0).mean())),
                human_diversity_deg=float(np.mean(pair_h)), synthetic_diversity_deg=float(np.mean(pair_g)),
                diversity_absolute_error_deg=float(abs(np.mean(pair_h) - np.mean(pair_g))),
                basic_parse_failure_rate=1 - sum(valid) / len(valid),
                geometry_issue_rate=sum(r['geometry_status'] != 'basic_checks_passed_not_certified' for r in generated) / len(generated))


def ls_task(image_id, image, samples):
    predictions, omitted = [], []
    for sample in samples:
        if not parsed(sample['points']):
            omitted.append(sample['simulation_id'])
            continue
        result = [dict(id=f'p{i:03}', from_name='kp', to_name='img', type='keypointlabels',
                       original_width=1024, original_height=512, image_rotation=0,
                       value=dict(x=x / 1024 * 100, y=y / 512 * 100, width=.3, keypointlabels=['Corner']))
                  for i, (x, y) in enumerate(sample['points'])]
        predictions.append(dict(model_version='experimental_simulator/' + sample['simulation_id'], result=result))
    return dict(data=dict(image=image['image_url'], title='实验模拟 ' + image_id, image_id=image_id,
                          synthetic=True, review_required=True, scope_status='not_simulated',
                          omitted_unparseable_simulations=omitted), predictions=predictions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20260915)
    parser.add_argument('--replicates', type=int, default=3)
    parser.add_argument('--min-human', type=int, default=16)
    parser.add_argument('--conservative', action='store_true', help='Use HoHoNet point count and capped paired jitter')
    parser.add_argument('--max-jitter-px', type=float, default=8.)
    parser.add_argument('--synthetic-workers', type=int, default=50)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Output exists; use a new directory to retain audit history')
    if args.replicates < 1 or args.min_human < 2 or args.max_jitter_px <= 0 or args.synthetic_workers < 1:
        raise SystemExit('replicates >= 1, min-human >= 2, max-jitter-px > 0, synthetic-workers >= 1 are required')
    args.output.mkdir(parents=True)
    human, models, images, exclusions = load_inputs()
    grouped = defaultdict(list)
    for h in human:
        grouped[h['image_id']].append(h)
    complete = {iid for iid, bank in models.items() if all(k in bank for k in FAMILIES)}
    targets = sorted(iid for iid, rows in grouped.items() if len(rows) >= args.min_human and iid in complete)
    buildings = sorted({images[i]['building_id'] for i in targets})
    roster = sorted({h['worker_id'] for h in human}, key=int)
    if not targets:
        raise SystemExit('No evaluation images satisfy the input criteria')
    methods = ('worker_conservative',) if args.conservative else METHODS
    metrics, samples, folds, cases = [], [], [], []
    sample_images = []
    for building in buildings:
        # Entire target building is excluded before fitting or drawing residuals.
        training = [h for h in human if h['building_id'] != building]
        learned = fit_holdout(human, models, building)
        fold_roster, fold_profile_map = make_simulated_roster(
            sorted(learned['profiles']), args.synthetic_workers, seed_for(args.seed, 'profiles', building))
        assert building not in learned['training_buildings']
        fold = dict(held_out_building=building, training_buildings=learned['training_buildings'],
                    training_annotation_ids=learned['training_annotation_ids'],
                    evaluation_image_ids=[i for i in targets if images[i]['building_id'] == building],
                    pooled_probabilities=learned['pooled'], worker_probabilities=learned['profiles'],
                    worker_training_counts=learned['profile_counts'], residual_donor_count=len(learned['donors']))
        folds.append(fold)
        print(f'Holdout {building}: {len(training)} training responses, {len(fold["evaluation_image_ids"])} targets', flush=True)
        sample_images.append(fold['evaluation_image_ids'][0])
        for iid in fold['evaluation_image_ids']:
            photo = next(iter((ROOT / 'data/mp3d_layout').glob(f'*/img/{iid}.png')), None)
            case = dict(image_id=iid, building_id=building, image_path=str(photo) if photo else '',
                        models=list(models[iid].values()),
                        human=[dict(name='真实 W' + h['worker_id'], points=h['points']) for h in grouped[iid]], synthetic=[])
            for rep in range(args.replicates):
                for method in methods:
                    base_method = 'worker' if method == 'worker_conservative' else method
                    generated = simulate(models[iid], learned, fold_roster, base_method,
                                         seed_for(args.seed, iid, method, rep), iid,
                                         conservative=args.conservative, max_jitter_px=args.max_jitter_px,
                                         worker_profile_map=fold_profile_map)
                    assert all(s['residual_donor_building_id'] != building for s in generated)
                    for s in generated:
                        s.update(held_out_building=building, replicate=rep, partition='building_holdout')
                    samples.extend(generated)
                    metrics.append(dict(image_id=iid, building_id=building, method=method, replicate=rep,
                                        **comparison([h['points'] for h in grouped[iid]], generated)))
                    if rep == 0:
                        case['synthetic'].extend(generated)
            cases.append(case)
    # Frozen full-history simulator for images with no human responses in this snapshot.
    full = fit(human, models)
    candidate_roster, candidate_profile_map = make_simulated_roster(
        sorted(full['profiles']), args.synthetic_workers, seed_for(args.seed, 'candidate_profiles'))
    candidates = sorted(i for i in complete if images[i]['population_role'] != 'historical_annotated')
    future, tasks = [], []
    for iid in candidates:
        generated = simulate(models[iid], full, candidate_roster, 'worker', seed_for(args.seed, 'candidate', iid), iid,
                             conservative=args.conservative, max_jitter_px=args.max_jitter_px,
                             worker_profile_map=candidate_profile_map)
        for s in generated:
            s.update(partition='unlabelled_candidate', replicate=0)
        future.extend(generated)
        tasks.append(ls_task(iid, images[iid], generated))
    write_jsonl(args.output / 'holdout_simulations.jsonl', samples)
    write_jsonl(args.output / 'candidate_simulations.jsonl', future)
    dump(args.output / 'candidate_label_studio_predictions.json', tasks)
    write_csv(args.output / 'evaluation.csv', metrics)
    # Report image means and equal-building means; Monte Carlo replicas are not new people.
    keys = [k for k in metrics[0] if k.endswith(('_deg', '_tv', '_rate'))]
    summary = {}
    building_metrics = []
    for method in methods:
        method_rows = [r for r in metrics if r['method'] == method]
        bvalues = []
        for building in buildings:
            rows = [r for r in method_rows if r['building_id'] == building]
            b = dict(building_id=building, method=method, image_count=len({r['image_id'] for r in rows}),
                     **{k: float(np.mean([r[k] for r in rows])) for k in keys})
            building_metrics.append(b)
            bvalues.append(b)
        summary[method] = dict(image_weighted={k: float(np.mean([r[k] for r in method_rows])) for k in keys},
                               building_weighted={k: float(np.mean([r[k] for r in bvalues])) for k in keys})
    write_csv(args.output / 'building_evaluation.csv', building_metrics)
    dump(args.output / 'folds.json', folds)
    # Full model contains no credentials; historical identities retained for donor audit.
    dump(args.output / 'fitted_simulator.json', full)
    dump(args.output / 'review_cases.json', {'cases': cases, 'default_examples': sample_images})
    input_paths = [REVIEWED, INPUT / 'models/layouts.jsonl', INPUT / 'images.csv', INPUT / 'models/MODEL_PROVENANCE.json']
    audit = dict(schema='empirical_annotator_simulation_v1', seed=args.seed, replicates=args.replicates,
                 min_human=args.min_human, human_records=len(human), human_images=len(grouped),
                 historical_worker_profiles=len(roster), evaluation_images=len(targets), evaluation_buildings=len(buildings),
                 evaluation_samples=len(samples), candidate_images=len(candidates), candidate_samples=len(future),
                 excluded=exclusions, metric_summary=summary, sample_count_per_method=args.synthetic_workers,
                 synthetic_worker_count=args.synthetic_workers,
                 methods=list(methods), conservative_mode=args.conservative, max_jitter_px=args.max_jitter_px,
                 fit_shrinkage=8, candidate_count_penalty_degrees=5, worker_residual_min_donors=3,
                 model_training_overlap='not_independently_verified', new_visual_inference=False,
                 scope_simulation=False, human_intent_classification=False,
                 input_sha256={str(p.relative_to(ROOT)): digest(p) for p in input_paths},
                 validation_scope='familiar-worker cross-building retrospective simulation; fixed offline model bank',
                 source_code_sha256=digest(Path(__file__)))
    dump(args.output / 'summary.json', audit)
    print(json.dumps({k: v for k, v in audit.items() if k not in {'metric_summary', 'input_sha256'}}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
