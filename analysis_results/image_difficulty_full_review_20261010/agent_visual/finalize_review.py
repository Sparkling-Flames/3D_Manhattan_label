import json
from pathlib import Path
from collections import Counter
p=Path('analysis_results/image_difficulty_full_review_20261010/agent_visual')
rows=json.loads((p/'manifest.json').read_text(encoding='utf-8'))
lines=(p/'observations.txt').read_text(encoding='utf-8-sig').splitlines()
assert len(lines)==259 and len(rows)==259
assert len({r["image_id"] for r in rows})==259
assert sum(r["in_current_178"] for r in rows)==178
seen=set()
for line in lines:
 n,occ,conf,rec,fact,unc=line.split('|');n=int(n);assert n not in seen;seen.add(n);r=rows[n-1];assert r['serial']==n
 if rec=='困难' and conf=='clear' and int(r['H'])>0:occ='substantial'
 elif conf!='clear' and int(r['H'])>0 and occ=='limited':occ='uncertain'
 r.update(reviewed=True,reviewer_type='Codex visual review; not blinded or expert human adjudication',occlusion_level=occ,gt_target_confidence=conf,difficulty_recommendation=rec,visible_evidence=fact,uncertainty_reason=unc,needs_user_review=rec in ['待复核','单列'] or rec!=r['working_difficulty_class'],review_artifacts=[r['review_page']])
 if n in [86,111,88,90,167,173]:r['review_artifacts'].append(f'detail_{n:03d}.jpg')
 assert occ in ['none','limited','substantial','uncertain']
 assert rec in ['简单','中等','困难','单列','待复核']
 assert fact and (rec!='待复核' or unc)
 assert all((p/x).exists() for x in r['review_artifacts'])
assert seen==set(range(1,260)) and sum(r['in_old_137'] for r in rows)==137
assert all(r['N'] in ['4','6'] and r['H']=='0' and r['occlusion_level'] in ['none','limited'] for r in rows if r['difficulty_recommendation']=='简单')
assert all(r['difficulty_recommendation']=='单列' for r in rows if r['assessment_track'] in ['oos','doorway_annotatable','doorway_difficult','oos_and_doorway'])
assert all('\ufffd' not in r['visible_evidence'] and any('\u4e00'<=ch<='\u9fff' for ch in r['visible_evidence']) for r in rows)
(p/'visual_review.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
c=Counter(r['difficulty_recommendation'] for r in rows)
change=[r for r in rows if r['difficulty_recommendation'] in ['简单','中等','困难'] and r['difficulty_recommendation']!=r['working_difficulty_class']]
report=['# 259图逐图视觉难度审查','', '2026-10-10。Codex按用户授权逐张读取65页原照片与GT点位图件，每页最多4张、每张1024×512；另对6张读取2048×1024原图。已覆盖259张已标注图片，保留旧137图与当前178图面板标志；含Manual、Semi、单人和暂停等不同条件，不等于259图均可作同条件共识实验。这不是独立盲法或专家人工判断。未读取人员误差、融合曲线或旧主观标签决定类别；已知GT结构N/H和现有场景标签。','', '**状态：本文件是建议与待核证据，不直接覆盖主分类、GT或已有用户判断。** gt_target_confidence=clear仅表示本次照片/参考未发现目标疑点，不认证GT正确。','', '## 可解释规则','', '- N/H来自固定参考的可复算几何；N为点对数，H为实心墙模型被挡角数。几何H不等于照片真实遮挡，玻璃、柜体、范围变化必须单列核实。','- 可见性V：none=参考关键角无明显遮挡；limited=局部下端受挡但上角、角线或相邻边界足够定位；substantial=关键角整处或多个必要上下证据缺失（包括必要结构背向转折），需补足信息；uncertain=参考目标或证据不足。V为有图像依据的定性视觉编码，不是纯自动客观量或像素遮挡率。','- 本轮普通候选简单须N为4或6、H为0、V为none/limited，参考无新疑点。多点且边界清楚通常中等；有适用结构遮挡且必要隐藏转折明确建议困难。四点家具遮挡较重但结构明确者给中等候选，非机械最高难度。','- OOS/门洞既有标签单列，新增范围疑点待复核。多数人与GT不一致不进入难度分。冻结类别后才能独立检验人员/人数响应，不按预期曲线调分类。','', '## 结果','', ' / '.join(f'{k} {v}' for k,v in c.items()),'',f'与现工作三档不同的明确建议{len(change)}张（仍待用户审查）；另有{c["待复核"]}张参考/范围/表示疑点及{c["单列"]}张已有特殊场景。','', '|图片|当前工作类|视觉建议|依据|','|---|---|---|---|']
report += [f'|{r["image"]}|{r["working_difficulty_class"]}|{r["difficulty_recommendation"]}|{r["visible_evidence"]}|' for r in change]
report += ['', '## 待人工复核','', '|图片|照片依据|待核问题|','|---|---|---|']
report += [f'|{r["image"]}|{r["visible_evidence"]}|{r["uncertainty_reason"]}|' for r in rows if r['difficulty_recommendation'] in ['待复核','单列']]
report += ['', '## 字段约定', '', '- serial为本轮阅读序号，原178顺序保持，179起补81张；image_id为唯一匹配键。in_old_137和in_current_178是面板成员布尔标志。', '- N/H及现有场景字段原样绑定输入；image_path为原照片路径，review_page/review_artifacts为实际读过的审图件。', '- occlusion_level取none/limited/substantial/uncertain；gt_target_confidence取clear/questionable/uncertain；difficulty_recommendation取简单/中等/困难/单列/待复核。', '- visible_evidence描述照片事实；uncertainty_reason记录需要核实的推断或参考问题。reviewed为本轮已看图，reviewer_type明确Codex视觉判断。needs_user_review包括单列、待复核及与工作分类不同者，不能解释成GT已错误。', '', '## 验证与边界','', 'visual_review.json为逐图记录，manifest.json为输入绑定，observations.txt保留逐页原始简记；JSON中必要结构隐藏角统一编码substantial，目标未定的H>0图不以局部家具遮挡推定整体V。build_pages.py只生成审图页，不修改源资料。覆盖、唯一ID、图片存在、GT点数、旧137/当前178标志、中文编码、分类枚举、简单条件及特殊单列断言通过。图件为分析证据，不是屏幕截图。未独立重建GT或验证每条隐藏墙；本结果不能宣称客观难度已获效度验证。']
(p/'REPORT.md').write_text('\n'.join(report),encoding='utf-8')
print(dict(c));print('changes',len(change));print('all covered',len(rows))
