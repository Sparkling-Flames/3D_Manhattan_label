#!/usr/bin/env python3
"""Read-only, fixed-prediction influence audit of nested LOBO worker profiles.

This is NOT a worker-removal/refit experiment, eligibility decision, hypothesis
significance test, or a new model search. It retains all 24 workers in targets
and training and only partitions the already frozen outer prediction losses.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd

DEFAULT_ROOT = Path(__file__).resolve().parent / 'source'

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, default=DEFAULT_ROOT)
    p.add_argument('--out', type=Path, default=Path(__file__).resolve().parent / 'results')
    args = p.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    src = args.source
    paths = [src / 'results/nested_prediction_cells.csv',
             src / 'results/nested_method_choices.csv',
             src / 'results/nested_summary.csv'] + [src / f'inputs/matrix_{pol}_iou.csv' for pol in ['original', 'revised_where_available']]
    fingerprints = {str(q.relative_to(src)): hashlib.sha256(q.read_bytes()).hexdigest() for q in paths}
    cells = pd.read_csv(paths[0])
    choices = pd.read_csv(paths[1])
    reported = pd.read_csv(paths[2]).set_index('policy')
    assert not cells.duplicated(['policy', 'image', 'worker']).any()
    known = []
    for pol in ['original', 'revised_where_available']:
        m = pd.read_csv(src / f'inputs/matrix_{pol}_iou.csv')
        workers = list(m.columns[2:])
        assert len(workers) == 24 and len(m) == 10 and m.building.nunique() == 8
        rr = m[workers].sub(m[workers].mean(axis=1), axis=0)
        rr['image'] = m.image
        rr['building'] = m.building
        rr['policy'] = pol
        known.append(rr.melt(id_vars=['policy', 'image', 'building'], var_name='worker', value_name='independently_centered_target'))
    known = pd.concat(known, ignore_index=True)
    cells = cells.merge(known, validate='one_to_one', on=['policy', 'image', 'worker'])
    assert len(cells) == 480
    center_error = float(abs(cells.centered_target - cells.independently_centered_target).max())
    assert center_error < 1e-12
    cells['baseline_sqerror'] = cells.centered_target ** 2
    cells['model_sqerror'] = (cells.centered_target - cells.prediction) ** 2
    cells['signed_gain'] = cells.baseline_sqerror - cells.model_sqerror
    image_n = cells.groupby(['policy', 'building']).image.transform('nunique')
    cells['image_n_in_building'] = image_n
    # Factor 1/8 and 1/24 cancels in each error ratio; each image gets 1/n_b.
    cells['building_equal_baseline_mass'] = cells.baseline_sqerror / image_n
    cells['building_equal_model_mass'] = cells.model_sqerror / image_n
    cells['building_equal_gain_mass'] = cells.signed_gain / image_n
    cell_fields = ['baseline_sqerror', 'model_sqerror', 'signed_gain', 'building_equal_baseline_mass', 'building_equal_model_mass', 'building_equal_gain_mass']
    workers = cells.groupby(['policy', 'worker'])[cell_fields].sum().reset_index()
    workers['pooled_relative_improvement'] = workers.signed_gain / workers.baseline_sqerror
    workers['building_equal_relative_improvement'] = workers.building_equal_gain_mass / workers.building_equal_baseline_mass
    workers['pooled_improved'] = workers.signed_gain > 0
    workers['building_equal_improved'] = workers.building_equal_gain_mass > 0
    totals = workers.groupby('policy')[cell_fields].sum()
    workers['share_of_total_signed_gain'] = workers.apply(lambda r: r.signed_gain / totals.loc[r.policy, 'signed_gain'], axis=1)
    workers['share_of_total_building_equal_gain'] = workers.apply(lambda r: r.building_equal_gain_mass / totals.loc[r.policy, 'building_equal_gain_mass'], axis=1)
    worker_buildings = cells.groupby(['policy', 'worker', 'building'])[cell_fields].sum().reset_index()
    worker_buildings['improved'] = worker_buildings.signed_gain > 0
    building = cells.groupby(['policy', 'building'])[cell_fields].sum().reset_index()
    building['pooled_relative_improvement'] = building.signed_gain / building.baseline_sqerror
    building['image_n'] = [int(cells[(cells.policy == r.policy) & (cells.building == r.building)].image.nunique()) for _, r in building.iterrows()]
    merged = building.merge(choices, left_on=['policy', 'building'], right_on=['policy', 'target'], validate='one_to_one')
    report_errors = {
        'outer_baseline_sse_max_abs_error': float(abs(merged.baseline_sqerror - merged.baseline_sse).max()),
        'outer_test_sse_max_abs_error': float(abs(merged.model_sqerror - merged.test_sse).max()),
    }
    assert max(report_errors.values()) < 1e-12
    summary = []
    exclusions = []
    for pol, x in cells.groupby('policy'):
        w = workers[workers.policy == pol]
        full = 1 - x.model_sqerror.sum() / x.baseline_sqerror.sum()
        beq = 1 - x.building_equal_model_mass.sum() / x.building_equal_baseline_mass.sum()
        assert abs(full - reported.loc[pol, 'pooled_relative_improvement']) < 1e-12
        assert abs(beq - reported.loc[pol, 'building_equal_relative_improvement']) < 1e-12
        summary.append(dict(policy=pol, workers=24, images=10, buildings=8,
            pooled_relative_improvement=full, building_equal_relative_improvement=beq,
            workers_with_pooled_improvement=int(w.pooled_improved.sum()),
            workers_with_building_equal_improvement=int(w.building_equal_improved.sum()),
            buildings_with_improvement=int((building[building.policy == pol].signed_gain > 0).sum()),
            p017_share_of_signed_gain=float(w[w.worker == 'P017'].share_of_total_signed_gain.iloc[0]),
            p017_share_of_building_equal_signed_gain=float(w[w.worker == 'P017'].share_of_total_building_equal_gain.iloc[0])))
        for ex in [[], ['P017'], ['P002', 'P017']]:
            z = x[~x.worker.isin(ex)]
            exclusions.append(dict(policy=pol, scoring_partition_excludes='|'.join(ex) or '(none)',
                evaluated_workers=z.worker.nunique(), refit=False, recentered=False,
                pooled_relative_improvement=1-z.model_sqerror.sum()/z.baseline_sqerror.sum(),
                building_equal_relative_improvement=1-z.building_equal_model_mass.sum()/z.building_equal_baseline_mass.sum()))
    summary = pd.DataFrame(summary)
    exclusions = pd.DataFrame(exclusions)
    cells.to_csv(out / 'fixed_outer_prediction_loss_cells.csv', index=False)
    workers.to_csv(out / 'per_worker_influence.csv', index=False)
    worker_buildings.to_csv(out / 'per_worker_per_building.csv', index=False)
    building.to_csv(out / 'per_building_influence.csv', index=False)
    summary.to_csv(out / 'summary.csv', index=False)
    exclusions.to_csv(out / 'fixed_prediction_scoring_partitions.csv', index=False)
    pivot = workers.pivot(index='worker', columns='policy', values=['signed_gain', 'pooled_improved', 'building_equal_gain_mass', 'building_equal_improved'])
    pivot.columns = ['__'.join(col) for col in pivot.columns]
    pivot.to_csv(out / 'all24_direction_comparison.csv')
    audit = dict(input_sha256=fingerprints, centered_target_max_abs_error=center_error,
        prediction_count=len(cells), no_production_code_imports=True, no_refits=True,
        no_eligibility_changes=True, no_remote_or_original_input_writes=True,
        **report_errors,
        interpretation='Shares are signed arithmetic loss decompositions, not causal contribution or independent significance. Scoring partitions retain the original 24-worker centering and trained predictions.')
    (out / 'audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False)+'\n')
    print(summary.to_string(index=False))
    print('\nFIXED-PREDICTION SCORING PARTITIONS\n'+exclusions.to_string(index=False))
    print('\nAUDIT\n'+json.dumps(audit, indent=2))

if __name__ == '__main__':
    main()
