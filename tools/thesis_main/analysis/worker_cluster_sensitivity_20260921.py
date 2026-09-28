"""Exploratory leave-worker-out sensitivity; never changes annotation eligibility.

Run as a file (frozen source package shadows the maintained tools package):
python tools/thesis_main/analysis/worker_cluster_sensitivity_20260921.py
Joint endpoints: import this module and call joint().
"""
from pathlib import Path
import collections
import importlib.util
import json
import itertools
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'analysis_results/panorama_research_received_20260921/original_package'
SOURCE = PACKAGE.parent / 'local_recompute/source_work'
OUT = ROOT / 'analysis_results/worker_cluster_sensitivity_20260921/numeric'
sys.path.insert(0, str(PACKAGE / 'code'))
import common as c
c.configure(SOURCE)
spec = importlib.util.spec_from_file_location('reference_replay', PACKAGE / 'code/02_replay.py')
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)


def subset(v, ix):
    return dict(image_id=v['image_id'], code=v['code'], building=v['building'], N=len(ix),
                ids=[v['ids'][j] for j in ix], workers=[v['workers'][j] for j in ix],
                d=v['d'][np.ix_(ix, ix)])


def metrics(v, kind):
    labels, _ = c.part(v['d'], v['ids'], kind)
    sizes = collections.Counter(labels)
    return dict(K=len(sizes), singleton_mass=sum(s == 1 for s in sizes.values()) / v['N'],
                U8=c.next_uncovered(v['d'], 8)), labels


def replay(v, orders):
    """Reference epsilon=.1/tail=3 rules with per-order detail omitted."""
    n = v['N']; index = {w: j for j, w in enumerate(v['workers'])}; result = []
    for kind in ['complete', 'representative']:
        cache = {}; counts = {p: np.zeros((max(0, n-4), 3), int) for p in ['uncapped', 'cap3_s20']}
        for order in orders:
            mask = 0; parts = {}
            for k, j in enumerate((index[w] for w in order if w in index), 1):
                mask |= 1 << j
                if k < 2:
                    continue
                if mask not in cache:
                    ix = [i for i in range(n) if mask & (1 << i)]
                    labels, _ = c.part(v['d'][np.ix_(ix, ix)], [v['ids'][i] for i in ix], kind)
                    groups = collections.defaultdict(int)
                    for i, label in zip(ix, labels):
                        groups[int(label)] |= 1 << i
                    cache[mask] = tuple(groups.values())
                parts[k] = cache[mask]
            anchors = {k: max(1 if not repeat else 2 if rel > .1+1e-12 or tv > .1+1e-12 or promotion else 0
                              for rel, tv, promotion, repeat in (ref.comparisons(parts[k], parts[j]) for j in range(k+1, n+1)))
                       for k in range(2, n)}
            for profile, count in counts.items():
                bad = {k: 2 * int(profile == 'cap3_s20' and (len(g) > 3 or sum(x.bit_count() == 1 for x in g)/k > .2+1e-12))
                       for k, g in parts.items()}
                status = max((bad[j] for j in range(max(2, n-2), n+1)), default=0)
                for k in range(n-3, 1, -1):
                    status = max(status, anchors[k], bad[k]); count[k-2, status] += 1
        for profile, count in counts.items():
            lower = count[:, 0] / len(orders); upper = count[:, :2].sum(1) / len(orders)
            ks = list(range(2, n-2))
            lo = next((k for k, p in zip(ks, upper) if p >= .8-1e-12), None)
            hi = next((k for k, p in zip(ks, lower) if p >= .8-1e-12), None)
            status = ('identified' if lo is not None and lo == hi else 'bounded_unknown' if hi is not None
                      else 'possible_only' if lo is not None else 'insufficient_tail' if not ks else 'not_reached')
            result.append(dict(image_id=v['image_id'], code=v['code'], building=v['building'], N=n,
                               method=kind, profile=profile, status=status, possible_onset=lo, conservative_onset=hi,
                               final_stable_probability=lower[-1] if ks else None))
    return result


def replay_job(job):
    scenario, v, orders = job
    return [dict(scenario=scenario, **r) for r in replay(v, orders)]


def verify_baseline():
    mem = pd.read_csv(OUT / 'memberships.csv')
    old = pd.read_csv(PACKAGE / 'results/current_memberships.csv')
    merged = mem.merge(old[['id', 'method', 'cluster_size']], on=['id', 'method'], validate='one_to_one')
    assert len(merged) == 4888 and merged.singleton.eq(merged.cluster_size.eq(1)).all()
    rp = pd.read_csv(OUT / 'replay_per_image.csv'); actual = rp[rp.scenario == 'baseline']
    old = pd.read_csv(PACKAGE / 'results/replay_onsets.csv')
    old = old[(old.N >= 8) & (old.epsilon == .1) & (old['tail'] == 3) & old.profile.isin(['uncapped', 'cap3_s20'])]
    merged = actual.merge(old, on=['image_id', 'method', 'profile'], suffixes=('_new', '_old'), validate='one_to_one')
    assert len(merged) == 440
    for column in ['status', 'possible_onset', 'conservative_onset', 'final_stable_probability']:
        assert merged[column+'_new'].fillna(-1).eq(merged[column+'_old'].fillna(-1)).all(), column
    result = dict(membership_rows_exact=4888, replay_setting_rows_exact=440, profiles=['uncapped', 'cap3_s20'], methods=['complete', 'representative'])
    (OUT / 'baseline_verification.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    return result


def transitions(views):
    rows = []
    for v in views.values():
        if v['N'] < 8 or 'W037' not in v['workers']:
            continue
        j = v['workers'].index('W037'); ix = [i for i in range(v['N']) if i != j]
        for kind in ['complete', 'representative']:
            _, a = metrics(v, kind); _, b = metrics(subset(v, ix), kind)
            sa, sb = collections.Counter(a), collections.Counter(b)
            rows.append(dict(image_id=v['image_id'], method=kind, deleted_singleton=int(sa[a[j]] == 1),
                             new_singletons=sum(sa[a[k]] > 1 and sb[b[t]] == 1 for t, k in enumerate(ix)),
                             lost_singletons=sum(sa[a[k]] == 1 and sb[b[t]] > 1 for t, k in enumerate(ix))))
    pd.DataFrame(rows).to_csv(OUT / 'w037_singleton_transitions.csv', index=False)


def target_panel_summary():
    assignments = pd.read_csv(OUT / 'replay_control_assignments.csv')
    replay_rows = pd.read_csv(OUT / 'replay_per_image.csv'); rows = []
    for target, selected in assignments.groupby('target'):
        panel = replay_rows[replay_rows.image_id.isin(selected.image_id) & replay_rows.scenario.isin(['baseline', 'remove_'+target, 'control_'+target])]
        for (scenario, method, profile), g in panel.groupby(['scenario', 'method', 'profile']):
            rows.append(dict(target=target, scenario=scenario, method=method, profile=profile, images=len(g),
                             identified=sum(g.status == 'identified'), possible_only=sum(g.status == 'possible_only'),
                             not_reached=sum(g.status == 'not_reached'), mean_final_stable_probability=g.final_stable_probability.mean()))
    pd.DataFrame(rows).to_csv(OUT / 'replay_target_panel_summary.csv', index=False)


def joint():
    """Joint deletion and equal-count random deletion, separate from primary run."""
    _, _, views, _, _ = c.load()
    selected = json.loads((OUT / 'selected.json').read_text())
    rng = np.random.default_rng(c.SEED+2); rows = []; scope = []
    for v in views.values():
        if v['N'] < 8:
            continue
        removed = [j for j, w in enumerate(v['workers']) if w in selected]
        kept = [j for j in range(v['N']) if j not in removed]
        # Uniform subsets of the original image pool; may include target workers.
        possibilities = list(itertools.combinations(range(v['N']), len(removed)))
        controls = possibilities if len(possibilities) <= 200 else [possibilities[j] for j in rng.choice(len(possibilities), 200, replace=False)]
        scope.append(dict(image_id=v['image_id'], original_N=v['N'], retained_N=len(kept), removed=len(removed),
                          baseline_U8_defined=v['N'] > 8, retained_U8_defined=len(kept) > 8,
                          baseline_tail_defined=v['N'] >= 5, retained_tail_defined=len(kept) >= 5,
                          control_subsets=len(controls), control_exact=len(controls) == len(possibilities)))
        for kind in ['complete', 'representative']:
            base, _ = metrics(v, kind); actual, _ = metrics(subset(v, kept), kind)
            null = [metrics(subset(v, [j for j in range(v['N']) if j not in deletion]), kind)[0] for deletion in controls]
            row = dict(image_id=v['image_id'], building=v['building'], N=v['N'], retained_N=len(kept), method=kind)
            for metric in base:
                row['baseline_'+metric] = base[metric]; row['removed_'+metric] = actual[metric]
                row['control_'+metric] = np.mean([r[metric] for r in null])
            rows.append(row)
    pd.DataFrame(scope).to_csv(OUT / 'joint_scope.csv', index=False)
    result = pd.DataFrame(rows); result.to_csv(OUT / 'joint_endpoint_per_image.csv', index=False)
    summary = []
    for kind, g in result.groupby('method'):
        for metric in ['K', 'singleton_mass', 'U8']:
            z = g[g.retained_N > 8] if metric == 'U8' else g
            summary.append(dict(method=kind, metric=metric, images=len(z), baseline=z['baseline_'+metric].mean(),
                                removed=z['removed_'+metric].mean(), control=z['control_'+metric].mean()))
    pd.DataFrame(summary).to_csv(OUT / 'joint_endpoint_summary.csv', index=False)
    print(pd.DataFrame(summary).to_string(index=False), flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plan = dict(source=str(SOURCE), cut=25.6, seed=c.SEED, orders=200, epsilon=.1, tail=3,
                selection='Top 3 complete-linkage singleton fractions on original N>=8 images, minimum 20 observations; include W037 if absent.',
                controls='Endpoint: exact mean of deleting every other worker on identical images. Replay: one seeded uniform other-worker deletion per target/image, 200 shared worker orders.',
                panels='Original N>=8 fixed panel; target-present panel also reported. U8 comparisons restricted to original N>=10 so all deletions retain N>8.',
                limitation='Exploratory conditional finite-pool sensitivity, no prospective stopping claim; singleton count is not a quality verdict; does not modify eligibility.')
    (OUT / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf8')
    _, _, views, _, _ = c.load()
    workers = sorted({w for v in views.values() for w in v['workers']})
    ranking = []; endpoint = []; membership = []
    for v in views.values():
        for kind in ['complete', 'representative']:
            base, labels = metrics(v, kind); sizes = collections.Counter(labels)
            deletes = [metrics(subset(v, [i for i in range(v['N']) if i != j]), kind)[0] for j in range(v['N'])] if v['N'] > 1 else []
            for j, w in enumerate(v['workers']):
                singleton = int(sizes[labels[j]] == 1)
                membership.append(dict(image_id=v['image_id'], id=v['ids'][j], worker=w, method=kind, N=v['N'], singleton=singleton,
                                       excess=singleton-base['singleton_mass']))
                if not deletes:
                    continue
                row = dict(image_id=v['image_id'], code=v['code'], building=v['building'], N=v['N'], worker=w, method=kind)
                for metric in base:
                    row['baseline_'+metric] = base[metric]
                    row['removed_'+metric] = deletes[j][metric]
                    row['control_'+metric] = np.mean([r[metric] for i, r in enumerate(deletes) if i != j])
                endpoint.append(row)
    mem = pd.DataFrame(membership); ep = pd.DataFrame(endpoint)
    transitions(views)
    for (kind, w), g in mem.groupby(['method', 'worker']):
        for scope, z in [('all', g), ('N_ge8', g[g.N >= 8])]:
            ranking.append(dict(method=kind, worker=w, scope=scope, images=len(z), singleton_count=z.singleton.sum(),
                                singleton_fraction=z.singleton.mean(), within_image_excess=z.excess.mean()))
    rank = pd.DataFrame(ranking)
    selected = rank[(rank.method == 'complete') & (rank.scope == 'N_ge8') & (rank.images >= 20)].sort_values(['singleton_fraction', 'worker'], ascending=[False, True]).head(3).worker.tolist()
    if 'W037' not in selected:
        selected.append('W037')
    mem.to_csv(OUT / 'memberships.csv', index=False); rank.to_csv(OUT / 'worker_ranking.csv', index=False)
    ep.to_csv(OUT / 'endpoint_per_image.csv', index=False)
    summaries = []; scopes = []
    for (kind, w), g in ep.groupby(['method', 'worker']):
        z = g[g.N >= 8]
        scopes.append(dict(worker=w, method=kind, target_images=len(z), lost_U8=int((z.N == 9).sum()),
                           lost_tail=0, retained_below8=int((z.N == 8).sum())))
        for metric in ['K', 'singleton_mass', 'U8']:
            x = z[z.N >= 10] if metric == 'U8' else z
            summaries.append(dict(method=kind, worker=w, metric=metric, images=len(x),
                                  baseline=x['baseline_'+metric].mean(), removed=x['removed_'+metric].mean(),
                                  control=x['control_'+metric].mean(), difference_vs_control=(x['removed_'+metric]-x['control_'+metric]).mean()))
    pd.DataFrame(summaries).to_csv(OUT / 'endpoint_summary.csv', index=False)
    pd.DataFrame(scopes).to_csv(OUT / 'individual_scope.csv', index=False)
    (OUT / 'selected.json').write_text(json.dumps(selected), encoding='utf8')
    print('Selected', selected, flush=True)
    rng = np.random.default_rng(c.SEED); orders = [list(rng.permutation(workers)) for _ in range(200)]
    rng_control = np.random.default_rng(c.SEED+1); jobs = []; assignments = []
    for v in views.values():
        if v['N'] < 8:
            continue
        jobs.append(('baseline', subset(v, list(range(v['N']))), orders))
        for w in selected:
            ix = list(range(v['N'])); control = None
            if w in v['workers']:
                j = v['workers'].index(w); ix.remove(j)
                control = int(rng_control.choice(ix))
                assignments.append(dict(image_id=v['image_id'], target=w, deleted_control=v['workers'][control]))
            jobs.append(('remove_'+w, subset(v, ix), orders))
            jobs.append(('control_'+w, subset(v, [i for i in range(v['N']) if i != control]), orders))
    pd.DataFrame(assignments).to_csv(OUT / 'replay_control_assignments.csv', index=False)
    rows = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        for j, result in enumerate(pool.map(replay_job, jobs)):
            rows.extend(result)
            if j % 25 == 0:
                print('replay', j, '/', len(jobs), flush=True)
    rp = pd.DataFrame(rows); rp.to_csv(OUT / 'replay_per_image.csv', index=False)
    rs = []
    for (scenario, kind, profile), g in rp.groupby(['scenario', 'method', 'profile']):
        rs.append(dict(scenario=scenario, method=kind, profile=profile, images=len(g), statuses=g.status.value_counts().to_dict(),
                       mean_final_stable_probability=g.final_stable_probability.mean()))
    (OUT / 'replay_summary.json').write_text(json.dumps(c.clean(rs), ensure_ascii=False, indent=2), encoding='utf8')
    verify_baseline()
    target_panel_summary()
    print(json.dumps(c.clean(rs), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
