你在HOHONET仓库执行“图片画像”数值分析。使用分支 codex/image-portrait-20260914，以及仓库根目录下 analysis_results/image_portrait_20260914_v1/ 的工作包。

先读 AGENTS.md、工作包 README、evaluation/metrics.md、evaluation/config.json、evaluation/folds.jsonl.gz 和运行状态。运行 python -m tools.thesis_main.analysis.image_portrait.build_bundle --check，只检查工作包，不在云端重建原始数据包。
这是探索研究，不修改正式 Paper A 合同、原始导出、人工原文或采集安排。

不查看原始图片，不调用视觉模型，不下载权重。只能依据提供的数值、几何、文字及来源记录分析。需要视觉判断的事项输出 image_id、具体疑问和触发依据，交回本地核查。

648图是画像覆盖，不等于648图都有真人结果。保留W011历史；W019/W026排除当前主分析。Manual与Semi分开；缺失、无效、低人数、观察内持续变化分别记录。不复制人员，不把重采样当独立样本，不把模型输出当GT。

所有标准化、降维、选层、调参及人员分型只使用当前训练侧。使用工作包固定的评价划分；不能挑成功划分或删除不利结果。evaluation/room_components.jsonl 是支持关系分析组件，不是已去重物理房间普查；待定关系隔离规则见 metrics.md。
输入不足时给出覆盖表和具体缺口，不能补造数据。特别检查模型每图每phase状态及required key，不能把partial文件看作完整输出。未提取模型明确pending；可独立的已有数据分析继续，不能自行替换模型。

仅修改自己路线的分析脚本、测试及输出目录。交付中文报告、逐图结果、覆盖与失败表、可运行命令和必要测试；区分论文结论、本轮实测和解释性假设。不要修改其他路线或汇总报告。

执行路线E：分析图片特质与人员特征的交互，以及人员子类和真实组合的标注规律。

保留质量、时间、规则、Semi的15种非空信息组合，另保留质量＋时间＋修改幅度；沿用现有多组数候选，并加入连续人员特征和不分型基线。不强行均分，不强行形成ABCD，不把未知人员并成一种真实类型。
特别区分规则执行、空间范围倾向、系统性偏差与几何质量。在目标房间之外形成类别或人员得分，再检验目标房间表现。检查人员差异是否随遮挡、门洞、连通空间等图片特质改变。几何质量和Scope选择不可自动解释为认真/粗心，规则正确性需要独立适用参考。
使用同图真实不同人员构成AA、AB、AAB、AABC、ABCD等可形成组合；同时区分总人数变化与构成变化。人数不足记不可组合。分析具体子类内部稳定、多类合并分歧以及跨房间名单复现。最终收敛判据尚未冻结，仅报告版本明确的探索统计，不新定正式门槛。
输出到工作包 cloud/E；代码限 tools/thesis_main/analysis/image_portrait/cloud_e.py 与对应测试。交付连续/离散方案的证据、各类名单和缺失覆盖、交互结果、组合结果以及不能支持的解释。

补充输入：history/worker_candidate_plan.json保留15组合、质量＋时间＋修改幅度及组数范围；worker_axes_historical.jsonl.gz保留原OSPA等历史口径。worker_memberships_descriptive_only.jsonl.gz仅作旧结果追溯，不得将其全数据拟合标签用于目标房间检验。
