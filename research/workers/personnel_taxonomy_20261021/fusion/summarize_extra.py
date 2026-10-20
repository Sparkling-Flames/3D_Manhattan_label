"""Reproduce supplementary ratios, difficulty, count paths, and final candidates.

This reads frozen results only. It neither selects new teams nor changes labels.
All population summaries average events within image, images within building,
then buildings equally. Nested paths are descriptive selected mechanisms.
"""
from collections import Counter
import json
import math
import numpy as np
import pandas as pd
import study as s


def aggregate(frame, keys, metrics):
    per_image = frame.groupby(keys + ['building', 'image'], dropna=False)[metrics].mean().reset_index()
    per_building = per_image.groupby(keys + ['building'], dropna=False)[metrics].mean().reset_index()
    rows = []
    for key, g in frame.groupby(keys, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        b = per_building
        for k, v in zip(keys, key):
            b = b[b[k].eq(v)]
        row = dict(zip(keys, key), events=len(g), images=g.image.nunique(), buildings=g.building.nunique())
        row.update({m: b[m].mean() for m in metrics})
        for m in metrics:
            row[m + '_events'] = int(g[m].notna().sum())
        rows.append(row)
    return pd.DataFrame(rows), per_image, per_building


def add_common(frame):
    frame = frame.copy()
    common = frame.within_valid_distance & frame.cross_valid_distance
    frame['common_distance_pair'] = common.astype(int)
    for arm in ('within', 'cross'):
        for metric in ('bev_mean_h', 'top_mean_h'):
            frame[arm + '_' + metric + '_common'] = frame[arm + '_' + metric].where(common)
    return frame


def compact_counts(team, tier='coarse'):
    return '|'.join(f'{k}:{v}' for k, v in sorted(team['type_counts'][tier].items()))


def main_structure():
    data = pd.read_csv(s.OUT / 'EVENTS.csv.gz')
    teams = s.read(s.OUT / 'TEAMS.json.gz')
    # Preserve both hierarchy count vectors, even when the design changed only one.
    for arm in 'ABC':
        for tier in ('coarse', 'fine'):
            data[arm + '_' + tier + '_counts'] = data[arm + '_team_key'].map(lambda k: compact_counts(teams[k], tier))
        data[arm + '_detail_count'] = data[arm + '_team_key'].map(
            lambda k: teams[k]['type_counts']['coarse'].get('M1', teams[k]['type_counts']['coarse'].get('S1', 0)))
        data[arm + '_detail_fraction'] = data[arm + '_detail_count'] / data.n
    keep = ['event_id', 'pool_id', 'image', 'building', 'condition', 'layer', 'difficulty',
            'design_tier', 'outgoing_class', 'incoming_class', 'n', 'm', 'net_B8L2', 'net_D10', 'net_nodes']
    keep += [a + '_' + k for a in 'ABC' for k in ('team_key', 'coarse_counts', 'fine_counts', 'detail_count', 'detail_fraction')]
    s.csv(s.OUT / 'CLASS_COMPOSITION_EVENTS.csv.gz', data[keep])
    metrics = ['net_B8L2', 'net_D10', 'net_nodes', 'net_ref_node_recall_5',
               'within_abs_B8L2_change', 'cross_abs_B8L2_change', 'within_different_count', 'cross_different_count']
    keys = ['condition', 'layer', 'outgoing_class', 'incoming_class', 'n', 'm',
            'B_detail_count', 'C_detail_count', 'B_detail_fraction', 'C_detail_fraction']
    ratio, _, _ = aggregate(data[data.design_tier.eq('coarse')], keys, metrics)
    s.csv(s.OUT / 'EXACT_RATIO_EFFECTS.csv', ratio)
    for condition in ('manual', 'semi'):
        sub = data[data.condition.eq(condition) & data.layer.eq('ordinary_' + condition) & data.design_tier.eq('coarse')]
        difficulty, _, _ = aggregate(sub, ['condition', 'difficulty', 'outgoing_class', 'incoming_class', 'n', 'm'], metrics)
        s.csv(s.OUT / (condition.upper() + '_DIFFICULTY_EFFECTS.csv'), difficulty)


def nested():
    data = pd.read_csv(s.OUT / 'NESTED_EVENTS.csv')
    teams = s.read(s.OUT / 'NESTED_TEAMS.json.gz')
    for arm in 'ABC':
        data[arm + '_coarse_counts'] = data[arm + '_team_key'].map(lambda k: compact_counts(teams[k]))
        data[arm + '_detail_count'] = data[arm + '_team_key'].map(
            lambda k: teams[k]['type_counts']['coarse'].get('M1', teams[k]['type_counts']['coarse'].get('S1', 0)))
        data[arm + '_detail_fraction'] = data[arm + '_detail_count'] / data.n
    data['net_B8L2'] = data.C_B8L2 - data.B_B8L2
    data['net_D10'] = data.C_D10 - data.B_D10
    data['net_nodes'] = data.C_nodes - data.B_nodes
    s.csv(s.OUT / 'NESTED_COMPOSITION_PATHS.csv', data)
    rows = []
    for path_id, g in data.groupby('path_id'):
        g = g.sort_values('n')
        first = g.iloc[0]
        row = {k: first[k] for k in ('path_id', 'image', 'building', 'condition', 'layer', 'difficulty', 'outgoing_class', 'incoming_class', 'm')}
        row.update(n_min=int(g.n.min()), n_max=int(g.n.max()), prefixes=len(g),
                   scored_prefixes=int(g.net_B8L2.notna().sum()), positive_prefixes=int((g.net_B8L2 > 0).sum()),
                   negative_prefixes=int((g.net_B8L2 < 0).sum()),
                   net_B8L2_min=g.net_B8L2.min(), net_B8L2_max=g.net_B8L2.max(),
                   first_net_B8L2=g.net_B8L2.iloc[0], last_net_B8L2=g.net_B8L2.iloc[-1],
                   first_B_counts=g.B_coarse_counts.iloc[0], first_C_counts=g.C_coarse_counts.iloc[0],
                   last_B_counts=g.B_coarse_counts.iloc[-1], last_C_counts=g.C_coarse_counts.iloc[-1])
        rows.append(row)
    s.csv(s.OUT / 'NESTED_PATH_SUMMARY.csv', pd.DataFrame(rows))
    steps = pd.read_csv(s.OUT / 'NESTED_STEPS.csv')
    rows = []
    for (condition, layer), g in steps.groupby(['condition', 'layer']):
        rows.append(dict(condition=condition, layer=layer, paths=g.path_id.nunique(), images=g.image.nunique(),
            adjacent_arm_comparisons=len(g), threshold_rise_comparisons=int((g.threshold_after > g.threshold_before).sum()),
            retained_partition_changed_comparisons=int(g.retained_partition_changed.sum()),
            threshold_only_loss_groups=int(g.threshold_only_losses.sum()),
            threshold_only_loss_comparisons=int((g.threshold_only_losses > 0).sum()),
            new_vote_gain_groups=int(g.new_vote_gains.sum()), new_vote_gain_comparisons=int((g.new_vote_gains > 0).sum()),
            scored_comparisons=int((g.B8L2_before.notna() & g.B8L2_after.notna()).sum())))
    s.csv(s.OUT / 'NESTED_MECHANISM_SUMMARY.csv', pd.DataFrame(rows))


def a2():
    data = add_common(pd.read_csv(s.OUT / 'a2_specific/EVENTS.csv.gz'))
    metrics = ['common_distance_pair'] + [a + '_' + m for a in ('within', 'cross') for m in (
        'bev_mean_h_common', 'top_mean_h_common', 'different_count', 'abs_B8L2_change', 'joint_stable_main')]
    summary, per_image, per_building = aggregate(data, ['condition', 'layer', 'n', 'm'], metrics)
    summary['common_distance_events'] = [int(data[(data.condition == r.condition) & (data.layer == r.layer) &
        (data.n == r.n) & (data.m == r.m)].common_distance_pair.sum()) for r in summary.itertuples()]
    s.csv(s.OUT / 'A2_SPECIFIC_POOLED.csv', summary)


def log_area(team):
    xy = (team.get('geometry') or {}).get('footprint')
    if xy is None or len(xy) < 3:
        return np.nan
    a = np.asarray(xy, dtype=float)
    area = abs(np.dot(a[:, 0], np.roll(a[:, 1], 1)) - np.dot(a[:, 1], np.roll(a[:, 0], 1))) / 2
    return math.log(area) if area > 0 else np.nan


def position():
    target = s.OUT / 'semi_position'
    data = add_common(pd.read_csv(target / 'EVENTS.csv.gz'))
    teams = s.read(target / 'TEAMS.json.gz')
    for arm in 'ABC':
        data[arm + '_height_mean_ratio'] = data[arm + '_team_key'].map(lambda k: teams[k].get('height_mean_ratio'))
        data[arm + '_log_height'] = np.log(data[arm + '_height_mean_ratio'])
        data[arm + '_log_area'] = data[arm + '_team_key'].map(lambda k: log_area(teams[k]))
        data[arm + '_class_counts'] = data[arm + '_team_key'].map(lambda k: compact_counts(teams[k]))
    for metric in ('log_height', 'log_area', 'height_mean_ratio'):
        data['net_' + metric] = data['C_' + metric] - data['B_' + metric]
        data['within_signed_' + metric] = data['B_' + metric] - data['A_' + metric]
        data['cross_signed_' + metric] = data['C_' + metric] - data['A_' + metric]
    metrics = ['net_B8L2', 'net_D10', 'net_log_height', 'net_log_area', 'net_height_mean_ratio',
               'within_signed_log_height', 'cross_signed_log_height', 'common_distance_pair']
    metrics += [a + '_' + m for a in ('within', 'cross') for m in ('bev_mean_h_common', 'top_mean_h_common', 'abs_B8L2_change')]
    summary, per_image, per_building = aggregate(data, ['outgoing_class', 'incoming_class', 'n', 'm'], metrics)
    summary['height_relative_change_pct'] = np.expm1(summary.net_log_height) * 100
    summary['area_relative_change_pct'] = np.expm1(summary.net_log_area) * 100
    summary['negative_height_events'] = [int((data[(data.outgoing_class == r.outgoing_class) &
        (data.incoming_class == r.incoming_class) & (data.n == r.n) & (data.m == r.m)].net_log_height < 0).sum()) for r in summary.itertuples()]
    summary['positive_height_events'] = [int((data[(data.outgoing_class == r.outgoing_class) &
        (data.incoming_class == r.incoming_class) & (data.n == r.n) & (data.m == r.m)].net_log_height > 0).sum()) for r in summary.itertuples()]
    s.csv(target / 'SIGNED_GEOMETRY_EVENTS.csv.gz', data)
    s.csv(target / 'SIGNED_GEOMETRY_SUMMARY.csv', summary)
    s.csv(target / 'SIGNED_GEOMETRY_PER_BUILDING.csv', per_building)


def scope():
    rows = []
    sources = [('B_new', s.OUT / 'EVENTS.csv.gz', s.OUT / 'TEAMS.json.gz'),
               ('B_nested_paths', s.OUT / 'NESTED_EVENTS.csv', s.OUT / 'NESTED_TEAMS.json.gz'),
               ('A2_specific', s.OUT / 'a2_specific/EVENTS.csv.gz', s.OUT / 'a2_specific/TEAMS.json.gz'),
               ('Semi_position_specific', s.OUT / 'semi_position/EVENTS.csv.gz', s.OUT / 'semi_position/TEAMS.json.gz')]
    combined_keys = set()
    for design, events_path, teams_path in sources:
        data = pd.read_csv(events_path)
        teams = s.read(teams_path)
        combined_keys.update(teams)
        for layer, g in data.groupby('layer'):
            keys = set(g.A_team_key) | set(g.B_team_key) | set(g.C_team_key)
            chosen = [teams[k] for k in keys]
            rows.append(dict(design=design, layer=layer, ABC_events=len(g), unique_teams=len(keys),
                images=g.image.nunique(), pools=g.pool_id.nunique(), buildings=g.building.nunique(),
                workers=len({w for t in chosen for w in t['member_workers']}),
                records=len({r for t in chosen for r in t['member_object_ids']}),
                teams_with_B8L2=sum(t.get('B8L2') is not None for t in chosen),
                teams_below_four=sum(t.get('below_four', False) for t in chosen)))
    jtc = s.read(s.OUT / 'JTC26_PREDECLARED.json.gz')
    jt = list(jtc['teams'].values())
    joint_keys = combined_keys | {t['team_key'] for t in jt}
    rows.append(dict(design='JTC26_user_prescribed_pair', layer='ordinary_manual', ABC_events=0,
        unique_teams=len(jt), images=1, pools=1, buildings=1,
        workers=len({w for t in jt for w in t['member_workers']}),
        records=len({r for t in jt for r in t['member_object_ids']}),
        teams_with_B8L2=sum(t.get('B8L2') is not None for t in jt), teams_below_four=0))
    s.csv(s.OUT / 'FUSION_SCOPE.csv', pd.DataFrame(rows))
    s.save(s.OUT / 'EXTRA_SUMMARY_RECEIPT.json', dict(new_design_unique_team_union=len(combined_keys),
        four_design_endpoint_sum=3828 + 1008 + 858 + 114,
        additional_prescribed_JTC26_teams=len({t['team_key'] for t in jt} - combined_keys),
        all_new_unique_teams_including_prescribed_case=len(joint_keys),
        reproduced_prescribed_JTC26_B8L2={w: t['B8L2'] for w, t in jtc['teams'].items()},
        added_A2_and_position_teams=858 + 114, all_experiments_completed=True,
        extra_testing_stopped=True, aggregation='event mean -> image equal -> building equal',
        height_definition='height_mean_ratio = continuous height moment / bound reference height moment; log(C/B) cancels reference',
        nested_boundary='selected fixed member-order paths; group counts and comparison counts overlap and must not be summed'))


if __name__ == '__main__':
    main_structure()
    nested()
    a2()
    position()
    scope()
    print('Saved ratio, difficulty, complete paths, A2 pooled, signed Semi geometry, and scope summaries.')
