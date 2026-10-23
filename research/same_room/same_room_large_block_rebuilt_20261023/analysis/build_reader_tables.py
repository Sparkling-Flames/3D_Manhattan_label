"""Readable projections and an exact additive decomposition of existing means.

No team, outcome or classification is selected or changed. Direction
contributions use the same configuration/pair/building weights as the main
result, so direction contribution points sum back to that result.
"""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from build_events import write_csv,boolean
from summarize_conditions import CFG

BASE={'subset':'支持层','method':'分类方案','condition':'条件','pairs':'图对数','Q_pairs':'共同Q图对数',
 'buildings':'建筑数','configurations':'配置数','attempted_events':'尝试事件数','common6_Q_events':'六端点共同Q事件数',
 'joint_QT_events':'六端点共同Q时间事件数','n_min':'n最小','n_max':'n最大','m_min':'m最小','m_max':'m最大',
 'positive_Q_extra_pairs':'额外Q幅度正向图对数','positive_Q_extra_pair_fraction':'额外Q幅度正向图对比例',
 'unique_actual_Z_blocks':'不同实际目标块数','unique_actual_XYZ_blocks':'不同实际三替换块数',
 'unique_actual_D_sets':'不同实际背景数','actual_source_worker_count':'实际源类人员数',
 'actual_target_worker_count':'实际目标类人员数','excluded_building':'剔除建筑'}
MET={'B8L2_within':'Q同类幅度','B8L2_cross':'Q对称跨类幅度','B8L2_extra':'Q额外幅度',
 'B8L2_BA':'Q_B减A','B8L2_CA':'Q_C减A','B8L2_CB':'Q_C减B','B8L2_CS':'Q_C减源双队均值',
 'D10_extra':'D10额外幅度','fusion_turn_n_extra':'实际转折额外幅度','fusion_turn_n_CA':'实际转折_C减A',
 'fusion_short_turn_edges_CA':'短转折_C减A','fusion_redundancy_n_CA':'近共线节点_C减A',
 'S_bottom_deg_CA':'底面误差_C减A','dir_CA':'内部方向残差_C减A','Hmean_CA':'均高误差_C减A',
 'Hcenter_CA':'局部高度误差_C减A','QT_Q_CA':'共同Q时间_Q_C减A','QT_time_ratio_CA':'共同Q时间_劳动比_C除A',
 'QT_Q_CB':'共同Q时间_Q_C减B','QT_time_ratio_CB':'共同Q时间_劳动比_C除B',
 'score_failure_fraction':'评分失败引用比例','incomplete_fraction':'不完整引用比例',
 'new_score_failure_CA':'C替A新增评分失败比例','recovered_score_CA':'C替A恢复评分比例',
 'CA_loss_gt5_fraction':'C替A降质超过5分比例'}

def projection(df):
    rename=BASE.copy()
    for weight,cn in [('pair_equal','图对等权'),('building_equal','建筑等权'),('declaration_building','声明组再建筑等权')]:
        for k,v in MET.items():rename[weight+'__'+k]=v+'_'+cn
    return df[[k for k in rename if k in df]].rename(columns=rename)

def contributions(root,out):
    met=['B8L2_within','B8L2_cross','B8L2_extra','B8L2_CA','B8L2_CB','B8L2_CS']
    cfg=pd.read_csv(root/'results/CONFIGURATION_METRICS.csv.gz',usecols=lambda x:x in CFG+met+['subset'],low_memory=False)
    mapping=pd.read_csv(root/'design/STRICT_ABC_EVENTS.csv.gz',usecols=CFG+['source_role_key','target_role_key'],low_memory=False)
    mapping=mapping.drop_duplicates()
    assert not mapping.duplicated(CFG).any()
    cfg=cfg.merge(mapping,on=CFG,validate='many_to_one')
    cfg=cfg[cfg.B8L2_extra.notna()]
    rows=[]
    for (sub,method,condition),d in cfg.groupby(['subset','method','condition'],observed=True):
        paircols=['pair_key','building']
        perpair=d.groupby(paircols,observed=True).size()
        bpair=perpair.groupby('building').size();nb=len(bpair);npair=len(perpair)
        d=d.copy();ix=pd.MultiIndex.from_frame(d[paircols])
        d['w_pair']=1/perpair.reindex(ix).to_numpy()/npair
        d['w_building']=1/perpair.reindex(ix).to_numpy()/d.building.map(bpair).to_numpy()/nb
        assert np.isclose(d.w_pair.sum(),1) and np.isclose(d.w_building.sum(),1)
        for (sr,tr),z in d.groupby(['source_role_key','target_role_key'],observed=True):
            r={'subset':sub,'method':method,'condition':condition,'source_role_key':sr,'target_role_key':tr,
               'source_role':z.source_role.iloc[0],'target_role':z.target_role.iloc[0],
               'configurations':len(z),'pairs':z.pair_key.nunique(),'buildings':z.building.nunique()}
            for weight,col in [('pair_equal','w_pair'),('building_equal','w_building')]:
                r[weight+'_weight_share']=float(z[col].sum())
                for metric in met:r[weight+'_contribution__'+metric]=float((z[col]*z[metric]).sum())
            rows.append(r)
        # The decomposition is an identity of the main published weighting.
        for metric in met:
            pair=d.groupby(paircols,observed=True)[metric].mean()
            assert np.isclose((d.w_pair*d[metric]).sum(),pair.mean())
            assert np.isclose((d.w_building*d[metric]).sum(),pair.groupby('building').mean().mean())
    result=pd.DataFrame(rows);write_csv(result,out/'DIRECTION_CONTRIBUTIONS.csv')
    return len(result)

def quality_joint_responses(root,out):
    # Incomplete output can still have a candidate polygon. For claims that
    # combine Q and structure, explicitly retain only all-six Q support.
    metrics=['B8L2','D10','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n',
             'S_bottom_deg','dir','Hmean','Hcenter','ref_node_recall_5','ref_edge_recall_5',
             'diag_wall_coverage_05','geometry_area_h2','height_mean_h']
    cols=[m+'_'+s for m in metrics for s in ['within','cross','extra','BA','CA','CB','CS']]
    meta=list(dict.fromkeys(CFG+['event_id','source_role_key','target_role_key','ordinary_comparable',
                       'D_empty','Q_common6','history_Q_block_range']))
    e=pd.read_csv(root/'results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz',usecols=meta+cols,low_memory=False)
    e=e[boolean(e.ordinary_comparable)&boolean(e.Q_common6)]
    rows=[]
    for (method,condition),d in e.groupby(['method','condition'],observed=True):
        masks={'ordinary_all':pd.Series(True,index=d.index),'ordinary_pure':boolean(d.D_empty),
          'ordinary_mixed':~boolean(d.D_empty),'ordinary_mixed_less_half':2*d.m<d.n,
          'ordinary_Q_blocks_within2':d.history_Q_block_range<=2,
          'ordinary_Q_blocks_within5':d.history_Q_block_range<=5}
        for subset,mask in masks.items():
            dd=d[mask]
            if not len(dd):continue
            groups=[('ALL_DIRECTIONS','ALL_DIRECTIONS',dd)]+[(sr,tr,z) for (sr,tr),z in dd.groupby(['source_role_key','target_role_key'],observed=True)]
            for sr,tr,z in groups:
                cfg=z.groupby(CFG,dropna=False,observed=True)[cols].mean().reset_index()
                pair=cfg.groupby(['pair_key','building'],observed=True)[cols].mean()
                building=pair.groupby('building').mean()
                r=dict(method=method,condition=condition,subset=subset,source_role_key=sr,target_role_key=tr,
                  events=len(z),pairs=z.pair_key.nunique(),buildings=z.building.nunique(),configurations=len(cfg),
                  support='all six endpoints Q-evaluable; component-specific finite values retained')
                for metric in metrics:
                    valid=z[metric+'_within'].notna()
                    r[metric+'_common_events']=int(valid.sum())
                    r[metric+'_common_pairs']=int(z.loc[valid,'pair_key'].nunique())
                for name in cols:
                    r['pair_equal__'+name]=pair[name].mean();r['building_equal__'+name]=building[name].mean()
                rows.append(r)
    write_csv(pd.DataFrame(rows),out/'QUALITY_STRUCTURE_COMMON_SUPPORT.csv')
    return len(rows)

def main(root):
    root=Path(root);out=root/'reader_tables';out.mkdir(parents=True,exist_ok=True)
    overall=pd.read_csv(root/'results/OVERALL_CONDITIONS.csv')
    write_csv(projection(overall),out/'KEY_CONDITIONS_ZH.csv')
    leave=pd.read_csv(root/'results/LEAVE_ONE_BUILDING_OUT.csv')
    write_csv(projection(leave),out/'KEY_BUILDING_LEAVE_ONE_ZH.csv')
    repeat=[]
    for _,r in overall.iterrows():
        for eps in ['eps0','eps2']:
            for contrast in ['BA','CA','CB']:
                row={BASE[k]:r[k] for k in BASE if k in r.index}
                row.update(阈值=0 if eps=='eps0' else 2,调整=contrast)
                for key,cn in [('both_near_zero','双方近零'),('both_gain','双方升质'),('both_loss','双方降质'),
                    ('opposite','双方反向'),('one_response','单边响应'),('sign_agree_including_zero','含双方零的符号一致')]:
                    for weight,wcn in [('pair_equal','图对等权'),('building_equal','建筑等权')]:
                        row[cn+'_'+wcn]=r.get(f'{weight}__{eps}_{contrast}_{key}',np.nan)
                for weight,wcn in [('pair_equal','图对等权'),('building_equal','建筑等权')]:
                    row['只筛源端_目标同向率_'+wcn]=r.get(f'{weight}_{eps}_{contrast}_source_only_same',np.nan)
                    row['两端都响应_同向率_'+wcn]=r.get(f'{weight}_{eps}_{contrast}_both_trigger_same',np.nan)
                row['只筛源端的原始触发次数']=r.get(f'event_weight_{eps}_{contrast}_source_triggers',np.nan)
                row['源端响应支持图对']=r.get(f'{eps}_{contrast}_source_triggered_pairs',np.nan)
                repeat.append(row)
    write_csv(pd.DataFrame(repeat),out/'KEY_REPETITION_ZH.csv')
    mem=pd.read_csv(root/'sensitivity/MEMBER_MATCHED_SUMMARY.csv')
    roles=pd.read_csv(root/'sensitivity/MEMBER_FOLD_ROLES.csv')
    role=roles.groupby('worker_id').apply(lambda d:'|'.join(sorted(set(d.building+':'+d.target_class+':'+d.target_role))),include_groups=False)
    mem['楼外折与目标角色']=mem.worker_id.map(role)
    rename={'worker_id':'人员编号','matching':'匹配方式','status':'状态','relevant_events':'匹配前事件数',
      'relevant_pairs':'匹配前图对数','relevant_buildings':'匹配前建筑数','matched_strata':'匹配层数',
      'matched_pairs':'保留图对数','matched_buildings':'保留建筑数','events_retained':'保留事件数',
      'event_retention_fraction':'事件保留比例','present_events_retained':'包含成员事件数',
      'absent_events_retained':'缺席成员事件数','matched_Q_pairs':'共同Q图对数',
      'matched_Q_buildings':'共同Q建筑数','matched_absent_positive_pair_fraction':'缺席子域正向图对比例',
      '楼外折与目标角色':'楼外折与目标角色'}
    for state,cn in [('original','匹配前'),('matched_present','匹配后包含'),('matched_absent','匹配后缺席')]:
        for w,wcn in [('pair_equal','图对等权'),('building_equal','建筑等权')]:
            rename[f'{state}_{w}__B8L2_extra']=cn+'额外Q幅度_'+wcn
    write_csv(mem[[k for k in rename if k in mem]].rename(columns=rename),out/'KEY_MEMBER_SENSITIVITY_ZH.csv')
    count=contributions(root,out)
    joint_count=quality_joint_responses(root,out)
    (out/'READER_TABLE_RECEIPT.json').write_text(json.dumps({'new_fusion':0,'new_classes':0,
       'direction_contribution_rows':count,'quality_structure_common_support_rows':joint_count,
       'direction_contributions_sum_to_published_weighted_effects':True,
       'status':'projections of complete saved results; exact provenance retained'},ensure_ascii=False,indent=2)+'\n')
    print('readable tables complete',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='.')
    a=p.parse_args();main(a.root)
