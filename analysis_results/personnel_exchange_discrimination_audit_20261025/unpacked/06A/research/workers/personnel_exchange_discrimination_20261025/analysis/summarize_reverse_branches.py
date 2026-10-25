#!/usr/bin/env python3
"""Separate the actual small-class entering direction from large-branch swaps."""
import argparse
from pathlib import Path
import pandas as pd
from summarize_exchange import aggregate,separation_table,effect_long,BASE,POOL,write_csv

STEMS=['B8L2','D10','IoU3D100','iou_2d','geometry_bev_distance','geometry_pair_angle',
       'geometry_top_angle','geometry_bottom_angle','geometry_log_area_distance',
       'geometry_centroid_distance','nodes','floor_turn5_n','floor_short_edge_03_n',
       'floor_redundant5_n','matched_ref_horizontal_abs_deg','matched_ref_top_abs_deg',
       'matched_ref_bottom_abs_deg','height_mean_ratio','height_mean_h',
       'floor_area_camera_h2','omission','extension','reference_node_shortfall',
       'ref_node_recall_5','ref_edge_recall_5']
RISKS=['A_failed','B_failed','C_failed','C_failure_or_loss10_CA','C_failure_or_loss10_CB',
       'C_loss10_CA','C_loss10_CB','record_time_CA_pct','record_time_CB_pct']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--summary',type=Path,required=True)
    ap.add_argument('--metrics',type=Path,required=True);a=ap.parse_args();out=a.summary
    header=pd.read_csv(out/'POOL_DIRECTION_SUMMARY.csv.gz',nrows=0).columns
    core=[s+'_'+x for s in STEMS for x in ['within','cross','gap','CA','CB','BA']]
    cols=[c for c in core+RISKS if c in header]
    metadata=POOL+['source_class','target_class','n_events','n_metric_records','n_pending']
    keep=set(metadata+cols+[c+'__event_n' for c in cols])
    direction=pd.read_csv(out/'POOL_DIRECTION_SUMMARY.csv.gz',usecols=lambda c:c in keep)
    rawcols=set(POOL+['source_class','target_class','background_id','block_id','A_team_key','B_team_key','C_team_key']+cols)
    raw=pd.read_csv(a.metrics,usecols=lambda c:c in rawcols)
    centers=pd.read_csv(out/'FOLD_CLASS_ROLE_MAP.csv')
    centers['smallest_class']=centers.class_people.eq(centers.groupby(['method','heldout_building']).class_people.transform('min'))
    write_csv(out/'REVERSE_CLASS_SIZE_ROLES.csv',centers)
    for side in ['source','target']:
        add=centers[['method','heldout_building','class_id','class_people','smallest_class']].rename(
            columns={'heldout_building':'building','class_id':side+'_class',
                     'class_people':side+'_class_people','smallest_class':side+'_smallest'})
        direction=direction.merge(add,on=['method','building',side+'_class'],how='left',validate='many_to_one')
        raw=raw.merge(add,on=['method','building',side+'_class'],how='left',validate='many_to_one')
    def masks(f):
        s=f.source_smallest.eq(True);t=f.target_smallest.eq(True)
        return {'into_smallest_class':~s&t,'out_of_smallest_class':s&~t,
                'between_nonsmall_classes':~s&~t,'all_registered_directions':pd.Series(True,index=f.index)}
    dp=masks(direction);rp=masks(raw);pools=[];buildings=[];rawbranches=[]
    for branch,mask in dp.items():
        if not mask.any():continue
        p=aggregate(direction[mask],POOL,cols);p['branch']=branch
        b=aggregate(p,BASE+['building'],cols);b['branch']=branch
        r=raw[rp[branch]].copy();r['branch']=branch
        pools.append(p);buildings.append(b);rawbranches.append(r)
    pool=pd.concat(pools,ignore_index=True);building=pd.concat(buildings,ignore_index=True);br=pd.concat(rawbranches,ignore_index=True)
    write_csv(out/'REVERSE_BRANCH_POOL_SUMMARY.csv.gz',pool)
    write_csv(out/'REVERSE_BRANCH_BUILDING_SUMMARY.csv.gz',building)
    write_csv(out/'REVERSE_BRANCH_COMPARISON.csv',separation_table(pool,building,br,BASE+['branch'],STEMS))
    write_csv(out/'REVERSE_BRANCH_RISK_TIME.csv',effect_long(pool,building,br,BASE+['branch'],[c for c in RISKS if c in cols]))
    db=aggregate(pool,BASE+['branch','difficulty','building'],cols)
    write_csv(out/'REVERSE_BRANCH_DIFFICULTY_COMPARISON.csv',separation_table(pool,db,br,BASE+['branch','difficulty'],STEMS))
    (out/'REVERSE_BRANCH_README.md').write_text('''# 真实团队响应反推类：小类进入与大分支分别评价

smallest_class由各楼外折的真实类别人数最小值确定，人员数来自冻结中心members；不根据目标效果选择。into_smallest_class是非最小类→最小类，between_nonsmall_classes是两个非最小类之间的替换。全方向表同时保留。类别不要求人数均衡，小类允许按其实际容量使用。

所有方向沿用已注册严格ABC；没有为显示好结果改成员、改规模或删失败。某方向因源类无法提供2m人而没有注册时，不冒充已测负结果。各branch会引用同一事件，不能把分表事件数相加称新的独立证据。

按原phase分别给筛选、同楼新图和本轮选型未使用建筑；共同背景层与XYZ已在原POOL_DIRECTION表中均衡，再对方向/图/楼汇总。小类进入效果与其余两个大分支的差异可以不同，不能用总体平均相互替代。
''')
    print({'summary':str(out),'branch_rows':len(pool),'methods':pool.method.nunique(),
           'phases':sorted(pool.phase.unique()),'branches':sorted(pool.branch.unique())})


if __name__=='__main__':main()
