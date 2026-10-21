"""Reconstruct source-informed and observable-geometry stopping from frozen replays.

This script reads existing native fusion outputs; it does not run, approximate,
or rescore fusion. B8L2 selects historical-source rules, D10 evaluates the same
selected teams. No target reference quantity is read by a decision function.
"""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import argparse, csv, gzip, hashlib, itertools, json, warnings
from collections import defaultdict
import numpy as np
import pandas as pd
POLICIES = ['full_common_pool', 'fixed_3_raw', 'fixed_5_raw', 'fixed_7_raw', 'fixed_9_raw', 'fixed_3_geometry', 'fixed_5_geometry', 'fixed_7_geometry', 'fixed_9_geometry', 'source_within2_min1_raw', 'source_within2_min3_raw', 'source_within2_min3_geometry', 'source_within1_min3_geometry', 'source_within0_min3_geometry', 'source_within5_min3_geometry', 'source_q_minus_k_min3_geometry', 'source_poolmean_within2_min3_geometry', 'source_poolmean_q_minus_k_min3_geometry', 'online_same_nodecount_3_geometry']
DECISION_POLICIES = {'full_common_pool', 'fixed_7_raw', 'fixed_7_geometry', 'source_within2_min1_raw', 'source_within2_min3_raw', 'source_within2_min3_geometry', 'source_q_minus_k_min3_geometry', 'online_same_nodecount_3_geometry'}

def near_peak(source, minimum, tolerance=2, penalty=0):
    ks = np.arange(source.shape[1])
    valid = np.isfinite(source) & (ks >= minimum) & (ks != 2)
    value = np.where(valid, source - penalty * ks[None, :], -np.inf)
    best = value.max(axis=1)
    hits = valid & (value >= best[:, None] - tolerance - 1e-10)
    return np.where(hits.any(axis=1), hits.argmax(axis=1), -1)

def geometry_next(geometry):
    """Map each observed prefix to first complete geometry at/after it, or -1."""
    r, width = geometry.shape
    ans = np.full((r, width), -1, dtype=int)
    current = np.full(r, -1, dtype=int)
    for k in reversed(range(width)):
        current = np.where(geometry[:, k], k, current)
        ans[:, k] = current
    return ans

def topup(choice, next_map):
    return np.where(choice > 0, next_map[np.arange(len(choice)), np.maximum(choice, 0)], -1)

def online_node_count(geometry, node_count):
    """First k>=5 with 3 consecutive complete prefix outputs having same count.

    Uses only target outputs already obtained. A count is not a correspondence or
    location check. If the rule does not trigger, collect the available pool.
    """
    r, width = geometry.shape
    choice = np.full(r, width - 1, dtype=int)
    triggered = np.zeros(r, dtype=bool)
    for k in range(5, width):
        hit = geometry[:, k - 2:k + 1].all(axis=1)
        hit &= (node_count[:, k] == node_count[:, k - 1]) & (node_count[:, k] == node_count[:, k - 2])
        fresh = hit & ~triggered
        choice[fresh] = k
        triggered |= hit
    return (choice, triggered)

def number(v):
    v = np.asarray(v, dtype=float)
    return float(np.nanmean(v)) if np.isfinite(v).any() else np.nan

def quant(v, q=0.1):
    v = np.asarray(v, dtype=float)
    return float(np.nanquantile(v, q)) if np.isfinite(v).any() else np.nan

def measure(a, mask=None):
    if mask is None:
        mask = np.ones(len(a['k']), bool)
    z = {key: np.asarray(val)[mask] for key, val in a.items()}
    q, qf, q7 = (z['q'], z['qfull'], z['q7'])
    valid = np.isfinite(q)
    paired = valid & np.isfinite(qf)
    paired7 = valid & np.isfinite(q7)
    loss = qf[paired] - q[paired]
    dpaired = np.isfinite(z['d10']) & np.isfinite(z['d10full'])
    dloss = z['d10full'][dpaired] - z['d10'][dpaired]
    tvalid = np.isfinite(z['seconds']) & np.isfinite(z['secondsfull']) & np.isfinite(z['seconds7'])
    out = {'attempts': len(q), 'valid_n': int(valid.sum()), 'paired_terminal_n': int(paired.sum()), 'chosen_rate': number(z['k'] > 0), 'geometry_complete_rate': number(z['geometry']), 'quality_available_rate': number(valid), 'mean_k': number(np.where(z['k'] > 0, z['k'], np.nan)), 'mean_requested_k': number(np.where(z['requested_k'] > 0, z['requested_k'], np.nan)), 'mean_topup_k': number(np.where(z['k'] > 0, z['k'] - z['requested_k'], np.nan)), 'topup_fraction': number(z['k'] > z['requested_k']), 'q_mean': number(q), 'q10': quant(q), 'q_below50_rate_valid': number(q[valid] < 50), 'q_below80_rate_valid': number(q[valid] < 80), 'mean_loss_to_full': number(loss), 'loss_gt5_to_full_rate_paired': number(loss > 5), 'loss_gt5_or_missing_rate_all': number(~valid | (qf - q > 5)), 'mean_gain_to_fixed7_geometry': number(q[paired7] - q7[paired7]), 'loss_gt5_to_fixed7_geometry_rate_paired': number(q7[paired7] - q[paired7] > 5), 'd10_mean': number(z['d10']), 'd10_q10': quant(z['d10']), 'd10_loss_gt5_to_full_rate_paired': number(dloss > 5), 'activity_time_valid_n': int(tvalid.sum()), 'mean_activity_seconds': number(z['seconds']), 'mean_activity_ratio_to_full': number(z['seconds'][tvalid] / z['secondsfull'][tvalid]), 'mean_activity_ratio_to_fixed7_geometry': number(z['seconds'][tvalid] / z['seconds7'][tvalid]), 'ratio_mean_activity_to_full': number(z['seconds'][tvalid]) / number(z['secondsfull'][tvalid]) if tvalid.any() else np.nan, 'ratio_mean_activity_to_fixed7_geometry': number(z['seconds'][tvalid]) / number(z['seconds7'][tvalid]) if tvalid.any() else np.nan, 'mean_source_full_activity_seconds': number(z['source_seconds']), 'mean_source_annotation_count': number(z['source_annotation_count']), 'same_requested_k_random_geometry_q': number(z['same_k_random_q']), 'gain_to_same_requested_k_random_geometry': number(q - z['same_k_random_q']), 'same_final_k_random_available_q': number(z['same_final_k_random_q']), 'same_final_k_random_quality_available_rate': number(z['same_final_k_random_available']), 'gain_to_same_final_k_random_available': number(q - z['same_final_k_random_q']), 'online_triggered_rate': number(z['online_triggered'])}
    return out

def load_group(part, group):
    images = group['images']
    replays = sorted(part.replay.unique())
    K = int(part.k.max())
    imap = {im: i for i, im in enumerate(images)}
    rmap = {r: i for i, r in enumerate(replays)}
    shape = (len(images), len(replays), K + 1)
    idx = (part.image_id.map(imap).to_numpy(), part.replay.map(rmap).to_numpy(), part.k.to_numpy())
    arrays = {}
    numeric = ['B8L2', 'D10', 'nodes', 'member_old_n', 'source_new_total_seconds', 'source_new_known_n']
    for key in numeric:
        value = np.full(shape, np.nan)
        value[idx] = pd.to_numeric(part[key], errors='coerce')
        arrays[key] = value
    geometry = part.geometry_status.eq('ok') & part.nodes.ge(4) & part.connection_available
    g = np.zeros(shape, bool)
    g[idx] = geometry.to_numpy()
    arrays['geometry'] = g
    arrays['quality'] = np.where(g, arrays['B8L2'], np.nan)
    arrays['d10'] = np.where(g, arrays['D10'], np.nan)
    time_ok = bool((arrays['member_old_n'][:, :, K] == 0).all() and (arrays['source_new_known_n'][:, :, K] == K).all() and np.isfinite(arrays['source_new_total_seconds'][:, :, K]).all())
    arrays['seconds'] = arrays['source_new_total_seconds'] if time_ok else np.full(shape, np.nan)
    return (images, replays, K, arrays, time_ok)

def main(repo, output, pr_dir=None):
    output.mkdir(parents=True, exist_ok=True)
    source = repo / 'research/same_room/same_room_multiview_20261020'
    nodes = _read_csv(source / 'replay_nodes.csv.gz', low_memory=False)
    groups = {g['group_id']: g for g in json.load(open(source / 'REPLAY_GROUPS.json'))}
    targets, projects, support, recovery, cases = ([], [], [], [], [])
    decision_fields = ['group_id', 'parent_group', 'panel', 'building', 'N', 'm', 'split_id', 'history', 'target_image', 'image_code', 'replay', 'policy', 'requested_k', 'selected_k', 'geometry_complete', 'B8L2', 'D10', 'B8L2_full', 'B8L2_fixed7_geometry', 'activity_seconds', 'source_full_activity_seconds', 'request_id', 'team_id', 'reference_id', 'member_object_ids', 'ordered_workers']
    decision_path = output / 'decisions_whole_maxhistory.csv.gz'
    fout = _open_data(decision_path, 'wt', encoding='utf-8', newline='')
    writer = csv.DictWriter(fout, fieldnames=decision_fields)
    writer.writeheader()
    selected_count = 0
    geometry_check = nodes.k.ge(3)
    defined_geometry = nodes.geometry_status.eq('ok') & nodes.nodes.ge(4) & nodes.connection_available
    geometry_agreement = int((defined_geometry[geometry_check] == nodes.loc[geometry_check, 'complete_evaluable']).sum())
    for gid, part in nodes.groupby('group_id', sort=True):
        group = groups[gid]
        images, replays, K, a, time_ok = load_group(part, group)
        N, R = (len(images), len(replays))
        rids = np.arange(R)
        q, d10, geometry, seconds = (a['quality'], a['d10'], a['geometry'], a['seconds'])
        next_maps = [geometry_next(geometry[t]) for t in range(N)]
        online = [online_node_count(geometry[t], a['nodes'][t]) for t in range(N)]
        fixed7 = [topup(np.full(R, min(7, K)), next_maps[t]) for t in range(N)]
        common = np.isfinite(q[:, :, [k for k in range(1, K + 1) if k != 2]]).all(axis=(0, 2))
        row_index = part.set_index(['image_id', 'replay', 'k'])
        support.append(dict(group_id=gid, parent_group=group.get('parent_group', gid), panel=group['replay_panel'], building=group['building'], images=N, paths=R, common_workers=K, dot_common_complete_paths=int(common.sum()), activity_all_new_complete=time_ok, actual_nodes=len(part), room_id=part.room_id.iloc[0], original_group_sources='|'.join(group['sources'])))
        for m in sorted({1, *range(N // 2 + 1, N)}):
            acc = defaultdict(lambda: defaultdict(list))
            for split_i, hist in enumerate(itertools.combinations(range(N), m)):
                remaining = [t for t in range(N) if t not in hist]
                history_key = '|'.join((images[h] for h in hist))
                source_curve = q[list(hist)].mean(axis=0)
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', RuntimeWarning)
                    pool_curve = np.nanmean(source_curve, axis=0)[None, :].repeat(R, axis=0)
                choices = {'source_within2_min1_raw': near_peak(source_curve, 1, 2), 'source_within2_min3_raw': near_peak(source_curve, 3, 2), 'source_within2_min3_geometry': near_peak(source_curve, 3, 2), 'source_within1_min3_geometry': near_peak(source_curve, 3, 1), 'source_within0_min3_geometry': near_peak(source_curve, 3, 0), 'source_within5_min3_geometry': near_peak(source_curve, 3, 5), 'source_q_minus_k_min3_geometry': near_peak(source_curve, 3, 0, 1), 'source_poolmean_within2_min3_geometry': near_peak(pool_curve, 3, 2), 'source_poolmean_q_minus_k_min3_geometry': near_peak(pool_curve, 3, 0, 1), 'full_common_pool': np.full(R, K)}
                for k in (3, 5, 7, 9):
                    choices[f'fixed_{k}_raw'] = np.full(R, min(k, K))
                    choices[f'fixed_{k}_geometry'] = np.full(R, min(k, K))
                source_seconds = seconds[list(hist), :, K].sum(axis=0)
                source7_seconds = sum((seconds[h, rids, fixed7[h]] for h in hist))
                target7_seconds = sum((seconds[t, rids, fixed7[t]] for t in remaining))
                all7_seconds = source7_seconds + target7_seconds
                allfull_seconds = seconds[:, :, K].sum(axis=0)
                project_targets = defaultdict(list)
                for t in remaining:
                    image = images[t]
                    q7 = q[t, rids, fixed7[t]]
                    s7 = seconds[t, rids, fixed7[t]]
                    random_mean = np.full(K + 1, np.nan)
                    random_final_mean = np.full(K + 1, np.nan)
                    random_final_available = np.full(K + 1, np.nan)
                    for kk in range(1, K + 1):
                        random_final_mean[kk] = number(q[t, :, kk])
                        random_final_available[kk] = np.isfinite(q[t, :, kk]).mean()
                    for kk in range(3, K + 1):
                        kk_next = next_maps[t][:, kk]
                        valid_next = kk_next > 0
                        random_mean[kk] = number(q[t, rids[valid_next], kk_next[valid_next]])
                    for policy in POLICIES:
                        if policy == 'online_same_nodecount_3_geometry':
                            requested = online[t][0]
                        else:
                            requested = choices[policy]
                        chosen = topup(requested, next_maps[t]) if policy.endswith('_geometry') else requested
                        safe = np.maximum(chosen, 0)
                        valid_choice = chosen > 0
                        tq = np.where(valid_choice, q[t, rids, safe], np.nan)
                        td = np.where(valid_choice, d10[t, rids, safe], np.nan)
                        ts = np.where(valid_choice, seconds[t, rids, safe], np.nan)
                        tg = valid_choice & geometry[t, rids, safe]
                        z = dict(k=chosen, requested_k=requested, q=tq, d10=td, qfull=q[t, :, K], d10full=d10[t, :, K], q7=q7, geometry=tg, seconds=ts, secondsfull=seconds[t, :, K], seconds7=s7, source_seconds=source_seconds, source_annotation_count=np.full(R, m * K), common=common, same_k_random_q=np.where(requested >= 3, random_mean[np.maximum(requested, 0)], np.nan), same_final_k_random_q=np.where(valid_choice, random_final_mean[safe], np.nan), same_final_k_random_available=np.where(valid_choice, random_final_available[safe], np.nan), online_triggered=online[t][1] if policy.startswith('online_') else np.full(R, np.nan))
                        for field, values in z.items():
                            acc[t, policy][field].append(values)
                        project_targets[policy].append((chosen, ts, tq))
                        if group['replay_panel'] == 'whole_group' and m == N - 1 and (policy in DECISION_POLICIES):
                            for ri, replay in enumerate(replays):
                                k = int(chosen[ri])
                                row = row_index.loc[image, replay, k] if k > 0 else None
                                item = dict(group_id=gid, parent_group=group.get('parent_group', gid), panel=group['replay_panel'], building=group['building'], N=N, m=m, split_id=f'{gid}_m{m}_h{split_i}', history=history_key, target_image=image, image_code=row['image'] if row is not None else '', replay=replay, policy=policy, requested_k=int(requested[ri]), selected_k=k, geometry_complete=bool(tg[ri]), B8L2=tq[ri], D10=td[ri], B8L2_full=q[t, ri, K], B8L2_fixed7_geometry=q7[ri], activity_seconds=ts[ri], source_full_activity_seconds=source_seconds[ri])
                                for field in ['request_id', 'team_id', 'reference_id', 'member_object_ids', 'ordered_workers']:
                                    item[field] = row[field] if row is not None else ''
                                writer.writerow(item)
                                selected_count += 1
                                if policy in {'source_within2_min3_geometry', 'source_q_minus_k_min3_geometry', 'online_same_nodecount_3_geometry'}:
                                    cases.append(item)
                for policy, plist in project_targets.items():
                    target_k = np.stack([p[0] for p in plist]).sum(axis=0)
                    target_seconds = np.stack([p[1] for p in plist]).sum(axis=0)
                    extra_source = source_seconds - source7_seconds
                    per_target_saving = (target7_seconds - target_seconds) / len(remaining)
                    break_even = np.divide(extra_source, per_target_saving, out=np.full(R, np.nan), where=per_target_saving > 0)
                    requires_source = policy.startswith('source_')
                    observed_source = source_seconds if requires_source else source7_seconds
                    projects.append(dict(group_id=gid, parent_group=group.get('parent_group', gid), panel=group['replay_panel'], building=group['building'], m=m, N=N, split_id=f'{gid}_m{m}_h{split_i}', history=history_key, targets='|'.join((images[t] for t in remaining)), policy=policy, target_views=len(remaining), activity_all_new_complete=time_ok, source_curve_required=requires_source, source_annotation_count=m * K if requires_source else np.nan, target_annotation_count=number(target_k), mean_source_full_activity_seconds=number(source_seconds), mean_source_fixed7_geometry_activity_seconds=number(source7_seconds), mean_target_activity_seconds=number(target_seconds), mean_target_fixed7_geometry_activity_seconds=number(target7_seconds), project_ratio_to_fixed7_geometry=number((source_seconds + target_seconds) / all7_seconds) if requires_source else np.nan, project_ratio_to_full_common_pool=number((source_seconds + target_seconds) / allfull_seconds) if requires_source else np.nan, project_people_ratio_to_capped_fixed7=number((m * K + target_k) / (N * min(7, K))) if requires_source else np.nan, project_people_ratio_to_full_pool=number((m * K + target_k) / (N * K)) if requires_source else np.nan, target_saving_positive_fraction=number(per_target_saving > 0) if time_ok else np.nan, median_break_even_future_target_views=quant(break_even, 0.5) if requires_source else np.nan, mean_break_even_future_target_views=number(break_even) if requires_source else np.nan))
            for (t, policy), vals in acc.items():
                z = {key: np.concatenate(value) for key, value in vals.items()}
                for support_name, mask in [('all_attempts', None), ('dot_common_complete', z['common'].astype(bool))]:
                    targets.append(dict(group_id=gid, parent_group=group.get('parent_group', gid), panel=group['replay_panel'], building=group['building'], room_id=part.room_id.iloc[0], m=m, N=N, target_image=images[t], policy=policy, support=support_name, activity_all_new_complete=time_ok, **measure(z, mask)))
            print(f'completed {gid} m={m} / N={N} paths={R}', flush=True)
    fout.close()
    target = pd.DataFrame(targets)
    _write_csv(target, output / 'stopping_target_actual_m.csv.gz', index=False)
    project = pd.DataFrame(projects)
    _write_csv(project, output / 'source_acquisition_project_cost.csv.gz', index=False)
    _write_csv(pd.DataFrame(support), output / 'stopping_support.csv', index=False)
    descriptive = [c for c in target.select_dtypes(include=np.number) if c not in ['m', 'N', 'attempts', 'valid_n', 'paired_terminal_n', 'activity_time_valid_n']]
    group_keys = ['group_id', 'parent_group', 'panel', 'building', 'room_id', 'm', 'N', 'policy', 'support', 'activity_all_new_complete']
    grouped = target.groupby(group_keys, observed=True, dropna=False)[descriptive].mean().reset_index()
    counts = target.groupby(group_keys, observed=True, dropna=False).agg(attempts=('attempts', 'sum'), valid_n=('valid_n', 'sum'), targets=('target_image', 'nunique')).reset_index()
    grouped = grouped.merge(counts, on=group_keys)
    _write_csv(grouped, output / 'stopping_group_actual_m.csv', index=False)
    summaries = []
    for budget, mask in [('single_source', target.m.eq(1)), ('minimum_majority', target.m.eq(target.N // 2 + 1)), ('maximum_history', target.m.eq(target.N - 1))]:
        for (panel, sup, policy), ss in target[mask].groupby(['panel', 'support', 'policy'], observed=True):
            for time_support, zz in [('all_groups', ss), ('all_new_complete_time', ss[ss.activity_all_new_complete])]:
                if not len(zz):
                    continue
                bygroup = zz.groupby(['building', 'group_id'], observed=True)[descriptive].mean()
                values = bygroup.groupby(level='building').mean().mean().to_dict()
                summaries.append(dict(history_budget=budget, panel=panel, support=sup, policy=policy, time_support=time_support, weighting='building_equal_after_group_target', groups=zz.group_id.nunique(), buildings=zz.building.nunique(), images=zz.target_image.nunique(), attempts=int(zz.attempts.sum()), valid_n=int(zz.valid_n.sum()), **values))
    summary = pd.DataFrame(summaries)
    _write_csv(summary, output / 'stopping_summary.csv', index=False)
    project_group = project.groupby(['group_id', 'parent_group', 'panel', 'building', 'm', 'N', 'policy', 'activity_all_new_complete', 'source_curve_required'], observed=True).mean(numeric_only=True).reset_index()
    _write_csv(project_group, output / 'source_acquisition_group_actual_m.csv', index=False)
    ps = []
    for budget, mask in [('single_source', project_group.m.eq(1)), ('minimum_majority', project_group.m.eq(project_group.N // 2 + 1)), ('maximum_history', project_group.m.eq(project_group.N - 1))]:
        pp = project_group[mask & project_group.source_curve_required & project_group.activity_all_new_complete]
        for (panel, policy), z in pp.groupby(['panel', 'policy'], observed=True):
            numeric = [c for c in z.select_dtypes(include=np.number) if c not in ['m', 'N']]
            vals = z.groupby('building')[numeric].mean().mean().to_dict()
            ps.append(dict(history_budget=budget, panel=panel, policy=policy, groups=z.group_id.nunique(), buildings=z.building.nunique(), **vals))
    _write_csv(pd.DataFrame(ps), output / 'source_acquisition_summary.csv', index=False)
    c = pd.DataFrame(cases)
    c['gain_to_full'] = c.B8L2 - c.B8L2_full
    c['gain_to_fixed7_geometry'] = c.B8L2 - c.B8L2_fixed7_geometry
    selected = []
    for key, z in c.groupby(['group_id', 'target_image', 'policy']):
        selected.extend([z.nsmallest(1, 'gain_to_full'), z.nlargest(1, 'gain_to_full')])
    _write_csv(pd.concat(selected).drop_duplicates(['group_id', 'target_image', 'policy', 'replay']), output / 'representative_stopping_events.csv', index=False)
    receipt = {'main_commit': '561584c8f64d5349d497ec1c6e91f1aeb4bbd7c9', 'pr19_fixed_head': 'e83286b7814afc614253aa392050e9a3851ae058', 'identity': 'current reconstruction/new analysis, not recovered Pro original', 'native_fusion_calls_this_script': 0, 'archived_actual_prefix_rows': len(nodes), 'saved_maxhistory_decision_rows': selected_count, 'input_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [source / 'replay_nodes.csv.gz', source / 'REPLAY_GROUPS.json', source / 'REPLAY_ORDERS.json.gz']}, 'geometry_definition': "candidate geometry_status=='ok', at least four consensus nodes, connection available; no target Q/reference quantity enters selection", 'geometry_agreement_k_ge3': {'eligible_rows': int(geometry_check.sum()), 'matches_archived_complete_evaluable': geometry_agreement}, 'source_curve_minimums_compared': [1, 3], 'source_incomplete_prefix': 'ineligible at that k; all source views must have valid B8L2; no interpolation', 'main_choices': 'B8L2 source; same choices evaluated by D10', 'time_contract': 'only pools entirely new-origin with known same-semantics source_new_total_seconds at every full-pool source/target; other time outputs missing', 'time_meaning': 'reported annotation activity, not queue/completion delivery time or money', 'history_budgets': 'm=1 plus every m>N/2; no pooling actual m in main result', 'weights': 'repeated splits/paths within target and m, then target equal, group equal within building, building equal', 'full_pool': 'all workers common to the declared supported replay panel, not every available annotator on each image', 'online_rule': 'first k>=5 with same selected node count at three consecutive complete target prefix outputs; fallback common-pool endpoint; no reference or source history', 'source_cost': 'full common pool on each historical image; acquired annotations reused for all permutations; reference construction and scoring labor not recorded and excluded, not assumed zero', 'dot_comparison': 'same full-pool all-attempt and common-complete supports; k>=1 versus k>=3 separated', 'decisions_export': 'whole groups, maximum actual history, 8 named policies; other cases exactly reproducible from code+frozen node table'}
    if pr_dir is not None:
        dot = _read_csv(pr_dir / 'stopping/summary.csv')
        checks = []
        for budget in ['minimum_majority', 'maximum_history']:
            for ours, dotsup in [('all_attempts', 'all_attempts'), ('dot_common_complete', 'common_complete')]:
                here = summary[(summary.history_budget == budget) & (summary.panel == 'whole_group') & (summary.support == ours) & (summary.policy == 'source_within2_min1_raw') & (summary.time_support == 'all_groups')].iloc[0]
                there = dot[(dot.history_budget == budget) & (dot.panel == 'whole_group') & (dot.support == dotsup) & (dot.policy == 'source_within_2') & (dot.horizon == 'full_pool') & (dot.weighting == 'building_equal')].iloc[0]
                checks.append(dict(budget=budget, support=ours, our_k=here.mean_k, dot_k=there.mean_k, our_q=here.q_mean, dot_q=there.target_q_mean, our_available=here.quality_available_rate, dot_available=there.target_complete_fraction, k_difference=here.mean_k - there.mean_k, q_difference=here.q_mean - there.target_q_mean))
        _write_csv(pd.DataFrame(checks), output / 'dot_rule_bridge.csv', index=False)
        receipt['dot_selected_rule_matched_to_numerical_tolerance'] = bool(max((abs(x['q_difference']) for x in checks)) < 1e-09)
    (output / 'REBUILD_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(summary[(summary.panel == 'whole_group') & (summary.support == 'all_attempts') & (summary.history_budget == 'maximum_history') & (summary.time_support == 'all_groups')][['policy', 'mean_k', 'q_mean', 'q10', 'quality_available_rate', 'loss_gt5_to_full_rate_paired']].to_string(index=False))
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    p.add_argument('--pr-dir', type=Path)
    a = p.parse_args()
    main(a.repo, a.output, a.pr_dir)
