"""Exact feasible count vectors plus documented systematic sampling of large grids."""
from __future__ import annotations
import argparse,collections,functools,hashlib,itertools,json,math
from pathlib import Path
import numpy as np
import pandas as pd
from fusion_runner import read,write,team_key
from design_screen import rng_for

DIFF={'简单':'easy','中等':'medium','困难':'hard'}

def load_labels(paths):
    frames=[]
    for p in paths:
        d=pd.read_csv(p,keep_default_na=False);d['domain']=d.domain.replace({'global':'all'});frames.append(d)
    d=pd.concat(frames,ignore_index=True)
    assert not d.duplicated(['method_id','domain','worker_id']).any()
    result={}
    for (m,dom),g in d.groupby(['method_id','domain']):
        result[(m,dom)]={r.worker_id:r.class_id for r in g.itertuples() if str(r.known).lower()=='true' and r.class_id not in ['','unknown']}
    return result

@functools.lru_cache(maxsize=2048)
def vectors(caps,k):
    if len(caps)==1:return ((k,),) if 0<=k<=caps[0] else ()
    return tuple((i,*v) for i in range(max(0,k-sum(caps[1:])),min(caps[0],k)+1) for v in vectors(caps[1:],k-i))

@functools.lru_cache(maxsize=2048)
def choose_vectors(caps,k,maximum):
    feasible=vectors(tuple(caps),k)
    if len(feasible)<=maximum:return feasible
    # Cover each pure class, the pool-proportional mixture, equal mixture and
    # maximum-separated boundaries/interiors in count-vector L1 distance.
    X=np.array(feasible,dtype=np.int16);nz=(X>0).sum(1)
    selected=list(np.where(nz==1)[0]);targets=[np.array(caps)/sum(caps)*k,np.repeat(k/len(caps),len(caps))]
    for target in targets:
        i=int(np.abs(X-target).sum(1).argmin())
        if i not in selected:selected.append(i)
    mind=np.full(len(X),9999,dtype=np.int16)
    for i in selected:mind=np.minimum(mind,np.abs(X-X[i]).sum(1))
    tie=np.array([int(hashlib.sha256(str(v).encode()).hexdigest()[:8],16)/2**32 for v in feasible])
    while len(selected)<maximum:
        score=mind.astype(float)+tie*.001;score[selected]=-1;i=int(score.argmax());selected.append(i);mind=np.minimum(mind,np.abs(X-X[i]).sum(1))
    return tuple(feasible[i] for i in sorted(selected))

def applicable(pool,domain):
    l=pool['meta']['layer']
    if domain=='all':return l=='ordinary_manual'
    if domain in ['easy','medium','hard']:return l=='ordinary_manual' and DIFF.get(pool['meta']['difficulty'])==domain
    if domain=='doorway':return l=='doorway_manual'
    if domain in ['semi_v1','semi_new']:return l=='ordinary_semi'
    return l==domain

def sample_cell(groups,counts,reps,seed_parts):
    poss=math.prod(math.comb(len(groups[c]),n) for c,n in counts.items());want=min(reps,poss)
    if poss<=reps:
        options=[list(itertools.combinations(groups[c],n)) for c,n in counts.items()]
        return [tuple(sorted(itertools.chain.from_iterable(parts))) for parts in itertools.product(*options)],poss,True
    chosen=[];seen=set();rep=0
    while len(chosen)<want:
        # Initial seed ranks are shared across compositions. Duplicate rejection
        # and small-cell enumeration can desynchronize exported replicate indices;
        # actual member intersections must determine every comparison's turnover.
        team=[]
        for c,n in counts.items():
            order=rng_for(*seed_parts,c,rep).permutation(groups[c]).tolist();team.extend(order[:n])
        t=tuple(sorted(team));rep+=1
        if t not in seen:seen.add(t);chosen.append(t)
    return chosen,poss,False

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--split',type=Path,required=True);ap.add_argument('--labels',type=Path,action='append',required=True);ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    split=read(a.split);spec=read(a.spec);maps=load_labels(a.labels);pools=read(a.snapshot)['images'];requests=[];ledger=[]
    phase=spec['phase'];eligible=[p for p in pools if p['meta']['building'] in split[phase+'_buildings']]
    dense={p['pool_id'] for p in eligible if p['meta']['difficulty'] in ['困难','中等']}
    for b in split[phase+'_buildings']:
        easy=sorted([p for p in eligible if p['meta']['layer']=='ordinary_manual' and p['meta']['building']==b and p['meta']['difficulty']=='简单'],key=lambda p:hashlib.sha256(p['pool_id'].encode()).hexdigest())
        dense.update(p['pool_id'] for p in easy[:2])
    for ms in spec['methods']:
        mid=ms['method_id'];domains=ms.get('domains',[d for m,d in maps if m==mid])
        for dom in domains:
            if (mid,dom) not in maps:raise KeyError((mid,dom))
            mapping=maps[(mid,dom)];classes=sorted(set(mapping.values()))
            for p in eligible:
                if not applicable(p,dom) or (ms.get('panel')=='dense' and p['pool_id'] not in dense):continue
                groups={c:sorted(r['worker_id'] for r in p['records'] if mapping.get(r['worker_id'])==c) for c in classes};caps=tuple(len(groups[c]) for c in classes)
                for k in ms['sizes']:
                    if k>sum(caps):continue
                    fs=vectors(caps,k);chosen=choose_vectors(caps,k,ms.get('max_vectors',64));cell_total=0
                    for vec in chosen:
                        counts=dict(zip(classes,vec));teams,possible,exhausted=sample_cell(groups,counts,ms.get('replicates',4),(spec['seed'],phase,p['pool_id'],mid,dom,k))
                        comp='|'.join(f'{c}:{n}' for c,n in counts.items())
                        for rep,team in enumerate(teams):
                            rid=hashlib.sha256(json.dumps([phase,mid,dom,p['pool_id'],k,vec,rep,spec['seed']]).encode()).hexdigest()[:24]
                            requests.append(dict(request_id='composition__'+rid,phase=phase,family='composition_grid',method_id=mid,domain=dom,pool_id=p['pool_id'],k=k,composition=comp,counts=counts,replicate=rep,worker_ids=list(team),team_key=team_key(p['pool_id'],team)))
                        ledger.append(dict(method_id=mid,domain=dom,pool_id=p['pool_id'],k=k,composition=comp,available_class_sizes=dict(zip(classes,caps)),possible_member_teams=str(possible),sampled_member_teams=len(teams),exhaustive_members=exhausted,feasible_compositions=len(fs),selected_compositions=len(chosen),exhaustive_compositions=len(chosen)==len(fs)));cell_total+=len(teams)
    write(a.out,dict(spec=spec,requests=requests,ledger=ledger))
    print(json.dumps(dict(requests=len(requests),unique_teams=len(set(r['team_key'] for r in requests)),methods=len(set(r['method_id'] for r in requests)),method_domains=len(set((r['method_id'],r['domain']) for r in requests)),pools=len(set(r['pool_id'] for r in requests)),composition_cells=len(ledger),exhaustive_member_cells=sum(r['exhaustive_members'] for r in ledger))))

if __name__=='__main__':main()
