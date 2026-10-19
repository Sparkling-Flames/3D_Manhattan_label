"""Materialize own-condition frozen rules as exact reproducible member requests."""
import argparse,hashlib,json
from pathlib import Path
from fusion_runner import read,write,team_key
from design_compositions import sample_cell

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--phase',choices=['discovery','validation'],required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    spec=read(a.spec);requests=[];ledger=[]
    for rule in spec['rules']:
      if rule['stage']!=a.phase:continue
      groups=rule['class_members'];mid=rule['method_id'];dom=rule['domain'];pid=rule['pool_id']
      for ns in rule['n_rules']:
        k=ns['n']
        for cs in ns['compositions']:
          counts=dict(zip(rule['class_order'],cs['counts']));comp='|'.join(f'{c}:{n}' for c,n in counts.items())
          teams,possible,exhausted=sample_cell(groups,counts,cs['sample_teams'],(spec['seed'],a.phase,pid,mid,dom,k))
          assert possible==int(cs['possible_distinct_teams']) and len(teams)==cs['sample_teams']
          for rep,ws in enumerate(teams):
            rid='condition__'+hashlib.sha256(json.dumps([a.phase,mid,dom,pid,k,cs['counts'],rep,spec['seed']]).encode()).hexdigest()[:24]
            requests.append(dict(request_id=rid,phase=a.phase,family='composition_grid',method_id=mid,domain=dom,pool_id=pid,k=k,
                composition=comp,counts=counts,replicate=rep,worker_ids=list(ws),team_key=team_key(pid,ws)))
          ledger.append(dict(method_id=mid,domain=dom,pool_id=pid,k=k,composition=comp,available_class_sizes=dict(zip(rule['class_order'],rule['available_class_counts'])),
                possible_member_teams=str(possible),sampled_member_teams=len(teams),exhaustive_members=exhausted,feasible_compositions=len(ns['compositions']),
                selected_compositions=len(ns['compositions']),exhaustive_compositions=True))
    write(a.out,dict(spec=dict(phase=a.phase,seed=spec['seed'],source_spec_sha256=hashlib.sha256(a.spec.read_bytes()).hexdigest(),source_spec=str(a.spec)),requests=requests,ledger=ledger))
    print(json.dumps(dict(requests=len(requests),unique_teams=len({r['team_key'] for r in requests}),pools=len({r['pool_id'] for r in requests}),composition_cells=len(ledger))))

if __name__=='__main__':main()
