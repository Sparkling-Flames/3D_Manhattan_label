"""Frozen-label strict ABC paths with one unchanged original A and nested m.

For m <= M: D_m = D0 union (Xmax minus X_m), A = D0 union Xmax,
B_m = D_m union Y_m, C_m = D_m union Z_m. X/Y/Z prefixes originate
from one score-blind order per path. The team size and voting-count threshold
stay fixed; class seats change by m. No target outcomes are read.
"""
from __future__ import annotations
import argparse,collections,itertools,hashlib,json,random,math
from pathlib import Path
from capacity_space import read_json,read_labels,capacities,canonical_hash,exact_counts,write_csv
from register_adaptive import key,members,make_event,select_blocks,rng,write_json,partition_id


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pools',nargs='+',required=True);ap.add_argument('--labels',required=True)
 ap.add_argument('--max-cells',required=True);ap.add_argument('--m-values',default='2,4,6,max')
 ap.add_argument('--blocks',type=int,default=2);ap.add_argument('--backgrounds',type=int,default=2)
 ap.add_argument('--background-levels',default='low,high');ap.add_argument('--reuse-events',nargs='*',default=[]);ap.add_argument('--output',required=True);ap.add_argument('--selection-phase',default='post_global_screen_fixed_A_m_path')
 a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 pools={p['pool_id']:p for fn in a.pools for p in read_json(fn)['images']};labels=read_labels(a.labels);cells=read_labels(a.max_cells)
 L=collections.defaultdict(list)
 for r in labels:L[r['method'],r['heldout_building']].append(r)
 old=collections.defaultdict(list)
 for fn in a.reuse_events:
  for r in read_labels(fn):
   if r.get('design') not in ('strict_disjoint_ABC','strict_ABC','strict_disjoint_ABC_fixedA_nested_m'):continue
   old[r['pool_id'],int(float(r['n'])),int(float(r['m']))].append(r)
 events={};requests={};paths=[];links=[];pairs=[];coverage=[]
 frozen=dict(labels_sha256=hashlib.sha256(Path(a.labels).read_bytes()).hexdigest(),cells_sha256=hashlib.sha256(Path(a.max_cells).read_bytes()).hexdigest(),
    score_blind_registration=True,source_commit='a476461d7ede8db95da43de4139e612c05e618bc',data_release='v2.1',
    fixed_A=True,fixed_n=True,nested_XYZ_prefixes=True,requested_m_values=a.m_values,blocks=a.blocks,backgrounds=a.backgrounds,
    background_levels=a.background_levels,old_event_inputs=a.reuse_events,selection_phase=a.selection_phase)
 write_json(out/'FROZEN_PATH_INPUTS.json',frozen)
 for cell in cells:
  pid=cell['pool_id'];pool=pools[pid];meta=pool['meta'];n=int(cell['n']);M=int(cell['m']);groups=capacities(pool,L[cell['method'],meta['building']])
  s,t=cell['source_class'],cell['target_class'];allws=set(r['worker_id'] for r in pool['records'])
  assert exact_counts(len(allws),len(groups[s]),len(groups[t]),n,M)['strict_ABC']
  spec=cell.get('m_values') or a.m_values
  values=[]
  for token in spec.replace('|',',').split(','):
   token=token.strip()
   if not token:continue
   values.append({'max':M,'half':max(1,math.ceil(M/2)),'quarter':max(1,math.ceil(M/4)),'three_quarter':max(1,math.ceil(3*M/4))}.get(token) if token in ('max','half','quarter','three_quarter') else int(token))
  mvals=sorted(set(values))
  mvals=[m for m in mvals if 1<=m<=M];assert M in mvals,'Max block must be included in each path.'
  if len(mvals)<2:
   coverage.append(dict(cell,paths=0,reason='fewer_than_two_supported_m_values'));continue
  blocks=select_blocks(cell,groups,pid,old[pid,n,M],a.blocks);cell_paths=0
  for bi,(x0,y0,z0,origin,oldid) in enumerate(blocks):
   R=rng('fixed_A_m_prefix',pid,partition_id(groups),x0,y0,z0,n,bi)
   xx,yy,zz=[list(q) for q in [x0,y0,z0]]
   for v in [xx,yy,zz]:R.shuffle(v)
   rest=sorted(allws-set(xx+yy+zz));rt=sorted(set(rest)&set(groups[t]));ro=sorted(set(rest)-set(groups[t]));d=n-M
   lo=max(0,d-len(ro));hi=min(d,len(rt));levelvals={'low':lo,'mid':(lo+hi)//2,'high':hi}
   levels=sorted({levelvals[k] for k in a.background_levels.split(',')});seen_D=set()
   for target_n in levels:
    for bg in range(a.backgrounds):
     rr=rng('fixed_A_D0',pid,xx,yy,zz,n,target_n,bg);tt=rt.copy();oo=ro.copy();rr.shuffle(tt);rr.shuffle(oo)
     d0=sorted(tt[:target_n]+oo[:d-target_n]);sig=tuple(d0)
     if sig in seen_D:continue
     seen_D.add(sig);path_id=canonical_hash([pid,cell['method'],n,xx,yy,zz,d0])[:24]
     A=sorted(d0+xx);aid=key(pid,A);steprows=[]
     paths.append(dict(path_id=path_id,pool_id=pid,image=meta['image'],building=meta['building'],condition=meta['condition'],method=cell['method'],
       source_class=s,target_class=t,n=n,max_m=M,m_values='|'.join(map(str,mvals)),D0='|'.join(d0),
       Xmax_ordered='|'.join(xx),Ymax_ordered='|'.join(yy),Zmax_ordered='|'.join(zz),A_members='|'.join(A),A_team_key=aid,
       background_target_n=target_n,block_replicate=bi,background_replicate=bg,block_origin=origin,
       selection_phase=a.selection_phase,condition_id=cell.get('condition_id','')))
     for m in mvals:
      x,y,z=[sorted(q[:m]) for q in [xx,yy,zz]];dm=sorted(d0+xx[m:]);cc=dict(cell,m=m,selection_phase=a.selection_phase)
      e,teams=make_event(pool,cc,groups,x,y,z,dm,bi,bg,origin,oldid,design='strict_disjoint_ABC_fixedA_nested_m')
      assert e['A_members']=='|'.join(A) and e['A_team_key']==aid
      assert e['background_target_n']==target_n
      events.setdefault(e['event_id'],e)
      for arm,ws in teams.items():
       tk=e[arm+'_team_key'];requests[tk]=dict(team_key=tk,pool_id=pid,n=n,member_workers='|'.join(ws),input_pool_sha256=canonical_hash(pool))
      link=dict(path_id=path_id,event_id=e['event_id'],pool_id=pid,method=cell['method'],n=n,m=m,max_m=M,
           A_team_key=aid,B_team_key=e['B_team_key'],C_team_key=e['C_team_key'],condition_id=cell.get('condition_id',''))
      links.append(link);steprows.append((link,teams))
     for (sm,st),(lg,lt) in itertools.combinations(steprows,2):
      delta=lg['m']-sm['m'];assert len(set(st['B'])-set(lt['B']))==len(set(st['C'])-set(lt['C']))==delta
      pairs.append(dict(path_id=path_id,pool_id=pid,method=cell['method'],n=n,m_small=sm['m'],m_large=lg['m'],additional_replacements=delta,
         event_small=sm['event_id'],event_large=lg['event_id'],A_team_key=aid,B_small=sm['B_team_key'],B_large=lg['B_team_key'],
         C_small=sm['C_team_key'],C_large=lg['C_team_key'],fixed_original_A=True,condition_id=cell.get('condition_id','')))
     cell_paths+=1
  coverage.append(dict(cell,paths=cell_paths,m_values='|'.join(map(str,mvals)),reason='registered'))
  write_json(out/'REGISTRATION_PROGRESS.json',dict(cells=len(coverage),paths=len(paths),events=len(events),unique_teams=len(requests)))
 write_csv(out/'EVENTS_EXACT.csv.gz',events.values());write_csv(out/'REQUESTS.csv.gz',requests.values());write_csv(out/'PATHS_EXACT.csv.gz',paths)
 write_csv(out/'PATH_EVENT_LINKS.csv.gz',links);write_csv(out/'EXACT_M_PATH_PAIR_LINKS.csv.gz',pairs);write_csv(out/'REGISTERED_COVERAGE.csv.gz',coverage)
 write_json(out/'DESIGN.json',dict(frozen,paths=len(paths),unique_events=len(events),path_event_links=len(links),path_pairs=len(pairs),unique_teams=len(requests),
   comparison_identity='Report C_large-C_small, B_large-B_small, and (C_large-B_large)-(C_small-B_small); A is exactly fixed.',
   all_registered_paths_validated=True,member_exhaustion=False))
 print(json.dumps(dict(paths=len(paths),unique_events=len(events),path_pairs=len(pairs),unique_teams=len(requests))),flush=True)
if __name__=='__main__':main()
