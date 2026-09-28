"""Exact helper-function subset of the earlier reproduction program.
Function bodies are preserved; no old study entrypoints execute on import.
"""
from __future__ import annotations
import ast,collections,hashlib,itertools,json,math
from typing import Any
import numpy as np
from scipy.cluster.hierarchy import linkage,fcluster
from scipy.spatial.distance import squareform
from scipy.optimize import linear_sum_assignment
DATA_BLOB='5e3a08f091a4611505f9eeb90680bf5edec87c49'
def recover_endpoints(points, norm):
    p=np.asarray(points,dtype=float)
    if not norm.get('valid',False):
        raise ValueError('An accepted normalized geometry is required')
    candidates=[]
    for row in norm['pairs']:
        top=np.flatnonzero(np.isclose(p[:,1],row['y_ceiling'],rtol=0,atol=1e-7))
        bot=np.flatnonzero(np.isclose(p[:,1],row['y_floor'],rtol=0,atol=1e-7))
        matches=[]
        for i in top:
            for j in bot:
                if i==j: continue
                xa=p[i,0]%1024; xb=p[j,0]%1024
                mean=(xa+((xb-xa+512)%1024-512)/2)%1024
                err=abs((mean-row['x']+512)%1024-512)
                if err<1e-6: matches.append((int(i),int(j)))
        candidates.append(matches)
    order=sorted(range(len(candidates)),key=lambda k:len(candidates[k]));solutions=[]
    def search(t,used,answer):
        if len(solutions)>=2:return
        if t==len(order):solutions.append(answer.copy());return
        k=order[t]
        for i,j in candidates[k]:
            if i in used or j in used:continue
            answer[k]=(i,j); search(t+1,used|{i,j},answer)
    search(0,set(),{})
    if len(solutions)!=1:
        raise ValueError(f'Endpoint recovery is not unique: solutions={len(solutions)}, candidates={[len(x)for x in candidates]}')
    pairs=np.asarray([solutions[0][k]for k in range(len(candidates))])
    assert len(np.unique(pairs))==len(p)
    return p[pairs],pairs

def safe_json(x):
    if isinstance(x, dict): return {str(k):safe_json(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)): return [safe_json(v) for v in x]
    if isinstance(x,np.integer): return int(x)
    if isinstance(x,np.bool_): return bool(x)
    if isinstance(x,(float,np.floating)): return float(x) if np.isfinite(x) else None
    return x

def save_json(path,x):path.write_text(json.dumps(safe_json(x),ensure_ascii=False,indent=2),encoding='utf-8')

def legacy_functions(data):
    # Compile function definitions only (not module imports or research entrypoints).
    # All code comes from the pinned, hash-checked repository source snapshot.
    ns={'np':np,'Any':Any,'hashlib':hashlib,'json':json,'linear_sum_assignment':linear_sum_assignment}
    names=['geometry_metrics.py','representation.py']
    for name in names:
        source=next(v for k,v in data['source_code_snapshots'].items() if k.endswith('/'+name))
        tree=ast.parse(source)
        defs=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
        exec(compile(ast.Module(body=defs,type_ignores=[]),name,'exec'),ns)
    return ns

def dense(ns,norm):
    p=norm['pairs']; x=np.asarray([q['x'] for q in p],np.float32)
    y=np.asarray([[q['y_ceiling'] for q in p],[q['y_floor'] for q in p]],np.float32)
    z=np.stack([ns['_interp_periodic'](x,a,1024) for a in y])
    z=np.clip(np.rint(z),0,511).astype(np.int32)
    return np.stack([np.minimum(z[0],z[1]),np.maximum(z[0],z[1])])

def dmask(a,b):
    inter=np.maximum(0,np.minimum(a[1],b[1])-np.maximum(a[0],b[0])+1)
    union=a[1]-a[0]+b[1]-b[0]+2-inter
    return 1-float(inter.sum()/union.sum())

def clust(dm,counts=None,cut=.1):
    n=len(dm)
    if counts is None:
        return np.ones(n,int) if n<2 else fcluster(linkage(squareform(dm,checks=True),method='complete'),cut,criterion='distance')
    labels=np.zeros(n,int); offset=0
    for c in sorted(set(counts)):
        ix=np.flatnonzero(counts==c); v=clust(dm[np.ix_(ix,ix)],None,cut)
        labels[ix]=v+offset;offset=int(labels.max())
    return labels

def cluster_stats(labels):
    co=np.array(list(collections.Counter(labels).values()),int);n=int(co.sum());p=co/n
    return dict(clusters=len(co),supported=int((co>=2).sum()),singletons=int((co==1).sum()),
                singleton_mass=float((co==1).sum()/n),largest_share=float(co.max()/n),
                entropy_bits=float(-(p*np.log2(p)).sum()),sizes=';'.join(map(str,sorted(co,reverse=True))))

def pairs3(norm):
    z=np.array([[r['x']%1024,r['y_ceiling'],r['y_floor']]for r in norm['pairs']])
    return z[np.argsort(z[:,0])]

def native_dense(ns,pts,norm):
    p,indices=recover_endpoints(pts,norm);top=p[:,0];bottom=p[:,1]
    d=np.stack([ns['_interp_periodic'](top[:,0],top[:,1],1024),ns['_interp_periodic'](bottom[:,0],bottom[:,1],1024)])
    z=np.clip(np.rint(d),0,511).astype(np.int32)
    return z,bool(np.any(z[0]>z[1]))

def cyclic_partial(a:np.ndarray,b:np.ndarray,cutoff:float)->dict:
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    if a.ndim!=2 or b.ndim!=2 or a.shape[1]!=3 or b.shape[1]!=3:
        raise ValueError('Inputs must be finite (n,3) paired-corner arrays')
    if not np.isfinite(a).all() or not np.isfinite(b).all() or not math.isfinite(cutoff) or cutoff<=0:
        raise ValueError('Non-finite coordinates or invalid cutoff')
    a=a.copy();b=b.copy();a[:,0]%=1024;b[:,0]%=1024
    a=a[np.argsort(a[:,0],kind='stable')];b=b[np.argsort(b[:,0],kind='stable')]
    m,n=len(a),len(b);penalty=cutoff**2/2
    delta=abs(a[:,None,:]-b[None,:,:]);delta[:,:,0]=np.minimum(delta[:,:,0],1024-delta[:,:,0])
    squared=(delta**2).sum(2);best=None
    if not m or not n:
        return dict(total_squared=penalty*(m+n),localization_squared=0.,unmatched_squared=penalty*(m+n),unmatched_pairs=m+n,matched_pairs=0,matches=[])
    for shift in range(n):
        order=(np.arange(n)+shift)%n;cost=squared[:,order]
        dp=np.empty((m+1,n+1));op=np.zeros((m+1,n+1),dtype=np.int8)
        dp[:,0]=np.arange(m+1)*penalty;dp[0,:]=np.arange(n+1)*penalty;op[1:,0]=1;op[0,1:]=2
        for i in range(1,m+1):
            for j in range(1,n+1):
                options=[dp[i-1,j-1]+cost[i-1,j-1] if cost[i-1,j-1]<2*penalty else np.inf,
                         dp[i-1,j]+penalty,dp[i,j-1]+penalty]
                choice=int(np.argmin(options));dp[i,j]=options[choice];op[i,j]=choice
        if best is None or dp[m,n]<best['total_squared']-1e-10:
            i,j=m,n;matches=[]
            while i or j:
                action=int(op[i,j])
                if action==0:matches.append((i-1,int(order[j-1])));i-=1;j-=1
                elif action==1:i-=1
                else:j-=1
            matches=sorted(matches);loc=sum(float(squared[i,j]) for i,j in matches);unmatched=m+n-2*len(matches)
            best=dict(total_squared=float(dp[m,n]),localization_squared=loc,unmatched_squared=penalty*unmatched,
                      unmatched_pairs=unmatched,matched_pairs=len(matches),matches=matches)
    assert abs(best['total_squared']-best['localization_squared']-best['unmatched_squared'])<1e-7
    return best

def cyclic_ok(matches):
    order=np.array([j for i,j in sorted(matches)])
    return len(order)<3 or np.sum(np.diff(np.r_[order,order[0]])<0)<=1

def brute(a,b,c):
    m,n=len(a),len(b);best=c*c/2*(m+n)
    for k in range(1,min(m,n)+1):
        for aa in itertools.combinations(range(m),k):
            for bb in itertools.permutations(range(n),k):
                match=list(zip(aa,bb))
                if not cyclic_ok(match):continue
                cost=c*c/2*(m+n-2*k)
                for i,j in match:
                    d=abs(a[i]-b[j]);d[0]=min(d[0],1024-d[0]);cost+=sum(d*d)
                best=min(best,cost)
    return best
