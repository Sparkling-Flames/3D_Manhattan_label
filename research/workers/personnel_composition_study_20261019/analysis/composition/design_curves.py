"""Exact integer proportion curves along declared lines of the class simplex."""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
from fusion_runner import read,write,team_key
from design_compositions import load_labels,applicable,sample_cell

def apportion(n, weights, classes):
    total=sum(weights.values());raw={c:n*weights.get(c,0)/total for c in classes};counts={c:int(math.floor(v)) for c,v in raw.items()}
    left=n-sum(counts.values())
    order=sorted(classes,key=lambda c:(-(raw[c]-counts[c]),c))
    for c in order[:left]:counts[c]+=1
    assert sum(counts.values())==n
    return counts

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--split',type=Path,required=True)
    ap.add_argument('--labels',type=Path,action='append',required=True);ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    spec=read(a.spec);split=read(a.split);maps=load_labels(a.labels);phase=spec['phase'];requests=[];ledger=[];curve_index=[]
    pools=[p for p in read(a.snapshot)['images'] if p['meta']['building'] in split[phase+'_buildings']]
    for ms in spec['methods']:
      mid=ms['method_id'];dom=ms['domain'];mapping=maps[mid,dom];classes=sorted(set(mapping.values()))
      for p in pools:
        if not applicable(p,dom):continue
        groups={c:sorted(r['worker_id'] for r in p['records'] if mapping.get(r['worker_id'])==c) for c in classes}
        capacities={c:len(ws) for c,ws in groups.items()}
        for k in ms['sizes']:
          if k>sum(capacities.values()):continue
          vectors={};origins={}
          for curve in ms['curves']:
            target=curve['target_class'];background=curve['background_weights'];assert target not in background
            for target_n in range(k+1):
              counts=apportion(k-target_n,background,classes);counts[target]=target_n
              feasible=all(counts[c]<=capacities[c] for c in classes)
              comp='|'.join(f'{c}:{counts[c]}' for c in classes)
              curve_index.append(dict(method_id=mid,domain=dom,pool_id=p['pool_id'],k=k,curve_id=curve['curve_id'],target_class=target,
                target_n=target_n,target_fraction=target_n/k,composition=comp,feasible=feasible,counts=counts))
              if feasible:vectors[comp]=counts;origins.setdefault(comp,[]).append(curve['curve_id'])
          for comp,counts in sorted(vectors.items()):
            teams,possible,exhausted=sample_cell(groups,counts,ms.get('replicates',8),(spec['seed'],phase,p['pool_id'],mid,dom,k))
            for rep,ws in enumerate(teams):
              rid='curve__'+hashlib.sha256(json.dumps([phase,mid,dom,p['pool_id'],k,counts,rep,spec['seed']],sort_keys=True).encode()).hexdigest()[:24]
              requests.append(dict(request_id=rid,phase=phase,family='composition_grid',method_id=mid,domain=dom,pool_id=p['pool_id'],k=k,
                composition=comp,counts=counts,replicate=rep,worker_ids=list(ws),team_key=team_key(p['pool_id'],ws),curve_ids=origins[comp]))
            ledger.append(dict(method_id=mid,domain=dom,pool_id=p['pool_id'],k=k,composition=comp,available_class_sizes=capacities,
                possible_member_teams=str(possible),sampled_member_teams=len(teams),exhaustive_members=exhausted,
                feasible_compositions=len(vectors),selected_compositions=len(vectors),exhaustive_compositions=True,
                composition_universe='only declared 1D simplex lines; not entire K-dimensional simplex'))
    write(a.out,dict(spec=spec,requests=requests,ledger=ledger,curve_index=curve_index))
    print(json.dumps(dict(requests=len(requests),unique_teams=len({r['team_key'] for r in requests}),pools=len({r['pool_id'] for r in requests}),
        composition_cells=len(ledger),curve_positions=len(curve_index),infeasible_curve_positions=sum(not r['feasible'] for r in curve_index))))

if __name__=='__main__':main()
