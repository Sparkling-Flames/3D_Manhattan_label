"""Build additive, SHA-guarded repository documentation overlays from frozen bytes."""
from pathlib import Path
import csv,io,json,hashlib,subprocess,shutil,posixpath

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
BASE=HERE/'base'
OVER=HERE/'overlay'
COMMIT='13a7861334749805a86dc19e9ea79fcaa71020c0'
WORKER='research/workers/personnel_full_chain_v21_20261030'
RELEASE='research/data/releases/v2.1/full_chain_downstream_20261030'
REG='research/data/releases/v2.1/personnel_reselection_dependencies'

def sha(b):return hashlib.sha256(b).hexdigest()
def link(from_file,to_file,label):return '['+label+']('+posixpath.relpath(to_file,posixpath.dirname(from_file))+')'
def added(path,text):
    src=(BASE/path).read_bytes();ending=b'\r\n' if b'\r\n' in src else b'\n'
    # Preserve every original byte. Insert a dated supplement after the first heading.
    at=src.index(b'\n')+1
    block=(text.strip()+'\n\n').replace('\n',ending.decode()).encode('utf-8')
    out=src[:at]+ending+block+src[at:]
    assert out[:at]+out[at+len(ending)+len(block):]==src
    dest=OVER/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(out)
    return dict(path=path,operation='insert_dated_addendum_after_title',base_sha256=sha(src),updated_sha256=sha(out),base_bytes=len(src),updated_bytes=len(out),original_bytes_preserved=True)
def new(path,text):
    out=(text.strip()+'\n').encode();dest=OVER/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(out)
    return dict(path=path,operation='new_entrypoint',base_sha256=None,updated_sha256=sha(out),base_bytes=0,updated_bytes=len(out),original_bytes_preserved=True)

def build():
    files=[]
    p=REG+'/README.md'
    t=f'''## 2026-10-30 全链路实际补齐：本轮验收接续

本节为前次“按v2全链路复核”查缺后的实际执行结果。此前“未找到完整验收”保留当时检查身份；本轮已经定位、计算并验证相应下游，不再以这些历史待办推断当前缺失。统一入口为{link(p,WORKER+'/README.md','人员全链路研究包')}与{link(p,RELEASE+'/README.md','v2.1下游发布说明')}，以冻结提交 `{COMMIT}` 的原答、参考、资格、范围和楼外标签为准。

**最终人员分类尚未由用户确定。** TARGET_DSTRUCT K3/K2是工作分析对象，OPPJOINT用于联合画像，RFUSE用于反向融合响应解释；下方旧“采用/最终”段落保留其历史来源，不作为本次最终选型决定。

|此前待接续环节|本轮已计算、已验证结果|当前边界与入口|
|---|---|---|
|最新14/7全部反例与机制|197事件、83图共同可评；G_A正61/83、G_S正62/83。非正分别22和21图，质量方向/不可评另列，联合诊断36图；已接原答、几何、轨迹与局部票账，并连接20/7实际背景|{link(p,WORKER+'/stage01_half_team/README.md','半队结果')}；不沿用旧focused-only 22张对称非正名单；半队人数不等于每个局部有半数票|
|旧ABC在当前标签下的双视角实际效果|已从8,904个TARGET K3合法旧D/X/Y/Z双视角事件连接实际端点，每事件含两图×A/B/C，非视角数；按楼外角色、n/m、空间和指标支持计算效应|{link(p,WORKER+'/stage02_same_room/README.md','同房完整接续')}；固定旧团队的条件子集，不改称当前分类重新选队|
|同类近Q快慢×难度|已按原规则保留旧63对、当前TARGET105对及精确共同52对；旧42/63转折、44/63短边多数规律保留，表达更多与质量更高分开|{link(p,WORKER+'/stage03_speed_difficulty/README.md','快慢难度')}；同来源、楼外近Q、同具体成员与原/扩展支持均可查|
|同房均值、个人相似与预测、多份历史|已重做原支持及扩展支持，比较源均值、楼外基线、个人同行差、扣除历史残差及预测增量；直接关系待定层独立列示|{link(p,WORKER+'/stage02_same_room/README.md','预测与用途')}；相关、预测误差和构成方差不互相替代|
|Q/QT选队、停止与历史成本|实际完成25,826个所需精确端点（310复用、25,516补算）；停止原124,924前缀只更新受参考影响的5,100行|{link(p,WORKER+'/stage05_selection_stop/REPORT_ZH.md','选队停止报告')}；原历史队固定评分与当前历史重选分别报告，未重跑全库256曲线|

原设计层和无关系待定主层并列。原n5时间池62图/11楼Q/T相对Q为+0.112分、31/62图升质，劳动比0.803且11/11楼减少；无待定57图/10楼为+0.124分、29/57图升质、劳动比0.827，仍有超过5分的质量损失尾部。停止原6组/24图和主5组/21图分别16/24、13/21图提高Q；可计时原4组和主3组冷成本相对fixed7为2.395和2.115，实际剩余视角内均未回本。不可把旧0.787劳动比改贴当前重新选队。

`DEPENDENCIES.csv`追加`*_full_chain_20261030`验收行，覆盖本节所列旧查缺状态；旧行保留前轮检查事实。最终对照见{link(p,WORKER+'/stage06_synthesis/V2_TO_V21_CROSSWALK.csv','v2→v2.1全链路表')}，剩余问题按{link(p,WORKER+'/stage06_synthesis/GAP_REGISTER.csv','缺口分类表')}解释。新分类大池策略、新选队同房ABC及最小跨楼历史采集属于需另立研究问题的新设计，本轮没有自动扩展。

本次验证涵盖保存结果的重聚合、受影响端点计算、关键身份/数值回算及文件完整读取；不宣称已在用户Windows D盘应用、远端推送或完成研究台浏览器验收。下方原检查记录原样保留。'''
    files.append(added(p,t))
    p='research/statistics/research_closeout_20261022/CONCLUSIONS_ZH.md'
    t=f'''## 2026-10-30 接续：v2解释与用途链已按当前资料实际补齐

{link(p,WORKER+'/REPORT_ZH.md','本轮中文综合报告')}、{link(p,WORKER+'/stage06_synthesis/V2_TO_V21_CROSSWALK.csv','全链路对照')}和{link(p,RELEASE+'/README.md','发布入口')}接续此前查缺结论。**分类方法仍未由用户最终确定**；TARGET K3/K2为工作分析对象，OPPJOINT与RFUSE保留各自用途。历史段落中的“最终/采用”不代表本轮新增最终选型决定。

- 最新半队仍有多数规律：14/7综合197事件中83图三队共同可评，同起点幅度正61/83、对称正62/83；全部22/21张对应非正图、质量方向反例及不可评联合36图已逐项接机制和20/7背景条件，不套用旧focused-only名单。详细局部票账说明半队人数只是达到门槛的容量，不保证每个结构获得7票。
- 旧同房ABC不再停留在8,904条适用登记：已按真实原团队、楼外角色方向、n/m、房间/范围及双视角共同支持计算效应，结构、Q和劳动的重复程度分别报告；未新增房间事实或改称新分类选队实验。
- 近楼外Q快慢×难度保留旧63对转折42正、短边44正的多数表达规律；当前TARGET105对、精确共同52对另列，表达更多不等于更正确。原/新增可评分支持和人员重匹配带来的变化分开。
- 同房均值、个人绝对/相对/残差、个人预测及多份历史的用途链已恢复，直接关系待定部分独立列示。当前无待定扩展面板65图/13楼源均值预测B8L2 MAE6.464，楼外图片均值9.496；不能用个人相关或构成方差代替预测增量。
- 当前Q/T选队在原62图/11楼劳动比0.803，11/11楼平均劳动减少，但Q只有31/62图提高，实际质量损失坏尾保留。主无待定57图/10楼对应劳动比0.827、29/57图Q提高。平均Q优势由负转正主要与当前历史重选改变Q-only基线有关，不是Q/T本身大幅升质。
- 原停止完整6组/24图有16图Q提高；主无待定5组/21图有13图提高，P10略降。合法时间支持原4组/主3组的已有历史目标劳动比分别1.235/1.256；从零源历史项目成本比fixed7为2.395/2.115，原4/4及主3/3组实际余下视角内均未回本。这是本轮逐项重算结果，不直接复用v2数值声明。

{link(p,WORKER+'/stage06_synthesis/GAP_REGISTER.csv','剩余缺口')}明确区分已补齐、未来新设计和人工语义判断。无需因为分类名称变化全面重跑融合；新分类大池策略或新选队同房ABC仍需具体问题和容量依据。本补充未覆盖并行工作，不声称D盘已应用或浏览器验收通过。下方原研究阶段及数值身份保留。'''
    files.append(added(p,t))
    p='research/same_room/same_room_acceptance_20261022/USES_CLOSEOUT.md'
    t=f'''## 2026-10-30 v2.1用途重算接续

本文下方v2结论保持冻结历史身份。对应v2.1的实际结果已接入{link(p,WORKER+'/stage02_same_room/README.md','同房换人、均值与个人预测')}和{link(p,WORKER+'/stage05_selection_stop/REPORT_ZH.md','Q/QT选队、停止及历史成本')}；完整前后比较见{link(p,WORKER+'/stage06_synthesis/V2_TO_V21_CROSSWALK.csv','对照表')}。

1. 保留原直接关系和共同人员，不以同建筑或传递关系制造同房。原直接关系中4对带既有关系`oos_pending`，它不是当前图池已认定OOS；原123对/扩展132对的回放保留，主要用途另用无待定119/128对。当前无待定扩展65图/13楼的源均值MAE6.464，楼外图片均值9.496；原支持与当前扩展支持不混成一次版本收益。
2. 个人绝对Q、相对同行表现、扣除楼外历史后的残差关系，以及个人预测对公共均值/稳定历史的增量已计算；多份现有同房历史按实际m与原组身份保留。相关系数、预测误差和构成解释比例分别解释。
3. 旧ABC当前适用子集的双视角质量、结构、几何、劳动、状态已有实际端点结果。8,904是TARGET K3合法旧双视角D/X/Y/Z事件数，每事件包含两图×ABC，不是8,904个视角。主2→3的10/5在19图对/7楼中图对平均C−B均正，两视角各自都正为18/19；14/7仅2图对、10事件、6共同Q，目标Z固定同七人，现有容量已经全执行。它验证原固定团队的条件性效应，不代表按当前分类重新选队的同房ABC。
4. n5当前Q/T原层62图/11楼平均ΔQ+0.112、31/62图提高、劳动比0.803且11/11楼减少；主无待定57图/10楼平均ΔQ+0.124、29/57图提高、劳动比0.827。实际损失超过5分的加权比例分别7.86%和8.65%，历史Q≤2分损失约束不是目标保质保证。
5. 原停止6组/24图与主5组/21图分别16/24、13/21图Q改善，低尾略降。劳动只用原4组/14图及主3组/11图；已有源历史目标劳动比1.235/1.256，从零项目劳动相对fixed7比2.395/2.115，实际剩余视角内均未回本。源原答取得一次供所有顺序回放使用，未将成本乘256；参考人工成本未记录，不填0。

最终分类尚未由用户确定。新分类约束选队、大池策略和新选队同房ABC维持不同问题/新设计身份。本次只补已有资料能回答的用途链，已保留旧源表及事件身份；下文旧0.787等数值只用于原v2条件。'''
    files.append(added(p,t))
    p='research/data/releases/v2.1/final_classification_downstream/README.md'
    t=f'''## 2026-10-30 最新下游实算接续与分类身份说明

**本目录名称及历史“最终工作分类”表述不等于用户已经最终确定分类。** 本轮以已归档TARGET K3/K2为工作分析对象，OPPJOINT联合画像和RFUSE反向解释用途保留；新接续见{link(p,WORKER+'/README.md','全链路研究包')}。

- `TARGET_MAIN_EVENTS.csv.gz`的197条14/7事件已独立重聚合：83图共同可评，G_A正61图、非正22图；G_S正62图、非正21图。C−B方向、不可评/失败另计，联合反例36图。{link(p,WORKER+'/stage01_half_team/README.md','完整反例与机制')}接入原图、完整原答、两队/三队融合、实际票账及20/7背景对照；半队局部支持与连接解释保留证据边界。
- `OLD_ABC_APPLICABILITY.csv.gz`的8,904条TARGET K3适用记录已继续计算双视角实际效应，按原团队身份、方向、n/m、关系层及每指标共同有效支持报告，见{link(p,WORKER+'/stage02_same_room/README.md','同房换人及用途')}。该数字是旧D/X/Y/Z双视角事件数，每事件含两图×ABC，不是视角数、新设计、独立图片或独立房间数。主2→3的10/5有268事件、237条双视角共同Q、19图对/7楼；图对平均C−B为19/19正，但两视角各自都正为18/19，分别保留。
- {link(p,WORKER+'/stage03_speed_difficulty/README.md','同类近Q快慢×难度')}、同房均值/个人预测、多份历史，以及{link(p,WORKER+'/stage05_selection_stop/REPORT_ZH.md','选队停止和成本')}已完成实际接续，不再以“画像存在”或“人数曲线存在”替代它们。

本轮没有改变本目录冻结标签、原事件或正式规则，也没有以某一个分差最大决定最终分类。原同房构成重聚合、旧ABC适用性与本轮效应分析各自保留身份，不能互相改称新实验。总对照和未决问题见{link(p,WORKER+'/stage06_synthesis/V2_TO_V21_CROSSWALK.csv','全链路表')}及{link(p,WORKER+'/stage06_synthesis/GAP_REGISTER.csv','缺口表')}。'''
    files.append(added(p,t))
    p='research/catalog/INDEX.md'
    t=f'''## 2026-10-30 人员v2.1全链路接续：新增研究入口

本轮新增{link(p,WORKER+'/README.md','人员全链路研究包')}和{link(p,RELEASE+'/README.md','发布说明')}：最新14/7全部反例/机制、旧ABC双视角实际效果、同类近Q快慢×难度、同房均值/个人预测及多份历史、Q/QT选队—停止—历史成本已经实际补齐。原v2来源、团队、规则、当前参考及指标分母分别保留；最终人员分类尚未由用户确定。

当前科学结论与验证范围见{link(p,WORKER+'/REPORT_ZH.md','综合报告')}；{link(p,WORKER+'/stage06_synthesis/V2_TO_V21_CROSSWALK.csv','全链路对照')}与{link(p,WORKER+'/stage06_synthesis/GAP_REGISTER.csv','缺口分类')}区别“本轮已完成”与“新设计/人工判断”。本条是文档目录补充，未擅自改变下方历史CATALOG版本、资料总数或宣称研究台浏览器验收。机器依赖已在{link(p,REG+'/DEPENDENCIES.csv','DEPENDENCIES.csv')}追加验收行；全量CATALOG机器目录重建保持独立更新身份。'''
    files.append(added(p,t))
    p='RESEARCH_ANALYSIS_INDEX.md'
    t=f'''## 2026-10-30：按v2完整链路实际补齐v2.1人员研究

- {link(p,WORKER+'/README.md','完整研究包与复现交接')}；{link(p,WORKER+'/REPORT_ZH.md','中文综合报告')}。
- {link(p,WORKER+'/stage01_half_team/README.md','最新半队全部反例与局部机制')}：197事件，22张同起点非正/21张对称非正，联合36图，不套用旧focused-only名单。
- {link(p,WORKER+'/stage02_same_room/README.md','旧同房ABC实际效果、均值与个人预测')}：固定原队与当前标签的条件子集、原/扩展直接关系、无待定主层和历史回放分开。
- {link(p,WORKER+'/stage03_speed_difficulty/README.md','同类近Q快慢×难度')}：原63对、当前105对、共同52对分别解释。
- {link(p,WORKER+'/stage05_selection_stop/REPORT_ZH.md','Q/QT选队、停止人数与冷启动成本')}：当前历史重选、质量坏尾、合法同源劳动和实际历史成本已重算。
- {link(p,WORKER+'/stage06_synthesis/V2_TO_V21_CROSSWALK.csv','v2→v2.1全链路对照')}；{link(p,WORKER+'/stage06_synthesis/GAP_REGISTER.csv','剩余缺口分类')}；{link(p,RELEASE+'/README.md','发布入口')}。

TARGET K3/K2等为工作分析对象，用户尚未最终确定分类。新分类大池策略和新选队同房ABC没有自动追加，本轮不把旧实验改名；以下早期交付仍保持当时身份。'''
    files.append(added(p,t))
    p=REG+'/DEPENDENCIES.csv';src=(BASE/p).read_bytes();rows=[]
    def dep(topic,path,identity,next_action,status='verified_v21_full_chain_20261030',delivered='True'):
        rows.append(dict(topic=topic,source_path=path,delivered=delivered,status=status,method_identity=identity,next_action=next_action))
    dep('final_half_exception_mechanisms_full_chain_20261030',WORKER+'/stage01_half_team/README.md','Supersedes historical pending lookup: combined 197 14/7 events; 22 GA and 21 GS nonpositive; 36 union cases; actual trace joins','Use per-metric counts and local support; compare saved 20/7 XYZ/background; no final class adoption')
    dep('old_ABC_effects_full_chain_20261030',WORKER+'/stage02_same_room/README.md','Current-label conditional subset of old exact same-room teams; dual-view effects computed; not newly selected ABC','Read role/n/m/relation/scope-specific joint support; distinguish repeated original designs and paired views')
    dep('matched_speed_difficulty_full_chain_20261030',WORKER+'/stage03_speed_difficulty/README.md','Supersedes historical equivalent-result-not-found: original 63 pairs; current TARGET105; exact shared52','Separate expression from correctness; preserve near-LOBO-Q and same-origin matching plus old/new support')
    dep('same_room_prediction_uses_full_chain_20261030',WORKER+'/stage02_same_room/README.md','Supersedes historical acceptance-not-found: fixed and expanded direct relations; mean/personal/residual prediction and multiple histories','Separate legacy all-relations from no-pending main layer; correlations and prediction errors are distinct')
    dep('selection_stopping_cost_full_chain_20261030',WORKER+'/stage05_selection_stop/REPORT_ZH.md','Supersedes historical result-not-found: original policy candidates/rules; frozen selections and current-history reselections separate','Use current labor0.803 original or0.827 no-pending n5; retain quality-loss tail; stopping original6/4 and main5/3 groups')
    dep('full_chain_crosswalk_20261030',WORKER+'/stage06_synthesis/V2_TO_V21_CROSSWALK.csv','v2 historical result to current v2.1 result with reasons and support','Do not treat conditional current result as final personnel-method selection')
    dep('full_chain_gap_register_20261030',WORKER+'/stage06_synthesis/GAP_REGISTER.csv','Current verified gaps classified as completed analysis, future design, or human interpretation','Final class choice and any new selected same-room ABC remain separate decisions; no automatic full fusion rerun')
    dep('full_chain_reproduction_20261030',WORKER+'/README.md','Frozen commit '+COMMIT+'; exact member/endpoint identities and source snapshots','Review numerical checks and file readability; documentation application is hash guarded and separate from remote/browser acceptance')
    f=io.StringIO(newline='');w=csv.DictWriter(f,fieldnames=['topic','source_path','delivered','status','method_identity','next_action'],lineterminator='\r\n' if b'\r\n' in src else '\n');w.writerows(rows)
    out=src+(b'' if src.endswith(b'\n') else b'\r\n')+f.getvalue().encode();assert out.startswith(src)
    dest=OVER/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(out)
    assert len(list(csv.DictReader(io.StringIO(out.decode('utf-8-sig')))))==len(list(csv.DictReader(io.StringIO(src.decode('utf-8-sig')))))+8
    files.append(dict(path=p,operation='append_8_current_acceptance_rows',base_sha256=sha(src),updated_sha256=sha(out),base_bytes=len(src),updated_bytes=len(out),original_bytes_preserved=True))
    p=WORKER+'/README.md'
    t=f'''# HOHONET v2.1人员全链路接续：研究交付与复现

以冻结提交 `{COMMIT}` 为输入，接续v2完整解释/用途链。用户尚未最终确定人员分类；TARGET K3/K2为工作分析对象，OPPJOINT用于联合画像，RFUSE用于反向融合响应。正式数据、参考、目标归属、人员/标注排除、难度标签和融合规则未改变。

## 入口

- [中文综合报告](REPORT_ZH.md)及[HTML报告](REPORT_ZH.html)。
- [完整交付原README](DELIVERY_README.md)：从交付根README保留导入，仓库此页只负责导航。
- [v2→v2.1全链路对照](stage06_synthesis/V2_TO_V21_CROSSWALK.csv)与[剩余缺口](stage06_synthesis/GAP_REGISTER.csv)。
- [v2.1发布说明](../../data/releases/v2.1/full_chain_downstream_20261030/README.md)。

|阶段|已完成的实际研究|直接入口|
|---|---|---|
|输入与冻结核对|当前提交、原始依赖、输入池与135项冻结引擎代码一致性|`stage00_intake/`|
|最新半队反例|197事件、最新21张对称非正，全部指标/状态联合36图；原答、端点、几何、票账、20/7背景|[阶段01](stage01_half_team/README.md)、[36图完整说明](stage01_half_team/ALL_36_CASES_ZH.md)|
|同房换人、个人与预测|旧ABC适用子集实际双视角效果、原与扩展直接关系、个人均值/历史/残差和多份同房历史|[阶段02](stage02_same_room/README.md)|
|同类近Q快慢×难度|原63对、当前105对及共同52对，表达/正确/劳动及成员建筑敏感性|[阶段03](stage03_speed_difficulty/README.md)|
|选队、停止与成本|Q/QT两种身份、25,826精确团队、124,924旧前缀定向更新、已有/从零历史成本|[阶段05](stage05_selection_stop/REPORT_ZH.md)、[复现](stage05_selection_stop/README.md)|
|综合与未决事项|支持范围、变化原因、采用说法及真正需要新设计/人工项|[全链路表](stage06_synthesis/V2_TO_V21_CROSSWALK.csv)|

## 身份与分母

v2冻结结果、旧团队固定重评、当前历史重选和新设计分别表达。普通Manual为主，Semi补充，OOS及其它合法空间单列。直接关系的旧`oos_pending`标志不自动改变当前图池资格；原设计完整层与无关系待定主层并列。缺Q不填0，原生失败、输出不可评和其它缺失分开；劳动只用合法同来源记录，不能作为并行等待时间。

本轮完成已有资料可回答的下游：半队机制、旧同房ABC实际效应、近Q快慢×难度、预测用途、选队/停止/历史成本。没有自动新增人员、房间或重新跑256自然曲线。当前标签下的新选队同房ABC、类别约束大池策略和最低跨楼历史采集成本需另立具体问题，不因本目录建立就标为完成。

## 导入与复现

本入口依赖同目录的`stage*`、`scripts/`、`source/`、`REPORT_ZH.md/html`。仅应用文档patch不会生成这些研究数据。交付包`repository_update/apply_update.py --repo <仓库> --study <完整交付根> --apply`会先检查7个原文档SHA256、补丁可应用性和所有新目录目标冲突，再导入实际研究文件并更新文档；交付根README保存为`DELIVERY_README.md`。不复制`repository_update`本身，避免递归。

各阶段README提供最小输入、代码、源表、精确事件和验证。应优先复用交付端点重聚合；完整源快照用于核查，不覆盖原仓库来源。若仓库目标文件已被并行线程更改，应用程序停止并列出冲突，保留其新版本，不自动强行覆盖。

本研究在可访问的冻结仓库快照上完成。交付时尚未写入用户`D:\\Work\\HOHONET`、提交/推送远端或完成研究台浏览器验收；实际应用另以应用回执为准。'''
    files.append(new(p,t))
    p=RELEASE+'/README.md'
    t=f'''# v2.1完整人员研究链：下游补齐发布入口

本发布连接{link(p,WORKER+'/README.md','人员全链路研究包')}，来源冻结提交 `{COMMIT}`。与先前“只接入核心构成模块、尚未查到全部用途验收”的阶段相比，本轮已经实际完成：最新半队全部反例/机制、旧同房ABC当前标签合法子集实际效果、同类近楼外Q快慢×难度、同房均值/个人相似与预测、多份历史、Q/QT选队、停止人数和历史获取成本。

结果和身份以{link(p,WORKER+'/REPORT_ZH.md','综合报告')}、{link(p,WORKER+'/stage06_synthesis/V2_TO_V21_CROSSWALK.csv','逐项对照')}及{link(p,WORKER+'/stage06_synthesis/GAP_REGISTER.csv','缺口表')}为准。证据不是仅有文件或适用数量：选队端点实际补算25,516个并精确复用310个，停止仅更新受影响的5,100旧前缀；其它原团队、原答或预测分支按各自回执说明重聚合与验证范围。

**分类最终决定仍未作出。** TARGET K3/K2可作工作分析对象，OPPJOINT联合画像与RFUSE反向解释保留，不能由单项分差最大或本次资料完备性替用户决定最终分类。旧设计子集不改称新类别重新选队；新分类大池策略和新选队同房ABC没有自动执行。

半队14/7当前共同可评83图中，G_A正61、G_S正62，全部反例和实际局部票账可追查。v2旧63快慢对42/63转折和44/63短边多数表达关系保留，同时当前105与共同52对显示人员/支持变化。选队原62图/11楼Q/T劳动比0.803，质量只31/62图提高且有坏尾；无待定主层57图/10楼另列。停止原6组/主5组及合法时间原4组/主3组不混用；从零取得源历史相对fixed7的项目成本比2.395/2.115仍未在原实际余下视角内回本。

数据、参考、空间归属、排除、正式难度与冻结融合未改；v2旧结果原位保留。不同合法目标各自组队/评价，Manual/Semi、OOS、关系待定层与指标有效分母独立。

文档补丁在完整交付的`repository_update/`，带原始字节SHA256 guard和冻结快照`git apply --check`回执。它尚未应用到用户Windows D盘或远端；研究文件须与新增workers入口一起导入，应用程序可据完整交付目录核验复制，不覆盖并行变化。'''
    files.append(new(p,t))
    (HERE/'UPDATED_FILES.json').write_text(json.dumps({'base_commit':COMMIT,'worker_path':WORKER,'release_path':RELEASE,'files':files},ensure_ascii=False,indent=2)+'\n')
    # Small isolated Git trees contain documents only, never the existing repository.
    for d in ['diff_tree','apply_check_tree']:
        repo=HERE/d
        if repo.exists():shutil.rmtree(repo)
        repo.mkdir();subprocess.run(['git','init','-q',str(repo)],check=True)
        subprocess.run(['git','-C',str(repo),'config','core.autocrlf','false'],check=True)
        for row in files:
            if row['base_sha256'] is None:continue
            dest=repo/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/row['path'],dest)
        subprocess.run(['git','-C',str(repo),'add','.'],check=True)
    diff=HERE/'diff_tree'
    for row in files:
        dest=diff/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OVER/row['path'],dest)
        if row['base_sha256'] is None:subprocess.run(['git','-C',str(diff),'add','-N','--',row['path']],check=True)
    patch=subprocess.check_output(['git','-C',str(diff),'diff','--binary','--no-ext-diff','--no-color'])
    (HERE/'UPDATE.patch').write_bytes(patch)
    check=HERE/'apply_check_tree'
    result=subprocess.run(['git','-C',str(check),'apply','--check',str(HERE/'UPDATE.patch')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    applied=subprocess.run(['git','-C',str(check),'apply',str(HERE/'UPDATE.patch')],capture_output=True,text=True);assert applied.returncode==0,applied.stderr
    for row in files:assert sha((check/row['path']).read_bytes())==row['updated_sha256'],row['path']
    receipt={'base_commit':COMMIT,'base_byte_sources':'BASE_FILES.json; exact public raw bytes including original CRLF','updated_files':files,'patch_sha256':sha(patch),'git_apply_check_on_frozen_document_snapshot':True,'git_apply_and_byte_match_all_overlay_files':True,'existing_repo_modified':False,'windows_D_drive_written':False,'remote_pushed':False,'old_content_preserved':True,'dependency_rows_appended':8,'payload_import_not_performed_here':True,'payload_target':WORKER,'data_import_rules':'all source/scripts/stage directories and root md/html/csv/json receipts; README mapped to DELIVERY_README; no repository_update recursion; never overwrite differing target files','classification_final_decision':'not made','review_entry':'README_ZH.md','application_script':'apply_update.py','validation_stderr':result.stderr.strip(),'applied_stderr':applied.stderr.strip()}
    (HERE/'UPDATE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'files':len(files),'patch_bytes':len(patch),'git_apply_check':True,'overlay_byte_parity':True,'original_files_preserved':True},ensure_ascii=False))

if __name__=='__main__':build()
