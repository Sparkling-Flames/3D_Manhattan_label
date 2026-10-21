#!/usr/bin/env python3
"""Replay six completed 7y-13 teams only for vote-state explanation.

Events are deliberately post-result positive/counterexample selections. No score
call is made, no endpoint changed, and replayed candidate digests must match the
native cache. Comparison nodes are linked by immutable observation identities.
"""
import collections,hashlib,importlib.util,itertools,json,sys
from pathlib import Path
import pandas as pd

HERE=Path(__file__).resolve().parent
V3=HERE.parents[1]
ROOT=V3.parents[2]
OLD=ROOT/'research/workers/personnel_global_composition_20261021'
sys.path.insert(0,str(OLD/'composition'))
import global_study as gs

SPECS=[dict(case_id='V3_7y13_positive_n12_m4',event_id='5ce0342d581473fa75f96547',
    title='7y-13：同构成换4人结果相同，改构成后定位改善',
    subtitle='Semi / n=12 / 同一8人背景；A→B、A→C均换4人；B→C净换1人'),
 dict(case_id='V3_7y13_counterexample_n12_m4',event_id='a8678d90c6f06ac4b62943e1',
    title='同图反例：同构成换4人定位恶化，改构成变化较小',
    subtitle='Semi / n=12 / 同一8人背景；A→B、A→C均换4人；B→C净换2人')]

def savecsv(name,frame):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp')
    frame.to_csv(tmp,index=False,encoding='utf-8-sig');assert pd.read_csv(tmp).shape==frame.shape;tmp.replace(p)

def parse_counts(s):return {c:int(n) for c,n in (x.split(':') for x in s.split('|'))}

def main():
    HERE.mkdir(parents=True,exist_ok=True)
    shards_path=V3/'composition/matched/PANEL_RESULT_SHARDS.csv'
    idx=pd.read_csv(shards_path,keep_default_na=False)
    index=idx[idx.panel_id.eq('7y3sRwLe3Va-13__semi__5b6c87b5f3__v1__n12')]
    assert len(index)==1
    savecsv('SOURCE_SHARD_ROW.csv',index)
    source=V3/'composition'/index.iloc[0].path
    assert hashlib.sha256(source.read_bytes()).hexdigest()==index.iloc[0].sha256
    events=pd.read_csv(source,keep_default_na=False,low_memory=False)
    events=events[events.event_id.isin([s['event_id'] for s in SPECS])]
    assert len(events)==2;savecsv('EXACT_EVENTS.csv',events)
    labels_path=V3/'taxonomy/LABELS_LOBO.csv.gz'
    labels=pd.read_csv(labels_path)
    ll=labels[(labels.condition=='semi')&(labels.heldout_building=='7y3sRwLe3Va')&labels.known]
    savecsv('TARGET_BUILDING_EXCLUDED_LABELS.csv',ll)
    centers=ll.groupby('coarse_label')[['turn_history','short_history','redundancy_history','area_history','height_history']].mean().reset_index()
    savecsv('TARGET_BUILDING_EXCLUDED_CENTROIDS.csv',centers)
    classnames={'S1':'S1 常规/偏少转折','S2':'S2 近共线分段较多','S3':'S3 较多转折/短边'}
    colors={'S1':'#2276a0','S2':'#c88523','S3':'#3c9265'}
    pools=gs.pool_lookup();fe,_,_,_=gs.setup_engine();cases=[];receipts=[]
    with fe.cached_matching():
      for spec in SPECS:
        event=events[events.event_id==spec['event_id']].iloc[0].to_dict()
        pool=pools[event['pool_id']];byworker={r['worker_id']:r for r in pool['records']};bylabel=dict(zip(ll.worker_id,ll.coarse_label))
        path=V3/'composition/runtime/batch_001'/(event['pool_id']+'.json.gz')
        data=gs.read(path);assert data['pool_input_sha256']==gs.digest(pool)
        needed={event['team_'+a] for a in 'ABC'};native={t['team_key']:t for t in data['teams'] if t['team_key'] in needed}
        assert set(native)==needed
        case=dict(spec,method_id=event['method_id'],tier=event['tier'],event=event,pool_id=event['pool_id'],
            pool_meta=pool['meta'],image_id=pool['meta']['image_id'],reference=dict(pool['reference'],reference_id=pool['meta']['reference_id']),
            selection='post_result_positive_and_counterexample_same_image_same_n_and_m_not_frequency_estimation',
            label_scope='target_building_excluded_STRUCTURE_inner_selected_coarse',class_names=classnames,class_colors=colors,
            member_overlay_title=spec['title']+'：实际成员按楼外结构类别叠加',teams=[])
        union=set();replays=[]
        for arm in 'ABC':
            t=dict(native[event['team_'+arm]]);union.update(t['member_workers'])
            assert t['k']==12 and '|'.join(sorted(t['member_workers']))==event[arm+'_member_workers']
            state=fe.clean(fe.compact(fe.fuse([byworker[w] for w in sorted(t['member_workers'])],gap=fe.WORKING_GAP)['automatic']))
            assert gs.digest(state['candidate'])==gs.digest(t['geometry']),(spec['case_id'],arm,'native geometry mismatch')
            assert state['n']==t['k'] and state['minimum_support']==t['minimum_support']
            assert len(state['node_consensus']['nodes'])==t['nodes']
            expected=parse_counts(event[arm+'_counts']);actual=collections.Counter(bylabel[w] for w in t['member_workers'])
            assert all(actual.get(k,0)==v for k,v in expected.items()) and sum(expected.values())==t['k']
            t.update(label=arm,counts=expected,full_state=state);case['teams'].append(t)
            replays.append(dict(arm=arm,team_key=t['team_key'],geometry_sha256=gs.digest(t['geometry']),replay_candidate_sha256=gs.digest(state['candidate'])))
        case['members']=[dict(byworker[w],class_id=bylabel[w]) for w in sorted(union)]
        case['raw_overlay_workers']=[w for cl in sorted(set(bylabel[w] for w in union)) for w in sorted(w for w in union if bylabel[w]==cl)[:3]]
        target=HERE/'cases'/(spec['case_id']+'.json.gz');gs.save(target,case);assert gs.read(target)==gs.clean(case)
        cases.append(case)
        receipts.append(dict(case_id=spec['case_id'],event_id=spec['event_id'],event_source=str(source.relative_to(ROOT)),
            event_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),native_source=str(path.relative_to(ROOT)),
            native_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pool_sha256=gs.digest(pool),replays=replays,
            output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),score_calls=0,new_endpoint_count=0))
        gs.save(HERE/'CASE_EXPORT_RECEIPT.json',dict(cases=receipts,full_state_replays=3*len(receipts),new_teams=0,score_calls=0,all_native_geometry_exact=True))
        print('Saved',spec['case_id'],[(t['label'],t['B8L2'],t['nodes'],t['minimum_support']) for t in case['teams']],flush=True)
    spec=importlib.util.spec_from_file_location('frozen_vote_transitions',OLD/'evidence/analyze_vote_transitions.py')
    trans=importlib.util.module_from_spec(spec);spec.loader.exec_module(trans)
    transitions=[];links=[];votes=[];metrics=[];members=[]
    for case in cases:
        bylabel={m['worker_id']:m['class_id'] for m in case['members']}
        for t in case['teams']:
            row={k:v for k,v in t.items() if not isinstance(v,(dict,list))};row.update(case_id=case['case_id'],arm=t['label'],composition=gs.canonical_counts(t['counts']))
            metrics.append(row)
            for g in t['full_state']['identity_groups']:
                votes.append(dict(case_id=case['case_id'],arm=t['label'],feature_id=g['feature_id'],support=g['support'],
                    threshold=t['minimum_support'],selected=g['selected'],top_x=g['center'][0][0],top_y=g['center'][0][1],
                    bottom_x=g['center'][1][0],bottom_y=g['center'][1][1],
                    class_votes=gs.canonical_counts(collections.Counter(bylabel[m['worker']] for m in g['members'])),
                    member_workers='|'.join(sorted(m['worker'] for m in g['members'])),
                    observation_keys='|'.join(f'{x[0]}:{x[1]}' for x in sorted(trans.obs(g)))))
        for m in case['members']:
            members.append(dict(case_id=case['case_id'],worker_id=m['worker_id'],object_id=m['id'],class_id=m['class_id'],origin=m['origin'],
                target_B8L2=m.get('B8L2'),target_D10=m.get('D10'),point_pairs=len(m['points'])//2,
                source_time_seconds=m.get('source_time_seconds'),time_source_kind=m.get('time_source_kind'),
                arms='|'.join(t['label'] for t in case['teams'] if m['worker_id'] in t['member_workers'])))
        for a,b in itertools.combinations(case['teams'],2):trans.analyze_pair(case,a,b,transitions,links)
    for name,rows in [('CASE_ENDPOINT_METRICS.csv',metrics),('EXACT_CASE_MEMBERS.csv',members),('GROUP_CLASS_VOTES.csv',votes),
            ('OBSERVATION_TRANSITIONS.csv',transitions),('GROUP_OVERLAP_LINKS.csv',links)]:savecsv(name,pd.DataFrame(rows))
    print('Completed six cached-team state replays; no scoring.',flush=True)

if __name__=='__main__':main()
