"""复核 Pro 返回，并单独修正外层留建筑模型中的人员特征隔离。"""
from pathlib import Path
import itertools
import json
import sys

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'analysis_results/panorama_research_received_20260921'


def compare_reproduction(original, local, out):
    def equal(x, y):
        if isinstance(x, dict):
            return isinstance(y, dict) and x.keys() == y.keys() and all(equal(x[k], y[k]) for k in x)
        if isinstance(x, list):
            return isinstance(y, list) and len(x) == len(y) and all(equal(a, b) for a, b in zip(x, y))
        if isinstance(x, (float, int)) and not isinstance(x, bool):
            return isinstance(y, (float, int)) and bool(np.isclose(x, y, rtol=1e-9, atol=1e-9, equal_nan=True))
        return x == y
    differences = {
        'validation.json': '本机源严格校验通过；Pro环境有浮点尾差。',
        'floating_roundoff.csv.gz': '本机没有源距离尾差，因此原脚本写出无列空表。',
        'manual_semantic_case_queue.csv': '并列排序缺少固定第二排序键，人工候选发生替换。',
        'case_spatial_source_excerpts.json': '随人工候选替换而变化。',
        'geometry_summary.json': '3D拟合数值随依赖环境变化，成功/失败状态一致。',
        'regularization_mechanism_panel.csv': '拟合残差最大差约0.00000263度，未改状态。',
        'regularization_mechanism_inputs_outputs.json': '同一输入的拟合输出有数值差异，原件与本机值均保留。',
    }
    report = []
    for p in sorted((original / 'results').iterdir()):
        if p.is_dir():
            continue
        q = local / 'results' / p.name
        entry = dict(file=p.name, local_exists=q.exists())
        try:
            if p.name.endswith(('.csv', '.csv.gz')):
                a, b = pd.read_csv(p), pd.read_csv(q)
                pd.testing.assert_frame_equal(a, b, check_dtype=False, check_exact=False, rtol=1e-9, atol=1e-9)
                entry.update(equal=True, rows=len(a))
            else:
                entry['equal'] = equal(json.loads(p.read_text(encoding='utf8')), json.loads(q.read_text(encoding='utf8')))
        except (AssertionError, pd.errors.EmptyDataError) as exc:
            entry.update(equal=False, reason=str(exc)[:700])
        if not entry['equal']:
            assert p.name in differences, f'Unexplained reproduction difference: {p.name}'
            entry['disposition'] = differences[p.name]
        report.append(entry)
    a = pd.read_csv(original / 'results/regularization_mechanism_panel.csv')
    b = pd.read_csv(local / 'results/regularization_mechanism_panel.csv')
    assert a.id.equals(b.id) and a.fit_status.equals(b.fit_status)
    assert a.fit_reasons.fillna('').equals(b.fit_reasons.fillna(''))
    assert np.nanmax(abs(a.fit_residual_max_deg - b.fit_residual_max_deg)) < 1e-5
    (out / 'REPRODUCTION_CHECK.json').write_text(json.dumps(dict(
        tolerance=dict(atol=1e-9, rtol=1e-9), files=report), ensure_ascii=False, indent=2), encoding='utf8')


def roster_features(views, roster, heldout_building):
    """同一外层折的所有图片都使用排除该折目标建筑的画像。"""
    rr = roster[(roster.config == 'Q_2') &
                (roster.heldout_building == heldout_building)]
    if rr.worker.duplicated().any() or rr.empty:
        raise ValueError(f'Invalid heldout roster: {heldout_building}')
    labels = rr.set_index('worker').subtype.to_dict()
    rows = {}
    for iid, view in views.items():
        values = np.array([labels.get(w, 0) for w in view['workers']])
        rows[iid] = [float(np.mean(values == 1)), float(np.mean(values == 0))]
    return pd.DataFrame.from_dict(rows, orient='index',
                                 columns=['Q2_type1_fraction', 'Q2_unknown_fraction'])


def main():
    original = BASE / 'original_package'
    source = BASE / 'local_recompute/source_work'
    out = BASE / 'audit'
    out.mkdir(exist_ok=True)
    compare_reproduction(original, BASE / 'local_recompute', out)
    sys.path.insert(0, str(original / 'code'))
    import common as c
    c.configure(source)
    _, records, views, _, _ = c.load()
    results = original / 'results'
    im = pd.read_csv(results / 'image_metrics.csv').set_index('image_id')
    # 用真实小人员池穷举留一人及观察子集，独立检查组合公式。
    checked = 0
    for iid, view in views.items():
        n = view['N']
        if not 2 <= n <= 9:
            continue
        for k in range(1, n):
            numerator = total = 0
            for j in range(n):
                for subset in itertools.combinations([x for x in range(n) if x != j], k):
                    numerator += not any(view['d'][j, x] <= 25.6 for x in subset)
                    total += 1
            assert np.isclose(numerator / total, c.next_uncovered(view['d'], k), atol=1e-12)
            checked += 1

    # 同一可评分面板比较同房与同栋其他房间，避免仅有跨建筑基线。
    room = pd.read_csv(results / 'room_scene_predictions.csv')
    room_checks = []
    def weighted(frame, column):
        return frame.groupby(['building', 'family'])[column].mean().groupby('building').mean().mean()
    for key, group in room.groupby(['kind', 'metric', 'k']):
        if not key[0].startswith('same_room') or not (key[1] == 'pair_disagreement' or key[2] in [5, 8]):
            continue
        z = group.dropna(subset=['building_other_room_baseline']).copy()
        z['other_error'] = abs(z.value - z.building_other_room_baseline)
        room_checks.append(dict(kind=key[0], metric=key[1], k=int(key[2]),
            images=len(z), buildings=z.building.nunique(),
            same_room_MAE=weighted(z, 'absolute_error'),
            same_building_other_room_MAE=weighted(z, 'other_error'),
            outside_building_MAE=weighted(z, 'baseline_absolute_error'),
            source_outcome_exposed_in_full_panel=int(group.source_outcome_exposed.sum())))

    feat = pd.read_csv(source / 'analysis_results/clustering_release_local_20260920/current/input/supplement/model_image_features.csv').set_index('image_id')
    feat['N'] = im.N
    roster = pd.read_csv(source / 'analysis_results/clustering_numeric_received_20260920/results/personnel/refitted_lobo_rosters.csv')
    counts = ['bi_enclosed_corners', 'bi_extended_corners', 'hohonet_corners']
    gaps = [x for x in feat if x.startswith('gap_')]
    personnel = ['Q2_type1_fraction', 'Q2_unknown_fraction']
    configs = {'N_only': ['N'], 'N_plus_roster': ['N'] + personnel,
        'N_plus_model_counts': ['N'] + counts,
        'N_plus_model_counts_gaps': ['N'] + counts + gaps,
        'N_plus_model_and_roster': ['N'] + counts + gaps + personnel}
    original_features = pd.DataFrame({
        iid: roster_features({iid: view}, roster, view['building']).loc[iid]
        for iid, view in views.items() if iid in feat.index}).T
    predictions, changes = [], []
    for outcome, minimum in [('pair_disagreement', 4), ('U5', 8), ('U8', 11)]:
        ids = [i for i in im.index if im.loc[i, 'N'] >= minimum and i in feat.index]
        buildings = np.array([views[i]['building'] for i in ids])
        y = im.loc[ids, outcome].to_numpy()
        for hold in sorted(set(buildings)):
            train = buildings != hold
            fixed = roster_features(views, roster, hold)
            fold = feat.join(fixed)
            differs = np.any(abs(fixed.loc[ids, personnel].to_numpy() - original_features.loc[ids, personnel].to_numpy()) > 1e-12, axis=1)
            changes.append(dict(outcome=outcome, heldout_building=hold,
                                training_images=int(train.sum()), changed_training_images=int((differs & train).sum())))
            for config, cols in configs.items():
                x = fold.loc[ids, cols].to_numpy()
                imp = SimpleImputer(strategy='median')
                a = imp.fit_transform(x[train]); b = imp.transform(x[~train])
                scale = StandardScaler()
                a = scale.fit_transform(a); b = scale.transform(b)
                weights = np.array([1. / sum(buildings[train] == z) for z in buildings[train]])
                weights *= len(weights) / weights.sum()
                pred = Ridge(alpha=10.).fit(a, y[train], sample_weight=weights).predict(b).clip(0, 1)
                for iid, truth, value in zip(np.array(ids)[~train], y[~train], pred):
                    predictions.append(dict(image_id=iid, building=hold, outcome=outcome,
                                            config=config, value=truth, prediction=value))
    pr = pd.DataFrame(predictions)
    old = pd.read_csv(results / 'model_N_roster_controls.csv')
    joined = pr.merge(old[['image_id', 'outcome', 'config', 'prediction']],
                      on=['image_id', 'outcome', 'config'], suffixes=('', '_original'), validate='one_to_one')
    unchanged = joined[~joined.config.isin(['N_plus_roster', 'N_plus_model_and_roster'])]
    assert np.allclose(unchanged.prediction, unchanged.prediction_original, atol=1e-9, rtol=1e-9)
    joined['absolute_error'] = abs(joined.value - joined.prediction)
    joined['original_error'] = abs(joined.value - joined.prediction_original)
    baseline = joined[joined.config == 'N_only'][['image_id', 'outcome', 'absolute_error']].rename(columns={'absolute_error': 'baseline_error'})
    joined = joined.merge(baseline, on=['image_id', 'outcome'], validate='many_to_one')
    summaries = []
    for (outcome, config), z in joined.groupby(['outcome', 'config']):
        z = z.copy(); z['gain'] = z.baseline_error - z.absolute_error
        summaries.append(dict(outcome=outcome, config=config, images=len(z), buildings=z.building.nunique(),
            corrected_MAE=z.groupby('building').absolute_error.mean().mean(),
            original_MAE=z.groupby('building').original_error.mean().mean(),
            conditional_gain=c.building_summary(z, 'gain')))
    joined.to_csv(out / 'outer_fold_corrected_model_predictions.csv', index=False)
    pd.DataFrame(changes).to_csv(out / 'outer_fold_roster_changes.csv', index=False)
    # 为不同点数候选补足实际匹配与未匹配原点号，仍不是语义裁决。
    from scipy.optimize import linear_sum_assignment
    queue = pd.read_csv(results / 'manual_semantic_case_queue.csv')
    correspondences = []
    for row in queue[~queue.same_count].itertuples():
        ra, rb = records[row.a_id], records[row.b_id]
        a, b = ra['p'][ra['links']], rb['p'][rb['links']]
        dx = abs((a[:, None, :, 0] - b[None, :, :, 0] + 512) % 1024 - 512)
        dy = abs(a[:, None, :, 1] - b[None, :, :, 1])
        distance = np.hypot(dx, dy).max(2)
        left, right = linear_sum_assignment(np.where(distance <= 25.6, distance / 1e5, 1.))
        accepted = [(int(i), int(j)) for i, j in zip(left, right) if distance[i, j] <= 25.6]
        assert len(accepted) == row.partial_matched
        correspondences.append(dict(code=row.code, a_id=row.a_id, b_id=row.b_id,
            matched=[dict(a_raw_points=(ra['links'][i] + 1).tolist(), b_raw_points=(rb['links'][j] + 1).tolist(), distance_px=float(distance[i, j])) for i, j in accepted],
            unmatched_a=[(ra['links'][i] + 1).tolist() for i in range(len(a)) if i not in {x for x, _ in accepted}],
            unmatched_b=[(rb['links'][j] + 1).tolist() for j in range(len(b)) if j not in {y for _, y in accepted}],
            semantic_status='候选自由匹配，未验证墙邻接或物理角身份'))
    payload = dict(finite_pool_exhaustive_checks=checked, same_building_controls=room_checks,
                   corrected_model_summary=summaries, partial_matching_candidates=correspondences)
    (out / 'independent_checks.json').write_text(json.dumps(c.clean(payload), ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(c.clean(dict(exhaustive_checks=checked, corrected_U8=[x for x in summaries if x['outcome'] == 'U8'])), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
