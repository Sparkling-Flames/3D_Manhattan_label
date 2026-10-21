"""Independent held-building interpretation of newly frozen multivariable classes.

Reuses existing per-answer expression descriptors; does not refit a class or
change annotation/quality/vote qualifications. Prediction below concerns
relative within-image expression, not prospective absolute image quality.
"""
from __future__ import annotations
import os
for _k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_k]='1'
import json
import itertools
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
ROOT=STUDY.parents[2]
KEY=['condition','layer','image_id','reference_id']
EXPR=['turn_n','short_turn_edges','near_straight_nodes_5deg','log_area','log_height']
DOMAIN={'Q':['q_effect','q_downside'],'T':['t_effect','t_tail'],
        'D':['hard_minus_easy','medium_minus_easy'],
        'scope':['scope_out_effect'],'Semi':['semi_edit_effect','semi_error_nonedit_effect']}

def save(d,name):
    d.to_csv(HERE/name,index=False,encoding='utf-8-sig',compression={'method':'gzip','mtime':0} if name.endswith('.gz') else None)

def load():
    x=pd.read_csv(ROOT/'research/workers/personnel_marking_patterns_20261020/record_expression.csv')
    x['source_expression_layer']=x.layer
    # The old descriptor table's geometric layer calls a few qualified
    # special-range records ordinary. Preserve its source label, but report
    # their actual frozen quality-use domain separately in this study.
    x.loc[x.quality_use.eq('special_conditional_only'),'layer']='special_conditional'
    x['turn_n']=x.pair_n-x.near_straight_nodes_5deg
    use=x.personal_comparison & x.peer_n.ge(3)
    med=x.loc[use].groupby(KEY,dropna=False).turn_n.transform('median')
    x['turn_n_peer_delta']=x.turn_n-med
    x['behavior_observation']=use
    idx=pd.read_csv(ROOT/'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz')
    x=x.merge(idx[['object_id','B8L2','D10','source_active_time_seconds','time_source_kind']],on='object_id',validate='one_to_one')
    for metric in ('B8L2','D10'):
        ordinary_ok=~x.layer.eq('ordinary') | x.quality_use.eq('ordinary_primary')
        x.loc[~x.quality_usable | ~ordinary_ok,metric]=np.nan
        good=x.quality_usable & x[metric].notna()
        x[metric+'_peer_delta']=x[metric]-x.loc[good].groupby(KEY,dropna=False)[metric].transform('mean')
    good=x.primary_expression & x.source_active_time_seconds.gt(0)
    x['log_time']=np.where(good,np.log(x.source_active_time_seconds.where(good)),np.nan)
    x['log_time_peer_delta']=x.log_time-x.loc[good].groupby(KEY+['origin','time_source_kind'],dropna=False).log_time.transform('mean')
    labels=pd.read_csv(STUDY/'multivariate/labels_lobo.csv.gz')
    sens=STUDY/'multivariate/same_source_candidate_labels.csv'
    if sens.exists():
        ss=pd.read_csv(sens);ss=ss[ss.heldout_building.ne('ALL')]
        labels=pd.concat([labels,ss],ignore_index=True)
    features=pd.read_csv(STUDY/'multivariate/continuous_features_lobo.csv.gz')
    return x,labels,features

def hierarchical_mean(d,metric):
    return d.groupby(['building_id','image_id'],dropna=False)[metric].mean().groupby('building_id').mean()

def contrasts(x,labels):
    d=x.merge(labels[labels.known],left_on=['building_id','condition','worker_id'],right_on=['heldout_building','condition','worker_id'],validate='many_to_many')
    d=d[d.behavior_observation]
    metrics=EXPR+['B8L2','D10','log_time_peer_delta']
    rows=[]
    for (method,condition,layer,image,ref),g in d.groupby(['method_id']+KEY,dropna=False):
        for source in ('all','new','v1'):
            z=g if source=='all' else g[g.origin_x.eq(source)]
            for level in ('coarse_class','fine_class'):
                for a,b in itertools.combinations(sorted(z[level].unique()),2):
                    ga,gb=z[z[level].eq(a)],z[z[level].eq(b)]
                    if min(len(ga),len(gb))<2:continue
                    r=dict(method_id=method,condition=condition,layer=layer,image_id=image,reference_id=ref,
                           image_code=g.iloc[0].image_code,building_id=g.iloc[0].building_id,difficulty=g.iloc[0].difficulty,
                           source=source,level=level,class_a=a,class_b=b,n_a=len(ga),n_b=len(gb),
                           same_parent=len(set(pd.concat([ga,gb]).coarse_class))==1)
                    for m in metrics:
                        aa,bb=ga[m].dropna(),gb[m].dropna()
                        r[m+'_n_a'],r[m+'_n_b']=len(aa),len(bb)
                        r[m+'_difference']=bb.mean()-aa.mean() if min(len(aa),len(bb))>=2 else np.nan
                    rows.append(r)
    panels=pd.DataFrame(rows);save(panels,'NEW_CLASS_EXPRESSION_PANELS.csv.gz')
    group=['method_id','condition','layer','source','level','class_a','class_b','same_parent']
    out=[]
    for extra in ([],['difficulty']):
        for vals,g in panels.groupby(group+extra,dropna=False):
            r=dict(zip(group+extra,vals));r['difficulty']=r.get('difficulty','all');r.update(panels=len(g),images=g.image_id.nunique(),buildings=g.building_id.nunique())
            for m in metrics:
                y=m+'_difference';v=hierarchical_mean(g,y).dropna()
                r[m+'_building_mean']=v.mean();r[m+'_building_n']=len(v);r[m+'_positive_buildings']=int(v.gt(0).sum())
            out.append(r)
    save(pd.DataFrame(out),'NEW_CLASS_EXPRESSION_SUMMARY.csv')
    return panels

def balanced_weights(d):
    """References within image, images within building, buildings equally."""
    k=['building_id','image_id','reference_id']
    counts=d.groupby(k,dropna=False).size().rename('_people').reset_index()
    counts['_panels']=counts.groupby(['building_id','image_id'],dropna=False)._people.transform('size')
    ni=counts[['building_id','image_id']].drop_duplicates().groupby('building_id').size()
    counts['_images']=counts.building_id.map(ni)
    keys=pd.MultiIndex.from_frame(counts[k]);v=1/(counts._people*counts._panels*counts._images*len(ni))
    s=pd.Series(v.to_numpy(),index=keys)
    return s.reindex(pd.MultiIndex.from_frame(d[k])).to_numpy(float)

def fit_predict(train,test,fields,cats):
    # Fixed ridge; no hyperparameter search or outcome-based class selection.
    a=[np.ones(len(train)),train.origin.eq('new').to_numpy(float)]
    b=[np.ones(len(test)),test.origin.eq('new').to_numpy(float)]
    for field in fields:
        av=train[field].to_numpy(float);bv=test[field].to_numpy(float)
        mu=np.mean(av);sd=np.std(av)
        if sd<1e-9:sd=1.
        a.append((av-mu)/sd);b.append((bv-mu)/sd)
    for field in cats:
        for level in sorted(train[field].unique())[1:]:
            a.append(train[field].eq(level).to_numpy(float));b.append(test[field].eq(level).to_numpy(float))
    a=np.column_stack(a);b=np.column_stack(b);w=balanced_weights(train)
    p=np.eye(a.shape[1])*.01;p[0,0]=0
    beta=np.linalg.solve((a*w[:,None]).T@a+p,(a*w[:,None]).T@train._y.to_numpy(float))
    return b@beta

def prediction(x,labels,features):
    metrics=[m+'_peer_delta' for m in EXPR]+['B8L2_peer_delta','D10_peer_delta','log_time_peer_delta']
    results=[]
    for method,labs in labels.groupby('method_id'):
        condition=labs.condition.iloc[0]
        entered=labs.domains.iloc[0].split('+')
        fields=sorted({s for dom in entered for s in DOMAIN[dom]})
        qt=DOMAIN['Q']+DOMAIN['T']
        for building,ls in labs.groupby('heldout_building'):
            ls=ls[ls.known][['worker_id','coarse_class','fine_class']]
            ff=features[features.condition.eq(condition)&features.heldout_building.eq(building)]
            # THE SAME outer-building-excluded personnel map is used on every
            # training and evaluation image, avoiding indirect target leakage.
            z=x[x.condition.eq(condition)&x.layer.eq('ordinary')&x.behavior_observation].merge(ls,on='worker_id',validate='many_to_one')
            z=z.merge(ff[['worker_id']+sorted(set(fields+qt))],on='worker_id',validate='many_to_one')
            z=z.dropna(subset=sorted(set(fields+qt)))
            for metric in metrics:
                dd=z[z[metric].notna()].copy();dd['_y']=dd[metric]
                train,test=dd[dd.building_id.ne(building)],dd[dd.building_id.eq(building)]
                if len(train)<100 or len(test)<10:continue
                models={'source':([],[]),'QT_continuous':(qt,[]),'coarse':([],['coarse_class']),
                        'fine':([],['fine_class']),'QT_plus_coarse':(qt,['coarse_class']),
                        'QT_plus_fine':(qt,['fine_class']),'entered_domains_continuous':(fields,[])}
                for version,(numeric,cats) in models.items():
                    pred=fit_predict(train,test,numeric,cats)
                    e=test[['building_id','image_id','reference_id']].copy();e['squared_error']=(test._y.to_numpy()-pred)**2;e['absolute_error']=abs(test._y.to_numpy()-pred)
                    def mean(c):return e.groupby(['image_id','reference_id'],dropna=False)[c].mean().groupby('image_id').mean().mean()
                    results.append(dict(method_id=method,condition=condition,heldout_building=building,outcome=metric,model=version,
                           training_records=len(train),test_records=len(test),test_images=test.image_id.nunique(),test_panels=len(e[['image_id','reference_id']].drop_duplicates()),
                           mse=mean('squared_error'),mae=mean('absolute_error'),label_source='one outer-building-excluded map for train and test'))
    per=pd.DataFrame(results);save(per,'NEW_CLASS_RAW_PREDICTION_BUILDINGS.csv')
    out=per.groupby(['method_id','condition','outcome','model'],as_index=False).agg(mse=('mse','mean'),mae=('mae','mean'),buildings=('heldout_building','nunique'),test_records=('test_records','sum'),test_images=('test_images','sum'))
    save(out,'NEW_CLASS_RAW_PREDICTION_SUMMARY.csv')

def main():
    x,l,f=load();contrasts(x,l);prediction(x,l,f)
    (HERE/'EXPRESSION_CHECK_CONTRACT.json').write_text(json.dumps(dict(
        inputs=['personnel_marking_patterns_20261020/record_expression.csv','personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz','../multivariate/labels_lobo.csv.gz','../multivariate/continuous_features_lobo.csv.gz'],
        behavioral_inventory_records=len(x),label_methods=sorted(l.method_id.unique()),
        directions='class_b minus class_a; >=2 nonmissing workers per class in same image, condition and reference',
        aggregation='reference panels equally within image, images equally within building, then buildings equally',
        repeated_validation='exploratory held-building check on already studied inventory, not a fresh blind test',
        prediction='relative peer-centered expression or score; does not predict unseen absolute room quality',
        predictor_training='Outer target building excluded for labels, scaling and history. Same outer label/history map applied to all training images.',
        ridge_penalty=.01,score_qualification_unchanged=True,reference_qualification_unchanged=True,
        source_time='source seconds; log relative within same image/origin/time-source; not target editing wall-clock'),ensure_ascii=False,indent=2)+'\n')
    print('Saved new-class held-building expression and incremental prediction checks.')

if __name__=='__main__':main()
