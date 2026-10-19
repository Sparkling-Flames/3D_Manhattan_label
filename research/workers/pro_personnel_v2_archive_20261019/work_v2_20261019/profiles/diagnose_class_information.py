#!/usr/bin/env python3
"""Separate Q amplitude discretization from information in difficulty shapes.

No classification or team-selection rule changes. This explanatory diagnostic
compares the already frozen type with an already frozen finer-Q baseline, and
adds only a type's difficulty deviation to each person's continuous global Q.
"""
import argparse,hashlib,time
from pathlib import Path
import numpy as np
import pandas as pd
from run_profiles import DIFFS,METRICS,predict_fold,js,digest,SEED

def paired(pred,base,model):
    rows=[];keys=['object_id','worker_id','image_id','building_id','difficulty','task']
    for metric,g in pred.groupby('metric'):
        a=g[g.model.eq(base)][keys+['observed','prediction_effect']].rename(columns={'prediction_effect':'base_effect'});b=g[g.model.eq(model)][keys+['prediction_effect']]
        d=a.merge(b,on=keys,validate='one_to_one').dropna(subset=['base_effect','prediction_effect']);n=d.groupby('task').worker_id.transform('size');d=d[n>=2];n=d.groupby('task').worker_id.transform('size')
        y=(d.observed-d.groupby('task')['observed'].transform('mean'))*n/(n-1);p0=(d.base_effect-d.groupby('task').base_effect.transform('mean'))*n/(n-1);p1=(d.prediction_effect-d.groupby('task').prediction_effect.transform('mean'))*n/(n-1);d['base']=(y-p0)**2;d['candidate']=(y-p1)**2
        for diff in ['all',*DIFFS]:
            x=d if diff=='all'else d[d.difficulty.eq(diff)];v=x.groupby(['building_id','image_id'])[['base','candidate']].mean().groupby('building_id').mean();m=len(v)
            if m<2:continue
            rng=np.random.default_rng(int(hashlib.sha256(f'{SEED}|information|{metric}|{base}|{model}|{diff}'.encode()).hexdigest()[:16],16));idx=rng.integers(0,m,(2000,m));p0=v.base.to_numpy();p1=v.candidate.to_numpy();delta=100*(p0[idx].mean(1)-p1[idx].mean(1))/p0[idx].mean(1)
            rows.append(dict(metric=metric,baseline=base,model=model,difficulty=diff,n=len(x),images=x.image_id.nunique(),buildings=m,baseline_mse=v.base.mean(),model_mse=v.candidate.mean(),improvement_percent=100*(v.base.mean()-v.candidate.mean())/v.base.mean(),ci_low=np.quantile(delta,.025),ci_high=np.quantile(delta,.975),improved_buildings=int((v.candidate<v.base).sum())))
    return pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path('work_v2_20261019/profiles'));out=ap.parse_args().out;t0=time.time();f=pd.read_csv(out/'fold_profiles.csv');d=pd.read_csv(out/'records_flat.csv');main=d[d.quality_usable&d.condition.eq('manual')&d.quality_use.eq('ordinary_primary')];original=pd.read_csv(out/'validation_predictions.csv.gz');extra=[]
    for b,p in f.groupby('heldout_building'):
        fits={}
        for metric in METRICS:
            fits[metric]={'models':{}}
            for typ in ['difficulty_type','fine_dtype','hard_adaptation']:
                mp={};known=~p[typ+'_'+metric].str.contains('unknown',regex=False)
                for _,g in p[known].groupby(typ+'_'+metric):
                    for di in DIFFS:
                        delta=(g[f'theta_{di}_{metric}']-g['Q_effect_'+metric]).mean()
                        for _,r in g.iterrows():mp[(r.worker_id,di)]=r['Q_effect_'+metric]+delta
                fits[metric]['models']['FE_plus_'+typ+'_delta']=mp
        extra.append(predict_fold(main[main.building_id.ne(b)],main[main.building_id.eq(b)],p,fits,'v2_full_5719'))
    ext=pd.concat(extra,ignore_index=True);ext.to_csv(out/'difficulty_increment_predictions.csv.gz',index=False,compression='gzip');pred=pd.concat([original,ext],ignore_index=True);tables=[paired(pred,'class_QT3','class_fine_dtype'),paired(pred,'class_QT3','class_fine_dtype_merged')]
    for m in ext.model.unique():tables.append(paired(pred,'FE',m));tables.append(paired(pred,'joint20',m))
    result=pd.concat(tables,ignore_index=True);result.to_csv(out/'fine_information_controls.csv',index=False)
    js(out/'INFORMATION_DIAGNOSTIC_RECEIPT.json',dict(completed=True,code_sha256=digest(Path(__file__)),runtime_seconds=time.time()-t0,classification_changed=False,fusion_selection_changed=False,not_new_blind_hypothesis=True,purpose='Quantify whether phenotype gains merely recover lost continuous Q amplitude; unknown types excluded, common peers reconstructed for each comparison'))
    print(result[(result.metric=='B8L2')&result.difficulty.isin(['all','hard'])].to_string(index=False))
if __name__=='__main__':main()
