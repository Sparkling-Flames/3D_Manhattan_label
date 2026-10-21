"""Original-response versus fused-geometry similarity on identical swaps.

Only one-person swaps; distances are conditional on joint valid cyclic matches.
Different counts and incomplete/ambiguous cases stay separately observable.
"""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import sys, json, gzip, os
import numpy as np, pandas as pd
from shapely.geometry import Polygon
OUT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('HOHONET_REPO', OUT.parents[2] / 'hohonet'))
sys.path[:0] = ['/tmp/hohonet_deps', str(ROOT / 'research/workers/personnel_interchangeability_followup_20261020/audit_corner')]
from corner_distance import corner_compare, project
from analyze import aggregate, csv

def read(p):
    return json.load(_open_data(p, 'rt'))

def main():
    pools = {p['pool_id']: p for p in read(ROOT / 'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz')['images']}
    d = _read_csv(OUT / 'SWAP_EVENTS.csv.gz')
    d = d[(d.n == 5) & (d.m == 1)].copy()
    rows = []
    for _, e in d.iterrows():
        p = pools[e.pool_id]
        by = {r['worker_id']: r for r in p['records']}
        raw = {}
        for arm in 'ABC':
            w = json.loads(e[arm + '_block'])[0]
            r = by[w]
            pts = np.asarray(r['points'])
            floor = project(pts)[0][:, [0, 2]]
            raw[arm] = dict(pool_id=e.pool_id, geometry=dict(points=pts.tolist(), footprint=floor.tolist()), complete_evaluable=bool(len(pts) >= 8 and Polygon(floor).is_valid))
        out = e.to_dict()
        for arm, name in [('B', 'within'), ('C', 'cross')]:
            m, _ = corner_compare(raw['A'], raw[arm])
            for k in ['status', 'same_count', 'bev_mean_h', 'top_mean_h', 'angle_deg']:
                out['raw_' + name + '_' + k] = m.get(k)
        rows.append(out)
    z = pd.DataFrame(rows)
    joint = z.raw_within_status.eq('unique_cyclic_candidate') & z.raw_cross_status.eq('unique_cyclic_candidate')
    z['raw_joint_distance'] = joint.astype(float)
    for arm in ['within', 'cross']:
        z['raw_' + arm + '_distance_common'] = z['raw_' + arm + '_bev_mean_h'].where(joint)
        z['raw_' + arm + '_same_count_rate'] = z['raw_' + arm + '_same_count'].astype(float)
        z['raw_' + arm + '_different_count'] = z['raw_' + arm + '_status'].eq('different_corner_count').astype(float)
    csv('RAW_SWAP_COMPARISONS.csv.gz', z)
    sm, im, bm = aggregate(z, ['condition', 'layer', 'scope_comparable', 'design', 'tier', 'outgoing_class', 'incoming_class'], ['raw_joint_distance', 'raw_within_distance_common', 'raw_cross_distance_common', 'raw_within_same_count_rate', 'raw_cross_same_count_rate', 'within_distance_common', 'cross_distance_common'] if 'within_distance_common' in z else ['raw_joint_distance', 'raw_within_distance_common', 'raw_cross_distance_common', 'raw_within_same_count_rate', 'raw_cross_same_count_rate'])
    csv('RAW_SWAP_SUMMARY.csv', sm)
    csv('RAW_SWAP_BUILDINGS.csv', bm)
if __name__ == '__main__':
    main()
