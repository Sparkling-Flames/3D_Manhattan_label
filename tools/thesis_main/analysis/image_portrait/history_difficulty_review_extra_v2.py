"""Focused robustness checks using actual distinct people and verified repairs."""
import collections,itertools,json,math
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import OUT,PREV,B,js,csv,sd,cluster,cluster_static,one_replay

def main():
 index=json.loads((OUT/'cache/group_index.json').read_text());arr=np.load(OUT/'cache/pairwise_geometry.npz',allow_pickle=False)
 per=pd.read_csv(OUT/'proposal/per_image_draft_for_user.csv');expert=pd.read_csv(PREV/'expert/independent_tags106.csv');focus=set(per[(per.expert_tag.isin(['中等','困难']))|(per.previous_grade=='difficult_candidate')|per.draft_grade.notna()].image_id)
 # Subset-cluster stability without replacement. If a reference cluster has <2
 # retained people it is unavailable, not a contradictory reclassification.
 rec=[];repairs=[];repair_replays=[]
 repairids=set(pd.read_csv(OUT/'audit/reviewed_repairs.csv').query('imputed_point==True').canonical_annotation_id)
 for r in index:
  key=r['key'];i=r['image_id'];c=r['condition'];dm=arr[key+'_dm'];pcs=arr[key+'_pcs'];cids=arr[key+'_ids'];n=len(pcs)
  if n<4:continue
  if i in focus:
   for cut in[.075,.10,.125,.15]:
    labs=cluster(dm,pcs,cut);co=collections.Counter(labs);sup=[l for l,k in co.items()if k>=2];rng=np.random.default_rng(sd(i,c,cut,'subset80'));m=max(3,int(np.floor(.8*n)));store=collections.defaultdict(list);elig=collections.Counter()
    for rep in range(200):
     ix=np.sort(rng.choice(n,m,replace=False));pred=cluster(dm[np.ix_(ix,ix)],pcs[ix],cut)
     for l in sup:
      target=set(ix[labs[ix]==l])
      if len(target)<2:continue
      elig[l]+=1
      candid=[set(ix[pred==z])for z in np.unique(pred)];j=max(len(target&s)/len(target|s)for s in candid);store[l].append(j)
    for l in sup:
     vals=store[l];prob=elig[l]/200
     rec.append(dict(image_id=i,condition=c,cut=cut,n_full=n,n_subset=m,cluster=int(l),cluster_people=co[l],subsets=200,prob_retains_two_people=prob,mean_jaccard_conditional=float(np.mean(vals))if vals else np.nan,p_jaccard_ge85_conditional=float(np.mean(np.asarray(vals)>=.85))if vals else np.nan,support_and_jaccard_ge85=prob*float(np.mean(np.asarray(vals)>=.85))if vals else 0.,workers=';'.join(arr[key+'_workers'][labs==l]),canonical_ids=';'.join(cids[labs==l])))
  drop=np.isin(cids,list(repairids))
  if drop.any():
   keep=np.flatnonzero(~drop)
   for cut in[.05,.075,.10,.125,.15,.20]:
    for scenario,ix in [('with_user_confirmed_addition',np.arange(n)),('exclude_confirmed_added_only',keep)]:
     st,_,_,_=cluster_static(dm[np.ix_(ix,ix)],pcs[ix],cut)
     repairs.append(dict(image_id=i,condition=c,cut=cut,scenario=scenario,removed_canonical_ids=';'.join(cids[drop])if scenario.startswith('exclude')else '',**st))
     if cut==.1 and scenario.startswith('exclude'):
      ss,_,_=one_replay(dm[np.ix_(ix,ix)],pcs[ix],cut,200,i,c)
      repair_replays+=ss
 csv('extra/clusterwise_80pct_distinct_person_subsets.csv',rec)
 csv('extra/confirmed_addition_sensitivity.csv',repairs)
 csv('extra/excluding_added_points_replay.csv.gz',repair_replays)
 # Reclustered common-n: medians across real images, not across permutations as iid.
 x=pd.read_csv(OUT/'process/reclustered_common_n_focused.csv');hi=per[per.expert_tag.isin(['中等','困难'])&(per.n_valid>=10)]
 a=x.merge(hi[['image_id','condition']],on=['image_id','condition']);cols=['total_clusters_mean','supported_clusters_mean','singletons_mean','p_fixed10pct_accepts','p_count_band_accepts'];summary=a.groupby(['condition','expert_tag','k'])[cols].agg(['median','min','max']).reset_index();summary.columns=['_'.join(c).rstrip('_')if isinstance(c,tuple)else c for c in summary.columns];csv('extra/common_n_expert_anchor_summary.csv',summary)
 # Counts and comments: no adjudication/future tag correction performed.
 rows=[]
 for label,g in per[per.expert_tag.isin(['中等','困难'])].groupby('expert_tag'):
  z=g[(g.condition=='manual')&(g.n_valid>=10)]
  rows.append(dict(expert_tag=label,all_historical_image_conditions=len(g),high_support_manual_images=len(z),median_total_clusters=z.total_clusters.median(),median_supported_clusters=z.supported_clusters.median(),median_singletons=z.singletons.median(),median_conditional_loo_jaccard=z.min_supported_loo_jaccard.median(),median_late_quarter_new=z.late_quarter_new.median(),weak_samepoint_separation_images=int(z.weakly_separated_supported_pair.sum())))
 csv('extra/expert_anchor_empirical_summary.csv',rows)
 # Equal n high support anchors and current conditional estimates are descriptive.
 js('extra/method.json',dict(subsetting='200 x 80% actual distinct people without replacement; conditional on cluster retaining >=2; report retention separately',added_point_sensitivity='exclude only the two explicitly imputed confirmed added records; keep removed-point corrections; never reinterpret them as fabricated',neither_resampling_nor_cuts_are_new_samples=True,model_prediction_not_refit=True))
if __name__=='__main__':main()
