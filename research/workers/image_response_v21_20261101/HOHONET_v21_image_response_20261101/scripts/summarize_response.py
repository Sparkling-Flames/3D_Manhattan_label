#!/usr/bin/env python3
"""Fixed-image response panels and transparent descriptive stratification.

Consumes stage03_response tables only; does not create teams, fuse, or rescore.
All marginal contrasts require the same image/target at both k values. Building
means are averages of image-first averages. Path counts never become image N.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import analyze_response as ar

ROOT=Path(__file__).resolve().parents[1]
FIELDS=['pool_id','image','building','domain','target_id','reference_id','reference_version','N','difficulty','difficulty_en']
MEASURES={f'{q}_{s}':(f'{q}_valid_n',1. if s=='sd' else 2.) for q in ar.QUALITY for s in ['mean','p10','sd']}
MEASURES.update({'complete_evaluable_rate':('complete_evaluable_valid_n',.05),
                 'quality_available_rate':('quality_available_valid_n',.05),
                 'geometry_formed_rate':('geometry_formed_valid_n',.05)})
INTERVALS=[(3,6),(6,10),(10,14),(10,15),(14,20),(15,20),(20,25),(25,30),(30,35),(3,10),(10,20),(20,30),(20,35),(3,20)]

def summarize_values(g, col, tol=None):
    valid=g[np.isfinite(pd.to_numeric(g[col],errors='coerce'))].copy()
    im=valid.groupby(['image','building'],dropna=False)[col].mean().reset_index()
    bb=im.groupby('building',dropna=False)[col].mean()
    a=im[col].to_numpy(float)
    out=dict(capacity_pools=g.pool_id.nunique(),capacity_images=g.image.nunique(),capacity_buildings=g.building.nunique(),
      valid_pools=valid.pool_id.nunique(),valid_images=len(im),valid_buildings=len(bb),
      mean_pool_equal=valid[col].mean(),mean_image_equal=im[col].mean(),mean_building_equal=bb.mean(),
      mean_absolute_image_value=np.abs(a).mean() if len(a) else np.nan,
      image_p10=np.quantile(a,.1) if len(a) else np.nan,image_median=np.median(a) if len(a) else np.nan,
      image_p90=np.quantile(a,.9) if len(a) else np.nan,
      positive_images=int((a>ar.TOL).sum()),negative_images=int((a<-ar.TOL).sum()),zero_images=int((np.abs(a)<=ar.TOL).sum()))
    if tol is not None:
        out.update(tolerance=tol,greater_than_tolerance_images=int((a>tol+ar.TOL).sum()),
          below_negative_tolerance_images=int((a<-tol-ar.TOL).sum()),within_tolerance_images=int((np.abs(a)<=tol+ar.TOL).sum()))
    if len(a) and np.abs(a).sum()>0:
        out['signed_change_cancellation_fraction']=1-abs(a.mean())/np.abs(a).mean()
        out['top_decile_abs_change_share']=np.sort(np.abs(a))[-max(1,int(math.ceil(.1*len(a)))):].sum()/np.abs(a).sum()
    else:out.update(signed_change_cancellation_fraction=np.nan,top_decile_abs_change_share=np.nan)
    return out

def strata(index):
    yield 'all','all',index
    if 'difficulty_en' in index:
        for v,g in index[index.difficulty_en.notna()].groupby('difficulty_en'):yield 'frozen_difficulty',str(v),g
    # conditional_short_span is a continuous angle (zero denotes absence of a
    # short edge), not a category; its continuous analysis is kept separately.
    for col in ['has_short']:
        if col in index:
            for v,g in index[index[col].notna()].groupby(col):yield col,str(int(v)),g
    if 'ref_turn5' in index:
        z=index[index.ref_turn5.notna()].copy()
        z['reference_turn_band']=pd.cut(z.ref_turn5,bins=[-np.inf,4,6,8,np.inf],labels=['at_most_4','5_to_6','7_to_8','9_or_more'])
        for v,g in z.groupby('reference_turn_band',observed=True):yield 'reference_turn_band',str(v),g

def panel_definitions(index,mode):
    panels=[]
    for dom,g in index.groupby('domain'):
        for horizon in [6,10,14,20,25,30,35]:
            h=g[g.N>=horizon]
            if len(h):panels.append((f'{dom}__capacity_ge{horizon}',dom,horizon,h.pool_id.tolist()))
        panels.append((f'{dom}__maximum_support',dom,None,g.pool_id.tolist()))
    if mode=='doorway':
        before=index[index.domain.eq('doorway_before')].set_index('image')
        after=index[index.domain.eq('doorway_after')].set_index('image')
        for horizon in [8,14,20,25,30,35]:
            images=before[before.N>=horizon].index.intersection(after[after.N>=horizon].index)
            if len(images):
                for dom in ['doorway_before','doorway_after']:
                    ids=index[index.domain.eq(dom)&index.image.isin(images)].pool_id.tolist()
                    panels.append((f'before_after_shared{horizon}',dom,horizon,ids))
    return panels

def per_k_panels(curves,index,panels):
    rows=[];membership=[]
    for panel,domain,horizon,ids in panels:
        ii=index[index.pool_id.isin(ids)]
        for r in ii[FIELDS].to_dict('records'):membership.append(dict(panel=panel,observed_through_k=horizon,**r))
        dd=curves[curves.pool_id.isin(ids)&curves.k.ge(3)]
        if horizon is not None:dd=dd[dd.k<=horizon]
        for dimension,level,ss in strata(ii):
            sub=dd[dd.pool_id.isin(ss.pool_id)]
            for k,g in sub.groupby('k'):
                for metric,(count,tol) in MEASURES.items():
                    h=g.copy();h.loc[h[count].lt(64),metric]=np.nan
                    rows.append(dict(panel=panel,domain=domain,fixed_panel_N=ss.pool_id.nunique(),
                      fixed_panel_images=ss.image.nunique(),fixed_panel_buildings=ss.building.nunique(),
                      fixed_observation_horizon=horizon,stratum_dimension=dimension,stratum=level,k=int(k),
                      k_fraction_min=g.k_fraction.min(),k_fraction_median=g.k_fraction.median(),k_fraction_max=g.k_fraction.max(),
                      metric=metric,valid_path_rows=int(g.loc[g[count]>=64,count].sum()),**summarize_values(h,metric)))
    return pd.DataFrame(rows),pd.DataFrame(membership)

def marginal_changes(curves,index):
    rows=[]
    for pid,g in curves[curves.k>=3].groupby('pool_id'):
        gg=g.set_index('k');meta=index[index.pool_id.eq(pid)].iloc[0]
        N=int(meta.N);windows={f'fixed_{a}_to_{b}':(a,b) for a,b in INTERVALS if b<=N}
        for k in [3,6,10,14,15,20,25,30,35]:
            if k<N:windows[f'fixed_{k}_to_full']=(k,N)
        if N>=8:windows['own_last5_to_full']=(N-5,N)
        for frac in [.25,.5,.75]:
            k=max(3,int(math.ceil(frac*N)))
            if k<N:windows[f'fraction_{frac}_to_full']=(k,N)
        for window,(a,b) in windows.items():
            if a not in gg.index or b not in gg.index:continue
            aa,bb=gg.loc[a],gg.loc[b]
            for metric,(count,tol) in MEASURES.items():
                valid=bool(aa[count]>=64 and bb[count]>=64 and np.isfinite(aa[metric]) and np.isfinite(bb[metric]))
                rows.append({**meta[FIELDS].to_dict(),'window':window,'k_from':a,'k_to':b,'k_from_fraction':a/N,'k_to_fraction':b/N,
                  'metric':metric,'tolerance':tol,'from_value':aa[metric],'to_value':bb[metric],
                  'from_valid_paths':int(aa[count]),'to_valid_paths':int(bb[count]),'paired_image_metric_valid':valid,
                  'delta':bb[metric]-aa[metric] if valid else np.nan,'abs_delta':abs(bb[metric]-aa[metric]) if valid else np.nan})
    return pd.DataFrame(rows)

def contrast_summaries(changes,index,panels):
    rows=[]
    for panel,domain,horizon,ids in panels:
        ii=index[index.pool_id.isin(ids)];dd=changes[changes.pool_id.isin(ids)]
        if horizon is not None:dd=dd[(dd.k_to<=horizon)&~dd.window.str.contains('full')]
        for dimension,level,ss in strata(ii):
            sub=dd[dd.pool_id.isin(ss.pool_id)]
            for (window,metric),g in sub.groupby(['window','metric']):
                rows.append(dict(panel=panel,domain=domain,stratum_dimension=dimension,stratum=level,
                  fixed_panel_images=ss.image.nunique(),fixed_panel_buildings=ss.building.nunique(),
                  window=window,metric=metric,**summarize_values(g,'delta',float(g.tolerance.iloc[0]))))
    return pd.DataFrame(rows)

def onset_strata(onsets,index):
    rows=[]
    for dom,ii in index.groupby('domain'):
        for dim,level,ss in strata(ii):
            dd=onsets[onsets.pool_id.isin(ss.pool_id)]
            for metric,g in dd.groupby('metric'):
                cap=g[g.N>=8];found=g[g.onset_k.notna()];x=found.onset_k.to_numpy(float)
                rows.append(dict(domain=dom,stratum_dimension=dim,stratum=level,metric=metric,
                  pools=len(g),images=g.image.nunique(),buildings=g.building.nunique(),capacity_ge3_pools=int(g.N.ge(3).sum()),
                  adequate_N_ge8_pools=len(cap),full_metric_available_pools=int(g.actual_full_value.notna().sum()),
                  observed_onset_pools=len(found),observed_onset_images=found.image.nunique(),observed_onset_buildings=found.building.nunique(),
                  onset_median=np.median(x) if len(x) else np.nan,onset_p10=np.quantile(x,.1) if len(x) else np.nan,
                  onset_p90=np.quantile(x,.9) if len(x) else np.nan,onset_fraction_median=found.onset_k_fraction.median(),
                  onsets_at_or_before_6=int(found.onset_k.le(6).sum()),onsets_at_or_before_10=int(found.onset_k.le(10).sum()),
                  onsets_at_or_before_15=int(found.onset_k.le(15).sum()),onsets_at_or_before_20=int(found.onset_k.le(20).sum()),
                  onsets_at_or_before_30=int(found.onset_k.le(30).sum()),near_exhaustion_onsets=int(found.near_exhaustion_onset.eq(True).sum()),
                  MC_upper_bound_within_tolerance=int(found.onset_MC_class.eq('upper_bound_within_tolerance').sum()),
                  MC_band_crosses_tolerance=int(found.onset_MC_class.eq('band_crosses_tolerance').sum()),
                  no_onset_reasons=json.dumps(g[g.onset_k.isna()].reason.value_counts().to_dict(),ensure_ascii=False)))
    return pd.DataFrame(rows)

def truncated_common_tail(curves,index,panels):
    rows=[]
    for panel,domain,horizon,ids in panels:
        if not panel.startswith('before_after_shared') or horizon!=14:continue
        for pid in ids:
            meta=index[index.pool_id.eq(pid)].iloc[0].to_dict();actualN=int(meta['N']);meta['N']=horizon
            c=curves[curves.pool_id.eq(pid)&curves.k.between(3,horizon)]
            env,onsets,transient,bcheck=ar.tail_analysis(c,meta,{})
            for r in onsets[onsets.primary_rule].to_dict('records'):
                r['actual_pool_N']=actualN;r['observed_horizon_k']=horizon;r['tail_is_actual_full_pool']=False
                r['onset_fraction_of_actual_pool']=r['onset_k']/actualN if pd.notna(r['onset_k']) else np.nan
                r['panel']=panel;r['reason']=r['reason'].replace('full_tail','tail_to_14').replace('actual_full','horizon_14')
                r['value_at_observed_horizon']=r.pop('actual_full_value');r['N']=actualN
                rows.append(r)
    return pd.DataFrame(rows)

def screening_contrasts(curves,index,panels):
    rows=[]
    for horizon in [8,14,20,25,30,35]:
        name=f'before_after_shared{horizon}'
        matches=[p for p in panels if p[0]==name]
        if len(matches)!=2:continue
        ids=sum([p[3] for p in matches],[]);dd=curves[curves.pool_id.isin(ids)&curves.k.between(3,horizon)]
        for (image,k),g in dd.groupby(['image','k']):
            if len(g)!=2:continue
            a=g[g.domain.eq('doorway_before')].iloc[0];b=g[g.domain.eq('doorway_after')].iloc[0]
            for metric,(count,tol) in MEASURES.items():
                valid=a[count]>=64 and b[count]>=64 and np.isfinite(a[metric]) and np.isfinite(b[metric])
                rows.append(dict(panel=name,image=image,building=a.building,pool_id=a.pool_id+'|'+b.pool_id,k=k,
                  metric=metric,tolerance=tol,before_N=a.N,after_N=b.N,before_pool_id=a.pool_id,after_pool_id=b.pool_id,
                  before_reference=a.reference_id,after_reference=b.reference_id,reference_id_equal=a.reference_id==b.reference_id,
                  before_value=a[metric],after_value=b[metric],before_valid_paths=a[count],after_valid_paths=b[count],
                  delta_after_minus_before=b[metric]-a[metric] if valid else np.nan))
    df=pd.DataFrame(rows);summary=[]
    for (panel,k,metric),g in df.groupby(['panel','k','metric']):
        summary.append(dict(panel=panel,k=k,metric=metric,reference_ids_equal=bool(g.reference_id_equal.all()),
          **summarize_values(g,'delta_after_minus_before',float(g.tolerance.iloc[0]))))
    return df,pd.DataFrame(summary)

def late_path_jumps(changes,index):
    data=changes[changes.interval_labels.str.contains('adjacent_',na=False)].copy()
    data=data[data.metric.isin(ar.QUALITY)]
    data['step']=data.k_to-data.k_from
    for start in [10,14,20,25,30]:
        pass
    rows=[]
    for dom,ii in index.groupby('domain'):
        for start in [10,14,20,25,30]:
            dd=data[data.domain.eq(dom)&data.k_from.ge(start)]
            for (pid,metric,step),g in dd.groupby(['pool_id','metric','step']):
                v=g[g.both_valid_n>=64]
                row=g.iloc[0]
                rows.append(dict(pool_id=pid,image=row.image,building=row.building,domain=dom,N=row.N,
                  late_start_k=start,metric=metric,step=step,attempted_transition_cells=len(g),valid_transition_cells=len(v),
                  total_paired_path_transitions=int(v.both_valid_n.sum()),
                  max_mean_absolute_path_delta=v.mean_abs_delta.max(),max_absolute_paired_mean_delta=v.mean_delta.abs().max(),
                  max_probability_jump_gt5=v.absolute_jump_gt5_rate.max(),max_probability_jump_gt10=v.absolute_jump_gt10_rate.max(),
                  worst_transition_k_from=v.loc[v.absolute_jump_gt5_rate.idxmax(),'k_from'] if len(v) else np.nan,
                  worst_transition_k_to=v.loc[v.absolute_jump_gt5_rate.idxmax(),'k_to'] if len(v) else np.nan,
                  pooled_transition_jump_gt5_probability=(v.absolute_jump_gt5_rate*v.both_valid_n).sum()/v.both_valid_n.sum() if v.both_valid_n.sum() else np.nan,
                  note='transition opportunities; do not interpret summed rows as independent paths or images'))
    return pd.DataFrame(rows)

def facts(mode,index,curve_summary,contrasts,onset_summary,screen,truncated,late,transient):
    selected_onset=onset_summary[(onset_summary.stratum_dimension.isin(['all','frozen_difficulty']))&onset_summary.metric.isin(['B8L2_mean','B8L2_p10','B8L2_sd','complete_evaluable_rate'])]
    selected_contrast=contrasts[contrasts.stratum_dimension.eq('all')&contrasts.metric.isin(['B8L2_mean','B8L2_p10','B8L2_sd','complete_evaluable_rate'])&contrasts.window.isin(['fixed_3_to_6','fixed_6_to_10','fixed_10_to_14','fixed_10_to_20','fixed_20_to_30','fixed_30_to_35','fixed_20_to_full','own_last5_to_full'])]
    out={'mode':mode,'path_population':'frozen saved random-prefix paths, duplicate physical teams retained',
      'minimum_valid_paths':64,'quality_onsets':'all observed future k; minimum additional workers max(5,ceil(.15*N)); N<8 description only',
      'state_label':'complete_evaluable = complete and scoreable, not pure fusion formation',
      'domains':index.groupby('domain').agg(pools=('pool_id','size'),images=('image','nunique'),buildings=('building','nunique'),minimum_N=('N','min'),maximum_N=('N','max')).reset_index().to_dict('records'),
      'onsets':selected_onset.to_dict('records'),'fixed_panel_contrasts':selected_contrast.to_dict('records')}
    if mode=='doorway':
        out['screening_shared14']=screen[screen.panel.eq('before_after_shared14')&screen.k.isin([3,6,10,14])&screen.metric.isin(['B8L2_mean','B8L2_p10','B8L2_sd','complete_evaluable_rate'])].to_dict('records')
        rr=[]
        for (dom,metric),g in truncated.groupby(['domain','metric']):
            if metric not in ['B8L2_mean','B8L2_p10','B8L2_sd','complete_evaluable_rate']:continue
            rr.append(dict(domain=dom,metric=metric,pools=len(g),observed_onsets=int(g.onset_k.notna().sum()),median_onset=g.onset_k.median(),observed_through_k=14,minimum_additional_followup=5))
        out['truncated_shared14_onsets']=rr
    out['late_jump_support']=late[late.metric.eq('B8L2')&late.step.eq(1)].groupby(['domain','late_start_k']).agg(
      capacity_pools=('pool_id','size'),valid_pools=('valid_transition_cells',lambda x:int((x>0).sum())),
      pools_with_at_least_one_10pct_gt5_transition=('max_probability_jump_gt5',lambda x:int((x>=.1).sum())),
      pools_with_at_least_one_25pct_gt5_transition=('max_probability_jump_gt5',lambda x:int((x>=.25).sum()))).reset_index().to_dict('records')
    if len(transient):
        out['transient_flat_then_later_change']=transient[transient.metric.eq('B8L2_mean')].groupby(['domain','change_reason']).agg(images=('image','nunique'),pools=('pool_id','nunique'),overlapping_windows=('pool_id','size')).reset_index().to_dict('records')
    return ar.json_clean(out)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--mode',choices=['manual','doorway'],required=True)
    ap.add_argument('--root',type=Path,default=ROOT);args=ap.parse_args();root=args.root.resolve();mode=args.mode
    src=root/'stage03_response'/mode;out=root/'stage07_summary'/mode;out.mkdir(parents=True,exist_ok=True)
    index=pd.read_csv(root/'stage02_normalized'/mode/'POOL_INDEX.csv')
    for c in FIELDS:
        if c not in index:index[c]=np.nan
    curves=pd.read_csv(src/'POOL_K_STATISTICS.csv.gz');onsets=pd.read_csv(src/'PRIMARY_SMALL_CHANGE_ONSETS.csv')
    path=pd.read_csv(src/'PATH_CHANGE_SUMMARY.csv.gz');transient=pd.read_csv(src/'TRANSIENT_FLAT_THEN_CHANGE.csv.gz')
    panels=panel_definitions(index,mode)
    stats,members=per_k_panels(curves,index,panels);ar.write_csv(stats,out/'FIXED_PANEL_CURVES.csv.gz');ar.write_csv(members,out/'FIXED_PANEL_MEMBERS.csv')
    individual=marginal_changes(curves,index);ar.write_csv(individual,out/'PER_IMAGE_MARGINAL_CHANGES.csv.gz')
    contrast=contrast_summaries(individual,index,panels);ar.write_csv(contrast,out/'FIXED_PANEL_CHANGE_SUMMARY.csv.gz')
    onset=onset_strata(onsets,index);ar.write_csv(onset,out/'ONSET_STRATA.csv')
    late=late_path_jumps(path,index);ar.write_csv(late,out/'LATE_PATH_JUMP_SENSITIVITY.csv.gz')
    screen=pd.DataFrame();truncated=pd.DataFrame()
    if mode=='doorway':
        screen_rows,screen=screening_contrasts(curves,index,panels)
        ar.write_csv(screen_rows,out/'SCREENING_FIXED_PANEL_IMAGE_CONTRASTS.csv.gz');ar.write_csv(screen,out/'SCREENING_FIXED_PANEL_SUMMARY.csv')
        truncated=truncated_common_tail(curves,index,panels);ar.write_csv(truncated,out/'COMMON_HORIZON14_SMALL_CHANGE_ONSETS.csv')
    ff=facts(mode,index,stats,contrast,onset,screen,truncated,late,transient)
    (out/'RESULT_FACTS.json').write_text(json.dumps(ff,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({'mode':mode,'pools':len(index),'curve_summary_rows':len(stats),'image_marginal_rows':len(individual),'contrast_summary_rows':len(contrast),'output':str(out)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
