"""Mean-Q holdout: one source plus all strictly-majority history budgets.

No target Q enters a prediction feature. Outer building is excluded from both
calibration labels and personnel histories; training-row histories additionally
exclude their own building. Existing manual training admission is preserved.
"""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
import argparse
import itertools
import json
from pathlib import Path
import numpy as np
import pandas as pd
from common import load, read, save_csv, COMMIT, RELATION_VERSION, METRICS
METHODS = ['external_image_mean', 'outside_roster_mean', 'outside_peer_roster_mean', 'source_mean', 'roster_adjusted_source', 'peer_adjusted_source', 'known_difficulty_adjusted_source', 'calibrated_roster_only', 'calibrated_source_mean', 'calibrated_roster_source', 'calibrated_peer_roster_only', 'calibrated_peer_source']

def histories(images):
    n = len(images)
    for m in [1] + list(range(n // 2 + 1, n)):
        for h in itertools.combinations(sorted(images), m):
            yield (h, [i for i in images if i not in h])

def build_rows(q, groups, metric, panel, outer, for_training=False):
    rows = []
    for g in groups:
        b = g['building']
        if (b == outer) == for_training:
            continue
        z = q[q.image_id.isin(g['images'])].copy()
        if for_training:
            z = z[z.training_allowed]
        if panel == 'common_workers':
            common = set(g['common_workers'])
            if len(common) < 3:
                continue
            z = z[z.worker_id.isin(common)]
            counts = z.groupby('worker_id').image_id.nunique()
            common = set(counts[counts.eq(g['N'])].index)
            z = z[z.worker_id.isin(common)]
            if len(common) < 3:
                continue
        if z.groupby('image_id').size().reindex(g['images'], fill_value=0).min() < 3:
            continue
        excluded = {outer, b}
        train = q[q.training_allowed & ~q.building_id.isin(excluded)]
        image_means = train.groupby('image_id')[metric].mean()
        pop = image_means.mean()
        wm = train.groupby('worker_id')[metric].mean()
        peer_n = train.groupby('image_id')[metric].transform('size')
        peer_sum = train.groupby('image_id')[metric].transform('sum')
        peer = train[metric] - (peer_sum - train[metric]) / (peer_n - 1)
        peer = peer.where(peer_n.gt(1))
        peer_wm = peer.groupby(train.worker_id).mean()
        class_table = train.groupby(['image_id', 'current_class'], as_index=False)[metric].mean()
        class_mean = class_table.groupby('current_class')[metric].mean()
        cells = {im: a for im, a in z.groupby('image_id')}
        means = {im: a[metric].mean() for im, a in cells.items()}
        roster = {im: a.worker_id.map(wm).mean() for im, a in cells.items()}
        peer_roster = {im: a.worker_id.map(peer_wm).mean() for im, a in cells.items()}
        hist_cover = {im: a.worker_id.isin(wm.index).mean() for im, a in cells.items()}
        difficulty = {im: class_mean.get(a.current_class.iloc[0], np.nan) for im, a in cells.items()}
        for si, (h, targets) in enumerate(histories(g['images'])):
            src = np.mean([means[i] for i in h])
            src_hist = np.mean([roster[i] for i in h])
            src_diff = np.mean([difficulty[i] for i in h])
            src_peer = np.mean([peer_roster[i] for i in h])
            for target in targets:
                a = cells[target]
                rows.append(dict(group_id=g['group_id'], group_codes='|'.join(g['sources']), building_id=b, N=g['N'], m=len(h), split_id=g['group_id'] + '_meannew_' + str(si), target_image=target, target_code=a.image_code.iloc[0], history='|'.join(h), panel=panel, metric=metric, actual=means[target], source_mean=src, external_image_mean=pop, outside_roster_mean=roster[target], source_roster_mean=src_hist, outside_peer_roster_mean=pop + peer_roster[target], target_peer_history=peer_roster[target], source_peer_history=src_peer, roster_adjusted_source=roster[target] + src - src_hist, peer_adjusted_source=peer_roster[target] + src - src_peer, known_difficulty_adjusted_source=src + difficulty[target] - src_diff, target_n=len(a), history_records=sum((len(cells[i]) for i in h)), target_history_coverage=hist_cover[target], minimum_source_history_coverage=min((hist_cover[i] for i in h)), target_workers='|'.join(sorted(a.worker_id)), target_object_ids='|'.join(sorted(a.object_id)), target_reference_id=a.reference_id.iloc[0], target_reference_version=a.reference_version.iloc[0], target_class=a.current_class.iloc[0], calibration_training=for_training))
    return pd.DataFrame(rows)

def weights(d):
    keys = ['building_id', 'target_image', 'group_id', 'm']
    repeated = d.groupby(keys).actual.transform('size')
    budgets = d[['building_id', 'target_image', 'group_id', 'm']].drop_duplicates().groupby(['building_id', 'target_image', 'group_id']).size()
    groups = d[['building_id', 'target_image', 'group_id']].drop_duplicates().groupby(['building_id', 'target_image']).size()
    images = d[['building_id', 'target_image']].drop_duplicates().groupby('building_id').size()
    w = []
    for row, n in zip(d.itertuples(), repeated):
        w.append(1 / (n * budgets.loc[row.building_id, row.target_image, row.group_id] * groups.loc[row.building_id, row.target_image] * images.loc[row.building_id]))
    return np.asarray(w)

def fit_one(train, test):
    output = {}
    coefficients = []
    w = weights(train)
    valid = np.isfinite(train.outside_roster_mean) & np.isfinite(train.source_roster_mean)
    designs = {'calibrated_roster_only': (np.zeros(len(train)), np.zeros(len(test)), train.outside_roster_mean, test.outside_roster_mean, False), 'calibrated_source_mean': (train.source_mean - train.external_image_mean, test.source_mean - test.external_image_mean, train.external_image_mean, test.external_image_mean, True), 'calibrated_roster_source': (train.source_mean - train.source_roster_mean, test.source_mean - test.source_roster_mean, train.outside_roster_mean, test.outside_roster_mean, True), 'calibrated_peer_roster_only': (np.zeros(len(train)), np.zeros(len(test)), train.outside_peer_roster_mean, test.outside_peer_roster_mean, False), 'calibrated_peer_source': (train.source_mean - train.source_peer_history - train.external_image_mean, test.source_mean - test.source_peer_history - test.external_image_mean, train.outside_peer_roster_mean, test.outside_peer_roster_mean, True)}
    for method, (x, xt, base, baset, slope) in designs.items():
        v = valid & np.isfinite(x) & np.isfinite(base)
        X = np.column_stack([np.ones(len(train)), x]) if slope else np.ones((len(train), 1))
        T = np.column_stack([np.ones(len(test)), xt]) if slope else np.ones((len(test), 1))
        coef = np.linalg.lstsq(X[v] * np.sqrt(w[v, None]), (train.actual.to_numpy() - np.asarray(base))[v] * np.sqrt(w[v]), rcond=None)[0]
        output[method] = np.clip(np.asarray(baset) + T @ coef, 0, 100)
        coefficients.append(dict(method=method, intercept=coef[0], source_coefficient=coef[1] if slope else np.nan, training_rows=int(v.sum()), training_images=train[v].target_image.nunique(), training_buildings=train[v].building_id.nunique()))
    return (output, coefficients)

def aggregate(pred):
    keys = ['metric', 'panel', 'method', 'group_id', 'building_id', 'N', 'm', 'target_image', 'target_code']
    target = pred.groupby(keys, as_index=False).agg(mae=('absolute_error', 'mean'), rmse2=('squared_error', 'mean'), bias=('error', 'mean'), expected_bad10=('bad10', 'mean'), expected_bad15=('bad15', 'mean'), sources_evaluated=('absolute_error', 'size'), actual=('actual', 'first'), prediction_mean=('predicted', 'mean'), target_n=('target_n', 'first'), history_records=('history_records', 'mean'))
    group = target.groupby(['metric', 'panel', 'method', 'group_id', 'building_id', 'N', 'm'], as_index=False).agg(mae=('mae', 'mean'), rmse2=('rmse2', 'mean'), bad10=('expected_bad10', 'mean'), bad15=('expected_bad15', 'mean'), images=('target_image', 'nunique'))
    bs = []
    for stage in ['single_source', 'minimum_majority', 'maximum_history']:
        m = 1 if stage == 'single_source' else target.N // 2 + 1 if stage == 'minimum_majority' else target.N - 1
        x = target[target.m.eq(m)]
        x = x.groupby(['metric', 'panel', 'method', 'building_id', 'target_image'], as_index=False).agg(mae=('mae', 'mean'), rmse2=('rmse2', 'mean'), bad10=('expected_bad10', 'mean'), bad15=('expected_bad15', 'mean'), target_n=('target_n', 'first'), history_records=('history_records', 'mean'))
        b = x.groupby(['metric', 'panel', 'method', 'building_id'], as_index=False).agg(mae=('mae', 'mean'), rmse2=('rmse2', 'mean'), bad10=('bad10', 'mean'), bad15=('bad15', 'mean'), images=('target_image', 'nunique'), mean_source_records=('history_records', 'mean'))
        b['stage'] = stage
        bs.append(b)
    buildings = pd.concat(bs, ignore_index=True)
    summary = buildings.groupby(['metric', 'panel', 'method', 'stage'], as_index=False).agg(mae=('mae', 'mean'), mse=('rmse2', 'mean'), bad10=('bad10', 'mean'), bad15=('bad15', 'mean'), images=('images', 'sum'), buildings=('building_id', 'nunique'), mean_source_records=('mean_source_records', 'mean'))
    summary['rmse'] = np.sqrt(summary.mse)
    return (target, group, buildings, summary)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    _, q, _, _, _ = load(a.repo)
    q = q[q.condition.eq('manual') & q.layer.eq('ordinary')].copy()
    gs = [g for g in read(a.repo / 'research/same_room/same_room_multiview_20261020/GROUPS.json') if g['metric'] == 'B8L2' and g['origin'] == 'all' and (g['layer'] == 'ordinary')]
    outputs = []
    folds = []
    features = []
    for metric in METRICS:
        for panel in ['actual_pool', 'common_workers']:
            for outer in sorted({g['building'] for g in gs}):
                test = build_rows(q, gs, metric, panel, outer, False)
                if test.empty:
                    continue
                train = build_rows(q, gs, metric, panel, outer, True)
                estimates, coefs = fit_one(train, test)
                for c in coefs:
                    folds.append(dict(**c, metric=metric, panel=panel, held_building=outer))
                for method in METHODS:
                    v = test[method].to_numpy() if method in test else estimates[method]
                    z = test.copy()
                    z['method'] = method
                    z['predicted'] = np.clip(v, 0, 100)
                    z['error'] = z.predicted - z.actual
                    z['absolute_error'] = z.error.abs()
                    z['squared_error'] = z.error ** 2
                    z['bad10'] = z.absolute_error.gt(10)
                    z['bad15'] = z.absolute_error.gt(15)
                    outputs.append(z)
                features.append(test)
    pred = pd.concat(outputs, ignore_index=True)
    identity = ['metric', 'panel', 'group_id', 'split_id', 'target_image']
    valid = pred.groupby(identity).predicted.transform(lambda v: v.notna().all())
    pred['all_methods_supported'] = valid
    wide = pred.pivot(index=identity, columns='method', values='predicted').reset_index()
    wide = wide.merge(pred[identity + ['actual', 'all_methods_supported']].drop_duplicates(), on=identity, validate='one_to_one')
    save_csv(wide, a.out / 'tables/mean_prediction_values.csv.gz')
    pred = pred[valid]
    target, group, building, summary = aggregate(pred)
    for name, d in [('mean_holdout_targets', target), ('mean_holdout_groups', group), ('mean_holdout_buildings', building), ('mean_holdout_summary', summary), ('mean_calibration_folds', pd.DataFrame(folds)), ('mean_feature_index', pd.concat(features, ignore_index=True))]:
        save_csv(d, a.out / 'tables' / (name + ('.csv.gz' if name == 'mean_feature_index' else '.csv')))
    receipt = dict(commit=COMMIT, relation_version=RELATION_VERSION, status='本轮新增；既有多数历史均值直接预测按固定输入重建', primary_condition='ordinary_manual', groups=len(gs), images=len(set(sum([g['images'] for g in gs], []))), budgets='m=1 plus every integer floor(N/2)+1 ... N-1; all historical subsets enumerated', metrics=METRICS, methods=METHODS, target_quality_only_for_evaluation=True, calibration='outer building excluded; train-row personnel histories also exclude own building; old training admission preserved; linear specifications fixed without tuning', mean_history='only available worker histories averaged; coverage recorded; no observed Q imputation', known_difficulty='conditional benchmark requiring adopted target difficulty; not a no-target-information deployment strategy', weighting='history subsets within target-budget, groups within image, images within building, buildings equal', new_external_validation=False, source_cost='history_records is number of reference-evaluated independent source answers, not a money or delivery-time estimate', method_discovery='exploratory current-inventory comparison; relative-peer baselines added to challenge absolute-Q roster correction; not a preregistered external test', raw_prediction_rows=len(pred), unsupported_rows=int((~valid).sum()), minimum_target_roster_history_coverage=float(pred.target_history_coverage.min()))
    (a.out / 'MEAN_PREDICTION_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(summary[summary.metric.eq('B8L2')].sort_values(['panel', 'stage', 'mae']).to_string(index=False))
if __name__ == '__main__':
    main()
