# v2.1人员重新选型：复算、数据连接与恢复

本文件负责技术接续；结论更新到既有《人员分类与构成不确定性》主报告。固定仓库 `Sparkling-Flames/3D_Manhattan_label`，实际读取提交 **a476461d7ede8db95da43de4139e612c05e618bc**，底层 **v2.1**。未改 CURRENT、GT、目标资格、环序、B8L2/D10或融合算法。

## 1. 哪些文件先读

1. `DELIVERY_INDEX.md` 和 `DOWNLOAD_INDEX.csv`：实际可取得的文件、阶段职责、大小、SHA256。大包全部按研究根目录的相对路径保存，可叠加解压到同一目录。
2. `stage07_adoption/EFFECTIVE_EXCHANGE_CONDITIONS.csv`：32个重点扩展条件的主要结果、语义角色和采用判断。
3. `stage07_adoption/ALL45_METHOD_ADOPTION_DECISIONS.csv`：45个冻结方法的全部采用/保留/补充理由。
4. `stage07_adoption/PERSONNEL_ALL_MEMBERS.csv` 与 `PERSONNEL_LOBO_LABELS_AND_SUPPORT.csv.gz`：前者描述ALL人员，后者连接真实楼外实验。两者不能互换。
5. 完整配比、严格ABC、直接AC、规模路径按不同结果目录读取，不拼成同一个统计总体。

主要代码保留本轮实际执行版本；本轮文件名沿用研究日期20261029。源提交和数据版本比文件日期更有识别意义。

## 2. 冻结输入与环境

仓库两个关键输入快照：

- `research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json`：263原主目标池、8,154份原答。
- `research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json`：31其它准入目标池、231份原答。

它们含精确人员、对象、原答、参考和时间来源，可直接重放团队。引用固定提交中的文件，不依赖以后可能变化的main。`stage01/SOURCE_FILE_MANIFEST.json`保存快照、质量库存、参考绑定、难度等关键仓库输入的字节数和SHA；`source/ENGINE_CHECKOUT_PATHS.json`列出实际取得的冻结引擎及依赖路径。大份仓库输入不再复制进每个研究分包。

运行环境记录在 `source/RUNTIME_VERSIONS.json`：Python3.12.14、numpy2.3.5、pandas2.2.3、scipy1.17.0、scikit-learn1.8.0、matplotlib3.10.8、Pillow12.3.0、Shapely2.2.0。Shapely在本次环境装于任务专用目录；迁移时普通安装即可，不需要恢复原虚拟环境。原生引擎还使用仓库冻结的JS测量/融合依赖，按该引擎本身的入口加载。实际9个已有端点一致性与吞吐结果见 `experiment/benchmark/BENCHMARK_AND_PARITY.json`；不要求为了读表重新跑基准。

典型目录布局：仓库目录与本研究目录相邻。本轮使用 `HOHONET_v21_20261029/` 和 `personnel_v21_research_20261029/`。多数新脚本通过 `--repo/--work` 传参；少数整理脚本使用自身文件相对根目录。各阶段RUN_PLAN保留本次绝对路径用于溯源，迁移时把工作根和仓库根替换成实际目录即可，不修改成员或数据。

## 3. 连接键与核心字段

|字段|含义与连接规则|
|---|---|
|`pool_id`|图片×条件×现行合法目标的池；任何团队只来自一个池。不能只按image合并不同空间|
|`image`, `building`, `reference_id`, `reference_version`|图片、建筑和固定参考；同图多个合法目标保留不同pool_id|
|`worker_id` / `member_workers`|真实研究人员ID及精确队伍；集合身份排序后哈希，进入顺序不改变同集合终点|
|`object_id`, `member_object_ids`|具体原始作答对象；人员相同也要核对目标及对象，不能仅靠工号复用另一池端点|
|`method`, `heldout_building`, `class`|冻结方法、楼外折和该折类别。ALL用于描述，不能直接代入楼外实验|
|`role_direction` / 历史秩|按楼外中心定义的角色方向；类别编号跨折不直接比较。秩不是由目标图效果确定|
|`event_id`|方法、目标、实际D/X/Y/Z、n/m的登记身份；跨阶段可能重复，同端点可被多事件引用|
|`A_team_key`, `B_team_key`, `C_team_key`|连接去重端点标量与几何；一个确定性端点只计算一次|
|`D`, `X`, `Y`, `Z`|共同背景、原块、同类替换块、跨类块，`|`分隔真实工号|
|`n`, `m`, `actual_m_AB/AC/BC`|团队人数与实际集合换人数；严格ABC三者均等于m。直接AC无B|
|`replacement_fraction`|m/n。另有`source_candidate_fraction`=m/该池源类容量、`source_A_seat_fraction`=m/A中全部源类席位|
|`seat_net_change_l1`|完整类别向量的L1席位差，严格单方向纯块为2m；不是实际换人数|
|`B8L2`, `D10`, `IoU3D100`|冻结主质量、敏感性质量、百分制三维IoU；底面`iou_2d`为0—1|
|`*_BA`, `*_CA`, `*_CB`|B−A、C−A、C−B各自的有符号变化，每项保留真实可评支持|
|`*_within`, `*_cross`, `*_gap`|三队共同可评时的\|B−A\|、(\|C−A\|+\|C−B\|)/2、二者差；不把幅度大写成必然更好|
|`A/B/C_failed`, `complete_evaluable`, `score_status`|可评分/完整输出状态。失败Q保留空值；geometry_reason进一步区分连接、少于四点、无效底面|
|`record_time_*_pct_source_matched`|库存记录秒数求和的百分比；比较双方所有时间已知且来源人数向量一致。不是新测生产工时|
|`official_difficulty`|正式目标难度；其它空间未知仍为未知|
|`geometric_challenge`, `ref_turn5`, `ref_H`, `ref_short_edges`|目标自身可计算结构条件，不能把它等同于正式人工难度|

严格ABC必须满足N≥n+2m、源类≥2m、目标类≥m。实际每个事件均核对四块互斥。源类块复用只有在新标签仍满足该折类条件时才合法；没有给失去同类关系的旧队伍改个名字充当新实验。

## 4. 数据层次和权重

类别历史：同目标同条件同行中心化；时间另分来源；个人目标内→图内→楼内汇总，楼等权。楼外排除目标建筑所有空间，跨条件方法同时排除两条件。

替换效应：同目标池内先对实际成员/背景事件平均，同图多目标再等权，主表按图片等权。建筑等权另在楼内平均图片。事件数量是覆盖，不是独立样本量。

完整配比：每面板固定D、固定12名变量人员、选6人全部924集合。按**完整团队类别向量**分格，包含D；先分解面板构成间/内方差，再按目标、图片、建筑层级汇总方差后相除。不能把方差比例当作分数增益或时间节省，也不能把面板全枚举称为35人池全枚举。

规模路径：主ΔC、ΔB、净变化使用同四个B/C端点；幅度增量另需固定A，共五端点。已经保存较宽的成对结果和匹配结果，只有共同分母上的三列满足均值ΔC−ΔB=净变化。固定X/Y/Z增加n的路径与固定A增加m是两类实验。

## 5. 最快复算：只从已交付结果重新汇总

从研究根目录运行，不需要先重新融合：

```bash
python stage07_adoption/code/summarize_adoption_conditions.py
python stage07_adoption/code/describe_frozen_personnel_roles.py
python stage07_adoption/code/write_personnel_roles_report.py
python analysis/summarize_scale_background.py \
  --merged-input analysis/scale_background_summary/FIXED_A_ALL_M_INCREMENT_METRICS.csv.gz
python analysis/build_scale_background_reading_tables.py
```

上述主条件整理直接读取 `analysis/focused_compact/EVENT_EFFECTS_COMPLETE.csv.gz`，并按 `method/event_id` 接入 `experiment/focused_design/EVENTS_EXACT.csv.gz` 的精确D/X/Y/Z及容量；阶段07B已包含两表，不需要恢复重复的764列工作宽表。绝对A/B/C标量从 `experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz` 按team_key接入，原始几何对与参考诊断亦有独立关系表。不要从汇总均值反推逐事件结果。

主图的实际绘制代码为 `stage07_adoption/code/plot_adopted_conditions.py`；CJK字体路径在脚本中明确，成品PNG/PDF已提供。构成图、病例图、原答相似性各有自己目录中的实际代码，不使用生成式图片替代测量图。

## 6. 重新形成新候选

首先取得固定提交的正式输入和本轮阶段02文件，另开复算目录，避免覆盖本轮冻结名单：

```bash
python classification/code/build_target_aware_candidates.py \
  --repo ../HOHONET_v21_20261029 --work .
python classification/code/build_target_weighted_rfuse.py \
  --repo ../HOHONET_v21_20261029
```

`CANDIDATE_CONFIG_BEFORE_TEAM_RESULTS.json`、各域变换、实际输入支持和`MAIN45_FROZEN_RECEIPT.json`给出参数及标签SHA。官方20前向、旧V3和原主目标RFUSE依赖仓库已保存的v2.1名单；这部分在本轮是复用，而不是声称重新训练了全部45法。新13前向和4目标等权RFUSE确实重新形成。旧3种XCOND没有新版标签，不应自行把旧v2名单贴成v2.1。

RFUSE训练使用已有自然队伍端点，目标×人数中心化后做目标等权；它不使用本轮待比较ABC输出。Manual/Semi/scope候选保持自己的输入条件。角色中心解释与聚类输入分别保存，不要把用于解释的公共历史表误认为所有方法的原始特征。

## 7. 必要时才补算端点

主请求、精确事件和池快照已冻结。示例以已登记的小规模对照请求为输入：

```bash
python experiment/run_registered.py \
  --repo ../HOHONET_v21_20261029 \
  --pools ../HOHONET_v21_20261029/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json \
    ../HOHONET_v21_20261029/research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json \
  --requests experiment/refinement_baseline_design/REQUESTS.csv.gz \
  --output replay/refinement_baseline \
  --cache-roots experiment/global_screen_endpoints endpoint_delivery \
  --jobs 6 --part-size 100
```

`run_registered.py`按pool、精确人员/对象、reference_id/version、v2.1来源和输入指纹复用缓存。它每100个新端点保存一个原子分片，每完成池再存标量；中断后从完整分片接续。未完成`.writing/.tmp`不是结果文件，不进入交付索引。

广筛几何001/002/003提供142,270个全部端点。focused、fixed_A_m、direct_AC、refinement、member_sensitivity各增量包只保存该批真正新增几何，加上所有请求标量和跨包来源映射。少量更早的原仓库缓存几何仍按来源引用；原图/完整原答快照与请求可确定性补算，不以找齐所有旧缓存为前置。案例包独立保存其必要原答/几何，因此不需要下载全部几何才能读主结论。

## 8. 把更新接回仓库

本轮已经在本地更新原路径 `docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md`，保留旧阶段正文。独立下载的同名报告是同一内容的可读导出，旧仓库链接指向固定提交，新结果链接指向本研究目录。

将各包叠加解压到仓库 `research/workers/personnel_v21_reselection_20261029/`；然后应用 `integration/PERSONNEL_MAIN_REPORT_UPDATE.patch` 或使用同目录提供的更新版仓库文档。补丁只更新人员主题主报告，不修改数据、质量、融合、同房或CURRENT。研究包内保留各专题报告，不把同房和画像重写进人员结果。

本轮没有推送GitHub或公开发布。独立报告、小表和分包均有实际文件；最终文件读取、链接检查和归档覆盖在 `FINAL_DELIVERY_READ_CHECK.json`，阶段回执保持原阶段身份。
