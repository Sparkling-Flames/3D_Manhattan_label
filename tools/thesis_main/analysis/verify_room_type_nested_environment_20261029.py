"""Compare nested-selection reproduction with each saved prediction environment."""
import json
import sys
import numpy as np
import pandas as pd
import sklearn
from .room_type_v21_reference_attribution_20261029 import BASE, OUT, TARGET, METHODS, prepare, fit_nested


def main():
    sys.path.insert(0,str(BASE/'code'));import image_similarity as engine
    support=pd.read_csv(OUT/'inputs/SUPPORT.csv');checks={}
    for label,keys,inputs,savedir in [
        ('v2_original177',set(support.loc[support.support.eq('original_support'),'image_key']),BASE/'inputs/images.csv',BASE/'results/image'),
        ('v21_all206',set(support.image_key),OUT/'inputs/images.csv',OUT/'results/image')]:
        pred,folds,tuning,splits=fit_nested(prepare(pd.read_csv(inputs),keys),engine)
        saved=pd.read_csv(savedir/'LOBO_IMAGE_PREDICTIONS.csv.gz');saved=saved[(saved.metric=='Q')&saved.method.isin(METHODS)]
        p=pred.merge(saved,on=['method','image_key'],validate='one_to_one',suffixes=('_check','_saved'))
        old=pd.read_csv(savedir/'LOBO_INNER_TUNING.csv.gz');old=old[(old.metric=='Q')&old.method.isin(METHODS)]
        t=tuning.merge(old,on=['method','held_out_building','family','alpha'],validate='one_to_one',suffixes=('_check','_saved'))
        assert len(p)==len(keys)*2 and len(t)==308
        pe=abs(p.predicted_check-p.predicted_saved);te=abs(t.inner_mae_check-t.inner_mae_saved)
        checks[label]=dict(prediction_rows=len(p),prediction_max_abs_difference=float(pe.max()),prediction_rows_above_1e_8=int(pe.gt(1e-8).sum()),candidate_rows=len(t),candidate_max_abs_difference=float(te.max()),candidate_rows_above_1e_8=int(te.gt(1e-8).sum()))
    assert checks['v21_all206']['prediction_rows_above_1e_8']==0 and checks['v21_all206']['candidate_rows_above_1e_8']==0
    result=dict(current_sklearn=sklearn.__version__,original_v2_recorded_sklearn='1.8.0',v21_all206_same_current_environment_reproduced=True,results=checks)
    (TARGET/'NESTED_ENVIRONMENT_CHECKS.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
