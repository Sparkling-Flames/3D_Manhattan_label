#!/usr/bin/env python3
"""Portable independent v2 Q/T/difficulty study from frozen audited evidence.

No raw exports, coordinates, reference selection or eligibility are changed.
Task effects are eliminated algebraically before fitting worker effects.  The
three-difficulty penalty shrinks a person's differences, not the task intercepts.
"""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse, collections, gzip, hashlib, json, math, time
from pathlib import Path
import numpy as np
import pandas as pd

DIFFS=('easy','medium','hard')
METRICS=('B8L2','D10')
SEED=20261019

def js(path,obj):
    def clean(x):
        if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)): return [clean(v) for v in x]
        if isinstance(x,(np.integer,)):return int(x)
        if isinstance(x,(np.bool_,)):return bool(x)
        if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
        return x
    Path(path).write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def loadgz(path):
    with gzip.open(path,'rt',encoding='utf8') as f:return json.load(f)
def cnt(d):return dict(n=len(d),workers=d.worker_id.nunique(),images=d.image_id.nunique(),buildings=d.building_id.nunique())
def key(d,cols):return d[list(cols)].fillna('').apply(lambda r:json.dumps(r.tolist(),ensure_ascii=False,separators=(',',':')),axis=1)
def support(d):return d.task.nunique()>=6 and d.building_id.nunique()>=3

def load_inputs(repo,out):
    ep=repo/'research/statistics/v2_evidence_audit_20261019/records.json.gz'
    tp=repo/'research/statistics/v2_integrated_analysis_20261019/tables.json.gz'
    ap=repo/'research/workers/pro_personnel_v2_20261019/analysis_context.json.gz'
    evidence=loadgz(ep)['records'];tables=loadgz(tp)['tables'];ctx=loadgz(ap)
    scalar=['object_id','worker_id','image_id','image_code','building_id','room_id','condition','origin','current_class','quality_usable','quality_use','pool_analysis_eligible','independent_vote_eligible','B8L2','D10','source_active_time_seconds','target_matched_time_seconds','reference_id','reference_version','point_count','declared_pair_count','is_doorway','is_oos','cleaning_disposition','calculation_class','IoU3D100','binding_status','ring_confirmed']
    rows=[]
    for e in evidence:
        r={k:e.get(k) for k in scalar}
        r['ordinary_difficulty_eligible']=e['binding_evidence'].get('ordinary_difficulty_eligible',False)
        r['difficulty_reference_match']=e['binding_evidence'].get('chosen_target_is_current',False)
        r['time_source_kind']=e['time_evidence'].get('source_kind')
        r['quality_exclusion_reasons']=json.dumps(e['quality_exclusion_reasons'],ensure_ascii=False)
        m=e['measurements'].get('same_reference_measurements') or {}
        for c in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','height_mean_ratio']:
            r[c]=m.get(c)
        dr=e['image_evidence'].get('difficulty_record') or {}
        r['reference_pair_count']=dr.get('N_floor')
        r['reference_hidden_count']=dr.get('H')
        r['difficulty_review_method']=dr.get('review_method')
        r['difficulty_classification_basis']=dr.get('classification_basis')
        rows.append(r)
    d=pd.DataFrame(rows);d['difficulty']=d.current_class.map({'简单':'easy','中等':'medium','困难':'hard'}).fillna('special_or_unknown')
    d['task']=key(d,['image_id','condition','reference_id','reference_version'])
    d['source_task']=key(d,['image_id','condition'])
    d['panel']=d.condition+'|'+d.quality_use
    assert d.object_id.is_unique and len(d)==10439
    q=d[d.quality_usable].copy();main=q[q.condition.eq('manual')&q.quality_use.eq('ordinary_primary')].copy()
    assert len(q)==7302 and q.worker_id.nunique()==60 and q.image_id.nunique()==196
    assert len(main)==5719 and main.image_id.nunique()==177 and main.building_id.nunique()==22
    assert main.difficulty.isin(DIFFS).all() and main.difficulty_reference_match.all()
    assert not main.duplicated(['task','worker_id']).any()
    times={}
    gate=d.pool_analysis_eligible & d.condition.eq('manual') & d.ordinary_difficulty_eligible & d.difficulty.isin(DIFFS)
    for name,col in [('source','source_active_time_seconds'),('target','target_matched_time_seconds')]:
        a=d[gate&d[col].gt(0)].copy();a['seconds']=a[col];a['log_seconds']=np.log(a.seconds)
        if name=='source':a['task']=a.source_task
        assert not a.duplicated(['task','worker_id']).any()
        times[name]=a
    old=pd.DataFrame(tables['statistics__v1_v2_common_membership'])
    oldqids=set(old.loc[old.quality_usable_v1,'object_id'])
    d['v1_quality_member']=d.object_id.isin(oldqids)
    q['v1_quality_member']=q.object_id.isin(oldqids);main['v1_quality_member']=main.object_id.isin(oldqids)
    dev=pd.read_csv(repo/'research/workers/worker_b8l2_d10_20261017/quality_panel.csv')
    for frame in [d,q,main]:frame['v1_development_member']=frame.object_id.isin(dev.object_id)
    assert main.v1_development_member.sum()==1048 and main.v1_quality_member.sum()==1258
    assert q.v1_quality_member.sum()==1911
    d.to_csv(out/'records_flat.csv',index=False)
    cov={'inventory':cnt(d),'quality':cnt(q),'ordinary_manual':cnt(main),'ordinary_by_difficulty':main.groupby('difficulty').apply(cnt,include_groups=False).to_dict(),'time':{k:cnt(v) for k,v in times.items()},'main_quality_time':{'source':int(main.source_active_time_seconds.notna().sum()),'target':int(main.target_matched_time_seconds.notna().sum())},'time_quality_missing':{k:int((~v.quality_usable).sum())for k,v in times.items()},'sources':{str(k):int(v) for k,v in d.groupby(['origin','time_source_kind']).source_active_time_seconds.count().items()},'v1_fixed':cnt(q[q.v1_quality_member]),'v1_manual':cnt(main[main.v1_quality_member]),'v1_development':cnt(main[main.v1_development_member]),'v1_newly_qualified':cnt(q[q.origin.eq('v1')&~q.v1_quality_member]),'inputs_sha256':{str(p.relative_to(repo)):digest(p)for p in [ep,tp,ap]},'registration_sha256':digest(out/'REGISTRATION.json')}
    js(out/'INPUT_COVERAGE.json',cov)
    return d,q,main,times,tables,ctx

def relative(d,metric):
    n=d.groupby('task')[metric].transform('size');mean=d.groupby('task')[metric].transform('mean');rank=d.groupby('task')[metric].rank(method='average')
    return pd.DataFrame({'percentile':((rank-1)/(n-1)).where(n>1),'centered':d[metric]-mean,'peer_delta':((d[metric]-mean)*n/(n-1)).where(n>1),'peer_n':n-1},index=d.index)

def sufficient(d,outcome,workers):
    ix={w:i for i,w in enumerate(workers)};n=len(workers);A=np.zeros((n,n));b=np.zeros(n)
    for _,g in d.groupby('task',sort=False):
        ids=np.array([ix[w] for w in g.worker_id]);y=g[outcome].to_numpy(float);m=len(g)
        A[np.ix_(ids,ids)]+=np.eye(m)-np.ones((m,m))/m;b[ids]+=y-y.mean()
    return A,b

def solve(A,b,C):
    C=np.asarray(C,float)
    if C.ndim==1:C=C[:,None]
    K=np.block([[A,C],[C.T,np.zeros((C.shape[1],C.shape[1]))]])
    return np.linalg.lstsq(K,np.r_[b,np.zeros(C.shape[1])],rcond=1e-11)[0][:len(b)]

def fit_fe(d,outcome,ridge=0,workers=None,anchor=None):
    if workers is None:workers=sorted(d.worker_id.unique())
    if not workers:return {},{'nullity':0}
    A,b=sufficient(d,outcome,workers);C=np.ones(len(workers)) if anchor is None else np.array([w in anchor for w in workers],float)
    if not C.any():C[:]=1
    beta=solve(A+ridge*np.eye(len(workers)),b,C)
    return dict(zip(workers,beta)),{'nullity':len(workers)-np.linalg.matrix_rank(A,tol=1e-8),'constraint_error':abs(float(C@beta))}

def fit_joint(d,outcome,strength=20,ridge=0,workers=None):
    workers=sorted(d.worker_id.unique()) if workers is None else workers;m=len(workers)
    A=np.zeros((3*m,3*m));b=np.zeros(3*m)
    for j,diff in enumerate(DIFFS):
        a,v=sufficient(d[d.difficulty.eq(diff)],outcome,workers);sl=slice(j*m,(j+1)*m);A[sl,sl]=a;b[sl]=v
    A+=strength*np.kron(np.eye(3)-np.ones((3,3))/3,np.eye(m))+ridge*np.eye(3*m)
    C=np.kron(np.eye(3),np.ones((m,1)));res=solve(A,b,C)
    return {(w,diff):res[j*m+i]for j,diff in enumerate(DIFFS)for i,w in enumerate(workers)}

def stats(g,col,prefix=''):
    a=pd.to_numeric(g[col],errors='coerce').dropna()
    out={prefix+'n':len(a)}
    for name,f in [('mean',lambda x:x.mean()),('median',lambda x:x.median()),('p10',lambda x:x.quantile(.1)),('q25',lambda x:x.quantile(.25)),('q75',lambda x:x.quantile(.75)),('p90',lambda x:x.quantile(.9)),('sd',lambda x:x.std()),('min',lambda x:x.min()),('max',lambda x:x.max())]:out[prefix+name]=float(f(a)) if len(a) else np.nan
    return out

def labelq(x,nclass=2,supported=True):
    if not supported or not np.isfinite(x):return 'unknown'
    if nclass==2:return 'Q+' if x>=0 else 'Q-'
    return 'above_peer' if x>=3 else ('below_peer' if x<=-3 else 'near_peer')
def labelt(x,nclass=2,supported=True):
    if not supported or not np.isfinite(x):return 'unknown'
    if nclass==2:return 'fast' if x<=0 else 'slow'
    a=math.log(1.25);return 'fast' if x < -a else ('slow' if x>=a else 'middle')
def fixedt(m,threshold,supported=True):
    return 'unknown' if not supported or not np.isfinite(m) else ('fast' if m<threshold[0] else ('slow'if m>=threshold[1] else'middle'))

def time_profiles(times,workers,heldout):
    out={w:{'worker_id':w}for w in workers}
    for name,alltime in times.items():
        t=alltime if heldout=='FULL' else alltime[alltime.building_id.ne(heldout)]
        beta,_=fit_fe(t,'log_seconds');groups=dict(tuple(t.groupby('worker_id')))
        originfits={}
        for _,g in t.groupby(['origin','time_source_kind']):originfits.update(fit_fe(g,'log_seconds')[0])
        for w in workers:
            r=out[w];g=groups.get(w,t.iloc[:0]);su=support(g);r[f'T_{name}_effect']=beta.get(w,np.nan);r[f'T_{name}_supported']=su
            r[f'T_{name}_tasks']=g.task.nunique();r[f'T_{name}_buildings']=g.building_id.nunique();r[f'T_{name}_images']=g.image_id.nunique();r[f'T_{name}_n']=len(g)
            r[f'T_{name}_origin_effect']=originfits.get(w,np.nan);r[f'T_{name}_origin_supported']=su
            for k,v in stats(g,'seconds',f'T_{name}_').items():r[k]=v
            r[f'T_{name}_origin']='|'.join(sorted(g.origin.unique()))
            r[f'T_{name}_kinds']='|'.join(sorted(g.time_source_kind.unique()))
            if name=='source':
                r['T_relative_2']=labelt(beta.get(w,np.nan),2,su);r['T_relative_3']=labelt(beta.get(w,np.nan),3,su)
                r['T_fixed_60_180']=fixedt(r['T_source_median'],(60,180),su);r['T_fixed_90_240']=fixedt(r['T_source_median'],(90,240),su)
                for diff in DIFFS:
                    s=g[g.difficulty.eq(diff)];r[f'T_source_{diff}_median']=s.seconds.median();r[f'T_source_{diff}_n']=len(s);r[f'T_source_{diff}_buildings']=s.building_id.nunique()
    return out

def make_profiles(train,times,workers,heldout):
    timeparts=time_profiles(times,workers,heldout);groups=dict(tuple(train.groupby('worker_id')));empty=train.iloc[:0]
    fitmaps={};rows=[]
    for w in workers:
        g=groups.get(w,empty);r=timeparts[w];r.update(heldout_building=heldout,Q_supported=support(g),Q_n=len(g),Q_tasks=g.task.nunique(),Q_images=g.image_id.nunique(),Q_buildings=g.building_id.nunique(),origin='|'.join(sorted(g.origin.unique())))
        for diff in DIFFS:
            x=g[g.difficulty.eq(diff)];r['difficulty_supported_'+diff]=support(x);r['n_'+diff]=len(x);r['images_'+diff]=x.image_id.nunique();r['buildings_'+diff]=x.building_id.nunique()
        rows.append(r)
    p=pd.DataFrame(rows).set_index('worker_id',drop=False)
    for metric in METRICS:
        beta,info=fit_fe(train,metric);ridge,_=fit_fe(train,metric,5)
        joint={lam:fit_joint(train,metric,lam)for lam in [0,5,20,80]};ridgejoint=fit_joint(train,metric,20,5)
        rr=relative(train,metric);a=train.join(rr)
        raw=a.groupby('worker_id')[metric].mean().to_dict();rank=a.groupby('worker_id').percentile.mean().to_dict();center=a.groupby('worker_id').centered.mean().to_dict();peerdelta=a.groupby('worker_id').peer_delta.mean().to_dict()
        a['rank_mean']=a.worker_id.map(rank);xc=a.rank_mean-a.groupby('task').rank_mean.transform('mean');yc=a[metric]-a.groupby('task')[metric].transform('mean');slope=float(xc@yc/(xc@xc))
        rankcal={w:(x-.5)*slope for w,x in rank.items()}
        models={'raw_mean':raw,'rank_calibrated':rankcal,'centered_mean':center,'peer_delta_mean':peerdelta,'FE':beta,'ridge5':ridge,'joint0':joint[0],'joint5':joint[5],'joint20':joint[20],'joint80':joint[80],'ridge5_joint20':ridgejoint}
        fitmaps[metric]={'models':models,'rank_scale':slope,'fitinfo':info}
        for w in workers:
            g=groups.get(w,empty);idx=g.index;su=bool(p.at[w,'Q_supported']);p.at[w,'Q_effect_'+metric]=beta.get(w,np.nan);p.at[w,'Q_ridge5_'+metric]=ridge.get(w,np.nan);p.at[w,'Q2_'+metric]=labelq(beta.get(w,np.nan),2,su);p.at[w,'Q3_'+metric]=labelq(beta.get(w,np.nan),3,su)
            p.at[w,'percentile_'+metric]=rank.get(w,np.nan);p.at[w,'centered_mean_'+metric]=center.get(w,np.nan);p.at[w,'peer_delta_'+metric]=peerdelta.get(w,np.nan)
            p.at[w,'Q_connectivity_nullity_'+metric]=info['nullity']
            for k,v in stats(g,metric,'absolute_'+metric+'_').items():p.at[w,k]=v
            for diff in DIFFS:
                x=g[g.difficulty.eq(diff)];p.at[w,f'theta_{diff}_{metric}']=joint[20].get((w,diff),np.nan)
                p.at[w,f'theta_joint5_{diff}_{metric}']=joint[5].get((w,diff),np.nan);p.at[w,f'theta_joint80_{diff}_{metric}']=joint[80].get((w,diff),np.nan)
                p.at[w,f'percentile_{diff}_{metric}']=rr.loc[x.index,'percentile'].mean();p.at[w,f'peer_delta_{diff}_{metric}']=rr.loc[x.index,'peer_delta'].mean()
                for k,v in stats(x,metric,f'absolute_{diff}_{metric}_').items():p.at[w,k]=v
            te,tm,th=[joint[20].get((w,d),np.nan)for d in DIFFS];de=th-te;dm=th-tm
            p.at[w,'hard_minus_easy_'+metric]=de;p.at[w,'hard_minus_medium_'+metric]=dm;p.at[w,'medium_minus_easy_'+metric]=tm-te
            ds=all(bool(p.at[w,'difficulty_supported_'+d])for d in DIFFS)
            typ=adapt='unknown'
            if ds:
                adapt='up' if de>=3 and dm>=3 else ('down'if de<=-3 and dm<=-3 else'mixed_or_near')
                typ='across_strong' if min(te,tm,th)>=3 else ('hard_specialist' if th>=3 and adapt=='up' else ('hard_relative_lift_only'if adapt=='up'else('hard_drop'if adapt=='down'else'mixed_or_near')))
            p.at[w,'hard_adaptation_'+metric]=adapt;p.at[w,'difficulty_type_'+metric]=typ
            p.at[w,'QT_'+metric]=p.at[w,'Q2_'+metric]+'|'+p.at[w,'T_relative_2'] if su and bool(p.at[w,'T_source_supported']) else 'unknown'
            p.at[w,'QT3_'+metric]=p.at[w,'Q3_'+metric]+'|'+p.at[w,'T_relative_3'] if su and bool(p.at[w,'T_source_supported']) else 'unknown'
            p.at[w,'fine_candidate_'+metric]=p.at[w,'QT_'+metric]+'|'+adapt if p.at[w,'QT_'+metric]!='unknown' else 'unknown'
        p['fine_'+metric]=p['QT_'+metric]
        for parent,g in p[p['QT_'+metric].ne('unknown')].groupby('QT_'+metric):
            counts=g['hard_adaptation_'+metric].value_counts();accepted=set(counts[(counts>=3)&counts.index.to_series().ne('unknown')].index)
            for w,row in g.iterrows():
                child=row['hard_adaptation_'+metric]
                if child=='unknown':fine=parent+'|difficulty_unknown'
                elif len(accepted)>=2 and child in accepted:fine=parent+'|'+child
                elif len(accepted)>=2:fine=parent+'|sparse_child'
                else:fine=parent+'|not_split'
                p.at[w,'fine_'+metric]=fine
        # Class prediction is trained from historical continuous effects, never target answers.
        for cname,col,usejoint in [('class_Q2','Q2_',False),('class_Q3','Q3_',False),('class_QT','QT_',False),('class_QT3','QT3_',False),('class_QTD','fine_',True),('class_QTD_candidate','fine_candidate_',True),('class_difficulty','difficulty_type_',True)]:
            mp={}
            for _,g in p[p[col+metric].ne('unknown')].groupby(col+metric):
                for diff in DIFFS:
                    vals=[joint[20].get((w,diff),np.nan) if usejoint else beta.get(w,np.nan) for w in g.worker_id];mean=float(np.nanmean(vals))
                    for w in g.worker_id:mp[(w,diff)]=mean
            fitmaps[metric]['models'][cname]=mp
        # Four-way parent using theta centroids isolates adding adaptation to QT.
        mp={}
        for _,g in p[p['QT_'+metric].ne('unknown')].groupby('QT_'+metric):
            for diff in DIFFS:
                mean=float(np.mean([joint[20][(w,diff)]for w in g.worker_id]))
                for w in g.worker_id:mp[(w,diff)]=mean
        fitmaps[metric]['models']['class_QT_theta']=mp
    return p.reset_index(drop=True),fitmaps

def map_effect(d,mp):
    return np.array([mp.get((w,di),mp.get(w,np.nan))for w,di in zip(d.worker_id,d.difficulty)],float)

def predict_fold(train,test,profiles,fits,panel):
    result=[];eligible=set(profiles.loc[profiles.Q_supported,'worker_id']);test=test[test.worker_id.isin(eligible)].copy()
    for metric in METRICS:
        for name,mp in fits[metric]['models'].items():
            pr=map_effect(test,mp);tr=map_effect(train,mp)
            a=train[['task','difficulty',metric]].copy();a['alpha']=a[metric]-tr
            alpha=a.groupby(['task','difficulty']).alpha.mean().reset_index().groupby('difficulty').alpha.mean().to_dict()
            x=test[['object_id','worker_id','image_id','image_code','building_id','task','difficulty','origin',metric]].copy().rename(columns={metric:'observed'})
            x['prediction_effect']=pr;x['prediction_absolute']=[alpha.get(d,np.nan)+v for d,v in zip(x.difficulty,pr)]
            x['panel']=panel;x['metric']=metric;x['model']=name
            valid=x.prediction_effect.notna();n=x[valid].groupby('task')['observed'].transform('size')
            # Outcomes and predictions use the identical set of supported evaluation peers.
            yy=x.loc[valid,'observed'];pp=x.loc[valid,'prediction_effect'];g=x.loc[valid,'task']
            x.loc[valid,'observed_peer_delta']=((yy-yy.groupby(g).transform('mean'))*n/(n-1)).where(n>1)
            x.loc[valid,'predicted_peer_delta']=((pp-pp.groupby(g).transform('mean'))*n/(n-1)).where(n>1)
            x['relative_sqerr']=(x.observed_peer_delta-x.predicted_peer_delta)**2;x['relative_abs_error']=(x.observed_peer_delta-x.predicted_peer_delta).abs()
            x['absolute_sqerr']=(x.observed-x.prediction_absolute)**2
            result.append(x)
    return pd.concat(result,ignore_index=True)

def summaries(pred,out,prefix=''):
    z=pred[pred.relative_sqerr.notna()].copy()
    im=z.groupby(['panel','metric','model','building_id','image_id','difficulty'],as_index=False).agg(relative_mse=('relative_sqerr','mean'),absolute_mse=('absolute_sqerr','mean'),relative_mae=('relative_abs_error','mean'),n=('object_id','size'))
    im.to_csv(out/(prefix+'validation_per_image.csv'),index=False)
    # All-difficulty and each difficulty have separately visible denominators.
    imall=pd.concat([im.assign(difficulty='all'),im],ignore_index=True)
    bld=imall.groupby(['panel','metric','model','difficulty','building_id'],as_index=False).agg(relative_mse=('relative_mse','mean'),absolute_mse=('absolute_mse','mean'),relative_mae=('relative_mae','mean'),n_images=('image_id','nunique'),n=('n','sum'))
    bld.to_csv(out/(prefix+'validation_per_building.csv'),index=False)
    ag=bld.groupby(['panel','metric','model','difficulty'],as_index=False).agg(building_equal_relative_mse=('relative_mse','mean'),building_equal_absolute_mse=('absolute_mse','mean'),building_equal_relative_mae=('relative_mae','mean'),buildings=('building_id','nunique'),images=('n_images','sum'),n=('n','sum'))
    ime=imall.groupby(['panel','metric','model','difficulty'],as_index=False).relative_mse.mean().rename(columns={'relative_mse':'image_equal_relative_mse'});ag=ag.merge(ime)
    ag.to_csv(out/(prefix+'validation_summary.csv'),index=False)
    # Comparisons pair exact rows, then images, then buildings; no denominator drift.
    bases=['FE','joint20','class_QT_theta','class_Q2'];compar=[]
    for (panel,metric),g in z.groupby(['panel','metric']):
        keys=['object_id','worker_id','image_id','building_id','difficulty','task']
        for base in bases:
            a=g[g.model.eq(base)][keys+['observed','prediction_effect','absolute_sqerr']].rename(columns={'prediction_effect':'base_effect','absolute_sqerr':'base_abs'})
            if a.empty:continue
            for model,x in g.groupby('model'):
                if model==base:continue
                m=a.merge(x[keys+['prediction_effect','absolute_sqerr']],on=keys,validate='one_to_one')
                # Reconstruct the target on each exact common peer set. Merely
                # pairing precomputed errors would leave different targets when
                # a class has missing T or different support from the baseline.
                ng=m.groupby('task')['observed'].transform('size')
                yd=(m.observed-m.groupby('task')['observed'].transform('mean'))*ng/(ng-1)
                bd=(m.base_effect-m.groupby('task').base_effect.transform('mean'))*ng/(ng-1)
                md=(m.prediction_effect-m.groupby('task').prediction_effect.transform('mean'))*ng/(ng-1)
                m['base']=(yd-bd)**2;m['relative_sqerr']=(yd-md)**2;m=m[ng>1].copy()
                for diff in ['all',*DIFFS]:
                    s=m if diff=='all' else m[m.difficulty.eq(diff)]
                    v=s.groupby(['building_id','image_id'])[['base','relative_sqerr','base_abs','absolute_sqerr']].mean().groupby('building_id').mean()
                    if len(v)<2:continue
                    seed=int(hashlib.sha256(f'{SEED}|{panel}|{metric}|{base}|{model}|{diff}'.encode()).hexdigest()[:16],16)
                    rng=np.random.default_rng(seed)
                    n=len(v);idx=rng.integers(0,n,size=(2000,n));a0=v.base.to_numpy();a1=v.relative_sqerr.to_numpy();boot0=a0[idx].mean(1);boot1=a1[idx].mean(1);gain=100*(boot0-boot1)/boot0
                    compar.append(dict(panel=panel,metric=metric,baseline=base,model=model,difficulty=diff,n=len(s),images=s.image_id.nunique(),buildings=n,base_mse=a0.mean(),model_mse=a1.mean(),improvement_percent=100*(a0.mean()-a1.mean())/a0.mean(),ci_low=np.quantile(gain,.025),ci_high=np.quantile(gain,.975),improved_buildings=int((a1<a0).sum()),absolute_improvement_percent=100*(v.base_abs.mean()-v.absolute_sqerr.mean())/v.base_abs.mean()))
    pd.DataFrame(compar).to_csv(out/(prefix+'paired_model_comparison.csv'),index=False)

def full_descriptions(q,main,full,out):
    rows=[]
    for (panel,w),g in q.groupby(['panel','worker_id']):
        for diff,x in [('all',g),*((d,g[g.difficulty.eq(d)&g.difficulty_reference_match])for d in DIFFS)]:
            r=dict(panel=panel,worker_id=w,difficulty=diff,**cnt(x),quality_n=len(x),source_time_n=x.source_active_time_seconds.notna().sum(),target_time_n=x.target_matched_time_seconds.notna().sum())
            for col in ['B8L2','D10','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','height_mean_ratio','IoU3D100','declared_pair_count']:
                r.update(stats(x,col,col+'_'))
            rows.append(r)
    pd.DataFrame(rows).to_csv(out/'worker_panel_descriptions.csv',index=False)
    classes=[]
    for metric in METRICS:
        for typ in ['Q2','Q3','QT','QT3','fine_candidate','fine','hard_adaptation','difficulty_type']:
            for lab,g in full.groupby(typ+'_'+metric):
                source=main[main.worker_id.isin(g.worker_id)]
                classes.append(dict(metric=metric,scheme=typ,label=lab,workers=len(g),members=';'.join(sorted(g.worker_id)),quality_n=len(source),images=source.image_id.nunique(),buildings=source.building_id.nunique(),q_supported_workers=g.Q_supported.sum(),t_supported_workers=g.T_source_supported.sum(),all_difficulty_supported_workers=g[[f'difficulty_supported_{d}'for d in DIFFS]].all(axis=1).sum(),status='unknown_or_sparse' if lab=='unknown' or len(g)<3 else'exploratory_candidate'))
    pd.DataFrame(classes).to_csv(out/'class_membership.csv',index=False)

def stability(full,fold,out):
    rows=[]
    for w,g in fold.groupby('worker_id'):
        f=full[full.worker_id.eq(w)].iloc[0]
        for metric in METRICS:
            r={'worker_id':w,'metric':metric,'folds':len(g)}
            for col in ['Q2','Q3','QT','QT3','fine_candidate','fine','hard_adaptation','difficulty_type']:
                a=g[col+'_'+metric];r[col+'_full']=f[col+'_'+metric];r[col+'_same_fraction']=(a==f[col+'_'+metric]).mean();r[col+'_unknown_fraction']=a.eq('unknown').mean();r[col+'_unique_labels']=a.nunique()
            for col in ['Q_effect','hard_minus_easy','hard_minus_medium','medium_minus_easy',*[f'theta_{d}'for d in DIFFS]]:
                vals=g[col+'_'+metric].dropna().to_numpy();est=f[col+'_'+metric];n=len(vals);se=np.sqrt((n-1)/n*np.sum((vals-vals.mean())**2)) if n>1 else np.nan
                r[col]=est;r[col+'_jackknife_se']=se;r[col+'_ci_low']=est-1.96*se;r[col+'_ci_high']=est+1.96*se;r[col+'_leaveout_min']=vals.min()if n else np.nan;r[col+'_leaveout_max']=vals.max()if n else np.nan
            rows.append(r)
    pd.DataFrame(rows).to_csv(out/'profile_stability_uncertainty.csv',index=False)

def audit_v1(repo,d,q,main,out):
    base=repo/'research/workers/worker_b8l2_d10_20261017';oldq=pd.read_csv(repo/'research/quality/quality_b8l2_d10_20261017/quality_records.csv')
    oldq=oldq[oldq.quality_usable];oldprof=pd.read_csv(base/'profiles.csv');dev=pd.read_csv(base/'quality_panel.csv');v1main=main[main.v1_quality_member].copy()
    olddev=main[main.v1_development_member].copy();legacy_anchor=sorted(dev.worker_id.unique());receipt={'quality_records':len(oldq),'v1_manual':cnt(v1main),'development':cnt(olddev),'existing_profile_panels':oldprof.groupby(['panel','axis']).size().to_dict()}
    common=q[q.v1_quality_member][['object_id','B8L2','D10','reference_id']].merge(oldq[['object_id','B8L2','D10','reference_id']],on='object_id',suffixes=('_v2','_v1'),validate='one_to_one')
    receipt['same_reference_identity']=int(common.reference_id_v2.eq(common.reference_id_v1).sum())
    receipt['score_max_abs_diff']={m:float((common[m+'_v2']-common[m+'_v1']).abs().max())for m in METRICS}
    assert len(common)==1911 and max(receipt['score_max_abs_diff'].values())<1e-9
    fits=[]
    for metric in METRICS:
        b,_=fit_fe(olddev,metric,anchor=legacy_anchor)
        for w,e in b.items():
            x=oldprof[oldprof.worker_id.eq(w)&oldprof.axis.eq(metric)&oldprof.panel.eq('current')]
            if x.empty:x=oldprof[oldprof.worker_id.eq(w)&oldprof.axis.eq(metric)&oldprof.panel.eq('all1048')]
            fits.append(dict(axis=metric,worker_id=w,independent_effect=e,published_effect=x.effect.iloc[0] if len(x)==1 else np.nan,published_panel=x.panel.iloc[0]if len(x)==1 else'not_identified'))
    for name,col in [('source','source_active_time_seconds'),('target','target_matched_time_seconds')]:
        a=pd.read_csv(base/f'T_{name}_panel.csv');a['task']=a.context_key;a['log1p']=np.log1p(a[col]);b,_=fit_fe(a,'log1p',anchor=legacy_anchor)
        receipt['legacy_time_'+name]=cnt(a)
        for w,e in b.items():
            x=oldprof[oldprof.worker_id.eq(w)&oldprof.axis.eq('T_'+name)&oldprof.panel.eq('T_'+name)]
            if x.empty:x=oldprof[oldprof.worker_id.eq(w)&oldprof.axis.eq('T_'+name)&oldprof.panel.eq('all1048')]
            fits.append(dict(axis='T_'+name,worker_id=w,independent_effect=e,published_effect=x.effect.iloc[0]if len(x)==1 else np.nan,published_panel=x.panel.iloc[0]if len(x)==1 else'not_identified'))
    pd.DataFrame(fits).to_csv(out/'v1_existing_effect_replication.csv',index=False)
    common.to_csv(out/'v1_fixed_record_score_replication.csv',index=False)
    q[q.origin.eq('v1')&~q.v1_quality_member].to_csv(out/'v1_newly_qualified_37.csv',index=False)
    # Fixed old answers: evaluate how adding peers changes relative descriptions, not geometry.
    shifts=[]
    for metric in METRICS:
        a=v1main.join(relative(v1main,metric)).set_index('object_id');b=main.join(relative(main,metric)).set_index('object_id')
        v=a[['worker_id','image_id','building_id',metric,'percentile','peer_delta','peer_n']].join(b[['percentile','peer_delta','peer_n']],rsuffix='_newpool')
        for c in ['percentile','peer_delta','peer_n']:v[c+'_shift']=v[c+'_newpool']-v[c]
        v['metric']=metric;shifts.append(v.reset_index())
    pd.concat(shifts,ignore_index=True).to_csv(out/'v1_fixed_answers_peer_pool_shift.csv',index=False)
    js(out/'V1_REPLICATION.json',receipt)

def timing_analysis(d,main,times,full,out):
    rows=[]
    for (origin,kind),g in d[d.source_active_time_seconds.notna()].groupby(['origin','time_source_kind']):
        r=dict(panel='all_inventory',origin=origin,time_source_kind=kind,**cnt(g));r.update(stats(g,'source_active_time_seconds','seconds_'));rows.append(r)
    for diff in ['all',*DIFFS]:
        z=times['source'] if diff=='all'else times['source'][times['source'].difficulty.eq(diff)]
        for origin,g in z.groupby('origin'):
            r=dict(panel='ordinary_source_time',difficulty=diff,origin=origin,**cnt(g));r.update(stats(g,'seconds','seconds_'));r['quality_available']=g.quality_usable.sum();rows.append(r)
    pd.DataFrame(rows).to_csv(out/'time_source_descriptions.csv',index=False)
    x=full[['worker_id','origin','Q_supported','T_source_supported','T_source_n','T_source_buildings','T_source_median','T_source_p90','T_source_effect','T_source_origin_effect','T_target_effect','T_target_supported','T_fixed_60_180','T_fixed_90_240','T_relative_2','T_relative_3','Q_effect_B8L2','absolute_B8L2_mean','absolute_B8L2_p10']].copy()
    x['fixed_label_changed']=x.T_fixed_60_180.ne(x.T_fixed_90_240);x.to_csv(out/'time_threshold_stability.csv',index=False)
    assoc=[]
    # Within-task comparisons are descriptive: speed could be caused by omissions or ability.
    for origin in ['all','v1','new']:
        z=main[main.source_active_time_seconds.gt(0)].copy()
        if origin!='all':z=z[z.origin.eq(origin)]
        z['log_time']=np.log(z.source_active_time_seconds)
        for diff in ['all',*DIFFS]:
            g=z if diff=='all'else z[z.difficulty.eq(diff)]
            for y in ['B8L2','declared_pair_count','iou_2d','S_bottom_deg','Hmean']:
                a=g[['task','building_id','image_id','log_time',y]].dropna();a['xc']=a.log_time-a.groupby('task').log_time.transform('mean');a['yc']=a[y]-a.groupby('task')[y].transform('mean')
                den=float(a.xc@a.xc);slope=float(a.xc@a.yc/den)if den else np.nan
                assoc.append(dict(origin=origin,difficulty=diff,outcome=y,n=len(a),images=a.image_id.nunique(),buildings=a.building_id.nunique(),within_task_slope_per_log_second=slope,correlation=a.xc.corr(a.yc)))
    pd.DataFrame(assoc).to_csv(out/'time_complexity_quality_associations.csv',index=False)

def main_cli():
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,default=Path('repo_main_20261019'));parser.add_argument('--out',type=Path,default=Path('work_v2_20261019/profiles'));parser.add_argument('--skip-v1-validation',action='store_true');args=parser.parse_args();repo=args.repo;out=args.out;out.mkdir(parents=True,exist_ok=True)
    started=time.time();d,q,main,times,tables,ctx=load_inputs(repo,out);print('loaded',cnt(main),'times',{k:cnt(v)for k,v in times.items()},flush=True)
    workers=sorted(q.worker_id.unique());full,fits=make_profiles(main,times,workers,'FULL');full.to_csv(out/'full_profiles.csv',index=False);print('full profiles written',len(full),flush=True)
    folds=[];pred=[]
    for i,b in enumerate(sorted(main.building_id.unique())):
        train=main[main.building_id.ne(b)];test=main[main.building_id.eq(b)];p,f=make_profiles(train,times,workers,b);folds.append(p);pred.append(predict_fold(train,test,p,f,'v2_full_5719'));print('fold',i+1,b,'test',len(test),flush=True)
    fold=pd.concat(folds,ignore_index=True);fold.to_csv(out/'fold_profiles.csv',index=False)
    pred=pd.concat(pred,ignore_index=True);pred.to_csv(out/'validation_predictions.csv.gz',index=False,compression='gzip');print('fold profiles ready',len(fold),'predictions',len(pred),flush=True)
    summaries(pred,out);full_descriptions(q,main,full,out);stability(full,fold,out);timing_analysis(d,main,times,full,out);audit_v1(repo,d,q,main,out)
    # Explicit version series: old fixed workers, old expanded qualification, and all v2.
    vpro=[];vp=[]
    for panel,source in [('v1_fixed_1258',main[main.v1_quality_member]),('v1_development_1048',main[main.v1_development_member]),('v2_old_1295',main[main.origin.eq('v1')])]:
        ws=sorted(source.worker_id.unique());ts={k:v[v.origin.eq('v1')]for k,v in times.items()};p,f=make_profiles(source,ts,ws,'FULL');p['version_panel']=panel;vpro.append(p)
        if not args.skip_v1_validation:
            for b in sorted(source.building_id.unique()):
                train=source[source.building_id.ne(b)];test=source[source.building_id.eq(b)];p,f=make_profiles(train,ts,ws,b);vp.append(predict_fold(train,test,p,f,panel))
        print('version done',panel,flush=True)
    pd.concat(vpro,ignore_index=True).to_csv(out/'version_profiles.csv',index=False)
    if vp:
        v=pd.concat(vp,ignore_index=True);v.to_csv(out/'version_validation_predictions.csv.gz',index=False,compression='gzip');summaries(v,out,'version_')
    js(out/'RUN_RECEIPT.json',{'completed':True,'runtime_seconds':time.time()-started,'code_sha256':digest(Path(__file__)),'registration_sha256':digest(out/'REGISTRATION.json'),'full_profiles':len(full),'fold_profiles':len(fold),'prediction_rows':len(pred),'source_commit':'82c6164b0d4630de5316199c92aa405930973168','v1_validation_rerun':bool(vp),'no_geometry_or_eligibility_mutation':True});print('COMPLETE',time.time()-started,flush=True)

if __name__=='__main__':main_cli()
