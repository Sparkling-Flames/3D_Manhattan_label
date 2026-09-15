"""Follow-up exploration of uncertainty/convergence, never a frozen stop policy.
All raw inputs and the preceding report remain immutable.
"""
from pathlib import Path
import hashlib,json,gzip,collections,itertools
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait import pro_core as core
ROOT=core.ROOT;BUNDLE=core.BUNDLE;OLD=core.OUT
OUT=BUNDLE/'cloud/pro_exploration/v2_convergence_e086b2b9'
FOUND=OUT/'foundation';SEED=20260914
CUTS=(.05,.10,.20)

def csv(path,values):
 p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True)
 d=values if isinstance(values,pd.DataFrame) else pd.DataFrame(values)
 if not len(d.columns):d=pd.DataFrame(columns=['status'])
 d.to_csv(p,index=False,float_format='%.12g');return d

def js(path,obj):core.write_json(OUT/path,obj)
def seed_for(*parts):return int(hashlib.sha256('|'.join(map(str,parts)).encode()).hexdigest()[:12],16)%2**32

def read_responses():
 return pd.read_csv(FOUND/'human/response_metrics.csv.gz')
def boundary_map():
 with np.load(FOUND/'human/dense_boundaries.npz',allow_pickle=False) as z:return dict(zip(z['canonical_annotation_ids'].tolist(),z['boundaries']))
def images():return pd.DataFrame(core.load(BUNDLE/'metadata/images.jsonl'))
def room_map():
 out={}
 for r in core.load(BUNDLE/'evaluation/room_components.jsonl'):
  for i in r['image_ids']:out[i]=(r['room_id'],r['status'])
 return out

def pairs_for(g,dense):
 n=len(g);pcs=g.effective_point_count.to_numpy();dm=np.zeros((n,n),float)
 cids=g.canonical_annotation_id.tolist()
 for i,j in itertools.combinations(range(n),2):dm[i,j]=dm[j,i]=core._d_mask(dense[cids[i]],dense[cids[j]]) if pcs[i]==pcs[j] else 2.
 return dm,pcs

def cluster(dm,pcs,cut):
 if len(pcs)==0:return np.array([],int)
 return core.topology_clusters(dm,pcs,cut)

def medoids(dm,labels,minimum=2):
 result=[]
 for l in np.unique(labels):
  ix=np.flatnonzero(labels==l)
  if len(ix)>=minimum:result.append(int(ix[np.argmin(dm[np.ix_(ix,ix)].sum(1))]))
 return np.asarray(result,int)

def probabilities(labels):
 c=np.array(list(collections.Counter(labels).values()),float);return c/c.sum() if len(c) else c

def entropy(labels):
 p=probabilities(labels);return float(-(p*np.log2(p)).sum()) if len(p) else np.nan

def mean_finite(x):
 x=np.asarray(x,float);return float(np.mean(x[np.isfinite(x)])) if np.isfinite(x).any() else np.nan

def paired_interval(df,delta_col,group='building',repeats=1000):
 """Image-macro estimate; resample independent building clusters, not orders."""
 d=df[[group,delta_col]].dropna();g=d.groupby(group)[delta_col].agg(['sum','count'])
 if not len(g):return dict(n=0,groups=0,delta=np.nan,lo=np.nan,hi=np.nan)
 if len(g)<2:return dict(n=len(d),groups=len(g),delta=d[delta_col].mean(),lo=np.nan,hi=np.nan)
 rng=np.random.default_rng(SEED);v=g.to_numpy();idx=rng.integers(len(v),size=(repeats,len(v)));a=v[idx].sum(1);boot=a[:,0]/a[:,1]
 return dict(n=len(d),groups=len(g),delta=d[delta_col].mean(),lo=np.quantile(boot,.025),hi=np.quantile(boot,.975))
