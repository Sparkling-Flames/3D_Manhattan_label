"""Read-only checks of a received Pro report; write only local_audit_20260915.

--tables uses delivered individual rows, never reruns predictive fitting.
--geometry rebuilds boundaries from the current canonical response package.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
BUNDLE = ROOT / 'analysis_results/image_portrait_20260914_v1'
V2 = BUNDLE / 'cloud/pro_exploration/v2_convergence_e086b2b9'
OUT = V2 / 'local_audit_20260915'


def save(name, result):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8', newline='\n')


def interval(d, col):
    z = d[['building', col]].dropna().groupby('building')[col].agg(['sum', 'count']).to_numpy()
    rng = np.random.default_rng(20260914)
    sampled = z[rng.integers(len(z), size=(1000, len(z)))].sum(1)
    return float(d[col].mean()), np.quantile(sampled[:, 0] / sampled[:, 1], [.025, .975])


def tables():
    read = lambda p: pd.read_csv(V2 / p)
    r = read('foundation/human/response_metrics.csv.gz')
    r = r[r.main_worker_included]
    assert len(r) == 2388 and r.worker_id.nunique() == 24
    assert not r.duplicated(['image_id', 'raw_condition', 'worker_id']).any()
    counts = r.groupby('raw_condition').agg(responses=('worker_id', 'size'), images=('image_id', 'nunique'))
    assert counts.loc['manual'].tolist() == [1634, 187]
    assert counts.loc['semi'].tolist() == [538, 43]
    structure = read('process/image_uncertainty_structure.csv')
    structure = structure[structure.cut == .1]
    summary = {}
    for arm, expected in [('manual', [58, 38, 34]), ('semi', [16, 11, 15])]:
        s = structure[structure.condition == arm]
        got = [int((s.n_supported_modes >= 2).sum()), int(s.same_topology_multimodality.sum()), int((s.supported_minority_modes > 0).sum())]
        assert got == expected
        summary[arm] = dict(images=len(s), supported_multiple=got[0], same_point_multiple=got[1], supported_minority=got[2])
    checks = []
    # Reaggregate three sets of headline intervals from per-image rows.
    for path, column, summary_path, keys in [
        ('process/quality_and_marginal_change.csv', 'reference_delta', 'process/quality_change_summary.csv', ['condition']),
        ('combinations/fixed_future_paired_image_contrasts.csv', 'delta', 'combinations/fixed_future_paired_summary.csv', ['condition', 'information', 'metric']),
    ]:
        detail, reported = read(path), read(summary_path)
        for key, d in detail.groupby(keys):
            key = key if isinstance(key, tuple) else (key,)
            target = reported
            for k, value in zip(keys, key):
                target = target[target[k] == value]
            assert len(target) == 1
            if d[column].notna().sum() == 0:
                continue
            mean, ci = interval(d, column)
            row = target.iloc[0]
            np.testing.assert_allclose([mean, *ci], [row.delta, row.lo, row.hi], atol=1e-10, rtol=1e-8)
            checks.append(dict(table=summary_path, key=list(key), paired_mean=mean, interval=ci.tolist()))
    pred = read('prefix/predictions.csv.gz')
    np.testing.assert_allclose(abs(pred.prediction - pred.truth), pred.absolute_error, atol=2e-11)
    im = pred.groupby(['image_id', 'building', 'condition', 'prefix_k', 'feature', 'target']).absolute_error.mean().reset_index()
    reported = read('prefix/paired_increments.csv')
    row = reported[(reported.condition == 'manual') & (reported.prefix_k == 3) & (reported.target == 'prefix_future_mass_TV') & (reported.feature == 'prefix_only') & (reported.baseline == 'cold_portrait')].iloc[0]
    selected = im[(im.condition == 'manual') & (im.prefix_k == 3) & (im.target == 'prefix_future_mass_TV')]
    paired = selected[selected.feature == 'prefix_only'].merge(selected[selected.feature == 'cold_portrait'], on=['image_id', 'building'], suffixes=('', '_base'))
    paired['delta'] = paired.absolute_error - paired.absolute_error_base
    mean, ci = interval(paired, 'delta')
    np.testing.assert_allclose([mean, *ci], [row.delta, row.lo, row.hi], atol=1e-10, rtol=1e-8)
    checks.append(dict(table='prefix/paired_increments.csv', target='manual k3 prefix_future_mass_TV', n=len(paired), method_MAE=float(paired.absolute_error.mean()), baseline_MAE=float(paired.absolute_error_base.mean()), paired_mean=mean, interval=ci.tolist()))
    scene = read('strict_cold/prediction/cold/scene.csv.gz')
    scene = scene[(scene.condition == 'manual') & (scene.target == 'stable_G10')]
    paired = scene[scene.algorithm == 'ridge'].merge(scene[scene.algorithm == 'constant'], on=['image_id', 'building'], suffixes=('', '_base'), validate='one_to_one')
    paired['delta'] = paired.absolute_error - paired.absolute_error_base
    mean, ci = interval(paired, 'delta')
    reported = read('strict_cold/paired_increments.csv')
    row = reported[(reported.condition == 'manual') & (reported.target == 'stable_G10') & (reported.feature == 'scene') & (reported.baseline == 'constant')].iloc[0]
    np.testing.assert_allclose([mean, *ci], [row.delta, row.lo, row.hi], atol=1e-10, rtol=1e-8)
    save('scene_increment_reaggregation.json', dict(images=len(paired), buildings=int(paired.building.nunique()), scene_MAE=float(paired.absolute_error.mean()), constant_MAE=float(paired.absolute_error_base.mean()), delta=mean, interval=ci.tolist()))
    checks.append(dict(table='strict_cold/paired_increments.csv', target='manual stable_G10 scene ridge vs constant', n=len(paired), paired_mean=mean, interval=ci.tolist()))
    w = read('sensitivity/window_frequency_image_results.csv')
    w = w[(w.cut == .1) & (w.tolerance == .1) & (w.n >= 10)]
    windows = {arm: dict(images=len(g), **g[['tail3_frequency_pass', 'last_half_frequency_pass', 'disjoint_halves_frequency_pass']].mean().to_dict()) for arm, g in w.groupby('condition')}
    state = read('process/replay_states.csv.gz')
    state = state[(state.cut == .1) & (state.rule == 'G10_geometry')]
    onset = state[(state.state == 'current_changes') & state.onset.notna()]
    onset.to_csv(OUT / 'onset_present_but_tail_state_changes.csv', index=False)
    pools = read('combinations/class_pool_process_transitions.csv')
    both = pools[pools.both_classes_unified80]
    assert len(pools) == 396 and len(both) == 22 and (both.unified_fraction >= .8).all()
    queue = read('review/local_review_final.csv')
    assert len(queue) == 112 and queue.image_id.nunique() == 62
    pseen = 1 - math.comb(22, 8) / math.comb(24, 8)
    psupported = math.comb(22, 6) / math.comb(24, 8)
    result = dict(status='passed', scope='Table reaggregation and intervals, not full model refitting', counts=counts.to_dict('index'), structure=summary, checked_intervals=checks, windows=windows, mode_2_of_24_at_k8=dict(seen=pseen, supported=psupported), onset_inconsistent_window=dict(rows=len(onset), image_condition_units=len(onset[['image_id', 'condition']].drop_duplicates()), all_current_changes_rows=int((state.state == 'current_changes').sum()), meaning='Different windows: nonempty retrospective suffix onset is not certification under the tail G10 state'), class_unions=dict(total=len(pools), both_unified80=len(both), both_unified_to_multiple80=int((both.multiple_fraction >= .8).sum())), visual_queue=dict(questions=len(queue), images=int(queue.image_id.nunique())))
    save('table_checks.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'checked_intervals'}, ensure_ascii=False))


def geometry():
    from tools.thesis_main.analysis.image_portrait import pro_core as core
    from tools.thesis_main.analysis.image_portrait.convergence_v2_common import pairs_for, cluster
    from tools.thesis_main.analysis.image_portrait.convergence_v2_process import partition_stats, group_replay

    responses = core.load(BUNDLE / 'human/responses.jsonl.gz')
    reference = pd.read_csv(V2 / 'foundation/human/response_metrics.csv.gz')
    byid = reference.set_index('canonical_annotation_id')
    dense = {}
    for r in responses:
        geom = core.normalize_geometry(r['effective_points_1024x512'])
        valid = bool(r['calculation_included'] and geom['valid'])
        assert valid == bool(byid.loc[r['canonical_annotation_id'], 'geometry_valid'])
        if valid:
            dense[r['canonical_annotation_id']] = core._dense_boundaries(geom['pairs'])
    s = pd.read_csv(V2 / 'process/image_uncertainty_structure.csv')
    s = s[s.cut == .1].set_index(['image_id', 'condition'])
    included = reference[reference.main_worker_included & reference.raw_condition.isin(['manual', 'semi'])]
    for key, g in included.groupby(['image_id', 'raw_condition']):
        g = g[g.geometry_valid].sort_values('worker_id').reset_index(drop=True)
        dm, pc = pairs_for(g, dense)
        stats = partition_stats(dm, pc, cluster(dm, pc, .1))
        for col in ['n_modes', 'n_supported_modes', 'supported_mass', 'same_topology_multimodality', 'topology_disagreement']:
            np.testing.assert_allclose(stats[col], s.loc[key, col], atol=1e-10)
    image = 'X7HyMhZNoso_987fd31155514f6facb131bd5c14881d'
    g = included[(included.image_id == image) & (included.raw_condition == 'manual')].sort_values('worker_id').reset_index(drop=True)
    dm, pc = pairs_for(g, dense)
    labels = cluster(dm, pc, .1)
    groups = [np.flatnonzero(labels == v) for v in np.unique(labels)]
    assert sorted(map(len, groups)) == [6, 18]
    distances = dm[np.ix_(*groups)].ravel()
    assert len(distances) == 108 and int((distances <= .1).sum()) == 102
    steps, states, _, _ = group_replay(g, dense, .1, orders=100)
    k8 = np.mean([r['n_supported_modes'] for r in steps if r['k'] == 8])
    assert abs(k8 - 1.05) < 1e-10
    roster = {'W001', 'W002', 'W006', 'W010', 'W012', 'W013', 'W017', 'W030'}
    selected = pd.read_csv(V2 / 'subgroups/fixed_disjoint_split_target_processes.csv')
    checks = []
    for im in ['S9hNv5qa7GM_bd9faec23bb3462c94a5fbc6c0a3d5cf', 'UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972']:
        h = included[(included.image_id == im) & (included.raw_condition == 'manual') & included.worker_id.isin(roster)]
        assert set(h.worker_id) == roster
        _, ss, _, _ = group_replay(h, dense, .1, orders=30, record_steps=False)
        results = [x for x in ss if x['rule'] == 'G10_geometry']
        assert len(results) == 30 and all(x['state'] == 'observed_unified' for x in results)
        assert len(selected[(selected.image_id == im) & (selected.n == 8) & (selected.unified_fraction == 1)]) > 0
        checks.append(dict(image_id=im, actual_people=8, unified_orders=30))
    save('geometry_checks.json', dict(status='passed', canonical_responses_checked=len(responses), rebuilt_boundaries=len(dense), image_condition_partitions_checked=len(s), cut=.1, representative_18_6=dict(image_id=image, compatible_cross_pairs=102, total_cross_pairs=108, k8_reclustered_supported_modes=float(k8)), fixed_roster_examples=checks, limitations='Reused reviewed geometry/distance and original clustering implementation; only key replays rerun, not all process fits or every threshold. No missing original caches recreated in received report.'))
    print('Geometry and key real-person replays passed')


def scene_refit():
    from tools.thesis_main.analysis.image_portrait import convergence_v2_prediction as cp
    t = pd.read_csv(V2 / 'prediction/process_targets.csv')
    ids = sorted(t.image_id.unique())
    fields = pd.read_csv(V2 / 'images/evidence_layers.csv').set_index('image_id').reindex(ids)
    x = pd.get_dummies(fields[['scene_human_adopted']].fillna('unknown'), dtype=float).to_numpy().astype(np.float32)
    def writer(path, values):
        dest = OUT / 'scene_refit' / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        d = values if isinstance(values, pd.DataFrame) else pd.DataFrame(values)
        d.to_csv(dest, index=False, float_format='%.12g')
        return d
    old_out, old_csv = cp.OUT, cp.csv
    try:
        cp.OUT, cp.csv = OUT / 'scene_refit', writer
        cp.evaluate_family('scene', x, ids, t, include_horizon=False)
    finally:
        cp.OUT, cp.csv = old_out, old_csv
    expected = pd.read_csv(V2 / 'strict_cold/prediction/cold/scene.csv.gz')
    got = pd.read_csv(OUT / 'scene_refit/prediction/cold/scene.csv.gz')
    keys = ['image_id', 'condition', 'target', 'algorithm']
    z = got.merge(expected, on=keys, suffixes=('', '_reported'), validate='one_to_one')
    assert len(z) == len(got) == len(expected)
    max_delta = float(abs(z.prediction - z.prediction_reported).max())
    mismatches = z[abs(z.prediction - z.prediction_reported) > 1e-7]
    mismatches.to_csv(OUT / 'scene_refit_mismatches.csv', index=False)
    non_knn = z[z.algorithm != 'knn']
    np.testing.assert_allclose(non_knn.prediction, non_knn.prediction_reported, atol=1e-7)
    save('scene_refit_check.json', dict(status='partial_reproduction_knn_mismatch' if len(mismatches) else 'passed', predictions=len(z), max_abs_delta=max_delta, mismatched_predictions=len(mismatches), mismatches_by_algorithm=mismatches.algorithm.value_counts().to_dict(), non_knn_max_abs_delta=float(abs(non_knn.prediction - non_knn.prediction_reported).max()), source='Current migrated source, delivered scene classes and process targets; full inner/outer grouped fitting rerun; no NPZ, originals or target n used.', interpretation='KNN discrepancies are retained, not silently accepted. Exact environment/cache reproduction and explicit handling of near-equal distances remain unresolved. Ridge and constant/same-scene baselines reproduce.'))
    print('Strict scene refit:', len(mismatches), 'unresolved KNN differences; non-KNN matched')


def roster_controls():
    from tools.thesis_main.analysis.image_portrait import pro_core as core
    from tools.thesis_main.analysis.image_portrait.convergence_v2_process import group_replay
    examples = ['S9hNv5qa7GM_bd9faec23bb3462c94a5fbc6c0a3d5cf', 'UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972']
    responses = pd.read_csv(V2 / 'foundation/human/response_metrics.csv.gz')
    responses = responses[responses.main_worker_included & responses.geometry_valid & (responses.raw_condition == 'manual') & responses.image_id.isin(examples)]
    dense = {}
    for r in core.load(BUNDLE / 'human/responses.jsonl.gz'):
        if r['canonical_annotation_id'] in set(responses.canonical_annotation_id):
            dense[r['canonical_annotation_id']] = core._dense_boundaries(core.normalize_geometry(r['effective_points_1024x512'])['pairs'])
    rng = np.random.default_rng(20260915)
    rows = []
    for image in examples:
        g = responses[responses.image_id == image].sort_values('worker_id').reset_index(drop=True)
        seen = set()
        while len(seen) < 100:
            ix = tuple(sorted(rng.choice(len(g), 8, replace=False).tolist()))
            if ix in seen:
                continue
            seen.add(ix)
            h = g.iloc[list(ix)]
            _, ss, _, _ = group_replay(h, dense, .1, orders=30, record_steps=False)
            s = [x['state'] for x in ss if x['rule'] == 'G10_geometry']
            rows.append(dict(image_id=image, actual_workers=';'.join(h.worker_id), people=8, orders=30, unified_fraction=s.count('observed_unified') / len(s), stable_multiple_fraction=s.count('stable_multicluster') / len(s), undetermined_fraction=sum(x.startswith('cannot') for x in s) / len(s)))
    d = pd.DataFrame(rows)
    d.to_csv(OUT / 'fixed_roster_equal8_controls.csv', index=False)
    summary = {im: dict(random_subsets=len(g), mean_unified_fraction=float(g.unified_fraction.mean()), fully_unified_subsets=int((g.unified_fraction == 1).sum()), mean_undetermined_fraction=float(g.undetermined_fraction.mean())) for im, g in d.groupby('image_id')}
    save('fixed_roster_equal8_control_summary.json', dict(status='completed_descriptive_audit', seed=20260915, scope='Two highlighted images selected after seeing the report. 100 distinct real eight-person subsets per image, each 30 order replays; no new independent observations, no confirmatory test.', original_selected_subgroup_unified_fraction=1., results=summary))
    print(json.dumps(summary))


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    p = argparse.ArgumentParser()
    p.add_argument('--tables', action='store_true')
    p.add_argument('--geometry', action='store_true')
    p.add_argument('--scene', action='store_true')
    p.add_argument('--roster', action='store_true')
    args = p.parse_args()
    if args.tables:
        tables()
    if args.geometry:
        geometry()
    if args.scene:
        scene_refit()
    if args.roster:
        roster_controls()
