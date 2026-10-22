#!/usr/bin/env python3
"""Human-readable identities, members, crosswalks and role evidence."""
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[v]='1'
import json
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score,adjusted_mutual_info_score
from scipy.optimize import linear_sum_assignment
from discover_cross_condition import HERE,PREVIOUS,HIST,CONDITIONS,PREFIX,FAMILIES,save,js,sha

def role(r,prefix):
 turn=r[prefix+'_turn_history'];red=r[prefix+'_redundancy_history'];area=r[prefix+'_area_history'];height=r[prefix+'_height_history']
 q=r[prefix+'_q_history'];t=r[prefix+'_t_history']
 text='较少转折' if turn<-.3 else ('较多转折' if turn>.3 else '常规转折量')
 if red>.05:text+='、近共线点偏多'
 if area<-.05:text+='、相对较小底面'
 elif area>.05:text+='、相对扩展底面'
 if height<-.02:text+='、相对较低高度'
 elif height>.02:text+='、相对较高高度'
 qtext='历史Q偏高' if q>3 else ('历史Q偏低' if q<-3 else '历史Q居中')
 ttext='相对快' if t<np.log(.8) else ('相对慢' if t>np.log(1.25) else '时间居中')
 return text,qtext,ttext

def main():
 freeze=sha(HERE/'LABEL_FREEZE.json')
 all_l=pd.read_csv(HERE/'CROSS_LABELS_ALL.csv');lo=pd.read_csv(HERE/'CROSS_LABELS_LOBO.csv.gz')
 ca=pd.read_csv(HERE/'CROSS_CLASS_CENTERS_ALL.csv');cl=pd.read_csv(HERE/'CROSS_CLASS_CENTERS_LOBO.csv.gz')
 centers=pd.concat([ca,cl],ignore_index=True);role_rows=[]
 for r in centers.to_dict('records'):
  m,mq,mt=role(r,'m');s,sq,st=role(r,'s')
  r.update(manual_marking_role_zh=m,semi_marking_role_zh=s,manual_qt_role_zh=mq+'、'+mt,semi_qt_role_zh=sq+'、'+st,
   joint_role_zh='Manual：'+m+'；Semi：'+s,role_thresholds_are_descriptive=True,
   role_interpretation='relative same-image/reference peers; do not equate extra turns with correctness or extended floor with error',
   qt_used_in_formation=r['method']=='XCOND_GEOM_QT')
  role_rows.append(r)
 roles=pd.DataFrame(role_rows);save(roles[roles.heldout_building.eq('ALL')],'CLASS_DEFINITIONS_ALL.csv');save(roles[roles.heldout_building.ne('ALL')],'CLASS_ROLES_LOBO.csv.gz')
 # One copy of common membership is enough for class stability: class formation
 # is truly joint, even though all endpoint evaluations must remain separate.
 aa=all_l[all_l.condition.eq('manual')];ll=lo[lo.condition.eq('manual')];pairs=pd.read_csv(HERE/'PAIRED_INPUT_RECORDS.csv.gz')
 stabs=[];align=[];member=[]
 for method,g in ll.groupby('method'):
  full=aa[aa.method.eq(method)&aa.known].set_index('worker_id')
  for outer,z in g.groupby('heldout_building'):
   train=z[z.known].set_index('worker_id');common=full.index.intersection(train.index)
   effective=bool(method!='XCOND_PAIRED' or pairs.building_id.eq(outer).any())
   for tier in ['coarse','fine']:
    col=tier+'_label';ari=adjusted_rand_score(full.loc[common,col],train.loc[common,col]) if len(common)>=6 else np.nan
    contingency=pd.crosstab(full.loc[common,col],train.loc[common,col]);a,b=linear_sum_assignment(-contingency.to_numpy())
    mapping={contingency.columns[j]:contingency.index[i] for i,j in zip(a,b)}
    matched=int(sum(contingency.iloc[i,j] for i,j in zip(a,b)))
    stabs.append(dict(method=method,heldout_building=outer,tier=tier,effective_feature_deletion=effective,workers_common=len(common),
     all_known_workers=len(full),outer_known_workers=len(train),ari=ari,optimal_one_to_one_agreement=matched/len(common) if len(common) else np.nan,
     all_k=full[col].nunique(),outer_k=train[col].nunique(),selection_status=z.selection_status.iloc[0],
     source_AMI=adjusted_mutual_info_score(train.origin,train[col]) if len(train) else np.nan))
    for clname,q in train.groupby(col):
     common_q=q.index.intersection(common);matches=full.loc[common_q,col].value_counts();largest=matches.index[0] if len(matches) else ''
     align.append(dict(method=method,heldout_building=outer,tier=tier,outer_class=clname,
      optimal_all_class=mapping.get(clname,''),majority_all_class=largest,majority_share=float(matches.iloc[0]/len(common_q)) if len(matches) else np.nan,
      members='|'.join(q.index),n_members=len(q),warning='alignment is descriptive, not identical class meaning across folds'))
    for worker in common:
     member.append(dict(method=method,heldout_building=outer,tier=tier,worker_id=worker,effective_feature_deletion=effective,
      all_class=full.loc[worker,col],outer_class=train.loc[worker,col],aligned_all_class=mapping.get(train.loc[worker,col],''),
      one_to_one_aligned_same=mapping.get(train.loc[worker,col],'')==full.loc[worker,col]))
 st=pd.DataFrame(stabs);save(st,'OUTER_STABILITY_BY_BUILDING.csv');save(pd.DataFrame(align),'OUTER_CLASS_ALIGNMENT.csv');save(pd.DataFrame(member),'MEMBER_OUTER_ALIGNMENT.csv.gz')
 summary=[]
 for (method,tier),g in st.groupby(['method','tier']):
  for mode,zz in [('all_computation_folds',g),('effective_feature_deletion_only',g[g.effective_feature_deletion])]:
   summary.append(dict(method=method,tier=tier,denominator=mode,folds=len(zz),mean_ari=zz.ari.mean(),median_ari=zz.ari.median(),minimum_ari=zz.ari.min(),
    mean_optimal_agreement=zz.optimal_one_to_one_agreement.mean(),minimum_known=zz.outer_known_workers.min(),maximum_known=zz.outer_known_workers.max(),
    mean_source_AMI=zz.source_AMI.mean()))
 save(pd.DataFrame(summary),'OUTER_STABILITY_SUMMARY.csv')
 choices=pd.DataFrame(json.loads((HERE/'SELECTED_MODELS.json').read_text())).drop(columns=['coarse_rule','family_domains','input_conditions'])
 save(choices,'SELECTION_BY_BUILDING.csv');save(choices[choices.heldout_building.ne('ALL')].groupby(['method','coarse_k','fine_k','status']).size().rename('folds').reset_index(),'SELECTION_DISTRIBUTION.csv')
 # Preserve all old methods rather than interpreting a new partition as a
 # replacement hierarchy for M/SP/A2/QTD/Rnew2/F01.
 old=pd.read_csv(HERE/'OLD_METHOD_LABELS_ALL.csv');cross=[]
 for (method,cond),g in all_l.groupby(['method','condition']):
  for (omid,tier),q in old[old.condition.eq(cond)].groupby(['method','tier']):
   z=g[g.known].merge(q[q.known][['worker_id','class_id']],on='worker_id',validate='one_to_one')
   for (newclass,oldclass),v in z.groupby(['fine_label','class_id']):
    cross.append(dict(method=method,condition=cond,new_fine_class=newclass,old_method=omid,old_tier=tier,old_class=oldclass,members='|'.join(v.worker_id),n_members=len(v)))
 save(pd.DataFrame(cross),'OLD_NEW_CLASS_CROSSWALK_ALL.csv')
 readable=[]
 for cond in CONDITIONS:
  p=all_l[all_l.condition.eq(cond)][['worker_id','origin']].drop_duplicates().set_index('worker_id')
  for method,g in all_l[all_l.condition.eq(cond)].groupby('method'):
   use=g.set_index('worker_id')[['coarse_label','fine_label','known','missing_reason']].add_prefix(method+'__');p=p.join(use)
  for (method,tier),g in old[old.condition.eq(cond)].groupby(['method','tier']):p=p.join(g.set_index('worker_id').class_id.rename(method+'__'+tier))
  readable.append(p.reset_index().assign(condition=cond))
 save(pd.concat(readable,ignore_index=True),'PERSONNEL_METHOD_MAP_ALL.csv')
 # Visible paired opportunities carry exact object ids and actual raw values.
 # The old source has no exact initialization for most new workers; no edit
 # trajectory is inferred from these final-answer condition contrasts.
 ann=aa[['worker_id','method','coarse_label','fine_label','known']]
 case_rows=[]
 for method,g in ann.groupby('method'):
  z=pairs.merge(g,on='worker_id',validate='many_to_one');z=z[z.known]
  for (label,building,img),v in z.groupby(['fine_label','building_id','image_id']):
   case_rows.append(dict(method=method,label_stage='ALL_discovery_opportunity_only',fine_label=label,building_id=building,image_id=img,
    image_code=v.image_code_m.iloc[0],members='|'.join(v.worker_id),n_pairs=len(v),
    mean_raw_delta_turn=v.pair_delta_raw_turn_history.mean(),mean_raw_delta_redundancy=v.pair_delta_raw_redundancy_history.mean(),
    mean_raw_delta_log_area=v.pair_delta_raw_area_history.mean(),mean_raw_delta_log_height=v.pair_delta_raw_height_history.mean(),
    m_object_ids='|'.join(v.object_id_m),s_object_ids='|'.join(v.object_id_s)))
 save(pd.DataFrame(case_rows),'PAIRED_VISIBLE_CLASS_OPPORTUNITIES.csv.gz')
 assert freeze==sha(HERE/'LABEL_FREEZE.json')
 js('CLASS_INTERPRETATION_RECEIPT.json',dict(label_freeze_sha256=freeze,role_thresholds={'turn':[-.3,.3],'redundancy':.05,'log_area':[-.05,.05],'log_height':[-.02,.02],'q':[-3,3],'log_relative_time':[float(np.log(.8)),float(np.log(1.25))]},
  role_labels='descriptive aids only; continuous centers remain authoritative; do not compare raw class numbers across folds',
  nested_levels_verified=bool((lo.groupby(['method','condition','heldout_building','fine_label']).coarse_label.nunique()<=1).all()),
  old_methods_preserved=True,paired_unknown_is_not_zero=True,paired_selected_history_not_causal=True))
 print(pd.DataFrame(summary).query("denominator=='effective_feature_deletion_only'").round(4).to_string(index=False))
if __name__=='__main__':main()
