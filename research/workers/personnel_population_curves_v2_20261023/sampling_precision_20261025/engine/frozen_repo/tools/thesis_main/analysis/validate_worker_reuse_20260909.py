"""复核点、留楼人员画像与真实人员离线组合；仅回顾性研究，不改变人员资格。"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import combinations
from math import comb
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from tools.thesis_main.analysis.worker_reference_feasibility_20260909 import (
    jsonlines, ordinal_groups, profiles, reference_metrics,
)
from tools.thesis_main.analysis.fit_worker_evidence_strata_20260908 import predict_peers
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import partition
from tools.thesis_main.analysis.audit_building_convergence_20260908 import ordered_points
from tools.thesis_main.data_prep.prepare_confirmed_point_calculation_view_20260909 import build

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/research_validation_20260909_v2/workers'
VIEW = ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed'
GEOMETRY = ROOT / 'analysis_results/multibuilding_threshold_stability_20260909_v1/revised/with_workers/geometry'
REFERENCE = ROOT / 'analysis_results/worker_reference_feasibility_20260909_v1/reference_ledger.jsonl'
SEED = 20260909
GROUPS = {'median2': (2, 'quantile'), 'ward3': (3, 'ward')}
CLUSTERS = {'q_0.975': .025, 'q_0.950': .05, 'q_0.900': .1, 'ospa30_t6': 6.}
COHORTS = ('all26', 'without_W19_W26', 'current20')


def crossfit(data):
    """目标整楼不进入画像、分界和组内均值；保留每折真实成员。"""
    members, predictions = [], []
    for building, test in data.groupby('building_id'):
        train = data[data.building_id != building]
        p = profiles(train)
        if p.empty or p.component.nunique() != 1 or not p.fit_status.eq('usable').all():
            raise ValueError('unidentifiable_training_worker_graph')
        for model, (k, method) in GROUPS.items():
            g = ordinal_groups(p, k, method)
            members.append(g.assign(model=model, heldout_building=building,
                training_buildings='|'.join(sorted(train.building_id.unique()))))
            predictions.append(predict_peers(test, g).assign(model=model))
    return pd.concat(members, ignore_index=True), pd.concat(predictions, ignore_index=True)


def adjusted_rand(left, right):
    if len(left) != len(right) or len(left) < 2:
        raise ValueError('invalid_label_vectors')
    choose = lambda n: n*(n-1)/2
    observed = sum(choose(n) for n in Counter(zip(left, right)).values())
    a = sum(choose(n) for n in Counter(left).values())
    b = sum(choose(n) for n in Counter(right).values())
    expected = a*b/choose(len(left))
    upper = (a+b)/2
    return (observed-expected)/(upper-expected) if upper != expected else 1.


@lru_cache(maxsize=128)
def partition_outcomes(n, mask):
    """二至四人图的有限图形缓存；复用v5最大团枚举，不强定歧义分区。"""
    if not 2 <= n <= 4 or not 0 <= mask < 2**comb(n, 2):
        raise ValueError('unsupported_subset_graph')
    matrix = np.ones((n, n)); np.fill_diagonal(matrix, 0)
    for bit, (i, j) in enumerate(combinations(range(n), 2)):
        if mask & (1 << bit):
            matrix[i, j] = matrix[j, i] = 0
    result = partition(matrix, .5)
    unique = result['status'] == 'unique'
    supported = sum(len(g) >= 2 for g in result['clusters']) if unique else np.nan
    return dict(unknown=float(not unique), supported_clusters=supported,
                multi_supported=float(unique and supported >= 2),
                no_supported=float(unique and supported == 0),
                single_supported=float(unique and supported == 1))


def subset_values(frame, matrix, point_counts, geometry_valid, n, threshold):
    """精确枚举不同真实人员，点数硬门独立于相似度阈值。"""
    if frame.worker_id.duplicated().any():
        raise ValueError('duplicate_worker')
    matrix = np.asarray(matrix, float)
    if matrix.shape != (len(frame), len(frame)) or not np.isfinite(matrix).all():
        raise ValueError('invalid_distance_matrix')
    if len(point_counts) != len(frame) or len(geometry_valid) != len(frame):
        raise ValueError('mismatched_geometry_identity')
    subsets = np.array(list(combinations(range(len(frame)), n)), dtype=int).reshape(-1, n)
    if not len(subsets):
        raise ValueError('insufficient_real_people')
    masks = np.zeros(len(subsets), int)
    mismatch = np.zeros(len(subsets), float)
    for bit, (i, j) in enumerate(combinations(range(n), 2)):
        a, b = subsets[:, i], subsets[:, j]
        same = point_counts[a] == point_counts[b]
        masks += ((matrix[a, b] <= threshold + 1e-12) & same).astype(int) << bit
        mismatch += ~same
    outcomes = {field: np.array([partition_outcomes(n, m)[field] for m in masks], dtype=float)
                for field in ('unknown', 'supported_clusters', 'multi_supported', 'no_supported', 'single_supported')}
    invalid = ~geometry_valid[subsets].all(axis=1)
    outcomes['unknown'][invalid] = 1.
    for field in ('multi_supported', 'no_supported', 'single_supported'):
        outcomes[field][invalid] = 0.
    outcomes['supported_clusters'][invalid] = np.nan
    outcomes.update(subsets=subsets, reference=frame.reference.to_numpy(float)[subsets].mean(axis=1),
                    count_mismatch=mismatch/comb(n, 2))
    return outcomes


def paired_means(data, arms):
    """共同图集合上先图内、再楼内、再楼等权；组合数不作权重。"""
    keys = ['building_id', 'image_id']
    if data.duplicated(keys + ['arm']).any():
        raise ValueError('duplicate_arm')
    wide = data.pivot(index=keys, columns='arm', values='value').reindex(columns=arms)
    common = wide.replace([np.inf, -np.inf], np.nan).dropna()
    buildings = common.groupby('building_id').mean()
    return dict(images=len(common), buildings=len(buildings),
                means=buildings.mean().to_dict(),
                image_ids=common.index.get_level_values('image_id').tolist(),
                by_building=buildings.reset_index().to_dict('records'))


def medoid_reference(reference, matrix, subsets):
    """代表仅按组合内部距离选择；并列代表均权计分，参考不进入选择。"""
    local = matrix[subsets[:, :, None], subsets[:, None, :]]
    costs = local.sum(axis=2)
    ties = np.isclose(costs, costs.min(axis=1)[:, None], atol=1e-10, rtol=0)
    return (reference[subsets]*ties).sum(axis=1)/ties.sum(axis=1), (ties.sum(axis=1) > 1).astype(float)


def project_orders(workers, orders, horizon=20):
    positions = {w: i for i, w in enumerate(workers)}
    if len(positions) != len(workers) or len(workers) < horizon:
        raise ValueError('invalid_projected_order_people')
    projected = []
    for order in orders:
        seq = [positions[w] for w in order if w in positions]
        if len(seq) != len(workers) or len(set(seq)) != len(workers):
            raise ValueError('invalid_projected_order')
        projected.append(seq[:horizon])
    return np.asarray(projected, dtype=int)


def verify_references(ledger):
    """核对既有参考选择的坐标，参考可评语义沿用账本、不重新做视觉裁决。"""
    checked = []
    for path, records in pd.DataFrame(ledger).groupby('source_path'):
        source = ROOT / path
        if source.suffix == '.jsonl':
            index = {r['base_task_id']: r for r in jsonlines(source)}
            for row in records.to_dict('records'):
                pairs = index[row['image_id']]['runtime_pairs_1024x512']
                expected = [[p['x'], p[key]] for p in pairs for key in ('y_ceiling', 'y_floor')]
                assert expected == row['points_1024x512']
        else:
            tasks = json.loads(source.read_text(encoding='utf-8-sig'))
            index = {Path(urlparse(t['data']['image']).path).stem: t for t in tasks}
            for row in records.to_dict('records'):
                task = index[row['image_id']]
                if row['reference_id'].startswith('current_manual_gt|'):
                    _, task_id, annotation_id = row['reference_id'].split('|')
                    assert str(task['id']) == task_id
                    annotation = next(a for a in task['annotations'] if str(a['id']) == annotation_id)
                else:
                    position = int(row['reference_id'].rsplit('|', 1)[1])
                    annotation = (task.get('annotations', []) + task.get('predictions', []))[position]
                expected = ordered_points(annotation['result'])
                assert np.allclose(sorted(expected), sorted(row['points_1024x512']), atol=1e-10, rtol=0)
        checked.append(dict(source=str(source), references=len(records)))
    return checked


def load_measurements():
    saved = jsonlines(VIEW / 'calculation_view.jsonl.gz')
    def geometry_decision_payload(value):
        if isinstance(value, dict):
            return {k: geometry_decision_payload(v) for k, v in value.items() if k != 'application_status'}
        if isinstance(value, list):
            return [geometry_decision_payload(v) for v in value]
        return value
    with TemporaryDirectory(prefix='worker_review_check_') as temporary:
        fresh, _ = build(ROOT, Path(temporary), VIEW / 'confirmed_user_decisions.json')
        old_by_id = {r['canonical_annotation_id']: r for r in saved}
        new_by_id = {r['canonical_annotation_id']: r for r in fresh}
        assert geometry_decision_payload(old_by_id) == geometry_decision_payload(new_by_id)
        status_updates = [cid for cid in old_by_id if old_by_id[cid] != new_by_id[cid]]
    annotations = pd.read_csv(ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1/annotations.csv.gz', dtype=str)
    by_id = annotations.set_index('canonical_annotation_id')
    ledger = jsonlines(REFERENCE)
    sources = verify_references(ledger)
    references = {r['image_id']: r for r in ledger}
    measurements = []
    for r in fresh:
        if not r['unassisted_manual_included']:
            continue
        meta = by_id.loc[r['canonical_annotation_id']]
        for field in ('image_id', 'worker_id', 'building_id', 'context_key', 'raw_condition', 'assistance_exposure'):
            assert str(meta[field]) == str(r[field])
        ref = references[r['image_id']]
        row = {key: r[key] for key in ('canonical_annotation_id', 'image_id', 'building_id', 'worker_id',
            'stage', 'raw_condition', 'assistance_exposure', 'effective_point_count', 'processing_status', 'imputed_point')}
        row.update(context_key=r['image_id'], original_context_key=r['context_key'],
                   current20_member=meta.current20_member.lower() == 'true',
                   reference_allowed=ref['score_allowed'], reference_basis=ref['basis'],
                   reference_id=ref['reference_id'], reference_hold=ref['hold_reason'])
        if ref['score_allowed']:
            row.update(reference_metrics(r['effective_points_1024x512'], ref['points_1024x512']))
        measurements.append(row)
    frame = pd.DataFrame(measurements)
    assert not frame.duplicated(['image_id', 'worker_id']).any()
    geometry = pd.read_csv(GEOMETRY / 'response_geometry.csv', dtype={'worker_id': str})
    assert set(frame.canonical_annotation_id) == set(geometry.canonical_annotation_id)
    joined = frame.merge(geometry[['canonical_annotation_id', 'effective_point_count', 'q_geometry_valid']],
                         on='canonical_annotation_id', validate='one_to_one', suffixes=('', '_geometry'))
    assert joined.effective_point_count.eq(joined.effective_point_count_geometry).all()
    joined = joined.drop(columns='effective_point_count_geometry')
    pairs = pd.read_csv(GEOMETRY / 'pairwise_q.csv.gz')
    old = pd.read_csv(ROOT / 'analysis_results/worker_reference_feasibility_20260909_v1/response_measurements.csv.gz')
    delta = joined.merge(old[['canonical_annotation_id', 'ospa30', 'ospa60']],
        on='canonical_annotation_id', suffixes=('', '_old'), validate='one_to_one')
    changed = delta[delta.reference_allowed & (~np.isclose(delta.ospa30, delta.ospa30_old, equal_nan=True)
                     | ~np.isclose(delta.ospa60, delta.ospa60_old, equal_nan=True))]
    changed.to_csv(OUT / 'reviewed_metric_changes.csv', index=False)
    qa = dict(canonical_source_records=len(fresh), raw_source_view_geometry_identity_and_decisions_matched=True,
        application_status_only_metadata_updates=status_updates,
        unassisted_responses=len(joined), images=joined.image_id.nunique(), buildings=joined.building_id.nunique(),
        workers=joined.worker_id.nunique(), reference_scored_responses=int(joined.reference_allowed.sum()),
        reference_scored_images=joined.loc[joined.reference_allowed, 'image_id'].nunique(),
        changed_reference_measurements=len(changed), imputed_responses=int(joined.imputed_point.sum()),
        sources=sources, q_values_recomputed=False, q_values_source=str(GEOMETRY),
        q_geometry_source_identities_and_effective_counts_checked=True)
    return joined, pairs, qa


def cohort(frame, name):
    return (frame if name == 'all26' else frame[~frame.worker_id.isin(['19', '26'])]
            if name == 'without_W19_W26' else frame[frame.current20_member])


def classification(frame):
    all_members, full_members, predictions, half_rows = [], [], [], []
    for scope in COHORTS:
        sample = cohort(frame[frame.reference_allowed], scope)
        for metric in ('ospa30', 'ospa60'):
            data = sample.assign(value=sample[metric])
            members, pred = crossfit(data)
            all_members.append(members.assign(cohort=scope, metric=metric))
            predictions.append(pred.assign(cohort=scope, metric=metric))
            full = profiles(data)
            for model, (k, method) in GROUPS.items():
                full_members.append(ordinal_groups(full, k, method).assign(cohort=scope, metric=metric, model=model))
            buildings = np.array(sorted(data.building_id.unique()))
            rng = np.random.default_rng(SEED)
            for split in range(200):
                left = set(rng.permutation(buildings)[:len(buildings)//2])
                a = profiles(data[data.building_id.isin(left)])
                b = profiles(data[~data.building_id.isin(left)])
                meta = dict(cohort=scope, metric=metric, split=split,
                    left_buildings='|'.join(sorted(left)), right_buildings='|'.join(sorted(set(buildings)-left)),
                    left_workers=len(a), right_workers=len(b))
                if a.component.nunique() != 1 or b.component.nunique() != 1:
                    half_rows.append(dict(**meta, status='disconnected', common_workers=0))
                    continue
                common = a.merge(b, on='worker_id', suffixes=('_a', '_b'))
                base = dict(**meta, status='usable', common_workers=len(common),
                    spearman=float(spearmanr(common.effect_a, common.effect_b).statistic))
                for model, (k, method) in GROUPS.items():
                    x, y = ordinal_groups(a, k, method), ordinal_groups(b, k, method)
                    z = x[['worker_id', 'label']].merge(y[['worker_id', 'label']], on='worker_id')
                    base[model+'_ari'] = adjusted_rand(z.label_x, z.label_y)
                    base[model+'_ordinal_agreement'] = float(z.label_x.eq(z.label_y).mean())
                half_rows.append(base)
    members, full, pred = map(lambda x: pd.concat(x, ignore_index=True), (all_members, full_members, predictions))
    summaries, by_building = [], []
    keys = ['cohort', 'metric', 'model']
    for key, g in pred.groupby(keys):
        bm = g.groupby('building_id')[['baseline_sqerr', 'continuous_sqerr', 'layer_sqerr']].mean()
        for building, row in bm.iterrows():
            by_building.append(dict(zip(keys, key), building_id=building, **row.to_dict()))
        summary = dict(zip(keys, key), responses=len(g), images=g.image_id.nunique(), buildings=len(bm), workers=g.worker_id.nunique())
        for model in ('continuous', 'layer'):
            summary[model+'_record_mse_gain'] = 1-g[model+'_sqerr'].mean()/g.baseline_sqerr.mean()
            summary[model+'_building_mse_gain'] = 1-bm[model+'_sqerr'].mean()/bm.baseline_sqerr.mean()
            summary[model+'_buildings_improved'] = int((bm[model+'_sqerr'] < bm.baseline_sqerr).sum())
        summaries.append(summary)
    stability = members.merge(full[keys+['worker_id', 'label']].rename(columns={'label': 'full_label'}),
        on=keys+['worker_id'], validate='many_to_one')
    stability['same_as_full'] = stability.label.eq(stability.full_label)
    stable = stability.groupby(keys+['worker_id']).agg(same_fraction=('same_as_full', 'mean'),
        folds=('same_as_full', 'size'), observed_labels=('label', lambda s: '|'.join(map(str, sorted(s.unique())))),
        min_effect=('effect', 'min'), max_effect=('effect', 'max')).reset_index()
    for filename, data in [('fold_members', members), ('full_members', full), ('classification_summary', pd.DataFrame(summaries)),
        ('classification_by_building', pd.DataFrame(by_building)), ('classification_predictions', pred),
        ('membership_stability', stable), ('disjoint_half_stability', pd.DataFrame(half_rows))]:
        data.to_csv(OUT / (filename + ('.csv.gz' if filename == 'classification_predictions' else '.csv')), index=False)
    return members


def image_matrices(frame, pairs):
    ids = frame.canonical_annotation_id.tolist()
    positions = {aid: i for i, aid in enumerate(ids)}
    if len(pairs) != comb(len(ids), 2):
        raise ValueError('missing_image_pairs')
    matrices = {key: np.zeros((len(ids), len(ids))) for key in ('ospa30', 'ospa60', 'q')}
    observed = set()
    for row in pairs.itertuples():
        i, j = positions[row.left_canonical], positions[row.right_canonical]
        observed.add(tuple(sorted((i, j))))
        assert row.count_compatible == (frame.effective_point_count.iloc[i] == frame.effective_point_count.iloc[j])
        for key in ('ospa30', 'ospa60'):
            matrices[key][i, j] = matrices[key][j, i] = getattr(row, key)
        matrices['q'][i, j] = matrices['q'][j, i] = (1-min(row.q_boundary, row.q_wallwall)
            if row.pointwise_correspondence_compatible and row.metric_compatible else 1e6)
    assert len(observed) == len(pairs)
    return matrices


def combinations_analysis(frame, pairs, members):
    rows, coverage = [], []
    for image, all_image in frame.groupby('image_id'):
        all_image = all_image.sort_values('canonical_annotation_id').reset_index(drop=True)
        matrices = image_matrices(all_image, pairs[pairs.image_id == image])
        building = all_image.building_id.iloc[0]
        for scope in COHORTS:
            subset = cohort(all_image, scope)
            if len(subset) < 2:
                continue
            positions = subset.index.to_numpy(); subset = subset.reset_index(drop=True)
            matrices_sub = {key: m[np.ix_(positions, positions)] for key, m in matrices.items()}
            for n in (2, 4):
                if len(subset) < n:
                    continue
                geometry = {}
                for config, threshold in CLUSTERS.items():
                    geometry[config] = subset_values(subset.assign(reference=subset.ospa30),
                        matrices_sub['q' if config.startswith('q_') else 'ospa30'],
                        subset.effective_point_count.to_numpy(),
                        subset.q_geometry_valid.to_numpy(bool) if config.startswith('q_') else np.ones(len(subset), bool), n, threshold)
                ix = geometry['q_0.950']['subsets']
                pair_index = list(combinations(range(n), 2))
                pair_disagreement = {metric: np.mean([m[ix[:, a], ix[:, b]] for a, b in pair_index], axis=0)
                    for metric, m in matrices_sub.items() if metric != 'q'}
                for metric in ('ospa30', 'ospa60'):
                    representative, medoid_tied = medoid_reference(subset[metric].to_numpy(float), matrices_sub[metric], ix)
                    for model in GROUPS:
                        if model == 'ward3' and n != 4:
                            continue
                        p = members[(members.cohort == scope) & (members.metric == metric)
                            & (members.model == model) & (members.heldout_building == building)]
                        labels = subset.worker_id.map(p.set_index('worker_id').label)
                        valid_members = labels.notna().to_numpy()[ix].all(axis=1)
                        names = np.array([''.join(chr(64 + int(v)) for v in sorted(x)) if ok else 'unknown'
                            for x, ok in zip(labels.to_numpy()[ix], valid_members)])
                        arms = (['AA', 'AB', 'BB'] if n == 2 else ['AAAA', 'AAAB', 'AABB', 'ABBB', 'BBBB']) if model == 'median2' else ['AABC', 'ABBC', 'ABCC']
                        quality = subset[metric].to_numpy()[ix].mean(axis=1)
                        metadata = dict(image_id=image, building_id=building, cohort=scope, metric=metric, model=model,
                            n=n, real_people=len(subset), reference_allowed=bool(subset.reference_allowed.iloc[0]))
                        group_counts = labels.value_counts().to_dict()
                        coverage.append(dict(**metadata, A=int(group_counts.get(1, 0)), B=int(group_counts.get(2, 0)),
                            C=int(group_counts.get(3, 0)), unknown_people=int(labels.isna().sum()),
                            complete_arm_support=all(np.any(names == a) for a in arms),
                            ABC_possible=all(group_counts.get(i, 0) >= 1 for i in (1, 2, 3)),
                            AABC_possible=group_counts.get(1, 0) >= 2 and all(group_counts.get(i, 0) >= 1 for i in (2, 3))))
                        for arm in arms:
                            mask = names == arm
                            if not mask.any():
                                continue
                            for config, values in geometry.items():
                                selected = values['supported_clusters'][mask]
                                rows.append(dict(**metadata, arm=arm, cluster_config=config, combinations=int(mask.sum()),
                                    reference_mean=float(quality[mask].mean()),
                                    medoid_reference_mean=float(representative[mask].mean()),
                                    medoid_tie_fraction=float(medoid_tied[mask].mean()),
                                    pairwise_mean=float(pair_disagreement[metric][mask].mean()),
                                    point_count_mismatch=float(values['count_mismatch'][mask].mean()),
                                    unknown_fraction=float(values['unknown'][mask].mean()),
                                    supported_clusters_conditional=float(np.mean(selected[np.isfinite(selected)])) if np.isfinite(selected).any() else np.nan,
                                    multi_supported_fraction=float(values['multi_supported'][mask].mean()),
                                    no_supported_fraction=float(values['no_supported'][mask].mean()),
                                    single_supported_fraction=float(values['single_supported'][mask].mean())))
    result = pd.DataFrame(rows)
    result.to_csv(OUT / 'combination_by_image.csv.gz', index=False)
    pd.DataFrame(coverage).to_csv(OUT / 'combination_coverage.csv', index=False)
    summaries, by_building = [], []
    keys = ['cohort', 'metric', 'model', 'n', 'cluster_config']
    fields = ['reference_mean', 'medoid_reference_mean', 'medoid_tie_fraction', 'pairwise_mean', 'point_count_mismatch', 'unknown_fraction',
        'supported_clusters_conditional', 'multi_supported_fraction', 'no_supported_fraction', 'single_supported_fraction']
    for key, g in result.groupby(keys):
        arms = (['AA', 'AB', 'BB'] if key[3] == 2 else ['AAAA', 'AAAB', 'AABB', 'ABBB', 'BBBB']) if key[2] == 'median2' else ['AABC', 'ABBC', 'ABCC']
        for field in fields:
            paired = paired_means(g[['image_id', 'building_id', 'arm', field]].rename(columns={field: 'value'}), arms)
            for arm in arms:
                summaries.append(dict(zip(keys, key), outcome=field, arm=arm,
                    paired_images=paired['images'], paired_buildings=paired['buildings'], building_equal_mean=paired['means'][arm]))
            for row in paired['by_building']:
                for arm in arms:
                    by_building.append(dict(zip(keys, key), outcome=field, building_id=row['building_id'], arm=arm, value=row[arm]))
    pd.DataFrame(summaries).to_csv(OUT / 'combination_summary.csv', index=False)
    pd.DataFrame(by_building).to_csv(OUT / 'combination_by_building.csv', index=False)
    return dict(combination_image_arm_rows=len(result), distinct_images=result.image_id.nunique(),
                distinct_buildings=result.building_id.nunique(), real_people_only=True,
                summary_unit='common images within building, then building equal; overlapping combinations are not independent')


def verify_outputs():
    data = pd.read_csv(OUT / 'response_measurements.csv.gz', dtype={'worker_id': str})
    members = pd.read_csv(OUT / 'fold_members.csv', dtype={'worker_id': str})
    result = pd.read_csv(OUT / 'combination_by_image.csv.gz')
    keys = ['image_id', 'cohort', 'metric', 'model', 'n', 'arm']
    assert not result.duplicated(keys + ['cluster_config']).any()
    assert result.groupby(keys).cluster_config.nunique().eq(len(CLUSTERS)).all()
    assert np.allclose(result[['unknown_fraction', 'no_supported_fraction', 'single_supported_fraction', 'multi_supported_fraction']].sum(axis=1), 1.)
    assert all(row.heldout_building not in row.training_buildings.split('|') for row in members.itertuples())
    member_map = {(r.cohort, r.metric, r.model, r.heldout_building, r.worker_id): int(r.label) for r in members.itertuples()}
    image_map = {i: g for i, g in data.groupby('image_id')}
    checked = 0
    for r in result[result.cluster_config == 'q_0.950'].itertuples():
        people = cohort(image_map[r.image_id], r.cohort).copy()
        people['label'] = [member_map.get((r.cohort, r.metric, r.model, r.building_id, w)) for w in people.worker_id]
        counts = Counter(r.arm); expected_n = 1; expected_reference = 0.
        for name, count in counts.items():
            group = people[people.label == ord(name)-64]
            expected_n *= comb(len(group), count)
            expected_reference += count/len(r.arm)*group[r.metric].mean()
        assert r.combinations == expected_n
        assert np.isclose(r.reference_mean, expected_reference, equal_nan=True, atol=1e-10, rtol=0)
        checked += 1
    check = dict(status='passed', combination_identity_keys_unique=True, probability_accounting=True,
        no_target_building_in_group_training=True, combinatorial_counts_and_mean_reference_closed_form_checks=checked,
        figure_source_tables='classification_summary, disjoint_half_stability, combination_summary',
        test_command='.venv/Scripts/python.exe -m pytest tests/test_validate_worker_reuse_20260909.py tests/test_worker_reference_feasibility_20260909.py tests/test_prepare_confirmed_point_calculation_view_20260909.py -q',
        test_result_record='tests.log', raw_annotation_modified=False)
    (OUT / 'OUTPUT_CHECKS.json').write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding='utf-8')
    return check


def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'], 'axes.unicode_minus': False,
                         'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    summary = pd.read_csv(OUT / 'classification_summary.csv')
    halves = pd.read_csv(OUT / 'disjoint_half_stability.csv')
    colors = {'ospa30': '#155e75', 'ospa60': '#9b6042'}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for j, metric in enumerate(colors):
        d = summary[(summary.cohort == 'current20') & (summary.metric == metric)].set_index('model')
        values = [d.loc['median2', 'continuous_building_mse_gain'], d.loc['median2', 'layer_building_mse_gain'], d.loc['ward3', 'layer_building_mse_gain']]
        bars = axes[0].bar(np.arange(3)+(j-.5)*.32, np.array(values)*100, width=.3, color=colors[metric], label=metric.upper())
        axes[0].bar_label(bars, fmt='%.2f', padding=3, fontsize=9)
        d = halves[(halves.cohort == 'current20') & (halves.metric == metric)]
        fields = ['spearman', 'median2_ari', 'ward3_ari']
        values = d[fields].median().to_numpy()
        low, high = d[fields].quantile(.1).to_numpy(), d[fields].quantile(.9).to_numpy()
        axes[1].errorbar(np.arange(3)+(j-.5)*.15, values, yerr=np.array([values-low, high-values]), fmt='o',
            color=colors[metric], capsize=4, label=metric.upper())
    axes[0].axhline(0, color='#555555', linewidth=.8)
    axes[0].set(xticks=range(3), xticklabels=['连续人员效应', '中位数两档', 'Ward三档'], ylabel='楼等权MSE改善（%）',
                title='当前20人：整楼留出预测\n147图 / 22个building', ylim=(-2.1, 4.4))
    axes[1].set(xticks=range(3), xticklabels=['连续排序相关', '两档 ARI', '三档 ARI'], ylabel='互斥建筑分半的一致性',
                title='当前20人：200次互斥building分半\n点为中位数，线为10%–90%分位范围', ylim=(-.2, 1.))
    for ax in axes:
        ax.grid(axis='y', alpha=.2); ax.set_axisbelow(True); ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(OUT / 'worker_validation.png', dpi=200); plt.close(fig)
    mixture = pd.read_csv(OUT / 'combination_summary.csv')
    arms = ['AAAA', 'AAAB', 'AABB', 'ABBB', 'BBBB']
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3))
    for ax, field, title in zip(axes, ['medoid_reference_mean', 'pairwise_mean'],
        ['组合代表作答的参考偏差\n共同41图 / 12个building', '组合内部的平均成对分歧\n共同55图 / 15个building']):
        for metric, color in colors.items():
            d = mixture[(mixture.cohort == 'current20') & (mixture.metric == metric) & (mixture.model == 'median2')
                & (mixture.n == 4) & (mixture.cluster_config == 'q_0.950') & (mixture.outcome == field)].set_index('arm')
            values = d.loc[arms, 'building_equal_mean']
            ax.plot(arms, values, '-o', color=color, label=metric.upper())
        ax.set(title=title, ylabel='OSPA角距（度）；楼等权', xlabel='固定4位不同人员；A/B由目标楼外资料分档')
        ax.grid(axis='y', alpha=.2); ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(OUT / 'worker_combinations.png', dpi=200); plt.close(fig)


def quality_prefix():
    """共同200全局顺序上的真实medoid；参考可评且至少20人图的质量描述。"""
    from tools.thesis_main.analysis.replay_multibuilding_stability_20260909 import ORDERS
    data = pd.read_csv(OUT / 'response_measurements.csv.gz', dtype={'worker_id': str})
    pairs = pd.read_csv(GEOMETRY / 'pairwise_q.csv.gz')
    orders = [json.loads(line)['worker_ids'] for line in ORDERS.read_text(encoding='utf8').splitlines()]
    assert len(orders) == 200
    ks = [1, 2, 4, 6, 8, 12, 16, 20]
    image_rows, replicate_rows, deltas = [], [], []
    coverage = []
    for scope in ('all26', 'current20'):
        sample = cohort(data[data.reference_allowed], scope)
        for image, frame in sample.groupby('image_id'):
            if len(frame) < 20:
                continue
            frame = frame.sort_values('canonical_annotation_id').reset_index(drop=True)
            ids = set(frame.canonical_annotation_id)
            pg = pairs[(pairs.image_id == image) & pairs.left_canonical.isin(ids) & pairs.right_canonical.isin(ids)]
            matrices = image_matrices(frame, pg)
            sequences = project_orders(frame.worker_id.tolist(), orders)
            meta = dict(cohort=scope, image_id=image, building_id=frame.building_id.iloc[0], observed_people=len(frame))
            coverage.append(meta)
            for metric in ('ospa30', 'ospa60'):
                values_by_k = {}
                for k in ks:
                    values, ties = medoid_reference(frame[metric].to_numpy(float), matrices[metric], sequences[:, :k])
                    assert np.isfinite(values).all()
                    if k == 2:
                        assert ties.min() == 1
                    if k == 20 and len(frame) == 20:
                        assert np.ptp(values) < 1e-9
                    values_by_k[k] = values
                    image_rows.append(dict(**meta, metric=metric, k=k, permutations=200, reference_deviation_mean=float(values.mean()),
                        permutation_p10=float(np.quantile(values, .1)), permutation_p90=float(np.quantile(values, .9)),
                        medoid_tie_fraction=float(ties.mean())))
                    replicate_rows.extend(dict(**meta, metric=metric, k=k, replicate=i, reference_deviation=float(v), medoid_tied=float(ties[i]))
                        for i, v in enumerate(values))
                delta = values_by_k[8] - values_by_k[20]
                deltas.append(dict(**meta, metric=metric, reference_k8=float(values_by_k[8].mean()),
                    reference_k20=float(values_by_k[20].mean()), improvement_8_to_20=float(delta.mean()),
                    permutation_improved_fraction=float((delta > 1e-10).mean()),
                    permutation_worsened_fraction=float((delta < -1e-10).mean())))
    image_frame, delta_frame = pd.DataFrame(image_rows), pd.DataFrame(deltas)
    pd.DataFrame(replicate_rows).to_csv(OUT / 'quality_prefix_replicates.csv.gz', index=False)
    image_frame.to_csv(OUT / 'quality_prefix_by_image.csv', index=False)
    delta_frame.to_csv(OUT / 'quality_8_to_20_by_image.csv', index=False)
    pd.DataFrame(coverage).to_csv(OUT / 'quality_prefix_coverage.csv', index=False)
    summaries, delta_summaries = [], []
    for (scope, metric, k), g in image_frame.groupby(['cohort', 'metric', 'k']):
        buildings = g.groupby('building_id').reference_deviation_mean.mean()
        summaries.append(dict(cohort=scope, metric=metric, k=k, images=len(g), buildings=len(buildings),
            image_equal_mean=g.reference_deviation_mean.mean(), building_equal_mean=buildings.mean()))
    for (scope, metric), g in delta_frame.groupby(['cohort', 'metric']):
        buildings = g.groupby('building_id')[['reference_k8', 'reference_k20', 'improvement_8_to_20']].mean()
        delta_summaries.append(dict(cohort=scope, metric=metric, images=len(g), buildings=len(buildings),
            reference_k8=buildings.reference_k8.mean(), reference_k20=buildings.reference_k20.mean(),
            improvement_8_to_20=buildings.improvement_8_to_20.mean(),
            buildings_improved=int((buildings.improvement_8_to_20 > 1e-10).sum()),
            buildings_worsened=int((buildings.improvement_8_to_20 < -1e-10).sum()),
            images_improved=int((g.improvement_8_to_20 > 1e-10).sum()),
            images_worsened=int((g.improvement_8_to_20 < -1e-10).sum())))
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / 'quality_prefix_summary.csv', index=False)
    pd.DataFrame(delta_summaries).to_csv(OUT / 'quality_8_to_20_summary.csv', index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'], 'axes.unicode_minus': False,
        'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for ax, scope, label in zip(axes, ['all26', 'current20'], ['历史全26人范围', '当前20人范围']):
        for metric, color in [('ospa30', '#155e75'), ('ospa60', '#9b6042')]:
            d = summary[(summary.cohort == scope) & (summary.metric == metric)].sort_values('k')
            ax.plot(d.k, d.building_equal_mean, '-o', color=color, label=metric.upper())
            for k in (8, 20):
                value = d.loc[d.k == k, 'building_equal_mean'].iloc[0]
                ax.annotate(f'{value:.2f}', (k, value), xytext=(0, 7), textcoords='offset points', ha='center', color=color)
        ax.axvline(8, color='#777777', linestyle='--', linewidth=.8)
        ax.set(title=f'{label}：固定{int(d.images.iloc[0])}图 / {int(d.buildings.iloc[0])}个building',
            xlabel='按同一全局人员顺序加入的真实人数 k', ylabel='真实medoid对参考的OSPA偏差（度）', xticks=ks)
        ax.grid(axis='y', alpha=.2); ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(OUT / 'quality_prefix.png', dpi=200); plt.close(fig)
    info = dict(status='passed', fixed_ks=ks, minimum_real_response_count=20, max_k=20, permutations=200,
        orders_source=str(ORDERS), order_coupled_across_k=True, reference_used_in_medoid_selection=False,
        tied_medoids='equally scored', all_n20_full_prefix_invariant=True, k2_all_tied=True,
        reference_unresolved_images_excluded=True, scientific_scope='finite-reference-deviation trajectory; no quality-ceiling or human-semantic-correctness claim',
        cohort_image_counts=pd.DataFrame(coverage).groupby('cohort').image_id.nunique().to_dict())
    (OUT / 'QUALITY_PREFIX_QA.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf8')
    print(pd.DataFrame(delta_summaries).to_string(index=False), flush=True)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    plan = dict(status='retrospective_exploratory', seed=SEED, cohorts=COHORTS, metrics=['ospa30', 'ospa60'],
        classification='image-adjusted worker effects; entire target building excluded; continuous, median2, Ward3',
        class_meaning='ordinal reference-relative deviation only, not personality, diligence or absolute quality',
        split_half='200 disjoint equal-size building halves; common workers only; continuous rank and adjusted Rand',
        inputs='reviewed point calculation view rebuilt from original exports; existing reference disposition retained and coordinates verified',
        manual_semi='only assistance_exposure=none; assisted records not pooled into classes',
        combination='all distinct-person subsets of size2 or4; identical-image identical-n arms; no invented or duplicated people',
        representative='medoid selected using within-combination OSPA only; all tied medoids equally scored against reference; reference never used for selection',
        geometry='v5 maximum-clique partition enumeration, hard effective point count gate, m=2 supported clusters; stable multiple clusters allowed',
        cluster_configs=CLUSTERS, cluster_outcome='static combination structure only, not 20-person sustained convergence',
        inferential_limit='existing-person finite-task reuse; observational retrospective categories; no independent new-person validation',
        original_data_changed=False, formal_protocol_changed=False)
    (OUT / 'METHOD.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    data, pairs, qa = load_measurements()
    data.to_csv(OUT / 'response_measurements.csv.gz', index=False)
    print('reviewed measurements', qa['reference_scored_responses'], flush=True)
    members = classification(data)
    print('classification and 200 disjoint halves complete', flush=True)
    qa.update(combinations_analysis(data, pairs, members))
    (OUT / 'QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    verify_outputs(); figures(); quality_prefix()
    print(json.dumps(qa, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    run()
