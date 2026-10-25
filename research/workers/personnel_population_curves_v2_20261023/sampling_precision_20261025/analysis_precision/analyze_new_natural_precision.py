#!/usr/bin/env python3
"""Independent-order replication of fixed-pool natural population curves.

No fusion, rescoring, personnel classification, or outcome-based seed selection.
Inputs are saved old/new path-prefix values and exact finite marginal anchors.
The balanced comparison is old24/new24/pooled48 on the same pool. Focus96 is a
separate old-precision-selected domain. Resampling is whole paths, stratified
by independently generated batches so dependent old-versus-pooled comparisons
retain the common old paths. Building resampling holds all path values fixed.
"""
from pathlib import Path
from collections import defaultdict
import argparse, csv, gc, gzip, hashlib, io, json, math, os, warnings
for _thread_var in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[_thread_var]='1'
import numpy as np
import pandas as pd
from scipy.stats import t
from diagnose_existing_paths import (seed_for, qlinear, binomial_interval,
                                      quantile_order_interval)

warnings.filterwarnings('ignore', category=RuntimeWarning)
META=['pool_id','image','image_id','building','condition','layer','difficulty','pool_n',
      'reference_id','reference_version']
QMET=['Q_mean','Q_p10','Q_sd_ddof1','D10_mean','floor_turn5_mean',
      'floor_redundant5_mean','nodes_mean','failure_rate','incomplete_rate']
RAW=['B8L2','D10','floor_turn5_n','floor_redundant5_n','nodes',
     'score_failure_nonpolicy','incomplete_nonpolicy','policy_deferred']
COMP=['B8_floor_block','B8_direction_block','B8_height_block',
      'B8_global_height_block','B8_local_height_block','iou_2d','S_bottom_deg',
      'dir','height_mean_h','Hmean','Hcenter','omission','extension']
IVMET=['marginal_Q_delta','Q_p10_delta','Q_sd_delta','paired_Q_delta',
       'paired_D10_delta','paired_Q_loss_gt5_rate','paired_Q_gain_gt5_rate',
       'failure_delta','incomplete_delta','floor_turn5_delta','nodes_delta']
VERSIONS=['old24','new24','pooled48','focus96']
ABS_K=[1,3,4,5,6,8,10,15,20,25,30,34,35]
THRESHOLDS=[6,10,20,30,35]
ZERO_TOL=1e-9
REPAIR_TARGETS=None
EXPORT_RECEIPTS=[]


def atomic_bytes(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.atomic.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o644)
    try:
        view=memoryview(payload);offset=0
        while offset<len(view):offset+=os.write(fd,view[offset:offset+1024*1024])
        os.fsync(fd)
    finally:os.close(fd)
    actual=tmp.read_bytes()
    assert actual==payload,('atomic temporary write truncated',path,len(payload),len(actual))
    tmp.replace(path)
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
    actual=path.read_bytes()
    assert actual==payload,('atomic final readback mismatch',path)


def save(df,path):
    path=Path(path)
    if REPAIR_TARGETS is not None and path.name not in REPAIR_TARGETS:return
    body=df.to_csv(index=False).encode('utf-8')
    payload=gzip.compress(body,compresslevel=6,mtime=0) if path.suffix=='.gz' else body
    atomic_bytes(path,payload)
    actual=path.read_bytes()
    decoded=(gzip.decompress(actual) if path.suffix=='.gz' else actual).decode('utf-8')
    reader=csv.reader(io.StringIO(decoded));head=next(reader);count=0
    assert head==list(map(str,df.columns)),('export header',path)
    for row in reader:
        count+=1
        assert len(row)==len(head),('export field count',path,count)
    assert count==len(df),('export row count',path,count,len(df))
    EXPORT_RECEIPTS.append(dict(file=path.name,rows=count,fields=len(head),bytes=len(actual),
                                sha256=hashlib.sha256(actual).hexdigest(),readback='complete_EOF_after_atomic_fsync_write'))


def verify_all_tables(folder):
    rows=[]
    for path in sorted(Path(folder).glob('*.csv*')):
        if path.name.endswith('.tmp'):continue
        raw=path.read_bytes();body=gzip.decompress(raw) if path.suffix=='.gz' else raw
        reader=csv.reader(io.StringIO(body.decode('utf-8')));head=next(reader);count=0
        for row in reader:
            count+=1
            assert len(row)==len(head),('final field count',path,count)
        rows.append(dict(file=path.name,rows=count,fields=len(head),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),ok=True))
    return rows


def asnum(s):
    if s.dtype==bool:return s.astype(float)
    if s.dtype==object:s=s.replace({'True':1,'False':0,'true':1,'false':0})
    return pd.to_numeric(s,errors='coerce').replace([np.inf,-np.inf],np.nan)


def arrays(g,paths,ks):
    return {c:g.pivot(index='path_id',columns='k',values=c).reindex(index=paths,columns=ks).to_numpy(float)
            for c in RAW+COMP if c in g}


def concat(a,b):
    return {c:np.concatenate([a[c],b[c]],axis=0) for c in a if c in b}


def stats(a):
    """Arrays are [...,paths,k]; result [...,k,metric]."""
    q=a['B8L2'];axis=q.ndim-2
    defer=a['policy_deferred']
    nondeferred=np.isfinite(defer)&(defer==0)
    den=nondeferred.sum(axis)
    fail=np.where(nondeferred,a['score_failure_nonpolicy'],0).sum(axis)
    inc=np.where(nondeferred,a['incomplete_nonpolicy'],0).sum(axis)
    out=[np.nanmean(q,axis),qlinear(q,axis=axis),np.nanstd(q,axis,ddof=1),
         np.nanmean(a['D10'],axis),np.nanmean(a['floor_turn5_n'],axis),
         np.nanmean(a['floor_redundant5_n'],axis),np.nanmean(a['nodes'],axis),
         np.divide(fail,den,out=np.full_like(fail,np.nan,dtype=float),where=den>0),
         np.divide(inc,den,out=np.full_like(inc,np.nan,dtype=float),where=den>0)]
    return np.stack(out,axis=-1)


def interval_definitions(n):
    candidates=[('1_to_3',1,3),('3_to_6',3,6),('6_to_10',6,10),
                ('10_to_20',10,20),('20_to_30',20,30),('30_to_35',30,35),
                ('3_to_20',3,20),('3_to_full',3,n),('10_to_full',10,n),
                ('20_to_full',20,n),('30_to_full',30,n),('leave_one_out_to_full',n-1,n)]
    return [(name,ka,kb) for name,ka,kb in candidates
            if 1<=ka<=kb<=n and (ka<kb or name.endswith('_to_full'))]


def interval_stats(a,s,idefs):
    results=[]
    axis=a['B8L2'].ndim-2
    for name,ka,kb in idefs:
        qa=a['B8L2'][...,ka-1];qb=a['B8L2'][...,kb-1]
        dq=qb-qa;good=np.isfinite(dq)
        dd=a['D10'][...,kb-1]-a['D10'][...,ka-1]
        # Once k is selected, the path axis is the last axis.
        out=[s[...,kb-1,0]-s[...,ka-1,0],s[...,kb-1,1]-s[...,ka-1,1],
             s[...,kb-1,2]-s[...,ka-1,2],np.nanmean(dq,-1),np.nanmean(dd,-1),
             np.nanmean(np.where(good,dq < -5,np.nan),-1),
             np.nanmean(np.where(good,dq > 5,np.nan),-1),
             s[...,kb-1,7]-s[...,ka-1,7],s[...,kb-1,8]-s[...,ka-1,8],
             s[...,kb-1,4]-s[...,ka-1,4],s[...,kb-1,6]-s[...,ka-1,6]]
        results.append(np.stack(out,axis=-1))
    return np.stack(results,axis=-2)


def init_agg(B,shape):
    return dict(sum=np.zeros((B,)+shape,np.float64),weight=np.zeros((B,)+shape,np.float64))


def add_agg(agg,vals,weights):
    good=np.isfinite(vals)
    agg['sum']+=np.where(good,vals,0)*weights[None]
    agg['weight']+=good*weights[None]


def boot_summary(v):
    valid=np.isfinite(v)
    if not valid.any():return (np.nan,np.nan,np.nan,0)
    if np.ptp(v[valid])==0:return (float(v[valid][0]),float(v[valid][0]),0.0,int(valid.sum()))
    lo,hi=np.nanquantile(v,[.025,.975])
    return lo,hi,np.nanstd(v,ddof=1),int(valid.sum())


def add_components(old,new,scalar_path):
    """Coalesce only needed saved scalar fields; never rerun the scorer."""
    cols=pd.read_csv(scalar_path,nrows=0).columns
    use=['team_key']+[c for c in COMP if c in cols]
    scalar=pd.read_csv(scalar_path,usecols=use,low_memory=False).drop_duplicates('team_key')
    for d in [old,new]:
        for c in COMP:
            if c not in d:d[c]=np.nan
        for c in use[1:]:
            looked=d.team_key.map(scalar.set_index('team_key')[c])
            d[c]=d[c].where(d[c].notna(),looked)
    return old,new


def component_summaries(components,focus_ids,out):
    """Saved component means on the same pool/k; path MC error analytically.

    The independent new24-minus-old24 variance is the sum of batch mean
    variances. For dependent pooled-versus-old comparisons only point changes
    are reported here; joint nonlinear Q uncertainty is in the main bootstrap.
    """
    base=components[components.version.eq('old24')]
    rows=[]
    for version in ['new24','pooled48','focus96']:
        newer=components[components.version.eq(version)]
        z=base.merge(newer,on=['pool_id','k','component'],suffixes=('_old','_new'),validate='one_to_one')
        z=z[z['mean_old'].notna()&z['mean_new'].notna()].copy()
        for domain in ['balanced_all','old_noise_focus']:
            d=z[z.pool_id.isin(focus_ids)] if domain=='old_noise_focus' else z
            if version=='focus96' and domain!='old_noise_focus':continue
            for threshold in THRESHOLDS:
                h=d[d.pool_n_old.ge(threshold)&d.k.isin([k for k in ABS_K if k<=threshold])].copy()
                if h.empty:continue
                h['difficulty_group']=h.difficulty_old
                allrows=h.copy();allrows['difficulty_group']=np.where(allrows.layer_old.eq('ordinary_manual'),'全部','单列')
                h=pd.concat([h,allrows],ignore_index=True).drop_duplicates(['pool_id','k','component','difficulty_group'])
                for (layer,diff,k,component),g in h.groupby(['layer_old','difficulty_group','k','component']):
                    buildings=sorted(g.building_old.unique());size=g.groupby('building_old').size()
                    for weighting in ['image_equal','building_equal']:
                        w=np.ones(len(g))/len(g) if weighting=='image_equal' else np.array([1/(len(buildings)*size[b]) for b in g.building_old])
                        oldmean=float(np.dot(w,g['mean_old']));newmean=float(np.dot(w,g['mean_new']))
                        ose=float(np.sqrt(np.dot(w*w,g.MCSE_old*g.MCSE_old)));nse=float(np.sqrt(np.dot(w*w,g.MCSE_new*g.MCSE_new)))
                        rows.append(dict(domain=domain,panel=f'fixed_N_ge_{threshold}',layer=layer,difficulty=diff,k=int(k),
                                         component=component,comparison=version+'_minus_old24',weighting=weighting,
                                         old_mean=oldmean,new_mean=newmean,difference=newmean-oldmean,
                                         old_mean_MCSE=ose,new_mean_MCSE=nse,
                                         independent_difference_MCSE=np.sqrt(ose*ose+nse*nse) if version=='new24' else np.nan,
                                         common_images=len(g),common_buildings=len(buildings),
                                         positive_image_difference_fraction=float((g['mean_new']-g['mean_old']>ZERO_TOL).mean()),
                                         negative_image_difference_fraction=float((g['mean_new']-g['mean_old'] < -ZERO_TOL).mean()),
                                         near_zero_image_difference_fraction=float(((g['mean_new']-g['mean_old']).abs()<=ZERO_TOL).mean()),
                                         strict_positive_image_difference_fraction=float((g['mean_new']>g['mean_old']).mean()),
                                         strict_negative_image_difference_fraction=float((g['mean_new']<g['mean_old']).mean()),
                                         interpretation='B8 loss block: lower better' if component.startswith('B8_') else 'saved frozen scalar'))
    save(pd.DataFrame(rows),out/'NATURAL_COMPONENT_COMMON_SUPPORT_COMPARISONS.csv.gz')


def export_hybrid48(curve,exact,out):
    """Adopt exact finite marginals without overwriting any random comparison."""
    base=curve[curve.version.eq('pooled48')].copy()
    lookup=exact.set_index(['pool_id','k']).to_dict('index')
    rows=[]
    for r in base.to_dict('records'):
        key=(r['pool_id'],r['k']);e=lookup.get(key)
        deferred=int(r['k'])==2
        z={c:r[c] for c in META+['k']}
        z.update(available_balanced_natural_paths=48,
                 finite_population_teams=str(math.comb(int(r['pool_n']),int(r['k']))),
                 estimation_target='uniform eligible-pool k-subsets; score distribution conditional on scoreable team',
                 P10_convention='NumPy linear; no replacement of saved old24 curves',
                 focus96_used=False)
        if e is not None and not deferred:
            z.update(estimator='exact_finite_uniform_marginal',path_count=0,
                     known_finite_teams=int(e['finite_population_teams']),
                     finite_marginal_complete=True,
                     unique_teams=int(e['finite_population_teams']),exact_kind=e['exact_kind'],
                     quality_valid_units=int(e['quality_valid_teams']),nondeferred_attempt_units=int(e['finite_population_teams']),
                     actual_failure_units=int(e['actual_failure_teams']),policy_deferred_units=0,
                     Q_mean=e['Q_mean'],Q_p10=e['Q_p10'],Q_sd_population_estimate=e['Q_sd_population'],
                     SD_convention='exact finite-population ddof0',
                     endpoint_locator='exact_marginal_design:pool_id+k; every distinct team weighted 1/C(N,k)')
            for metric in QMET[3:]:z[metric]=e[metric]
            for metric,value in [('Q_mean',z['Q_mean']),('Q_p10',z['Q_p10']),('Q_sd_population_estimate',z['Q_sd_population_estimate'])]+[(v,z[v]) for v in QMET[3:]]:
                z[metric+'_MCSE']=0.0 if np.isfinite(value) else np.nan
            z['quality_uncertainty_status']='exact_known' if np.isfinite(z['Q_mean']) else 'no_scoreable_finite_team'
        elif deferred:
            z.update(estimator='contract_deferred_k2',path_count=48,known_finite_teams=0,
                     finite_marginal_complete=False,
                     catalogued_deferred_finite_teams=int(e['finite_population_teams']) if e is not None else 0,
                     unique_teams=int(r['unique_teams']),exact_kind='',quality_valid_units=0,
                     nondeferred_attempt_units=0,actual_failure_units=0,policy_deferred_units=48,
                     Q_mean=np.nan,Q_p10=np.nan,Q_sd_population_estimate=np.nan,
                     SD_convention='not_computed_contract_deferred',endpoint_locator='balanced48 saved prefix keys; no formal two-person fusion')
            for metric in QMET[3:]:z[metric]=np.nan
            for metric in ['Q_mean','Q_p10','Q_sd_population_estimate']+QMET[3:]:z[metric+'_MCSE']=np.nan
            z['quality_uncertainty_status']='not_computed_contract_deferred'
        else:
            z.update(estimator='balanced48_uniform_random_permutation_prefixes',path_count=48,known_finite_teams=int(r['unique_teams']),
                     finite_marginal_complete=False,
                     unique_teams=int(r['unique_teams']),exact_kind='',quality_valid_units=int(r['quality_valid_paths']),
                     nondeferred_attempt_units=int(r['nondeferred_attempts']),actual_failure_units=int(r['failure_paths']),
                     policy_deferred_units=int(r['policy_deferred_paths']),Q_mean=r['Q_mean'],Q_p10=r['Q_p10'],
                     Q_sd_population_estimate=r['Q_sd_ddof1'],SD_convention='sample ddof1 estimate of finite-population dispersion',
                     endpoint_locator='old exact order design + new balanced_new24 prefix links:pool_id+k')
            for metric in QMET[3:]:z[metric]=r[metric]
            z['Q_mean_MCSE']=r['Q_mean_MCSE_analytic']
            z['Q_p10_MCSE']=r['Q_p10_bootse']
            z['Q_sd_population_estimate_MCSE']=r['Q_sd_ddof1_bootse']
            for metric in QMET[3:]:z[metric+'_MCSE']=r[metric+'_bootse']
            z['quality_uncertainty_status']='observed_path_estimate' if r['quality_uncertainty_estimable'] else 'fewer_than_two_scoreable_paths'
        rows.append(z)
    hybrid=pd.DataFrame(rows)
    save(hybrid,out/'HYBRID48_IMAGE_CURVES.csv.gz')
    # Readable fixed-support adoption points; uncertainty comparison remains in
    # the original batch tables, where exact replacements have not been made.
    summary=[]
    metrics=['Q_mean','Q_p10','Q_sd_population_estimate']+QMET[3:]
    for threshold in THRESHOLDS:
        h=hybrid[hybrid.pool_n.ge(threshold)&hybrid.k.isin([k for k in ABS_K if k<=threshold])].copy()
        h['difficulty_group']=h.difficulty
        hh=h.copy();hh['difficulty_group']=np.where(hh.layer.eq('ordinary_manual'),'全部','单列')
        h=pd.concat([h,hh],ignore_index=True).drop_duplicates(['pool_id','k','difficulty_group'])
        for (layer,diff,k),g in h.groupby(['layer','difficulty_group','k']):
            for metric in metrics:
                good=g[metric].notna();gg=g[good];buildings=sorted(gg.building.unique())
                for weighting in ['image_equal','building_equal']:
                    value=gg[metric].mean() if weighting=='image_equal' else gg.groupby('building')[metric].mean().mean()
                    if len(gg):
                        w=np.ones(len(gg))/len(gg) if weighting=='image_equal' else np.array([1/(len(buildings)*int((gg.building==b).sum())) for b in gg.building])
                        ses=gg[metric+'_MCSE'].to_numpy(float)
                        se=float(np.sqrt(np.dot(w*w,ses*ses))) if np.isfinite(ses).all() else np.nan
                    else:se=np.nan
                    summary.append(dict(panel=f'fixed_N_ge_{threshold}',layer=layer,difficulty=diff,k=int(k),metric=metric,
                                        weighting=weighting,estimate=value,MCSE_fixed_images_analytic=se,
                                        available_images=len(g),observed_images=len(gg),observed_buildings=len(buildings),
                                        exact_images=int(gg.estimator.eq('exact_finite_uniform_marginal').sum()),
                                        random48_images=int(gg.estimator.eq('balanced48_uniform_random_permutation_prefixes').sum()),
                                        uncertainty='marginal MCSE only; not interval/change covariance and not building variation'))
    save(pd.DataFrame(summary),out/'HYBRID48_FIXED_SUPPORT_CURVES.csv')


def export_independent_focus72(raw,meta,focus_ids,curve,out):
    """Only a conditional descriptive comparison; no new resampling/model."""
    rows=[]
    for p in sorted(focus_ids):
        arr={c:v[24:] for c,v in raw[p]['focus96'].items()}
        assert arr['B8L2'].shape[0]==72
        s=stats(arr);n=int(meta.loc[p,'pool_n'])
        if np.isfinite(arr['B8L2'][:,-1]).any():s[-1,2]=0.0
        for ki in range(n):
            q=arr['B8L2'][:,ki];valid=int(np.isfinite(q).sum());exact=ki==n-1
            se=0.0 if exact and valid else np.nanstd(q,ddof=1)/np.sqrt(valid) if valid>1 else np.nan
            qlo,qhi,_,_,_,_=quantile_order_interval(q)
            if exact:qlo=qhi=s[ki,1]
            trials=int((arr['policy_deferred'][:,ki]==0).sum())
            fail=int(arr['score_failure_nonpolicy'][:,ki].sum())
            flo,fhi,fu=binomial_interval(fail,trials,exact=exact)
            rows.append({**meta.loc[p].to_dict(),'version':'independent_new72','k':ki+1,
                         'paths_attempted':72,'quality_valid_paths':valid,'nondeferred_attempts':trials,
                         'failure_paths':fail,'Q_mean_MCSE':se,'Q_p10_order95_low':qlo,'Q_p10_order95_high':qhi,
                         'failure_CP95_low':flo,'failure_CP95_high':fhi,'failure_one_sided95_high':fu,
                         'pool_selection':'fixed original24 high-noise list; all 72 new paths independent of selection observations',
                         'interpretation':'descriptive conditional check; lower old-to-new SD/MCSE can include regression to mean',
                         **dict(zip(QMET,s[ki]))})
    fresh=pd.DataFrame(rows);save(fresh,out/'FOCUS_INDEPENDENT_NEW72_IMAGE_CURVES.csv.gz')
    summaries=[]
    for v in VERSIONS:
        other=curve[curve.version.eq(v)&curve.pool_id.isin(focus_ids)]
        d=fresh.merge(other,on=['pool_id','k'],suffixes=('_new72','_comparison'),validate='one_to_one')
        for threshold in THRESHOLDS:
            h=d[d.pool_n_new72.ge(threshold)&d.k.isin([k for k in ABS_K if k<=threshold])].copy()
            h['difficulty_group']=h.difficulty_new72
            hh=h.copy();hh['difficulty_group']=np.where(hh.layer_new72.eq('ordinary_manual'),'全部','单列')
            h=pd.concat([h,hh],ignore_index=True).drop_duplicates(['pool_id','k','difficulty_group'])
            for (layer,diff,k),g in h.groupby(['layer_new72','difficulty_group','k']):
                for metric in QMET:
                    good=g[metric+'_new72'].notna()&g[metric+'_comparison'].notna();gg=g[good]
                    buildings=sorted(gg.building_new72.unique())
                    for weighting in ['image_equal','building_equal']:
                        if len(gg):
                            w=np.ones(len(gg))/len(gg) if weighting=='image_equal' else np.array([1/(len(buildings)*int((gg.building_new72==b).sum())) for b in gg.building_new72])
                            newer=float(np.dot(w,gg[metric+'_new72']));older=float(np.dot(w,gg[metric+'_comparison']))
                            ses=gg.Q_mean_MCSE.to_numpy(float)
                            mcse=float(np.sqrt(np.dot(w*w,ses*ses))) if metric=='Q_mean' and np.isfinite(ses).all() else np.nan
                            deltas=gg[metric+'_new72']-gg[metric+'_comparison']
                        else:newer=older=mcse=np.nan;deltas=pd.Series(dtype=float)
                        summaries.append(dict(domain='fixed_old_noise_selected_pools',panel=f'fixed_N_ge_{threshold}',
                            layer=layer,difficulty=diff,k=int(k),metric=metric,weighting=weighting,
                            comparison='independent_new72_minus_'+v,independent_new72_estimate=newer,comparison_estimate=older,
                            difference=newer-older,independent_new72_Qmean_MCSE=mcse,available_images=len(g),
                            common_images=len(gg),common_buildings=len(buildings),
                            positive_image_difference_fraction=float((deltas>ZERO_TOL).mean()) if len(deltas) else np.nan,
                            negative_image_difference_fraction=float((deltas < -ZERO_TOL).mean()) if len(deltas) else np.nan,
                            near_zero_image_difference_fraction=float((deltas.abs()<=ZERO_TOL).mean()) if len(deltas) else np.nan,
                            strict_positive_image_difference_fraction=float((deltas>0).mean()) if len(deltas) else np.nan,
                            strict_negative_image_difference_fraction=float((deltas<0).mean()) if len(deltas) else np.nan,
                            inference_scope='fixed selected pool domain; no re-selection bootstrap; no new sampling'))
    save(pd.DataFrame(summaries),out/'FOCUS_NEW72_COMMON_SUPPORT_COMPARISONS.csv.gz')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--old',type=Path,required=True)
    ap.add_argument('--new',type=Path,required=True)
    ap.add_argument('--old-scalars',type=Path,required=True)
    ap.add_argument('--focus',type=Path,required=True)
    ap.add_argument('--exact',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--bootstrap',type=int,default=2000)
    ap.add_argument('--seed',type=int,default=2026102513)
    ap.add_argument('--repair-derived-outputs',nargs='+',default=None)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    global REPAIR_TARGETS
    REPAIR_TARGETS=set(a.repair_derived_outputs) if a.repair_derived_outputs else None
    if REPAIR_TARGETS is not None:
        previous=a.out/'NATURAL_ANALYSIS_RECEIPT.json'
        if previous.exists():previous.replace(a.out/'ORIGINAL_COMPUTATION_RECEIPT_before_export_repair.json')
    needed=set(META+RAW+COMP+['path_id','policy','batch','k','team_key'])
    old=pd.read_csv(a.old,usecols=lambda c:c in needed,low_memory=False)
    new=pd.read_csv(a.new,usecols=lambda c:c in needed,low_memory=False)
    focus=pd.read_csv(a.focus)
    pools=set(focus.pool_id)
    old=old[old.policy.eq('natural_random')&old.pool_id.isin(pools)].copy()
    new=new[new.policy.eq('natural_random')&new.pool_id.isin(pools)].copy()
    old_prefix_count=len(old);new_prefix_count=len(new)
    old,new=add_components(old,new,a.old_scalars)
    for d in [old,new]:
        for c in RAW+COMP:
            if c not in d:d[c]=np.nan
            d[c]=asnum(d[c])
        for flag in ['policy_deferred','score_failure_nonpolicy','incomplete_nonpolicy']:
            assert d[flag].notna().all(),f'uncomputed/missing status cannot become zero: {flag}'
        assert not d.duplicated(['pool_id','path_id','k']).any()
    meta=old[META].drop_duplicates('pool_id').sort_values('pool_id').set_index('pool_id',drop=False)
    raw={};point={};ipoint={};point_n={};ipoint_n={};idefs={};curve_rows=[];interval_rows=[];seeds=[]
    component_rows=[];support=[]
    grouped_old={p:g for p,g in old.groupby('pool_id')}
    grouped_new={p:g for p,g in new.groupby('pool_id')}
    focus_ids=set(focus.loc[focus.focus_selected,'pool_id'])
    for p in meta.index:
        m=meta.loc[p].to_dict();n=int(m['pool_n']);ks=list(range(1,n+1))
        g=grouped_old[p];h=grouped_new[p]
        oldpaths=sorted(g.path_id.unique())
        balanced=h[h.batch.eq('balanced_new24')]
        extra=h[h.batch.eq('focus_new48')]
        newpaths=sorted(balanced.path_id.unique());extrapaths=sorted(extra.path_id.unique())
        assert len(oldpaths)==24 and len(newpaths)==24,(p,len(oldpaths),len(newpaths))
        assert len(extrapaths)==(48 if p in focus_ids else 0),(p,len(extrapaths))
        assert len(g)==24*n and len(balanced)==24*n and len(extra)==len(extrapaths)*n
        oa=arrays(g,oldpaths,ks);na=arrays(balanced,newpaths,ks)
        versions={'old24':oa,'new24':na,'pooled48':concat(oa,na)}
        if len(extrapaths):
            ea=arrays(extra,extrapaths,ks);versions['focus96']=concat(versions['pooled48'],ea)
        raw[p]=versions;idefs[p]=interval_definitions(n);point[p]={};ipoint[p]={};point_n[p]={};ipoint_n[p]={}
        pathframes={'old24':g,'new24':balanced,'pooled48':pd.concat([g,balanced],ignore_index=True)}
        if len(extrapaths):pathframes['focus96']=pd.concat([g,balanced,extra],ignore_index=True)
        for version,arr in versions.items():
            s=stats(arr)
            if np.isfinite(arr['B8L2'][:,-1]).any():s[-1,2]=0.0
            ii=interval_stats(arr,s,idefs[p]);point[p][version]=s;ipoint[p][version]=ii
            r=arr['B8L2'].shape[0]
            qcount=np.isfinite(arr['B8L2']).sum(0)
            point_n[p][version]=np.stack([qcount,qcount,qcount,
                np.isfinite(arr['D10']).sum(0),np.isfinite(arr['floor_turn5_n']).sum(0),
                np.isfinite(arr['floor_redundant5_n']).sum(0),np.isfinite(arr['nodes']).sum(0),
                (arr['policy_deferred']==0).sum(0),(arr['policy_deferred']==0).sum(0)],axis=-1)
            interval_count_rows=[]
            for j,k in enumerate(ks):
                q=arr['B8L2'][:,j];qv=q[np.isfinite(q)];valid=len(qv)
                deferred=int(arr['policy_deferred'][:,j].sum());trial=r-deferred
                fail=int(arr['score_failure_nonpolicy'][:,j].sum());exact=k==n
                flo,fhi,fhione=binomial_interval(fail,trial,exact=exact)
                qlo,qhi,qlr,qur,lowerbound,upperbound=quantile_order_interval(q)
                if exact:qlo=qhi=s[j,1];lowerbound=upperbound=False
                se=0.0 if exact and valid else np.nanstd(q,ddof=1)/np.sqrt(valid) if valid>1 else np.nan
                row={**m,'version':version,'k':k,'paths_attempted':r,'quality_valid_paths':valid,
                     'unique_teams':pathframes[version].loc[pathframes[version].k.eq(k),'team_key'].nunique(),
                     'policy_deferred_paths':deferred,'nondeferred_attempts':trial,'failure_paths':fail,
                     'incomplete_paths':int(arr['incomplete_nonpolicy'][:,j].sum()),'mc_exact_full_pool':exact,
                     'quality_uncertainty_estimable':bool(valid>=2 or (exact and valid>0)),
                     'Q_mean_MCSE_analytic':se,'Q_mean_t95_halfwidth':t.ppf(.975,valid-1)*se if valid>1 else np.nan,
                     'Q_p10_order95_low':qlo,'Q_p10_order95_high':qhi,
                     'Q_p10_order95_uses_lower_support_bound':lowerbound,
                     'Q_p10_order95_uses_upper_support_bound':upperbound,
                     'failure_CP95_low':flo,'failure_CP95_high':fhi,'failure_one_sided95_high':fhione,
                     **dict(zip(QMET,s[j]))}
                curve_rows.append(row)
                for c in ([] if REPAIR_TARGETS is not None else COMP):
                    v=arr[c][:,j];nv=int(np.isfinite(v).sum())
                    cse=0.0 if exact and nv else np.nanstd(v,ddof=1)/np.sqrt(nv) if nv>1 else np.nan
                    component_rows.append({**m,'version':version,'k':k,'component':c,'valid_paths':nv,
                                           'mean':np.nanmean(v),'MCSE':cse,
                                           'interpretation':'B8 loss block: lower better' if c.startswith('B8_') else 'saved frozen component; no rescore'})
            for j,(name,ka,kb) in enumerate(idefs[p]):
                qa=arr['B8L2'][:,ka-1];qb=arr['B8L2'][:,kb-1]
                qmin=min(int(np.isfinite(qa).sum()),int(np.isfinite(qb).sum()))
                qpair=int((np.isfinite(qa)&np.isfinite(qb)).sum())
                dpair=int(np.isfinite(arr['D10'][:,kb-1]-arr['D10'][:,ka-1]).sum())
                interval_count_rows.append([qmin,qmin,qmin,qpair,dpair,qpair,qpair,r,r,
                    min(np.isfinite(arr['floor_turn5_n'][:,ka-1]).sum(),np.isfinite(arr['floor_turn5_n'][:,kb-1]).sum()),
                    min(np.isfinite(arr['nodes'][:,ka-1]).sum(),np.isfinite(arr['nodes'][:,kb-1]).sum())])
                z={**m,'version':version,'interval':name,'from_k':ka,'to_k':kb,'paths_attempted':r,
                   'from_quality_valid_paths':int(np.isfinite(qa).sum()),'to_quality_valid_paths':int(np.isfinite(qb).sum()),
                   'both_quality_valid_paths':int((np.isfinite(qa)&np.isfinite(qb)).sum()),
                   'gained_score_paths':int((~np.isfinite(qa)&np.isfinite(qb)).sum()),
                   'lost_score_paths':int((np.isfinite(qa)&~np.isfinite(qb)).sum()),**dict(zip(IVMET,ii[j]))}
                interval_rows.append(z)
            ipoint_n[p][version]=np.array(interval_count_rows)
        support.append({**m,'old_natural_paths':len(oldpaths),'balanced_new_paths':len(newpaths),
                        'focus_new_paths':len(extrapaths),'old_prefixes':len(g),
                        'new_prefixes':len(balanced)+len(extra),'focus_selected':p in focus_ids})
    curve=pd.DataFrame(curve_rows);ints=pd.DataFrame(interval_rows);components=pd.DataFrame(component_rows)
    save(pd.DataFrame(support),a.out/'NATURAL_BATCH_SUPPORT.csv')
    save(curve,a.out/'NATURAL_POOL_K_BATCH_POINTS.csv.gz')
    save(ints,a.out/'NATURAL_POOL_INTERVAL_BATCH_POINTS.csv.gz')
    if REPAIR_TARGETS is None:
        save(components,a.out/'NATURAL_COMPONENT_POOL_K_BATCH_POINTS.csv.gz')
        component_summaries(components,focus_ids,a.out)
    del old,new,grouped_old,grouped_new,components,component_rows,pathframes,g,h,balanced,extra
    gc.collect()

    # Scope definitions are fixed by pool capacity and the preregistered focus.
    # Point and bootstrap quality comparisons use the same images per cell.
    specs=[]
    for domain,domain_ids,versions in [('balanced_all',set(meta.index),VERSIONS[:3]),('old_noise_focus',focus_ids,VERSIONS)]:
        for (layer,diff),mm in [(('ordinary_manual','全部'),meta[meta.layer.eq('ordinary_manual')]),
                              *((('ordinary_manual',di),meta[meta.layer.eq('ordinary_manual')&meta.difficulty.eq(di)]) for di in ['简单','中等','困难']),
                              (('doorway_manual','单列'),meta[meta.layer.eq('doorway_manual')])]:
            ids=[p for p in mm.index if p in domain_ids]
            if not ids:continue
            for threshold in THRESHOLDS:
                ps=[p for p in ids if int(meta.loc[p,'pool_n'])>=threshold]
                if not ps:continue
                positions=[k for k in ABS_K if k<=threshold]
                curve_indices={p:[k-1 for k in positions] for p in ps}
                names=[name for name,ka,kb in interval_definitions(threshold) if not name.endswith('full') and not name.endswith('to_full')]
                # Only fixed absolute intervals belong in fixed-N panels.
                names=[n for n in ['1_to_3','3_to_6','6_to_10','10_to_20','20_to_30','30_to_35','3_to_20'] if any(n==x[0] for x in interval_definitions(threshold))]
                if threshold==30:names.append('30_to_full')
                ii={p:[[x[0] for x in idefs[p]].index(name) for name in names] for p in ps}
                specs.append(dict(domain=domain,layer=layer,difficulty=diff,panel=f'fixed_N_ge_{threshold}',
                                  pools=ps,versions=versions,positions=positions,cidx=curve_indices,inames=names,iidx=ii))
            ps=ids;positions=['singleton','leave_one_out','full_pool']
            cidx={p:[0,int(meta.loc[p,'pool_n'])-2,int(meta.loc[p,'pool_n'])-1] for p in ps}
            names=['leave_one_out_to_full'];ii={p:[[x[0] for x in idefs[p]].index(names[0])] for p in ps}
            specs.append(dict(domain=domain,layer=layer,difficulty=diff,panel='relative_pool_endpoints',
                              pools=ps,versions=versions,positions=positions,cidx=cidx,inames=names,iidx=ii))

    # Precompute compatible image masks and building-equal weights for each cell.
    spec_states=[];membership=defaultdict(list)
    for si,spec in enumerate(specs):
        ps=spec['pools'];build=np.array([meta.loc[p,'building'] for p in ps]);state={'spec':spec,'kind':{}}
        for kind,source,idxkey,metrics in [('curve',point,'cidx',QMET),('interval',ipoint,'iidx',IVMET)]:
            x={v:np.stack([source[p][v][spec[idxkey][p]] for p in ps]) for v in spec['versions']}
            count_source=point_n if kind=='curve' else ipoint_n
            observations={v:np.stack([count_source[p][v][spec[idxkey][p]] for p in ps]) for v in spec['versions']}
            common=np.logical_and.reduce([np.isfinite(v) for v in x.values()])
            weights={}
            wi=common.astype(float);den=wi.sum(0);wi=np.divide(wi,den,out=np.zeros_like(wi),where=den>0)
            wb=np.zeros_like(wi)
            buildings=sorted(set(build));bcount=np.zeros(common.shape[1:])
            for b in buildings:bcount+=common[build==b].any(0)
            for b in buildings:
                loc=build==b;ct=common[loc].sum(0)
                wb[loc]=np.divide(common[loc],ct*bcount,out=np.zeros_like(wb[loc]),where=(ct*bcount)>0)
            weights={'image_equal':wi,'building_equal':wb}
            accum={}
            for v in spec['versions']:
                for w in weights:accum[(v,w)]=init_agg(a.bootstrap,common.shape[1:])
            state['kind'][kind]=dict(x=x,common=common,observations=observations,weights=weights,accum=accum,build=build,metrics=metrics)
        spec_states.append(state)
        for i,p in enumerate(ps):membership[p].append((si,i))

    # Bootstrap with coupled old/new/focus batches. Indices are shared across k.
    curve_lookup={(r['pool_id'],r['version'],r['k']):i for i,r in enumerate(curve_rows)}
    int_lookup={(r['pool_id'],r['version'],r['interval']):i for i,r in enumerate(interval_rows)}
    comparison_rows=[]
    for pi,p in enumerate(meta.index):
        arrs=raw[p];n=int(meta.loc[p,'pool_n']);m=meta.loc[p].to_dict()
        seed_old=seed_for('old_batch_whole_paths',p,a.seed);seed_new=seed_for('new_batch_whole_paths',p,a.seed)
        io=np.random.default_rng(seed_old).integers(24,size=(a.bootstrap,24))
        inn=np.random.default_rng(seed_new).integers(24,size=(a.bootstrap,24))
        indices={'old24':io,'new24':inn,'pooled48':np.concatenate([io,inn+24],axis=1)}
        seeds.extend([dict(pool_id=p,batch='old24',seed=str(seed_old),B=a.bootstrap),dict(pool_id=p,batch='new24',seed=str(seed_new),B=a.bootstrap)])
        if p in focus_ids:
            seed_extra=seed_for('focus_extra48_whole_paths',p,a.seed)
            ie=np.random.default_rng(seed_extra).integers(48,size=(a.bootstrap,48))
            indices['focus96']=np.concatenate([io,inn+24,ie+48],axis=1)
            seeds.append(dict(pool_id=p,batch='focus_extra48',seed=str(seed_extra),B=a.bootstrap))
        bs={};bis={}
        for version,ix in indices.items():
            aa={c:v[ix] for c,v in arrs[version].items() if c in RAW}
            bs[version]=stats(aa)
            bs[version][:,-1,:]=point[p][version][-1,:]
            bis[version]=interval_stats(aa,bs[version],idefs[p])
            for k in range(1,n+1):
                row=curve_rows[curve_lookup[(p,version,k)]]
                for j,metric in enumerate(QMET):
                    lo,hi,se,valid=boot_summary(bs[version][:,k-1,j])
                    if point_n[p][version][k-1,j]<2 and k!=n:
                        row[metric+'_empirical_degenerate_boot95_low']=lo
                        row[metric+'_empirical_degenerate_boot95_high']=hi
                        lo=hi=se=np.nan
                    row[metric+'_boot95_low']=lo;row[metric+'_boot95_high']=hi
                    row[metric+'_bootse']=se;row[metric+'_boot_valid_draws']=valid
            for ki,(name,ka,kb) in enumerate(idefs[p]):
                if REPAIR_TARGETS is not None:continue
                row=interval_rows[int_lookup[(p,version,name)]]
                for j,metric in enumerate(IVMET):
                    lo,hi,se,valid=boot_summary(bis[version][:,ki,j])
                    if ipoint_n[p][version][ki,j]<2:
                        row[metric+'_empirical_degenerate_boot95_low']=lo
                        row[metric+'_empirical_degenerate_boot95_high']=hi
                        lo=hi=se=np.nan
                    row[metric+'_boot95_low']=lo;row[metric+'_boot95_high']=hi
                    row[metric+'_bootse']=se;row[metric+'_boot_valid_draws']=valid
        for newversion in ['new24','pooled48']+(['focus96'] if p in focus_ids else []):
            for k in range(1,n+1):
                for j,metric in enumerate(QMET):
                    dd=bs[newversion][:,k-1,j]-bs['old24'][:,k-1,j]
                    lo,hi,se,valid=boot_summary(dd)
                    insufficient=(min(point_n[p][newversion][k-1,j],point_n[p]['old24'][k-1,j])<2 and k!=n)
                    if insufficient:lo=hi=se=np.nan
                    comparison_rows.append({**m,'comparison':newversion+'_minus_old24','k':k,'metric':metric,
                                            'old24':point[p]['old24'][k-1,j],newversion:point[p][newversion][k-1,j],
                                            'difference':point[p][newversion][k-1,j]-point[p]['old24'][k-1,j],
                                            'difference_boot95_low':lo,'difference_boot95_high':hi,
                                            'difference_bootse':se,'valid_bootstrap_draws':valid,
                                            'uncertainty_estimable_from_observed_paths':not insufficient})
        for si,pi_in_spec in membership[p]:
            state=spec_states[si];spec=state['spec']
            for kind,boot,idxkey in [('curve',bs,'cidx'),('interval',bis,'iidx')]:
                st=state['kind'][kind];ix=spec[idxkey][p]
                for version in spec['versions']:
                    vals=boot[version][:,ix]
                    for weighting,weights in st['weights'].items():
                        add_agg(st['accum'][(version,weighting)],vals,weights[pi_in_spec])
        if pi%20==0:print('bootstrapped natural pools',pi+1,flush=True)
    curve=pd.DataFrame(curve_rows);ints=pd.DataFrame(interval_rows)
    save(curve,a.out/'NATURAL_POOL_K_BATCH_PRECISION.csv.gz')
    save(ints,a.out/'NATURAL_POOL_INTERVAL_BATCH_PRECISION.csv.gz')
    save(pd.DataFrame(comparison_rows),a.out/'NATURAL_POOL_K_REPLICATION_COMPARISON.csv.gz')
    save(pd.DataFrame(seeds),a.out/'NATURAL_EXACT_BOOTSTRAP_SEEDS.csv')
    if REPAIR_TARGETS is None:export_independent_focus72(raw,meta,focus_ids,curve,a.out)

    summary=[];aggregate_comparisons=[];panel_support=[];building_rows=[]
    for state in spec_states:
        spec=state['spec'];scope={k:spec[k] for k in ['domain','layer','difficulty','panel']}
        ps=spec['pools'];build=np.array([meta.loc[p,'building'] for p in ps]);buildings=sorted(set(build))
        for kind in ['curve','interval']:
            st=state['kind'][kind];x=st['x'];common=st['common'];metrics=st['metrics']
            positions=spec['positions'] if kind=='curve' else spec['inames']
            if not positions:continue
            draws={};points={}
            for v in spec['versions']:
                for weighting,weights in st['weights'].items():
                    points[(v,weighting)]=np.sum(np.where(common,x[v],0)*weights,axis=0)
                    points[(v,weighting)][common.sum(0)==0]=np.nan
                    ac=st['accum'][(v,weighting)]
                    # Do not renormalize onto a different image set when a rare
                    # scoreable image becomes unscoreable in a bootstrap draw.
                    draws[(v,weighting,'path_MC_fixed_images')]=np.divide(ac['sum'],ac['weight'],out=np.full_like(ac['sum'],np.nan),where=ac['weight']>=1-1e-10)
                # Whole-building draws condition on the saved path sample.
                bsum=[];bcount=[];bmean=[]
                for b in buildings:
                    loc=build==b;xx=np.where(common[loc],x[v][loc],np.nan)
                    sm=np.nansum(xx,axis=0);ct=np.isfinite(xx).sum(0)
                    mn=np.divide(sm,ct,out=np.full_like(sm,np.nan),where=ct>0)
                    bsum.append(sm);bcount.append(ct);bmean.append(mn)
                    for i,pos in enumerate(positions):
                        for j,metric in enumerate(metrics):
                            if REPAIR_TARGETS is not None:continue
                            building_rows.append({**scope,'kind':kind,'position':pos,'version':v,'building':b,'metric':metric,
                                                  'estimate':mn[i,j],'observed_common_images':int(ct[i,j]),'available_images':int(loc.sum())})
                seed_b=seed_for('building_fixed_paths',json.dumps({**scope,'kind':kind},sort_keys=True),a.seed)
                rng=np.random.default_rng(seed_b);w=rng.multinomial(len(buildings),np.ones(len(buildings))/len(buildings),size=a.bootstrap)
                sm=np.stack(bsum);ct=np.stack(bcount);bm=np.stack(bmean);shape=sm.shape[1:]
                numerator=w@sm.reshape(len(buildings),-1);denominator=w@ct.reshape(len(buildings),-1)
                draws[(v,'image_equal','building_resampling_fixed_paths')]=np.divide(numerator,denominator,out=np.full_like(numerator,np.nan),where=denominator>0).reshape((a.bootstrap,)+shape)
                numerator=w@np.nan_to_num(bm).reshape(len(buildings),-1);denominator=w@np.isfinite(bm).reshape(len(buildings),-1).astype(float)
                draws[(v,'building_equal','building_resampling_fixed_paths')]=np.divide(numerator,denominator,out=np.full_like(numerator,np.nan),where=denominator>0).reshape((a.bootstrap,)+shape)
            for (v,weighting,resampling),bb in draws.items():
                for i,pos in enumerate(positions):
                    for j,metric in enumerate(metrics):
                        lo,hi,se,valid=boot_summary(bb[:,i,j]);observed=common[:,i,j]
                        bv=sorted(set(build[observed]));xp=x[v][observed,i,j]
                        insufficient=int((observed&(st['observations'][v][:,i,j]<2)).sum())
                        row={**scope,'kind':kind,'position':pos,'version':v,'metric':metric,'weighting':weighting,
                             'resampling':resampling,'estimate':points[(v,weighting)][i,j],'percentile_2_5':lo,'percentile_97_5':hi,
                             'resampling_SE':se,'available_images':len(ps),'common_observed_images':int(observed.sum()),
                             'available_buildings':len(buildings),'common_observed_buildings':len(bv),
                             'positive_common_image_fraction':float((xp>ZERO_TOL).mean()) if len(xp) else np.nan,
                             'negative_common_image_fraction':float((xp < -ZERO_TOL).mean()) if len(xp) else np.nan,
                             'near_zero_common_image_fraction':float((np.abs(xp)<=ZERO_TOL).mean()) if len(xp) else np.nan,
                             'strict_positive_common_image_fraction':float((xp>0).mean()) if len(xp) else np.nan,
                             'strict_negative_common_image_fraction':float((xp<0).mean()) if len(xp) else np.nan,
                             'numerical_zero_tolerance':ZERO_TOL,
                             'valid_bootstrap_draws':valid,'bootstrap_replicates':a.bootstrap,
                             'common_images_with_lt2_metric_observations':insufficient,
                             'support_rule':'same pool/capacity domain; all compared versions have finite metric per cell'}
                        row['selection_uncertainty']='conditional_on_fixed_old_noise_selected_pools' if spec['domain']=='old_noise_focus' else 'no_focus_selection_in_primary_panel'
                        if resampling=='path_MC_fixed_images':
                            den=st['accum'][(v,weighting)]['weight'][:,i,j]
                            row['bootstrap_min_available_normalized_weight']=float(np.min(den))
                            row['bootstrap_missing_image_weight_draws']=int((den<.999999).sum()) if observed.any() else a.bootstrap
                            if insufficient:
                                row['empirical_conditioned_bootstrap_SE']=se
                                row['empirical_conditioned_percentile_2_5']=lo
                                row['empirical_conditioned_percentile_97_5']=hi
                                row['percentile_2_5']=row['percentile_97_5']=row['resampling_SE']=np.nan
                                row['uncertainty_support_status']='not_fully_estimable_single_metric_observation_in_at_least_one_image'
                            else:row['uncertainty_support_status']='estimable_from_observed_paths' if observed.any() else 'no_common_metric_support'
                        summary.append(row)
            for newversion in ['new24','pooled48']+(['focus96'] if 'focus96' in spec['versions'] else []):
                for weighting in ['image_equal','building_equal']:
                    for resampling in ['path_MC_fixed_images','building_resampling_fixed_paths']:
                        db=draws[(newversion,weighting,resampling)]-draws[('old24',weighting,resampling)]
                        for i,pos in enumerate(positions):
                            for j,metric in enumerate(metrics):
                                lo,hi,se,valid=boot_summary(db[:,i,j]);observed=common[:,i,j]
                                delta=x[newversion][observed,i,j]-x['old24'][observed,i,j]
                                insufficient=int((observed&((st['observations'][newversion][:,i,j]<2)|(st['observations']['old24'][:,i,j]<2))).sum())
                                if resampling=='path_MC_fixed_images' and insufficient:lo=hi=se=np.nan
                                aggregate_comparisons.append({**scope,'kind':kind,'position':pos,'metric':metric,
                                    'comparison':newversion+'_minus_old24','weighting':weighting,'resampling':resampling,
                                    'difference':points[(newversion,weighting)][i,j]-points[('old24',weighting)][i,j],
                                    'old24':points[('old24',weighting)][i,j],'new_estimate':points[(newversion,weighting)][i,j],
                                    'difference_95_low':lo,'difference_95_high':hi,'difference_SE':se,
                                    'common_images':int(observed.sum()),'common_buildings':len(set(build[observed])),
                                    'median_image_absolute_difference':np.median(np.abs(delta)) if len(delta) else np.nan,
                                    'p90_image_absolute_difference':np.quantile(np.abs(delta),.9) if len(delta) else np.nan,
                                    'positive_image_difference_fraction':float((delta>ZERO_TOL).mean()) if len(delta) else np.nan,
                                    'negative_image_difference_fraction':float((delta < -ZERO_TOL).mean()) if len(delta) else np.nan,
                                    'near_zero_image_difference_fraction':float((np.abs(delta)<=ZERO_TOL).mean()) if len(delta) else np.nan,
                                    'strict_positive_image_difference_fraction':float((delta>0).mean()) if len(delta) else np.nan,
                                    'strict_negative_image_difference_fraction':float((delta<0).mean()) if len(delta) else np.nan,
                                    'numerical_zero_tolerance':ZERO_TOL,
                                    'common_images_with_lt2_metric_observations_in_either_batch':insufficient,
                                    'valid_bootstrap_draws':valid})
            # Small support key table, not repeated worker/geometry content.
            for i,p in enumerate(ps):
                for j,pos in enumerate(positions):
                    panel_support.append({**scope,'kind':kind,'position':pos,'pool_id':p,'image':meta.loc[p,'image'],
                                          'building':meta.loc[p,'building'],'quality_common_all_versions':bool(common[i,j,0]),
                                          'failure_common_all_versions':bool(common[i,j,7] if kind=='curve' else common[i,j,7])})
    save(pd.DataFrame(summary),a.out/'NATURAL_FIXED_SUPPORT_STABILITY.csv.gz')
    save(pd.DataFrame(aggregate_comparisons),a.out/'NATURAL_FIXED_SUPPORT_BATCH_COMPARISONS.csv.gz')
    save(pd.DataFrame(building_rows),a.out/'NATURAL_BUILDING_BATCH_RESULTS.csv.gz')
    save(pd.DataFrame(panel_support),a.out/'NATURAL_FIXED_PANEL_EXACT_SUPPORT.csv.gz')

    # Accuracy targets are diagnostics, never a criterion for extending budget.
    acc=curve[curve.k.ne(2)].copy()
    acc['mean_MCSE_le1']=acc.Q_mean_MCSE_analytic.le(1)&acc.Q_mean.notna()
    acc['p10_boot95_halfwidth']=(acc.Q_p10_boot95_high-acc.Q_p10_boot95_low)/2
    acc['p10_boot95_halfwidth_le2']=acc.p10_boot95_halfwidth.le(2)&acc.Q_p10.notna()&acc.quality_uncertainty_estimable
    acc['sampled_zero_failures']=acc.failure_paths.eq(0)&acc.nondeferred_attempts.gt(0)
    save(acc[['pool_id','image','building','layer','difficulty','pool_n','version','k','quality_valid_paths',
              'Q_mean_MCSE_analytic','mean_MCSE_le1','p10_boot95_halfwidth','p10_boot95_halfwidth_le2',
              'Q_p10_order95_low','Q_p10_order95_high','sampled_zero_failures','failure_one_sided95_high',
              'mc_exact_full_pool']],a.out/'PRECISION_TARGET_REACH.csv.gz')

    # Independent generation/multiplicity is unchanged; compare exact marginals.
    if a.exact and REPAIR_TARGETS is None:
        exact_needed=set(META+RAW+COMP+['k','team_key','exact_kind'])
        ex=pd.read_csv(a.exact,usecols=lambda c:c in exact_needed,low_memory=False)
        ex=ex[ex.pool_id.isin(pools)].drop_duplicates(['pool_id','k','team_key']).copy()
        for c in RAW+COMP:
            if c not in ex:ex[c]=np.nan
            ex[c]=asnum(ex[c])
        for flag in ['policy_deferred','score_failure_nonpolicy','incomplete_nonpolicy']:
            assert ex[flag].notna().all(),f'exact marginal missing status: {flag}'
        exact_rows=[]
        for (p,k),g in ex.groupby(['pool_id','k']):
            m=meta.loc[p].to_dict();n=int(m['pool_n']);expected=math.comb(n,int(k))
            assert len(g)==expected,(p,k,len(g),expected)
            # Exact finite-population dispersion is ddof=0; retain ddof1 also.
            q=g.B8L2.to_numpy(float);valid=np.isfinite(q)
            deferred=int(g.policy_deferred.eq(1).sum())
            nondeferred=g.policy_deferred.eq(0)
            attempted=int(nondeferred.sum())
            failure_rate=g.loc[nondeferred,'score_failure_nonpolicy'].mean() if attempted else np.nan
            incomplete_rate=g.loc[nondeferred,'incomplete_nonpolicy'].mean() if attempted else np.nan
            point_ex={'Q_mean':np.nanmean(q),'Q_p10':np.nanquantile(q,.1) if valid.any() else np.nan,
                      'Q_sd_population':np.nanstd(q,ddof=0) if valid.any() else np.nan,
                      'Q_sd_ddof1':np.nanstd(q,ddof=1) if valid.sum()>1 else 0.0 if valid.sum() else np.nan,
                      'D10_mean':g.D10.mean(),'floor_turn5_mean':g.floor_turn5_n.mean(),
                      'floor_redundant5_mean':g.floor_redundant5_n.mean(),'nodes_mean':g.nodes.mean(),
                      'failure_rate':failure_rate,'incomplete_rate':incomplete_rate}
            exact_rows.append({**m,'k':int(k),'finite_population_teams':expected,'quality_valid_teams':int(valid.sum()),
                               'actual_failure_teams':int(g.loc[nondeferred,'score_failure_nonpolicy'].sum()),
                               'policy_deferred_teams':deferred,'nondeferred_attempts':attempted,
                               'formal_fusion_attempted':bool(attempted),'exact_complete':True,
                               'marginal_status':'contract_deferred' if not attempted else 'exact_finite_marginal' if valid.any() else 'all_nonpolicy_attempts_unscoreable',
                               'exact_kind':'all_small_pool_subsets' if n<=10 else 'singletons' if k==1 else 'leave_one_out' if k==n-1 else 'full_pool',
                               **point_ex})
        exs=pd.DataFrame(exact_rows)
        save(exs,a.out/'EXACT_FINITE_MARGINAL_STATISTICS.csv')
        export_hybrid48(curve,exs,a.out)
        comparison=[]
        merged=curve.merge(exs,on=['pool_id','k'],suffixes=('','_exact'),validate='many_to_one')
        for r in merged.to_dict('records'):
            for metric in QMET:
                exact_metric='Q_sd_population' if metric=='Q_sd_ddof1' else metric+'_exact'
                truth=r[exact_metric];estimate=r[metric]
                lo=r.get(metric+'_boot95_low',np.nan);hi=r.get(metric+'_boot95_high',np.nan)
                comparison.append({k:r[k] for k in META+['version','k','paths_attempted','quality_valid_paths','unique_teams','exact_kind','finite_population_teams']}|
                                  {'metric':metric,'estimate':estimate,'exact_value':truth,'error':estimate-truth,'absolute_error':abs(estimate-truth),
                                   'bootstrap_95_low':lo,'bootstrap_95_high':hi,
                                   'exact_reference_inside_empirical_bootstrap_interval':bool(lo-1e-10<=truth<=hi+1e-10) if np.isfinite([truth,lo,hi]).all() else np.nan,
                                   'population_SD_convention':'true finite-population ddof0; sample estimate ddof1',
                                   'P10_convention':'NumPy linear on full finite marginal; interval rank targets distribution quantile'})
        save(pd.DataFrame(comparison),a.out/'EXACT_ANCHOR_BATCH_ACCURACY.csv.gz')
    rec={'operation':'independent_random_order_replication_and_finite_marginal_precision',
         'source_commit':'40d0fe62dc62f6f6c12723af10195b7abb7bc9fe',
         'input_paths':{k:str(v) for k,v in vars(a).items() if isinstance(v,Path)},
         'natural_pools':len(meta),'focus_pools':len(focus_ids),'old_prefixes':old_prefix_count,'new_prefixes':new_prefix_count,
         'old_paths_per_pool':24,'balanced_new_paths_per_pool':24,'focus_additional_paths':48,
         'direction_numerical_zero_tolerance':ZERO_TOL,'strict_sign_columns_retained':True,
         'actual_full_interval':'30_to_full in fixed N>=30 includes N=30 pools as zero changes',
         'bootstrap_replicates':a.bootstrap,'master_bootstrap_seed':a.seed,
         'interval_coverage':'pointwise percentile95 per reported statistic; not a simultaneous whole-curve band',
         'resampling':'independent batch whole-path resampling coupled across old/new/pooled versions; separate whole-building resampling',
         'focus_uncertainty':'conditional on the fixed old-noise-selected 53 pools; does not include rerunning pool selection',
         'focus_independent72':'additional point/mean-MCSE description from the 72 genuinely new paths only; no extra bootstrap or fusion',
         'bootstrap_rare_scoreability':'when a common image is unscoreable in a draw, keep whole panel cell missing rather than renormalizing image weights; nonexact single-observation Q uncertainty is unestimable',
         'Q_missing':'NaN; no zero fill; common-image-per-cell paired batch summaries; separate failure all attempts',
         'deferred_k2':'retained, excluded from actual failure denominator; not analyzed as Q',
         'full_pool':'single deterministic team; zero MC error, not independent duplicate teams',
         'new_fusion_in_this_analysis':0,'new_classification':0,'new_GT_or_scoring':0}
    if REPAIR_TARGETS is not None:
        rec['export_repair']=dict(files=sorted(REPAIR_TARGETS),reason='direct gzip streaming produced truncated local exports despite process exit0',
            recovery='replay the same registered 2000 seeds to rebuild only damaged derived outputs; no fusion, no new samples, no change to statistics',
            unaffected_tables='not rewritten')
    final_check=verify_all_tables(a.out)
    atomic_bytes(a.out/'COMPLETE_EOF_READBACK.json',(json.dumps(final_check,ensure_ascii=False,indent=2)+'\n').encode())
    atomic_bytes(a.out/'ATOMIC_EXPORT_RECEIPTS.json',(json.dumps(EXPORT_RECEIPTS,ensure_ascii=False,indent=2)+'\n').encode())
    atomic_bytes(a.out/'NATURAL_ANALYSIS_RECEIPT.json',(json.dumps(rec,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps(rec,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
