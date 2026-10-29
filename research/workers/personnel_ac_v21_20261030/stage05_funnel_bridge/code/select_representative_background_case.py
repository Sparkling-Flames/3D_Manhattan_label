"""Select one observed fixed-XZ background comparison nearest its cell mean.

This is a transparent post-result mechanism case selection from the complete
registered comparison set, not a research-design change or new fusion.
"""
from pathlib import Path
import gzip,hashlib,json
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parents[1];BASE=OUT.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 effect_path=OUT/'STRICT66_EXACT_BACKGROUND_EFFECTS.csv.gz';index_path=OUT/'STRICT66_EXACT_F_NEUTRAL_VS_B_OUTSIDE_BACKGROUND_PAIRS.csv.gz'
 e=pd.read_csv(effect_path);index=pd.read_csv(index_path);cs=pd.read_csv(OUT/'STRICT66_EXACT_BACKGROUND_CONDITION_EFFECTS.csv')
 pool='wc2JMjhGNzB-53__manual__c22e59afe7';method='TARGET_DSTRUCT_K3'
 cs=cs[(cs.pool_id==pool)&cs.method.eq(method)&cs.n.eq(11)&cs.m.eq(9)&cs.metric.eq('B8L2')];assert len(cs)==1
 avg=float(cs.iloc[0].F_minus_B_effect)
 candidates=e[(e.pool_id==pool)&e.n.eq(11)&e.m.eq(9)&e.metric.eq('B8L2')&e.paired_effect_valid].copy()
 # Explicitly prefer the main interpretation method as the display label;
 # identical physical four-endpoint observations across methods occur once.
 candidates['_display_priority']=candidates.method.ne(method).astype(int)
 candidates=candidates.sort_values(['_display_priority','method','background_comparison_id']).drop_duplicates('physical_background_comparison_id')
 candidates['distance_to_condition_mean']=(candidates.F_minus_B_effect-avg).abs()
 candidates=candidates.sort_values(['distance_to_condition_mean','physical_background_comparison_id'])
 assert len(candidates)==6
 selected=candidates.iloc[0];physical=selected.physical_background_comparison_id
 all_methods=index[index.physical_background_comparison_id.eq(physical)];r=all_methods[all_methods.method.eq(method)].iloc[0]
 with open(OUT/'BACKGROUND_WC2_53_ALL_VALID_PHYSICAL_CANDIDATES.csv','w',encoding='utf-8-sig',newline='') as f:
  candidates.drop(columns='_display_priority').to_csv(f,index=False)
 epdir=BASE/'stage03_endpoints/pools'/pool;teams={r[k] for k in ['F_A_team_key','F_C_team_key','B_A_team_key','B_C_team_key']}
 found={};files=[]
 for p in sorted(epdir.glob('part_*.jsonl.gz')):
  anyfound=False
  with gzip.open(p,'rt',encoding='utf-8') as f:
   for line in f:
    a=json.loads(line)
    if a['team_key'] in teams:found[a['team_key']]=a;anyfound=True
  if anyfound:files.append({'path':str(p.relative_to(BASE)),'sha256':sha(p)})
  if len(found)==4:break
 assert set(found)==teams
 metric_path=BASE/'stage04_metrics/metric_shards'/(pool+'.csv.gz')
 md=pd.read_csv(metric_path,low_memory=False);md=md[md.event_id.isin([r.F_event_id,r.B_event_id])].set_index('event_id');assert len(md)==2
 link=pd.read_csv(BASE/'stage01_registered/DESIGN_LINKS.csv.gz',usecols=['event_id','design_family','input_orientation_sign','bridge_strict_source_class','bridge_strict_target_class'],low_memory=False)
 link=link[link.event_id.isin([r.F_event_id,r.B_event_id])]
 endpoint_rows=[];geometry={}
 for branch in ['F','B']:
  event=md.loc[r[branch+'_event_id']]
  for arm in ['A','C']:
   tk=r[branch+'_'+arm+'_team_key'];a=found[tk]
   assert set(a['member_workers'])==set((r[branch+'_D_workers']+'|'+r['X_workers' if arm=='A' else 'Z_workers']).split('|'))
   assert int(a['k'])==11 and abs(a['B8L2']-event[arm+'_B8L2'])<1e-9
   vals={k:a.get(k) for k in ['team_key','k','nodes','fusion_turn_n','fusion_short_turn_edges','B8L2','D10','geometry_area_h2','height_mean_h',
      'centroid_x_h','centroid_z_h','score_status','order_status','minimum_support','node_supports','identity_groups_n','unselected_groups_n',
      'boundary_loss','direction_loss','height_loss','ref_node_recall_9','ref_edge_recall_9']}
   vals.update(branch=branch,arm=arm,member_workers='|'.join(a['member_workers']),D_workers=r[branch+'_D_workers'],
     output_state=event[arm+'_output_state'],geometry_pair_angle_AC=event.geometry_pair_angle_AC,geometry_centroid_distance_AC=event.geometry_centroid_distance_AC)
   endpoint_rows.append(vals);geometry[branch+'_'+arm]={'team_key':tk,'geometry':a['geometry'],'member_workers':a['member_workers'],'nodes':a['nodes'],
     'full_state_in_existing_chunk':'full_state' in a,'raw_no_connection_requires_full_state_mechanism':True}
 endpoint=pd.DataFrame(endpoint_rows)
 with open(OUT/'BACKGROUND_WC2_53_SELECTED_FOUR_ENDPOINTS.csv','w',encoding='utf-8-sig',newline='') as f:endpoint.to_csv(f,index=False)
 (OUT/'BACKGROUND_WC2_53_SELECTED_FOUR_GEOMETRIES.json').write_text(json.dumps(geometry,indent=2,ensure_ascii=False))
 result={'status':'selected_from_complete_registered_substudy','purpose':'one mechanism example close to cell-average background effect, not maximum effect',
   'substudy_registered_method_comparisons':120,'substudy_physical_comparisons':108,'cell_registered_method_background_comparisons':8,
   'cell_joint_Q_evaluable_unique_physical_comparisons':6,'cell_average_F_minus_B_B8L2':avg,
   'selection_rule':'Among four-endpoint B8L2-evaluable unique physical comparisons in this pool/n11/m9, minimize absolute distance to the frozen per-condition mean; tie by physical ID. Prefer TARGET label when the physical comparison is also RAW.',
   'selection_uses_results_for_mechanism_case_only':True,'new_design_or_teams':False,'selected_background_comparison':r.to_dict(),
   'selected_F_B8L2_delta_canonical':float(selected.F_effect),'selected_B_B8L2_delta_canonical':float(selected.B_effect),
   'selected_F_minus_B_B8L2':float(selected.F_minus_B_effect),'distance_to_cell_mean':float(selected.distance_to_condition_mean),
   'maximum_candidate_F_minus_B_not_selected':float(candidates.F_minus_B_effect.max()),
   'duplicate_method_views':all_methods[['method','background_comparison_id','F_event_id','B_event_id']].to_dict('records'),
   'canonical_direction':'C1 -> C2 (historical effective-turn rank 1 -> 2 in these frozen partitions)',
   'historical_strict_source_direction':'C2 -> C1; strict_to_canonical_sign = -1',
   'original_design_links':link.where(pd.notna(link),None).to_dict('records'),
   'both_AC_events_are_new_registered_events_not_prior_strict_endpoints':True,
   'D_changed_people_and_class_composition':True,'F_D_class_counts':json.loads(r.F_D_class_counts),'B_D_class_counts':json.loads(r.B_D_class_counts),
   'minimum_support_for_all_four_teams':6,'replacement_block_size':9,'background_size':2,
   'block_capacity_alone_does_not_prove_node_identity_or_connection':True,
   'source_hashes':[{'path':str(p.relative_to(BASE)),'sha256':sha(p)} for p in [effect_path,index_path,metric_path]]+files}
 (OUT/'BACKGROUND_WC2_53_REPRESENTATIVE_SELECTION.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str))
 print(endpoint[['branch','arm','k','nodes','fusion_turn_n','B8L2','D10','geometry_area_h2','height_mean_h','score_status']].to_string(index=False))
 print(json.dumps({k:result[k] for k in ['selected_F_B8L2_delta_canonical','selected_B_B8L2_delta_canonical','selected_F_minus_B_B8L2','distance_to_cell_mean']},indent=2))
if __name__=='__main__':main()
