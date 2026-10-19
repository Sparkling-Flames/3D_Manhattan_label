"""Retain count changes and failures alongside corresponding-corner distances."""
import pandas as pd
from tools.thesis_main.analysis.personnel_composition_followup_20261019 import OUT,FUSION,read,save,csv,building_mean
from tools.thesis_main.analysis.personnel_corner_review_20261020 import project,figure


def pair_stats(a,b):
    na,nb=a.get('nodes'),b.get('nodes')
    changed=None if na is None or nb is None else na!=nb
    incomplete=not(a['complete_evaluable'] and b['complete_evaluable'])
    qa,qb=a.get('B8L2'),b.get('B8L2')
    r=dict(count_changed=changed,incomplete=incomplete,count_change_or_incomplete=True if incomplete else changed,
           count_delta=None if changed is None else nb-na,Q_delta=None if qa is None or qb is None else qb-qa,
           quality_unavailable=qa is None or qb is None)
    assert a['reference_nodes']==b['reference_nodes']
    n=a['reference_nodes']
    for t in [5,9]:
        for kind in ['node','edge']:
            x,y=a.get(f'ref_matched_{kind}s_{t}'),b.get(f'ref_matched_{kind}s_{t}')
            known=x is not None and y is not None
            if known:x,y=set(x),set(y)
            r[f'{kind}_set_difference_{t}']=len(x^y)/n if known else None
            r[f'{kind}_lost_{t}']=len(x-y) if known else None
            r[f'{kind}_gained_{t}']=len(y-x) if known else None
    return r


def main():
    e=pd.read_csv(OUT/'EVENTS.csv.gz');c=pd.read_csv(OUT/'PANEL_CORNER_EVENTS.csv.gz')[['event_id','both_available']]
    e=e.merge(c,on='event_id',validate='one_to_one');teams=read(OUT/'TEAMS.json.gz')
    rows=[];pair_fields=[]
    for _,event in e.iterrows():
        row={k:event[k] for k in ['event_id','target','sample','historical_phase','pool_id','image','building','k','m','both_available']}
        a=teams[event.A_team_key]
        supports=a['node_supports'];threshold=a['minimum_support']
        row['A_selected_min_margin']=min(supports)-threshold if supports else None
        row['A_selected_vulnerable_static']=min(supports)-threshold<event.m if supports else None
        for arm,letter in [('within','B'),('cross','C')]:
            r=pair_stats(a,teams[event[letter+'_team_key']]);pair_fields=list(r)
            row.update({arm+'_'+k:v for k,v in r.items()})
        for letter in 'ABC':
            t=teams[event[letter+'_team_key']]
            row[letter+'_team_key']=event[letter+'_team_key']
            for field in ['nodes','score_status','B8L2','reference_nodes','complete_evaluable','ref_node_recall_9','ref_edge_recall_9']:
                row[letter+'_'+field]=t.get(field)
        rows.append(row)
    data=pd.DataFrame(rows);csv(OUT/'STRUCTURE_EVENTS.csv.gz',data)
    tail=data[~data.both_available];assert len(data)==451 and len(tail)==58
    csv(OUT/'STRUCTURE_NONCOMMON_58.csv',tail)
    summary=[];margin=[]
    # Each continuous diagnostic uses the same available events in both arms.
    for keys,g in data.groupby(['target','sample','historical_phase']):
        meta=dict(zip(['target','sample','historical_phase'],keys))
        for scope,frame in [('all_attempts',g),('noncommon_corner',g[~g.both_available])]:
            for metric in pair_fields:
                cols=['within_'+metric,'cross_'+metric]
                common=frame.dropna(subset=cols)
                summary.append(dict(meta,scope=scope,metric=metric,attempts=len(frame),paired_events=len(common),images=common.pool_id.nunique(),buildings=common.building.nunique(),
                    within=building_mean(common,cols[0]),cross=building_mean(common,cols[1]),
                    within_event_sum=common[cols[0]].sum() if metric in ['count_changed','incomplete','quality_unavailable','count_change_or_incomplete'] else None,
                    cross_event_sum=common[cols[1]].sum() if metric in ['count_changed','incomplete','quality_unavailable','count_change_or_incomplete'] else None))
        for vulnerable,frame in g.groupby('A_selected_vulnerable_static'):
            margin.append(dict(meta,vulnerable=bool(vulnerable),events=len(frame),images=frame.pool_id.nunique(),buildings=frame.building.nunique(),
                within_count_change=building_mean(frame,'within_count_changed'),cross_count_change=building_mean(frame,'cross_count_changed')))
    csv(OUT/'STRUCTURE_SUMMARY.csv',pd.DataFrame(summary));csv(OUT/'STRUCTURE_VOTE_MARGIN.csv',pd.DataFrame(margin))
    pools={p['pool_id']:p for p in read(FUSION/'INPUT_SNAPSHOT.json.gz')['images']}
    chosen=[]
    selectors=[('yqstnuAEVhm-01','extra0'),('yqstnuAEVhm-01','extra2'),('X7HyMhZNoso-19','extra1')]
    for number,(image,suffix) in enumerate(selectors,1):
        found=data[(data.target=='G_17_8')&(data.image==image)&data.event_id.str.endswith('__'+suffix)]
        assert len(found)==1
        row=found.iloc[0].to_dict();pool=pools[row['pool_id']]
        case=dict(image=dict(image_code=image),reference=dict(points=pool['reference']['points_1024x512']),teams={a:teams[row[a+'_team_key']] for a in 'ABC'})
        assert all(t['complete_evaluable'] for t in case['teams'].values())
        figure('S'+str(number),case,{a:project(t['geometry']['points']) for a,t in case['teams'].items()})
        chosen.append(dict(case='S'+str(number),event=row,reference_id=pool['meta']['reference_id'],
                           teams={a:dict(key=t['team_key'],members=t['member_workers'],nodes=t['nodes'],Q=t['B8L2'],node_recall_9=t['ref_node_recall_9'],edge_recall_9=t['ref_edge_recall_9']) for a,t in case['teams'].items()}))
    save(OUT/'STRUCTURE_CASES.json',dict(selection='Post-hoc explanatory cases from independent review; not a new efficacy denominator',cases=chosen))
    save(OUT/'STRUCTURE_CHECKS.json',dict(events=len(data),noncommon=len(tail),noncommon_images=tail.image.nunique(),
        within_count_changes=int(data.within_count_changed.sum()),cross_count_changes=int(data.cross_count_changed.sum()),
        within_quality_unavailable=int(data.within_quality_unavailable.sum()),cross_quality_unavailable=int(data.cross_quality_unavailable.sum()),
        reference_diagnostics='Stored Hungarian angular endpoint matching at5/9 degrees; includes available diagnostic geometry even when full scoring invalid; report full eligibility separately',
        vote_margin='Selected A nodes only; static support minus threshold < replaced count; does not account for identity regrouping or new nodes and is not a stability certificate'))
    s=pd.DataFrame(summary);print(s[(s['sample']=='additional_background')&(s.historical_phase=='validation')&(s.scope=='all_attempts')&s.metric.isin(['count_changed','quality_unavailable','node_set_difference_9','edge_set_difference_9'])].to_string(index=False))


if __name__=='__main__':main()
