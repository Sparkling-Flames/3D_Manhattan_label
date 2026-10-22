"""Class composition and member response across directly adopted room views.

Inputs: frozen design, current LOBO labels, native endpoint scalars.
No classification refit, fusion or scoring. Descriptive moment decomposition and
single-source transfer diagnostics stay explicitly separate. Source-only local
ridge selection never reads target endpoints; it is a comparator, not a new
personnel classification.
"""
from __future__ import annotations
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[k]='1'
import argparse, gzip, json, hashlib, math
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

SCHEMES={'structure':'structure_vector','joint':'joint_vector'}
METRICS=['B8L2','D10','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n',
 'ref_node_recall_9','ref_edge_recall_9','S_bottom_deg','dir','Hmean','omission','extension',
 'log_recorded_time','failure']
PROFILE=['q_history','turn_history','t_history','short_history','q_downside']
META=['panel_id','pair_key','building','groups','image_a','image_b','ordinary_comparable',
 'relation_tier','scope_comparable','layer_a','layer_b','difficulty_a','difficulty_b',
 'method','selected_family','class_lo','class_hi','n','k_selected','replicate',
 'known_common_n','mid_n','is_primary_budget']


def annotate_budget(panels):
    """Registered half-pool budget, clipped by the finite-panel design rules."""
    p=panels.copy()
    p['mid_n']=np.minimum(np.maximum(p.known_common_n//2,np.maximum(3,p.k_selected)),p.known_common_n-p.k_selected).astype(int)
    p['is_primary_budget']=(p.replicate==0)&(p.n==p.mid_n)
    return p


def budget_rows(frame):
    """Keep principal, all-n sensitivity, and new-member replicates separate."""
    return pd.concat([
        frame[frame.is_primary_budget.astype(bool)].assign(budget='mid_n_rep0'),
        frame[frame.replicate==0].assign(budget='all_n_rep0'),
        frame[frame.replicate==1].assign(budget='replicate1_mid'),
    ],ignore_index=True)


def analysis_layer(row):
    if bool(row['ordinary_comparable']):return 'ordinary_comparable'
    if 'doorway' in str(row.get('layer_a','')) or 'doorway' in str(row.get('layer_b','')):return 'doorway_involved'
    if not bool(row['scope_comparable']):return 'ordinary_scope_different'
    return 'ordinary_other_adoption_state'


def write_csv(path, df):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    raw=df.to_csv(index=False).encode('utf-8-sig')
    if path.suffix=='.gz':raw=gzip.compress(raw,mtime=0)
    tmp=path.with_name(path.name+'.tmp');tmp.write_bytes(raw);os.replace(tmp,path)


def read_endpoints(native, partial=False):
    path=native/'ENDPOINT_SCALARS.csv.gz'
    if path.exists() and not partial:
        z=pd.read_csv(path,low_memory=False)
    else:
        rows=[]
        for f in sorted((native/'pools').glob('*.json.gz')):
            for r in json.load(gzip.open(f,'rt'))['teams']:
                rows.append({k:v for k,v in r.items() if not isinstance(v,(list,dict))})
        z=pd.DataFrame(rows)
    if len(z)==0:return z
    assert not z.team_key.duplicated().any()
    t=pd.to_numeric(z['recorded_time_total_seconds'],errors='coerce')
    z['log_recorded_time']=np.where(t>0,np.log(t),np.nan)
    z['failure']=1-z['complete_evaluable'].astype(float)
    return z


def corr(x,y):
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float)
    if len(x)<2 or np.std(x)<1e-10 or np.std(y)<1e-10:return np.nan
    return float(np.corrcoef(x,y)[0,1])


def moments(g,metric,scheme):
    a=g[metric+'_a'].to_numpy(dtype=float);b=g[metric+'_b'].to_numpy(dtype=float)
    good=np.isfinite(a)&np.isfinite(b); z=g.loc[good].copy();a=a[good];b=b[good]
    base={'n_requested':len(g),'n_joint_finite':len(z),'metric':metric,'scheme':scheme}
    if len(z)<2:return base
    vcol=SCHEMES[scheme];codes=pd.factorize(z[vcol],sort=True)[0];counts=np.bincount(codes)
    am=np.bincount(codes,weights=a)/counts;bm=np.bincount(codes,weights=b)/counts
    ma=am[codes];mb=bm[codes];ra=a-ma;rb=b-mb
    vat=np.var(a);vbt=np.var(b);vab=np.var(ma);vbb=np.var(mb);vaw=np.mean(ra**2);vbw=np.mean(rb**2)
    covt=np.mean((a-a.mean())*(b-b.mean()));covb=np.mean((ma-a.mean())*(mb-b.mean()));covw=np.mean(ra*rb)
    assert abs(vat-vab-vaw)<1e-7*max(1,vat) and abs(covt-covb-covw)<1e-7*max(1,abs(covt))
    base.update(n_compositions=len(counts),n_member_residual_df=len(a)-len(counts),
      n_compositions_with_replicates=int((counts>=2).sum()),n_singleton_teams=int((counts[codes]==1).sum()),
      mean_a=a.mean(),mean_b=b.mean(),total_var_a=vat,total_var_b=vbt,
      between_var_a=vab,between_var_b=vbb,within_var_a=vaw,within_var_b=vbw,
      between_fraction_a=vab/vat if vat>1e-12 else np.nan,
      between_fraction_b=vbb/vbt if vbt>1e-12 else np.nan,
      total_cov=covt,between_cov=covb,within_cov=covw,
      total_rho=corr(a,b),composition_rho=corr(ma,mb),member_residual_rho=corr(ra,rb),
      both_total_invariant=bool(vat<1e-12 and vbt<1e-12),
      both_within_invariant=bool(vaw<1e-12 and vbw<1e-12),
      composition_range_a=float(np.ptp(am)),composition_range_b=float(np.ptp(bm)),
      both_composition_invariant=bool(vab<1e-12 and vbb<1e-12),
      both_composition_Q_range_ge2=bool(np.ptp(am)>=2 and np.ptp(bm)>=2) if metric in ['B8L2','D10'] else np.nan,
      composition_mean_abs_gap=float(np.mean(np.abs(ma-mb))),
      exact_team_mean_abs_gap=float(np.mean(np.abs(a-b))),
      member_residual_abs_change=float(np.mean(np.abs(ra-rb))),
      within_sd_a=math.sqrt(vaw),within_sd_b=math.sqrt(vbw))
    return base


def hierarchy(df,keys,value_cols):
    """Panel -> direct pair -> declared group -> building equally.

    A direct pair with multiple declarations appears in each adopted declaration;
    this is an explicit descriptive weighting, not independent-room inference.
    """
    if not len(df):return pd.DataFrame(),pd.DataFrame(),pd.DataFrame(),pd.DataFrame()
    keys=list(keys);keep=keys+['pair_key','building','groups']
    pair=df.groupby(keep,dropna=False)[value_cols].mean().reset_index()
    counts=df.groupby(keep,dropna=False).size().reset_index(name='n_panel_rows')
    pair=pair.merge(counts,on=keep,how='left')
    pair['group_id']=pair.groups.fillna('').str.split('|');e=pair.explode('group_id')
    group=e.groupby(keys+['building','group_id'],dropna=False)[value_cols].mean().reset_index()
    group=group.merge(e.groupby(keys+['building','group_id'],dropna=False).agg(n_direct_pairs=('pair_key','nunique')).reset_index(),on=keys+['building','group_id'])
    building=group.groupby(keys+['building'],dropna=False)[value_cols].mean().reset_index()
    building=building.merge(group.groupby(keys+['building'],dropna=False).agg(n_declared_groups=('group_id','nunique')).reset_index(),on=keys+['building'])
    summary=building.groupby(keys,dropna=False)[value_cols].mean().reset_index()
    support=e.groupby(keys,dropna=False).agg(direct_pairs=('pair_key','nunique'),buildings=('building','nunique'),declared_groups=('group_id','nunique')).reset_index()
    summary=summary.merge(support,on=keys,how='left')
    return pair,group,building,summary


def derive_pooled(df):
    if not len(df):return df
    d=df.copy()
    d['pooled_between_fraction']=(d.between_var_a+d.between_var_b)/(d.total_var_a+d.total_var_b).where((d.total_var_a+d.total_var_b)>1e-12)
    for name,va,vb,cv in [('total','total_var_a','total_var_b','total_cov'),('composition','between_var_a','between_var_b','between_cov'),('member_residual','within_var_a','within_var_b','within_cov')]:
        den=np.sqrt(d[va]*d[vb]);d['pooled_'+name+'_rho']=d[cv]/den.where(den>1e-12)
    return d


def numeric_indicators(frame):
    """Nullable indicator columns stay numeric in hierarchical summaries."""
    z=frame.copy()
    for c in ['both_total_invariant','both_within_invariant','both_composition_invariant','both_composition_Q_range_ge2']:
        if c in z:
            z[c]=z[c].map(lambda x: np.nan if pd.isna(x) else (float(x) if isinstance(x,(bool,int,float,np.number)) else {'True':1.,'False':0.}.get(str(x),np.nan)))
    return z


def label_path(repo=None,override=None):
    if override is not None:return Path(override)
    if repo is None:raise ValueError('Provide --labels (portable required-field index) or --repo (frozen repository)')
    return Path(repo)/'research/workers/personnel_mixture_comparison_20261022/inputs/four_main/ALL_METHOD_LABELS_LOBO.csv.gz'


def member_features(links,panels,repo=None,labels_path=None):
    labels=pd.read_csv(label_path(repo,labels_path))
    labels=labels[(labels.condition=='manual')&(labels.method=='V3_JOINT_QT')].set_index(['heldout_building','worker_id'])
    vectors={idx:np.asarray(val,dtype=float) for idx,val in zip(labels.index,labels[PROFILE].to_numpy())}
    building=panels.set_index('panel_id').building.to_dict(); cache={};rows=[]
    for pid,ms in links[['panel_id','member_set_key']].itertuples(index=False,name=None):
        key=(building[pid],ms)
        if key not in cache:
            ws=ms.split('|');v=np.stack([vectors.get((key[0],w),np.full(len(PROFILE),np.nan)) for w in ws])
            good=np.isfinite(v).all();row={'profile_complete':bool(good)}
            means=np.mean(v,axis=0)
            for j,col in enumerate(PROFILE):
                row['history_mean_'+col]=means[j]
            cache[key]=row
        rows.append(cache[key])
    return pd.concat([links.reset_index(drop=True),pd.DataFrame(rows)],axis=1)


def source_continuous_ridge(X,y):
    """Linear/quadratic continuous comparator selected by SOURCE-only LOOCV.

    Five pre-existing outside-building continuous histories. Standardization and
    candidate losses use only source values. No target labels/outcomes are fit.
    """
    X=np.asarray(X,dtype=float);y=np.asarray(y,dtype=float)
    sd=np.std(X,axis=0);z=(X-X.mean(axis=0))/np.where(sd>1e-9,sd,1)
    z=z[:,sd>1e-9]
    if z.shape[1]==0:return np.repeat(y.mean(),len(y)),dict(degree=0,alpha=np.nan,source_loo_mse=np.var(y),effective_df=1.)
    best=None
    for degree in [1,2]:
        f=z
        if degree==2:
            f=np.column_stack([z]+[z[:,i]*z[:,j] for i in range(z.shape[1]) for j in range(i,z.shape[1])])
        f=f-f.mean(axis=0);s=f.std(axis=0);f=f[:,s>1e-9]/s[s>1e-9]
        u,s,v=np.linalg.svd(f,full_matrices=False);uy=u.T@(y-y.mean())
        for alpha in [.1,1.,10.,100.]:
            sh=s*s/(s*s+alpha);pred=y.mean()+u@(sh*uy);h=1/len(y)+(u*u)@sh
            loo=(y-pred)/np.clip(1-h,1e-6,None);loss=float(np.mean(loo*loo))
            candidate=(loss,degree,alpha,pred,float(1+sh.sum()))
            if best is None or candidate[:3]<best[:3]:best=candidate
    return best[3],dict(degree=best[1],alpha=best[2],source_loo_mse=best[0],effective_df=best[4])


def source_group_mean(y,labels):
    code=pd.factorize(labels,sort=True)[0];count=np.bincount(code);mu=np.bincount(code,weights=y)/count
    return mu[code],len(count)


def transfer_rows(g,metric):
    fields=['history_mean_'+x for x in PROFILE]
    allowed=g.joint_all_known.astype(bool)&g.profile_complete.astype(bool)
    out=[]
    for direction,sv,tv in [('a_to_b','a','b'),('b_to_a','b','a')]:
        # Every predictor is fitted on known SOURCE endpoints. Target failures
        # never determine the source bank or a class mean.
        z=g.loc[allowed & np.isfinite(g[metric+'_'+sv])].copy()
        if len(z)<6:continue
        source=z[metric+'_'+sv].to_numpy(float);target=z[metric+'_'+tv].to_numpy(float);X=z[fields].to_numpy(float)
        cp,info=source_continuous_ridge(X,source)
        sp,ns=source_group_mean(source,z.structure_vector);jp,nj=source_group_mean(source,z.joint_vector)
        models={'source_panel_mean':np.repeat(source.mean(),len(z)), 'source_exact_team':source,
            'source_structure_composition_mean':sp,'source_joint_composition_mean':jp,
            'source_continuous_history_response':cp}
        evaluate=np.isfinite(target)
        if evaluate.sum()<6:continue
        target=target[evaluate]
        for model,full_pred in models.items():
            pred=full_pred[evaluate];error=pred-target;cen=(pred-pred.mean())-(target-target.mean())
            out.append(dict(metric=metric,direction=direction,model=model,n_joint_teams=len(target),source_bank_teams=len(z),
                target_unscored_in_source_bank=int((~evaluate).sum()),
                structure_cells=ns,joint_cells=nj,member_replication_supported=bool(len(z)-max(ns,nj)>=3),
                mae=float(np.mean(abs(error))),rmse=float(np.sqrt(np.mean(error**2))),
                bias=float(np.mean(error)),contrast_mae=float(np.mean(abs(cen))),contrast_mse=float(np.mean(cen**2)),
                target_variance=float(np.var(target)),rho=corr(pred,target),
                source_variance=float(np.var(source)),source_target_mean_gap=float(source.mean()-target.mean()),
                continuous_degree=info['degree'],continuous_alpha=info['alpha'],
                continuous_source_loo_mse=info['source_loo_mse'],continuous_effective_df=info['effective_df']))
    return out


def cross_member_cells(merged,panels):
    """Replicate 0/1, identical full class vector, remove identical team sets."""
    cells=[];curves=[]
    pindex=panels.set_index('panel_id');by_panel={pid:g for pid,g in merged.groupby('panel_id',sort=False)}
    key=['pair_key','method','class_lo','class_hi','n']
    for _,ps in panels.groupby(key,dropna=False,sort=False):
        if set(ps.replicate)!=set([0,1]):continue
        pa=ps[ps.replicate==0].iloc[0];pb=ps[ps.replicate==1].iloc[0]
        if pa.panel_id not in by_panel or pb.panel_id not in by_panel:continue
        ga=by_panel[pa.panel_id];gb=by_panel[pb.panel_id]
        for scheme,vc in SCHEMES.items():
            if scheme=='joint':ga1=ga[ga.joint_all_known.astype(bool)];gb1=gb[gb.joint_all_known.astype(bool)]
            else:ga1,gb1=ga,gb
            shared_vectors=set(ga1[vc])&set(gb1[vc]);base={c:pa[c] for c in META if c not in ['panel_id','replicate']}
            local=[]
            for vector in sorted(shared_vectors):
                x=ga1[ga1[vc]==vector];y=gb1[gb1[vc]==vector]
                overlap=set(x.member_set_key)&set(y.member_set_key)
                x=x[~x.member_set_key.isin(overlap)];y=y[~y.member_set_key.isin(overlap)]
                if len(x)==0 or len(y)==0:continue
                fx=defaultdict(float);fy=defaultdict(float)
                for ms in x.member_set_key:
                    for w in ms.split('|'):fx[w]+=1/len(x)
                for ms in y.member_set_key:
                    for w in ms.split('|'):fy[w]+=1/len(y)
                changed=pa.n-sum(fx[w]*fy[w] for w in fx)
                for metric in METRICS:
                    r=base|dict(scheme=scheme,metric=metric,panel_id_0=pa.panel_id,panel_id_1=pb.panel_id,full_class_vector=vector,
                        removed_identical_member_sets=len(overlap),member_sets_0=len(x),member_sets_1=len(y),mean_replaced_workers=changed)
                    for view in ['a','b']:
                        for rep,z in [(0,x),(1,y)]:
                            v=z[metric+'_'+view].dropna();r[f'mean_{view}_{rep}']=v.mean();r[f'sd_{view}_{rep}']=v.std(ddof=0);r[f'n_{view}_{rep}']=len(v)
                    cells.append(r);local.append(r)
            ld=pd.DataFrame(local)
            if ld.empty:continue
            for metric,g in ld.groupby('metric',sort=False):
                for source,target,identity in [('a_0','a_1','same_view_different_members'),('b_0','b_1','same_view_different_members'),('a_0','b_1','cross_view_different_members'),('b_0','a_1','cross_view_different_members')]:
                    x=g['mean_'+source].to_numpy(float);y=g['mean_'+target].to_numpy(float);ok=np.isfinite(x)&np.isfinite(y);x=x[ok];y=y[ok]
                    if len(x)<2:continue
                    curves.append(base|dict(scheme=scheme,metric=metric,comparison=identity,source=source,target=target,n_common_compositions=len(x),
                        source_range=float(np.ptp(x)),target_range=float(np.ptp(y)),composition_curve_rho=corr(x,y),
                        centered_mae=float(np.mean(abs((x-x.mean())-(y-y.mean())))),
                        absolute_mae=float(np.mean(abs(x-y))),
                        source_mean_absolute_mae=float(np.mean(abs(x.mean()-y))),
                        source_mean_centered_mae=float(np.mean(abs(y-y.mean()))),
                        both_curves_constant=bool(np.ptp(x)<1e-9 and np.ptp(y)<1e-9),
                        source_Q_active=bool(np.ptp(x)>=2) if metric in ['B8L2','D10'] else np.nan,
                        target_Q_active=bool(np.ptp(y)>=2) if metric in ['B8L2','D10'] else np.nan))
    return pd.DataFrame(cells),pd.DataFrame(curves)


def composition_direction_results(mom,out):
    """Descriptive two-end filtering and source-only gating kept distinct.

    Both-end >=2 is a retrospective mechanism subset. Source-only >=2 is an
    information-feasible gate, but still evaluates the already registered
    finite bank; it is not an externally validated selection policy.
    """
    base=mom[(mom.metric.isin(['B8L2','D10']))&(mom.n_joint_finite>=2)].copy()
    rows=[]
    for r in base.to_dict('records'):
        active_a=r['composition_range_a']>=2;active_b=r['composition_range_b']>=2
        rho=r.get('composition_rho',np.nan)
        flags=dict(both_near_zero=float(not active_a and not active_b),
          only_one_active=float(active_a!=active_b),both_active=float(active_a and active_b),
          positive_rho=float(np.isfinite(rho) and rho>0),negative_rho=float(np.isfinite(rho) and rho<0),
          rho_ge_point5=float(np.isfinite(rho) and rho>=.5),rho_le_minus_point5=float(np.isfinite(rho) and rho<=-.5),
          rho_undefined=float(not np.isfinite(rho)),zero_rho=float(np.isfinite(rho) and rho==0))
        rows.append(r|flags|dict(eligibility_rule='all_panels',direction='undirected',
            source_range=np.nan,target_range=np.nan,target_near_zero=np.nan))
        if active_a and active_b:
            rows.append(r|flags|dict(eligibility_rule='both_ends_range_ge2_descriptive',direction='undirected',
                source_range=np.nan,target_range=np.nan,target_near_zero=0.))
        for sv,tv,source_active,target_active in [('a','b',active_a,active_b),('b','a',active_b,active_a)]:
            if not source_active:continue
            rows.append(r|flags|dict(eligibility_rule='source_only_range_ge2',direction=sv+'_to_'+tv,
                source_range=r['composition_range_'+sv],target_range=r['composition_range_'+tv],
                target_near_zero=float(not target_active),
                target_active_positive=float(target_active and np.isfinite(rho) and rho>0),
                target_active_negative=float(target_active and np.isfinite(rho) and rho<0)))
    d=pd.DataFrame(rows)
    if d.empty:return
    write_csv(out/'COMPOSITION_DIRECTION_PANEL.csv.gz',d)
    b=budget_rows(d)
    keys=['budget','analysis_layer','support_domain','scheme','metric','eligibility_rule']
    values=['both_near_zero','only_one_active','both_active','positive_rho','negative_rho','rho_ge_point5','rho_le_minus_point5','rho_undefined','zero_rho',
      'source_range','target_range','target_near_zero','target_active_positive','target_active_negative','composition_rho']
    for name,z in zip(['PAIR','GROUP','BUILDING','SUMMARY'],hierarchy(b,keys,values)):
        write_csv(out/('COMPOSITION_DIRECTION_'+name+'.csv'),z)
    count=[]
    for key,z in b.groupby(keys,dropna=False):
        row=dict(zip(keys,key));row.update(panel_direction_rows=len(z),unique_panels=z.panel_id.nunique(),
          direct_pairs=z.pair_key.nunique(),buildings=z.building.nunique(),
          declared_groups=len(set('|'.join(z.groups).split('|'))),
          raw_positive_rows=int(z.positive_rho.sum()),raw_negative_rows=int(z.negative_rho.sum()),
          raw_target_near_zero_rows=int(z.target_near_zero.sum()),
          raw_both_near_zero_rows=int(z.both_near_zero.sum()),raw_only_one_active_rows=int(z.only_one_active.sum()))
        count.append(row)
    write_csv(out/'COMPOSITION_DIRECTION_COUNTS.csv',pd.DataFrame(count))


def analyze(args):
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    immutable_inputs=[Path(__file__),args.design/'PANELS.csv',args.design/'PANEL_TEAM_LINKS.csv.gz',label_path(args.repo,args.labels)]
    signature={str(p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in immutable_inputs}
    panels=annotate_budget(pd.read_csv(args.design/'PANELS.csv'));links=pd.read_csv(args.design/'PANEL_TEAM_LINKS.csv.gz')
    links=member_features(links,panels,args.repo,args.labels)
    print('Joined continuous history features',len(links),flush=True)
    endpoints=read_endpoints(args.native,args.partial)
    if endpoints.empty:raise RuntimeError('No completed native endpoints available')
    want=['team_key']+METRICS
    for c in want:
        if c not in endpoints:endpoints[c]=np.nan
    g=links.merge(endpoints[want].add_suffix('_a'),left_on='team_key_a',right_on='team_key_a',how='left').merge(endpoints[want].add_suffix('_b'),left_on='team_key_b',right_on='team_key_b',how='left')
    # Partial checkpoints: only fully available panels enter; finite failures stay.
    present=set(endpoints.team_key)
    panel_ready=links.assign(present=links.team_key_a.isin(present)&links.team_key_b.isin(present)).groupby('panel_id').present.all()
    ready=set(panel_ready[panel_ready].index);g=g[g.panel_id.isin(ready)].copy();panels=panels[panels.panel_id.isin(ready)].copy()
    print('Completed native panels ready',len(ready),'endpoint rows',len(endpoints),flush=True)
    pm=panels.set_index('panel_id',drop=False);mom=[];pred=[];support=[];cached_panels=set()
    if args.reuse_existing and (out/'ANALYSIS_RECEIPT.json').exists():
        previous=json.loads((out/'ANALYSIS_RECEIPT.json').read_text())
        if previous.get('immutable_input_signature')!=signature:raise RuntimeError('Existing response cache has different code/design/labels; use another output or omit --reuse-existing')
        old_support=pd.read_csv(out/'PANEL_COMMON_SUPPORT.csv',low_memory=False)
        cached_panels=set(old_support.panel_id)&ready
        old_mom=pd.read_csv(out/'PANEL_DECOMPOSITION.csv.gz',low_memory=False)
        old_pred=pd.read_csv(out/'SOURCE_TRANSFER_PANEL_RESULTS.csv.gz',low_memory=False)
        mom=old_mom[old_mom.panel_id.isin(cached_panels)].to_dict('records')
        pred=old_pred[old_pred.panel_id.isin(cached_panels)].to_dict('records')
        support=old_support[old_support.panel_id.isin(cached_panels)].to_dict('records')
        print('Reusing completed response panels',len(cached_panels),'new',len(ready-cached_panels),flush=True)
    for pid,z in g.groupby('panel_id',sort=False):
        if pid in cached_panels:continue
        meta={c:pm.loc[pid,c] for c in META}
        support.append(meta|dict(n_finite_member_sets=len(z),joint_known_member_sets=int(z.joint_all_known.sum()),
           structure_compositions=z.structure_vector.nunique(),joint_compositions=z[z.joint_all_known].joint_vector.nunique(),
           profile_complete_member_sets=int(z.profile_complete.sum())))
        for domain,zz in [('structure_all_known',z),('both_classifications_known',z[z.joint_all_known.astype(bool)])]:
            if len(zz)<2:continue
            schemes=['structure'] if domain=='structure_all_known' else ['structure','joint']
            for metric in METRICS:
                for scheme in schemes:
                    mom.append(meta|{'support_domain':domain}|moments(zz,metric,scheme))
        for metric in ['B8L2','D10','fusion_turn_n','S_bottom_deg','dir','log_recorded_time']:
            pred.extend([meta|r for r in transfer_rows(z,metric)])
    mom=numeric_indicators(pd.DataFrame(mom));pred=pd.DataFrame(pred);support=pd.DataFrame(support)
    for d in [mom,pred,support]:
        if len(d):d['analysis_layer']=d.apply(analysis_layer,axis=1)
    write_csv(out/'PAIRED_TEAM_RESPONSES.csv.gz',g)
    write_csv(out/'PAIRED_TEAM_RESPONSES_PRIMARY.csv.gz',g[g.panel_id.isin(panels.loc[panels.is_primary_budget,'panel_id'])])
    write_csv(out/'PANEL_COMMON_SUPPORT.csv',support)
    write_csv(out/'PANEL_DECOMPOSITION.csv.gz',mom)
    write_csv(out/'PANEL_DECOMPOSITION_PRIMARY.csv.gz',mom[mom.is_primary_budget.astype(bool)])
    write_csv(out/'SOURCE_TRANSFER_PANEL_RESULTS.csv.gz',pred)
    numeric=[c for c in mom if pd.api.types.is_numeric_dtype(mom[c]) and c not in ['n','replicate','k_selected','ordinary_comparable','scope_comparable','known_common_n','mid_n','is_primary_budget']]
    keys=['budget','analysis_layer','support_domain','scheme','metric']
    for name,z in zip(['PAIR','GROUP','BUILDING','SUMMARY'],hierarchy(budget_rows(mom[mom.n_joint_finite>=2]),keys,numeric)):
        write_csv(out/('DECOMPOSITION_'+name+'.csv'),derive_pooled(z))
    for name,z in zip(['PAIR_N','GROUP_N','BUILDING_N','SUMMARY_N'],hierarchy(mom[mom.n_joint_finite>=2],['n','replicate','analysis_layer','support_domain','scheme','metric'],numeric)):
        write_csv(out/('DECOMPOSITION_'+name+'.csv'),derive_pooled(z))
    family=hierarchy(budget_rows(mom[mom.n_joint_finite>=2]),keys+['selected_family'],numeric)[-1]
    write_csv(out/'DECOMPOSITION_FAMILY_SUMMARY.csv',derive_pooled(family))
    composition_direction_results(mom,out)
    if len(pred):
        fields=['mae','rmse','bias','contrast_mae','contrast_mse','target_variance','rho','source_variance','source_target_mean_gap','n_joint_teams','source_bank_teams','target_unscored_in_source_bank','structure_cells','joint_cells','member_replication_supported']
        for name,z in zip(['PAIR','GROUP','BUILDING','SUMMARY'],hierarchy(budget_rows(pred),['budget','analysis_layer','metric','model'],fields)):
            write_csv(out/('SOURCE_TRANSFER_'+name+'.csv'),z)
    cells,curves=cross_member_cells(g,panels)
    if len(cells):write_csv(out/'REPLICATE_MATCHED_COMPOSITION_CELLS.csv.gz',cells)
    if len(curves):
        curves['analysis_layer']=curves.apply(analysis_layer,axis=1)
        write_csv(out/'REPLICATE_COMPOSITION_CURVES.csv',curves)
        vals=['n_common_compositions','source_range','target_range','composition_curve_rho','centered_mae','absolute_mae','source_mean_absolute_mae','source_mean_centered_mae','both_curves_constant','source_Q_active','target_Q_active']
        for name,z in zip(['PAIR','GROUP','BUILDING','SUMMARY'],hierarchy(curves,['analysis_layer','scheme','metric','comparison'],vals)):
            write_csv(out/('REPLICATE_'+name+'.csv'),z)
    receipt={'source_commit':'72a44e80c344975962e1071bd54d894dd86bb4b4','partial':args.partial,'design_panels':len(panel_ready),'complete_panels':len(ready),'primary_budget':'mid_n_rep0: floor(common known N/2), clipped by [max(3,k),N-k], replicate0 only','primary_panels':int(panels.is_primary_budget.sum()),'endpoint_rows':len(endpoints),'paired_member_sets':len(g),'decomposition_rows':len(mom),'source_transfer_rows':len(pred),'no_classification_refit':True,'new_fusion':0,'new_scoring':0,'immutable_input_signature':signature,'hierarchy':'finite panel -> direct pair -> declared group -> building equal','source_prediction_conditions':'one source view with GT and all saved source team endpoints; target only evaluation; labels and profile histories exclude target building'}
    (out/'ANALYSIS_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path);p.add_argument('--labels',type=Path);p.add_argument('--design',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--partial',action='store_true');p.add_argument('--reuse-existing',action='store_true');a=p.parse_args();analyze(a)
