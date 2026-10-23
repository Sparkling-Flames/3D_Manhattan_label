"""核对冻结分类输入、全部容量配置及几何事件连接和层级汇总。

几何距离本身另由 audit_same_room_geometry_20261023 从保存几何重算。
"""
from pathlib import Path
from itertools import permutations
import argparse
import json

import numpy as np
import pandas as pd

from audit_rebuilt_sensitivity_20261023 import compare, check_frame, masks, PAIR, CONFIG


def labels_capacity(root, repo, out, checks):
    inputs = root/'design/inputs'
    rows = []
    source_files = {
        **{name: repo/'research/same_room/same_room_current_classes_v2_20261023/source_index'/name
           for name in ['CURRENT_MANUAL_LABELS_LOBO.csv', 'CURRENT_MANUAL_FOLD_CENTERS.csv',
                        'DIRECT_PAIR_CURRENT_CLASS_CAPACITY.csv', 'DIRECT_PAIR_CLASS_MEMBERS.csv']},
        **{name: repo/'research/workers/personnel_population_curves_v2_20261023/inputs'/name
           for name in ['ALL_METHOD_LABELS_LOBO.csv.gz', 'FOLD_CLASS_DEFINITIONS.csv']}}
    for name, source in source_files.items():
        same = (inputs/name).read_bytes() == source.read_bytes()
        assert same, name
        rows.append(dict(input=name, main_source=source.relative_to(repo).as_posix(),
                         bytes=(inputs/name).stat().st_size, byte_identical=same))
    pd.DataFrame(rows).to_csv(out/'FROZEN_INPUT_IDENTITY.csv', index=False)

    centers = pd.read_csv(inputs/'CURRENT_MANUAL_FOLD_CENTERS.csv')
    centers = centers[centers.tier.eq('coarse')]
    roles = pd.read_csv(root/'design/CLASS_ROLES_AND_MEMBERS.csv')
    identity = ['condition', 'method', 'heldout_building', 'class_id']
    for col in centers:
        a = centers.set_index(identity).sort_index()[col] if col not in identity else None
        if a is not None:
            b = roles.set_index(identity).sort_index()[col]
            if pd.api.types.is_numeric_dtype(a):
                compare(a, b, 'center_'+col, checks)
            else:
                assert a.fillna('').equals(b.fillna('')), col
    generated = []
    for fold, d in centers.groupby(['condition', 'method', 'heldout_building']):
        ranks = d.assign(t=d.turn_history_mean.fillna(0), q=d.q_history_mean.fillna(0))
        tr = {idx: k+1 for k, idx in enumerate(ranks.sort_values(['t', 'class_id']).index)}
        qr = {idx: k+1 for k, idx in enumerate(ranks.sort_values(['q', 'class_id']).index)}
        red_mid = sorted(d.redundancy_history_mean.fillna(0))[len(d)//2]
        for idx, r in d.iterrows():
            turn = '较少转折' if tr[idx] == 1 else '较多转折' if tr[idx] == len(d) else '常规转折'
            red = '较多近共线分段' if r.redundancy_history_mean > red_mid else '较少近共线分段'
            if r.method == 'V3_BEHAVIOR':
                if r.selected_family == 'TURN':
                    role = turn; family = 'TURN'
                elif r.selected_family == 'JOINT':
                    role = turn+'、'+red; family = 'JOINT'
                else:
                    context = '复杂图额外保留' if r.complex_turn_history_mean > 0 else '复杂图倾向简化'
                    role = turn+'、'+context+'、'+red; family = 'CONTEXT'
            else:
                qrole = '历史Q较高' if qr[idx] == len(d) else '历史Q较低' if qr[idx] == 1 else '历史Q中间'
                speed = '历史较快' if r.t_history_mean < 0 else '历史较慢' if r.t_history_mean > 0 else '历史时间近基准'
                role = qrole+'、'+speed+'、'+turn; family = r.selected_family
            generated.append(dict(zip(identity, [*fold, r.class_id]), role_zh=role,
                                  role_alignment_key=f'{family}{len(d)}:{role}',
                                  turn_center_order=tr[idx], q_center_order=qr[idx]))
    actual = pd.DataFrame(generated).set_index(identity).sort_index()
    expected = roles.set_index(identity).sort_index()
    assert actual.index.equals(expected.index)
    assert actual.role_zh.equals(expected.role_zh) and actual.role_alignment_key.equals(expected.role_alignment_key)
    compare(actual[['turn_center_order', 'q_center_order']], expected[['turn_center_order', 'q_center_order']],
            'historical_role_rank_alignment', checks)

    capacity = pd.read_csv(inputs/'DIRECT_PAIR_CURRENT_CLASS_CAPACITY.csv')
    byclass = pd.read_csv(inputs/'DIRECT_PAIR_CLASS_MEMBERS.csv')
    cfg_expected = set(); direction_expected = set()
    for r in capacity.itertuples(index=False):
        c = byclass[byclass.pair_key.eq(r.pair_key) & byclass.method.eq(r.method)]
        counts = c.set_index('class_id').n_common.to_dict()
        assert sum(counts.values()) == r.common_n
        assert counts.pop('unknown', 0) == r.unknown_common_n
        assert counts == json.loads(r.class_counts)
        for source, target in permutations(counts, 2):
            max_m = min(counts[source]//2, counts[target])
            direction_expected.add((r.pair_key, r.method, source, target, max_m))
            for m in range(5, max_m+1):
                for n in range(m, r.common_n-2*m+1):
                    cfg_expected.add((r.pair_key, r.method, source, target, m, n))
    columns = ['pair_key', 'method', 'source_class', 'target_class', 'm', 'n']
    registered = pd.read_csv(root/'design/CAPACITY_CONFIGURATIONS.csv')
    assert set(registered[columns].itertuples(index=False, name=None)) == cfg_expected
    assert len(registered) == len(cfg_expected) == 2825
    events = pd.read_csv(root/'design/STRICT_ABC_EVENTS.csv.gz', usecols=columns)
    assert set(events.itertuples(index=False, name=None)) == cfg_expected
    directions = pd.read_csv(root/'design/CAPACITY_DIRECTIONS.csv')
    assert set(directions[columns[:4]+['strict_m_max']].itertuples(index=False, name=None)) == direction_expected
    return dict(exact_main_inputs=len(rows), historical_roles=len(roles), capacity_input_rows=len(capacity),
                directions=len(directions), feasible_configurations=len(cfg_expected),
                all_feasible_n_m_configurations_covered=True,
                design_code_review='Selection uses class membership, capacities, deterministic hash ordering and anchors; q/t only stored as historical descriptions. Target Q is not read for selection.',
                design_regeneration=False, classification_refit=False)


def geometry(root, out, checks):
    e = pd.read_csv(root/'results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz', low_memory=False)
    g = pd.read_csv(root/'geometry/EVENT_GEOMETRY_RESULTS.csv.gz', low_memory=False)
    u = pd.read_csv(root/'geometry/UNIQUE_GEOMETRY_COMPARISONS.csv.gz', low_memory=False)
    assert len(g) == 6*len(e) == 376056 and len(u) == 365622
    assert not g.duplicated(['event_id', 'view', 'comparison']).any() and u.geometry_pair_key.is_unique
    assert set(g.geometry_pair_key) == set(u.geometry_pair_key)
    joined = u.set_index('geometry_pair_key').loc[g.geometry_pair_key].reset_index()
    for col in u:
        if pd.api.types.is_numeric_dtype(u[col]):
            compare(g[col], joined[col], 'unique_join_'+col, checks)
        else:
            assert g[col].fillna('').equals(joined[col].fillna('')), col
    event = e.set_index('event_id')
    for (view, contrast), z in g.groupby(['view', 'comparison']):
        d = event.loc[z.event_id]
        for side, arm in [('from', contrast[0]), ('to', contrast[1])]:
            assert np.array_equal(z['team_key_'+side], d[f'team_{arm}_{view}'])
        for col in ['pair_key', 'building', 'method', 'condition', 'config_id', 'n', 'm']:
            assert np.array_equal(z[col], d[col]), col
        assert np.array_equal(z.pool_id, d['pool_id_'+view])

    order = ['a_AB', 'a_AC', 'a_BC', 'b_AB', 'b_AC', 'b_BC']
    g['contrast'] = g.view+'_'+g.comparison
    matrices = lambda name: g.pivot(index='event_id', columns='contrast', values=name).reindex(index=e.event_id, columns=order).to_numpy()
    status = matrices('status')
    unique = status == 'unique_cyclic_candidate'
    derived = {}
    metrics = ['bev_mean_h', 'top_mean_h', 'bev_max_h', 'top_max_h', 'angle_deg', 'matched_reflex_disagreement_n']
    for metric in metrics:
        v = matrices(metric).astype(float)
        valid = unique.all(axis=1) & np.isfinite(v).all(axis=1)
        within = v[:, [0, 3]].mean(axis=1); cross = v[:, [1, 2, 4, 5]].mean(axis=1)
        derived['geometry_common6_'+metric] = valid
        for suffix, value in [('within', within), ('cross', cross), ('extra', cross-within)]:
            derived['geometry_'+metric+'_'+suffix] = np.where(valid, value, np.nan)
    derived['geometry_all_unique6'] = unique.all(axis=1)
    derived['Q_geometry_joint6'] = e.Q_common6.to_numpy() & unique.all(axis=1)
    for name in sorted(set(g.status)-{'unique_cyclic_candidate'} | {'ambiguous_cyclic_match'}):
        v = status == name
        within, cross = v[:, [0, 3]].mean(axis=1), v[:, [1, 2, 4, 5]].mean(axis=1)
        for suffix, value in [('within', within), ('cross', cross), ('extra', cross-within)]:
            derived['geometry_'+name+'_'+suffix] = value
    warning = matrices('high_angle_correspondence_warning')
    warning = np.isin(warning.astype(str), ['True', '1', '1.0'])
    derived['geometry_any_high_angle_warning'] = np.where(unique.all(axis=1), warning.any(axis=1), np.nan)
    actual = pd.DataFrame(derived)
    saved = pd.read_csv(root/'geometry_summary/EVENT_GEOMETRY_COMMON_SUPPORT.csv.gz', low_memory=False).set_index('event_id').loc[e.event_id]
    compare(actual, saved[actual.columns], 'all_geometry_event_metrics', checks)
    z = e.assign(**derived)
    cols = [c for c in derived if not c.startswith('geometry_common6_')]+['B8L2_extra']
    records = []; signs = []; paired = []
    for (method, condition), sub in z.groupby(['method', 'condition']):
        for subset, mask in masks(z).items():
            selected = sub[mask.loc[sub.index]]
            for support in ['all_geometry_diagnostics', 'joint_Q_and_geometry']:
                d = selected if support == 'all_geometry_diagnostics' else selected[selected.Q_geometry_joint6]
                if d.empty:
                    continue
                p = d.groupby(CONFIG)[cols].mean().groupby(PAIR).mean()
                b = p.groupby('building').mean()
                row = dict(subset=subset, method=method, condition=condition, support=support,
                           events=len(d), pairs=d.pair_key.nunique(), buildings=d.building.nunique(),
                           six_unique_geometry_events=int(d.geometry_all_unique6.sum()),
                           six_Q_and_geometry_events=int(d.Q_geometry_joint6.sum()))
                for c in cols:
                    row['pair_equal__'+c] = p[c].mean(); row['building_equal__'+c] = b[c].mean()
                for c in ['geometry_bev_mean_h_extra', 'geometry_top_mean_h_extra']:
                    values = p[c].dropna()
                    # 1e-12 h 只处理双精度舍入，绝非研究上的最小有意义差异。
                    signs.append(dict(subset=subset, method=method, condition=condition, support=support,
                                      metric=c, pairs=len(values), positive_exact=int(values.gt(0).sum()),
                                      negative_exact=int(values.lt(0).sum()), positive_eps=int(values.gt(1e-12).sum()),
                                      negative_eps=int(values.lt(-1e-12).sum()), zero_eps=int(values.abs().le(1e-12).sum())))
                    row['valid_pairs__'+c] = len(values)
                records.append(row)
                paired.append(p.reset_index().assign(subset=subset, method=method, condition=condition, support=support))
    actual = pd.DataFrame(records)
    keys = ['subset', 'method', 'condition', 'support']
    expected = pd.read_csv(root/'geometry_summary/GEOMETRY_CONDITIONS.csv')
    check_frame(actual, expected, keys, [c for c in actual if c not in keys], 'geometry_conditions', checks)
    actual.to_csv(out/'GEOMETRY_CONDITIONS.csv', index=False)
    paired = pd.concat(paired, ignore_index=True)
    check_frame(paired, pd.read_csv(root/'geometry_summary/GEOMETRY_PAIR_METRICS.csv.gz'), keys+PAIR,
                cols, 'geometry_pair_means', checks)
    signs = pd.DataFrame(signs)
    original_sign = expected[keys+['positive_pair_fraction__geometry_bev_mean_h_extra', 'positive_pair_fraction__geometry_top_mean_h_extra']].melt(
        id_vars=keys, var_name='metric', value_name='published_positive_fraction')
    original_sign.metric = original_sign.metric.str.replace('positive_pair_fraction__', '', regex=False)
    signs = signs.merge(original_sign, on=keys+['metric'], validate='one_to_one')
    signs['published_positive_count'] = (signs.published_positive_fraction*signs.pairs).round().astype(int)
    signs['changed_positive_pairs'] = signs.published_positive_count-signs.positive_eps
    signs.to_csv(out/'GEOMETRY_SIGN_TOLERANCE.csv', index=False)
    return dict(geometry_event_rows=len(g), unique_geometry_pairs=len(u), events=len(e),
                signs_changed_rows=int(signs.changed_positive_pairs.ne(0).sum()),
                tolerance_camera_height=1e-12, native_geometry_distances_recomputed_here=False)


def main(root, repo, out):
    out.mkdir(parents=True, exist_ok=True)
    checks = []
    receipt = labels_capacity(root, repo, out, checks)
    print('分类输入、历史角色和全部容量配置核对完成', flush=True)
    receipt.update(geometry(root, out, checks))
    pd.DataFrame(checks).to_csv(out/'NUMERIC_CHECKS.csv', index=False)
    receipt.update(numeric_values=sum(r['values'] for r in checks))
    (out/'RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    main(args.root, args.repo, args.out)
