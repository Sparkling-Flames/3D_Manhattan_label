# 精简成果包的实际重建与输入边界

本目录提供两个已经实跑的入口：**重建精确实验成员设计**，以及**从冻结记录重新计算历史画像和全部正向类别**。这两个入口都不会修改冻结标签、参考、融合、评分或研究规则，也不会从原始导出重新清洗坐标。原生融合重放由成果包的核心重放入口执行；这里不重复计算它。

## 1. 最少操作：核验所有成员设计

保留成果包的同级布局：`analysis/` 与 `interchangeability_20261020/` 同级。使用附带依赖版本的 Python，运行：

```bash
python interchangeability_20261020/reproduction/verify_designs.py \
  --package-root /path/to/extracted-package \
  --restored /path/to/restored \
  --out /tmp/personnel_design_rebuild
```

`--restored` 指向已经按照固定档案恢复的目录；它下面应有：

```text
work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz
```

该输入 SHA256 固定为 `83179b9842d06916b105d80ff181918c223e4fee2073f425f9825db124ec11d7`。外部恢复来源、归档文件名与逐件 SHA 由冻结交接和 `reverse/REVERSE_RECOVERY_INPUTS.json` 记录。当前任务文档 main、科学源 commit 和归档恢复 commit 是三种版本，不能相互替代；本入口以具体文件 SHA 为最后校验。

程序先从 `--package-root` 复制 `DESIGN_FINGERPRINTS.json` 中的 35 个小文件白名单到输出目录的隔离布局，再通过一个明确的只读用途路径引用外部恢复目录；它不会从当前完整工作区偷偷补读缺少的科学输入。源包缺文件或 SHA 不同会立即报错。脚本调用原科学生成器，逐一重建请求，再和归档前从原请求保存的指纹比较。生成文件、日志、外部恢复目录链接都留在 `--out`，不应再次放入精简包。

`DESIGN_REBUILD_RECEIPT.json` 是每次实际执行的结果。包内 `PREPACK_DESIGN_REBUILD_RECEIPT.json` 记录本次交付前执行：18 个命名设计流全部覆盖；16 个重新生成完全一致，2 个小请求明确采用精确保留；没有未重建却声称已经重建的设计。`PREPACK_FORWARD_LABEL_RECONSTRUCTION.json` 同时记录从冻结历史画像直接重建 188 个正向候选、11,280 行标签的结果。

### 核查的不只是文件字节

每个请求同时记录完整请求多重集指纹与去重团队指纹。团队的规范形式是 `(pool_id, sorted(worker_ids), k)`。同一团队因多个事件被请求多次时，重复行会在多重集保留，且不会被计成多个不同团队。

ABC 事件核查完整事件字段的规范 JSON 指纹，并逐项重新检查：成员来自该冻结池；三队人数正确；A/B、A/C 交集都精确等于共同背景；两种替换人数都等于 m；团队键对应成员；A/B 类别计数相同、A/C 不同；类别计数由冻结标签重新计算；`outside_group` 仍是未分型背景；实际来源块计数匹配声明真实；参考 ID 与冻结池相同。嵌套路径、共同核心面板的全部 block／pair 索引、条件 links、配比 links 和搜索台账也保留各自指纹。

规范 JSON 使用 UTF-8、对象键排序、紧凑分隔符；先对规范行排序，再以换行分隔计算 SHA256。完整事件列表和账本会检查全部字段，不能只重建“成功”事件或几张案例。重新运行生成器的登记时间、gzip 容器字节或绝对输入路径可能变化，这些不当作人员组成变化；冻结生成器、spec 和标签的 SHA 仍逐件强制核对。

### 已实际覆盖的设计

| 设计流 | 使用的原入口 | 审计方式 |
|---|---|---|
| 发现 F 宽搜 | `code/design_blocks.py` + `discovery/FORWARD_SPEC.json` | 重建全部 62,610 ABC、183,219 不同团队 |
| 发现 R 宽搜 | 同一入口 + `discovery/REVERSE_SPEC.json` | 重建全部 33,468 ABC、97,432 不同团队 |
| 17 条冻结固定／压力方向 | 同一入口 + `assessment/DIRECTION_SPEC.json` | 重建全部 11,808 ABC、35,179 不同团队 |
| 新来源 R 二类嵌套 n | `code/design_nested_new2.py` | 重建 5,232 ABC、15,679 不同团队及全部固定路径 |
| 同班 Manual／Semi | `code/design_condition_transfer.py` | 重建全量，再按原 phase 分拆，三个命名文件分别核对 |
| 混类／整队挑战两阶段 | `code/design_mixed_challenge.py` | 分阶段重建所有成员、类别向量和实际 B/C 换人量 |
| 初始配比广网格 | `code/design_ratio_grid.py` | 重建原元数据选图、全部记录向量和成员 |
| 五比例新成员复查／评估 | `code/design_ratio_replication.py` | 使用重建的原网格排除旧团队，分别核对两阶段 |
| 共同 26 人面板两阶段 | `forward/common_panel/design_common_panel.py` | 重建 14,243／10,577 队及全部核心、块、disjoint pair 索引 |
| R 新增历史面板 | `code/design_history_panel.py` | 重建 31,539 队及历史 anchors |
| 已知 G／R 全整数 n/m 基线 | `independent/baseline/design_baseline.py` | 重建请求、固定块、嵌套核心及 EVENT_DESIGN |
| P05 单图有限人员总体 | 原小型精确请求 | 原样保留并核文件 SHA、3,752 个精确团队和事件；不宣称再次运行设计器 |
| W132 机制探针 | 原小型精确请求 | 原样保留并核文件 SHA、全部精确成员和事件；不宣称再次训练人员类 |

此表的 18 个设计流存在团队、条件全表／分表和图像复用，不能把它们的行数相加当作独立研究样本。P05 census 是发现结果推动的单图机制检查，W132 也是特定人员机制复查，都不是新的外部验证。

可使用 `--only forward_wide reverse_wide fixed_directions` 只重建指定流；如果请求某个条件 phase 或配比复查，程序会自动先重建它的上游设计。结果回执会明确列出所有未执行设计，不能把子集回执改称全量通过。`--record-reference` 仅供归档作者从仍存在的原完整请求创建指纹；正常复现不得重新记录一个新基准来掩盖不一致。

## 2. 从冻结记录重建全部正向画像、类别与容量

```bash
python interchangeability_20261020/reproduction/rebuild_forward.py \
  --package-root /path/to/extracted-package \
  --restored /path/to/restored \
  --out /tmp/personnel_forward_rebuild
```

这个入口按 `FORWARD_FEATURE_INPUTS.json` 搭建独立布局，调用原 `audit_and_features.py`，随后调用原 `build_candidates.py`。它使用原 SPLIT 的 10 栋历史建筑，重新计算 60 人、328 个字段，并核原 156 个历史字段、额外条件变量、来源内相对用时与高 Q23 的同口径支持；随后重新拟合全部 188 个正向候选，比较 11,280 行标签和每类成员、类规模、partition 指纹及元数据容量表。质量和时间未知仍保持未知，不补零；不会为更好地匹配标签另改标准化、切点或随机种子。

大的冻结 `records.json.gz` 不重复放入成果包。它从外部恢复目录引用，SHA 为 `46ee9890a1a56264c8955538f47c650cbe893662e7cefc21e360a3e00eca9251`。同样从恢复目录引用两份旧估计代码：

- `work_personnel_typing_A_20261019/forward/build_features.py`：SHA `4b54ac047cf4853fcb4e26d6073437d42b0e37c1ad9c8316bafc9de207f1c6f7`。
- `work_personnel_typing_A_20261019/recovered/work_v2_20261019/profiles/run_profiles.py`：SHA `808deba4d7ae2e395175511fad0e566eb3aa24ba27cc71306f7ca3f373ac5bdc`。

这三件已经核对与当时用于本轮特征审计的 repo 件逐字节一致。包内只补充旧 `analysis/forward/build_forward.py`、旧历史画像与 Q 标签、当前正向代码／画像／标签，以及 `feature_support/` 的高 Q23 核对小表、池库存和成员表。四个支持 CSV 合计 132,597 字节；它们是复建所需的精确元数据，来源和 SHA 单独记录。

该入口与只从冻结画像重建标签有明确区别：前者重新估计全部画像字段，后者只重跑类别算法。数值字段按绝对误差 1e-9、缺失位置一致核查；类别成员必须完全一致。浮点 CSV/gzip 容器字节改变不等于分类改变，回执记录真实字段差值、各层 SHA 与标签指纹。输出的容量表可以使用发现／评估建筑的池成员元数据，但训练画像和类别定义仍只使用历史建筑；该元数据支持检查不读取目标融合成绩。

## 3. 反向模型与共同面板的复跑边界

共同 26 人的 **成员设计** 已由第 1 节从零重建；八种比较分类、16 项消融及 40 个固定随机分区的计算入口在 `forward/common_panel/`。分类共用同一真实团队缓存，分析还必须保留每个方法的 eligible A 和共同 A 交集；不能为复跑方便改为比较不同支持的原始均值。`common26` 生成器同时重建随机分区、核心和全部有限 disjoint block 索引。分析原生结果使用 `summarize_common_panel.py`、`compare_competitors.py`，不重新拟合目标图上的人员类别。

共同面板分析的原入口有较严格的原文件 SHA 和路径检查。不要直接把重新生成的登记时间文件替换原 `COMMON_PANEL_REGISTRATION.json`；应该保留原冻结登记，使用已证明逐字节相同的重建 requests、anchors 和随机标签。以下准备入口已实跑：

```bash
python interchangeability_20261020/reproduction/prepare_common_analysis.py \
  --package-root /path/to/extracted-package \
  --restored /path/to/restored \
  --design-rebuild /tmp/personnel_design_rebuild \
  --native-discovery /path/to/discovery-common-native \
  --native-assessment /path/to/assessment-common-native \
  --out /tmp/personnel_common_analysis
```

两个 native 目录下面分别应有 `pools/<pool_id>.json.gz`，可由第 1 节的两份共同面板请求运行冻结融合得到。默认命令只准备隔离分析目录：核原登记／请求／anchors／随机标签和三个标签来源的 SHA，创建旧 Q 路径的同 SHA 别名，核原生数据确实含全部 14,243／10,577 个请求团队及准确成员。加 `--run` 会依序调用原代码、重新生成两阶段的原 16 项消融与八方法公平比较表，全部结果写在输出目录内。

包内 `PREPACK_COMMON_ANALYSIS_PREPARATION_RECEIPT.json` 是实际准备及成员核验的回执；它明确 `analyses_executed=false`，本次包装未重复已完成的两阶段统计分析。`COMMON_ANALYSIS_INPUTS.json` 记录分析额外依赖；旧 Q 的完整 manifest 与新 R 的完整 manifest 在 ZIP 中可压缩保留，用于原 SHA 绑定。旧 Q 的 current_main 路径只是指向包内 `analysis/forward/results/` 同文件的别名，不需要再次放入一份完整仓库。

完整反向类别学习的入口、79 份旧历史逐池事件输入、额外原生历史 pair 重建、软件依赖和精确命令，见 `reverse/REVERSE_REPRODUCTION_ZH.md`、`REVERSE_RECOVERY_INPUTS.json`、`REVERSE_MINIMAL_REPRODUCTION.json`。本次包装审计**没有再次执行完整反向优化学习过程**；已有训练和内部删楼结果原样保留。它实际核验了冻结 R 标签驱动的所有本轮精确实验成员，以及新增历史面板可重建。不能用设计重建通过来替代模型重新学习通过。

反向 mixed 训练默认需要恢复的旧 A `events/comparisons/*/events.csv.gz` 和新增历史 `native_history_events.csv.gz`。新增事件可由本次已重建的历史请求运行冻结原生融合，再运行 `reverse/extract_native_history.py` 生成。训练入口只从注册 10 栋历史建筑学习；旧 `common_events` 总表不是此入口读取的替代品。不要把整个旧事件档案和每对缓存再塞进成果包，保留恢复索引、精确 hash 与生成代码即可。

## 4. 必需小文件、路径和运行环境

`DESIGN_FINGERPRINTS.json` 的 `required_files` 是设计入口的完整白名单，含每件大小与 SHA；`FORWARD_FEATURE_INPUTS.json` 是完整正向特征入口的白名单；`COMMON_ANALYSIS_INPUTS.json` 是共同面板分析的附加白名单与路径别名。`PACKAGE_DEPENDENCIES.json` 合并三者，最终打包脚本应据其复制，而不是复制整棵工作区。完整 F 特征入口的额外四个 CSV 已放入 `feature_support/`，可直接按原路径保留。

主要路径依赖如下：

| 代码 | 既有路径约束 | 本包装入口的处理 |
|---|---|---|
| `design_blocks.py` | snapshot、split、labels、spec 均为显式参数 | 全部传入隔离目录绝对路径 |
| `design_nested_new2.py` | 仍读取相邻 study 的 `REGISTRATION.json` 并校验 spec／标签／snapshot SHA | 保留 study 层级和原登记文件 |
| mixed／ratio 生成器 | 从自身相对位置导入旧 `analysis/composition/design_compositions.py`；后者导入 `fusion_runner.py`、`design_screen.py` | 白名单同时复制这些小依赖，保留同级目录 |
| G／R baseline | 默认读取 `ROOT/restored`、旧画像、旧 R 标签、METRIC_CONTRACT | 在隔离目录创建显式外部 restored 路径引用，并复制原代码／合约 |
| 原 `audit_and_features.py` | 默认旧 main 路径，且来源记录要求能相对工程根记录 provenance | 新入口传绝对 stage/repo、stage/analysis 与 stage/feature_support；科学源文件不改 |
| 原 `build_candidates.py` | 容量检查读取 handoff 的两个池元数据表 | 将相同 SHA 的精简支持文件放在原 repo 相对位置 |

设计器主要依赖 Python 标准库、NumPy、Pandas、SciPy；正向候选还依赖 scikit-learn。G／R baseline 的旧模块导入链会加载 Shapely，即使本步骤没有计算新几何。使用成果包的冻结依赖版本；不要把虚拟环境、原生缓存、逐折模型或 `check_scratch/` 打包。

最终原生重放的精确核心子集应另外保留其请求和校验回执，特别是最终报告引用的 F01、Rnew2 固定四格、G／R 新 draw、混类精确比例、五比例评估与 P05 有限总体。宽搜大请求可由本目录重建；省掉它们不代表省掉核心主张的精确证据。
