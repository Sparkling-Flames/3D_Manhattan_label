"""Fixed-plan LOBO comparison using saved individual outcomes, without scoring/fusion."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.linalg import solve

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/difficulty/difficulty_computable_comparison_20261028'
SOURCE = ROOT / 'research/workers/personnel_population_curves_v2_20261023'
GEOMETRY = ['ref_turn5', 'ref_H', 'ref_short_edges', 'ref_min_horizontal_deg',
            'has_short', 'conditional_short_span']
MODELS = ['baseline', 'binary_easy', 'binary_hard', 'three', 'turn_only', 'geometry', 'three_geometry']
LOSSES = dict(reduced='mse', turn_deficit='mse', bottom_bias_abs='mae', unmatched='mse',
              Q='mae', time_old='mae', time_new='mae')


def load_data():
    pools = pd.read_csv(SOURCE / 'design/ACTUAL_POOLS.csv')
    pools = pools[pools.layer.eq('ordinary_manual')].copy()
    members = pd.read_csv(SOURCE / 'inputs/RAW_POOL_MEMBER_FEATURES.csv.gz')
    d = members.merge(pools[['pool_id', 'building', 'difficulty', 'reference_id', 'workers', 'pool_n']],
                      on='pool_id', validate='many_to_one')
    assert len(d) == 5719 and d.image_id.nunique() == 177 and d.worker_id.nunique() == 60
    assert d.object_id.is_unique and not d.duplicated(['image_id', 'worker_id']).any()
    assert d.pool_reference_matches_features.all()
    for _, g in d.groupby('pool_id'):
        assert len(g) == g.pool_n.iloc[0] and set(g.worker_id) == set(g.workers.iloc[0].split('|'))
    f = pd.read_csv(SOURCE / 'inputs/IMAGE_DIFFICULTY_OPPORTUNITIES.csv')
    f = f[['image_id', 'target_id', 'reference_id', 'difficulty_coarse', *GEOMETRY[:4], 'ref_short_min_horizontal_deg']]
    d = d.merge(f, on=['image_id', 'reference_id'], validate='many_to_one')
    assert len(d) == 5719 and d.reference_id.eq(d.target_id).all()
    assert d.difficulty.eq(d.difficulty_coarse).all() and d[GEOMETRY[:4]].notna().all().all()
    t = pd.read_csv(SOURCE / 'inputs/RECORD_ELIGIBILITY_TIME_LINK.csv.gz')
    d = d.merge(t[['object_id', 'worker', 'reference_id', 'quality_usable', 'current_target_match',
                   'is_oos', 'is_doorway', 'time_source', 'time_status', 'source_active_time_seconds']],
                on=['object_id', 'reference_id'], validate='one_to_one', suffixes=('', '_link'))
    assert len(d) == 5719 and d.worker.eq(d.worker_id).all()
    assert d.quality_usable.all() and d.current_target_match.all() and not (d.is_oos | d.is_doorway).any()
    np.testing.assert_allclose(d.source_active_time_seconds, d.source_active_time_seconds_link, equal_nan=True)
    d['source'] = d.time_source.map({'inherited_v1_audited_source': 'old',
        'user_processed_reported_not_raw_log_replayed': 'new'})
    assert d.source.notna().all()
    d['has_short'] = d.ref_short_edges.gt(0).astype(float)
    assert d.loc[d.has_short.eq(1), 'ref_short_min_horizontal_deg'].notna().all()
    assert d.loc[d.has_short.eq(0), 'ref_short_min_horizontal_deg'].isna().all()
    d['conditional_short_span'] = d.ref_short_min_horizontal_deg.fillna(0)
    for name, col in dict(reduced='reference_reduced', turn_deficit='reference_turn_deficit',
                         bottom_bias_abs='abs_bottom_bias_9', unmatched='unmatched_ref_9', Q='B8L2').items():
        d[name] = d[col]
    assert d[list(LOSSES)[:5]].notna().all().all()
    for name, source, status in [('time_old', 'old', 'usable'), ('time_new', 'new', 'reported_processed')]:
        mask = d.source.eq(source) & d.time_status.eq(status) & d.source_active_time_seconds.gt(0)
        d[name] = np.log(d.source_active_time_seconds.where(mask))
    return d


def matrix(train, test, model, weights):
    """All levels and scales are fitted on training buildings only."""
    left, right, names = [np.ones(len(train))], [np.ones(len(test))], ['intercept']
    for field in ['worker_id', 'source']:
        for value in sorted(train[field].unique()):
            left.append(train[field].eq(value).to_numpy(float))
            right.append(test[field].eq(value).to_numpy(float))
            names.append(field + ':' + value)
    for grade in (['中等', '困难'] if model in ['three', 'three_geometry'] else []):
        left.append(train.difficulty.eq(grade).to_numpy(float))
        right.append(test.difficulty.eq(grade).to_numpy(float)); names.append('grade:' + grade)
    if model in ['binary_easy', 'binary_hard']:
        grade = '简单' if model == 'binary_easy' else '困难'
        left.append(train.difficulty.eq(grade).to_numpy(float))
        right.append(test.difficulty.eq(grade).to_numpy(float)); names.append('grade:' + grade)
    numeric = GEOMETRY if model in ['geometry', 'three_geometry'] else ['ref_turn5'] if model == 'turn_only' else []
    for field in numeric:
        a, b = train[field].to_numpy(float), test[field].to_numpy(float)
        mean = np.average(a, weights=weights)
        sd = np.sqrt(np.average((a - mean)**2, weights=weights))
        sd = sd if sd > 1e-12 else 1.
        left.append((a - mean)/sd); right.append((b - mean)/sd); names.append(field)
    return np.column_stack(left), np.column_stack(right), names


def fit_predict(train, test, outcome, model):
    weights = 1 / train.groupby('image_id').image_id.transform('size').to_numpy(float)
    x, z, names = matrix(train, test, model, weights)
    penalty = np.eye(x.shape[1]); penalty[0, 0] = 0
    beta = solve(x.T @ (weights[:, None]*x) + penalty,
                 x.T @ (weights*train[outcome].to_numpy(float)), assume_a='pos')
    raw = z @ beta
    pred = np.clip(raw, 0, 1) if outcome == 'reduced' else raw
    return pred, raw, dict(zip(names, beta))


def losses(predictions):
    p = predictions.copy()
    p['mae'] = abs(p.prediction-p.observed)
    p['mse'] = (p.prediction-p.observed)**2
    p['bias'] = p.prediction-p.observed
    return p


def aggregate(p, extra=()):
    keys = ['outcome', 'model', *extra]
    images = p.groupby([*keys, 'building', 'image_id'])[['mae', 'mse', 'bias']].mean().reset_index()
    buildings = images.groupby([*keys, 'building'])[['mae', 'mse', 'bias']].mean().reset_index()
    summary = buildings.groupby(keys)[['mae', 'mse', 'bias']].mean().reset_index()
    return images, buildings, summary


def comparisons(buildings):
    rows = []
    pairs = [(m, 'baseline') for m in MODELS if m != 'baseline']
    pairs += [('geometry', x) for x in ['three', 'turn_only', 'binary_easy', 'binary_hard']]
    pairs += [('three_geometry', 'three'), ('three', 'binary_easy'), ('three', 'binary_hard')]
    rng = np.random.default_rng(20261028)
    for outcome, g in buildings.groupby('outcome'):
        loss = LOSSES[outcome]
        wide = g.pivot(index='building', columns='model', values=loss)
        for model, reference in pairs:
            diff = wide[reference]-wide[model]
            draws = rng.integers(0, len(diff), size=(5000, len(diff)))
            lo, hi = np.quantile(diff.to_numpy()[draws].mean(axis=1), [.025, .975])
            rows.append(dict(outcome=outcome, loss=loss, model=model, reference=reference,
                reference_loss=wide[reference].mean(), model_loss=wide[model].mean(),
                improvement=diff.mean(), relative_improvement_pct=100*diff.mean()/wide[reference].mean(),
                lo=lo, hi=hi, better_buildings=int((diff>0).sum()), buildings=len(diff),
                worst_improvement=diff.min(), best_improvement=diff.max()))
    return pd.DataFrame(rows)


def main():
    plan = json.loads((OUT/'PLAN.json').read_text(encoding='utf-8'))
    assert plan['models'] == MODELS and plan['primary_losses'] == LOSSES
    d = load_data()
    d.to_csv(OUT/'INPUT_RECORDS.csv.gz', index=False, encoding='utf-8')
    support, predictions, coefficients, folds = [], [], [], []
    for outcome in LOSSES:
        data = d[d[outcome].notna()].copy()
        support.append(dict(outcome=outcome, records=len(data), images=data.image_id.nunique(),
            buildings=data.building.nunique(), workers=data.worker_id.nunique(), missing_records=len(d)-len(data)))
        for building in sorted(data.building.unique()):
            train, test = data[data.building.ne(building)], data[data.building.eq(building)]
            assert set(train.image_id).isdisjoint(test.image_id)
            unseen = ~test.worker_id.isin(train.worker_id)
            folds.append(dict(outcome=outcome, building=building, train_records=len(train),
                test_records=len(test), test_images=test.image_id.nunique(),
                unseen_worker_records=int(unseen.sum()), unseen_workers=test.loc[unseen,'worker_id'].nunique()))
            for model in MODELS:
                pred, raw, beta = fit_predict(train, test, outcome, model)
                part = test[['object_id', 'image_id', 'building', 'worker_id', 'source', 'difficulty']].copy()
                part['outcome'], part['model'] = outcome, model
                part['observed'], part['prediction'], part['raw_prediction'] = test[outcome], pred, raw
                predictions.append(part)
                coefficients.extend(dict(outcome=outcome, building=building, model=model,
                    feature=k, coefficient=v) for k,v in beta.items() if not k.startswith('worker_id:'))
        print(outcome, support[-1], flush=True)
    p = losses(pd.concat(predictions, ignore_index=True))
    assert not p.duplicated(['object_id','outcome','model']).any()
    images, buildings, summary = aggregate(p)
    p.to_csv(OUT/'OOF_PREDICTIONS.csv.gz', index=False, encoding='utf-8')
    for name, frame in [('SUPPORT',pd.DataFrame(support)), ('FOLD_SUPPORT',pd.DataFrame(folds)),
        ('COEFFICIENTS',pd.DataFrame(coefficients)), ('IMAGE_LOSS',images), ('BUILDING_LOSS',buildings),
        ('SUMMARY',summary), ('COMPARISONS',comparisons(buildings)),
        ('SOURCE_SUMMARY',aggregate(p,['source'])[2]), ('GRADE_SUMMARY',aggregate(p,['difficulty'])[2])]:
        frame.to_csv(OUT/(name+'.csv'), index=False, encoding='utf-8')
    d.groupby(['source','time_status'],dropna=False).size().rename('records').to_csv(OUT/'TIME_SUPPORT.csv',encoding='utf-8')
    d.groupby(['worker_id','building']).size().rename('records').to_csv(OUT/'WORKER_BUILDING_SUPPORT.csv',encoding='utf-8')
    checks = dict(records=len(d), images=d.image_id.nunique(), buildings=d.building.nunique(),
        workers=d.worker_id.nunique(), all_unique=True, same_reference_target=True,
        same_support_all_models=True, no_heldout_building_in_training=True,
        missing_or_nonfinite_predictions=int((~np.isfinite(p.prediction)).sum()),
        unseen_worker_test_records=pd.DataFrame(folds).groupby('outcome').unseen_worker_records.sum().to_dict(),
        prediction_rows=len(p), official_labels_changed=False, scoring_or_fusion_runs=0)
    assert checks['missing_or_nonfinite_predictions']==0
    (OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
