"""Integrate completed findings into the actual latest personnel main report."""
import difflib,hashlib,json,re
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
REL='../../research/workers/personnel_exchange_discrimination_20261025'
TARGET='docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md'
SRC=ROOT/'report_integration/sources'/TARGET
source=SRC.read_text()
draft=(ROOT/'report_integration/MAIN_REPORT_INSERTIONS_ZH.md').read_text()

size_text=f'''固定成员实验现已完成，而不是把不同n的独立抽样当成人数路径：286条固定X7/Y7/Z7路径、3,264个严格ABC事件，n逐人覆盖10…N−14，实际至21；每步同一人加入三队的D，m恒为7。固定n21容量队列有DSTRUCT 58图20楼、scope联合39图15楼，保持同一批路径，不以失败后更换队列。

|固定n21容量队列，全部阶段|n/m|Q同类／跨类幅度|跨类幅度较大图／楼|C−A／C−B|
|---|---|---|---|---|
|DSTRUCT_K3|10/7|4.869／7.271|39/57；14/20|+7.922／+7.468|
|DSTRUCT_K3|20/7|3.192／5.472|42/57；16/20|+4.318／+4.949|
|DSTRUCT_K3|21/7|2.846／5.987|44/57；18/20|+4.377／+4.937|
|scope联合K4|14/7|2.528／6.729|35/39；14/15|+5.888／+5.998|
|scope联合K4|20/7|2.891／3.625|27/39；13/15|+3.637／+3.374|
|scope联合K4|21/7|2.420／4.689|28/39；15/15|+4.527／+4.229|

对应的本轮选型保留建筑中，DSTRUCT n21同／跨为2.897／6.523，19/26图、8/10楼gap正，C−A+5.826、C−B+6.751。规模影响不是单调的，也不是n20后自动没有区别。固定队列从n10到n21，C自身的可评配对均值也下降；完整报告同时提供B/C共同分母的差分解，不把CB优势缩小全部解释成C队改变。见[完整规模结果]({REL}/analysis/size_paths/FINDINGS.md)、[逐规模条件表]({REL}/analysis/size_paths/SCALE_CONDITION_COMPARISON.csv)。

**大团队另按直接AC完成，不伪造B。** 在上述严格路径末端，原Y7逐人进入A/C共同背景，固定X7/Z7；2,288事件、90图22楼，人数到28。固定N35队列，n28/m7时共同D有21人，换去团队25%。DSTRUCT在全部阶段C−A+2.868，51/57图、17/20楼正；本轮选型保留建筑为+4.016，25/26图、9/10楼正，52个登记事件无C失败或相对A下降>10。全部阶段仍有3个明显损失事件，完整保留。scope联合保留楼n28为+5.081、14/14可评图正，但有1/28事件C失败。见[大团队AC结果]({REL}/analysis/large_team_ac_tail/FINDINGS.md)。n28的数值支持定向换类用途，同／跨幅度证据仍来自严格ABC到n21。

严格ABC需要N≥n+2m，因此35人池、m7最多到n21；同图直接AC只要求N≥n+m，才能将同一7人类别块延伸到n28。全员35人唯一集合的零成员波动没有被当作分类有效证据。'''

memo=(ROOT/'analysis/ADOPTED_CONDITIONS_MEMO.md').read_text()
memo=memo.split('## 1. 采用判断',1)[1].split('## 6. 文件入口',1)[0]
memo='##### 采用条件与实际支持\n'+memo
memo=re.sub(r'^## (.+)$',r'##### \1',memo,flags=re.M)
memo=re.sub(r'^### (.+)$',r'###### \1',memo,flags=re.M)
confirmation=f'''#### 4.12.3 楼外扩展、反推与最终方向条件比较

前向重点候选扩展实际完成38,808事件、115图18楼；四个反推方案独立完成探索8,082事件、50图12楼和扩展20,278事件、120图18楼。以下主条件使用本轮初筛未用的建筑，全部类别仍由各目标建筑之外的历史形成。最终具体方向和规模是在完整比较后挑选的，整套v2已经多次使用，称内部楼外检查，不称新外部盲测。

完整候选、未选中方向、近零与反向结果保存在[31实例采用表]({REL}/analysis/METHOD_ADOPTION_DECISIONS.csv)、[全配置与分项]({REL}/analysis/method_adoption/ALL_31_SCREEN_CONFIGURATION_METRICS.csv)和各阶段全方向表。下面所有值可在[有效条件表]({REL}/analysis/FINAL_CONDITIONS_COMPACT.csv)、[逐图结果]({REL}/analysis/FINAL_CONDITIONS_POOL_SUMMARIES.csv.gz)、[全部分项]({REL}/analysis/FINAL_CONDITIONS_ALL_COMPONENTS.csv.gz)定位。

{memo}

![保留建筑中四个采用条件的全部可评图片；反向点保留]({REL}/analysis/figures/CONFIRM_Q_SEPARATION.png)

图中点是图片层级，不是独立事件。横轴同类Q幅度、纵轴对称跨类Q幅度，虚线表示两者相等；难度颜色、全体点和分母均保留。

'''

draft=draft.replace('`{{CONFIRM_SIZE_BACKGROUND_FINDING}}`',size_text)
draft=re.sub(r'#### 4\.12\.3 独立于本轮选型的确认与反推结果.*?(?=#### 4\.12\.4)',confirmation,draft,flags=re.S)
draft=draft.replace('#### 4.12.4 四个完整机制案例','#### 4.12.4 六个完整机制案例：定位、补票、重新对应与反转')
case_extra=f'''

另有两例来自本轮扩展，阶段身份独立于上面四个screen案例：

- **反推小类的集体补票：B6ByNegPMKs-47，RFUSE_GEOM_K2，n12/m4。** 对应楼外Z为W109/W112/W126/W130；A/B/C为7/8/10节点。R4在A/B为4票，C由D的2票加Z的4票达到6票门槛；R9由B的5票变为C的7票。C−B Q+5.938，底面IoU+11.245个百分点、三维代理+10.836。R7附近共同D中的W124/W131还发生重新对应，因此既有局部补票，也有位置和分组变化。所选图两种背景均Q gap正；另一背景形状gap为负，也在选例账保留。见[反推机制]({REL}/cases_reverse/README.md)。
- **固定块人数反转：jh4fc5c5qoQ-12，DSTRUCT_K3，n14→15、m7固定。** W117同时进入三队共同D。C从8节点变6节点，Q96.596→45.462，底面IoU98.146%→86.345%，三维代理97.371→85.807。R4票数和位置都不变，7票因门槛升到8而失选；R6原8票中的W115被新W117带入2票新组，原组剩7票后也失选。A仅+0.078、B−0.918。该例gap反而由1.489增至20.705，清楚说明区分度增加不自动是换类收益。C在后续人数又可恢复，不要求人数曲线单调。见[人数/对应/门槛机制]({REL}/cases_size_threshold/CASE_NOTE_ZH.md)。

![固定类别块时，一个背景成员引发的门槛与重新对应反转]({REL}/cases_size_threshold/SIZE_THRESHOLD_MECHANISM_ZH.png)

这些案例重放端点与已存Q/D10/底面/三维值一致。被遮挡的背面转折按冻结参考和已有机会说明，不冒充原图可直接看清的新人工裁定；没有为解释案例改变GT或融合参数。
'''
draft=draft.replace('## 插入 C：',case_extra+'\n\n## 插入 C：',1)
draft=draft.replace('{{CONFIRM_REVERSE_DELIVERY_COUNTS}}','前向扩展38,808事件；反推探索/扩展8,082/20,278事件；7选6为2,002事件；固定块规模3,264严格ABC及2,288直接AC，全部登记结果实际取得')
draft=draft.replace('按真实完成文件填入，不能以登记数代替已算数','全部已完成，探索/同楼新增/选型保留楼和设计身份分开')
draft=draft.replace('|原图机制|4例、12个正式ABC端点、实际原答和完整票账|','|原图机制|6例，实际原答、正式端点、原图及完整票账；新增反推和人数反转例|')
draft=draft.replace('`{{FINAL_RESULT_INDEX}}`',f'[统一文件与下载索引]({REL}/DOWNLOAD_INDEX.md)。全轮97,552事件，其中95,264严格ABC、2,288直接AC；170图22楼、31个方法/层级实例。必要端点去重后283,211，其中283,092本轮新计算、119旧缓存直接复用；279,013正式可评，4,198保留不可评/失败原因。相同终点不因事件重复而重复计算。反推训练另复用24,237个历史端点，并非新融合')
decision=f'''**采用四个有具体方向和规模的工作分类用途：** DSTRUCT_K3以n18/m7为主条件，并保留固定块n10—21与n28/m7直接AC；RFUSE_GEOM_K2保留4人小类在n12/m4的整块用途；RFUSE_GEOMQ_K3保留n20/m6向响应核心的方向，优先解释困难时较少转折/上下界收拢的非核心源分支；MSDGEOM_SCOPE_K4保留n20/m6向较高历史Q、较慢、较多转折角色的质量和定位用途。小类按实际容量选图，不以人数不均衡为取消条件。

原M、A2、QTD、SP、F01、Rnew2、旧结构和联合分类按历史身份保留；旧结构在合适大块条件也有区别，Q二分是有力透明基线。DBOUNDARY在Q差较弱时仍有上下界/质心距离用途，作为几何补充。更多变量或更多细类没有被预设为更优：反推K3的大分支之间多为弱差异，而特定小核心方向有价值；旧联合粗/细在本轮22/22折实际分区相同，不能把不同抽样的均值差叫细分增量。详见[采用/保留/探索判断]({REL}/analysis/METHOD_ADOPTION_NOTES.md)。

本轮主问题可以收尾：已经取得可解释的人员类别、同D/n/m的大块差异、实际成员/背景重复性，以及结构/定位/投票/对应机制。新结论集中于普通Manual；Semi终稿与scope用于部分建类，既有Semi效果保留，本轮没有补跑新的Semi替换。大空间成员集合和全部进入顺序没有穷尽；已登记有限面板、7选6小空间及每条固定路径的全部人数均已完成。没有把未完成全空间作为阻止采用具体规律的前置条件。'''
draft=draft.replace('`{{FINAL_CLASS_AND_CONDITION_DECISION}}`',decision)
draft=draft.replace('{{RESEARCH_REL}}',REL)
raw=f'''\n\n独立的原答检查也支持该结构分类：普通Manual困难图上，DSTRUCT_K2同类/跨类非冗余转折数差为1.569/3.050，31/31图、15/15楼跨类更大；固定原答角点数量后，顶界角距离仍为2.243°/3.303°（24/28图），底界2.648°/3.449°（24/28图）。这解释了为何一类“困难时更保留转折”的人员在四角简单图仍可能产生定位差异。它是独立标法证据，正式融合用途由4.12节实际替换给出。原答历史含111条特殊范围辅助记录，主换类效应始终排除这些图；具体支持与普通/特殊原答分层见[分类说明]({REL}/classifications/README.md)。\n\n'''
draft=draft.replace('**反推路线另形成4个候选。**',raw+'**反推路线另形成4个候选。**',1)
assert '{{' not in draft.split('## 插入 A：',1)[1]

sections={}
for letter in 'ABCDE':
    match=re.search(r'^## 插入 '+letter+r'[^\n]*\n(.*?)(?=^## 插入 [A-E]|\Z)',draft,re.M|re.S)
    sections[letter]=match.group(1).strip()+'\n\n'
plan=json.loads((ROOT/'report_integration/PREPARED_PATCH_PLAN.json').read_text())
updated=source
for insertion in plan['insertions']:
    txt=sections[insertion['draft_section']]
    if insertion.get('at')=='end_of_file':updated=updated.rstrip()+'\n\n'+txt
    else:
        anchor=insertion['before_exact_heading'];assert updated.count(anchor)==1
        updated=updated.replace(anchor,txt+anchor,1)
header='''> **2026-10-25人员同图大块换类续研更新。** 本轮已完成31个方法/层级实例的有限候选比较、95,264个严格ABC与2,288个直接AC事件，采用四个具体方向/规模用途；新增结构类、实际融合响应反推类及Manual＋Semi＋scope联合类均有真实成员和多数图片/建筑支持。新增内容见1.5、4.12、5.1、7.1、8.1，原阶段成果和来源保留。底层仍是真人v2。计算读取972857b2，文档整合读取e88d1d4；GitHub确认e88d1d4包含ef148c82d。这里只交付本地主报告更新稿和补丁，未公开推送仓库。\n\n'''
lines=updated.splitlines(keepends=True);updated=lines[0]+'\n'+header+''.join(lines[1:])
dest=ROOT/'repo_integration'/TARGET;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(updated)
standalone=ROOT/'final/人员分类与构成不确定性_主报告_更新至20261025.md';standalone.write_text(updated)
chapter=ROOT/'final/20261025_新增分类与有效换类章节.md';chapter.write_text('# 20261025新增分类与有效换类章节\n\n以下为现有人员主报告的本轮新增章节，原报告及阶段身份保留。\n\n'+''.join(sections.values()))
patch=''.join(difflib.unified_diff(source.splitlines(keepends=True),updated.splitlines(keepends=True),fromfile='a/'+TARGET,tofile='b/'+TARGET))
(ROOT/'repo_integration/personnel_main_update.patch').write_text(patch)
(ROOT/'report_integration/MAIN_REPORT_INSERTIONS_COMPLETED_ZH.md').write_text('# 已完成、已接入更新稿的新增章节\n\n'+''.join(sections.values()))
receipt={'status':'completed_local_updated_report_and_patch','base_commit':plan['base_commit'],'target':TARGET,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'updated_sha256':hashlib.sha256(updated.encode()).hexdigest(),'standalone_report':str(standalone.relative_to(ROOT)),'all_insertions_completed':True,'unfilled_placeholders':0,'git_push_performed':False}
(ROOT/'report_integration/INTEGRATION_COMPLETE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))

# Human-readable adoption table; the complete 71-row multi-component table stays intact.
data=pd.read_csv(ROOT/'analysis/FINAL_CONDITIONS_COMPACT.csv')
choices=[('DSTRUCT_K3',18,7,'largest_to_highest_turn','常规/最大类','困难时较多非冗余转折类','结构与定位；主条件'),('RFUSE_GEOM_K2',12,4,'into_smallest_class','其余融合几何响应类','4人几何响应小类','小类整块；结构/定位'),('RFUSE_GEOMQ_K3',20,6,'into_smallest_class','非核心融合响应类，优先较高Q响应/困难较少转折分支','当地6名几何＋质量响应核心','较大团队；细分方向用途'),('MSDGEOM_SCOPE_K4',20,6,'higher_Q|slower|more_turns','该折相对较低Q/较快/较少转折源类','相对较高历史Q、较慢、困难转折更多类','跨条件+scope联合；质量/定位')]
rows=[]
for method,n,m,role,source_role,target_role,use in choices:
    row=data[(data.phase=='selection_heldout_building')&(data.method==method)&(data.n==n)&(data.m==m)&(data.role==role)]
    assert len(row)==1;(r,)=row.to_dict('records')
    rows.append({'分类':method,'源角色':source_role,'目标角色':target_role,'用途':use,'总人数n':n,'实际换人数m':m,'换人占团队比例':m/n,'同类Q幅度':r['B8L2_within_image_equal'],'跨类Q幅度':r['B8L2_cross_image_equal'],'跨减同':r['B8L2_gap_image_equal'],'跨同均值比':r['B8L2_ratio_of_image_means'],'跨类幅度更大图片':f"{int(r['B8L2_gap_positive_images'])}/{int(r['B8L2_valid_images'])}",'跨类幅度更大建筑':f"{int(r['B8L2_gap_positive_buildings'])}/{int(r['B8L2_valid_buildings'])}",'C减A平均Q':r['B8L2_CA_image_equal'],'C减B平均Q':r['B8L2_CB_image_equal'],'C减B平均D10':r['D10_CB_image_equal'],'C减B平均三维代理':r['IoU3D100_CB_image_equal'],'记录时间C相对B百分比':r['record_time_CB_pct_image_equal'],'时间可评图片':int(r['record_time_CB_pct_valid_images']),'C失败事件':f"{int(r['C_failed_raw_count'])}/{int(r['C_failed_raw_valid_events'])}",'C较B损失超10事件':f"{int(r['C_loss10_CB_raw_count'])}/{int(r['C_loss10_CB_raw_valid_events'])}",'实际XYZ块':int(r['unique_XYZ']),'实际共同背景D':int(r['unique_D']),'D目标类人数范围':f"{int(r['D_target_min'])}—{int(r['D_target_max'])}",'选择身份':'本轮完整条件比较后选择；初筛未用建筑；类别楼外形成；内部v2','完整条件表角色':role})
pd.DataFrame(rows).to_csv(ROOT/'final/有效换类条件_20261025.csv',index=False,encoding='utf-8-sig')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
