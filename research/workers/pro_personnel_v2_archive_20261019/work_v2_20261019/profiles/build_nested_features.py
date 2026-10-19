#!/usr/bin/env python3
"""Double-building exclusion for reverse-route training feature cross fitting.

For an outer target building, every training image's feature excludes both the
outer building and its own building. The corresponding test feature is the
single-building fold in fold_profiles.csv. This avoids using a training answer's
own geometric quality to predict its answer-cluster membership.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse,itertools,time
from pathlib import Path
import numpy as np
import pandas as pd
from run_profiles import sufficient,solve,js,digest,DIFFS

def cache_parts(d,outcome,workers):
    parts={b:sufficient(g,outcome,workers)for b,g in d.groupby('building_id')}
    z=np.zeros((len(workers),len(workers)));v=np.zeros(len(workers))
    for a,b in parts.values():z+=a;v+=b
    return z,v,parts
def minus(c,excluded):
    a,b,parts=c;a=a.copy();b=b.copy()
    for ex in excluded:
        if ex in parts:a-=parts[ex][0];b-=parts[ex][1]
    return a,b
def support_cells(d,excluded,workers):
    out={w:(0,0)for w in workers}
    for w,g in d[~d.building_id.isin(excluded)].groupby('worker_id'):out[w]=(g.task.nunique(),g.building_id.nunique())
    return out
def fast_effect(c,excluded,workers,sups):
    A,b=minus(c,excluded);C=np.array([sups[w][0]>0 for w in workers],float)
    r=solve(A,b,C);return {w:(r[i]if C[i]else np.nan)for i,w in enumerate(workers)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path('work_v2_20261019/profiles'));args=ap.parse_args();out=args.out;t0=time.time()
    d=pd.read_csv(out/'records_flat.csv');m=d[d.quality_usable&d.condition.eq('manual')&d.quality_use.eq('ordinary_primary')].copy();ts=d[d.pool_analysis_eligible&d.condition.eq('manual')&d.ordinary_difficulty_eligible&d.difficulty.isin(DIFFS)&d.source_active_time_seconds.gt(0)].copy();ts['task']=ts.source_task;ts['log_time']=np.log(ts.source_active_time_seconds)
    ws=sorted(m.worker_id.unique());tw=sorted(ts.worker_id.unique());buildings=sorted(m.building_id.unique());qc=cache_parts(m,'B8L2',ws);dc={di:cache_parts(m[m.difficulty.eq(di)],'B8L2',ws)for di in DIFFS};tc=cache_parts(ts,'log_time',tw);ocs={o:(cache_parts(g,'log_time',sorted(g.worker_id.unique())),sorted(g.worker_id.unique()),g)for o,g in ts.groupby('origin')}
    rows=[];cache={};M=len(ws)
    for j,ex in enumerate(itertools.combinations(buildings,2)):
        qs=support_cells(m,ex,ws);bs=fast_effect(qc,ex,ws,qs);ds={di:support_cells(m[m.difficulty.eq(di)],ex,ws)for di in DIFFS}
        A=np.zeros((3*M,3*M));b=np.zeros(3*M)
        for i,di in enumerate(DIFFS):
            a,v=minus(dc[di],ex);sl=slice(i*M,(i+1)*M);A[sl,sl]=a;b[sl]=v
        A+=20*np.kron(np.eye(3)-np.ones((3,3))/3,np.eye(M));C=np.kron(np.eye(3),np.array([qs[w][0]>0 for w in ws],float)[:,None]);th=solve(A,b,C)
        ss=support_cells(ts,ex,tw);tv=fast_effect(tc,ex,tw,ss);ov={}
        for oc,ow,od in ocs.values():ov.update(fast_effect(oc,ex,ow,support_cells(od,ex,ow)))
        for outer,inner in [ex,ex[::-1]]:
            for i,w in enumerate(ws):
                r=dict(outer_heldout_building=outer,inner_heldout_building=inner,worker_id=w,Q_effect_B8L2=bs[w],Q_supported=qs[w][0]>=6 and qs[w][1]>=3,Q_tasks=qs[w][0],Q_buildings=qs[w][1],T_source_effect=tv.get(w,np.nan),T_source_origin_effect=ov.get(w,np.nan),T_source_supported=ss.get(w,(0,0))[0]>=6 and ss.get(w,(0,0))[1]>=3)
                for k,di in enumerate(DIFFS):r[f'theta_{di}_B8L2']=th[k*M+i]if qs[w][0]else np.nan;r['difficulty_supported_'+di]=ds[di][w][0]>=6 and ds[di][w][1]>=3
                r['hard_minus_easy_B8L2']=r['theta_hard_B8L2']-r['theta_easy_B8L2'];r['hard_minus_medium_B8L2']=r['theta_hard_B8L2']-r['theta_medium_B8L2'];rows.append(r)
        if j%25==0:print('pairs',j+1,'of',len(buildings)*(len(buildings)-1)//2,flush=True)
    pd.DataFrame(rows).to_csv(out/'nested_fold_features.csv',index=False)
    js(out/'NESTED_FEATURE_RECEIPT.json',{'rows':len(rows),'outer_folds':len(buildings),'double_excluded_sets':len(buildings)*(len(buildings)-1)//2,'elapsed_seconds':time.time()-t0,'source_profiles_code_sha256':digest(Path(__file__).with_name('run_profiles.py')),'code_sha256':digest(Path(__file__)),'training_rule':'exclude both outer validation building and training sample building','test_rule':'single outer-building exclusion from fold_profiles.csv','no_target_geometry_labels_used_in_person_features':True})
    print('COMPLETE',len(rows),time.time()-t0,flush=True)
if __name__=='__main__':main()
