# Manual / Semi 完整成员面板响应结果

本目录补齐 Manual 与 Semi 的完整有限成员面板响应结果，来源为两个用户提供的研究交付包：

- `HOHONET_v3_Manual_粗细类与连续特征完整面板结果_20261021.zip`：Manual 完整面板、响应摘要、模型与分解表；同时包含分类采用整合的响应复核回执。
- `HOHONET_v3_Semi_粗细类与连续特征完整面板结果_20261021.zip`：Semi 几何共同域和 Q/T 共同域的逐面板预测、分解、拟合模型及支持表。

Manual 的结果保留在 `manual/`；Semi 原包根目录下的文件放在 `response/`，其条件结果保留在 `semi/`。两个包共用的 `analyze_responses.py`、`DESIGN_FROZEN_ZH.md` 和 `MODEL_REPRESENTATION_AMENDMENT.json` 在两个原包中逐字节相同，只保存一份。各包清单校验了列出的文件字节数和 SHA-256；ZIP 成员 CRC 均通过。

这些结果复用已保存的真实 v2 面板，没有新增融合、评分或类别拟合。本次只补齐原始结果明细和复现材料，没有改变研究采用结论。详见 [Manual结果说明](MANUAL_RESPONSE_FINDINGS_ZH.md)、[Semi阶段回执](SEMI_RESPONSE_CHECKPOINT_ZH.md) 及[整合报告的复现与恢复说明](../../personnel_v3_20261021/integrated_report/integration/REPRODUCE_AND_RECOVER_ZH.md)。
