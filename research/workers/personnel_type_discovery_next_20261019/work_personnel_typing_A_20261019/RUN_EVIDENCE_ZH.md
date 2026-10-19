# Part A 可读运行证据

本文件索引已实际完成的计算、核查与未完成事项。它不是根据计划自动生成的“成功”说明。

## 已完成

| 阶段 | 实际输入/输出 | 独立检查 | 证据路径 |
|---|---|---|---|
| 固定 main 与归档恢复 | main dafa73ac…；科学源 82c6164b…；824 源＋519 核心 | 1,343 项 SHA 一致；原兄弟目录结构 | `recovered/BOOTSTRAP_RECEIPT.json`；`reproducibility/PACKAGING_DATA_MANIFEST.json` |
| 当前输入审计 | 10,439 唯一记录；7,302 Q；5,719 普通 Manual；60 Q 画像/62 库存 ID | 质量/几何/行为/时间资格分母分别重数；v1 固定 1,911 发布差值≤4e−15 | `input/CURRENT_INPUT_AUDIT.json` |
| 事件注册 | 58,882 端点请求，58,679 唯一团队，286,666 替换事件 | 固定背景、换入身份、参考、人数、随机种子；新增面板不得训练 | `events/DESIGN.json`；`events/REQUESTS.json.gz` |
| 原生融合/评分 | 100 试跑＋58,579 后续新状态；后续用时约 907.8 秒 | 0 执行异常；904 唯一不完整团队仍保留；源函数未改 | `events/FULL_RUN_RECEIPT.json`；`assessment/REPORT_TABLE_RECEIPT.json` |
| 事件逐分项检查 | 286,666 事件/175 图/22 楼 | 唯一键、同 k−1 背景、嵌套链、上下距离、阈值、失败；963 保留旧事件最大差 5.68e−14 | `events/EVENT_VERIFICATION_RECEIPT.json` |
| 历史画像 | 69 训练子集×60 人×B8/D10 | 全量原函数 parity；另独立重拟合排除 yqstnuAEVhm 的 116 数值列，最大差 1.14e−13 | `forward/FORWARD_BOUNDARY_CHECKS.json`；`input/ROOT_FEATURE_REFIT_PARITY.json` |
| 正向分区 | 28 候选；FULL＋22 外折；内层各自重建画像与类 | 目标楼污染不改变历史；全部候选/1SE选择/缺失/域距离保留 | `forward/CLASS_EXPORT_COMPLETE.json`；`forward/FINAL_EXPORT_COMPLETE.json` |
| 反向分区 | 64 候选；FULL＋22 外折；162,840 人员关系、186,300 类别行 | 未用连通性造大类；新背景仅评价；176 gzip 完整 | `reverse/FINAL_OUTPUT_INTEGRITY.json`；`reverse/TRAINING_ISOLATION_RECEIPT.json` |
| 共同评价 | 同事件附全部方法，未知回到同 k/难度基线 | 19 个选定别名共 5,446,654 概率，根任务独立校准最大差 3.33e−16 | `assessment/INDEPENDENT_ALIAS_PREDICTION_PARITY.json` |
| 敏感性 | Q接近、来源、规则、D10、固定K消融、直接房组、重复请求、四节点共同图 | 不重新选类或阈值；不同分母单列 | `assessment/*RECEIPT.json`；各逐事件和摘要表 |
| 展示页 | 177 图池/5,719 标注、708 历史局部分区；7 案例/14 团队 | 230 jsdom/Canvas检查通过；7 原图校验；实际看过5案例13画布 | `presentation/VIEWER_BUILD_RECEIPT.json`；`presentation/qa/VIEWER_QA.json`；`presentation/VISUAL_REVIEW.json` |
| 统一入口 | aggregate/refit/fresh 三层，8/24/26 步 | 关键 SHA/依赖闭包/表头/语法；已有目录哨兵保护；没有为测编排器重跑昂贵全管线 | `reproducibility/ENTRY_POINT_CHECKS.json`；`reproducibility/REPLAY_ENTRY_SMOKE.json` |

## 工程问题与恢复

一次全量宽 CSV 解析因内存不足退出 137，之后按块读取；未将失败进程的部分数据用于结果。少数 gzip 导出有不完整尾部，已从冻结的完整特征、类别、校准或原事件重建，核对可读前缀、最终 CRC/行数/唯一键。原子导出使用 UUID 临时文件、读回校验与 rename；不推测损坏底层原因。失败临时文件可以不放入精简包，错误/恢复收据保留。

原事件的链字段为 `chain_id`，根汇总首次保留清单漏写这个名字，链分析在出表前停止。修复为原字段直传并设置同值 `nested_chain_id`，不重新推导身份、不改变其它事件数据；最终四节点 3,936 链/164 图/15,744 事件通过检查。证据：`assessment/CHAIN_FIELD_MAPPING_REPAIR.json`。

反向两份预测修复可读前缀共 1,300,000 行完全一致，未重拟合或重选。根汇总和正向导出修复也只涉及发布/字段映射，科学选择没有改变。原始失败、恢复及最终检查分别保留，不能将一次成功入口检查误写成完整采集复现。

## 未完成或不在 Part A 内

- 没有从原始导出重新审核全部采集、参考与人工标记；本轮消费和重放已审计证据。
- 没有 Dot 全部 DESIGN/逐曲线/完整团队状态，未声称完成 Dot 全套复现。
- 没有新 Semi 525 份初始几何；修改/得分提高不等于已确认纠正。
- 没有通用 scope 金标；93 个历史机会全部有限 in-scope，不能推出误收率。
- 没有完整整数 k 曲线、相邻奇偶全实验和全部排列；Part A 算的是 8/12/16/24 四节点嵌套背景，Part B 独立负责机制补充。
- 没有新跑完整比例组合最优化；固定背景最后一席不能包装为最优团队。
- 没有两张缺失原图的视觉审查，也没有整套原图的全分辨率审核。7 张案例虽已下载，实际打开检查仅5张对应科学画布。
- 没有真实浏览器布局截图验证；浏览器下载受阻，已完成 jsdom/Canvas 功能检查。
- 没有修改正式人员等级、冻结几何、参考、质量资格、评分与融合规则，没有推送 GitHub main。

## 独立接收应先查什么

将三 ZIP 解压到同一父目录，运行统一入口的默认验证或 `--deep`。对科学结论优先查相同 `event_id` 的已选方法预测、同背景分项差、unknown/失败分母，再看来源内和 Q接近。类别 FULL 描述不得替换外楼预测名单。重要边界和建议见 `REPORT_ZH.md`，字段意义见 `reproducibility/EXCHANGE_FIELD_CONTRACT.json`。
