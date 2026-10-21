"""One-source mean prediction on every supported adopted ordinary Manual pair.

This includes the ten two-view groups outside the old majority-history set.
It uses no fitted parameters and no target Q in features.
"""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from common import load, save_csv, METRICS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    _, q, _, _, _ = load(a.repo)
    q = q[q.condition.eq('manual') & q.layer.eq('ordinary')]
    p = _read_csv(a.out / 'tables/direct_pair_similarity.csv')
    p = p[p.condition.eq('manual') & p.origin.eq('all') & p.layer.eq('ordinary') & p.scope_comparable & ~p.substantive_conflict & p.n_common.ge(4)]
    cells = {i: z for i, z in q.groupby('image_id')}
    rows = []
    for metric in METRICS:
        for building, z in p[p.metric.eq(metric)].groupby('building_id'):
            train = q[q.training_allowed & q.building_id.ne(building)]
            pop = train.groupby('image_id')[metric].mean().mean()
            wm = train.groupby('worker_id')[metric].mean()
            n = train.groupby('image_id')[metric].transform('size')
            total = train.groupby('image_id')[metric].transform('sum')
            residual = (train[metric] - (total - train[metric]) / (n - 1)).where(n.gt(1))
            rel = residual.groupby(train.worker_id).mean()
            for r in z.itertuples():
                for source, target in [(r.image_a, r.image_b), (r.image_b, r.image_a)]:
                    s = cells[source]
                    t = cells[target]
                    source_mean = s[metric].mean()
                    target_mean = t[metric].mean()
                    target_peer = t.worker_id.map(rel).mean()
                    source_peer = s.worker_id.map(rel).mean()
                    rows.append(dict(pair_id=r.pair_id, building_id=building, group_ids=r.user_group_ids, metric=metric, source_image=source, target_image=target, source_code=s.image_code.iloc[0], target_code=t.image_code.iloc[0], source_n=len(s), target_n=len(t), source_mean=source_mean, actual=target_mean, external_image_mean=pop, outside_roster_mean=t.worker_id.map(wm).mean(), outside_peer_roster_mean=pop + target_peer, peer_adjusted_source=source_mean + target_peer - source_peer, target_history_coverage=t.worker_id.isin(wm.index).mean(), source_history_coverage=s.worker_id.isin(wm.index).mean(), source_object_ids='|'.join(sorted(s.object_id)), target_object_ids='|'.join(sorted(t.object_id)), source_reference_id=s.reference_id.iloc[0], target_reference_id=t.reference_id.iloc[0]))
    d = pd.DataFrame(rows)
    save_csv(d, a.out / 'tables/direct_mean_prediction_values.csv.gz')
    methods = ['external_image_mean', 'outside_roster_mean', 'outside_peer_roster_mean', 'source_mean', 'peer_adjusted_source']
    long = []
    for method in methods:
        x = d[['pair_id', 'building_id', 'group_ids', 'metric', 'source_image', 'target_image', 'actual']].copy()
        x['method'] = method
        x['predicted'] = d[method]
        x['absolute_error'] = (x.predicted - x.actual).abs()
        x['bad10'] = x.absolute_error.gt(10)
        long.append(x)
    l = pd.concat(long, ignore_index=True)
    target = l.groupby(['metric', 'method', 'building_id', 'target_image'], as_index=False).agg(mae=('absolute_error', 'mean'), bad10=('bad10', 'mean'), directions=('source_image', 'size'))
    building = target.groupby(['metric', 'method', 'building_id'], as_index=False).agg(mae=('mae', 'mean'), bad10=('bad10', 'mean'), images=('target_image', 'nunique'), directions=('directions', 'sum'))
    summary = building.groupby(['metric', 'method'], as_index=False).agg(mae=('mae', 'mean'), bad10=('bad10', 'mean'), images=('images', 'sum'), directions=('directions', 'sum'), buildings=('building_id', 'nunique'))
    for name, x in [('direct_mean_targets', target), ('direct_mean_buildings', building), ('direct_mean_summary', summary)]:
        save_csv(x, a.out / 'tables' / (name + '.csv'))
    print(summary.to_string(index=False))
if __name__ == '__main__':
    main()
