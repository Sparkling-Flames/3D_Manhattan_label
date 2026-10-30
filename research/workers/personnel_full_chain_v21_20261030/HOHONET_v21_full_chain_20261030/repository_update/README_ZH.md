# 仓库文档更新包：审阅与安全应用

本包基于冻结提交 `13a7861334749805a86dc19e9ea79fcaa71020c0`，为本轮已经完成的v2.1全链路研究补充仓库入口、依赖状态和用途说明。**实际用户 `D:\Work\HOHONET` 未写入，现有旧repo和远端未修改。** 当前环境已完成可以独立验证的文档、补丁和保护程序；Windows应用以执行后的回执为准。

## 审阅入口

- [UPDATE.patch](UPDATE.patch)：9个目标文件的增量补丁。
- [overlay/](overlay/)：可逐文件阅读的完整更新副本。
- [UPDATE_RECEIPT.json](UPDATE_RECEIPT.json)：源提交、原始和更新SHA256、原内容保留、补丁与保护验证。
- [UPDATED_FILES.json](UPDATED_FILES.json)：逐文件操作与哈希。
- [BASE_FILES.json](BASE_FILES.json)：冻结提交的7份原始字节来源，含URL、Git blob、SHA256和CRLF计数。
- [GUARD_BASE_CHECK.json](GUARD_BASE_CHECK.json)：原冻结文档通过只读检查。
- [GUARD_CONFLICT_CHECK.json](GUARD_CONFLICT_CHECK.json)：人为模拟并行修改后，程序拒绝且该修改字节不变。

## 更新内容

以下7个既有文件全部保留原内容，仅在标题后插入注明日期的新接续段落，或在CSV追加验收记录：

1. `research/data/releases/v2.1/personnel_reselection_dependencies/README.md`
2. `research/data/releases/v2.1/personnel_reselection_dependencies/DEPENDENCIES.csv`
3. `research/statistics/research_closeout_20261022/CONCLUSIONS_ZH.md`
4. `research/same_room/same_room_acceptance_20261022/USES_CLOSEOUT.md`
5. `research/data/releases/v2.1/final_classification_downstream/README.md`
6. `research/catalog/INDEX.md`
7. `RESEARCH_ANALYSIS_INDEX.md`

新增两个入口：

- `research/workers/personnel_full_chain_v21_20261030/README.md`
- `research/data/releases/v2.1/full_chain_downstream_20261030/README.md`

新接续明确：最新半队机制、旧同房ABC实际双视角效果、同类近Q快慢×难度、均值/个人预测与多份历史、Q/QT选队/停止/历史成本已经实际计算并验证。最终分类仍未由用户确定；新选队同房ABC、大池类别策略和最小跨楼历史成本是不同的新设计问题，没有自动改写为完成。

依赖表新增8条`*_full_chain_20261030`当前验收行，并明确它们接续哪些原查缺状态；旧行保留当时事实，不把当时“未找到”当作当前仍缺失。CATALOG机器总数与历史版本未被猜测更新，本包新增可读目录入口并更新依赖机器表。

## 已完成验证

7份既有文件已从指定冻结提交定点取得原始字节，避免初始读取造成换行标准化。4份保留CRLF，其余保留原LF。保存的原内容按字节完整嵌在新增副本中。

在独立、仅含这些文档的Git快照上已经：

1. 生成 `UPDATE.patch`。
2. 执行 `git apply --check` 成功。
3. 实际应用到该独立验证快照，9个文件逐项SHA256均等于overlay。
4. 验证应用程序接受冻结原文件；模拟一项并行修改后程序以退出码2停止，该文件原样保留。

这些操作不在用户D盘或已有repo上执行，也不等于远端推送或研究台浏览器验收。

## 应用方法

先将完整研究包解压。`--study`必须指向包含`REPORT_ZH.md/html`、根`README.md`、各`stage*`、`scripts/`与`source/`的完整目录。

在PowerShell中先进行只读检查：

```powershell
python .\repository_update\apply_update.py --repo 'D:\Work\HOHONET' --study '完整研究包解压目录'
```

确认输出后，可用本次已授权的更新命令应用：

```powershell
python .\repository_update\apply_update.py --repo 'D:\Work\HOHONET' --study '完整研究包解压目录' --apply
```

程序先检查所有原文档的SHA256、研究导入目标是否冲突、所需主入口是否存在和`git apply --check`；这些检查全部通过后才开始写入。目标HEAD允许存在其它并行提交，但上述7个目标原文件必须仍匹配。若文本甚至换行已变，会明确列出冲突并停止，不强行覆盖、删除或自动回退。应在保留并行版本的前提下审阅相应日期段落后再决定合并。

实际研究资料导入新的 `research/workers/personnel_full_chain_v21_20261030/`，逐文件比较复制前后SHA256。已存在且相同的文件复用；不同的文件拒绝覆盖。交付根README保存为`DELIVERY_README.md`，仓库README使用overlay导航；根报告/HTML及其它根工件保留原名。`repository_update`不会被再次复制到自己，顶层压缩包、字节码与临时文件也不递归导入。

仅应用文档patch不会产生研究数据，因此程序在没有已安装完整研究资料且未提供`--study`时拒绝`--apply`。程序不提交、不推送、不改原正式研究来源。

应用回执默认写到新研究目录的`REPOSITORY_APPLICATION_RECEIPT.json`。如该回执已存在，先前结果被保留；可用`--receipt <新的回执路径>`明确保存另一回执。

## 重建更新包

`build_update.py`使用本包`base/`的原始字节生成overlay和patch，并在独立文档Git树验证。该程序只重建本包内指定的临时验证树，不读取或修改用户已有repo。源表科学结果不由该程序重算；相应验证在研究各阶段回执中。
