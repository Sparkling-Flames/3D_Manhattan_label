"""Distinguish a short stable suffix from the previous tail-window confirmation.
No extra participant requirement is imposed, and neither version is final.
"""
from tools.thesis_main.analysis.image_portrait.difficulty_history_bridge import *
def main():
 s=pd.read_csv(O/'historical_bridge/inputs/image_uncertainty_structure.csv');r=pd.read_csv(O/'historical_bridge/inputs/replay_states.csv.gz');keys=['image_id','condition','cut'];groups={k:g for k,g in r.groupby(keys+['rule'])};rows=[];dif=[]
 for _,st in s.iterrows():
  for rule in RULES:
   g=groups.get((st.image_id,st.condition,st.cut,rule));raw=g.onset.to_numpy()if g is not None else np.array([np.nan]);tail=g.state.isin(['observed_unified','stable_multicluster']).to_numpy()if g is not None else np.array([False]);ons=raw.copy();ons[~tail]=np.nan
   m=st.n_supported_modes if pd.notna(st.n_supported_modes)else 0;ss=st.singleton_mass if pd.notna(st.singleton_mass)else 1
   for confirm,xx in [('suffix_only',raw),('suffix_and_tail',ons)]:
    for k in [2,3,4,5,6,7]:
     for h in [10,12,15,18,19]:
      pe=np.mean(xx<=k);pl=np.mean((xx>k)&(xx<=h));pa=np.mean(np.isfinite(xx));label=label_profile(int(st.n_valid),int(st.n_invalid),m,ss,pe,pl,pa,0.,k,h,3,.1,.8)
      # Fragmentation does not change under the confirmation sensitivity; preserve it explicitly.
      if label.startswith('observed_fragmented'):label='observed_fragmented_confirmation_not_a_convergence_test'
      rows.append(dict(image_id=st.image_id,condition=st.condition,cut=st.cut,rule=rule,confirmation=confirm,early_k=k,late_h=h,n_valid=st.n_valid,n_supported_modes=m,singleton_mass=ss,p_early=pe,p_later=pl,p_any_suffix=pa,p_tail_stable=float(tail.mean()),process_tier=label))
   dif.append(dict(image_id=st.image_id,condition=st.condition,cut=st.cut,rule=rule,n_valid=st.n_valid,n_supported_modes=m,p_any_suffix=float(np.mean(np.isfinite(raw))),p_tail_stable=float(tail.mean()),p_short_suffix_without_tail=float(np.mean(np.isfinite(raw)&~tail))))
 q=csv('historical_bridge/confirmation_sensitivity_per_image.csv.gz',rows);csv('historical_bridge/confirmation_disagreement.csv',dif);csv('historical_bridge/confirmation_sensitivity_counts.csv',q.groupby(['condition','cut','rule','confirmation','early_k','late_h','process_tier']).size().reset_index(name='images'))
 savej('historical_bridge/confirmation_method.json',dict(status='additional explicitly reported sensitivity after identifying onset-vs-tail mismatch',suffix='existing earliest k sustaining checks through actual n; k<n, may have only one subsequent observation',tail='existing last min(3,n-2) transitions must also satisfy rule',not_equivalent=True,not_new_collection_requirement=True,old_results_preserved=True))
 print(q[(q.cut==.1)&(q.rule=='G10_geometry')&(q.early_k==7)&(q.late_h==19)].groupby(['condition','confirmation','process_tier']).size().to_string(),flush=True)
if __name__=='__main__':main()
