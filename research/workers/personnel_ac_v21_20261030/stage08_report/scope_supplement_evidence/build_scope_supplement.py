"""Extract already-complete scope results after a registration-only selection.

No eligibility check, label fitting, team generation, fusion, or scoring occurs.
Only the separate supplement folder and requested Markdown report are written.
"""
from pathlib import Path
import csv,hashlib,json,subprocess
import pandas as pd

OUT=Path(__file__).resolve().parent
BASE=OUT.parents[1]
REPORT=BASE/'stage08_report/SCOPE_SUPPLEMENT_VERIFIED_ZH.md'
COMMIT='ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff'
KEY=['scope','condition','analysis_view','method','role_direction','n_condition','m_condition']
METRICS=['B8L2_CA','D10_CA','fusion_turn_n_CA','fusion_short_turn_edges_CA',
 'ref_node_recall_5_CA','ref_node_recall_9_CA','ref_edge_recall_5_CA',
 'geometry_bev_distance_AC_complete_outputs_only','geometry_centroid_distance_AC_complete_outputs_only',
 'geometry_area_h2_CA','height_mean_h_CA','boundary_loss_CA','direction_loss_CA','height_loss_CA',
 'record_time_CA_seconds_source_matched','record_time_CA_pct_source_matched',
 'A_Q_missing','C_Q_missing','A_insufficient_nodes','C_insufficient_nodes',
 'A_connection_failure','C_connection_failure','A_output_invalid_geometry','C_output_invalid_geometry',
 'A_reference_floor_only','C_reference_floor_only','A_measurement_exception','C_measurement_exception',
 'A_other_Q_missing','C_other_Q_missing']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(d,name):
 d=d if isinstance(d,pd.DataFrame) else pd.DataFrame(d)
 d.to_csv(OUT/name,index=False,encoding='utf-8-sig')
def safe_json(d):return json.loads(pd.DataFrame(d).to_json(orient='records',force_ascii=False))
def fmt(v,places=3,signed=False):return '不可评' if pd.isna(v) else format(float(v),('+' if signed else '')+f'.{places}f')
def table(headers,rows):
 return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|']+['|'+'|'.join(str(v) for v in r)+'|' for r in rows])

def main():
 selection_path=OUT/'SCORE_BLIND_SCOPE_SELECTION.json'
 selection=json.loads(selection_path.read_text())
 src=BASE/'stage05_main/CONDITION_METRIC_SUMMARY.csv.gz'
 assert sha(src)==selection['source_sha256']
 d=pd.read_csv(src,low_memory=False)
 selected=[];ledger=[]
 for s in selection['selections']:
  q=d
  for k,v in s['source_key'].items():q=q[q[k].astype(str).eq(str(v))]
  q=q[q.metric.isin(METRICS)].copy()
  assert len(q)==len(METRICS) and q.metric.nunique()==len(METRICS),(s['selection_id'],len(q))
  q.insert(0,'selection_id',s['selection_id']);selected.append(q)
  for r in q.to_dict('records'):
   ledger.append(dict(selection_id=s['selection_id'],source_path=str(src.relative_to(BASE)),
    source_row_key=json.dumps({**s['source_key'],'metric':r['metric']},ensure_ascii=False,sort_keys=True),
    values_json=pd.DataFrame([r]).to_json(orient='records',force_ascii=False,double_precision=15)))
 selected=pd.concat(selected,ignore_index=True)
 save(selected,'SCOPE_SELECTED_METRIC_SOURCE_ROWS.csv')
 save(ledger,'SCOPE_SOURCE_ROW_LEDGER.csv')
 def row(sid,metric):
  r=selected[(selected.selection_id==sid)&(selected.metric==metric)]
  assert len(r)==1
  return r.iloc[0]
 brief=[]
 for s in selection['selections']:
  sid=s['selection_id'];q=row(sid,'B8L2_CA');z=row(sid,'D10_CA')
  item={**s['source_key'],'selection_id':sid,
   **{c:q[c] for c in ['registered_pools','registered_images','registered_buildings','registered_pairs',
    'actual_n_A_min','actual_n_A_max','actual_m_X_min','actual_m_X_max']}}
  for metric,prefix in [('B8L2_CA','B8L2'),('D10_CA','D10')]:
   r=row(sid,metric)
   for c in ['valid_pairs','valid_pools','valid_images','valid_buildings','image_mean','image_balanced_mean_absolute',
    'positive_images','negative_images','tied_images','positive_buildings','negative_buildings','building_balanced_mean','image_p10','image_p90']:
    item[prefix+'_'+c]=r[c]
  for metric,prefix in [('A_Q_missing','A_missing'),('C_Q_missing','C_missing'),
   ('fusion_turn_n_CA','turns'),('geometry_bev_distance_AC_complete_outputs_only','complete_BEV'),
   ('record_time_CA_pct_source_matched','record_labor_pct')]:
   r=row(sid,metric)
   for c in ['image_mean','valid_pairs','valid_images','valid_buildings','positive_images','negative_images','tied_images']:item[prefix+'_'+c]=r[c]
  brief.append(item)
 brief=pd.DataFrame(brief);save(brief,'SCOPE_SELECTED_CONDITION_BRIEF.csv')

 inventory_path=BASE/'stage01_capacity/POOL_INVENTORY_ALL_DOMAINS.csv'
 # The formal funnel execution index is Manual-only (226 pools). Read the
 # already-complete per-pool native receipts to include the 32 Semi pools.
 execution_path=OUT/'NATIVE_EXECUTION_CHECKS_ALL_DOMAINS.csv'
 checks=[]
 for p in sorted((BASE/'stage03_endpoints/pools').glob('*/CHECKS.json')):
  c=json.loads(p.read_text())
  checks.append({k:c[k] for k in ['pool_id','complete','requested','total']}|
   dict(source_path=str(p.relative_to(BASE)),source_sha256=sha(p),scalar_gzip_read_to_EOF=c['scalar_verification']['gzip_read_to_eof']))
 execution=pd.DataFrame(checks);save(execution,execution_path.name)
 inventory=pd.read_csv(inventory_path)
 assert inventory.pool_id.nunique()==len(inventory)==294
 assert execution.pool_id.nunique()==len(execution)==258
 assert execution.requested.sum()==execution.total.sum()==478012
 assert set(execution.pool_id)<=set(inventory.pool_id) and execution.complete.all()
 inventory['this_run_executed']=inventory.pool_id.isin(execution.pool_id)
 def group(r):
  if r['layer']=='ordinary_manual':return 'ordinary_Manual'
  if r['layer']=='ordinary_semi':return 'ordinary_Semi'
  return 'doorway_or_special_inventory_only'
 inventory['verified_scope_group']=inventory.apply(group,axis=1)
 counts=inventory.groupby('verified_scope_group').agg(input_pools=('pool_id','size'),executed_pools=('this_run_executed','sum')).reset_index()
 expected={'ordinary_Manual':(236,226),'ordinary_Semi':(38,32),'doorway_or_special_inventory_only':(20,0)}
 for r in counts.itertuples(index=False):assert (r.input_pools,r.executed_pools)==expected[r.verified_scope_group]
 counts.loc[len(counts)]=['TOTAL',294,258];save(counts,'ALL_DOMAIN_ENTRY_EXECUTION_COUNTS.csv')
 domains=[]
 for k,g in inventory.groupby(['scope','condition','layer'],dropna=False):
  a=g[g.this_run_executed]
  domains.append(dict(zip(['scope','condition','layer'],k))|dict(input_pools=len(g),input_images=g.image.nunique(),input_buildings=g.building.nunique(),
   executed_pools=len(a),executed_images=a.image.nunique(),executed_buildings=a.building.nunique(),not_executed_pools=len(g)-len(a)))
 domains=pd.DataFrame(domains);save(domains,'SCOPE_DOMAIN_POOL_COVERAGE.csv')
 identities=inventory[(inventory.scope=='other_admitted')&(inventory.condition=='manual')&inventory.this_run_executed]
 assert len(identities)==20 and identities.image.nunique()==18 and identities.building.nunique()==7
 save(identities,'EXECUTED_OTHER_TARGET_POOL_IDENTITIES.csv')
 save(inventory[~inventory.this_run_executed],'NOT_EXECUTED_POOL_SCOPE_STATUS.csv')
 status_path=BASE/'stage05_funnel_bridge/STATE_DOMAIN_DENOMINATOR_SUMMARY.csv'
 statuses=pd.read_csv(status_path)
 save(statuses,'FROZEN_PHYSICAL_PAIR_STATES_BY_DOMAIN.csv')
 assert statuses.physical_pairs.sum()==412839
 semi_receipt_path=BASE/'stage01b_semi/DESIGN_REGISTRATION_RECEIPT.json'
 semi=json.loads(semi_receipt_path.read_text())
 assert semi['manual_labels_applied_to_semi'] is False and semi['pools_available']==38 and semi['registered_pools']==32
 label_path=BASE/'stage01b_semi/SEMI_BASE_LABELS_ALL_LOBO.csv.gz'
 assert sha(label_path)==semi['label_sha256']

 # An existing audited source statement, not a new re-count or new admission.
 audit_rel='research/data/releases/v2.1/SCOPE_ROUTING_INDEPENDENT_AUDIT_20261029.md'
 audit=subprocess.run(['git','show',COMMIT+':'+audit_rel],cwd=BASE.parent/'repo',check=True,capture_output=True).stdout
 blob=subprocess.run(['git','rev-parse',COMMIT+':'+audit_rel],cwd=BASE.parent/'repo',check=True,capture_output=True,text=True).stdout.strip()
 source_dir=OUT/'sources';source_dir.mkdir(exist_ok=True)
 audit_path=source_dir/'FROZEN_SCOPE_ROUTING_AUDIT_20261029.md';audit_path.write_bytes(audit)
 audit_text=audit.decode('utf-8');oos_lines=[s.strip() for s in audit_text.splitlines() if '1,222' in s and 'OOS' in s]
 assert len(oos_lines)==1
 oos=dict(source_commit=COMMIT,git_path=audit_rel,git_blob=blob,sha256=sha(audit_path),
  source_statement=oos_lines[0],reported_OOS_or_pending_OOS_original_records=1222,
  current_task_recount=False,unit='original_answer_inventory_records',formal_quality_admission=False,
  inclusion_in_new_ordinary_Manual_or_Semi_teams=False,
  note='Separate record-level inventory; not 1222 pools and not the 20 doorway/special pools. No hold, historical exclusion, or eligibility restriction is lifted.')
 (OUT/'OOS_FROZEN_STATUS.json').write_text(json.dumps(oos,ensure_ascii=False,indent=2))

 # Compact report and independently selectable source rows for the parent report.
 blocks=['# 普通Semi、其它合法目标与OOS范围补充核验',
 '本补充只读取已完成结果，不新增人员、标签拟合、团队、融合或评分。条件先按登记支持选定并保存，再提取效果；没有按最高Q或最大收益挑选。完整源行、筛选键和来源哈希保存在同名证据目录。',
 '## 1 范围核对：294个入口与258个实际执行池',
 table(['入口类别','入口池','执行池'],counts.values.tolist()),
 '294=236个普通Manual池+38个普通Semi池+20个门口/特殊库存池；258=226个普通Manual执行池+32个普通Semi执行池。旧容量阶段所称“普通Manual以外58池”包括38个普通Semi池，不能把58全部称为未执行OOS。20个未执行特殊库存池具体为17个门口Manual、2个特殊Manual、1个特殊Semi。',
 table(['空间域','条件','layer','入口池/图','执行池/图/楼'],[[r.scope,r.condition,r.layer,f'{r.input_pools}/{r.input_images}',f'{r.executed_pools}/{r.executed_images}/{r.executed_buildings}'] for r in domains.itertuples(index=False)]),
 '其它合法目标的普通Manual实际执行20池、18图、7楼；同一图的不同目标始终分别组队、使用各自参考评价。图层汇总才在同图的目标池之间等权，不能将20池称作20张独立图片。其余10池只有3–4人，未进入本轮登记设计，不统一称作任何规模的AC都不可能。',
 '## 2 其它合法目标：按主方法保留全部方向',
 '采用既定TARGET_DSTRUCT K3。固定条件选择n6/m3，保留1→2、1→3、2→3全部方向；另外保留三个方向的池前沿整类等量结果。各方向的池前沿n/m和图片可能不同，不能用前沿与固定条件均值之差解释纯人数或背景效应。此处整类前沿按主表合并来源全出、目标全入、两类全换，并不把它们冒称同一种整目标干预。']
 def quality_rows(ids):
  rows=[]
  for sid in ids:
   q=row(sid,'B8L2_CA');z=row(sid,'D10_CA')
   n=f'{int(q.actual_n_A_min)}–{int(q.actual_n_A_max)}';m=f'{int(q.actual_m_X_min)}–{int(q.actual_m_X_max)}'
   rows.append([sid,q.role_direction,n+'/'+m,f'{int(q.valid_pairs)}/{int(q.registered_pairs)}',
    f'{int(q.valid_pools)}/{int(q.registered_pools)}',f'{int(q.valid_images)}/{int(q.registered_images)}；{int(q.valid_buildings)}',
    fmt(q.image_mean,signed=True),fmt(z.image_mean,signed=True),fmt(q.image_balanced_mean_absolute),fmt(z.image_balanced_mean_absolute),
    f'{int(q.positive_images)}/{int(q.negative_images)}/{int(q.tied_images)}',f'{int(z.positive_images)}/{int(z.negative_images)}/{int(z.tied_images)}'])
  return rows
 ids=[s['selection_id'] for s in selection['selections'] if s['selection_id'].startswith('other_target')]
 hdr=['条件ID','方向','实际n/m','Q可评/登记对','Q可评/登记池','Q可评/登记图；楼','ΔB8L2','ΔD10','均|ΔB8L2|','均|ΔD10|','B8正/负/零图','D10正/负/零图']
 blocks.append(table(hdr,quality_rows(ids)))
 blocks.append('固定6/3中→高方向在5图、3楼有共同可评分结果，B8L2平均+24.302，D10+24.253，但质量只覆盖26/48登记对。全部登记事件的缺Q图等权率A为38.75%、C为5.00%，两者和成功对的平均升质是不同分母。不能仅凭较大的成功对分差推广到所有尝试。这个条件有效转折图均值+1.550，但同源劳动只有4对、1图，不足以概括这个目标域的劳动方向。')
 blocks.append('整类前沿2→3覆盖18个登记目标池、17图、6楼，其中17池/17图有共同Q，103/107对可评分；B8L2平均+10.848、均绝对变化14.445，13图正向、4图负向。其同源劳动35对、6图、4楼，图均值+2.237%，4图增加、2图减少。低→中的前沿则B8L2均值仅+0.625，7图正向、8图负向，D10均值−0.150。三个方向一起说明目标空间补充存在差异，并非所有类别调整普遍改善。')
 blocks.extend(['## 3 普通Semi：自身冻结V3标签的次要补充',
 'Semi用独立冻结的V3_BEHAVIOR_COARSE/FINE和V3_JOINT_QT_COARSE/FINE，不应用Manual的TARGET分类。方向是已有类别ID的字典序，不能把S1→S2或K1→K2改写成低Q→高Q。条件选择每条粗路线登记图数最多的方向，以及对应主要细层方向；所有其他方向仍留在完整结果中。这是选取有足够支持的范围说明，不是粗细分类优劣测试。',
 'Semi固定n20的多数方向只有1–2张登记图，因此本节使用池前沿整类等量设计；n/m随池而变。行为粗层的n范围3–42、m范围1–13，QT粗层n范围3–43、m范围1–13，不能沿用普通Manual最大35人的界限。粗细层的成员候选与覆盖不完全相同。'])
 semi_ids=['semi_behavior_coarse','semi_behavior_fine','semi_joint_coarse','semi_joint_fine']
 blocks.append(table(hdr,quality_rows(semi_ids)))
 blocks.append('行为粗层S1→S2有28图登记、27图共同Q可评；B8L2均值−2.612，均绝对变化3.077，但27图中是4图正向、11图负向、12图近零，不能写成多数图片下降。其A缺Q图等权率7.143%、C为0；质量均值只用106/114个共同可评分对，因此“输出更常可评”与“已可评分组合的均值降低”应并列，不能彼此替代。')
 blocks.append('QT细层K1.1→K2.1的B8L2均值−1.865，但8图正向、7图负向、10图近零；负均值不代表多数图负向。该补充保留了质量降低、零变化及输出状态改善等不同响应，不能称作Manual规律的外部验证。')
 support=[]
 for sid in ids+semi_ids:
  t=row(sid,'fusion_turn_n_CA');g=row(sid,'geometry_bev_distance_AC_complete_outputs_only');l=row(sid,'record_time_CA_pct_source_matched');a=row(sid,'A_Q_missing');c=row(sid,'C_Q_missing')
  support.append([sid,fmt(t.image_mean,signed=True),str(int(t.valid_pairs)),fmt(g.image_mean,4),str(int(g.valid_pairs)),
   fmt(l.image_mean,signed=True)+'%',f'{int(l.valid_pairs)}对/{int(l.valid_images)}图/{int(l.valid_buildings)}楼',
   f'{int(l.positive_images)}/{int(l.negative_images)}/{int(l.tied_images)}',fmt(100*a.image_mean,3)+'%→'+fmt(100*c.image_mean,3)+'%',int(a.valid_pairs)])
 blocks.extend(['## 4 结构、劳动与状态采用各自有效分母',
 table(['条件ID','Δ有效转折','结构对','完整输出BEV距离','几何对','Δ记录劳动%','劳动支持','劳动增/减/零图','A→C缺Q图等权率','状态对'],support),
 '劳动为同源记录劳动：要求两队全部成员记录完整且各计时来源人数向量相同，不是并行完成时间。Semi行为粗层劳动−15.846%只来自16对、6图、4楼（1图增加、5图减少）；QT粗层−1.115%仅20对、4图、3楼（2图增加、2图减少）。质量与劳动的有效图片不相同，不能合成已证实的整体质量—时间权衡。',
 '域级状态按不同物理端点对去重，含各已登记设计族和背景，不能与上面的neutral主条件直接当同一分母相减：',
 table(['条件','目标域','物理对','双端Q可评','仅一端缺Q','双端缺Q','双缺但状态不同'],[[r.condition,r.scope,r.physical_pairs,r.both_present_pairs,r.one_missing_pairs,r.both_missing_pairs,r.both_missing_different_pairs] for r in statuses.itertuples(index=False) if r.condition=='semi' or r.scope=='other_admitted']),
 '其它合法目标的唯一Semi池为uNb9QFRL6hY-68，N=4，执行1池1图1楼；全部设计跨方法去重后8个物理对均可评分。其整类前沿条件为n3/m1，各方向仅1–2个登记方法事件，完整结果保留在证据CSV，但不作为多图规律。',
 '## 5 OOS与门口/特殊库存的边界',
 '门口/特殊20池是已有池库存层，当前没有新增执行；它们并不等同于原答层的OOS清单。冻结提交中的空间验收记录称1,222份OOS或待定OOS原答仍无正式质量准入。本补充沿用该已审查状态，没有重做1,222份资格审查，没有因空间修复解除历史GT、清洗或人工hold，也没有将缺Q填零或称作本轮融合失败。',
 '1,222的单位是原答库存条目，不能与294个池相加，不能与20个门口/特殊池互换。本轮普通Manual与Semi只在各自已准入目标池内登记和评价；其它合法目标已经准入的池也不再因“不是原主目标”而被误称OOS。',
 '## 6 可回连文件与筛选键',
 'SCOPE_SELECTED_METRIC_SOURCE_ROWS.csv保存15个选择条件×30个指标的原汇总行；SCOPE_SOURCE_ROW_LEDGER.csv逐行保存完整筛选键和原值。SCORE_BLIND_SCOPE_SELECTION.json保留登记支持选型、来源哈希及对应理由；SCOPE_SELECTED_CONDITION_BRIEF.csv提供紧凑结果。ALL_DOMAIN_ENTRY_EXECUTION_COUNTS.csv、SCOPE_DOMAIN_POOL_COVERAGE.csv与EXECUTED_OTHER_TARGET_POOL_IDENTITIES.csv提供范围分母和20个实际其它目标池。OOS_FROZEN_STATUS.json区分来源引用与本轮未重新核算。'])
 REPORT.write_text('\n\n'.join(blocks)+'\n',encoding='utf-8')
 source_paths=[src,inventory_path,execution_path,status_path,semi_receipt_path,label_path,selection_path,audit_path]
 receipt=dict(status='passed',source_commit=COMMIT,selected_conditions=len(selection['selections']),metric_source_rows=len(selected),
  unique_source_keys=True,no_target_result_used_for_selection=True,new_fusions=0,new_scores=0,new_teams=0,
  input_pool_decomposition={'ordinary_Manual':236,'ordinary_Semi':38,'doorway_or_special':20,'total':294},
  executed_pool_decomposition={'ordinary_Manual':226,'ordinary_Semi':32,'doorway_or_special':0,'total':258},
  other_admitted_Manual={'input_pools':30,'executed_pools':20,'executed_images':18,'executed_buildings':7},
  Semi_own_V3_labels=True,Semi_Manual_labels_applied=False,Semi_class_ID_direction_is_quality_order=False,
  OOS_count_is_existing_audit_statement_not_new_recount=True,
  sources=[dict(path=str(p.relative_to(BASE)),bytes=p.stat().st_size,sha256=sha(p)) for p in source_paths])
 (OUT/'SCOPE_SUPPLEMENT_VERIFICATION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
 files=[]
 for p in sorted([*OUT.rglob('*'),REPORT]):
  if not p.is_file() or p.name in ['MANIFEST.csv','READABILITY_RECEIPT.json'] or '__pycache__' in p.parts:continue
  rows=None
  if p.suffix=='.csv':
   with p.open(encoding='utf-8-sig',newline='') as f:
    rr=csv.reader(f);header=next(rr);assert len(header)==len(set(header));rows=0
    for v in rr:assert len(v)==len(header);rows+=1
  elif p.suffix=='.json':json.loads(p.read_text())
  elif p.suffix=='.py':compile(p.read_text(),str(p),'exec')
  else:p.read_text(encoding='utf-8')
  files.append(dict(path=str(p.relative_to(BASE)),bytes=p.stat().st_size,sha256=sha(p),rows=rows))
 save(files,'MANIFEST.csv')
 (OUT/'READABILITY_RECEIPT.json').write_text(json.dumps(dict(status='passed',files=len(files),all_csv_read_to_EOF=True,all_json_parsed=True,all_python_compiled=True,report_included=True),indent=2))
 print(json.dumps({k:v for k,v in receipt.items() if k!='sources'},ensure_ascii=False))
 print(brief[~brief.selection_id.str.contains('inventory')][['selection_id','B8L2_image_mean','D10_image_mean','B8L2_valid_pairs','registered_pairs','B8L2_valid_images','registered_images']].to_string(index=False))

if __name__=='__main__':main()
