# 质量研究 Pro 交接（2026-10-14）

唯一推荐交付：[READY 离线包](quality_pro_handoff_20261014_READY.zip)。三例审核已收到，Q02/Q03有修订；目前足以开始普通粗调，无需等待92份门洞暂缓样本解锁。具体研究方法由Pro独立判断，保留“普通粗调→冻结普通版→门洞交界细调→普通回归”的顺序。

## 当前入口

- [当前状态与评分版本](CURRENT_STATUS.md)：区分历史分数、当前工作分及有效审核状态。
- [目标导向任务书](PRO_TASK.md)：研究目标、证据边界与交付要求；不限定候选数量、搜索方式或具体操作步骤。
- [人工审核及修订解释](human_review/REVIEW_FINDINGS.md)：原回执与补充修订原样保留；Q02/Q03不能作为完整质量排序约束。
- [交付检查](DELIVERY_CHECK.json)：完整性、原始数据/引擎/回执保持情况与实际解包启动结果。
- [已有分阶段比较](../quality_staged_calibration_20261014/README.md)：当前研究工作版及完整结果，尚不是正式算法或最终调参结论。

## 离线使用与内容

下载并解压READY包，阅读包内CURRENT_STATUS.md、PRO_TASK.md及START_HERE.md。用Python 3.10及以上、numpy/scipy/shapely运行`python -B run.py`。程序不需要联网、clone仓库或读取原机器路径；启动输出应为`review_status=received_with_amendments`。

包内有574普通（207显式普通/367既有条件）、9单列严重、217门洞（125条件完整评分/92暂缓），151控制几何、907相关对象、21张针对性原图、16组审核材料、冻结引擎及既有研究结果。21张原图不是574份全部原图；缺少新视觉证据时须指明具体对象。`REVIEW.html`供备查，`SUPPLEMENT.md`记录材料覆盖和未决问题。

普通/严重的当前工作分读取包内`stage/COARSE.json.records[*].hill_global08`，各层统一复算使用`stage/WORKING_FINAL.json`。`data/cohorts.json`普通/严重行的旧components保留历史，不可混用。缺参考、held与不确定意见均不能补成零分、相等或强制排序。

## 归档与验证边界

Git保留最终READY包、回执、检查记录、复现源码及分阶段研究结果。重复解包目录与旧PENDING_REVIEW/WITH_REVIEW ZIP只留本地。构建工具`quality_pro_handoff_20261014.py`产生审核前快照；最终人工回执及修订必须显式保留，不能直接用重建快照覆盖READY包。

定向测试直接解压最终ZIP检查人员/参考限制和审核绑定，不依赖本机package目录。数值启动检查覆盖583份存储metrics重评分，以及R03274、2个底点控制、7个菱形重建；不等于所有几何重新计算或量表效度验收。原启动记录[EXTRACTED_STARTUP.json](EXTRACTED_STARTUP.json)保留历史，最新实跑记录见[READY_STARTUP.json](READY_STARTUP.json)。

网页交互尚未完成浏览器实机视觉验收；此前JS语法、绑定、分数隐藏及静态图已检查。没有新增检查截图。此次发布不修改正式评分算法、原始作答、GT、资格或融合。
