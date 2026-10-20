# 已知 G／R 方向的全整数人数与替换规模复查

本目录研究的是既有全局分类的两个指定方向：G 的 `C02→C01`，R 的 `C05→C02`。它不是一次重新训练类别的分析，也不是新外部盲测。分类只来自历史 10 栋楼；本批评估沿用已被探索过的 v2 另外 12 栋楼和既有 55 名可分类人员。

## 冻结设计

`BASELINE_SPEC.json` 保存规则与源文件 SHA；`DESIGN_FREEZE.json` 保存精确请求与可重建成员摘要。完整精确真源为 `REQUESTS.json.gz` 中的逐队 `requests` 与每条固定 block 的 `blocks/core_order`；`EVENT_DESIGN.csv.gz` 是可重建的分析索引。

对每个普通 Manual 池、每个可行替换规模 m，按来源分别要求至少 2m 个 outgoing 成员和 m 个 incoming 成员。三套互不重叠的替换块 A、B、C 具有完全相同的来源人数；A/B 同类，C 改类。共同背景从其余人员中取一个固定随机顺序的前缀，枚举 `n=max(2,m)…N−2m`。所以 A→B 与 A→C 始终共用同一背景、相同 n 和相同实际替换人数 m。

99,996 条团队请求对应 99,779 个不同团队、33,332 个事件、1,608 条嵌套链。所有 20,679 个可行 `target×pool×m×n` 条件都至少有一套 block。G 为 96 图、m 最大 11；R 为 84 图、m 最大 3；总人数最大 33。R 的 187 个 pool×m 条件均有两套 block，G 的 822 个条件中 412 个有两套、410 个一套。精确成员没有穷举：1,321 个可行来源向量机会中实际覆盖 1,110 个，未采用额外富集背景顺序。详见 `SEARCH_LEDGER.csv` 与 `POOL_CAPACITY.csv`。

原生 n=2 资格为 `two_person_deferred`。590 个这类事件和原始 flag 全部保留在请求及全尝试表，正式比较为 n≥3 的 32,742 个事件；deferred 与真正融合失败分开。此处沿用既有资格，没有改变参考或判据。

`MECHANISM_SPEC.json` 从元数据选择 606 个邻步、332 条链、938 个端点事件，用于原生观察分区和票数追踪。整体 `shape` 子集的 9,190 个事件在新融合之前按端点、n≈2m 与固定哈希选定。606 个邻步中 497 个的两端同时在该 shape 子集中，只有这些邻步追加新几何指标；其余 109 个仍保留原生身份／票数机制，附加几何为缺失。形状阈值仍是并列诊断，不替换旧 strict/main/wide，不叫已验证的必要结构正确率或 N1。

## 运行顺序

从成果包／工作区根目录运行。环境与源码恢复沿用主复现说明和 `analysis/requirements.txt`，原生科学源码固定为 `82c6164b0d4630de5316199c92aa405930973168`。本目录导入的旧 wrapper、评分、输入快照没有修改；新 main 与旧源的字节核对见上一层的 `SOURCE_PARITY_AUDIT.json`。`restored/` 必须已按主说明恢复；恢复源代码本身不等于已重跑科研。

```bash
python interchangeability_20261020/independent/baseline/design_baseline.py
python interchangeability_20261020/independent/baseline/audit_design.py
python interchangeability_20261020/independent/baseline/select_mechanisms.py
python interchangeability_20261020/independent/baseline/profile_known_classes.py

python analysis/composition/fusion_runner.py \
  --restored restored \
  --requests interchangeability_20261020/independent/baseline/REQUESTS.json.gz \
  --out interchangeability_20261020/independent/baseline/native_runs \
  --jobs 2

python interchangeability_20261020/independent/baseline/analyze_baseline.py
python interchangeability_20261020/independent/baseline/replay_mechanisms.py --jobs 2
python interchangeability_20261020/independent/baseline/phase_summaries.py
python interchangeability_20261020/independent/baseline/plot_baseline.py
python interchangeability_20261020/independent/baseline/select_case_candidates.py
python interchangeability_20261020/independent/baseline/make_export_selection.py
```

只验证成员重建时，将 `design_baseline.py --out` 指向新的临时目录，然后用 `audit_design.py --folder` 审查该目录并比较 `DESIGN_FREEZE.json` 中 `member_reconstruction_digest`。这不会读取或重跑新融合。源路径布局和 Python 随机实现／依赖版本需要保持相同；更换了源文件，源 SHA 应当明确变化。

只重绘图表时，保留小表 `results/N_M.csv` 与 `results/SHAPE_N_M.csv`，执行最后一条命令即可，无需 native 缓存或原图。字体默认读取主包 `analysis/fonts/NotoSansSC-Regular.ttf`。

## 结果文件与解释

`N_M.csv` 是每个方向、每个实际 n,m 的主表；`N_M_PHASE`、`N_M_DIFFICULTY`、`N_M_SOURCE`、`SOURCE_VECTOR`、`CORE_N_M` 依次给旧阶段、难度、来源及背景配比条件。统计先在每个 pool,n,m 内平均具体 block draws，再平均该图中的条件、再按图和建筑等权。整体表描述的是这张枚举条件网格，不代表自然招募中人数与类别的出现频率。

`DRAW_REPLICATION.csv` 只比较同时拥有第 0／1 套抽样的同 pool,n,m 条件，并区分两套 block 是否同来源向量。`PERSON_EXCLUSION.csv` 同时报告排除某个参与者后的支持量，以及同样保留下来的 pool,n,m 上原数据的对齐基线。这仍是敏感性分析，不是独立人员因果效应。

`Q_MATCHED_SUPPORT.csv` 保留历史 block Q 差的绝对值≤2的可用条件；`Q_SOURCE_ADJUSTMENT.json` 是描述性建筑加权回归。总体类别效用先独立报告；这些控制不能证明类标签对具体人员完全独立，也不代表已经训练出对新人的通用预测器。

`SHAPE_PAIR_RESULTS` 的平均高度棱柱量是 proxy。非平天花板的内表面没有被最终边界唯一识别时，精确平顶棱柱 IoU 返回缺失，不补零。`MECHANISM_STEPS` 的 `threshold_only_selection_loss_supported` 只证明旧观察的分组与票数支持了选中状态变化；它不证明丢失节点在语义上必要。

`ANALYSIS_RECEIPT.json` 与 `MECHANISM_REPLAY_RECEIPT.json` 列实际计算、失败、来源 SHA 和重放一致性。缺失与失败保留；相同团队重用、同图多背景和相邻人数节点都不算新的独立图片。

`DISCOVERY_CASE_CANDIDATES.json` 是按结果选择的可视化候选，同时保存明确差异、分数接近而结构不同、低历史 Q 局部改善、融合失败和人数门槛的正反例。候选只读原 discovery 建筑；选择准则、实际合格数量和排序保存在 `CASE_SELECTION_LEDGER.csv`。它是展示样例，不是新的确认性规则，也不能用极端案例代替全网格的发生率。

`BASELINE_EXPORT_SELECTION.json` 把其中七个候选适配为主包 `code/export_cases.py` 的 inline event schema，包含相邻 n 或两套独立 block 的六臂显示方案。原标签文件的 domain 叫 `global`、旧请求辅助函数映射为 `all`，适配中保留 alias 注记并使用原 global 标签；不是新分类。主包可按需选择条目并补 Release 原图路径，数值导出与重放不依赖原图。

## 精简交付边界

应保留关键代码、冻结规格、精确请求、简要台账、核心小表、图及主结论案例的必要几何。不需要将 `native_runs/`、全部逐事件富指标或所有中间文件打包。完整重算通过上述命令可恢复；最终代表案例应另附精确成员和最终几何，并可调用主包的便携重放入口。

执行环境曾出现长 CSV 直接流式 gzip 写入后截断；本目录现使用完整字节生成、fsync、原子替换和 CRC 解压回读。修复只涉及文件写入，所有成员摘要保持相同，证据见 `IO_REPAIR_RECEIPT.json`。
