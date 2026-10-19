#!/usr/bin/env python3
"""Meaningful input, leakage, old-method, and double-exclusion checks."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse,json,time
from pathlib import Path
import numpy as np
import pandas as pd
from run_profiles import fit_fe,fit_joint,support,DIFFS,METRICS,js,digest

def old_separate_replay(main):
    result=[]
    for metric in METRICS:
        for b in sorted(main.building_id.unique()):
            tr=main[main.building_id.ne(b)].copy();te=main[main.building_id.eq(b)]
            def infofit(d):
                d=d[d.groupby('task').worker_id.transform('size')>=2].copy();fit,inf=fit_fe(d,metric)
                return {w:e for w,e in fit.items() if inf['nullity']==1 and support(d[d.worker_id.eq(w)])}
            general=infofit(tr)
            for di,g in te.groupby('difficulty'):
                sp=infofit(tr[tr.difficulty.eq(di)]);x=g[g.worker_id.isin(general)&g.worker_id.isin(sp)].copy();x=x[x.groupby('task').worker_id.transform('size')>=2]
                if x.empty:continue
                x['general']=x.worker_id.map(general);x['specialized']=x.worker_id.map(sp)
                for col in [metric,'general','specialized']:x[col+'_c']=x[col]-x.groupby('task')[col].transform('mean')
                x['target']=x[metric+'_c'];x['baseline_sqerr']=x.target**2;x['general_sqerr']=(x.target-x.general_c)**2;x['specialized_sqerr']=(x.target-x.specialized_c)**2
                x['metric']=metric;result.append(x[['metric','object_id','worker_id','building_id','image_id','difficulty','target','general_c','specialized_c','baseline_sqerr','general_sqerr','specialized_sqerr']])
    pred=pd.concat(result,ignore_index=True);summ=[]
    for metric,d in pred.groupby('metric'):
        for di in ['all',*DIFFS]:
            g=d if di=='all' else d[d.difficulty.eq(di)];v=g.groupby(['building_id','image_id'])[['baseline_sqerr','general_sqerr','specialized_sqerr']].mean().groupby('building_id').mean();a=v.mean()
            summ.append(dict(metric=metric,difficulty=di,n=len(g),images=g.image_id.nunique(),buildings=len(v),**a.to_dict(),specialized_gain_over_general=1-a.specialized_sqerr/a.general_sqerr,buildings_improved=int((v.specialized_sqerr<v.general_sqerr).sum())))
    return pred,pd.DataFrame(summ)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path('work_v2_20261019/profiles'));ap.add_argument('--repo',type=Path,default=Path('repo_main_20261019'));a=ap.parse_args();out=a.out;repo=a.repo;t0=time.time();d=pd.read_csv(out/'records_flat.csv');m=d[d.quality_usable&d.condition.eq('manual')&d.quality_use.eq('ordinary_primary')].copy();f=pd.read_csv(out/'fold_profiles.csv');full=pd.read_csv(out/'full_profiles.csv');checks={}
    assert len(f)==22*60 and not f.duplicated(['heldout_building','worker_id']).any();checks['fold_rows']=len(f)
    checks['quality_population_60_but_supported_59']=dict(workers=len(full),Q_supported=int(full.Q_supported.sum()),Q_unknown=full.loc[~full.Q_supported,'worker_id'].tolist())
    assert full.loc[~full.Q_supported,'worker_id'].tolist()==['W022']
    errors=[];negative_leakage=[]
    for b,g in f.groupby('heldout_building'):
        tr=m[m.building_id.ne(b)]
        assert b not in set(tr.building_id)
        be,inf=fit_fe(tr,'B8L2');th=fit_joint(tr,'B8L2',20)
        for _,r in g.iterrows():
            if r.worker_id not in be:
                assert pd.isna(r.Q_effect_B8L2) and not r.Q_supported;continue
            errors.append(abs(r.Q_effect_B8L2-be[r.worker_id]))
            for di in DIFFS:errors.append(abs(r[f'theta_{di}_B8L2']-th[(r.worker_id,di)]))
            assert bool(r.Q_supported)==support(tr[tr.worker_id.eq(r.worker_id)])
        negative_leakage.append(dict(heldout_building=b,train_rows=len(tr),test_rows=int(m.building_id.eq(b).sum()),train_object_id_sha256=__import__('hashlib').sha256('\n'.join(sorted(tr.object_id)).encode()).hexdigest(),train_buildings=';'.join(sorted(tr.building_id.unique())),test_building_present_in_training=False,connectivity_nullity=int(inf['nullity'])))
    assert max(errors)<1e-9;checks['all_22_fold_Q_theta_max_abs_error']=max(errors);pd.DataFrame(negative_leakage).to_csv(out/'fold_training_membership_audit.csv',index=False)
    # Poison target-building values and refit only outside. This explicitly
    # checks that target labels and scores cannot alter historical features.
    b=sorted(m.building_id.unique())[0];poison=m.copy();poison.loc[poison.building_id.eq(b),'B8L2']=1e9
    ba,_=fit_fe(m[m.building_id.ne(b)],'B8L2');bb,_=fit_fe(poison[poison.building_id.ne(b)],'B8L2');pe=max(abs(ba[w]-bb[w])for w in ba);assert pe==0;checks['heldout_score_poison_max_feature_change']=pe
    nested=pd.read_csv(out/'nested_fold_features.csv');samples=nested[['outer_heldout_building','inner_heldout_building']].drop_duplicates().iloc[[0,40,123,240,400]]
    ne=[]
    for row in samples.itertuples(index=False):
        ex=[row.outer_heldout_building,row.inner_heldout_building];tr=m[~m.building_id.isin(ex)];be,_=fit_fe(tr,'B8L2');th=fit_joint(tr,'B8L2',20);g=nested[nested.outer_heldout_building.eq(ex[0])&nested.inner_heldout_building.eq(ex[1])]
        for _,r in g.iterrows():
            if r.worker_id not in be:assert not r.Q_supported;continue
            ne.append(abs(r.Q_effect_B8L2-be[r.worker_id]));ne.extend(abs(r[f'theta_{di}_B8L2']-th[(r.worker_id,di)])for di in DIFFS)
    assert max(ne)<1e-8;checks['nested_double_exclusion_max_abs_error']=max(ne)
    pred,rep=old_separate_replay(m[m.v1_development_member]);published=pd.read_csv(repo/'research/workers/worker_difficulty_profiles_20261018/validation_summary.csv');cmp=rep.merge(published,on=['metric','difficulty'],suffixes=('_new','_old'),validate='one_to_one');num=['n','images','buildings','baseline_sqerr','general_sqerr','specialized_sqerr','specialized_gain_over_general','buildings_improved'];errors={c:float((cmp[c+'_new']-cmp[c+'_old']).abs().max())for c in num};assert max(errors.values())<1e-8
    rep.to_csv(out/'v1_original_separate_difficulty_replay.csv',index=False);pred.to_csv(out/'v1_original_separate_difficulty_predictions.csv.gz',index=False,compression='gzip');checks['original_difficulty_scheme_summary_max_error']=errors
    checks['old_hard_claim_confirmed']=rep[(rep.metric=='B8L2')&rep.difficulty.eq('hard')].to_dict('records')[0]
    checks['target_definition']={'primary':'heldout y_i-mean(y_other supported evaluation workers in exact same task); prediction beta_i-mean(beta_other); paired comparisons first intersect exact workers','absolute':'training-only task-balanced difficulty intercept plus historical worker effect','test_y_used_for_profile_or_classification':False,'test_task_mean_used_as_absolute_prediction_intercept':False}
    checks['source_time_is_not_target_time']=dict(inventory_source=int(d.source_active_time_seconds.notna().sum()),inventory_target=int(d.target_matched_time_seconds.notna().sum()),main_source=int(m.source_active_time_seconds.notna().sum()),main_target=int(m.target_matched_time_seconds.notna().sum()))
    checks['runtime_seconds']=time.time()-t0;checks['code_sha256']=digest(Path(__file__));checks['all_passed']=True;js(out/'AUDIT_CHECKS.json',checks);print(json.dumps(checks,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
