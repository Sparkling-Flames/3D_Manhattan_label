"""只读已交付端点，建立 v2.1 模拟换人证据链；不执行融合或重新分类。"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/workers/personnel_v21_reselection_20261029'
ADD = BASE / 'additional_delivery/packages'
OUT = ROOT / 'research/data/releases/v2.1/simulated_population_evidence/exchange'
GROUP = ['method', 'condition', 'scope', 'role_direction']


def read(path, **kw):
    return pd.read_csv(path, low_memory=False, **kw)


def rel(path):
    return Path(path).relative_to(ROOT).as_posix()


def members(value):
    if pd.isna(value) or value == '':
        return []
    if str(value).startswith('['):
        return list(json.loads(value))
    return str(value).split('|')


def equal_image_stats(frame, value):
    """事件先池内平均，再同图等池平均；图片等权，建筑再平均。"""
    valid = frame[np.isfinite(pd.to_numeric(frame[value], errors='coerce'))]
    pools = valid.groupby(['building', 'image', 'pool_id'], dropna=False)[value].mean()
    images = pools.groupby(level=['building', 'image']).mean()
    buildings = images.groupby(level='building').mean()
    return dict(valid_events=len(valid), valid_images=len(images), valid_buildings=len(buildings),
                mean_image=float(images.mean()), mean_building=float(buildings.mean()),
                positive_images=int((images > 0).sum()), positive_buildings=int((buildings > 0).sum()))


def paired_change(b0, b1, c0, c1):
    """四端点共同可评的 ΔC、ΔB、Δ(C-B)，缺失不以零填充。"""
    a = np.column_stack([b0, b1, c0, c1]).astype(float)
    ok = np.isfinite(a).all(axis=1)
    dc = np.where(ok, a[:, 3] - a[:, 2], np.nan)
    db = np.where(ok, a[:, 1] - a[:, 0], np.nan)
    return dc, db, dc - db


def validate_blocks(row, ac_only=False):
    d, x, z = (set(members(row[k])) for k in ['D', 'X', 'Z'])
    y = set() if ac_only else set(members(row['Y']))
    blocks = [d, x, z] if ac_only else [d, x, y, z]
    assert all(not a & b for i, a in enumerate(blocks) for b in blocks[i + 1:])
    assert len(d) == int(row['n']) - int(row['m'])
    assert len(x) == len(z) == int(row['m'])
    if not ac_only:
        assert len(y) == int(row['m'])
    for arm, block in [('A', x), ('C', z)] + ([] if ac_only else [('B', y)]):
        seq = members(row[f'{arm}_members'])
        assert len(seq) == len(set(seq)) == int(row['n'])
        assert set(seq) == d | block
    return d, x, y, z


def assert_numeric(actual, expected):
    assert np.allclose(np.asarray(actual, float), np.asarray(expected, float), atol=1e-8, rtol=1e-8, equal_nan=True)


def summarize(frame, keys, metrics, stage, source):
    rows = []
    for key, g in frame.groupby(keys, dropna=False, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        r = dict(zip(keys, key))
        r.update(stage=stage, registered_events=len(g), registered_pools=g.pool_id.nunique(),
                 registered_images=g.image.nunique(), registered_buildings=g.building.nunique(),
                 source_table=rel(source))
        for label, col in metrics.items():
            r.update({f'{label}_{k}': v for k, v in equal_image_stats(g, col).items()})
        if 'n' in r and 'm' in r:
            r['replacement_fraction'] = r['m'] / r['n']
            r['replacement_band'] = 'exact_half' if 2 * r['m'] == r['n'] else ('above_half' if 2 * r['m'] > r['n'] else 'below_half')
        rows.append(r)
    return pd.DataFrame(rows)


def write(frame, name):
    frame.to_csv(OUT / name, index=False, encoding='utf-8-sig')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    snapshots = [ROOT / 'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',
                 ROOT / 'research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json']
    pools, objects, snapshot_for = {}, {}, {}
    for snapshot in snapshots:
        for p in json.loads(snapshot.read_text(encoding='utf-8'))['images']:
            assert p['pool_id'] not in pools
            pools[p['pool_id']] = p
            objects[p['pool_id']] = {r['worker_id']: r['object_id'] for r in p['records']}
            snapshot_for[p['pool_id']] = rel(snapshot)
    assert len(pools) == 294
    epath = ADD / '05A/experiment/global_screen_design/EVENTS_EXACT.csv.gz'
    spath = ADD / '05A/experiment/global_screen_endpoints/ENDPOINT_SCALARS.csv.gz'
    fpath = ADD / '05A/analysis/global_screen_compact/EVENT_EFFECTS_COMPLETE.csv.gz'
    lpath = ADD / '05A/classification/MAIN45_LABELS_ALL_LOBO.csv.gz'
    rpath = ADD / '05B/analysis/global_screen_summary/EVENT_ROLE_LINKS.csv.gz'
    framepath = ADD / '05B/experiment/global_screen_capacity/SCREEN_POOL_FRAME.csv'
    events = read(epath)
    scalars = read(spath)
    effects = read(fpath)
    labels = read(lpath)
    roles = read(rpath)
    frame = read(framepath)
    assert events.event_id.is_unique and scalars.team_key.is_unique and effects.event_id.is_unique
    assert set(events.event_id) == set(effects.event_id) == set(roles.event_id)
    ss = scalars.set_index('team_key')
    ee = events.set_index('event_id')
    labelmap = labels.set_index(['method', 'heldout_building', 'worker_id']).class_id.to_dict()
    endpoint_members = {r.team_key: set(members(r.member_workers)) for r in scalars.itertuples()}
    selected = frame[frame.selected.astype(str).str.lower().eq('true')]
    assert set(events.pool_id) <= set(selected.pool_id)
    defects = []
    for r in scalars.to_dict('records'):
        w = members(r['member_workers'])
        assert len(w) == len(set(w)) == int(r['k'])
        expected = [objects[r['pool_id']][x] for x in w]
        if members(r['member_object_ids']) != expected:
            # Historical scalar exporter joined a pre-joined string character by character.
            assert r['member_object_ids'] == '|'.join('|'.join(expected))
            defects.append(dict(team_key=r['team_key'], pool_id=r['pool_id'], k=int(r['k']),
                                supplied_object_token_count=len(members(r['member_object_ids'])),
                                restored_member_object_ids='|'.join(expected), snapshot=snapshot_for[r['pool_id']],
                                recovery='worker_id -> INPUT_SNAPSHOT.records.object_id'))
    print('loaded global', len(events), 'endpoint object defects', len(defects), flush=True)
    for r in events.to_dict('records'):
        d, x, y, z = validate_blocks(r)
        assert r['building'] == r['heldout_building'] == pools[r['pool_id']]['meta']['building']
        assert all(labelmap[(r['method'], r['heldout_building'], w)] == r['source_class'] for w in x | y)
        assert all(labelmap[(r['method'], r['heldout_building'], w)] == r['target_class'] for w in z)
        assert r['source_class'] != r['target_class']
        for arm in 'ABC':
            k = r[f'{arm}_team_key']
            assert endpoint_members[k] == set(members(r[f'{arm}_members']))
            assert ss.at[k, 'pool_id'] == r['pool_id']
            assert ss.at[k, 'reference_id'] == r['reference_id']
    merged = effects.copy()
    for arm in 'ABC':
        assert (merged[f'{arm}_team_key'] == merged.event_id.map(ee[f'{arm}_team_key'])).all()
    for arm in 'ABC':
        merged[f'{arm}_Q'] = merged[f'{arm}_team_key'].map(ss.B8L2)
    for first, second in [('B', 'A'), ('C', 'A'), ('C', 'B')]:
        assert_numeric(merged[f'B8L2_{first}{second}'], merged[f'{first}_Q'] - merged[f'{second}_Q'])
    valid3 = merged[['A_Q', 'B_Q', 'C_Q']].notna().all(axis=1)
    assert_numeric(merged.B8L2_within, (merged.B_Q - merged.A_Q).abs().where(valid3))
    assert_numeric(merged.B8L2_cross, ((merged.C_Q - merged.A_Q).abs() + (merged.C_Q - merged.B_Q).abs()).div(2).where(valid3))
    assert_numeric(merged.B8L2_gap, merged.B8L2_cross - merged.B8L2_within)
    effects = effects.merge(roles[['event_id', 'role_direction']], on='event_id', validate='one_to_one') if 'role_direction' not in effects else effects
    summary = summarize(effects, GROUP + ['n', 'm'],
                        dict(net_CB='B8L2_CB', change_CA='B8L2_CA', within='B8L2_within', cross='B8L2_cross', amplitude_gap='B8L2_gap'),
                        'global_registered_ABC', fpath)
    write(summary, 'GLOBAL_ALL_N_M_CONDITIONS.csv')
    write(summary[summary.replacement_band.eq('exact_half')], 'EXACT_HALF_CONDITIONS.csv')
    write(summary[summary.replacement_band.eq('above_half')], 'ABOVE_HALF_CONDITIONS.csv')
    write(pd.DataFrame(defects, columns=['team_key', 'pool_id', 'k', 'supplied_object_token_count', 'restored_member_object_ids', 'snapshot', 'recovery']), 'GLOBAL_OBJECT_ID_RECOVERY.csv')
    dimpath = ADD / '05B/analysis/global_screen_summary/ALL_DIRECTION_N_M_RESULTS.csv.gz'
    metric_names = ['B8L2_CA', 'B8L2_CB', 'B8L2_within', 'B8L2_cross', 'B8L2_gap',
                    'boundary_loss_CB', 'direction_loss_CB', 'height_loss_CB', 'IoU3D100_CB',
                    'geometry_bev_distance_cross', 'geometry_bev_distance_gap', 'geometry_area_h2_CB',
                    'fusion_turn_n_CB', 'height_mean_h_CB', 'record_time_CB_pct_source_matched',
                    'A_failed', 'B_failed', 'C_failed', 'A_incomplete', 'B_incomplete', 'C_incomplete',
                    'failure_or_loss10_CB']
    dims = read(dimpath, usecols=lambda c: c in GROUP + ['n', 'm', 'events', 'images', 'buildings'] or
                any(c == f'{metric}_{suffix}' for metric in metric_names for suffix in
                    ['mean_image', 'valid_images', 'positive_images', 'mean_building', 'valid_buildings']))
    check_summary = summary.merge(dims, on=GROUP + ['n', 'm'], validate='one_to_one')
    for short, full in [('net_CB', 'B8L2_CB'), ('change_CA', 'B8L2_CA'), ('within', 'B8L2_within'), ('cross', 'B8L2_cross'), ('amplitude_gap', 'B8L2_gap')]:
        # Source supplies building summaries for signed Q / gap, not within/cross.
        suffixes = ['mean_image', 'valid_images'] if short in ['within', 'cross'] else ['mean_image', 'valid_images', 'mean_building', 'valid_buildings']
        for suffix in suffixes:
            assert_numeric(check_summary[f'{short}_{suffix}'], check_summary[f'{full}_{suffix}'])
    dims['source_table'] = rel(dimpath)
    dims['validation'] = 'Q和支持独立复算一致；其余维度为保留字段的交付汇总，未逐项重新计算'
    write(dims, 'ALL_DIMENSION_N_M_RESULTS.csv')
    for stem, output in [('DIRECTION_FORMAL_DIFFICULTY_RESULTS', 'FORMAL_DIFFICULTY_RESULTS.csv'),
                         ('DIRECTION_STRUCTURE_OPPORTUNITY_RESULTS', 'STRUCTURAL_CONDITION_RESULTS.csv')]:
        source = ADD / f'05B/analysis/global_screen_summary/{stem}.csv.gz'
        stratified = read(source, usecols=lambda c: c in GROUP + ['n', 'm', 'layer', 'official_difficulty', 'geometric_challenge', 'events', 'images', 'buildings',
                          'A_failed_events', 'B_failed_events', 'C_failed_events', 'ABC_scored_events',
                          'Q_loss10_CB_events_valid', 'Q_loss10_CB_events'] or
                          any(c == f'{metric}_{suffix}' for metric in metric_names for suffix in
                              ['mean_image', 'valid_images', 'positive_images', 'mean_building', 'valid_buildings']))
        stratified['source_table'] = rel(source)
        stratified['validation'] = '原交付逐条件数值；未全表独立重算；难度未知原样保留'
        write(stratified, output)
    difficulty_key = effects[(effects.method == 'OPPJOINT_K4') & (effects.scope == 'primary') &
                             (effects.condition == 'manual') & (effects.role_direction == 'q_rank_asc:1/4->4/4') &
                             (effects.n == 12) & (effects.m == 6)]
    difficulty_check = summarize(difficulty_key, GROUP + ['n', 'm', 'official_difficulty'],
                                  dict(net_CB='B8L2_CB', amplitude_gap='B8L2_gap'), 'global_difficulty_key', fpath)
    official_saved = read(OUT / 'FORMAL_DIFFICULTY_RESULTS.csv')
    diff_join = difficulty_check.merge(official_saved, on=GROUP + ['n', 'm', 'official_difficulty'], validate='one_to_one')
    for short, full in [('net_CB', 'B8L2_CB'), ('amplitude_gap', 'B8L2_gap')]:
        for suffix in ['mean_image', 'valid_images', 'positive_images']:
            assert_numeric(diff_join[f'{short}_{suffix}'], diff_join[f'{full}_{suffix}'])
    write(difficulty_check, 'DIFFICULTY_KEY_CHECKS.csv')

    # Equivalence means all folds have the same known-worker partition, ignoring class names.
    signatures = {}
    for method, g in labels.groupby('method'):
        signatures[method] = tuple((fold, tuple(sorted(tuple(sorted(c.worker_id)) for _, c in fg[fg.class_id.notna()].groupby('class_id'))),
                                   tuple(sorted(fg.loc[fg.class_id.isna(), 'worker_id'])))
                                  for fold, fg in g.groupby('heldout_building', sort=True))
    signature_ids = {s: f'P{i + 1:02d}' for i, s in enumerate(dict.fromkeys(signatures.values()))}

    # Exact nested n: same X/Y/Z, D only expands, and native endpoint scalars agree.
    npath = ADD / '05B/analysis/global_size_paths/EXACT_SIZE_PATH_EFFECTS.csv.gz'
    nested = read(npath)
    for r in nested.to_dict('records'):
        lo, hi = ee.loc[r['lower_event_id']], ee.loc[r['higher_event_id']]
        assert lo.pool_id == hi.pool_id == r['pool_id'] and lo.method == hi.method == r['method']
        assert lo['n'] == r['n_lower'] and hi['n'] == r['n_higher'] and lo['m'] == hi['m'] == r['m']
        assert set(members(lo.D)) < set(members(hi.D))
        assert set(members(r['background_added'])) == set(members(hi.D)) - set(members(lo.D))
        for block in 'XYZ':
            assert set(members(lo[block])) == set(members(hi[block])) == set(members(r[block]))
    for arm in 'ABC':
        for end in ['lower', 'higher']:
            assert_numeric(nested[f'{end}_{arm}_B8L2'], nested[f'{arm}_{end}_team_key'].map(ss.B8L2))
    dc, db, dn = paired_change(nested.lower_B_B8L2, nested.higher_B_B8L2, nested.lower_C_B8L2, nested.higher_C_B8L2)
    for col, v in [('paired_CB_delta_C_Q', dc), ('paired_CB_delta_B_Q', db), ('paired_CB_delta_net_CB_Q', dn)]:
        assert_numeric(nested[col], v)
    nsum = summarize(nested, GROUP + ['m', 'n_lower', 'n_higher'],
                     dict(delta_C='paired_CB_delta_C_Q', delta_B='paired_CB_delta_B_Q', delta_net_CB='paired_CB_delta_net_CB_Q'),
                     'fixed_XYZ_nested_n', npath)
    write(nsum, 'FIXED_XYZ_NESTED_N_CONDITIONS.csv')
    print('nested n checked', len(nested), flush=True)

    # Fixed A paths: every m uses identical original A and nested replacement blocks.
    fixed_path_rows, fixed_events = [], []
    for stage in ['fixed_A_m', 'refinement_m']:
        ps = read(BASE / f'experiment/{stage}_design/PATHS_EXACT.csv.gz')
        es = read(BASE / f'experiment/{stage}_design/EVENTS_EXACT.csv.gz').set_index('event_id')
        links = read(BASE / f'experiment/{stage}_design/PATH_EVENT_LINKS.csv.gz')
        fixed_events.append(es.reset_index())
        for r in ps.to_dict('records'):
            sub = links[links.path_id.eq(r['path_id'])].sort_values('m')
            xx, yy, zz = (members(r[k]) for k in ['Xmax_ordered', 'Ymax_ordered', 'Zmax_ordered'])
            d0 = set(members(r['D0']))
            for q in sub.to_dict('records'):
                ev = es.loc[q['event_id']]
                validate_blocks(ev)
                m = int(q['m'])
                assert ev.A_team_key == r['A_team_key']
                assert set(members(ev.X)) == set(xx[:m]) and set(members(ev.Y)) == set(yy[:m]) and set(members(ev.Z)) == set(zz[:m])
                assert set(members(ev.D)) == d0 | set(xx[m:])
            fixed_path_rows.append(dict(path_id=r['path_id'], method=r['method'], condition=r['condition'],
                                        pool_id=r['pool_id'], image=r['image'], building=r['building'], n=r['n'],
                                        scope='other_admitted' if 'admitted_space_extension' in snapshot_for[r['pool_id']] else 'primary',
                                        min_m=int(sub.m.min()), max_m=int(sub.m.max()),
                                        actual_m_values='|'.join(map(str, sorted(sub.m.astype(int).unique()))),
                                        exact_half_present=bool((sub.m * 2 == r['n']).any()),
                                        above_half_present=bool((sub.m * 2 > r['n']).any()),
                                        source_table=rel(BASE / f'experiment/{stage}_design/PATHS_EXACT.csv.gz')))
    fixedpaths = pd.DataFrame(fixed_path_rows)
    write(fixedpaths, 'FIXED_A_ACTUAL_PATHS.csv')
    mpath = BASE / 'analysis/scale_background_summary/FIXED_A_ALL_M_INCREMENT_METRICS.csv.gz'
    fixed = read(mpath, usecols=lambda c: c in GROUP + ['path_id', 'pool_id', 'image', 'building', 'n', 'm_small', 'm_large',
                            'event_small', 'event_large', 'A_B8L2', 'B_small_B8L2', 'B_large_B8L2', 'C_small_B8L2', 'C_large_B8L2',
                            'B8L2_C_increment_matched_CB', 'B8L2_B_increment_matched_CB', 'B8L2_net_increment_matched_CB'])
    dc, db, dn = paired_change(fixed.B_small_B8L2, fixed.B_large_B8L2, fixed.C_small_B8L2, fixed.C_large_B8L2)
    for col, v in [('B8L2_C_increment_matched_CB', dc), ('B8L2_B_increment_matched_CB', db), ('B8L2_net_increment_matched_CB', dn)]:
        assert_numeric(fixed[col], v)
    msum = summarize(fixed, GROUP + ['n', 'm_small', 'm_large'],
                     dict(delta_C='B8L2_C_increment_matched_CB', delta_B='B8L2_B_increment_matched_CB', delta_net_CB='B8L2_net_increment_matched_CB'),
                     'fixed_A_increase_m', mpath)
    write(msum, 'FIXED_A_ALL_M_CONDITIONS.csv')

    fepath = BASE / 'experiment/focused_design/EVENTS_EXACT.csv.gz'
    fe = read(fepath).set_index('event_id')
    fscalar = read(BASE / 'experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz').set_index('team_key')
    bpath = BASE / 'analysis/focused_contexts/FIXED_XYZ_BACKGROUND_CONTRASTS.csv.gz'
    background = read(bpath)
    for r in background.to_dict('records'):
        lo, hi = fe.loc[r['lower_event_id']], fe.loc[r['higher_event_id']]
        assert lo.pool_id == hi.pool_id == r['pool_id'] and lo['n'] == hi['n'] == r['n'] and lo['m'] == hi['m'] == r['m']
        for block in 'XYZ':
            assert set(members(lo[block])) == set(members(hi[block])) == set(members(r[block]))
        assert set(members(lo.D)) == set(members(r['D_low'])) and set(members(hi.D)) == set(members(r['D_high']))
    rawq = {}
    for end in ['lower', 'higher']:
        for arm in 'BC':
            keys = background[f'{end}_event_id'].map(fe[f'{arm}_team_key'])
            rawq[end + arm] = keys.map(fscalar.B8L2)
    dc, db, dn = paired_change(rawq['lowerB'], rawq['higherB'], rawq['lowerC'], rawq['higherC'])
    for col, v in [('C_Q_change_matched_CB', dc), ('B_Q_change_matched_CB', db), ('net_CB_Q_change_matched_CB', dn)]:
        assert_numeric(background[col], v)
    bsum = summarize(background, GROUP + ['n', 'm'],
                     dict(delta_C='C_Q_change_matched_CB', delta_B='B_Q_change_matched_CB', delta_net_CB='net_CB_Q_change_matched_CB'),
                     'fixed_XYZ_change_background', bpath)
    write(bsum, 'FIXED_XYZ_BACKGROUND_CONDITIONS.csv')

    acpath = BASE / 'analysis/direct_AC_combined_summary/EXACT_EVENTS_WITH_ROLES.csv.gz'
    ac = read(acpath)
    for row in ac.to_dict('records'):
        validate_blocks(row, ac_only=True)
    assert_numeric(ac.B8L2_CA, ac.C_B8L2 - ac.A_B8L2)
    acsum = summarize(ac, GROUP + ['n', 'm'], dict(change_CA='B8L2_CA'), 'direct_AC_large_team', acpath)
    acsum['comparison_has_B'] = False
    write(acsum, 'DIRECT_AC_CONDITIONS.csv')

    # Original 12/6 claim now has the actual screen frame, not only an author's flag.
    fp = BASE / 'analysis/focused_compact/EVENT_EFFECTS_COMPLETE.csv.gz'
    focus = read(fp)
    fr = read(BASE / 'analysis/focused_summary/EVENT_ROLE_LINKS.csv.gz')
    focus = focus.merge(fr[['event_id', 'role_direction']], on='event_id', validate='one_to_one') if 'role_direction' not in focus else focus
    opp = focus[(focus.method == 'OPPJOINT_K4') & (focus.n == 12) & (focus.m == 6) & (focus.scope == 'primary') & (focus.condition == 'manual')]
    assert len(opp) == 172
    opp = opp.copy()
    opp['in_actual_screen_frame'] = opp.pool_id.isin(selected.pool_id)
    opp['in_realized_screen_images'] = opp.image.isin(events.image)
    assert (opp.in_actual_screen_frame == opp.in_realized_screen_images).all()
    outside = opp[~opp.in_actual_screen_frame]
    oppimages = opp.groupby(['image', 'building', 'pool_id', 'in_actual_screen_frame', 'in_realized_screen_images'], dropna=False).B8L2_CB.mean().reset_index()
    write(oppimages, 'OPPJOINT_12_6_SCREEN_FRAME_CHECK.csv')
    assert opp.image.nunique() == 56 and outside.image.nunique() == 30
    outside_stats = equal_image_stats(outside, 'B8L2_CB')
    assert outside_stats['positive_images'] == 28
    assert np.isclose(outside_stats['mean_image'], 6.68713869)
    focus_summary = summarize(focus, GROUP + ['n', 'm'],
                         dict(net_CB='B8L2_CB', change_CA='B8L2_CA', within='B8L2_within', cross='B8L2_cross', amplitude_gap='B8L2_gap'),
                         'focused_ABC', fp)
    write(focus_summary, 'FOCUSED_ALL_N_M_CONDITIONS.csv')

    # A real registered event per sign and method, linked through workers to source objects.
    mechanism_path = BASE / 'stage06_cases/CASE_MECHANISM_SUMMARY.csv'
    mechanisms = read(mechanism_path)
    mech = mechanisms.set_index('event_id').to_dict('index')
    cases = []
    for method, g in effects.groupby('method'):
        for sign, mask in [('positive_CB', g.B8L2_CB.gt(0)), ('nonpositive_CB', g.B8L2_CB.le(0))]:
            gg = g[mask]
            if gg.empty:
                continue
            val = gg.B8L2_CB.median()
            row = gg.assign(_distance=(gg.B8L2_CB - val).abs()).sort_values(['_distance', 'event_id']).iloc[0]
            ev = ee.loc[row.event_id]
            r = dict(method=method, case_kind=sign, event_id=row.event_id, pool_id=row.pool_id, image=row.image,
                     building=row.building, condition=row.condition, scope=row.scope, n=int(row.n), m=int(row.m),
                     role_direction=row.role_direction, source_class=row.source_class, target_class=row.target_class,
                     Q_CA=row.B8L2_CA, Q_CB=row.B8L2_CB, amplitude_gap=row.B8L2_gap,
                     original_snapshot=snapshot_for[row.pool_id], source_event_table=rel(epath), labels_table=rel(lpath),
                     marking_evidence='traceable_real_originals',
                     mechanism_case_id=mech.get(row.event_id, {}).get('case_id', ''),
                     preplotted_mechanism=row.event_id in mech,
                     interpretation='方向内真实正/非正实例；不同角色方向不合并为统一优劣结论')
            for arm in 'ABC':
                workers = members(ev[f'{arm}_members'])
                r[f'{arm}_workers'] = '|'.join(workers)
                r[f'{arm}_object_ids'] = '|'.join(objects[row.pool_id][w] for w in workers)
                r[f'{arm}_team_key'] = ev[f'{arm}_team_key']
            cases.append(r)
    caseframe = pd.DataFrame(cases)
    write(caseframe, 'METHOD_ORIGINAL_CASES.csv')
    plotted = mechanisms.copy()
    for column in ['trace_file', 'figure_directory']:
        plotted[column] = plotted[column].map(lambda p: rel(BASE / 'stage06_cases' / p))
    plotted['original_file'] = plotted.original_file.map(lambda p: rel(BASE / p))
    plotted['source_table'] = rel(mechanism_path)
    write(plotted, 'PREPLOTTED_MECHANISM_CASES.csv')
    # Examples for each link of the chain retain the actual original method and endpoints.
    chain_cases = []
    fixed_e = pd.concat(fixed_events).drop_duplicates('event_id').set_index('event_id')
    sources = [
        ('fixed_A_increase_m', fixed, 'B8L2_net_increment_matched_CB', fixed_e, 'event_small', 'event_large', mpath),
        ('fixed_XYZ_change_background', background, 'net_CB_Q_change_matched_CB', fe, 'lower_event_id', 'higher_event_id', bpath),
        ('fixed_XYZ_nested_n', nested, 'paired_CB_delta_net_CB_Q', ee, 'lower_event_id', 'higher_event_id', npath),
        ('direct_AC_large_team', ac, 'B8L2_CA', ac.set_index('event_id'), None, 'event_id', acpath),
    ]
    for stage, data, metric, event_lookup, low_key, high_key, source_path in sources:
        for method, g in data.groupby('method'):
            for sign, mask in [('positive', g[metric].gt(0)), ('nonpositive', g[metric].le(0))]:
                gg = g[mask]
                if gg.empty:
                    continue
                r0 = gg.assign(_distance=(gg[metric] - gg[metric].median()).abs()).sort_values('_distance', kind='stable').iloc[0]
                r = dict(stage=stage, method=method, sign=sign, metric=metric, value=r0[metric],
                         pool_id=r0.pool_id, image=r0.image, building=r0.building,
                         condition=r0.condition, scope=r0.scope, role_direction=r0.role_direction,
                         source_table=rel(source_path), original_snapshot=snapshot_for[r0.pool_id],
                         interpretation='按此真实方向和共同可评端点选择的中位附近实例，不能跨方向改贴方法标签')
                for name, key in [('lower', low_key), ('higher', high_key)]:
                    if key is None:
                        continue
                    ev = event_lookup.loc[r0[key]]
                    r[f'{name}_event_id'] = r0[key]
                    r[f'{name}_n'], r[f'{name}_m'] = ev['n'], ev['m']
                    for arm in ('AC' if stage == 'direct_AC_large_team' else 'ABC'):
                        ww = members(ev[f'{arm}_members'])
                        r[f'{name}_{arm}_workers'] = '|'.join(ww)
                        r[f'{name}_{arm}_object_ids'] = '|'.join(objects[r0.pool_id][w] for w in ww)
                        r[f'{name}_{arm}_team_key'] = ev[f'{arm}_team_key']
                chain_cases.append(r)
    write(pd.DataFrame(chain_cases), 'CHAIN_CASES.csv')

    adoption = read(BASE / 'stage07_adoption/ALL45_METHOD_ADOPTION_DECISIONS.csv')
    coverage, matrix = [], []
    for row in adoption.to_dict('records'):
        method = row['method']
        g = effects[effects.method.eq(method)]
        dimensions = {
            'actual_marking': (pd.Series(True, index=g.index), ['event_id', 'A/B/C_members', 'worker_id', 'object_id'], '完整真实原答可按楼外标签读取；单独绘制精讲案例数另列'),
            'quality': (g.B8L2_CB.notna(), ['B8L2_CA', 'B8L2_CB', 'B8L2_gap'], 'C-B质量净差与跨类/同类幅度分开；此有效数按C-B'),
            'quality_components': (g[['boundary_loss_CB', 'direction_loss_CB', 'height_loss_CB']].notna().all(axis=1), ['boundary_loss_CB', 'direction_loss_CB', 'height_loss_CB'], '三分项共同可评；loss减小代表改善'),
            'geometry': (g[['geometry_area_h2_CB', 'fusion_turn_n_CB', 'height_mean_h_CB']].notna().all(axis=1), ['geometry_area_h2_CB', 'fusion_turn_n_CB', 'height_mean_h_CB', 'IoU3D100_CB'], '面积/转角/高度共同可评，形状变动不自动等同质量改善'),
            'labor': (g.record_time_CB_pct_source_matched.notna(), ['record_time_CB_pct_source_matched', 'time_comparable_ABC', 'time_source_signature_A/B/C'], '仅原答劳动量且来源匹配；不能解释为新采集耗时或融合计算时长'),
            'failure_unscoreable': (g[['A_failed', 'B_failed', 'C_failed', 'A_incomplete', 'B_incomplete', 'C_incomplete']].notna().all(axis=1), ['A/B/C_failed', 'A/B/C_incomplete'], 'failed为原分析缺Q状态，须与几何失败及完整性分别读取；不可评不补零'),
            'difficulty': (g.official_difficulty.notna() & ~g.official_difficulty.astype(str).isin(['unknown', '未知', '']), ['official_difficulty', 'geometric_challenge', 'scope'], '正式难度与结构挑战分开；其他合法空间正式难度未知不强填'),
            'counterexamples': (g.B8L2_CB.notna(), ['B8L2_CB', 'B8L2_gap', 'Q_loss10'], '所有方向保留非正事件；它们只对该条件/方向构成反向实例，不否定其他多数趋势'),
        }
        mr = dict(method=method, family=row.get('route', ''), partition_equivalence_id=signature_ids[signatures[method]],
                  equivalent_configs='|'.join(m for m, s in signatures.items() if s == signatures[method]),
                  global_events=len(g), global_images=g.image.nunique(), global_buildings=g.building.nunique(),
                  exact_half_events=int((g.n == 2 * g.m).sum()), above_half_events=int((g.n < 2 * g.m).sum()),
                  actual_n_values='|'.join(map(str, sorted(g.n.unique()))), actual_m_values='|'.join(map(str, sorted(g.m.unique()))),
                  size_path_pairs=int(nested.method.eq(method).sum()),
                  fixed_A_paths=int(fixedpaths.method.eq(method).sum()),
                  fixed_XYZ_background_pairs=int(background.method.eq(method).sum()),
                  direct_AC_events=int(ac.method.eq(method).sum()),
                  original_answer_cases=int(caseframe.method.eq(method).sum()),
                  preplotted_mechanism_cases=int(mechanisms.method.eq(method).sum()),
                  adoption_status=row.get('adoption_status', ''), retained_use_zh=row.get('retained_use_zh', ''),
                  full_condition_table='GLOBAL_ALL_N_M_CONDITIONS.csv')
        for name, (mask, fields, note) in dimensions.items():
            valid = g[mask]
            status = 'available_all_registered' if len(valid) == len(g) else ('available_partial' if len(valid) else 'not_evaluable_in_registered_events')
            if name == 'actual_marking':
                status = 'traceable_originals_all'
            mr[name + '_status'] = status
            coverage.append(dict(method=method, dimension=name, status=status, registered_events=len(g),
                                 valid_events=len(valid), valid_images=valid.image.nunique(), valid_buildings=valid.building.nunique(),
                                 missing_events=len(g) - len(valid),
                                 nonpositive_CB_events=int(g.B8L2_CB.le(0).sum()) if name == 'counterexamples' else np.nan,
                                 negative_gap_events=int(g.B8L2_gap.lt(0).sum()) if name == 'counterexamples' else np.nan,
                                 source_table=rel(epath if name == 'actual_marking' else fpath),
                                 fields='|'.join(fields), note=note))
        matrix.append(mr)
    matrix = pd.DataFrame(matrix)
    assert len(matrix) == 45 and len(caseframe.method.unique()) == 45
    write(matrix, 'METHOD_EVIDENCE_MATRIX.csv')
    write(pd.DataFrame(coverage), 'METHOD_DIMENSION_COVERAGE.csv')
    chain = pd.concat([summary, focus_summary, msum, bsum, nsum, acsum], ignore_index=True)
    write(chain, 'CHAIN_SUMMARY.csv')

    badkeys = {r['team_key'] for r in defects}
    affected = events[[f'{a}_team_key' for a in 'ABC']].isin(badkeys).any(axis=1)
    checks = dict(schema_version=1, source_version='v2.1', computation='saved-endpoint/read-only reaggregation; no native fusion or classifier refit',
                  global_screen=dict(events=len(events), pools=events.pool_id.nunique(), images=events.image.nunique(), buildings=events.building.nunique(),
                              frame_selected_pools=len(selected), frame_selected_images=selected.image.nunique(),
                              frame_selected_buildings=selected.building.nunique(),
                              methods=events.method.nunique(), distinct_all_fold_partitions=len(signature_ids),
                              endpoint_rows=len(scalars), all_events_DXYZ_members_class_reference_checked=True,
                              all_Q_differences_match_saved_native_scalars=True,
                              object_id_export_defects=len(defects), events_referencing_object_id_defects=int(affected.sum()),
                              defect_recovery=('all recovered exactly from trusted worker_id and target pool snapshot; sources unchanged'
                                               if defects else 'none required; all object sequences match trusted worker_id and target pool snapshot'),
                              Q_affected_by_object_string=False),
                  nested_n=dict(pairs=len(nested), fixed_XYZ_nested_D_checked=True, all_Q_endpoints_match_scalars=True, shared_four_endpoint_deltas_checked=True),
                  fixed_A=dict(paths=len(fixedpaths), pairs=len(fixed), actual_max_m=int(fixedpaths.max_m.max()), all_A_and_block_prefixes_checked=True, shared_four_endpoint_deltas_checked=True),
                  fixed_XYZ_background=dict(pairs=len(background), identities_checked=True, Q_from_focused_native_scalars_checked=True),
                  direct_AC=dict(events=len(ac), pools=ac.pool_id.nunique(), images=ac.image.nunique(), buildings=ac.building.nunique(),
                                 identities_and_saved_Q_differences_checked=True, comparison_has_B=False),
                  dimension_tables=dict(configurations=45, coverage_rows=360, all_n_m_rows=len(dims),
                                        formal_difficulty_rows=len(read(OUT / 'FORMAL_DIFFICULTY_RESULTS.csv')),
                                        structural_condition_rows=len(read(OUT / 'STRUCTURAL_CONDITION_RESULTS.csv')),
                                        independent_Q_check='all 7356 global condition Q means and denominators match saved source summaries; all global event Q contrasts match endpoint scalars',
                                        difficulty_key_check='three OPPJOINT 12/6 formal difficulty strata independently match means, valid images and positive images',
                                        other_dimensions='source summary values retained with exact paths; not independently recomputed in full',
                                        method_original_cases=len(caseframe), chain_cases=len(chain_cases),
                                        preplotted_case_paths='24 paths normalized to repository root and checked separately'),
                  oppjoint_12_6=dict(events=len(opp), images=opp.image.nunique(), buildings=opp.building.nunique(),
                                    frame_check='05B selected pools and realized 05A event images independently agree for all 56 images', outside_screen=outside_stats,
                                    all_CB=equal_image_stats(opp, 'B8L2_CB'), all_gap=equal_image_stats(opp, 'B8L2_gap')),
                  boundaries=['45 configurations are not 45 independent ideas; equivalent partitions retained with identifiers',
                              'global screen is selected 78-image evidence, not exhaustive search across 225 primary images',
                              'case sign is conditional on method, role direction, n, m, target and availability',
                              'no new native fusion, classification, OPP large-pool strategy or same-room ABC experiment',
                              'fixed XYZ nested n changes both background people and vote threshold',
                              'direct AC has no B and cannot establish cross-versus-within or net C-B',
                              'fair Q-only increment remains a distinct future estimand, not a prerequisite for observed majority effects'])
    (OUT / 'CHECKS.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    source_paths = {rel(p) for p in snapshots + [epath, spath, fpath, lpath, rpath, framepath, dimpath, npath, mpath, fepath, bpath, acpath, fp, mechanism_path]}
    for table in OUT.glob('*.csv'):
        columns = pd.read_csv(table, nrows=0).columns
        pathcols = [c for c in columns if c in ['source_table', 'source_event_table', 'labels_table', 'original_snapshot', 'snapshot']]
        if pathcols:
            for col in pathcols:
                source_paths.update(read(table, usecols=pathcols)[col].dropna().unique())
    assert all((ROOT / p).is_file() for p in source_paths)
    write(pd.DataFrame([dict(source_path=p, exists=True, role='只读交付来源或本地原答；不改源文件') for p in sorted(source_paths)]), 'SOURCE_INDEX.csv')
    print(json.dumps(checks, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
