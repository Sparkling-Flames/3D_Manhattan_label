#!/usr/bin/env python3
"""Exact toy checks. These are mathematical examples, not research-data replications."""
from itertools import combinations, product
from fractions import Fraction as F
from collections import Counter
import json


def avg(xs):
    xs = list(xs)
    return sum(xs, F(0)) / len(xs)


def dist(a, b):
    return F(sum(x != y for x, y in zip(a,b)),len(a))


def fuse(pop, S, strict=False):
    return tuple((2*sum(pop[j][t] for j in S) > len(S)) if strict else (2*sum(pop[j][t] for j in S) >= len(S)) for t in range(len(pop[0])))


def series(pop, gt, strict=False):
    n=len(pop); area=sum(gt)
    out={}
    for k in range(1,n+1):
        groups=list(combinations(range(n),k))
        fs=[fuse(pop,S,strict) for S in groups]
        ds=[F(sum(x!=y for x,y in zip(f,gt)),area) for f in fs]
        rs=[avg(dist(pop[a],pop[b]) for a,b in combinations(S,2)) for S in groups] if k>1 else None
        h=avg(dist(f,pop[j]) for S,f in zip(groups,fs) for j in range(n) if j not in S) if k<n else None
        delta=avg(dist(f,fuse(pop,tuple(S)+(j,),strict)) for S,f in zip(groups,fs) for j in range(n) if j not in S) if k<n else None
        dmean=avg(ds)
        out[k]={'R':avg(rs) if rs else None,'V':avg(dist(a,b) for a,b in product(fs,repeat=2)), 'H':h,'delta_plus':delta,'mean_D':dmean,'variance_D':avg((d-dmean)**2 for d in ds),'D_distribution':{str(x):f'{cnt}/{len(ds)}' for x,cnt in sorted(Counter(ds).items())}}
    return out


def exact_error_gain(pop, gt, strict=False):
    k=len(pop); area=sum(gt); fused=fuse(pop,tuple(range(k)),strict)
    gain={'O':F(0),'E':F(0)}
    bins={side:{'minority':F(0),'tie':F(0),'majority':F(0)} for side in gain}
    for t,y in enumerate(gt):
        q=F(sum(row[t]!=y for row in pop),k)
        g=(q-int(fused[t]!=y))/area
        side='O' if y else 'E'
        gain[side]+=g
        bins[side]['minority' if q<F(1,2) else 'majority' if q>F(1,2) else 'tie']+=g
    mean=avg(F(sum(a!=b for a,b in zip(row,gt)),area) for row in pop)
    fusedD=F(sum(a!=b for a,b in zip(fused,gt)),area)
    assert gain['O']+gain['E']==mean-fusedD
    return {'mean_member_D':mean,'fused_D':fusedD,'gain':gain,'gain_by_wrong_vote_frequency':bins}


def main():
    A=[tuple(map(int,x)) for x in ('1100','1100','0011','0011')]
    B=[tuple(map(int,x)) for x in ('1100','1010','0101','0011')]
    gt=(1,1,0,0)
    result={}
    for strict in (False,True):
        key='strict' if strict else 'MV50'
        aa,bb=series(A,gt,strict),series(B,gt,strict)
        for k in aa:
            for metric in ('R','V','H','delta_plus','mean_D'):
                assert aa[k][metric]==bb[k][metric], (key,k,metric)
        assert aa[1]['V']*F(4,3)==aa[4]['R']
        result[key]={'clustered':aa,'crossed':bb}
    assert [result['MV50']['clustered'][k]['V'] for k in range(1,5)]==[F(1,2),F(5,18),F(1,2),F(0)]
    assert [result['MV50']['clustered'][k]['H'] for k in range(1,4)]==[F(2,3),F(2,3),F(1)]
    # Identical worker O/E, different shared error locations and fusion quality.
    gt8=(1,1,1,1,0,0,0,0)
    shared=[(0,1,1,1,1,0,0,0)]*4
    dispersed=[]
    for j in range(4):
        row=list(gt8); row[j]=0; row[j+4]=1; dispersed.append(tuple(row))
    for strict in (False,True):
        key='strict' if strict else 'MV50'
        result[key]['gain_shared']=exact_error_gain(shared,gt8,strict)
        result[key]['gain_dispersed']=exact_error_gain(dispersed,gt8,strict)
    print(json.dumps(result,default=str,indent=2))

if __name__=='__main__': main()
