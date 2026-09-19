# Pro下一轮资料：分簇收束、人工复核与分析成稿准备

先读[本轮完整任务](../../docs/thesis_main/Pro下一轮_分簇定稿与分析准备_20260920.md)，再读[来源核对](来源核对与最新要求.md)与[uNb-21用户局部对应](uNb21_用户局部对应.json)。这是本轮入口，旧任务中“继续广泛探索”“按x尚未运行”等按历史时点理解。

用户已授权上传至既有GitHub仓库；使用独立分支`codex/pro-clustering-ready-20260920`，不改main。上传验收以本轮对话的实际Git结果为准。仓库：`Sparkling-Flames/3D_Manhattan_label`。

## 云端只需这个包

[下载自包含数值包](pro_next_round_20260920.zip)，解压保留目录结构。无需本地D/C盘、旧Downloads路径、Studio服务器或视觉能力。`MANIFEST.json`列出文件与用途范围。包含代码、冻结输入、原结果、独立核验摘要、用户审核原件、导师必要原话、AI视觉文字与8幅审核证据；不上传原始日志、额外运行时导出、凭据或完整图库。人员以既有W编号表示。

旧报告/源码作为原件保留，可能提及未打包的旧HTML或本机路径；它们只是历史来源，不是运行依赖。本包支持下列数值命令，不要求运行历史UI生成或再次打包。

## 阅读顺序与证据等级

1. 本轮任务与来源核对：导师书面／用户回忆／用户最新决定分开。
2. `analysis_results/paired_split_research_received_20260920/独立审查与研究方向.md`：最新按序研究的核验、限制；下一轮以短平快任务优先。
3. 同目录`history_visual_review/visual_findings.json`、`selected_evidence.json`、`all_history_queue.json`：214图全量数值筛查，8图指定作答对目视；不冒称全部视觉完成。uNb-21的用户最新局部确认单独存于本目录，不覆盖原AI观察。
4. `inputs/user_six_review.json`、旧39/12图原始JSON：用户裁决与AI意见不混用。只接受某种规范标法不等于其他响应无研究价值。
5. 两轮数值输入/结果与代码；按需读取全量成对表，不把候选告警当错误名单。

## 从解压根目录运行

已有numpy、pandas、scipy、pytest即可；不要求安装返回包原requirements的特定版本。完整复算会产生独立`local_recheck/`，不改接收输入：

```bash
python -B -m tools.thesis_main.analysis.paired_split_research.pro_package --verify-root .
python -B -m tools.thesis_main.analysis.paired_split_research
python -B -m tools.thesis_main.analysis.local_point_research
python -B -m pytest tests/test_paired_split_research.py tests/test_local_point_research.py tests/test_point_pair_pilot.py -q
```

按序原包25表本地复现一致；局部点旧包25表中13表有已记录的浮点阈值/代表选择差异，不能称全一致。本轮脱离仓库的实际复算验收见`DELIVERY_CHECK.json`（交付时生成）。生成图片的脚本需要未打包Studio图片来源，不属于云端数值复算入口；视觉文字和证据已给出。

## 本轮不再拖延的边界

现有简单方法中明确主候选和必要对照，疑难局部对应人工复核，输出历史分析示范及新数据到齐后的可重跑流程。复杂修正、按图尺度/中心学习、虚拟人员暂缓。人员独立采集后组合，AABC需四位不同真人；不可计算、少数表达、单人簇、OOS保留；不因“快”伪造收敛、误并准确率或人员能力结论。
