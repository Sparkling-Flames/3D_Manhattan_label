#!/usr/bin/env python3
"""Freeze finite, label-independent composition panels for admitted other spaces.

No fusion is performed. Small pools enumerate all subsets of size >=3.
Larger pools choose a reproducible panel independently of Q or class labels.
Exact deterministic team keys permit reuse of existing natural endpoints.
"""
import argparse
import hashlib
import itertools
import json
from math import comb
from pathlib import Path

import pandas as pd

SEED = 'v21-other-target-finite-panels-20261029'


def team_key(pool_id, members):
    # Same team identity as register_v21_exchange_20261028.py.
    payload = json.dumps(sorted(members), sort_keys=True, separators=(',', ':'))
    return pool_id + '__' + hashlib.sha256(payload.encode()).hexdigest()[:20]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    source = args.repo / 'research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json'
    pools = json.loads(source.read_text())['images']
    panels, links, teams, capacity = [], [], [], []
    for pool in pools:
        m = pool['meta']; pid = m['pool_id']
        records = {r['worker_id']: r for r in pool['records']}
        workers = sorted(records)
        N = len(workers)
        order = sorted(workers, key=lambda w: hashlib.sha256((SEED + '|' + pid + '|' + w).encode()).hexdigest())
        variable = sorted(order[:min(N, 12)])
        sizes = list(range(3, N + 1)) if N <= 10 else [len(variable) // 2]
        planned = sum(comb(len(variable), n) for n in sizes)
        full = sum(comb(N, n) for n in range(3, N + 1))
        selected_n_full = sum(comb(N, n) for n in sizes)
        capacity.append(dict(
            pool_id=pid, image=m['image'], building=m['building'], condition=m['condition'],
            reference_id=m['reference_id'], pool_n=N, panel_workers='|'.join(variable),
            excluded_panel_workers='|'.join(sorted(set(workers)-set(variable))),
            panel_size=len(variable), team_sizes='|'.join(map(str, sizes)),
            planned_unique_teams=planned, all_pool_n_ge3_unique_teams=full,
            unrequested_all_n_ge3_unique_teams=full-planned,
            all_pool_teams_at_selected_n=selected_n_full,
            unrequested_teams_at_selected_n=selected_n_full-planned,
            all_selected_n_member_sets_enumerated=(planned == selected_n_full),
            all_n_ge3_member_sets_enumerated=(planned == full),
            label_and_quality_independent_seed=SEED,
            source='new_finite_panel_design_no_new_fusion_yet',
        ))
        for n in sizes:
            panel_id = pid + '__finite_v21__n' + str(n)
            panels.append(dict(
                panel_id=panel_id, pool_id=pid, image=m['image'], image_id=m['image_id'],
                building=m['building'], condition=m['condition'], n=n, background_workers='',
                variable_workers='|'.join(variable), source_domain='all_formal_other_target',
                reference_id=m['reference_id'], reference_version=m['reference_version'],
                difficulty=m['difficulty'], scope='other_admitted',
                expected_teams=comb(len(variable), n), variable_choose=n,
                member_variation_estimable=comb(len(variable), n) > 1,
            ))
            for selected in itertools.combinations(variable, n):
                key = team_key(pid, selected)
                links.append(dict(panel_id=panel_id, team_key=key, selected_variable_workers='|'.join(selected)))
                teams.append(dict(
                    team_key=key, pool_id=pid, image=m['image'], building=m['building'],
                    condition=m['condition'], n=n, k=n, member_workers='|'.join(selected),
                    member_object_ids='|'.join(records[w]['object_id'] for w in selected),
                    reference_id=m['reference_id'], reference_version=m['reference_version'],
                    request_origin='other_target_finite_composition_panel',
                ))
    frames = {'PANELS_USED.csv':pd.DataFrame(panels), 'PANEL_TEAMS.csv.gz':pd.DataFrame(links),
              'TEAM_REQUESTS.csv.gz':pd.DataFrame(teams), 'POOL_CAPACITY_PLAN.csv':pd.DataFrame(capacity)}
    assert frames['TEAM_REQUESTS.csv.gz'].team_key.is_unique
    assert len(frames['TEAM_REQUESTS.csv.gz']) == 8940
    for filename, df in frames.items():
        df.to_csv(args.out / filename, index=False)
    facts = dict(input_repository_path=str(source.relative_to(args.repo)),
                 input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                 seed=SEED, pools=len(pools), panels=len(panels), unique_teams=len(teams),
                 manual_requests=sum(r['condition']=='manual' for r in teams),
                 semi_requests=sum(r['condition']=='semi' for r in teams),
                 all_pool_n_ge3_unique_teams=sum(r['all_pool_n_ge3_unique_teams'] for r in capacity),
                 unrequested_all_pool_n_ge3_unique_teams=sum(r['unrequested_all_n_ge3_unique_teams'] for r in capacity),
                 new_fusions=0, status='finite_requests_frozen_pending_cache_match_and_needed_fusion',
                 existing_cache_directory='research/data/releases/v2.1/admitted_space_extension/new_space_natural256')
    (args.out/'PLAN.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(facts, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
