"""Part B: outcome-independent common swaps and adjacent-k mechanism checks."""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/workers/personnel_type_validation_next_20261019'
RUNTIME = ROOT / 'analysis_results/personnel_type_runtime_20261019'
KS = [7, 8, 9, 11, 12, 13, 15, 16, 17, 23, 24, 25]
SEED = 'codex-common-swaps-20261019-v1'


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read(path):
    opener = gzip.open if Path(path).suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig') as f:
        return json.load(f)


def save(path, x):
    from pool_io import clean
    path = Path(path)
    raw = (json.dumps(clean(x), ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)


def runtime(base):
    source = Path(base).resolve() / 'work_v2_20261019'
    sys.path.insert(0, str(source / 'fusion'))
    import fusion_engine as fe
    return source, fe


def member_design(pool_id, workers):
    rng = np.random.default_rng(int(digest([SEED, pool_id, 'candidates'])[:16], 16))
    order = rng.permutation(sorted(workers)).tolist()
    candidates, remaining = order[:3], order[3:]
    backgrounds = []
    for context in range(2):
        rng = np.random.default_rng(int(digest([SEED, pool_id, 'background', context])[:16], 16))
        backgrounds.append(rng.permutation(remaining).tolist()[:24])
    return dict(candidates=candidates, backgrounds=backgrounds)


def same_class(a, b):
    if any(pd.isna(v) or 'unknown' in str(v).lower() for v in (a, b)):
        return None
    return a == b


def alternative_q(edge, anchor):
    if edge['worker_a'] == anchor:
        return edge['q_b']
    if edge['worker_b'] == anchor:
        return edge['q_a']
    raise ValueError('anchor_not_in_edge')


def vote_gate(supports, n):
    threshold = (n + 1) // 2
    return dict(vote_threshold=threshold,
                one_swap_can_flip=any(s in (threshold-1, threshold) for s in supports),
                near_vote_groups=sum(s in (threshold-1, threshold) for s in supports))


def stable(row, q, floor, angle):
    keys = ['abs_B8L2_change', 'floor_jaccard_difference', 'structure_bound_cyclic_deg']
    return bool(row['both_complete'] and row['node_count_difference'] == 0
                and all(row.get(k) is not None and math.isfinite(row[k]) for k in keys)
                and row[keys[0]] <= q and row[keys[1]] <= floor and row[keys[2]] <= angle)


def paired_summary(df, near, far):
    d = df.dropna(subset=[near, far]).copy()
    if d.empty:
        return dict(buildings=0, images=0, paired_rows=0, delta=None)
    d[[near, far]] = d[[near, far]].astype(float)
    im = d.groupby(['building', 'pool_id'])[[near, far]].mean()
    b = im.groupby('building').mean()
    delta = (b[far] - b[near]).to_numpy()
    rng = np.random.default_rng(20261019)
    draws = rng.choice(delta, (10000, len(delta)), replace=True).mean(axis=1)
    return dict(buildings=len(b), images=len(im), paired_rows=len(d),
                near=float(b[near].mean()), far=float(b[far].mean()), delta=float(delta.mean()),
                low=float(np.quantile(draws, .025)), high=float(np.quantile(draws, .975)),
                image_delta=float((im[far]-im[near]).mean()),
                experiment_delta=float((d[far]-d[near]).mean()))


def history_rows(assignments):
    a = assignments[(assignments.layer == 'ordinary_manual') & (assignments.method == 'affinity')]
    rows = []
    for (pid, cut), g in a.groupby(['pool_id', 'threshold_deg']):
        first = g.iloc[0]
        for x, y in itertools.combinations(g.to_dict('records'), 2):
            rows.append(dict(pool_id=pid, building=first.building_id, difficulty=first.difficulty,
                             cut=int(cut), pair='|'.join(sorted([x['worker_id'], y['worker_id']])),
                             same=x['cluster_id'] == y['cluster_id']))
    return pd.DataFrame(rows)


def register(base, out, layer='ordinary_manual'):
    source, fe = runtime(base)
    out.mkdir(parents=True, exist_ok=False)
    pools = read(source/'fusion/INPUT_SNAPSHOT.json.gz')['images']
    fold = pd.read_csv(source/'profiles/fold_profiles.csv')
    assignments = pd.read_csv(source/'clusters/assignments.csv')
    histories = history_rows(assignments)
    chosen = {}
    coverage = []
    for p in sorted(pools, key=lambda p: digest([SEED, 'panel', p['pool_id']])):
        m = p['meta']
        eligible = m['layer'] == layer and m['difficulty_aligned'] and len(p['records']) >= 27
        key = (m['building'], m['difficulty'])
        selected = eligible and key not in chosen
        if selected:
            chosen[key] = p
        coverage.append(dict(**m, eligible=eligible, selected=selected,
                             reason='selected' if selected else 'other_pool_in_stratum' if eligible else 'layer_alignment_or_n27'))
    requests, events, panels, labels = [], [], [], []
    for (building, difficulty), pool in sorted(chosen.items()):
        pid = pool['pool_id']
        records = {r['worker_id']: r for r in pool['records']}
        md = member_design(pid, records)
        fp = fold[fold.heldout_building == building].set_index('worker_id').to_dict('index') if layer == 'ordinary_manual' else {}
        train = histories[histories.building != building]
        prior = train.groupby(['building', 'pool_id', 'difficulty', 'cut']).same.mean().groupby(
            ['building', 'difficulty', 'cut']).mean().groupby(['difficulty', 'cut']).mean()
        stats = train.groupby(['pair', 'difficulty', 'cut']).agg(s=('same', 'sum'), n=('pool_id', 'nunique'), buildings=('building', 'nunique'))
        panels.append(dict(pool_id=pid, building=building, difficulty=difficulty, **md))
        for a, b in itertools.combinations(md['candidates'], 2):
            x, y = fp.get(a, {}), fp.get(b, {})
            label = dict(pool_id=pid, worker_a=a, worker_b=b,
                         Q_same=same_class(x.get('Q2_B8L2'), y.get('Q2_B8L2')),
                         QT_same=same_class(x.get('QT_B8L2'), y.get('QT_B8L2')),
                         QTD_same=same_class(x.get('fine_dtype_B8L2'), y.get('fine_dtype_B8L2')),
                         q_a=x.get('Q_effect_B8L2'), q_b=y.get('Q_effect_B8L2'),
                         T_a=x.get('T_source_effect'), T_b=y.get('T_source_effect'),
                         target_same_pair_count=len(records[a]['points']) == len(records[b]['points']))
            for cut in (9, 12):
                key = ('|'.join(sorted([a, b])), difficulty, cut)
                st = stats.loc[key] if key in stats.index else None
                support = layer == 'ordinary_manual' and st is not None and st.n >= 6 and st.buildings >= 3
                label.update({f'history_{cut}': float((st.s + 5*prior[(difficulty, cut)])/(st.n+5)) if support else None,
                              f'history_{cut}_images': int(st.n) if st is not None and layer == 'ordinary_manual' else 0,
                              f'history_{cut}_buildings': int(st.buildings) if st is not None and layer == 'ordinary_manual' else 0})
            labels.append(label)
        for context, background in enumerate(md['backgrounds']):
            for k in KS:
                rids = {}
                for arm, w in enumerate(md['candidates']):
                    rid = f'b_{digest([pid, context, k, w])[:20]}'
                    rids[w] = rid
                    requests.append(dict(request_id=rid, request_family='common_swap_panel', pool_id=pid,
                                         k=k, worker_ids=background[:k-1]+[w], context=context, arm=arm,
                                         entrant_worker_id=w, background_worker_ids=background[:k-1]))
                for a, b in itertools.combinations(md['candidates'], 2):
                    events.append(dict(event_id=digest([pid, context, k, a, b])[:20], pool_id=pid,
                                       building=building, difficulty=difficulty, context=context, k=k,
                                       worker_a=a, worker_b=b, request_a=rids[a], request_b=rids[b]))
    reg = dict(status='registered_before_new_panel_outputs', data_release='v2', seed=SEED, k=KS,
               panel=f'first deterministic hash pool per building*difficulty; {layer}, aligned, n>=27',
               layer=layer, class_label_policy='heldout ordinary Manual baseline' if layer == 'ordinary_manual' else 'unknown: no condition-specific fitted classes; do not transfer ordinary Manual labels',
               members='3 uniformly sampled candidate identities, same across 2 independent background permutations and all k',
               selection_uses_target_geometry=False, selection_uses_class_labels=False,
               history='assignment-derived exact pair co-membership; heldout building excluded; >=6 images/3 buildings; shrinkage5',
               metrics='B8L2 signed/absolute, D10, floor Jaccard, equal-count bound cyclic angle, node/identity/connection, failures',
               thresholds=dict(strict=[1,.02,2], main=[2,.05,3], wide=[5,.1,5]),
               inference='context then image then building equal; paired bootstrap buildings10000; alternative weights shown',
               scientific_status='retrospective_exploratory_not_new_blind_data',
               implementation='unmodified frozen fusion_engine.run_pool; independent portable comparator, no fcntl shim',
               special_layers='not_in_this_first_panel' if layer == 'ordinary_manual' else 'separate condition-specific descriptive mechanism extension', N1_applied=False,
               input_files={n: fe.sha(source/n) for n in ['fusion/INPUT_SNAPSHOT.json.gz', 'profiles/fold_profiles.csv', 'clusters/assignments.csv']},
               sources='Pro curated bootstrap; missing Dot full payload not used',
               expected=dict(pools=len(chosen), buildings=len({k[0] for k in chosen}), requests=len(requests), events=len(events)))
    fe.validate_requests(dict(requests=requests), list(chosen.values()))
    save(out/'REGISTRATION.json', reg)
    save(out/'DESIGN.json.gz', dict(panels=panels, requests=requests, events=events, labels=labels))
    pd.DataFrame(coverage).to_csv(out/'POOL_COVERAGE.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(labels).to_csv(out/'PAIR_LABELS.csv', index=False, encoding='utf-8-sig')
    print(reg['expected'], flush=True)


def run_one(base, out, pool, requests):
    _, fe = runtime(base)
    fe.OUT = Path(out)/'runtime'
    return fe.run_pool(pool, requests)


def run(base, out, jobs):
    source, fe = runtime(base)
    design = read(out/'DESIGN.json.gz')
    reg = read(out/'REGISTRATION.json')
    assert all(fe.sha(source/n) == h for n,h in reg['input_files'].items()), 'frozen_inputs_changed'
    pools = {p['pool_id']: p for p in read(source/'fusion/INPUT_SNAPSHOT.json.gz')['images']}
    requests = pd.DataFrame(design['requests'])
    receipts = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futures = [ex.submit(run_one, base, out, pools[pid], g.to_dict('records')) for pid, g in requests.groupby('pool_id')]
        for f in as_completed(futures):
            row = f.result()
            receipts.append(row)
            save(out/'RUN_RECEIPTS.json', receipts)
            print(json.dumps(dict(done=len(receipts), total=len(futures), pool=row['pool_id'],
                                  fusions=row['new_fusions'], seconds=round(row['total_seconds'], 1),
                                  exceptions=len(row['exceptions']))), flush=True)


def compare(a, b, sa, sb, fe):
    out = dict(both_complete=bool(a['complete_evaluable'] and b['complete_evaluable']),
               complete_a=a['complete_evaluable'], complete_b=b['complete_evaluable'],
               Q_a=a.get('B8L2'), Q_b=b.get('B8L2'),
               B8L2_change=None, abs_B8L2_change=None, D10_change=None,
               node_count_difference=None, floor_jaccard_difference=None,
               structure_bound_cyclic_deg=None, structure_reason='missing_state',
               changed_coidentity_pairs=None, selected_shared_change=None, edge_change=None,
               common_partition_unchanged=None, shared_group_vote_flips=None,
               one_swap_can_flip=None, near_vote_groups=None)
    for name in ('B8L2', 'D10'):
        if a.get(name) is not None and b.get(name) is not None:
            out[name+'_change'] = b[name]-a[name]
    if out['B8L2_change'] is not None:
        out['abs_B8L2_change'] = abs(out['B8L2_change'])
    if sa is not None and sb is not None:
        out.update(fe.structural_distance(sa['candidate']['points'], sb['candidate']['points']))
        out.update(node_count_difference=abs(a['nodes']-b['nodes']))
        pa, pb = fe.footprint(sa['candidate']['footprint']), fe.footprint(sb['candidate']['footprint'])
        if pa is not None and pb is not None and a['complete_floor_evaluable'] and b['complete_floor_evaluable']:
            out['floor_jaccard_difference'] = 1-pa.intersection(pb).area/pa.union(pb).area
        def groups(s):
            return {g['feature_id']: frozenset((m['id'], m['pair_index']) for m in g['members']) for g in s['identity_groups']}
        ga, gb = groups(sa), groups(sb)
        shared = set().union(*ga.values()) & set().union(*gb.values())
        def signatures(s, gs):
            restricted = {v & shared: g['selected'] for g in s['identity_groups'] if (v := gs[g['feature_id']]) & shared}
            co = {frozenset(p) for g in restricted for p in itertools.combinations(g, 2)}
            selected = set().union(*(g for g, selected in restricted.items() if selected))
            ring = s['candidate'].get('feature_ids', [])
            edges = None if s['candidate']['points'] is None else {frozenset((x, y)) for u, v in zip(ring, ring[1:]+ring[:1])
                for x in gs[u] & shared for y in gs[v] & shared if x != y}
            return restricted, co, selected, edges
        ra, ca, sela, ea = signatures(sa, ga)
        rb, cb, selb, eb = signatures(sb, gb)
        same_partition = ra.keys() == rb.keys()
        out.update(changed_coidentity_pairs=len(ca ^ cb), common_partition_unchanged=same_partition,
                   selected_shared_change=len(sela ^ selb)/len(shared) if shared else None,
                   shared_group_vote_flips=sum(ra[g] != rb[g] for g in ra) if same_partition else None,
                   edge_change=len(ea ^ eb)/len(ea | eb) if ea is not None and eb is not None and ea | eb else None,
                   **vote_gate([g['support'] for g in sa['identity_groups']], sa['n']))
    for name, q, f, s in [('strict',1,.02,2), ('main',2,.05,3), ('wide',5,.1,5)]:
        out['stable_'+name] = stable(out, q, f, s)
    return out


def summarize(base, out):
    source, fe = runtime(base)
    design = read(out/'DESIGN.json.gz')
    labels = {(r['pool_id'], r['worker_a'], r['worker_b']): r for r in design['labels']}
    events, growth, backgrounds, teams = [], [], [], []
    for panel in design['panels']:
        pid = panel['pool_id']
        p = out/'runtime/pools'/pid
        rows = read(p/'request_results.json.gz')['results']
        states = {s['team_id']: s['automatic'] for s in read(p/'states.json.gz')['states']}
        byid = {r['request_id']: r for r in rows}
        expected = {r['request_id'] for r in design['requests'] if r['pool_id'] == pid}
        assert set(byid) == expected and len(rows) == len(expected), 'missing_or_duplicate_results'
        def pair(a, b):
            return compare(a, b, states[a['team_id']], states[b['team_id']], fe)
        for event in (e for e in design['events'] if e['pool_id'] == pid):
            a, b = byid[event['request_a']], byid[event['request_b']]
            assert len(set(a['member_workers'].split('|')) ^ set(b['member_workers'].split('|'))) == 2
            events.append(dict(event, **{k:v for k,v in labels[(pid,event['worker_a'],event['worker_b'])].items() if k not in event}, **pair(a,b)))
        for w in panel['candidates']:
            for context in range(2):
                path = sorted([r for r in rows if r['entrant_worker_id'] == w and r['context'] == context], key=lambda r:r['k'])
                assert [r['k'] for r in path] == KS
                for a, b in zip(path, path[1:]):
                    if b['k'] != a['k']+1:
                        continue
                    growth.append(dict(pool_id=pid, building=panel['building'], difficulty=panel['difficulty'],
                                       worker=w, context=context, k_from=a['k'], k_to=b['k'],
                                       threshold_increased=(b['k']+1)//2 > (a['k']+1)//2, **pair(a,b)))
            for k in KS:
                a, b = [next(r for r in rows if r['entrant_worker_id']==w and r['context']==c and r['k']==k) for c in range(2)]
                backgrounds.append(dict(pool_id=pid, building=panel['building'], difficulty=panel['difficulty'], worker=w, k=k,
                                        turnover=len(set(a['member_workers'].split('|')) ^ set(b['member_workers'].split('|')))//2, **pair(a,b)))
        teams.extend(rows)
    d = pd.DataFrame(events)
    d.to_csv(out/'SWAPS.csv.gz', index=False)
    pd.DataFrame(growth).to_csv(out/'GROWTH.csv.gz', index=False)
    pd.DataFrame(backgrounds).to_csv(out/'BACKGROUNDS.csv.gz', index=False)
    pd.DataFrame(teams).to_csv(out/'TEAM_RESULTS.csv.gz', index=False)
    # Same image, context and k: average available same/cross edges among the same random triple.
    results = []
    for method in ('Q', 'QT', 'QTD'):
        for k, g in d[d[method+'_same'].notna()].groupby('k'):
            for metric in ('stable_main', 'stable_strict', 'stable_wide', 'abs_B8L2_change'):
                grouped = g.groupby(['building','pool_id','context',method+'_same'])[metric]
                values = grouped.agg(lambda x: x.mean() if x.notna().all() else np.nan)
                piv = values.unstack(method+'_same')
                if True not in piv or False not in piv:
                    continue
                piv = piv.rename(columns={True:'near',False:'far'}).reset_index()
                results.append(dict(method=method, k=int(k), metric=metric, **paired_summary(piv,'near','far')))
    pd.DataFrame(results, columns=None if results else ['method','k','metric','buildings','images','paired_rows','near','far','delta','low','high','image_delta','experiment_delta']).to_csv(out/'CLASS_BASELINES.csv', index=False, encoding='utf-8-sig')
    summary = dict(status='computed_finite_panel', requests=len(teams), unique_teams=len({r['team_id'] for r in teams}),
                   swap_events=len(d), growth_events=len(growth), background_events=len(backgrounds),
                   images=d.pool_id.nunique(), buildings=d.building.nunique(),
                   all_requests_present=True, quality_available=sum(r['B8L2'] is not None for r in teams),
                   complete=sum(r['complete_evaluable'] for r in teams),
                   history_supported_pairs=sum(r['history_9'] is not None for r in design['labels']),
                   candidate_pairs=len(design['labels']), no_new_personnel_classes=True,
                   limits='One random candidate triple per selected image, two backgrounds; one registered layer n>=27 only; retrospective, not blind or causal.',
                   layer=read(out/'REGISTRATION.json').get('layer','ordinary_manual'))
    save(out/'COVERAGE.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def verify(base, out):
    """Read original comparison definitions without importing its POSIX writer."""
    source, fe = runtime(base)
    original = source/'fusion/compare_fusions.py'
    tree = ast.parse(original.read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
             and n.name in {'value','difference','ring_key','ComparisonPool'}]
    ns = dict(np=np, math=math, combinations=itertools.combinations, footprint=fe.footprint,
              structural_distance=fe.structural_distance, OUT=out/'runtime', read=fe.read, clean=fe.clean,
              META=('pool_id','image','image_id','building','condition','layer','difficulty','reference_id','reference_version'))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(original), 'exec'), ns)
    pools = {p['pool_id']:p for p in read(source/'fusion/INPUT_SNAPSHOT.json.gz')['images']}
    design = read(out/'DESIGN.json.gz')
    fields = {k:k for k in ['B8L2_change','D10_change','floor_jaccard_difference','node_count_difference',
                            'structure_bound_cyclic_deg','changed_coidentity_pairs']}
    fields.update(selected_shared_change='selected_shared_observation_difference', edge_change='edge_relation_jaccard_difference',
                  stable_main='joint_stable_main', stable_strict='joint_stable_strict', stable_wide='joint_stable_wide')
    checked, maxdiff = 0, 0.
    # Cover all selected pools, failures and every registered k, using their first random pair.
    for panel in design['panels']:
        cp = ns['ComparisonPool'](pools[panel['pool_id']])
        for e in design['events']:
            if e['pool_id'] != panel['pool_id'] or e['worker_a'] != panel['candidates'][0] or e['worker_b'] != panel['candidates'][1]:
                continue
            a, b = cp.byid[e['request_a']], cp.byid[e['request_b']]
            new = compare(a,b,cp.states[a['team_id']],cp.states[b['team_id']],fe)
            old = cp.pair(e['request_a'],e['request_b'])
            for nk, ok in fields.items():
                x, y = new[nk], old[ok]
                if x is None or y is None:
                    assert x is y, (nk,x,y)
                else:
                    delta = abs(float(x)-float(y))
                    assert delta < 1e-10, (nk,x,y)
                    maxdiff = max(delta,maxdiff)
            checked += 1
    receipt = dict(events=checked, pools=len(design['panels']), fields=fields,
                   max_numeric_difference=maxdiff, passed=True,
                   method='read-only original comparison definitions excluding unused writer; no edits or fcntl replacement',
                   original_source_unchanged=True, python=sys.version,
                   numpy=np.__version__, pandas=pd.__version__)
    save(out/'COMPARATOR_PARITY.json',receipt)
    print(json.dumps(receipt,indent=2),flush=True)


def mechanisms(base, out):
    runtime(base)
    swaps = pd.read_csv(out/'SWAPS.csv.gz')
    growth = pd.read_csv(out/'GROWTH.csv.gz')
    outputs = []
    for df in (swaps, growth):
        df['unstable'] = 1-df.stable_main.astype(float)
        df['node_changed'] = df.node_count_difference.gt(0).where(df.node_count_difference.notna())
        df['identity_changed'] = df.changed_coidentity_pairs.gt(0).where(df.changed_coidentity_pairs.notna())
    for metric in ('unstable','node_changed','identity_changed','abs_B8L2_change'):
        piv = growth.groupby(['building','pool_id','context','worker','threshold_increased'])[metric].agg(
            lambda x:x.mean() if x.notna().all() else np.nan).unstack('threshold_increased')
        piv = piv.rename(columns={False:'near',True:'far'}).reset_index()
        outputs.append(dict(comparison='growth_threshold_increase_minus_unchanged', metric=metric, **paired_summary(piv,'near','far')))
        piv = swaps.groupby(['building','pool_id','context','k','one_swap_can_flip'])[metric].agg(
            lambda x:x.mean() if x.notna().all() else np.nan).unstack('one_swap_can_flip')
        if False in piv and True in piv:
            piv = piv.rename(columns={False:'near',True:'far'}).reset_index()
            outputs.append(dict(comparison='vote_near_minus_clear_paired_images', metric=metric, **paired_summary(piv,'near','far')))
    pd.DataFrame(outputs).to_csv(out/'MECHANISM_SUMMARY.csv',index=False,encoding='utf-8-sig')
    # History near/far uses the same outgoing person and two alternatives in the random triple.
    paired, matched = [], []
    save(out/'Q_MATCHED_ANALYSIS_SPEC.json', dict(
        status='planned_Q_matched_sensitivity_on_existing_random_panel',
        design_unchanged=True, q_calibration='heldout-building historical Q',
        contrast='same outgoing anchor; one same-class and one cross-class entrant',
        constraint='abs(Q_same_entrant-Q_cross_entrant)<=3',
        target_point_count_matching=False, weights='same paired image/building aggregation',
        interpretation='incremental descriptive comparison, not causal proof or selection gain'))
    for (pid, context, k), g in swaps.groupby(['pool_id','context','k']):
        people = sorted(set(g.worker_a) | set(g.worker_b))
        for anchor in people:
            edges = g[g.worker_a.eq(anchor) | g.worker_b.eq(anchor)]
            for method in ('Q','QT','QTD'):
                h = edges.dropna(subset=[method+'_same'])
                if len(h)!=2 or h[method+'_same'].nunique()!=2:
                    continue
                near = h[h[method+'_same'].eq(True)].iloc[0]
                far = h[h[method+'_same'].eq(False)].iloc[0]
                qnear, qfar = alternative_q(near,anchor), alternative_q(far,anchor)
                if not np.isfinite([qnear,qfar]).all() or abs(qnear-qfar)>3:
                    continue
                for metric in ('stable_main','abs_B8L2_change'):
                    matched.append(dict(building=near.building,pool_id=pid,context=context,k=k,anchor=anchor,
                                        method=method,metric=metric,near=near[metric],far=far[metric],
                                        entrant_Q_gap=abs(qnear-qfar)))
            for cut in (9,12):
                h = edges.dropna(subset=[f'history_{cut}']).sort_values(f'history_{cut}')
                if len(h)!=2 or h.iloc[1][f'history_{cut}']-h.iloc[0][f'history_{cut}'] < .2:
                    continue
                far, near = h.iloc[0], h.iloc[1]
                for metric in ('stable_main','abs_B8L2_change'):
                    paired.append(dict(building=near.building,pool_id=pid,context=context,k=k,anchor=anchor,
                                       cut=cut,metric=metric,near=near[metric],far=far[metric]))
    hp = pd.DataFrame(paired)
    hp.to_csv(out/'HISTORY_PAIRED.csv.gz',index=False)
    rows = [dict(cut=int(cut), k=int(k), metric=metric, **paired_summary(g,'near','far'))
            for (cut,k,metric), g in hp.groupby(['cut','k','metric'])] if len(hp) else []
    pd.DataFrame(rows).to_csv(out/'HISTORY_SUMMARY.csv',index=False,encoding='utf-8-sig')
    mq = pd.DataFrame(matched)
    mq.to_csv(out/'Q_MATCHED_PAIRED.csv.gz',index=False)
    rows = [dict(method=method,k=int(k),metric=metric,**paired_summary(g,'near','far'))
            for (method,k,metric),g in mq.groupby(['method','k','metric'])] if len(mq) else []
    pd.DataFrame(rows).to_csv(out/'Q_MATCHED_SUMMARY.csv',index=False,encoding='utf-8-sig')
    # Test a single label-pair on the same image across both backgrounds; no selection by outcomes.
    chains = swaps.groupby(['building','pool_id','context','worker_a','worker_b']).agg(
        nodes=('k','nunique'), all12_stable=('stable_main','all'), any_incomplete=('both_complete', lambda x:not x.all()),
        max_abs_Q=('abs_B8L2_change',lambda x:x.max() if x.notna().all() else np.nan),
        Q_same=('Q_same','first'), QT_same=('QT_same','first'), QTD_same=('QTD_same','first')).reset_index()
    assert chains.nodes.eq(len(KS)).all()
    chains.to_csv(out/'CHAINS.csv',index=False,encoding='utf-8-sig')
    class_chains = []
    for method in ('Q','QT','QTD'):
        for metric in ('all12_stable','max_abs_Q'):
            g = chains[chains[method+'_same'].notna()]
            piv = g.groupby(['building','pool_id','context',method+'_same'])[metric].agg(
                lambda x:x.mean() if x.notna().all() else np.nan).unstack(method+'_same')
            if True in piv and False in piv:
                piv = piv.rename(columns={True:'near',False:'far'}).reset_index()
                class_chains.append(dict(method=method,metric=metric,**paired_summary(piv,'near','far')))
    pd.DataFrame(class_chains).to_csv(out/'CLASS_CHAIN_SUMMARY.csv',index=False,encoding='utf-8-sig')
    transfer = chains.pivot(index=['building','pool_id','worker_a','worker_b'],columns='context',values='all12_stable')
    transfer.columns=['background0_stable','background1_stable']
    transfer.reset_index().to_csv(out/'BACKGROUND_TRANSFER.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(outputs).to_string(index=False),flush=True)


def mechanism_flags(swaps):
    d = swaps.copy()
    d['identity_repartition'] = d.changed_coidentity_pairs.gt(0).where(d.changed_coidentity_pairs.notna())
    d['node_count_change'] = d.node_count_difference.gt(0).where(d.node_count_difference.notna())
    d['selected_membership_change'] = d.selected_shared_change.gt(0).where(d.selected_shared_change.notna())
    known = d.identity_repartition.notna() & d.node_count_change.notna()
    d['identity_and_node_change'] = (d.identity_repartition.eq(True) & d.node_count_change.eq(True)).where(known)
    return d


def mechanism_followup(base, out):
    _, fe = runtime(base)
    assert (out/'MECHANISM_FOLLOWUP_SPEC.json').exists()
    teams = pd.read_csv(out/'TEAM_RESULTS.csv.gz').set_index('request_id')
    assert teams.index.is_unique
    fields = ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
    valid = teams[fields+['B8L2']].notna().all(axis=1)
    no_direction = pd.Series(np.nan, index=teams.index)
    with fe.scoring_engine(fe.ENGINE/'measurement_engine.zip', fe.ENGINE/'working_models.py') as (_, models):
        t = teams.loc[valid]
        no_direction.loc[valid] = models.score(t.iou_2d, t.S_bottom_deg, 0., t.Hmean, t.Hcenter, models.MODELS['B8L2'])
    d = mechanism_flags(pd.read_csv(out/'SWAPS.csv.gz'))
    d['direction_zero_gap'] = abs(d.request_b.map(no_direction)-d.request_a.map(no_direction))
    d['direction_gap_amplification'] = d.abs_B8L2_change-d.direction_zero_gap
    metrics = ['identity_repartition','node_count_change','selected_membership_change',
               'identity_and_node_change','direction_gap_amplification']
    results, coverage, overall = [], [], []
    for k, g in d.groupby('k'):
        for metric in metrics:
            known = g.dropna(subset=[metric]).copy()
            im = known.groupby(['building','pool_id'])[metric].mean()
            overall.append(dict(k=k,metric=metric,events=len(g),known_events=len(known),
                images=known.pool_id.nunique(),buildings=known.building.nunique(),
                event_mean=float(known[metric].mean()),building_mean=float(im.groupby('building').mean().mean())))
        for method in ('Q','QT','QTD'):
            h = g[g[method+'_same'].notna()]
            for metric in metrics:
                values = h.groupby(['building','pool_id','context',method+'_same'])[metric].agg(
                    lambda x: x.astype(float).mean() if x.notna().all() else np.nan)
                piv = values.unstack(method+'_same')
                if True in piv and False in piv:
                    piv = piv.rename(columns={True:'near',False:'far'}).reset_index()
                    results.append(dict(method=method,k=k,metric=metric,**paired_summary(piv,'near','far')))
                for same, q in h.groupby(method+'_same'):
                    coverage.append(dict(method=method,k=k,same=bool(same),metric=metric,
                        events=len(q),known_events=int(q[metric].notna().sum()),images=q.pool_id.nunique(),buildings=q.building.nunique()))
    cols = ['event_id','pool_id','building','context','k','worker_a','worker_b','Q_same','QT_same','QTD_same','both_complete','direction_zero_gap']+metrics
    d[cols].to_csv(out/'MECHANISM_EVENTS.csv.gz',index=False)
    pd.DataFrame(results, columns=None if results else ['method','k','metric','buildings','images','paired_rows','near','far','delta','low','high','image_delta','experiment_delta']).to_csv(out/'MECHANISM_CLASS_SUMMARY.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(coverage, columns=None if coverage else ['method','k','same','metric','events','known_events','images','buildings']).to_csv(out/'MECHANISM_CLASS_COVERAGE.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(overall).to_csv(out/'MECHANISM_OVERALL.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(overall).query('k==25').to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['register', 'run', 'summarize', 'verify', 'mechanisms', 'mechanism_followup'])
    parser.add_argument('--runtime', type=Path, default=RUNTIME)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--jobs', type=int, default=3)
    parser.add_argument('--layer', choices=['ordinary_manual','doorway_manual','ordinary_semi'], default='ordinary_manual')
    args = parser.parse_args()
    if args.stage == 'run':
        run(args.runtime, args.out, args.jobs)
    elif args.stage == 'register':
        register(args.runtime, args.out, args.layer)
    else:
        globals()[args.stage](args.runtime, args.out)
