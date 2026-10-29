"""Explicit direct AC tail where a legal independent same-class B may not fit.

No B is manufactured. Exact members, actual m, class-seat change and background
are retained. These events must not enter within-vs-cross amplitude estimates.
"""
from __future__ import annotations
import argparse,collections,hashlib,itertools,json
from pathlib import Path
from capacity_space import read_json,read_labels,capacities,canonical_hash,exact_counts,write_csv
from register_adaptive import key,members,class_vector,rng,write_json,partition_id


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pools',nargs='+',required=True);ap.add_argument('--labels',required=True)
 ap.add_argument('--cells',required=True);ap.add_argument('--output',required=True);ap.add_argument('--blocks',type=int,default=3)
 ap.add_argument('--backgrounds',type=int,default=2);ap.add_argument('--background-levels',default='low,high');ap.add_argument('--reuse-events',nargs='*',default=[]);ap.add_argument('--selection-phase',default='post_global_screen_direct_AC_tail')
 a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 pools={p['pool_id']:p for fn in a.pools for p in read_json(fn)['images']};labels=read_labels(a.labels);cells=read_labels(a.cells)
 L=collections.defaultdict(list)
 for r in labels:L[r['method'],r['heldout_building']].append(r)
 old=collections.defaultdict(list)
 for fn in a.reuse_events:
  for r in read_labels(fn):old[r['pool_id'],int(float(r['n'])),int(float(r['m']))].append(r)
 events={};requests={};coverage=[];conditionlinks=[]
 frozen=dict(labels_sha256=hashlib.sha256(Path(a.labels).read_bytes()).hexdigest(),cells_sha256=hashlib.sha256(Path(a.cells).read_bytes()).hexdigest(),
  blocks=a.blocks,backgrounds=a.backgrounds,background_levels=a.background_levels,score_blind_registration=True,
  data_release='v2.1',source_commit='a476461d7ede8db95da43de4139e612c05e618bc',design='direct_AC_no_same_class_B',selection_phase=a.selection_phase)
 write_json(out/'FROZEN_REGISTRATION_INPUTS.json',frozen)
 for cell in cells:
  pid=cell['pool_id'];p=pools[pid];meta=p['meta'];n,m=int(cell['n']),int(cell['m']);s,t=cell['source_class'],cell['target_class']
  groups=capacities(p,L[cell['method'],meta['building']]);S,T=set(groups[s]),set(groups[t]);poolws=set(r['worker_id'] for r in p['records'])
  counts=exact_counts(len(poolws),len(S),len(T),n,m);assert counts['direct_AC'] and n>=3
  blocks=[];seen=set()
  for er in old[pid,n,m]:
   x,z=members(er.get('X')),members(er.get('Z'))
   if len(x)!=m or len(z)!=m or not set(x)<=S or not set(z)<=T:continue
   sig=tuple(x),tuple(z)
   if sig not in seen:blocks.append((x,z,'existing_XZ_revalidated',er.get('event_id','')));seen.add(sig)
   if len(blocks)>=a.blocks:break
  rr=rng('directAC_XZ',pid,sorted(S),sorted(T),m)
  for attempt in range(100*a.blocks):
   if len(blocks)>=a.blocks:break
   x,z=sorted(rr.sample(sorted(S),m)),sorted(rr.sample(sorted(T),m));sig=tuple(x),tuple(z)
   if sig not in seen:blocks.append((x,z,'new_seeded_XZ',''));seen.add(sig)
  registered=[];backgrounds=set()
  for bi,(x,z,origin,oldid) in enumerate(blocks):
   rest=sorted(poolws-set(x+z));rt=sorted(set(rest)&T);ro=sorted(set(rest)-T);d=n-m;lo=max(0,d-len(ro));hi=min(d,len(rt))
   levels={'low':lo,'mid':(lo+hi)//2,'high':hi};targets=sorted({levels[k] for k in a.background_levels.split(',')});dseen=set()
   for tn in targets:
    for bg in range(a.backgrounds):
     R=rng('directAC_D',pid,x,z,bg);tt=rt.copy();oo=ro.copy();R.shuffle(tt);R.shuffle(oo);D=sorted(tt[:tn]+oo[:d-tn])
     if tuple(D) in dseen:continue
     dseen.add(tuple(D));assert len(D)==n-m and not set(D)&set(x+z)
     A,C=sorted(D+x),sorted(D+z);actual=len(set(A)-set(C));assert actual==m and len(A)==len(C)==n
     eid=canonical_hash([pid,cell['method'],s,t,n,m,D,x,z])[:24];bgid=canonical_hash([pid,D])[:20]
     ev=dict(event_id=eid,pool_id=pid,image=meta['image'],building=meta['building'],condition=meta['condition'],layer=meta['layer'],
       difficulty=meta.get('difficulty'),analysis_scope=meta.get('analysis_scope','primary_target'),reference_id=meta['reference_id'],reference_version=meta['reference_version'],
       method=cell['method'],heldout_building=meta['building'],source_class=s,target_class=t,n=n,m=m,pool_n=len(poolws),
       source_capacity=len(S),target_capacity=len(T),D='|'.join(D),X='|'.join(x),Z='|'.join(z),
       A_members='|'.join(A),C_members='|'.join(C),A_team_key=key(pid,A),C_team_key=key(pid,C),A_class_vector=class_vector(A,groups),C_class_vector=class_vector(C,groups),
       actual_m_AC=actual,replacement_fraction=m/n,source_candidate_fraction=m/len(S),target_candidate_fraction=m/len(T),
       source_seat_replaced_fraction=m/(m+len(set(D)&S)),seat_net_change_l1=2*m,background_id=bgid,block_id=canonical_hash([pid,x,z])[:20],
       background_source_n=len(set(D)&S),background_target_n=len(set(D)&T),background_unknown_n=len(set(D)&set(groups.get('unknown',[]))),
       block_replicate=bi,background_replicate=bg,block_origin=origin,reused_identity_event_id=oldid,method_partition_id=partition_id(groups),
       design='direct_AC_no_same_class_B',comparison_has_B=False,selection_phase=a.selection_phase,data_release='v2.1')
     events.setdefault(eid,ev);registered.append(eid);backgrounds.add(bgid)
     conditionlinks.append(dict(event_id=eid,condition_id=cell.get('condition_id',''),requested_n_spec=cell.get('requested_n_spec',str(n)),pool_id=pid,n=n,m=m))
     for team in [A,C]:
      tk=key(pid,team);requests[tk]=dict(team_key=tk,pool_id=pid,n=n,member_workers='|'.join(team),input_pool_sha256=canonical_hash(p))
  coverage.append(dict(cell,registered_events=len(set(registered)),registered_blocks=len(blocks),registered_backgrounds=len(backgrounds),**counts))
  write_json(out/'REGISTRATION_PROGRESS.json',dict(cells=len(coverage),events=len(events),unique_teams=len(requests)))
 write_csv(out/'EVENTS_EXACT.csv.gz',events.values());write_csv(out/'REQUESTS.csv.gz',requests.values());write_csv(out/'EVENT_CONDITION_LINKS.csv.gz',conditionlinks)
 write_csv(out/'REGISTERED_COVERAGE.csv.gz',coverage)
 write_json(out/'DESIGN.json',dict(frozen,cells=len(coverage),events=len(events),unique_teams=len(requests),
   has_B=False,within_cross_discrimination_estimable=False,endpoint_deduplication=True,all_AC_identities_validated=True,member_combinations_exhausted=False))
 print(json.dumps(dict(cells=len(coverage),events=len(events),unique_teams=len(requests))),flush=True)
if __name__=='__main__':main()
