"""Descriptive, exact finite-team conditional comparison; no fusion or new scores.

Every analysis row retains its exact saved panel/team key. Nested historical-Q
models are sensitivity analyses, not causal attribution or prediction scores.
"""
from pathlib import Path
import argparse, gzip, hashlib, json, os
import numpy as np
import pandas as pd

METHODS = ['DSTRUCT_K3','TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K4',
           'OPPSTRUCT_K3','OPPJOINT_K3','OPPJOINT_K4','RFUSE_GEOM_K2',
           'V3_JOINT_QT_COARSE','V21_DSTRUCT_RAW3_K3','V21_DSTRUCT_LEVEL_K3']
METRICS = ['B8L2','D10','fusion_turn_n','fusion_short_turn_edges','geometry_area_h2',
           'height_mean_h','S_bottom_deg','failure','record_time_single_source']
MODELS = ['exact_Q_quota','quota_continuous_Q','quota_continuous_QT']

def save(df,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=df.to_csv(index=False).encode('utf-8-sig')
    if path.suffix=='.gz':data=gzip.compress(data,mtime=0)
    tmp=path.with_suffix(path.suffix+'.partial');tmp.write_bytes(data);tmp.replace(path)

def encode(counts):
    # Full n <= 35. Base 64 makes the count-vector code injective.
    return counts.astype(np.int64) @ (64**np.arange(counts.shape[1],dtype=np.int64))

def groups_from(q,m):
    return np.unique(np.column_stack([q,m]),axis=0,return_inverse=True)[1]

def demean(y,groups):
    counts=np.bincount(groups)
    if y.ndim==1:
        means=np.bincount(groups,weights=y)/counts
    else:
        means=np.vstack([np.bincount(groups,weights=y[:,j])/counts for j in range(y.shape[1])]).T
    return y-means[groups],len(counts)

def sse(y,groups,x=None):
    yg,ng=demean(y,groups)
    rank=0
    if x is not None and x.shape[1]:
        xg,_=demean(x,groups)
        u,s,_=np.linalg.svd(xg,full_matrices=False)
        rank=int((s>max(s[0] if len(s) else 0,1)*1e-10).sum())
        if rank:yg=yg-u[:,:rank]@(u[:,:rank].T@yg)
    return float(yg@yg),int(ng+rank)

def hierarchy(df,cols):
    p=df.groupby(['method','metric','model','pool_id','image','building'],dropna=False)[cols].mean().reset_index()
    im=p.groupby(['method','metric','model','image','building'],dropna=False)[cols].mean().reset_index()
    bl=im.groupby(['method','metric','model','building'],dropna=False)[cols].mean().reset_index()
    out=[]
    for weighting,tab in [('image_equal',im),('building_equal',bl)]:
        for keys,g in tab.groupby(['method','metric','model'],sort=False):
            row=dict(zip(['method','metric','model'],keys));row['weighting']=weighting
            vals=g[cols].mean();row.update(vals.to_dict())
            row['candidate_extra_share_total']=vals.increment_variance/vals.total_variance if vals.total_variance>1e-15 else np.nan
            row['candidate_share_baseline_residual']=vals.increment_variance/vals.baseline_residual_variance if vals.baseline_residual_variance>1e-15 else np.nan
            row['baseline_explained_share']=1-vals.baseline_residual_variance/vals.total_variance if vals.total_variance>1e-15 else np.nan
            row['remaining_share_total']=vals.combined_residual_variance/vals.total_variance if vals.total_variance>1e-15 else np.nan
            src=df[(df.method==keys[0])&(df.metric==keys[1])&(df.model==keys[2])]
            mi=im[(im.method==keys[0])&(im.metric==keys[1])&(im.model==keys[2])]
            row.update(panels=src.panel_id.nunique(),pools=src.pool_id.nunique(),images=src.image.nunique(),buildings=src.building.nunique(),valid_team_links=int(src.valid_teams.sum()),
                       nonconstant_images=int(mi.total_variance.gt(1e-15).sum()),images_increment_gt_1pct_total=int((mi.increment_variance>.01*mi.total_variance).sum()))
            out.append(row)
    return pd.DataFrame(out),im,bl

def main(args):
    root=Path(args.repo);w=root/'research/workers/personnel_v21_reselection_20261029'
    core=w/'additional_delivery/packages/03B_core/composition';out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    panels=pd.read_csv(core/'primary_panel_inputs/PANELS_USED.csv')
    panels=panels[panels.condition.eq('manual')&panels.layer.eq('ordinary_manual')&panels.scope.eq('primary')].set_index('panel_id')
    links=pd.read_csv(core/'primary_compact_links/TEAM_LINK_INDEX.csv.gz')
    links=links[links.shared_known&links.panel_id.isin(panels.index)].copy()
    codes=pd.read_csv(core/'primary_compact_links/METHOD_VECTOR_CODES.csv.gz',usecols=['team_link_id','Q_MEDIAN2']+[m for m in METHODS if not m.startswith('V21_')])
    links=links.merge(codes,on='team_link_id',validate='one_to_one')
    teams=pd.read_csv(core/'primary_panel_inputs/PANEL_TEAMS.csv.gz')
    links=links.merge(teams,on=['panel_id','team_key'],validate='one_to_one')
    ecol=['team_key']+[m for m in METRICS if m!='record_time_single_source']+['recorded_time_eligible','recorded_time_total_seconds','time_source_kinds','complete_evaluable']
    endpoints=pd.read_csv(core/'primary_panel_inputs/ENDPOINT_SCALARS.csv.gz',usecols=ecol)
    endpoints['record_time_single_source']=endpoints.recorded_time_total_seconds.where(endpoints.recorded_time_eligible & endpoints.time_source_kinds.eq('user_processed_reported_not_raw_log_replayed'))
    links=links.merge(endpoints,on='team_key',validate='many_to_one')
    labels=pd.read_csv(w/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    new=pd.read_csv(args.new_labels)
    labels=pd.concat([labels,new],ignore_index=True)
    labels=labels[labels.method.isin(METHODS+['Q_MEDIAN2'])&labels.known.astype(str).str.lower().eq('true')&labels.heldout_building.ne('ALL')]
    maps={(m,b):g.set_index('worker_id').class_id.to_dict() for (m,b),g in labels.groupby(['method','heldout_building'])}
    qaxis={(b):g.set_index('worker_id').axis_score.to_dict() for b,g in labels[labels.method.eq('Q_MEDIAN2')].groupby('heldout_building')}
    h=pd.read_csv(args.history).set_index(['heldout_building','worker_id'])
    codebook=pd.read_csv(core/'primary_compact_links/VECTOR_CODEBOOK.csv')
    book={(r.method,int(r.vector_code)):r.class_counts for r in codebook.itertuples()}
    rows=[];assign=[];counts=[];perm_files=[];perm_total=0
    sources=[core/'primary_panel_inputs/PANELS_USED.csv',core/'primary_panel_inputs/PANEL_TEAMS.csv.gz',core/'primary_panel_inputs/ENDPOINT_SCALARS.csv.gz',w/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',Path(args.new_labels),Path(args.history)]
    config=dict(methods=METHODS,metrics=METRICS,models=MODELS,permutations=args.permutations,seed=args.seed,
                scope='ordinary_manual primary',support='common45_known plus new method known, identical teams',
                continuous_Q=['mean official primary-history Q axis','mean target-equal historical Q','mean target-equal historical Q p20','mean square official historical Q','square of team mean official historical Q'],
                continuous_QT_adds=['mean historical log time','mean square historical log time','square team mean log time','team Q mean x team log time mean'],
                no_new_fusion=True,no_new_scoring=True,interpretation='nested in-sample descriptive residual variances; not prediction, causal isolation, or an inferential p value',
                source_paths=[str(s) for s in sources])
    (out/'EXACT_CONFIGURATION.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
    for pi,(pid,g0) in enumerate(links.groupby('panel_id',sort=False)):
        perms=[]
        p=panels.loc[pid];fold=p.building
        bg=str(p.background_workers).split('|') if pd.notna(p.background_workers) else []
        variables=str(p.variable_workers).split('|')
        candidate_known=set.intersection(*(set(maps[(m,fold)]) for m in METHODS+['Q_MEDIAN2']))
        validbg=set(bg).issubset(candidate_known)
        mask=g0.selected_variable_workers.map(lambda s:set(s.split('|')).issubset(candidate_known)) & validbg
        g=g0[mask].copy()
        counts.append(dict(panel_id=pid,original_shared45_teams=len(g0),new_shared_teams=len(g),background_known=validbg,available_variable_workers='|'.join(v for v in variables if v in candidate_known),pool_id=p.pool_id,image=p.image,building=p.building,n=int(p.n)))
        if not len(g):continue
        # Drop unavailable variables from the randomization universe.
        variables=[v for v in variables if v in candidate_known]
        incidence=np.array([[int(v in set(s.split('|'))) for v in variables] for s in g.selected_variable_workers],dtype=np.int8)
        assert (incidence.sum(1)==p.selected_variable_n).all()
        qmap=maps[('Q_MEDIAN2',fold)];qclasses=sorted(set(qmap.values()))
        qv=np.array([qclasses.index(qmap[v]) for v in variables]);qbase=np.array([sum(qmap[b]==c for b in bg) for c in qclasses])
        qcounts=incidence@np.eye(len(qclasses),dtype=int)[qv]+qbase
        qgroups=np.unique(encode(qcounts),return_inverse=True)[1]
        # Per-person Q/T history comes only from the held-out-building history table.
        def person(wid):
            z=h.loc[(fold,wid)];qa=qaxis[fold][wid]
            return np.array([qa,z.m_all_B8L2,z.m_all_B8L2_p20,qa**2,z.m_all_log_time,z.m_all_log_time**2],float)
        fv=np.vstack([person(v) for v in variables]);fb=np.sum([person(b) for b in bg],axis=0) if bg else np.zeros(6)
        hist=(incidence@fv+fb)/int(p.n)
        xQ=np.column_stack([hist[:,:4],hist[:,0]**2]);xQT=np.column_stack([xQ,hist[:,4:6],hist[:,4]**2,hist[:,0]*hist[:,4]])
        for x in [xQ,xQT]:
            center=np.nanmean(x,axis=0);scale=np.nanstd(x,axis=0);scale[scale<1e-12]=1;x[:]=(x-center)/scale
        qtext=['|'.join(f'{c}:{v}' for c,v in zip(qclasses,row)) for row in qcounts]
        assert all(book[('Q_MEDIAN2',int(code))]==text for code,text in zip(g.Q_MEDIAN2,qtext))
        baseinfo=dict(panel_id=pid,pool_id=p.pool_id,image=p.image,building=p.building,n=int(p.n),source_domain=p.source_domain,difficulty=p.official_difficulty)
        ag=g[['team_link_id','panel_id','team_key','selected_variable_workers','Q_MEDIAN2']+METRICS].copy()
        ag['Q_quota']=qtext
        for j,nm in enumerate(['official_Q_mean','target_Q_mean','target_Qp20_mean','official_Q_square_mean','logT_mean','logT_square_mean']):ag[nm]=hist[:,j]
        for method in METHODS:
            mmap=maps[(method,fold)];classes=sorted(set(mmap.values()))
            cv=np.array([classes.index(mmap[v]) for v in variables]);cb=np.array([sum(mmap[b]==c for b in bg) for c in classes])
            mc=incidence@np.eye(len(classes),dtype=int)[cv]+cb
            mtext=['|'.join(f'{c}:{v}' for c,v in zip(classes,row)) for row in mc]
            if not method.startswith('V21_'):assert all(book[(method,int(code))]==text for code,text in zip(g[method],mtext)),(pid,method)
            ag[method+'_composition']=mtext
            comb=groups_from(qgroups,encode(mc))
            metric_cache={}
            for metric in METRICS:
                y0=g[metric].to_numpy(float);finite=np.isfinite(y0)
                for model,x0 in zip(MODELS,[None,xQ,xQT]):
                    valid=finite.copy()
                    if x0 is not None:valid &= np.isfinite(x0).all(1)
                    y=y0[valid];n=len(y)
                    if n<2:continue
                    qg=np.unique(qgroups[valid],return_inverse=True)[1];mg=np.unique(comb[valid],return_inverse=True)[1]
                    x=x0[valid] if x0 is not None else None
                    base,base_df=sse(y,qg,x);full,full_df=sse(y,mg,x);total=float(np.mean((y-y.mean())**2));inc=(base-full)/n
                    assert inc>=-1e-7*(1+total),(pid,method,metric,model,inc)
                    rr={**baseinfo,'method':method,'metric':metric,'model':model,'valid_teams':n,'missing_teams':len(g)-n,'total_variance':total,
                        'baseline_residual_variance':base/n,'combined_residual_variance':full/n,'increment_variance':max(inc,0.),
                        'baseline_rank':base_df,'combined_rank':full_df,'baseline_cells':len(np.unique(qg)),'combined_cells':len(np.unique(mg)),
                        'teams_in_singleton_combined_cells':int((np.bincount(mg)[mg]==1).sum())}
                    rr['baseline_share']=1-base/n/total if total>1e-15 else np.nan
                    rr['increment_share']=inc/total if total>1e-15 else np.nan
                    rr['remaining_sd']=np.sqrt(full/n)
                    rows.append(rr)
                    if model=='exact_Q_quota':metric_cache[metric]=(finite,y,base/n,total,max(inc,0.))
            seed=int.from_bytes(hashlib.sha256(f'{args.seed}|{pid}|{method}'.encode()).digest()[:8],'little')
            rng=np.random.default_rng(seed);strata=[np.flatnonzero(qv==q) for q in np.unique(qv)]
            onehot=np.eye(len(classes),dtype=int)
            for rep in range(args.permutations):
                perm=cv.copy()
                for ids in strata:perm[ids]=rng.permutation(cv[ids])
                rcode=encode(incidence@onehot[perm]+cb);rgroup=groups_from(qgroups,rcode)
                for metric,(finite,y,basevar,total,observed) in metric_cache.items():
                    mg=np.unique(rgroup[finite],return_inverse=True)[1];rs,_=sse(y,mg)
                    perms.append({**baseinfo,'method':method,'metric':metric,'replicate':rep,'increment_variance':max(basevar-rs/len(y),0.),'total_variance':total,'observed_increment_variance':observed})
        assign.append(ag)
        shard=out/'randomization_shards'/f'panel_{pi:03d}.csv.gz'
        save(pd.DataFrame(perms),shard);perm_files.append(shard);perm_total+=len(perms)
        if (pi+1)%10==0 or pi==0:
            print(f'panels {pi+1}/{links.panel_id.nunique()} rows={len(rows)} permutations={perm_total}',flush=True)
        if (pi+1)%30==0:
            save(pd.DataFrame(rows),out/'PANEL_CONDITIONAL_RESULTS.csv.gz')
            save(pd.DataFrame(counts),out/'PANEL_SUPPORT.csv')
    df=pd.DataFrame(rows);save(df,out/'PANEL_CONDITIONAL_RESULTS.csv.gz')
    save(pd.DataFrame(counts),out/'PANEL_SUPPORT.csv');save(pd.concat(assign,ignore_index=True),out/'EXACT_TEAM_ASSIGNMENTS_AND_METRICS.csv.gz')
    cols=['total_variance','baseline_residual_variance','combined_residual_variance','increment_variance']
    summary,images,buildings=hierarchy(df,cols)
    save(summary,out/'CONDITIONAL_METHOD_SUMMARY.csv');save(images,out/'IMAGE_CONDITIONAL_RESULTS.csv.gz');save(buildings,out/'BUILDING_CONDITIONAL_RESULTS.csv.gz')
    # Independent per-panel label permutations provide a capacity-preserving reference,
    # not a population null distribution; replicate index only enables equal weighting.
    perm=pd.concat([pd.read_csv(f) for f in perm_files],ignore_index=True)
    keys=['method','metric','replicate'];vals=['increment_variance','total_variance','observed_increment_variance']
    pp=perm.groupby(keys+['pool_id','image','building'])[vals].mean().reset_index()
    ii=pp.groupby(keys+['image','building'])[vals].mean().reset_index()
    bb=ii.groupby(keys+['building'])[vals].mean().reset_index()
    prs=[]
    for weighting,dd in [('image_equal',ii),('building_equal',bb)]:
        rr=dd.groupby(keys)[vals].mean().reset_index();rr['increment_share']=rr.increment_variance/rr.total_variance.where(rr.total_variance.gt(1e-15))
        for (method,metric),g in rr.groupby(['method','metric']):
            observed=g.observed_increment_variance.mean()/g.total_variance.mean() if g.total_variance.mean()>1e-15 else np.nan
            prs.append(dict(method=method,metric=metric,weighting=weighting,replicates=len(g),observed_increment_share=observed,
                            randomized_share_mean=g.increment_share.mean(),randomized_share_p05=g.increment_share.quantile(.05),randomized_share_p50=g.increment_share.quantile(.5),randomized_share_p95=g.increment_share.quantile(.95),
                            observed_minus_randomized_mean=observed-g.increment_share.mean()))
    save(pd.DataFrame(prs),out/'LABEL_RANDOMIZATION_REFERENCE.csv')
    receipt=dict(panels=pd.DataFrame(counts).query('new_shared_teams>0').shape[0],team_links=sum(z['new_shared_teams'] for z in counts),method_results=len(df),
                 assignment_rows=sum(len(z) for z in assign),configuration_vectors_checked_against_existing_codebook=True,nested_SSE_monotonicity_checked=True,
                 new_fusions=0,new_scores=0,permutations=args.permutations,source_sha256={str(s):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources})
    (out/'COMPLETION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--repo',required=True);a.add_argument('--history',required=True);a.add_argument('--new-labels',required=True);a.add_argument('--out',required=True);a.add_argument('--seed',type=int,default=20261029);a.add_argument('--permutations',type=int,default=128);main(a.parse_args())
