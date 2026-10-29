"""Post-comparison case selection from the complete, immutable AC study.

This changes no teams or outcomes. Every candidate pool and the deterministic
selection rule are retained, including negative and nearly unchanged responses.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage06_cases/representative_selection';OUT.mkdir(exist_ok=True)
assert json.loads((ROOT/'stage05_main/SUMMARY_RECEIPT.json').read_text())['complete']
cols=['analysis_view','scope','condition','method','role_direction','n_condition','m_condition','pool_id','image','building','registered_pairs',
 'B8L2_CA__mean','B8L2_CA__mean_absolute','D10_CA__mean','fusion_turn_n_CA__mean','ref_node_recall_5_CA__mean',
 'ref_edge_recall_5_CA__mean','geometry_bev_distance_AC__mean','A_B8L2__mean','C_B8L2__mean','A_Q_missing__mean','C_Q_missing__mean']
d=pd.read_csv(ROOT/'stage05_main/POOL_CONDITION_EFFECTS.csv.gz',usecols=cols,dtype={'n_condition':str,'m_condition':str})
a=d[(d.analysis_view=='A_fixed_n')&(d.scope=='primary')&(d.condition=='manual')]
t=a[(a.method=='TARGET_DSTRUCT_K3')&(a.n_condition=='20')&(a.m_condition=='7')&(a.role_direction=='2->3')].copy()
links=pd.read_csv(ROOT/'stage01_registered/DESIGN_LINKS.csv.gz',usecols=['event_id','pool_id','method','design_family','background_profile','nested_background_path_id','n','m'],dtype=str)
links=links[(links.design_family=='A_equal_AC')&(links.background_profile=='neutral_members_0')].copy()
mainids=set(links.event_id)
selection=[];candidate_tables=[]

def choose_pool(frame,kind,rule,center,sort_col='B8L2_CA__mean'):
    f=frame.copy();f['distance_to_selection_center']=(f[sort_col]-center).abs();f['case_kind']=kind;f['selection_rule']=rule
    f=f.sort_values(['distance_to_selection_center','pool_id']);candidate_tables.append(f)
    if f.empty:raise ValueError('No supported case for '+kind)
    row=f.iloc[0]
    metric=pd.read_csv(ROOT/'stage04_metrics/metric_shards'/(row.pool_id+'.csv.gz'),low_memory=False)
    role=metric.source_role_rank.astype('Int64').astype(str)+'->'+metric.target_role_rank.astype('Int64').astype(str)
    events=metric[metric.event_id.isin(mainids)&metric.method.eq(row.method)&metric.n.eq(int(row.n_condition))&metric.m.eq(int(row.m_condition))&role.eq(row.role_direction)].copy()
    events=events[events.B8L2_CA.notna()]
    if kind=='target_structure_positive':events=events[(events.fusion_turn_n_CA>0)&(events.ref_node_recall_5_CA>0)]
    if kind=='target_structure_negative':events=events[events.B8L2_CA<0]
    events['distance_to_pool_mean']=(events.B8L2_CA-row.B8L2_CA__mean).abs()
    events=events.sort_values(['distance_to_pool_mean','event_id'])
    if events.empty:raise ValueError('No matching event '+kind)
    e=events.iloc[0]
    selection.append({'case_name':kind,'event_id':e.event_id,'selection_rule':rule+'; within selected pool choose eligible event nearest pool mean, never largest effect',
      'source_full_scope_images':len(frame),'pool_mean_B8L2_delta':row.B8L2_CA__mean,'event_B8L2_delta':e.B8L2_CA,'event_distance_to_pool_mean':e.distance_to_pool_mean,
      'pool_id':row.pool_id,'method':row.method,'n':row.n_condition,'m':row.m_condition,'role_direction':row.role_direction})
    events.to_csv(OUT/(kind+'_ALL_ELIGIBLE_EVENTS.csv'),index=False,encoding='utf-8-sig')

positive=t[(t.B8L2_CA__mean>0)&(t.fusion_turn_n_CA__mean>0)&(t.ref_node_recall_5_CA__mean>0)]
choose_pool(positive,'target_structure_positive','full TARGET n20/m7 role2->3 pools; positive Q plus increased turns and reference retention; pool nearest all-image signed mean',t.B8L2_CA__mean.mean())
negative=t[t.B8L2_CA__mean<0]
choose_pool(negative,'target_structure_negative','all negative TARGET n20/m7 role2->3 pool responses; choose median negative pool response',negative.B8L2_CA__mean.median())
small=t[(t.A_B8L2__mean>=90)&(t.C_B8L2__mean>=90)&(t.B8L2_CA__mean_absolute<1)]
choose_pool(small,'target_high_score_small_response','both mean Q >=90 and mean absolute Q change <1; choose smallest absolute pool signed change',0)
raw=a[(a.method=='V21_DSTRUCT_RAW3_K3')&(a.n_condition=='20')&(a.m_condition=='12')&(a.role_direction=='1->2')]
choose_pool(raw,'raw12_negative','all four supported RAW3 n20/m12 role1->2 pools; choose pool nearest their equal-image mean',raw.B8L2_CA__mean.mean())
joint=a[(a.method=='OPPJOINT_K3')&(a.n_condition=='20')&(a.m_condition=='12')&(a.B8L2_CA__mean>0)]
choose_pool(joint,'joint12_typical_positive','all positive JOINT3 n20/m12 role1->2 pools; choose median positive response',joint.B8L2_CA__mean.median())
pd.concat(candidate_tables,ignore_index=True).to_csv(OUT/'ALL_CANDIDATE_POOLS_AND_SELECTION_RULES.csv',index=False,encoding='utf-8-sig')

# Fixed X/Z at n20 and n22: select a real transition from missing point sequence
# to complete output in one arm, keeping the other arm complete at both sizes.
lg=links[links.m.eq('10')&links.n.isin(['20','22'])&links.method.isin(['OPPJOINT_K3','OPPJOINT_K4'])].copy()
metriccols=['event_id','pool_id','method','n','m','D_workers','X_workers','Z_workers','A_team_key','C_team_key','physical_pair_id',
 'A_score_status','C_score_status','A_nodes','C_nodes','A_B8L2','C_B8L2','B8L2_CA','D10_CA','A_minimum_support','C_minimum_support']
saved=[]
for pool,g in lg.groupby('pool_id',sort=True):
    x=pd.read_csv(ROOT/'stage04_metrics/metric_shards'/(pool+'.csv.gz'),usecols=metriccols,low_memory=False)
    saved.append(g.drop(columns=['n','m']).merge(x.drop(columns=['pool_id','method']),on='event_id',validate='many_to_one'))
z=pd.concat(saved,ignore_index=True)
keys=['pool_id','method','nested_background_path_id']
small=z[z.n.eq(20)].drop_duplicates(keys);large=z[z.n.eq(22)].drop_duplicates(keys)
both=small.merge(large,on=keys,suffixes=('_20','_22'),validate='one_to_one')
assert (both.X_workers_20==both.X_workers_22).all() and (both.Z_workers_20==both.Z_workers_22).all()
both['D20_subset_D22']=[set(str(x).split('|'))<set(str(y).split('|')) for x,y in zip(both.D_workers_20,both.D_workers_22)]
assert both.D20_subset_D22.all()
both['C_point_sequence_recovers']=(both.C_score_status_20=='no_connection')&(both.C_score_status_22=='complete_conditional')&(both.A_score_status_20=='complete_conditional')&(both.A_score_status_22=='complete_conditional')
both['A_point_sequence_recovers']=(both.A_score_status_20=='no_connection')&(both.A_score_status_22=='complete_conditional')&(both.C_score_status_20=='complete_conditional')&(both.C_score_status_22=='complete_conditional')
both.to_csv(OUT/'ALL_FIXED_XZ_20_22_CANDIDATES.csv.gz',index=False,encoding='utf-8-sig',compression='gzip')
eligible=both[both.C_point_sequence_recovers|both.A_point_sequence_recovers].copy()
eligible['recovered_arm_nodes_at_20']=np.where(eligible.C_point_sequence_recovers,eligible.C_nodes_20,eligible.A_nodes_20)
eligible['distance_to_transition_median_nodes']=(eligible.recovered_arm_nodes_at_20-eligible.recovered_arm_nodes_at_20.median()).abs()
eligible=eligible.sort_values(['distance_to_transition_median_nodes','pool_id','method','event_id_20'])
eligible.to_csv(OUT/'ELIGIBLE_POINT_SEQUENCE_RECOVERY_CASES.csv',index=False,encoding='utf-8-sig')
if eligible.empty:raise ValueError('No point-sequence recovery; preserve candidate file and select another justified mechanism separately.')
b=eligible.iloc[0]
for n in [20,22]:
    selection.append({'case_name':'fixed_XZ_m10_n'+str(n),'event_id':b['event_id_'+str(n)],'selection_rule':'complete paired n20/n22 population; one legacy no_connection arm recovers while other remains complete; choose near median selected-node count then deterministic identity, not maximum Q gain','source_full_scope_images':eligible.pool_id.nunique(),'pool_id':b.pool_id,'method':b.method,'n':n,'m':10,'paired_event_id':b['event_id_'+str(42-n)]})
result=pd.DataFrame(selection);assert not result.event_id.duplicated().any()
result.to_csv(OUT/'SELECTED_EVENT_IDS.csv',index=False,encoding='utf-8-sig')
(OUT/'SELECTION_RECEIPT.json').write_text(json.dumps({'complete_comparison_required':True,'new_teams':0,'new_fusions':0,'selection_after_full_results':True,'selected_events':len(result),'fixed_XZ_n20_n22_all_panels':len(both),'eligible_recovery_panels':len(eligible),'paired_recovery_pool':b.pool_id,'selection_does_not_establish_population_representativeness':True},ensure_ascii=False,indent=2)+'\n')
print(result.to_json(orient='records',force_ascii=False,indent=2))
