"""Postprocess saved nested requests and export case labels; no additional fusion."""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import sys, json, gzip
import pandas as pd
import numpy as np
P = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(P / 'native_teams'))
import analyze
d = _read_csv(P / 'native_teams/SWAP_EVENTS.csv.gz')
z = d[(d.condition == 'manual') & (d.layer == 'ordinary_manual') & d.scope_comparable & (d.design == 'capacity_random') & (d.tier == 'primary_coarse_class') & (d.m == 1)].copy()
sizes = {3, 5, 6, 7, 9, 13}
paths = z.groupby(['path_id', 'image']).n.apply(lambda v: set(v) == sizes)
good = set(paths[paths].index)
z = z[[tuple(r) in good for r in z[['path_id', 'image']].to_numpy()]].copy()
z['both_scored'] = (z.B_B8L2.notna() & z.C_B8L2.notna()).astype(float)
keys = ['outgoing_class', 'incoming_class', 'n']
s, im, b = analyze.aggregate(z, keys, ['net_B8L2', 'net_D10', 'both_scored'])
for n, t in [('NESTED_COUNT_SUMMARY.csv', s), ('NESTED_COUNT_BUILDINGS.csv', b)]:
    _write_csv(t, P / 'native_teams' / n, index=False)
print(s[['outgoing_class', 'incoming_class', 'n', 'events', 'images', 'buildings', 'net_B8L2', 'both_scored']].to_string(index=False))
import os
repo = Path(os.environ['HOHONET_REPO'])
labs = _read_csv(repo / 'research/workers/personnel_taxonomy_20261021/labels/lobo_labels.csv')
cases = []
for f in sorted((P / 'case_evidence').glob('*.json.gz')):
    obj = json.load(_open_data(f, 'rt'))
    if not isinstance(obj, list):
        continue
    for e in obj:
        if not isinstance(e, dict) or 'team' not in e:
            continue
        t = e['team']
        meta = e['meta']
        for r in e['records']:
            l = labs[(labs.condition == meta['condition']) & (labs.heldout_building == meta['building']) & (labs.worker_id == r['worker_id'])]
            l = l.iloc[0].to_dict() if len(l) else {}
            cases.append(dict(case_id=e['case_id'], image=meta['image'], pool_id=t['pool_id'], team_key=t['team_key'], arm=e.get('arm', e.get('policy', 'all')), worker_id=r['worker_id'], object_id=r['object_id'], origin=r['origin'], primary_coarse_class=l.get('primary_coarse_class'), primary_fine_class=l.get('primary_fine_class'), label_version=l.get('label_version'), heldout_building=meta['building'], reference_id=t['reference_id'], reference_version=t['reference_version']))
_write_csv(pd.DataFrame(cases), P / 'case_evidence/CASE_MEMBER_LABELS.csv', index=False)
s = _read_csv(P / 'native_teams/SWAP_EVENTS.csv.gz')
a = _read_csv(P / 'native_teams/SELECTION_RESULTS.csv.gz')
x = s.groupby(['condition', 'layer', 'scope_comparable', 'design', 'tier', 'n', 'm'], dropna=False).agg(events=('event_id', 'size'), images=('image', 'nunique'), buildings=('building', 'nunique'), paths=('path_id', 'nunique'), scored_B=('B_B8L2', 'count'), scored_C=('C_B8L2', 'count')).reset_index()
x['family'] = 'exact_swaps'
y = a.groupby(['condition', 'layer', 'scope_comparable', 'domain', 'policy', 'n'], dropna=False).agg(events=('team_key', 'size'), images=('target_image', 'nunique'), buildings=('building', 'nunique'), distinct_teams=('team_key', 'nunique'), scored=('B8L2', 'count')).reset_index()
y['family'] = 'selection'
_write_csv(pd.concat([x, y], ignore_index=True), P / 'native_teams/SEARCH_SUMMARY.csv', index=False)
