"""Uniform class-independent discovery panel, fixed before any candidate ranking."""
import argparse,hashlib,itertools,json,math
from pathlib import Path
import numpy as np
from fusion_runner import read,write,team_key

def rng_for(*parts):
    seed=int(hashlib.sha256('|'.join(map(str,parts)).encode()).hexdigest()[:16],16)
    return np.random.default_rng(seed)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--split',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    split=read(a.split);pools=read(a.snapshot)['images'];requests=[];ledger=[]
    sizes=[3,4,5,6,7,9,13,17,21,25,29,33];reps=24
    for p in pools:
        if p['meta']['building'] not in split['discovery_buildings'] or p['meta']['layer']!='ordinary_manual':continue
        ws=sorted(r['worker_id'] for r in p['records']);n=len(ws)
        for k in sorted(set([x for x in sizes if x<=n]+[n])):
            possibilities=math.comb(n,k);num=min(reps,possibilities);rng=rng_for(2026101902,p['pool_id'],k);teams=set()
            if possibilities<=reps:teams=set(itertools.combinations(ws,k))
            else:
                while len(teams)<num:teams.add(tuple(sorted(rng.choice(ws,k,replace=False).tolist())))
            for j,t in enumerate(sorted(teams)):
                requests.append(dict(request_id=f'screen__{p["pool_id"]}__n{k}__r{j}',phase='discovery',family='uniform_screen',pool_id=p['pool_id'],k=k,worker_ids=list(t),replicate=j,team_key=team_key(p['pool_id'],t)))
            ledger.append(dict(pool_id=p['pool_id'],k=k,available_workers=n,total_possible_teams=str(possibilities),sampled_teams=len(teams),exhaustive_teams=possibilities<=reps))
    write(a.out,dict(seed=2026101902,sizes=sizes,replicates=reps,requests=requests,ledger=ledger,selection='all discovery ordinary pools, uniform sampling without score/class conditioning, exhaustive when <=24 possible teams'))
    print(json.dumps(dict(requests=len(requests),pools=len(set(r['pool_id'] for r in requests)),unique_teams=len(set(r['team_key'] for r in requests)),cells=len(ledger),exhaustive_cells=sum(r['exhaustive_teams'] for r in ledger))))

if __name__=='__main__':main()
