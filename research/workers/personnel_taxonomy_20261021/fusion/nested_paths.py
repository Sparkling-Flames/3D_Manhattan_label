"""Complete integer member-count paths for predeclared structural-type cases."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
import time
import pandas as pd
import study as s

PREDECLARED_MANUAL=['jtcxE69GiFV-26','UwV83HsGsw3-22','q9vSo1VnCiC-30','B6ByNegPMKs-22']


def prepare():
    pools=s.read(s.FUSION/'INPUT_SNAPSHOT.json.gz')['images'];maps=s.label_maps()
    selected=[p for p in pools if p['meta']['condition']=='manual' and p['meta']['image'] in PREDECLARED_MANUAL]
    # Semi easy/medium/hard representatives and one doorway pool chosen only by metadata.
    for layer in ['ordinary_semi','doorway_manual']:
        groups=defaultdict(list)
        for p in pools:
            if p['meta']['layer']==layer and len(p['records'])>=15:groups[p['meta']['difficulty']].append(p)
        for group in groups.values():selected.append(min(group,key=lambda p:s.digest(p['pool_id'])))
    paths=[];unavailable=[]
    for p in selected:
        meta=p['meta'];labels=maps.get((meta['condition'],meta['building']),{})
        available=[r['worker_id'] for r in p['records'] if r['worker_id'] in labels]
        cs=sorted({labels[w]['coarse'] for w in available})
        for c in cs:
            for d in cs:
                if c==d:continue
                blocks,reason=s.draw_blocks(p,labels,'coarse',c,d,5,2,910)
                if blocks is None:
                    unavailable.append(dict(pool_id=p['pool_id'],c=c,d=d,reason=reason));continue
                remainder=sorted(set(available)-set(blocks['A_block']+blocks['B_block']+blocks['C_block']+blocks['core_workers']))
                rr=s.rng(['nested',p['pool_id'],c,d]);rr.shuffle(remainder)
                core_order=blocks['core_workers']+remainder
                path_id='PATH_'+s.digest([p['pool_id'],c,d,core_order,blocks])[:20]
                events=[]
                for core_n in range(3,len(core_order)+1):
                    core=sorted(core_order[:core_n]);e=dict(pool_id=p['pool_id'],image=meta['image'],building=meta['building'],
                        condition=meta['condition'],layer=meta['layer'],difficulty=meta['difficulty'],path_id=path_id,
                        design_tier='coarse',outgoing_class=c,incoming_class=d,n=core_n+2,m=2,core_workers=core,
                        A_workers=sorted(core+blocks['A_block']),B_workers=sorted(core+blocks['B_block']),C_workers=sorted(core+blocks['C_block']),
                        added_worker=core_order[core_n-1] if core_n>3 else None)
                    e['event_id']=path_id+'__n'+str(e['n']);s.validate(e,labels);events.append(e)
                paths.append(dict(path_id=path_id,pool_id=p['pool_id'],outgoing_class=c,incoming_class=d,
                                  core_order=core_order,blocks={a:blocks[a+'_block'] for a in 'ABC'},events=events))
    s.save(s.OUT/'NESTED_REQUESTS.json.gz',dict(paths=paths,unavailable=unavailable,
        design='m2 fixed pure blocks; all integer n from 5 to shared-pool capacity; same entrant in A/B/C at every increment',
        panel='four previously named Manual mechanisms; Semi one hash-selected pool per difficulty; doorway one hash-selected pool',
        labels='Frozen B coarse target-building-out labels, no outcome selection',
        selected_pools=[p['meta'] for p in selected]))
    print('Nested paths',len(paths),'ABC prefixes',sum(len(p['events']) for p in paths),flush=True)


def run_path(path,pool,labels):
    fe,fr,sg,corner,step,normalize=s.setup_engine();teams={};states={};rows=[];steps=[]
    previous=None
    with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
        for e in path['events']:
            armstates={};keys={};row=dict(e)
            for a in 'ABC':
                key=fr.team_key(pool['pool_id'],e[a+'_workers']);keys[a]=key
                t=fr.evaluate_one(pool,e[a+'_workers'],engine,models,full_state=True)
                st=normalize(t.pop('full_state'));armstates[a]=st
                t['type_counts']={tier:s.counts(e[a+'_workers'],labels,tier) for tier in ('coarse','fine')}
                teams[key]=t;row[a+'_team_key']=key
                for f in ['nodes','B8L2','D10','minimum_support','complete_evaluable','ref_node_recall_5','ref_edge_recall_5']:
                    row[a+'_'+f]=t.get(f)
                if previous:
                    old=previous['states'][a];oldkey=previous['keys'][a];ot=teams[oldkey]
                    change=step(old,st,set(ot['member_workers']));change.pop('group_components')
                    steps.append(dict(path_id=path['path_id'],pool_id=pool['pool_id'],image=e['image'],condition=e['condition'],
                        layer=e['layer'],difficulty=e['difficulty'],arm=a,n_from=e['n']-1,n_to=e['n'],added_worker=e['added_worker'],
                        added_class=labels[e['added_worker']]['coarse'],team_before=oldkey,team_after=key,
                        nodes_before=ot['nodes'],nodes_after=t['nodes'],B8L2_before=ot['B8L2'],B8L2_after=t['B8L2'],
                        D10_before=ot['D10'],D10_after=t['D10'],threshold_before=old['minimum_support'],threshold_after=st['minimum_support'],**change))
            for a,name in [('B','within'),('C','cross')]:
                row.update({name+'_'+k:v for k,v in s.compare(teams[keys['A']],teams[keys[a]],sg,corner).items()})
            rows.append(row);previous=dict(states=armstates,keys=keys)
    target=s.OUT/'nested_runtime'/(path['path_id']+'.json.gz')
    s.save(target,dict(teams=teams,events=rows,steps=steps))
    return dict(path_id=path['path_id'],teams=len(teams),events=len(rows),steps=len(steps))


def run(jobs):
    pools={p['pool_id']:p for p in s.read(s.FUSION/'INPUT_SNAPSHOT.json.gz')['images']};maps=s.label_maps()
    req=s.read(s.OUT/'NESTED_REQUESTS.json.gz');receipts=[]
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        fs=[]
        for path in req['paths']:
            p=pools[path['pool_id']];fs.append(ex.submit(run_path,path,p,maps[p['meta']['condition'],p['meta']['building']]))
        for f in as_completed(fs):
            receipts.append(f.result());print(receipts[-1],flush=True)
    teams={};events=[];steps=[]
    for p in req['paths']:
        result=s.read(s.OUT/'nested_runtime'/(p['path_id']+'.json.gz'));teams.update(result['teams']);events.extend(result['events']);steps.extend(result['steps'])
    s.save(s.OUT/'NESTED_TEAMS.json.gz',teams);s.csv(s.OUT/'NESTED_EVENTS.csv',pd.DataFrame(events));s.csv(s.OUT/'NESTED_STEPS.csv',pd.DataFrame(steps))
    s.save(s.OUT/'NESTED_RECEIPT.json',dict(paths=receipts,distinct_teams=len(teams),events=len(events),steps=len(steps),
        aggregation='These fixed predeclared paths illustrate mechanisms; they are not random population count curves'))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','run']);ap.add_argument('--jobs',type=int,default=4);a=ap.parse_args()
    prepare() if a.stage=='prepare' else run(a.jobs)
