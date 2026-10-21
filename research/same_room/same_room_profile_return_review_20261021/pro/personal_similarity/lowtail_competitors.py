"""Necessary strong simple risk baselines, added once after the fixed rich-model comparison.

This is an explicit extension, not retuning the Q models. No hyperparameter search.
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
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from analyze import flat_records, history_stats, hierarchy_weights, save, writej

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path(__file__).parent)
    a = ap.parse_args()
    out = a.out
    d = flat_records(a.repo)
    p = _read_csv(out / 'prediction_design.csv.gz')
    oof = _read_csv(out / 'heldout_information.csv.gz').set_index('row_id')
    base = oof.reindex(p.row_id)[['peer', 'own', 'peer_low', 'source_count', 'actual']].reset_index(drop=True)
    predictions = _read_csv(out / 'prediction_rows.csv.gz')
    new = []
    coefs = []
    for outer in sorted(p.building.unique()):
        f = base.copy()
        for b, g in p.groupby('building'):
            h = history_stats(d, {outer, b})
            theta = g.worker_id.map(h.theta)
            f.loc[g.index, 'theta'] = theta.to_numpy()
        f['calibrated_Q'] = f.peer + f.theta
        f['own_surprise'] = f.own - f.peer - f.theta
        for budget in ['majority', 'single_direct']:
            te = p.building.eq(outer) & (p.budget.isin(['majority', 'single_matched']) if budget == 'majority' else p.budget.eq(budget))
            tr = p.building.ne(outer) & p.budget.eq(budget) & p.training_allowed
            tr &= f[['peer', 'theta']].notna().all(axis=1)
            te &= f[['peer', 'theta']].notna().all(axis=1)
            if not te.any() or p[tr].building.nunique() < 3:
                continue
            w = hierarchy_weights(p[tr])
            w = w / w.sum() * 1000
            target = (f.loc[tr, 'actual'] < 50).astype(int)
            r = p.loc[te, ['row_id']].copy()
            r['metric'] = 'B8L2'
            feature_sets = {'p_low_basic': ['peer', 'theta'], 'p_low_calibrated_Q': ['calibrated_Q'], 'p_low_basic_peer_risk': ['peer', 'theta', 'peer_low'], 'p_low_basic_own': ['peer', 'theta', 'own_surprise']}
            for name, cols in feature_sets.items():
                sc = StandardScaler().fit(f.loc[tr, cols], sample_weight=w)
                model = LogisticRegression(C=1, solver='lbfgs', max_iter=1000).fit(sc.transform(f.loc[tr, cols]), target, sample_weight=w)
                r[name] = model.predict_proba(sc.transform(f.loc[te, cols]))[:, 1]
                coefs.append(dict(outer=outer, budget=budget, model=name, columns=cols, intercept=model.intercept_.tolist(), coef=model.coef_.tolist(), mean=sc.mean_.tolist(), scale=sc.scale_.tolist()))
            new.append(r)
    new = pd.concat(new)
    assert not new.duplicated(['row_id', 'metric']).any()
    for c in new.columns:
        if c.startswith('p_low_') and c in predictions:
            predictions = predictions.drop(columns=c)
    predictions = predictions.merge(new, on=['row_id', 'metric'], how='left', validate='one_to_one')
    save(predictions, out / 'prediction_rows.csv.gz')
    writej(out / 'lowtail_simple_parameters.json', coefs)
    writej(out / 'LOWTAIL_EXTENSION.json', dict(reason='The rich continuous risk model is not a sufficient strongest-baseline comparison. Add fixed simple public-plus-external, calibrated-Q, source-peer-risk and own-surprise logistic baselines once.', status='new explicit internal extension after initial risk results; no changes or tuning of Q regressors', hyperparameter_selection='none', outer_building_exclusion=True))
if __name__ == '__main__':
    main()
