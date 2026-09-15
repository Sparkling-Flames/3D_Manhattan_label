"""Reanalyse saved real-person replays into SEPARATE exploratory process tiers.

These are outcomes, never new subjective expert difficulty labels. A fragmented
finite sample cannot establish permanent non-convergence. No image/model read.
"""
import itertools,hashlib,shutil
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_prepare import *
OLD=B/'cloud/pro_exploration/v2_convergence_e086b2b9'
RULES=['P_pattern','D10_distribution','D20_distribution','G10_geometry']

def label_profile(n,invalid,modes,singletons,p_early,p_later,p_any,late_new,k,h,x,smax,probability):
 if invalid>0:return 'invalid_records_preclude_process_tier'
 if n<4:return 'insufficient_observed_people'
 if singletons<=smax+1e-9 and modes<=2 and p_early>=probability-1e-9:return 'early_one_or_two_supported_modes'
 if n>=10 and singletons<=smax+1e-9 and modes<=x and p_later>=probability-1e-9:return 'later_few_supported_modes'
 if singletons<=smax+1e-9 and modes>x and p_any>=probability-1e-9:return 'stable_many_supported_modes'
 # This is a descriptive fragmented state, NOT a convergence impossibility judgment.
 if n>=10 and singletons>=.2-1e-9 and modes+round(singletons*n)>=x+2:return 'observed_fragmented_late_changes'if late_new>.05 else 'observed_fragmented_without_late_novelty'
 if n<10:return 'insufficient_horizon_or_other_trajectory'
 if singletons>smax+1e-9:return 'singleton_support_insufficient'
 return 'intermediate_or_order_sensitive'

def main():
 dest=O/'historical_bridge';dest.mkdir(exist_ok=True);(dest/'inputs').mkdir(exist_ok=True)
 source=['process/image_uncertainty_structure.csv','process/replay_states.csv.gz','process/image_growth_curves.csv.gz','process/mode_memberships.csv.gz'];hashes=[]
 for name in source:
  p=OLD/name;shutil.copy2(p,dest/'inputs'/p.name);hashes.append(dict(source=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),use='reanalysis of previous executed per-person-replay outputs; not a newly repeated full geometric replay'))
 savej('historical_bridge/input_hashes.json',hashes)
 s=pd.read_csv(OLD/source[0]);r=pd.read_csv(OLD/source[1]);curve=pd.read_csv(OLD/source[2]);meta=pd.read_csv(O/'images/metadata_all648.csv');keys=['image_id','condition','cut'];structures=s.set_index(keys)
 cf=curve[curve.k>curve.n_valid_full/2].groupby(keys).agg(late_new=('new_incompatible_mode','mean'),late_promotions=('support_promotions','mean'),later_repartition=('repartition_pair_change','mean')).reset_index();s=s.merge(cf,on=keys,how='left')
 groups={k:g for k,g in r.groupby(keys+['rule'])};records=[];probs=[]
 for _,st in s.iterrows():
  i,arm,cut=st.image_id,st.condition,st.cut;n=int(st.n_valid);invalid=int(st.n_invalid);m=float(st.n_supported_modes)if pd.notna(st.n_supported_modes)else 0.;ss=float(st.singleton_mass)if pd.notna(st.singleton_mass)else 1.;late=st.late_new
  for rule in RULES:
   rr=groups.get((i,arm,cut,rule));onsets=rr.onset.to_numpy()if rr is not None else np.array([np.nan]);pany=float(np.mean(np.isfinite(onsets)))
   for k in [2,3,4,5,6,7]:
    pe=float(np.mean(onsets<=k));probrow=dict(image_id=i,condition=arm,cut=cut,rule=rule,early_k=k,n_observed=int(st.n_observed),n_valid=n,n_invalid=invalid,n_supported_modes=m,singleton_mass=ss,p_sustained_onset_by_k=pe,p_any_observed_onset=pany,onset_median_conditional=float(np.nanmedian(onsets))if np.isfinite(onsets).any()else np.nan,late_new_geometry=late)
    probs.append(probrow)
    for h,x,smax,pg in itertools.product([10,12,15,18,19],[2,3,4],[0.,.1],[.8,.9]):
     pl=float(np.mean((onsets>k)&(onsets<=h)));label=label_profile(n,invalid,m,ss,pe,pl,pany,late,k,h,x,smax,pg)
     records.append(dict(probrow,late_h=h,max_few_modes=x,max_singleton_mass=smax,order_fraction_required=pg,p_sustained_onset_between_k_and_h=pl,process_tier=label))
 out=csv('historical_bridge/process_tier_grid.csv.gz',records);csv('historical_bridge/early_onset_probabilities.csv',probs)
 params=['condition','cut','rule','early_k','late_h','max_few_modes','max_singleton_mass','order_fraction_required','process_tier'];csv('historical_bridge/grid_coverage.csv',out.groupby(params).agg(n_images=('image_id','nunique')).reset_index())
 # A declared display slice, not a frozen final criterion or a selected best threshold.
 display=out[(out.early_k==7)&(out.late_h==15)&(out.max_few_modes==3)&(out.max_singleton_mass==.1)&(out.order_fraction_required==.8)].merge(meta[['image_id','difficulty_tag','difficulty_status','scene_category','main_function_primary','room_status']],on='image_id',how='left')
 csv('historical_bridge/display_slice_per_image.csv',display)
 overlap=display[display.difficulty_status=='labelled'];csv('historical_bridge/subjective_overlap.csv',overlap);csv('historical_bridge/subjective_process_cross_tab.csv',overlap.groupby(['condition','cut','rule','difficulty_tag','process_tier']).size().reset_index(name='images'))
 broad=out[(out.late_h==15)&(out.max_few_modes==3)&(out.max_singleton_mass==.1)&(out.order_fraction_required==.8)];csv('historical_bridge/early_k_sensitivity.csv',broad.groupby(['condition','cut','rule','early_k','process_tier']).size().reset_index(name='images'))
 robustness=out.groupby(['image_id','condition']).agg(distinct_tiers=('process_tier','nunique'),n_definitions=('process_tier','size'),early_fraction_of_definitions=('process_tier',lambda a:np.mean(a=='early_one_or_two_supported_modes')),later_fraction_of_definitions=('process_tier',lambda a:np.mean(a=='later_few_supported_modes')),fragmented_fraction_of_definitions=('process_tier',lambda a:np.mean(a.str.startswith('observed_fragmented')))).reset_index();csv('historical_bridge/definition_robustness.csv',robustness)
 median_rows=[]
 for kk,g in r.groupby(keys+['rule']):
  on=g.onset.to_numpy();st=structures.loc[kk[:3]]
  for h in [10,12,15,18,19]:
   median_rows.append(dict(zip(keys+['rule'],kk),late_h=h,n_valid=int(st.n_valid),n_supported_modes=st.n_supported_modes,singleton_mass=st.singleton_mass,p_onset_8_to_h=float(np.mean((on>=8)&(on<=h))),onset_conditional_median=float(np.nanmedian(on))if np.isfinite(on).any()else np.nan))
 csv('historical_bridge/late_onset_window_probabilities.csv',median_rows)
 # Count-only naive classification can call an actually stable multi-mode image hard.
 naive=s.copy();naive['n_singletons']=np.rint(naive.singleton_mass*naive.n_valid);naive['naive_many_modes']=naive.n_modes>=5
 csv('historical_bridge/terminal_structure_with_growth.csv',naive.merge(meta[['image_id','scene_category','main_function_primary']],on='image_id'))
 # Snapshot cluster labels do not claim semantic legitimacy. Modes for audit cases remain real people.
 mm=pd.read_csv(OLD/source[3]);ids=set(display[display.process_tier.isin(['early_one_or_two_supported_modes','stable_many_supported_modes','observed_fragmented_without_late_novelty'])].image_id)
 csv('historical_bridge/review_candidate_modes.csv.gz',mm[mm.image_id.isin(ids)])
 savej('historical_bridge/method.json',dict(target='historical observed convergence trajectory class, not replacement subjective difficulty',early_k=[2,3,4,5,6,7],late_h=[10,12,15,18,19],max_early_supported_modes=2,max_few_supported_modes=[2,3,4],singleton_sensitivity=[0,.1],order_fraction=[.8,.9],distance_cuts=[.05,.1,.2],rules=RULES,actual_n_retained=True,independent_new_participants=0,semantic_legitimacy='requires local image review',chronology='finite-pool random order sensitivity, not arrival-time reconstruction',forbidden_conclusion='fragmented or not stable in observed sample does not imply never converges',two_tags_not_pooled=True,ordinal_interval='process tiers are not exhaustive ordinal labels; insufficient/intermediate/stable-many states retained',singletons='one distinct worker, not a single supported cluster'))
 print('HISTORY',len(out),'grid records',len(overlap),'overlap rows',overlap.image_id.nunique(),'unique images',flush=True)
 print(display[(display.rule=='G10_geometry')&(display.cut==.1)].groupby(['condition','process_tier']).size().to_string(),flush=True)
if __name__=='__main__':main()
