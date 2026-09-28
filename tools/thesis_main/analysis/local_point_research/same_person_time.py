"""Same-person expenditure across saved same-room view pairs, not time/geometry similarity.
Uses previously source-audited active time. No lead-time, causal speed removal, or online claims.
Leave-one-person-out ratio calibration uses other people's BOTH views. It tests fixed-pair
transfer to another person, not prediction for an unseen view or room. No thresholds selected.
"""
from pathlib import Path
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[4]/'analysis_results/local_point_research_received_20260919'

def run(root=R, output_dir=None):
 R=Path(root)
 output_dir=Path(output_dir) if output_dir is not None else R/'local_recheck'
 output_dir.mkdir(parents=True,exist_ok=True)
 d=pd.read_csv(R/'inputs/time_same_room_person_pairs.csv')
 t=pd.read_csv(R/'inputs/time_rows.csv').set_index('id')
 assert not d.duplicated(['image_a','image_b','context','worker']).any()
 for x in d.itertuples():
  for id_,sec in [(x.id_a,x.seconds_a),(x.id_b,x.seconds_b)]:
   q=t.loc[id_];assert q['worker']==x.worker and q.context==x.context
   assert q.analysis_eligible and q.status=='owner_valid_complete'
   assert q.source_seconds_match and sec>0 and np.isclose(sec,q.seconds)
 d['log_ratio_b_over_a']=np.log(d.seconds_b/d.seconds_a)
 d['larger_over_smaller']=np.exp(d.log_ratio_b_over_a.abs())
 groups=[];pred=[]
 for key,g in d.groupby(['image_a','image_b','context'],sort=True):
  z=g.log_ratio_b_over_a.to_numpy();n=len(g);v=g.iloc[0]
  info={k:v[k] for k in ['image_a','image_b','code_a','code_b','building','group_ids','context']}
  s=dict(**info,N=n,median_ratio_b_over_a=float(np.exp(np.median(z))),median_larger_over_smaller=float(g.larger_over_smaller.median()),ratio_q25=float(g.larger_over_smaller.quantile(.25)),ratio_q75=float(g.larger_over_smaller.quantile(.75)),fraction_within_1_5=float((g.larger_over_smaller<=1.5).mean()),fraction_within_2=float((g.larger_over_smaller<=2.).mean()),fraction_b_longer=float((z>0).mean()),uncalibrated_log_mae=float(np.abs(z).mean()),fixed_pair_transfer_evaluable=n>=5)
  if n>=5:
   ez=[];ebase=[]
   for i,(_,r) in enumerate(g.iterrows()):
    factor=float(np.median(np.delete(z,i)))
    err=abs(z[i]-factor);ez.append(err)
    for direction in ['a_to_b','b_to_a']:
     sign=1 if direction=='a_to_b' else -1
     source=r.id_a if sign==1 else r.id_b;target=r.id_b if sign==1 else r.id_a
     source_log=np.log(t.loc[source,'seconds']);target_log=np.log(t.loc[target,'seconds'])
     base=t.loc[target,'speed_baseline'];be=abs(target_log-base) if np.isfinite(base)else np.nan
     ebase.append(be)
     pred.append(dict(**info,N=n,worker=r.worker,direction=direction,source_id=source,target_id=target,training_pair_workers=n-1,estimated_ratio=float(np.exp(sign*factor)),actual_target_seconds=float(np.exp(target_log)),predicted_target_seconds=float(np.exp(source_log+sign*factor)),copy_source_log_error=abs(target_log-source_log),calibrated_log_error=err,personal_outside_building_baseline_log_error=be,information_condition='other_people_both_views_observed; target_person_source_view_observed'))
   s['calibrated_loo_log_mae']=float(np.mean(ez));s['personal_baseline_bidirectional_log_mae']=float(np.nanmean(ebase))
  groups.append(s)
 d.to_csv(output_dir/'same_person_time_ratios.csv',index=False)
 pd.DataFrame(groups).to_csv(output_dir/'same_person_time_pair_summary.csv',index=False)
 pd.DataFrame(pred).to_csv(output_dir/'same_person_time_loo.csv',index=False)
 z=pd.DataFrame(groups).query('N>=5')
 print(z[['code_a','code_b','context','N','median_ratio_b_over_a','median_larger_over_smaller','fraction_within_1_5','uncalibrated_log_mae','calibrated_loo_log_mae','personal_baseline_bidirectional_log_mae']].to_string(index=False))
 print('pairs',len(z),'unique_people',d.worker.nunique(),'pair_equal_mean_errors',z[['uncalibrated_log_mae','calibrated_loo_log_mae','personal_baseline_bidirectional_log_mae']].mean().to_dict())
