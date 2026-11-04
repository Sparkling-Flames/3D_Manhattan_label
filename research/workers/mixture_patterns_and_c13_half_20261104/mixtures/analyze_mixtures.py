#!/usr/bin/env python3
"""Explore existing current-class coalitions and finite team configurations.

No new teams, fits, fusion or quality scores. Every contrast is computed from
saved values; unavailable Q remains missing. Run from any working directory.
"""
from __future__ import annotations
from pathlib import Path
from itertools import combinations
import hashlib,json,math,sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
CUR='research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030'
OLD='research/workers/personnel_v21_reselection_20261029'
AC='research/workers/personnel_ac_v21_20261030/stage05_sensitivity'
PRIOR='research/workers/current_class_interpretation_20261104'
HEAD='48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
METHODS=['TARGET_DSTRUCT_K3','RFUSE_GEOM_K2','OPPJOINT_K3','OPPJOINT_K4']
GEOM_METRICS=['B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter',
    'omission','extension','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n',
    'geometry_area_h2','height_mean_h','ref_node_recall_5','ref_edge_recall_5',
    'failure','connection_available','log_recorded_time','recorded_time_total_seconds']
SOURCES=[];CHECKS={};META=None

def read(path,**kwargs):
    p=Path(path);p=p if p.is_absolute() else ROOT/p
    SOURCES.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_commit=HEAD))
    return pd.read_csv(p,low_memory=False,**kwargs)

def save(d,name):
    target=HERE/name
    temporary=target.with_name(target.name+'.writing')
    d.to_csv(temporary,index=False,encoding='utf-8-sig',float_format='%.14g',
        compression='gzip' if name.endswith('.gz') else None)
    temporary.replace(target)

def class_tuple(s):
    if isinstance(s,(tuple,list)):return tuple(s)
    return tuple(sorted(str(s).split('|')))

def counts(s,k):
    z={a:int(b) for a,b in (v.split(':') for v in str(s).split('|'))}
    return tuple(z.get('C'+str(i),0) for i in range(1,k+1))

def current_meta():
    d=read(CUR+'/POOL_TARGET_CONDITIONS.csv')
    assert not d.pool_id.duplicated().any()
    purpose=read('research/statistics/room_type_similarity_scoping_20261027/IMAGE_TYPE_INDEX.csv')
    assert not purpose.image_code.duplicated().any()
    d=d.merge(purpose[['image_code','room_type_display','room_type_source']],left_on='image',right_on='image_code',how='left',validate='many_to_one')
    d['purpose']=d.room_type_display.fillna('未记录')
    d['reference_shape']=np.where(d.ref_turn5<=4,'four_turn_reference','more_than_four_turn_reference')
    d['short_wall_reference']=np.where(d.ref_short_edges>0,'has_short_walls','no_short_walls')
    keep=['pool_id','image','image_id','building','condition','scope','pool_n','official_difficulty',
        'purpose','room_type_source','ref_turn5','ref_short_edges','ref_H','structural_condition',
        'reference_shape','short_wall_reference','reference_id','reference_version']
    d=d[keep].copy();save(d,'POOL_SCENE_DIFFICULTY_INDEX.csv')
    return d

def attach(d):
    meta_cols=['pool_id','official_difficulty','purpose','room_type_source','ref_turn5','ref_short_edges',
        'ref_H','structural_condition','reference_shape','short_wall_reference']
    # All strata use current official metadata, replacing historical grade copies.
    d=d.drop(columns=[c for c in meta_cols if c!='pool_id' and c in d],errors='ignore')
    z=d.merge(META[meta_cols],on='pool_id',how='left',validate='many_to_one')
    assert z.official_difficulty.notna().all(),z.loc[z.official_difficulty.isna(),'pool_id'].tolist()[:10]
    return z

def describe(s,value='effect',unit='Q_points'):
    raw=pd.to_numeric(s[value],errors='coerce').to_numpy(dtype=float);ok=np.isfinite(raw);x=raw[ok]
    if not len(x):return dict(valid_images=0,buildings=0,image_mean=np.nan,building_mean=np.nan)
    image=s.image.to_numpy()[ok];assert len(set(image))==len(image)
    buildings=s.building.to_numpy()[ok];code,unique=pd.factorize(buildings)
    bcount=np.bincount(code);bsum=np.bincount(code,weights=x);by=bsum/bcount
    leave=((x.sum()-bsum)/(len(x)-bcount)).tolist() if len(by)>1 else []
    eps=1e-9
    quantiles=np.quantile(x,[.1,.5,.9])
    result=dict(registered_images=len(set(s.image)),valid_images=len(x),buildings=len(by),
        image_mean=x.mean(),image_median=quantiles[1],image_p10=quantiles[0],image_p90=quantiles[2],
        image_min=x.min(),image_max=x.max(),mean_absolute=np.abs(x).mean(),
        positive_images=int((x>eps).sum()),negative_images=int((x< -eps).sum()),zero_images=int((np.abs(x)<=eps).sum()),
        positive_fraction=float((x>eps).mean()),building_mean=by.mean(),
        positive_buildings=int((by>eps).sum()),negative_buildings=int((by< -eps).sum()),
        leave_one_building_image_mean_min=min(leave) if leave else np.nan,
        leave_one_building_image_mean_max=max(leave) if leave else np.nan,units=unit)
    if unit=='Q_points':
        result.update(below_minus_0_5=int((x<-.5).sum()),between_minus_0_5_plus_0_5=int(((x>=-.5)&(x<=.5)).sum()),above_plus_0_5=int((x>.5).sum()))
    if unit=='log_team_recorded_time':result['geometric_time_ratio']=math.exp(result['image_mean'])
    return result

def strata(frame,keys,metrics,unit_map=None,include_cross=False):
    rows=[];unit_map=unit_map or {}
    axes=['ALL','official_difficulty','purpose','structural_condition','reference_shape']
    if include_cross:axes+=['purpose_x_difficulty']
    for key,g in frame.groupby(keys,dropna=False,sort=False):
        base=dict(zip(keys,key if isinstance(key,tuple) else (key,)))
        for axis in axes:
            if axis=='ALL':groups=[('ALL',g)]
            elif axis=='purpose_x_difficulty':groups=g.groupby(['purpose','official_difficulty'],dropna=False)
            else:groups=g.groupby(axis,dropna=False)
            for val,s in groups:
                for metric in metrics:
                    if metric not in s:continue
                    vals=s[metric]
                    if not pd.to_numeric(vals,errors='coerce').notna().any():continue
                    d=describe(s,metric,unit_map.get(metric,'Q_points' if metric in ['effect','B8L2','Q_effect'] else metric))
                    rows.append(dict(**base,axis=axis,stratum=' | '.join(map(str,val)) if isinstance(val,tuple) else str(val),metric=metric,**d))
    return pd.DataFrame(rows)

def dstruct_alliances():
    d=read(HERE/'inputs/DSTRUCT_ALLIANCE_RESULTS_ASSISTED.csv.gz')
    d=d[d.version.eq('updated')&d.scope.eq('primary')&d.condition.eq('manual')].copy()
    lab=read(PRIOR+'/basis/WORKER_LABELS_ALL_LOBO.csv.gz')
    lab=lab[lab.method.eq('TARGET_DSTRUCT_K3')&lab.heldout_building.ne('ALL')].set_index(['heldout_building','worker_id'])
    checks=0
    for r in d[~d.unknown_background_included].itertuples():
        cl=set(r.classes.split('|'))
        workers=r.members.split('|') if pd.notna(r.members) else []
        assert len(workers)==r.n
        for worker in workers:
            l=lab.loc[(r.building,worker)];assert l['class_id'] in cl and bool(l.known);checks+=1
    CHECKS['DSTRUCT_current_alliance_member_label_checks']=checks
    no=d[~d.unknown_background_included].copy()
    assert not no.duplicated(['pool_id','classes']).any()
    no=attach(no);no['method']='TARGET_DSTRUCT_K3';save(no,'DSTRUCT_CURRENT_ALLIANCE_ENDPOINTS.csv.gz')
    metrics=['B8L2','D10','IoU3D100','fusion_turn_n','fusion_short_turn_edges',
        'boundary_loss','direction_loss','height_loss','omission','extension']
    pairs=[];supports=[];full=[]
    for pool,g in no.groupby('pool_id',sort=False):
        index={r.classes:r for r in g.itertuples()}
        for ca,cb in combinations(sorted(index,key=lambda c:(len(c.split('|')),c)),2):
            a,b=index[ca],index[cb]
            aQ=pd.notna(a.B8L2);bQ=pd.notna(b.B8L2)
            kind='class_addition' if set(ca.split('|'))<set(cb.split('|')) else 'alternative_coalition'
            r=dict(method='TARGET_DSTRUCT_K3',pool_id=pool,image=a.image,building=a.building,
                from_classes=ca,to_classes=cb,comparison=ca+' -> '+cb,kind=kind,n_from=a.n,n_to=b.n,
                Q_from=a.B8L2,Q_to=b.B8L2,from_team_key=a.team_key,to_team_key=b.team_key,
                Q_from_available=int(aQ),Q_to_available=int(bQ),Q_availability_change=int(bQ)-int(aQ),
                new_Q_available=int(bQ and not aQ),lost_Q_available=int(aQ and not bQ),
                reference_id=a.reference_id,reference_version=a.reference_version,
                endpoint_version='existing_accepted_fixed_coordinate_assisted; primary_unhit')
            assert a.reference_id==b.reference_id and a.reference_version==b.reference_version
            for metric in metrics:r[metric]=getattr(b,metric)-getattr(a,metric)
            pairs.append(r)
        available_classes=set().union(*(set(c.split('|')) for c in index))
        whole='|'.join(sorted(available_classes));allrow=index[whole]
        pure=g[g.classes.str.count(r'\|').eq(0)&g.B8L2.notna()]
        if len(pure) and pd.notna(allrow.B8L2):
            best=pure.sort_values(['B8L2','classes'],ascending=[False,True]).iloc[0]
            full.append(dict(method='TARGET_DSTRUCT_K3',pool_id=pool,image=allrow.image,building=allrow.building,
                comparison='all_classified_minus_best_scoreable_pure',all_classes=whole,best_pure_class=best.classes,
                n_all=allrow.n,n_pure=best.n,Q_all=allrow.B8L2,Q_best_pure=best.B8L2,
                effect=allrow.B8L2-best.B8L2,selection='posthoc_best_pure_descriptive_only'))
    pairs=attach(pd.DataFrame(pairs));save(pairs,'DSTRUCT_ALLIANCE_IMAGE_CONTRASTS.csv.gz')
    key=['method','from_classes','to_classes','kind']
    summary=strata(pairs,key,metrics+['Q_availability_change'],include_cross=True)
    save(summary,'DSTRUCT_ALLIANCE_STRATA.csv')
    support=pairs.groupby(key).agg(registered_images=('image','nunique'),from_Q_images=('Q_from_available','sum'),
        to_Q_images=('Q_to_available','sum'),newly_evaluable_images=('new_Q_available','sum'),lost_evaluable_images=('lost_Q_available','sum'),
        common_Q_images=('B8L2','count'),n_from_median=('n_from','median'),n_to_median=('n_to','median')).reset_index()
    save(support,'DSTRUCT_ALLIANCE_SUPPORT.csv')
    full=attach(pd.DataFrame(full));save(full,'DSTRUCT_ALL_CLASSIFIED_VS_BEST_PURE_IMAGES.csv')
    save(strata(full,['method','comparison'],['effect'],include_cross=True),'DSTRUCT_ALL_CLASSIFIED_VS_BEST_PURE_STRATA.csv')
    CHECKS['DSTRUCT_full_vs_best_pure_images']=len(full)
    CHECKS['DSTRUCT_full_vs_best_pure_mean']=float(full.effect.mean())
    assert len(full)==205 and abs(full.effect.mean()-(-6.051))<.001
    # Prespecified seven-coalition common-Q comparison; no posthoc best subset.
    all7=['C1','C2','C3','C1|C2','C1|C3','C2|C3','C1|C2|C3']
    complete=no.pivot(index='pool_id',columns='classes',values='B8L2').reindex(columns=all7).dropna().index
    common=no[no.pool_id.isin(complete)].copy();save(common,'DSTRUCT_SEVEN_COALITIONS_COMMON_Q.csv')
    save(strata(common,['method','classes'],metrics),'DSTRUCT_SEVEN_COALITIONS_COMMON_Q_STRATA.csv')
    CHECKS['DSTRUCT_seven_coalitions_common_Q_images']=len(complete)
    # Distinguish actual all-members endpoints where an unknown-class background exists.
    extras=[]
    for pool,g in d.groupby('pool_id'):
        if not g.unknown_background_included.any():continue
        classes='|'.join(sorted(set().union(*(set(s.split('|')) for s in g.classes))))
        z=g[g.classes.eq(classes)]
        if len(z)!=2:continue
        a=z[~z.unknown_background_included].iloc[0];b=z[z.unknown_background_included].iloc[0]
        extras.append(dict(pool_id=pool,image=a.image,building=a.building,n_classified=a.n,n_actual_all=b.n,
            Q_classified=a.B8L2,Q_actual_all=b.B8L2,Q_effect=b.B8L2-a.B8L2,
            classified_members=a.members,actual_all_members=b.members))
    save(pd.DataFrame(extras),'DSTRUCT_CLASSIFIED_VS_ACTUAL_ALL_MEMBERS.csv')
    return pairs,summary,no

def config_path(method):
    prefix=OLD+'/additional_delivery/packages/03B_03/composition/primary_manual45/by_method/' if method.startswith('OPP') else CUR+'/composition/primary/by_method/'
    return prefix+method+'/CONFIGURATION_DISTRIBUTIONS.csv.gz'

def configurations(reuse_pairs=False):
    all_pairs=[];chains=[];member=[];panel_aggregates=[]
    for method in ([] if reuse_pairs else METHODS):
        d=read(config_path(method));d=d[d.support.eq('method_known')&d.metric.isin(GEOM_METRICS)].copy()
        k=int(method[-1]);d['counts']=d.class_counts.map(lambda s:counts(s,k))
        assert d.apply(lambda r:sum(r.counts)==r.n,axis=1).all()
        d=attach(d)
        # Use the saved complete configuration means; condition on fixed total n,
        # same 12-person candidate panel and its unchanged background.
        pairs=[]
        for (panel,metric,ts),g in d.groupby(['panel_id','metric','time_source'],dropna=False,sort=False):
            available={r.counts:r for r in g.itertuples()}
            for count,a in available.items():
                for src,tgt in combinations(range(k),2):
                    if count[src]<=0:continue
                    other=list(count);other[src]-=1;other[tgt]+=1;b=available.get(tuple(other))
                    if b is None:continue
                    if not(pd.notna(a.mean) and pd.notna(b.mean)):continue
                    pairs.append(dict(method=method,panel_id=panel,pool_id=a.pool_id,image=a.image,building=a.building,
                        source_domain=a.source_domain,n=a.n,metric=metric,time_source=ts,
                        from_class='C'+str(src+1),to_class='C'+str(tgt+1),
                        from_counts=a.class_counts,to_counts=b.class_counts,
                        value_from=a.mean,value_to=b.mean,effect=b.mean-a.mean,
                        teams_from=a.teams,teams_to=b.teams,valid_from=a.valid_teams,valid_to=b.valid_teams,
                        both_configurations_fully_observed=bool(a.teams==a.valid_teams and b.teams==b.valid_teams),
                        mean_within_sd=(a.sd+b.sd)/2,
                        max_within_p05_p95_width=max(a.p95-a.p05,b.p95-b.p05)))
            if metric=='B8L2':
                for src,tgt in combinations(range(k),2):
                    buckets={}
                    for ct,r in available.items():
                        other=tuple(v for i,v in enumerate(ct) if i not in [src,tgt])
                        if pd.notna(r.mean):buckets.setdefault(other,[]).append(r)
                    for other,rs in buckets.items():
                        if len(rs)<2:continue
                        rs=sorted(rs,key=lambda r:r.counts[tgt]);x=np.array([r.counts[tgt] for r in rs]);y=np.array([r.mean for r in rs]);dd=np.diff(y)
                        if not(np.diff(x)==1).all():continue
                        base=rs[0]
                        chains.append(dict(method=method,panel_id=panel,pool_id=base.pool_id,image=base.image,building=base.building,
                            source_domain=base.source_domain,n=base.n,from_class='C'+str(src+1),to_class='C'+str(tgt+1),
                            other_class_counts=str(other),steps=len(dd),count_low=int(x[0]),count_high=int(x[-1]),
                            Q_low=y[0],Q_high=y[-1],Q_net=y[-1]-y[0],mean_step=dd.mean(),
                            positive_steps=int((dd>1e-9).sum()),negative_steps=int((dd< -1e-9).sum()),
                            zero_steps=int((abs(dd)<=1e-9).sum()),max_drop=float(max(0,-dd.min())),
                            max_increase=float(max(0,dd.max())),
                            nondecreasing=bool((dd>=-1e-9).all()),nonincreasing=bool((dd<=1e-9).all()),
                            no_drop_above_0_5=bool((dd>=-.5).all()),
                            both_directions=bool((dd>1e-9).any() and (dd< -1e-9).any()),
                            fully_observed=all(r.teams==r.valid_teams for r in rs),
                            Q_sequence='|'.join(f'{v:.12g}' for v in y),target_count_sequence='|'.join(map(str,x))))
        pairs=pd.DataFrame(pairs);all_pairs.append(pairs)
        q=d[d.metric.eq('B8L2')].copy();q['within_p05_p95_width']=q.p95-q.p05
        member.append(q[['method','panel_id','pool_id','image','building','n','source_domain','official_difficulty','purpose','structural_condition','reference_shape','class_counts','teams','valid_teams','mean','sd','p05','p95','within_p05_p95_width','member_variation_estimable']])
    if reuse_pairs:
        pairs=pd.read_csv(HERE/'FIXED_N_ADJACENT_CONFIGURATION_PAIRS.csv.gz',low_memory=False)
        chains=pd.read_csv(HERE/'FIXED_N_MONOTONICITY_CHAINS.csv.gz',low_memory=False)
        member=pd.read_csv(HERE/'SAME_CONFIGURATION_MEMBER_DISTRIBUTIONS.csv.gz',low_memory=False)
        for method in METHODS:
            p=ROOT/config_path(method)
            SOURCES.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_commit=HEAD))
    else:
        pairs=attach(pd.concat(all_pairs,ignore_index=True));save(pairs,'FIXED_N_ADJACENT_CONFIGURATION_PAIRS.csv.gz')
        chains=attach(pd.DataFrame(chains));save(chains,'FIXED_N_MONOTONICITY_CHAINS.csv.gz')
        member=pd.concat(member,ignore_index=True);save(member,'SAME_CONFIGURATION_MEMBER_DISTRIBUTIONS.csv.gz')
    # Each source domain is retained separately; ALL_domains averages panels,
    # not teams, so heavily represented configurations cannot dominate an image.
    summaries=[];images=[];pans=[]
    for support,p in [('available_configurations',pairs),('fully_observed_configurations',pairs[pairs.both_configurations_fully_observed])]:
        for domain in ['ALL_domains']+sorted(p.source_domain.unique().tolist()):
            x=p if domain=='ALL_domains' else p[p.source_domain.eq(domain)]
            keys=['method','panel_id','pool_id','image','building','n','metric','time_source','from_class','to_class']
            z=x.groupby(keys,dropna=False).agg(effect=('effect','mean'),adjacent_pairs=('effect','size'),
                positive_pair_fraction=('effect',lambda a:float((a>1e-9).mean())),
                max_pair_abs_effect=('effect',lambda a:float(a.abs().max())),
                within_sd_mean=('mean_within_sd','mean')).reset_index()
            z['support']=support;z['domain']=domain;pans.append(z)
            for n_slice in ['ALL_n']+list(sorted(z.n.unique())):
                a=z if n_slice=='ALL_n' else z[z.n.eq(n_slice)]
                ikeys=['method','metric','time_source','from_class','to_class','pool_id','image','building']
                v=a.groupby(ikeys,dropna=False).agg(effect=('effect','mean'),panels=('panel_id','nunique'),adjacent_pairs=('adjacent_pairs','sum'),within_sd_mean=('within_sd_mean','mean')).reset_index()
                v=v.groupby(['method','metric','time_source','from_class','to_class','image','building'],dropna=False).agg(
                    effect=('effect','mean'),panels=('panels','sum'),adjacent_pairs=('adjacent_pairs','sum'),within_sd_mean=('within_sd_mean','mean')).reset_index()
                # Primary ordinary panel sets have one legal primary pool per image.
                v=v.merge(META[META.scope.eq('primary')&META.condition.eq('manual')][['pool_id','image']],on='image',how='left',validate='many_to_one')
                v=attach(v);v['support']=support;v['domain']=domain;v['n_slice']=str(n_slice);images.append(v)
    image=pd.concat(images,ignore_index=True);panel=pd.concat(pans,ignore_index=True)
    save(panel,'FIXED_N_PANEL_MEAN_STEPS.csv.gz');save(image,'FIXED_N_IMAGE_MEAN_STEPS.csv.gz')
    out=[]
    keys=['method','support','domain','n_slice','metric','time_source','from_class','to_class']
    for key,g in image.groupby(keys,dropna=False,sort=False):
        base=dict(zip(keys,key));metric=base['metric']
        units='Q_points' if metric=='B8L2' else ('log_team_recorded_time' if metric=='log_recorded_time' else metric)
        for axis in ['ALL','official_difficulty','purpose','structural_condition']:
            groups=[('ALL',g)] if axis=='ALL' else g.groupby(axis)
            for val,s in groups:
                row=dict(**base,axis=axis,stratum=val,**describe(s,'effect',units));row['panels']=int(s.panels.sum());row['adjacent_pairs']=int(s.adjacent_pairs.sum());out.append(row)
    summary=pd.DataFrame(out);save(summary,'FIXED_N_CONFIGURATION_STEP_STRATA.csv')
    # Auxiliary all-chain summaries weight chains equally within each image.
    # deepen_mixtures.py supplies the primary >=3-level, panel-weighted version.
    # Neither version is a natural one-person-entry sequence.
    ck=['method','from_class','to_class','pool_id','image','building']
    c=chains.groupby(ck).agg(chains=('steps','size'),steps=('steps','sum'),
        nondecreasing_fraction=('nondecreasing','mean'),no_drop_above_0_5_fraction=('no_drop_above_0_5','mean'),
        mixed_direction_fraction=('both_directions','mean'),mean_net_Q=('Q_net','mean'),
        max_drop=('max_drop','max')).reset_index()
    c=attach(c);save(c,'FIXED_N_MONOTONICITY_BY_IMAGE.csv')
    save(strata(c,['method','from_class','to_class'],['nondecreasing_fraction','no_drop_above_0_5_fraction','mixed_direction_fraction','mean_net_Q','max_drop']),
        'FIXED_N_MONOTONICITY_STRATA.csv')
    CHECKS['finite_configuration_adjacent_rows']=len(pairs)
    CHECKS['finite_configuration_chains']=len(chains)
    return pairs,summary,chains,member

def other_coalitions():
    path=AC+'/results_v1/COMPLETE_COALITIONS.csv.gz'
    use=['pool_id','image','building','scope','condition','method','event_id','physical_pair_id',
        'analysis_orientation_sign','input_A_team_key','input_C_team_key','n_A','n_C','A_class_counts','C_class_counts',
        'unknown_background_included','coalition_comparison_type','B8L2_CA','D10_CA','IoU3D100_CA',
        'S_bottom_deg_CA','dir_CA','Hmean_CA','omission_CA','extension_CA','fusion_turn_n_CA',
        'fusion_short_turn_edges_CA','record_time_CA_pct_source_matched','record_time_CA_seconds_single_source',
        'record_time_per_member_CA_pct_single_source','Q_missing_risk_change_CA','output_not_complete_risk_change_CA',
        'A_B8L2','C_B8L2']
    d=read(path,usecols=use)
    mask=d.method.isin(METHODS[1:])&d.scope.eq('primary')&d.condition.eq('manual')&~d.unknown_background_included
    d=d[mask].copy()
    patch=read(HERE/'inputs/AC_ASSISTED_COMPLETE_COALITIONS_AFFECTED.csv.gz',usecols=use)
    patch=patch[patch.method.isin(METHODS[1:])&patch.scope.eq('primary')&patch.condition.eq('manual')&~patch.unknown_background_included]
    keys=['pool_id','method','event_id','analysis_orientation_sign']
    assert not d.duplicated(keys).any() and not patch.duplicated(keys).any()
    a=d.set_index(keys);p=patch.set_index(keys);assert p.index.isin(a.index).all()
    CHECKS['RFUSE_JOINT_coalition_affected_rows']=len(p)
    CHECKS['RFUSE_JOINT_coalition_changed_Q_rows']=int((a.loc[p.index,'B8L2_CA'].fillna(-999)!=p.B8L2_CA.fillna(-999)).sum())
    d=pd.concat([a.drop(p.index),p]).reset_index()
    rows=[]
    additive=[m for m in use if m.endswith('_CA') and '_pct_' not in m and m not in ['A_B8L2','C_B8L2']]
    for r in d.itertuples():
        ca=tuple(sorted(c for c,n in json.loads(r.A_class_counts).items() if n>0 and c!='unknown'))
        cc=tuple(sorted(c for c,n in json.loads(r.C_class_counts).items() if n>0 and c!='unknown'))
        if set(ca)<set(cc):sign=1
        elif set(cc)<set(ca):sign=-1
        else:continue
        if abs(len(ca)-len(cc))!=1:continue
        fr,to=(ca,cc) if sign==1 else (cc,ca)
        row=dict(method=r.method,pool_id=r.pool_id,image=r.image,building=r.building,
            from_classes='|'.join(fr),to_classes='|'.join(to),added_class=next(iter(set(to)-set(fr))),
            event_id=r.event_id,physical_pair_id=r.physical_pair_id,
            n_from=r.n_A if sign==1 else r.n_C,n_to=r.n_C if sign==1 else r.n_A,
            Q_from=r.A_B8L2 if sign==1 else r.C_B8L2,Q_to=r.C_B8L2 if sign==1 else r.A_B8L2,
            from_team=r.input_A_team_key if sign==1 else r.input_C_team_key,
            to_team=r.input_C_team_key if sign==1 else r.input_A_team_key)
        for m in additive:row[m]=getattr(r,m)*sign
        pct=r.record_time_per_member_CA_pct_single_source
        row['record_time_per_member_CA_pct_single_source']=pct if sign==1 else (100*(1/(1+pct/100)-1) if pd.notna(pct) and pct> -100 else np.nan)
        rows.append(row)
    pair=pd.DataFrame(rows)
    # Same physical endpoints may have multiple registration links; count once
    # per current method/coalition/pool and retain all source ids separately.
    subset=['method','pool_id','from_classes','to_classes','from_team','to_team']
    CHECKS['RFUSE_JOINT_duplicate_coalition_registration_links']=int(pair.duplicated(subset).sum())
    pair=pair.drop_duplicates(subset)
    pair=attach(pair);save(pair,'RFUSE_JOINT_CLASS_ADDITION_PAIRS.csv.gz')
    assert np.allclose(pair.Q_to-pair.Q_from,pair.B8L2_CA,equal_nan=True)
    assert pair.n_to.gt(pair.n_from).all()
    pair['Q_from_available']=pair.Q_from.notna();pair['Q_to_available']=pair.Q_to.notna()
    pair['newly_evaluable']=~pair.Q_from.notna()&pair.Q_to.notna()
    pair['lost_evaluable']=pair.Q_from.notna()&~pair.Q_to.notna()
    save(pair.groupby(['method','from_classes','to_classes']).agg(registered_images=('image','nunique'),
        common_Q_images=('B8L2_CA','count'),from_Q_images=('Q_from_available','sum'),
        to_Q_images=('Q_to_available','sum'),new_Q_images=('newly_evaluable','sum'),
        lost_Q_images=('lost_evaluable','sum'),median_n_from=('n_from','median'),
        median_n_to=('n_to','median')).reset_index(),'RFUSE_JOINT_CLASS_ADDITION_SUPPORT.csv')
    metrics=[m for m in additive if m in pair]+['record_time_per_member_CA_pct_single_source']
    ikeys=['method','from_classes','to_classes','added_class','pool_id','image','building']
    img=pair.groupby(ikeys,dropna=False)[metrics+['n_from','n_to','Q_from','Q_to']].mean().reset_index()
    assert not img.duplicated(['method','from_classes','to_classes','image']).any()
    img=attach(img);save(img,'RFUSE_JOINT_CLASS_ADDITION_IMAGE_EFFECTS.csv.gz')
    sm=strata(img,['method','from_classes','to_classes','added_class'],metrics,unit_map={'B8L2_CA':'Q_points'},include_cross=True)
    save(sm,'RFUSE_JOINT_CLASS_ADDITION_STRATA.csv')
    return pair,sm

def backgrounds():
    path=AC+'/results_v1/FIXED_BLOCK_BACKGROUND_STEPS.csv.gz'
    head=pd.read_csv(ROOT/path,nrows=0)
    use=['pool_id','image','building','scope','condition','method','path_kind','path_id','role_direction',
        'event_from','event_to','n_from','n_to','m_from','m_to','D_from','D_to','A_from','A_to','C_from','C_to']
    metrics=['B8L2_CA','D10_CA','IoU3D100_CA','S_bottom_deg_CA','dir_CA','Hmean_CA',
        'omission_CA','extension_CA','fusion_turn_n_CA','fusion_short_turn_edges_CA',
        'record_time_per_member_CA_pct_single_source','Q_missing_risk_change_CA']
    use+=[m+s for m in metrics for s in ['__from','__to','__step_difference']]
    chunks=[]
    for x in read(path,usecols=use,chunksize=100000):
        x=x[x.method.isin(METHODS[1:])&x.scope.eq('primary')&x.condition.eq('manual')]
        if len(x):chunks.append(x)
    d=pd.concat(chunks,ignore_index=True)
    patch=read(HERE/'inputs/AC_ASSISTED_BACKGROUND_STEPS_AFFECTED.csv.gz',usecols=use)
    patch=patch[patch.method.isin(METHODS[1:])&patch.scope.eq('primary')&patch.condition.eq('manual')]
    keys=['pool_id','method','path_id','event_from','event_to'];a=d.set_index(keys);p=patch.set_index(keys)
    assert not a.index.duplicated().any() and not p.index.duplicated().any() and p.index.isin(a.index).all()
    CHECKS['RFUSE_JOINT_background_affected_rows']=len(p)
    before=a.loc[p.index,'B8L2_CA__step_difference'];after=p['B8L2_CA__step_difference']
    CHECKS['RFUSE_JOINT_background_float_roundtrip_different_rows']=int((before.fillna(-999)!=after.fillna(-999)).sum())
    CHECKS['RFUSE_JOINT_background_max_absolute_Q_step_difference']=float((after-before).abs().max())
    CHECKS['RFUSE_JOINT_background_changed_Q_rows']=int(((before.isna()!=after.isna())|(after-before).abs().gt(1e-9)).sum())
    d=pd.concat([a.drop(p.index),p]).reset_index()
    assert np.allclose(d['B8L2_CA__to']-d['B8L2_CA__from'],d['B8L2_CA__step_difference'],equal_nan=True)
    worker_set=lambda value:set(str(value).split('|')) if pd.notna(value) and str(value) else set()
    d['background_nested']=[worker_set(a)<=worker_set(b) for a,b in zip(d.D_from,d.D_to)]
    assert d.background_nested.all()
    CHECKS['RFUSE_JOINT_background_nested_verified_rows']=len(d)
    d['absolute_effect_change']=d['B8L2_CA__to'].abs()-d['B8L2_CA__from'].abs()
    d['absolute_effect_from']=d['B8L2_CA__from'].abs()
    d['absolute_effect_to']=d['B8L2_CA__to'].abs()
    d['effect_sign_flipped']=np.where(d['B8L2_CA__from'].notna()&d['B8L2_CA__to'].notna(),
        (d['B8L2_CA__from']*d['B8L2_CA__to']< -1e-18).astype(float),np.nan)
    d=attach(d);save(d,'FIXED_BLOCK_BACKGROUND_EXISTING_ROWS.csv.gz')
    ikeys=['method','role_direction','path_kind','n_from','n_to','m_from','m_to','pool_id','image','building']
    cols=['B8L2_CA__from','B8L2_CA__to','B8L2_CA__step_difference','absolute_effect_from','absolute_effect_to','absolute_effect_change','effect_sign_flipped']
    d['both_Q_effects_available']=d['B8L2_CA__from'].notna()&d['B8L2_CA__to'].notna()
    save(d.groupby(ikeys,dropna=False).agg(registered_path_steps=('path_id','size'),
        valid_common_Q_path_steps=('both_Q_effects_available','sum')).reset_index(),
        'FIXED_BLOCK_BACKGROUND_COMMON_Q_SUPPORT.csv.gz')
    common=d[d.both_Q_effects_available].copy()
    x=common.groupby(ikeys,dropna=False).agg(**{c:(c,'mean') for c in cols},paths=('path_id','nunique'),
        transitions=('path_id','size'),nested_fraction=('background_nested','mean')).reset_index()
    assert np.allclose(x['B8L2_CA__to']-x['B8L2_CA__from'],x['B8L2_CA__step_difference'])
    assert np.allclose(x['absolute_effect_to']-x['absolute_effect_from'],x['absolute_effect_change'])
    assert not x.duplicated(['method','role_direction','path_kind','n_from','n_to','m_from','m_to','image']).any()
    x=attach(x);save(x,'FIXED_BLOCK_BACKGROUND_IMAGE_EFFECTS.csv.gz')
    summary=strata(x,ikeys[:7],cols,unit_map={c:'Q_points' for c in cols if c!='effect_sign_flipped'})
    save(summary,'FIXED_BLOCK_BACKGROUND_STRATA.csv')
    return x,summary

def main():
    global META
    HERE.mkdir(exist_ok=True);META=current_meta()
    a,asum,endpoints=dstruct_alliances();print('DSTRUCT alliances',len(a),flush=True)
    pairs,csum,chains,member=configurations(reuse_pairs='--reuse-pairs' in sys.argv);print('Configurations',len(pairs),flush=True)
    oc,osum=other_coalitions();print('RFUSE JOINT additions',len(oc),flush=True)
    bg,bgsum=backgrounds();print('Background image conditions',len(bg),flush=True)
    save(pd.DataFrame(SOURCES).drop_duplicates('path'),'SOURCES.csv')
    CHECKS.update(new_fits=0,new_fusion=0,new_quality_scoring=0,new_teams=0,
        primary_meta_images=int(META[META.scope.eq('primary')&META.condition.eq('manual')].image.nunique()),
        official_difficulty_used=True,room_purpose_source='IMAGE_TYPE_INDEX recorded user types',
        source_commit=HEAD,numeric_tolerance=1e-9,status='passed')
    (HERE/'CHECKS.json').write_text(json.dumps(CHECKS,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(CHECKS,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
