"""Transparent image/building weighted summaries of the saved exact events."""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import json, gzip
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
OUT = Path(__file__).resolve().parent
RNG = np.random.default_rng(2026102144)

def csv(name, d):
    _write_csv(d, OUT / name, index=False, compression={'method': 'gzip', 'mtime': 0} if name.endswith('.gz') else None)

def aggregate(d, keys, metrics, image='image'):
    a = d.groupby(keys + ['building', image], dropna=False)[metrics].mean().reset_index()
    b = a.groupby(keys + ['building'], dropna=False)[metrics].mean().reset_index()
    rows = []
    for key, g in d.groupby(keys, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        v = b
        for k, x in zip(keys, key):
            v = v[v[k].eq(x) if pd.notna(x) else v[k].isna()]
        r = dict(zip(keys, key))
        r.update(events=len(g), images=g[image].nunique(), buildings=g.building.nunique())
        for m in metrics:
            z = v[m].dropna().to_numpy()
            r[m] = z.mean() if len(z) else np.nan
            r[m + '_finite_events'] = g[m].notna().sum()
            if m in ['net_B8L2', 'delta_Q', 'log_activity_ratio', 'source_choice_minus_class_choice'] and len(z) >= 3:
                boot = RNG.choice(z, (2000, len(z))).mean(axis=1)
                r[m + '_lo'], r[m + '_hi'] = np.quantile(boot, [0.025, 0.975])
        rows.append(r)
    return (pd.DataFrame(rows), a, b)

def main():
    d = _read_csv(OUT / 'SWAP_EVENTS.csv.gz')
    d['complete_B'] = d.B_complete_evaluable.astype(float)
    d['complete_C'] = d.C_complete_evaluable.astype(float)
    d['both_scored'] = d.B_B8L2.notna() & d.C_B8L2.notna()
    d['loss_over5'] = (d.net_B8L2 < -5).astype(float).where(d.both_scored)
    d['gain_over5'] = (d.net_B8L2 > 5).astype(float).where(d.both_scored)
    joint = d.within_status.eq('unique_cyclic_candidate') & d.cross_status.eq('unique_cyclic_candidate')
    d['joint_distance'] = joint.astype(float)
    for arm in ['within', 'cross']:
        d[arm + '_distance_common'] = d[arm + '_bev_mean_h'].where(joint)
        d[arm + '_different_count'] = d[arm + '_status'].eq('different_corner_count').astype(float)
        d[arm + '_valid_distance'] = d[arm + '_status'].eq('unique_cyclic_candidate').astype(float)
    keys = ['condition', 'layer', 'scope_comparable', 'design', 'tier', 'outgoing_class', 'incoming_class', 'n', 'm']
    metrics = ['net_B8L2', 'net_D10', 'net_nodes', 'net_omission', 'net_extension', 'net_ref_node_recall_5', 'block_history_Q_gap', 'complete_B', 'complete_C', 'both_scored', 'loss_over5', 'gain_over5', 'within_abs_Q', 'cross_abs_Q', 'joint_distance', 'within_distance_common', 'cross_distance_common', 'within_different_count', 'cross_different_count', 'within_valid_distance', 'cross_valid_distance']
    s, a, b = aggregate(d, keys, metrics)
    csv('SWAP_SUMMARY.csv', s)
    csv('SWAP_BY_IMAGE.csv.gz', a)
    csv('SWAP_BY_BUILDING.csv', b)
    transfers = []
    for _, g in d.groupby(['path_id', 'n']):
        if len(g) != 2:
            raise ValueError('Expected exactly two declared views per exact swap')
        for i in [0, 1]:
            src = g.iloc[i]
            t = g.iloc[1 - i]
            if pd.isna(src.net_B8L2) or pd.isna(t.net_B8L2):
                continue
            r = {k: t[k] for k in keys + ['building', 'image', 'pair_id', 'path_id', 'pool_id']}
            sd, td = (src.net_B8L2, t.net_B8L2)
            r.update(source_image=src.image, source_net=sd, target_net=td, sign_agree=float(np.sign(sd) == np.sign(td)), abs_effect_gap=abs(td - sd), copy_source_AE=abs(td - sd), zero_AE=abs(td), source_choice_gain_over_B=td if sd > 0 else 0, class_choice_gain_over_B=td if t.incoming_class == 'M1' else 0, source_choice_minus_random=(td if sd > 0 else 0) - 0.5 * td, class_choice_minus_random=(td if t.incoming_class == 'M1' else 0) - 0.5 * td, source_choice_minus_class_choice=(td if sd > 0 else 0) - (td if t.incoming_class == 'M1' else 0))
            transfers.append(r)
    t = pd.DataFrame(transfers)
    csv('SWAP_TRANSFERS.csv.gz', t)
    conditions = [('all_scored', np.ones(len(t), bool)), ('source_abs_ge2', t.source_net.abs() >= 2), ('source_abs_ge5', t.source_net.abs() >= 5), ('both_abs_ge2', (t.source_net.abs() >= 2) & (t.target_net.abs() >= 2))]
    ss = []
    bb = []
    for name, mask in conditions:
        z = t.loc[mask].copy()
        z['effect_filter'] = name
        sm, _, bm = aggregate(z, keys + ['effect_filter'], ['sign_agree', 'abs_effect_gap', 'copy_source_AE', 'zero_AE', 'source_choice_minus_random', 'class_choice_minus_random', 'source_choice_minus_class_choice'])
        ss.append(sm)
        bb.append(bm)
    csv('TRANSFER_SUMMARY.csv', pd.concat(ss))
    csv('TRANSFER_BUILDINGS.csv', pd.concat(bb))
    z = d[(d.condition == 'manual') & (d.layer == 'ordinary_manual') & d.scope_comparable & (d.design == 'capacity_random') & (d.tier == 'primary_coarse_class') & (d.n == 5) & (d.m == 1) & d.outgoing_class.isin(['M0', 'M1']) & d.incoming_class.isin(['M0', 'M1'])].dropna(subset=['net_B8L2', 'block_history_Q_gap']).copy()
    z['class_direction'] = np.where(z.incoming_class == 'M1', 1, -1)
    z['qgap_team_mean'] = z.block_history_Q_gap / 5
    z['hard'] = z.difficulty.eq('困难').astype(float)
    z['medium'] = z.difficulty.eq('中等').astype(float)
    z['class_hard'] = z.class_direction * z.hard
    z['class_medium'] = z.class_direction * z.medium
    models = {'history_Q_only': ['qgap_team_mean'], 'history_Q_plus_class': ['qgap_team_mean', 'class_direction'], 'history_Q_class_difficulty': ['qgap_team_mean', 'class_direction', 'class_hard', 'class_medium']}
    preds = []
    coef = []
    for building, g in z.groupby('building'):
        train = z[z.building != building]
        weights = 1 / train.groupby(['building', 'image']).image.transform('size') / train.groupby('building').image.transform('nunique')
        for name, features in models.items():
            model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
            model.fit(train[features], train.net_B8L2, ridge__sample_weight=weights)
            out = g[['event_id', 'building', 'image', 'net_B8L2', 'block_history_Q_gap', 'class_direction']].copy()
            out['model'] = name
            out['prediction'] = model.predict(g[features])
            out['AE'] = (out.prediction - out.net_B8L2).abs()
            preds.append(out)
            coef.append(dict(heldout_building=building, model=name, features=json.dumps(features), coefficients=json.dumps(model[-1].coef_.tolist())))
    pred = pd.concat(preds)
    csv('HISTORY_Q_ADJUSTMENT_PREDICTIONS.csv.gz', pred)
    csv('HISTORY_Q_ADJUSTMENT_COEFFICIENTS.csv', pd.DataFrame(coef))
    sm, _, bm = aggregate(pred, ['model'], ['AE'])
    csv('HISTORY_Q_ADJUSTMENT_SUMMARY.csv', sm)
    csv('HISTORY_Q_ADJUSTMENT_BUILDINGS.csv', bm)
    p = _read_csv(OUT / 'SELECTION_RESULTS.csv.gz')
    join = ['pair_id', 'source_pool_id', 'target_pool_id', 'domain', 'n']
    p['policy'] = p.policy.where(~p.policy.str.startswith('random_'), 'random')
    bas = p[p.policy == 'outside_Q'][join + ['B8L2', 'D10', 'target_activity_seconds', 'team_key', 'complete_evaluable']].rename(columns={c: 'base_' + c for c in ['B8L2', 'D10', 'target_activity_seconds', 'team_key', 'complete_evaluable']})
    p = p.merge(bas, on=join, how='left', validate='many_to_one')
    p['delta_Q'] = p.B8L2 - p.base_B8L2
    p['delta_D10'] = p.D10 - p.base_D10
    scored = p.B8L2.notna() & p.base_B8L2.notna()
    timed = p.target_activity_seconds.gt(0) & p.base_target_activity_seconds.gt(0)
    p['loss_over5'] = (p.delta_Q < -5).astype(float).where(scored)
    p['within2'] = (p.delta_Q >= -2).astype(float).where(scored)
    p['same_team'] = p.team_key.eq(p.base_team_key).astype(float)
    p['complete_rate'] = p.complete_evaluable.astype(float)
    p['base_complete_rate'] = p.base_complete_evaluable.astype(float)
    p['both_scored'] = scored.astype(float)
    p['low_Q50'] = p.B8L2.lt(50).astype(float).where(p.B8L2.notna())
    p['log_activity_ratio'] = np.log(p.target_activity_seconds / p.base_target_activity_seconds).where(timed)
    p['joint_save20_loss_atmost2'] = (p.delta_Q.ge(-2) & (p.target_activity_seconds / p.base_target_activity_seconds <= 0.8)).astype(float).where(scored & timed)
    p['source_plus_target_over_base_target'] = (p.source_roster_activity_seconds + p.target_activity_seconds) / p.base_target_activity_seconds
    csv('POLICY_COMPARISONS.csv.gz', p)
    keys = ['condition', 'layer', 'scope_comparable', 'domain', 'n', 'policy']
    metrics = ['B8L2', 'D10', 'delta_Q', 'delta_D10', 'complete_rate', 'base_complete_rate', 'both_scored', 'low_Q50', 'loss_over5', 'within2', 'same_team', 'target_activity_seconds', 'base_target_activity_seconds', 'log_activity_ratio', 'joint_save20_loss_atmost2', 'source_roster_activity_seconds', 'source_plus_target_over_base_target']
    sm, im, bm = aggregate(p, keys, metrics, image='target_image')
    sm['activity_ratio_geometric'] = np.exp(sm.log_activity_ratio)
    sm['activity_ratio_lo'] = np.exp(sm.log_activity_ratio_lo)
    sm['activity_ratio_hi'] = np.exp(sm.log_activity_ratio_hi)
    csv('POLICY_SUMMARY.csv', sm)
    csv('POLICY_BY_IMAGE.csv.gz', im)
    csv('POLICY_BY_BUILDING.csv', bm)
    paired = []
    for candidate, base in [('half_Q_structure', 'half_Q'), ('outside_Q_outside_T_fast', 'outside_Q_source_T_fast')]:
        a = p[p.policy == candidate]
        b = p[p.policy == base][join + ['B8L2', 'target_activity_seconds', 'team_key']].rename(columns={k: 'other_' + k for k in ['B8L2', 'target_activity_seconds', 'team_key']})
        x = a.merge(b, on=join, validate='one_to_one')
        x['comparison'] = candidate + '_minus_' + base
        x['delta_Q'] = x.B8L2 - x.other_B8L2
        x['log_activity_ratio'] = np.log(x.target_activity_seconds / x.other_target_activity_seconds)
        x['same_team'] = x.team_key.eq(x.other_team_key).astype(float)
        paired.append(x)
    x = pd.concat(paired)
    sm, _, bm = aggregate(x, ['condition', 'layer', 'scope_comparable', 'domain', 'n', 'comparison'], ['delta_Q', 'log_activity_ratio', 'same_team'], image='target_image')
    csv('INCREMENTAL_POLICY_SUMMARY.csv', sm)
    csv('INCREMENTAL_POLICY_BUILDINGS.csv', bm)
    examples = p[(p.layer == 'ordinary_manual') & p.scope_comparable & (p.domain == 'new_timed_history') & (p.n == 5) & p.policy.eq('outside_Q_outside_T_fast')].sort_values('delta_Q')
    csv('COST_EXTREME_EXAMPLES.csv', pd.concat([examples.head(8), examples.tail(8)]))
    print('Summaries saved:', len(d), 'swap view events,', len(t), 'directed transfer rows,', len(p), 'policy target rows')
if __name__ == '__main__':
    main()
