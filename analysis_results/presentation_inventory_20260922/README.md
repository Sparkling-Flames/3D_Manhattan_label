# 导师展示资产盘点（2026-09-22）

本目录为展示供数与讲解依据，不改变研究方法、原始标注、人员资格或模型。模型输出、参考GT与真人作答是不同对象，不合计成一个“数据量”。

后续[展示完整性复核](展示完整性复核_20260922.md)登记人员分类、子类稳定、组成、同房起点和同场景等遗漏的补全，以及当前与历史结果的版本隔离、数值核对和视觉验收限制。

## 实际覆盖

| 对象 | 当前数量 | 范围与核查 |
|---|---:|---|
| 已纳入人工作答 | 3019份、259图、25人、22建筑 | 终审记录重新计数，与SUMMARY一致 |
| Manual | 2265份、232图、25人、22建筑 | 原条件manual |
| OOS | 216份、9图、24人、6建筑 | 原条件oos，保留单列 |
| Semi | 538份、43图、24人、12建筑 | 原条件semi；530份可上下绑定，43图 |
| 当前无辅助预测视图 | 2444份、240图、25人、22建筑 | 不与含Semi的总表混用 |
| 模型图片池 | 648图 | valid190＋test458；当前259张人工图均在内 |
| 公共GT原目录 | 2295图 | train1647＋valid190＋test458；259/259人工图、240/240预测图覆盖 |
| 公共GT no_occ目录版本 | 2295图 | 单列另一目录版本；不能计成额外2295张独立图片 |
| HoHoNet ep300布局重放 | 648图 | TXT逐份有限坐标、偶数点检查，不证明历史实际初始化相同 |
| Bi历史双头清单 | 648图，status=ok为646 | 两头是同一模型；normal覆盖人工257/259、预测238/240 |
| Bi历史每头坐标 | 各647图通过最小数值检查 | 每头各一张只有两个端点；此检查不是完整布局或语义有效性判据 |
| HoHoNet原始特征 | 648图×4相位＝2592文件 | 全文件NPZ键集合/存在性核对 |
| Bi原始特征 | 648图×4相位＝2592文件 | 同上；两头共享模型 |
| uLayout边界与特征 | 648图 | 单文件包含4相位；没有可直接当官方预测角点的输出 |
| DINOv3特征 | 648图 | 全景＋六面、5个候选层patch与最后CLS；图像表征，不是布局答案 |
| DA3单图深度与特征 | 648图 | 六面单独推理，4个完整候选层及深度/置信/相机 |
| DA3同房辅助 | 316对资产 | 当前核对文件数；历史记录指出相机一致性问题，不是已验证重建 |

五类模型原始特征都与当前259图人工作答、240图预测集完整关联。归档模型包也逐图核对git文件清单，覆盖各648图。它们的历史完整数值验收与本次文件结构核查分开，不能把本次说成重新执行所有模型或逐张人工验收。

## 文件接口

- `human_coverage.json`：conditions为原条件计数；condition_image_ids可联接图片；current_views沿用原SUMMARY各研究口径。
- `asset_coverage.json`：`assets`逐项给出asset、source、validation、image_ids，以及pool_images/648、human_images/259、prediction_images/240和各自缺失名单。`available_images`为该版本资产的唯一图片数，不一定等于模型池交集。原始特征另含files、expected_keys、problems及不完整相位名单。`auxiliary_pairs`以对为单位，不并入images。
- `numeric_file_audit.json`：实际TXT路径、图片ID、数值检查和点数；失败不静默丢失。
- `semi_descriptive.json`：43图当前完整链接25.6px的N、簇数、单人簇占比、最大簇占比；25张共同可计算图片的Manual/Semi并列。未匹配人员、人数和阶段，不能直接估计辅助因果效果；这些指标不是正确率。
- `historical_README.md`、`historical_output_coverage.json`、`historical_local_validation.json`：从`codex/image-portrait-20260914`只读保存的历史来源，原文保留。旧研究建议/任务不作为本轮执行指令。

DINOv3、DA3、uLayout的归档每图有features/geometry两个NPZ，按二者齐备计算图片覆盖。DINO的geometry命名是包格式，不将它解释为独立深度模型。

## 验证与边界

复算：`python -X utf8 -B -m tools.thesis_main.analysis.audit_presentation_inventory_20260922`。

检查：`python -m pytest tests/test_audit_presentation_inventory_20260922.py -q`，1项通过，检查图片交集及缺失分母。实际执行完成全部TXT数值检查、各原始特征文件结构检查、逐图关联及SUMMARY一致性断言。未读取全部数十GB高维张量进行新全量有限值验证，未推理、训练或评估新的预测模型。历史模型训练成员关系也未重新核验。

资产覆盖不等于质量评价已完成；同一GT的范围适用性、模型版本与Semi真实初始化一致性仍须逐任务核对。本文只登记供数，不新增GT变量或用模型取代真人。
