# 36 份整答质量人工评分与研究归档

本批从六张图中选出 36 份完整作答，用一个暂定的 1–5 分整体评价，补足当前质量指标需要的人工证据。**初始人工评分全部为空，完成数为 0；目前尚无最终验证过的整体质量公式或权重。**

## 已上线工作台

[打开36份评分工作台](https://panorama-quality-review.fringnb.chatgpt.site)。v3 已于 2026-10-07 17:23:06 UTC 成功部署，仍仅账户所有者可访问。评分在浏览器本地保存，请导出 JSON 备份，不会自动同步到 GitHub。

42 项源码／数据／应用事件测试通过。真实浏览器访问受私有站点登录门槛阻挡，尚未完成实际浏览器／WebGL视觉验收；部署成功不替代视觉验收。

## 从这里开始

1. [人工评分锚点](RATING_RUBRIC.md)：5 到 1 的用途解释，以及未评分／无法判断的区别
2. [工作台与结果保存](WORKBENCH_AND_RESULTS.md)：逐份判断、保存、导出和接收结果的规则
3. [选样协议](SELECTION_PROTOCOL.md)：六图各六份，24 份目的性对照加 12 份固定种子抽取
4. [当前研究进展](CURRENT_STATUS.md)：哪些计算已经可信复现，整体质量还缺什么证据
5. [来源与复现](PROVENANCE_AND_REPRODUCTION.md)：冻结输入、参考版本、预处理坐标、公开范围与可计算性
6. [已有指标说明](METRICS_REFERENCE.md)：LC、上部参考项与自身三维诊断的定义和限制

## 本轮面板

| 图片 | 现有候选池 | 本轮评分份数 |
|---|---:|---:|
| wc2JMjhGNzB-15 | 24 | 6 |
| 7y3sRwLe3Va-04 | 24 | 6 |
| rPc6DW4iMge-06 | 24 | 6 |
| UwV83HsGsw3-09 | 24 | 6 |
| yqstnuAEVhm-31 | 21 | 6 |
| uNb9QFRL6hY-26 | 18 | 6 |
| 合计 | 135 | 36 |

六图来自六个建筑。原始小面板另有 14 份不属现有候选池的记录，未为本轮改变其资格。36 份不是 36 名不同人员，也不是全体作答的无偏质量样本。具体匿名 ID、排序与哈希随冻结清单保存。

## 小文件归档与恢复

为方便可靠传输，超过 30,000 字节的三个原文件以确定性的 gzip + base64 保存在 `packed/`，每片不超过 20,000 ASCII 字节。这只是存储表示变化，不改变数据、GT、计算定义或前端代码。原路径在恢复后生成，不重复提交。

先在本研究目录运行（仅需 Python 标准库，无网络访问）：

```sh
python restore_packed.py
```

脚本先验证全部分片、原文件大小和 SHA-256，再恢复 `data/frozen_geometry.json`、`data/selection_manifest.json` 和 `frontend/vendor/three.min.js`。重复运行安全；若现有同名文件内容不同会停止，不覆盖本地修改。[分片清单](packed/manifest.json)与[原始工件哈希](provenance/frozen_artifacts.json)可核对恢复结果。之后再运行重放或前端重建命令。

## 冻结文件与重放

- [选样清单分片](packed/data/selection_manifest.json/)（恢复至 `data/selection_manifest.json`）：Q01–Q36 与匿名 R 记录映射、完整候选池、抽取和展示顺序
- [冻结几何分片](packed/data/frozen_geometry.json/)（恢复至 `data/frozen_geometry.json`）：36 份作答、6 份原 GT、2 份人工修订 GT，及必要点位、连接、三维／ERP 派生数据和数值
- [初始空白模板](data/ratings_initial.json)：36 行全空，仅作归档模板；恢复进度请使用工作台自己的 JSON 导出，格式见使用说明
- [纯 Python 重放脚本](replay_public.py)和[原样指标内核](vendor/)：可以核验抽样、几何与当前分项数值
- [几何验证](validation/public_replay_validation.json)与[指标重放](validation/public_metric_replay_validation.json)：公开输入支持的验证范围

数据内容指纹：`491740bec4a8eaa8dc4fb9a2a9741bbbf870fed2a789a220b5b0f72a3ff33ab2`。文件级哈希见[冻结工件清单](provenance/frozen_artifacts.json)。

[工作台前端源码](frontend/README.md)同步归档，可由 [build_frontend_data.py](build_frontend_data.py) 从冻结几何重建浏览器数据；不重复存放数据文件或原图。[技术验收记录](validation/frontend/README.md)说明42项检查及其范围，真实浏览器／WebGL不在该验收覆盖内。

## 已有证据和新结果分开

- [六对历史比较的匿名更正摘要](prior_evidence/pilot_comparisons_summary.json)：保留明确、弱、相当及分项取舍，未换算为本轮 1–5 分
- [最近独立数值审核摘要](prior_evidence/reproduction_summary.json)：24 个输出逐字节复现等验证事实；不等同人工质量有效性认证
- [上游来源收据](provenance/source_receipts.json)：完整原件的角色、大小和 SHA-256；原件未重复放进此精选目录

本轮评分用于探索“实际内容是否足够、已经画出的内容是否准确”。它不按点数、面积或与某版 GT 的相似程度自动加分；也不因完整意图而忽略实际几何问题。

研究目标仍是评价当前作答，并连接人员、图片、构成、人数及融合。现行[统一研究模型](../../docs/thesis_main/研究模型_人员图片与融合不确定性_20261006.md)、[数据说明](../../docs/thesis_main/研究数据说明_来源预处理与用途_20261006.md)和[方法合同](../../docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json)保留；本目录不重定义其资格或覆盖已有研究结果。

## 公开归档边界

此处只含匿名研究 ID、最小冻结几何、数值和研究材料。原图、真实身份映射、原始人审评论／聊天及访问凭证不在本次新增公开内容中。私有工作台承担原图视觉查看；公开几何小包只能复现其声明范围内的选择与数值检查，不能替代原图语义判断。
