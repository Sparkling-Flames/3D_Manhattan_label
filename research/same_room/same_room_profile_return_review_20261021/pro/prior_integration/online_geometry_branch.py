"""Small preregistered-by-code no-GT geometry stopping branch on native fusion.

Three existing replay orders per supported panel are chosen by a stable hash,
independently of quality. All their view/prefix geometries are reconstructed by
the frozen native fuse. Archived B8L2/D10 are evaluation-only and never used in
native geometry generation or online selection. This is an internal comparison,
not external validation or a replacement for the full 124,924-node analysis.
"""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import argparse, gzip, hashlib, json, os, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd

def setup(repo):
    sys.path[:0] = ['/tmp/hohonet_deps', str(repo)]

def native_pool(task):
    repo, pool, requests = task
    setup(repo)
    from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse, WORKING_GAP
    from tools.thesis_main.analysis.wall_consensus_v1_process_20261017 import cached_matching
    from tools.thesis_main.analysis.wall_consensus_population_20261014 import summarize_state
    by_worker = {r['worker_id']: r for r in pool['records']}
    cache = {}
    outputs = []
    with cached_matching():
        for req in requests:
            workers = req['ordered_workers'].split('|')
            key = '|'.join(sorted(workers))
            if key not in cache:
                state = fuse([by_worker[w] for w in sorted(workers)], gap=WORKING_GAP)['automatic']
                summary = summarize_state(state)
                cache[key] = dict(**summary, points=state['candidate']['points'], footprint=state['candidate']['footprint'], minimum_support=state['minimum_support'], identity_group_n=len(state['identity_groups']), selected_node_support=[n['support'] for n in state['node_consensus']['nodes']])
            outputs.append(dict(request_id=req['request_id'], team_id=req['team_id'], group_id=req['group_id'], replay=req['replay'], image_id=req['image_id'], image_code=req['image'], reference_id=req['reference_id'], ordered_workers=req['ordered_workers'], member_object_ids=req['member_object_ids'], **cache[key]))
    return (pool['pool_id'], len(cache), outputs)

def ring_distance(pa, pb):
    from tools.thesis_main.analysis.paired_split_research.study import angular, cyclic
    if pa is None or pb is None or len(pa) != len(pb) or (len(pa) < 8):
        return np.nan
    a, b = (np.asarray(pa, float), np.asarray(pb, float))
    costs = np.maximum(angular(a[::2], b[::2]), angular(a[1::2], b[1::2]))
    return float(cyclic(costs)[0])

def main(repo, output, jobs, reuse_geometry=False):
    setup(repo)
    output.mkdir(parents=True, exist_ok=True)
    src = repo / 'research/same_room/same_room_multiview_20261020'
    nodes = _read_csv(src / 'replay_nodes.csv.gz', low_memory=False)
    groups = {g['group_id']: g for g in json.load(open(src / 'REPLAY_GROUPS.json'))}
    with _open_data(src / 'REPLAY_ORDERS.json.gz', 'rt') as f:
        orders = json.load(f)
    selected = []
    for gid in sorted(nodes.group_id.unique()):
        candidates = [o for o in orders if o['group_id'] == gid]
        candidates.sort(key=lambda o: hashlib.sha256(f"online_geometry_fixed_v1|{gid}|{o['replay']}".encode()).hexdigest())
        for o in candidates[:3]:
            selected.append(dict(o, selection_hash=hashlib.sha256(f"online_geometry_fixed_v1|{gid}|{o['replay']}".encode()).hexdigest()))
    sel = {(o['group_id'], o['replay']) for o in selected}
    part = nodes[[(r.group_id, r.replay) in sel for r in nodes[['group_id', 'replay']].itertuples(index=False)]].copy()
    with _open_data(src / 'REPLAY_POOLS.json.gz', 'rt') as f:
        pools = {p['pool_id']: p for p in json.load(f)}
    cols = ['request_id', 'team_id', 'group_id', 'replay', 'k', 'image_id', 'image', 'reference_id', 'ordered_workers', 'member_object_ids']
    tasks = [(repo, pools[pid], p[cols].to_dict('records')) for pid, p in part.groupby('pool_id')]
    geometries = []
    calls = 0
    receipts = []
    if reuse_geometry:
        with _open_data(output / 'online_geometry_prefixes.json.gz', 'rt') as f:
            geometries = json.load(f)
        prior = json.load(open(output / 'ONLINE_GEOMETRY_RECEIPT.json'))
        calls = prior['native_fusion_calls']
        receipts = prior['pool_receipts']
        assert {r['request_id'] for r in geometries} == set(part.request_id)
    else:
        with ProcessPoolExecutor(max_workers=jobs) as executor:
            futures = [executor.submit(native_pool, t) for t in tasks]
            for future in as_completed(futures):
                pid, n, rows = future.result()
                calls += n
                geometries.extend(rows)
                receipts.append(dict(pool_id=pid, unique_native_fusions=n, prefix_rows=len(rows)))
                print(f'native {len(receipts)}/{len(tasks)} pools; calls {calls}', flush=True)
    geometries.sort(key=lambda r: (r['group_id'], r['image_id'], r['replay'], r['k']))
    with _open_data(output / 'online_geometry_prefixes.json.gz', 'wt', encoding='utf-8') as f:
        json.dump(geometries, f, ensure_ascii=False, separators=(',', ':'))
    (output / 'online_geometry_orders.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2) + '\n')
    gt = {r['request_id']: r for r in geometries}
    archived = {r.request_id: r for r in part.itertuples()}
    mismatches = []
    for rid, g in gt.items():
        a = archived[rid]
        if int(a.nodes) != g['nodes'] or bool(a.complete_evaluable) != g['complete_evaluable']:
            mismatches.append(dict(request_id=rid, archive_nodes=a.nodes, new_nodes=g['nodes'], archive_complete=bool(a.complete_evaluable), new_complete=g['complete_evaluable']))
    if mismatches:
        raise RuntimeError(f'Native structural mismatch: {mismatches[:3]}')
    decisions = []
    transitions = []
    for (gid, image, replay), p in part.groupby(['group_id', 'image_id', 'replay']):
        p = p.sort_values('k').set_index('k')
        K = int(p.index.max())
        g = groups[gid]
        states = {k: gt[p.loc[k, 'request_id']] for k in p.index}
        distance = {k: ring_distance(states[k - 1]['points'], states[k]['points']) if k > 1 else np.nan for k in p.index}
        for k in p.index:
            transitions.append(dict(group_id=gid, image_id=image, replay=replay, k=k, request_id=p.loc[k, 'request_id'], complete_geometry=states[k]['complete_evaluable'], nodes=states[k]['nodes'], transition_bound_cyclic_deg=distance[k]))
        chosen = K
        triggered = False
        for k in range(5, K + 1):
            window = range(k - 3, k + 1)
            if all((states[j]['complete_evaluable'] for j in window)) and len({states[j]['nodes'] for j in window}) == 1 and all((np.isfinite(distance[j]) and distance[j] <= 2.0 for j in range(k - 2, k + 1))):
                chosen = k
                triggered = True
                break
        choices = {'online_three_transitions_2deg': chosen, 'full_common_pool': K}
        for budget in [5, 7, 9]:
            start = min(budget, K)
            choices[f'fixed_{budget}_geometry'] = next((k for k in range(start, K + 1) if states[k]['complete_evaluable']), K)
        others = part[(part.group_id == gid) & (part.replay == replay) & (part.image_id != image)]
        source_curves = others.pivot(index='image_id', columns='k', values='B8L2').to_numpy()
        source_mean = source_curves.mean(axis=0)
        ks = np.arange(1, K + 1)
        valid = (ks >= 3) & np.isfinite(source_mean)
        for name, penalty, tolerance in [('source_within2_min3_geometry', 0, 2), ('source_q_minus_k_min3_geometry', 1, 0)]:
            value = np.where(valid, source_mean - penalty * ks, -np.inf)
            k0 = int(ks[np.flatnonzero(valid & (value >= value.max() - tolerance - 1e-10))[0]])
            choices[name] = next((k for k in range(k0, K + 1) if states[k]['complete_evaluable']), K)
        full = p.loc[K]
        for policy, k in choices.items():
            row = p.loc[k]
            time_ok = bool(full.member_old_n == 0 and full.source_new_known_n == K)
            decisions.append(dict(group_id=gid, parent_group=g.get('parent_group', gid), panel=g['replay_panel'], building=g['building'], room_id=row.room_id, image_id=image, image_code=row.image, replay=replay, policy=policy, selected_k=k, terminal_k=K, online_triggered=triggered if policy.startswith('online_') else None, complete_geometry=states[k]['complete_evaluable'], B8L2=row.B8L2, D10=row.D10, B8L2_full=full.B8L2, loss_gt5_full=full.B8L2 - row.B8L2 > 5 if pd.notna(row.B8L2) else None, activity_all_new_complete=time_ok, activity_seconds=row.source_new_total_seconds if time_ok else np.nan, full_activity_seconds=full.source_new_total_seconds if time_ok else np.nan, request_id=row.request_id, team_id=row.team_id, reference_id=row.reference_id, member_object_ids=row.member_object_ids, ordered_workers=row.ordered_workers))
    d = pd.DataFrame(decisions)
    _write_csv(d, output / 'online_geometry_decisions.csv', index=False)
    _write_csv(pd.DataFrame(transitions), output / 'online_geometry_transitions.csv', index=False)
    target = []
    for keys, z in d.groupby(['group_id', 'parent_group', 'panel', 'building', 'room_id', 'image_id', 'image_code', 'policy']):
        target.append(dict(zip(['group_id', 'parent_group', 'panel', 'building', 'room_id', 'image_id', 'image_code', 'policy'], keys), activity_all_new_complete=bool(z.activity_all_new_complete.all()), attempts=len(z), complete_fraction=z.complete_geometry.mean(), quality_available_fraction=z.B8L2.notna().mean(), mean_k=z.selected_k.mean(), B8L2=z.B8L2.mean(), D10=z.D10.mean(), target_q10=z.B8L2.quantile(0.1), loss_gt5_full=z.loss_gt5_full.mean(), mean_activity_seconds=z.activity_seconds.mean(), mean_activity_ratio_to_full=(z.activity_seconds / z.full_activity_seconds).mean()))
    t = pd.DataFrame(target)
    _write_csv(t, output / 'online_geometry_target.csv', index=False)
    numeric = ['complete_fraction', 'quality_available_fraction', 'mean_k', 'B8L2', 'D10', 'target_q10', 'loss_gt5_full', 'mean_activity_seconds', 'mean_activity_ratio_to_full']
    summary = []
    for (panel, policy), z in t.groupby(['panel', 'policy']):
        for ts, zz in [('all_groups', z), ('all_new_complete_time', z[z.activity_all_new_complete])]:
            if not len(zz):
                continue
            vals = zz.groupby(['building', 'group_id'])[numeric].mean().groupby(level='building').mean().mean().to_dict()
            summary.append(dict(panel=panel, policy=policy, time_support=ts, groups=zz.group_id.nunique(), buildings=zz.building.nunique(), images=zz.image_id.nunique(), attempts=int(zz.attempts.sum()), **vals))
    _write_csv(pd.DataFrame(summary), output / 'online_geometry_summary.csv', index=False)
    receipt = dict(main_commit='561584c8f64d5349d497ec1c6e91f1aeb4bbd7c9', identity='new internal native-geometry replay branch', native_fusion_calls=calls, native_fusion_calls_this_invocation=0 if reuse_geometry else calls, score_calls=0, prefix_rows=len(part), panels=part.group_id.nunique(), actual_images=part.image_id.nunique(), selected_replay_paths=len(selected), path_selection='smallest 3 SHA256(online_geometry_fixed_v1|group_id|replay) per supported panel', geometry_and_nodecount_mismatches=mismatches, online_rule='k>=5; last four outputs geometrically complete and equal selected-node count; all three consecutive bound cyclic paired-top/bottom mean angular distances <=2 degrees; stop first, otherwise full available common pool', parameters_tuned_on_target=False, target_GT_or_Q_used_for_decision=False, metric_source='archived actual B8L2/D10 joined by exact request_id; unchanged scoring', source_comparator='maximum history N-1 other views, exact same path, archived source B8L2; distinct from online no-GT rule', scope='secondary fixed-hash finite replay sample, not external validation and not all 124924 nodes', pool_receipts=receipts)
    (output / 'ONLINE_GEOMETRY_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(pd.DataFrame(summary).to_string(index=False))
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    p.add_argument('--jobs', type=int, default=2)
    p.add_argument('--reuse-geometry', action='store_true')
    a = p.parse_args()
    main(a.repo, a.output, a.jobs, a.reuse_geometry)
