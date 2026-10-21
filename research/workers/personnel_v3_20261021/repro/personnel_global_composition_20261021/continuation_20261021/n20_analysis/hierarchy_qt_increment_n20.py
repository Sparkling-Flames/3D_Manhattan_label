"""Requested coarse/fine increment contrasts from already fitted common endpoints."""
import argparse
import numpy as np
import pandas as pd
from analyze_n20 import HERE, SEED, save, js


def analyze(condition):
    out=HERE/condition
    building=pd.read_csv(out/'N20_PREDICTION_BUILDINGS.csv.gz')
    keys=['condition','method_id','support_scope','design_anchor','family','weighting','outcome','target_panel']
    rows=[]
    pairs=[('QT_plus_coarse_source','QT_source'),('QT_plus_fine_source','QT_plus_coarse_source')]
    for vals,g in building.groupby(keys,dropna=False):
        wide=g.pivot(index='heldout_building',columns='model',values='mse')
        for new,base in pairs:
            if new not in wide or base not in wide:continue
            x=wide[[new,base]].dropna();gain=x[base]-x[new]
            rng=np.random.default_rng(SEED)
            if len(gain)>1:
                boot=gain.to_numpy()[rng.integers(len(gain),size=(2000,len(gain)))].mean(axis=1)
                lo,hi=np.quantile(boot,[.025,.975])
            else:lo=hi=np.nan
            rows.append(dict(zip(keys,vals),new_model=new,baseline=base,buildings=len(x),
                mse_new=x[new].mean(),mse_baseline=x[base].mean(),mse_gain=gain.mean(),
                relative_mse_gain=gain.mean()/x[base].mean() if x[base].mean()>1e-12 else np.nan,
                positive_buildings=int((gain>1e-12).sum()),negative_buildings=int((gain<-1e-12).sum()),
                bootstrap95_low=lo,bootstrap95_high=hi,
                status='postfit requested hierarchy contrast; no refitting or outcome-driven model selection'))
    save(pd.DataFrame(rows),out/'N20_HIERARCHY_QT_INCREMENT.csv')
    js(out/'N20_HIERARCHY_QT_INCREMENT_RECEIPT.json',dict(condition=condition,contrast_rows=len(rows),
        new_fusion=False,new_models=False,all_metrics_and_attempts_retained=True,
        contrasts=[{'new':n,'baseline':b} for n,b in pairs]))
    print(condition,'hierarchy QT contrasts',len(rows))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--condition',choices=['manual','semi'],required=True)
    analyze(p.parse_args().condition)
