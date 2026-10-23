"""独立重聚合新同房大块实验的条件、成员、历史 Q 和锚点结果。

输入事件差值已经由 audit_same_room_rebuilt_20261023 从端点独立核对。
本脚本不导入生产方分析函数，也不改变作者包或重新融合。
"""
from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd


PAIR = ['pair_key', 'building']
CONFIG = PAIR + ['source_class', 'target_class', 'n', 'm']
METRICS = ['B8L2_within', 'B8L2_cross', 'B8L2_extra', 'B8L2_CA',
           'B8L2_CB', 'B8L2_CS', 'D10_extra', 'fusion_turn_n_extra',
           'S_bottom_deg_extra', 'dir_extra', 'QT_time_ratio_CA',
           'CA_loss_gt5_fraction', 'score_failure_fraction', 'incomplete_fraction']
PATH_EFFECTS = ['A_change', 'B_change', 'C_change', 'net_C_minus_B_change',
                'BA_change', 'CA_change', 'within_amplitude_change',
                'cross_amplitude_change', 'extra_amplitude_change']
PATH_METRICS = ['B8L2', 'D10', 'fusion_turn_n', 'fusion_short_turn_edges',
                'fusion_redundancy_n', 'S_bottom_deg', 'dir', 'Hmean',
                'height_mean_ratio', 'geometry_area_h2', 'IoU3D100',
                'recorded_time_total_seconds']


def compare(actual, expected, name, checks):
    a, b = np.asarray(actual, float), np.asarray(expected, float)
    assert a.shape == b.shape, (name, a.shape, b.shape)
    ok = np.isclose(a, b, atol=1e-8, rtol=1e-10, equal_nan=True)
    assert ok.all(), (name, int((~ok).sum()), a[~ok][:4], b[~ok][:4])
    finite = np.isfinite(a) & np.isfinite(b)
    checks.append(dict(check=name, values=a.size,
                       max_abs_error=float(np.abs(a[finite]-b[finite]).max()) if finite.any() else 0.))


def check_frame(a, b, keys, columns, name, checks):
    a = a.set_index(keys).sort_index()
    b = b.set_index(keys).sort_index()
    assert a.index.is_unique and b.index.is_unique and a.index.equals(b.index), name
    compare(a[columns], b[columns], name, checks)


def pair_means(frame, columns, config=CONFIG):
    return frame.groupby(config, dropna=False)[columns].mean().groupby(PAIR).mean()


def masks(e):
    ordinary = e.ordinary_comparable
    mixed = e.D_n.gt(0)
    doorway = e.layer_a.str.contains('doorway') | e.layer_b.str.contains('doorway')
    return dict(ordinary_all=ordinary, ordinary_pure=ordinary & ~mixed,
                ordinary_mixed=ordinary & mixed,
                ordinary_mixed_less_half=ordinary & (2*e.m < e.n),
                ordinary_mixed_half=ordinary & (2*e.m == e.n),
                ordinary_mixed_more_half=ordinary & mixed & (2*e.m > e.n),
                doorway=~ordinary & doorway, other_nonordinary=~ordinary & ~doorway,
                ordinary_Q_blocks_within2=ordinary & e.history_Q_block_range.le(2),
                ordinary_Q_blocks_within5=ordinary & e.history_Q_block_range.le(5),
                ordinary_mixed_Q_blocks_within2=ordinary & mixed & e.history_Q_block_range.le(2))


def condition_row(z):
    p = pair_means(z, METRICS)
    b = p.groupby('building').mean()
    row = dict(attempted_events=len(z), common6_Q_events=int(z.Q_common6.sum()),
               pairs=z.pair_key.nunique(), buildings=z.building.nunique(),
               Q_pairs=int(p.B8L2_extra.notna().sum()),
               positive_Q_extra_pairs=int(p.B8L2_extra.gt(0).sum()))
    for tag, t in [('pair_equal', p), ('building_equal', b)]:
        row.update({tag+'__'+c: t[c].mean() for c in METRICS})
    return row


def audit_conditions(e, read, out, checks):
    for filename, keys in [
        ('LEAVE_ONE_BUILDING_OUT.csv', ['subset', 'method', 'condition', 'excluded_building']),
        ('DIFFICULTY_PAIR_CONDITIONS.csv', ['method', 'condition', 'difficulty_pair']),
        ('DIRECTION_RESULTS.csv', ['subset', 'method', 'condition', 'source_role_key', 'target_role_key']),
    ]:
        expected = read('results/'+filename)
        rows = []
        mm = masks(e)
        for r in expected.itertuples(index=False):
            z = e[e.method.eq(r.method) & e.condition.eq(r.condition)]
            if filename.startswith('DIFFICULTY'):
                z = z[z.ordinary_comparable & z.difficulty_pair.eq(r.difficulty_pair)]
            else:
                z = z[mm[r.subset].loc[z.index]]
            if filename.startswith('LEAVE'):
                z = z[z.building.ne(r.excluded_building)]
            elif filename.startswith('DIRECTION'):
                z = z[z.source_role_key.eq(r.source_role_key) & z.target_role_key.eq(r.target_role_key)]
            row = {k: getattr(r, k) for k in keys}
            row.update(condition_row(z)); rows.append(row)
        actual = pd.DataFrame(rows)
        cols = [c for c in actual if c not in keys]
        check_frame(actual, expected, keys, cols, filename, checks)
        actual.to_csv(out/filename, index=False)

    contribution_rows = []
    for (method, condition), sub in e.groupby(['method', 'condition']):
        for subset, mask in masks(e).items():
            z = sub[mask.loc[sub.index]]
            if z.empty:
                continue
            cols = [c for c in METRICS if c.startswith('B8L2_')]
            keys = CONFIG + ['source_role_key', 'target_role_key']
            cfg = z.groupby(keys)[cols].mean().dropna(subset=['B8L2_extra']).reset_index()
            if cfg.empty:
                continue
            cfg['pair_weight'] = 1 / cfg.groupby('pair_key').pair_key.transform('size') / cfg.pair_key.nunique()
            pairs_per_building = cfg[PAIR].drop_duplicates().groupby('building').size()
            cfg['building_weight'] = (1 / cfg.groupby('pair_key').pair_key.transform('size')
                                      / cfg.building.map(pairs_per_building) / len(pairs_per_building))
            assert np.isclose(cfg.pair_weight.sum(), 1) and np.isclose(cfg.building_weight.sum(), 1)
            for (sr, tr), zz in cfg.groupby(['source_role_key', 'target_role_key']):
                row = dict(subset=subset, method=method, condition=condition,
                           source_role_key=sr, target_role_key=tr, configurations=len(zz),
                           pairs=zz.pair_key.nunique(), buildings=zz.building.nunique())
                for label, weight in [('pair_equal', 'pair_weight'), ('building_equal', 'building_weight')]:
                    row[label+'_weight_share'] = zz[weight].sum()
                    row.update({label+'_contribution__'+c: np.dot(zz[weight], zz[c]) for c in cols})
                contribution_rows.append(row)
    actual = pd.DataFrame(contribution_rows)
    keys = ['subset', 'method', 'condition', 'source_role_key', 'target_role_key']
    check_frame(actual, read('reader_tables/DIRECTION_CONTRIBUTIONS.csv'), keys,
                [c for c in actual if c not in keys], 'direction_contributions', checks)
    actual.to_csv(out/'DIRECTION_CONTRIBUTIONS.csv', index=False)


def audit_history(e, read, out, checks):
    common = read('design/FROZEN_COMMON_CLASS_MEMBERS.csv.gz')
    labels = read('design/inputs/ALL_METHOD_LABELS_LOBO.csv.gz')
    labels = labels[labels.method.eq('V3_JOINT_QT')].set_index(['condition', 'heldout_building', 'worker_id'])
    keys = pd.MultiIndex.from_frame(common[['condition', 'building', 'worker_id']])
    compare(common[['q_history', 't_history']], labels.reindex(keys)[['q_history', 't_history']],
            'common_history_bound_to_joint_lobo_labels', checks)
    lookup = common.set_index(['pair_key', 'method', 'worker_id'])[['q_history', 't_history']].to_dict('index')
    rows = []
    for r in e.itertuples(index=False):
        row = {}
        for block in 'DXYZ':
            people = getattr(r, block+'_members').split('|') if getattr(r, block+'_members') else []
            for history in ['q', 't']:
                v = np.array([lookup[(r.pair_key, r.method, w)][history+'_history'] for w in people])
                row[history+'_'+block] = np.nanmean(v) if np.isfinite(v).any() else np.nan
                row[history+'_'+block+'_known_n'] = int(np.isfinite(v).sum())
        rows.append(row)
    hist = pd.DataFrame(rows)
    compare(hist, e[hist.columns], 'block_history_from_frozen_worker_values', checks)
    v = hist[['q_X', 'q_Y', 'q_Z']].to_numpy()
    full = hist[['q_X_known_n', 'q_Y_known_n', 'q_Z_known_n']].eq(e.m, axis=0).all(axis=1)
    ranges = np.where(full, np.max(v, axis=1)-np.min(v, axis=1), np.nan)
    compare(ranges, e.history_Q_block_range, 'history_range_full_support', checks)

    expected = read('history_q/HISTORY_Q_COMMON_SUPPORT_RESULTS.csv')
    # 几何距离的端点级计算由另一个审查脚本负责，此处核对事件表已有分项。
    columns = [c for c in expected.metric.unique() if c in e]
    result = []
    for (method, condition), z in e[e.ordinary_comparable].groupby(['method', 'condition']):
        for threshold in [2, 5]:
            near = z[z.history_Q_block_range.le(threshold)]
            for matching, keys in [('same_configuration', CONFIG), ('same_configuration_exact_D', CONFIG+['D_members'])]:
                a = near.groupby(keys, dropna=False)[columns].mean()
                b = z.groupby(keys, dropna=False)[columns].mean().reindex(a.index)
                ca = near.groupby(keys, dropna=False).agg(events=('event_id', 'size'), q=('Q_common6', 'sum'))
                cb = z.groupby(keys, dropna=False).agg(events=('event_id', 'size'), q=('Q_common6', 'sum')).reindex(a.index)
                for metric in columns:
                    ok = a[metric].notna() & b[metric].notna()
                    if not ok.any():
                        continue
                    v = pd.concat([a.loc[ok, metric].rename('near'), b.loc[ok, metric].rename('all')], axis=1)
                    c = v.groupby(CONFIG).mean()
                    p = c.groupby(PAIR).mean(); bld = p.groupby('building').mean()
                    row = dict(method=method, condition=condition, threshold=threshold, matching=matching,
                               metric=metric, valid_strata=int(ok.sum()), configurations=len(c),
                               pairs=len(p), buildings=len(bld), near_events=int(ca.loc[ok, 'events'].sum()),
                               all_on_support_events=int(cb.loc[ok, 'events'].sum()),
                               near_Q_events=int(ca.loc[ok, 'q'].sum()), all_on_support_Q_events=int(cb.loc[ok, 'q'].sum()),
                               positive_near_pair_fraction=p.near.gt(0).mean())
                    for tag, zz in [('pair_equal', p), ('building_equal', bld)]:
                        row[tag+'_near'] = zz.near.mean(); row[tag+'_all_on_support'] = zz['all'].mean()
                        row[tag+'_difference'] = (zz.near-zz['all']).mean()
                    result.append(row)
    actual = pd.DataFrame(result)
    keys = ['method', 'condition', 'threshold', 'matching', 'metric']
    check_frame(actual, expected[expected.metric.isin(columns)], keys,
                [c for c in actual if c not in keys], 'history_common_support', checks)
    actual.to_csv(out/'HISTORY_Q_COMMON_SUPPORT_RESULTS.csv', index=False)


def audit_members(e, read, out, checks):
    e = e[e.ordinary_comparable & e.method.eq('V3_BEHAVIOR')].copy()
    candidates = sorted(set('|'.join(e.loc[e.target_n.le(10), 'Z_members']).split('|'))-{''})
    expected = read('sensitivity/MEMBER_MATCHED_SUMMARY.csv').set_index(['worker_id', 'matching'])
    assert set(candidates) == set(expected.index.get_level_values(0)) and len(candidates) == 28
    e['people'] = (e.D_members+'|'+e.X_members+'|'+e.Y_members+'|'+e.Z_members).map(lambda s: set(s.split('|'))-{''})
    cols = [c for c in METRICS if 'original_pair_equal__'+c in expected]
    results = []; reweight = []
    for worker in candidates:
        relevant = e.loc[e.Z_members.map(lambda s: worker in s.split('|')), ['pair_key', 'source_class', 'target_class']].drop_duplicates()
        z = e.merge(relevant, on=['pair_key', 'source_class', 'target_class'], validate='many_to_one')
        z['present'] = z.people.map(lambda people: worker in people)
        for matching, keys in [('class_composition_background', CONFIG+['D_class_counts']),
                               ('exact_D', CONFIG+['D_class_counts', 'D_members'])]:
            count = z.groupby(keys+['present'], dropna=False).agg(events=('event_id', 'size'), quality_events=('Q_common6', 'sum'))
            data = z.groupby(keys+['present'], dropna=False)[cols].mean().join(count)
            yes = data.xs(True, level='present') if True in data.index.get_level_values('present') else data.iloc[:0].droplevel('present')
            no = data.xs(False, level='present') if False in data.index.get_level_values('present') else data.iloc[:0].droplevel('present')
            both = yes.index.intersection(no.index)
            yes, no = yes.reindex(both), no.reindex(both)
            row = dict(worker_id=worker, matching=matching, relevant_events=len(z),
                       relevant_Q_events=int(z.Q_common6.sum()), relevant_pairs=z.pair_key.nunique(),
                       relevant_buildings=z.building.nunique(), matched_strata=len(both),
                       matched_pairs=len(set(both.get_level_values('pair_key'))),
                       matched_buildings=len(set(both.get_level_values('building'))),
                       present_events_retained=int(yes.events.sum()), absent_events_retained=int(no.events.sum()))
            row['events_retained'] = row['present_events_retained']+row['absent_events_retained']
            row['event_retention_fraction'] = row['events_retained']/len(z)
            for metric in cols:
                old = pair_means(z, [metric])
                row['original_pair_equal__'+metric] = old[metric].mean()
                row['original_building_equal__'+metric] = old.groupby('building')[metric].mean().mean()
                valid = yes[metric].notna() & no[metric].notna()
                for tag, table in [('present', yes), ('absent', no)]:
                    p = table.loc[valid, [metric]].groupby(PAIR).mean()
                    row['matched_'+tag+'_pair_equal__'+metric] = p[metric].mean()
                    row['matched_'+tag+'_building_equal__'+metric] = p.groupby('building')[metric].mean().mean()
                if metric == 'B8L2_extra':
                    row['matched_Q_strata'] = int(valid.sum())
                    pp = yes.loc[valid, [metric]].groupby(PAIR).mean()
                    pn = no.loc[valid, [metric]].groupby(PAIR).mean()
                    row['matched_Q_pairs'] = len(pp); row['matched_Q_buildings'] = len(set(pp.index.get_level_values('building')))
                    row['Q_events_retained'] = int(yes.loc[valid, 'quality_events'].sum()+no.loc[valid, 'quality_events'].sum())
                    row['matched_present_positive_pair_fraction'] = pp[metric].gt(0).mean()
                    row['matched_absent_positive_pair_fraction'] = pn[metric].gt(0).mean()
                    # 显式量化“匹配层等权”与主文“配置等权”的不同，避免暗中替换原结果。
                    for tag, table in [('present', yes), ('absent', no)]:
                        alt = table.loc[valid, [metric]].groupby(CONFIG).mean().groupby(PAIR).mean()
                        reweight.append(dict(worker_id=worker, matching=matching, state=tag,
                                             matched_stratum_equal=row['matched_'+tag+'_pair_equal__'+metric],
                                             configuration_equal=alt[metric].mean()))
            results.append(row)
    actual = pd.DataFrame(results)
    keys = ['worker_id', 'matching']
    check_frame(actual, expected.reset_index(), keys, [c for c in actual if c not in keys], 'member_matching', checks)
    actual.to_csv(out/'MEMBER_MATCHED_SUMMARY.csv', index=False)
    pd.DataFrame(reweight).to_csv(out/'MEMBER_WEIGHTING_COMPARISON.csv', index=False)


def audit_paths(read, out, checks):
    t = read('anchor_paths/ANCHOR_PATH_EFFECTS.csv.gz')
    assert len(t) == 35603 and t.path_transition_id.is_unique
    z = t.assign(comparison=t.comparison_tags.str.split('|')).explode('comparison')
    keys = ['study_type', 'comparison', 'method', 'condition', 'ordinary_comparable',
            'source_role_key', 'target_role_key', 'source_class', 'target_class',
            'pair_key', 'building', 'groups', 'm_small', 'm_large', 'n_small', 'n_large']
    computed = []
    for metric in PATH_METRICS:
        columns = [metric+'_'+x for x in PATH_EFFECTS]
        d = z.groupby(keys, dropna=False)[columns].mean().rename(columns=dict(zip(columns, PATH_EFFECTS)))
        d['attempted_transitions'] = z.groupby(keys, dropna=False).size()
        d['common_transitions'] = z.groupby(keys, dropna=False)[metric+'_common12'].sum()
        d = d.reset_index(); d['metric'] = metric; computed.append(d)
    actual = pd.concat(computed, ignore_index=True)
    check_frame(actual, read('anchor_paths/PATH_PAIR_CONFIG_SUMMARY.csv.gz'), ['metric']+keys,
                PATH_EFFECTS+['attempted_transitions', 'common_transitions'], 'all_path_pair_configurations', checks)
    pk = [c for c in ['metric']+keys if c not in ['source_class', 'target_class', 'm_small', 'm_large', 'n_small', 'n_large']]
    pair = actual.groupby(pk, dropna=False)[PATH_EFFECTS].mean().reset_index()
    check_frame(pair, read('anchor_paths/PATH_PAIR_SUMMARY.csv.gz'), pk, PATH_EFFECTS, 'all_path_pair_summary', checks)
    pair.to_csv(out/'PATH_PAIR_SUMMARY.csv.gz', index=False)

    expected = read('anchor_paths/KEY_PATH_JOINT_METRICS.csv')
    direction = t[t.method.eq('V3_BEHAVIOR') & t.ordinary_comparable &
                  t.source_role_key.eq('TURN3:常规转折') & t.target_role_key.eq('TURN3:较多转折')]
    combined_metrics = ['B8L2', 'D10', 'fusion_turn_n', 'fusion_short_turn_edges',
                        'fusion_redundancy_n', 'S_bottom_deg', 'dir', 'Hmean', 'height_mean_ratio']
    cfg = PAIR+['source_class', 'target_class', 'm_small', 'm_large', 'n_small', 'n_large']
    output = []
    for r in expected.itertuples(index=False):
        if r.comparison.startswith('fixed_A'):
            large = int(r.comparison[-1])
            d = direction[direction.study_type.eq('fixed_A_scale') & direction.m_small.eq(5) & direction.m_large.eq(large)]
        else:
            d = direction[direction.study_type.eq('fixed_XYZ_background') & direction.comparison_tags.str.split('|').map(lambda x: r.comparison in x)]
        common = (d[[m+'_common12' for m in combined_metrics]].all(axis=1)
                  if r.domain == 'joint_Q_structure_position' else d.QT_common12)
        d = d[common]
        suffixes = ['A_change', 'B_change', 'C_change', 'net_C_minus_B_change', 'extra_amplitude_change']
        columns = [r.metric+'_'+ef for ef in suffixes]
        configs = d.groupby(cfg)[columns].mean(); pairs = configs.groupby(PAIR).mean()
        row = dict(comparison=r.comparison, domain=r.domain, metric=r.metric,
                   transitions=len(d), configurations=len(configs), pairs=len(pairs),
                   buildings=len(set(pairs.index.get_level_values('building'))))
        for c, suffix in zip(columns, suffixes):
            row['pair_equal__'+suffix] = pairs[c].mean()
            row['building_equal__'+suffix] = pairs.groupby('building')[c].mean().mean()
            row['supported_pairs__'+suffix] = int(pairs[c].notna().sum())
            row['positive_pairs__'+suffix] = int(pairs[c].gt(0).sum())
            row['negative_pairs__'+suffix] = int(pairs[c].lt(0).sum())
        output.append(row)
    actual = pd.DataFrame(output)
    keys = ['comparison', 'domain', 'metric']
    check_frame(actual, expected, keys, [c for c in actual if c not in keys], 'key_path_metrics', checks)
    actual.to_csv(out/'KEY_PATH_JOINT_METRICS.csv', index=False)


def main(root, out):
    out.mkdir(parents=True, exist_ok=True)
    read = lambda file: pd.read_csv(root/file, low_memory=False)
    checks = []
    e = read('results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz')
    for c in ['D_members', 'X_members', 'Y_members', 'Z_members']:
        e[c] = e[c].fillna('')
    audit_conditions(e, read, out, checks)
    print('逐楼删除、方向、难度与方向贡献核对完成', flush=True)
    audit_history(e, read, out, checks)
    print('历史 Q 块均值与共同支持核对完成', flush=True)
    audit_members(e, read, out, checks)
    print('28 人两种匹配核对完成', flush=True)
    audit_paths(read, out, checks)
    pd.DataFrame(checks).to_csv(out/'NUMERIC_CHECKS.csv', index=False)
    receipt = dict(event_rows=len(e), checks=len(checks), numeric_values=sum(c['values'] for c in checks),
                   source='saved complete events independently checked against scalar endpoints by parent audit',
                   native_fusion_rerun=False, classification_training_rerun=False,
                   geometry_distance_recomputed_here=False)
    (out/'RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    main(args.root, args.out)
