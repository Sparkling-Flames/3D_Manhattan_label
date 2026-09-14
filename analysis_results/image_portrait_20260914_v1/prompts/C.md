你在HOHONET仓库执行“图片画像”数值分析。使用分支 codex/image-portrait-20260914，以及仓库根目录下 analysis_results/image_portrait_20260914_v1/ 的工作包。

先读 AGENTS.md、工作包 README、evaluation/metrics.md、evaluation/config.json、evaluation/folds.jsonl.gz 和运行状态。运行 python -m tools.thesis_main.analysis.image_portrait.build_bundle --check，只检查工作包，不在云端重建原始数据包。
这是探索研究，不修改正式 Paper A 合同、原始导出、人工原文或采集安排。

不查看原始图片，不调用视觉模型，不下载权重。只能依据提供的数值、几何、文字及来源记录分析。需要视觉判断的事项输出 image_id、具体疑问和触发依据，交回本地核查。

648图是画像覆盖，不等于648图都有真人结果。保留W011历史；W019/W026排除当前主分析。Manual与Semi分开；缺失、无效、低人数、观察内持续变化分别记录。不复制人员，不把重采样当独立样本，不把模型输出当GT。

所有标准化、降维、选层、调参及人员分型只使用当前训练侧。使用工作包固定的评价划分；不能挑成功划分或删除不利结果。evaluation/room_components.jsonl 是支持关系分析组件，不是已去重物理房间普查；待定关系隔离规则见 metrics.md。
输入不足时给出覆盖表和具体缺口，不能补造数据。特别检查模型每图每phase状态及required key，不能把partial文件看作完整输出。未提取模型按运行记录区分待运行、受阻及失败；DINOv3当前为作者拒绝访问、未运行；可独立的已有数据分析继续，不能自行替换模型。

仅修改自己路线的分析脚本、测试及输出目录。交付中文报告、逐图结果、覆盖与失败表、可运行命令和必要测试；区分论文结论、本轮实测和解释性假设。不要修改其他路线或汇总报告。

执行路线C：回答哪些模型层及汇聚方式更适合预测人类标注结果。

保留source_split分层敏感性：冻结布局模型使用过MP3D训练数据，不等于648图全是视觉模型未见样本；具体训练成员未核实则标未知。透视面local16是各面图像x条带，不能直接等同ERP方位扇区。

比较工作包预先列出的所有候选层，重点包括：HoHoNet各阶段与旧均值；Bi范围引导前后；uLayout压缩与Transformer输出；DINOv3第3、6、9、11、12层patch及最后层CLS；DA3已导出的中间表征。
分别比较全局与局部汇聚、DINO全景与透视投影。使用统一简单近邻和正则化预测模型，控制覆盖及降维条件。区分模型架构差异、层差异、投影差异与新增输入信息的影响。旧d_t只使用来源可核实的版本，不能用其他risk字段冒名替代；包含目标标注信息则不能作为纯图像输入。
外层留出结果用于评价，内层训练资料用于选层和参数。既报告固定候选层，也报告内层选层方案，不能只报告总体最佳层。选择规则/参数见 evaluation/config.json 与 metrics.md。
输出到工作包 cloud/C；代码限 tools/thesis_main/analysis/image_portrait/cloud_c.py 与对应测试。结论按预测目标分别给出，允许不存在统一最优层；模型输出缺失不能被表示为零分或零特征。

补充输入：先读 history/coverage.json、historical_feature_plan.json、d_model_feat.jsonl；历史特征和1647参考缓存已打包。原值/CPU复算值分别保留。legacy_dt_rule.json只提供规则，不代表有已实现d_t；当前缺少已核实Calibration参考池及旧d_t分数，不得补造。历史冻结参考投影与本轮训练侧PCA分开比较。
