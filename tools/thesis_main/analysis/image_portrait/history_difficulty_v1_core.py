"""Shared definitions for historical-response difficulty follow-up.

No legacy experimental difficulty is consumed. Main outputs and independent
expert tags remain distinct. CLI delegates to separately testable stages.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, itertools, json, os, re, subprocess
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
B=ROOT/'analysis_results/image_portrait_20260914_v1'
OLD=B/'cloud/pro_exploration/v2_convergence_e086b2b9'
MAINSPACE=B/'cloud/difficulty_tags_20260915_v1/mainspace_v1_9d19e4e7'
OUT=B/'cloud/history_difficulty_20260915_v1/run_13859d59'
BASE='13859d591acb1bac7790fb0762f2c53282f65748'
SEED=20260915
TRAITS=['floor_boundary','ceiling_boundary','corner_occlusion','connected_space','reflection_glass','low_contrast']
RULES=['P_pattern','D10_distribution','D20_distribution','G10_geometry']
GRADES=['simple','medium','difficult_candidate']
ANCHOR=dict(cut=.1,rule='G10_geometry',early_k=7,late_h=19,max_few_modes=3,max_singleton_mass=.1,order_fraction_required=.8,confirmation='suffix',medium_definition='cumulative')

def safe(x):
    if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [safe(v) for v in x]
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x

def read(p):
    p=Path(p)
    if p.suffix=='.gz':
        with gzip.open(p,'rt',encoding='utf-8-sig') as f:return [json.loads(x) for x in f if x.strip()]
    if p.suffix=='.jsonl':return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    return json.loads(p.read_text(encoding='utf-8-sig'))

def js(name,x):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(safe(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def csv(name,x):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    d=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x)
    if not len(d.columns):d=pd.DataFrame(columns=['status'])
    kw={'compression':{'method':'gzip','mtime':0}} if p.suffix=='.gz' else {}
    d.to_csv(p,index=False,float_format='%.12g',**kw);return d

def seed(*x):return int(hashlib.sha256('|'.join(map(str,x)).encode()).hexdigest()[:8],16)

def scope_collapse(x):
    x=str(x or '').lower().strip()
    if x.startswith('oos') or x.startswith('out_of_scope'):return 'oos'
    if x in ('normal','in_scope','in-scope'):return 'in_scope'
    return 'unknown'

def finite_median(a):
    a=np.asarray(a,float);return float(np.median(a[np.isfinite(a)])) if np.isfinite(a).any() else np.nan

def paired_ci(d,column,group='building',repeats=2000):
    z=d[[group,column]].dropna();a=z.groupby(group)[column].agg(['sum','count'])
    r=dict(n=len(z),groups=len(a),delta=z[column].mean() if len(z) else np.nan,lo=np.nan,hi=np.nan,group_macro=z.groupby(group)[column].mean().mean() if len(z) else np.nan)
    if len(a)>1:
        v=a.to_numpy();rng=np.random.default_rng(SEED);ii=rng.integers(len(v),size=(repeats,len(v)));w=v[ii].sum(1);q=w[:,0]/w[:,1];r.update(lo=np.quantile(q,.025),hi=np.quantile(q,.975))
    return r

def classify(n,invalid,modes,singletons,early,cumulative,interval,any_stable,late_change,k=7,h=19,x=3,smax=.1,q=.8,medium='cumulative'):
    if invalid:return '', 'invalid_response_evidence'
    if n<4:return '', 'insufficient_people'
    if 1<=modes<=2 and singletons<=smax+1e-10 and early>=q-1e-10:return 'simple','assigned_observed_early'
    later=cumulative if medium=='cumulative' else interval
    if n>=10 and 1<=modes<=x and singletons<=smax+1e-10 and early<q-1e-10 and later>=q-1e-10:return 'medium','assigned_observed_later'
    if modes>=1 and singletons<=smax+1e-10 and any_stable>=q-1e-10:return '', 'stable_outside_three_tier_limits'
    ns=int(round(singletons*n))
    if n>=10 and modes+ns>=5 and ns>=2 and singletons>=.2-1e-10 and late_change:return 'difficult_candidate','assigned_observed_fragmentation_and_change'
    if n<10:return '', 'limited_horizon_or_order_sensitive'
    if singletons>smax+1e-10:return '', 'singleton_support_unresolved'
    return '', 'order_sensitive_or_other_trajectory'

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('stage',choices=['prepare','targets']);args=a.parse_args()
    if args.stage=='prepare':
        from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_prepare import run
    else:
        from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_targets import run
    run()
