#!/usr/bin/env python3
"""Deterministic representative/counterexample selection; never fits any class.

Filters and ordering are written to the output together with every eligible
denominator. This post-evaluation case selection cannot validate the method.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from evaluate_common import attach,boolcol,savej,PRIMARY

def main():
    cols=['event_id','panel_id','pool_id','image','image_id','building','difficulty','k','worker_a','worker_b','background_id','B8L2_a','B8L2_b','both_complete','complete_a','complete_b','stable_main','either_failure','abs_delta_Q','delta_Q','floor_change','mean_height_prism_pair_iou','beta_a','beta_b','theta_a','theta_b','q_support_a','q_support_b','theta_support_a','theta_support_b','node_count_difference','upper_bound_shift_max_deg','lower_bound_shift_max_deg']
    e=pd.concat(pd.read_csv(HERE/'COMMON_EVENT_ANALYSIS_INPUT.csv.gz',usecols=cols,chunksize=25000),ignore_index=True)
    for c in ['both_complete','complete_a','complete_b','stable_main','either_failure','q_support_a','q_support_b','theta_support_a','theta_support_b']:e[c]=boolcol(e[c])
    l=pd.read_csv(HERE/'ALL_SELECTED_AND_BASELINE_LABELS.csv.gz',low_memory=False)
    for method in ['forward_selected','reverse_selected']:
        e['relation__'+method]='unknown'
        for b,g in e.groupby('building'):
            ca,cb,rel=attach(g,l[l.method_id.eq(method)&l.heldout_building.eq(b)])
            e.loc[g.index,'class_a__'+method]=ca;e.loc[g.index,'class_b__'+method]=cb;e.loc[g.index,'relation__'+method]=rel
    e=e[e.panel_id.eq(PRIMARY)&e.k.eq(16)].copy()
    e['mean_team_Q']=(e.B8L2_a+e.B8L2_b)/2
    e['opposes_historical_Q']=(e.beta_b-e.beta_a)*e.delta_Q<0
    e['completion_switch']=e.complete_a.ne(e.complete_b)
    within=e['relation__reverse_selected'].eq('within');between=e['relation__reverse_selected'].eq('between')
    median=e.loc[within&e.stable_main,'abs_delta_Q'].median()
    e['distance_to_typical_stable_absQ']=(e.abs_delta_Q-median).abs()
    specs=[
      ('within_typical','同类且相近的普通例',within&e.stable_main&e.mean_team_Q.ge(70),['distance_to_typical_stable_absQ','event_id'],[True,True],'reverse within; joint main stable; average team B8 >=70; closest to all within-stable median absolute Q change'),
      ('within_large','同类仍大变的反例',within&e.both_complete&e.abs_delta_Q.ge(10),['abs_delta_Q','event_id'],[False,True],'reverse within; both complete; absolute B8 change >=10; descending absolute change'),
      ('within_failure','同类换人改变完整性的反例',within&e.completion_switch,['event_id'],[True],'reverse within; exactly one complete; deterministic event ID'),
      ('between_stable','跨类仍相近的反例',between&e.stable_main&e.mean_team_Q.ge(70),['floor_change','abs_delta_Q','event_id'],[True,True,True],'reverse between; joint main stable; average team B8 >=70; least floor and Q change'),
      ('between_improves_against_Q','较低历史Q成员带来更高团队Q',between&e.both_complete&e.q_support_a&e.q_support_b&e.opposes_historical_Q&e.abs_delta_Q.ge(5),['abs_delta_Q','event_id'],[False,True],'reverse between; both historical Q supported; signed team change opposes historical Q order; absolute team B8 change >=5'),
      ('stable_low_Q','稳定但质量仍低',within&e.stable_main&e.mean_team_Q.le(55),['mean_team_Q','event_id'],[True,True],'reverse within; joint main stable; average team B8 <=55; ascending team quality'),
      ('floor_close_3d_different','底面近而平均高度棱柱不同',e.both_complete&e.floor_change.le(.02)&e.mean_height_prism_pair_iou.le(.85),['mean_height_prism_pair_iou','event_id'],[True,True],'both complete; floor difference <=.02; mean-height prism pair IoU <=.85; illustrative, not exact general 3D truth'),
      ('hard_rule_disagreement','困难图中两套历史类别解释不同',e.difficulty.eq('hard')&e.both_complete&e['relation__forward_selected'].ne('unknown')&e['relation__reverse_selected'].ne('unknown')&e['relation__forward_selected'].ne(e['relation__reverse_selected']),['abs_delta_Q','event_id'],[False,True],'hard image; forward and reverse relation disagree; both complete; largest absolute change')
    ]
    chosen=[];catalog=[];used_images=set();used_buildings={}
    for key,title,mask,sort,ascending,definition in specs:
        pool=e.loc[mask].sort_values(sort,ascending=ascending)
        r=dict(case_type=key,title_zh=title,base_panel=PRIMARY,k=16,eligibility=definition,eligible_events=len(pool),eligible_images=pool.image_id.nunique(),eligible_buildings=pool.building.nunique(),sorting=sort,ascending=ascending)
        available=pool[~pool.image_id.isin(used_images)&pool.building.map(used_buildings).fillna(0).lt(2)]
        r['eligible_after_display_diversity']=len(available)
        if len(available):
            item=available.iloc[0].to_dict();item.update(case_type=key,title_zh=title)
            chosen.append(item);used_images.add(item['image_id']);used_buildings[item['building']]=used_buildings.get(item['building'],0)+1
            r['selected_event_id']=item['event_id']
        else:r['selected_event_id']=None
        catalog.append(r)
    pd.DataFrame(chosen).to_csv(HERE/'REPRESENTATIVE_CASES.csv',index=False)
    savej(HERE/'CASE_SELECTION_CATALOG.json',{'post_hoc_presentation_only':True,'model_or_threshold_adjustment':False,'max_cases':8,'diversity_limit':'one event per image; at most two per building','all_filters_and_denominators':catalog})
    print(pd.DataFrame(chosen)[['case_type','event_id','image','worker_a','worker_b','B8L2_a','B8L2_b','floor_change','mean_height_prism_pair_iou']].to_string(index=False))
if __name__=='__main__':main()
