# n20 同构成／改构成匹配对照：复现与恢复

## 研究对象和阶段身份

本阶段继续使用 `personnel_global_composition_20261021` 中既有人员标签、楼外训练、资格与冻结终点评分／融合。新增的是：在各方法自己的 n=20 预登记有限成员面板内，枚举全部符合共同背景与相同替换规模的三团队对照，再读取已有终点比较。没有重跑人员分型搜索，也没有新增融合或评分。

Manual 完整设计为 269,814 个事件、164 个图片池、22 栋建筑；Semi 为 1,517 个事件。A/B/C 是三支实际团队：A 为锚点，B 保持完整类别人数向量，C 改变该向量；并要求 A∩B=A∩C=S、n=20、m_AB=m_AC≥4。人员类别数没有三类上限。B/C 的重叠及实际替换人数另列，不能自动把 B/C 当成相同规模的对照。

这里的完整枚举仅指每法已经登记的有限成员集合面板内的全部合法三元组；上一阶段每个类别人数配置至多登记 3 队。它没有穷举全人口的所有成员集合或所有加入顺序。粗层与细层复用同家族相同团队面板，A2 使用自己的面板；不会把不同方法拼成统一的已验证层级。候选和类别标签已经参与过探索，本阶段不宣称全新盲测。

## 输入合同

输入位于研究目录下：

- `continuation_20261021/next_stage/candidate_n20/CONFIG_MEMBERSHIP.csv.gz`：144,666 个方法／配置／团队引用；SHA256 `dafab3fad16939065cee4f2b4acb0247842eaa55f92ed2cbf3ce3b5d6846c2c5`。
- 同目录 `ENDPOINT_REQUESTS.json.gz`：144,642 个按实际成员集合去重的 n20 请求；SHA256 `b6814db7652b6e53a2129d2345fd0d49aedc88049f1b4a6dfe6dc8d83ccc2169`。
- `composition/FROZEN_LABELS.csv`：各方法／条件／留出建筑的实际人员标签；SHA256 `5b1832776fd0a4fe393fc30157fd07dc4b8a99f944e0bb5599933d12cfa39359`。
- `multivariate/continuous_features_lobo.csv.gz`：仅供结果阶段的楼外历史 Q、T、低尾、困难适应解释；不用于匹配事件选择。
- `continuation_20261021/next_stage/batches/`：复用终点和六批新增 n20 终点标量／几何。只读取有 `COMPLETION.json` 的完整批次。各文件具体哈希在 `INDEX_RECEIPT.json`、结果批内的不可变快照及 Semi 的 `RESULT_RECEIPT.json` 中。

B8L2 为主、D10 为敏感性，保持原始预处理、参考绑定、环序和融合门槛。配对几何直接调用既有 `summarize_grid.pair_metrics` 与相应角点距离合同。原答 9°／12°分簇阈值没有在本实验中更改；联合稳定的结构角差≤3°是结果判据，不是原答分簇或融合内部对应参数。

## 运行顺序

以下命令在研究目录中运行；脚本所在目录为 `continuation_20261021/n20_abc/`。

```bash
python continuation_20261021/n20_abc/discover_n20_abc.py --condition semi
python continuation_20261021/n20_abc/discover_n20_abc.py --condition manual
python continuation_20261021/n20_abc/evaluate_n20_abc.py --condition semi
python continuation_20261021/n20_abc/evaluate_n20_checkpointed.py --condition manual --prepare-only
python continuation_20261021/n20_abc/evaluate_n20_checkpointed.py --condition manual --index-only
python continuation_20261021/n20_abc/evaluate_n20_checkpointed.py --condition manual --read-only-index
python continuation_20261021/n20_abc/summarize_n20_checkpointed.py --condition manual
```

Semi 结果的 697 字段表头同时作为 Manual 完整导出的固定 schema；697 字段定义另见 `N20_MATCHED_EVENT_FIELD_DICTIONARY.csv`。需要并行时，准备和终点索引只运行一次，随后以固定 `--partition-count 4` 和各不相同的 `--partition-index 0/1/2/3` 启动四个只读索引进程。所有分区来自冻结 `POOL_PAIR_SCALE.csv` 中完整 164 池的配对数，和哪些终点暂时可用无关；具体名单见 `FIXED_FOUR_PARTITION_ASSIGNMENT.csv`。

`endpoint_index.sqlite` 是可重建的临时查询索引，不随结果包交付。每池仅加载相关团队，几何配对缓存完成该池后释放。每片最多 20,000 个事件；本次实际 164 池各占一片。汇总以单片读取，不创建 269,814×697 的全局 DataFrame。

## 检查点和异常恢复

一个片段只有同时具备完整事件文件和成功的 `part_XXXX_RECEIPT.json` 才被视为完成。完成条件包括：固定表头和 697 列列宽、预定行数、唯一事件 ID、与设计中相应 ID 的顺序完全一致，以及 SHA256。恢复运行跳过已完成片，只计算缺少成功 receipt 的片，不重算融合。

一次初始并行尝试出现 gzip 的 EOF 读回异常，未完成的临时片没有成功 receipt，也没有发布。对应首个未提交片为 `part_0092`，pa4-48 的 7,274 个事件。其余当时完成的 148 片 SHA256 全部复核一致；随后顺序恢复余下 16 片，包括异常片的完整 7,274 行。异常具体原因未确认，没有归因磁盘故障或外部中断。完整记录在 `CHECKPOINT_EXCEPTION_AND_RECOVERY.json`。

后续输出使用 `atomic_checkpoint_io.py`：临时路径包含进程 PID 和纳秒唯一号，关闭文本与 gzip writer、同步文件后才读回检查，验证通过后才原子替换最终路径。若失败，保留具体阶段、唯一临时路径、字节数、异常和完整回溯。该加固不改变任何实验分数。曾启动的恢复进程使用此前已经导入的写函数，其中每片同样通过了完整读回验证；记录未将所有历史写入冒称为新函数完成。

打包通过 `freeze_n20_results.py`，以完整建筑或多栋小建筑为一批。只有 ZIP 完整性检查和逐文件哈希通过后产生 `BATCH_XXX_ZIP_RECEIPT.json`，才将该批登记为封存。孤立 manifest 或 `.pending` 文件不表示已完成。已交付包不再修改，后续批不重复之前建筑。

## 统计与阅读

完整事件表保存三个终点原始标量、质量各分项方向差、绝对差、失败、时间来源、实际成员、所有几何距离。`same_` 是 B−A，`cross_` 是 C−A，`net_` 是 C−B；配对几何用 `within_`、`cross_`、`net_`。缺失不补零。原生失败留在联合稳定和失败风险分母中，无法评分的质量变化另记不可估计。

汇总依次做事件→图片池→图片→建筑平均，最终建筑等权；每个指标分别记录可用事件和建筑数。细类另列“父类构成不变”的实际块替换，来源人数匹配、历史 Q 匹配是总作用后的辅助检查。记录每个 m 的响应，不把不同 m 混成同规模实验。

尾部表提供池内方向差 q05／中位数／q95、绝对差及几何差尾部；跨建筑汇总是池内分位数的建筑等权均值，不冒称总体成员宇宙的无条件分位数。>5、>10 分损失风险和原生失败分开保留。建筑 bootstrap 区间为探索后的描述性检查，不将几万相关事件当作独立样本量。
