# 问题GT及研究排除核对（2026-10-10）

## 可直接采用的结论

已实际调用当前给定 checkout 的 `load_current_bundle()`，跨表验证通过：3441对象、3152份人员作答、259张研究图、2张参考专用图、3312可用配对对象、1312确认环。

这是对给定本地工作树的核验（checkout commit `24360ad8544d76d8aba18a8e641f784a76ca0d42`）；工作树已有点/环接入改动，来源文件SHA-256载于机器登记。未宣称远端最新提交已同样更新。审计没有改正式数据、GT、人员资格、正式loader、分数，也没有上传。

### 1. 明确问题参考/明确主分析暂停：8图、9个GT版本

- jtcxE69GiFV-05：原GT；用户“gt是错误的,不是空间的问题,是完全错误”。9月上传审核、10月10日回执“这gt是错误的”及当前消息一致。6份人员作答为hold_reference_quality。
- jtcxE69GiFV-17：原GT；“gt标的是错误的……错误把门当成墙了”。1份hold_reference_quality。
- pRbA3pwrgk9-12：原GT；“我认为它标的高度也有问题,是错误的”。不是仅缺凸起细节。2份hold_reference_quality。
- uNb9QFRL6hY-51：原GT；“玻璃区域的顶部是斜着的……所以gt肯定不对”。只标内侧空间的后续决定未认证原GT。4份hold_reference_quality，2份原excluded。
- zsNo4HB9uLZ-05：原GT；“gt是肯定错的”。4份hold_reference_quality。
- x8F5xyUWy9e-01：原GT；“01的gt有点问题,不太准确”。5份hold_reference_quality。暂停原因是GT问题，而非真实非正交。
- wc2JMjhGNzB-14：原GT及人工修订GT；用户明确“两者都不太对”，人数少时搁置。4份hold_reference_quality，1份原excluded。
- uNb9QFRL6hY-32：原GT；“先不进入主分析,因为gt也不太对,这图也很怪”。5份hold_main_analysis，保留这项比参考层更宽的既有暂停。

合计34份人员作答：26份hold_reference_quality、5份hold_main_analysis、3份原excluded。完整image_id、每版GT对象ID、坐标hash、原话、审核文件与JSON指针已在 `reference_exclusion_registry_20261010.json`。

### 2. 用户明确暂停，GT错误尚未定性：另2图

- jtcxE69GiFV-11：用户无法判断GT正确性、全部分析暂缓；2份hold_all_analysis。
- pRbA3pwrgk9-16：“不太确定是不是oos……如果真的能标,gt也有点问题.先排除吧”；2份hold_all_analysis。

保留已有暂停，不改称用户已确认GT错误。

### 3. 证据冲突，供Pro核查：q9vSo1VnCiC-16

9月23日逐人审核出现“gt有误”“不过gt也不对”；9月27日后续评价是“gt是标了两个主标注区域外的空间,不一定好”。目前只存在原GT，未找到修正版本或明确撤回错误判断；正式gate仍为8份candidate_pending_geometry、2份excluded。

按本轮用户要求，为新研究主参数选择、主GT比较/优劣论证、标注者不确定性校准暂不使用该参考，保留诊断与版本核查。此项是研究使用隔离，不是新增用户GT错误裁定，也没有改正式gate。

## 必须显著提醒消费者

多数问题GT对象自身的worker_quality_gate仍是candidate_pending_geometry，既有reference hold实际施加在人员作答行。因此，单查GT对象gate会漏排。消费者须按完整image_id、GT对象ID与版本连接登记，再叠加正式人员gate。

登记的exclude=false仅代表不额外增加本登记的参考排除，绝不表示恢复其他hold、excluded或out_of_primary_scene。登记尚未接入正式loader，也没有据此重算分数。

新近底面范围确认（包括新35份）不能自动证明旧顶界或完整GT正确，也不能自动解除上述参考暂停。任何派生新参考须独立命名并技术验证。

## 疑似、范围、细节、版本差异分开保留

机器登记另列10个不自动排除案例及1个已修订版本案例：

- x8F5xyUWy9e-09：真实非正交，没有用户GT错误判断；quality_reference_hold=false。既有24份out_of_primary_scene和2份excluded不自动恢复。
- jtcxE69GiFV-10：仅“有可能算作oos”，不是GT错误。
- B6ByNegPMKs-37、q9vSo1VnCiC-34：旧“有点问题”附于范围评语，具体错误未定性，交Pro核查，不能按关键词升级。
- uNb9QFRL6hY-01：后续具体为最左凸起遗漏，属于本轮不自动排除的细节简化。
- uNb9QFRL6hY-88：玻璃内外、两侧走廊范围以及旧环序问题应分开。
- uNb9QFRL6hY-36：以最严格曼哈顿规则为前提的停止线批评，非无条件GT错误裁定。
- uNb9QFRL6hY-47：门洞条件与细节遗漏；既有hold_scene_or_reference继续保留。
- yqstnuAEVhm-32：“可能”问题且原始/修订范围有别，不能把两版都判错。
- yqstnuAEVhm-07：本轮接受GT、暂不处理壁炉细节；原有场景gate仍保留。
- e9zR4mvMWw7-16：用户明确“我人工修正过后的……没问题了”；原始空间差异不否定人工修订GT。

本次最新26图审核的8张“范围明显不同”和3张范围备注，不自动成为11张错误GT。也没有把54张具有任一种人员hold的图片全算成GT错误；完整hold快照另存机器登记供核对。

补充旧清单仅新增库外线索q9vSo1VnCiC-19：“角点重复；GT错误且人工不适合”。该条明确标为旧校准代理摘要、非已核用户原话，不在当前259图；不计入本轮明确错误图数，也不猜测GT对象ID。

## 文件

- `reference_exclusion_registry_20261010.json`：可机器消费的研究使用登记和来源证据。
- `validation.json`：实际loader检查与数量。
- `verify_registry.py`：只读核验脚本，对给定正式输入检查来源hash、22图版本绑定、坐标hash与人员gate；依赖原研究运行环境。
- `verification_result.json`：该脚本实际运行通过的结果。

停止条件已达到：已知明确问题及暂停全部登记；历史未消解项交Pro核查，不重新视觉裁判所有负面GT关键词。
