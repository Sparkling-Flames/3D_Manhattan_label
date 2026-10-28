"""重放已登记同团队，恢复未保存的完整票账；不评分、不改规则。"""
from pathlib import Path
import argparse
import gzip
import json
import sys
import time
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
RELEASE = OUT.parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT))
from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse, WORKING_GAP
from tools.thesis_main.analysis.wall_consensus_v1_process_20261017 import cached_matching
from tools.thesis_main.analysis.wall_consensus_population_20261014 import compact


def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)): return [clean(v) for v in x]
    if isinstance(x, np.generic): return clean(x.item())
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all-eight', action='store_true')
    ap.add_argument('--all-events', action='store_true')
    args = ap.parse_args()
    image_results = pd.read_csv(OUT/'SAME_ABC_IMAGE_RESULTS.csv')
    selected_images = set(image_results.loc[image_results.B8L2_gap.lt(0), 'image'])
    selected_images.add('jh4fc5c5qoQ-10')
    if not args.all_eight: selected_images = {'jh4fc5c5qoQ-04'}
    selected_ids = set(pd.read_csv(OUT/'SAME_ABC_RFUSE_EVENTS.csv.gz', usecols=['event_id']).event_id)
    events = pd.read_csv(RELEASE/'current_exchange_results/confirm/EVENT_METRICS.csv.gz', low_memory=False)
    events = events[events.event_id.isin(selected_ids) & events.image.isin(selected_images)]
    first_ids = set(events.groupby('image', sort=False).head(1).event_id)
    chosen = events if args.all_events else events[events.event_id.isin(first_ids)]
    assert chosen.image.nunique() == len(selected_images)
    pools = {p['pool_id']: p for p in json.loads((RELEASE/'pools/INPUT_SNAPSHOT.json').read_text(encoding='utf8'))['images']}
    wanted = {r[f'{arm}_team_key'] for r in chosen.to_dict('records') for arm in 'ABC'}
    saved = {}
    paths = [p for pid in chosen.pool_id.unique() for p in (RELEASE/'current_exchange_endpoints'/pid).glob('*.jsonl.gz')]
    paths.append(RELEASE/'current_exchange_endpoints/REUSED_ENDPOINTS.jsonl.gz')
    for path in paths:
        if not path.exists(): continue
        with gzip.open(path, 'rt', encoding='utf8') as f:
            for line in f:
                row = json.loads(line)
                if row['team_key'] in wanted: saved[row['team_key']] = row
        if len(saved) == len(wanted): break
    assert set(saved) == wanted, wanted-set(saved)
    states, checks, groups = [], [], []
    replay_cache = {}
    start = time.monotonic()
    with cached_matching():
        for event in chosen.to_dict('records'):
            pool = pools[event['pool_id']]
            by_worker = {r['worker_id']: r for r in pool['records']}
            for arm in 'ABC':
                old = saved[event[f'{arm}_team_key']]
                records = [by_worker[w] for w in sorted(old['member_workers'])]
                if old['team_key'] not in replay_cache:
                    replay_cache[old['team_key']] = clean(compact(fuse(records, gap=WORKING_GAP)['automatic']))
                state = replay_cache[old['team_key']]
                members_match = {m['id'] for g in state['identity_groups'] for m in g['members']} == {r['id'] for r in records}
                same_candidate = state['candidate'] == old['geometry']
                same_without_footprint = ({k:v for k,v in state['candidate'].items() if k!='footprint'} ==
                                          {k:v for k,v in old['geometry'].items() if k!='footprint'})
                a, b = state['candidate'].get('footprint'), old['geometry'].get('footprint')
                footprint_max_abs_delta = (0. if a is None and b is None else
                                          float(np.max(np.abs(np.asarray(a)-np.asarray(b)))))
                old_supports = old['node_supports']
                old_support_encoding = 'pipe_separated_string' if isinstance(old_supports, str) else 'list'
                if isinstance(old_supports, str): old_supports = [int(x) for x in old_supports.split('|')]
                same_supports = [n['support'] for n in state['node_consensus']['nodes']] == old_supports
                assert state['n'] == old['k'] == 18 and state['minimum_support'] == old['minimum_support'] == 9
                assert members_match and same_supports and same_without_footprint and footprint_max_abs_delta < 1e-12, (
                    event['image'], arm, members_match, same_supports, same_without_footprint, footprint_max_abs_delta)
                base = dict(image=event['image'], event_id=event['event_id'], arm=arm, team_key=old['team_key'],
                            first_registered_event=event['event_id'] in first_ids)
                checks.append(dict(base, exact_candidate_match=same_candidate, selected_supports_match=same_supports,
                    exact_points_order_state_match=same_without_footprint,
                    footprint_max_abs_delta=footprint_max_abs_delta,
                    saved_node_supports_encoding=old_support_encoding,
                    member_records_match=members_match, n=state['n'], threshold=state['minimum_support'],
                    candidate_nodes=len(state['candidate'].get('feature_ids', [])),
                    saved_Q=old.get('B8L2'), saved_D10=old.get('D10'), saved_iou_2d=old.get('iou_2d'),
                    saved_dir=old.get('dir'), order_status=state['candidate'].get('order_status'),
                    geometry_status=state['candidate'].get('geometry_status')))
                states.append(dict(base, full_state=state))
                selected_node_ids = {n['feature_id'] for n in state['node_consensus']['nodes']}
                candidate_ids = set(state['candidate'].get('feature_ids', []))
                for group in state['identity_groups']:
                    groups.append(dict(base, feature_id=group['feature_id'], support=group['support'],
                        selected=group['selected'], in_node_consensus=group['feature_id'] in selected_node_ids,
                        in_candidate=group['feature_id'] in candidate_ids,
                        votes_to_threshold=state['minimum_support']-group['support'],
                        center_json=json.dumps(group.get('center'), ensure_ascii=False),
                        member_keys='|'.join(str(m['id'])+':'+str(m['pair_index']) for m in group['members']),
                        workers='|'.join(str(m['worker']) for m in group['members'])))
            print(event['image'], event['event_id'], 'ABC points/order/state/support match', flush=True)
    with gzip.open(OUT/'VOTE_REPLAY_EXACT_STATES.json.gz','wt',encoding='utf8') as f:
        json.dump(states, f, ensure_ascii=False, allow_nan=False)
    pd.DataFrame(checks).to_csv(OUT/'VOTE_REPLAY_CHECKS.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(groups).to_csv(OUT/'VOTE_REPLAY_GROUPS.csv', index=False, encoding='utf-8-sig')
    receipt = dict(images=chosen.image.nunique(), events=len(chosen), endpoint_occurrences=len(checks),
        existing_unique_teams_replayed=len(replay_cache), first_registered_events=len(first_ids),
        new_experimental_teams=0, scoring_calls=0, gap=WORKING_GAP, threshold=9,
        all_exact_candidate_matches=all(r['exact_candidate_match'] for r in checks),
        exact_candidate_matches=sum(r['exact_candidate_match'] for r in checks),
        all_exact_points_order_state_support_matches=all(r['exact_points_order_state_match'] and r['selected_supports_match'] for r in checks),
        footprint_max_abs_delta=max(r['footprint_max_abs_delta'] for r in checks),
        elapsed_seconds=time.monotonic()-start)
    (OUT/'VOTE_REPLAY_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2),encoding='utf8')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__': main()
