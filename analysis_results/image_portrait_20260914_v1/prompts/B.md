你在HOHONET仓库执行“图片画像”数值分析。使用分支 codex/image-portrait-20260914，以及仓库根目录下 analysis_results/image_portrait_20260914_v1/ 的工作包。

先读 AGENTS.md、工作包 README、evaluation/metrics.md、evaluation/config.json、evaluation/folds.jsonl.gz 和运行状态。运行 python -m tools.thesis_main.analysis.image_portrait.build_bundle --check，只检查工作包，不在云端重建原始数据包。
这是探索研究，不修改正式 Paper A 合同、原始导出、人工原文或采集安排。

不查看原始图片，不调用视觉模型，不下载权重。只能依据提供的数值、几何、文字及来源记录分析。需要视觉判断的事项输出 image_id、具体疑问和触发依据，交回本地核查。

648图是画像覆盖，不等于648图都有真人结果。保留W011历史；W019/W026排除当前主分析。Manual与Semi分开；缺失、无效、低人数、观察内持续变化分别记录。不复制人员，不把重采样当独立样本，不把模型输出当GT。

所有标准化、降维、选层、调参及人员分型只使用当前训练侧。使用工作包固定的评价划分；不能挑成功划分或删除不利结果。evaluation/room_components.jsonl 是支持关系分析组件，不是已去重物理房间普查；待定关系隔离规则见 metrics.md。
输入不足时给出覆盖表和具体缺口，不能补造数据。特别检查模型每图每phase状态及required key，不能把partial文件看作完整输出。未提取模型明确pending；可独立的已有数据分析继续，不能自行替换模型。

仅修改自己路线的分析脚本、测试及输出目录。交付中文报告、逐图结果、覆盖与失败表、可运行命令和必要测试；区分论文结论、本轮实测和解释性假设。不要修改其他路线或汇总报告。

执行路线B：检验模型反馈能否形成有用的图片画像。

uLayout官方训练忽略第二返回的corner logits，不能把这些原始输出当作已训练角点置信或拓扑证据；它只参加有预测上下边界支持的比较。按metadata/images.jsonl的source_split另报敏感性；模型使用过MP3D训练数据可能影响表现，不能假定648图对每个视觉模型均为未见样本。

比较HoHoNet、Bi-Layout、uLayout的结构输出、局部几何差异和旋转敏感性。Bi分别分析Fc、两种Fg、双头输出；共享的静态Embedding不当图片特征。区分几何位移、点数/拓扑变化、范围变化及模型无效输出。
系统检查“模型差异小/大 × 人员分歧小/大”的四种情况，连续关联优先，展示分位界限只能训练侧确定。比较单模型、模型组合及移除一个模型后的结果，检查是否依赖某个模型。不把多个模型的一致视为独立投票，也不用GT选择最优预测头。
历史Semi另分析初始预测、修改方向和净改善；使用 human/semi_initializations.jsonl.gz 核对当时实际初始化，不用本轮新预测替代历史初始化。初始化来源的synthetic/natural和参考依赖单列；不将修改幅度直接解释为难度或认真程度，不作未经设计支持的因果结论。
输出到工作包 cloud/B；代码限 tools/thesis_main/analysis/image_portrait/cloud_b.py 与对应测试。交付哪些反馈有效、失效边界，以及数值筛出的关键反例。
