"""Translate computational findings without promoting tolerance to ground truth."""
import collections,json
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *
from tools.thesis_main.analysis.image_portrait.convergence_v2_process import group_replay


def run():
 s=pd.read_csv(OUT/'process/image_uncertainty_structure.csv');st=pd.read_csv(OUT/'process/image_state_probabilities.csv');m=pd.read_csv(OUT/'process/mode_memberships.csv.gz');d=read_responses();d=d[d.main_worker_included];dense=boundary_map();layers=pd.read_csv(OUT/'images/evidence_layers.csv').set_index('image_id')
 # Expose that "unified" only refers to supported core under the90% version.
 a=st.merge(s[['image_id','condition','cut','singleton_mass']],on=['image_id','condition','cut']);a['semantic_state']=a.state
 mask=a.state.eq('observed_unified') & (a.singleton_mass>0)
 a.loc[mask,'semantic_state']='supported_core_unified_with_unconfirmed_singletons'
 csv('process/states_with_explicit_singleton_semantics.csv',a)
 strict=a.copy();gate=(strict.singleton_mass>0)&(~strict.state.isin(['cannot_judge_low_n','cannot_judge_invalid']))
 strict.loc[gate,'state']='cannot_judge_any_singleton';strict['singleton_policy']='zero_singleton_sensitivity_not_primary'
 strict=strict.groupby(['image_id','building','condition','cut','rule','state','n_observed','n_valid','singleton_policy'],dropna=False).fraction.sum().reset_index()
 csv('sensitivity/zero_singleton_state_sensitivity.csv',strict)
 csv('sensitivity/zero_singleton_state_summary.csv',strict.groupby(['condition','cut','rule','state']).fraction.sum().reset_index(name='expected_images'))
 # Finite supported subclasses can be internally stable even when the full
 # population is not certifiable. Individual-level relevance still needs review.
 group=pd.read_csv(OUT/'subgroups/selected_and_continuous_target_states.csv');g=group[(group.rule=='G10_geometry')&group.candidate.str.startswith('local_')]
 full=st[(st.cut==.1)&(st.rule=='G10_geometry')].pivot_table(index=['image_id','condition'],columns='state',values='fraction',aggfunc='sum',fill_value=0).reset_index()
 for c in ['observed_unified','stable_multicluster','current_changes','cannot_judge_low_n','cannot_judge_singletons','cannot_judge_invalid']:
  if c not in full:full[c]=0.
 full['full_stable_fraction']=full.observed_unified+full.stable_multicluster;full['full_undetermined_fraction']=full.filter(like='cannot_judge').sum(axis=1)
 z=g.merge(full[['image_id','condition','full_stable_fraction','full_undetermined_fraction','current_changes']],on=['image_id','condition']);csv('subgroups/local_vs_full_process.csv',z)
 # All class-pair transitions, not only illustrative successes.
 pools=pd.read_csv(OUT/'combinations/actual_class_pool_growth_states.csv');index=pools.set_index(['image_id','condition','information','k_classes','pool']);rows=[]
 for r in pools[pools.pool.str.contains('+',regex=False)].to_dict('records'):
  a,b=r['pool'].split('+');u=index.loc[(r['image_id'],r['condition'],r['information'],r['k_classes'],a)];v=index.loc[(r['image_id'],r['condition'],r['information'],r['k_classes'],b)];r.update(class_a_stable=u.stable_fraction,class_b_stable=v.stable_fraction,class_a_undetermined=u.undetermined_fraction,class_b_undetermined=v.undetermined_fraction,both_stable80=u.stable_fraction>=.8 and v.stable_fraction>=.8)
  r['process_transition']=('both_unified_to_multi' if r['both_classes_unified80'] and r['multiple_fraction']>=.8 else 'both_unified_to_unified'if r['both_classes_unified80'] and r['unified_fraction']>=.8 else 'both_stable_to_multi'if r['both_stable80'] and r['multiple_fraction']>=.8 else 'one_unified_to_multi'if max(u.unified_fraction,v.unified_fraction)>=.8 and r['multiple_fraction']>=.8 else 'union_undetermined'if r['undetermined_fraction']==1 else 'other_observed_transition')
  rows.append(r)
 x=csv('combinations/class_pool_process_transitions.csv',rows);csv('combinations/class_pool_transition_summary.csv',x.groupby(['condition','information','process_transition']).agg(comparisons=('image_id','size'),images=('image_id','nunique'),buildings=('building','nunique')).reset_index())
 # Add exact minority contributors, without deciding their validity.
 memberships=pd.read_csv(OLD/'E/worker_memberships_oof.csv.gz');memberships=memberships[memberships.panel=='native'];lookup={key:dict(zip(u.worker_id,u.label))for key,u in memberships.groupby(['heldout_building','information','k'])}
 r=[]
 for (im,arm,cut),u in m.groupby(['image_id','condition','cut']):
  if cut!=.1:continue
  for info,k in [('Q',2),('T',2),('B',2),('QTSB',4),('quality_time_edit',3)]:
   mp=lookup.get((im.split('_')[0],info,k),{})
   for cid,mode in u.groupby('cluster'):
    if not 2<=len(mode)<=len(u)*.2:continue
    labels=collections.Counter(mp.get(w,'unknown_not_a_type')for w in mode.worker_id)
    r.append(dict(image_id=im,condition=arm,information=info,k_classes=k,cluster=int(cid),point_count=int(mode.point_count.iloc[0]),people=len(mode),total_people=len(u),workers=';'.join(mode.worker_id),canonical_ids=';'.join(mode.canonical_annotation_id),class_membership=json.dumps(labels),all_from_one_known_class=len(labels)==1 and 'unknown_not_a_type'not in labels,semantic_legitimacy='requires_local_image_review'))
 csv('combinations/minority_mode_class_contributors.csv',r)
 # Expand local review queue with both positive subclasses and their counterexamples.
 queue=pd.read_csv(OUT/'review/local_mode_review_queue.csv').to_dict('records');qkeys={(r['image_id'],r['condition'],r['trigger'])for r in queue}
 special=z[(z.p_unified>=.8)&(z.full_stable_fraction<.2)].sort_values(['n_subgroup'],ascending=False).head(12)
 fixed=pd.read_csv(OUT/'subgroups/fixed_disjoint_split_target_processes.csv');selected=pd.read_csv(OUT/'subgroups/fixed_disjoint_split_selected.csv')
 extra=[]
 for r in special.to_dict('records'):extra.append((r['image_id'],r['condition'],'stable_local_subgroup_in_noncertifiable_full_population',r['actual_workers'],'这些组内标注是否遵循同一可辩护几何解释？其他模式是空间范围差别、定位差别还是协议/参考冲突？','局部稳定子类是否具有语义解释，而非事后多数投票'))
 # The same exactly eight people recur in two heldout buildings; preserve them.
 candidate='W001;W002;W006;W010;W012;W013;W017;W030'
 for r in fixed[fixed.actual_workers==candidate].to_dict('records'):extra.append((r['image_id'],r['condition'],'fixed_training_roster_eight_people_cross_building',r['actual_workers'],'八人作答是否对应同一合法范围？与其他人的差别落在哪些具体边界？','同一名单在不同物理地点的观察内统一'))
 for r in x[x.process_transition.isin(['both_stable_to_multi','one_unified_to_multi'])].head(8).to_dict('records'):extra.append((r['image_id'],r['condition'],'class_pool_merge_changes_supported_modes',r['pool_workers'],'合并后模式由哪些真实人员贡献？多模式是否反映不同范围、隐藏结构解释或系统性位移？','组合如何改变模式构成，不是组合优劣排名'))
 # Fixed roster fails are deliberately reviewed too (not selected on success alone).
 for r in fixed[(fixed.n>=8)&(fixed.undetermined_fraction==1)].head(6).to_dict('records'):extra.append((r['image_id'],r['condition'],'fixed_roster_nonconvergence_counterexample',r['actual_workers'],'同一跨房训练名单在这里为什么产生单人模式或波动？是否存在目标范围、遮挡或局部定位的变化？','否定该子类普遍收敛，并界定其适用图片条件'))
 for im,arm,trig,workers,question,affected in extra:
  if (im,arm,trig)in qkeys:continue
  mode_rows=[];u=m[(m.image_id==im)&(m.condition==arm)&(m.cut==.1)]
  for lab,v in u.groupby('cluster'):mode_rows.append(dict(cluster=int(lab),point_count=int(v.point_count.iloc[0]),people=len(v),workers=v.worker_id.tolist(),canonical_ids=v.canonical_annotation_id.tolist(),representative=v.medoid_canonical_annotation_id.iloc[0],representative_worker=v.medoid_worker_id.iloc[0]))
  queue.append(dict(image_id=im,condition=arm,trigger=trig,question=question,n_people=len(u),modes=json.dumps(mode_rows,ensure_ascii=False),conclusion_affected=affected,selected_worker_roster=workers));qkeys.add((im,arm,trig))
 q=csv('review/local_mode_review_queue_enriched.csv',queue)
 # Numerical annotation payload for an optional local offline overlay; no image bytes.
 cids={cid for row in queue for mode in json.loads(row['modes'])for cid in mode['canonical_ids']};raw={r['canonical_annotation_id']:r for r in core.load(BUNDLE/'human/responses.jsonl.gz')};out=[]
 for cid in sorted(cids):
  rr=raw[cid];out.append({k:rr.get(k)for k in ['canonical_annotation_id','image_id','worker_id','raw_points_1024x512','effective_points_1024x512','raw_point_count','effective_point_count','geometry_review_status','imputed_point','choices']})
 js('review/annotation_overlay_payload.json',dict(no_original_images=True,no_network_needed=True,annotations=out))
 js('audit/interpretation_summary.json',dict(class_union_comparisons=len(x),class_union_images=x.image_id.nunique(),both_unified_comparisons=int(x.both_classes_unified80.sum()),both_unified_to_multi=int((x.process_transition=='both_unified_to_multi').sum()),both_stable_to_multi=int((x.process_transition=='both_stable_to_multi').sum()),local_review_rows=len(q),local_review_images=q.image_id.nunique(),singleton_tolerance='Supported core may be stable with <=10% still-unconfirmed singleton interpretations. Do NOT say all individuals agree.',eight_person_case='Two images have the same actual eight-person subset of one training-fixed9-person roster; they are subgroup evidence, not full-image eight-person cohorts.'))
 print('INTERPRET DONE',len(q),'review rows',flush=True)

if __name__=='__main__':run()
