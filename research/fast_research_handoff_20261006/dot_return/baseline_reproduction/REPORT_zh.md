# 2026-10-06 新到交接包：108状态独立复算与来源审计

## 结论

9图×3门限×4路线的**108个状态全部成功运行**。与交接包 `baselines.json` 比较，**53个状态解析后完全相等；55个状态仅有93处浮点尾数差异，最大绝对误差1.7763568394002505×10⁻¹⁵**。不存在类型、键、长度、整数、布尔、字符串、状态、成员或顺序差异，候选中心坐标也完全相等。因此可以确认本环境下的离散算法语义一致、数值在机器精度范围内一致；不能称为完整解析对象精确相等，也不能照抄原 README 的 `actual == expected` 断言为通过。

本次使用解压包自身代码，不假定它等于旧 GitHub main 或上一份结构原型。交接包声明包含本地未提交修订。此前旧包的36个端点状态不替代本次108个四路线状态。

## 一条复算命令

在安装 `requirements-audit.txt` 所列依赖的 Python 3.12 环境运行：

```bash
bash run_replay.sh /绝对路径/新交接包 /绝对路径/新的输出目录
```

底层等价命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python -B reproduce.py --source /绝对路径/新交接包 --out /绝对路径/新的输出目录
```

脚本按 README 的顺序，逐图调用 `build_routes(records, threshold)`，门限固定 `[5,9,12]`，不改变来源代码或输入。所有输出进入独立目录。脚本保留完整实际状态、全部差异、紧凑结果、逐观察来源检查、全库计数核查及邻点控制。差异列表按路径稳定输出。运行约5.46秒仅指108状态构造，不包含其后的审计和文件序列化。

本云端实际执行命令额外用 `PYTHONPATH` 指向已存在的 Shapely 和可选 numba 依赖目录；该机器特定路径不构成可移植脚本的前提。

## 环境与数值差异

| 依赖 | 交接包声明 | 本次实际 |
|---|---|---|
| Python | 未声明 | 3.12.14 / Linux x86_64 |
| NumPy | 1.26.4 | 2.3.5 |
| SciPy | 1.11.4 | 1.17.0 |
| Shapely | 2.0.4 | 2.1.2 |
| pandas | 2.3.1 | 2.2.3 |
| matplotlib | 3.8.0 | 3.10.8 |
| Pillow | 10.2.0 | 12.3.0 |

numba 0.65.1存在于云端并记录在环境文件中，但此包复算入口不依赖它。没有为追求精确相等而修改或舍入结果。

93处差异分布：
- `/result/candidate/footprint`：55个浮点叶值
- `/result/correspondence_diagnostics/bottom/competing_match_examples/candidates/distance_deg`：3个浮点叶值
- `/result/correspondence_diagnostics/competing_match_examples/candidates/distance_deg`：8个浮点叶值
- `/result/correspondence_diagnostics/top/competing_match_examples/candidates/distance_deg`：5个浮点叶值
- `/result/endpoint_groups/bottom/maximum_match_angle_deg`：6个浮点叶值
- `/result/endpoint_groups/top/maximum_match_angle_deg`：3个浮点叶值
- `/result/endpoint_groups/top/maximum_pair_angle_deg`：1个浮点叶值
- `/result/identity_groups/maximum_match_angle_deg`：9个浮点叶值
- `/result/identity_groups/maximum_pair_angle_deg`：3个浮点叶值

全部差异明确保存在 `all_differences.json`，包含每个字段的期望值、实际值、绝对误差、相对误差及容差检查。所有差异均通过绝对1e-9＋相对1e-12检查；观测最大值远小于该审计容差。数值差异只出现于少数球面角距、对应诊断角距和候选BEV足迹，不影响分组、达票、选择、成环、失败或来源信息。

## 九图来源、人数与资格

| 图 | 作答份数 | 原点对数 | 已确认源环份数 |
|---|---:|---:|---:|
| B6ByNegPMKs-33 | 23 | 92 | 0 |
| UwV83HsGsw3-09 | 24 | 122 | 24 |
| b8cTxDM8gDG-18 | 6 | 24 | 6 |
| uNb9QFRL6hY-67 | 15 | 68 | 15 |
| wc2JMjhGNzB-53 | 23 | 127 | 23 |
| e9zR4mvMWw7-15 | 8 | 35 | 2 |
| rPc6DW4iMge-06 | 24 | 224 | 24 |
| 2t7WUuJeko7-06 | 3 | 12 | 0 |
| 7y3sRwLe3Va-04 | 24 | 96 | 0 |
| 合计 | 150 | 800 | 94 |

检查内容：

- 9图顺序和每图人数与 manifest 完全一致；150个作答ID全局唯一，每图人员ID唯一
- 全部来源为 manual、independent=true、consensus_eligible=true、main_consensus_gate=main_candidate；无 borrowed_points、无 independence_reasons
- 全部至少8端点，坐标有限且在1024×512连续画布内，上下原有shared-x一致、top-y小于bottom-y
- source_pair_indices、source_point_indices、source_point_labels长度与点阵一致，来源索引无重复；处理后点对和源点序不重排
- 输入在运行前后逐字段相等；69份交接文件的SHA-256前后完全相同。实际磁盘共有45个 `.py` 文件（含包初始化文件），manifest 声明 source_modules=44，未定义此字段计数口径；这项元数据计数差别不影响入口导入或108状态结果
- 9张原图文件齐全，实际像素大小均为2048×1024。标注仍使用1024×512连续坐标；本次未缩放或改写标注

范围限制：上述证明交接包内的名单、资格元数据及基线成员绑定相互一致，不能替代从未交付的上游137图原始全集重新推导纳入资格，也不能据元数据确认新的物理身份关系。

## 独立算法核验

108状态共核验**12,000个源成员绑定、1,547个身份组、42个分开路线配对身份**。

1. 每个身份组的成员点、作答ID、worker、处理后索引、来源点对索引、来源点索引逐项对应原输入；每位人员在每组最多一票
2. 每一路身份划分完整且不重复地覆盖全部来源观察，未达票观察没有静默删除
3. 分母始终为每图完整作答池，MV50门槛为 ceil(n/2)，没有先选最大整答簇
4. 独立以三维单位向量的 atan2(叉积范数, 点积)核验球面距离，与源码公式最大差异3.8413716652030416e-14°；绑定路线控制上下最大角距，锚定路线只控制所选端点角距
5. 原环赋值顺序、源环确认状态、直接边支持、删除投影边支持、原完整环支持分别重算并匹配；没有把投影边当作原边，也没有把局部边票数当作整环票数
6. split_unique 的 joint_members 等于所选top/bottom成员交集，joint_support为该交集人数；不能把两端边际支持当作联合位置支持
7. 每个候选仍为未确认新环；源码中 ok 只表示已有计算检查通过，不能认证真实场景正确
8. 构造期间记录文件打开事件，未读取 evaluation 参考；参考文件只作为全包不可变性哈希对象，不参与算法或参数选择

## 原始MV不足四对行为

**没有强制四对、补点或修改票权。**

三种绑定／锚定路线中有35个状态达票身份不足四对：26个恰好三对、9个少于三对。少于三对者仍保留所有身份组和票数，但无法生成此入口要求的多边形。恰好三对者照常生成。加上 split_unique 的两个三对结果，108状态中共28个三对候选具有可计算几何。

下表是绑定路线的达票身份数，不是正确角点数：

| 图 | 5° | 9° | 12° |
|---|---:|---:|---:|
| B6ByNegPMKs-33 | 2 | 3 | 3 |
| UwV83HsGsw3-09 | 3 | 3 | 3 |
| b8cTxDM8gDG-18 | 2 | 3 | 3 |
| uNb9QFRL6hY-67 | 2 | 3 | 3 |
| wc2JMjhGNzB-53 | 2 | 3 | 3 |
| e9zR4mvMWw7-15 | 3 | 4 | 5 |
| rPc6DW4iMge-06 | 7 | 9 | 9 |
| 2t7WUuJeko7-06 | 4 | 4 | 4 |
| 7y3sRwLe3Va-04 | 4 | 4 | 4 |

全部四路线状态：

| 路线（每路27状态） | ok | geometry_review | unavailable |
|---|---:|---:|---:|
| paired | 6 | 17 | 4 |
| bottom_anchor | 7 | 18 | 2 |
| top_anchor | 9 | 15 | 3 |
| split_unique | 0 | 11 | 16 |

总计83个状态有可计算候选、25个不可用。`split_unique` 的达票点对数保持 null；未决配对不记成零对。全部108行另见 `compact_states.csv/json`，不删失败行。

## 全库137图计数的可核验范围

**这里是对交付摘要的独立重计数与一致性核查，并非重新运行137图几何。**原始记录仅交付9图；其余128图缺少本次独立全量重算输入。

由 `evidence/all_image_pair_count_audit.json` 独立求和、交叉检查：

- 137个唯一图片、1520份合格作答；1520不是不同人员人数
- 逐图端点数直方图总数等于n，全部记录至少8端点
- 恰好1644个不同图片×门限×路线组合，既无遗漏也无重复
- 每行门槛为ceil(n/2)，绑定／锚定达票身份数等于group_supports中达票组数
- 绑定不足四对依次为29/137、10/137、5/137；恰好三对为12、9、5图，零至两对为17、1、0图
- 9°不足四对的10图中，6图已有23—24份作答
- 下端锚定不足四对18/6/2图，上端锚定18/5/2图
- 分开路线已生成但不足四对为1/1/1图，未生成为53/26/17图；两种情况分开，未定义的达票身份数保持null
- 9图实际重算所得108行的分母、门槛、达票数、生成数、状态和原因均与全库摘要对应行一致

`rPc6DW4iMge-22 / R01424 / P002` 的原坐标适用失败出现在该图全部12个状态；原因均为 coordinates_outside_continuous_canvas。n=24、MV50门槛=12保持不变，失败作答仍留在1520总分母中，不从137图或24人分母剔除。该图不属于九图主面板，因而本次未重新判断它的原坐标。

## 即时邻点控制复算

使用包内 `compare_context` 入口和原human_review记录，重新生成全部2565条有向／侧别比较：52条有既有人工解释、2513条未审；共351个目标记录×侧别查询。没有添加人工标签或新查询，也没有重新开展e9z视觉研究。

rpc查询R02452处理后索引2，对R01557：

| 处理后候选索引 | 已有人审关系 | 仅本点A | 即时邻点B=max(A,N) | 记录内排名 |
|---|---|---:|---:|---|
| 4（正确紫色） | 同角点 | 3.0669444542° | 43.0962701299° | 1→2 |
| 2（此前误选） | 不同细节 | 4.4525811262° | 28.1271876999° | 2→1 |

纯共线细分控制保持连续边界与查询锚点不变，A=0°，B=41.8103148958°。反向、循环换起点保持距离完全不变；共同接缝平移最大数值差1.4210854715e-14°。另外以独立向量球面公式对全部2565条A/N/B重算，最大差5.6843418861e-14°。

这证实已知的即时邻点负例可复现。它不否定所有结构方法，也不等于实现了分段不变的局部连续路径。全部转折点敏感性结果另存 `neighbor_threshold_sensitivity.json`；本次不推荐或校准最佳阈值。

## 失败记录与未执行项

- 108次基线构造无异常；最终审计完整通过
- 审计辅助脚本首跑把R01424的worker检查误写成P018，导致核查器断言停止；实际交付证据是P002。纠正核查器后从头重跑通过，未改源数据或算法。首跑日志保留为 `run_attempt1.log`
- 初次依赖探测时matplotlib默认缓存目录不可写，之后固定到独立输出目录；最终正式日志无此缓存警告
- 未把manifest 44与磁盘45个Python文件的不同计数擅自“修正”进交付源包
- 未重跑137图原始几何、未重做全仓历史测试、未重新裁定未审成员身份、未把任何路线输出认定为真实正确布局
- 五张12°仍缺点图是定向困难面板；人审曝光样例不是独立留出验证；此复算不产生算法效果的泛化证据

## 文件导航

- `reproduce.py`、`run_replay.sh`、`requirements-audit.txt`：可移植复算器
- `comparison.json`、`all_differences.json`：全部精确比较与数值差异
- `actual_baselines.json`：108个完整实际结果
- `compact_states.csv/json`：108行紧凑结果
- `roster_checks.json`、`independent_checks.json`：名单及独立来源核验
- `global_count_ledger_checks.json`：137图摘要核查及明确覆盖边界
- `neighbor_summary.json`、`neighbor_comparisons.json`、`neighbor_reviewed_comparisons.json`、`neighbor_nearest.json`、`neighbor_threshold_sensitivity.json`：邻点复算
- `environment.json`、`run.log`、`run_attempt1.log`、`completion.json`、`source_sha256_before/after.json`：环境、日志、完成状态与源文件不可变性证据
