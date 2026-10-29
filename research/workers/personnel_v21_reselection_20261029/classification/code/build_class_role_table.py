#!/usr/bin/env python3
"""Semantic ranks from training history; never assigns target-outcome roles."""
import argparse,gzip,json,os,warnings
from pathlib import Path
import numpy as np,pandas as pd
warnings.filterwarnings('ignore',category=pd.errors.PerformanceWarning)
ROOT=Path(__file__).resolve().parents[1]
AXES={
'turn':'m_all_turn_n','hard_turn':'m_hard_turn_n','challenge_turn':'m_challenge_turn_n',
'Q':'m_all_B8L2','lowtail_Q':'m_all_B8L2_p20','log_time':'m_all_log_time',
'area':'m_all_log_area_ratio','height':'m_all_log_height','redundancy':'m_all_near_straight_nodes_5deg',
'bottom':'m_all_matched_bottom_bias_deg','top':'m_all_matched_top_bias_deg',
'semi_turn':'s_all_turn_n','semi_Q':'s_all_B8L2','semi_log_time':'s_all_log_time',
}
def save(d,path):
    raw=d.to_csv(index=False).encode('utf-8-sig')
    if path.suffix=='.gz':raw=gzip.compress(raw,compresslevel=6,mtime=0)
    tmp=path.with_name(path.name+'.partial')
    with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    tmp.replace(path)
def add_ranks(d,axes):
    group=d.groupby(['method','heldout_building'])
    for axis,column in axes.items():
        rank=group[column].rank(method='dense',ascending=True)
        levels=group[column].transform(lambda s:s.dropna().nunique())
        d['rank_'+axis]=rank
        d['rank_'+axis+'_levels']=levels
        d['range_'+axis]=group[column].transform('max')-group[column].transform('min')
        d['relative_rank_'+axis]=np.where(levels.gt(1),(rank-1)/(levels-1),np.where(rank.notna(),.5,np.nan))
        d['lowest_'+axis]=rank.eq(1)&levels.gt(1)
        d['highest_'+axis]=rank.eq(levels)&levels.gt(1)
    return d
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
    d=pd.read_csv(ROOT/'CLASS_MEMBERS_COMMON_HISTORY_CENTERS_ALL_LOBO.csv.gz',low_memory=False)
    native_files=[
      (args.repo/'research/data/releases/v2.1/fusion_role_classification/CENTERS_ALL_LOBO.csv.gz','primary_response'),
      (ROOT/'target_rfuse/CENTERS_ALL_LOBO.csv.gz','target_equal_response'),
    ]
    nc=[]
    fieldmap={'all_floor_turn5_n':'own_fusion_all_turn','hard_floor_turn5_n':'own_fusion_hard_turn','all_B8L2':'own_fusion_Q','hard_B8L2':'own_fusion_hard_Q','all_bottom_y_mean_px':'own_fusion_bottom_y_px','all_top_y_mean_px':'own_fusion_top_y_px','all_log_floor_area':'own_fusion_log_area','all_log_height_mean':'own_fusion_log_height'}
    for p,label in native_files:
        a=pd.read_csv(p);a=a[['method','heldout_building','class_id']+list(fieldmap)]
        a=a.rename(columns=fieldmap);a['own_fusion_center_source']=label;nc.append(a)
    d=d.merge(pd.concat(nc,ignore_index=True),on=['method','heldout_building','class_id'],how='left',validate='one_to_one')
    group=d.groupby(['method','heldout_building'])
    d['size_rank_desc']=group.workers.rank(method='min',ascending=False)
    d['is_dominant_class']=d.workers.eq(group.workers.transform('max'))
    d['is_smallest_class']=d.workers.eq(group.workers.transform('min'))
    d['training_class_share']=d.workers/group.workers.transform('sum')
    d=add_ranks(d,AXES)
    d=add_ranks(d,{k.replace('own_fusion_','response_'):k for k in fieldmap.values()})
    d['k']=d.groupby(['method','heldout_building']).class_id.transform('nunique')
    aliases={'turn_rank_asc':'rank_turn','hard_turn_rank_asc':'rank_hard_turn','challenge_turn_rank_asc':'rank_challenge_turn','q_rank_asc':'rank_Q','time_rank_asc':'rank_log_time','area_rank_asc':'rank_area','height_rank_asc':'rank_height','redundancy_rank_asc':'rank_redundancy','response_turn_rank_asc':'rank_response_all_turn','response_hard_turn_rank_asc':'rank_response_hard_turn','response_q_rank_asc':'rank_response_Q'}
    for alias,original in aliases.items():d[alias]=d[original]
    d['dominant']=d.is_dominant_class
    def semantic(r):
        x=['人数最多类' if r.is_dominant_class else ('人数最少类' if r.is_smallest_class else '中间容量类')]
        for axis,pos,neg in [('turn','总体转折较多','总体转折较少'),('challenge_turn','复杂机会转折较多','复杂机会转折较少'),('Q','历史Q较高','历史Q较低'),('log_time','来源内记录时间较长','来源内记录时间较短'),('area','相对面积较大','相对面积较小'),('height','相对高度较高','相对高度较低'),('redundancy','近共线冗余较多','近共线冗余较少')]:
            if getattr(r,'highest_'+axis):x.append(pos)
            elif getattr(r,'lowest_'+axis):x.append(neg)
        if pd.notna(r.own_fusion_all_turn):
            if r.highest_response_all_turn:x.append('自身模型总体融合转折响应最高')
            if r.highest_response_Q:x.append('自身模型融合Q响应最高')
        return '；'.join(x)
    d['semantic_training_role']=d.apply(semantic,axis=1)
    d['role_basis']='within-method/fold training-history rank; not target outcome; magnitude and spread retained'
    d['rank_interpretation']='ascending dense rank; log_time high means slower; area/height relative peer residual; ties retain same rank'
    save(d,ROOT/'CLASS_ROLES_ALL_LOBO.csv.gz')
    save(d[d.heldout_building.eq('ALL')],ROOT/'CLASS_ROLES_ALL.csv')
    # Compact role definitions suitable for report and cross-fold event aggregation.
    cols=['method','heldout_building','class_id','k','workers','members','is_dominant_class','is_smallest_class','dominant','training_class_share','semantic_training_role']+list(aliases)+['size_rank_desc']
    cols += [x for x in d if x.startswith('rank_') and not x.endswith('_levels')]
    cols += ['m_all_turn_n','m_hard_turn_n','m_challenge_turn_n','m_all_B8L2','m_all_log_time','m_all_log_area_ratio','m_all_log_height','m_all_near_straight_nodes_5deg','own_fusion_all_turn','own_fusion_hard_turn','own_fusion_Q','own_fusion_center_source']
    save(d[cols],ROOT/'CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz')
    # Repair scope denominator names: some pools contain only one observed class and no direction.
    s=pd.read_csv(ROOT/'METHOD_CAPACITY_SCOPE_SUMMARY.csv')
    pools=pd.read_csv(ROOT.parent/'targets/POOL_TARGET_CONDITIONS.csv')
    full=pools.groupby(['condition','scope','layer']).pool_id.nunique().rename('full_scope_pool_count').reset_index()
    s=s.rename(columns={'pool_count':'pools_with_two_or_more_observed_classes'})
    s=s.drop(columns=[c for c in s if c.startswith('full_scope_pool_count')])
    s=s.merge(full,on=['condition','scope','layer'],how='left',validate='many_to_one')
    save(s,ROOT/'METHOD_CAPACITY_SCOPE_SUMMARY.csv')
    status={'methods':d.method.nunique(),'class_fold_rows':len(d),'ALL_class_rows':int(d.heldout_building.eq('ALL').sum()),'all_persons_precisely_listed':True,'history_ranks_are_not_raw_label_numbers':True,'native_RFUSE_rows':int(d.own_fusion_Q.notna().sum())}
    (ROOT/'CLASS_ROLE_COMPLETION.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
    print(status)
if __name__=='__main__':main()

