#!/usr/bin/env python3
"""Image-level room-purpose similarity and honest whole-building holdout.

All output comes from frozen original-answer v2 input tables. No fusion runs.
Run --part descriptive, prediction, or all. Objects and references are not edited.
"""
from __future__ import annotations
import argparse, hashlib, itertools, json, math, platform, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, PolynomialFeatures
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

SEED=2026102703
COMMIT='b9bcec809fbaec8ab055931a1abb7baa5db44dac'
MAJOR=['卧室','卫浴','通行与连接','起居与休闲','厨房与用餐','工作与学习']
GEO=['ref_turn5','ref_H','ref_short_edges','ref_min_horizontal_deg','ref_radius_p90_h']
ANN_METRICS=['Q','D10','annotation_turn5','turn_delta','near_straight_nodes_5deg','actual_simplification','omission','extension','bottom_bias_9','S_bottom_deg','dir','Hmean','log_area_ratio']
IMAGE_OUTCOMES=['mean_Q','mean_D10','sd_Q','p10_Q','low_Q50','mean_annotation_turn5','mean_turn_delta','mean_actual_simplification','mean_near_straight_nodes_5deg','mean_omission','mean_extension','mean_bottom_bias_9','mean_S_bottom_deg','mean_dir','mean_Hmean']

def save(df,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(path,index=False,compression={'method':'gzip','mtime':0} if path.suffix=='.gz' else None)

def js(path,x):
    Path(path).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else str(v))+'\n',encoding='utf-8')

def valid_purpose(d):
    return d.room_type_status.eq('recorded_purpose')

def load(inp):
    a=pd.read_csv(inp/'annotations.csv.gz',low_memory=False)
    d=pd.read_csv(inp/'images.csv',low_memory=False)
    a=a[a.formal_quality & a.Q.notna() & a.D10.notna()].copy()
    assert not a.duplicated(['image_key','worker_id']).any()
    return a,d

def describe(a,d,out):
    rows=[]
    for (condition,layer,purpose),g in d[d.n_formal>0].groupby(['condition','layer','room_type_model'],dropna=False):
        z=a[a.image_key.isin(g.image_key)]
        base=dict(condition=condition,layer=layer,purpose=purpose,n_images=len(g),n_buildings=g.building.nunique(),n_workers=z.worker_id.nunique(),n_records=len(z))
        for metric in IMAGE_OUTCOMES+GEO:
            if metric not in g:continue
            x=g[['building',metric]].dropna()
            if x.empty:continue
            rows.append(dict(**base,metric=metric,metric_images=len(x),image_equal=x[metric].mean(),building_equal=x.groupby('building')[metric].mean().mean(),image_median=x[metric].median(),image_p10=x[metric].quantile(.1),image_p90=x[metric].quantile(.9)))
    save(pd.DataFrame(rows),out/'PURPOSE_DESCRIPTION_ALL_LAYERS.csv')
    ordinary=d[(d.condition=='manual')&(d.layer=='ordinary')&(d.n_formal>0)].copy()
    rows=[]
    for (purpose,diff),g in ordinary.groupby(['room_type_model','difficulty'],dropna=False):
        for metric in IMAGE_OUTCOMES+GEO:
            if metric in g:
                x=g[metric].dropna()
                rows.append(dict(purpose=purpose,difficulty=diff,metric=metric,n_images=len(x),n_buildings=g.loc[x.index,'building'].nunique(),image_equal=x.mean(),image_sd=x.std(ddof=1)))
    save(pd.DataFrame(rows),out/'PURPOSE_DIFFICULTY_DESCRIPTION.csv')
    major=ordinary[ordinary.room_type_model.isin(MAJOR)]
    weights=major.difficulty.value_counts(normalize=True).to_dict()
    standard=[]
    for p in MAJOR:
        g=major[major.room_type_model==p]
        for metric in IMAGE_OUTCOMES:
            v=g.groupby('difficulty')[metric].mean()
            supported=all(k in v.index and pd.notna(v[k]) for k in weights)
            standard.append(dict(purpose=p,metric=metric,n_images=len(g),n_buildings=g.building.nunique(),raw_mean=g[metric].mean(),standardized_mean=sum(weights[k]*v[k] for k in weights) if supported else np.nan,supported=supported,standard_difficulty_weights=json.dumps(weights,ensure_ascii=False),estimand='six-major-purpose pooled image difficulty proportions; within-purpose strata means; descriptive'))
    save(pd.DataFrame(standard),out/'DIFFICULTY_STANDARDIZED_PURPOSE.csv')
    # Building-preserving sensitivity for the primary bedroom/bathroom contrast.
    rng=np.random.default_rng(SEED);buildings=sorted(major.building.unique());idx={b:i for i,b in enumerate(buildings)}
    boot=[]
    for rep in range(2000):
        w=np.bincount(rng.integers(0,len(buildings),len(buildings)),minlength=len(buildings))
        estimates={}
        for p in ['卧室','卫浴']:
            g=major[major.room_type_model==p];ww=g.building.map(lambda b:w[idx[b]]).to_numpy()
            if ww.sum()==0:continue
            estimates[p+'_raw']=np.average(g.mean_Q,weights=ww)
            vals=[]
            for dif,f in weights.items():
                mask=(g.difficulty==dif).to_numpy();dw=ww[mask]
                if not dw.sum():break
                vals.append(f*np.average(g.loc[mask,'mean_Q'],weights=dw))
            if len(vals)==len(weights):estimates[p+'_adjusted']=sum(vals)
        for mode in ['raw','adjusted']:
            x,y=estimates.get('卧室_'+mode),estimates.get('卫浴_'+mode)
            if x is not None and y is not None:boot.append(dict(replicate=rep,mode=mode,bedroom_minus_bathroom=x-y))
    bb=pd.DataFrame(boot);save(bb,out/'BEDROOM_BATHROOM_BUILDING_BOOTSTRAP.csv.gz')
    save(bb.groupby('mode').bedroom_minus_bathroom.agg(valid_replicates='size',mean='mean',p025=lambda x:x.quantile(.025),p975=lambda x:x.quantile(.975)).reset_index(),out/'BEDROOM_BATHROOM_BOOTSTRAP_INTERVALS.csv')

def pair_statistics(ga,gb,metrics,workers=None):
    ids=sorted(set(ga.index)&set(gb.index)) if workers is None else workers
    ans={'n_common':len(ids),'common_workers':'|'.join(ids)}
    if len(ids)<3:return ans
    matrix_a=ga.loc[ids,metrics].to_numpy(float);matrix_b=gb.loc[ids,metrics].to_numpy(float)
    for col,metric in enumerate(metrics):
        va=matrix_a[:,col];vb=matrix_b[:,col]
        ok=np.isfinite(va)&np.isfinite(vb);va=va[ok];vb=vb[ok]
        ans[metric+'_n']=len(va)
        if len(va)<3:continue
        ans[metric+'_common_mean_absdiff']=abs(va.mean()-vb.mean())
        ans[metric+'_common_individual_absdiff']=np.mean(abs(va-vb))
        # Relative-to-other-common-people residual, not score of the target worker in their own peer mean.
        aa=(va-va.mean())*len(va)/(len(va)-1);ab=(vb-vb.mean())*len(vb)/(len(vb)-1)
        ans[metric+'_common_relative_absdiff']=np.mean(abs(aa-ab))
        ans[metric+'_common_sd_absdiff']=abs(va.std(ddof=1)-vb.std(ddof=1))
        if va.std()>1e-12 and vb.std()>1e-12:
            ans[metric+'_common_pearson']=np.corrcoef(va,vb)[0,1]
            if metric in ['Q','D10','annotation_turn5','turn_delta']:
                ans[metric+'_common_spearman']=np.corrcoef(rankdata(va),rankdata(vb))[0,1]
    return ans

def summarize_pair_contrasts(pairs,images,out):
    # Expand physical unordered pairs to two targets, never count them as independent images.
    rows=[]
    for reverse in [False,True]:
        x=pairs.copy()
        if reverse:
            for stem in ['image_key','image','building','purpose','difficulty','ref_turn5']:
                x[[stem+'_a',stem+'_b']]=x[[stem+'_b',stem+'_a']].to_numpy()
        x=x.rename(columns={'image_key_a':'target_key','image_a':'target_image','building_a':'target_building','purpose_a':'target_purpose','image_key_b':'source_key','image_b':'source_image','building_b':'source_building','purpose_b':'source_purpose'})
        rows.append(x)
    directed=pd.concat(rows,ignore_index=True)
    distance_metrics=[c for c in pairs if c.endswith('_absdiff') or c.endswith('_pearson') or c.endswith('_spearman')]
    target=[]
    for regime,mask in [('all_cross_building',np.ones(len(directed),bool)),('same_difficulty',directed.same_difficulty),('same_difficulty_and_turns',directed.same_difficulty & directed.same_ref_turn5)]:
        x=directed.loc[mask]
        for (key,purpose,building),g in x.groupby(['target_key','target_purpose','target_building']):
            for metric in distance_metrics:
                # Source building equal within target gives large buildings less chance to dominate.
                by=g.groupby(['same_purpose','source_building'])[metric].mean().reset_index()
                vals=by.groupby('same_purpose')[metric].mean()
                if False not in vals or True not in vals or not np.isfinite(vals[False]) or not np.isfinite(vals[True]):continue
                target.append(dict(regime=regime,target_key=key,purpose=purpose,building=building,metric=metric,same=vals[True],different=vals[False],same_minus_different=vals[True]-vals[False],same_pairs=int((g.same_purpose & g[metric].notna()).sum()),different_pairs=int((~g.same_purpose & g[metric].notna()).sum()),same_source_buildings=by.loc[by.same_purpose & by[metric].notna(),'source_building'].nunique(),different_source_buildings=by.loc[~by.same_purpose & by[metric].notna(),'source_building'].nunique()))
    t=pd.DataFrame(target);save(t,out/'PAIR_CONTRAST_PER_TARGET.csv.gz')
    summaries=[]
    for (regime,metric),g in t.groupby(['regime','metric']):
        for purpose,sub in [('ALL',g)]+list(g.groupby('purpose')):
            v=sub.same_minus_different
            summaries.append(dict(regime=regime,metric=metric,purpose=purpose,n_images=len(sub),n_buildings=sub.building.nunique(),same_mean=sub.same.mean(),different_mean=sub.different.mean(),difference_image_equal=v.mean(),difference_building_equal=sub.groupby('building').same_minus_different.mean().mean(),negative_images=int((v<-1e-10).sum()),positive_images=int((v>1e-10).sum()),near_zero_images=int((v.abs()<=1e-10).sum()),difference_p10=v.quantile(.1),difference_p90=v.quantile(.9),note='distance: negative=closer within-purpose; correlation: positive=more repeatable'))
    save(pd.DataFrame(summaries),out/'PAIR_CONTRAST_SUMMARY.csv')
    return directed

def pairs_and_triplets(a,d,out):
    d=d[(d.condition=='manual')&(d.layer=='ordinary')&(d.n_formal>0)&valid_purpose(d)].copy().sort_values('image_key').reset_index(drop=True)
    aa=a[a.image_key.isin(d.image_key)].copy()
    metrics=[x for x in ANN_METRICS if x in aa]
    cells={k:g.set_index('worker_id') for k,g in aa.groupby('image_key')}
    rows=[]
    for x,y in itertools.combinations(d.itertuples(index=False),2):
        if x.building==y.building:continue
        rec={'pair_key':x.image_key+'|||'+y.image_key,'image_key_a':x.image_key,'image_key_b':y.image_key,'image_a':x.image,'image_b':y.image,'building_a':x.building,'building_b':y.building,'purpose_a':x.room_type_model,'purpose_b':y.room_type_model,'difficulty_a':x.difficulty,'difficulty_b':y.difficulty,'ref_turn5_a':x.ref_turn5,'ref_turn5_b':y.ref_turn5,'same_purpose':x.room_type_model==y.room_type_model,'same_difficulty':x.difficulty==y.difficulty,'same_ref_turn5':x.ref_turn5==y.ref_turn5,'n_formal_a':x.n_formal,'n_formal_b':y.n_formal}
        for metric in IMAGE_OUTCOMES:
            va=getattr(x,metric);vb=getattr(y,metric)
            rec['actual_pool_'+metric+'_absdiff']=abs(va-vb) if np.isfinite(va) and np.isfinite(vb) else np.nan
        rec.update(pair_statistics(cells[x.image_key],cells[y.image_key],metrics))
        rows.append(rec)
    p=pd.DataFrame(rows);save(p,out/'CROSS_BUILDING_IMAGE_PAIRS.csv.gz')
    summarize_pair_contrasts(p,d,out)
    # Matching uses only accepted purpose, source building, coarse difficulty and reference geometry.
    z=d[GEO].to_numpy(float).copy();z[:,1:3]=np.log1p(z[:,1:3]);z[:,3:5]=np.log(np.maximum(z[:,3:5],1e-5))
    sd=np.nanstd(z,axis=0);sd[sd<1e-12]=1;z=(z-np.nanmean(z,axis=0))/sd
    meta=d.set_index('image_key');index={k:i for i,k in enumerate(d.image_key)}
    triples=[]
    for t in d.itertuples(index=False):
        same=d[(d.building!=t.building)&(d.room_type_model==t.room_type_model)]
        for s in same.itertuples(index=False):
            base=d[(d.building==s.building)&(d.room_type_model!=t.room_type_model)]
            for regime in ['source_building','source_building_difficulty','source_building_difficulty_geometry']:
                cands=base if regime=='source_building' else base[base.difficulty==s.difficulty]
                if cands.empty:continue
                choices=[]
                for c in cands.itertuples(index=False):
                    common=sorted(set(cells[t.image_key].index)&set(cells[s.image_key].index)&set(cells[c.image_key].index))
                    if len(common)<3:continue
                    dist=float(np.linalg.norm(z[index[s.image_key]]-z[index[c.image_key]]))
                    choices.append((dist,c.image_key,c,common))
                if not choices:continue
                # For the two broader regimes use all eligible controls; their means are later within-anchor averaged.
                n_legal=len(choices)
                if regime.endswith('_geometry'):choices=[min(choices,key=lambda v:(v[0],v[1]))]
                for dist,ck,c,common in choices:
                    row=dict(regime=regime,target_key=t.image_key,target_image=t.image,target_building=t.building,purpose=t.room_type_model,source_same_key=s.image_key,source_same_image=s.image,source_building=s.building,source_different_key=c.image_key,source_different_image=c.image,source_different_purpose=c.room_type_model,target_difficulty=t.difficulty,source_same_difficulty=s.difficulty,source_different_difficulty=c.difficulty,source_same_ref_turn5=s.ref_turn5,source_different_ref_turn5=c.ref_turn5,geometry_distance=dist,n_candidate_images=len(cands),n_legal_candidate_images=n_legal,n_common=len(common),common_workers='|'.join(common))
                    sm=pair_statistics(cells[t.image_key],cells[s.image_key],metrics,common);df=pair_statistics(cells[t.image_key],cells[c.image_key],metrics,common)
                    for key in sm:
                        if key.endswith('_absdiff') or key.endswith('_pearson') or key.endswith('_spearman'):
                            if key in df:
                                row[key+'_same']=sm[key];row[key+'_different']=df[key];row[key+'_contrast']=sm[key]-df[key]
                    triples.append(row)
    tr=pd.DataFrame(triples);save(tr,out/'MATCHED_THREE_IMAGE_EVENTS.csv.gz')
    mets=[c[:-9] for c in tr if c.endswith('_contrast')]
    target=[]
    for regime,g in tr.groupby('regime'):
        for metric in mets:
            cols=[metric+x for x in ['_same','_different','_contrast']]
            # First controls for each same-purpose anchor, then same-purpose anchors in each source building.
            anchor=g.groupby(['target_key','target_building','purpose','source_building','source_same_key'])[cols].mean().reset_index()
            sb=anchor.groupby(['target_key','target_building','purpose','source_building'])[cols].mean().reset_index()
            for (tk,tb,purpose),sub in sb.groupby(['target_key','target_building','purpose']):
                vals=sub[cols].mean()
                if not np.isfinite(vals.iloc[2]):continue
                target.append(dict(regime=regime,metric=metric,target_key=tk,building=tb,purpose=purpose,same=vals.iloc[0],different=vals.iloc[1],same_minus_different=vals.iloc[2],source_buildings=int(sub[cols[2]].notna().sum())))
    tg=pd.DataFrame(target);save(tg,out/'MATCHED_CONTRAST_PER_TARGET.csv.gz')
    sums=[]
    for (regime,metric),g in tg.groupby(['regime','metric']):
        for purpose,sub in [('ALL',g)]+list(g.groupby('purpose')):
            v=sub.same_minus_different;b=sub.groupby('building').same_minus_different.mean()
            sums.append(dict(regime=regime,metric=metric,purpose=purpose,n_images=len(sub),n_buildings=len(b),same=sub.same.mean(),different=sub.different.mean(),difference_image_equal=v.mean(),difference_building_equal=b.mean(),negative_images=int((v<-1e-10).sum()),positive_images=int((v>1e-10).sum()),near_zero_images=int((v.abs()<=1e-10).sum()),negative_buildings=int((b<-1e-10).sum()),positive_buildings=int((b>1e-10).sum()),difference_p10=v.quantile(.1),difference_p90=v.quantile(.9)))
    save(pd.DataFrame(sums),out/'MATCHED_CONTRAST_SUMMARY.csv')
    # Whole-building sensitivity for matched contrasts; target and source incidence both reweighted.
    rr=tr[tr.regime=='source_building_difficulty_geometry']
    selected=['Q_common_mean_absdiff','D10_common_mean_absdiff','Q_common_individual_absdiff','Q_common_relative_absdiff','Q_common_spearman','annotation_turn5_common_mean_absdiff','turn_delta_common_mean_absdiff','actual_simplification_common_mean_absdiff']
    rng=np.random.default_rng(SEED+1);bs=sorted(d.building.unique());bidx={b:i for i,b in enumerate(bs)}
    bres=[]
    for metric in selected:
        col=metric+'_contrast'
        sb=rr.groupby(['target_key','target_building','source_building'])[col].mean().dropna().reset_index()
        tkeys=sorted(sb.target_key.unique());tidx={k:i for i,k in enumerate(tkeys)}
        ti=sb.target_key.map(tidx).to_numpy();si=sb.source_building.map(bidx).to_numpy();tb=sb.drop_duplicates('target_key').set_index('target_key').loc[tkeys,'target_building'].map(bidx).to_numpy();v=sb[col].to_numpy()
        for rep in range(2000):
            w=np.bincount(rng.integers(0,len(bs),len(bs)),minlength=len(bs));sw=w[si]
            sums=np.bincount(ti,weights=sw*v,minlength=len(tkeys));den=np.bincount(ti,weights=sw,minlength=len(tkeys));valid=(den>0)&(w[tb]>0)
            if valid.any():bres.append(dict(metric=metric,replicate=rep,effect=np.average(sums[valid]/den[valid],weights=w[tb[valid]]),target_images_present=int(valid.sum())))
    bt=pd.DataFrame(bres);save(bt,out/'MATCHED_BUILDING_RESAMPLES.csv.gz')
    save(bt.groupby('metric').effect.agg(valid_replicates='size',p025=lambda x:x.quantile(.025),p975=lambda x:x.quantile(.975)).reset_index(),out/'MATCHED_BUILDING_INTERVALS.csv')
    coverage=[]
    for regime,g in tr.groupby('regime'):
        coverage.append(dict(regime=regime,event_rows=len(g),target_images=g.target_key.nunique(),target_buildings=g.target_building.nunique(),source_images=len(set(g.source_same_key)|set(g.source_different_key)),source_buildings=g.source_building.nunique(),people=len(set('|'.join(g.common_workers).split('|'))),common_people_median=g.n_common.median(),common_people_min=g.n_common.min(),source_same_anchor_pairs=g[['target_key','source_same_key']].drop_duplicates().shape[0]))
    save(pd.DataFrame(coverage),out/'MATCHING_COVERAGE.csv')
    return p,tr

def make_pipeline(cat,num,family,alpha=10):
    prep=[]
    if cat:prep.append(('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cat))
    if num:
        transforms=[('impute',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler())]
        if family=='ridge_quadratic':transforms.append(('poly',PolynomialFeatures(2,include_bias=False)))
        prep.append(('num',Pipeline(transforms),num))
    transformer=ColumnTransformer(prep,remainder='drop')
    if family.startswith('ridge'):est=Ridge(alpha=alpha)
    else:est=HistGradientBoostingRegressor(max_iter=120,max_leaf_nodes=7,min_samples_leaf=15,learning_rate=.05,l2_regularization=10.,random_state=SEED)
    return Pipeline([('prepare',transformer),('model',est)])

def historical_pool_features(train_annotations,target_images,metric):
    # Every observed historical task uses an other-person peer benchmark.
    a=train_annotations[['image_key','building','worker_id',metric]].dropna().copy()
    g=a.groupby('image_key')[metric]
    n=g.transform('size');a['rel']=(a[metric]-g.transform('mean'))*n/(n-1)
    per=a.groupby('worker_id').agg(mean=('rel','mean'),count=('rel','size'),absolute=(metric,'mean'))
    # Fixed modest shrinkage is an input feature, not a fitted purpose/person classifier.
    per['skill']=per['mean']*per['count']/(per['count']+10.)
    global_absolute=a[metric].mean()
    rows=[]
    for row in target_images.itertuples():
        members=json.loads(row.workers_json);v=per.reindex(members)
        rows.append(dict(image_key=row.image_key,pool_history_relative=v.skill.fillna(0).mean(),pool_history_absolute=v.absolute.fillna(global_absolute).mean(),pool_history_known_fraction=v['count'].notna().mean()))
    return pd.DataFrame(rows).set_index('image_key')

def outer_history_features(a,d,held,metric):
    outer_train=a[a.building!=held];hist=[]
    for b,g in d.groupby('building'):
        train=outer_train[outer_train.building!=b]
        hist.append(historical_pool_features(train,g,metric))
    return pd.concat(hist).reindex(d.image_key)

def run_predictions(a,d,out):
    d=d[(d.condition=='manual')&(d.layer=='ordinary')&(d.n_formal>0)].copy().sort_values('image_key').reset_index(drop=True)
    a=a[a.image_key.isin(d.image_key)].copy()
    d['purpose']=d.room_type_model.fillna('__MISSING__');d['difficulty']=d.difficulty.fillna('__UNKNOWN__')
    # Stable transforms have known geometric meanings and are outcome-independent.
    d['log_H']=np.log1p(d.ref_H);d['short_fraction']=d.ref_short_edges/d.ref_turn5
    d['log_min_angle']=np.log(np.maximum(d.ref_min_horizontal_deg,1e-5));d['log_radius']=np.log(np.maximum(d.ref_radius_p90_h,1e-5))
    gnum=['ref_turn5','log_H','short_fraction','log_min_angle','log_radius']
    hnum=['pool_history_relative','pool_history_absolute','pool_history_known_fraction']
    specs={
      'training_mean':([],[],'none'),
      'purpose_only':(['purpose'],[],'ridge'),
      'difficulty':(['difficulty'],[],'ridge'),
      'difficulty_purpose':(['difficulty','purpose'],[],'ridge'),
      'geometry':(['difficulty'],gnum,'ridge'),
      'geometry_purpose':(['difficulty','purpose'],gnum,'ridge'),
      'geometry_history':(['difficulty'],gnum+hnum,'rich'),
      'geometry_history_purpose':(['difficulty','purpose'],gnum+hnum,'rich'),
      'geometry_history_ridge10':(['difficulty'],gnum+hnum,'fixed'),
      'geometry_history_purpose_ridge10':(['difficulty','purpose'],gnum+hnum,'fixed'),
    }
    preds=[];folds=[];tuning=[];feature_rows=[]
    for metric,response in [('Q','mean_Q'),('D10','mean_D10')]:
        for held in sorted(d.building.unique()):
            work=d.copy();hist=outer_history_features(a,d,held,metric)
            for col in hnum:work[col]=work.image_key.map(hist[col])
            istrain=work.building!=held;train=work[istrain];test=work[~istrain]
            for r in work[['image_key','building']+hnum].to_dict('records'):feature_rows.append(dict(metric=metric,held_out_building=held,role='test' if r['building']==held else 'train_crossfitted',**r))
            y=train[response].to_numpy();yt=test[response].to_numpy();groups=train.building.to_numpy()
            cv=list(GroupKFold(n_splits=min(5,len(set(groups)))).split(train,y,groups))
            inner_work=[]
            for ix,jx in cv:
                itrain=train.iloc[ix].copy();ival=train.iloc[jx].copy()
                valid_b=set(ival.building);allowed=a[~a.building.isin(valid_b|{held})]
                hf=[]
                for b,bg in pd.concat([itrain,ival]).groupby('building'):
                    hf.append(historical_pool_features(allowed[allowed.building!=b],bg,metric))
                hh=pd.concat(hf)
                for col in hnum:
                    itrain[col]=itrain.image_key.map(hh[col]);ival[col]=ival.image_key.map(hh[col])
                inner_work.append((itrain,ival,y[ix],y[jx]))
            for name,(cat,num,kind) in specs.items():
                if kind=='none':
                    fitted=None;selected=('mean',None);pr=np.full(len(test),np.mean(y));cvscore=np.nan
                else:
                    candidates=[('ridge',v) for v in [0.1,1.,10.,100.]]
                    if kind=='rich':candidates += [('ridge_quadratic',v) for v in [10.,100.]]+[('hgb',0.)]
                    if kind=='fixed':candidates=[('ridge',10.)]
                    cv_scores=[]
                    for family,alpha in candidates:
                        scores=[]
                        for ci,(itrain,ival,iy,ivy) in enumerate(inner_work):
                            # Cached, crossfitted inner histories exclude outer and inner validation buildings.
                            model=make_pipeline(cat,num,family,alpha)
                            model.fit(itrain,iy);ip=np.clip(model.predict(ival),0,100)
                            scores.append(np.mean(abs(ip-ivy)))
                        score=float(np.mean(scores));cv_scores.append(score)
                        tuning.append(dict(metric=metric,held_out_building=held,method=name,family=family,alpha=alpha,inner_mae=score,inner_folds=len(cv)))
                    best=int(np.argmin(cv_scores));selected=candidates[best];cvscore=cv_scores[best]
                    fitted=make_pipeline(cat,num,*selected);fitted.fit(train,y);pr=np.clip(fitted.predict(test),0,100)
                folds.append(dict(metric=metric,method=name,held_out_building=held,n_train_images=len(train),n_train_buildings=train.building.nunique(),n_test_images=len(test),family=selected[0],alpha=selected[1],inner_mae=cvscore,numeric_features='|'.join(num),categorical_features='|'.join(cat),train_buildings='|'.join(sorted(train.building.unique()))))
                for row,pred,truth in zip(test.itertuples(),pr,yt):
                    preds.append(dict(metric=metric,method=name,image_key=row.image_key,image=row.image,building=held,purpose=row.purpose,difficulty=row.difficulty,n_formal=row.n_formal,actual=truth,predicted=pred,error=pred-truth,absolute_error=abs(pred-truth),squared_error=(pred-truth)**2))
            print('prediction',metric,held,flush=True)
    p=pd.DataFrame(preds);save(p,out/'LOBO_IMAGE_PREDICTIONS.csv.gz');save(pd.DataFrame(folds),out/'LOBO_MODELS.csv');save(pd.DataFrame(tuning),out/'LOBO_INNER_TUNING.csv.gz');save(pd.DataFrame(feature_rows),out/'LOBO_HISTORY_FEATURES.csv.gz')
    aggregate_predictions(p,d,a,out)

def aggregate_predictions(p,d,a,out):
    support=[]
    for row in d.itertuples():
        hist=d[(d.building!=row.building)&(d.room_type_model==row.room_type_model)]
        support.append(dict(image_key=row.image_key,image=row.image,building=row.building,purpose=row.room_type_model,room_type_status=row.room_type_status,n_same_purpose_history_images=len(hist),n_same_purpose_history_buildings=hist.building.nunique(),recorded_purpose=row.room_type_status=='recorded_purpose',repeated_recorded_purpose=row.room_type_status=='recorded_purpose' and len(hist)>0))
    sp=pd.DataFrame(support);save(sp,out/'LOBO_TARGET_PURPOSE_SUPPORT.csv')
    repeated=set(sp.loc[sp.repeated_recorded_purpose,'image_key'])
    summaries=[]
    for (metric,method),g in p.groupby(['metric','method']):
        for subset,sub in [('ALL',g),('RECORDED_PURPOSE',g[~g.purpose.isin(['__MISSING__','无法判断','开放复合空间'])]),('REPEATED_RECORDED_PURPOSE',g[g.image_key.isin(repeated)])]+[(q,s) for q,s in g.groupby('purpose')]:
            summaries.append(dict(metric=metric,method=method,subset=subset,images=len(sub),buildings=sub.building.nunique(),mae=sub.absolute_error.mean(),rmse=np.sqrt(sub.squared_error.mean()),bias=sub.error.mean(),building_equal_mae=sub.groupby('building').absolute_error.mean().mean()))
    save(pd.DataFrame(summaries),out/'LOBO_PREDICTION_SUMMARY.csv')
    by=p.groupby(['metric','method','building']).agg(images=('image_key','size'),mae=('absolute_error','mean'),mse=('squared_error','mean')).reset_index();save(by,out/'LOBO_BY_BUILDING.csv')
    contrasts=[('purpose_only','training_mean'),('difficulty','training_mean'),('difficulty_purpose','difficulty'),('geometry','difficulty'),('geometry_purpose','geometry'),('geometry_history_purpose','geometry_history'),('geometry_history_purpose_ridge10','geometry_history_ridge10')]
    if 'geometry_rich' in set(p.method):contrasts += [('geometry_purpose_rich','geometry_rich'),('geometry_history','geometry_rich')]
    gains=[]
    for metric,g in p.groupby('metric'):
        wide=g.assign(method='model_'+g.method).pivot(index=['image_key','image','building','purpose','difficulty'],columns='method',values='absolute_error').reset_index()
        for m,b in contrasts:
            tmp=wide[['image_key','image','building','purpose','difficulty']].copy();tmp['metric']=metric;tmp['method']=m;tmp['baseline']=b;tmp['gain_mae']=wide['model_'+b]-wide['model_'+m];gains.append(tmp)
    gg=pd.concat(gains,ignore_index=True);save(gg,out/'LOBO_INCREMENT_PER_IMAGE.csv')
    rng=np.random.default_rng(SEED+2);inc=[];brep=[]
    for (metric,m,b),g in gg.groupby(['metric','method','baseline']):
        for subset,sub in [('ALL',g),('RECORDED_PURPOSE',g[~g.purpose.isin(['__MISSING__','无法判断','开放复合空间'])]),('REPEATED_RECORDED_PURPOSE',g[g.image_key.isin(repeated)])]+list(g.groupby('purpose')):
            bg=sub.groupby('building').gain_mae.agg(['mean','sum','count']);arr=bg.to_numpy();draws=[]
            for k in range(2000):
                ids=rng.integers(0,len(arr),len(arr));draws.append(arr[ids,1].sum()/arr[ids,2].sum())
            value=sub.gain_mae
            inc.append(dict(metric=metric,method=m,baseline=b,subset=subset,images=len(sub),buildings=len(bg),gain_image_equal=value.mean(),gain_building_equal=bg['mean'].mean(),improved_images=int((value>1e-10).sum()),worsened_images=int((value<-1e-10).sum()),near_zero_images=int((value.abs()<=1e-10).sum()),improved_buildings=int((bg['mean']>1e-10).sum()),worsened_buildings=int((bg['mean']<-1e-10).sum()),building_boot_p025=np.quantile(draws,.025),building_boot_p975=np.quantile(draws,.975)))
    save(pd.DataFrame(inc),out/'LOBO_INCREMENT_SUMMARY.csv')
    checks={'images':len(d),'buildings':d.building.nunique(),'workers':a.worker_id.nunique(),'records':len(a),'methods':sorted(p.method.unique()),'all_models_same_targets':bool(p.groupby(['metric','method']).size().nunique()==1),'Q_D10_support_equal':True,'outer_held_building_never_trains':True,'inner_history_recomputed_excluding_inner_validation_buildings':True,'no_target_annotation_features_in_predictors':True,'geometry_information':'Frozen reference-derived geometry; audited-geometry application/oracle covariate analysis, not no-reference RGB predictor','history_shrinkage_n':10,'main_loss':'image equal absolute error; whole-building group inner 5-fold; 2000 whole-building sensitivity resamples','source_commit':COMMIT,'new_fusion':0}
    js(out/'PREDICTION_CHECKS.json',checks)

def run_geometry_portfolio(a,d,out):
    """Same richer candidate family with/without purpose, without personnel history.

    Added to disentangle richer curve fitting from historical-pool information.
    No new features, class fitting or outcome-based subgroup selection.
    """
    d=d[(d.condition=='manual')&(d.layer=='ordinary')&(d.n_formal>0)].copy().sort_values('image_key').reset_index(drop=True)
    a=a[a.image_key.isin(d.image_key)].copy()
    d['purpose']=d.room_type_model.fillna('__MISSING__');d['difficulty']=d.difficulty.fillna('__UNKNOWN__')
    d['log_H']=np.log1p(d.ref_H);d['short_fraction']=d.ref_short_edges/d.ref_turn5
    d['log_min_angle']=np.log(np.maximum(d.ref_min_horizontal_deg,1e-5));d['log_radius']=np.log(np.maximum(d.ref_radius_p90_h,1e-5))
    gnum=['ref_turn5','log_H','short_fraction','log_min_angle','log_radius']
    preds=[];folds=[];tuning=[]
    specs={'geometry_rich':['difficulty'],'geometry_purpose_rich':['difficulty','purpose']}
    for metric,response in [('Q','mean_Q'),('D10','mean_D10')]:
        for held in sorted(d.building.unique()):
            train=d[d.building!=held];test=d[d.building==held];y=train[response].to_numpy();yt=test[response].to_numpy();groups=train.building.to_numpy()
            cv=list(GroupKFold(n_splits=min(5,len(set(groups)))).split(train,y,groups))
            for name,cat in specs.items():
                candidates=[('ridge',v) for v in [0.1,1.,10.,100.]]+[('ridge_quadratic',v) for v in [10.,100.]]+[('hgb',0.)]
                cv_scores=[]
                for family,alpha in candidates:
                    scores=[]
                    for ix,jx in cv:
                        model=make_pipeline(cat,gnum,family,alpha);model.fit(train.iloc[ix],y[ix]);ip=np.clip(model.predict(train.iloc[jx]),0,100);scores.append(np.mean(abs(ip-y[jx])))
                    score=float(np.mean(scores));cv_scores.append(score);tuning.append(dict(metric=metric,held_out_building=held,method=name,family=family,alpha=alpha,inner_mae=score,inner_folds=len(cv)))
                best=int(np.argmin(cv_scores));selected=candidates[best];model=make_pipeline(cat,gnum,*selected);model.fit(train,y);pr=np.clip(model.predict(test),0,100)
                folds.append(dict(metric=metric,method=name,held_out_building=held,n_train_images=len(train),n_train_buildings=train.building.nunique(),n_test_images=len(test),family=selected[0],alpha=selected[1],inner_mae=cv_scores[best],numeric_features='|'.join(gnum),categorical_features='|'.join(cat),train_buildings='|'.join(sorted(train.building.unique()))))
                for row,pred,truth in zip(test.itertuples(),pr,yt):preds.append(dict(metric=metric,method=name,image_key=row.image_key,image=row.image,building=held,purpose=row.purpose,difficulty=row.difficulty,n_formal=row.n_formal,actual=truth,predicted=pred,error=pred-truth,absolute_error=abs(pred-truth),squared_error=(pred-truth)**2))
            print('matched model portfolio',metric,held,flush=True)
    extra=pd.DataFrame(preds);save(extra,out/'ADDITIONAL_GEOMETRY_PORTFOLIO_PREDICTIONS.csv.gz')
    for fname,frame in [('LOBO_IMAGE_PREDICTIONS.csv.gz',extra),('LOBO_MODELS.csv',pd.DataFrame(folds)),('LOBO_INNER_TUNING.csv.gz',pd.DataFrame(tuning))]:
        base=pd.read_csv(out/fname);base=base[~base.method.isin(specs)];save(pd.concat([base,frame],ignore_index=True),out/fname)
    aggregate_predictions(pd.read_csv(out/'LOBO_IMAGE_PREDICTIONS.csv.gz'),d,a,out)
    js(out/'ADDITIONAL_GEOMETRY_PORTFOLIO_RECEIPT.json',{'reason':'Keep the geometry-only and geometry-plus-person-history comparison in the same fixed inner model candidate family; isolate feature information from functional-form flexibility.','methods':list(specs),'new_fusion':0,'source_commit':COMMIT})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--part',choices=['descriptive','prediction','aggregate_prediction','geometry_portfolio','all'],default='all');args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    a,d=load(args.inputs)
    if args.part in ['descriptive','all']:describe(a,d,args.out);pairs_and_triplets(a,d,args.out)
    if args.part in ['prediction','all']:run_predictions(a,d,args.out);run_geometry_portfolio(a,d,args.out)
    if args.part=='geometry_portfolio':run_geometry_portfolio(a,d,args.out)
    if args.part=='aggregate_prediction':
        p=pd.read_csv(args.out/'LOBO_IMAGE_PREDICTIONS.csv.gz');keys=set(p.image_key)
        aggregate_predictions(p,d[d.image_key.isin(keys)],a[a.image_key.isin(keys)],args.out)
    js(args.out/('COMPLETE_'+args.part+'.json'),{'part':args.part,'source_commit':COMMIT,'seed':SEED,'inputs':{x:hashlib.sha256((args.inputs/x).read_bytes()).hexdigest() for x in ['annotations.csv.gz','images.csv']},'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'new_fusion':0})

if __name__=='__main__':main()
