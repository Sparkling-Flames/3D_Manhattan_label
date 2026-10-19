"""Replay noncommon teams and trace identity groups by shared original observations."""
import os
import sys
import pandas as pd
from tools.thesis_main.analysis.personnel_composition_followup_20261019 import ROOT,OUT,FUSION,read,save,csv


def observations(group):
    return {(m['worker'],m['source_pair_index']) for m in group['members']}


def trace_groups(before,after,retained):
    groups={('A',i):g for i,g in enumerate(before)}|{('D',i):g for i,g in enumerate(after)}
    obs={k:observations(g) for k,g in groups.items()}
    shared_before={o for k,v in obs.items() if k[0]=='A' for o in v if o[0] in retained}
    shared_after={o for k,v in obs.items() if k[0]=='D' for o in v if o[0] in retained}
    assert shared_before==shared_after, 'retained observation identities changed'
    adj={k:set() for k in groups}
    for i in range(len(before)):
        for j in range(len(after)):
            a,b=('A',i),('D',j)
            if obs[a]&obs[b]:adj[a].add(b);adj[b].add(a)
    rows=[];unseen=set(groups)
    while unseen:
        seed=min(unseen);component=set();todo=[seed]
        while todo:
            k=todo.pop()
            if k in component:continue
            component.add(k);todo.extend(adj[k]-component)
        unseen-=component
        left=sorted(k for k in component if k[0]=='A');right=sorted(component-set(left))
        x=set().union(*(obs[k] for k in left));y=set().union(*(obs[k] for k in right))
        a,b=len(left),len(right)
        kind='one_to_one' if a==b==1 else 'unlinked_before' if not b else 'unlinked_after' if not a else 'split' if a==1 else 'merge' if b==1 else 'many_to_many'
        lost=sum(w not in retained for w,_ in x);gained=sum(w not in retained for w,_ in y)
        retained_delta=sum(w in retained for w,_ in y)-sum(w in retained for w,_ in x)
        assert len(y)-len(x)==gained-lost+retained_delta
        for k in component:assert len(obs[k])==groups[k]['support']
        rows.append(dict(kind=kind,before_ids='|'.join(groups[k]['feature_id'] for k in left),after_ids='|'.join(groups[k]['feature_id'] for k in right),
            support_before=len(x),support_after=len(y),support_delta=len(y)-len(x),outgoing_votes=lost,incoming_votes=gained,retained_delta=retained_delta,
            selected_before=sum(groups[k]['selected'] for k in left),selected_after=sum(groups[k]['selected'] for k in right),
            shared_observations=len(x&y),outgoing_workers='|'.join(sorted({w for w,_ in x if w not in retained})),incoming_workers='|'.join(sorted({w for w,_ in y if w not in retained}))))
    return rows


def main():
    os.environ['PERSONNEL_V2_REPOSITORY']=str(ROOT);sys.path.insert(0,str(FUSION))
    import fusion_engine as fe
    pools={p['pool_id']:p for p in fe.load_pools()};teams=read(OUT/'TEAMS.json.gz')
    events=pd.read_csv(OUT/'STRUCTURE_NONCOMMON_58.csv');states={};rows=[];checks=[]
    with fe.cached_matching():
        for _,event in events.iterrows():
            pool=pools[event.pool_id];by={r['worker_id']:r for r in pool['records']}
            for arm in 'ABC':
                key=event[arm+'_team_key']
                if key in states:continue
                old=teams[key];selected=[by[w] for w in sorted(old['member_workers'])]
                worker_by_id={r['id']:r['worker_id'] for r in selected}
                state=fe.compact(fe.fuse(selected,gap=fe.WORKING_GAP)['automatic'])
                assert fe.clean(state['candidate'])==old['geometry'],key
                assert state['minimum_support']==old['minimum_support']
                states[key]=dict(minimum_support=state['minimum_support'],groups=[dict(feature_id=g['feature_id'],support=g['support'],selected=g['selected'],center=g['center'],members=[dict(worker=worker_by_id[m['id']],source_pair_index=m['source_pair_index']) for m in g['members']]) for g in state['identity_groups']])
                checks.append(dict(team_key=key,geometry_identical=True,threshold=state['minimum_support']))
            for arm,letter in [('within','B'),('cross','C')]:
                ak,bk=event.A_team_key,event[letter+'_team_key'];a,b=states[ak],states[bk]
                retained=set(teams[ak]['member_workers'])&set(teams[bk]['member_workers'])
                result=trace_groups(a['groups'],b['groups'],retained)
                for r in result:r.update(event_id=event.event_id,target=event.target,sample=event['sample'],historical_phase=event.historical_phase,image=event.image,building=event.building,arm=arm,threshold=a['minimum_support'])
                assert sum(r['selected_after']-r['selected_before'] for r in result)==sum(g['selected'] for g in b['groups'])-sum(g['selected'] for g in a['groups'])
                rows.extend(result)
            print('traced',len(checks),'teams',event.event_id,flush=True)
    save(OUT/'VOTE_GROUPS.json.gz',states);csv(OUT/'VOTE_TRANSITIONS.csv.gz',pd.DataFrame(rows))
    save(OUT/'VOTE_CHECKS.json',dict(events=len(events),teams=len(states),geometry_identical=len(checks),rows=len(rows),scope='58 noncommon events, mechanism-selected; not population rates'))
    frame=pd.DataFrame(rows);summary=frame.groupby(['arm','kind']).agg(components=('event_id','size'),events=('event_id','nunique'),selected_before=('selected_before','sum'),selected_after=('selected_after','sum')).reset_index()
    csv(OUT/'VOTE_SUMMARY.csv',summary)
    cases={c['event']['event_id']:c['case'] for c in read(OUT/'STRUCTURE_CASES.json')['cases']}
    chosen=frame[frame.event_id.isin(cases) & (frame.selected_before!=frame.selected_after)].copy()
    chosen.insert(0,'case',chosen.event_id.map(cases));csv(OUT/'VOTE_CASE_TRANSITIONS.csv',chosen)
    event_rows=[]
    for (event_id,arm),g in frame.groupby(['event_id','arm']):
        one=g[g.kind=='one_to_one'];complex_group=g[g.kind.isin(['split','merge','many_to_many'])]
        event_rows.append(dict(event_id=event_id,arm=arm,has_regrouping=len(complex_group)>0,
            one_to_one_lost=int(((one.selected_before==1)&(one.selected_after==0)).sum()),
            one_to_one_gained=int(((one.selected_before==0)&(one.selected_after==1)).sum()),
            regrouping_selected_count_changed=bool((complex_group.selected_before!=complex_group.selected_after).any())))
    csv(OUT/'VOTE_EVENT_SUMMARY.csv',pd.DataFrame(event_rows));print(summary.to_string(index=False))


if __name__=='__main__':main()
