#!/usr/bin/env python3
"""Target-building-excluded, opportunity-aware five-domain personnel classes.

Reuses the frozen task fixed-effect and difficulty partial-pooling estimators.
No fusion outcome, target-building record, or old final label enters a fit.
This study is exploratory reuse of an already-explored inventory, not a blind test.
"""
from __future__ import annotations
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import gzip
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from sklearn.metrics import adjusted_rand_score, adjusted_mutual_info_score, silhouette_score

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SOURCE = REPO / 'research/statistics/v2_evidence_audit_20261019/records.json.gz'
INDEX = REPO / 'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz'
UPSTREAM = REPO / 'research/workers/personnel_interchangeability_20261020/analysis/forward/build_forward.py'
DOMAIN_ORDER = ['Q', 'T', 'D', 'scope', 'Semi']
DOMAINS = {
    'Q': ['q_effect', 'q_downside'],
    'T': ['t_effect', 't_tail'],
    'D': ['hard_minus_easy', 'medium_minus_easy'],
    'scope': ['scope_out_effect'],
    'Semi': ['semi_edit_effect', 'semi_error_nonedit_effect'],
}
OLD_PURE = {'Q+T', 'Q+D', 'T+scope', 'T+Semi', 'Q+T+D+scope+Semi'}
OLD_GATE = {'Q+scope', 'Q+Semi', 'Q+T+scope', 'Q+T+Semi'}
METHODS = [
    {'method_id': 'MV_QTD_manual', 'condition': 'manual', 'domains': ['Q','T','D'], 'new_only': False,
     'parent': 'Q_zero', 'children': ['T','D'], 'scope': 'ordinary_manual',
     'description': '自身普通 Manual 的 Q 效应正负为父层；每父层按域等权 T/D 划二细类。'},
    {'method_id': 'MV_TDScopeSemi_manual_new', 'condition': 'manual', 'domains': ['T','D','scope','Semi'], 'new_only': True,
     'parent': 'ward2', 'children': ['T','D','scope','Semi'], 'scope': 'ordinary_manual_new',
     'description': '新批普通 Manual 自身 T/D/scope 加楼外 Semi 编辑及报告错误机会下未改行为；不使用 Q。'},
    {'method_id': 'MV_QTScopeSemi_semi_new', 'condition': 'semi', 'domains': ['Q','T','scope','Semi'], 'new_only': True,
     'parent': 'Q_zero', 'children': ['T','scope','Semi'], 'scope': 'ordinary_semi_new',
     'description': '新批自身普通 Semi 的 Q 效应正负为父层；每父层按域等权 T/scope/Semi 行为划二细类。'},
]

def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k,v in x.items()}
    if isinstance(x, (list,tuple,np.ndarray)): return [clean(v) for v in x]
    if isinstance(x, (np.integer,)): return int(x)
    if isinstance(x, (np.bool_,)): return bool(x)
    if isinstance(x, (float,np.floating)): return float(x) if np.isfinite(x) else None
    return x

def js(path, x):
    Path(path).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load():
    spec=importlib.util.spec_from_file_location('unchanged_forward_helpers',UPSTREAM)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    native, fn=mod.upstream_functions(REPO)
    evidence=json.load(gzip.open(SOURCE,'rt'))['records']
    d=mod.flatten(evidence); ex=fn['extra_frame'](evidence)
    idx=pd.read_csv(INDEX)
    inv=idx[['object_id','panel']].copy()
    d=d.merge(inv,on='object_id',how='inner',validate='one_to_one')
    ex=ex.merge(inv,on='object_id',how='inner',validate='one_to_one')
    assert len(d)==len(idx)==9217
    return d,ex,native,fn

def features(d,ex,native,fn,heldout,condition,metric='B8L2'):
    """All qualification gates precede fitting, and all fits exclude heldout."""
    a=d[(d.building_id!=heldout)&d.panel.eq('ordinary')].copy()
    e=ex[(ex.building_id!=heldout)&ex.panel.eq('ordinary')].copy()
    workers=sorted(d.loc[d.condition.eq(condition),'worker_id'].unique())
    q=a[a.condition.eq(condition)&a.quality_usable&a.quality_use.eq('ordinary_primary')&a[metric].notna()].copy()
    qbeta,qfit=fn['effect'](q,metric)
    joint=native.fit_joint(q,metric,strength=20)
    q['q_centered']=q[metric]-q.groupby('task')[metric].transform('mean')
    # Same-source log seconds: never compare v1 and new clock conventions directly.
    t=a[a.condition.eq(condition)&a.pool_analysis_eligible&a.ordinary_difficulty_eligible&a.difficulty.isin(('easy','medium','hard'))&a.source_active_time_seconds.gt(0)].copy()
    t['log_seconds']=np.log(t.source_active_time_seconds)
    t['task']=[fn['key'](i,c,o,s) for i,c,o,s in zip(t.image_id,t.condition,t.origin,t.time_source_kind)]
    t['t_centered']=t.log_seconds-t.groupby('task').log_seconds.transform('mean')
    tbeta={};tfit={}
    for tag,g in t.groupby(['origin','time_source_kind']):
        b,meta=fn['effect'](g,'log_seconds');tbeta.update(b);tfit[str(tag)]=meta
    # Own condition, non-OOS ordinary opportunity inventory, including held-quality records.
    sc=e[e.condition.eq(condition)&e.scope_out.notna()].copy()
    sc['task']=sc.scope_task
    sc=sc[sc.groupby('task').worker_id.transform('nunique')>=2].copy()
    sc['task_varies']=sc.groupby('task').scope_out.transform('nunique')>1
    scbeta,scfit=fn['effect'](sc,'scope_out',ridge=5)
    # Historical Semi behavior is an explicitly cross-condition auxiliary for Manual.
    semis={};semibeta={};semimeta={}
    for origin,tier in [('new','new'),('v1','old')]:
        ss=e[e.condition.eq('semi')&e.origin.eq(origin)].copy()
        for what,mask,value in [('edit',ss.semi_edited.notna(),'semi_edited'),('error_nonedit',ss['semi_'+tier+'_opp']&ss['semi_'+tier+'_nonedit'].notna(),'semi_'+tier+'_nonedit')]:
            key=origin+'_'+what;g=ss[mask].copy();g['task']=g.semi_task
            semis[key]=g;semibeta[key],semimeta[key]=fn['effect'](g,value,ridge=5)
    byq=dict(tuple(q.groupby('worker_id')));byt=dict(tuple(t.groupby('worker_id')));bysc=dict(tuple(sc.groupby('worker_id')))
    bysemi={k:dict(tuple(g.groupby('worker_id'))) for k,g in semis.items()}
    rows=[]
    for w in workers:
        g=byq.get(w,q.iloc[:0]);tt=byt.get(w,t.iloc[:0]);s=bysc.get(w,sc.iloc[:0])
        origins=sorted(d.loc[d.worker_id.eq(w)&d.condition.eq(condition),'origin'].unique());origin='|'.join(origins)
        qok=g.task.nunique()>=(8 if condition=='manual' else 4) and g.building_id.nunique()>=3
        r=dict(worker_id=w,condition=condition,heldout_building=heldout,origin=origin,metric=metric,
               q_tasks=g.task.nunique(),q_buildings=g.building_id.nunique(),q_records=len(g),Q_supported=qok,
               q_effect=qbeta.get(w,np.nan) if qok else np.nan,
               q_downside=g.q_centered.mean()-g.q_centered.quantile(.1) if qok else np.nan,
               q_absolute_mean=g[metric].mean(),q_absolute_p10=g[metric].quantile(.1),q_absolute_sd=g[metric].std(),
               q_relative_p10=g.q_centered.quantile(.1),q_relative_sd=g.q_centered.std(),q_fit_nullity=qfit.get('nullity'))
        for diff in ('easy','medium','hard'):
            z=g[g.difficulty.eq(diff)];ok=z.task.nunique()>=6 and z.building_id.nunique()>=3
            r.update({diff+'_tasks':z.task.nunique(),diff+'_buildings':z.building_id.nunique(),diff+'_supported':ok,
                      'theta_'+diff:joint.get((w,diff),np.nan) if ok else np.nan})
        r['hard_minus_easy']=r['theta_hard']-r['theta_easy'];r['medium_minus_easy']=r['theta_medium']-r['theta_easy']
        r['D_supported']=bool(r['easy_supported'] and r['medium_supported'] and r['hard_supported'])
        tok=tt.task.nunique()>=6 and tt.building_id.nunique()>=3
        r.update(t_tasks=tt.task.nunique(),t_buildings=tt.building_id.nunique(),t_records=len(tt),T_supported=tok,
                 t_effect=tbeta.get(w,np.nan) if tok else np.nan,t_tail=tt.t_centered.quantile(.9)-tt.t_centered.median() if tok else np.nan,
                 source_time_median_seconds=tt.source_active_time_seconds.median(),source_time_mean_seconds=tt.source_active_time_seconds.mean(),
                 time_source_kind='|'.join(sorted(tt.time_source_kind.dropna().unique())),time_unit='seconds',
                 target_time_n=tt.target_matched_time_seconds.notna().sum())
        varies=s.loc[s.task_varies,'task'].nunique();scok=s.task.nunique()>=10 and s.building_id.nunique()>=3 and varies>=2
        r.update(scope_tasks=s.task.nunique(),scope_buildings=s.building_id.nunique(),scope_records=len(s),scope_varying_tasks=varies,
                 scope_supported=scok,scope_out_effect=scbeta.get(w,np.nan) if scok else np.nan,
                 scope_out_raw_rate=s.scope_out.mean(),scope_gold_n=int(s.scope_compatible_gold.sum()),
                 scope_gold_correct_n=int(s.loc[s.scope_compatible_gold,'scope_correct'].fillna(False).sum()))
        for what in ('edit','error_nonedit'):
            key=origin+'_'+what
            z=bysemi.get(key,{}).get(w,e.iloc[:0]);iserr=what=='error_nonedit'
            n_tasks=z.task.nunique() if len(z) else 0;n_buildings=z.building_id.nunique()
            ok=n_tasks>=(3 if iserr else 6) and n_buildings>=(2 if iserr else 3)
            value=('semi_new_nonedit' if origin=='new' else 'semi_old_nonedit') if iserr else 'semi_edited'
            r.update({'semi_'+what+'_tasks':n_tasks,'semi_'+what+'_buildings':n_buildings,'semi_'+what+'_records':len(z),
                      'semi_'+what+'_supported':ok,'semi_'+what+'_effect':semibeta.get(key,{}).get(w,np.nan) if ok else np.nan,
                      'semi_'+what+'_raw_rate':z[value].mean() if len(z) else np.nan})
        r['Semi_supported']=bool(r['semi_edit_supported'] and r['semi_error_nonedit_supported'])
        r['semi_evidence_tier']='reported_error_no_exact_initialization' if origin=='new' else 'exact_initialization_confirmed_error'
        r['Semi_cross_condition_auxiliary']=condition=='manual'
        rows.append(r)
    f=pd.DataFrame(rows)
    meta={'heldout_building':heldout,'condition':condition,'metric':metric,'train_buildings':sorted(a.building_id.unique()),
          'q_fit':qfit,'time_fits':tfit,'scope_fit':scfit,'semi_fits':semimeta,'target_records_used':0}
    return f,meta

def robust_matrix(f,domains):
    xs=[];meta={}
    for domain in domains:
        cols=DOMAINS[domain];a=f[cols].to_numpy(float)
        assert np.isfinite(a).all()
        median=np.median(a,axis=0);scale=np.quantile(a,.75,axis=0)-np.quantile(a,.25,axis=0)
        scale=np.where(scale>1e-9,scale,np.std(a,axis=0));scale=np.where(scale>1e-9,scale,1.)
        z=np.clip((a-median)/scale,-3,3)
        xs.append(z/np.sqrt(len(cols))/np.sqrt(len(domains)))
        meta[domain]={'features':cols,'median':median,'scale':scale,'domain_squared_distance_weight':1/len(domains),'feature_squared_distance_weight':1/len(domains)/len(cols)}
    return np.column_stack(xs),meta

def subset_mask(f,domains,new_only=False):
    mask=np.ones(len(f),bool)
    if new_only:mask &= f.origin.eq('new').to_numpy()
    for domain in domains:mask &= f[domain+'_supported'].to_numpy(bool)&f[DOMAINS[domain]].notna().all(axis=1).to_numpy()
    return mask

def ward2(x,f,domains):
    lab=cut_tree(linkage(x,method='ward',optimal_ordering=False),n_clusters=2).ravel()
    # Canonical ordering uses only entered domains. No hidden Q ordering for no-Q methods.
    first=DOMAINS[domains[0]][0]
    order=sorted(np.unique(lab),key=lambda z:(f.loc[lab==z,first].mean(),tuple(f.loc[lab==z,'worker_id'])))
    return np.array([order.index(z) for z in lab])

def classify(f,method):
    mask=subset_mask(f,method['domains'],method['new_only']);g=f.loc[mask].reset_index(drop=True)
    coarse=np.full(len(f),'unknown',object);fine=coarse.copy();childmeta={};fitmeta={}
    if len(g)>=8:
        if method['parent']=='Q_zero':
            p=np.where(g.q_effect.to_numpy()>=0,'QH','QL')
            fitmeta={'parent_rule':'q_effect >= 0: QH; else QL','parent_domain_weight':{'Q':1.}}
        else:
            x,fitmeta=robust_matrix(g,method['domains']);p=np.array(['C'+str(v+1) for v in ward2(x,g,method['domains'])])
        fineg=p.copy()
        for parent in sorted(set(p)):
            ix=np.flatnonzero(p==parent);h=g.iloc[ix].reset_index(drop=True)
            if len(h)<8:
                childmeta[parent]={'status':'no_split_parent_lt8','n':len(h)};continue
            x,scaling=robust_matrix(h,method['children']);v=ward2(x,h,method['children']);sizes=pd.Series(v).value_counts()
            if sizes.min()<4:
                childmeta[parent]={'status':'no_split_child_lt4','proposed_child_sizes':sizes.to_dict(),'scaling':scaling};continue
            # IDs preserve hierarchy; features and member lists carry interpretation.
            fineg=fineg.astype(object);fineg[ix]=[parent+'.'+str(z+1) for z in v]
            childmeta[parent]={'status':'split','class_sizes':sizes.to_dict(),'scaling':scaling}
        coarse[mask]=p;fine[mask]=fineg
    out=f[['condition','heldout_building','worker_id','origin']].copy()
    out['method_id']=method['method_id'];out['coarse_class']=coarse;out['fine_class']=fine;out['known']=coarse!='unknown'
    out['support']=out.known.map({True:'supported_outside_target_building',False:'unknown'})
    reasons=[]
    for _,row in f.iterrows():
        missing=[]
        if method['new_only'] and row.origin!='new':missing.append('outside_declared_new_source_population')
        for domain in method['domains']:
            if not row[domain+'_supported'] or row[DOMAINS[domain]].isna().any():missing.append('insufficient_'+domain+'_opportunity')
        if not missing and len(g)<8:missing.append('joint_supported_population_lt8')
        reasons.append('|'.join(missing))
    out['missing_reason']=reasons;out['domains']='+'.join(method['domains']);out['Semi_cross_condition_auxiliary']=('Semi' in method['domains'] and method['condition']=='manual')
    out['formal_team_eligibility']='not_granted_by_label; retain per-record frozen qualification'
    out['label_status']='final_all_data_exploratory' if str(f.heldout_building.iloc[0])=='ALL' else 'target_building_excluded_exploratory'
    return out,dict(method=method,supported_workers=len(g),parent=fitmeta,children=childmeta)

def subset_exploration(features_all):
    rows=[];labels=[];scalings=[]
    combos=[list(c) for n in range(2,6) for c in itertools.combinations(DOMAIN_ORDER,n)]
    for (condition,heldout),f in features_all.groupby(['condition','heldout_building'],sort=True):
        f=f.reset_index(drop=True)
        for domains in combos:
            subset='+'.join(domains);new_only='scope' in domains or 'Semi' in domains
            good=subset_mask(f,domains,new_only);g=f.loc[good].reset_index(drop=True)
            r={'condition':condition,'heldout_building':heldout,'domain_subset':subset,'domain_count':len(domains),'population':'new' if new_only else 'all_sources',
               'supported_workers':len(g),'old_coverage':'pure_fitted' if subset in OLD_PURE else 'Q_population_gate_only' if subset in OLD_GATE else 'no_pure_old_candidate_found',
               'new_work_scope':'one_prespecified_equal_domain_Ward2_screen_only','new_team_experiment':False}
            for domain in domains:r[domain+'_individually_supported']=int(f.loc[f.origin.eq('new') if new_only else np.ones(len(f),bool),domain+'_supported'].sum())
            if len(g)<8:
                r.update(status='opportunity_insufficient',class_sizes='',silhouette=np.nan,source_AMI=np.nan,min_class_size=0)
            else:
                x,scaling=robust_matrix(g,domains);lab=ward2(x,g,domains);counts=pd.Series(lab).value_counts().sort_index()
                r.update(status='screened' if counts.min()>=4 else 'screened_thin_class_not_adopted',class_sizes='|'.join(map(str,counts)),min_class_size=counts.min(),
                         silhouette=silhouette_score(x,lab),source_AMI=adjusted_mutual_info_score(g.origin,lab))
                for w,l in zip(g.worker_id,lab):labels.append({'condition':condition,'heldout_building':heldout,'domain_subset':subset,'worker_id':w,'class_id':'C'+str(l+1)})
                if heldout=='ALL':scalings.append({'condition':condition,'domain_subset':subset,'scaling':scaling})
            rows.append(r)
    return pd.DataFrame(rows),pd.DataFrame(labels),scalings

def summarize(labels,features_all,subset_rows,subset_labels):
    stability=[]
    for method,g in labels.groupby('method_id'):
        full=g[g.heldout_building.eq('ALL')&g.known]
        for b,h in g[~g.heldout_building.eq('ALL')].groupby('heldout_building'):
            pair=full.merge(h[h.known],on='worker_id',suffixes=('_full','_lobo'))
            for level in ('coarse_class','fine_class'):
                stability.append({'method_id':method,'heldout_building':b,'level':level,'common_supported_workers':len(pair),'full_supported_workers':len(full),'lobo_supported_workers':int(h.known.sum()),
                                  'ARI_full_vs_lobo':adjusted_rand_score(pair[level+'_full'],pair[level+'_lobo']) if len(pair)>1 else np.nan,
                                  'same_named_fraction':(pair[level+'_full']==pair[level+'_lobo']).mean() if len(pair) else np.nan,
                                  'interpretation':'sensitivity_to_omitting_one_building; not_independent_external_validation'})
    class_rows=[]
    full=labels[labels.heldout_building.eq('ALL')&labels.known].merge(features_all[features_all.heldout_building.eq('ALL')],on=['worker_id','condition','heldout_building','origin'],suffixes=('','_feature'))
    feature_cols=list(dict.fromkeys(sum(DOMAINS.values(),[])))+['q_absolute_mean','q_absolute_p10','q_relative_sd','source_time_median_seconds','scope_out_raw_rate','semi_edit_raw_rate','semi_error_nonedit_raw_rate']
    for (method,condition),g in full.groupby(['method_id','condition']):
        for level in ('coarse_class','fine_class'):
            for c,h in g.groupby(level):
                r={'method_id':method,'condition':condition,'level':level,'class_id':c,'members_n':len(h),'members':'|'.join(sorted(h.worker_id)),'origin_counts':json.dumps(h.origin.value_counts().to_dict()),'parent':c.split('.')[0]}
                for col in feature_cols:r[col+'_mean']=h[col].mean();r[col+'_median']=h[col].median()
                for domain in DOMAIN_ORDER:r[domain+'_support_n']=int(h[domain+'_supported'].sum())
                class_rows.append(r)
    sub_st=[]
    for (condition,subset),g in subset_labels.groupby(['condition','domain_subset']):
        full=g[g.heldout_building.eq('ALL')]
        for b,h in g[~g.heldout_building.eq('ALL')].groupby('heldout_building'):
            p=full.merge(h,on='worker_id',suffixes=('_full','_lobo'))
            sub_st.append({'condition':condition,'domain_subset':subset,'heldout_building':b,'common_workers':len(p),'ARI':adjusted_rand_score(p.class_id_full,p.class_id_lobo) if len(p)>1 else np.nan})
    return pd.DataFrame(stability),pd.DataFrame(class_rows),pd.DataFrame(sub_st)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reuse-features',action='store_true');ap.add_argument('--skip-subsets',action='store_true');args=ap.parse_args()
    start=time.time();HERE.mkdir(parents=True,exist_ok=True)
    if args.reuse_features:
        features_all=pd.read_csv(HERE/'continuous_features_lobo.csv.gz');fit_metadata=json.loads((HERE/'FEATURE_FITS.json').read_text())
    else:
        d,e,native,fn=load();buildings=sorted(d.building_id.unique());frames=[];fit_metadata=[]
        for heldout in ['ALL']+buildings:
            for condition in ('manual','semi'):
                f,meta=features(d,e,native,fn,heldout,condition);frames.append(f);fit_metadata.append(meta)
            print('features',heldout,'elapsed',round(time.time()-start,1),flush=True)
        features_all=pd.concat(frames,ignore_index=True);features_all.to_csv(HERE/'continuous_features_lobo.csv.gz',index=False,float_format='%.12g')
        js(HERE/'FEATURE_FITS.json',fit_metadata)
    labels=[];fits=[]
    for method in METHODS:
        for heldout,f in features_all[features_all.condition.eq(method['condition'])].groupby('heldout_building',sort=False):
            ll,meta=classify(f.reset_index(drop=True),method);labels.append(ll);meta['heldout_building']=heldout;fits.append(meta)
    labels=pd.concat(labels,ignore_index=True);labels.to_csv(HERE/'candidate_labels.csv',index=False)
    labels[labels.heldout_building.eq('ALL')].to_csv(HERE/'labels_full.csv',index=False)
    labels[~labels.heldout_building.eq('ALL')].to_csv(HERE/'labels_lobo.csv.gz',index=False)
    js(HERE/'CLASSIFICATION_FITS.json',fits)
    js(HERE/'FREEZE.json',{'source_main':'51b519f943b2dd3a4fb2f0198133ac5dd17209ab','frozen_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'methods':METHODS,'domains':DOMAINS,
        'label_sha256':sha(HERE/'candidate_labels.csv'),'continuous_features_sha256':sha(HERE/'continuous_features_lobo.csv.gz'),'input_sha256':{str(p.relative_to(REPO)):sha(p) for p in [SOURCE,INDEX,UPSTREAM]},
        'frozen_before_team_outcomes':True,'selection':'Prespecified opportunity and interpretation criteria; no target fusion outcome. Hierarchical child split requires parent >=8 and both children >=4.',
        'missing':'No imputation; domains require every declared feature finite. Failure produces unknown and explicit missing_reason.',
        'training_scope':'Own-condition ordinary non-OOS. Q retains ordinary_primary quality eligibility. T retains pool/difficulty eligibility. Behavior may include held-quality observations and grants no eligibility.',
        'Semi_domain':'Editing and opportunity-conditional nonediting; no final Semi Q inside Semi domain. Exact v1 and reported new tiers are not pooled. Main methods requiring Semi use new only.',
        'scope_domain':'Own-condition, image/condition/source task-adjusted response propensity; not adjudicated correctness.',
        'Q_domain':'Task FE level and lower-tail gap within-task residuals; hierarchical Q parent uses level only.',
        'weights':'Ward uses robust clipped IQR-scaled features, equal mean squared distance per domain. Hierarchy weights are stage-specific; Q parent then equal refinement domains.',
        'validation_status':'22-building-out refits on previously explored inventory, not fresh blind test. All-data final labels never used for target performance.'})
    print('FROZEN',labels.groupby(['method_id','heldout_building']).known.sum().groupby(level=0).agg(['min','max']).to_dict(),flush=True)
    if not args.skip_subsets:
        sr,sl,scalings=subset_exploration(features_all);sr.to_csv(HERE/'domain_subset_26_fold_coverage.csv',index=False);sl.to_csv(HERE/'domain_subset_screen_labels.csv.gz',index=False)
        js(HERE/'DOMAIN_SUBSET_SCALING.json',scalings)
        stability,classes,ss=summarize(labels,features_all,sr,sl)
        stability.to_csv(HERE/'candidate_lobo_stability.csv',index=False);classes.to_csv(HERE/'class_members_and_features.csv',index=False);ss.to_csv(HERE/'domain_subset_stability.csv',index=False)
        full=sr[sr.heldout_building.eq('ALL')].copy();agg=ss.groupby(['condition','domain_subset']).ARI.agg(['mean','median','min']).rename(columns=lambda x:'lobo_ARI_'+x).reset_index()
        full=full.merge(agg,on=['condition','domain_subset'],how='left');full.to_csv(HERE/'domain_subset_26_coverage.csv',index=False)
    print('DONE seconds',round(time.time()-start,2),flush=True)

if __name__=='__main__':main()
