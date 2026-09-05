"""Targeted, retrospective reanalysis; does not assign final worker types.
Inputs are byte-verified against main 11a72ff. Peer distance is not GT error.
Building split-half rank correlations measure stability in these observed tasks,
not new-worker generalization. Cross-validation evaluates within-task contrasts.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from scipy.cluster.hierarchy import linkage, fcluster
from sklearn.metrics import adjusted_rand_score
ROOT=Path(__file__).parent
D=pd.read_csv(ROOT/'c1_targeted_rows.csv')
G=pd.read_csv(ROOT/'inputs/legacy_rq1/c1_geometry_repair_audit.csv')
keys=['project_id','runtime_task_id','worker_id','annotation_id']
D=D.drop(columns=['repair_applied'],errors='ignore').merge(G[keys+['repair_applied']],on=keys,validate='one_to_one')
D['corner_pair_count']=(D.raw_point_count-D.repair_applied.astype(int))/2
assert ((D.corner_pair_count%1)==0).all()
D['log_active_time']=np.log1p(D.active_time_seconds)
D['peer_centered']=D.peer_distance_mean-D.groupby('base_task_id').peer_distance_mean.transform('mean')
D.to_csv(ROOT/'c1_targeted_rows.csv',index=False)
metrics=['peer_distance_mean','corner_pair_count','log_active_time']

def fit(df,metric,weights=None):
    d=df.dropna(subset=[metric]).copy()
    workers=sorted(d.worker_id.unique())
    X=(d.worker_id.to_numpy()[:,None]==np.array(workers)[None,:]).astype(float)
    y=d[metric].to_numpy(float)
    taskcode,_=pd.factorize(d.base_task_id)
    for i in np.unique(taskcode):
        ix=taskcode==i; X[ix]-=X[ix].mean(axis=0);y[ix]-=y[ix].mean()
    if weights is not None:
        w=np.sqrt(np.asarray(weights));X=X*w[:,None];y=y*w
    rank=int(np.linalg.matrix_rank(X))
    if rank != len(workers)-1:
        raise ValueError(f'Disconnected or unidentifiable worker-task design: rank={rank}, workers={len(workers)}')
    coef=np.linalg.lstsq(X,y,rcond=None)[0];coef-=coef.mean()
    pred=X@coef
    return pd.Series(coef,index=workers),pd.DataFrame({'worker_id':d.worker_id.to_numpy(),'task':d.base_task_id.to_numpy(),'y_centered':y,'pred':pred,'residual':y-pred}),np.linalg.matrix_rank(X)

def heldout_within_task(d,metric):
    out=[]
    for b in sorted(d.building_id.unique()):
        tr=d[d.building_id!=b].dropna(subset=[metric]);te=d[d.building_id==b].dropna(subset=[metric]).copy()
        c,_,_=fit(tr,metric);te=te[te.worker_id.isin(c.index)]
        p=te.worker_id.map(c).to_numpy()
        te['pred']=p-te.groupby('base_task_id').worker_id.transform(lambda v: v.map(c).mean())
        te['y_centered']=te[metric]-te.groupby('base_task_id')[metric].transform('mean')
        for r in te[['worker_id','base_task_id','building_id','y_centered','pred']].to_dict('records'):out.append(r)
    z=pd.DataFrame(out);sse=float(((z.y_centered-z.pred)**2).sum());sst=float((z.y_centered**2).sum())
    return {'metric':metric,'heldout_rows':len(z),'task_only_sse':sst,'worker_task_sse':sse,'lobo_within_task_r2':1-sse/sst,'baseline_within_task_rmse':np.sqrt(sst/len(z)),'worker_within_task_rmse':np.sqrt(sse/len(z))},z

summary=[];profile=[];cv=[];stability=[];cluster=[]
variants={'all_calculation_valid':D,'strict_clean_tasks':D[~D.base_task_id.isin(D.loc[D.repair_applied,'base_task_id'])]}
for variant,data in variants.items():
    for m in metrics:
        c,r,rank=fit(data,m)
        s,z=heldout_within_task(data,m);s['variant']=variant;summary.append(s)
        z['metric']=m;z['variant']=variant;cv.extend(z.to_dict('records'))
        for w,coef in c.items():
            rr=r[r.worker_id==w].residual
            profile.append({'variant':variant,'metric':m,'worker_id':int(w),'effect':float(coef),'residual_sd':float(rr.std(ddof=1)),'residual_MAD':float((rr-rr.median()).abs().median()),'rows':len(rr),'design_rank':int(rank),'worker_count':len(c)})
    rng=np.random.default_rng(20260905)
    buildings=np.array(sorted(data.building_id.unique()))
    for rep in range(300):
        a=set(rng.permutation(buildings)[:len(buildings)//2]); da=data[data.building_id.isin(a)];db=data[~data.building_id.isin(a)]
        pa,pb={},{}
        for m in metrics:
            ca,_,_=fit(da,m);cb,_,_=fit(db,m);wi=ca.index.intersection(cb.index)
            rho=spearmanr(ca[wi],cb[wi]).statistic
            stability.append({'variant':variant,'replicate':rep,'metric':m,'n_workers':len(wi),'rank_rho':rho})
            pa[m]=ca;pb[m]=cb
        for mode,columns in {'geometry_only':metrics[:2],'geometry_and_time':metrics}.items():
            A=pd.DataFrame({m:pa[m] for m in columns});B=pd.DataFrame({m:pb[m] for m in columns});ix=A.dropna().index.intersection(B.dropna().index)
            xa=A.loc[ix].to_numpy();xb=B.loc[ix].to_numpy();xa=(xa-xa.mean(0))/xa.std(0);xb=(xb-xb.mean(0))/xb.std(0)
            for k in (2,3,4):
                la=fcluster(linkage(xa,method='ward'),k,criterion='maxclust');lb=fcluster(linkage(xb,method='ward'),k,criterion='maxclust')
                cluster.append({'variant':variant,'replicate':rep,'features':mode,'k':k,'ari':adjusted_rand_score(la,lb),'n_workers':len(ix)})
pd.DataFrame(summary).to_csv(ROOT/'profile_lobo_cv.csv',index=False)
pd.DataFrame(profile).to_csv(ROOT/'continuous_worker_profiles.csv',index=False)
pd.DataFrame(cv).to_csv(ROOT/'profile_heldout_rows.csv',index=False)
stab=pd.DataFrame(stability);stab.to_csv(ROOT/'profile_split_stability.csv',index=False)
cl=pd.DataFrame(cluster);cl.to_csv(ROOT/'cluster_split_stability.csv',index=False)
ss=stab.groupby(['variant','metric']).rank_rho.agg(['median',lambda x:x.quantile(.25),lambda x:x.quantile(.75)]);ss.columns=['median_rho','q25','q75'];ss.reset_index().to_csv(ROOT/'profile_stability_summary.csv',index=False)
cs=cl.groupby(['variant','features','k']).ari.agg(['median',lambda x:x.quantile(.25),lambda x:x.quantile(.75)]);cs.columns=['median_ari','q25','q75'];cs.reset_index().to_csv(ROOT/'cluster_stability_summary.csv',index=False)
print('LOBO\n',pd.DataFrame(summary).to_string(index=False));print('STABILITY\n',ss.to_string());print('CLUSTER\n',cs.to_string())
