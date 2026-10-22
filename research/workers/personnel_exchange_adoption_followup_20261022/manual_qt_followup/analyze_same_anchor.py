#!/usr/bin/env python3
"""Matched finite-candidate policies; no fitting, target selection or fusion.

All selections use frozen leave-building-out history. Original outcomes are
read only. Uniform selection is the exact distribution on the already frozen
target reservoir, not the whole class or the whole available personnel pool.
"""
from pathlib import Path
import io, json, os, hashlib
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
OLD=HERE.parent.parent/'personnel_exchange_closure_20261022'
BASE=OLD/'manual_joint'
METRICS=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter',
         'omission','extension','nodes','fusion_turn_n','fusion_short_turn_edges',
         'fusion_redundancy_n','ref_node_recall_9','ref_edge_recall_9',
         'height_mean_h','top_y_mean_px','bottom_y_mean_px','geometry_area_h2']
KEY=['pool_id','image','building','panel_id','n','m']

def write(df,name):
    dest=HERE/name; dest.parent.mkdir(parents=True,exist_ok=True)
    buf=io.BytesIO()
    df.to_csv(buf,index=False,compression={'method':'gzip','mtime':0} if name.endswith('.gz') else None)
    data=buf.getvalue(); tmp=dest.with_name(dest.name+'.tmp')
    with tmp.open('wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    tmp.replace(dest)

def text(name,content):
    dest=HERE/name; dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_name(dest.name+'.tmp')
    with tmp.open('w',encoding='utf-8') as f: f.write(content); f.flush(); os.fsync(f.fileno())
    tmp.replace(dest)

def levels(df,group,metrics,stem):
    panel=df.groupby(group+['building','image','panel_id'],dropna=False)[metrics].mean().reset_index()
    image=panel.groupby(group+['building','image'],dropna=False)[metrics].mean().reset_index()
    building=image.groupby(group+['building'],dropna=False)[metrics].mean().reset_index()
    summary=building.groupby(group,dropna=False)[metrics].mean().reset_index()
    for level,table in [('PANEL',panel),('IMAGE',image),('BUILDING',building),('SUMMARY',summary)]:
        for col in [x for x in metrics if 'logT' in x]:
            table[col+'_geomean_pct']=100*np.expm1(table[col])
        if 'delta_B8L2' in table and 'delta_logT' in table:
            table['both_improved']=(table.delta_B8L2>1e-9)&(table.delta_logT< -1e-12)
        write(table,stem+'_'+level+'.csv')
    counts=[]
    for k,g in df.groupby(group,dropna=False):
        if not isinstance(k,tuple): k=(k,)
        d=dict(zip(group,k)); d.update(registered_anchor_rows=len(g),
                quality_common_anchors=int(g.delta_B8L2.notna().sum()),
                registered_images=g.image.nunique(),registered_buildings=g.building.nunique(),
                registered_panels=g.panel_id.nunique())
        for level,tab in [('image',image),('building',building),('panel',panel)]:
            use=tab
            for col,val in zip(group,k): use=use[use[col].eq(val)]
            d[level+'_Q_improved']=int(use.delta_B8L2.gt(1e-9).sum())
            d[level+'_Q_known']=int(use.delta_B8L2.notna().sum())
            d[level+'_both_improved']=int(use.both_improved.sum())
        counts.append(d)
    summary=summary.merge(pd.DataFrame(counts),on=group)
    write(summary,stem+'_SUMMARY.csv')
    return summary,panel,image,building

def main():
    # Stage 01: exact class-constrained vs unrestricted QT10 identity and all
    # policies on one shared set of original A teams.
    P=pd.read_csv(BASE/'POLICIES_COMPLETE.csv.gz')
    assert not P.duplicated(['panel_id','team_A','policy']).any()
    a=P[P.policy.eq('class_QT_10')].copy()
    b=P[P.policy.eq('continuous_QT_10')]
    ident=a[KEY+['team_A','team_P','replacement_block','available_choice_workers']].merge(
        b[['panel_id','team_A','team_P','replacement_block','available_choice_workers']],
        on=['panel_id','team_A'],suffixes=('_class','_QT10'),validate='one_to_one')
    ident['same_team']=ident.team_P_class.eq(ident.team_P_QT10)
    ident['same_initial_candidate_universe']=ident.available_choice_workers_class.eq(ident.available_choice_workers_QT10)
    assert ident.same_team.all() and ident.same_initial_candidate_universe.all()
    write(ident,'CLASS_QT10_EXACT_IDENTITY.csv.gz')
    identity_summary=ident.groupby(['n','m']).agg(anchors=('team_A','size'),images=('image','nunique'),
        buildings=('building','nunique'),panels=('panel_id','nunique'),identical_teams=('same_team','sum')).reset_index()
    write(identity_summary,'CLASS_QT10_IDENTITY_SUMMARY.csv')
    text('STAGE01_IDENTITY_ZH.md',
        '# 阶段01：同锚点类别约束与连续QT10\n\n'
        '已读取上一轮完整政策结果；本轮不重新融合、不重拟合标签。\n\n'
        f'全部 {len(ident):,} 个相同原队 A、共同背景 D、实际替换人数 m 的锚点，'
        '类别约束 QT10 与全候选连续 QT10 选中完全相同成员。候选初始人员域也逐锚相同；'
        '类别约束是选择规则中的限制。分类在此提供类别角色解释和候选池组织，并未增加连续 QT10 以外的收益。\n\n'
        '精确链接：CLASS_QT10_EXACT_IDENTITY.csv.gz；规模：CLASS_QT10_IDENTITY_SUMMARY.csv。'
        '后续同范围再选择分析在同一冻结目标储备内进行，与全池最优或重新训练分类不同。\n')
    print('stage01 saved',len(ident),flush=True)

    common=P.groupby(['panel_id','team_A']).A_B8L2.transform(lambda x:x.notna().all()) & \
           P.groupby(['panel_id','team_A']).P_B8L2.transform(lambda x:x.notna().all())
    G=P[KEY+['team_A','team_P','policy','A_failure','P_failure','A_member_workers',
        'P_member_workers','common_background','outgoing_block_X','replacement_block','available_choice_workers']].copy()
    G['common_four_policy_quality']=common
    for col in METRICS:
        G['delta_'+col]=P['change_'+col].where(common)
    G['delta_logT']=P.change_recorded_time_logratio.where(common)
    G['all_time_delta_logT']=P.change_recorded_time_logratio
    G['target_failure_rate']=P.P_failure.astype(float)
    G['loss_gt5']=P.change_B8L2.lt(-5).astype(float).where(common)
    G['loss_gt10']=P.change_B8L2.lt(-10).astype(float).where(common)
    write(G,'GLOBAL_POLICIES_SAME_ANCHOR.csv.gz')
    global_metrics=['delta_'+c for c in METRICS]+['delta_logT','all_time_delta_logT','target_failure_rate','loss_gt5','loss_gt10']
    global_summary,*_=levels(G,['n','m','policy'],global_metrics,'GLOBAL_POLICIES_COMMON')

    # Stage 02: all target blocks of each frozen reservoir are already computed.
    ecol=KEY[:-1]+['m_AB','training_QT_direction','event_id','team_A','team_B','team_C',
                  'changed_count_block_Z','Z_history_q_effect','Z_history_t_effect']
    E=pd.read_csv(BASE/'EVENTS_COMPLETE.csv.gz',usecols=ecol).rename(columns={'m_AB':'m'})
    E=E[E.n.eq(20)&E.m.ge(3)&E.training_QT_direction.eq('q_up__faster')]
    C=E[KEY+['team_C','changed_count_block_Z','Z_history_q_effect','Z_history_t_effect']].drop_duplicates(['panel_id','team_C'])
    needed=set(C.team_C)|set(a.team_A)
    sc=pd.read_csv(OLD/'delivery/endpoints/ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz',
        usecols=['team_key','score_status','member_workers','source_time_total_seconds',
                 'source_time_known_n','time_source_kinds']+METRICS)
    sc=sc[sc.team_key.isin(needed)].set_index('team_key')
    assert len(sc)==len(needed)
    C=C.merge(sc.reset_index(),left_on='team_C',right_on='team_key',validate='many_to_one')
    C['failure']=C.B8L2.isna()
    # Use exactly the q_history/t_history supplied to the original policy
    # ranking. The event q_effect/t_effect columns are a separate auxiliary
    # historical interface and are retained only as provenance.
    labels=pd.read_csv(BASE/'ACTUAL_MEMBER_LABELS.csv.gz').set_index(['pool_id','worker_id'])
    for field in ['q_history','t_history']:
        C['classification_'+field]=[np.mean([labels.loc[(r.pool_id,w),field]
            for w in r.changed_count_block_Z.split('|')]) for r in C.itertuples()]
    assert sc.source_time_known_n.eq(20).all()
    assert sc.time_source_kinds.nunique()==1
    C['logT']=np.log(C.source_time_total_seconds.where(C.source_time_total_seconds>0))
    panels=pd.read_csv(BASE/'BACKGROUND_PANELS.csv.gz')
    C=C.merge(panels[['panel_id','source_class','target_class','background_workers','source_reservoir','target_reservoir']],on='panel_id',validate='many_to_one')
    write(C,'FROZEN_TARGET_CANDIDATES.csv.gz')
    links=E[['event_id','panel_id','team_A','team_B','team_C']].copy()
    write(links,'SOURCE_ABC_LINKS.csv.gz')
    selections=[]; rows=[]
    for panel,cs in C.groupby('panel_id'):
        cs=cs.sort_values('changed_count_block_Z')
        anchors=a[a.panel_id.eq(panel)]
        assert len(anchors)>0
        selected={}
        for policy,lam in [('finite_Q',0),('finite_QT10',10),('finite_QT20',20)]:
            rank=cs.classification_q_history-lam*cs.classification_t_history
            chosen=cs.loc[rank.idxmax()]
            selected[policy]=chosen
            selections.append({**{k:chosen[k] for k in KEY},'policy':policy,'lambda_logtime':lam,
                'selected_team':chosen.team_C,'selected_block_Z':chosen.changed_count_block_Z,
                'selected_score_history':float(rank.max()),'history_tie_count':int(rank.eq(rank.max()).sum()),
                'selected_history_Q':chosen.classification_q_history,'selected_history_logT':chosen.classification_t_history,
                'target_reservoir':chosen.target_reservoir,'background_D':chosen.background_workers,
                'source_reservoir':chosen.source_reservoir,'source_class':chosen.source_class,
                'target_class':chosen.target_class,'candidate_blocks':len(cs),
                'selected_failure':bool(chosen.failure)})
        all_selected_valid=all(np.isfinite(v.B8L2) for v in selected.values())
        policy_cache={}
        for policy,choice in [('finite_uniform',None)]+list(selected.items()):
            cand=cs if choice is None else choice.to_frame().T
            valid=cand[cand.B8L2.notna()]
            policy_cache[policy]=(choice,{metric:pd.to_numeric(valid[metric],errors='coerce').mean()
                  for metric in METRICS},float(cand.logT.mean()),float(valid.logT.mean()),
                  float(cand.source_time_total_seconds.mean()),float(cand.failure.mean()),
                  pd.to_numeric(valid.B8L2,errors='coerce').to_numpy())
        for _,anchor in anchors.iterrows():
            A=sc.loc[anchor.team_A]
            common_quality=np.isfinite(A.B8L2) and all_selected_valid and cs.B8L2.notna().any()
            source_logT=np.log(A.source_time_total_seconds) if A.source_time_total_seconds>0 else np.nan
            for policy,(choice,means,alllog,validlog,seconds,failure,cvals) in policy_cache.items():
                row={**{k:anchor[k] for k in KEY},'team_A':anchor.team_A,'policy':policy,
                     'A_member_workers':anchor.A_member_workers,'background_D':anchor.common_background,
                     'outgoing_X':anchor.outgoing_block_X,'selected_team':None if choice is None else choice.team_C,
                     'selected_Z':None if choice is None else choice.changed_count_block_Z,
                     'target_reservoir':cs.iloc[0].target_reservoir,'candidate_blocks':len(cs),
                     'candidate_scored_blocks':int(cs.B8L2.notna().sum()),
                     'A_failure':not np.isfinite(A.B8L2),'common_four_policy_quality':common_quality,
                     'target_failure_rate':failure,
                     'all_time_delta_logT':alllog-source_logT,
                     'expected_time_seconds_change':seconds-A.source_time_total_seconds}
                for metric in METRICS:
                    row['delta_'+metric]=float(means[metric]-A[metric]) if common_quality else np.nan
                row['delta_logT']=validlog-source_logT if common_quality else np.nan
                for cut in [5,10]:
                    row['loss_gt'+str(cut)]=float((cvals-A.B8L2 < -cut).mean()) if common_quality else np.nan
                rows.append(row)
    R=pd.DataFrame(rows)
    write(pd.DataFrame(selections),'FINITE_SELECTED_BLOCKS.csv')
    write(R,'FINITE_POLICIES_SAME_ANCHOR.csv.gz')
    fmetrics=['delta_'+c for c in METRICS]+['delta_logT','all_time_delta_logT','expected_time_seconds_change',
                                          'target_failure_rate','loss_gt5','loss_gt10']
    fs,fp,fi,fb=levels(R,['n','m','policy'],fmetrics,'FINITE_POLICIES_COMMON')
    # Additional within-class selection value, always P-A minus uniform(C-A)
    # on the exact same A/candidate set and common successful comparisons.
    U=R[R.policy.eq('finite_uniform')][['panel_id','team_A']+fmetrics]
    inc=R[R.policy.ne('finite_uniform')].merge(U,on=['panel_id','team_A'],suffixes=('','_uniform'),validate='many_to_one')
    for metric in fmetrics: inc[metric]=inc[metric]-inc[metric+'_uniform']
    inc=inc.drop(columns=[x for x in inc if x.endswith('_uniform')])
    write(inc,'FINITE_SELECTION_INCREMENT_SAME_ANCHOR.csv.gz')
    ins,_,_,_=levels(inc,['n','m','policy'],fmetrics,'FINITE_SELECTION_INCREMENT')
    # Per-panel source and target identities make frozen roles reviewable.
    role=panels[panels.panel_id.isin(C.panel_id)].copy()
    hist=pd.read_csv(BASE/'ACTUAL_DIRECTION_HISTORY.csv')
    role=role.merge(hist,on=['pool_id','source_class','target_class','n','m'],how='left',validate='many_to_one')
    write(role,'ACTUAL_ROLES_MEMBERS_BACKGROUND.csv')
    eff=pd.read_csv(BASE/'EFFECTIVE_CONDITIONS.csv')
    write(eff[(eff.n.eq(20)&eff.actual_m.isin([3,4,5,6]))|(eff.n.eq(21)&eff.actual_m.eq(3))],
          'INHERITED_RECOMMENDATION_ROWS.csv')
    receipt={'new_main_commit':'cf053a6e31d17393c0e8216ce15660fa37b8b7bb','data_version':'v2',
       'new_native_fusion_calls':0,'new_classification_fits':0,'global_policy_records':len(P),
       'same_anchor_QT10_identity':len(ident),'frozen_target_panel_count':C.panel_id.nunique(),
       'frozen_target_block_records':len(C),'unique_target_endpoints':C.team_C.nunique(),
       'finite_policy_anchor_rows':len(R),'finite_selection_increment_rows':len(inc),
       'estimand':'P-A for all policies on same A; P-A minus uniform(C-A) for increments',
       'aggregation':'anchors within D, D within image, images within building, buildings equal',
       'selection_uses_target_quality':False,'candidate_scope':'frozen target-class reservoir, not whole class',
       'selection_history':'ACTUAL_MEMBER_LABELS.csv.gz q_history/t_history, identical to original policy ranking',
       'quality_common_scope':'same A and all three history-selected endpoints have Q; uniform C conditioned on scored C',
       'failures':'all registered candidates/selected endpoints retain failure rate independent of common Q mask'}
    text('ANALYSIS_RECEIPT.json',json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(fs[['m','policy','delta_B8L2','delta_D10','delta_logT_geomean_pct','target_failure_rate',
              'image_Q_improved','image_Q_known','building_Q_improved','building_Q_known']].to_string(index=False))
    print('INCREMENT',ins[['m','policy','delta_B8L2','delta_logT_geomean_pct','image_Q_improved',
                         'image_Q_known','building_Q_improved','building_Q_known']].to_string(index=False),flush=True)

if __name__=='__main__': main()
