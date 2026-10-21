#!/usr/bin/env python3
"""Export two completed pure eight-seat Manual block events; replay only six native endpoints.

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
    dict(case_id='V3_jtc28_pure_positive_n10_m8', event_id='c70e935220e4ec6d39036e69', n=10,
         title='jtc-28：八席转折表达类补回必要结构',
         subtitle='Manual / n=10 / 共同2人背景；A→B、A→C、B→C各换8人'),
    dict(case_id='V3_jtc28_pure_counterexample_n15_m8', event_id='8be1375b4d2a53e269e1ccf2', n=15,
         title='jtc-28反例：同一八人类别块在另一背景中降低质量',
         subtitle='Manual / n=15 / 共同7人背景；A→B、A→C、B→C各换8人')]

def savecsv(name, frame):
    p = HERE/name; p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name+'.tmp'); frame.to_csv(tmp, index=False, encoding='utf-8-sig')
    assert pd.read_csv(tmp).shape == frame.shape; tmp.replace(p)

def parse_counts(s):
    return {c:int(n) for c,n in (x.split(':') for x in s.split('|'))}

def main():
    HERE.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_csv(V3/'composition/matched/PURE_EXPLANATORY_CANDIDATES.csv.gz',keep_default_na=False,low_memory=False)
    candidates = candidates[candidates.event_id.isin([s['event_id'] for s in SPECS])]
    assert len(candidates)==2; savecsv('CASE_SELECTION_RECORDS.csv',candidates)
    idx = pd.read_csv(V3/'composition/matched/PURE_RESULT_SHARDS.csv', keep_default_na=False)
    index = idx[idx.path.isin(candidates.source_result_shard)]
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
    ll = ll[(ll.condition == 'manual') & (ll.heldout_building == 'jtcxE69GiFV') & ll.known]
    assert set(ll.selected_family) == {'JOINT'} and set(ll.coarse_k) == {4} and set(ll.fine_k) == {4}
    assert ll.groupby('coarse_label').fine_label.nunique().eq(1).all()
    savecsv('TARGET_BUILDING_EXCLUDED_LABELS.csv', ll)
    centers = ll.groupby('coarse_label').agg(members=('worker_id','size'), **{c:(c,'mean') for c in
        ['turn_history','short_history','redundancy_history','area_history','height_history']}).reset_index()
    savecsv('TARGET_BUILDING_EXCLUDED_CENTROIDS.csv', centers)
    gs.save(HERE/'EXPORT_PROGRESS.json', dict(stage='full_events_and_frozen_target_excluded_labels_saved',
        events=len(events), event_columns=len(events.columns), label_sha256=hashlib.sha256(labels_path.read_bytes()).hexdigest(),
        final_taxonomy_unchanged=True, score_calls=0))
    names = {'M1':'明显简化/偏收缩', 'M2':'略简化/分段较多', 'M3':'常规/略简化', 'M4':'较多转折/短边'}
    colors = {'M1':'#ae5a54', 'M2':'#8d6baf', 'M3':'#2276a0', 'M4':'#3c9265'}
    for label in list(names): names[label+'.1'] = names[label]; colors[label+'.1'] = colors[label]
    names = {k:k+' '+v for k,v in names.items()}
    pools = gs.pool_lookup(); fe,_,_,_ = gs.setup_engine()
    cases, receipts, replay_cache, native_cache = [], [], {}, {}
    # Resume verified mechanism states without replaying any endpoint again.
    for existing in (HERE/'cases').glob('*.json.gz'):
        previous=gs.read(existing)
        if previous['event_id'] in {x['event_id'] for x in SPECS}:
            for team in previous['teams']:
                assert gs.digest(team['full_state']['candidate']) == gs.digest(team['geometry'])
                replay_cache[(previous['pool_id'],team['team_key'])]=team['full_state']
    with fe.cached_matching():
      for spec in SPECS:
        event = events[events.event_id == spec['event_id']].iloc[0].to_dict()
        pool = pools[event['pool_id']]
        byworker = {r['worker_id']:r for r in pool['records']}
        bylabel = dict(zip(ll.worker_id, ll[event['tier']+'_label']))
        label_meta = ll.set_index('worker_id').to_dict('index')
        paths = list((V3/'composition/runtime').glob('pure_001/'+event['pool_id']+'.json.gz'))
        assert len(paths) == 1, paths
        path = paths[0]
        if path not in native_cache:
            data = gs.read(path); assert data['pool_input_sha256'] == gs.digest(pool)
            native_cache[path] = {t['team_key']:t for t in data['teams']}
        native = native_cache[path]
        assert all(event['team_'+a] in native for a in 'ABC')
        case = dict(spec, method_id=event['method_id'], tier=event['tier'], event=event, pool_id=event['pool_id'],
            pool_meta=pool['meta'], image_id=pool['meta']['image_id'], reference=dict(pool['reference'],reference_id=pool['meta']['reference_id']),
            selection='post_result_pure_8_seat_blocks_same_image_same_incoming_Z_different_background_n_not_causal_n_curve',
            label_scope='V3_BEHAVIOR_target_building_excluded_geometry_E_R_G_family_named_JOINT_4_coarse_4_fine_no_QT_no_fine_increment',
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
        case['raw_overlay_workers'] = [w for w in ['W101','W104','W109','W115','W125','W130'] if w in union]
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
        for a,b in itertools.combinations(case['teams'],2):
            # Existing transition helper assumes scored endpoints; preserve an
            # observed failure as missing quality, never zero or dropped.
            aa=dict(a, B8L2=a['B8L2'] if a['B8L2'] is not None else float('nan'),
                    D10=a['D10'] if a['D10'] is not None else float('nan'))
            bb=dict(b, B8L2=b['B8L2'] if b['B8L2'] is not None else float('nan'),
                    D10=b['D10'] if b['D10'] is not None else float('nan'))
            for copy_team in (aa,bb):
                for field in ['iou_2d','dir']:
                    if copy_team[field] is None: copy_team[field]=float('nan')
            trans.analyze_pair(case,aa,bb,transitions,links)
    for name,rows in [('CASE_ENDPOINT_METRICS.csv',metrics),('EXACT_CASE_MEMBERS.csv',members),('GROUP_CLASS_VOTES.csv',votes),
                      ('OBSERVATION_TRANSITIONS.csv',transitions),('GROUP_OVERLAP_LINKS.csv',links)]:
        savecsv(name,pd.DataFrame(rows))
    gs.save(HERE/'EXPORT_PROGRESS.json', dict(stage='exact_events_members_native_endpoints_and_full_states_saved',
        full_state_replays=len(replay_cache),new_teams=0,score_calls=0,all_native_geometry_exact=True))
    print('Unique cached-team state replays:',len(replay_cache),'No scoring.',flush=True)

if __name__ == '__main__': main()
