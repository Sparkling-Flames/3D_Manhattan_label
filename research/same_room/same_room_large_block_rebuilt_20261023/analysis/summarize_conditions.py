"""Equal-configuration, equal-physical-pair and declaration/building summaries.

No team selection. This script retains n/m and never subtracts unmatched
subgroup means to estimate a size effect.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from build_events import boolean,write_csv,METRICS,VERSION

CFG=['pair_key','building','groups','method','condition','source_class','target_class',
     'source_role','target_role','n','m']

def analysis_columns(e):
    cols=[f'{m}_{s}' for m in METRICS for s in ['within','cross','extra','BA','CA','CB','CS']]
    cols += [c for c in e if c.startswith(('eps0_','eps2_','QT_','QT4_','time_ratio_','time_logratio_'))]
    cols += ['score_failure_fraction','incomplete_fraction','Q_common6','complete6','time_common6',
       'new_incomplete_BA','new_incomplete_CA','recovered_complete_BA','recovered_complete_CA',
       'new_score_failure_BA','new_score_failure_CA','recovered_score_BA','recovered_score_CA']
    cols += [f'{k}_{z}' for k in ['BA','CA','CB'] for z in ['loss_gt5_fraction','gain_gt5_fraction',
       'any_loss_gt5','same_nonzero_turn_step','same_nonzero_turn_q_opposite','zero_turn_q_opposite']]
    return list(dict.fromkeys(c for c in cols if c in e and c not in CFG))

def subsets(e):
    ordinary=boolean(e.ordinary_comparable); door=e.layer_a.astype(str).str.contains('doorway')|e.layer_b.astype(str).str.contains('doorway')
    pure=boolean(e.D_empty)
    masks=[('ordinary_all',ordinary),('ordinary_pure',ordinary&pure),('ordinary_mixed',ordinary&~pure),
       ('ordinary_mixed_less_half',ordinary&~pure&(2*e.m<e.n)),
       ('ordinary_mixed_half',ordinary&~pure&(2*e.m==e.n)),
       ('ordinary_mixed_more_half',ordinary&~pure&(2*e.m>e.n)),
       ('doorway',~ordinary&door),('other_nonordinary',~ordinary&~door),
       ('ordinary_Q_blocks_within2',ordinary&(e.history_Q_block_range<=2)),
       ('ordinary_Q_blocks_within5',ordinary&(e.history_Q_block_range<=5)),
       ('ordinary_mixed_Q_blocks_within2',ordinary&~pure&(e.history_Q_block_range<=2))]
    for (method,condition),z in e.groupby(['method','condition'],sort=True):
        for name,mask in masks:
            dd=z[mask.loc[z.index]]
            if len(dd):yield name,method,condition,dd

def hierarchy(dd,cols):
    cfg=dd.groupby(CFG,dropna=False,observed=True)[cols].mean().reset_index()
    counts=dd.groupby(CFG,dropna=False,observed=True).agg(attempted_events=('event_id','size'),
       common6_Q_events=('Q_common6','sum'),complete6_events=('complete6','sum'),
       common6_time_events=('time_common6','sum'),joint_QT_events=('QT_common6','sum')).reset_index()
    cfg=cfg.merge(counts,on=CFG,validate='one_to_one')
    pk=['pair_key','building','groups','method','condition']
    pair=cfg.groupby(pk,dropna=False,observed=True)[cols].mean().reset_index()
    ct=cfg.groupby(pk,dropna=False,observed=True).agg(configurations=('n','size'),
       attempted_events=('attempted_events','sum'),common6_Q_events=('common6_Q_events','sum'),
       complete6_events=('complete6_events','sum'),joint_QT_events=('joint_QT_events','sum')).reset_index()
    pair=pair.merge(ct,on=pk,validate='one_to_one')
    exp=pair.assign(group_id=pair.groups.fillna('unknown').astype(str).str.split('|')).explode('group_id')
    group=exp.groupby(['building','group_id','method','condition'],dropna=False,observed=True)[cols].mean().reset_index()
    b_decl=group.groupby(['building','method','condition'],dropna=False,observed=True)[cols].mean().reset_index()
    b_pair=pair.groupby(['building','method','condition'],dropna=False,observed=True)[cols].mean().reset_index()
    return cfg,pair,group,b_decl,b_pair

def overall_row(dd,pair,b_decl,b_pair,cols,subset,method,condition):
    good=pair.B8L2_extra.notna(); z=pair[good]
    def distinct_people(columns):
        return len(set('|'.join(dd[c].fillna('').astype(str).str.cat(sep='|') for c in columns).split('|'))-{''})
    row={'subset':subset,'method':method,'condition':condition,'attempted_events':len(dd),
      'common6_Q_events':int(dd.Q_common6.sum()),'joint_QT_events':int(dd.QT_common6.sum()),
      'pairs':dd.pair_key.nunique(),'Q_pairs':len(z),'buildings':dd.building.nunique(),
      'Q_buildings':z.building.nunique(),'images':len(set(dd.image_a)|set(dd.image_b)),
      'declared_groups':len(set('|'.join(dd.groups.fillna('').astype(str)).split('|'))),
      'directions':len(dd[['pair_key','source_class','target_class']].drop_duplicates()),
      'unique_actual_Z_blocks':dd.Z_members.nunique(),
      'unique_actual_XY_pairs':len(dd[['X_members','Y_members']].drop_duplicates()),
      'unique_actual_XYZ_blocks':len(dd[['X_members','Y_members','Z_members']].drop_duplicates()),
      'unique_actual_D_sets':dd.D_members.fillna('').nunique(),
      'actual_source_worker_count':distinct_people(['X_members','Y_members']),
      'actual_target_worker_count':distinct_people(['Z_members']),
      'actual_background_worker_count':distinct_people(['D_members']),
      'unique_view_endpoints':len(set(dd[[f'team_{r}_{v}' for v in ['a','b'] for r in ['A','B','C']]].to_numpy().ravel())),
      'configurations':len(dd[CFG].drop_duplicates()),'n_min':dd.n.min(),'n_max':dd.n.max(),
      'm_min':dd.m.min(),'m_max':dd.m.max(),
      'positive_Q_extra_pairs':int((z.B8L2_extra>0).sum()),
      'positive_Q_extra_pair_fraction':float((z.B8L2_extra>0).mean()) if len(z) else np.nan,
      'positive_Q_extra_building_fraction':float((b_pair.B8L2_extra.dropna()>0).mean()),
      'Q_extra_pair_p10':z.B8L2_extra.quantile(.1),'Q_extra_pair_p50':z.B8L2_extra.quantile(.5),
      'Q_extra_pair_p90':z.B8L2_extra.quantile(.9)}
    for metric in METRICS:
        valid=dd[metric+'_within'].notna()
        row[metric+'_common6_events']=int(valid.sum())
        row[metric+'_common6_Q_events']=int((valid&boolean(dd.Q_common6)).sum())
        row[metric+'_common6_pairs']=int(dd.loc[valid,'pair_key'].nunique())
        row[metric+'_common6_buildings']=int(dd.loc[valid,'building'].nunique())
    for contrast in ['BA','CA','CB']:
        valid=boolean(dd['QT4_common_'+contrast])
        row['joint_QT4_'+contrast+'_events']=int(valid.sum())
        row['joint_QT4_'+contrast+'_pairs']=int(dd.loc[valid,'pair_key'].nunique())
        row['joint_QT4_'+contrast+'_buildings']=int(dd.loc[valid,'building'].nunique())
    for col in cols:
        row['pair_equal__'+col]=pair[col].mean()
        row['building_equal__'+col]=b_pair[col].mean()
        row['declaration_building__'+col]=b_decl[col].mean()
    # Source-only rate conditional on triggers on common six-endpoint support.
    for eps in ['eps0','eps2']:
        for con in ['BA','CA','CB']:
            num=dd[f'{eps}_{con}_source_same_n'].sum();den=dd[f'{eps}_{con}_source_trigger_n'].sum()
            row[f'event_weight_{eps}_{con}_source_only_same']=num/den if den else np.nan
            row[f'event_weight_{eps}_{con}_source_triggers']=int(den)
            two=dd[f'{eps}_{con}_both_response'].sum()
            row[f'event_weight_{eps}_{con}_both_trigger_same']=dd[f'{eps}_{con}_same_nonzero'].sum()/two if two else np.nan
            row[f'event_weight_{eps}_{con}_both_response_events']=int(two)
            pr=dd.groupby(['pair_key','building'],observed=True)[[f'{eps}_{con}_source_same_n',f'{eps}_{con}_source_trigger_n']].sum()
            raw_rr=pr.iloc[:,0]/pr.iloc[:,1].replace(0,np.nan)
            row[f'pair_equal_event_trigger_weight_{eps}_{con}_source_only_same']=raw_rr.mean()
            # Match the main configuration weighting before conditioning on a
            # source response. A fully enumerated small cell must not outweigh
            # another cell solely because it has more member combinations.
            cc=dd[boolean(dd.Q_common6)].groupby(CFG,dropna=False,observed=True)[
                [f'{eps}_{con}_source_same_n',f'{eps}_{con}_source_trigger_n',
                 f'{eps}_{con}_same_nonzero',f'{eps}_{con}_both_response']].mean().reset_index()
            pp=cc.groupby(['pair_key','building'],observed=True)[
                [f'{eps}_{con}_source_same_n',f'{eps}_{con}_source_trigger_n',
                 f'{eps}_{con}_same_nonzero',f'{eps}_{con}_both_response']].mean()
            rr=pp[f'{eps}_{con}_source_same_n']/pp[f'{eps}_{con}_source_trigger_n'].replace(0,np.nan)
            br=pp[f'{eps}_{con}_same_nonzero']/pp[f'{eps}_{con}_both_response'].replace(0,np.nan)
            row[f'pair_equal_{eps}_{con}_source_only_same']=rr.mean()
            row[f'building_equal_{eps}_{con}_source_only_same']=rr.groupby('building').mean().mean()
            row[f'pair_equal_{eps}_{con}_both_trigger_same']=br.mean()
            row[f'building_equal_{eps}_{con}_both_trigger_same']=br.groupby('building').mean().mean()
            row[f'{eps}_{con}_source_triggered_pairs']=int(rr.notna().sum())
    return row

def main(events,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    e=pd.read_csv(events,low_memory=False)
    for c in ['Q_common6','complete6','time_common6','QT_common6','D_empty']:
        e[c]=boolean(e[c])
    cols=analysis_columns(e)
    all_cfg=[];all_pair=[];all_group=[];all_building=[];overall=[];leave=[];directions=[];conditions=[]
    for subset,method,condition,dd in subsets(e):
        cfg,pair,group,b_decl,b_pair=hierarchy(dd,cols)
        for df,dest in [(cfg,all_cfg),(pair,all_pair),(group,all_group)]:
            df=df.copy();df.insert(0,'subset',subset);dest.append(df)
        for weight,b in [('declaration_then_building',b_decl),('pair_then_building',b_pair)]:
            b=b.copy();b.insert(0,'weighting',weight);b.insert(0,'subset',subset);all_building.append(b)
        overall.append(overall_row(dd,pair,b_decl,b_pair,cols,subset,method,condition))
        if subset in ['ordinary_all','ordinary_pure','ordinary_mixed','ordinary_mixed_less_half']:
            for building in sorted(dd.building.unique()):
                left=dd[dd.building!=building]
                if not len(left):continue
                # Removing a whole building cannot change means in retained pairs.
                row=overall_row(left,pair[pair.building!=building],b_decl[b_decl.building!=building],
                  b_pair[b_pair.building!=building],cols,subset,method,condition)
                row['excluded_building']=building;leave.append(row)
        if subset in ['ordinary_all','ordinary_pure','ordinary_mixed','ordinary_mixed_less_half','doorway','other_nonordinary']:
            for (srck,tgtk),dz in dd.groupby(['source_role_key','target_role_key'],dropna=False,observed=True):
                _,p,g,bd,bp=hierarchy(dz,cols)
                row=overall_row(dz,p,bd,bp,cols,subset,method,condition)
                row.update(source_role=dz.source_role.iloc[0],target_role=dz.target_role.iloc[0],
                           source_role_key=srck,target_role_key=tgtk)
                row['source_workers']='|'.join(sorted(set(('|'.join(dz.X_members)+'|'+'|'.join(dz.Y_members)).split('|'))))
                row['target_workers']='|'.join(sorted(set('|'.join(dz.Z_members).split('|'))))
                row['actual_n_m']='|'.join(f'{int(n)}/{int(m)}' for n,m in sorted(set(zip(dz.n,dz.m))))
                directions.append(row)
            # n/m and background composition are kept raw, not collapsed as a size experiment.
            for (n,m),dz in dd.groupby(['n','m'],observed=True):
                _,p,g,bd,bp=hierarchy(dz,cols)
                row=overall_row(dz,p,bd,bp,cols,subset,method,condition);row.update(n=n,m=m,m_over_n=m/n)
                conditions.append(row)
    for name,frames in [('CONFIGURATION_METRICS.csv.gz',all_cfg),('PAIR_METRICS.csv.gz',all_pair),
                        ('DECLARATION_GROUP_METRICS.csv.gz',all_group),('BUILDING_METRICS.csv.gz',all_building)]:
        write_csv(pd.concat(frames,ignore_index=True),out/name)
    for name,rows in [('OVERALL_CONDITIONS.csv',overall),('LEAVE_ONE_BUILDING_OUT.csv',leave),
                      ('DIRECTION_RESULTS.csv',directions),('N_M_CONDITIONS.csv',conditions)]:
        write_csv(pd.DataFrame(rows),out/name)
    l=pd.DataFrame(leave)
    write_csv(l[l.excluded_building=='uNb9QFRL6hY'] if len(l) else pd.DataFrame(columns=['excluded_building','subset','method']),out/'EXCLUDE_UNB_SPECIFIC.csv')
    # Detailed difficulty conditions, kept descriptive on their own support.
    dr=[]
    for (method,condition,difficulty),dd in e[boolean(e.ordinary_comparable)].groupby(['method','condition','difficulty_pair'],dropna=False):
        _,p,g,bd,bp=hierarchy(dd,cols);row=overall_row(dd,p,bd,bp,cols,'ordinary_difficulty_pair',method,condition)
        row['difficulty_pair']=difficulty;dr.append(row)
    write_csv(pd.DataFrame(dr),out/'DIFFICULTY_PAIR_CONDITIONS.csv')
    (out/'SUMMARY_RECEIPT.json').write_text(json.dumps({'version':VERSION,'input_events':len(e),
       'subsets':len(overall),'source_only_filter_after_common6':True,'physical_pairs_not_independent_rooms':True,
       'weighting':'members within pair/direction/n/m -> configuration mean -> physical pair mean; optional declaration/building',
       'new_fusion_calls':0},ensure_ascii=False,indent=2))
    print('summaries complete',len(overall),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--events',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();main(a.events,a.out)
