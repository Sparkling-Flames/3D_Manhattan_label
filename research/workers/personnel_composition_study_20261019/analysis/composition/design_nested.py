"""Mechanistic size curves: fixed detail-role members plus nested common members.

These supplementary chains isolate actual additions around ceil(n/2) transitions;
they are not the main composition-replacement experiment or new independent images.
"""
import argparse,hashlib,json
from pathlib import Path
from fusion_runner import read,write,team_key
from design_screen import rng_for
from design_compositions import load_labels,applicable

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--split',type=Path,required=True);ap.add_argument('--labels',type=Path,action='append',required=True);ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    spec=read(a.spec);split=read(a.split);maps=load_labels(a.labels);phase=spec['phase'];requests=[];chains=[]
    pools=[p for p in read(a.snapshot)['images'] if p['meta']['building'] in split[phase+'_buildings']]
    for ms in spec['methods']:
      mid=ms['method_id'];dom=ms['domain'];mapping=maps[mid,dom];classes=sorted(set(mapping.values()))
      for p in pools:
        if not applicable(p,dom):continue
        high=sorted(r['worker_id'] for r in p['records'] if mapping.get(r['worker_id'])==ms['fixed_class'])
        common=sorted(r['worker_id'] for r in p['records'] if mapping.get(r['worker_id'])==ms['added_class'])
        for m in ms['fixed_sizes']:
          if m>len(high) or len(common)<m+1:continue
          for rep in range(ms['replicates']):
            rng=rng_for(spec['seed'],phase,mid,dom,p['pool_id'],m,rep)
            fixed=sorted(rng.choice(high,m,replace=False).tolist());order=rng.permutation(common).tolist()
            cid='nested__'+hashlib.sha256(json.dumps([spec['seed'],phase,mid,dom,p['pool_id'],m,rep]).encode()).hexdigest()[:24]
            points=[]
            for low_n in range(min(len(common),m+3)+1):
              ws=sorted(fixed+order[:low_n]);k=len(ws);counts={c:0 for c in classes};counts[ms['fixed_class']]=m;counts[ms['added_class']]=low_n
              tk=team_key(p['pool_id'],ws);points.append(dict(k=k,added_n=low_n,team_key=tk,worker_ids=ws,counts=counts))
              requests.append(dict(request_id=cid+'__n'+str(k),phase=phase,family='nested_addition',chain_id=cid,method_id=mid,domain=dom,pool_id=p['pool_id'],k=k,
                composition='|'.join(f'{c}:{v}' for c,v in counts.items()),counts=counts,worker_ids=ws,team_key=tk,replicate=rep,fixed_n=m))
            chains.append(dict(chain_id=cid,phase=phase,method_id=mid,domain=dom,pool_id=p['pool_id'],fixed_class=ms['fixed_class'],added_class=ms['added_class'],fixed_workers=fixed,added_worker_order=order,replicate=rep,fixed_n=m,points=points,
                threshold_comparison={'before_n':2*m,'after_n':2*m+1},possible_fixed_member_sets=__import__('math').comb(len(high),m)))
    write(a.out,dict(spec=spec,requests=requests,chains=chains))
    print(json.dumps(dict(requests=len(requests),unique_teams=len({r['team_key'] for r in requests}),chains=len(chains),pools=len({r['pool_id'] for r in requests}))))

if __name__=='__main__':main()
