"""Reproducible, outcome-free matched block substitutions in real personnel pools.

Each event has A=core+out, B=core+same-class new members and
C=core+different-class new members. A->B and A->C replace exactly m people.
The common core is sampled by its class count vector, not by a fixed person.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, math
from pathlib import Path
import numpy as np
from fusion_runner import read, write, team_key
from design_screen import rng_for
from design_compositions import load_labels, applicable, vectors, choose_vectors

def sample(groups, counts, rng, exclude=()):
    banned=set(exclude); out=[]
    for c,n in zip(groups,counts):
        available=[w for w in groups[c] if w not in banned]
        if n>len(available): return None
        if n: out.extend(rng.choice(available,size=n,replace=False).tolist())
    return sorted(out)

def make_event(pool, mapping, k, m, outcounts, incounts, mode, origin, seedparts, core_rank):
    classes=sorted(set(mapping.values())); rng=rng_for(*seedparts)
    allgroups={c:sorted(r['worker_id'] for r in pool['records'] if mapping.get(r['worker_id'])==c) for c in classes}
    allowed={r['worker_id'] for r in pool['records'] if mode=='unrestricted' or r['origin']==origin}
    groups={c:[w for w in allgroups[c] if w in allowed] for c in classes}
    outgoing=sample(groups,outcounts,rng)
    if outgoing is None:return None,'out_capacity'
    same=sample(groups,outcounts,rng,outgoing)
    if same is None:return None,'within_capacity'
    cross=sample(groups,incounts,rng,outgoing)
    if cross is None:return None,'cross_capacity'
    reserved=set(outgoing+same+cross)
    coregroups={c:[w for w in allgroups[c] if w not in reserved] for c in classes}
    caps=tuple(map(len,coregroups.values()))
    if sum(caps)<k-m:return None,'core_capacity_after_one_member_draw'
    corevectors=choose_vectors(caps,k-m,64)
    cv=corevectors[core_rank%len(corevectors)]
    core=sample(coregroups,cv,rng)
    A=sorted(core+outgoing);B=sorted(core+same);C=sorted(core+cross)
    def comp(ws):return dict(zip(classes,[sum(mapping[w]==c for w in ws) for c in classes]))
    ca,cb,cc=map(comp,[A,B,C])
    assert ca==cb and ca!=cc
    assert len(A)==len(B)==len(C)==k
    assert len(set(A)-set(B))==len(set(A)-set(C))==m
    assert set(A)&set(B)==set(A)&set(C)==set(core)
    origins={r['worker_id']:r['origin'] for r in pool['records']}
    if mode=='source_matched':assert len({sum(origins[w]=='new' for w in T) for T in [A,B,C]})==1
    value=dict(core_workers=core,outgoing_workers=outgoing,within_incoming=same,cross_incoming=cross,
        A_workers=A,B_workers=B,C_workers=C,A_counts=ca,C_counts=cc,
        outgoing_counts=dict(zip(classes,outcounts)),incoming_counts=dict(zip(classes,incounts)),
        changed_category_slots=sum(abs(a-b) for a,b in zip(outcounts,incounts))//2,
        replaced_classes=sum(n>0 for n in outcounts),incoming_classes=sum(n>0 for n in incounts),
        core_composition_options=len(vectors(caps,k-m)),core_vectors_considered=len(corevectors),
        replaced_entire_categories=[c for c,n in zip(classes,outcounts) if n>0 and ca[c]==n])
    return value,None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--split',type=Path,required=True)
    ap.add_argument('--labels',type=Path,action='append',required=True);ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    spec=read(a.spec);split=read(a.split);maps=load_labels(a.labels);phase=spec['phase']
    pools=[p for p in read(a.snapshot)['images'] if p['meta']['building'] in split[phase+'_buildings']]
    requests=[];events=[];ledger=[]
    for ms in spec['methods']:
      mid=ms['method_id']
      for dom in ms.get('domains',[d for m,d in maps if m==mid]):
        mapping=maps[mid,dom];classes=sorted(set(mapping.values()))
        for p in pools:
          if not applicable(p,dom):continue
          eligible=[r for r in p['records'] if r['worker_id'] in mapping]
          for k in ms['sizes']:
            if k+2>len(eligible):continue
            sizes=sorted({x for x in [1,2,max(2,round(k/3)),max(2,round(k/2))] if x<=len(eligible)-k and x<k})
            candidates=[]
            for mode,origin in [('unrestricted','any'),('source_matched','new'),('source_matched','v1')]:
              caps=tuple(sum(mapping[r['worker_id']]==c and (mode=='unrestricted' or r['origin']==origin) for r in eligible) for c in classes)
              for m in sizes:
                outs=vectors(tuple(n//2 for n in caps),m)
                ins=vectors(caps,m)
                for oc in outs:
                  # Include every feasible pure incoming class and a deterministic
                  # farthest-L1 subset of mixed incoming blocks, also for pure out.
                  if sum(n>0 for n in oc)>1:
                    if oc not in choose_vectors(tuple(n//2 for n in caps),m,16):continue
                  icandidates=choose_vectors(caps,m,16)
                  for ic in icandidates:
                    if oc==ic:continue
                    pattern='single_class' if sum(n>0 for n in oc)==1 and sum(n>0 for n in ic)==1 else 'multi_class'
                    candidates.append((mode,origin,m,oc,ic,pattern))
            # Stratify the finite candidate frame by matching mode, origin,
            # block type and size. Directed count changes are shuffled within
            # strata, without their own quota; do not call this all teams.
            strata=collections.defaultdict(list)
            for cand in candidates:
                mode,origin,m,oc,ic,pattern=cand
                strata[(mode,origin,pattern,m)].append(cand)
            rng=rng_for(spec['seed'],phase,mid,dom,p['pool_id'],k)
            for vals in strata.values():rng.shuffle(vals)
            keys=list(strata);rng.shuffle(keys);ordered=[]
            while keys:
                nextkeys=[]
                for key in keys:
                    ordered.append(strata[key].pop())
                    if strata[key]:nextkeys.append(key)
                keys=nextkeys
            accepted=[];failures=collections.Counter();attempts=0
            quota=ms.get('events_per_cell',32)
            for index,cand in enumerate(ordered):
                if len(accepted)>=quota:break
                mode,origin,m,oc,ic,pattern=cand;attempts+=1
                parts=(spec['seed'],phase,mid,dom,p['pool_id'],k,index)
                ev,reason=make_event(p,mapping,k,m,oc,ic,mode,origin,parts,index)
                if ev is None:failures[reason]+=1;continue
                eid='block__'+hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:24]
                ev.update(event_id=eid,phase=phase,method_id=mid,domain=dom,pool_id=p['pool_id'],k=k,m=m,
                    matching=mode,matched_origin=origin,pattern=pattern,building=p['meta']['building'],image=p['meta']['image'],difficulty=p['meta']['difficulty'],layer=p['meta']['layer'])
                for arm in ['A','B','C']:
                    ws=ev[arm+'_workers'];counts=ev['C_counts'] if arm=='C' else ev['A_counts']
                    tk=team_key(p['pool_id'],ws);ev[arm+'_team_key']=tk
                    requests.append(dict(request_id=eid+'__'+arm,event_id=eid,arm=arm,phase=phase,family='matched_block',
                        method_id=mid,domain=dom,pool_id=p['pool_id'],k=k,worker_ids=ws,team_key=tk,counts=counts,
                        composition='|'.join(f'{c}:{n}' for c,n in counts.items())))
                events.append(ev);accepted.append(ev)
            ledger.append(dict(method_id=mid,domain=dom,pool_id=p['pool_id'],k=k,
                finite_count_pattern_candidates=len(candidates),attempted_patterns=attempts,accepted_events=len(accepted),
                event_quota=quota,all_count_pattern_candidates_attempted=attempts==len(candidates),failure_reasons=dict(failures),
                accepted_by_mode=dict(collections.Counter(e['matching'] for e in accepted)),
                accepted_by_pattern=dict(collections.Counter(e['pattern'] for e in accepted)),
                accepted_by_m=dict(collections.Counter(e['m'] for e in accepted)),
                member_sampling='one deterministic real-member draw per selected pattern; not exhaustive',
                multi_count_patterns='farthest L1 capped at 16 per outgoing/incoming side'))
    write(a.out,dict(spec=spec,requests=requests,events=events,ledger=ledger))
    print(json.dumps(dict(events=len(events),requests=len(requests),unique_teams=len({r['team_key'] for r in requests}),
        pools=len({r['pool_id'] for r in requests}),methods=len({r['method_id'] for r in requests}),
        single_person_events=sum(e['m']==1 for e in events),multi_person_events=sum(e['m']>1 for e in events),
        multi_class_events=sum(e['pattern']=='multi_class' for e in events),source_matched_events=sum(e['matching']=='source_matched' for e in events))))

if __name__=='__main__':main()
