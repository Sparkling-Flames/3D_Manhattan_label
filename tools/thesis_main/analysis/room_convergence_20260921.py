"""同房穷举留图的收敛人数转移；冻结留建筑名单的真实 AABC 组合。

python -X utf8 -B -m tools.thesis_main.analysis.room_convergence_20260921 --jobs 4
只写探索输出，不修改资格、原始点、冻结时间或正式方法合同。
"""
import argparse
import collections
import hashlib
import itertools
import json
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from .analyze_new_manual_20260921 import ROOT, OUT, read
from .room_scene_personnel_20260921 import load_views
from .clustering_numeric_research.common import clean, partition
from .worker_four_block_exploration_20260910 import compare_bits

DEST = OUT / 'convergence_and_composition'
PROFILES = [(None, None)] + list(itertools.product([2, 3, 4], [.1, .2]))
TAILS = [2, 3, 5]
ROSTER = ROOT / 'analysis_results/clustering_numeric_received_20260920/results/personnel/refitted_lobo_rosters.csv'


def view_input(v):
    return dict(ids=v['ids'], workers=v['workers'], image_id=v['image_id'], building=v['building'],
                condition=v['condition'], image=v['image'].tolist())


def save(name, value):
    p = DEST / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, pd.DataFrame):
        value.to_csv(p, index=False, encoding='utf-8-sig')
    else:
        p.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def split_sizes(n):
    """穷举历史/预测人数比在1:2至2:1之内的图片分法。"""
    return [s for s in range(1, n) if 1 / 3 <= s / n <= 2 / 3]


def onset(ks, probabilities):
    return next((int(k) for k, p in zip(ks, probabilities) if p >= .8 - 1e-12), None)


def stage_states(parts, n, tail, cap, single, anchors=None):
    # The old repeated-support promotion test is deliberately reused unchanged.
    if anchors is None:
        anchors = {k: max(compare_bits(parts[k], parts[j]) for j in range(k + 1, n + 1))
                   for k in range(2, n)}
    bad = {}
    for k, groups in parts.items():
        bad[k] = int(cap is not None and
                     (len(groups) > cap or sum(g.bit_count() == 1 for g in groups) / k > single + 1e-12)) * 2
    states = {}
    for k in range(2, n - tail + 1):
        # Tail comparisons always reach the observed endpoint, including cap failures.
        states[k] = max(max(anchors[j] for j in range(k, n - tail + 1)),
                        max(bad[j] for j in range(k, n + 1)))
    return states


def image_curves(job):
    v, orders = job
    n = v.get('horizon', len(v['ids'])); out = []
    assert 0 <= n <= len(v['ids'])
    worker_index = {w: j for j, w in enumerate(v['workers'])}
    arrivals = [[worker_index[w] for w in order if w in worker_index][:n] for order in orders]
    for kind in ['complete', 'representative']:
        cache = {}
        counts = {(tail, pi): np.zeros((max(0, n-tail-1), 3), int)
                  for tail in TAILS for pi in range(len(PROFILES))}
        for order in arrivals:
            parts = {}
            mask = 0
            for k, i in enumerate(order, 1):
                mask |= 1 << i
                if k < 2: continue
                if mask not in cache:
                    ix = [j for j in range(len(v['ids'])) if mask & (1 << j)]
                    labels, _ = partition(v['image'][np.ix_(ix, ix)], [v['ids'][j] for j in ix], 25.6, kind)
                    groups = collections.defaultdict(int)
                    for j, lab in zip(ix, labels): groups[int(lab)] |= 1 << j
                    cache[mask] = tuple(groups.values())
                parts[k] = cache[mask]
            anchors = {k: max(compare_bits(parts[k], parts[j]) for j in range(k+1, n+1))
                       for k in range(2, n)}
            for tail in TAILS:
                for pi, (cap, single) in enumerate(PROFILES):
                    for k, state in stage_states(parts, n, tail, cap, single, anchors).items():
                        counts[tail, pi][k-2, state] += 1
        for (tail, pi), ct in counts.items():
            ks = list(range(2, n-tail+1)); cap, single = PROFILES[pi]
            lo = ct[:, 0] / len(orders); hi = (ct[:, 0]+ct[:, 1]) / len(orders)
            assert np.all(np.diff(lo) >= -1e-12) and np.all(np.diff(hi) >= -1e-12)
            lower, upper = onset(ks, hi), onset(ks, lo)
            out.append(dict(method=kind, tail=tail, profile=pi, max_clusters=cap, max_singleton_share=single,
                            N=n, ks=ks, stable=ct[:, 0], unknown=ct[:, 1], changing=ct[:, 2], L=lo, U=hi,
                            possible_onset=lower, conservative_onset=upper,
                            status='identified' if lower is not None and lower == upper else
                            'bounded_unknown' if upper is not None else 'possible_only' if lower is not None else
                            'insufficient_tail' if not ks else 'not_reached'))
    return v['job_id'], clean(out)


def group_curve(images, curves, setting):
    cc = [curves[i, *setting] for i in images]
    length = min(len(c['ks']) for c in cc)
    ks = list(range(2, length+2))
    lo = np.mean([c['L'][:length] for c in cc], axis=0)
    hi = np.mean([c['U'][:length] for c in cc], axis=0)
    return onset(ks, lo), onset(ks, hi), length


def median_bounds(cc):
    """各图按自身观察终点给起点区间；不删除尚未达标者。"""
    lower = [c['possible_onset'] if c['possible_onset'] is not None else
             (c['ks'][-1]+1 if c['ks'] else 2) for c in cc]
    upper = [c['conservative_onset'] if c['conservative_onset'] is not None else float('inf') for c in cc]
    return float(np.median(lower)), float(np.median(upper))


def room_transfer(views, results, candidates):
    records = []; inventory = []
    for pool in ['historical', 'strict', 'conditional']:
        pv = {i: v for (p, i), v in views.items() if p == pool and len(v['ids'])}
        curves = {(i, c['method'], c['tail'], c['profile']): c
                  for i, v in pv.items() for c in results[v['job_id']]}
        seen = {}
        for cand in candidates:
            images = sorted(i for i in cand['image_ids'] if i in pv)
            key = tuple(images)
            inventory.append(dict(pool=pool, candidate=cand['candidate_id'], building=cand['building'],
                                  images=images, N=[len(pv[i]['ids']) for i in images],
                                  absent=[i for i in cand['image_ids'] if i not in pv],
                                  alias_of=seen.get(key), comparable_for_prediction=cand['comparable_for_prediction']))
            if len(images) < 2 or key in seen: continue
            seen[key] = cand['candidate_id']
            for kind, tail, pi in itertools.product(['complete', 'representative'], TAILS, range(len(PROFILES))):
                setting = (kind, tail, pi)
                outside = [i for i in pv if pv[i]['building'] != cand['building']]
                for s in split_sizes(len(images)):
                    for source in itertools.combinations(images, s):
                        target = sorted(set(images)-set(source))
                        predicted, possible, length = group_curve(source, curves, setting)
                        target_onset, target_possible, _ = group_curve(target, curves, setting)
                        sl, su = median_bounds([curves[i, *setting] for i in source])
                        tl, tu = median_bounds([curves[i, *setting] for i in target])
                        median_exact = sl == su and tl == tu
                        valid_base = [i for i in outside if len(curves[i, *setting]['ks']) >= length] if length else []
                        # Building-equal external baseline, with source-side observation support.
                        baseline = None
                        if valid_base:
                            by_building = collections.defaultdict(list)
                            for i in valid_base: by_building[pv[i]['building']].append(curves[i, *setting]['L'][:length])
                            basecurve = np.mean([np.mean(x, axis=0) for x in by_building.values()], axis=0)
                            baseline = onset(range(2, length+2), basecurve)
                        exact = predicted is not None and predicted == possible and target_onset is not None and target_onset == target_possible
                        indiv = [curves[i, *setting] for i in target]
                        known = [c['conservative_onset'] for c in indiv if c['status'] == 'identified']
                        errors = [abs(predicted-k) for k in known] if predicted is not None and predicted == possible else []
                        records.append(dict(pool=pool, candidate=cand['candidate_id'], building=cand['building'], method=kind,
                            tail=tail, profile=pi, source_n=s, target_n=len(target), balanced=abs(s-len(target)) <= 1,
                            source='|'.join(source), target='|'.join(target), prediction=predicted, prediction_possible=possible,
                            target_onset=target_onset, target_possible=target_possible, baseline=baseline,
                            source_median_lower=sl, source_median_upper=su if np.isfinite(su) else None,
                            target_median_lower=tl, target_median_upper=tu if np.isfinite(tu) else None,
                            median_identified_pair=median_exact, median_absolute_error=abs(sl-tl) if median_exact else None,
                            identified_pair=exact, absolute_error=abs(predicted-target_onset) if exact else None,
                            baseline_error=abs(baseline-target_onset) if exact and baseline is not None else None,
                            target_identified=len(known), individual_comparable=len(errors), individual_error_sum=sum(errors),
                            within1=sum(x <= 1 for x in errors), within2=sum(x <= 2 for x in errors), within3=sum(x <= 3 for x in errors)))
    save('room_inventory.json', inventory)
    df = pd.DataFrame(records); save('room_all_splits.csv.gz', df)
    summary = []
    keys = ['pool', 'method', 'tail', 'profile', 'source_n', 'target_n']
    for key, g in df.groupby(keys):
        ok = g[g.identified_pair]
        b = ok.groupby(['building', 'candidate']).absolute_error.mean().groupby('building').mean()
        same = ok.dropna(subset=['baseline_error'])
        delta = (same.baseline_error-same.absolute_error).groupby([same.building, same.candidate]).mean().groupby('building').mean()
        summary.append(dict(zip(keys, key), splits=len(g), rooms=g.candidate.nunique(), buildings=g.building.nunique(),
                            identified_pairs=len(ok), source_identified=int((g.prediction.notna() & g.prediction.eq(g.prediction_possible)).sum()),
                            target_identified=int((g.target_onset.notna() & g.target_onset.eq(g.target_possible)).sum()),
                            identified_buildings=len(b), building_equal_MAE=b.mean(), matched_baseline_splits=len(same),
                            building_equal_gain=delta.mean(), within2=int(g.within2.sum()), individual_comparable=int(g.individual_comparable.sum())))
    save('room_split_summary.csv', pd.DataFrame(summary))
    return df


def compositions(views):
    rosters = pd.read_csv(DEST/'personnel_roster_snapshot.csv'); records = []; audit = []; teams_saved = []
    patterns = {(4,): 'AAAA', (3, 1): 'AAAB', (2, 2): 'AABB', (2, 1, 1): 'AABC'}
    for (pool, iid), v in views.items():
        if pool != 'strict' or len(v['ids']) < 8: continue
        ids, ws = v['ids'], v['workers']; n = len(ids)
        validation = sorted(range(n), key=lambda j: hashlib.sha256((ids[j]+'|validation').encode()).hexdigest())[:4]
        rest = [j for j in range(n) if j not in validation]
        maps = {cfg: z.set_index('worker').subtype.to_dict()
                for cfg, z in rosters[rosters.heldout_building == v['building']].groupby('config')}
        common = [j for j in rest if all(ws[j] in m for m in maps.values())] if maps else []
        audit.append(dict(image_id=iid, code=v['code'], building=v['building'], N=n, validation=[ws[j] for j in validation],
                          common_classified_pool=len(common), unavailable=[ws[j] for j in rest if j not in common]))
        if len(common) < 4: continue
        ix = np.array(list(itertools.combinations(common, 4)))
        measurements = {}
        for metric, cut in [('image', 25.6), ('sphere', 9.)]:
            d = np.round(v[metric], 8); a, b = np.triu_indices(4, 1)
            measurements[metric] = ((d[ix[:, a], ix[:, b]] > cut).mean(1),
                                   (d[np.array(validation)[None, :, None], ix[:, None, :]] > cut).all(2).mean(1))
        for j, team in enumerate(ix):
            teams_saved.append(dict(image_id=iid, team=j, workers='|'.join(ws[z] for z in team),
                validation='|'.join(ws[z] for z in validation), image_incompatible=measurements['image'][0][j],
                image_uncovered=measurements['image'][1][j], sphere_incompatible=measurements['sphere'][0][j],
                sphere_uncovered=measurements['sphere'][1][j]))
        for cfg, mapping in maps.items():
            grouped = collections.defaultdict(list)
            for j, team in enumerate(ix):
                co = collections.Counter(int(mapping[ws[z]]) for z in team)
                grouped[patterns[tuple(sorted(co.values(), reverse=True))], '|'.join(f'{z}:{co[z]}' for z in sorted(co))].append(j)
            for (pat, signature), ji in grouped.items():
                for metric, (inc, unc) in measurements.items():
                    records.append(dict(image_id=iid, code=v['code'], building=v['building'], config=cfg, pattern=pat,
                        signature=signature, metric=metric, teams=len(ji), incompatible=inc[ji].mean(), uncovered=unc[ji].mean(),
                        all_teams_uncovered=unc.mean(), all_teams_incompatible=inc.mean()))
    save('team_inventory.json', audit); save('actual_teams.csv.gz', pd.DataFrame(teams_saved))
    df = pd.DataFrame(records); save('composition_exact.csv.gz', df)
    per = []
    for key, z in df.groupby(['image_id', 'building', 'config', 'pattern', 'metric']):
        per.append(dict(zip(['image_id', 'building', 'config', 'pattern', 'metric'], key),
                        teams=int(z.teams.sum()), uncovered=np.average(z.uncovered, weights=z.teams),
                        incompatible=np.average(z.incompatible, weights=z.teams), baseline=z.all_teams_uncovered.iloc[0]))
    per = pd.DataFrame(per); save('composition_image.csv', per)
    contrasts = []
    for (cfg, metric), g in per.groupby(['config', 'metric']):
        for pattern in ['AAAA', 'AAAB', 'AABB']:
            a = g[g.pattern == 'AABC'].set_index('image_id'); b = g[g.pattern == pattern].set_index('image_id')
            both = a.index.intersection(b.index)
            if not len(both): continue
            for measure in ['uncovered', 'incompatible']:
                delta = (a.loc[both, measure]-b.loc[both, measure]).groupby(a.loc[both, 'building']).mean()
                boot = np.random.default_rng(20260921).choice(delta.to_numpy(), (5000, len(delta)), replace=True).mean(1)
                contrasts.append(dict(config=cfg, metric=metric, comparator=pattern, measure=measure, images=len(both), buildings=len(delta),
                    AABC=a.loc[both].groupby('building')[measure].mean().mean(), comparator_mean=b.loc[both].groupby('building')[measure].mean().mean(),
                    delta=delta.mean(), interval_low=np.quantile(boot, .025), interval_high=np.quantile(boot, .975)))
    save('composition_paired.csv', pd.DataFrame(contrasts))
    configs = ['Q_3', 'QT_3', 'QTSB_3', 'TRI_3']; common_panel = []
    for metric in ['image', 'sphere']:
        eligible = []
        for cfg in configs:
            z = per[(per.config == cfg) & (per.metric == metric)]
            eligible.append(set(z[z.pattern == 'AAAA'].image_id) & set(z[z.pattern == 'AABC'].image_id))
        common = set.intersection(*eligible)
        for cfg in configs:
            z = per[(per.config == cfg) & (per.metric == metric) & per.image_id.isin(common)]
            a = z[z.pattern == 'AABC'].set_index('image_id'); b = z[z.pattern == 'AAAA'].set_index('image_id')
            delta = (a.uncovered-b.uncovered).groupby(a.building).mean()
            boot = np.random.default_rng(20260921).choice(delta.to_numpy(), (5000, len(delta)), replace=True).mean(1)
            common_panel.append(dict(config=cfg, metric=metric, images=len(common), buildings=len(delta), delta=delta.mean(),
                interval_low=np.quantile(boot, .025), interval_high=np.quantile(boot, .975)))
    save('composition_common_panel.csv', pd.DataFrame(common_panel))


def endpoint_check(job):
    """同H、最后三名观察窗口；可判断存在合格持续阶段，不伪造精确起点。"""
    v, orders, horizon, jid = job
    wi = {w: j for j, w in enumerate(v['workers'])}; result = []
    for kind in ['complete', 'representative']:
        cache = {}; states = np.zeros((len(PROFILES), 3), int)
        for order in orders:
            arrival = [wi[w] for w in order if w in wi][:horizon]; parts = {}
            for k in range(horizon-3, horizon+1):
                ix = tuple(sorted(arrival[:k]))
                if ix not in cache:
                    labels, _ = partition(v['image'][np.ix_(ix, ix)], [v['ids'][j] for j in ix], 25.6, kind)
                    groups = collections.defaultdict(int)
                    for j, label in zip(ix, labels): groups[int(label)] |= 1 << j
                    cache[ix] = tuple(groups.values())
                parts[k] = cache[ix]
            k = horizon-3
            anchor = max(compare_bits(parts[k], parts[j]) for j in range(k+1, horizon+1))
            for pi, (cap, single) in enumerate(PROFILES):
                bad = cap is not None and any(len(p) > cap or sum(g.bit_count() == 1 for g in p)/j > single+1e-12 for j, p in parts.items())
                states[pi, max(anchor, 2 if bad else 0)] += 1
        for pi, ct in enumerate(states):
            result.append(dict(method=kind, profile=pi, H=horizon, k=horizon-3, L=ct[0]/len(orders), U=(ct[0]+ct[1])/len(orders)))
    return jid, clean(result)


def subtype_checks(views, orders, jobs_n):
    rosters = pd.read_csv(DEST/'personnel_roster_snapshot.csv'); jobs = {}; members = []
    for (pool, iid), v in views.items():
        if pool != 'strict': continue
        available = rosters[rosters.heldout_building == v['building']]
        maps = [set(z.worker) for _, z in available.groupby('config')]
        common = set.intersection(*maps) if maps else set()
        pool_ix = [j for j, w in enumerate(v['workers']) if w in common]
        for (cfg, subtype), g in available.groupby(['config', 'subtype']):
            ix = [j for j in pool_ix if v['workers'][j] in set(g.worker)]
            h = len(ix)
            if h < 5: continue
            keys = []
            for selected in [ix, pool_ix]:
                ids = tuple(v['ids'][j] for j in selected); key = (ids, h)
                if key not in jobs:
                    sub = dict(v, ids=list(ids), workers=[v['workers'][j] for j in selected], image=v['image'][np.ix_(selected, selected)])
                    jobs[key] = (sub, orders, h, str(len(jobs)))
                keys.append(jobs[key][3])
            members.append(dict(image_id=iid, code=v['code'], building=v['building'], config=cfg, subtype=int(subtype), H=h,
                                workers=[v['workers'][j] for j in ix], classified_population=len(pool_ix), actual=keys[0], control=keys[1]))
    save('subtype_members.json', members); results = {}
    with ProcessPoolExecutor(max_workers=jobs_n) as executor:
        for jid, result in executor.map(endpoint_check, jobs.values()):
            results[jid] = result
            if len(results) % 100 == 0: print('subtype checks', len(results), '/', len(jobs), flush=True)
    save('subtype_endpoint_curves.json', results)
    summarize_subtypes(members, results)


def summarize_subtypes(members, results):
    records = []
    for row in members:
        for actual, control in zip(results[row['actual']], results[row['control']]):
            assert (actual['method'], actual['profile'], actual['H']) == (control['method'], control['profile'], control['H'])
            records.append(dict(**{k: v for k, v in row.items() if k not in ['workers', 'actual', 'control', 'H']}, **actual,
                                random_L=control['L'], random_U=control['U'], gain=actual['L']-control['L'],
                                observed_stage=actual['L'] >= .8, random_stage=control['L'] >= .8))
    df = pd.DataFrame(records); save('subtype_matched.csv.gz', df)
    summary = []
    for key, z in df.groupby(['config', 'subtype', 'method', 'profile']):
        by = z.groupby('building')[['L', 'random_L', 'gain', 'observed_stage', 'random_stage']].mean()
        boot = np.random.default_rng(20260921).choice(by.gain.to_numpy(), (5000, len(by)), replace=True).mean(1)
        summary.append(dict(zip(['config', 'subtype', 'method', 'profile'], key), images=len(z), buildings=len(by), min_H=int(z.H.min()), max_H=int(z.H.max()),
                            **by.mean().to_dict(), interval_low=np.quantile(boot, .025), interval_high=np.quantile(boot, .975)))
    save('subtype_summary.csv', pd.DataFrame(summary)); print('SUBTYPES DONE', flush=True)


def matched_horizon(views, candidates, orders, jobs_n):
    pv = {i: v for (p, i), v in views.items() if p == 'strict' and len(v['ids'])}
    jobs = {}; groups = []; seen = set()
    for cand in candidates:
        images = sorted(i for i in cand['image_ids'] if i in pv)
        if len(images) < 2 or tuple(images) in seen: continue
        seen.add(tuple(images)); h = min(len(pv[i]['ids']) for i in images)
        mapping = {}
        for i in images:
            key = (tuple(pv[i]['ids']), h)
            if key not in jobs: jobs[key] = dict(pv[i], horizon=h, job_id=str(len(jobs)))
            mapping[i] = jobs[key]['job_id']
        groups.append(dict(candidate=cand['candidate_id'], building=cand['building'], H=h, images=images, jobs=mapping))
    save('matched_horizon_inventory.json', groups); results = {}
    with ProcessPoolExecutor(max_workers=jobs_n) as executor:
        for jid, value in executor.map(image_curves, [(v, orders) for v in jobs.values()]):
            results[jid] = value
            if len(results) % 20 == 0: print('matched horizon', len(results), '/', len(jobs), flush=True)
    save('matched_horizon_curves.json', results); rows = []
    for g in groups:
        cc = {(i, c['method'], c['tail'], c['profile']): c for i, jid in g['jobs'].items() for c in results[jid]}
        for setting in itertools.product(['complete', 'representative'], TAILS, range(len(PROFILES))):
            for size in split_sizes(len(g['images'])):
                for source in itertools.combinations(g['images'], size):
                    target = sorted(set(g['images'])-set(source))
                    a, b = median_bounds([cc[i, *setting] for i in source]); c, d = median_bounds([cc[i, *setting] for i in target])
                    rows.append(dict(candidate=g['candidate'], building=g['building'], H=g['H'], method=setting[0], tail=setting[1], profile=setting[2],
                        source='|'.join(source), target='|'.join(target), source_n=size, target_n=len(target),
                        source_lower=a, source_upper=b if np.isfinite(b) else None, target_lower=c, target_upper=d if np.isfinite(d) else None,
                        identified=a == b and c == d, absolute_error=abs(a-c) if a == b and c == d else None))
    save('matched_horizon_splits.csv.gz', pd.DataFrame(rows)); print('MATCHED HORIZON DONE', flush=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--reuse-curves', action='store_true', help='仅复用本次固定输入运行的曲线；先核对全部作答与距离一致')
    parser.add_argument('--subtypes-only', action='store_true')
    parser.add_argument('--matched-horizon-only', action='store_true')
    args = parser.parse_args(); _, views = load_views()
    if not (args.subtypes_only or args.matched_horizon_only):
        save('personnel_roster_snapshot.csv', pd.read_csv(ROSTER))
    registry = read('analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    candidates = [c for c in registry['candidates'] if c['physical_same_supported']]
    workers = sorted({w for v in views.values() for w in v['workers']})
    rng = np.random.default_rng(20260921); orders = [rng.permutation(workers).tolist() for _ in range(200)]
    if args.subtypes_only or args.matched_horizon_only:
        frozen = json.loads((DEST/'curve_inputs.json').read_text(encoding='utf-8'))
        frozen_by_ids = {tuple(v['ids']): v for v in frozen.values()}
        assert all(view_input(v) == frozen_by_ids[tuple(v['ids'])] for v in views.values())
        if args.subtypes_only: subtype_checks(views, orders, args.jobs)
        else: matched_horizon(views, candidates, orders, args.jobs)
        return
    jobs = {}; identities = {}
    for v in views.values():
        key = tuple(v['ids'])
        if key not in jobs:
            jid = str(len(jobs)); v['job_id'] = jid
            jobs[key] = dict(v); identities[jid] = view_input(v)
        else:
            assert view_input(v) == view_input(jobs[key])
            v['job_id'] = jobs[key]['job_id']
    DEST.mkdir(parents=True, exist_ok=True)
    if args.reuse_curves:
        assert json.loads((DEST/'curve_inputs.json').read_text(encoding='utf-8')) == identities
        results = json.loads((DEST/'curves.json').read_text(encoding='utf-8'))
    else:
        save('curve_inputs.json', identities); save('global_orders.json', orders)
        results = {}
        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            for jid, result in executor.map(image_curves, [(v, orders) for v in jobs.values()]):
                results[jid] = result
                if len(results) % 20 == 0: print('curves', len(results), '/', len(jobs), flush=True)
        save('curves.json', results)
    flat = []
    for (pool, iid), v in views.items():
        for c in results[v['job_id']]:
            flat.append(dict(pool=pool, image_id=iid, code=v['code'], building=v['building'],
                             **{k: val for k, val in c.items() if k not in ['ks', 'L', 'U', 'stable', 'unknown', 'changing']}))
    save('image_onsets.csv', pd.DataFrame(flat))
    print('room exhaustive splits', flush=True)
    room_transfer(views, results, candidates)
    print('actual team enumeration', flush=True); compositions(views)
    save('RUN.json', dict(orders=200, seed=20260921, unique_pools=len(jobs), image_views=len(views),
        methods=['image_max_endpoint_complete', 'image_max_endpoint_representative'], pixel_probe=25.6,
        profiles=PROFILES, tails=TAILS, epsilon=.1, repeated_support=2, order_probability=.8,
        no_frozen_caps=True, historical_frozen_time_changed=False, classification_target_building_excluded=True,
        team_validation='fixed four disjoint responses; same classified team universe across six configurations',
        inputs=['../responses.jsonl.gz', '../distances.json', str(ROSTER.relative_to(ROOT))],
        limitation='finite observed pools; deterministic partitions conditional on candidate method; not prospective stopping validation'))
    subtype_checks(views, orders, args.jobs)
    matched_horizon(views, candidates, orders, args.jobs)
    print('DONE', flush=True)


if __name__ == '__main__': main()
