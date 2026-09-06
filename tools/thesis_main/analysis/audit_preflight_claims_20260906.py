"""Read-only scientific audit of preflight inputs; outputs stay in a separate audit directory."""
from pathlib import Path
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import itertools
import json
import math
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'analysis_results/preflight_20260906_v2'
OUT = ROOT / 'analysis_results/preflight_independent_audit_20260906_v1'


def finite_variance_projection(distance, k):
    """Orthogonal node/edge decomposition, independent of the source edge-pair formula."""
    n = len(distance)
    if not 2 <= k <= n or n < 4:
        raise ValueError('This audit projection requires 4 <= N and 2 <= k <= N.')
    mean = distance.sum() / (n * (n - 1))
    node = (distance.sum(axis=1) / (n - 1) - mean) * (n - 1) / (n - 2)
    edge = distance - mean - node[:, None] - node[None, :]
    edge_mse = np.mean(edge[np.triu_indices(n, 1)] ** 2)
    return (4 * (n - k) / (k * (n - 1)) * np.mean(node ** 2)
            + 2 * (n - k) * (n - k - 1) / (k * (k - 1) * (n - 2) * (n - 3)) * edge_mse)


def write(name, data):
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    frame.to_csv(OUT / name, index=False, encoding='utf-8-sig')


def prediction_scope_summary(predictions, scope):
    result = []
    for k, rows in predictions.groupby('k'):
        for condition, q in [('all', rows), *list(rows.groupby(['stage', 'condition']))]:
            by = q.groupby(['building', 'context', 'model']).squared_error.mean().unstack('model')
            full, simple = 'early_plus_corners_models', 'calibrated_early'
            delta = (by[full] - by[simple]).groupby(level='building').mean()
            result.append(dict(scope=scope, k=int(k), condition=str(condition), contexts=len(by),
                               buildings=len(delta), full_RMSE=math.sqrt(by[full].mean()),
                               calibrated_RMSE=math.sqrt(by[simple].mean()),
                               full_minus_calibrated_MSE_building_equal=delta.mean(),
                               buildings_full_better=int((delta < 0).sum())))
    return result


def metric_representation_probe():
    """Same rectangular room, with and without an extra collinear wall vertex."""
    from tools.thesis_main.analysis import audit_annotation_research_data_20260905 as old
    from lib.misc.panostretch import pano_connect_points
    def height(z, radius):
        return (np.arctan2(z, radius) / np.pi + .5) * 512 - .5
    pairs = [dict(x=x, y_ceiling=height(-1.4, 3*np.sqrt(2)), y_floor=height(1.6, 3*np.sqrt(2)))
             for x in [127.5, 383.5, 639.5, 895.5]]
    extra = sorted(pairs + [dict(x=255.5, y_ceiling=height(-1.4, 3), y_floor=height(1.6, 3))], key=lambda p:p['x'])
    def projected(p):
        curves = []
        for field, z in [('y_ceiling', -1.4), ('y_floor', 1.6)]:
            value = np.full(1024, np.nan)
            for a, b in zip(p, p[1:] + p[:1]):
                xy = pano_connect_points((a['x'], a[field]), (b['x'], b[field]), z=z)
                value[xy[:, 0].astype(int)] = xy[:, 1]
            assert np.isfinite(value).all()
            curves.append(np.rint(value).astype(int))
        return tuple(curves)
    return dict(role='synthetic_representation_check_not_human_data',
                physical_geometry='6m square room, centered camera; floor 1.6m below, ceiling 1.4m above; extra collinear vertex',
                point_pairs_before=4, point_pairs_after=5,
                linear_wall_band_distance=old._d_mask(old._dense_boundaries(pairs), old._dense_boundaries(extra)),
                spherical_wall_band_distance=old._d_mask(projected(pairs), projected(extra)))


def supplementary_checks():
    """Inspect archived row-selection ties and one locally available dual-head example."""
    from tools.thesis_main.analysis import audit_annotation_research_data_20260905 as old
    from tools.thesis_main.analysis.preflight_data_20260906 import sha
    predictions = pd.read_csv(SOURCE / 'early_prediction_all_draws.csv.gz')
    ties = []
    for row in pd.read_csv(SOURCE / 'early_prediction_worst_cases.csv').itertuples():
        group = predictions[(predictions.k == row.k) & (predictions.model == row.model) & (predictions.context == row.context)]
        tied = group[(group.underestimate - row.underestimate).abs() < 1e-10]
        ties.append(dict(k=row.k, model=row.model, context=row.context, near_tied_replicates=len(tied),
                         late_mode_values=tied.late_mode_unseen.nunique()))
    write('worst_case_tie_diagnostic.csv', ties)
    source = pd.read_csv(SOURCE / 'model_feature_source.csv').iloc[0]
    details = dict(archived_model_feature_contents_match=sha(ROOT / source['path']) == source.sha256,
                   model_feature_path_difference='Windows backslashes versus archived forward slashes')
    base = 'wc2JMjhGNzB_ec04ef10a0664e94878aa2d0f1720c2f'
    paths = [old.BI_ROOT / 'test' / mode / 'corners_1024x512' / (base + '.txt') for mode in ['enclosed', 'extended']]
    details['C05'] = dict(image=base, raw_paths=[str(p) for p in paths], both_present=all(p.is_file() for p in paths))
    if details['C05']['both_present']:
        pairs = [old.parse_alternating_corner_file(p)[1] for p in paths]
        details['C05'].update(corner_counts=[len(p) for p in pairs],
                              linear_wall_band_distance=old._d_mask(*[old._dense_boundaries(p) for p in pairs]),
                              role='raw_file_numeric_check_not_visual_or_human_adjudication')
    (OUT / 'supplementary_checks.json').write_text(json.dumps(details, indent=2) + '\n')


def main():
    from tools.thesis_main.analysis import preflight_data_20260906 as data
    from tools.thesis_main.analysis import preflight_statistics_20260906 as stats
    from tools.thesis_main.analysis import preflight_panels_20260906 as panels
    from tools.thesis_main.analysis import preflight_deliver_20260906 as deliver
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'metric_representation_check.json').write_text(json.dumps(metric_representation_probe(), indent=2)+'\n')
    supplementary_checks()
    comparisons, captured = [], {}

    def compare_save(name, rows):
        frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
        if name in ['raw_coordinate_audit.csv', 'record_inventory.csv', 'task_inventory.csv']:
            captured[name] = frame
        old = pd.read_csv(SOURCE / name)
        same_shape = frame.shape == old.shape and list(frame.columns) == list(old.columns)
        differences, text_equal = {}, True
        if same_shape:
            for col in frame:
                a, b = frame[col], old[col]
                if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
                    aa, bb = a.to_numpy(float), b.to_numpy(float)
                    if not np.array_equal(np.isnan(aa), np.isnan(bb)):
                        text_equal = False
                    good = np.isfinite(aa) & np.isfinite(bb)
                    delta = float(np.max(np.abs(aa[good] - bb[good]))) if good.any() else 0.
                    if delta > 1e-8:
                        differences[col] = delta
                else:
                    text_equal &= a.fillna('').astype(str).reset_index(drop=True).equals(b.fillna('').astype(str).reset_index(drop=True))
        comparisons.append(dict(file=name, rows=len(frame), same_shape=same_shape,
                                 nonnumeric_and_missing_equal=bool(text_equal), numeric_differences_over_1e_minus8=differences))

    # Imported functions otherwise overwrite the reviewed package. Route their writes to a comparison sink.
    data.OUT = OUT
    for module in [data, stats, panels, deliver]:
        module.save = compare_save
    print('Re-extracting all canonical raw coordinates...', flush=True)
    rows, groups, refs = data.load()
    raw_audit = captured['raw_coordinate_audit.csv']
    status_mismatch = raw_audit.second_strict_valid.astype(bool) != raw_audit.archived_strict_valid.astype(bool)
    write('geometry_status_differences.csv', raw_audit[status_mismatch])
    dense = [g for g in groups.values() if g['n'] >= 20]
    print('Checking exact finite variance and current20 panels...', flush=True)
    math_checks = []
    for g in dense:
        for k in range(2, g['n'] + 1):
            independent = finite_variance_projection(g['D'], k)
            original = stats.finite_var(stats.moments(g['D']), k)
            math_checks.append(dict(context=g['context'], k=k, difference=abs(independent-original)))
    assert max(r['difference'] for r in math_checks) < 1e-10
    write('independent_finite_variance.csv', math_checks)
    exact_panels = []
    complete = [g for g in groups.values() if set(data.CURRENT) <= set(g['workers'])]
    subsets = np.array(list(itertools.combinations(range(20), 15)))
    for stage, condition in sorted({(g['stage'], g['condition']) for g in complete}):
        gg = [g for g in complete if (g['stage'], g['condition']) == (stage, condition)]
        matrices = []
        for g in gg:
            ids = [list(g['workers']).index(w) for w in data.CURRENT]
            matrices.append(g['D'][np.ix_(ids, ids)])
        mean = np.mean(matrices, axis=0)
        fixed = np.var(mean[subsets[:, :, None], subsets[:, None, :]].sum((1, 2)) / 210)
        independent = sum(finite_variance_projection(d, 15) for d in matrices) / len(matrices)**2
        exact_panels.append(dict(stage=stage, condition=condition, contexts=len(gg), panels=len(subsets),
                                 enumerated_fixed_variance=fixed, independent_variance=independent, ratio=fixed/independent))
    write('independent_panel_enumeration.csv', exact_panels)
    published_panels = pd.read_csv(SOURCE / 'fixed_panel_vs_independent.csv')
    for row in exact_panels:
        reference = published_panels[(published_panels.k == 15) & (published_panels.stage == row['stage'])
                                     & (published_panels.condition == row['condition'])]
        assert len(reference) == 1
        assert np.isclose(row['enumerated_fixed_variance'], reference.iloc[0].exact_fixed_panel_variance, rtol=1e-9, atol=1e-12)
        assert np.isclose(row['ratio'], reference.iloc[0].exact_variance_ratio, rtol=1e-9, atol=1e-12)
    stats.check_math()
    stats.precision(groups)
    panels.support(groups, rows)
    panels.strata(rows, groups)
    deliver.resources(groups)
    deliver.em_demo()
    print('Raw, precision, support, composition, resource and EM checks complete.', flush=True)
    (OUT / 'REPRODUCTION_CHECKS.json').write_text(json.dumps(comparisons, indent=2)+'\n')

    original_predictions = pd.read_csv(SOURCE / 'early_prediction_all_draws.csv.gz')
    model = original_predictions[original_predictions.model == 'early_plus_corners_models']
    scope_rows = prediction_scope_summary(original_predictions, 'published_full_fit_all')
    proposals = pd.read_csv(data.SUB / 'proposal_fact.csv', keep_default_na=False)
    synthetic = set(proposals.loc[proposals.initialization_source_kind == 'trap_synthetic_disjoint_source', 'base_task_id'])
    # Explicitly report the exact source labels used in the sensitivity rather than guessing unobserved provenance.
    write('semi_initialization_roles.csv', proposals[['stage', 'base_task_id', 'initialization_source_kind', 'trap_family_set_json']])
    write('synthetic_exclusion_images.csv', [{'image': i} for i in sorted(synthetic)])
    scope_rows += prediction_scope_summary(original_predictions[~original_predictions.image.isin(synthetic)], 'published_fit_evaluate_without_synthetic')
    loss = original_predictions.groupby(['k', 'building', 'context', 'model']).squared_error.mean().unstack('model')
    loss['full_minus_calibrated'] = loss.early_plus_corners_models - loss.calibrated_early
    write('prediction_increment_by_building.csv', loss.groupby(['k', 'building']).full_minus_calibrated.agg(['mean', 'size']).reset_index())
    write('prediction_by_scope.csv', scope_rows)
    # Check known early/remaining identities before accepting the disjoint-target interpretation.
    assert all(set(r.early_workers.split(';')).isdisjoint(r.remaining_workers.split(';')) for r in model.itertuples())
    coverage = model.groupby(['k', 'context']).size()
    assert coverage.eq(stats.B).all()
    print('Rebuilding early-response rows and nested building-held-out models...', flush=True)
    early = stats.early_data(groups)
    full_prediction = stats.predict(early)
    for col in ['early_D', 'target', 'prediction', 'squared_error']:
        a = full_prediction.sort_values(['k','model','context','replicate'])[col].to_numpy()
        b = original_predictions.sort_values(['k','model','context','replicate'])[col].to_numpy()
        assert np.allclose(a, b, atol=1e-8, rtol=1e-7, equal_nan=True), col
    (OUT / 'REPRODUCTION_CHECKS.json').write_text(json.dumps(comparisons, indent=2)+'\n')
    print('All original nested predictions reproduced. Running the no-synthetic sensitivity...', flush=True)
    sensitivity_outputs = {}
    stats.save = lambda name, values: sensitivity_outputs.update({name: values if isinstance(values, pd.DataFrame) else pd.DataFrame(values)})
    reduced = stats.predict(early[~early.image.isin(synthetic)].copy())
    for name in ['early_prediction_baselines.csv', 'early_prediction_incremental_gain.csv']:
        write('without_synthetic_' + name, sensitivity_outputs[name])
    scope_rows += prediction_scope_summary(reduced, 'refit_without_synthetic')
    write('prediction_by_scope.csv', scope_rows)
    qa = dict(status='completed_with_interpretation_findings', raw_rows=len(rows), strict_rows=sum(r['valid'] for r in rows),
              strict_status_differences_from_archived=int(status_mismatch.sum()), dense_contexts=len(dense),
              dense_buildings=len({g['building'] for g in dense}), complete_current20_contexts=len(complete),
              mathematical_projection_max_error=max(r['difference'] for r in math_checks),
              synthetic_images_excluded=len(set(early.image) & synthetic), original_nested_prediction_rows=len(full_prediction),
              refit_without_synthetic_contexts=reduced.context.nunique(), replay_rows_are_not_independent_images=True,
              original_scientific_outputs_modified=False,
              synthetic_definition='initialization_source_kind == trap_synthetic_disjoint_source; natural errors retained')
    (OUT / 'QA.json').write_text(json.dumps(qa, indent=2)+'\n')
    print(json.dumps(qa), flush=True)


if __name__ == '__main__':
    main()
