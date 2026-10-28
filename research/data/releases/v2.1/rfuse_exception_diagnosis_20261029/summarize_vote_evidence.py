"""逐队票数及公共 D 观察的精确身份链接；不以队内编号跨队配对。"""
from pathlib import Path
import gzip
import json
import pandas as pd

OUT = Path(__file__).resolve().parent
states = json.load(gzip.open(OUT/'VOTE_REPLAY_EXACT_STATES.json.gz', 'rt', encoding='utf8'))
events = pd.read_csv(OUT/'SAME_ABC_RFUSE_EVENTS.csv.gz').drop_duplicates('event_id').set_index('event_id')
summaries, links, edges, block_supports = [], [], [], []
for row in states:
    s = row['full_state']; gs = s['identity_groups']; rd = s['ring_diagnostics']
    selected = [g for g in gs if g['selected']]
    discarded = [g for g in gs if not g['selected']]
    node_ids = {g['feature_id'] for g in s['node_consensus']['nodes']}
    candidate_ids = set(s['candidate'].get('feature_ids', []))
    base = {k: row[k] for k in ['image', 'event_id', 'arm', 'team_key', 'first_registered_event']}
    d_workers = set(events.loc[row['event_id'], 'D'].split('|'))
    for g in gs:
        workers = {m['worker'] for m in g['members']}
        assert len(workers)==len(g['members'])==g['support']
        d = workers & d_workers
        block_supports.append(dict(base,feature_id=g['feature_id'],support=g['support'],selected=g['selected'],
            D_support=len(d),replacement_support=len(workers-d),D_workers='|'.join(sorted(d)),
            replacement_workers='|'.join(sorted(workers-d)),center=json.dumps(g.get('center'))))
    summaries.append(dict(base, groups=len(gs), selected=len(selected), unselected=len(discarded),
        unselected_support8=sum(g['support']==8 for g in discarded),
        selected_support9=sum(g['support']==9 for g in selected),
        selected_support10=sum(g['support']==10 for g in selected),
        lowest_selected_support=min((g['support'] for g in selected), default=None),
        highest_unselected_support=max((g['support'] for g in discarded), default=None),
        selected_without_position=sum(g['feature_id'] not in node_ids for g in selected),
        positioned_not_in_candidate=len(node_ids-candidate_ids),
        ring_tied=rd.get('tied_best'),
        strongest_complete_ring_support=max((x['support'] for x in rd.get('alternatives', [])), default=None),
        weakest_direct_edge_support=min((x['direct_support'] for x in rd.get('edges', [])), default=None)))
    for edge in rd.get('edges', []):
        edges.append(dict(base, edge='|'.join(edge['feature_ids']),
            direct_support=edge['direct_support'], projected_support=edge['projected_support']))
for eid in sorted({x['event_id'] for x in states}):
    by_arm = {x['arm']: x for x in states if x['event_id']==eid}
    image = by_arm['A']['image']
    d_workers = set(events.loc[by_arm['A']['event_id'], 'D'].split('|'))
    def signature(group):
        return {(m['id'],m['pair_index']) for m in group['members'] if m['worker'] in d_workers}
    for g in by_arm['A']['full_state']['identity_groups']:
        sig = signature(g)
        if not sig: continue
        for arm in ['B','C']:
            for other in by_arm[arm]['full_state']['identity_groups']:
                other_sig = signature(other)
                overlap = sig & other_sig
                if not overlap: continue
                links.append(dict(image=image,event_id=by_arm['A']['event_id'],A_feature=g['feature_id'],
                    other_arm=arm,other_feature=other['feature_id'],common_D_observations=len(overlap),
                    A_D_observations=len(sig),other_D_observations=len(other_sig),
                    exact_same_D_signature=sig==other_sig,A_support=g['support'],other_support=other['support'],
                    A_selected=g['selected'],other_selected=other['selected'],
                    A_center=json.dumps(g.get('center')),other_center=json.dumps(other.get('center'))))
for name, rows in [('VOTE_TEAM_SUMMARY',summaries),('VOTE_GROUP_COMMON_D_LINKS',links),('VOTE_RING_EDGES',edges),
                   ('VOTE_GROUP_BLOCK_SUPPORT',block_supports)]:
    pd.DataFrame(rows).to_csv(OUT/(name+'.csv'), index=False, encoding='utf-8-sig')
assert len(summaries)==len(states)
summary = pd.DataFrame(summaries)
image_summary = summary.groupby('image').agg(events=('event_id','nunique'), endpoint_occurrences=('team_key','size'),
    unique_teams=('team_key','nunique'), occurrences_with_unselected=('unselected',lambda x:x.gt(0).sum()),
    occurrences_with_unselected_8=('unselected_support8',lambda x:x.gt(0).sum()),
    occurrences_with_selected_9=('selected_support9',lambda x:x.gt(0).sum()),
    occurrences_with_selected_10=('selected_support10',lambda x:x.gt(0).sum()),
    occurrences_selected_without_position=('selected_without_position',lambda x:x.gt(0).sum()),
    occurrences_positioned_not_in_candidate=('positioned_not_in_candidate',lambda x:x.gt(0).sum())).reset_index()
image_summary.to_csv(OUT/'VOTE_IMAGE_SUMMARY.csv', index=False, encoding='utf-8-sig')
print(image_summary.to_string(index=False))
q = pd.DataFrame(links)
print(q[(q.event_id=='84320bad6f9ea2b352a805f2') & q.A_feature.isin(['node_003','node_004'])].to_string(index=False))
