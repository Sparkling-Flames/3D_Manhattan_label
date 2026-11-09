"""Offline reproduction of the 16 focal estimates and their descriptive intervals.

Uses only the supplied minimal-field response table. It does not repeat raw
source linkage or establish consent for releasing any source exports.
Run: python reproduce_reported_estimates.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[3] / "research/difficulty/participant_feedback_20261109"
R = BASE / 'results'
raw = pd.read_csv(R / 'difficulty_geometry_analysis_records.csv')
expected = pd.read_csv(R / 'difficulty_association_summary.csv')
seed = 20261109
focal = [('occlusion', 'simplified'), ('occlusion', 'turn_deficit'),
         ('occlusion', 'omission'), ('seam', 'matched_boundary_abs_deg')]


def interval(frame, cluster):
    totals = frame.groupby(cluster)['difference'].agg(['sum', 'count'])
    rng = np.random.default_rng(seed)
    indices = rng.integers(len(totals), size=(4000, len(totals)))
    boot = (totals['sum'].to_numpy()[indices].sum(axis=1) /
            totals['count'].to_numpy()[indices].sum(axis=1))
    return np.quantile(boot, [.025, .975])


checks = []
for condition, required_n in [('manual', 1016), ('semi', 456)]:
    d = raw[(raw.condition == condition) & (raw.scene_route == 'ordinary')]
    assert len(d) == required_n
    for factor, metric in focal:
        z = d.dropna(subset=[metric]).copy()
        image_rows = []
        for (image, target), group in z.groupby(['image_id', 'reference_id'], dropna=False):
            if group[factor].nunique() != 2:
                continue
            difference = (group.loc[group[factor] == 1, metric].mean() -
                          group.loc[group[factor] == 0, metric].mean())
            image_rows.append({'image': image, 'target': target,
                               'building': group.building_id.iloc[0],
                               'difference': difference})
        images = pd.DataFrame(image_rows)
        z['centered'] = z[metric] - z.groupby(['image_id', 'reference_id'], dropna=False)[metric].transform('mean')
        person_rows = []
        for (person, building), group in z.groupby(['worker_id', 'building_id']):
            if group[factor].nunique() != 2:
                continue
            difference = (group.loc[group[factor] == 1, 'centered'].mean() -
                          group.loc[group[factor] == 0, 'centered'].mean())
            person_rows.append({'person': person, 'building': building, 'difference': difference})
        within = pd.DataFrame(person_rows)
        persons = within.groupby('person', as_index=False).difference.mean()
        for comparison, units, cluster in [
                ('same_image_target', images, 'building'),
                ('same_person_same_building_image_centered', persons, 'person')]:
            record = expected[(expected.condition == condition) &
                              (expected.scene_route == 'ordinary') &
                              (expected.factor == factor) & (expected.metric == metric) &
                              (expected.comparison == comparison)]
            assert len(record) == 1
            record = record.iloc[0]
            low, high = interval(units, cluster)
            observed = np.array([units.difference.mean(), low, high])
            saved = record[['mean_difference', 'lower_95', 'upper_95']].to_numpy(dtype=float)
            assert len(units) == int(record.units)
            np.testing.assert_allclose(observed, saved, rtol=0, atol=1e-11)
            checks.append({'condition': condition, 'factor': factor, 'outcome': metric,
                           'comparison': comparison, 'units': len(units),
                           'difference': observed[0], 'lower_95': low, 'upper_95': high})

semi = pd.read_csv(BASE / 'inputs/semi_linked_response_records.csv')
ordinary = semi[semi.formal_primary & semi.scene_route.eq('ordinary')]
assert len(ordinary) == 456 and int(ordinary.geometry_edited.sum()) == 349
known = ordinary[ordinary.confirmed_defect_opportunity]
assert len(known) == 138
states = known.error_specific_state.value_counts().to_dict()
assert states == {'unknown_after_edit': 85, 'localized_duplicate_removed_exact': 32,
                  'known_defect_retained_unchanged': 20,
                  'known_duplicate_retained_after_other_edits': 1}
result = {'all_checks_passed': True, 'focal_estimates_reproduced': len(checks),
          'seed': seed, 'resamples': 4000, 'estimates': checks,
          'ordinary_semi_responses': 456, 'known_defect_subset': 138, 'states': states,
          'scope': 'Minimal-field reproduction; does not recheck source geometry or acquisition.'}
(BASE / 'OFFLINE_REPRODUCTION.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'all_checks_passed': True, 'focal_estimates_reproduced': len(checks),
                  'known_defect_subset': len(known)}, indent=2))
