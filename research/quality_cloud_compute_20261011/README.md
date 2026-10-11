# 云端质量计算与盲评小样审阅包

供dot主线程审阅；主线程负责最终研究判断及main发布。本提交以Pro归档64e8b645为父提交，保留此前源归档。不修改原数据、GT、资格或旧分数，不校准最终规则，不批量渲染。

先读 [计算核验报告](reports/COMPUTE_HANDOFF_REPORT.md) 与 [摘要](summaries/)。精简 [审阅小包](artifacts/quality_stage1_2_review_20261010.zip) 含代码、报告、关键当前分量、匹配矩阵和Pro核验摘要；它不是完整复现包。

[完整计算包](artifacts/quality_cloud_compute_review_20261010.zip) 包含本轮离线入口、当前正式loader快照、冻结v1.1、61个精选Pro原件、两份原样MIT许可证、候选结果及历史小样映射。原样Pro3152条当前流水线输出CSV与Pro归档逐字节一致；状态/空值/原因/五方案全部核对。为避免冗余，生成的51MB详细JSONL、8.4MB投影副本及与冻结原件字节相同的11MB分数CSV不再重复打包；本执行器保留、可按入口重算。

[用户八例小样](artifacts/quality_blind_sample_user_20261010.zip) 隐藏Q、方案名和人员；内有原图、中文版比较图、空白表单和离线HTML。X01为同一答案对A/B，题目为“仅 A 可匹配 / 仅 B 可匹配 / 两者均可匹配 / 两者均不匹配 / 无法判断”。B只画底面、顶界待定。八例全部来自历史材料，不称历史未见验证。

[答案映射](artifacts/quality_blind_sample_answer_mapping_20261010.zip) 单独供主线程/研究者使用，包含选择依据、人员/方案数字和留出清单，不随用户小样发出。留出9组/282条；任何建筑缺room_id则整楼合组，已曝光组固定开发。

每个ZIP内含逐文件SHA256清单且CRC核验通过；ZIP自身大小与SHA见 [ARTIFACT_MANIFEST.json](ARTIFACT_MANIFEST.json)。源Pro归档247原件已通过逐文件验证，仍在同一研究分支的quality_pro_source_archive_20261011，不重复搬入本目录。精选包缺原图/PDF/字体/工作簿，不能称其单独复现全部Pro实验。

解压完整计算包到独立目录，依requirements.txt准备运行时，按RUN_COMMANDS.txt复算。如需八例重渲染，把用户ZIP解压到该目录blind_sample/user；代码会用随包真实JPEG回退，不依赖私有原照片路径。正式质量校准和批量盲评仍待主线程结合人工判断；不存在最终阈值或公式选择。

Library批量替换因助手工具列表网络失败未成功，旧Library链接并非此修订版。本研究提交是新的可读取交付渠道。

回执修订：当前用户ZIP已增加浏览器草稿状态、JSON/CSV下载和导入续填；不能保证浏览器自动保存，存储失败会明确提示必须下载。CSV首行为版本标记，第二行为原13字段，后续八例与case_id不变；默认全部回答为空。当前独立答案映射明确C02/C05仅为一般质量观察、禁止惩罚拟合。完整计算包与第一阶段小包保留ceff6990的原字节，内含当时的页面/映射；回执功能以当前用户ZIP和本提交code为准。测试与说明见[回执修订报告](reports/RECEIPT_DELIVERY_FIX_20261011.md)。
