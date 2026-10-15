import json,gzip,hashlib,subprocess,pathlib,copy
ROOT=pathlib.Path('/workspace/scratch/a365811da80c')
REPO=ROOT/'current_order_review_20261010'
REL=pathlib.Path('analysis_results/image_difficulty_full_review_20261010/user_review_20261010')
NEW=REPO/REL
OLD=ROOT/'scope_release_staging_20261010/full_review'
OUT=ROOT/'new_scope_batch_20261010'
COMMIT='24360ad8544d76d8aba18a8e641f784a76ca0d42'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
q=read(NEW/'scope_queue.json'); src=read(NEW/'source_review.json'); previous=read(ROOT/'manual_scope_review_received_20261010_batch2.json')
inv=json.load(gzip.open(OLD/'cloud_inventory/inventory.json.gz','rt'))
rows={x['image_id']:x for x in inv['images']}
latest={x['image_id']:(i,x) for i,x in enumerate(src['records'])}
prior_ids={x['image_id'] for x in previous['records']}
prior_gt={x['reference_object_id'] for x in previous['records']}
archive_names=['local_increment/integration_verified69.json','archive_reconciliation/new_early_image_comments_21.json','archive_reconciliation/historical_group_comments_55.json','archive_reconciliation/historical_image_notes_39_reconfirmed.json','archive_reconciliation/new_batch_discussion_records_3.json']
archive={name:read(OLD/name) for name in archive_names}
restored=read(OLD/'archive_reconciliation/restored_historical_reference_coordinates.json')
ops={
'S9hNv5qa7GM-04':('local_boundary_redefinition','柜边、门扇边与更内侧真实墙面的取舍；请用户重新画定或保留边界。','最新备注把 GT 解释为柜边/门扇边，旧 W011/R00672 备注却说 GT 到柜后墙角而人员停柜处，方向相反。不得沿用旧备注替用户预选内/外。'),
'pa4otMbVnkk-14':('doorway_target_redefinition','确认靠近门洞时以外侧区域还是房间内部为目标，并明确门口停止线。','最新 scope 选项为未审。旧原话偏好 GT 标法并强调外侧区域；新增意见未给出新 polygon，也未明确推翻旧偏好。'),
'q9vSo1VnCiC-11':('doorway_branch_decision','核对右侧门洞后区域是否纳入，若不纳入由用户指定停止线。','最新只说范围不同；旧原话“我觉得可以不标”提供候选方向，不是本轮坐标确认。'),
'q9vSo1VnCiC-12':('two_doorway_branch_decision','核对 GT 两处门后区域是否纳入，可展示旧 W032/R01744 的简化标法作证据。','最新未指明哪两条停止线，也未批准复制任何人员 polygon。'),
'uNb9QFRL6hY-44':('entrance_step_region_decision','核对入口台阶区域及其停止边，区分台阶不同平面与房间底面。','旧评论偏向不标门口台阶；几何约束和同房讨论只作历史说明，不能自动删去区域。'),
'uNb9QFRL6hY-55':('entrance_branch_decision','核对是否舍去 GT 的门口区域，并分开处理人员额外 p9/p10。','旧 W033/R03156、W037/R03157 支持不标入口；W028/R03160 同时有多余点问题。不得把多余点误认成范围裁定。'),
'uNb9QFRL6hY-68':('entrance_branch_decision','核对是否舍去 GT 门口区域，选择实际停止线。','旧记录包含 W036/R03200 与 GT 类似的范围，也有 W032 等不同范围；不能升级为“无人同 GT”。同一范围中的点位错误须分开。'),
'uNb9QFRL6hY-81':('entrance_branch_decision','核对 GT 的门口细长区域是否纳入，并确认停止边。','历史措辞是“大部分”未标，不能写成全部；最新未给坐标。'),
'wc2JMjhGNzB-22':('entrance_branch_decision','核对 GT 的门口区域是否保留，用户指定保留区域或新停止线。','旧 W037/R03419 所说“目前的标注者都没有标”是当时描述；不是当前全体语义统计。'),
'wc2JMjhGNzB-26':('bathroom_corridor_target_redefinition','以当前修订 GT 为编辑基底，确认浴室与相连走廊边界；另保留左侧墙面细节。','当前 GT 是 export_label/groudTruth.json，历史原 GT 不同。旧原话 GT 不含走廊、人员可能多标走廊；不得套用“GT 一律裁小”。最新 scope 为目标基本一致，备注指出部分人员不同。'),
'wc2JMjhGNzB-29':('entrance_branch_decision','核对 GT 的门口区域是否纳入，用户明确停止边。','历史“所有标注者都没标”只属于当时原话；最新未确认具体 polygon。与已确认 q9vSo1VnCiC-29 是不同建筑、不同 image_id。'),
}
new=[]
for ix,c0 in enumerate(q['cases']):
 c=copy.deepcopy(c0); im=c['image_id']; old=rows[im]; si,raw=latest[im]
 assert all(raw[k]==c[k] for k in raw)
 assert im not in prior_ids and c['gt_object_id'] not in prior_gt
 assert old['selected_gt_object_id']==c['gt_object_id']
 assert old['user_confirmed_floor_region'] is False
 typ,operation,uncertainty=ops[c['image']]
 comments=[]
 for ci,h in enumerate(inv['comments']):
  if h['image_id']==im and any(s.get('role')=='raw_review_export' for s in h['source_occurrences']):
   comments.append({k:copy.deepcopy(h[k]) for k in ['comment_id','comment','object_kind','object_id','record_id','worker_id','condition','reference_binding_status','source_occurrences']})
 extras=[]
 for name,items in archive.items():
  for i,a in enumerate(items):
   if a.get('image_id')==im or any(x.get('image_id')==im for x in a.get('associated_images',[])):
    extras.append({'source_path':str(OLD/name),'json_pointer':f'/{i}','record':a})
 card=(NEW/c['card']).resolve(); assert card.is_file()
 c.update({
  'image_code':c['image'], 'reference_object_id':c['gt_object_id'],
  'source_commit':COMMIT,
  'latest_user_review':raw,
  'latest_user_review_source':{'path':str(REL/'source_review.json'),'json_pointer':f'/records/{si}','review_version':src['review_version'],'exported_at':src['exported_at']},
  'queue_source':{'path':str(REL/'scope_queue.json'),'json_pointer':f'/cases/{ix}'},
  'requested_operation_type':typ,'requested_operation_zh':operation,'operation_is_adjudication_prompt_not_user_confirmed_geometry':True,
  'uncertainty_and_conflict_zh':uncertainty,
  'existing_workbench_inventory_match':True,'existing_broad_review_queue':old['broad_review_queue'],
  'overlap_with_prior_confirmed_five':False,
  'initial_review_state':{'decision':'pending','completed':False,'floor_region_confirmed':False,'confirmed_version':None,'received_confirmed_version':None,'selected_target':None,'operations':[],'top_boundary_pending':True,'reference_ready':False,'GT_modified':False},
  'current_selected_gt_object_id':old['selected_gt_object_id'],'historical_original_gt_object_id':old['original_gt_object_id'],
  'historical_reference_version_pending':old['historical_reference_version_pending'],
  'hold_layers_in_frozen_inventory':json.loads(old['hold_layers']) if isinstance(old['hold_layers'],str) else old['hold_layers'],
  'hold_corpus_is_exhaustive_current_policy':False,
  'historical_image_comment_summary':old['image_comment'],
  'historical_original_comments':comments,'additional_historical_context':extras,
  'review_card_path':str(card),
 })
 if c['historical_reference_version_pending']:
  c['restored_historical_reference']=next(x for x in restored if x['image_id']==im)
 new.append(c)
prior_summary=[]
for r in previous['records']:
 old=rows[r['image_id']]
 prior_summary.append({**{k:r[k] for k in ['image_code','image_id','reference_object_id','floor_region_confirmed','completed','top_boundary_pending','reference_ready']},'confirmed_at':r['confirmed_version']['confirmed_at'],'confirmation_source':r['confirmed_version']['source'],'action':'preserve_confirmation_and_geometry_do_not_requeue','hold_layers':json.loads(old['hold_layers']) if isinstance(old['hold_layers'],str) else old['hold_layers']})
fire=next(r for r in src['records'] if r['image']=='yqstnuAEVhm-07')
file_sources=[NEW/'scope_queue.json',NEW/'source_review.json',NEW/'REPORT.md',NEW/'scope_review.html',ROOT/'manual_scope_review_received_20261010_batch2.json',OLD/'cloud_inventory/inventory.json.gz',OLD/'cloud_inventory/policy_hold_evidence.json',OLD/'archive_reconciliation/restored_historical_reference_coordinates.json']+[OLD/name for name in archive_names]
result={
 'schema':'scope_workbench_incremental_queue_v1','batch_id':'user_scope_review_11_20261010','source_commit':COMMIT,
 'purpose':'将最新11图设为现有裁剪/重定义工作台的独立待裁定队列，保留已有5份底面确认。',
 'counts':{'new_scope_queue':11,'explicit_scope_different':8,'note_only_or_local_boundary':3,'prior_confirmed_floor_regions':5,'overlap_by_image_id':0,'overlap_by_gt_object_id':0,'separate_reference_or_oos_holds':2,'excluded_fireplace':1,'machine_area_screen_triggered':3},
 'cases':new,'prior_confirmed_preserve':prior_summary,
 'separate_reference_or_oos_holds':[dict(r,queue_action='keep_separate_not_in_new_scope_queue',reference_ready=False) for r in q['separate_reference_or_oos_holds']],
 'excluded_by_user':[{'image_code':fire['image'],'image_id':fire['image_id'],'gt_object_id':fire['gt_object_id'],'reason':q['excluded_by_user'][0]['reason'],'historical_user_review':fire,'latest_applicable_instruction_source':str(REL/'REPORT.md'),'scope_action':'do_not_reintroduce_fireplace_scope','order_review_is_separate':True}],
 'invariants':['不得改写已有5份确认 polygon 或要求重复完成。','不得把本轮加入队列等同于用户已确认具体裁剪区域。','原GT、原作答、人员资格、质量hold和难度正式分层不因本队列改变。','所有底面范围确认不等同顶界或完整3D参考获准，reference_ready保持false。','当前选定GT与历史GT必须区分；历史评论不替代最新目标裁定。','没有把全部11图描述成机器独立自动发现；面积筛查只触发3图。'],
 'source_files':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in file_sources],
 'known_hold_layers_all':[{k:r[k] for k in ['image_code','image_id','hold_layers']} for r in inv['images'] if r['reference_paused']],
 'limitations':['原图卡存在性与身份绑定已检查；本任务未做新一轮视觉范围裁定。','旧 hold 记录为分层证据，并非最新全3152份正式资格的重新穷举。','本目录仅为输入队列和核对报告，没有修改工作台或仓库，也未发布。'],
}
(OUT/'input_queue.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# 新增范围队列核对（2026-10-10）','',f'依据仓库提交 `{COMMIT}` 的最新用户26图回执及11图范围队列，逐一对照先前全图库存与5份底面确认。','',
'## 结论','',
'- 11图均已存在于原259图库存及宽复核队列。本次应新增“最新11图待裁定”筛选入口，不重复造图。',
'- 与此前5份按完整 image_id、GT object_id 均无重叠；旧确认原样保留。',
'- 8图明确选“范围明显不同”；S9-04、pa4-14、wc2-26由备注补充局部/部分人员范围问题。全部尚未确认本轮 polygon。',
'- 11图中仅 pa4-14、q9-12、wc2-26 触发已有0.30面积筛查，不能称11图由机器独立筛出。',
'- 本次只准备输入材料，未改工作台、仓库、GT、作答或正式分类，也未发布。','',
'## 逐图：最新原话与待做操作','']
for i,c in enumerate(new,1):
 lines += [f"### {i}. {c['image_code']}",f"- ID：`{c['image_id']}`",f"- 最新选择：{c['scope']}；难度意见：{c['grade']}；时间：{c['updated_at']}",f"- 原话：{c['note']}",f"- 待操作：{c['requested_operation_zh']}",f"- 限制：{c['uncertainty_and_conflict_zh']}",'']
lines += ['## 旧5份保留','',', '.join(r['image_code'] for r in prior_summary),'','以上5份仅底面已确认，top_boundary_pending=true、reference_ready=false；不得因这次入队重置。q9vSo1VnCiC-29 的既有 hold_scene_or_reference 质量暂停仍保留。','','## 排除与单列','',
'- yqstnuAEVhm-07：按随后用户指示接受GT，壁炉细节不进本轮范围队列。其三份点序确认是独立事项，最新 REPORT 开头已说明写回；后文“未写回/待确认”是发放时历史状态。',
'- jtcxE69GiFV-05：原话“这gt是错误的”，scope=GT需核查。独立GT核查，不擅自改称范围差异。',
'- jtcxE69GiFV-10：原话“有可能算作oos”，scope=不能确定。独立OOS待核，不擅自裁剪。',
'- 11图在此次对照的历史/用户/已观察正式hold层中均未命中；这不是全库现行资格已重算的证明。',
'','## 不能被旧材料覆盖的新证据','',
'- S9-04：最新把GT解释为柜边/门扇边，旧 W011/R00672 原话把GT解释为柜后墙角。保留双方原文，待图上明确内外方向。旧“尚不能确定/最终确定歧义”也不替代这次具体选边。',
'- wc2-26：当前选定GT来自 export_label/groudTruth.json，与历史原GT不同。当前应从修订GT编辑，历史原GT只能作对照；“不标走廊”并不代表用户新批次已经确认该polygon。',
'- pa4-14：旧原话偏好GT、强调门外区域，新增回执只指出门洞和遮挡，仍未选择目标。',
'- uNb-68 有旧 W036 与GT类似的反例；uNb-81 旧说“大部分”。wc2-22/-29 旧说“目前/所有未标”也是当时描述，均不能写成最新全体统计。',
'- 历史同房组评论是场景上下文，不能扩成对组内其它图片的新增范围确认。',
'','## 文件','',
'- input_queue.json：11图完整身份、最新原话、操作提示、不确定性、旧原话来源、5份保留状态、单列项和排除项。',
'- validation.json：计数、唯一性、精确绑定、相交检查及源文件哈希。',
'- reconcile_queue.py：可复算本次队列的本地脚本。',
'']
(OUT/'REPORT_zh.md').write_text('\n'.join(lines))
actual=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()
assert actual==COMMIT
assert len(new)==11 and len({r['image_id'] for r in new})==11
assert sum(r['scope']=='范围明显不同' for r in new)==8
assert sum(r['machine_area_screen'] for r in new)==3
assert all(not r['hold_layers_in_frozen_inventory'] for r in new)
assert all(r['initial_review_state']['confirmed_version'] is None for r in new)
assert {r['image_code'] for r in prior_summary}=={'e9zR4mvMWw7-17','e9zR4mvMWw7-09','b8cTxDM8gDG-18','q9vSo1VnCiC-29','pRbA3pwrgk9-02'}
val={'status':'passed','source_commit':actual,'new_count':11,'unique_image_ids':11,'unique_reference_object_ids':len({r['reference_object_id'] for r in new}),'latest_original_review_records_exactly_match':11,'prior_confirmed_count':5,'image_id_overlap':0,'reference_object_id_overlap':0,'new_all_exist_in_prior_inventory':True,'new_all_exist_in_prior_broad_review_queue':True,'new_prior_confirmations':0,'new_all_pending_without_geometry_confirmation':True,'new_historical_gt_versions_differ':['wc2JMjhGNzB-26'],'new_hold_layers_observed':0,'holds_not_exhaustive':True,'excluded_fireplace_not_in_queue':True,'separate_reference_oos_not_in_queue':True,'repository_or_workbench_modified':False,'published':False,'output_files':[{'path':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in [OUT/'input_queue.json',OUT/'REPORT_zh.md']]}
(OUT/'validation.json').write_text(json.dumps(val,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(val,ensure_ascii=False,indent=2))
