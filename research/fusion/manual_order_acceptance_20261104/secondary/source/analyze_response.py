#!/usr/bin/env python3
"""Retrospective per-image sample-size response from frozen path tables.

No fusion, reference, worker exclusion, routing or difficulty changes occur here.
Each input row is one saved random-prefix path observation. Duplicate physical
teams retain their path frequency. Counts of paths, teams, images and buildings
are always separate. Usage: python scripts/analyze_response.py --help
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import warnings

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TOL = 1e-9
QUALITY = ['B8L2', 'D10', 'IoU3D100']
GEOMETRY = ['nodes', 'turns', 'short_turn_edges', 'short_edges_03_h',
            'floor_area_h2', 'height_mean_h', 'S_bottom_deg', 'dir',
            'Hmean', 'Hcenter', 'omission', 'extension']
META = ['pool_id','image','building','condition','domain','target_id',
        'reference_id','reference_version','N','difficulty','difficulty_en']
STATE = ['complete_evaluable','quality_available','geometry_formed']
CONFIG = {
    'analysis_id': 'HOHONET_v21_image_response_20261101',
    'source_commit': 'e1873bfadc1d0e61499809c91fba9dc39c717f83',
    'main_min_k': 3,
    'tail_rule': 'range of every observed integer k from start through actual N',
    'minimum_followup': 'max(5,ceil(0.15*N)) additional workers',
    'near_exhaustion_fraction': .8,
    'small_pool_max_N': 7,
    'quality_tolerances': [1.,2.,3.,5.],
    'sd_tolerances': [.5,1.,2.],
    'rate_tolerances': [.02,.05,.10],
    'minimum_valid_paths': [32,64,128],
    'primary_mean_tolerance': 2.,
    'primary_p10_tolerance': 2.,
    'primary_sd_tolerance': 1.,
    'primary_rate_tolerance': .05,
    'primary_minimum_valid_paths': 64,
    'local_flat_additional_workers': 3,
    'path_jump_quality_cutoffs': [2.,5.,10.],
    'main_SD_ddof': 1,
    'P10': 'linear empirical quantile of finite outputs, retaining path frequency',
    'precision': 'reuse matching 256-path simultaneous Q mean/P10 bands; conservative range bounds',
    'onset_is_retrospective_not_online_stop': True,
    'no_composite_stability_score': True,
}


def as_bool(s):
    """Three-valued boolean; missing does not become failure."""
    if pd.api.types.is_bool_dtype(s):
        return s.astype(float)
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s,errors='coerce').where(lambda x:x.isin([0,1]))
    return s.astype('string').str.lower().map({'true':1.,'false':0.,'1':1.,'0':0.})


def finite_stats(a):
    a=np.asarray(a,dtype=float); a=a[np.isfinite(a)]
    n=len(a)
    return dict(valid_n=n,mean=float(np.mean(a)) if n else np.nan,
      median=float(np.median(a)) if n else np.nan,
      p10=float(np.quantile(a,.1,method='linear')) if n else np.nan,
      p90=float(np.quantile(a,.9,method='linear')) if n else np.nan,
      p10_inverse_cdf=float(np.sort(a)[max(0,math.ceil(.1*n)-1)]) if n else np.nan,
      sd=float(np.std(a,ddof=1)) if n>1 else np.nan,
      sd_population=float(np.std(a,ddof=0)) if n else np.nan,
      minimum=float(np.min(a)) if n else np.nan,
      maximum=float(np.max(a)) if n else np.nan)


def ratio_mcse(values, strata):
    """Delta-method MCSE for conditional mean under fixed stratum path counts.

    Invalid paths contribute zero to the numerator residual, not a zero score.
    This is an approximation, not a confidence interval for a population of rooms.
    """
    x=np.asarray(values,dtype=float); ok=np.isfinite(x); n=int(ok.sum())
    if not n:return np.nan
    mu=float(x[ok].mean()); residual=np.where(ok,x-mu,0.)
    variance=0.
    ss=np.asarray(strata,dtype=str)
    for st in np.unique(ss):
        z=residual[ss==st]
        if len(z)<2:return np.nan
        variance+=len(z)*float(np.var(z,ddof=1))
    return math.sqrt(max(0.,variance))/n


def get_meta(idx, df):
    out={}
    for c in META:
        v=idx.get(c,np.nan)
        if (pd.isna(v) or str(v)=='') and len(df) and c in df:
            vals=df[c].dropna().unique()
            if len(vals):v=vals[0]
        out[c]=v.item() if isinstance(v,np.generic) else v
    out['N']=int(out['N'])
    return out


def prepare_frame(df,meta):
    if not len(df):return df
    required=['k','replicate_id','team_key','B8L2']
    assert all(c in df for c in required), (meta['pool_id'],'missing columns')
    df=df.copy();df['k']=pd.to_numeric(df.k,errors='raise').astype(int)
    assert not df.duplicated(['replicate_id','k']).any(),(meta['pool_id'],'duplicate path/k')
    assert df.k.between(1,meta['N']).all(),(meta['pool_id'],'k outside capacity')
    df['replicate_id']=df.replicate_id.astype(str)
    if 'origin_stratum' not in df:df['origin_stratum']='reported_single_stratum'
    df['origin_stratum']=df.origin_stratum.fillna('unknown').astype(str)
    if 'status_class' not in df:df['status_class']='not_classified'
    df['status_class']=df.status_class.fillna('not_classified').astype(str)
    if 'complete_evaluable' not in df:
        df['complete_evaluable']=df.get('complete_output',np.nan)
    for c in ['complete_evaluable','geometry_formed']:
        if c not in df:df[c]=np.nan
        df[c]=as_bool(df[c])
    for c in QUALITY+GEOMETRY:
        if c not in df:df[c]=np.nan
        df[c]=pd.to_numeric(df[c],errors='coerce')
    # Availability is stated explicitly; does not infer the cause of a missing Q.
    df['quality_available']=np.isfinite(df.B8L2).astype(float)
    df['all_three_quality_available']=np.isfinite(df[QUALITY]).all(axis=1).astype(float)
    # Raw original confirmation flags are not fusion outcomes.
    df.loc[df.k.eq(1),['complete_evaluable','geometry_formed']]=np.nan
    # Primary geometric descriptors use a formed/evaluable output. Candidate nodes
    # remain separately available below for diagnosing failed outputs.
    df['nodes_candidate']=df.nodes
    gate=df.complete_evaluable.eq(1)
    if 'complete_floor_evaluable' in df:
        floor_gate=as_bool(df.complete_floor_evaluable).eq(1)
    else:floor_gate=gate
    for c in ['nodes','turns','short_turn_edges','short_edges_03_h','floor_area_h2',
              'S_bottom_deg','dir','omission','extension']:
        df.loc[(df.k>=3)&(~floor_gate),c]=np.nan
    for c in ['height_mean_h','Hmean','Hcenter']:
        df.loc[(df.k>=3)&(~gate),c]=np.nan
    return df


def per_k_statistics(df,meta):
    rows=[]; status=[]
    for k,g in df.groupby('k',sort=True):
        row={**meta,'k':int(k),'k_fraction':k/meta['N'],
             'path_rows':len(g),'unique_teams':g.team_key.nunique(),
             'stage':'raw_original' if k==1 else 'two_person_supplement' if k==2 else 'fusion_main',
             'full_pool':bool(k==meta['N']),
             'full_pool_unique_team_n':int(g.team_key.nunique()) if k==meta['N'] else np.nan}
        if k==meta['N']:assert g.team_key.nunique()==1,(meta['pool_id'],'multiple full teams')
        for c in QUALITY+GEOMETRY+['nodes_candidate']:
            s=finite_stats(g[c]);row.update({c+'_'+name:value for name,value in s.items()})
            row[c+'_mean_MCSE_stratified']=ratio_mcse(g[c],g.origin_stratum)
            ok=np.isfinite(g[c]);row[c+'_unique_valid_teams']=g.loc[ok,'team_key'].nunique()
        for c in STATE+['all_three_quality_available']:
            a=pd.to_numeric(g[c],errors='coerce');valid=a.notna()
            row[c+'_valid_n']=int(valid.sum())
            row[c+'_rate']=float(a[valid].mean()) if valid.any() else np.nan
            row[c+'_rate_MCSE_stratified']=ratio_mcse(a,g.origin_stratum)
        for label,n in g.status_class.value_counts(dropna=False).items():
            status.append({**meta,'k':int(k),'k_fraction':k/meta['N'],
              'status_class':str(label),'path_n':int(n),'denominator_paths':len(g),'rate':n/len(g)})
        rows.append(row)
    return pd.DataFrame(rows),pd.DataFrame(status)


def pair_design(N):
    out=defaultdict(set)
    for step in [1,2]:
        for k in range(3,N-step+1):out[(k,k+step)].add('adjacent_'+str(step))
    fixed=[(3,6),(6,10),(10,14),(10,15),(14,20),(15,20),(20,25),
           (20,30),(25,30),(30,35),(3,10),(10,20),(20,35),(3,20)]
    for a,b in fixed:
        if b<=N:out[(a,b)].add(f'fixed_{a}_to_{b}')
    for a in [3,6,10,14,15,20,25,30,35]:
        if a<N:out[(a,N)].add(f'fixed_{a}_to_full')
    if N>=8:out[(N-5,N)].add('own_last5_to_full')
    if N>=3:
        for frac in [.25,.5,.75]:
            a=max(3,min(N-1,int(math.ceil(frac*N))));
            if a<N:out[(a,N)].add(f'fraction_{str(frac).replace(".","p")}_to_full')
    return out


def paired_response(df,meta,save_events):
    summary=[];events=[]
    value_cols=QUALITY+GEOMETRY+['nodes_candidate']+STATE
    groups={int(k):g.set_index('replicate_id',drop=False) for k,g in df.groupby('k')}
    for (ka,kb),labels in sorted(pair_design(meta['N']).items()):
        if ka not in groups or kb not in groups:continue
        aa,bb=groups[ka],groups[kb]
        ids=aa.index.intersection(bb.index)
        a,b=aa.loc[ids],bb.loc[ids]
        assert len(a)==len(b)
        common={**meta,'k_from':ka,'k_to':kb,'k_from_fraction':ka/meta['N'],
          'k_to_fraction':kb/meta['N'],'pair_rows':len(ids),
          'from_only_path_ids':len(aa)-len(ids),'to_only_path_ids':len(bb)-len(ids),
          'interval_labels':'|'.join(sorted(labels)),
          'same_team_rows':int((a.team_key.to_numpy()==b.team_key.to_numpy()).sum()),
          'unique_team_pairs':len(set(zip(a.team_key,b.team_key))),
          'to_actual_full':kb==meta['N']}
        if save_events:
            e=pd.DataFrame({'pool_id':meta['pool_id'],'replicate_id':ids,
              'origin_stratum':a.origin_stratum.to_numpy(),'k_from':ka,'k_to':kb,
              'N':meta['N'],'interval_labels':common['interval_labels'],
              'from_team_key':a.team_key.to_numpy(),'to_team_key':b.team_key.to_numpy(),
              'from_status':a.status_class.to_numpy(),'to_status':b.status_class.to_numpy()})
        for c in value_cols:
            x=a[c].to_numpy(dtype=float);y=b[c].to_numpy(dtype=float)
            vx=np.isfinite(x);vy=np.isfinite(y);both=vx&vy
            delta=np.where(both,y-x,np.nan);v=delta[both];av=np.abs(v)
            row={**common,'metric':c,'both_valid_n':int(both.sum()),
                'from_only_valid_n':int((vx&~vy).sum()),'to_only_valid_n':int((~vx&vy).sum()),
                'neither_valid_n':int((~vx&~vy).sum()),
                'paired_from_mean':float(x[both].mean()) if both.any() else np.nan,
                'paired_to_mean':float(y[both].mean()) if both.any() else np.nan,
                'from_marginal_mean':float(x[vx].mean()) if vx.any() else np.nan,
                'to_marginal_mean':float(y[vy].mean()) if vy.any() else np.nan,
                'mean_delta':float(v.mean()) if len(v) else np.nan,
                'mean_abs_delta':float(av.mean()) if len(v) else np.nan,
                'median_delta':float(np.median(v)) if len(v) else np.nan,
                'p10_delta':float(np.quantile(v,.1)) if len(v) else np.nan,
                'p90_delta':float(np.quantile(v,.9)) if len(v) else np.nan,
                'p90_abs_delta':float(np.quantile(av,.9)) if len(v) else np.nan,
                'maximum_abs_delta':float(av.max()) if len(v) else np.nan,
                'positive_paths':int((v>TOL).sum()),'negative_paths':int((v<-TOL).sum()),
                'near_zero_paths':int((np.abs(v)<=TOL).sum()),
                'mean_delta_MCSE_stratified':ratio_mcse(delta,a.origin_stratum)}
            if c in QUALITY:
                for cutoff in CONFIG['path_jump_quality_cutoffs']:
                    row[f'absolute_jump_gt{int(cutoff)}_rate']=float((av>cutoff).mean()) if len(v) else np.nan
                    row[f'gain_gt{int(cutoff)}_rate']=float((v>cutoff).mean()) if len(v) else np.nan
                    row[f'loss_gt{int(cutoff)}_rate']=float((v<-cutoff).mean()) if len(v) else np.nan
            summary.append(row)
            if save_events:
                e[c+'_delta']=delta
                if c in QUALITY+['nodes','turns']+STATE:
                    e[c+'_from']=x;e[c+'_to']=y
        if save_events:events.append(e)
    return pd.DataFrame(summary),pd.concat(events,ignore_index=True) if events else pd.DataFrame()


def specifications():
    specs=[]
    for q in QUALITY:
        for st in ['mean','p10','sd']:
            specs.append(dict(metric=f'{q}_{st}',count=f'{q}_valid_n',
              tolerance=1. if st=='sd' else 2.,
              grid=CONFIG['sd_tolerances'] if st=='sd' else CONFIG['quality_tolerances'],
              units='quality_points',kind=st))
    for metric in ['complete_evaluable','quality_available','geometry_formed']:
        specs.append(dict(metric=metric+'_rate',count=metric+'_valid_n',tolerance=.05,
          grid=CONFIG['rate_tolerances'],units='proportion',kind='rate'))
    return specs


def load_bands(root,extra_paths=()):
    base=root/'source/repo/research/data/releases/v2.1/natural_results/NATURAL_CURVE_BANDS.csv.gz'
    paths=[base]+[Path(p) for p in extra_paths];out={}
    for path in paths:
        if not path.exists():continue
        d=pd.read_csv(path)
        if not {'pool_id','cohort','metric','band_scope','k'}.issubset(d.columns):continue
        d=d[d.cohort.isin(['pooled256','new_space256']) & d.band_scope.eq('all_random_prefix_k') & d.metric.isin(['Q_mean','Q_p10'])]
        for row in d.to_dict('records'):
            met={'Q_mean':'B8L2_mean','Q_p10':'B8L2_p10'}[row['metric']]
            key=(row['pool_id'],met,int(row['k']))
            val=dict(low=row.get('max_studentized_low'),high=row.get('max_studentized_high'),
              estimate=row.get('estimate'),cohort=row['cohort'],source=str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
              complete_bootstrap_draws=row.get('complete_bootstrap_draws'))
            if key in out:
                # Duplicate source packages may repeat the same record; not independent evidence.
                for c in ['low','high','estimate']:
                    av,bv=out[key][c],val[c]
                    assert (pd.isna(av) and pd.isna(bv)) or np.isclose(av,bv,rtol=0,atol=1e-8),(key,c)
            out[key]=val
    return out


def tail_analysis(curves,meta,bands):
    N=meta['N'];h=max(5,int(math.ceil(.15*N)))
    full_k=np.arange(3,N+1,dtype=int)
    s=curves.set_index('k').reindex(full_k) if len(curves) else pd.DataFrame(index=full_k)
    envelopes=[];onsets=[];transient=[];band_checks=[]
    for spec in specifications():
        metric,count=spec['metric'],spec['count']
        x=pd.to_numeric(s.get(metric,pd.Series(np.nan,index=full_k)),errors='coerce').to_numpy(float)
        nv=pd.to_numeric(s.get(count,pd.Series(0,index=full_k)),errors='coerce').fillna(0).to_numpy(float)
        l=np.full(len(x),np.nan);u=np.full(len(x),np.nan)
        for i,k in enumerate(full_k):
            b=bands.get((meta['pool_id'],metric,int(k)))
            if b and np.isfinite(x[i]) and pd.notna(b['estimate']):
                match=bool(np.isclose(x[i],b['estimate'],rtol=0,atol=1e-7))
                band_checks.append({**meta,'metric':metric,'k':int(k),
                  'curve_estimate':x[i],'band_estimate':b['estimate'],'estimate_matches':match,
                  'cohort':b['cohort'],'source':b['source'],
                  'complete_bootstrap_draws':b['complete_bootstrap_draws']})
                if match:l[i],u[i]=b['low'],b['high']
            # A full-pool metric is known from one deterministic team, not 256 independent teams.
            if k==N and np.isfinite(x[i]) and len(curves) and int(s.iloc[i].get('unique_teams',0))==1:
                if metric in ['B8L2_mean','B8L2_p10']:
                    l[i]=u[i]=x[i]
        spec_rows=[]
        for i,k in enumerate(full_k):
            tail=x[i:]; ok=np.isfinite(tail);finite=tail[ok]
            allgood=bool(ok.all());bs=np.isfinite(l[i:])&np.isfinite(u[i:])
            brange_low=max(0.,float(np.max(l[i:])-np.min(u[i:]))) if bs.all() and len(bs) else np.nan
            brange_high=float(np.max(u[i:])-np.min(l[i:])) if bs.all() and len(bs) else np.nan
            row={**meta,'metric':metric,'units':spec['units'],'k':int(k),'k_fraction':k/N,
              'observed_value':x[i],'tail_finite_k':int(ok.sum()),'tail_expected_k':len(tail),
              'tail_missing_k':int((~ok).sum()),'tail_min_valid_paths':float(np.min(nv[i:])) if len(tail) else 0,
              'tail_range':float(np.ptp(finite)) if len(finite) else np.nan,
              'tail_min':float(finite.min()) if len(finite) else np.nan,
              'tail_max':float(finite.max()) if len(finite) else np.nan,
              'tail_mean':float(finite.mean()) if len(finite) else np.nan,
              'actual_full_value':x[-1] if len(x) else np.nan,
              'subsequent_workers_observed':N-k,'minimum_required_followup':h,
              'adequate_followup':bool(N-k>=h),'near_exhaustion':bool(k/N>=.8),
              'all_future_metric_values_finite':allgood,
              'MC_range_lower':brange_low,'MC_range_upper':brange_high,
              'MC_full_tail_band_available':bool(bs.all() and len(bs)),
              'primary_tolerance':spec['tolerance'],
              'primary_support_valid':bool(allgood and np.min(nv[i:])>=64),
              'primary_small_range_observed':bool(allgood and np.min(nv[i:])>=64 and np.ptp(finite)<=spec['tolerance']+TOL)}
            row['primary_MC_class']='unavailable'
            if np.isfinite(brange_high):
                row['primary_MC_class']='upper_bound_within_tolerance' if brange_high<=spec['tolerance']+TOL else 'lower_bound_exceeds_tolerance' if brange_low>spec['tolerance']+TOL else 'band_crosses_tolerance'
            envelopes.append(row);spec_rows.append(row)
        for tol in spec['grid']:
          for min_valid in CONFIG['minimum_valid_paths']:
            candidates=[r for r in spec_rows if r['all_future_metric_values_finite'] and r['tail_min_valid_paths']>=min_valid and r['tail_range']<=tol+TOL]
            supported=[r for r in candidates if r['adequate_followup'] and N>=8]
            first=candidates[0] if candidates else None
            chosen=supported[0] if supported else None
            good=[r for r in spec_rows if r['adequate_followup'] and r['all_future_metric_values_finite'] and r['tail_min_valid_paths']>=min_valid]
            if chosen:reason='observed_small_full_tail_with_adequate_followup'
            elif N==0:reason='no_members'
            elif N<3:reason='no_main_fusion_capacity'
            elif N<8:reason='short_pool_N_lt8_description_only'
            elif not len(x) or not np.isfinite(x[-1]):reason='actual_full_metric_unavailable'
            elif not good:reason='future_metric_or_path_support_insufficient'
            elif first:reason='small_range_only_with_short_remaining_followup'
            else:reason='no_small_range_over_observed_remaining_pool'
            onset={**meta,'metric':metric,'units':spec['units'],'tolerance':tol,'minimum_valid_paths':min_valid,
              'primary_rule':bool(tol==spec['tolerance'] and min_valid==64),
              'minimum_required_followup':h,'onset_k':chosen['k'] if chosen else np.nan,
              'onset_k_fraction':chosen['k_fraction'] if chosen else np.nan,
              'first_small_range_without_followup_gate':first['k'] if first else np.nan,
              'near_exhaustion_onset':chosen['near_exhaustion'] if chosen else np.nan,
              'onset_tail_range':chosen['tail_range'] if chosen else np.nan,
              'remaining_workers':N-chosen['k'] if chosen else np.nan,
              'reason':reason,'actual_full_value':x[-1] if len(x) else np.nan,
              'onset_MC_range_lower':chosen['MC_range_lower'] if chosen else np.nan,
              'onset_MC_range_upper':chosen['MC_range_upper'] if chosen else np.nan,
              'onset_MC_class':'not_applicable_without_onset'}
            if chosen:
                lo,hi=chosen['MC_range_lower'],chosen['MC_range_upper']
                onset['onset_MC_class']='unavailable' if not np.isfinite(hi) else 'upper_bound_within_tolerance' if hi<=tol+TOL else 'lower_bound_exceeds_tolerance' if lo>tol+TOL else 'band_crosses_tolerance'
                if spec['kind']=='rate':
                    onset['tail_rate_level']='consistently_high_ge95pct' if chosen['tail_min']>=.95 else 'consistently_low_le5pct' if chosen['tail_max']<=.05 else 'persistent_mixed_rate'
            onsets.append(onset)
        # A short flat run that is later left is explicitly indexed; overlapping
        # windows remain descriptive, never counted as independent images.
        tol=spec['tolerance'];w=CONFIG['local_flat_additional_workers']
        for i,k in enumerate(full_k):
            end=i+w
            if end>=len(x)-1:continue
            local=x[i:end+1]
            if not np.isfinite(local).all() or np.min(nv[i:end+1])<64 or np.ptp(local)>tol+TOL:continue
            later=None;reason=None
            for j in range(end+1,len(x)):
                if not np.isfinite(x[j]) or nv[j]<64:
                    later=j;reason='later_metric_unavailable_or_under_supported';break
                if np.ptp(x[i:j+1])>tol+TOL:
                    later=j;reason='later_range_exceeds_tolerance';break
            if later is not None:
                transient.append({**meta,'metric':metric,'tolerance':tol,'start_k':int(k),
                   'local_end_k':int(full_k[end]),'first_later_change_k':int(full_k[later]),
                   'local_range':float(np.ptp(local)),'local_start_value':x[i],
                   'local_end_value':x[end],'later_value':x[later],
                   'change_reason':reason})
    return tuple(pd.DataFrame(x) for x in [envelopes,onsets,transient,band_checks])


def write_csv(df,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    compression=dict(method='gzip',compresslevel=4,mtime=0) if str(path).endswith('.gz') else None
    df.to_csv(temporary,index=False,encoding='utf-8-sig',compression=compression)
    temporary.replace(path)


def json_clean(value):
    if isinstance(value,dict):return {k:json_clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [json_clean(v) for v in value]
    if isinstance(value,np.generic):return json_clean(value.item())
    if isinstance(value,float) and not np.isfinite(value):return None
    return value


def input_file(row,root):
    for c in ['absolute_file','absolute_path','normalized_file','path']:
        if c in row and pd.notna(row[c]) and str(row[c]):
            p=Path(str(row[c]));p=p if p.is_absolute() else root/p
            if p.exists():return p
    raise FileNotFoundError(f"No normalized table for {row.get('pool_id')}")


def process_pool(row,root,out,bands,save_events=True,resume=True):
    source=input_file(row,root)
    pool_id=str(row['pool_id']);tag=re.sub(r'[^A-Za-z0-9_.-]','_',pool_id)
    dest=out/'by_pool'/tag;marker=dest/'COMPLETION.json'
    src_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    config_sha=hashlib.sha256(json.dumps(CONFIG,sort_keys=True).encode()).hexdigest()
    code_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if resume and marker.exists():
        old=json.loads(marker.read_text())
        if old.get('source_sha256')==src_sha and old.get('config_sha256')==config_sha and old.get('code_sha256')==code_sha and old.get('save_events')==save_events:
            return old
    df=pd.read_csv(source,low_memory=False)
    meta=get_meta(row,df);df=prepare_frame(df,meta)
    dest.mkdir(parents=True,exist_ok=True)
    curve,status=per_k_statistics(df,meta) if len(df) else (pd.DataFrame(),pd.DataFrame())
    changes,events=paired_response(df,meta,save_events) if len(df) else (pd.DataFrame(),pd.DataFrame())
    env,onsets,transient,bcheck=tail_analysis(curve,meta,bands)
    outputs={'POOL_K_STATISTICS.csv.gz':curve,'STATUS_BY_K.csv.gz':status,
      'PATH_CHANGE_SUMMARY.csv.gz':changes,'TAIL_ENVELOPES.csv.gz':env,
      'PLATEAU_SENSITIVITY.csv.gz':onsets,'TRANSIENT_FLAT_THEN_CHANGE.csv.gz':transient,
      'REUSED_BAND_ESTIMATE_CHECKS.csv.gz':bcheck}
    if save_events:outputs['PATH_CHANGE_EVENTS.csv.gz']=events
    for name,data in outputs.items():write_csv(data,dest/name)
    counts_by_k=df.groupby('k').size().to_dict() if len(df) else {}
    qconflict=int(((df.k>=3)&np.isfinite(df.B8L2)&df.complete_evaluable.eq(0)).sum()) if len(df) else 0
    result={**meta,'source_file':str(source.relative_to(root)) if source.is_relative_to(root) else str(source),
      'source_sha256':src_sha,'config_sha256':config_sha,'code_sha256':code_sha,'save_events':save_events,
      'path_rows':len(df),'replicate_ids':df.replicate_id.nunique() if len(df) else 0,
      'rows_by_k':{str(k):int(v) for k,v in counts_by_k.items()},
      'duplicate_path_k':int(df.duplicated(['replicate_id','k']).sum()) if len(df) else 0,
      'finite_Q_but_not_complete_main_rows':qconflict,
      'matching_band_rows':int(bcheck.estimate_matches.sum()) if len(bcheck) else 0,
      'mismatching_band_rows':int((~bcheck.estimate_matches).sum()) if len(bcheck) else 0,
      'new_fusion':False,'new_quality_scores':False,'output_dir':str(dest.relative_to(root)),
      'output_rows':{k:len(v) for k,v in outputs.items()}}
    # Disagreements are retained in a visible check, never repaired by dropping rows.
    result=json_clean(result)
    temporary=marker.with_name(marker.name+'.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    temporary.replace(marker)
    return result


def combine_pool_outputs(results,out,root):
    names=['POOL_K_STATISTICS.csv.gz','STATUS_BY_K.csv.gz','PATH_CHANGE_SUMMARY.csv.gz',
      'TAIL_ENVELOPES.csv.gz','PLATEAU_SENSITIVITY.csv.gz','TRANSIENT_FLAT_THEN_CHANGE.csv.gz',
      'REUSED_BAND_ESTIMATE_CHECKS.csv.gz']
    combined={}
    for name in names:
        parts=[]
        for r in results:
            p=root/r['output_dir']/name
            try:d=pd.read_csv(p,low_memory=False)
            except pd.errors.EmptyDataError:continue
            if len(d):parts.append(d)
        d=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
        write_csv(d,out/name);combined[name]=d
    onsets=combined['PLATEAU_SENSITIVITY.csv.gz']
    if len(onsets):
        primary=onsets[onsets.primary_rule.eq(True)].copy()
        write_csv(primary,out/'PRIMARY_SMALL_CHANGE_ONSETS.csv')
        rows=[]
        for keys,g in primary.groupby(['domain','metric'],dropna=False):
            v=g.onset_k.dropna();cap=g[g.N>=8];found=g[g.onset_k.notna()]
            rows.append(dict(domain=keys[0],metric=keys[1],pools=len(g),images=g.image.nunique(),
                buildings=g.building.nunique(),adequate_N_pools=len(cap),
                observed_onset_pools=len(v),observed_onset_images=found.image.nunique(),
                onset_median=float(v.median()) if len(v) else np.nan,
                onset_p10=float(v.quantile(.1)) if len(v) else np.nan,
                onset_p90=float(v.quantile(.9)) if len(v) else np.nan,
                near_exhaustion_onset_pools=int(found.near_exhaustion_onset.eq(True).sum()),
                no_onset_reasons=json.dumps(g[g.onset_k.isna()].reason.value_counts().to_dict(),ensure_ascii=False)))
        write_csv(pd.DataFrame(rows),out/'PRIMARY_ONSET_DOMAIN_SUMMARY.csv')
    # Fixed intervals only; each target-domain stays separate. Extra targets retain
    # both pool-level and image-first means so multiple targets cannot inflate image support.
    ch=combined['PATH_CHANGE_SUMMARY.csv.gz']
    if len(ch):
        ch=ch[ch.interval_labels.str.contains('fixed_',na=False)].copy()
        ch['window']=ch.interval_labels.str.split('|');ch=ch.explode('window')
        ch=ch[ch.window.str.startswith('fixed_')]
        rows=[]
        for keys,g in ch.groupby(['domain','window','metric'],dropna=False):
            valid=g[g.mean_delta.notna()];im=valid.groupby(['image','building']).mean_delta.mean().reset_index()
            b=im.groupby('building').mean_delta.mean()
            a=im.mean_delta.to_numpy(float)
            rows.append(dict(domain=keys[0],window=keys[1],metric=keys[2],capacity_pools=len(g),
              capacity_images=g.image.nunique(),capacity_buildings=g.building.nunique(),
              valid_pools=len(valid),valid_images=len(im),valid_buildings=len(b),
              mean_delta_pool_equal=valid.mean_delta.mean(),mean_delta_image_equal=im.mean_delta.mean(),
              mean_delta_building_equal=b.mean(),mean_abs_path_delta_pool_equal=valid.mean_abs_delta.mean(),
              positive_images=int((a>TOL).sum()),negative_images=int((a<-TOL).sum()),near_zero_images=int((np.abs(a)<=TOL).sum()),
              image_delta_p10=float(np.quantile(a,.1)) if len(a) else np.nan,
              image_delta_median=float(np.median(a)) if len(a) else np.nan,
              image_delta_p90=float(np.quantile(a,.9)) if len(a) else np.nan,
              paired_valid_path_rows=int(g.both_valid_n.sum()),
              unavailable_endpoint_path_rows=int((g.from_only_valid_n+g.to_only_valid_n+g.neither_valid_n).sum())))
        write_csv(pd.DataFrame(rows),out/'FIXED_WINDOW_DOMAIN_SUMMARY.csv')
    return {name:len(df) for name,df in combined.items()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--input-index',type=Path,action='append')
    ap.add_argument('--output',type=Path)
    ap.add_argument('--domains',help='Comma-separated domain names')
    ap.add_argument('--pool-id',action='append')
    ap.add_argument('--limit',type=int)
    ap.add_argument('--no-path-events',action='store_true')
    ap.add_argument('--no-resume',action='store_true')
    ap.add_argument('--bands',type=Path,action='append',default=[])
    args=ap.parse_args();root=args.root.resolve()
    out=args.output or root/'stage03_response';out=out if out.is_absolute() else root/out
    indexes=args.input_index or [root/'stage02_normalized/manual/POOL_INDEX.csv',root/'stage02_normalized/doorway/POOL_INDEX.csv']
    ii=[]
    for p in indexes:
        p=p if p.is_absolute() else root/p
        if not p.exists():raise FileNotFoundError(p)
        d=pd.read_csv(p);d['normalized_index_source']=str(p);ii.append(d)
    index=pd.concat(ii,ignore_index=True)
    if args.domains:index=index[index.domain.isin(args.domains.split(','))]
    if args.pool_id:index=index[index.pool_id.isin(args.pool_id)]
    if args.limit:index=index.head(args.limit)
    assert not index.pool_id.duplicated().any(),'Duplicate pools across normalized indexes'
    out.mkdir(parents=True,exist_ok=True)
    (out/'ANALYSIS_CONFIG.json').write_text(json.dumps(CONFIG,ensure_ascii=False,indent=2))
    bands=load_bands(root,args.bands);results=[]
    for i,row in enumerate(index.to_dict('records')):
        r=process_pool(row,root,out,bands,not args.no_path_events,not args.no_resume)
        results.append(r)
        print(json.dumps({'done':i+1,'total':len(index),'pool_id':r['pool_id'],'N':r['N'],'rows':r['path_rows']},ensure_ascii=False),flush=True)
    combined=combine_pool_outputs(results,out,root)
    write_csv(pd.DataFrame(results),out/'ANALYSIS_POOL_INDEX.csv')
    final=dict(pools=len(results),images=len(set(r['image'] for r in results)),
      input_path_rows=sum(r['path_rows'] for r in results),new_fusion=False,new_quality_scores=False,
      sum_finite_Q_not_complete=sum(r['finite_Q_but_not_complete_main_rows'] for r in results),
      band_estimate_mismatches=sum(r['mismatching_band_rows'] for r in results),
      output_rows=combined,all_input_indexes=[str(x) for x in indexes])
    (out/'ANALYSIS_COMPLETION.json').write_text(json.dumps(final,ensure_ascii=False,indent=2))
    print(json.dumps(final,ensure_ascii=False),flush=True)


if __name__=='__main__':
    warnings.filterwarnings('ignore',message='invalid value encountered in cast',category=RuntimeWarning)
    main()
