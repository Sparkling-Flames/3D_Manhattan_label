# 全员点身份并列：独立复现与最小诊断修复

日期：2026-10-04。范围：dot `oct4-repo-audit/check_partition_ties.py` 与 `partition_tie_result.json` 的三人四点反例；使用当前仓库正常导入运行，没有采用外包 AST 替代导入，也没有修改外部下载。

**dot 指出的漏报成立。它是合成存在性反例，不是已确认的真人图片故障，也没有给出 137 图的发生比例。** 三人的第一对 x 分别为 100、116、132；其他三对相同，上下 y 为 120/390。相邻角距离严格并列，均约 3.827555°，两端约 7.650149°；5° 完整链接只能选择其中一对先合并。

仅交换人员和记录编号，点、环和票数不变。当前仓库复现了中心 x 从 108 变为 124、两次均 `ok`、旧 `competing_worker_matches=0`。原因是旧诊断只覆盖“同一观测对同一其他人员有多个候选”，不覆盖不同人员间的并列合并选择。

## 本轮修改

保留现有 canonical 排序、原 linkage 和中心计算。额外用反向观测顺序运行一次同样的 complete-link，再把标签映回原观测索引，只比较共同成员集合。若分区改变，保留原候选并增加 `complete_linkage_partition_tie` 提示，使可生成候选进入 `geometry_review`。

这是一项**有限扰动检查**：只检查一个反向顺序，不枚举所有排列或可行分区；未发现变化不证明身份唯一、不证明对所有重命名不变。`uniqueness_established` 继续为 false。不使用备选分区修改原中心，不以新提示排除人员，也没有更换几何或融合算法。

|输入|规则|修复前→后|第一对 x|点支持|
|---|---|---|---:|---|
|原编号|≥50%|ok → geometry_review|108|2,3,3,3|
|原编号|>50%|ok → geometry_review|108|2,3,3,3|
|交换编号|≥50%|ok → geometry_review|124|2,3,3,3|
|交换编号|>50%|ok → geometry_review|124|2,3,3,3|

四个输出逐字段比对：除新增诊断与既有 status/reason 外，**所有原有字段完全相同**，包括身份分区、点、footprint、分母、支持人员与原环。两次均检出 3 个共同成员集合改变的观测。重复相同坐标仍作为不同人员独立票；原有重复几何案例仍为 ok，不把无害的等距合并一概报警。

## 验证与合同

先加入回归，修复前得到预期的 3 项失败、6 项通过；新增两条规则的测试均揭示原 status=ok，另一个失败揭示新增诊断字段尚不存在。修复后运行：

```powershell
python -B -m pytest -p no:cacheprovider tests/test_global_pair_consensus_20261004.py tests/test_consensus_result_studio_20261004.py -q
```

结果 **12 passed**，含原测试及工作台相关检查；定向 `git diff --check` 通过。首次红测试曾提示工作区 pytest cache 无写权限，最终验证禁用 cacheprovider，不需要权限升级。

保留现有 v1 schema，新增 `correspondence_diagnostics.partition_tie_check`；字段与边界见 [field_contract.json](field_contract.json)。历史保存结果缺少此字段表示未记录该检查，不能当成检查通过。本轮没有覆盖旧输出，没有重算 137 图或 822 个设置；已有报告中的 ok 数量仍是旧诊断口径。

文件：[fixture.json](fixture.json)、[before.json](before.json)、[after.json](after.json)、[verification.json](verification.json)。仅修改专属两个 Python 文件及本目录，不修改其他工具、全局文档或提交。下一步若要报告真实发生比例，应在单独新版本结果中运行此诊断；当前反例不能给出该比例。
