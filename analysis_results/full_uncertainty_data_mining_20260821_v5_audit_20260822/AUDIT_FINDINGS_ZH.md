# 全景布局标注不确定性 v5 独立审计补充（2026-08-22）

## 1. 审计对象

- 仓库：`Sparkling-Flames/3D_Manhattan_label`
- 基线分支：`main`
- 基线提交：`4a4b9afbd1d4a34438e41bb438f5f256fa474def`
- 提交说明：`Publish full uncertainty audit v5`
- 主要目录：`analysis_results/full_uncertainty_data_mining_20260821_v5`

本补充不覆盖或改写 v5；所有修正均作为并列审计层保存。

## 2. 与此前分析要求的覆盖关系

### 已覆盖

1. **全部记录与筛选边界**
   - 2,513 个 raw annotation versions；
   - 2,501 个 selected/canonical/auditable contexts；
   - 12 个 raw-only/nonselected versions；
   - raw ledger、raw→selected crosswalk、revision lineage、行政/资格/任务外原因均有单独表。
   - 分析资格只决定具体指标分母，不把整名工人从数据挖掘层删除。

2. **Manual/Semi 同图不确定性**
   - 25 个 paired base tasks、9 个 buildings；
   - q=0.95 下 10 个收敛、11 个扩散、4 个熵不变；
   - 同时报告 Shannon entropy、Gini-Simpson、最大模式占比、模式数、两两几何分歧、GT 指标变化。

3. **元标签不确定性**
   - canonical-final 与 raw/history 分开；
   - 回答模式熵、Jaccard 分歧、众数占比；
   - difficulty 与 scope 逐任务 Manual/Semi 对照。

4. **几何不确定性**
   - topology/mode、pairwise geometry、validity、阈值敏感性、subset reclustering；
   - 101 个 Crowd–GT task-condition；
   - 54 个双人任务敏感性；
   - 不同 topology 不做坐标平均。

5. **Active time 与 lead time**
   - C1 正式 task-worker active time、P1/C2 日志来源、阶段×模式×计时来源；
   - lead time 不进入 active-time 分母；
   - 34,417 个事件和 3,735 个 session 的事件级完整性审计。

6. **共识、少数模式与 GT**
   - 最大簇、最佳 GT 对齐簇及可观察几何差异；
   - 少数簇不自动解释为错误，GT 冲突不自动解释为 GT 错误。

7. **稳定工人观点**
   - task-condition 内置换；
   - leave-one-task-out 稳定性；
   - worker pair 共现关系；
   - 当前 C1 全部可计算 lane 的 task-stratified permutation p≈0.002；旧 k=22 可评价 lane p≈0.021。

8. **持续多峰与随 k 变化**
   - PreScreen 29 个高支持任务：q=.95 强持续分裂 10/29；
   - Calibration 12 个高支持任务：q=.95 强持续分裂 5/12；
   - k=5/8/12/16/20 的 200 次前缀重放和 k=22 全样本状态。

9. **Proposal 行为**
   - 初始/最终几何、编辑率、编辑幅度、U 指标变化、可接受/简单标签后仍编辑；
   - 指标下降使用中性术语，不自动称为真实几何不合理。

10. **样本量与功效**
    - 当前 building-level SD、未来 building/task 数、MDE、条件功效；
    - 稀有模式发现概率。

### 部分覆盖或尚未覆盖

1. **缺失机制模型**：仅有缺失/计时来源审计，没有正式的 missingness probability model。
2. **reference 版本轨迹**：存在 reference status/provenance，但没有按 task 物化完整的版本变化时间线。
3. **专家重聚类**：没有新的双专家盲审标签，不能从现有算法簇客观推导“真实模式”。
4. **任务机制聚类**：现有表提供变量和案例，未冻结稳定、可解释的 task mechanism clusters。
5. **事件行为表型**：已有 event/session 审计，但没有将事件序列建成稳定的行为 phenotype。
6. **完整视觉附件**：214 个 task 均有图像路径/特征，尚未为全部 101+54+标签案例生成统一叠加式视觉附录。
7. **正式标注前风险关系**：C1 pre-assignment feature manifest 的 `n_ready=0`；因此正式冻结风险与 Semi 收敛/扩散的关系仍不可评价。

## 3. 已识别的计算模式问题

### 3.1 图像特征存在别名/冗余

`build_a4_image_evidence_substrate.py` 中：

- `horizontal_gradient_mean_no_seam` 是 x 方向灰度差；
- `vertical_edge_mean` 也是同一个 x 方向灰度差的均值；
- `vertical_edge_p90_proxy` 也是该 x 方向差的 P90；
- `boundary_gradient_mean` 才是 y 方向灰度差均值。

若将 `vertical_edge_mean` 理解为“垂直边缘响应”，公式在图像处理语义上可以成立；但它不是独立的 y-gradient 特征，而且与 horizontal-gradient family 高度冗余。当前 25 个 paired tasks 上，`vertical_edge_mean` 与 `horizontal_gradient_mean_wrap` 对所有结果给出完全相同的 Spearman 结果，因此不能视为两条独立复现证据。

建议：
- 重命名为 `x_gradient_vertical_edge_mean`；
- 或从独立 predictor family 中删除；
- 明确 `boundary_gradient_mean` 为 y-gradient/horizontal-boundary proxy。

### 3.2 图像特征扫描未控制总体多重检验与 building 依赖

`IMAGE_FEATURE_VS_SEMI_ASSOCIATIONS.csv` 扫描约 72 个 predictor–outcome 组合，只报告 task-level 未调整置换 p 值和普通 task bootstrap。当前名义 p<.05 的结果不应直接称为稳定关联。

按全表 72 项校正：
- 最小原始 p≈0.00899；
- 最小 Holm 调整 p≈0.647；
- 最小全局 BH q≈0.198；
- 全局无结果保留。

在单独的 `delta_supported_multimodality` outcome family 内，BH 可能保留三条 edge-related predictor，但它们来自同一梯度家族，其中一条还是别名，因此不能视为三次独立确认。

此外，25 个任务只来自 9 个 buildings；当前 permutation/bootstrap 没有把 building 当作 cluster。该表只能作为候选筛查。

### 3.3 `QUALITY_RISK_SLOPE_POPULATIONS.csv` 的 p 值不是正式推断

当前代码对 227/235 行直接调用 `scipy.stats.linregress`，未控制同一 task、worker、building 内的重复依赖。斜率约 -0.023 至 -0.026 可作为描述量，但其 row-level SE、CI 和 10^-6 量级 p 值会低估不确定性，不能作为正式证据。

建议：
- 以 `base_task_id` 聚合 task mean quality；
- building-cluster bootstrap 或 small-cluster robust sensitivity；
- worker/stage/condition 作为适当控制；
- 保留 slope effect，但不沿用 row-level formal p。

### 3.4 编辑幅度与 `delta_U` 不是独立机制证据

排除 `(edit=0, delta_U=0)` 后，row/task/worker 轴仍呈负相关；formal-only lane 接近 -1。两者均由相同 initial/final geometry 及 operational reference 派生，存在内生几何耦合；worker/task 均值还受任务分配构成影响。

因此该结果可以写为：

> 较大几何改动与更负的 operational metric change 同时出现。

不能写为：

> 编辑幅度独立预测有害行为，或证明工人过度修正。

真正的行为机制需要随机化 proposal、任务内中心化或跨任务 held-out 验证。

### 3.5 `client_server_lag_seconds` 不能解释为网络延迟

事件表的 median client–server difference 约为 28,800 秒，即约 8 小时。这更符合时区或客户端/服务器时钟基准差，而不是网络延迟。完成 clock normalization 前，该字段只能作为时钟偏移审计。

### 3.6 自动验证仍偏重计数

现有测试已经覆盖：
- frozen counts；
- 缺失 RMSE 不填零；
- workbook 不截行；
- 简单行复制不改变 task/worker 聚合结果。

仍应增加：
- predictor alias/重复检查；
- 多重检验字段存在性；
- building-cluster inference gate；
- 禁止 row-level repeated-measure p 升级为 formal；
- 8 小时时钟偏移告警；
- `COVERAGE_AUDIT` 中每项缺口必须有“不可计算原因或物化输出”。

## 4. 当前可重复的核心数据结论

### 4.1 Semi 不是统一的不确定性降低器

q=.95 的 25 个配对任务：

- 10 收敛；
- 11 扩散；
- 4 熵不变；
- task-weighted mean ΔH = -0.0100；
- building-cluster 95% CI ≈ [-0.2194, 0.1766]；
- building exact sign-flip p≈0.914。

所以当前数据不支持总体净收敛，也不支持总体净扩散。

### 4.2 同一方向可以伴随不同质量变化

- `wc2JMjhGNzB_55b45...`：ΔH=-1.248，GT IoU change=+0.0349；
- `q9vSo1VnCiC_a424...`：全部 Semi 工人大幅修改后仍收敛，ΔH=-0.382，GT IoU change=+0.0237；
- `uNb9QFRL6hY_85e7...`：由 Manual 单峰转为 Semi 双峰，ΔH=+0.500，但 GT IoU change=+0.0444；
- `q9vSo1VnCiC_1cd4...`：由 Manual 单峰转为 Semi 四模式，ΔH=+1.386，GT IoU change=-0.0737。

这说明“收敛/扩散”和“更接近 operational GT”是两个不同结果。

### 4.3 任务效应明显大于工人效应

交叉方差分解：

- GT IoU：task variance≈0.00671，worker variance≈0.000349，约 19:1；
- 几何 pairwise RMSE：task≈0.00226，worker≈0.0000955，约 24:1；
- 元标签 cardinality：task≈0.0348，worker≈0.00765，约 4.6:1；
- log active time：worker≈0.621，task≈0.139，worker 约为 task 的 4.5 倍。

因此：
- 几何/质量不确定性主要是 task-centric；
- 时间差异主要是 worker-centric；
- 这两种不确定性不应压缩成一个总分。

### 4.4 高支持任务中多峰并未普遍消失

- PreScreen：强持续分裂 10/29；
- Calibration：强持续分裂 5/12；
- k=5 时 supported multimodal 在富集的 12-task 样本中只占约 15.8%；
- k=8/12/16/20 时约 45.3%/53.8%/54.3%/51.1%；
- k=22 全样本为 6/12 supported multimodal，另有 3/12 partition not-evaluable。

这说明增加工人数有时是在发现少数模式，而不是消灭分歧；但该 12-task 样本是高支持富集样本，不能外推为总体 prevalence。

### 4.5 工人模式倾向有统计信号，但不是 specialist 证据

- 当前 C1 全部可计算 lane 的 task-stratified permutation p≈0.002；
- leave-one-task-out median Spearman≈0.997；
- 旧 k=22 可评价 9-task lane p≈0.021，LOTO median≈0.948。

这支持“部分工人更常进入最大模式”的稳定倾向。它不能区分：
- 正确性；
- 协议偏好；
- 保守/延伸风格；
- 视觉能力；
- task allocation 残余差异。

需要 held-out tasks 和专家 mode audit 才能升级为可解释的 annotator style。

## 5. 增加 Semi 数据后的显著性情景

当前 observed building-level SD≈0.2758，observed mean |ΔH|≈0.0100。

若真实平均效应仍接近 0.010：
- 9 buildings：power≈5.1%；
- 18：5.3%；
- 36：5.5%；
- 72：6.1%；
- 按当前方差达到 80% power 约需 5,966 buildings，明显不可行。

若真实平均效应为：
- |δ|=0.05：约 239 buildings / 664 paired tasks；
- |δ|=0.10：约 60 / 167；
- |δ|=0.15：约 27 / 75；
- |δ|=0.20：约 15 / 42。

因此，“继续增加 Semi 就会得到总体显著降低不确定性”没有事实依据。可行的研究目标应改为：
1. 预先定义任务机制/歧义 strata；
2. 检验 task×Semi heterogeneity；
3. 同时增加独立 tasks、buildings 和每图工人数；
4. 保留完整标签分布，而不是只检验总体 mean ΔH。

## 6. 后续研究建议

### 主线 A：持续拓扑不确定性与模式发现

以独立 task 为单位，研究：
- 模式数和模式比例随 k 的稳定；
- 少数模式发现概率；
- topology-first clustering 与现有 complete-link 的 false split/false merge；
- expert-blind mode legitimacy audit。

### 主线 B：任务歧义与工人解释风格分解

模型应区分：
- task-level mode probabilities；
- worker-specific mode tendency；
- mode 内连续几何方差；
- contamination/error component。

只有 held-out task 预测有增量时，worker tendency 才可作为研究贡献。

### 主线 C：协议随机干预

对 opening/adjacent-space 等边界任务，随机比较清楚冻结的 enclosed 与 extended-visible instruction，区分：
- protocol-induced uncertainty；
- image/observability uncertainty；
- worker style；
- residual error。

### 主线 D：分布式训练与评估

若后续获得足够多 multi-rater tasks，再比较：
- single medoid GT；
- majority-mode GT；
- topology-mixture + conditional geometry；
- probability/distribution-aware layout model。

评价不应只用单一 IoU，还应包括：
- mode coverage；
- distribution calibration；
- generalized energy distance；
- best-of-N / expected utility；
- ambiguity detection。

## 7. 数据采集合同

下一批 Semi 数据至少冻结：

- 同一 base task 的 Manual/Semi 并行分配；
- 同一工人不能看同图两模式；
- building 分层、worker load 平衡、seed/manifest；
- 标注前 image traits 与 proposal geometry/version/hash；
- 每个 task 足够的 Manual 和 Semi 支持；
- 新增独立 buildings，而不是只在现有图片加人；
- 若目标是发现 20% 少数模式，k=4 只有约 18% 概率看到至少两名少数派，建议 k≥10–12；
- Scope/reference/协议歧义必须在结果前独立审查。

## 8. 结论

v5 已经覆盖本对话中的绝大多数实证要求，并修复了 v3 的主要数据层缺口。它现在可作为完整数据工作底稿，但仍不能把所有输出等同于正式统计证据。

最主要的科学判断是：

> 当前数据支持“标注不确定性具有强任务异质性、持续多峰和一定工人模式倾向”，不支持“模型预标注统一降低不确定性”。

增加 Semi 标注可行，但若继续以总体平均熵差显著为唯一目标，按当前观测效应成功概率接近名义显著性水平。更可行、也更有研究价值的方案，是预先定义歧义机制，增加独立 task/building，并以 mode discovery、distribution stability、protocol intervention 或 distribution-aware learning 作为主要问题。
