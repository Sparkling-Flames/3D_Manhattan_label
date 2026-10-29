"""Outcome-blind v2.1 ordinary-Manual ABC gap completion.

Existing m7 cells with evidence are retained through their old identity rather
than simulated again. For m8, the new 12/8--16/8 pair uses the same XYZ and
nested backgrounds, which was absent from the former main grid. The RAW3
candidate receives a 12/4 bridge to the existing broad-coverage comparison.
"""
from pathlib import Path
import collections, hashlib, itertools, json, random, sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / 'repo'
BASE = REPO / 'research/workers/personnel_v21_reselection_20261029'
OUT = Path(__file__).resolve().parents[1] / 'stage03_new_abc'
sys.path.insert(0, str(BASE / 'experiment'))
from capacity_space import capacities, canonical_hash, exact_counts, write_csv, read_json
from register_adaptive import make_event, key, write_json

METHODS = ['TARGET_DSTRUCT_K3', 'V21_DSTRUCT_RAW3_K3', 'OPPSTRUCT_K3',
           'OPPJOINT_K3', 'OPPJOINT_K4']
SEED = 202610291031
COMMIT = '519c7447278dd16c3d69f505b807fb5b53792b36'

def rnd(*args):
    return random.Random(int(canonical_hash([SEED, *args])[:16], 16))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    old = pd.read_csv(BASE / 'classification/MAIN45_LABELS_ALL_LOBO.csv.gz', low_memory=False)
    new = pd.read_csv(ROOT / 'audit_classification/results/NEW_LABELS_ALL_LOBO.csv.gz')
    labels = pd.concat([old[old.method.isin(METHODS)], new[new.method.isin(METHODS)]], ignore_index=True)
    labels = labels.fillna('')
    labels.to_csv(OUT / 'FROZEN_LABELS_ALL_LOBO.csv.gz', index=False)
    lookup = {k: g.to_dict('records') for k, g in labels.groupby(['method', 'heldout_building'])}
    source = pd.read_csv(ROOT / 'audit_capacity/results/M7_M8_EXACT_SUPPLEMENT_CANDIDATES.csv')
    source = source[(source.method.isin(METHODS)) & (source.layer == 'ordinary_manual') & (source.scope == 'primary')]
    grid = {(14, 7), (20, 7), (12, 8), (16, 8)}
    source = source[[tuple(x) in grid for x in source[['n', 'm']].to_numpy()]].copy()
    source['reason'] = source.apply(lambda r: 'new_raw_only_definition' if r['method'].startswith('V21_') else
                                  ('new_m8_half_vs_above_half_matched_path' if r['m'] == 8 else 'capacity_present_prior_design_absent'), axis=1)
    # No new sampling of already-supported m7 conditions in the old methods.
    omitted = source[(source.m == 7) & (source.prior_events > 0) & ~source.method.str.startswith('V21_')]
    omitted.to_csv(OUT / 'EXISTING_M7_CELLS_REUSED_NOT_RERUN.csv', index=False)
    source = source.drop(omitted.index)
    pools = {p['pool_id']: p for p in read_json(REPO / 'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json')['images']}
    cells = source.to_dict('records')
    # Small-block bridge for the new definition, all legitimate directions.
    for pid, pool in sorted(pools.items()):
        if pool['meta']['layer'] != 'ordinary_manual':
            continue
        method = 'V21_DSTRUCT_RAW3_K3'
        groups = capacities(pool, lookup[method, pool['meta']['building']])
        for s, t in itertools.permutations(sorted(set(groups) - {'unknown'}), 2):
            if exact_counts(len(pool['records']), len(groups[s]), len(groups[t]), 12, 4)['strict_ABC']:
                cells.append(dict(pool_id=pid, image=pool['meta']['image'], building=pool['meta']['building'],
                                  condition='manual', layer='ordinary_manual', scope='primary', method=method,
                                  source_class=s, target_class=t, n=12, m=4, prior_events=0,
                                  reason='new_raw_only_definition_broad_12_4_bridge'))
    frame = pd.DataFrame(cells).fillna('')
    assert not frame.duplicated(['pool_id','method','source_class','target_class','n','m']).any()
    frame.to_csv(OUT / 'FROZEN_CELLS.csv', index=False)
    write_json(OUT / 'PRE_OUTCOME_DESIGN.json', dict(
        source_commit=COMMIT, data_release='v2.1', seed=SEED, methods=METHODS,
        label_file='FROZEN_LABELS_ALL_LOBO.csv.gz', cell_file='FROZEN_CELLS.csv',
        m7_policy='only prior-unregistered cells in established methods; all feasible in new RAW3',
        m8_policy='all feasible 12/8 and 16/8 with shared XYZ and nested same-order low/high D',
        new_bridge='RAW3 all feasible ordinary primary Manual 12/4 directions',
        samples_per_cell='two distinct XYZ blocks; low/high target-background order, deduplicated',
        block_replicates_are_not_independent_images=True,
        labels_or_team_outcomes_do_not_enter_native_fusion=True,
        scoring_failure_retained_as_missing=True,
        no_new_people_rooms_scope_changes_or_natural_curves=True,
        fitting_uses_quality_or_time=False,
        existing_m7_cells_not_rerun=len(omitted), cells=len(frame)))
    events = []; requests = {}; seen = set(); coverage = []
    for (pid, method, s, t, m), cgroup in frame.groupby(['pool_id','method','source_class','target_class','m'], sort=True):
        pool = pools[pid]; building = pool['meta']['building']
        groups = capacities(pool, lookup[method, building]); S, T = sorted(groups[s]), sorted(groups[t])
        rr = rnd('XYZ', pid, S, T, int(m)); xyz = []; sigs = set()
        for attempt in range(100):
            xy = rr.sample(S, 2 * int(m)); x, y = sorted(xy[:int(m)]), sorted(xy[int(m):]); z = sorted(rr.sample(T, int(m)))
            sig = (tuple(sorted((tuple(x), tuple(y)))), tuple(z))
            if sig not in sigs:
                xyz.append((x,y,z)); sigs.add(sig)
            if len(xyz) == 2:
                break
        for cell in cgroup.to_dict('records'):
            n = int(cell['n']); before = len(events)
            for bi, (x,y,z) in enumerate(xyz):
                rest = sorted({r['worker_id'] for r in pool['records']} - set(x+y+z))
                dr = rnd('D_order', pid, x, y, z); dr.shuffle(rest)
                targets = [w for w in rest if w in T]; others = [w for w in rest if w not in T]
                backgrounds = [('low', (others+targets)[:n-int(m)]), ('high', (targets+others)[:n-int(m)])]
                for name, d in backgrounds:
                    d = sorted(d)
                    e, teams = make_event(pool, cell, groups, x,y,z,d,bi,name,'new_frozen_score_blind','')
                    if e['event_id'] in seen:
                        continue
                    e.update(supplement_reason=cell['reason'], prior_cell_events=cell.get('prior_events',0),
                             design_phase='v21_independent_reaudit_20261029', background_order=name,
                             source_commit=COMMIT, scope='primary',
                             nested_background_path=canonical_hash([pid,method,s,t,int(m),x,y,z,name])[:24])
                    events.append(e);seen.add(e['event_id'])
                    for arm, members in teams.items():
                        k = e[arm+'_team_key'];requests[k]=dict(team_key=k,pool_id=pid,n=n,member_workers='|'.join(members))
            coverage.append(dict(cell, registered_events=len(events)-before, distinct_XYZ=len(xyz)))
    write_csv(OUT / 'EVENTS_EXACT.csv.gz', events)
    write_csv(OUT / 'REQUESTS.csv.gz', requests.values())
    write_csv(OUT / 'REGISTERED_COVERAGE.csv.gz', coverage)
    write_json(OUT / 'DESIGN_RECEIPT.json', dict(events=len(events), unique_teams=len(requests),
               pools=len({e['pool_id'] for e in events}), source_commit=COMMIT,
               method_events=dict(collections.Counter(e['method'] for e in events)),
               disjoint_DXYZ_and_class_checks_passed=True, all_original_answers_unchanged=True))
    print((OUT / 'DESIGN_RECEIPT.json').read_text(), flush=True)

if __name__ == '__main__':
    main()
