"""Post-fit falsification, minority support and case-level evidence.

All full-history modes in this file are used ONLY to stratify scoring after
predictions have been made. They never define training labels or candidates.
"""
from __future__ import annotations
import argparse, collections, itertools, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import softmax
from tools.thesis_main.analysis.image_portrait import person_distribution_hypothesis_v1 as c
from tools.thesis_main.analysis.image_portrait.person_distribution_run_v1 import CachedLearner
from tools.thesis_main.analysis.image_portrait.person_distribution_growth_v1 import matrix,clusters

def paired_fast(df,method,base,metric,keys=('image_id','building')):
 a=df[df.method==method];b=df[df.method==base];z=a.merge(b,on=list(keys),suffixes=('_a','_b'));da=z[metric+'_a']-z[metric+'_b'];ok=np.isfinite(da);z=z[ok];da=da[ok]
 if not len(z):return None
 bs=z.building if 'building'in z else z.building_a;parts=pd.DataFrame({'b':bs.to_numpy(),'d':da.to_numpy()}).groupby('b').d.agg(['sum','count','mean']);r=c.seed('fast_pair',method,base,metric);draw=r.integers(0,len(parts),(2000,len(parts)));v=parts['sum'].to_numpy()[draw].sum(1)/parts['count'].to_numpy()[draw].sum(1)
 return dict(method=method,baseline=base,metric=metric,images=z.image_id.nunique(),buildings=len(parts),delta=float(da.mean()),ci_low=float(np.quantile(v,.025)),ci_high=float(np.quantile(v,.975)),building_macro_delta=float(parts['mean'].mean()))

def run(out):
 dest=out/'diagnostics';dest.mkdir(exist_ok=True);s,pools,bank,raw,meta,workers=c.prepare(out);pool={g['key']:g for g in pools};snaps=json.loads((out/'growth_prediction_snapshots.json').read_text());cache={};learners={};rows=[];placebo=[]
 for sp in snaps:
  g=pool[sp['condition']+'|'+sp['image_id']];key=(g['condition'],g['building'])
  if key not in learners:learners[key]=CachedLearner([h for h in pools if h['condition']==g['condition'] and h['building']!=g['building'] and len(h['ids'])>=2],meta,workers,[g['building']])
  L=learners[key];hi=np.array(sp['future_index']);si=np.array(sp['seed_index']);ai=np.array(sp['indices']);w=np.array(sp['weights'])
  if g['key']not in cache:cache[g['key']]=matrix(g)[:2]
  D,valid=cache[g['key']];lab=clusters(g['dm'],g['count'],.1);cnt=collections.Counter(lab);st=[('singleton'if cnt[lab[j]]==1 else 'supported_minority'if cnt[lab[j]]/len(lab)<=.2 else 'supported_majority')for j in hi]
  sc=c.scores(g,hi,ai,w);compat=(g['all_count'][hi,None]==g['all_count'][ai][None,:])&(D[np.ix_(hi,ai)]<=.1)
  for name in sorted(set(st)):
   m=np.array(st)==name;pw=sc['per_worker_kernel'][m];pb=sc['per_worker_brier'][m]
   rows.append(dict(image_id=g['image_id'],building=g['building'],condition=g['condition'],k=sp['k'],repeat=sp['repeat'],method=sp['method'],stratum=name,heldout_people=int(m.sum()),kernel_score=float(pw.mean()),count_brier=float(pb.mean()),compatible_probability=float(np.sum(w[m]*compat[m],axis=1).mean()),outside_candidates=float(np.mean(~compat[m].any(1))),worker_ids='|'.join(g['workers'][h]for h,use in zip(hi,m)if use),canonical_ids='|'.join(g['ids'][h]for h,use in zip(hi,m)if use)))
  if sp['method']=='seed_person_t025':
   equal=c.scores(g,hi,si,np.full((len(hi),len(si)),1/len(si)))['kernel_score'];actual=sc['kernel_score']
   for permrep in range(20):
    perm=c.seed('identity_alignment_placebo',g['condition'],permrep).permutation(len(workers));d=L.D[np.ix_(perm[g['wi'][hi]],perm[g['wi'][si]])];ww=.1/len(si)+.9*softmax(-d/.25,axis=1);score=c.scores(g,hi,si,ww)['kernel_score']
    placebo.append(dict(image_id=g['image_id'],building=g['building'],condition=g['condition'],k=sp['k'],repeat=sp['repeat'],permutation=permrep,actual_person_loss=actual,shuffled_profile_loss=score,equal_loss=equal,actual_minus_equal=actual-equal,shuffled_minus_equal=score-equal,actual_minus_shuffled=actual-score,meaning='profile identity-alignment placebo; not exact exchangeability test'))
 pd.DataFrame(rows).to_csv(dest/'minority_scoring_only.csv',index=False);minor=pd.DataFrame(rows).groupby(['condition','k','method','stratum','image_id','building'],as_index=False)[['kernel_score','count_brier','compatible_probability','outside_candidates']].mean();minor.groupby(['condition','k','method','stratum']).agg(images=('image_id','nunique'),kernel=('kernel_score','mean'),count_brier=('count_brier','mean'),compatible_probability=('compatible_probability','mean'),outside_candidates=('outside_candidates','mean')).reset_index().to_csv(dest/'minority_summary.csv',index=False)
 mp=[]
 for (arm,k,st),df in minor.groupby(['condition','k','stratum']):
  for name in set(df.method)-{'seed_equal'}:
   for metric in ('kernel_score','count_brier'):
    rr=paired_fast(df,name,'seed_equal',metric)
    if rr:mp.append(dict(condition=arm,k=k,stratum=st,**rr))
 pd.DataFrame(mp).to_csv(dest/'minority_paired.csv',index=False)
 pd.DataFrame(placebo).to_csv(dest/'identity_placebo.csv.gz',index=False)
 if placebo:
  p=pd.DataFrame(placebo);v=p.groupby(['condition','k','permutation','image_id'],as_index=False)[['actual_minus_equal','shuffled_minus_equal','actual_minus_shuffled']].mean();v.groupby(['condition','k','permutation'])[['actual_minus_equal','shuffled_minus_equal','actual_minus_shuffled']].mean().reset_index().to_csv(dest/'identity_placebo_summary.csv',index=False)
 # Image strata on the SAME predicted targets; leave-one-building gain concentration.
 per=pd.read_csv(out/'per_image_scores.csv');md=meta.reset_index();per=per.merge(md[['image_id','scene_category','main_function_primary','floor_boundary','ceiling_boundary']],on='image_id',how='left')
 strata=[]
 for field in ('scene_category','main_function_primary','floor_boundary'):
  z=per.groupby(['condition','k','method',field],dropna=False).agg(images=('image_id','nunique'),buildings=('building','nunique'),kernel=('kernel_score','mean'),count_brier=('count_brier','mean'),uncovered_count=('uncovered_count','mean')).reset_index().rename(columns={field:'stratum'});z['field']=field;strata.append(z)
 pd.concat(strata).to_csv(dest/'image_strata_all_coverage.csv',index=False)
 gains=[]
 for (arm,k),df in per.groupby(['condition','k']):
  if not k:continue
  base=df[df.method=='seed_equal'];names=['seed_person_t025','seed_context_t025','selected_person','selected_context','selected_type','selected_mixture']
  for name in names:
   z=df[df.method==name].merge(base,on=['image_id','building'],suffixes=('_a','_b'));z['d']=z.kernel_score_a-z.kernel_score_b
   for b,g in z.groupby('building'):gains.append(dict(condition=arm,k=k,method=name,building=b,images=len(g),sum_loss_delta=float(g.d.sum()),mean_loss_delta=float(g.d.mean()),without_this_building_delta=float(z[z.building!=b].d.mean())))
 pd.DataFrame(gains).to_csv(dest/'gain_building_concentration.csv',index=False)
 # High observed-n paired coverage, not a replacement of all-available analysis.
 high=per[per.n_valid>=19];high.groupby(['condition','k','method']).agg(images=('image_id','nunique'),kernel=('kernel_score','mean'),count_brier=('count_brier','mean'),uncovered_count=('uncovered_count','mean')).reset_index().to_csv(dest/'common_high_support_scores.csv',index=False)
 # Conditional predictive probability is evaluated against real-world diagnostics.
 gr=pd.read_csv(out/'growth_per_replay.csv.gz');ff=gr[gr.metric.isin(['diagnostic_stable80','diagnostic_stable100','diagnostic_stable_multimode80'])].copy();ff['squared_probability_error']=(ff.prediction-ff.real)**2;ff['declared_stable']=ff.prediction>=.8;ff['false_stable']=ff.declared_stable&(ff.real==0);ff.to_csv(dest/'stability_calibration_per_replay.csv.gz',index=False)
 cal=[]
 for key,g in ff.groupby(['condition','k','cut','method','metric']):
  by=g.groupby('image_id')[['real','prediction','squared_probability_error','declared_stable','false_stable']].mean();cal.append(dict(zip(['condition','k','cut','method','metric'],key),images=len(by),real_stability=float(by.real.mean()),predicted_stability=float(by.prediction.mean()),brier=float(by.squared_probability_error.mean()),declaration_rate=float(by.declared_stable.mean()),false_declaration_rate=float(by.false_stable.mean()),false_fraction_among_declarations=float(g.false_stable.sum()/g.declared_stable.sum())if g.declared_stable.sum()else None))
 pd.DataFrame(cal).to_csv(dest/'stability_calibration_summary.csv',index=False)
 # Genuine physical-room identity validation; uncertain relations excluded.
 rp=out/'sources/evaluation/room_components.jsonl';rel=[]
 if rp.exists():
  for line in rp.read_text().splitlines():
   r=json.loads(line);ids=r.get('image_ids',[]);bs=sorted({i.split('_')[0]for i in ids});rel.append(dict(room_id=r.get('room_id'),status=r.get('status'),images=len(ids),buildings='|'.join(bs),crosses_buildings=len(bs)>1))
 pd.DataFrame(rel).to_csv(dest/'room_building_leakage_audit.csv',index=False)
 assert not any(r['status']=='supported_component'and r['crosses_buildings']for r in rel),'Physical relation crosses outer buildings'
 # Independent expert tags are joined after ALL predictions, not used in fitting.
 try:
  p=c.get(c.B+'metadata/spatial_history.jsonl.gz',c.INPUT_REF,dest/'expert_source_spatial.jsonl.gz');import gzip
  expert=[]
  for line in gzip.open(p,'rt',encoding='utf8'):
   rr=json.loads(line);v=rr.get('latest_selection_record')or{}
   if v.get('difficulty')in ('简单','中等','困难'):expert.append(dict(image_id=rr['image_id'],expert_tag=v['difficulty']))
  ex=pd.DataFrame(expert);assert ex.expert_tag.value_counts().to_dict()=={'简单':49,'中等':41,'困难':16};per.merge(ex,on='image_id',how='inner').to_csv(dest/'expert_tag_posthoc_comparison.csv',index=False)
 except Exception as e:c.js(dest/'expert_comparison_failure.json',dict(error=str(e),effect='No substitution from old experimental difficulty'))
 # Questions only: neither candidates nor decisions are filled for the user.
 review=[];cap=pd.read_csv(out/'candidate_support_ceiling.csv');cs=cap[(cap.cut==.1)&(cap.k==8)].groupby(['image_id','condition','method'],as_index=False).hidden_geometry_outside_candidate_support.mean()
 for _,rr in cs[(cs.method=='selected_mixture')&(cs.hidden_geometry_outside_candidate_support>=.25)].sort_values('hidden_geometry_outside_candidate_support',ascending=False).head(25).iterrows():
  g=pool[rr.condition+'|'+rr.image_id];review.append(dict(image_id=rr.image_id,condition=rr.condition,trigger='hidden geometry outside allowed seed/model candidates',value=rr.hidden_geometry_outside_candidate_support,question='后续真实标法是否对应模型及早期种子遗漏的结构/范围？请区分合理解释、定位变化及无效性；不得仅以多数票裁决。',canonical_ids='|'.join(g['ids']),worker_ids='|'.join(g['workers']),adjudication_status='not_reviewed_by_assistant'))
 pd.DataFrame(review).to_csv(dest/'local_review_questions.csv',index=False)
 c.js(dest/'DIAGNOSTICS_COMPLETE.json',dict(status='complete',minority_usage='post-prediction scoring strata only',profile_placebo='20 fixed identity permutations, no significance claim of exchangeability',expert_tag_used_in_training=False,user_review_39='not filled',new_visual_inference=False))
 print('DIAGNOSTICS_COMPLETE',len(review),'review questions',flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(c.OUT_DEFAULT));args=ap.parse_args();run(args.output)
