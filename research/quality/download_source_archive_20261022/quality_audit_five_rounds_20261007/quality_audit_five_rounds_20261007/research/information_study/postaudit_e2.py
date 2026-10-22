"""Post-audit extension; NOT part of the originally frozen four-component E experiment.
Use the SAME angular (0.1 deg) and spatial (0.01 h) tolerance on lower boundary.
No tuning or rewriting of original E outputs.
"""
from round_d import *
import pandas as pd
MET={'L0':'iou','C':'centroid_distance_normalized','U':'top_mae_deg','D3':'top3d_symmetric_mean_h','B':'bottom_mae_deg','F3':'floor3d_symmetric_mean_h'}
TOL={'L0':.0001,'C':.0001,'U':.1,'D3':.01,'B':.1,'F3':.01}
POL={'original_four':['L0','C','U','D3'],'both_angles':['L0','C','U','B'],'both_angles_and_floor3d':['L0','C','U','B','F3'],'six_components':['L0','C','U','B','D3','F3']}

def main():
 c=pd.read_csv(DENSITY/'round_c_reference_comparisons.csv');c=c[c.method=='continuous_boundary'];rows=[]
 for _,r in c.iterrows():
  before={k:1-r['before_'+v] if k=='L0' else r['before_'+v] for k,v in MET.items()};after={k:1-r['after_'+v] if k=='L0' else r['after_'+v] for k,v in MET.items()};delta={k:after[k]-before[k] for k in MET}
  for policy,req in POL.items():
   ready=all(np.isfinite(before[k]) for k in req);candidate_ready=all(np.isfinite(after[k]) for k in req)
   propose=ready and candidate_ready and after['L0']+.5*after['C']<before['L0']+.5*before['C']-1e-12 and all(delta[k]<=TOL[k]+1e-12 for k in req)
   status='abstain_metric_NA' if not ready else 'propose_change' if propose else 'retain_anchor'
   row={'image':r.image,'building':r.building,'source_id':r.expression_id,'reference_version':r.reference_version,'source_panel':r.source_panel,'policy':policy,'status':status,'proposed':propose,'candidate_metric_ready':candidate_ready}
   for k in MET:row['before_'+k]=before[k];row['candidate_'+k]=after[k];row['candidate_delta_'+k]=delta[k];row['chosen_delta_'+k]=delta[k] if propose else 0. if ready else np.nan
   rows.append(row)
 d=pd.DataFrame(rows);d.to_csv(OUT/'E2_lower_boundary_policy_decisions.csv',index=False,encoding='utf-8-sig')
 old=pd.read_csv(OUT/'E_policy_decisions.csv');old=old[(old.experiment=='new_continuous_projection')&(old.policy=='guard_full_strict')]
 check=old.merge(d[d.policy=='original_four'],on=['image','source_id','reference_version']);assert all((check.status_x=='propose_change')==check.proposed)
 summaries=[]
 for (version,policy),g in d.groupby(['reference_version','policy']):
  changed=g[g.proposed];s={'reference_version':version,'policy':policy,'successful_fit_pools':len(g),'decided':int((g.status!='abstain_metric_NA').sum()),'NA':int((g.status=='abstain_metric_NA').sum()),'propose_change':len(changed),'retain_anchor':int((g.status=='retain_anchor').sum())}
  for k in MET:s['selected_regression_'+k]=int((changed['candidate_delta_'+k]>TOL[k]+1e-12).sum())
  summaries.append(s)
 csvout('E2_lower_boundary_summary.csv',summaries)
 four=d[d.policy=='original_four'];six=d[d.policy=='six_components'];both=d[d.policy=='both_angles'];key=['image','source_id','reference_version']
 delta=four.merge(six,on=key,suffixes=('_four','_six'));dropped=delta[delta.proposed_four&~delta.proposed_six];dropped.to_csv(OUT/'E2_lower_boundary_removed_cases.csv',index=False,encoding='utf-8-sig')
 increment=both.merge(six,on=key,suffixes=('_angles','_six'));increment=increment[increment.proposed_angles&~increment.proposed_six];increment.to_csv(OUT/'E2_threeD_incremental_cases.csv',index=False,encoding='utf-8-sig')
 orig=six[six.reference_version=='original'];rev=six[six.reference_version=='manual_revision'];paired=orig.merge(rev,on=['image','source_id'],suffixes=('_original','_revision'));paired['both_decided']=(paired.status_original!='abstain_metric_NA')&(paired.status_revision!='abstain_metric_NA');paired['changed']=paired.both_decided&(paired.proposed_original!=paired.proposed_revision);paired.to_csv(OUT/'E2_reference_reversals.csv',index=False,encoding='utf-8-sig')
 definition={'status':'post-audit extension, not preregistered nor part of frozen four-component experiment','reason':'Four-component rule did not inspect bottom angular/floor3D; five originally proposed C changes worsened bottom MAE beyond 0.1 degree.','tolerances':TOL,'input':'same saved C continuous fits, same references; no refitting or retuning','stopping_condition':'Apply both-angle and six-component versions once, verify original-four reproduction, list changed membership and NA, retain all initial results.'}
 dump('E2_postaudit_definition.json',definition);print(pd.DataFrame(summaries).to_string(index=False));print('removed',dropped[key+['candidate_delta_B_four','candidate_delta_F3_four']].to_string(index=False));print('increment',increment[key+['candidate_delta_D3_angles','candidate_delta_F3_angles','candidate_delta_B_angles']].to_string(index=False));print('reference:',int(paired.both_decided.sum()),int(paired.changed.sum()))
if __name__=='__main__':main()
