"""Post-hoc scope/turnover and missing-score sensitivities, independent of author code."""
from pathlib import Path
import pandas as pd,numpy as np,json
R=Path('/workspace/shared/composition_audit_20261019');P=R/'extracted/personnel_composition_study_20261019/analysis/composition';O=Path(__file__).parent
w=pd.read_csv(P/'frozen_grid_results/within_fixed_compositions_per_image.csv.gz');w=w[(w.stage=='confirm_validation')&(w.method_id=='F_rule_Q_quantile_K3')&(w.k==9)];a=w[w.composition=='C01:0|C02:0|C03:9'];rows=[]
for label,comp in [('low','C01:9|C02:0|C03:0'),('mix','C01:3|C02:0|C03:6')]:
 j=a.merge(w[w.composition==comp],on=['pool_id','turnover_stratum'],suffixes=('_hi','_other'))
 for m,g in j.groupby('turnover_stratum'):
  g=g[(g.pair_n_hi>0)&(g.pair_n_other>0)];z={'other':label,'m':m,'images':len(g),'buildings':g.building_hi.nunique()}
  for metric in ['abs_B8L2_change_mean','joint_stable_main_mean']:
   for side in ['hi','other']:z[metric+'_'+side]=g.groupby('building_hi')[metric+'_'+side].mean().mean()
  rows.append(z)
pd.DataFrame(rows).to_csv(O/'same_m_common_image_stability.csv',index=False)
t=pd.read_csv(P/'nested_validation/nested_transitions.csv.gz');p=pd.read_csv(P/'nested_validation/nested_points.csv.gz').set_index(['chain_id','team_key']);t=t[(t.method_id=='R_role_ward_difficulty_K2')&(t.fixed_n==4)&(t.tag=='critical_2m_to_2m1')].copy()
for side in ['before','after']:t[side+'_Q']=[p.loc[(r['chain_id'],r[side+'_team']),'B8L2'] for r in t.to_dict('records')]
bounds={}
for name,dq in [('lower',t.after_Q.fillna(0)-t.before_Q.fillna(100)),('upper',t.after_Q.fillna(100)-t.before_Q.fillna(0))]:bounds[name]=dq.groupby([t.building,t.image]).mean().groupby(level=0).mean().mean()
t.to_csv(O/'nested_fixed4_missing_sensitivity.csv',index=False);(O/'nested_fixed4_bounds.json').write_text(json.dumps(bounds,indent=2))
e=pd.read_csv(P/'compact_block_evidence/01_highlight_events.csv.gz');rows=[]
for key,g in e[e.phase=='validation'].groupby('highlight_id'):
 q=g.C_B8L2-g.B_B8L2;ex=(g.C_B8L2-g.A_B8L2).abs()-(g.B_B8L2-g.A_B8L2).abs();exf=g.changed_floor_jaccard_difference-g.within_floor_jaccard_difference
 def bmean(x):return x.groupby([g.building,g.pool_id]).mean().groupby(level=0).mean().mean()
 rows.append(dict(highlight=key,events=len(g),finite_Q=int(q.notna().sum()),Q_positive=int((q>0).sum()),Q_negative=int((q<0).sum()),finite_excess=int(ex.notna().sum()),cross_absQ_larger=int((ex>0).sum()),cross_absQ_smaller=int((ex<0).sum()),excess_Q_building=bmean(ex),floor_excess_building=bmean(exf),within_stable_building=bmean(g.within_joint_stable_main),cross_stable_building=bmean(g.changed_joint_stable_main)))
pd.DataFrame(rows).to_csv(O/'same_m_comparisons.csv',index=False)
d=pd.read_csv(P/'compact_block_evidence/02_all_exact_strata.csv.xz');d=d[(d.view=='exact_counts_k_m')&(d.phase=='validation')&d.subset.isin(['all_events','actual_source_matched'])]
def cls(s):return {k:int(v) for k,v in (x.split(':') for x in s.split('|')) if int(v)>0}
def pick(r):
 hi={'F_rule_Q_threshold_K3':'C03','F_rule_Q_quantile_K3':'C03','R_role_ward_difficulty_K2':'C02','R_geo9_source_signed_p2_K2':'C02'}.get(r.method_id)
 return hi is not None and set(cls(r.outgoing_counts))=={'C01'} and set(cls(r.incoming_counts))=={hi}
d[[pick(r) for r in d.itertuples()]].to_csv(O/'larger_replacement_strata.csv',index=False)
print('Supplementary artifacts regenerated')
