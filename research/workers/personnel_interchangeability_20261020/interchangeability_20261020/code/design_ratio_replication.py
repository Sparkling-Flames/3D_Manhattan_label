"""Replay five frozen composition hypotheses on novel member draws and buildings.

No outcomes are read. Old grid requests are used only to exclude its concrete
members in the same-image replication. A team new to this grid may have occurred
in another historic experiment; this is not a new-person or external test.
"""
from __future__ import annotations
import argparse,collections,hashlib,itertools,math,random
from pathlib import Path
from design_history_panel import read,write,digest,team_key
from design_blocks import labels_from,counts

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True)
 ap.add_argument('--split',type=Path,required=True);ap.add_argument('--labels',type=Path,action='append',required=True)
 ap.add_argument('--freeze',type=Path,required=True);ap.add_argument('--old-requests',type=Path,required=True)
 ap.add_argument('--phase',choices=['replication','assessment'],required=True);ap.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();spec=read(a.freeze);old=read(a.old_requests);maps=labels_from(a.labels);split=read(a.split)
 allp=read(a.snapshot)['images']
 if a.phase=='replication':pools=[p for p in allp if p['pool_id'] in old['spec']['chosen_pool_ids']]
 else:pools=[p for p in allp if p['meta']['building'] in split['validation_buildings'] and p['meta']['layer']=='ordinary_manual']
 old_keys=collections.defaultdict(set)
 for e in old['events']:
  key=(e['method_id'],e['domain'],e['pool_id'],e['n'],tuple(sorted(e['class_counts'].items())))
  old_keys[key].add(e['team_key'])
 requests={};events=[];ledger=[];links=[];done={}
 for rule in spec['rules']:
  mid,domain=rule['method_id'],rule['domain'];mapping=maps[mid,domain];n=rule['n']
  vectors=[rule['mixture']]+[{c:n} for c in sorted(rule['mixture'])]
  for p in sorted(pools,key=lambda p:p['pool_id']):
   ws=sorted(r['worker_id'] for r in p['records'] if r['worker_id'] in mapping and r['origin'] in rule['allowed_origins'])
   groups={c:[w for w in ws if mapping[w]==c] for c in sorted(set(mapping.values()))}
   capacities={c:len(w) for c,w in groups.items()};missing=[v for v in vectors if any(capacities.get(c,0)<q for c,q in v.items())]
   base=dict(rule_id=rule['rule_id'],phase=a.phase,method_id=mid,domain=domain,pool_id=p['pool_id'],image=p['meta']['image'],building=p['meta']['building'],n=n,class_capacities=capacities)
   if missing:
    ledger.append(dict(base,status='insufficient_mixture_or_constituent_pure_capacity',unsupported_vectors=missing));continue
   cids=[];exhausted=[]
   for vector in vectors:
    v=tuple(sorted(vector.items()));key=(mid,domain,p['pool_id'],n,v)
    cid='RP20_'+digest([spec['seed'],a.phase,key])[:22];cids.append(cid)
    if cid in done:
     if not done[cid]:exhausted.append(cid)
     continue
    total=math.prod(math.comb(capacities[c],q) for c,q in v)
    excluded=old_keys[key] if a.phase=='replication' else set()
    available=total-len(excluded);target=min(spec['draws_per_composition'],available)
    rng=random.Random(int(digest([spec['seed'],a.phase,key])[:16],16));teams=[]
    if target and available<=spec['draws_per_composition']:
     for parts in itertools.product(*[itertools.combinations(groups[c],q) for c,q in v]):
      workers=sorted(sum((list(x) for x in parts),[]))
      if team_key(p['pool_id'],workers) not in excluded:teams.append(workers)
     sampling='all_novel_concrete_teams' if excluded else 'all_concrete_teams'
    else:
     seen=set(excluded)
     while len(teams)<target:
      workers=sorted(sum((rng.sample(groups[c],q) for c,q in v),[]));tk=team_key(p['pool_id'],workers)
      if tk not in seen:seen.add(tk);teams.append(workers)
     sampling='sixteen_distinct_uniform_novel_teams' if excluded else 'sixteen_distinct_uniform_teams'
    assert len(teams)==target
    done[cid]=target
    if not target:exhausted.append(cid)
    for rep,workers in enumerate(teams):
     assert counts(workers,mapping)==dict(v)
     tk=team_key(p['pool_id'],workers);assert tk not in excluded
     requests.setdefault(tk,dict(request_id=tk,pool_id=p['pool_id'],k=n,worker_ids=workers))
     events.append(dict(event_id=cid+'_'+str(rep),composition_id=cid,phase=a.phase,method_id=mid,domain=domain,
      pool_id=p['pool_id'],image=p['meta']['image'],building=p['meta']['building'],difficulty=p['meta']['difficulty'],
      layer=p['meta']['layer'],condition=p['meta']['condition'],reference_id=p['meta']['reference_id'],n=n,
      class_counts=dict(v),pure=len(v)==1,replicate=rep,team_key=tk,workers=workers,
      concrete_population=str(total),excluded_old_grid_teams=len(excluded),available_novel_population=str(available),sampling=sampling,
      vector_coverage='frozen_five_mixtures_and_each_constituent_pure'))
   ledger.append(dict(base,status='new_member_population_exhausted' if exhausted else 'complete_supported_comparison',composition_ids=cids,empty_composition_ids=exhausted))
   links.append(dict(base,mixture_composition_id=cids[0],pure_composition_ids=cids[1:],all_compositions_have_teams=not exhausted))
 write(a.out,dict(schema='frozen_ratio_replication_requests_v1',spec=spec,phase=a.phase,
  input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [a.snapshot,a.split,a.freeze,a.old_requests,*a.labels]},
  events=events,requests=list(requests.values()),ledger=ledger,rule_links=links))
 print(dict(phase=a.phase,team_rows=len(events),unique_teams=len(requests),compositions=len({e['composition_id'] for e in events}),
  images=len({e['image'] for e in events}),pools=len({e['pool_id'] for e in events}),buildings=len({e['building'] for e in events}),
  ledger_status=dict(collections.Counter(x['status'] for x in ledger))))

if __name__=='__main__':main()
