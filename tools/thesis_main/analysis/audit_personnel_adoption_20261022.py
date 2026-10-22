"""Independently check the received adoption tables; no fusion or label fitting."""
from dataclasses import replace
from itertools import combinations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.quality.quality_ab_feedback_handoff_20261015.prior_AB.src import working_models as models

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'research/workers/personnel_exchange_adoption_followup_20261022'


def members(value):
    return frozenset(str(value).split('|'))


def close(actual, expected):
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-9, equal_nan=True)


def aggregate(frame, columns, inner=()):
    result = frame
    for keys in [list(inner) + ['building', 'image'], ['building', 'image'], ['building']]:
        result = result.groupby(keys, dropna=False)[columns].mean().reset_index()
    return result[columns].mean()


def direction_counts(frame, column, inner=(), positive=True):
    g = frame.groupby(list(inner) + ['building', 'image'], dropna=False)[column].mean().reset_index()
    images = g.groupby(['building', 'image'])[column].mean()
    buildings = images.groupby('building').mean()
    result = {}
    for name, values in [('images', images), ('buildings', buildings)]:
        result[name + '_valid'] = int(values.notna().sum())
        result[name + '_direction'] = int((values > 0).sum() if positive else (values < 0).sum())
    return result


def abc_members(frame, m_col):
    for r in frame.to_dict('records'):
        d, x, y, z = [members(r[k]) for k in ['common_background', 'outgoing_block_X', 'same_count_block_Y', 'changed_count_block_Z']]
        n, m = int(r['n']), int(r[m_col])
        assert len(d) == n - m and len(x) == len(y) == len(z) == m
        assert sum(map(len, [d, x, y, z])) == len(d | x | y | z)
        for arm, block in zip('ABC', [x, y, z]):
            assert members(r[arm + '_member_workers']) == d | block


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    read = lambda name: pd.read_csv(PACKAGE / name, low_memory=False)
    report = {'data': 'real_v2', 'method': 'saved member/endpoint relations, score formula and independent hierarchical aggregation',
              'not_run': ['native fusion', 'raw annotation to feature reconstruction', 'classification refitting', 'human image adjudication']}

    base = 'structure_followup/background_gradient/'
    scalar = read(base + 'ENDPOINT_SCALARS.csv.gz').set_index('team_key', verify_integrity=True)
    geo = read(base + 'ENDPOINT_GEOMETRY.csv.gz').set_index('team_key', verify_integrity=True)
    assert set(scalar.index) == set(geo.index) and len(scalar) == 3276
    for col in ['pool_id', 'member_workers', 'k', 'reference_id', 'reference_version']:
        assert scalar[col].astype(str).equals(geo.loc[scalar.index, col].astype(str)), col
    good = scalar.B8L2.notna()
    fields = ['iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter']
    inputs = [scalar.loc[good, f].to_numpy() for f in fields]
    max_error = 0.
    for col, params in [('B8L2', models.B), ('D10', replace(models.B, direction_scale_deg=10.))]:
        values = models.score(*inputs, params)
        close(values, scalar.loc[good, col])
        max_error = max(max_error, float(np.max(np.abs(values - scalar.loc[good, col]))))
    assert scalar.loc[~good, ['B8L2', 'D10']].isna().all().all()
    assert not scalar.loc[~good, 'complete_evaluable'].any()
    report['background_endpoints'] = {'total': len(scalar), 'scored': int(good.sum()), 'unscored': int((~good).sum()), 'score_max_abs_error': max_error}

    events = read(base + 'EVENTS_COMPLETE.csv.gz')
    assert len(events) == events.event_id.nunique() == events.physical_triple_id.nunique() == 1092
    abc_members(events, 'm')
    assert events.m.eq(7).all() and events.n.eq(20).all()
    for arm in 'ABC':
        s = scalar.loc[events['team_' + arm]]
        assert list(s.member_workers.map(members)) == list(events[arm + '_member_workers'].map(members))
        for met in ['B8L2', 'D10']:
            close(s[met].to_numpy(), events[arm + '_' + met])
    anchors = read(base + 'ANCHORS_EXACT.csv')
    labels = read(base + 'USED_LOBO_LABELS.csv.gz').set_index(['heldout_building', 'worker_id'])
    for a in anchors.itertuples():
        group = events[events.anchor_id.eq(a.anchor_id)]
        universe = members(a.background_universe)
        assert len(group) == len(universe) == 14
        assert set(group.common_background.map(members)) == {universe - {w} for w in universe}
        for key, val, label in [('outgoing_block_X', a.X, a.source_class), ('same_count_block_Y', a.Y, a.source_class), ('changed_count_block_Z', a.Z, a.target_class)]:
            assert group[key].map(members).eq(members(val)).all()
            assert all(labels.loc[(a.building, w), 'coarse_label'] == label for w in members(val))
    common = events[['A_B8L2', 'B_B8L2', 'C_B8L2']].notna().all(axis=1)
    events['recalc_net'] = (events.C_B8L2 - events.B_B8L2).where(common)
    close(events.net_B8L2, events.C_B8L2 - events.B_B8L2)
    net = aggregate(events, ['recalc_net'], ['anchor_id']).iloc[0]
    close(net, read(base + 'ABC_SUMMARY.csv').net_B8L2.iloc[0])
    report['background_abc'] = {'events': len(events), 'anchors': len(anchors), 'images': events.image.nunique(), 'buildings': events.building.nunique(),
        'common_scored': int(common.sum()), 'C_failed': int(events.C_failure.sum()), 'net_Q': net,
        'loss_gt5': int((events.loc[common, 'recalc_net'] < -5).sum()), 'loss_gt10': int((events.loc[common, 'recalc_net'] < -10).sum())}

    pairs = read(base + 'MATCHED_BACKGROUND_GRADIENT_PAIRS.csv.gz')
    by_id = events.set_index('event_id')
    low, high = by_id.loc[pairs.event_low].reset_index(drop=True), by_id.loc[pairs.event_high].reset_index(drop=True)
    for key in ['anchor_id', 'outgoing_block_X', 'same_count_block_Y', 'changed_count_block_Z']:
        assert low[key].equals(high[key])
    for d1, d2 in zip(low.common_background.map(members), high.common_background.map(members)):
        assert len(d1 - d2) == len(d2 - d1) == 1
    close(high.background_target_seats - low.background_target_seats, np.ones(len(pairs)))
    common6 = low[['A_B8L2', 'B_B8L2', 'C_B8L2']].notna().all(axis=1) & high[['A_B8L2', 'B_B8L2', 'C_B8L2']].notna().all(axis=1)
    cols = []
    for arm in 'ABC':
        col = arm + '_change_B8L2'
        pairs[col] = (high[arm + '_B8L2'] - low[arm + '_B8L2']).where(common6)
        cols.append(col)
    pairs['net_change_B8L2'] = pairs.C_change_B8L2 - pairs.B_change_B8L2
    cols.append('net_change_B8L2')
    values = aggregate(pairs, cols, ['anchor_id'])
    close(values, read(base + 'GRADIENT_SUMMARY.csv')[cols].iloc[0])
    report['background_gradient'] = {'pairs': len(pairs), 'common_six_scored': int(common6.sum()), **values.to_dict()}
    report['background_gradient'].update(direction_counts(pairs, 'net_change_B8L2', ['anchor_id'], positive=False))

    paths = read('structure_followup/FIXED_A_PATHS_EXACT.csv.gz')
    assert paths.team_A_4.equals(paths.team_A_max)
    for suffix, mcol in [('_4', 'm_from'), ('_max', 'm_to')]:
        subset = paths.rename(columns={k: k.removesuffix(suffix) for k in paths if k.endswith(suffix)}).copy()
        abc_members(subset, mcol)
    for role in ['outgoing_block_X', 'same_count_block_Y', 'changed_count_block_Z']:
        assert all(members(a) <= members(b) for a, b in zip(paths[role + '_4'], paths[role + '_max']))
    five = paths[['A_B8L2_4','B_B8L2_4','C_B8L2_4','B_B8L2_max','C_B8L2_max']].notna().all(axis=1)
    paths['C_direct'] = (paths.C_B8L2_max - paths.C_B8L2_4).where(five)
    paths['B_direct'] = (paths.B_B8L2_max - paths.B_B8L2_4).where(five)
    paths['net_direct'] = paths.C_direct - paths.B_direct
    close(paths[['C_direct','B_direct','net_direct']], paths[['C_change','B_change','net_advantage_change']])
    rows = []
    for keys, group in paths.groupby(['source_role','target_role','m_from','m_to']):
        values = aggregate(group, ['C_direct','B_direct','net_direct'])
        rows.append(dict(zip(['source_role','target_role','m_from','m_to'], keys)) | {'paths':len(group),'common_paths':int(group.C_direct.notna().sum()), **values.to_dict(), 'C_directions':direction_counts(group,'C_direct'), 'net_directions':direction_counts(group,'net_direct')})
    report['fixed_A_paths'] = rows

    ident = read('manual_qt_followup/CLASS_QT10_EXACT_IDENTITY.csv.gz')
    assert len(ident) == 19896 and ident.team_P_class.equals(ident.team_P_QT10)
    assert ident.replacement_block_class.map(members).equals(ident.replacement_block_QT10.map(members))
    candidates = read('manual_qt_followup/FROZEN_TARGET_CANDIDATES.csv.gz')
    selected = read('manual_qt_followup/FINITE_SELECTED_BLOCKS.csv')
    for r in selected.itertuples():
        g = candidates[candidates.panel_id.eq(r.panel_id)].copy()
        g['rank'] = g.classification_q_history - r.lambda_logtime * g.classification_t_history
        g = g.sort_values(['rank','changed_count_block_Z'], ascending=[False,True])
        assert g.iloc[0].team_C == r.selected_team
    finite = read('manual_qt_followup/FINITE_POLICIES_SAME_ANCHOR.csv.gz')
    increments = read('manual_qt_followup/FINITE_SELECTION_INCREMENT_SAME_ANCHOR.csv.gz')
    ref = finite[finite.policy.eq('finite_uniform')].set_index(['panel_id','team_A'])
    metrics = ['delta_B8L2','delta_logT']
    for policy, part in increments.groupby('policy'):
        orig = finite[finite.policy.eq(policy)].set_index(['panel_id','team_A']).loc[pd.MultiIndex.from_frame(part[['panel_id','team_A']])]
        uniform = ref.loc[orig.index]
        close(part[metrics], (orig[metrics] - uniform[metrics]).to_numpy())
    qt = increments[increments.n.eq(20) & increments.m.eq(4) & increments.policy.eq('finite_QT10')]
    vals = aggregate(qt, metrics, ['panel_id'])
    report['continuous_QT'] = {'identical_anchors':len(ident),'candidate_blocks':len(candidates),'reservoirs':candidates.panel_id.nunique(),
        'choices_recomputed':len(selected),'QT10_minus_uniform_Q':vals.delta_B8L2,'QT10_time_pct':100*np.expm1(vals.delta_logT)}

    semi = read('semi_followup/NEW_MAIN_EVENT_LINKS.csv.gz')
    old = read('semi_followup/OLD_EXACT_EVENTS.csv.gz')
    abc_members(semi, 'm_AB')
    for pre, a, b in [('same','B','A'),('cross','C','A'),('net','C','B')]:
        close(semi[pre+'_B8L2'], (semi[a+'_B8L2']-semi[b+'_B8L2']).where(semi.all_scored))
    cell = ['building','image','pool_id','source_class','target_class','n','m_AB']
    met = ['net_B8L2','net_recorded_time_logratio']
    newcell = semi.groupby(cell+['reservoir_id','common_background'],dropna=False)[met].mean().reset_index().groupby(cell+['reservoir_id'])[met].mean().reset_index().groupby(cell)[met].mean().reset_index()
    oldcell = old.groupby(cell+['common_background'],dropna=False)[met].mean().reset_index().groupby(cell)[met].mean().reset_index()
    commoncell = newcell.merge(oldcell[cell],on=cell,validate='one_to_one')
    vals = aggregate(commoncell, met)
    report['semi'] = {'oriented_rows_in_received_link_table':len(semi),'physical_ABC':semi.physical_triple_id.nunique(),'common_old_cells':len(commoncell),
        'old_net_Q':aggregate(oldcell,met).net_B8L2,'new_net_Q_common_cells':vals.net_B8L2,'new_time_pct_common_cells':100*np.expm1(vals.net_recorded_time_logratio)}
    case = semi[semi.image.eq('7y3sRwLe3Va-13') & semi.n.eq(12) & semi.m_AB.eq(4)]
    for _, g in case.groupby('common_background'):
        source = sorted(members(g.iloc[0].source_union))
        expected = {frozenset((frozenset(x), frozenset(source)-frozenset(x))) for x in combinations(source,4)}
        actual = {frozenset((members(r.outgoing_block_X),members(r.same_count_block_Y))) for r in g.itertuples()}
        assert actual == expected and len(actual)==35
    report['semi']['case_7y13_backgrounds'] = case.common_background.nunique()
    report['semi']['case_7y13_physical_ABC'] = case.physical_triple_id.nunique()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=lambda x:x.item())+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2,default=lambda x:x.item()))


if __name__ == '__main__':
    main()
