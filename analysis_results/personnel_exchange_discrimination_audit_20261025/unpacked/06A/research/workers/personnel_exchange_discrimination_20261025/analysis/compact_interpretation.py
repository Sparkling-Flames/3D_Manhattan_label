#!/usr/bin/env python3
"""Compact all-candidate, historical-Q-direction and structure-opportunity views."""
import argparse
import gzip
import json
from pathlib import Path
import numpy as np
import pandas as pd
from summarize_exchange import aggregate, separation_table, effect_long, BASE, POOL, write_csv

STEMS=['B8L2','D10','geometry_bev_distance','geometry_pair_angle',
       'geometry_top_angle','geometry_bottom_angle','nodes','floor_turn5_n']
RISKS=['A_failed','B_failed','C_failed','C_failure_or_loss10_CA','C_failure_or_loss10_CB',
       'C_loss10_CA','C_loss10_CB','C_improved_CA','C_improved_CB',
       'record_time_CA_pct','record_time_CB_pct']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--summary',type=Path,required=True)
    ap.add_argument('--metrics',type=Path,required=True);ap.add_argument('--inputs',type=Path,required=True)
    args=ap.parse_args();out=args.summary
    core=[s+'_'+suffix for s in STEMS for suffix in ['within','cross','gap','CA','CB','BA']]
    available=pd.read_csv(out/'POOL_DIRECTION_SUMMARY.csv.gz',nrows=0).columns
    cols=[c for c in core+RISKS if c in available]
    wanted=set(POOL+['source_class','target_class','semantic_role','n_events','n_metric_records','n_pending']
               +cols+[c+'__event_n' for c in cols])
    direction=pd.read_csv(out/'POOL_DIRECTION_SUMMARY.csv.gz',usecols=lambda c:c in wanted)
    raw_wanted=set(BASE+['pool_id','image','building','difficulty','background_id','block_id',
                         'A_team_key','B_team_key','C_team_key','historical_q_direction']+cols)
    raw=pd.read_csv(args.metrics,usecols=lambda c:c in raw_wanted)
    direction['quality_direction']=direction.semantic_role.str.split('|').str[0]
    raw['quality_direction']=raw.historical_q_direction
    qpool=aggregate(direction,POOL+['quality_direction'],cols)
    qbuild=aggregate(qpool,BASE+['quality_direction','building'],cols)
    write_csv(out/'HISTORICAL_Q_DIRECTION_POOL.csv.gz',qpool)
    write_csv(out/'HISTORICAL_Q_DIRECTION_COMPARISON.csv',separation_table(qpool,qbuild,raw,BASE+['quality_direction'],STEMS))
    write_csv(out/'HISTORICAL_Q_DIRECTION_RISK_TIME.csv',effect_long(qpool,qbuild,raw,BASE+['quality_direction'],[c for c in RISKS if c in cols]))
    # Fair directional roles by difficulty, using the already-balanced pool rows.
    fwanted=set(POOL+['fair_role','n_events','n_metric_records','n_pending']+cols+[c+'__event_n' for c in cols])
    fair=pd.read_csv(out/'FAIR_ROLE_POOL_SUMMARY.csv.gz',usecols=lambda c:c in fwanted)
    fbuild=aggregate(fair,BASE+['fair_role','difficulty','building'],cols)
    # Raw matching counts are unavailable without repeating role attachment here;
    # use carried actual event counts and do not invent unique endpoint counts.
    empty_raw=pd.DataFrame(columns=BASE+['fair_role','difficulty','background_id','block_id',
                                      'A_team_key','B_team_key','C_team_key']+cols)
    write_csv(out/'FAIR_ROLE_DIFFICULTY_COMPARISON.csv',separation_table(fair,fbuild,empty_raw,BASE+['fair_role','difficulty'],STEMS))
    write_csv(out/'FAIR_ROLE_DIFFICULTY_RISK_TIME.csv',effect_long(fair,fbuild,empty_raw,BASE+['fair_role','difficulty'],[c for c in RISKS if c in cols]))
    # Existing structure-opportunity ledger, requiring exact bound reference identity.
    opp=pd.read_csv(args.inputs/'IMAGE_DIFFICULTY_OPPORTUNITIES.csv')
    with gzip.open(args.inputs/'INPUT_SNAPSHOT.json.gz','rt') as f:ps=json.load(f)['images']
    meta=pd.DataFrame([p['meta'] for p in ps])[['pool_id','image','reference_id']]
    fields=['image','reference_id','structure_opportunity','ref_turn5','ref_short_edges','gt_detail_omission_mark']
    joined=meta.merge(opp[fields],on=['image','reference_id'],how='left',validate='many_to_one')
    joined['structure_opportunity']=joined.structure_opportunity.fillna('unknown_or_reference_mismatch')
    joined['reference_turn_group']=np.select([joined.ref_turn5.le(4),joined.ref_turn5.gt(4)],
                                             ['reference_4_or_fewer','reference_more_than_4'],default='unknown')
    write_csv(out/'POOL_STRUCTURE_OPPORTUNITY_LINK.csv',joined)
    pool=aggregate(direction,POOL,cols)
    for stratifier in ['structure_opportunity','reference_turn_group']:
        p=pool.merge(joined[['pool_id',stratifier]],on='pool_id',how='left',validate='many_to_one')
        r=raw.merge(joined[['pool_id',stratifier]],on='pool_id',how='left',validate='many_to_one')
        b=aggregate(p,BASE+[stratifier,'building'],cols)
        write_csv(out/(stratifier.upper()+'_COMPARISON.csv'),separation_table(p,b,r,BASE+[stratifier],STEMS))
    # One compact row for every method/n/m: no positive-only pruning.
    comparison=pd.read_csv(out/'METHOD_N_M_COMPARISON.csv')
    compact=None
    keys=BASE
    fieldlist=['valid_images','valid_buildings','within_image_equal','cross_image_equal','gap_image_equal',
               'ratio_of_image_means','gap_positive_images','gap_positive_buildings','gap_building_equal',
               'CA_image_equal','CB_image_equal']
    for metric in ['B8L2','geometry_bev_distance','geometry_pair_angle','nodes']:
        g=comparison[comparison.metric.eq(metric)][keys+fieldlist].copy()
        g=g.rename(columns={c:metric+'__'+c for c in fieldlist})
        compact=g if compact is None else compact.merge(g,on=keys,how='outer',validate='one_to_one')
    risks=pd.read_csv(out/'ALL_OUTCOMES_BY_METHOD_N_M.csv.gz')
    for metric in RISKS:
        g=risks[risks.metric.eq(metric)][keys+['mean_image_equal','valid_images','valid_events']].copy()
        g=g.rename(columns={c:metric+'__'+c for c in ['mean_image_equal','valid_images','valid_events']})
        compact=compact.merge(g,on=keys,how='outer',validate='one_to_one')
    write_csv(out/'ALL_CANDIDATES_COMPACT.csv',compact)
    # Capacity and actual target-member coverage for the main semantic role.
    coverage_cols=['pool_id','building','method','n','m','source_class','target_class','target_capacity',
                   'Z','X','Y','D','background_target_n']
    ce=pd.read_csv(args.metrics,usecols=coverage_cols)
    center=pd.read_csv(out/'FOLD_CLASS_ROLE_MAP.csv')
    for side in ['source','target']:
        attrs=center[['method','heldout_building','class_id','largest_class','highest_turn']].rename(
            columns={'heldout_building':'building','class_id':side+'_class',
                     'largest_class':side+'_largest','highest_turn':side+'_highest'})
        ce=ce.merge(attrs,on=['method','building',side+'_class'],how='left',validate='many_to_one')
    ce=ce[ce.source_largest.eq(True)&ce.target_highest.eq(True)&~ce.source_highest.eq(True)]
    cover=[]
    for (method,n,m),g in ce.groupby(['method','n','m']):
        pp=g.groupby('pool_id').agg(target_cap=('target_capacity','first'),Z_sets=('Z','nunique'),
             X_sets=('X','nunique'),Y_sets=('Y','nunique'),D_sets=('D','nunique'),
             target_bg_levels=('background_target_n','nunique'))
        cover.append(dict(method=method,n=n,m=m,images=len(pp),buildings=g.building.nunique(),
             images_Z_changes=int(pp.Z_sets.gt(1).sum()),images_target_spare=int(pp.target_cap.gt(m).sum()),
             median_target_spare=(pp.target_cap-m).median(),
             images_background_target_changes=int(pp.target_bg_levels.gt(1).sum()),
             unique_target_members=len(set('|'.join(g.Z).split('|')))))
    write_csv(out/'TARGET_BLOCK_CAPACITY_AND_VARIATION.csv',pd.DataFrame(cover))
    receipt=dict(derived_from='completed hierarchical per-pool results',
                 q_direction='Building-excluded historical class-center Q sign; all feasible class pairs with each sign retained.',
                 opportunity='Existing actual reference-bound opportunity table; omitted real details are not automatically errors.',
                 fair_difficulty='Same balanced role/pool values, then image/building equal; event counts carried, unique endpoint counts intentionally not inferred.',
                 candidate_rows=len(compact),candidate_selection='No pruning in ALL_CANDIDATES_COMPACT.')
    (out/'INTERPRETATION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
