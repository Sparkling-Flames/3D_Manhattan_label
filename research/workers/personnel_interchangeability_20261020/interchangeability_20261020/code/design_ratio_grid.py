"""Pure/mixed composition census at declared n, with finite member resampling.

Three fixed routes and a metadata-selected, building/difficulty-spread discovery
panel. Enumerates all feasible count vectors at n=3..9, then binary proportion
landmarks at each n=10..17. Enumerates concrete teams only when <=4 exist;
otherwise samples four distinct actual teams. No outcome is read.
"""
from __future__ import annotations
import argparse,collections,datetime,itertools,math,random,sys
from pathlib import Path
from design_history_panel import read,write,digest,team_key
from design_blocks import labels_from,counts
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'analysis/composition'))
from design_compositions import vectors

SEED=2026102019
METHODS=[
 ('F20_newCommon_Full_balanced_K3','all',['new']),
 ('F20_highQ23_T_qK2','all',['new','v1']),
 ('R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1','ordinary_new',['new'])]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--split',type=Path,required=True)
 ap.add_argument('--labels',type=Path,action='append',required=True);ap.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();split=read(a.split);maps=labels_from(a.labels)
 pools=[p for p in read(a.snapshot)['images'] if p['meta']['building'] in split['discovery_buildings'] and p['meta']['layer']=='ordinary_manual']
 strata=collections.defaultdict(list)
 for p in pools:strata[p['meta']['building'],p['meta']['difficulty']].append(p)
 chosen=[]
 for key,ps in sorted(strata.items()):chosen.append(min(ps,key=lambda p:digest([SEED,key,p['pool_id']])))
 events=[];requests={};ledger=[]
 for mid,domain,origins in METHODS:
  mapping=maps[mid,domain];classes=sorted(set(mapping.values()))
  for p in chosen:
   ws=sorted(r['worker_id'] for r in p['records'] if r['worker_id'] in mapping and r['origin'] in origins)
   groups={c:[w for w in ws if mapping[w]==c] for c in classes};caps=tuple(len(x) for x in groups.values())
   nrange=range(3,min(17 if len(classes)==2 else 9,len(ws))+1)
   for n in nrange:
    choices=list(vectors(caps,n))
    if n>=10:
     landmarks={0,n,n//4,n//2,(3*n)//4}
     choices=[v for v in choices if v[0] in landmarks]
    for vector in choices:
     cid='RG20_'+digest([SEED,mid,domain,p['pool_id'],n,vector])[:22]
     total=math.prod(math.comb(cap,count) for cap,count in zip(caps,vector))
     if total<=4:
      teams=[sorted(sum((list(z) for z in parts),[])) for parts in itertools.product(*[list(itertools.combinations(groups[c],cnt)) for c,cnt in zip(classes,vector)])]
      sampling='all_concrete_teams'
     else:
      rng=random.Random(int(digest([SEED,cid])[:16],16));seen=set();teams=[]
      while len(teams)<4:
       team=tuple(sorted(sum((rng.sample(groups[c],cnt) for c,cnt in zip(classes,vector)),[])))
       if team not in seen:seen.add(team);teams.append(list(team))
      sampling='four_distinct_uniform_concrete_teams'
     for rep,workers in enumerate(teams):
      tk=team_key(p['pool_id'],workers);requests.setdefault(tk,dict(request_id=tk,pool_id=p['pool_id'],k=n,worker_ids=workers))
      events.append(dict(event_id=cid+'_'+str(rep),composition_id=cid,phase='discovery',method_id=mid,domain=domain,
       pool_id=p['pool_id'],image=p['meta']['image'],building=p['meta']['building'],difficulty=p['meta']['difficulty'],
       layer=p['meta']['layer'],condition=p['meta']['condition'],reference_id=p['meta']['reference_id'],n=n,
       class_counts=counts(workers,mapping),pure=sum(x>0 for x in vector)==1,replicate=rep,team_key=tk,workers=workers,
       concrete_population=str(total),sampling=sampling,vector_coverage='all_feasible_count_vectors' if n<10 else 'binary_integer_quarter_half_endpoints'))
    ledger.append(dict(method_id=mid,domain=domain,pool_id=p['pool_id'],n=n,class_capacities=dict(zip(classes,caps)),
       feasible_vectors_all=len(list(vectors(caps,n))),tested_vectors=len(choices),
       vector_coverage='all' if n<10 else 'quarter_half_and_endpoints'))
 spec=dict(schema='pure_mixed_ratio_grid_v1',seed=SEED,registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  methods=METHODS,selection='Three fixed user-priority/history-risk and discovery-common-panel routes. One metadata-hash image per discovery building/difficulty stratum, no fusion outcomes used to pick images.',
  chosen_pool_ids=sorted(p['pool_id'] for p in chosen),replicates=4,
  estimands='Actual quality, structural summaries, time and within-composition whole-team member variation. Mixture quality compared to same-n supported pure classes; no prediction-score replacement. This resampling panel does not claim all actual member turnovers equal; each pair turnover is retained.',
  search='All feasible class-count vectors n3..9. Binary n10..17 integer-quarter/half/endpoints. At most4 distinct sampled teams per vector, exact enumeration only when finite count<=4. Other images and concrete teams are not called exhaustively searched.')
 write(a.out,dict(spec=spec,events=events,requests=list(requests.values()),ledger=ledger))
 print(dict(team_rows=len(events),unique_teams=len(requests),compositions=len({e['composition_id'] for e in events}),
   pools=len(chosen),buildings=len({p['meta']['building'] for p in chosen}),n=sorted({e['n'] for e in events})))

if __name__=='__main__':main()
