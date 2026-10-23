"""Shared, explicit I/O and measurement primitives for the independent sidecar."""
from __future__ import annotations
import os,sys,json,gzip,hashlib,math,collections
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
ROOT=Path(__file__).resolve().parents[4]/'analysis_results/clustering_numeric_received_20260920'
SOURCE=Path(os.environ.get('CLUSTER_SOURCE',ROOT/'work/source'))
OUT=Path(os.environ.get('CLUSTER_OUT',ROOT/'results_recomputed'))
STUDY=SOURCE/'rc2_received/sources/current/study'
CUTS=(6.,9.,12.)
BLOCK=1e6

def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.bool_,)):return bool(v)
    if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
    if isinstance(v,Path):return str(v)
    return v

def dump(name,value):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return p

def save(name,rows):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    d=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    compression={'method':'gzip','mtime':0} if str(p).endswith('.gz') else None
    d.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.17g',compression=compression)
    return d

def readrows(p):
    with gzip.open(p,'rt',encoding='utf-8-sig') as f:return [json.loads(x) for x in f if x.strip()]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def rawdata():
    rows=readrows(STUDY/'inputs/responses.jsonl.gz')
    return rows,{r['canonical_annotation_id']:r for r in rows}

def records():
    # Upstream representation is deliberately reused; its automatic binding is
    # independently checked in audit_numeric.py, not treated as semantic truth.
    sys.path.insert(0,str(SOURCE))
    from tools.thesis_main.analysis.paired_split_research import study as st
    rows,by=rawdata();audit=pd.read_csv(STUDY/'inputs/prior_response_audit.csv').set_index('id')
    approved=st.accepted_map(STUDY/'inputs',rows)
    rec,el=st.prepare(rows,audit,approved,'min_horizontal')
    return rows,by,rec,el,approved

def rays(p):
    p=np.asarray(p,float);phi=(p[:,1]+.5)*np.pi/512-np.pi/2
    u=(p[:,0]+.5)*2*np.pi/1024
    return np.column_stack([np.cos(phi)*np.cos(u),np.cos(phi)*np.sin(u),np.sin(phi)])

def angle_matrix(a,b):
    a,b=rays(a),rays(b)
    cross=np.linalg.norm(np.cross(a[:,None,:],b[None,:,:]),axis=-1)
    dot=np.einsum('ik,jk->ij',a,b)
    return np.degrees(np.arctan2(cross,dot))

def image_matrix(a,b):
    a,b=np.asarray(a,float),np.asarray(b,float)
    raw=np.abs(a[:,None,0]-b[None,:,0])%1024
    dx=np.minimum(raw,1024-raw)
    return np.sqrt(dx*dx+(a[:,None,1]-b[None,:,1])**2)

def canonical_labels(l):
    out=np.empty(len(l),int);seen={}
    for i,x in enumerate(l):
        if x not in seen:seen[x]=len(seen)+1
        out[i]=seen[x]
    return out

def partition(d,ids,t,kind):
    d=np.asarray(d,float)
    if d.shape!=(len(ids),len(ids)) or len(set(ids))!=len(ids):raise ValueError('Bad matrix/identity size')
    if not np.isfinite(d).all() or not np.allclose(d,d.T,atol=1e-10) or np.any(np.diag(d)):
        raise ValueError('Distance matrix must be finite, symmetric, zero diagonal')
    order=np.argsort(ids);a=np.round(d[np.ix_(order,order)],8);n=len(a)
    if not n:return np.array([],int),[]
    if kind=='complete':
        l=canonical_labels(fcluster(linkage(squareform(a),method='complete'),t,criterion='distance')) if n>1 else np.ones(1,int)
        groups=[np.flatnonzero(l==k) for k in range(1,l.max()+1)]
        centers=[int(ix[np.argmin(np.round(a[np.ix_(ix,ix)].sum(1),8))]) for ix in groups]
    elif kind=='representative':
        remaining=np.ones(n,bool);groups=[];centers=[]
        while remaining.any():
            ix=np.flatnonzero(remaining);near=a[np.ix_(ix,ix)]<=t
            degree=near.sum(1);mean=np.array([round(float(a[i,ix[near[z]]].mean()),8) for z,i in enumerate(ix)])
            best=np.lexsort((ix,mean,-degree))[0];c=int(ix[best]);members=ix[near[best]]
            groups.append(members);centers.append(c);remaining[members]=False
        l=np.empty(n,int)
        for k,ix in enumerate(groups,1):l[ix]=k
    else:raise ValueError(kind)
    out=np.empty(n,int);out[order]=l
    return out,[ids[order[c]] for c in centers]

def coassign(l):
    l=np.asarray(l);return l[:,None]==l[None,:]

def miss_probability(N,degree,k):
    if not 0<=k<N:return np.nan
    return math.comb(N-1-degree,k)/math.comb(N-1,k) if k<=N-1-degree else 0.

def next_uncovered(d,k,t):
    near=np.round(d,8)<=t;n=len(d)
    return float(np.mean([miss_probability(n,int(q)-1,k) for q in near.sum(1)])) if 0<=k<n else np.nan

def fixed_stats(l,k):
    n=len(l);sizes=np.bincount(np.asarray(l,int))[1:];sizes=sizes[sizes>0]
    den=math.comb(n,k);ks=single=supported=mass=minor=minor_total=0.
    for s0 in sizes:
        s=int(s0);p0=math.comb(n-s,k)/den if k<=n-s else 0.
        p1=s*math.comb(n-s,k-1)/den if k>=1 and k-1<=n-s else 0.
        ks+=1-p0;single+=p1;supported+=1-p0-p1;mass+=s/n*p0
        if s>=2 and s/n<=.2:minor+=s/n*p0;minor_total+=s/n
    return dict(fixed_expected_clusters=ks,fixed_expected_singletons=single,fixed_expected_supported=supported,
        fixed_unseen_pool_mass=mass,fixed_unseen_repeated_minority_mass=minor,repeated_minority_total_mass=minor_total)

def load_groups():
    return json.loads((OUT/'independent_groups.json').read_text(encoding='utf-8'))

def nominal_cut(metric,nominal):return nominal if metric=='sphere' else nominal*1024/360

def source_json(rel):return json.loads((SOURCE/rel).read_text(encoding='utf-8-sig'))
