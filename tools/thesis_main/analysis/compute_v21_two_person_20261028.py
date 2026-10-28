"""Supplement the saved natural paths with two-person MV50 outcomes."""
import argparse
import gzip
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import pandas as pd
from .rebuild_v21_20261028 import ROOT, OUT, read
from .fuse_v21_new_pools_20261028 import adapter
from .prepare_v21_natural_inputs_20261028 import BASE, PRIOR, EXT

TARGET = OUT / 'two_person_natural256'


def prepare():
    pools = {p['pool_id']: p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    curves = pd.read_csv(OUT/'natural_results/HYBRID_DISPLAY_CURVES.csv.gz', usecols=['pool_id','layer','pool_n'])
    ids = set(curves.loc[curves.layer.isin(['ordinary_manual','doorway_manual']) & curves.pool_n.ge(3), 'pool_id'])
    links = []
    for path, labels in [(BASE/'results/PREFIX_TEAM_LINKS.csv.gz', {'': 'old24'}),
                         (PRIOR/'design/NEW_PREFIX_TEAM_LINKS.csv.gz', {'balanced_new24': 'prior_new24'})]:
        for d in pd.read_csv(path, chunksize=100000, low_memory=False):
            d = d[d.pool_id.isin(ids) & d.policy.eq('natural_random') & d.k.le(3)].copy()
            if 'batch' in d: d = d[d.batch.isin(labels)]; d['stratum'] = d.batch.map(labels)
            else: d['stratum'] = labels['']
            links.append(d[['pool_id','path_id','k','team_key','entrant_worker','stratum']])
    for stage in (1, 2):
        for pid in ids:
            path = EXT/f'design26/links_by_pool/stage{stage}'/(pid+'.csv.gz')
            if path.exists():
                d = pd.read_csv(path, usecols=['pool_id','path_id','k','team_key','entrant_worker','policy'])
                d = d[d.policy.eq('natural_random') & d.k.le(3)].copy()
                d['stratum'] = 'new104A' if stage == 1 else 'new104B'
                links.append(d.drop(columns='policy'))
    data = pd.concat(links, ignore_index=True)
    added = ids - set(data.pool_id)
    new_links = []
    for pid in sorted(added):
        path = OUT/'new_space_natural256'/pid/'DESIGN.json'
        plan = read(path)
        for item in plan['paths']:
            for k in (1,2,3):
                new_links.append(dict(pool_id=pid, path_id=pid+'__new256_'+str(item['path_index']), k=k, team_key='', entrant_worker=item['workers'][k-1], stratum='new_space256'))
    if new_links: data = pd.concat([data, pd.DataFrame(new_links)], ignore_index=True)
    first = data[data.k.eq(1)][['pool_id','path_id','stratum','entrant_worker','team_key']].rename(columns={'entrant_worker':'first','team_key':'team_key_1'})
    third = data[data.k.eq(3)][['pool_id','path_id','stratum','entrant_worker','team_key']].rename(columns={'entrant_worker':'third','team_key':'team_key_3'})
    second = data[data.k.eq(2)].merge(first, on=['pool_id','path_id','stratum'], validate='one_to_one')
    second = second.merge(third, on=['pool_id','path_id','stratum'], validate='one_to_one')
    assert second.groupby('pool_id').size().eq(256).all(), second.groupby('pool_id').size().value_counts().to_dict()
    assert set(second.pool_id) == ids
    assert (second['first'] != second.entrant_worker).all() and (second['third'] != second.entrant_worker).all() and (second['third'] != second['first']).all()
    TARGET.mkdir(parents=True,exist_ok=True)
    second.to_csv(TARGET/'PATH_LINKS.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    return [(pools[pid], g.to_dict('records')) for pid,g in second.groupby('pool_id',sort=True)]


def compute(payload):
    pool, links = payload
    pid = pool['pool_id']; target = TARGET/'pools'/(pid+'.json.gz')
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        with gzip.open(target,'rt',encoding='utf8') as f: saved=json.load(f)
        if saved['complete']: return saved['summary']
    native=adapter()
    from tools.thesis_main.analysis.ring_correspondence_20261007 import build
    from tools.thesis_main.analysis import wall_consensus_quality_20261015 as quality
    with native.Engine(full_state=False) as engine:
        original_fuse = engine.fe.fuse
        classify = quality.classify_output
        engine.fe.fuse = lambda records,gap: {'automatic': build(records,gap=gap)}
        quality.classify_output = lambda k,nodes,connected,full: classify(3 if k==2 else k,nodes,connected,full)
        try:
            teams = {}
            for link in links:
                workers=sorted([link['first'],link['entrant_worker']]); key=engine.fr.team_key(pid,workers)
                assert not link['team_key'] or link['team_key']==key
                if key not in teams:
                    row=engine.evaluate(pool,workers)
                    assert row['team_key']==key and row['k']==2
                    supports=row.get('node_supports',[]); assert all(x in (1,2) for x in supports)
                    row['single_support_nodes']=supports.count(1);row['joint_support_nodes']=supports.count(2)
                    row['single_support_fraction']=supports.count(1)/len(supports) if supports else None
                    row['policy_deferred']=False
                    teams[key]=row
        finally:
            engine.fe.fuse=original_fuse; quality.classify_output=classify
    summary=dict(pool_id=pid,paths=len(links),unique_teams=len(teams),scored=sum(r.get('B8L2') is not None for r in teams.values()))
    temp=target.with_suffix('.writing')
    with gzip.open(temp,'wt',encoding='utf8') as f:json.dump(dict(complete=True,summary=summary,teams=list(teams.values())),f,ensure_ascii=False,allow_nan=False)
    temp.replace(target)
    return summary


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pool');ap.add_argument('--jobs',type=int,default=2);a=ap.parse_args()
    payloads=prepare()
    if a.pool: payloads=[p for p in payloads if p[0]['pool_id']==a.pool];assert payloads
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for i,result in enumerate(ex.map(compute,payloads),1): print(i,len(payloads),json.dumps(result),flush=True)


if __name__=='__main__':main()
