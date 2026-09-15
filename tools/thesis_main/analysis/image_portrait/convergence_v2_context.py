"""Window/threshold explanations, provenance sensitivity and room/scene transfer.
All tests are explicitly exploratory follow-ups, not an altered formal protocol.
"""
import collections,itertools,json,time
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *
from tools.thesis_main.analysis.image_portrait.convergence_v2_process import group_replay,partition_stats


def window_sensitivity():
 members=pd.read_csv(OUT/'process/mode_memberships.csv.gz');st=pd.read_csv(OUT/'process/image_uncertainty_structure.csv');rows=[];bounds=[]
 for (image,arm,cut),g in members.groupby(['image_id','condition','cut']):
  g=g.sort_values('worker_id');n=len(g);labels=np.unique(g.cluster,return_inverse=True)[1];sizes=np.bincount(labels);prob=sizes/n
  if n<4:continue
  rng=np.random.default_rng(seed_for(image,arm,cut,'window_audit'))
  for rep in range(100):
   order=rng.permutation(n);counts=np.eye(len(sizes),dtype=int)[labels[order]].cumsum(0);hist=counts/np.arange(1,n+1)[:,None];tv=.5*np.abs(hist-prob).sum(1);h=int(np.ceil(n/2));w=min(3,n-2)
   half_tv=.5*np.abs(counts[h-1]/h-(sizes-counts[h-1])/(n-h)).sum()
   for tol in [.1,.2]:
    rows.append(dict(image_id=image,building=image.split('_')[0],condition=arm,cut=cut,n=n,replay=rep,tolerance=tol,tail3_frequency_pass=bool(max(tv[n-w-1:])<=tol+1e-12),last_half_frequency_pass=bool(max(tv[h-1:])<=tol+1e-12),disjoint_halves_frequency_pass=bool(half_tv<=tol+1e-12),disjoint_half_TV=half_tv,last_half_max_TV=max(tv[h-1:]),descriptive_fixed_full_partition=True))
  bounds.append(dict(image_id=image,condition=arm,cut=cut,n=n,tail_first_k=n-w,maximum_possible_subset_to_full_TV=w/n,TV20_check_mathematically_vacuous=w/n<=.2,TV10_check_mathematically_vacuous=w/n<=.1))
 z=pd.DataFrame(rows);csv('sensitivity/window_frequency_image_results.csv',z.groupby(['image_id','building','condition','cut','n','tolerance'])[['tail3_frequency_pass','last_half_frequency_pass','disjoint_halves_frequency_pass','disjoint_half_TV','last_half_max_TV']].mean().reset_index());csv('sensitivity/window_bound_audit.csv',bounds)
 js('sensitivity/window_method.json',dict(new_after_inspecting_tail_definition=True,reason='For any subset of size k from n with fixed categories, TV(p_k,p_n)<= (n-k)/n. A fixed short tail can mechanically pass a loose tolerance.',mathematical_bound='p_n=(k/n)p_k+((n-k)/n)p_remaining; TV<= (n-k)/n',variants='tail3, entire last half, disjoint half distributions; report all, do not choose by higher convergence rate',limitations='Uses full observed labels only for descriptive frequency sensitivity; not an online partition or physical mode validation. Disjoint halves not new people or independent repeated studies.'))


def structure_and_cases():
 s=pd.read_csv(OUT/'process/image_uncertainty_structure.csv');state=pd.read_csv(OUT/'process/image_state_probabilities.csv');mem=pd.read_csv(OUT/'process/mode_memberships.csv.gz');dense=boundary_map();df=read_responses();rows=[];cases=[]
 for r in s.to_dict('records'):
  m=mem[(mem.image_id==r['image_id'])&(mem.condition==r['condition'])&(mem.cut==r['cut'])];lab=m.cluster.to_numpy();pcs=m.point_count.to_numpy();cids=m.canonical_annotation_id.tolist();within_sum=between_sum=0.;within_n=between_n=0
  for i,j in itertools.combinations(range(len(m)),2):
   if pcs[i]!=pcs[j]:continue
   dist=core._d_mask(dense[cids[i]],dense[cids[j]])
   if lab[i]==lab[j]:within_sum+=dist;within_n+=1
   else:between_sum+=dist;between_n+=1
  r.update(same_point_distance_between_mode_fraction=between_sum/(between_sum+within_sum) if between_sum+within_sum>0 else np.nan,within_pair_n=within_n,between_same_point_pair_n=between_n,
   mode_kind='same_point_only'if r['same_topology_multimodality']and r['supported_topologies']==1 else 'mixed_point_and_geometry'if r['same_topology_multimodality']else'different_point_only'if r['supported_topologies']>=2 else'one_or_no_supported_mode')
  rows.append(r)
  if r['cut']!=.1 or r['n_valid']<4:continue
  trig=[]
  if r['supported_minority_modes'] and r['same_topology_median_d']<=.05:trig.append(('low_median_with_supported_minority','低同点数几何中位数是否遮蔽合理少数模式？'))
  if r['same_topology_multimodality']:trig.append(('same_point_multiple_modes','同点数的不同模式来自范围/边界定位、系统偏差还是标注错误？'))
  if r['n_supported_modes']>=2 and r['supported_topologies']>=2:trig.append(('multiple_supported_structures','不同点数模式是否反映多种可辩护结构解释，还是配对/遗漏问题？'))
  a=state[(state.image_id==r['image_id'])&(state.condition==r['condition'])&(state.cut==.1)&(state.rule=='G10_geometry')]
  if len(a)and float(a[a.state=='stable_multicluster'].fraction.sum())>=.8:trig.append(('stable_multiple_pattern','稳定多簇是否包含合理的不同标法？不能用人数或参考距离自动定对错。'))
  if r['n_invalid']>0:trig.append(('invalid_response_uncertainty','无效提交的具体原因为何？是否妨碍完整分布判断，而不只是几何位置分歧？'))
  modes=[]
  for cl,g in m.groupby('cluster'):
   modes.append(dict(cluster=int(cl),point_count=int(g.point_count.iloc[0]),people=len(g),workers=g.worker_id.tolist(),canonical_ids=g.canonical_annotation_id.tolist(),representative=g.medoid_canonical_annotation_id.iloc[0],representative_worker=g.medoid_worker_id.iloc[0]))
  for trigger,question in trig:cases.append(dict(image_id=r['image_id'],condition=r['condition'],trigger=trigger,question=question,n_people=r['n_valid'],same_point_median=r['same_topology_median_d'],supported_modes=r['n_supported_modes'],singleton_mass=r['singleton_mass'],conclusion_affected='计算多模式能否解释为合理标注不确定性，以及稳定多簇的语义有效性',modes=json.dumps(modes,ensure_ascii=False)))
 a=csv('structure/uncertainty_decomposition.csv',rows)
 # Deterministic case ordering, selected as examples not as prevalence evidence.
 c=pd.DataFrame(cases);c=c.sort_values(['trigger','supported_modes','n_people','image_id'],ascending=[True,False,False,True]).groupby('trigger',group_keys=False).head(12);csv('review/local_mode_review_queue.csv',c)
 cur=pd.read_csv(OUT/'process/image_growth_curves.csv.gz');stats=[]
 for (im,arm),g in cur[cur.cut==.1].groupby(['image_id','condition']):
  n=int(g.k.max());nobs=int(g.n_observed.iloc[0])
  if n<4:continue
  full=g[g.k==n].iloc[0];h=max(2,int(np.ceil(n/2)));mid=g[g.k==h].iloc[0]
  stats.append(dict(image_id=im,building=im.split('_')[0],condition=arm,n=n,n_observed=nobs,half_k=h,mean_medoid_reference_error_half=mid.largest_mode_medoid_reference_error,mean_medoid_reference_error_full=full.largest_mode_medoid_reference_error,reference_delta=full.largest_mode_medoid_reference_error-mid.largest_mode_medoid_reference_error,new_modes_late=g[g.k>h].new_incompatible_mode.mean(),late_support_promotions=g[g.k>h].support_promotions.mean(),half_TV=mid.TV_full_observed,within_geometry_half=mid.within_mode_max_median_d,within_geometry_full=full.within_mode_max_median_d))
 q=csv('process/quality_and_marginal_change.csv',stats);csv('process/quality_change_summary.csv',[dict(condition=arm,mean_half=g.mean_medoid_reference_error_half.mean(),mean_full=g.mean_medoid_reference_error_full.mean(),images_improved=int((g.reference_delta< -1e-9).sum()),images_worsened=int((g.reference_delta>1e-9).sum()),**paired_interval(g,'reference_delta')) for arm,g in q.groupby('condition')])
 # Same final point disagreement can hide different geometry/discovery processes.
 x=a[a.cut==.1].merge(q[['image_id','condition','new_modes_late','half_TV']],on=['image_id','condition']);pairs=[]
 for arm,g in x.groupby('condition'):
  for (_,u),(_,v) in itertools.combinations(g.iterrows(),2):
   if abs(u.n_valid-v.n_valid)>1 or u.n_valid<4:continue
   if not np.isfinite(u.topology_disagreement)or not np.isfinite(v.topology_disagreement):continue
   if abs(u.topology_disagreement-v.topology_disagreement)>.02:continue
   delta=abs(u.new_modes_late-v.new_modes_late)
   if delta<.15:continue
   pairs.append(dict(condition=arm,image_a=u.image_id,image_b=v.image_id,n_a=u.n_valid,n_b=v.n_valid,point_disagreement_a=u.topology_disagreement,point_disagreement_b=v.topology_disagreement,modes_a=u.n_supported_modes,modes_b=v.n_supported_modes,geometry_a=u.same_topology_median_d,geometry_b=v.same_topology_median_d,late_novelty_a=u.new_modes_late,late_novelty_b=v.new_modes_late,late_novelty_gap=delta))
 csv('structure/same_final_structure_different_growth.csv',pd.DataFrame(pairs).sort_values('late_novelty_gap',ascending=False)if pairs else [])


def transfer():
 t=pd.read_csv(OUT/'prediction/process_targets.csv');t=t[t.cut==.1];meta=pd.read_csv(OUT/'images/evidence_layers.csv').set_index('image_id');rm=room_map();results=[];fails=[]
 targets=['stable_G10','late_novel_geometry_rate','half_TV','half_future_uncovered','supported_multimodal']
 for arm,g in t.groupby('condition'):
  g=g.set_index('image_id');eligible=[i for i in g.index if rm.get(i,('',''))[1]=='supported_component']
  for image in eligible:
   r=g.loc[image];room=rm[image][0];b=r.building;sc=meta.loc[image,'scene_human_adopted']
   donors={'same_physical_room':[i for i in eligible if i!=image and rm[i][0]==room],
           'same_building_other_supported_component':[i for i in eligible if g.loc[i,'building']==b and rm[i][0]!=room],
           'same_human_scene_other_building_room':[i for i in eligible if g.loc[i,'building']!=b and meta.loc[i,'scene_human_adopted']==sc],
           'all_other_buildings':[i for i in g.index if g.loc[i,'building']!=b]}
   for target in targets:
    if not np.isfinite(r[target]):continue
    for matched in [False,True]:
     for kind,ids in donors.items():
      ds=g.loc[ids].dropna(subset=[target])
      if matched:ds=ds[(ds.n_valid-r.n_valid).abs()<=2]
      if not len(ds):fails.append(dict(image_id=image,condition=arm,target=target,donor=kind,horizon_matched=matched,reason='no_eligible_historical_donor'));continue
      if kind=='all_other_buildings':pred=ds[target].median()
      else:
       rr=ds[target].groupby([rm[i][0] for i in ds.index]).median();pred=rr.median()
      results.append(dict(image_id=image,building=b,room_id=room,condition=arm,scene=sc,target=target,donor=kind,horizon_matched=matched,n_donor_images=len(ds),n_donor_rooms=len({rm.get(i,('unknown',))[0]for i in ds.index}),donor_ids=';'.join(ds.index),target_n=r.n_valid,truth=r[target],prediction=pred,absolute_error=abs(pred-r[target])))
 a=csv('transfer/room_scene_process_predictions.csv',results);csv('transfer/coverage_failures.csv',fails);out=[]
 for keys,g in a.groupby(['condition','target','horizon_matched']):
  base=g[g.donor=='all_other_buildings']
  for name,z in g.groupby('donor'):
   if name=='all_other_buildings':continue
   m=z[['image_id','building','absolute_error']].merge(base[['image_id','absolute_error']],on='image_id',suffixes=('','_base'));m['delta']=m.absolute_error-m.absolute_error_base
   out.append(dict(condition=keys[0],target=keys[1],horizon_matched=keys[2],donor=name,method_MAE=m.absolute_error.mean(),base_MAE=m.absolute_error_base.mean(),all_available_images=len(z),**paired_interval(m,'delta')))
 csv('transfer/paired_process_transfer.csv',out)
 # Shared-worker contrast keeps the identical people in both genuine views.
 d=read_responses();d=d[d.main_worker_included&d.raw_condition.isin(['manual','semi'])];dense=boundary_map();pr=[]
 for room in core.load(BUNDLE/'evaluation/room_components.jsonl'):
  if room['status']!='supported_component':continue
  for ia,ib in itertools.combinations(room['image_ids'],2):
   for arm in ['manual','semi']:
    ga=d[(d.image_id==ia)&(d.raw_condition==arm)];gb=d[(d.image_id==ib)&(d.raw_condition==arm)];common=set(ga.worker_id)&set(gb.worker_id)
    if len(common)<2:continue
    vals=[]
    for g in [ga,gb]:
     sub=g[g.worker_id.isin(common)];_,s,_,st=group_replay(sub,dense,.1,orders=30,record_steps=False);p=pd.DataFrame(s);p=p[p.rule=='G10_geometry']if len(p)else p
     vals.append(dict(point_disagreement=st.get('topology_disagreement'),same_point_dispersion=st.get('same_topology_median_d'),supported_modes=st.get('n_supported_modes'),stable_fraction=float(p.state.isin(['observed_unified','stable_multicluster']).mean())if len(p)and len(common)>=4 else np.nan))
    pr.append(dict(room_id=room['room_id'],building=ia.split('_')[0],condition=arm,image_a=ia,image_b=ib,n_common=len(common),common_workers=';'.join(sorted(common)),**{k+'_a':v for k,v in vals[0].items()},**{k+'_b':v for k,v in vals[1].items()}))
 csv('transfer/common_worker_view_processes.csv',pr)
 js('transfer/method.json',dict(primary_relations='Only supported components with no pending/unsupported overlap',scene='Human-reviewed adopted scene label, NOT an AI visible trait',different_room='Different buildings establish different physical rooms; different components in one building are NOT automatically distinct rooms',same_building='Explicit baseline only, not declared scene similarity',matching='Report native AND donor horizon difference<=2',same_room_prediction='Uses only other views in target supported component',shared_worker='Same actual IDs in both views, no geometric coordinate registration claimed',comparison_unit='Images then building, not donor pairs as independent physical rooms'))


def context_sensitivity():
 d=read_responses();d=d[d.main_worker_included&d.raw_condition.isin(['manual','semi'])];dense=boundary_map();rows=[]
 for (im,arm),g in d.groupby(['image_id','raw_condition']):
  variants=[]
  if g.imputed_point.any():variants.append(('no_imputed',g[~g.imputed_point]))
  if g.context_key.nunique()>1:
   variants += [('context:'+c,x)for c,x in g.groupby('context_key')]
  for name,x in variants:
   for cut in [.05,.1,.2]:
    _,ss,_,st=group_replay(x,dense,cut,orders=30,record_steps=False);q=pd.DataFrame(ss)
    for rule in ['P_pattern','D10_distribution','G10_geometry']:
     u=q[q.rule==rule]if len(q)else q
     rows.append(dict(image_id=im,condition=arm,variant=name,cut=cut,rule=rule,n_original=len(g),n_variant=len(x),n_valid=st.get('n_valid',0),stable_fraction=float(u.state.isin(['observed_unified','stable_multicluster']).mean())if len(u)else np.nan,unified_fraction=float((u.state=='observed_unified').mean())if len(u)else np.nan,multicluster_fraction=float((u.state=='stable_multicluster').mean())if len(u)else np.nan,undetermined_fraction=float(u.state.str.startswith('cannot').mean())if len(u)else 1.))
 csv('sensitivity/context_and_imputed_processes.csv',rows)
 # OOS is categorical protocol execution, not ordinary geometry convergence.
 o=read_responses();o=o[o.main_worker_included&(o.raw_condition=='oos')];ors=[]
 for image,g in o.groupby('image_id'):
  cnt=g.scope.value_counts(dropna=False);known=g[g.scope!='unknown'];ors.append(dict(image_id=image,building=image.split('_')[0],n_workers=g.worker_id.nunique(),scope_distribution=json.dumps(cnt.to_dict()),n_known=len(known),normal_fraction=float((known.scope=='normal').mean())if len(known)else np.nan,scope_entropy=entropy(known.scope),reference_scope=';'.join(sorted(g.historical_reference_scope.fillna('unknown').unique()))))
 csv('sensitivity/oos_rule_task_distribution.csv',ors)
 js('sensitivity/context_and_invalid_notes.json',dict(raw_arrival_order_absent=True,geometry_curves_axis='k valid distinct people; actual observedn and invalid count retained; invalid cases cannot certify the full response distribution',pooled_context_limit='Same condition can span historical contexts, hence context-specific tables and no new-protocol generalization.',quality_mean_limit='Reference quality curve is expected reference deviation of an actual dominant-mode medoid, not a quality upper bound or automatically fused output.'))

if __name__=='__main__':
 window_sensitivity();structure_and_cases();transfer();context_sensitivity();print('CONTEXT DONE',flush=True)
