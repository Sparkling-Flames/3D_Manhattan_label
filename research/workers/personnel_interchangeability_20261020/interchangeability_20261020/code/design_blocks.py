"""Exact equal-n/equal-m class-block design on real frozen pools.

Every feasible (ordered class pair, integer n, integer m, background policy,
source policy) in the stated frame is counted. A deterministic stratified subset
is drawn; concrete workers/backgrounds are sampled, never called exhaustive.
Known fine-domain members form the replacement blocks; other workers may only
form an explicit outside_group background. No outcome enters request generation.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, json, math, random
from pathlib import Path
import pandas as pd
from design_history_panel import read, write, digest, team_key

OUTSIDE = 'outside_group'

def labels_from(paths):
    maps = {}
    for path in paths:
        frame = pd.read_csv(path)
        if 'known' in frame:
            frame = frame[frame.known.astype(str).str.lower().isin(['true','1','1.0'])]
        frame = frame[frame.class_id.notna()]
        for (mid, domain), df in frame.groupby(['method_id', 'domain']):
            mapping = dict(zip(df.worker_id, df.class_id.astype(str)))
            if (mid, domain) in maps:
                assert maps[mid, domain] == mapping
            maps[mid, domain] = mapping
    return maps

def counts(workers, mapping):
    return dict(sorted(collections.Counter(mapping.get(w, OUTSIDE) for w in workers).items()))

def applicable(pool, method):
    filt = method.get('pool_filter', {})
    meta = pool['meta']
    for key in ['layer', 'condition', 'difficulty', 'building', 'pool_id']:
        wanted = filt.get(key, filt.get(key + 's'))
        if wanted is not None and meta.get(key) not in ([wanted] if isinstance(wanted, str) else wanted):
            return False
    return True

def allowed_workers(pool, method):
    excluded = set(method.get('exclude_workers', []))
    allowed_origins = method.get('allowed_origins', ['new', 'v1'])
    return sorted(r['worker_id'] for r in pool['records']
                  if r['worker_id'] not in excluded and r['origin'] in allowed_origins)

def possible_source_counts(groups, origins, outgoing, incoming, m):
    on = sum(origins[w] == 'new' for w in groups[outgoing]); oo = len(groups[outgoing])-on
    inn = sum(origins[w] == 'new' for w in groups[incoming]); ino = len(groups[incoming])-inn
    return [t for t in range(m+1) if 2*t <= on and 2*(m-t) <= oo and t <= inn and m-t <= ino]

def select_blocks(groups, origins, outgoing, incoming, m, matching, rng):
    if matching == 'source_matched':
        ts = possible_source_counts(groups, origins, outgoing, incoming, m)
        if not ts:
            return None, 'no_equal_source_count'
        t = rng.choice(ts); blocks = [[], [], []]
        for origin, amount in [('new', t), ('v1', m-t)]:
            source = [w for w in groups[outgoing] if origins[w] == origin]
            selected = rng.sample(source, 2*amount)
            blocks[0].extend(selected[:amount]); blocks[1].extend(selected[amount:])
            blocks[2].extend(rng.sample([w for w in groups[incoming] if origins[w] == origin], amount))
    else:
        selected = rng.sample(groups[outgoing], 2*m)
        blocks = [selected[:m], selected[m:], rng.sample(groups[incoming], m)]
    return [sorted(x) for x in blocks], None

def choose_core(ws, reserved, mapping, outgoing, incoming, size, policy, rng):
    remain = [w for w in ws if w not in reserved]
    if len(remain) < size:
        return None
    if policy == 'random':
        return sorted(rng.sample(remain, size))
    priority = outgoing if policy == 'out_rich' else incoming if policy == 'in_rich' else OUTSIDE
    first = [w for w in remain if mapping.get(w, OUTSIDE) == priority]
    if len(first) >= size:
        return sorted(rng.sample(first, size))
    rest = [w for w in remain if w not in set(first)]
    return sorted(first + rng.sample(rest, size-len(first)))

def event_for(pool, method, mapping, candidate, seed, phase, rank, replicate=0):
    outgoing, incoming, n, m, background, matching = candidate
    mid, domain = method['method_id'], method['domain']
    context = method.get('context_id', 'primary')
    key = [seed, phase, mid, domain, context, pool['pool_id'], list(candidate), rank, replicate]
    rng = random.Random(int(digest(key)[:16], 16))
    excluded = set(method.get('exclude_workers', []))
    ws = allowed_workers(pool, method)
    origins = {r['worker_id']:r['origin'] for r in pool['records']}
    groups = {c:[w for w in ws if mapping.get(w) == c] for c in sorted(set(mapping.values()))}
    blocks, reason = select_blocks(groups, origins, outgoing, incoming, m, matching, rng)
    if reason:
        return None, reason
    core = choose_core(ws, set(sum(blocks, [])), mapping, outgoing, incoming, n-m, background, rng)
    if core is None:
        return None, 'core_capacity'
    arms = [sorted(core + b) for b in blocks]
    ca, cb, cc = [counts(x, mapping) for x in arms]
    assert ca == cb and ca != cc
    assert all(len(a) == len(set(a)) == n for a in arms)
    assert len(set(arms[0])-set(arms[1])) == len(set(arms[0])-set(arms[2])) == m
    assert set(arms[0]) & set(arms[1]) == set(arms[0]) & set(arms[2]) == set(core)
    source_vectors = [collections.Counter(origins[w] for w in b) for b in blocks]
    if matching == 'source_matched':
        assert source_vectors[0] == source_vectors[1] == source_vectors[2]
    e = dict(event_id='I20_' + digest(key)[:22], phase=phase, method_id=mid, domain=domain,
             family=method.get('family', 'unspecified'), context_id=context, pool_id=pool['pool_id'],
             building=pool['meta']['building'], image=pool['meta']['image'],
             difficulty=pool['meta']['difficulty'], layer=pool['meta']['layer'],
             condition=pool['meta']['condition'], reference_id=pool['meta']['reference_id'],
             n=n, k=n, m=m, outgoing_class=outgoing, incoming_class=incoming,
             background_policy=background, matching=matching,
             actual_source_match=source_vectors[0] == source_vectors[1] == source_vectors[2],
             core_workers=core, outgoing_workers=blocks[0], within_incoming=blocks[1],
             cross_incoming=blocks[2], A_counts=ca, B_counts=cb, C_counts=cc,
             core_counts=counts(core, mapping), changed_category_slots=m,
             pattern='single_class_block', outside_background_n=sum(w not in mapping for w in core),
             complete_turnover=m==n, direction=outgoing+'>'+incoming,
             excluded_workers=sorted(excluded), allowed_origins=method.get('allowed_origins', ['new','v1']),
             available_population_n=len(ws), replicate=replicate)
    for arm, workers in zip('ABC', arms):
        e[arm+'_workers'] = workers; e[arm+'_team_key'] = team_key(pool['pool_id'], workers)
    return e, None

def candidate_frame(pool, method, mapping):
    ws = allowed_workers(pool, method)
    origins = {r['worker_id']:r['origin'] for r in pool['records']}
    groups = {c:[w for w in ws if mapping.get(w) == c] for c in sorted(set(mapping.values()))}
    frame = []; excluded_counts = collections.Counter()
    directions = method.get('directions') or [(a,b) for a in groups for b in groups if a != b]
    bgs = method.get('background_policies', ['random','out_rich','in_rich'])
    policies = method.get('matching_policies', ['unrestricted','source_matched'])
    for out, inc in directions:
        if out not in groups or inc not in groups:
            excluded_counts['class_absent'] += 1; continue
        max_m = min(len(groups[out])//2, len(groups[inc]), len(ws)//3)
        if not max_m:
            excluded_counts['no_disjoint_block_capacity'] += 1
        for m in range(1, max_m+1):
            if method.get('m_values') is not None and m not in method['m_values']:
                continue
            same_source = bool(possible_source_counts(groups, origins, out, inc, m))
            for n in range(max(2,m), len(ws)-2*m+1):
                if n<method.get('min_n',2) or n>method.get('max_n',len(ws)):
                    continue
                if method.get('n_values') is not None and n not in method['n_values']:
                    continue
                for bg in bgs:
                    for matching in policies:
                        if matching == 'source_matched' and not same_source:
                            excluded_counts['source_count_capacity'] += 1; continue
                        frame.append((out, inc, n, m, bg, matching))
    return frame, dict(excluded_counts), {c:len(g) for c,g in groups.items()}

def stratified_sample(frame, quota, key):
    if len(frame) <= quota:
        return sorted(frame)
    rng = random.Random(int(digest(key)[:16], 16))
    # Give every ordered pair / matching policy priority before repeating them.
    # m=1 gets one quarter of a stratum's picks when supported; all other integer
    # m and n remain in the shuffled frame. This is not outcome stratification.
    strata = collections.defaultdict(list)
    for x in frame:
        strata[(x[0],x[1],x[5])].append(x)
    for values in strata.values():
        rng.shuffle(values)
        values.sort(key=lambda x: x[3] == 1)
    keys = list(strata); rng.shuffle(keys); selected = []
    while keys and len(selected) < quota:
        nextkeys = []
        for key in keys:
            if len(selected) >= quota:
                break
            values = strata[key]
            # Cycle auxiliary single-member comparison only every fourth pass.
            index = next((i for i,x in enumerate(values) if x[3] == 1), 0) if (len(selected)//max(1,len(strata)))%4 == 3 else 0
            selected.append(values.pop(index))
            if values:
                nextkeys.append(key)
        keys = nextkeys
    return selected

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot',type=Path,required=True); ap.add_argument('--split',type=Path,required=True)
    ap.add_argument('--labels',type=Path,action='append',required=True); ap.add_argument('--spec',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True); a = ap.parse_args()
    spec, split = read(a.spec), read(a.split); maps = labels_from(a.labels)
    phase = spec['phase']; bkey = 'validation_buildings' if phase == 'assessment' else phase+'_buildings'
    pools = [p for p in read(a.snapshot)['images'] if p['meta']['building'] in split[bkey]]
    requests = {}; events = []; ledger = []
    for method in spec['methods']:
        mid, domain = method['method_id'], method['domain']; mapping = maps[mid,domain]
        for pool in pools:
            if not applicable(pool, method):
                continue
            frame, exclusions, capacities = candidate_frame(pool, method, mapping)
            quota = method.get('events_per_pool', spec.get('events_per_pool', 24))
            selected = stratified_sample(frame, quota, [spec['seed'],phase,mid,domain,pool['pool_id']])
            accepted = []; failures = collections.Counter()
            for rank, candidate in enumerate(selected):
                for rep in range(method.get('replicates', 1)):
                    e, reason = event_for(pool,method,mapping,candidate,spec['seed'],phase,rank,rep)
                    if reason:
                        failures[reason] += 1; continue
                    events.append(e); accepted.append(e)
                    for arm in 'ABC':
                        tk = e[arm+'_team_key']; ws = e[arm+'_workers']
                        requests.setdefault(tk, dict(request_id=tk,pool_id=pool['pool_id'],k=e['n'],worker_ids=ws))
            ledger.append(dict(method_id=mid,domain=domain,pool_id=pool['pool_id'],class_capacities=capacities,
                finite_candidate_contexts=len(frame),selected_contexts=len(selected),accepted_events=len(accepted),
                all_finite_contexts_selected=len(frame)==len(selected),capacity_exclusions=exclusions,
                draw_failures=dict(failures),n_counts=dict(collections.Counter(e['n'] for e in accepted)),
                m_counts=dict(collections.Counter(e['m'] for e in accepted)),
                directions=dict(collections.Counter(e['direction'] for e in accepted)),
                source_policies=dict(collections.Counter(e['matching'] for e in accepted)),
                concrete_team_sampling='Seeded real workers; not exhaustive over possible members/cores'))
    output = dict(schema='interchangeability_block_requests_v1',spec=spec,
                  input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [a.snapshot,a.split,*a.labels,a.spec]},
                  requests=list(requests.values()),events=events,ledger=ledger)
    write(a.out,output)
    print(json.dumps(dict(events=len(events),unique_teams=len(requests),pools=len({e['pool_id'] for e in events}),
        buildings=len({e['building'] for e in events}),methods=len({(e['method_id'],e['domain']) for e in events}),
        n_nodes=sorted({e['n'] for e in events}),m_nodes=sorted({e['m'] for e in events}),
        full_turnover_events=sum(e['complete_turnover'] for e in events),
        multi_member_events=sum(e['m']>1 for e in events),
        finite_contexts=sum(r['finite_candidate_contexts'] for r in ledger)),ensure_ascii=False))

if __name__ == '__main__':
    main()
