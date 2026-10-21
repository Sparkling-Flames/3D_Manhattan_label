#!/usr/bin/env python3
"""Export two completed Manual events and replay unique endpoints for vote states.

This is a post-result mechanism case study. No scorer is loaded or called. Each
replayed candidate must match the existing native geometry exactly. All original
event fields, including zero-count classes, are retained.
"""
import collections, hashlib, importlib.util, itertools, sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
V3 = HERE.parents[1]
ROOT = V3.parents[2]
OLD = ROOT/'research/workers/personnel_global_composition_20261021'
sys.path.insert(0, str(OLD/'composition'))
import global_study as gs

SPECS = [
    dict(case_id='V3_pa4_18_positive_n12_m4', event_id='74063a5976c4235dc911a0fc', n=12,
         title='pa4-18：改构成后保留必要转折',
         subtitle='Manual / n=12 / 共同8人背景；A→B、A→C均换4人；B→C净换2人'),
    dict(case_id='V3_pa4_18_counterexample_n20_m5', event_id='4153e2a9129b075063bc42ac', n=20,
         title='pa4-18反例：同构成换人也能补足必要结构',
         subtitle='Manual / n=20 / 共同15人背景；A→B、A→C均换5人；B→C净换1人')]

def savecsv(name, frame):
    p = HERE/name; p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name+'.tmp'); frame.to_csv(tmp, index=False, encoding='utf-8-sig')
    assert pd.read_csv(tmp).shape == frame.shape; tmp.replace(p)

def parse_counts(s):
    return {c:int(n) for c,n in (x.split(':') for x in s.split('|'))}

def main():
    HERE.mkdir(parents=True, exist_ok=True)
    idx = pd.read_csv(V3/'composition/matched/PANEL_RESULT_SHARDS.csv', keep_default_na=False)
    index = idx[idx.panel_id.isin([f'pa4otMbVnkk-18__manual__bbb972aaa9__v1__n{s["n"]}' for s in SPECS])]
    assert len(index) == 2; savecsv('SOURCE_SHARD_ROWS.csv', index)
    parts, source_by_event = [], {}
    for row in index.itertuples():
        p = V3/'composition'/row.path
        assert hashlib.sha256(p.read_bytes()).hexdigest() == row.sha256
        z = pd.read_csv(p, keep_default_na=False, low_memory=False)
        z = z[z.event_id.isin([s['event_id'] for s in SPECS])]
        parts.append(z)
        for eid in z.event_id: source_by_event[eid] = p
    events = pd.concat(parts, ignore_index=True)
    assert len(events) == 2; savecsv('EXACT_EVENTS.csv', events)
    labels_path = V3/'taxonomy/LABELS_LOBO.csv.gz'
    ll = pd.read_csv(labels_path)
    ll = ll[(ll.condition == 'manual') & (ll.heldout_building == 'pa4otMbVnkk') & ll.known]
    assert set(ll.selected_family) == {'TURN'} and set(ll.coarse_k) == {3} and set(ll.fine_k) == {3}
    assert ll.groupby('coarse_label').fine_label.nunique().eq(1).all()
    savecsv('TARGET_BUILDING_EXCLUDED_LABELS.csv', ll)
    centers = ll.groupby('coarse_label').agg(members=('worker_id','size'), **{c:(c,'mean') for c in
        ['turn_history','short_history','redundancy_history','area_history','height_history']}).reset_index()
    savecsv('TARGET_BUILDING_EXCLUDED_CENTROIDS.csv', centers)
    gs.save(HERE/'EXPORT_PROGRESS.json', dict(stage='full_events_and_frozen_target_excluded_labels_saved',
        events=len(events), event_columns=len(events.columns), label_sha256=hashlib.sha256(labels_path.read_bytes()).hexdigest(),
        final_taxonomy_unchanged=True, score_calls=0))
    names = {'M1':'复杂结构偏简化', 'M2':'常规/略简化', 'M3':'较多转折/短边'}
    colors = {'M1':'#ae5a54', 'M2':'#2276a0', 'M3':'#3c9265'}
    for label in list(names): names[label+'.1'] = names[label]; colors[label+'.1'] = colors[label]
    names = {k:k+' '+v for k,v in names.items()}
    pools = gs.pool_lookup(); fe,_,_,_ = gs.setup_engine()
    cases, receipts, replay_cache, native_cache = [], [], {}, {}
    with fe.cached_matching():
      for spec in SPECS:
        event = events[events.event_id == spec['event_id']].iloc[0].to_dict()
        pool = pools[event['pool_id']]
        byworker = {r['worker_id']:r for r in pool['records']}
        bylabel = dict(zip(ll.worker_id, ll[event['tier']+'_label']))
        label_meta = ll.set_index('worker_id').to_dict('index')
        paths = list((V3/'composition/runtime').glob('batch_*/'+event['pool_id']+'.json.gz'))
        assert len(paths) == 1, paths
        path = paths[0]
        if path not in native_cache:
            data = gs.read(path); assert data['pool_input_sha256'] == gs.digest(pool)
            native_cache[path] = {t['team_key']:t for t in data['teams']}
        native = native_cache[path]
        assert all(event['team_'+a] in native for a in 'ABC')
        case = dict(spec, method_id=event['method_id'], tier=event['tier'], event=event, pool_id=event['pool_id'],
            pool_meta=pool['meta'], image_id=pool['meta']['image_id'], reference=dict(pool['reference'],reference_id=pool['meta']['reference_id']),
            selection='post_result_positive_and_counterexample_same_image_different_n_m_not_frequency_estimation',
            label_scope='target_building_excluded_TURN_3_coarse_3_fine_identical_partition_no_fine_increment',
            class_names=names, class_colors=colors, member_overlay_title=spec['title']+'：实际成员按楼外结构类叠加', teams=[])
        union, replays = set(), []
        for arm in 'ABC':
            t = dict(native[event['team_'+arm]]); union.update(t['member_workers'])
            assert t['k'] == spec['n'] and '|'.join(sorted(t['member_workers'])) == event[arm+'_member_workers']
            replay_key = (event['pool_id'], t['team_key'])
            reused = replay_key in replay_cache
            if not reused:
                replay_cache[replay_key] = fe.clean(fe.compact(fe.fuse([byworker[w] for w in sorted(t['member_workers'])],
                    gap=fe.WORKING_GAP)['automatic']))
            state = replay_cache[replay_key]
            assert gs.digest(state['candidate']) == gs.digest(t['geometry']), (spec['case_id'],arm,'native geometry mismatch')
            assert state['n'] == t['k'] and state['minimum_support'] == t['minimum_support']
            assert len(state['node_consensus']['nodes']) == t['nodes']
            expected = parse_counts(event[arm+'_counts'])
            actual = collections.Counter(bylabel[w] for w in t['member_workers'])
            assert all(actual.get(k,0) == v for k,v in expected.items()) and sum(expected.values()) == t['k']
            t.update(label=arm, counts=expected, full_state=state); case['teams'].append(t)
            replays.append(dict(arm=arm,team_key=t['team_key'],state_reused=reused,
                geometry_sha256=gs.digest(t['geometry']),replay_candidate_sha256=gs.digest(state['candidate'])))
        for arm in 'BC':
            assert len(set(case['teams'][0]['member_workers'])-set(case['teams']['ABC'.index(arm)]['member_workers'])) == event['m_A'+arm]
        assert len(set(case['teams'][1]['member_workers'])-set(case['teams'][2]['member_workers'])) == event['m_BC']
        case['members'] = [dict(byworker[w], class_id=bylabel[w], coarse_class=label_meta[w]['coarse_label'],
            fine_class=label_meta[w]['fine_label']) for w in sorted(union)]
        case['raw_overlay_workers'] = [w for w in ['W101','W112','W122','W130'] if w in union]
        target = HERE/'cases'/(spec['case_id']+'.json.gz'); gs.save(target,case)
        assert gs.read(target) == gs.clean(case); cases.append(case)
        source = source_by_event[spec['event_id']]
        receipts.append(dict(case_id=spec['case_id'],event_id=spec['event_id'],event_source=str(source.relative_to(ROOT)),
            event_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),native_source=str(path.relative_to(ROOT)),
            native_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pool_sha256=gs.digest(pool),replays=replays,
            output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),score_calls=0,new_endpoint_count=0))
        gs.save(HERE/'CASE_EXPORT_RECEIPT.json', dict(cases=receipts, full_state_replays=len(replay_cache),
            new_teams=0,score_calls=0,all_native_geometry_exact=True))
        print('Saved', spec['case_id'], [(t['label'],t['B8L2'],t['nodes'],t['minimum_support']) for t in case['teams']], flush=True)
    mod = importlib.util.spec_from_file_location('frozen_vote_transitions', OLD/'evidence/analyze_vote_transitions.py')
    trans = importlib.util.module_from_spec(mod); mod.loader.exec_module(trans)
    transitions, links, votes, metrics, members = [], [], [], [], []
    for case in cases:
        bylabel = {m['worker_id']:m['class_id'] for m in case['members']}
        for t in case['teams']:
            row = {k:v for k,v in t.items() if not isinstance(v,(dict,list))}
            row.update(case_id=case['case_id'],arm=t['label'],composition=gs.canonical_counts(t['counts'])); metrics.append(row)
            for g in t['full_state']['identity_groups']:
                votes.append(dict(case_id=case['case_id'],arm=t['label'],feature_id=g['feature_id'],support=g['support'],
                    threshold=t['minimum_support'],selected=g['selected'],top_x=g['center'][0][0],top_y=g['center'][0][1],
                    bottom_x=g['center'][1][0],bottom_y=g['center'][1][1],
                    class_votes=gs.canonical_counts(collections.Counter(bylabel[m['worker']] for m in g['members'])),
                    member_workers='|'.join(sorted(m['worker'] for m in g['members'])),
                    observation_keys='|'.join(f'{x[0]}:{x[1]}' for x in sorted(trans.obs(g)))))
        for m in case['members']:
            members.append(dict(case_id=case['case_id'],worker_id=m['worker_id'],object_id=m['id'],class_id=m['class_id'],
                coarse_class=m['coarse_class'],fine_class=m['fine_class'],origin=m['origin'],target_B8L2=m.get('B8L2'),target_D10=m.get('D10'),
                point_pairs=len(m['points'])//2,source_time_seconds=m.get('source_time_seconds'),time_source_kind=m.get('time_source_kind'),
                arms='|'.join(t['label'] for t in case['teams'] if m['worker_id'] in t['member_workers'])))
        for a,b in itertools.combinations(case['teams'],2): trans.analyze_pair(case,a,b,transitions,links)
    for name,rows in [('CASE_ENDPOINT_METRICS.csv',metrics),('EXACT_CASE_MEMBERS.csv',members),('GROUP_CLASS_VOTES.csv',votes),
                      ('OBSERVATION_TRANSITIONS.csv',transitions),('GROUP_OVERLAP_LINKS.csv',links)]:
        savecsv(name,pd.DataFrame(rows))
    gs.save(HERE/'EXPORT_PROGRESS.json', dict(stage='exact_events_members_native_endpoints_and_full_states_saved',
        full_state_replays=len(replay_cache),new_teams=0,score_calls=0,all_native_geometry_exact=True))
    print('Unique cached-team state replays:',len(replay_cache),'No scoring.',flush=True)

if __name__ == '__main__': main()
