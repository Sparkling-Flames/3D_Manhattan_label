"""Recompute saved odd/even contrasts and full-pool status from per-k curves."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument('--input-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
curves = pd.read_csv(args.input_root / 'analysis_precision26/results_stage2/NATURAL_CURVES.csv.gz')
contrasts = pd.read_csv(args.input_root / 'analysis_shape26/results/PARITY_LOCAL_CONTRAST_PER_IMAGE.csv.gz')
lookup = curves.set_index(['pool_id', 'cohort', 'k'])
errors = []
for row in contrasts.itertuples():
    if pd.isna(row.common_odd_k):
        continue
    ks = [int(float(k)) for k in str(row.common_odd_k).split('|')]
    values = [lookup.loc[(row.pool_id, row.cohort, k), row.metric]
              - 0.5 * (lookup.loc[(row.pool_id, row.cohort, k - 1), row.metric]
                       + lookup.loc[(row.pool_id, row.cohort, k + 1), row.metric]) for k in ks]
    errors.append(abs(np.mean(values) - row.estimate))
assert errors and max(errors) < 1e-9
full = curves[(curves.cohort == 'pooled256') & (curves.k == curves.pool_n)]
assert not full.pool_id.duplicated().any()
status = full.groupby('layer').agg(
    images=('pool_id', 'size'), scoreable=('Q_mean', 'count'),
    actual_failure=('actual_consensus_failure_rate', 'sum'),
    geometry_unscoreable=('output_unscoreable_rate', 'sum')).reset_index()
status.to_csv(args.output / 'FULL_POOL_STATUS_CHECK.csv', index=False)
result = {'parity_per_image_records_recalculated': len(errors),
          'maximum_absolute_difference': float(max(errors)), 'full_pool': status.to_dict('records')}
(args.output / 'ROOT_CHECK.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=True))
