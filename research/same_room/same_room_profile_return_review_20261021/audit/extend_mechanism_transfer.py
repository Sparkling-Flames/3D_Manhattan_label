"""New descriptive cross-view mechanism analysis of frozen exact swap events.
No new fusion, target selection, GT edits or taxonomy fitting.
"""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import argparse, json
import numpy as np, pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    d = _read_csv(a.source / 'native_teams/SWAP_EVENTS.csv.gz')
    rows = []
    for (path, n), g in d.groupby(['path_id', 'n'], sort=True):
        assert len(g) == 2
        x, y = g.sort_values('image').to_dict('records')
        r = {k: x[k] for k in ['pair_id', 'group_ids', 'condition', 'layer', 'scope_comparable', 'building', 'design', 'tier', 'outgoing_class', 'incoming_class', 'n', 'm', 'path_id']}
        assert all((x[k] == y[k] for k in ['core_workers', 'A_block', 'B_block', 'C_block', 'n', 'm']))
        r.update(image_a=x['image'], image_b=y['image'], history_Q_gap=x['block_history_Q_gap'])
        both = all((pd.notna(z[f'{arm}_B8L2']) for z in [x, y] for arm in ['B', 'C']))
        r['both_views_scored'] = int(both)
        for z, s in [(x, 'a'), (y, 'b')]:
            for v in ['B8L2', 'D10', 'nodes', 'dir', 'S_bottom_deg', 'Hmean', 'omission', 'extension']:
                r['delta_' + v + '_' + s] = z['C_' + v] - z['B_' + v]
        sign = lambda v: 0 if abs(v) < 1e-09 else int(np.sign(v))
        if both:
            qsign = sign(r['delta_B8L2_a']) * sign(r['delta_B8L2_b'])
            ns = [sign(r['delta_nodes_a']), sign(r['delta_nodes_b'])]
            r.update(Q_opposite=float(qsign < 0), Q_same_nonzero=float(qsign > 0), nodes_same_sign=float(ns[0] == ns[1]), nodes_both_zero=float(ns == [0, 0]), nodes_nonzero_any=float(ns != [0, 0]), nodes_same_nonzero=float(ns[0] == ns[1] and ns[0] != 0), Q_opposite_nodes_same=float(qsign < 0 and ns[0] == ns[1]), Q_opposite_nodes_both_zero=float(qsign < 0 and ns == [0, 0]), Q_opposite_nodes_same_nonzero=float(qsign < 0 and ns[0] == ns[1] and (ns[0] != 0)), dir_opposite=float(sign(r['delta_dir_a']) * sign(r['delta_dir_b']) < 0), Q_gap=abs(r['delta_B8L2_a'] - r['delta_B8L2_b']))
        rows.append(r)
    p = pd.DataFrame(rows)
    _write_csv(p, a.out / 'cross_view_mechanisms.csv', index=False)
    keys = ['condition', 'layer', 'scope_comparable', 'design', 'tier', 'outgoing_class', 'incoming_class', 'n', 'm']
    metrics = ['both_views_scored', 'Q_opposite', 'Q_same_nonzero', 'nodes_same_sign', 'nodes_both_zero', 'nodes_nonzero_any', 'nodes_same_nonzero', 'Q_opposite_nodes_same', 'Q_opposite_nodes_both_zero', 'Q_opposite_nodes_same_nonzero', 'dir_opposite', 'Q_gap']
    pair = p.groupby(keys + ['building', 'pair_id'], dropna=False)[metrics].mean().reset_index()
    b = pair.groupby(keys + ['building'], dropna=False)[metrics].mean().reset_index()
    s = b.groupby(keys, dropna=False)[metrics].mean().reset_index()
    count = p.groupby(keys, dropna=False).agg(exact_paths=('path_id', 'size'), direct_pairs=('pair_id', 'nunique'), buildings=('building', 'nunique'), scored_paths=('both_views_scored', 'sum')).reset_index()
    s = s.merge(count, on=keys)
    _write_csv(s, a.out / 'cross_view_mechanism_summary.csv', index=False)
    _write_csv(b, a.out / 'cross_view_mechanism_buildings.csv', index=False)
    (a.out / 'METHOD.json').write_text(json.dumps({'analysis': 'new descriptive mechanism cross-view comparison', 'source': 'frozen Pro exact SWAP_EVENTS', 'unit': 'one undirected pair per path and n', 'weighting': 'path within direct pair, direct pairs within building, equal buildings', 'failure': 'all paths retained with both_views_scored; mechanism rates conditional on both scored', 'zero_tolerance': 1e-09, 'node_count_is_not_semantic_structure': True, 'GT_changed': False, 'new_native_fusion_calls': 0}, indent=2))
    print(s[(s.condition == 'manual') & (s.layer == 'ordinary_manual') & s.scope_comparable & (s.design == 'capacity_random') & (s.tier == 'primary_coarse_class') & (s.n == 5) & (s.m == 1)].to_string(index=False))
if __name__ == '__main__':
    main()
