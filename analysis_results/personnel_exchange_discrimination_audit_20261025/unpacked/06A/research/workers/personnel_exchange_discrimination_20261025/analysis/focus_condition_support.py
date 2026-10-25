#!/usr/bin/env python3
"""Exact background, source-seat fraction, and actual member repetitions."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from summarize_exchange import write_csv


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--metrics',type=Path,nargs='+',required=True)
    ap.add_argument('--centers',type=Path,nargs='+',required=True);ap.add_argument('--method',required=True)
    ap.add_argument('--n',type=int,required=True);ap.add_argument('--m',type=int,required=True)
    ap.add_argument('--role',choices=['largest_to_highest_turn','into_smallest_class','higher_Q|slower|more_turns'],default='largest_to_highest_turn')
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    keep=['stage','phase','event_id','pool_id','image','building','difficulty','method','n','m',
          'source_class','target_class','source_capacity','target_capacity','pool_n',
          'D','X','Y','Z','background_id','block_id','background_source_n','background_target_n',
          'background_unknown_n','A_members','B_members','C_members','A_class_vector',
          'A_team_key','B_team_key','C_team_key','B8L2_within','B8L2_cross','B8L2_gap','B8L2_CA','B8L2_CB',
          'A_failed','B_failed','C_failed']
    keep+=['historical_q_direction','historical_turn_direction','history_target_minus_source_m_all_log_time']
    data=pd.concat([pd.read_csv(p,usecols=lambda c:c in keep) for p in a.metrics],ignore_index=True)
    data=data[data.method.eq(a.method)&data.n.eq(a.n)&data.m.eq(a.m)].copy()
    centers=pd.concat([pd.read_csv(p) for p in a.centers],ignore_index=True)
    centers=centers.drop_duplicates(['method','heldout_building','class_id'],keep='last')
    centers['class_people']=centers.members.fillna('').map(lambda s:len(set(s.split('|'))-{''}))
    cg=centers.groupby(['method','heldout_building'])
    centers['highest_turn']=centers.m_hard_turn_n.eq(cg.m_hard_turn_n.transform('max'))
    centers['largest_class']=centers.class_people.eq(cg.class_people.transform('max'))
    centers['smallest_class']=centers.class_people.eq(cg.class_people.transform('min'))
    for side in ['source','target']:
        cc=centers[['method','heldout_building','class_id','class_people','largest_class','highest_turn','smallest_class']].rename(
          columns={'heldout_building':'building','class_id':side+'_class','class_people':side+'_fold_class_people',
                   'largest_class':side+'_largest','highest_turn':side+'_highest','smallest_class':side+'_smallest'})
        data=data.merge(cc,on=['method','building',side+'_class'],how='left',validate='many_to_one')
    if a.role=='largest_to_highest_turn':mask=data.source_largest.eq(True)&data.target_highest.eq(True)&~data.source_highest.eq(True)
    elif a.role=='into_smallest_class':mask=~data.source_smallest.eq(True)&data.target_smallest.eq(True)
    else:mask=data.historical_q_direction.eq('higher_Q')&pd.to_numeric(data.history_target_minus_source_m_all_log_time,errors='coerce').gt(0)&data.historical_turn_direction.eq('more_turns')
    data=data[mask].copy()
    def seats(row):
        vector=dict(s.rsplit(':',1) for s in row.A_class_vector.split('|'))
        return int(vector[row.source_class])
    data['source_seats_original_A']=data.apply(seats,axis=1)
    assert data.source_seats_original_A.eq(data.background_source_n+a.m).all()
    actual=[]
    for row in data.itertuples(index=False):
        A=set(row.A_members.split('|'));B=set(row.B_members.split('|'));C=set(row.C_members.split('|'))
        assert len(A)==len(B)==len(C)==a.n
        assert len(A-B)==len(A-C)==len(B-C)==a.m
        actual.append(len(A-B))
    data['actual_m_from_sets']=actual
    data['fraction_of_original_A_source_seats_replaced']=data.actual_m_from_sets/data.source_seats_original_A
    data['fraction_of_team_replaced']=data.actual_m_from_sets/data.n
    data['fraction_of_source_pool_replaced']=data.actual_m_from_sets/data.source_capacity
    data['target_entire_available_class_in_image']=data.target_capacity.eq(a.m)
    data['role']=a.role
    prefix=f'{a.method}_n{a.n}_m{a.m}'
    write_csv(a.output/(prefix+'_EXACT_SUPPORT_EVENTS.csv.gz'),data)
    poolrows=[]
    for (phase,pid),g in data.groupby(['phase','pool_id']):
        block_levels=g.groupby(['block_id','background_target_n']).B8L2_gap.mean()
        block=block_levels.groupby('block_id').mean().dropna()
        background=g.groupby('background_id').B8L2_gap.mean().dropna()
        row=dict(phase=phase,pool_id=pid,image=g.image.iloc[0],building=g.building.iloc[0],difficulty=g.difficulty.iloc[0],
            method=a.method,n=a.n,m=a.m,role=a.role,events=len(g),pool_n=g.pool_n.iloc[0],
            source_capacity=g.source_capacity.iloc[0],target_capacity=g.target_capacity.iloc[0],
            source_capacity_min=g.source_capacity.min(),source_capacity_max=g.source_capacity.max(),
            target_capacity_min=g.target_capacity.min(),target_capacity_max=g.target_capacity.max(),
            source_classes='|'.join(sorted(g.source_class.unique())),target_classes='|'.join(sorted(g.target_class.unique())),
            source_fold_class_people=g.source_fold_class_people.iloc[0],target_fold_class_people=g.target_fold_class_people.iloc[0],
            target_entire_available_class_in_image=bool(g.target_entire_available_class_in_image.all()),
            all_D_target_zero=bool(g.background_target_n.eq(0).all()),
            D_target_min=int(g.background_target_n.min()),D_target_max=int(g.background_target_n.max()),
            D_source_min=int(g.background_source_n.min()),D_source_max=int(g.background_source_n.max()),
            A_source_seats_min=int(g.source_seats_original_A.min()),A_source_seats_max=int(g.source_seats_original_A.max()),
            original_source_fraction_min=g.fraction_of_original_A_source_seats_replaced.min(),
            original_source_fraction_median=g.fraction_of_original_A_source_seats_replaced.median(),
            original_source_fraction_max=g.fraction_of_original_A_source_seats_replaced.max(),
            unique_X=g.X.nunique(),unique_Y=g.Y.nunique(),unique_Z=g.Z.nunique(),unique_D=g.D.nunique(),
            unique_XYZ=g.block_id.nunique(),unique_endpoint_teams=len(set(g[['A_team_key','B_team_key','C_team_key']].to_numpy().ravel())),
            valid_XYZ_gap=len(block),positive_XYZ_gap=int(block.gt(1e-9).sum()),
            fraction_XYZ_gap_positive=block.gt(1e-9).mean() if len(block) else np.nan,
            valid_D_gap=len(background),positive_D_gap=int(background.gt(1e-9).sum()),
            fraction_D_gap_positive=background.gt(1e-9).mean() if len(background) else np.nan,
            source_members_observed='|'.join(sorted(set('|'.join(pd.concat([g.X,g.Y])).split('|')))),
            target_members_observed='|'.join(sorted(set('|'.join(g.Z).split('|')))),
            D_target_count_event_distribution=json.dumps(g.background_target_n.value_counts().sort_index().to_dict(),ensure_ascii=False),
            D_source_count_event_distribution=json.dumps(g.background_source_n.value_counts().sort_index().to_dict(),ensure_ascii=False))
        poolrows.append(row)
    pools=pd.DataFrame(poolrows);write_csv(a.output/(prefix+'_POOL_MEMBER_BACKGROUND_SUPPORT.csv'),pools)
    rows=[]
    for phase,g in data.groupby('phase'):
        p=pools[pools.phase.eq(phase)]
        rows.append(dict(phase=phase,method=a.method,n=a.n,m=a.m,role=a.role,
            events=len(g),images=len(p),buildings=g.building.nunique(),unique_XYZ=g.block_id.nunique(),unique_D=g.background_id.nunique(),
            entire_target_class_images=int(p.target_entire_available_class_in_image.sum()),
            all_D_target_zero_images=int(p.all_D_target_zero.sum()),D_target_zero_events=int(g.background_target_n.eq(0).sum()),
            images_with_multiple_Z=int(p.unique_Z.gt(1).sum()),images_with_multiple_XYZ=int(p.unique_XYZ.gt(1).sum()),
            images_with_multiple_D=int(p.unique_D.gt(1).sum()),
            images_majority_XYZ_gap_positive=int(p.fraction_XYZ_gap_positive.gt(.5).sum()),
            images_at_least_75pct_XYZ_gap_positive=int(p.fraction_XYZ_gap_positive.ge(.75).sum()),
            images_majority_D_gap_positive=int(p.fraction_D_gap_positive.gt(.5).sum()),
            images_at_least_75pct_D_gap_positive=int(p.fraction_D_gap_positive.ge(.75).sum()),
            pool_equal_fraction_XYZ_gap_positive=p.fraction_XYZ_gap_positive.mean(),
            pool_equal_fraction_D_gap_positive=p.fraction_D_gap_positive.mean(),
            A_source_seats_min=int(g.source_seats_original_A.min()),A_source_seats_max=int(g.source_seats_original_A.max()),
            original_source_fraction_event_median=g.fraction_of_original_A_source_seats_replaced.median(),
            original_source_fraction_min=g.fraction_of_original_A_source_seats_replaced.min(),
            original_source_fraction_max=g.fraction_of_original_A_source_seats_replaced.max(),
            D_target_count_event_distribution=json.dumps(g.background_target_n.value_counts().sort_index().to_dict(),ensure_ascii=False),
            D_source_count_event_distribution=json.dumps(g.background_source_n.value_counts().sort_index().to_dict(),ensure_ascii=False)))
    result=pd.DataFrame(rows);write_csv(a.output/(prefix+'_PHASE_SUPPORT.csv'),result)
    print(result.to_json(orient='records',force_ascii=False,indent=2))


if __name__=='__main__':main()
