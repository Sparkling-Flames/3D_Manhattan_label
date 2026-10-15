#!/usr/bin/env python3
"""Build Chinese report, CSVs and manifest from validated machine results; stdlib only."""
import csv,json,hashlib,platform,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
load=lambda name:json.loads((P/name).read_text())
v=load('validation_report.json');ind=load('independent_audit.json');neg=load('negative_tests.json');o=load('normalized_confirmation_overlay.json');a=load('inputs/raw_scope_receipt.json')
assert v['result']==ind['result']==neg['result']=='PASS'
s=v['summary'];by={r['image_code']:r for r in v['rows']}
def csvout(name,rows,fields=None):
    if fields is None:fields=list(dict.fromkeys(k for row in rows for k in row))
    with (P/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in rows:w.writerow({k:json.dumps(row.get(k),ensure_ascii=False,separators=(',',':')) if isinstance(row.get(k),(dict,list)) else row.get(k) for k in fields})
def flattened(r):
    q={k:v for k,v in r.items() if k!='geometry_delta'};d=r['geometry_delta']
    q.update({'baseline_vertices':d['baseline']['vertices'],'current_vertices':d['current']['vertices'],'baseline_area_h2':d['baseline']['area_h2'],'current_area_h2':d['current']['area_h2'],'area_delta_h2':d['area_delta_h2'],'area_relative_change':d['area_relative_change'],'same_as_baseline_within_1e8':d['ordered_coordinates_equal_within_1e8']});return q
csvout('all_261_audit.csv',[flattened(r)for r in v['rows']])
csvout('all_261_regions.csv',[flattened(r)for r in v['region_rows']])
csvout('confirmed_35_geometry_deltas.csv',[flattened(r)for r in v['region_rows'] if r['included_in_overlay']])
csvout('priority_19_completion.csv',[flattened(r)for r in v['queue_coverage']['priority_19']])
csvout('assigned_23_completion.csv',[flattened(r)for r in v['queue_coverage']['assigned_room_batch_23']])
csvout('prior_16_exact_comparison.csv',v['prior_16_comparison'])
csvout('operation_replay_32_steps.csv',v['operation_replay_steps'])
csvout('confirmation_56_snapshots.csv',v['confirmation_snapshots'])
csvout('snap_61_measurements.csv',v['snap_metadata'])
(P/'summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
origin={'new_explicit_confirmation':'本次新增按钮确认','inherited_prior_confirmation':'保留上轮确认'}
decision={'allow':'修改范围','full_gt':'完整编辑GT'}
new=v['queue_coverage']['priority_19'];old=v['prior_16_comparison'];exp=[r for r in new if r['geometry_delta']['area_delta_h2']>1e-8];shr=[r for r in new if r['geometry_delta']['area_delta_h2']< -1e-8]
lines=['# 最终空间范围审核回执核验与统计（2026-10-10）','','## 结论','',
'双重核验通过。261 条导出记录中，明确确认 35 张：上轮 16 张完整继承，本次默认待复核队列新增 19 张全部收齐。其余 226 张仍是未确认的默认草稿，不能把整个导出文件当成 261 张已审核。','',
'- 35 张：28 张采用修改范围，7 张接受完整编辑基准 GT 底面。','- 新增 19 张：15 张修改范围，4 张按钮确认完整编辑 GT；19 张全部是实际按钮确认。','- 23 张同房间分配批次：23/23 完成，包含 19 张新确认和 4 张旧确认。','- “无任何切割/操作则继续使用原 GT”政策本次自动确认 0 张，applied_image_codes=[]；7 张无操作全 GT 都已有按钮确认，不能重记为政策补确认。','- 修改后未确认 0、明确待定 0、新增替代空间候选 0。261 张均只导出 primary。','- 35 张中 33 张在原 259 图研究基集，另 2 张 q9vSo1VnCiC-21、q9vSo1VnCiC-25 为基集外补回视角；这 2 张没有研究标注，不扩大正式研究分母。','',
'## 本次19张的实际结果','','| 图号 | 结论 | 操作 | 原/现顶点 | 面积变化 h² | 研究基集 |','|---|---|---|---:|---:|---|']
for r in new:
    d=r['geometry_delta'];change=0 if abs(d['area_delta_h2'])<1e-8 else d['area_delta_h2']
    lines.append(f"| {r['image_code']} | {decision[r['decision']]} | {', '.join(r['operation_types']) or '无'} | {d['baseline']['vertices']} / {d['current']['vertices']} | {change:.9g} | {'是' if r['in_current_corpus'] else '否，补回视角'} |")
lines+=['',f'新增19张中，6张净扩展、9张净缩减、4张不变（几何容差1e-8）。扩展图为：{"、".join(r["image_code"] for r in exp)}。保留用户原坐标，不再裁回 GT、不改成凸包。面积变化不是质量分，也不说明扩展区域语义正确与否。','',
'## 上轮16张对比','',
'16/16 的 polygon、operations、decision、confirmed_version 和 confirmed_at 均与上轮规范化确认逐项精确一致，没有重新覆盖、重算坐标或补造确认时间。本轮确认总数 = 旧16 + 新19，不把继承确认计为19张新增的一部分。','',
'旧16中的5张仍保留 user_chat 来源及原消息绑定；另11张保留原按钮确认。35张总来源为30张 workbench_button、5张 user_chat。原始回执(2)中5张“忘点确认”的状态仍保留在冻结旧原件；本次与正式接回后的规范化16图快照对比。','',
'## 来源、版本与时间','',
f'- 最新原始文件：空间范围人工审核_2026-10-10(3).json；导出时间 {a["exported_at"]}。',
f'- 最新原件 SHA256：{o["source"]["receipt_sha256"]}。',
'- 交回消息：Sentinel_2646209598188191b7822706987eac95，2026-10-10 13:17 UTC（收到的是分钟精度）：“完成了,统计好这些数据后,一并上传到github main”。这条交回指令不扩展为对226张无关草稿的批准。',
f'- 编辑参考提交：{a["source_commit"]}；范围意见提交：{a["latest_scope_review_source_commit"]}。',
'- 一般历史图证来源提交为 d905d7dbb31dccabb3b190cb317d38b034b7cd65；补回的q9-21/25按各自记录绑定24360ad8544d76d8aba18a8e641f784a76ca0d42。不能用单一顶层图证提交覆盖逐图来源。',
'- 冻结输入包括工作台 data.json、geometry.js、review-state.js、app.js、最新/旧原始回执、旧规范化16图，以及两张补回视角的惰性加载记录。所有原件只复制，不修改。','',
'## 已实际执行的核验','',
f'1. 官方工作台Node重放：PASS，{s["numerical_checks"]:,}项数值/来源/状态断言。检查261条身份、编辑GT和历史GT来源、确认历史、每个候选的GT/提交绑定、所有当前操作、相机严格包含、根记录与活动空间别名一致。',
f'2. 共核验{s["current_and_historical_confirmation_snapshots_checked"]}份当前/接回/历史确认快照；32个当前唯一操作步骤全部有效：rectangle 15、edge_move 13、cut 4。',
f'3. 独立Python标准库复核：PASS，{ind["checks"]:,}项检查，{ind["audited_polygons_including_intermediate_and_historical"]}个含中间步骤/历史版本的多边形，{ind["independently_replayed_operation_instances"]}次含重复快照的操作回放。另查JSON重复键、非有限数、独立ERP投影、线交点、裁切、绕数法相机包含和规范化坐标保真。',
f'4. 10项反例测试全部被拒绝：改单个多边形别名、错图绑定、错GT版本、错提交、重复候选ID、越界边索引、全GT却带操作、越权提升正式资格，以及与坐标不符的edge_follow储存线。',
f'5. 跨运行时投影尾差：Node最大{s["baseline_projection_max_abs_error"]:.17g}，独立Python最大{ind["max_projection_abs_error"]:.17g}；独立操作重放最大{ind["max_replay_abs_error"]:.17g}。均远小于1e-8；输出保留接收坐标，不用计算尾差覆盖。','',
'六张扩展图发生一个相邻端点折叠，按现有geometry.js规则由14→13或10→9个顶点；独立回放确认是同一操作的局部端点合并，不是后处理修补。','',
'## 吸附、edge_follow与多空间','',
'- 本回执有61条吸附元数据：55条有限边、5条GT顶点、1条支撑线延长匹配（uNb9QFRL6hY-18）。snap_61_measurements.csv按匹配类别分别记录最终距离；distance_px是吸附前视口距离，不能当最终误差。',
'- 边索引绑定各步操作前的多边形；端点折叠后的边编号不能错误套回原索引。延长线匹配不宣称有限段重叠。',
'- 工作台支持edge_follow储存线重放，校验器保留支持；本回执实际edge_follow=0、gt_follow=0，不虚构精确沿GT操作。',
'- space_regions存在于所有记录，但均仅primary；没有新建替代空间。通用规范化键为(image_code, region_id)。不得把一个空间的确认传播给另一个，也不得按最高GT分数选择空间。','',
'## 补回视角与不能推导的结论','',
'q9vSo1VnCiC-21/25 的 editing_reference_version=recovered_original_equivalent_snapshot。回执 historical_original_GT_points_1024x512 与工作台惰性加载详情精确一致，来自可追溯原始等价快照；原 label_cor 文本字节并未取得。不能因为字段含“original”就宣称重新取得原始TXT。两张均in_current_corpus=false，不新增研究标注或正式研究资格。','',
'本报告只核验来源一致性、状态依据与可复算底面几何，不替代原图语义复审。所有输出仍top_boundary_pending=true、reference_ready=false、formal_eligibility_changed=false；顶界、完整3D参考和正式评分资格未由此验收。未修改GT、旧包或Site，本核验目录没有执行GitHub上传。','',
'## 交付文件与复算','',
'- normalized_confirmation_overlay.json：35条确认底面，兼容v1核心字段并明确region_id、确认来源和研究基集归属；字段约定见SCHEMA.md。','- validation_report.json / independent_audit.json / negative_tests.json：机器校验与逐项结果。','- all_261_audit.csv / all_261_regions.csv：所有图片和候选状态。','- confirmed_35_geometry_deltas.csv：35图几何变化；priority_19_completion.csv、assigned_23_completion.csv记录队列收齐情况。','- prior_16_exact_comparison.csv：旧16逐项精确对比。','- operation_replay_32_steps.csv / confirmation_56_snapshots.csv / snap_61_measurements.csv：步骤、确认历史与吸附测量。','- unconfirmed_226_image_codes.json：未确认名单；inputs/保存可复算冻结输入。','',
'依赖仅Node.js（建议18+）和Python 3标准库。无需网络、浏览器、npm/pip包或工作台原目录。在本目录执行：','',
'```sh','node validate_receipt.js','python independent_audit.py','node negative_tests.js','python build_reports.py','```','',
'数据在该目录内可独立复算；manifest.json记录全部交付文件哈希。']
(P/'REPORT.md').write_text('\n'.join(lines)+'\n')
schema='''# normalized_confirmation_overlay.json字段约定

- schema=manual_floor_scope_confirmation_overlay_v1；extension_schema=region_identity_and_confirmation_origin_v1。
- records每条是一个独立确认的底面候选，唯一键(image_code, region_id)。本次35条、35图、全部primary。未确认草稿不进入records。
- region_id、region_name、is_primary、is_active保留空间身份。主空间和替代空间不能合并确认，不允许按GT最高分自动选择。
- polygon与cropped_floor_xz_h：相机高度归一化xz底面，按回执原数值/原顺序保留，不旋转起点、不排序、不裁回GT。
- operations、cuts、decision、note、axis_angle、completed、updated_at沿用实际确认快照；confirmed_review完整保存原确认快照。
- source、confirmed_at、confirmation_message_id、source_sha256为确认自身的历史来源，不能用最新交回时间覆盖。最新回执hash位于provenance.receipt_sha256。
- confirmation_origin为inherited_prior_confirmation（16）或new_explicit_confirmation（19）；预留policy_no_operation_confirmation，本次0。
- 编辑GT绑定：editing_reference_version / editing_reference_object_id / editing_reference_points_1024x512。reference_object_id为兼容字段。
- historical_original_GT_*仅保存收到的历史来源字段；两张recovered_original_equivalent_snapshot并非取得原TXT字节，详情见reference_provenance。
- provenance包含最新回执文件名、SHA256、导出时刻、JSON pointer、editor版本、逐图证据来源提交、原空间source_binding。
- in_current_corpus=true共33条；false共2条（q9vSo1VnCiC-21、q9vSo1VnCiC-25），后者recovered_reference_view=true且没有研究标注，不扩大259图研究基集。
- previous_confirmation_history保存工作台收到的旧历史及上一接回快照。protected_site_metadata保存资格/暂停等元数据，不能由底面确认推导解禁。
- GT_modified=false、formal_eligibility_changed=false、reference_ready=false、top_boundary_pending=true始终保留；只允许独立底面指标接入，不当完整3D参考。

消费建议：先确认validation_report.json和independent_audit.json均PASS，按image_code+region_id读取polygon，按各记录in_current_corpus筛选正式研究语料，并与对应编辑GT和正式标注身份绑定。不要把顶层evidence_source_commit覆盖逐图provenance.evidence_source_commit。
'''
(P/'SCHEMA.md').write_text(schema)
manifest={'schema':'final_scope_receipt_validation_manifest_v1','created_from_export_at':a['exported_at'],'validation_result':'PASS','input_original_filename':'空间范围人工审核_2026-10-10(3).json','input_copy':'inputs/raw_scope_receipt.json','input_sha256':o['source']['receipt_sha256'],'reproduction':['node validate_receipt.js','python independent_audit.py','node negative_tests.js','python build_reports.py'],'dependencies':{'node':subprocess.check_output(['node','--version'],text=True).strip(),'python':platform.python_version(),'third_party_packages':[]},'files':{str(p.relative_to(P)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(P.rglob('*')) if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts}}
(P/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'result':'PASS','report':'REPORT.md','manifest_files':len(manifest['files']),'summary':s},ensure_ascii=False,indent=2))
