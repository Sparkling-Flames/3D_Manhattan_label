"""Final fair risk comparison: add existing class information to the strongest simple baseline.

Fixed columns and regularization; not a search over taxonomy, thresholds or hyperparameters.
"""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
import argparse, json
from pathlib import Path
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from analyze import flat_records, features, hierarchy_weights, save

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path(__file__).parent)
    a = ap.parse_args()
    out = a.out
    d = flat_records(a.repo)
    pall = _read_csv(out / 'prediction_design.csv.gz')
    labels = _read_csv(a.repo / 'research/workers/personnel_taxonomy_20261021/labels/lobo_labels.csv')
    rows = []
    for outer in sorted(pall.building.unique()):
        p = pall if outer in set(pall[pall.budget.eq('majority')].building) else pall[pall.budget.eq('single_direct')].reset_index(drop=True)
        f = features(p, d, labels, outer, 'B8L2', {})
        for budget in ['majority', 'single_direct']:
            test = p.building.eq(outer) & (p.budget.isin(['majority', 'single_matched']) if budget == 'majority' else p.budget.eq('single_direct'))
            train = p.building.ne(outer) & p.budget.eq(budget) & p.training_allowed
            valid = f[['peer', 'theta']].notna().all(axis=1)
            test &= valid
            train &= valid
            if not test.any() or p[train].building.nunique() < 3:
                continue
            y = (f.loc[train, 'actual'] < 50).astype(int)
            w = hierarchy_weights(p[train])
            w = w / w.sum() * 1000
            r = p.loc[test, ['row_id']].copy()
            r['metric'] = 'B8L2'
            for own in [False, True]:
                cols = ['peer', 'theta', 'class_fine', 'class_coarse', 'class_fine_n', 'class_coarse_n', 'class_M00', 'class_M01', 'class_M10', 'class_M11']
                if own:
                    cols += ['own_surprise']
                imp = SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)
                xt = imp.fit_transform(f.loc[train, cols])
                xe = imp.transform(f.loc[test, cols])
                sc = StandardScaler().fit(xt, sample_weight=w)
                model = LogisticRegression(C=1, solver='lbfgs', max_iter=1000).fit(sc.transform(xt), y, sample_weight=w)
                r['p_low_basic_own_class' if own else 'p_low_basic_class'] = model.predict_proba(sc.transform(xe))[:, 1]
            rows.append(r)
        print('Class risk increment', outer, flush=True)
    new = pd.concat(rows)
    pred = _read_csv(out / 'prediction_rows.csv.gz')
    pred = pred.drop(columns=[c for c in ['p_low_basic_class', 'p_low_basic_own_class'] if c in pred])
    pred = pred.merge(new, on=['row_id', 'metric'], how='left', validate='one_to_one')
    save(pred, out / 'prediction_rows.csv.gz')
    path = out / 'LOWTAIL_EXTENSION.json'
    m = json.loads(path.read_text())
    m['final_fair_class_comparison'] = 'Add the fixed existing class-source residuals and class indicators directly to (P,theta), with/without own surprise. Same C=1, outer-building isolation and no tuning. This closes the comparison rather than selecting a new model family.'
    path.write_text(json.dumps(m, ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()
