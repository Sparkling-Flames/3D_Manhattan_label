#!/usr/bin/env python3
"""Assemble readable receipts; does not run a model or infer visual gold labels."""
from pathlib import Path
import datetime,hashlib,html,json,shutil

HERE=Path(__file__).resolve().parent;WORK=HERE.parent;OUT=WORK/'delivery';QA=HERE/'qa'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb')as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def load(rel):return json.loads((WORK/rel).read_text())
def esc(x):return html.escape(str(x))

# Explicit record of the assistant's actual view_image inspection. Re-running
# this builder republishes that record, not a new visual review.
views={
 'geometry_angle_near_floor_far':(['erp','bev','3d'],'整簇球面投影接近，但靠近地平线的底点投影产生明显长距离BEV分离。未判定真实边界或遮挡金标。'),
 'geometry_floor_near_height_far':(['erp','3d'],'查看原图叠加和3D；相近底面下，顶部及高度分离仍可见。未将角距13.79°误称9°内近邻。'),
 'declared_direction_equivalence':(['erp'],'整簇空间覆盖接近；坐标反向声明问题由保留的环序证据检验，ERP视觉本身不能证明索引方向。'),
 'high_Q_shared_node_count_gap':(['erp','bev'],'检查9°下四名成员整簇及参考：4点对与参考6点对差异可见，成员坐标亦有差异。没有认定四人均高Q，也没有新增共同遗漏金标。'),
 'fusion_within_cluster_large_geometry':(['erp_a','erp_b'],'A/B叠加在左侧区域出现较大的端点和范围变化；同簇替换不保证小变。'),
 'fusion_within_cluster_stable':(['erp_a','erp_b'],'A/B可见几何高度重合；稳定指标与图示相容，不外推全部同簇替换。'),
 'fusion_cross_cluster_large_geometry':(['erp_a','erp_b'],'A/B在中央及右侧结构出现大变化；仅解释这一实际团队对。'),
 'fusion_cross_cluster_small_geometry':(['erp_a','erp_b'],'跨簇替换的A/B轮廓近乎重合，是跨簇也可稳定的实际反例。'),
 'fusion_stable_low_quality':(['erp_a','erp_b'],'A/B轮廓接近，而局部轮廓与参考明显不同；稳定不代替参考质量。'),
 'fusion_within_cluster_failure':(['erp_a','erp_b'],'A有完整输出叠加，B没有可评分完整环；失败状态来自原生记录，未以空白图替代失败原因。'),
 'QD_hard_k16_most_negative':(['erp_a','erp_b'],'Q与QD底面多数区域接近，节点14→13及局部连接变化需与参考分项一同解释；不据此修改难度或选人规则。'),
 'QD_hard_k16_most_positive':(['erp_a','erp_b'],'正例A/B保留5→6节点及局部变化；仅一名成员替换，不能据此证明其困难专长普遍改善融合。'),
}
catalog={c['case_id']:c for c in load('presentation/viewer_cases.json')['cases']}
qa=load('presentation/qa/VIEWER_QA.json');inter={r['id']:r for r in qa['case_interactions']}
assert len(views)==12 and all(c['passed']for c in qa['checks'])
review=[]
for cid,(suffixes,observation)in views.items():
    files=[]
    for suffix in suffixes:
        p=QA/(cid+'_'+suffix+'.png');assert p.is_file()
        files.append({'path':str(p.relative_to(WORK)),'sha256':sha(p)})
    review.append({'case_id':cid,'image_code':catalog[cid]['image_code'],'image_status':inter[cid]['image_status'],'viewed_rendered_files':files,'observation_zh':observation})
visual={'schema':'explicit_assistant_visual_inspection_v2_r1','reviewer':'assistant; no new human expert adjudication',
 'basis':'Actual view_image inspection of native-canvas scientific overlays derived from verified Release originals and frozen annotation/team geometry.',
 'scope':'12 preselected representative/counterexample displays only; not all current originals, annotations, clusters or team outputs.',
 'new_reference_or_difficulty_or_quality_eligibility_changes':False,'new_personal_error_gold':False,'cases':review,
 'browser_layout_verified':False,'visual_selection_was_post_outcome_for_explanation_only':True,
 'inspection_record_republished_by_builder':True}
(QA/'VISUAL_REVIEW_RECEIPT.json').write_text(json.dumps(visual,ensure_ascii=False,indent=2))

g=load('audit/GEOMETRY_REPLAY_CHECKS.json');s=load('audit/INTEGRATED_STATISTICS_REPLAY.json')
p=load('profiles/END_TO_END_REPRODUCTION.json');f=load('fusion/FINAL_RUN_RECEIPT.json');c=load('clusters/FINAL_VALIDATION.json')
assert not g['failures'] and not g['initial_failures'] and s['all_checked_pass']
assert p['matched_tables']==48 and c['status']=='PASS'
rows=[
 ('固定输入','main 82c6164b0d4630de5316199c92aa405930973168；10439个唯一作答。','逐文件散列与来源清单保留。不是从零重建历史采集。','audit/EVIDENCE_AUDIT_CHECKS.json'),
 ('几何逐份重放',f"{g['full']}完整／{g['floor_only']}底面／{g['uncomputable']}不可计算；全部既定检查通过。",'B8/D10/3D最大差小于2.2e−13；参考、点位、删点和环序继承。','audit/GEOMETRY_REPLAY_CHECKS.json'),
 ('旧Semi初始化','519份可评分；500沿用嵌入环，19按明确既有来源环恢复。','保留原数组失败证据；未按GT或得分优化环序。','audit/GEOMETRY_REPLAY_NATIVE_PAYLOAD_CHECKS.json'),
 ('原生统计重放',f"{s['tables_checked']}/{s['expected_tables']}表实际重算，逐值通过。",'其余7表缺原生成步骤所需旧人员CSV/历史源；能读发布表不等于复现采集。','audit/INTEGRATED_STATISTICS_REPLAY.json'),
 ('Q/T/难度独立重放','独立新目录9步骤；48/48数值结果表一致。','代码可迁移修复未改变数值、阈值或人员分类。','profiles/END_TO_END_REPRODUCTION.json'),
 ('分簇计算','229质量池，四种分区；333个非平凡MILP组件gap0。','最优是对已冻结几何目标而言；不等于已验证语义聚类正确。','clusters/ALGORITHM_AUDIT.json'),
 ('真实融合',f"{f['coverage']['request_rows']:,}请求；{f['coverage']['unique_teams']:,}不同成员集合；229池。",'3个实际执行批次的汇总收据，不是后来又运行了一次；没有生成的独立真人标注。','fusion/FINAL_RUN_RECEIPT.json'),
 ('融合失败与空档','162825可评分请求；1624两人政策空档；3132其它不可评分；0原生异常。','不可评分保留在请求和比较分母。可计算完整不等于新人工验收。','fusion/OUTPUT_STATUS_AUDIT.json'),
 ('比较明细完整性','五张全局比较表两次新进程全流CRC、字段数、行数、摘要验证通过。','出现过压缩文件缺尾；恢复及已知/未知原因均另存，不掩盖失败尝试。','fusion/COMPARISON_INTEGRITY_CHECK_2.json'),
 ('反向迁移完整预测','270370事件宽表无损保留6370576模型预测/实际值。','从宽表重算16296个逐图误差，最大差5.55e−17；不是只保存总体均值。','clusters/FINAL_VALIDATION.json'),
 ('离线展示结构与交互',f"{len(qa['checks'])}项检查通过；229池、7302作答、57062真实请求浏览子集。",'Node DOM＋原生canvas验证；不是实际浏览器布局自动化。所有总体统计使用完整结果。','presentation/qa/VIEWER_QA.json'),
 ('有限视觉检查',f"实际查看12个代表/反例的整簇或A/B投影；{sum(len(r['viewed_rendered_files'])for r in review)}张已查看渲染逐个保留散列。",'不是全量原图审核，也未产生新的GT、错误gold或人工验收。','presentation/qa/VISUAL_REVIEW_RECEIPT.json'),
]
# Keep file names grounded, rather than silently publishing broken evidence links.
fallback={'fusion/OUTPUT_STATUS_AUDIT.json':'fusion/FINAL_RUN_RECEIPT.json'}
for i,row in enumerate(rows):
    if not(WORK/row[3]).is_file():
        rel=fallback.get(row[3]);assert rel and(WORK/rel).is_file();rows[i]=(*row[:3],rel)
cells=''.join('<tr><th>'+esc(a)+'</th><td>'+esc(b)+'</td><td>'+esc(d)+'</td><td><a href="../'+rel+'">'+esc(rel)+'</a></td></tr>'for a,b,d,rel in rows)
casecells=''.join('<tr><td>'+esc(r['image_code'])+'</td><td>'+esc(r['observation_zh'])+'</td><td>'+''.join('<a href="../'+x['path']+'">'+esc(Path(x['path']).name)+'</a><br>'for x in r['viewed_rendered_files'])+'</td></tr>'for r in review)
body='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>v2独立研究｜可读运行证据</title><style>body{font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif;background:#edf3f5;color:#203f4b;margin:0}main{max-width:1150px;margin:auto;padding:32px}section{background:white;border:1px solid #dbe7eb;padding:25px;margin:22px 0;border-radius:10px}h1,h2{color:#135269}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #dbe7eb;padding:10px;text-align:left;vertical-align:top}th{background:#eff6f8}a{color:#066f94;overflow-wrap:anywhere}code,pre{background:#edf4f7;white-space:pre-wrap;overflow-wrap:anywhere}pre{padding:16px}.table{overflow:auto}</style><main><h1>v2 人员分类与融合共识：运行证据</h1><p>本页汇总实际完成的计算和复核，不把文件散列验证、缓存复用或已发布表读取称为从零重跑采集。完整方法、采用判断和局限见主报告。</p><section><h2>已经完成的检查</h2><div class="table"><table><thead><tr><th>阶段</th><th>实际结果</th><th>解释范围</th><th>原始收据</th></tr></thead><tbody>'''+cells+'''</tbody></table></div></section><section><h2>可直接运行的入口</h2><p>三个ZIP解压至同一目录。默认只验证文件；显式执行才重放计算。统一编排入口做了语法、依赖计划及完整载荷校验，各模块有各自实际运行收据；没有把这些检查说成统一入口在另一个干净环境中又执行过全部步骤。</p><pre>python work_v2_20261019/REPRODUCE.py --stage verify --full-hash
python work_v2_20261019/REPRODUCE.py --stage all
python work_v2_20261019/REPRODUCE.py --stage all --execute --fresh-fusion --jobs 3</pre><p><a href="README_REPRO_ZH.txt">完整中文复现说明</a> · <a href="coverage_missing_ledger.csv">覆盖与缺失台账</a> · <a href="research_report_v2_zh.html">完整研究报告</a></p></section><section><h2>有限视觉检查的实际范围</h2><p>以下是助手已查看的科学叠加图，全部来自预先保存的案例集合。读者可在离线页切换整簇成员、A/B团队和真实入场顺序。观察未被回写为参考、资格或个人严重错误裁定。</p><div class="table"><table><thead><tr><th>图</th><th>有限观察</th><th>已查看投影</th></tr></thead><tbody>'''+casecells+'''</tbody></table></div></section></main></html>'''
# Remove formatting markers from the source's readable command literal.
body=body.replace('\n+python','\npython').replace('三个ZIP解压至同一目录','四个ZIP解压至同一目录')
OUT.mkdir(exist_ok=True);path=OUT/'run_evidence_v2.html';path.write_text(body)
source=WORK/'profiles/人员画像与候选细类60人.csv';assert source.is_file()
shutil.copyfile(source,OUT/'personnel_profiles_v2_60.csv')
receipt={'readable_evidence':path.name,'sha256':sha(path),'visual_cases':len(review),'actually_viewed_png_count':sum(len(r['viewed_rendered_files'])for r in review),'not_a_new_model_run':True,'source_receipts':[{'path':r[3],'sha256':sha(WORK/r[3])}for r in rows]}
(OUT/'EVIDENCE_PAGE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print(json.dumps(receipt,ensure_ascii=False))

