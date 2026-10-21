import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import argparse, gzip, json, hashlib
import numpy as np, pandas as pd

def load(p):
    return json.load(_open_data(p, 'rt', encoding='utf-8'))

def checkclose(a, b):
    if pd.isna(a) and (b is None or pd.isna(b)):
        return True
    return b is not None and np.isclose(a, b, rtol=1e-09, atol=1e-08)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    p = a.source
    idx = _read_csv(p / 'FILE_INDEX.csv')
    # Original hashes are checked separately against SOURCE_MAP and direct-file manifest.
    t = load(p / 'native_teams/TEAMS.json.gz')
    req = load(p / 'native_teams/REQUESTS.json.gz')
    assert len(req) == len(t) == 45552
    for r in req:
        z = t[r['team_key']]
        assert sorted(z['member_workers']) == r['workers'] and z['k'] == len(r['workers'])
    d = _read_csv(p / 'native_teams/SWAP_EVENTS.csv.gz')
    sel = _read_csv(p / 'native_teams/SELECTION_RESULTS.csv.gz')
    n = 0
    for r in d.to_dict('records'):
        for arm in 'ABC':
            z = t[r[arm + '_team_key']]
            assert json.loads(r[arm + '_workers']) == z['member_workers']
            assert z['reference_id'] == r['reference_id']
            for v in ['B8L2', 'D10', 'nodes', 'dir', 'S_bottom_deg', 'Hmean', 'omission', 'extension']:
                assert checkclose(r[arm + '_' + v], z.get(v)), (r['event_id'], arm, v)
            n += 1
    for r in sel.to_dict('records'):
        z = t[r['team_key']]
        assert sorted(json.loads(r['workers'])) == z['member_workers']
        assert z['reference_id'] == r['reference_id']
        for v in ['B8L2', 'D10', 'nodes', 'dir', 'S_bottom_deg', 'Hmean', 'omission', 'extension']:
            assert checkclose(r[v], z.get(v)), (r['team_key'], v)
        n += 1
    result = {'original_index_files': len(idx), 'unique_teams_with_exact_requests': len(t), 'swap_rows': len(d), 'selection_rows': len(sel), 'team_event_joins_checked': n, 'all_scalar_member_reference_checks_passed': True, 'native_fusion_all_replayed': False}
    pred = _read_csv(p / 'personal_similarity/main_prediction_rows_wide.csv.gz')
    expected = _read_csv(p / 'personal_similarity/prediction_summary.csv')
    checks = []
    for metric in ['B8L2', 'D10']:
        for budget, stage in [('single_direct', 'single'), ('single_matched', 'single'), ('majority', 'minimum_majority'), ('majority', 'maximum_history')]:
            q = pred[(pred.metric == metric) & (pred.budget == budget)].copy()
            if budget == 'majority':
                q = q[q.m.eq(q.N // 2 + 1 if stage == 'minimum_majority' else q.N - 1)]
            for method in ['external_abs', 'own_source', 'public_source', 'public_external', 'public_external_halfown', 'public_external_halfclass']:
                e = expected[(expected.metric == metric) & (expected.budget == budget) & (expected.stage == stage) & (expected.method == method)]
                if q.empty or e.empty:
                    continue
                x = q.assign(ae=(q[method] - q.actual).abs())
                v = x.groupby(['building', 'target_image', 'group_id', 'worker_id', 'm']).ae.mean().groupby(['building', 'target_image', 'group_id', 'm']).mean().groupby(['building', 'target_image']).mean().groupby('building').mean().mean()
                ev = float(e.mae.iloc[0])
                assert abs(v - ev) < 2e-05, (metric, budget, stage, method, v, ev)
                checks.append(dict(metric=metric, budget=budget, stage=stage, method=method, recomputed_mae=v, reported_mae=ev, difference=v - ev))
    _write_csv(pd.DataFrame(checks), a.out / 'prediction_mae_recheck.csv', index=False)
    result['prediction_mae_cells_checked'] = len(checks)
    (a.out / 'SAVED_EVIDENCE_CHECKS.json').write_text(json.dumps(result, indent=2))
    print(result)
if __name__ == '__main__':
    main()
