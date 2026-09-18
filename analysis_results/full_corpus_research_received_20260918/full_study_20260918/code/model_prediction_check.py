"""Small nested leave-building-out prediction check; post-hoc exploratory.
Target is empirical human pairwise spherical dispersion, not intrinsic difficulty or semantic truth.
Only observed manual groups with at least 5 computable persons are included.
"""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(k,'1')
from pathlib import Path
import json
import numpy as np,pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
import legacy_reproduction as old
R=Path(__file__).resolve().parents[1]
def run():
    t=pd.read_csv(R/'results/model_linkage_targets.csv');f=pd.read_csv(R/'results/model_image_features.csv')
    t=t[(t.condition=='manual')&(t.N_human_spherical>=5)&t.human_mean_pair_solid_distance.notna()].merge(f,on=['image_id','building'],validate='many_to_one')
    counts=[c for c in f if c.endswith('_corners')];gaps=[c for c in f if c.startswith('gap_')];rotation=[c for c in f if c.startswith('rotation_')]
    configs={'global_mean':[],'model_counts':counts,'bi_head_gap':['gap_bi_enclosed__bi_extended'],'model_counts_and_gaps':counts+gaps,'counts_gaps_rotation':counts+gaps+rotation}
    builds=t.building.unique();rows=[];tuning=[]
    for b in builds:
        tr=t[t.building!=b];te=t[t.building==b];y=tr.human_mean_pair_solid_distance.to_numpy()
        for name,cols in configs.items():
            if not cols:p=np.repeat(y.mean(),len(te));alpha=None
            else:
                X=tr[cols].to_numpy();best=None
                for a in [.1,1.,10.,100.,1000.]:
                    cv=GroupKFold(n_splits=min(4,tr.building.nunique()));errs=[]
                    for ii,jj in cv.split(X,y,tr.building):
                        model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(),Ridge(alpha=a))
                        model.fit(X[ii],y[ii]);pred=np.clip(model.predict(X[jj]),0,1);errs.extend(abs(pred-y[jj]))
                    loss=float(np.mean(errs));tuning.append(dict(heldout_building=b,model=name,alpha=a,inner_mae=loss))
                    if best is None or loss<best[0]:best=(loss,a)
                alpha=best[1];model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(),Ridge(alpha=alpha));model.fit(X,y);p=np.clip(model.predict(te[cols].to_numpy()),0,1)
            for k,(_,r) in enumerate(te.iterrows()):rows.append(dict(image_id=r.image_id,code=r.code,building=b,N=int(r.N_human_spherical),model=name,target=float(r.human_mean_pair_solid_distance),prediction=float(p[k]),absolute_error=abs(p[k]-r.human_mean_pair_solid_distance),alpha=alpha))
    df=pd.DataFrame(rows);df.to_csv(R/'results/model_dispersion_lobo_predictions.csv',index=False);pd.DataFrame(tuning).to_csv(R/'results/model_dispersion_inner_tuning.csv',index=False)
    scores=df.groupby('model').agg(N=('image_id','size'),MAE=('absolute_error','mean')).reset_index();scores.to_csv(R/'results/model_dispersion_lobo_scores.csv',index=False)
    base=df[df.model=='global_mean'][['image_id','absolute_error']].rename(columns={'absolute_error':'base_error'});q=df.merge(base,on='image_id');q['delta']=q.absolute_error-q.base_error
    rng=np.random.default_rng(20260918);boot=[]
    for name,z in q.groupby('model'):
        g=z.groupby('building').delta.agg(['sum','count']);draw=rng.integers(0,len(g),size=(4000,len(g)));vals=g['sum'].to_numpy()[draw].sum(1)/g['count'].to_numpy()[draw].sum(1)
        boot.append(dict(model=name,delta_MAE=float(z.delta.mean()),cluster_bootstrap_low=float(np.quantile(vals,.025)),cluster_bootstrap_high=float(np.quantile(vals,.975)),buildings=len(g),draws=4000))
    pd.DataFrame(boot).to_csv(R/'results/model_dispersion_delta_bootstrap.csv',index=False)
    old.save_json(R/'results/model_prediction_scope.json',dict(images=len(t),buildings=t.building.nunique(),condition='manual',minimum_spherical_people=5,target='historical_mean_pairwise_solid_angle_distance',person_features_fitted=False,semantic_clustering_validation=False,model_weights_retrained=False,feature_sets=configs,outer='leave_one_building_out',inner='4-fold building-group CV, MAE',bootstrap='descriptive resampling of saved outer errors by building, not independent validation or refit'))
    print(scores.to_string(index=False));print(pd.DataFrame(boot).to_string(index=False))
if __name__=='__main__':run()
