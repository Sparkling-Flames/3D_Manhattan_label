# 复现与恢复：人员分类及整体构成 v3

## 1. 输入与研究身份

本轮基准为 GitHub main `324dba44d0a82d9d64a62965f2e549ee05165417`。该 SHA 固定本轮开始时的代码和数据；后来的 main 更新不自动改变本轮输入。原生融合仍使用原冻结预处理、参考绑定、环序、人员资格、票数和评分。`NATIVE_CONTRACT_MAIN_IDENTITY.json` 记录实际导入文件与 main 的对应关系；本轮没有改融合或评分公式。

三个阶段的目录不可互相覆盖：

1. 历史阶段1原工作目录为 `research/workers/personnel_global_composition_20261021/`。这不是 main 中已有的同名目录；最小代码包会保留该旧运行目录，并补入本轮确实依赖的小型历史标签/连续特征。完整端点和事件通过下载索引单独取得。
2. 历史阶段2 n20 在原工作目录的 `continuation_20261021/`。仓库归档位于 `research/workers/personnel_composition_n20_20261021/`，归档索引不能直接当成完整大表。恢复后的文件在本轮 `integration/restored_full_tables/`，保留原阶段身份。
3. 本轮新分类、多人数面板、类别块、用途模型及原图案例位于 `research/workers/personnel_useful_taxonomy_v3_20261021/`。其中 `taxonomy`、`composition`、`utility`、`response`、`evidence` 各自保存输入、参数、结果和完成回执。

原图来自仓库 Release 的原图索引。案例包只保留对应图片/裁切和叠图证据，不包含原图全集。Release CRC、尺寸及本地 SHA 见各图证据回执；没有将本地 SHA 伪称为发布者提供的独立校验值。

## 2. 只读取结果时，需要哪些文件

首选 `HOHONET_全部已保存文件_独立下载目录.csv` 或同名 Markdown。它们包含可直接下载的独立表、ZIP 替代入口、阶段身份和完成回执。完整大表为标准 UTF-8 CSV+gzip；一些文件由多个完整 gzip member 拼接，Python `gzip` 和标准解压工具可连续读取全部内容。

| 需要回答的问题 | 最小输入 |
|---|---|
| 每个人是什么类别、为何未知 | `taxonomy/MANUAL_LABELS_EXPLAINED.csv`、`SEMI_LABELS_EXPLAINED.csv`、`CLASS_DEFINITIONS.csv` |
| 在目标楼评价用哪个标签 | `taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz`；使用 method、condition、heldout_building、worker_id 联合键 |
| 一个事件具体换了谁、怎样变化 | `composition/delivery/events/*EVENT_INDEX.csv.gz` 定位完整事件分片；保留全部端点分项和失败 |
| 任意已算团队的原生输出 | 合并端点标量/几何直接表，或对应批次 ZIP 内的 `ENDPOINT_SCALARS.csv.gz`、`ENDPOINT_GEOMETRY.csv.gz` |
| 配置是否穷尽 | `composition/configuration_union/` 与 all-n 规模账；按真实成员域去重，不把别名当独立配置 |
| 类别是否有实际质量—时间用途 | `utility/*FINDINGS_ZH.md`、策略逐面板表、完整选择概率及实际端点 |
| 粗细和连续表示提供什么 | `response/{manual,semi}/{geometry_common,qt_common}/` 的逐面板分解、楼外预测与系数 |
| 为什么局部票数或位置改变 | `evidence/fusion_pa4_18/`、`evidence/fusion_7y13/` 的票账、精确成员及原图叠图 |

每个分片有独立表头。合并 CSV 时只保留一个表头，按 event_id 或 team_key 查重；不同方法/层级可能引用同一实际团队，不能按事件行数统计新融合次数。

## 3. 从交付表恢复可重放的端点

最终精简包不包含重复 runtime 缓存。已交付的每批请求、标量和几何足以恢复事件脚本需要的输入。

原生批次 ZIP 的首级目录为 `batches/`，应解压到本轮 `composition/` 目录。分类与用途包的首级为 `taxonomy/`、`utility/`，应解压到本轮根目录；Semi响应包首级直接为 `semi/`，应解压到本轮 `response/`，Manual响应包已含 `response/` 前缀，应解压到本轮根。核心代码包以 `research/` 开头，解压到仓库根目录。逐包目的目录另存于 `PACKAGE_RESTORE_DESTINATIONS.csv`。较早冻结检查点保留阶段身份，不要覆盖后来已完成的结果；优先恢复最终分类/用途包和原生完成批次，再解压核心代码。然后从仓库根目录执行：

截至 2026-10-23，Manual 与 Semi 的完整成员面板响应包已按上述目的地恢复至 `research/workers/personnel_useful_taxonomy_v3_20261021/`；阅读其结果和校验范围见 [`response/README.md`](../../../personnel_useful_taxonomy_v3_20261021/response/README.md)。

```bash
python3 research/workers/personnel_useful_taxonomy_v3_20261021/integration/restore_v3_runtime_from_tables.py \
  --batch-dir research/workers/personnel_useful_taxonomy_v3_20261021/composition/batches/batch_017 \
  --output research/workers/personnel_useful_taxonomy_v3_20261021/composition/runtime/batch_017
```

对需要重放的批次分别运行。恢复器先校验冻结 SHA、EOF、字段宽度、精确团队键全集和标量/几何的一致性，再逐池原子写出 JSON。已存在的输出只在值一致时通过，不覆盖冲突文件。它不调用融合或评分。`RESTORE_SMOKE_CHECK.json` 记录对第17批全部2,772端点的逐值比较；输出成员、几何、分项、票数、参考和失败状态一致。

CSV 无法区分原 JSON 中“字段不存在”与“明确为空”，匹配索引为空时也无法恢复原作者使用了 null 还是空列表。恢复器保留同一已知信息与数值；这不是缺失值填零。相关限制写在 schema 和恢复回执中。

历史第一阶段完整几何另有 `phase1_geometry_recovery/README_ZH.md` 和恢复代码，291,904 个键与完整标量一致。历史 n20 的144,642个端点及全部 Manual/Semi 事件已有独立恢复回执；读取这些完整表不需要再次融合旧团队。

## 4. 分类与原答检查

`taxonomy/INPUTS_AND_CHECKSUMS.csv` 指向 main 中的原逐答结构表达及画像记录索引。首先恢复仓库原输入，再按本轮保存的代码运行。核心脚本为：

- `discover_behavior_classes.py`、`discover_joint_qt.py`：分别形成行为类、联合类；输入域等权，类别数按实际最小类容量检查。
- `extend_candidate_range.py`、`check_class_capacity.py`：登记从初始计算范围扩展到实际容量上界的全部候选，不把类数变体当域组合。
- `finalize_selection.py`：固定内侧选型与最终楼外/全数据标签。精确标签 SHA 在 `LABEL_FREEZE.json`。
- `evaluate_raw_behavior.py`、`check_raw_geometric_similarity.py`：原答表达、同点数几何和连续对照。
- `export_support_and_definitions.py`、`describe_classes.py`：成员支持、未知原因、辅助域和中文解释。

已有内侧损失和冻结标签可以直接复用，不必为了复现报告重新运行所有候选。全数据 ALL 标签只用于最终成员描述，目标建筑实验必须使用该建筑对应的楼外标签。

旧语义窗口复用脚本支持显式源路径：

```bash
python3 research/workers/personnel_useful_taxonomy_v3_20261021/evidence/reuse_semantic_opportunities.py \
  --source research/workers/personnel_taxonomy_20261021/evidence/local_opportunities.csv
```

输入 SHA 必须与保存的 `PROVENANCE.json` 一致。它只连接新的楼外类别，不重裁定语义或重评暂停 GT。

## 5. 实际团队、事件与用途模型

原生团队请求已冻结；复核统计时直接使用完成端点。只有缺少某个登记端点且确需补算时，才运行 `composition/run_multin_batches.py run --batch <批次> --jobs 4`。该路径遵守原团队集合键，先复用已有精确集合，失败也写入完成结果。

匹配事件脚本为 `composition/evaluate_matched_events.py`，分别运行 `panel`、`large`、`pure`；纯块 AC 有独立评价脚本。同构成 B 与改构成 C 均相对相同 A、共同背景、n 和实际 m 比较。B/C 自身净换人数另列，不用其净差冒充登记的 m。`consolidate_deliverables.py` 保存完整事件/端点及定位索引；无需把全部原生 runtime 再打包。

用途模型完整命令、冻结目标、训练身份、并列最优成员概率以及逐策略风险定义见 `utility/REPRODUCE_UTILITY_ZH.md`。该目录明确区分旧团队训练、本轮其它建筑训练和 F01 有限域训练；相同候选集合 SHA 才能作跨方法直接比较。目标建筑的结果不进入其训练或选队，所有实际选择完成后才读取该建筑端点评价。

主用途模型只用其它建筑的新面板训练，不与历史旧团队混训。`historical_only` 的精确固定抽样输入另以 `TRAINING_ENDPOINTS.csv.gz` 独立提供，恢复到本轮 `utility/` 即可；它是每池×人数最多256个、按成员键筛选的125,462条必要训练输入，不是全部历史运行缓存。对应 `TRAINING_SOURCE_INDEX.csv` 和 `TRAINING_CACHE_RECEIPT.json` 记录来源与SHA。直接使用该冻结输入可避免本地未恢复全部历史批次时无意改变训练集合。完整旧标量仍可按源索引重建并校验。

完整成员面板的统计合同保存在 `response/analyze_responses.py`。计算时使用已通过逐值等价核对的执行器，按相同缺失掩码复用矩阵乘积，不改变特征、权重、ridge或指标：

```bash
python3 research/workers/personnel_useful_taxonomy_v3_20261021/response/analyze_responses.py derive
python3 research/workers/personnel_useful_taxonomy_v3_20261021/integration/taxonomy_adoption_synthesis/run_response_fast.py run --condition manual --domain geometry_common --out research/workers/personnel_useful_taxonomy_v3_20261021/response/manual/geometry_common
python3 research/workers/personnel_useful_taxonomy_v3_20261021/integration/taxonomy_adoption_synthesis/run_response_fast.py run --condition manual --domain qt_common --out research/workers/personnel_useful_taxonomy_v3_20261021/response/manual/qt_common
```

Semi 用相同两域分别运行。`derive` 只从已保存的几何派生表达代理；不会重新融合。主响应的加载器只取同一批主面板表达表，避免把后来补充的F01/大块重复端点混入主支持。每楼单独存完成回执，原执行器已完成且统计代码合同一致的楼直接恢复。两种条件的模型、系数、预测和分解等价回执在 `integration/taxonomy_adoption_synthesis/fast_validation/`。类别人数的二阶项、连续特征的对应二阶项和人数交互均按保存的模型修订登记，不是看目标楼成绩后增加特征。

## 6. 参数、失败与保存规则

软件版本、分类参数、原生输入和标签 hash 均随各专题小表保存。主结果以 B8L2 为准，D10 为敏感性；完整质量分项、顶/底 ERP 坐标、底面及高度代理、结构召回、时间和失败并行报告。原答整份9°/12°分簇、逐点评价5°/9°与融合内部 `WORKING_GAP=7.5` 的保序匹配跳点代价是不同用途，未互相替换。

实际总记录时间为秒，来源保留在端点及用途表中；主质量—时间比较只使用全候选具有完整、兼容来源的面板。它不等于并行工期，也不是预测误差的节省比例。scope回答倾向与裁定正确率不同，错误初始化机会未知、时间未知、无可替换成员均保留未知或不可估计。

所有正式新表采用完成一批保存一批：先写临时文件，核对行宽、主键全集和 gzip EOF 后再发布。需要较大单表时使用多个已完整压缩的 gzip member，避免流式尾部丢失。文件索引只收录已成功保存的文件，临时/partial/superseded 文件不属于交付。

本轮没有枚举所有人员排列及等价终点；顺序只在明确登记的人数路径中展开。未计算的全人员池集合仍按精确整数记入覆盖账，不会被条件面板或构成覆盖率替代。
