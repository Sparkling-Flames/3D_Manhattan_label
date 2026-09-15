"""Versioned image links; no image inference or legacy experimental difficulty."""
from __future__ import annotations
import collections,gzip,hashlib,json,os
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
B=ROOT/'analysis_results/image_portrait_20260914_v1'
V1=B/'cloud/history_difficulty_20260915_v1/run_13859d59'
V2=B/'cloud/history_difficulty_review_20260915_v2/run_c0069628'
OUT=B/'cloud/image_links_after_review_20260915_v1/run_b02a97e2'
INPUT_COMMIT='b02a97e215bf5759fec1d512cffc333d7833779d'
SEED=20260915
EXCLUDE={'W019','W026'}
TRAITS=['floor_boundary','ceiling_boundary','corner_occlusion','connected_space','reflection_glass','low_contrast','doorway']
def safe(x):
 if isinstance(x,dict):return {str(k):safe(v)for k,v in x.items()}
 if isinstance(x,(tuple,list,np.ndarray)):return [safe(v)for v in x]
 if isinstance(x,np.bool_):return bool(x)
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,(float,np.floating)):return float(x)if np.isfinite(x)else None
 return x

def js(rel,data):
 p=OUT/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(safe(data),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def csv(rel,data):
 d=data if isinstance(data,pd.DataFrame)else pd.DataFrame(data)
 if not len(d.columns):d=pd.DataFrame(columns=['status'])
 p=OUT/rel;p.parent.mkdir(parents=True,exist_ok=True);d.to_csv(p,index=False,float_format='%.12g',compression={'method':'gzip','mtime':0}if p.suffix=='.gz'else 'infer');return d

def readj(p):
 p=Path(p)
 if p.suffix=='.json':return json.loads(p.read_text(encoding='utf-8-sig'))
 with (gzip.open(p,'rt',encoding='utf-8-sig')if p.suffix=='.gz'else p.open(encoding='utf-8-sig'))as f:return [json.loads(s)for s in f if s.strip()]
def seed(*a):return int(hashlib.sha256('|'.join(map(str,a)).encode()).hexdigest()[:8],16)
def md(a):
 v=np.asarray(a,float);return float(np.median(v[np.isfinite(v)]))if np.isfinite(v).any()else np.nan

def paired(d,col='delta',group='building',repeats=2000):
 a=d[[group,col]].dropna();v=a.groupby(group)[col].agg(['sum','count']).to_numpy();r=dict(images=len(a),groups=len(v),delta=a[col].mean(),macro_delta=a.groupby(group)[col].mean().mean(),lo=np.nan,hi=np.nan)
 if len(v)>1:
  rng=np.random.default_rng(SEED);ix=rng.integers(len(v),size=(repeats,len(v)));w=v[ix].sum(1);q=w[:,0]/w[:,1];r.update(lo=np.quantile(q,.025),hi=np.quantile(q,.975))
 return r

def groups():
 ix=readj(OUT/'inputs/group_index.json');z=np.load(OUT/'inputs/pairwise_geometry.npz',allow_pickle=False)
 return {(r['image_id'],r['condition']):(r,z[r['key']+'_dm'],z[r['key']+'_pcs'],z[r['key']+'_workers'],z[r['key']+'_ids'])for r in ix}
