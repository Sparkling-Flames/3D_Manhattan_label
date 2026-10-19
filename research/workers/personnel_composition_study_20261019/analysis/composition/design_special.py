"""Descriptive qualified special-condition fusions, without unsupported classes."""
import argparse,hashlib,json,math
from pathlib import Path
from fusion_runner import read,write,team_key
from design_screen import rng_for

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();rows=[];ledger=[]
    for p in read(a.snapshot)['images']:
      if not p['meta']['layer'].startswith('special_'):continue
      ws=sorted(r['worker_id'] for r in p['records'])
      for k in sorted({3,5,9,13,17,len(ws)}):
        if k>len(ws):continue
        want=min(12,math.comb(len(ws),k));rng=rng_for(2026101908,p['pool_id'],k);teams=set()
        while len(teams)<want:teams.add(tuple(sorted(rng.choice(ws,k,replace=False).tolist())))
        for rep,team in enumerate(sorted(teams)):
          key=team_key(p['pool_id'],team)
          rows.append(dict(request_id='special__'+hashlib.sha256(json.dumps([key,rep]).encode()).hexdigest()[:24],phase='special_descriptive',family='special_descriptive',pool_id=p['pool_id'],k=k,worker_ids=list(team),team_key=key))
        ledger.append(dict(pool_id=p['pool_id'],k=k,possible_teams=str(math.comb(len(ws),k)),sampled_teams=len(teams),exhaustive_teams=len(teams)==math.comb(len(ws),k),reason='no supported historical own-condition personnel classes'))
    write(a.out,dict(spec={'seed':2026101908,'meaning':'qualified special-only descriptive fusions; not pooled with ordinary or category evidence'},requests=rows,ledger=ledger))
    print(json.dumps(dict(requests=len(rows),pools=len({r['pool_id'] for r in rows}))))

if __name__=='__main__':main()
