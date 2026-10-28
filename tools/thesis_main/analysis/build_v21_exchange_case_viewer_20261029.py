"""Export saved current-label ABC examples for the offline geometry viewer."""
import gzip
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / 'research/data/releases/v2.1'
VIEWER = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'


def build():
    summary = pd.read_csv(RELEASE / 'current_exchange_results/confirm/combined/summary/POOL_DIRECTION_SUMMARY.csv.gz')
    selected = summary[(summary.method == 'DSTRUCT_K3') & (summary.n == 18) & (summary.m == 7)
                       & (summary.phase == 'selection_heldout_building')
                       & summary.source_largest_class.eq(True) & summary.target_highest_turn.eq(True)].copy()
    assert len(selected) == 33 and selected.image.is_unique
    chosen = pd.concat([selected[selected.B8L2_gap < 0], selected[selected.image == 'jh4fc5c5qoQ-10']])
    assert len(chosen) == 8
    events = pd.read_csv(RELEASE / 'current_exchange_design/design/confirm/EVENTS_EXACT.csv.gz')
    replay_dir = RELEASE / 'rfuse_exception_diagnosis_20261029'
    receipt = json.loads((replay_dir / 'VOTE_REPLAY_RECEIPT.json').read_text(encoding='utf8'))
    assert receipt['all_exact_points_order_state_support_matches'] and receipt['existing_unique_teams_replayed'] == 213
    assert receipt['footprint_max_abs_delta'] <= 1e-12
    with gzip.open(replay_dir / 'VOTE_REPLAY_EXACT_STATES.json.gz', 'rt', encoding='utf8') as f:
        states = {(r['event_id'], r['team_key']): r for r in json.load(f)}
    checks = pd.read_csv(replay_dir / 'VOTE_REPLAY_CHECKS.csv')
    assert len(states) == len(checks) == 213
    assert checks[['exact_points_order_state_match', 'selected_supports_match', 'member_records_match']].eq(True).all().all()
    links = pd.read_csv(replay_dir / 'VOTE_GROUP_COMMON_D_LINKS.csv')
    b_links = links[(links.event_id == '84320bad6f9ea2b352a805f2') & (links.other_arm == 'B')]
    for feature, count in [('node_003', 5), ('node_004', 6), ('node_005', 7)]:
        link = b_links[(b_links.A_feature == feature) & (b_links.other_feature == feature)]
        assert len(link) == 1 and int(link.iloc[0].common_D_observations) == count
        assert bool(link.iloc[0].exact_same_D_signature)
    focus_links = links[(links.event_id == '84320bad6f9ea2b352a805f2') & (links.other_arm == 'C')]
    for source, dest, n, exact in [('node_003', 'node_003', 5, True), ('node_004', 'node_004', 6, True),
                                    ('node_005', 'node_005', 2, False), ('node_005', 'node_011', 5, False)]:
        found_link = focus_links[(focus_links.A_feature == source) & (focus_links.other_feature == dest)]
        assert len(found_link) == 1 and int(found_link.iloc[0].common_D_observations) == n
        assert bool(found_link.iloc[0].exact_same_D_signature) == exact
    with (RELEASE / 'pools/INPUT_SNAPSHOT.json').open(encoding='utf8') as f:
        pools = {p['pool_id']: p for p in json.load(f)['images']}
    images = {}
    for path in (VIEWER / 'v2-resources/images').glob('*.js'):
        text = path.read_text(encoding='utf8')
        image = json.loads(text[text.index('= ') + 2:-2])
        if image['image_code'] in set(chosen.image):
            images[image['image_code']] = image
    cases = []
    for row in chosen.itertuples():
        q = events[(events.pool_id == row.pool_id) & (events.method == row.method) & (events.n == 18)
                   & (events.m == 7) & (events.source_class == row.source_class)
                   & (events.target_class == row.target_class) & (events.phase == row.phase)]
        assert not q.empty
        event = q.iloc[0]
        image = images[row.image]
        image['annotations'] = [a for a in image['annotations'] if a['condition'] == 'manual']
        wanted = {event[f'{a}_team_key'] for a in 'ABC'}
        found = {}
        paths = list((RELEASE / 'current_exchange_endpoints' / row.pool_id).glob('*.jsonl.gz'))
        paths.append(RELEASE / 'current_exchange_endpoints/REUSED_ENDPOINTS.jsonl.gz')
        for path in paths:
            with gzip.open(path, 'rt', encoding='utf8') as f:
                for line in f:
                    record = json.loads(line)
                    if record.get('team_key') in wanted:
                        found[record['team_key']] = record
            if len(found) == 3:
                break
        assert len(found) == 3, (row.image, wanted - found.keys())
        teams = {}
        for arm in 'ABC':
            record = found[event[f'{arm}_team_key']]
            assert sorted(event[f'{arm}_members'].split('|')) == sorted(record['member_workers'])
            if isinstance(record['member_object_ids'], str):
                record['member_object_ids'] = record['member_object_ids'].split('|')
            if isinstance(record.get('node_supports'), str):
                record['node_supports'] = [int(value) for value in record['node_supports'].split('|')]
            assert len(record['member_object_ids']) == 18
            assert all(any(a['object_id'] == oid for a in image['annotations']) for oid in record['member_object_ids'])
            teams[arm] = {k: record.get(k) for k in ('team_key', 'member_workers', 'member_object_ids', 'B8L2',
                          'score_status', 'minimum_support', 'node_supports', 'geometry', 'reference_id')}
            state = states[(event.event_id, record['team_key'])]
            assert state['arm'] == arm and state['image'] == row.image
            full = state['full_state']
            assert full['n'] == 18 and full['minimum_support'] == record['minimum_support']
            annotations = {a['object_id']: a for a in image['annotations']}
            candidates = []
            review_groups = []
            for group in full['identity_groups']:
                review = event.event_id == '84320bad6f9ea2b352a805f2' and group['feature_id'] in (
                    {'node_003', 'node_004', 'node_005', 'node_011'} if arm == 'C' else {'node_003', 'node_004', 'node_005'})
                if group['selected'] and not review:
                    continue
                members = group['members']
                assert len({m['id'] for m in members}) == len({m['worker'] for m in members}) == group['support']
                assert len(group['center']) == 2
                for member in members:
                    assert member['id'] in record['member_object_ids']
                    annotation = annotations[member['id']]
                    assert annotation['worker_id'] == member['worker']
                    index = member['source_pair_index']
                    assert annotation['points'][index * 2:index * 2 + 2] == member['points'], (row.image, arm, group['feature_id'], member['id'], index)
                group_record = dict(feature_id=group['feature_id'], support=group['support'], selected=group['selected'],
                    center=group['center'], members=[dict(object_id=m['id'], worker_id=m['worker'],
                    source_pair_index=m['source_pair_index'], points=m['points']) for m in members])
                if not group['selected']:
                    assert group['support'] < full['minimum_support']
                    candidates.append(group_record)
                if review:
                    group_record['D_support'] = sum(m['worker'] in event.D.split('|') for m in members)
                    group_record['replacement_support'] = group['support'] - group_record['D_support']
                    review_groups.append(group_record)
            teams[arm]['unselected_candidates'] = candidates
            teams[arm]['review_groups'] = review_groups
            if event.event_id == '84320bad6f9ea2b352a805f2':
                by_id = {g['feature_id']: g for g in review_groups}
                expected = {'A': {'node_003': (5, 3), 'node_004': (6, 4), 'node_005': (7, 5)},
                            'B': {'node_003': (5, 3), 'node_004': (6, 1), 'node_005': (7, 7)},
                            'C': {'node_003': (5, 6), 'node_004': (6, 6), 'node_005': (2, 6), 'node_011': (5, 7)}}
                assert {k: (v['D_support'], v['replacement_support']) for k, v in by_id.items()} == expected[arm]
        assert len({t['reference_id'] for t in teams.values()}) == 1
        reference = pools[row.pool_id]['reference']
        assert reference['target_id'] == teams['A']['reference_id']
        cases.append(dict(image=image, event_id=event.event_id, pool_id=row.pool_id,
                          **{k: event[k].split('|') for k in ('D', 'X', 'Y', 'Z')},
                          source_class=row.source_class, target_class=row.target_class, teams=teams,
                          reference={'points': reference['points_1024x512'], 'floor': reference['floor_xz_h'],
                                     'target_id': reference['target_id'], 'version': reference['reference_version']},
                          image_within=row.B8L2_within, image_cross=row.B8L2_cross, image_gap=row.B8L2_gap))
    target = VIEWER / 'v21-exchange-case-data.js'
    target.write_text('window.V21_EXCHANGE_CASES=' + json.dumps(cases, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')) + ';\n', encoding='utf8')
    print(f'{len(cases)} saved cases, {sum(len(c["teams"]) for c in cases)} exact endpoints')


if __name__ == '__main__':
    build()
