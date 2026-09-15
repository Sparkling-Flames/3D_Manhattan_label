"""Read the Pro ZIP directly; audit saved evidence without changing its outputs.

Model-family selectors and boundary sensitivity are post-return diagnostics,
not newly trained vision models or independent confirmatory experiments.
"""
import argparse
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[4]
BUNDLE = ROOT / 'analysis_results/image_portrait_20260914_v1'
PREFIX = 'repo/analysis_results/image_portrait_20260914_v1/cloud/image_links_after_review_20260915_v1/run_b02a97e2/'
OUT = BUNDLE / 'independent_synthesis_20260916'
TARGETS = ['candidate_v2', 'full_p_by_8', 'core10_p_by_19', 'late_quarter_new']


def select_family(data, family):
    selected = []
    for _, group in data[data.feature.str.startswith(family + '__')].groupby(['condition', 'target', 'building']):
        scores = group.groupby('feature').agg(score=('inner_loss', 'first'), n=('inner_n', 'first'))
        scores = scores[scores.n == scores.n.max()]
        best = scores.score.fillna(np.inf).sort_values(kind='stable').index[0]
        selected.append(group[group.feature.eq(best)])
    return pd.concat(selected, ignore_index=True)


def paired(frame):
    frame = frame.dropna(subset=['loss', 'loss_base'])
    delta = frame.loss - frame.loss_base
    by = frame.assign(delta=delta).groupby('building').delta.agg(['sum', 'count']).to_numpy()
    rng = np.random.default_rng(20260915)
    sample = by[rng.integers(len(by), size=(2000, len(by)))].sum(1)
    lo, hi = np.quantile(sample[:, 0] / sample[:, 1], [.025, .975])
    return dict(images=len(frame), buildings=len(by), loss=frame.loss.mean(), baseline_loss=frame.loss_base.mean(), delta=delta.mean(), lo=lo, hi=hi)


def boundary_checks(targets):
    rows = []
    for target in TARGETS[1:]:
        for horizon in ['all', 'n_ge_19']:
            q = targets[targets.condition.eq('manual') & targets.floor_boundary.isin(['partial', 'present'])].dropna(subset=[target])
            if horizon == 'n_ge_19':
                q = q[q.n_valid >= 19]
            for control in ['log_n', 'n_categories']:
                ncols = pd.DataFrame({'log_n': np.log(q.n_valid)}, index=q.index) if control == 'log_n' else pd.get_dummies(q.n_valid, drop_first=True, dtype=float)
                X = pd.concat([q.floor_boundary.eq('partial').astype(float).rename('partial'),
                               pd.Series(1., index=q.index, name='const'), ncols,
                               pd.get_dummies(q.scene_category, drop_first=True, dtype=float),
                               pd.get_dummies(q.building, drop_first=True, dtype=float)], axis=1)
                model = sm.OLS(q[target].to_numpy(float), X.to_numpy(float)).fit(cov_type='cluster', cov_kwds={'groups': q.building, 'use_correction': True})
                low, high = model.conf_int()[0]
                rows.append(dict(target=target, horizon=horizon, control=control, images=len(q), buildings=q.building.nunique(), partial_images=int(q.floor_boundary.eq('partial').sum()), coefficient=model.params[0], lo=low, hi=high, rank=np.linalg.matrix_rank(X.to_numpy(float)), columns=len(X.columns)))
    return pd.DataFrame(rows)


def camera_audit():
    old = pd.read_csv(BUNDLE / 'cloud/pro_exploration/v1_e086b2b9/D/pair_geometry_audit.csv')
    projection = json.loads((BUNDLE / 'models/da3/manifest.json').read_text(encoding='utf-8'))['projection']
    known = np.array([projection['camera_to_panorama'][face] for face in projection['order']])
    rows = []
    for row in old.itertuples():
        with np.load(BUNDLE / f'models/da3/multiview/{row.pair_id}.geometry.npz', allow_pickle=False) as z:
            assert z['image_ids'].tolist() == [row.image_a, row.image_b]
            ext = z['extrinsics']
        rotations = np.linalg.inv(ext[:, :, :3]) @ np.tile(known.transpose(0, 2, 1), (2, 1, 1))
        rotations = rotations.reshape(2, 6, 3, 3)
        maximum = 0.
        for capture in rotations:
            for a in range(6):
                for b in range(a + 1, 6):
                    cosine = (np.trace(capture[a].T @ capture[b]) - 1) / 2
                    maximum = max(maximum, float(np.degrees(np.arccos(np.clip(cosine, -1, 1)))))
        rows.append(dict(pair_id=row.pair_id, relation_eligible=row.relation_eligible, max_angle=maximum, archived_max_angle=row.max_same_capture_angle))
    result = pd.DataFrame(rows)
    result.to_csv(OUT / 'da3_camera_recheck.csv', index=False)
    eligible = result[result.relation_eligible]
    return dict(pairs=len(result), eligible=len(eligible), passing_20_degrees=int((eligible.max_angle <= 20).sum()), eligible_angle_min=float(eligible.max_angle.min()), eligible_angle_median=float(eligible.max_angle.median()), max_difference=float(np.max(np.abs(result.max_angle - result.archived_max_angle))))


def run(archive):
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        npzs = [n for n in z.namelist() if n.endswith('.npz')]
        for name in npzs:
            with np.load(io.BytesIO(z.read(name)), allow_pickle=False) as arrays:
                for key in arrays.files:
                    _ = arrays[key]
        def table(name):
            return pd.read_csv(io.BytesIO(z.read(PREFIX + name)), compression='gzip' if name.endswith('.gz') else None, low_memory=False)
        predictions = table('prediction/all_predictions.csv.gz')
        scores = table('prediction/score_summary.csv')
        targets = table('targets/per_image_versions_and_process.csv')
        pairs = table('prediction/paired_increment.csv')
        original_associations = table('A/adjusted_picture_associations.csv')
        files = len(z.namelist())
    keys = ['condition', 'target', 'feature', 'algorithm']
    assert not predictions.duplicated(keys + ['image_id']).any()
    mean = predictions.groupby(keys, as_index=False).loss.mean().merge(scores, on=keys, validate='one_to_one')
    score_delta = np.max(np.abs(mean.loss - mean.image_loss))
    assert score_delta < 1e-9
    valid = predictions.dropna(subset=['loss'])
    categorical = valid.target.isin(['grade_v1', 'candidate_v2'])
    probs = valid.loc[categorical, ['p_simple', 'p_medium', 'p_difficult']].to_numpy()
    truth = np.eye(3)[valid.loc[categorical, 'truth'].to_numpy(int)]
    classification_delta = np.max(np.abs(((probs - truth) ** 2).sum(1) - valid.loc[categorical, 'loss']))
    continuous = valid.loc[~categorical]
    continuous_delta = np.max(np.abs(np.abs(continuous.prediction - continuous.truth) - continuous.loss))
    assert max(classification_delta, continuous_delta) < 1e-9
    data = predictions[predictions.target.isin(TARGETS) & predictions.algorithm.isin(['ridge', 'baseline'])]
    selected = []
    for family in ['hohonet', 'bilayout', 'ulayout', 'da3', 'dinov3']:
        selected.append(select_family(data, family).assign(family=family))
    chosen = pd.concat(selected, ignore_index=True)
    chosen.to_csv(OUT / 'family_selected_predictions.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    results = []
    for (family, condition, target), q in chosen.groupby(['family', 'condition', 'target']):
        for baseline in ['constant', 'feedback_counts', 'feedback_all']:
            base = data[data.feature.eq(baseline) & data.condition.eq(condition) & data.target.eq(target)]
            joined = q.merge(base[['image_id', 'building', 'loss']], on=['image_id', 'building'], suffixes=('', '_base'), validate='one_to_one')
            results.append(dict(family=family, condition=condition, target=target, baseline=baseline, **paired(joined)))
    pd.DataFrame(results).to_csv(OUT / 'family_paired_summary.csv', index=False)
    fixed = []
    for (condition, target, feature), q in data[data.feature.str.startswith('da3__')].groupby(['condition', 'target', 'feature']):
        for baseline in ['constant', 'feedback_counts']:
            base = data[data.feature.eq(baseline) & data.condition.eq(condition) & data.target.eq(target)]
            joined = q.merge(base[['image_id', 'building', 'loss']], on=['image_id', 'building'], suffixes=('', '_base'), validate='one_to_one')
            fixed.append(dict(condition=condition, target=target, feature=feature, baseline=baseline, **paired(joined)))
    pd.DataFrame(fixed).to_csv(OUT / 'da3_fixed_layers.csv', index=False)
    reproduced = []
    for row in pairs.itertuples():
        new = predictions[predictions.condition.eq(row.condition) & predictions.target.eq(row.target) & predictions.feature.eq(row.new) & predictions.algorithm.eq('ridge')]
        base = predictions[predictions.condition.eq(row.condition) & predictions.target.eq(row.target) & predictions.feature.eq(row.baseline) & predictions.algorithm.isin(['ridge', 'baseline'])]
        check = paired(new.merge(base[['image_id', 'building', 'loss']], on=['image_id', 'building'], suffixes=('', '_base'), validate='one_to_one'))
        reproduced += [abs(check[k] - getattr(row, k)) for k in ['delta', 'lo', 'hi']]
    assert max(reproduced) < 1e-9
    boundary = boundary_checks(targets)
    boundary.to_csv(OUT / 'boundary_sensitivity.csv', index=False)
    compared = boundary[(boundary.horizon == 'all') & (boundary.control == 'log_n')].merge(original_associations[(original_associations.condition == 'manual') & (original_associations.trait == 'floor_boundary') & (original_associations.adjustment == 'n_scene_building')], on='target', suffixes=('', '_saved'))
    boundary_delta = np.max(np.abs(compared.coefficient - compared.coefficient_saved))
    assert boundary_delta < 1e-9
    x = targets[targets.condition.eq('manual') & targets.full_p_by_8.notna()]
    cross = pd.crosstab(x.scene_category, x.floor_boundary)
    cross.to_csv(OUT / 'boundary_scene_coverage.csv')
    audit = dict(schema='image_links_independent_audit_v1', archive=str(archive), zip_entries=files, readable_npz=len(npzs), prediction_rows=len(predictions), score_rows=len(scores), max_score_difference=float(score_delta), max_loss_recompute_difference=float(max(classification_delta, continuous_delta)), max_paired_interval_difference=float(max(reproduced)), max_boundary_coefficient_difference=float(boundary_delta), da3_cameras=camera_audit(), new_prediction_model_fits=0, boundary_regression_fits=len(boundary), new_visual_inference=0, new_human_adjudications=0, interpretations='New per-family selectors use saved inner loss only. No outer result selects a layer. Boundary sensitivities are retrospective diagnostics; small or rank-deficient controls limit interpretation. No source files changed.')
    (OUT / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    run(parser.parse_args().archive)
