"""Export small mechanism evidence with exact current records and native states."""
import pandas as pd
import study as s


def main():
    fe,fr,sg,corner,step,normalize=s.setup_engine()
    pools={p['pool_id']:p for p in s.read(s.FUSION/'INPUT_SNAPSHOT.json.gz')['images']};maps=s.label_maps()
    nested=pd.read_csv(s.OUT/'NESTED_EVENTS.csv');req=s.read(s.OUT/'NESTED_REQUESTS.json.gz')['paths']
    requests={e['event_id']:e for p in req for e in p['events']};cases={}
    specifications=[('Uw22_complement_and_dilution','UwV83HsGsw3-22','M0','M1',[(8,'A'),(8,'B'),(8,'C'),(9,'C'),(10,'C'),(13,'C')]),
                    ('Semi_wc56_extra_nodes','wc2JMjhGNzB-56','S0','S1',[(12,'A'),(12,'B'),(12,'C'),(13,'C')])]
    with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
        for cid,image,c,d,panels in specifications:
            frame=nested[(nested.image==image)&(nested.outgoing_class==c)&(nested.incoming_class==d)]
            p=pools[frame.iloc[0].pool_id];labels=maps[p['meta']['condition'],p['meta']['building']]
            teams=[];used=set()
            for n,arm in panels:
                row=frame[frame.n==n].iloc[0];request=requests[row.event_id];workers=request[arm+'_workers'];used.update(workers)
                t=fr.evaluate_one(p,workers,engine,models,full_state=True);t['full_state']=normalize(t['full_state'])
                t.update(panel=f'{arm}_n{n}',event_id=row.event_id,coarse_counts=s.counts(workers,labels,'coarse'),fine_counts=s.counts(workers,labels,'fine'))
                teams.append(t)
            cases[cid]=dict(case_id=cid,selection='Predeclared case pool; selected path prefixes illustrate observed support changes, not effect estimation',
                pool_meta=p['meta'],reference=p['reference'],records=[r for r in p['records'] if r['worker_id'] in used],
                labels={w:labels[w] for w in used},teams=teams,
                path=next(p for p in req if p['path_id']==frame.iloc[0].path_id))
        # Reconstruct the user-prescribed pair directly; the saved fixture is an
        # output, not an undocumented prerequisite for reproduction.
        p=next(p for p in pools.values() if p['meta']['image']=='jtcxE69GiFV-26' and p['meta']['condition']=='manual')
        core=['W103','W104','W116','W128'];jtc=dict(core=core,pool=p,teams={})
        for worker in ('W113','W106'):
            t=fr.evaluate_one(p,sorted(core+[worker]),engine,models,full_state=True)
            t['full_state']=normalize(t['full_state']);jtc['teams'][worker]=t
        s.save(s.OUT/'JTC26_PREDECLARED.json.gz',jtc)
    p=jtc['pool'];labels=maps['manual',p['meta']['building']]
    used=set(jtc['core']+['W106','W113'])
    a=normalize(jtc['teams']['W113']['full_state']);b=normalize(jtc['teams']['W106']['full_state'])
    cases['JTC26_same_fine_class_third_vote']=dict(case_id='JTC26_same_fine_class_third_vote',
        selection='User-specified exact background and replacement, predeclared before research',pool_meta=p['meta'],reference=p['reference'],
        records=[r for r in p['records'] if r['worker_id'] in used],labels={w:labels[w] for w in used},
        teams=[dict(t,panel=w,coarse_counts=s.counts(t['member_workers'],labels,'coarse'),fine_counts=s.counts(t['member_workers'],labels,'fine')) for w,t in jtc['teams'].items()],
        mechanism=step(a,b,set(jtc['core'])),core=jtc['core'],
        interpretation='Both entrants belong to B-M01 and A2-A01 outside the target building; a local third vote changes fusion despite lower individual target quality.')
    s.save(s.OUT/'MECHANISM_CASES.json.gz',cases)
    panels=[]
    for name,c in cases.items():
        for t in c['teams']:
            st=t['full_state'];panels.append(dict(case_id=name,image=c['pool_meta']['image'],condition=c['pool_meta']['condition'],
                panel=t['panel'],team_key=t['team_key'],workers='|'.join(t['member_workers']),n=t['k'],
                coarse_counts=str(t['coarse_counts']),fine_counts=str(t['fine_counts']),nodes=t['nodes'],B8L2=t['B8L2'],D10=t['D10'],threshold=st['minimum_support']))
    s.csv(s.OUT/'MECHANISM_PANELS.csv',pd.DataFrame(panels))


if __name__=='__main__':main()
