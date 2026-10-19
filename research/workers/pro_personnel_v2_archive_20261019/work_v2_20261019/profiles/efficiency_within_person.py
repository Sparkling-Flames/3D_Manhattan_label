#!/usr/bin/env python3
"""Finite efficiency diagnostics requested separately from personnel labels.

Compare task-only and task+worker fixed effects within each time provenance.
Final minus reference point-pair count is a structural proxy, never omission gold.
"""
import argparse,time
from pathlib import Path
import numpy as np
import pandas as pd
from run_profiles import js,digest

OUTCOMES=['B8L2','declared_pair_count','pair_count_gap_proxy','absolute_pair_count_gap_proxy']

def residualize(A,codes):
    A=A.copy().astype(float)
    if not len(A):return A,0
    for it in range(1000):
        before=A.copy()
        for c in codes:
            n=np.bincount(c)
            for j in range(A.shape[1]):A[:,j]-=(np.bincount(c,weights=A[:,j])/n)[c]
        if np.max(np.abs(A-before))<1e-11:return A,it+1
    raise RuntimeError('fixed-effect alternating projections did not converge')

def regress(d,worker=False):
    a=d[['task','worker_id','log_time',*OUTCOMES]].dropna().copy()
    a=a[a.groupby('task').worker_id.transform('size')>=2]
    codes=[pd.factorize(a.task)[0]]
    if worker:codes.append(pd.factorize(a.worker_id)[0])
    R,it=residualize(a[['log_time',*OUTCOMES]].to_numpy(),codes);den=float(R[:,0]@R[:,0]);beta=R[:,0]@R[:,1:]/den if den>1e-14 else np.full(len(OUTCOMES),np.nan)
    return dict(zip(OUTCOMES,beta)),len(a),a.task.nunique(),it

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path('work_v2_20261019/profiles'));out=ap.parse_args().out;t0=time.time();d=pd.read_csv(out/'records_flat.csv');m=d[d.quality_usable&d.condition.eq('manual')&d.quality_use.eq('ordinary_primary')].copy();m=m[m.source_active_time_seconds.gt(0)];m['seconds']=m.source_active_time_seconds
    target=d[d.quality_usable&d.target_matched_time_seconds.gt(0)].copy();target['seconds']=target.target_matched_time_seconds
    panels=[('source_manual_v1',m[m.origin.eq('v1')]),('source_manual_new',m[m.origin.eq('new')]),('source_manual_pooled',m),('target_manual_418',target[target.condition.eq('manual')]),('target_semi_22',target[target.condition.eq('semi')])]
    rows=[];raw=[]
    for panel,g in panels:
        g=g.copy();g['log_time']=np.log(g.seconds);g['pair_count_gap_proxy']=g.declared_pair_count-g.reference_pair_count;g['absolute_pair_count_gap_proxy']=g.pair_count_gap_proxy.abs();lo,hi=g.seconds.quantile([.01,.99]);trim=g[g.seconds.between(lo,hi)]
        raw.append(dict(panel=panel,n=len(g),images=g.image_id.nunique(),buildings=g.building_id.nunique(),workers=g.worker_id.nunique(),time_p01=lo,time_p99=hi,trimmed_n=len(trim),target_time_is_source_overlap=bool(g.source_active_time_seconds.eq(g.target_matched_time_seconds).all())if panel.startswith('target')else None))
        for sample,z in [('all_positive',g),('trim_1_99_percentile',trim)]:
            for worker in [False,True]:
                b,n,tasks,it=regress(z,worker);folds={y:[]for y in OUTCOMES}
                # Building jackknife gives clustered uncertainty; it is not a
                # random allocation or causal estimate of taking more time.
                buildings=sorted(z.building_id.unique())
                if len(buildings)>=3:
                    for ex in buildings:
                        c,_,_,_=regress(z[z.building_id.ne(ex)],worker)
                        for y in OUTCOMES:folds[y].append(c[y])
                for y in OUTCOMES:
                    f=np.array(folds[y]);f=f[np.isfinite(f)];nb=len(f);se=np.sqrt((nb-1)/nb*np.sum((f-f.mean())**2))if nb>1 else np.nan
                    rows.append(dict(panel=panel,sample=sample,adjustment='task_and_worker_FE'if worker else'task_FE',outcome=y,n=n,images=tasks,buildings=len(buildings),workers=z.worker_id.nunique(),coefficient_per_log_second=b[y],effect_for_doubling_seconds=b[y]*np.log(2),building_jackknife_se=se,ci_low=b[y]-1.96*se,ci_high=b[y]+1.96*se,doubling_ci_low=(b[y]-1.96*se)*np.log(2),doubling_ci_high=(b[y]+1.96*se)*np.log(2),projection_iterations=it))
    p=pd.DataFrame(rows);p.to_csv(out/'efficiency_within_person_diagnostics.csv',index=False);pd.DataFrame(raw).to_csv(out/'efficiency_diagnostic_coverage.csv',index=False)
    js(out/'EFFICIENCY_DIAGNOSTIC_RECEIPT.json',dict(completed=True,code_sha256=digest(Path(__file__)),runtime_seconds=time.time()-t0,target_n=len(target),target_same_as_source_n=int(target.source_active_time_seconds.eq(target.target_matched_time_seconds).sum()),target_is_independent_replication=False,cohort_sources_not_calibrated=True,point_pair_gap_is_omission_gold=False,classifications_modified=False,causal_effect_claim=False))
    print(p[(p.outcome=='B8L2')&p['sample'].eq('all_positive')].to_string(index=False))
if __name__=='__main__':main()
