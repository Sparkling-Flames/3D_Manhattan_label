#!/usr/bin/env python3
"""Replay only stored exact teams to expose votes; never rescore endpoints."""
from __future__ import annotations
import collections,importlib.util,itertools,json,sys
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent/'positive_cases';STUDY=HERE.parents[1];REPO=STUDY.parents[2]
V3=REPO/'research/workers/personnel_useful_taxonomy_v3_20261021'
OLD=REPO/'research/workers/personnel_global_composition_20261021'
sys.path.insert(0,str(STUDY/'expanded_blocks'))
from run_native import gs,write_csv,prior

SPECS=[
 dict(case_id='E20261022_wc2_56_n20_m6',event_id='ae7834d1143c3eb255ef9d70',
      title='wc2-56：同样四角，换类后的定位与效率收益'),
 dict(case_id='E20261022_zs16_n20_m6',event_id='f5a4b2fb6c7c48b523c8d0bc',
      title='zs-16：人数20时，同类成员B已保留必要转折'),
 dict(case_id='E20261022_zs16_n21_m6',event_id='c2244690085439b7a26cd94e',
      title='zs-16：增加共同背景后，目标类别保住必要转折')]

def angular(a,b):
    def ray(p):
        p=np.asarray(p,float);u=2*np.pi*(p[:,0]/1024-.5);v=np.pi*(.5-p[:,1]/512)
        return np.c_[np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)]
    return np.rad2deg(np.arccos(np.clip(ray(a)@ray(b).T,-1,1)))
def obs(g):return {(m['id'],int(m['pair_index'])) for m in g['members']}

def main():
    HERE.mkdir(parents=True,exist_ok=True)
    e=pd.read_csv(STUDY/'joint_exchange/NATIVE_MANUAL_EVENTS_COMPLETE.csv.gz',keep_default_na=False,low_memory=False)
    e=e[e.event_id.isin([s['event_id'] for s in SPECS])];assert len(e)==3
    write_csv(HERE/'EXACT_EVENTS.csv',e)
    l=pd.read_csv(V3/'taxonomy/JOINT_LABELS_LOBO.csv.gz',keep_default_na=False)
    l=l[(l.condition=='manual') & l.heldout_building.isin(e.building) & l.known.astype(str).str.lower().isin(['true','1'])]
    write_csv(HERE/'TARGET_BUILDING_EXCLUDED_LABELS.csv',l)
    pools=gs.pool_lookup();fe,_,_,_=gs.setup_engine();cases=[];receipts=[];tables=collections.defaultdict(list)
    palette=['#955f9a','#3e78a4','#777777','#c88a3e','#299678','#be5d63']
    with fe.cached_matching():
      for spec in SPECS:
        event=e[e.event_id.eq(spec['event_id'])].iloc[0].to_dict();pool=pools[event['pool_id']]
        byworker={r['worker_id']:r for r in pool['records']}
        ll=l[l.heldout_building.eq(event['building'])];lm=ll.set_index('worker_id').coarse_label.to_dict()
        classes=sorted(set(lm.values()));colors={c:palette[i%len(palette)] for i,c in enumerate(classes)}
        names={c:c+' 楼外联合类' for c in classes}
        names[event['source_class']]=event['source_class']+' 常规历史表达'
        names[event['target_class']]=event['target_class']+' 历史较高Q／更快'
        case=dict(spec,n=int(event['n']),method_id=event['method_id'],tier='coarse',event=event,pool_id=event['pool_id'],pool_meta=pool['meta'],
            image_id=pool['meta']['image_id'],reference=dict(pool['reference'],reference_id=pool['meta']['reference_id']),
            subtitle=f"Manual / n={event['n']} / 同背景 / 实际换{event['m_AB']}人",
            class_names=names,class_colors=colors,member_overlay_title=spec['title']+'：楼外类别的实际原答',
            selection='post-result explanatory case; effect sizes come from all registered matched events',
            underlying_data_version='v2',teams=[])
        native={};sources=[]
        for p in sorted((STUDY/'expanded_blocks/runtime').glob('joint_*/'+event['pool_id']+'.json.gz')):
            data=gs.read(p);assert data['pool_input_sha256']==gs.digest(pool)
            native.update({t['team_key']:t for t in data['teams']});sources.append(str(p.relative_to(REPO)))
        union=set();replay=[]
        for arm in 'ABC':
            team=dict(native[event['team_'+arm]]);ws=team['member_workers'];union.update(ws)
            assert '|'.join(ws)==event[arm+'_member_workers']
            state=fe.clean(fe.compact(fe.fuse([byworker[w] for w in sorted(ws)],gap=fe.WORKING_GAP)['automatic']))
            assert gs.digest(state['candidate'])==gs.digest(team['geometry'])
            assert state['minimum_support']==team['minimum_support']
            counts=collections.Counter(lm[w] for w in ws)
            team.update(label=arm,counts=dict(counts),full_state=state);case['teams'].append(team)
            replay.append(dict(arm=arm,team_key=team['team_key'],native_geometry_sha256=gs.digest(team['geometry']),state_geometry_equal=True))
        case['members']=[dict(byworker[w],class_id=lm[w],coarse_class=lm[w],fine_class=lm[w]) for w in sorted(union)]
        # Only X/Y/Z are shown in the explanatory raw panels, with all members
        # retained in the case; background is visible in the full member plot.
        case['raw_overlay_groups']=[dict(class_id=event['source_class'],workers=event['outgoing_block_X'].split('|'),label='同类块X：A中的6人'),
            dict(class_id=event['source_class'],workers=event['same_count_block_Y'].split('|'),label='同类块Y：B中的6人'),
            dict(class_id=event['target_class'],workers=event['changed_count_block_Z'].split('|'),label='目标类别块Z：C中的6人')]
        dest=HERE/'cases'/(case['case_id']+'.json.gz');gs.save(dest,case);cases.append(case)
        receipts.append(dict(case_id=case['case_id'],event_id=event['event_id'],native_sources=sources,replays=replay,
            output_sha256=prior.sha(dest),native_endpoint_count=0,score_calls=0))
        gs.save(HERE/'CASE_EXPORT_RECEIPT.json',dict(cases=receipts,new_endpoints=0,score_calls=0,replayed_cached_states=3*len(cases)))
        print('saved',case['case_id'],flush=True)
    for c in cases:
        ref=np.asarray(c['reference']['points_1024x512']);members={m['worker_id']:m for m in c['members']};bg=set(c['event']['common_background'].split('|'))
        for m in c['members']:
            tables['EXACT_MEMBERS'].append(dict(case_id=c['case_id'],worker_id=m['worker_id'],class_id=m['class_id'],object_id=m['id'],
                source_time_seconds=m.get('source_time_seconds'),time_source_kind=m.get('time_source_kind'),
                target_B8L2=m.get('B8L2'),raw_pair_count=len(m['points'])//2,
                in_background=m['worker_id'] in bg,arms='|'.join(t['label'] for t in c['teams'] if m['worker_id'] in t['member_workers'])))
        for t in c['teams']:
            metric={k:v for k,v in t.items() if not isinstance(v,(list,dict))};metric.update(case_id=c['case_id'],arm=t['label']);tables['ENDPOINT_METRICS'].append(metric)
            for g in t['full_state']['identity_groups']:
                center=np.asarray(g['center']);dist=np.maximum(angular(center[:1],ref[::2]),angular(center[1:],ref[1::2]))[0]
                j=int(np.argmin(dist));co=collections.Counter(members[m['worker']]['class_id'] for m in g['members'])
                tables['GROUP_VOTES'].append(dict(case_id=c['case_id'],arm=t['label'],n=c['n'],feature_id=g['feature_id'],support=g['support'],threshold=t['minimum_support'],selected=g['selected'],
                    nearest_reference_corner=j,nearest_paired_bound_deg=float(dist[j]),class_votes=gs.canonical_counts(co),
                    background_votes=sum(m['worker'] in bg for m in g['members']),variable_votes=sum(m['worker'] not in bg for m in g['members']),
                    member_workers='|'.join(sorted(m['worker'] for m in g['members'])),
                    top_x=float(center[0,0]),top_y=float(center[0,1]),bottom_x=float(center[1,0]),bottom_y=float(center[1,1])))
                for coordinate,index in [('x',(0,0)),('top_y',(0,1)),('bottom_y',(1,1))]:
                    mm=sorted(g['members'],key=lambda m:(m['points'][index[0]][index[1]],m['worker']))
                    median=float(np.median([x['points'][index[0]][index[1]] for x in mm]));assert abs(median-center[index])<1e-8
                    for rank,m in enumerate(mm):
                        tables['MEDIAN_ORDER'].append(dict(case_id=c['case_id'],arm=t['label'],feature_id=g['feature_id'],coordinate=coordinate,
                            rank=rank+1,worker_id=m['worker'],class_id=members[m['worker']]['class_id'],value=m['points'][index[0]][index[1]],
                            median_value=median,central_rank=rank in {(len(mm)-1)//2,len(mm)//2}))
                for m in g['members']:
                    tables['OBSERVATION_ASSIGNMENTS'].append(dict(case_id=c['case_id'],arm=t['label'],feature_id=g['feature_id'],support=g['support'],selected=g['selected'],
                        worker_id=m['worker'],object_id=m['id'],pair_index=m['pair_index'],source_pair_index=m['source_pair_index']))
            for ed in t['full_state']['ring_diagnostics']['edges']:
                tables['EDGE_VOTES'].append(dict(case_id=c['case_id'],arm=t['label'],node_pair='|'.join(ed['feature_ids']),
                    direct_support=ed['direct_support'],projected_support=ed['projected_support'],
                    direct_workers='|'.join(ed['direct_workers']),projected_workers='|'.join(ed['projected_workers'])))
    # Link identical observations across arms and the nested n20/n21 contexts.
    comparisons=[]
    for c in cases:
        for a,b in itertools.combinations(c['teams'],2):comparisons.append((c['case_id'],a,c['case_id'],b))
    for arm in 'ABC':comparisons.append((cases[1]['case_id'],cases[1]['teams']['ABC'.index(arm)],cases[2]['case_id'],cases[2]['teams']['ABC'.index(arm)]))
    for ca,a,cb,b in comparisons:
        for ga in a['full_state']['identity_groups']:
            for gb in b['full_state']['identity_groups']:
                shared=obs(ga)&obs(gb)
                if shared:tables['GROUP_OBSERVATION_LINKS'].append(dict(case_A=ca,arm_A=a['label'],case_B=cb,arm_B=b['label'],
                    group_A=ga['feature_id'],group_B=gb['feature_id'],support_A=ga['support'],support_B=gb['support'],
                    threshold_A=a['minimum_support'],threshold_B=b['minimum_support'],selected_A=ga['selected'],selected_B=gb['selected'],
                    shared_observations=len(shared),shared_workers='|'.join(sorted(m['worker'] for m in ga['members'] if (m['id'],m['pair_index']) in shared))))
    for name,rows in tables.items():write_csv(HERE/(name+'.csv'),rows)
    print('Mechanism tables saved; no quality recomputation.',flush=True)

if __name__=='__main__':main()
