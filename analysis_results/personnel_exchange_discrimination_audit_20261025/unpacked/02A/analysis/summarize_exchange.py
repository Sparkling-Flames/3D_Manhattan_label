#!/usr/bin/env python3
"""Hierarchical, failure-preserving summaries of strict same-background ABC.

No fusion is run and no input/label/event file is edited. Each registered direction
is retained. Building-excluded class IDs are used only inside their pool/fold;
cross-building role summaries use historical Q/time/turn semantics.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

EFFECT_RE = re.compile(r'.*_(within|cross|gap|CA|CB|BA)$')
BASE = ['stage','phase','method','n','m']
POOL = BASE + ['pool_id','image','building','difficulty']
DIRECTION = POOL + ['source_class','target_class','semantic_role']
ARM_FIELDS = ['B8L2','D10','score_available','connection_available','score_status',
              'source_time_total_seconds','source_time_missing_n','nodes',
              'floor_turn5_n','floor_short_edge_03_n','floor_redundant5_n',
              'height_mean_h','floor_area_camera_h2']


def write_csv(path, frame):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.writing')
    frame.to_csv(temporary,index=False,compression='gzip' if path.suffix=='.gz' else None)
    temporary.replace(path)


def truth(values):
    """Nullable bool/numeric flags; absence must not become failure or zero."""
    s=values.astype(str).str.lower()
    return s.map({'true':1.,'false':0.,'1':1.,'0':0.,'1.0':1.,'0.0':0.})


def direction(value, positive, negative):
    v=pd.to_numeric(value,errors='coerce')
    return np.select([v>0,v<0,v==0],[positive,negative,'equal'],default='unknown')


def aggregate(frame, keys, cols):
    """Equal-weight children. Carry original metric counts through all levels."""
    groups=frame.groupby(keys,dropna=False,observed=True,sort=False)
    means=groups[cols].mean()
    counts=[c+'__event_n' for c in cols]
    summable=['n_events','n_metric_records','n_pending']+counts
    sums=groups[summable].sum(min_count=1)
    out=means.join(sums)
    out['n_child_cells']=groups.size()
    return out.reset_index()


def save_aggregate(out,name,frame):
    write_csv(out/(name+'.csv.gz'),frame)


def effect_long(pool_rows,building_rows,raw,keys,cols):
    rows=[]
    raw_groups={key if isinstance(key,tuple) else (key,):g
                for key,g in raw.groupby(keys,dropna=False,sort=False)}
    building_groups={key if isinstance(key,tuple) else (key,):g
                     for key,g in building_rows.groupby(keys,dropna=False,sort=False)}
    for key,group in pool_rows.groupby(keys,dropna=False,sort=False):
        key=key if isinstance(key,tuple) else (key,)
        bg=building_groups.get(key)
        rg=raw_groups.get(key)
        coverage=dict(attempted_events=len(rg) if rg is not None else int(group.n_events.sum()),
                      attempted_images=group.pool_id.nunique(),attempted_buildings=group.building.nunique(),
                      unique_backgrounds=rg.background_id.nunique() if rg is not None else np.nan,
                      unique_XYZ_blocks=rg.block_id.nunique() if rg is not None else np.nan)
        if rg is not None:
            coverage['unique_endpoint_teams']=len(set(rg[['A_team_key','B_team_key','C_team_key']].to_numpy().ravel()))
        # Quantiles/means for all columns at once keep full component coverage cheap.
        vx=group[cols]
        vb=bg[cols] if bg is not None else pd.DataFrame(columns=cols,dtype=float)
        xmean=vx.mean();bmean=vb.mean();xcount=vx.count();bcount=vb.count()
        quantiles=vx.quantile([.1,.25,.5,.75,.9]);sd=vx.std(ddof=1)
        xpos=vx.gt(1e-9).sum();xneg=vx.lt(-1e-9).sum()
        bpos=vb.gt(1e-9).sum();bneg=vb.lt(-1e-9).sum()
        for col in cols:
            r=dict(zip(keys,key),metric=col,**coverage,
                   valid_images=int(xcount[col]),valid_buildings=int(bcount[col]),
                   valid_events=int(group[col+'__event_n'].sum()),
                   mean_image_equal=xmean[col],mean_building_equal=bmean[col],
                   image_q10=quantiles.loc[.1,col],image_q25=quantiles.loc[.25,col],image_median=quantiles.loc[.5,col],
                   image_q75=quantiles.loc[.75,col],image_q90=quantiles.loc[.9,col],image_sd=sd[col],
                   positive_images=int(xpos[col]),negative_images=int(xneg[col]),
                   positive_buildings=int(bpos[col]),negative_buildings=int(bneg[col]))
            if col.endswith('_gap'):
                r.update(images_gap_gt1=int(vx[col].gt(1).sum()),images_gap_gt2=int(vx[col].gt(2).sum()),
                         images_gap_gt5=int(vx[col].gt(5).sum()))
            rows.append(r)
    return pd.DataFrame(rows)


def separation_table(pool_rows,building_rows,raw,keys,stems):
    rows=[]
    bg={key if isinstance(key,tuple) else (key,):g
        for key,g in building_rows.groupby(keys,dropna=False,sort=False)}
    rawg={key if isinstance(key,tuple) else (key,):g
          for key,g in raw.groupby(keys,dropna=False,sort=False)}
    for key,group in pool_rows.groupby(keys,dropna=False,sort=False):
        key=key if isinstance(key,tuple) else (key,);build=bg[key];attempt=rawg.get(key)
        def matrix(frame,suffix):
            return frame.reindex(columns=[s+'_'+suffix for s in stems]).set_axis(stems,axis=1)
        w,c,g=matrix(group,'within'),matrix(group,'cross'),matrix(group,'gap')
        valid=w.notna()&c.notna()&g.notna();w=w.where(valid);c=c.where(valid);g=g.where(valid)
        bw,bc,bgaps=matrix(build,'within'),matrix(build,'cross'),matrix(build,'gap')
        bv=bw.notna()&bc.notna()&bgaps.notna();bw=bw.where(bv);bc=bc.where(bv);bgaps=bgaps.where(bv)
        wm,cm,gm=w.mean(),c.mean(),g.mean();bwm,bcm,bgm=bw.mean(),bc.mean(),bgaps.mean()
        gn=g.count();bgn=bgaps.count();q=g.quantile([.1,.5,.9]);gsd=g.std(ddof=1)
        gpos=g.gt(1e-9).sum();gneg=g.lt(-1e-9).sum();bgpos=bgaps.gt(1e-9).sum();bgneg=bgaps.lt(-1e-9).sum()
        ratios=c/w.where(w.gt(0));rn=ratios.count();r15=ratios.gt(1.5).sum();zwi=w.eq(0).sum()
        support=dict(attempted_events=len(attempt) if attempt is not None else int(group.n_events.sum()),
                     attempted_images=group.pool_id.nunique(),attempted_buildings=group.building.nunique())
        if attempt is not None:
            support['unique_endpoint_teams']=len(set(attempt[['A_team_key','B_team_key','C_team_key']].to_numpy().ravel()))
            event_valid=(matrix(attempt,'within').notna()&matrix(attempt,'cross').notna()&matrix(attempt,'gap').notna()).sum()
        signed={}
        for contrast in ['BA','CA','CB']:
            sv=matrix(group,contrast);sb=matrix(build,contrast)
            signed[contrast]=dict(image=sv.mean(),building=sb.mean(),image_n=sv.count(),building_n=sb.count(),
                                  image_pos=sv.gt(1e-9).sum(),building_pos=sb.gt(1e-9).sum())
        for stem in stems:
            row=dict(zip(keys,key),metric=stem,**support,
                     metric_polarity='agreement_higher_similar' if stem=='geometry_same_pair_count' else 'distance_higher_different',
                     valid_images=int(gn[stem]),valid_buildings=int(bgn[stem]),
                     within_image_equal=wm[stem],cross_image_equal=cm[stem],gap_image_equal=gm[stem],
                     ratio_of_image_means=cm[stem]/wm[stem] if wm[stem]>0 else np.nan,
                     within_building_equal=bwm[stem],cross_building_equal=bcm[stem],gap_building_equal=bgm[stem],
                     ratio_of_building_means=bcm[stem]/bwm[stem] if bwm[stem]>0 else np.nan,
                     gap_positive_images=int(gpos[stem]),gap_negative_images=int(gneg[stem]),
                     gap_positive_buildings=int(bgpos[stem]),gap_negative_buildings=int(bgneg[stem]),
                     gap_image_median=q.loc[.5,stem],gap_image_q10=q.loc[.1,stem],gap_image_q90=q.loc[.9,stem],
                     paired_standardized_gap=gm[stem]/gsd[stem] if gsd[stem]>0 else np.nan,
                     ratio_gt1_5_images=int(r15[stem]),ratio_valid_images=int(rn[stem]),zero_within_images=int(zwi[stem]))
            if attempt is not None:
                row['valid_separation_events']=int(event_valid[stem])
            for contrast in ['BA','CA','CB']:
                col=stem+'_'+contrast
                if col in group:
                    stats=signed[contrast]
                    row[contrast+'_image_equal']=stats['image'][stem];row[contrast+'_building_equal']=stats['building'][stem]
                    row[contrast+'_positive_images']=int(stats['image_pos'][stem]);row[contrast+'_valid_images']=int(stats['image_n'][stem])
                    row[contrast+'_positive_buildings']=int(stats['building_pos'][stem]);row[contrast+'_valid_buildings']=int(stats['building_n'][stem])
            rows.append(row)
    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--events',type=Path,nargs='+',required=True)
    ap.add_argument('--metrics',type=Path,nargs='+',required=True)
    ap.add_argument('--endpoints',type=Path,nargs='*',default=[])
    ap.add_argument('--centers',type=Path,nargs='*',default=[])
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    events=pd.concat([pd.read_csv(p,low_memory=False) for p in args.events],ignore_index=True)
    assert not events.event_id.duplicated().any(),'Duplicate event ids across input stages.'
    metric=pd.concat([pd.read_csv(p,low_memory=False) for p in args.metrics],ignore_index=True)
    assert not metric.event_id.duplicated().any(),'Duplicate metric event ids.'
    effects=[c for c in metric if EFFECT_RE.fullmatch(c)]
    effects=[c for c in effects if pd.api.types.is_numeric_dtype(metric[c])]
    assert effects,'No contrast columns found in metrics.'
    # Event ledger remains authoritative for phase, members, and background.
    extra=[c for c in metric if c not in events.columns]
    data=events.merge(metric[['event_id']+extra],on='event_id',how='left',validate='one_to_one',indicator='_metric_join')
    data['n_events']=1;data['n_metric_records']=data._metric_join.eq('both').astype(int)
    data['n_pending']=1-data.n_metric_records
    data['difficulty']=data.difficulty.fillna('unknown')
    data['background_target_fraction']=data.background_target_n/(data.n-data.m)
    data['history_time_direction']=direction(data.history_target_minus_source_m_all_log_time,'slower','faster')
    data['semantic_role']=(data.historical_q_direction.astype(str)+'|'+data.history_time_direction.astype(str)
                           +'|'+data.historical_turn_direction.astype(str))
    center_paths=args.centers or [p.parent/'FOLD_ROLE_CENTERS.csv.gz' for p in args.events]
    center_paths=[p for p in center_paths if p.exists()]
    role_fields=[]
    if center_paths:
        centers=pd.concat([pd.read_csv(p) for p in center_paths],ignore_index=True)
        centers=centers.drop_duplicates(['method','heldout_building','class_id'],keep='last')
        centers['class_people']=centers.members.fillna('').map(lambda s:len(set(s.split('|'))-{''}))
        cg=centers.groupby(['method','heldout_building'],dropna=False)
        centers['turn_rank']=cg.m_hard_turn_n.rank(method='dense',ascending=True)
        centers['highest_turn']=centers.m_hard_turn_n.eq(cg.m_hard_turn_n.transform('max'))
        centers['lowest_turn']=centers.m_hard_turn_n.eq(cg.m_hard_turn_n.transform('min'))
        centers['largest_class']=centers.class_people.eq(cg.class_people.transform('max'))
        write_csv(out/'FOLD_CLASS_ROLE_MAP.csv',centers)
        attrs=['class_people','turn_rank','highest_turn','lowest_turn','largest_class']
        for side in ['source','target']:
            ren={'heldout_building':'building','class_id':side+'_class'}
            ren.update({x:side+'_'+x for x in attrs})
            add=centers[['method','heldout_building','class_id']+attrs].rename(columns=ren)
            data=data.merge(add,on=['method','building',side+'_class'],how='left',validate='many_to_one')
            role_fields += [side+'_'+x for x in attrs]
    provided_flags=[c for c in metric if (re.fullmatch(r'[ABC]_(failed|incomplete)',c)
                    or c=='ABC_scored' or c.startswith('C_loss10_') or c.startswith('C_improved_')
                    or c.startswith('C_failure_or_loss10_') or re.fullmatch(r'record_time_.*_pct',c))]
    provided_arm=[c for c in metric if re.fullmatch(r'[ABC]_(B8L2|D10|source_time_total_seconds|nodes|floor_turn5_n|floor_short_edge_03_n|floor_redundant5_n|height_mean_h|floor_area_camera_h2)',c)]
    outcome_cols=provided_flags+provided_arm
    # Actual endpoint metadata provides separate failed versus not-yet-computed status.
    if args.endpoints:
        endpoint_parts=[]
        for p in args.endpoints:
            ep=pd.read_csv(p,usecols=lambda c:c in ['team_key']+ARM_FIELDS,low_memory=False)
            endpoint_parts.append(ep)
        endpoint=pd.concat(endpoint_parts,ignore_index=True).drop_duplicates('team_key',keep='last').set_index('team_key')
        for arm in 'ABC':
            keys=data[arm+'_team_key'];present=keys.isin(endpoint.index)
            data[arm+'_endpoint_present']=present.astype(float);outcome_cols.append(arm+'_endpoint_present')
            for field in ARM_FIELDS:
                if field not in endpoint:continue
                mapped=keys.map(endpoint[field])
                col='endpoint_'+arm+'_'+field
                data[col]=mapped
                if field in ['B8L2','D10','source_time_total_seconds','nodes','floor_turn5_n',
                             'floor_short_edge_03_n','floor_redundant5_n','height_mean_h','floor_area_camera_h2']:
                    data[col]=pd.to_numeric(data[col],errors='coerce');outcome_cols.append(col)
            if 'score_available' in endpoint:
                col=arm+'_score_failure';data[col]=1-truth(data['endpoint_'+arm+'_score_available'])
                data.loc[~present,col]=np.nan;outcome_cols.append(col)
            if 'connection_available' in endpoint:
                col=arm+'_connection_failure';data[col]=1-truth(data['endpoint_'+arm+'_connection_available'])
                data.loc[~present,col]=np.nan;outcome_cols.append(col)
        if all(a+'_score_failure' in data for a in 'ABC'):
            f=data[[a+'_score_failure' for a in 'ABC']]
            data['any_ABC_score_failure']=f.max(axis=1).where(f.notna().all(axis=1))
            outcome_cols.append('any_ABC_score_failure')
    # Explicit pair denominators: a missing comparison is unknown, never zero loss.
    for stem in ['B8L2','D10']:
        for contrast in ['BA','CA','CB']:
            col=stem+'_'+contrast
            if col not in data:continue
            x=pd.to_numeric(data[col],errors='coerce')
            for suffix,flag in [('positive',x.gt(0)),('loss_gt5',x.lt(-5)),('loss_gt10',x.lt(-10)),('abs_le1',x.abs().le(1))]:
                name=col+'_'+suffix;data[name]=flag.astype(float).where(x.notna());outcome_cols.append(name)
    for contrast,left,right in [('BA','B','A'),('CA','C','A'),('CB','C','B')]:
        lc='endpoint_'+left+'_source_time_total_seconds';rc='endpoint_'+right+'_source_time_total_seconds'
        if lc not in data or rc not in data:continue
        valid=data[lc].notna()&data[rc].gt(0)
        for arm in [left,right]:
            missing='endpoint_'+arm+'_source_time_missing_n'
            if missing in data:valid &= pd.to_numeric(data[missing],errors='coerce').eq(0)
        col='record_time_'+contrast+'_percent'
        data[col]=(100*(data[lc]/data[rc]-1)).where(valid);outcome_cols.append(col)
        q='B8L2_'+contrast
        if q in data:
            good=valid&data[q].notna();name='quality_and_time_'+contrast+'_both_better'
            data[name]=(data[q].gt(0)&data[col].lt(0)).astype(float).where(good);outcome_cols.append(name)
    cols=list(dict.fromkeys(effects+outcome_cols))
    for col in cols:
        data[col]=pd.to_numeric(data[col],errors='coerce')
    count_frame=pd.DataFrame({c+'__event_n':data[c].notna().astype('int64') for c in cols},index=data.index)
    data=pd.concat([data,count_frame],axis=1)
    # Background replicate mean inside each concrete XYZ / target-background quota.
    blocklevel_keys=DIRECTION+['block_id','background_target_n','background_target_fraction']
    blocklevel=aggregate(data,blocklevel_keys,cols)
    save_aggregate(out,'BLOCK_BACKGROUND_LEVEL_SUMMARY',blocklevel)
    # Levels first inside block, then equal XYZ blocks: no block gains weight from
    # having more valid background draws or from repeated endpoint references.
    block=aggregate(blocklevel,DIRECTION+['block_id'],cols)
    save_aggregate(out,'CONCRETE_BLOCK_SUMMARY',block)
    pooldirection=aggregate(block,DIRECTION,cols)
    if role_fields:
        role_attrs=data[DIRECTION+role_fields].drop_duplicates(DIRECTION)
        pooldirection=pooldirection.merge(role_attrs,on=DIRECTION,how='left',validate='one_to_one')
    save_aggregate(out,'POOL_DIRECTION_SUMMARY',pooldirection)
    pool=aggregate(pooldirection,POOL,cols)
    save_aggregate(out,'POOL_METHOD_N_M_SUMMARY',pool)
    building=aggregate(pool,BASE+['building'],cols)
    save_aggregate(out,'BUILDING_METHOD_N_M_SUMMARY',building)
    stems=sorted(c[:-7] for c in effects if c.endswith('_within') and c[:-7]+'_cross' in effects and c[:-7]+'_gap' in effects)
    write_csv(out/'METHOD_N_M_COMPARISON.csv',separation_table(pool,building,data,BASE,stems))
    write_csv(out/'ALL_OUTCOMES_BY_METHOD_N_M.csv.gz',effect_long(pool,building,data,BASE,cols))
    # Difficulty keeps actual support, no collapse of doorway into difficulty.
    dbuild=aggregate(pool,BASE+['difficulty','building'],cols)
    save_aggregate(out,'BUILDING_DIFFICULTY_SUMMARY',dbuild)
    write_csv(out/'DIFFICULTY_COMPARISON.csv',separation_table(pool,dbuild,data,BASE+['difficulty'],stems))
    write_csv(out/'ALL_OUTCOMES_BY_DIFFICULTY.csv.gz',effect_long(pool,dbuild,data,BASE+['difficulty'],cols))
    # Semantic role alignment, never C1/C2 identity across held-out folds.
    rolepool=aggregate(pooldirection,POOL+['semantic_role'],cols)
    rolebuild=aggregate(rolepool,BASE+['semantic_role','building'],cols)
    save_aggregate(out,'POOL_ROLE_SUMMARY',rolepool)
    save_aggregate(out,'BUILDING_ROLE_SUMMARY',rolebuild)
    write_csv(out/'SEMANTIC_ROLE_COMPARISON.csv',separation_table(rolepool,rolebuild,data,BASE+['semantic_role'],stems))
    write_csv(out/'ALL_OUTCOMES_BY_SEMANTIC_ROLE.csv.gz',effect_long(rolepool,rolebuild,data,BASE+['semantic_role'],cols))
    # A matched semantic direction panel prevents extra middle-class directions
    # in a baseline from diluting its main ordinary-to-more-turns use case.
    if role_fields:
        def fair_masks(frame):
            sh=frame.source_highest_turn.eq(True);th=frame.target_highest_turn.eq(True)
            sl=frame.source_largest_class.eq(True);tl=frame.target_largest_class.eq(True)
            up=frame.historical_turn_direction.eq('more_turns') if 'historical_turn_direction' in frame else frame.semantic_role.str.endswith('|more_turns')
            down=frame.historical_turn_direction.eq('fewer_turns') if 'historical_turn_direction' in frame else frame.semantic_role.str.endswith('|fewer_turns')
            return {'toward_highest_turn':th&~sh,
                    'away_from_highest_turn':sh&~th,
                    'largest_to_highest_turn':sl&th&~sh,
                    'highest_to_largest':sh&tl&~th,
                    'largest_to_higher_turn':sl&up,
                    'all_more_turns':up,'all_fewer_turns':down}
        pd_masks=fair_masks(pooldirection);raw_masks=fair_masks(data)
        fairp=[];fairb=[];fairraw=[]
        for name,mask in pd_masks.items():
            if not mask.any():continue
            pp=aggregate(pooldirection[mask],POOL,cols);pp['fair_role']=name
            bb=aggregate(pp,BASE+['building'],cols);bb['fair_role']=name
            rcols=list(dict.fromkeys(BASE+['pool_id','image','building','difficulty','background_id','block_id',
                                          'A_team_key','B_team_key','C_team_key']+cols))
            rr=data.loc[raw_masks[name],rcols].copy();rr['fair_role']=name
            fairp.append(pp);fairb.append(bb);fairraw.append(rr)
        if fairp:
            fp=pd.concat(fairp,ignore_index=True);fb=pd.concat(fairb,ignore_index=True);fr=pd.concat(fairraw,ignore_index=True)
            save_aggregate(out,'FAIR_ROLE_POOL_SUMMARY',fp)
            save_aggregate(out,'FAIR_ROLE_BUILDING_SUMMARY',fb)
            write_csv(out/'FAIR_ROLE_COMPARISON.csv',separation_table(fp,fb,fr,BASE+['fair_role'],stems))
            risk_cols=[c for c in cols if re.search('failure|failed|loss_gt|loss10|record_time|both_better',c)]
            write_csv(out/'FAIR_ROLE_RISK_TIME.csv',effect_long(fp,fb,fr,BASE+['fair_role'],risk_cols))
            fair_paired=[]
            fkeys=['stage','phase','pool_id','n','m','fair_role']
            primary=[c for c in ['B8L2_within','B8L2_cross','B8L2_gap','B8L2_CA','B8L2_CB',
                                 'geometry_bev_distance_gap','geometry_pair_angle_gap'] if c in fp]
            for baseline in [x for x in fp.method.unique() if x.startswith('V3_')]:
                bas=fp[fp.method.eq(baseline)][fkeys+primary]
                for meth in sorted(set(fp.method)-{baseline}):
                    merged=fp[fp.method.eq(meth)].merge(bas,on=fkeys,suffixes=('','_baseline'),how='inner')
                    for _,row in merged.iterrows():
                        rec={k:row[k] for k in fkeys+['image','building','difficulty']}
                        rec.update(method=meth,baseline=baseline,comparison_support='same_semantic_role_pool_n_m_not_same_ABC')
                        for c in primary:rec[c+'_minus_baseline']=row[c]-row[c+'_baseline']
                        fair_paired.append(rec)
            write_csv(out/'FAIR_ROLE_COMMON_POOL_DIFFERENCES.csv.gz',pd.DataFrame(fair_paired))
    # Fixed XYZ background response, with low/high actual quota and all three arms.
    gradient_rows=[]
    for key,g in blocklevel.groupby(DIRECTION+['block_id'],dropna=False,sort=False):
        g=g.sort_values('background_target_n')
        if g.background_target_n.nunique()<2:continue
        low,high=g.iloc[0],g.iloc[-1]
        row=dict(zip(DIRECTION+['block_id'],key),target_n_low=int(low.background_target_n),
                 target_n_high=int(high.background_target_n),target_fraction_low=low.background_target_fraction,
                 target_fraction_high=high.background_target_fraction,levels=len(g))
        for c in cols:
            row[c+'_high_minus_low']=high[c]-low[c]
        gradient_rows.append(row)
    gradients=pd.DataFrame(gradient_rows);write_csv(out/'FIXED_XYZ_BACKGROUND_GRADIENTS.csv.gz',gradients)
    # Same image/n/m common-support contrast with old methods. These are same-pool
    # sampled designs, not identical ABC endpoints; that limitation is explicit.
    paired=[]
    baselines=[m for m in pool.method.unique() if m.startswith('V3_')]
    match_keys=['stage','phase','pool_id','n','m']
    primary=[c for c in ['B8L2_within','B8L2_cross','B8L2_gap','B8L2_CA','B8L2_CB'] if c in pool]
    primary += [s+'_gap' for s in stems if 'geometry' in s]
    for baseline in baselines:
        b=pool[pool.method.eq(baseline)][match_keys+primary]
        for method in sorted(set(pool.method)-{baseline}):
            merged=pool[pool.method.eq(method)].merge(b,on=match_keys,suffixes=('','_baseline'),how='inner')
            for _,r in merged.iterrows():
                row={k:r[k] for k in match_keys+['image','building','difficulty']}
                row.update(method=method,baseline=baseline,comparison_support='same_pool_n_m_not_same_ABC')
                for c in primary:row[c+'_minus_baseline']=r[c]-r[c+'_baseline']
                paired.append(row)
    write_csv(out/'COMMON_POOL_BASELINE_DIFFERENCES.csv.gz',pd.DataFrame(paired))
    # Compact risk table remains on the same balanced image/building scale.
    allout=pd.read_csv(out/'ALL_OUTCOMES_BY_METHOD_N_M.csv.gz')
    risk=allout[allout.metric.str.contains('failure|failed|incomplete|loss_gt|loss10|record_time|both_better',regex=True)]
    write_csv(out/'RISK_TIME_SUMMARY.csv',risk)
    receipt=dict(schema='hierarchical_exchange_summary_v1',events=len(events),
                 metric_records=int(data.n_metric_records.sum()),pending_events=int(data.n_pending.sum()),
                 methods=data.method.nunique(),images=data.pool_id.nunique(),buildings=data.building.nunique(),
                 outcome_fields=len(cols),separation_metrics=stems,
                 phases=data.phase.value_counts().to_dict(),
                 input_events=[str(p) for p in args.events],input_metrics=[str(p) for p in args.metrics],
                 input_endpoints=[str(p) for p in args.endpoints],
                 weighting='background replicates -> quota levels within exact XYZ -> XYZ blocks -> directed class pairs within image -> equal images; buildings average their images then equal buildings',
                 denominator='Each metric retains actual contributing event counts; failures are separate outcomes and never imputed Q=0.',
                 background_warning='D quota gradients hold XYZ fixed but change real D members; they estimate sampled background composition changes, not a pure one-variable intervention.',
                 baseline_warning='COMMON_POOL table aligns pool/n/m; it does not claim identical D/XYZ or identical eligible domains.',
                 selection='Screen summaries are exploratory selection evidence. Confirm held-out buildings and new combinations are reported in separate phase rows.')
    (out/'SUMMARY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
