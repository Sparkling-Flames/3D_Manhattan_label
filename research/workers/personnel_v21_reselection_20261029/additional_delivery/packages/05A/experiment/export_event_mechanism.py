"""Materialize a few selected exact ABC events with source answers and vote state.

This repeats only the selected endpoints to obtain internal traces, checking
their scalar values against the saved endpoint table. It does not fit classes.
"""
import argparse,json,math
from pathlib import Path
import pandas as pd
from capacity_space import read_json,read_labels,write_csv,canonical_hash
from register_adaptive import members,write_json
from benchmark_engine import load_engine

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--pools',nargs='+',required=True)
    p.add_argument('--events',required=True);p.add_argument('--event-ids',nargs='+',required=True);p.add_argument('--scalars',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True);pools={p['pool_id']:p for fn in a.pools for p in read_json(fn)['images']}
    selected=[r for r in read_labels(a.events) if r['event_id'] in set(a.event_ids)];assert {r['event_id'] for r in selected}==set(a.event_ids)
    old=pd.read_csv(a.scalars,low_memory=False).set_index('team_key');native=load_engine(Path(a.repo));index=[];votes=[];checks=[]
    for e in selected:
        pool=pools[e['pool_id']];rows={};own={r['object_id']:r['worker_id'] for r in pool['records']}
        with native.Engine(full_state=True) as engine:
            for arm in ['A','B','C']:
                row=engine.evaluate(pool,members(e[arm+'_members']));g=row.get('geometry')
                if g is not None:
                    score=engine.scorecache.get(engine.fr.digest([row['k']==2,row.get('nodes'),g]))
                    if score:row.update(score)
                key=e[arm+'_team_key'];assert row['team_key']==key;before=old.loc[key];diffs={}
                for field in ['B8L2','D10','nodes','minimum_support','geometry_area_h2','height_mean_h']:
                    x,y=before.get(field),row.get(field)
                    if pd.isna(x):assert y is None or pd.isna(y),(key,field,x,y)
                    else:assert y is not None and abs(float(x)-float(y))<1e-8,(key,field,x,y);diffs[field]=abs(float(x)-float(y))
                checks.append(dict(event_id=e['event_id'],arm=arm,team_key=key,maximum_scalar_difference=max(diffs.values(),default=0.)))
                row.update(data_release='v2.1',underlying_data_version='v2.1',input_pool_sha256=canonical_hash(pool),trace_only_refusion=True)
                rows[arm]=native.gs.clean(row)
                for group in (row.get('full_state') or {}).get('identity_groups',[]):
                    g=dict(event_id=e['event_id'],arm=arm,team_key=key,minimum_support=row.get('minimum_support'),**group)
                    g['member_workers']='|'.join(sorted({own.get(m.get('id'),'unknown') for m in group.get('members',[])}))
                    for k,v in list(g.items()):
                        if isinstance(v,(dict,list)):g[k]=json.dumps(v,ensure_ascii=False,separators=(',',':'))
                    votes.append(g)
        case=dict(event=e,pool=pool,arms=rows,reference=pool['reference'],source='Frozen v2.1 pool; exact registered participants and original point order; current native vote/connection trace')
        name=e['event_id']+'.json.gz';write_json(out/name,native.gs.clean(case));index.append(dict(event_id=e['event_id'],pool_id=e['pool_id'],method=e['method'],n=e['n'],m=e['m'],file=name))
    write_csv(out/'CASE_INDEX.csv',index);write_csv(out/'VOTE_GROUPS.csv.gz',votes);write_json(out/'TRACE_SCALAR_PARITY.json',checks)
    print(json.dumps(dict(cases=len(index),arms=len(checks),vote_groups=len(votes))),flush=True)

if __name__=='__main__':main()
