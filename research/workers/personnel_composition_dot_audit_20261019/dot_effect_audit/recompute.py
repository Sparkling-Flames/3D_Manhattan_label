from pathlib import Path
import pandas as pd,numpy as np,json,itertools
P=Path('/workspace/shared/composition_audit_20261019/extracted/personnel_composition_study_20261019/analysis'); O=Path(__file__).parent
F=P/'composition/frozen_grid_results'
main=pd.read_csv(P/'report_tables/main_frozen_effects.csv'); imgs=pd.read_csv(F/'frozen_contrasts_per_image.csv.gz'); ev=pd.read_csv(P/'composition/compact_block_evidence/01_highlight_events.csv.gz')
results={}; out=[]
for r in main.to_dict('records'):
 g=imgs[(imgs.stage==r['stage'])&(imgs.rule_id==r['rule_id'])&(imgs.k==r['k'])&(imgs.comparison_label==r['comparison_label'])]
 if r['reported_difficulty']!='all': g=g[g.difficulty==r['reported_difficulty']]
 q=g.B8L2_mean_b-g.B8L2_mean_a;b=q.groupby(g.building).mean()
 # Exact empirical bootstrap distribution; avoids author's seed and 2000-resample Monte Carlo.
 a=b.dropna().to_numpy(); boots=np.array([a[list(ix)].mean() for ix in itertools.product(range(len(a)),repeat=len(a))])
 complete=g[g.all_team_scores_present]
 # Worst-case bounds for missing scores in [0,100], keeping original image/building weighting.
 bounds={}
 for direction in ('low','high'):
  av=(g.B8L2_mean_a*g.scored_teams_a+(g.unique_teams_a-g.scored_teams_a)*(100 if direction=='low' else 0))/g.unique_teams_a
  bv=(g.B8L2_mean_b*g.scored_teams_b+(g.unique_teams_b-g.scored_teams_b)*(0 if direction=='low' else 100))/g.unique_teams_b
  bounds[direction]=float((bv-av).groupby(g.building).mean().mean())
 out.append(dict(rule=r['rule_id'],k=r['k'],stage=r['stage'],comparison=r['comparison_label'],images=len(g),buildings=len(b),effect=float(b.mean()),reported=r['building_B8L2_change_mean'],error=float(b.mean()-r['building_B8L2_change_mean']),exact_bootstrap_95=np.quantile(boots,[.025,.975]).tolist(),building_effects=b.to_dict(),complete_image_effect=float(complete.groupby('building').B8L2_mean_change.mean().mean()),complete_images=len(complete),missing_score_0_100_bounds=bounds,positive_images=int((q>0).sum()),negative_images=int((q<0).sum())))
results['headlines']=out
# Reconstruct every event's directional scores, equal-m and stable flags from retained values.
checks={}
checks['AB_m_mismatch']=int((ev.within_turnover!=ev.m).sum()); checks['AC_m_mismatch']=int((ev.changed_turnover!=ev.m).sum());checks['BC_less_than_m']=int((ev.net_turnover<ev.m).sum())
for key,expected in [('net_B8L2_change',ev.C_B8L2-ev.B_B8L2),('within_abs_B8L2_change',(ev.B_B8L2-ev.A_B8L2).abs()),('changed_abs_B8L2_change',(ev.C_B8L2-ev.A_B8L2).abs())]: checks[key+'_max_abs_error']=float((ev[key]-expected).abs().max())
for prefix,arm in [('within','B'),('changed','C')]:
 expected=ev.A_complete&ev[arm+'_complete']&ev[prefix+'_abs_B8L2_change'].le(2)&ev[prefix+'_floor_jaccard_difference'].le(.05)&ev[prefix+'_structure_bound_cyclic_deg'].le(3)&ev[prefix+'_node_count_difference'].eq(0)
 checks[prefix+'_stability_mismatches']=int((ev[prefix+'_joint_stable_main']!=expected).sum())
results['event_checks']=checks
# Independent block aggregation across all provided control subsets.
controls=pd.read_csv(P/'composition/block_source_Q_control_comparison.csv'); checks2=[]; errors=[]
for r in controls.to_dict('records'):
 g=ev[(ev.highlight_id==r['highlight_id'])&(ev.phase==r['phase'])]; m=r['m']; k=r['k']
 masks={'all_events':np.ones(len(g),bool),'actual_source_matched':g.actual_source_match,'matched_new_incoming_blocks':g.actual_source_match&g.outgoing_new_n.eq(m),'matched_v1_incoming_blocks':g.actual_source_match&g.outgoing_new_n.eq(0),'all_new_teams':g.A_new_n.eq(k)&g.B_new_n.eq(k)&g.C_new_n.eq(k),'incoming_history_Q_close_3':g.incoming_Q_close_3,'source_and_incoming_Q_close_3':g.actual_source_match&g.incoming_Q_close_3,'matched_new_and_Q_close_3':g.actual_source_match&g.outgoing_new_n.eq(m)&g.incoming_Q_close_3,'matched_v1_and_Q_close_3':g.actual_source_match&g.outgoing_new_n.eq(0)&g.incoming_Q_close_3}
 g=g[masks[r['subset']]]; q=g.C_B8L2-g.B_B8L2; bm=q.groupby([g.building,g.pool_id]).mean().groupby(level=0).mean(); value=bm.mean(); reported=r['net_B8L2_change_equal_building_mean']
 if not np.isclose(value,reported,atol=1e-7,equal_nan=True): errors.append(dict(highlight=r['highlight_id'],subset=r['subset'],phase=r['phase'],value=value,reported=reported))
 checks2.append(dict(highlight=r['highlight_id'],subset=r['subset'],phase=r['phase'],events=len(g),finite=int(q.notna().sum()),images=g.pool_id.nunique(),buildings=g.building.nunique(),effect=value,p10=q.quantile(.1),positive_buildings=int((bm>0).sum()),negative_buildings=int((bm<0).sum()),B_missing=int(g.B_B8L2.isna().sum()),C_missing=int(g.C_B8L2.isna().sum())))
pd.DataFrame(checks2).to_csv(O/'recomputed_block_controls.csv',index=False);results['block_control_errors']=errors
# Mixture requires both original pure baselines, then chooses larger score; independently check.
mix=pd.read_csv(F/'frozen_mixture_best_pure_per_image.csv.gz'); errs=[]
for r in mix.to_dict('records'):
 pure=json.loads(r['pure_composition_B8_json']); vals=list(pure.values()); expected=r['B8L2_mean_mixed']-max(vals) if len(vals)==2 and all(v is not None for v in vals) else np.nan
 if not np.isclose(expected,r['B8L2_mean_change'],atol=1e-7,equal_nan=True):errs.append(r['image'])
results['mixture_arithmetic_errors']=errs
mixrows=[]
for key,g in mix.groupby(['stage','rule_id','k','composition_b']):
 q=g.B8L2_mean_change; b=q.groupby(g.building).mean();mixrows.append(dict(zip(['stage','rule','k','composition'],key))|dict(attempted=len(g),comparable=int(q.notna().sum()),buildings=int(b.notna().sum()),effect=b.mean(),positive=int((q>0).sum()),negative=int((q<0).sum()),all_scores_images=int(g.all_three_cell_team_scores_present.sum())))
pd.DataFrame(mixrows).to_csv(O/'recomputed_mixtures.csv',index=False)
# Within composition building means, support and per-turnover descriptives.
w=pd.read_csv(F/'within_fixed_compositions_per_image.csv.gz');ws=[]
for key,g in w[w.phase.eq('validation')].groupby(['stage','method_id','domain','k','composition','turnover_stratum']):
 d=dict(zip(['stage','method','domain','k','composition','m'],key));d.update(images=len(g),pair_images=int((g.pair_n>0).sum()),teams=int(g.available_unique_teams.sum()),single_team_images=int((g.available_unique_teams==1).sum()))
 for metric in ['abs_B8L2_change_mean','joint_stable_main_mean','turnover_mean']:
  d[metric]=g.groupby('building')[metric].mean().mean()
 ws.append(d)
pd.DataFrame(ws).to_csv(O/'recomputed_within.csv',index=False)
results['single_team_cell_rows']=int(((w.turnover_stratum=='all')&(w.available_unique_teams==1)).sum())
results['single_team_nonmissing_variation']=int(w[(w.turnover_stratum=='all')&(w.available_unique_teams==1)].joint_stable_main_mean.notna().sum())
# LOOW output consistency only; event member IDs are absent in compact evidence.
l=pd.read_csv(P/'composition/compact_block_evidence/04_highlight_loow_person.csv.gz');rev=l[l.supports_three_building_Q_comparison_after_removal&(l.base_net_B8L2_change*l.retained_net_B8L2_change<0)];rev.to_csv(O/'loow_reversals.csv',index=False);results['loow_reversals']=len(rev);results['loow_member_deletion_verification']='Performed separately by recompute_loow.py; see loow_checks.json'
(O/'results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False,allow_nan=True))
print(json.dumps(results,indent=2,ensure_ascii=False,allow_nan=True))
