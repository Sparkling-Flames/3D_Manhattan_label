#!/usr/bin/env python3
"""Publish phase-specific conditions with balanced effects and raw risk denominators.

No fusion is performed. Role masks use historical fold centers only. Event counts
are coverage, not independent sample counts; effects retain image/building weighting.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from summarize_exchange import write_csv

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis'
SELECTED={
 'DSTRUCT_K3': {(10,7):'supported_large_block_small_team',(18,7):'primary_structure_condition',(20,6):'adjacent_scale'},
 'MSDGEOM_SCOPE_K4': {(10,7):'large_replacement_path_condition',(18,7):'adjacent_scale',(20,6):'adopt_cross_condition_scope_large_team'},
 'V3_BEHAVIOR_coarse': {(12,8):'retained_old_structure_comparator',(18,7):'matched_role_old_structure_comparator'},
 'Q_MEDIAN2': {(12,8):'quality_gradient_baseline',(18,7):'quality_gradient_baseline'},
 'RFUSE_GEOM_K2': {(8,4):'small_class_early_team',(12,4):'primary_response_geometry_condition',(20,4):'larger_team_boundary'},
 'RFUSE_GEOMQ_K2': {(8,4):'response_geometry_quality_supplement',(12,4):'response_geometry_quality_supplement',
                    (20,4):'larger_team_supplement',(20,6):'larger_block_supplement',(24,5):'largest_team_supplement'},
 'RFUSE_GEOM_K3': {(12,4):'small_class_partition_supplement',(14,9):'large_branch_comparator',(17,9):'large_branch_comparator'},
 'RFUSE_GEOMQ_K3': {(12,4):'small_class_partition_supplement',(20,6):'adopt_response_quality_large_team_condition',
                    (17,9):'large_branch_comparator'}
}
CORE=['B8L2','D10','IoU3D100','geometry_bev_distance','geometry_pair_angle',
      'geometry_top_angle','geometry_bottom_angle','nodes','floor_turn5_n',
      'matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','height_mean_ratio','omission','extension']
RISK=['A_failed','B_failed','C_failed','C_loss10_CA','C_loss10_CB',
      'C_failure_or_loss10_CA','C_failure_or_loss10_CB']

def role_events(raw,centers,role):
    if 'smallest_class' not in centers:
        centers=centers.copy()
        centers['smallest_class']=centers.class_people.eq(centers.groupby(['method','heldout_building']).class_people.transform('min'))
    for side in ['source','target']:
        fields=['class_people','highest_turn','largest_class','smallest_class']
        part=centers[['method','heldout_building','class_id']+fields].rename(columns={
             'heldout_building':'building','class_id':side+'_class',**{c:side+'_'+c for c in fields}})
        raw=raw.merge(part,on=['method','building',side+'_class'],how='left',validate='many_to_one')
    if role=='largest_to_highest_turn':
        mask=raw.source_largest_class.eq(True)&raw.target_highest_turn.eq(True)&~raw.source_highest_turn.eq(True)
    elif role=='into_smallest_class':
        mask=~raw.source_smallest_class.eq(True)&raw.target_smallest_class.eq(True)
    elif role=='between_nonsmall_classes':
        mask=~raw.source_smallest_class.eq(True)&~raw.target_smallest_class.eq(True)
    elif role=='higher_Q|slower|more_turns':
        mask=raw.historical_q_direction.eq('higher_Q')&pd.to_numeric(raw.history_target_minus_source_m_all_log_time,errors='coerce').gt(0)&raw.historical_turn_direction.eq('more_turns')
    else:mask=pd.Series(True,index=raw.index)
    return raw[mask].copy()

def main():
    rows=[];longrows=[]
    for stage in ['screen','confirm','reverse_screen','reverse_confirm']:
        reverse=stage.startswith('reverse')
        folder=OUT/stage
        comparison=pd.read_csv(folder/('REVERSE_BRANCH_COMPARISON.csv' if reverse else 'FAIR_ROLE_COMPARISON.csv'))
        risk=pd.read_csv(folder/('REVERSE_BRANCH_RISK_TIME.csv' if reverse else 'FAIR_ROLE_RISK_TIME.csv'))
        rolecol='branch' if reverse else 'fair_role'
        roles=['into_smallest_class','between_nonsmall_classes'] if reverse else ['largest_to_highest_turn']
        comparison=comparison.rename(columns={rolecol:'role'});risk=risk.rename(columns={rolecol:'role'});rolecol='role'
        if not reverse:
            sc=pd.read_csv(folder/'SEMANTIC_ROLE_COMPARISON.csv').rename(columns={'semantic_role':'role'})
            sr=pd.read_csv(folder/'ALL_OUTCOMES_BY_SEMANTIC_ROLE.csv.gz').rename(columns={'semantic_role':'role'})
            comparison=pd.concat([comparison,sc[sc.role.eq('higher_Q|slower|more_turns')]],ignore_index=True)
            risk=pd.concat([risk,sr[sr.role.eq('higher_Q|slower|more_turns')]],ignore_index=True)
            roles.append('higher_Q|slower|more_turns')
        rawcols=set(['event_id','pool_id','image','building','method','phase','n','m','source_class','target_class',
                     'background_id','block_id','D','X','Y','Z','A_members','B_members','C_members','A_class_vector',
                     'source_capacity','target_capacity','background_target_n','background_source_n',
                     'historical_q_direction','historical_turn_direction','history_target_minus_source_m_all_log_time',
                     'A_team_key','B_team_key','C_team_key','B8L2_CA','B8L2_CB','B8L2_gap']+RISK)
        raw=pd.read_csv(ROOT/'results'/stage/'EVENT_METRICS.csv.gz',usecols=lambda c:c in rawcols)
        centers=pd.read_csv(folder/('REVERSE_CLASS_SIZE_ROLES.csv' if reverse else 'FOLD_CLASS_ROLE_MAP.csv'))
        for role in roles:
            er=role_events(raw,centers,role)
            q=comparison[(comparison[rolecol]==role)&(comparison.metric=='B8L2')]
            for x in q.itertuples(index=False):
                config=(int(x.n),int(x.m))
                if config not in SELECTED.get(x.method,{}):continue
                if role=='higher_Q|slower|more_turns' and (x.method!='MSDGEOM_SCOPE_K4' or config!=(20,6)):continue
                if role=='between_nonsmall_classes' and x.m<7:continue
                if role=='into_smallest_class' and x.m>=7:continue
                g=er[(er.phase==x.phase)&(er.method==x.method)&(er.n==x.n)&(er.m==x.m)]
                assert len(g)==x.attempted_events
                rolekey={rolecol:role,'phase':x.phase,'method':x.method,'n':x.n,'m':x.m}
                comp=comparison
                rk=risk
                for key,value in rolekey.items():
                    comp=comp[comp[key]==value];rk=rk[rk[key]==value]
                row={'stage':stage,'phase':x.phase,'method':x.method,'role':role,'n':x.n,'m':x.m,
                     'evaluation_condition':'Manual','use':SELECTED[x.method][config],
                     'fraction_team_replaced':x.m/x.n,'seat_net_l1':2*x.m,
                     'attempted_events':len(g),'attempted_images':g.pool_id.nunique(),'attempted_buildings':g.building.nunique(),
                     'unique_ABC_endpoints':pd.unique(g[['A_team_key','B_team_key','C_team_key']].to_numpy().ravel()).size,
                     'unique_D':g[['pool_id','background_id']].drop_duplicates().shape[0],
                     'unique_XYZ':g[['pool_id','block_id']].drop_duplicates().shape[0]}
                for c in comp.itertuples(index=False):
                    dd=c._asdict();dd['role']=dd.pop(rolecol);longrows.append(dd)
                    if c.metric not in CORE:continue
                    for field in ['within_image_equal','cross_image_equal','gap_image_equal','ratio_of_image_means',
                                  'valid_images','valid_buildings','gap_positive_images','gap_positive_buildings',
                                  'BA_image_equal','CA_image_equal','CB_image_equal',
                                  'CA_positive_images','CA_valid_images','CA_positive_buildings','CA_valid_buildings',
                                  'CB_positive_images','CB_valid_images','CB_positive_buildings','CB_valid_buildings']:
                        if c.metric!='B8L2' and field not in ['within_image_equal','cross_image_equal','gap_image_equal',
                             'valid_images','gap_positive_images','CA_image_equal','CB_image_equal']:continue
                        row[c.metric+'_'+field]=getattr(c,field)
                for c in rk.itertuples(index=False):
                    if c.metric not in RISK+['record_time_CA_pct','record_time_CB_pct']:continue
                    row[c.metric+'_image_equal']=c.mean_image_equal
                    row[c.metric+'_valid_images']=c.valid_images
                    row[c.metric+'_valid_events']=c.valid_events
                    if c.metric.startswith('record_time'):
                        row[c.metric+'_negative_images']=c.negative_images
                for metric in RISK:
                    vals=pd.to_numeric(g[metric],errors='coerce');has=vals.notna();occur=vals.eq(1)
                    row[metric+'_raw_count']=int(occur.sum());row[metric+'_raw_valid_events']=int(has.sum())
                    row[metric+'_affected_images']=g.loc[occur,'pool_id'].nunique()
                    row[metric+'_affected_buildings']=g.loc[occur,'building'].nunique()
                seatcounts=[int(dict(item.rsplit(':',1) for item in v.split('|'))[s]) for v,s in zip(g.A_class_vector,g.source_class)]
                fractions=g.m.to_numpy()/np.asarray(seatcounts)
                row.update(A_source_seats_min=min(seatcounts),A_source_seats_max=max(seatcounts),
                           source_seats_replaced_fraction_min=float(min(fractions)),
                           source_seats_replaced_fraction_event_median=float(np.median(fractions)),
                           source_seats_replaced_fraction_max=float(max(fractions)),
                           D_source_min=g.background_source_n.min(),D_source_max=g.background_source_n.max(),
                           D_target_min=g.background_target_n.min(),D_target_max=g.background_target_n.max(),
                           D_target_zero_events=int(g.background_target_n.eq(0).sum()),
                           images_all_D_target_zero=int(g.groupby('pool_id').background_target_n.max().eq(0).sum()),
                           images_target_block_equals_available_target_class=int(g.groupby('pool_id').target_capacity.max().eq(x.m).sum()),
                           images_with_multiple_target_blocks=int(g.groupby('pool_id').Z.nunique().gt(1).sum()),
                           target_capacity_min=g.target_capacity.min(),target_capacity_max=g.target_capacity.max())
                row['evidence_identity']='exploratory_selection' if x.phase=='screen' else ('selection_unseen_buildings_internal_v2' if x.phase=='selection_heldout_building' else 'new_images_in_selection_buildings_internal_v2')
                rows.append(row)
    table=pd.DataFrame(rows).sort_values(['method','n','m','stage','phase','role'])
    write_csv(OUT/'FINAL_CONDITIONS_COMPACT.csv',table)
    write_csv(OUT/'FINAL_CONDITIONS_ALL_COMPONENTS.csv.gz',pd.DataFrame(longrows))
    (OUT/'FINAL_CONDITIONS_README.md').write_text('''# 最终条件表的口径

`FINAL_CONDITIONS_COMPACT.csv`按stage、phase、method、role、n、m保存主推荐及有比较价值的邻近条件。`FINAL_CONDITIONS_ALL_COMPONENTS.csv.gz`保留这些条件的全部已汇总分项。完整搜索空间仍在各stage的方法、角色及反推分支表中，未进入紧凑表不是被删除。

同类幅度=|B-A|；跨类幅度=(|C-A|+|C-B|)/2；gap=跨类-同类。主要均值先均衡同XYZ内背景层、再XYZ、方向、图片；建筑另汇总。B8L2、D10、IoU3D100分数越高越好；几何距离只说明变化幅度。定位角误差、omission、extension的负向CB通常表示改善；结构点数增加本身不代表更正确。

每项 *_image_equal 是图片均衡统计；*_raw_count / *_raw_valid_events 是原始事件计数，分母不同，不能互换。*_affected_images 是出现过该风险的图片数。C_failed原始分母包括所有尝试；C_loss10使用对应两队可评分的真实分母。失败未补零，失败/明显损失复合指标独立保留。时间是库存标注记录总秒数的相对变化，不是新测生产耗时；各时间量保留实际图片与事件支持。

source_seats_replaced_fraction=m/A队真实源类席位；fraction_team_replaced=m/n；这两者均不同于m/source_capacity。D目标类人数、目标类全换及Z变化均来自实际成员，不凭类别规模假设。小类定义来自各楼外折历史人数最小类；最大类→最高困难转折角色也只用楼外历史定义。

筛选与确认分开。selection_heldout_building为本轮该次选型未用建筑的内部v2检查，数据不是全新外部盲测。部分补充条件是在此次确认表中发现更有意思的方向，需按补充探索解读，不抹去原stage身份。
''')
    print({'rows':len(table),'methods':table.method.nunique(),'file':str(OUT/'FINAL_CONDITIONS_COMPACT.csv')})

if __name__=='__main__':main()
