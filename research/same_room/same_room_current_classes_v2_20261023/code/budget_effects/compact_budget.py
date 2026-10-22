"""Compact complete budget outputs; same-support tails and mid+1 parity table.

This consumes already computed scalar results only. Full intermediate addition
matrix is omitted; precise member/team links and requested effect scalars remain.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_study_paths import WORK,CODE_ROOT,NATIVE,TAXONOMY,MECHANISMS,BUDGET,BUDGET_CASES,BUDGET_FINAL,FIGURES,ENGINE,REPO

from pathlib import Path
import json,argparse,shutil
import pandas as pd,numpy as np
from analyze_budget import write_csv,save_hierarchy
P=Path(__file__).parent
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
receipt=json.loads((a.source/'BUDGET_RECEIPT.json').read_text());assert receipt['data_complete']
a.out.mkdir(parents=True,exist_ok=True)
for path in a.source.glob('BUDGET_*.csv'):shutil.copy2(path,a.out/path.name)
shutil.copy2(a.source/'ENDPOINT_AVAILABILITY.csv',a.out/'ENDPOINT_AVAILABILITY.csv')
roles=pd.read_csv(a.source/'BUDGET_PANEL_ROLES.csv')
rolecols=['series_id','panel_id','pair_key','building','groups','image_a','image_b','budget','role_aliases','n','known_common_n',
 'method','selected_family','class_lo','class_hi','k_selected','replicate','core','candidates','n_finite_teams']
write_csv(a.out/'BUDGET_PANEL_ROLES.csv',roles[rolecols])
adds=pd.read_csv(a.source/'ADDITION_LINKS.csv.gz',low_memory=False)
z=[];time_support=[]
for side in 'ab':
 q0=pd.to_numeric(adds['B8L2_before_'+side],errors='coerce');q1=pd.to_numeric(adds['B8L2_after_'+side],errors='coerce')
 joint=q0.notna()&q1.notna();f=adds[['series_id','transition','added_n']].copy()
 for threshold in [70,80]:
  f[f'Q_lt{threshold}_joint_before']=q0.lt(threshold).astype(float).where(joint)
  f[f'Q_lt{threshold}_joint_after']=q1.lt(threshold).astype(float).where(joint)
 timed=pd.to_numeric(adds['labor_ratio_'+side],errors='coerce').notna()
 f['Q_delta_time_matched']=(q1-q0).where(joint&timed)
 f['Q_loss_gt5_time_matched']=(q1-q0).lt(-5).astype(float).where(joint&timed)
 f['Q_gain_gt5_time_matched']=(q1-q0).gt(5).astype(float).where(joint&timed)
 ts=adds[['transition','pair_key','building','groups','added_n']].copy();ts['image']=adds['image_'+side]
 ts['timing_eligible']=timed;ts['timing_and_quality_eligible']=timed&joint;time_support.append(ts)
 z.append(f)
joined=pd.concat(z,ignore_index=True);joined=joined[joined.added_n.gt(0)]
cols=[c for c in joined if c.startswith('Q_lt') or c.endswith('_time_matched')]
extra=joined.groupby(['series_id','transition'])[cols].mean().reset_index()
tp=pd.read_csv(a.source/'ADDITION_PANEL_RESULTS.csv');tp=tp.drop(columns=cols,errors='ignore').merge(extra,on=['series_id','transition'],validate='one_to_one')
write_csv(a.out/'ADDITION_PANEL_RESULTS.csv',tp)
exclude={'series_id','pair_key','building','groups','transition','parity_step','class_lo','class_hi','difficulty_a','difficulty_b'}
tm=[c for c in tp if c not in exclude]
ts=save_hierarchy(a.out,'ADDITION',tp,['transition'],tm)
sp=tp[tp.added_n.eq(1)&tp.transition.eq('mid_half__mid_plus_one')].copy()
ss=save_hierarchy(a.out,'SINGLE_ADDITION_PARITY',sp,['parity_step'],[c for c in tm if c!='n_team_additions'])
linkcols=['series_id','pair_key','building','groups','panel_before','panel_after','transition','selected_mask','selected_members',
 'n_before','n_after','added_n','added_members','core_before','core_after',
 'team_before_a','team_after_a','team_before_b','team_after_b',
 'members_before','members_after','class_vector_before','class_vector_after',
 'image_a','image_b','pool_id_a','pool_id_b','reference_id_a','reference_id_b',
 'difficulty_a','difficulty_b','class_lo','class_hi','known_common_n','parity_step','crossview_Q_state_t1','crossview_turn_state']
for side in 'ab':
 for m in ['B8L2','complete_evaluable','minimum_support']:
  linkcols.extend([f'{m}_before_{side}',f'{m}_after_{side}'])
 for m in ['B8L2','D10','nodes','fusion_turn_n']:
  linkcols.append(f'delta_{m}_{side}')
 linkcols.append('labor_ratio_'+side)
write_csv(a.out/'ADDITION_LINKS.csv.gz',adds[linkcols])
support=[];tt=pd.concat(time_support,ignore_index=True);tt=tt[tt.added_n.gt(0)]
for transition,g in tt.groupby('transition'):
 for field in ['timing_eligible','timing_and_quality_eligible']:
  h=g[g[field]]
  support.append(dict(transition=transition,subset=field,view_addition_records=len(h),
    requested_view_addition_records=len(g),images=h.image.nunique(),direct_pairs=h.pair_key.nunique(),
    buildings=h.building.nunique(),declared_groups=len(set(v for x in h.groups for v in str(x).split('|')))))
write_csv(a.out/'TIMING_SUPPORT.csv',pd.DataFrame(support))
receipt.update(analysis_version='nested_core_budget_v2',parity_comparison='mid_half to mid_plus_one only; one actual added member',
 additional_same_support_tails='finite before and after within view; Q_lt70/80_joint_before/after',
 compact_addition_table_columns=linkcols,full_intermediate_matrix_omitted=True)
(a.out/'BUDGET_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print(ts[['transition','Q_delta_mean','Q_loss_gt5','Q_gain_gt5','Q_lt70_joint_before','Q_lt70_joint_after','Q_lt80_joint_before','Q_lt80_joint_after']].round(5).to_string(index=False))
print(ss[['parity_step','n_before','Q_delta_mean','nodes_increase','nodes_decrease','fusion_turn_n_increase','fusion_turn_n_decrease','Q_loss_gt5','Q_gain_gt5','direct_pairs','buildings']].round(5).to_string(index=False))
print('compact link MiB',(a.out/'ADDITION_LINKS.csv.gz').stat().st_size/2**20)
