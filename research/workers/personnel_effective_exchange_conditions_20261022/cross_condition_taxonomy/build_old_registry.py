#!/usr/bin/env python3
"""Preserve old method identities and exact member maps; no refitting."""
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[v]='1'
from pathlib import Path
import pandas as pd
from discover_cross_condition import REPO, PREVIOUS, save, js, sha

OLD=REPO/'research/workers/personnel_global_composition_20261021'
TAX=REPO/'research/workers/personnel_taxonomy_20261021'
UNKNOWN={'','unknown','unassigned','insufficient_evidence','nan'}

def main():
 rows=[];sources=[]
 def take(path):
  sources.append(dict(path=str(path.relative_to(REPO)),sha256=sha(path)))
  return pd.read_csv(path,keep_default_na=False)
 for path in [TAX/'labels/manual_labels.csv',TAX/'labels/semi_labels.csv',TAX/'labels/lobo_labels.csv']:
  for r in take(path).to_dict('records'):
   cond=r['condition'];outer='ALL' if r['heldout_building']=='ALL_DATA' else r['heldout_building']
   for method,tier,col,parent in [('M_structure' if cond=='manual' else 'SP_scale','coarse','primary_coarse_class','primary_coarse_class'),
    ('M_structure' if cond=='manual' else 'SP_scale','fine','primary_fine_class','primary_coarse_class'),
    ('A2_relation','single','geometry_relation_class','geometry_relation_class')]:
    label=r[col];rows.append(dict(method=method,tier=tier,condition=cond,heldout_building=outer,worker_id=r['worker_id'],
     class_id=label,parent_class=r[parent],known=label not in UNKNOWN,missing_reason=r.get('geometry_missing_reason' if method=='A2_relation' else 'missing_reason',''),
     input_conditions=cond,label_fit_scope=r['label_fit_scope'],source_path=str(path.relative_to(REPO)),source_method=r['primary_method'] if method!='A2_relation' else 'cross_image_bound_cyclic_raw_relation',historical_identity='20261021_first_taxonomy'))
 for path in [PREVIOUS/'ALL_METHOD_LABELS_ALL_DATA.csv',PREVIOUS/'ALL_METHOD_LABELS_LOBO.csv.gz']:
  for r in take(path).to_dict('records'):
   for tier in ['coarse','fine']:
    rows.append(dict(method=r['method'],tier=tier,condition=r['condition'],heldout_building=r['heldout_building'],worker_id=r['worker_id'],class_id=r[tier+'_label'],parent_class=r['coarse_label'],known=r['known'],missing_reason=r['missing_reason'],input_conditions=r['condition'],label_fit_scope=r['label_stage'],source_path=str(path.relative_to(REPO)),source_method=r['selected_family'],historical_identity='20261021_v3_taxonomy'))
 for path in [OLD/'multivariate/labels_full.csv',OLD/'multivariate/labels_lobo.csv.gz',OLD/'multivariate/same_source_candidate_labels.csv']:
  for r in take(path).to_dict('records'):
   for tier in ['coarse','fine']:
    cross=str(r['Semi_cross_condition_auxiliary']).lower() in ['true','1']
    rows.append(dict(method=r['method_id'],tier=tier,condition=r['condition'],heldout_building=r['heldout_building'],worker_id=r['worker_id'],class_id=r[tier+'_class'],parent_class=r['coarse_class'],known=r['known'],missing_reason=r['missing_reason'],input_conditions='manual|semi_edit_auxiliary' if cross else r['condition'],label_fit_scope=r['label_status'],source_path=str(path.relative_to(REPO)),source_method=r['domains'],historical_identity='20261021_five_domain_study'))
 path=OLD/'composition/legacy_composition_labels.csv'
 for r in take(path).to_dict('records'):
  rows.append(dict(method=r['method_id'],tier=r['tier'],condition=r['condition'],heldout_building=r['heldout_building'],worker_id=r['worker_id'],class_id=r['class_id'],parent_class=r['parent_class'] or r['class_id'],known=True,missing_reason='',input_conditions='manual',label_fit_scope=r['label_fit_scope'],source_path=str(path.relative_to(REPO)),source_method=r['source_method_id'],historical_identity='20261019_20_frozen_history10_target12',training_buildings=r['training_buildings'],original_target_phase=r['original_target_phase']))
 d=pd.DataFrame(rows);assert not d.duplicated(['method','tier','condition','heldout_building','worker_id']).any()
 save(d[d.heldout_building.eq('ALL')],'OLD_METHOD_LABELS_ALL.csv');save(d[d.heldout_building.ne('ALL')],'OLD_METHOD_LABELS_TARGET_MAPS.csv.gz')
 members=[]
 for keys,g in d.groupby(['method','tier','condition','heldout_building','class_id'],dropna=False):
  members.append(dict(zip(['method','tier','condition','heldout_building','class_id'],keys),members='|'.join(sorted(g.worker_id)),n_members=len(g),known=bool(g.known.astype(str).str.lower().isin(['true','1']).all()),input_conditions=g.input_conditions.iloc[0],label_fit_scope=g.label_fit_scope.iloc[0]))
 mm=pd.DataFrame(members);save(mm[mm.heldout_building.eq('ALL')],'OLD_METHOD_MEMBERS_ALL.csv');save(mm[mm.heldout_building.ne('ALL')],'OLD_METHOD_MEMBERS_TARGET_MAPS.csv.gz')
 registry=[]
 descriptions={
 'M_structure':('Manual结构粗2/细4','Manual非OOS结构历史；原细类身份保留','结构补充、质量选择与有条件父内大块替换'),
 'SP_scale':('Semi位置尺度粗2/细3','Semi自身面积/高度；不是Manual类别转用','尺度差异与有条件替换风险'),
 'A2_relation':('跨图原答关系分区','Manual与Semi分别的原答几何关系；不是同图作答簇号直比','原答相似性及有条件替换风险分区'),
 'V3_BEHAVIOR':('v3各条件独立行为类','Manual和Semi分别选E/R/G或结构复杂度上下文；未联合两条件','Manual结构补充；Semi表达与冗余机会描述'),
 'V3_JOINT_QT':('v3各条件独立结构×QT','Manual CQT与Semi EQT均只用自身条件；联合指变量域，不是M+S','可解释质量—时间构成，连续QT保留竞争力'),
 'MV_QTD_manual':('Manual Q→T/D','自身Manual Q、时间和困难响应；S不在该方法中','质量与效率分层历史对照'),
 'MV_QTD_manual_new':('新批Manual Q→T/D','相同方法限制新批；不能与全人员版本混为一套标签','同来源敏感性及效率对照'),
 'MV_TDScopeSemi_manual_new':('Manual T/D/scope + Semi行为辅助','确有跨条件输入，但Semi域是编辑/错误机会下未改，不是双条件几何/QT','既有有标签探索/稳定性负结果'),
 'MV_QTScopeSemi_semi_new':('Semi Q/T/scope/Semi行为','自身Semi条件；缺困难机会不填零','既有Semi多域描述/预测对照'),
 'Rnew2':('真实替换关系反推','Manual新批；固定历史10楼训练、目标12楼映射','条件性成员替换风险分区'),
 'F01':('高Q内快慢类','Manual新批高Q域；固定历史10楼训练、目标12楼映射','简单图效率取舍，困难结构另查'),
 }
 for method,g in d.groupby('method'):
  dd=descriptions[method];registry.append(dict(method=method,name_zh=dd[0],formation_identity_zh=dd[1],previous_use_zh=dd[2],conditions='|'.join(sorted(g.condition.unique())),input_conditions='|'.join(sorted(g.input_conditions.unique())),all_label_rows=int(g.heldout_building.eq('ALL').sum()),target_label_rows=int(g.heldout_building.ne('ALL').sum()),distinct_target_buildings=g.loc[g.heldout_building.ne('ALL'),'heldout_building'].nunique(),source_paths='|'.join(sorted(g.source_path.unique())),new_fit_this_round=False))
 save(pd.DataFrame(registry),'OLD_METHOD_REGISTRY.csv');save(pd.DataFrame(sources),'OLD_METHOD_SOURCE_HASHES.csv')
 js('OLD_REGISTRY_RECEIPT.json',dict(rows=len(d),methods=len(registry),refitted=False,unknowns_preserved=True,
  legacy_fixed_history_note='Rnew2/F01 have only their published target maps; absent ALL/global memberships not fabricated',
  domain_screens='26-subset Ward2 screening identities remain in old multivariate/domain_subset_26_coverage.csv; no repeated domain-grid search',
  old_cross_condition='MV_TDScopeSemi_manual_new and other Manual screens containing Semi edit domain truly cross conditions; V3_JOINT_QT does not'))
 print('Old registry:',len(registry),'methods;',len(d),'labels')
if __name__=='__main__':main()
