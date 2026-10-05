# 局部路径与空间候选：本地／Pro并行交接

2026-10-05。Pro指Chat中的Pro，由用户手动上传资料并发送对话提示词。本地没有启动或发送Pro任务。这里记录分工、可复算输入及接回验收，不冻结正式融合方法。

返回状态：用户已带回Pro与dot结果，[本地审查、修复及原件归档](../../analysis_results/local_path_review_20261005/REPORT.md)完成。下文为原任务说明；当前接续两个真实窗口的锚点、候选与证据前提核查，不能用合成b=1直接自动删点。

## 本轮本地进展

- [新回投与原图报告](../../analysis_results/local_shortcut_evidence_20261005/REPORT.md)：51次单点对删除的局部经度诊断、两个预定窗口的源路径与跨接图件。
- [原删改实验](../../analysis_results/local_structure_deletion_20261005/REPORT.md)：5份原答、51次操作，不是完整多人重组。
- [可靠性修复](../../analysis_results/layout_reliability_fixed_20261005/REPORT.md)：两处修复已由本地和dot定向复跑。
- [dot本地审查原件](../layout_reliability_20261005/dot_local_review/LOCAL_REVIEW_ZH.md)：附同目录原日志及聚合数值，三份文件逐字节复制。其9项与35项测试属于dot本次执行；本线程本轮运行的是13项相关回归，不把他人的执行写成本次执行。

原四图面板共66份记录、24个不同worker ID；这次交接的两个完整图名单是39份记录、24个不同worker ID，分别为rPc-06的24份和uNb-67的15份。只有其中预先选定的五份原环参与51次删除。不得将66或39称为独立人员数，也不得将51个生成候选计票。

## 分工及返回验收

本地继续核查真实原图、来源与对应锚点，维护诊断和证据账本。两个原图窗口暂不足以生成可靠的自动删除标签；两例均保持待定。这不阻止Pro研究明确假设下的有限候选模型。

Pro任务限定为：**给定对应锚点、有限带来源路径及相容关系，检验细节保护与新跨接依据。** 至少区分仅用人员路径、增加有误差／缺失的局部核验证据两种条件；少数真细节与少数伪细节都要覆盖。保护输入若直接是真值，必须称条件上界，不能称自动识别。

应输出完整有限候选及失败、逐候选依据、真实结构误删、错误结构误保留／新增、遗漏／外扩和待定率；不先合成总分。允许证明观测不足以唯一选定。合成锚点身份已知不代表解决了真实角点对应。

同一候选集合与目标先穷举核对；只在相同可达域和计入初始化成本的有限预算下比较加法／减法。互斥观测的并集不自动是一个合法“最大房间”。生成规则、预算及候选保存后才接触合成真值评价，不靠两张真实图调出指定结论。

本地接回时独立挑反例复算，并检查真值泄漏、遗漏失败、不同搜索可达域、票数继承和保护证据误判。条件性结论、数学保证、浮点数值验证及真实视觉观察分开写。提示词仅在当前对话提供，不在此保存重复版本。

## 最小可复算包

本地生成的[Pro输入包](../../analysis_results/local_shortcut_evidence_20261005/pro_input_pack.zip)便于用户手动上传，文件清单见[package_manifest.json](package_manifest.json)。ZIP是可再生交付附件，不作为Git真源；main保存引用的代码、结果与说明。包里没有GT、身份映射或私人评论；有两张原PNG、两图完整匿名名单、现有候选和新诊断、图件及必要代码。它不包含完整仓库，历史背景文档链接可能需回到main阅读。

使用Python、NumPy、Shapely；绘图另需Matplotlib和Pillow；回归需pytest。无需panorama工作台或本地未提交的几何修改。解压后在包根目录执行：

```powershell
python -B -m pytest -p no:cacheprovider tests/test_local_shortcut_projection_20261005.py -q
python -B -m tools.thesis_main.analysis.local_shortcut_projection_20261005 --out check_projection
python -B -m tools.thesis_main.analysis.local_shortcut_figures_20261005 --out check_figures
```

输出目录须不存在。两项生成器只读输入；诊断不靠显示采样。包内最小回归、51操作重跑及输入/结果比对由本地解压验证；图件在当前完整仓库实际生成、人工查看。本次未上传或推送。
