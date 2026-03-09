# 1 研究问题与贡献（Research Questions & Contributions）

本文聚焦于“全景室内 layout（角点）半自动标注”的真实落地问题：当无法对所有样本进行逐一人工精标审核时，如何在控制偏差的前提下，量化半自动流程的效率收益、质量/可靠性变化，并进一步用多任务表现估计标注者可靠度，从而实现任务分配与专家识别。

## 1.1 研究问题（RQs）

- **RQ1（效率）**：半自动初始化是否降低真实活跃标注时间（active time）？下降比例是多少？
- **RQ2（质量/可靠性/一致性）**：当无法对全部样本人工精标审核时，半自动流程能否提升（或至少不降低）标注结果的可靠性与一致性？能否系统性发现“乱搞/异常编辑”的反例？
- **RQ3（任务分配/专家识别）**：能否基于多任务表现估计标注者可靠度 $r_u$ 与速率特征，并利用“擅长任务类型”实现更优任务分配，从而提升总体质量与效率？

## 1.2 关键贡献（写作时可精炼为 3–5 条）

1. **将工作量幅度与质量/可靠性解耦**：改动幅度只回答“改了多少”，质量/可靠性通过 IAA、LOO 共识、$r_u$ 及不确定性估计回答。
2. **可复现实验设计**：Manual vs Semi 的对照 + 校准集估计 $r_u$（避免工具把人“拉齐”导致能力评估污染）。
3. **透明门控与缺失披露**：将“不可计算/不可比较”的失败原因显式记录并条件化报告，避免 selection bias。
4. **把结构差异当作信号而非直接剔除**：例如角点对数差（$\Delta n_{pairs}$）用于分层与诊断，而不是粗暴 gate 掉所有样本。

---

# 2 方法（Metrics & Definitions）

本节给出用于量化“改动幅度/工作量”与“质量/可靠性”的指标体系，并明确各指标适用范围与局限性。核心原则：

- 改动幅度只回答“改了多少”，不回答“改得对不对”；
- 质量/可靠性独立估计，避免与工作量指标形成 circularity；
- 所有剔除/失败均必须记录原因并在报告中披露。

## 2.1 标注对象与元信息（Scope/Difficulty/Model Issue）

我们的标注输入以角点（Corner）为主；不强制要求绘制墙面 polygon。

每次提交建议记录三类元信息（来自 Label Studio choices 的显示文本），其中 `scope` 必填；其余字段在适用时填写（不适用留空以降低噪声）。

1. `scope`（单选，决定是否进入主指标）
   - **In-scope：只标相机所在房间（camera room only）**：能形成唯一、可复现的包络，即墙-天花与墙-地面外边界存在稳定的 $y_{ceil}(x), y_{floor}(x)$。
   - **OOS 子类**：几何假设不成立 / 边界不可判定 / 错层多平面 / 证据不足。
2. `difficulty`（多选，解释耗时/误差来源）：遮挡、拼接缝、玻璃/反光干扰、画质差、`residual`（尽力调整但 3D 仍不佳）等。
3. `model_issue`（仅 Semi 条件，多选）：预标注失效、配对异常、包含相邻空间、漏标、错位等。

**门洞规则（尽量写死以避免“需要理解算法”）**：

- 若门框/墙垛清晰：边界止于门框/墙垛处，不跨门洞，仍为 `scope=In-scope`。
- 若没有可靠停止点、必须靠语义“猜”才能闭合：选 `scope=OOS：边界不可判定`，不硬凑 cuboid。

## 2.2 改动幅度 / 工作量（主要用于 Semi 条件）

设任务 $t$ 的模型初始化结果为 $P_t$，标注者 $u$ 的提交结果为 $A_{t,u}$。

### 2.2.1 图像空间 Layout Polygon IoU（改动幅度）

用图像空间 polygon 的交并比刻画从初始化到最终结果的形状改动规模：

$$
\mathrm{IoU}(X,Y)=\frac{|X\cap Y|}{|X\cup Y|}.
$$

在 Corner-only 标注计划中，$X,Y$ 均由角点生成的 layout polygon 得到。

半自动条件下默认比较：

$$
\mathrm{IoU}_{\text{edit}}(t,u)=\mathrm{IoU}(P_t, A_{t,u}).
$$

> 解释：IoU 越低通常表示改动越大，但它不保证改动是正确的，因此仅作为工作量/改动幅度信号。

### 2.2.2 边界 RMSE（改动幅度，更鲁棒）

当角点数量不一致或配对不稳定时，点对点 RMSE 会失真。用从角点生成的上/下边界曲线 $y_{ceil}(x),y_{floor}(x)$ 在离散网格上的误差作为更鲁棒的几何改动幅度指标：

$$
\mathrm{BoundaryRMSE}(X,Y)=\sqrt{\mathbb{E}_x\big[(\Delta y_{ceil}(x))^2+(\Delta y_{floor}(x))^2\big]}.
$$

### 2.2.3 角点匹配 RMSE（辅助，需门控）

设预测角点集合为 $\{p_i\}_{i=1}^{n}$，标注角点集合为 $\{g_j\}_{j=1}^{m}$，距离 $d(p,g)$ 为欧式距离。使用 Hungarian 匹配得到：

$$
\mathrm{RMSE}=\sqrt{\frac{1}{N}\sum_{i=1}^{N} d\big(p_i, g_{\pi(i)}\big)^2},\;N=\min(n,m).
$$

该指标仅在“配对覆盖率足够高/拓扑可比”等门控通过时启用，用于补充解释改动来自哪里。

## 2.3 质量与可靠度（必须独立于“改动幅度”）

本节定义标注者间一致性（IAA）与标注者可靠度 $r_u$。关键原则：

- **不允许 circularity**：共识不能包含被评估者自身，否则 $r_u$ 系统性偏高。
- **推荐方案 A**：$r_u$ 只在统一基准条件的校准集（纯 Manual）上估计，避免半自动初始化把大家“拉齐”导致能力被工具污染。

### 2.3.1 In-scope 任务级一致性 $IAA_t$

对任务 $t$，收集所有标注者的提交结果 $\{A_{t,u}\}_{u\in U_t}$（仅在 $|U_t|\ge2$ 时定义）。

**仅对 `scope=In-scope` 样本**计算任务内一致性：

$$
IAA_t = \mathrm{median}_{u\ne v,\;u,v\in U_t}\; \mathrm{IoU}(A_{t,u}, A_{t,v}).
$$

使用中位数而非均值，以降低极端标注的影响。

### 2.3.2 Leave-One-Out（LOO）共识与 $r_u$

对任务 $t$ 定义 leave-one-out 共识：

$$
C_t^{(-u)} = \arg\max_{A_{t,w},\;w\in U_t\setminus\{u\}}\; \mathrm{median}_{v\in U_t\setminus\{u,w\}}\;\mathrm{IoU}(A_{t,w}, A_{t,v}).
$$

并计算：

$$
\mathrm{IoU}_{\text{LOO}}(t,u)=\mathrm{IoU}(A_{t,u}, C_t^{(-u)}).
$$

标注者可靠度定义为（同样仅使用 In-scope 且多标注任务）：

$$
r_u = \mathrm{median}_{t\in\mathcal{T}_u}\;\mathrm{IoU}(A_{t,u}, C_t^{(-u)}).
$$

用 percentile bootstrap 估计 $r_u$ 的置信区间（CI），并在有效任务数达到阈值时报告（例如 $\ge5$ 个多标注 In-scope 任务）。

### 2.3.3 标准 layout 指标与门控（含“可计算性”与“可比性”分离）

为与 HoHoNet/HorizonNet 常用指标对齐，我们在 `scope=In-scope` 且通过门控的样本上额外报告标准 layout 指标：

- **2D IoU / 3D IoU**：HoHoNet 风格的地面投影重合度（2D）与考虑高度的体积重合度（3D）。
- **layout-rendered depth RMSE / $\delta_1$（可选）**：将 layout（角点/边界）按几何关系**渲染**为全景视角下的“每像素深度图”，再对两份 layout 的深度图做像素级 RMSE 与阈值准确率（$\delta_1$）。

> 重要澄清：这里的“深度图”并非深度网络预测输出，也不需要真实深度传感器 GT；它是由 layout 几何直接生成的 **rendered depth map**，用于把布局误差转换成更接近 3D 几何一致性的像素级信号。若论文主结果不打算使用该指标，可将其放入附录/补充实验。

**门控需要拆成两类并分别披露：**

- **可计算性门控（computability）**：几何归一化失败、polygon 无法构造、layout→rendered-depth 生成失败等。
- **可比性门控（comparability, 仅对点级指标）**：点对点 RMSE 需要稳定匹配时，才要求角点对数一致/覆盖率足够。

**P0-1（关键实现决策）**：对“标准 layout 指标”（polygon/深度类）不再强制要求预测与标注角点对数一致。

- `n_pairs_mismatch` **不再**作为标准 layout 指标的 gate 条件（避免把“强纠错/高工作量”样本系统性排除）。
- 与结构差异相关的信息（例如 $|\Delta n_{pairs}|$、是否存在 odd points、配对 warning）被保留为 **分层/诊断变量**，用于透明报告与反例筛选。
- **仅**在点级可比指标（例如 pointwise RMSE）里保留“角点可比性门控”，并把失败原因单列披露。

同时记录所有门控失败原因并在报告中披露（overall 与 in-scope 两口径），避免“只报能算的样本”带来偏差。

## 2.4 结构差异信号：角点对数差（$\Delta n_{pairs}$）

定义角点对数差（示例）：

$$
\Delta n_{pairs}(t,u)= n_{pairs}(A_{t,u}) - n_{pairs}(P_t),\quad |\Delta n_{pairs}|\ \text{用于分层}.
$$

直觉：

- $|\Delta n_{pairs}|$ 更像“结构性纠错/难度/预标注拓扑问题”的 proxy，而不是可靠性本身；
- 该信号应优先用于 **分层报告与反例筛选**，而不是直接作为 layout 主指标的全局 gate。

## 2.5 OOS（超出假设）统计（不进入主指标池）

当 `scope` 为任一 OOS 子类时：

- 标准 layout 指标默认不进入主报告汇总；
- IAA 与 $r_u$ 的主估计默认不进入；
- 必须单列报告：OOS 比例、OOS 子类分布，以及（可选）OOS 判定一致性。

当同一任务出现 “有人 In-scope / 有人 OOS” 分歧时，单独标记为人工复核样本池。

---

# 3 实验设置（Study Design）

目标是同时检验：半自动初始化的效率收益（RQ1）、质量/可靠性影响（RQ2）、以及基于一致性/LOO 可靠度的专家识别与任务分配收益（RQ3）。

## 3.1 实验目的

通过对照实验收集标注过程数据（active time）与结果数据（角点 + `scope/difficulty/model_issue`），并在统一评估框架下输出：指标、门控原因、分层统计、反例案例库与统计置信区间。

## 3.2 参与者

参与者接受统一培训：Label Studio 基础使用、工具使用、camera room only 规则、OOS 分流规则、门洞停止规则。

为降低偏差：

- Manual 与 Semi 两组中“新手/有经验”比例匹配；
- 任务随机抽样并按难度 proxy 分层，使条件间可比。

## 3.3 条件分组与数据组织（建议 5 项目 / 5 份导出）

### 3.3.1 条件定义

- **Semi（实验组）**：提供模型初始化，标注者可修改或保留。
- **Manual（对照组）**：不提供初始化，从零完成标注。

除初始化与否外，界面、字段与导出解析规则保持一致。

### 3.3.2 五组数据划分（示例）

- `Manual_Test`（100）：纯人工主对照
- `SemiAuto_Test`（100）：半自动初始化主对照
- `calibration_manual`（30，多标注）：统一基准校准集（用于估计 $r_u$）
- `validation_manual`（60）：验证集（纯人工）
- `validation_semi`（60）：验证集（半自动初始化）

数据划分原则：

- `Manual_Test` 与 `SemiAuto_Test` 可使用同一批图像，但由不同参与者组完成，避免同一人跨条件学习/记忆。
- `calibration_manual` 与两份 `validation_*` 与主对照互斥。
- 抽样规则预先固定，并采用分层规则保证难度 proxy 分布可比。

## 3.4 效率评估（RQ1）

核心指标：`active time`（会话内取 max、跨会话求和）。展示至少包含：

- Level 1：Manual vs Semi 的 active time 分布（中位数/四分位/降幅），按经验分层。
- Level 2：active time 与改动幅度（$\mathrm{IoU}_{edit}$、BoundaryRMSE、$|\Delta n_{pairs}|$）的关系，用于排查“省时是否来自少改/瞎改”。

## 3.5 可靠性、一致性与反例（RQ2 / RQ3 基础）

### 3.5.1 校准集合 $C_{manual}$（30 张，多标注）

`calibration_manual` 对应 $C_{manual}$：每张至少由 $k\ge3$ 人在 Manual 条件下独立标注，用于：

- 估计 In-scope 的 $IAA_t$ 分布；
- 构建 LOO 共识并估计 $r_u$（中位数 + bootstrap CI）；
- 构建“稳定共识 / 不稳定任务”的反例候选池。

### 3.5.2 反例定义（自动候选 + 人工复核）

反例候选由可复现规则筛选，并按 `scope/difficulty/model_issue` 与 $|\Delta n_{pairs}|$ 分层展示：

- **低一致性**：$IAA_t$ 位于分布尾部；
- **修改模式异常**：改动幅度极大但一致性不升，或幅度很小但与他人显著不一致；
- **门控失败但差异显著**：主指标因可计算性失败不可得，但 BoundaryRMSE 或其他 proxy 显示差异显著；

最终由人工复核确认并写入论文“局限性/失败案例”。

## 3.6 专家识别与分配策略验证（方案 A，RQ3）

### 3.6.1 方案 A：统一基准（Manual）估计 $r_u$

为避免工具效应污染，$r_u$ 仅在 `calibration_manual` 的 In-scope、多标注任务上估计。

### 3.6.2 验证集合 $V$ 与任务分配对照

在 `validation_manual` 与 `validation_semi` 内分别比较两种分配策略：

- **Baseline**：分层随机分配（按难度/OOS proxy 平衡）。
- **Proposed**：按 $r_u$ 加权分配（难例/复核优先给高 $r_u$），并允许按任务类型（如高 $|\Delta n_{pairs}|$、特定 model_issue）匹配“擅长者”。

> 备注：若验证集全部为单标注，将无法直接比较 $IAA_t$。工程上可采用“验证集内抽取子集做 2–3 人复核”的方式，使一致性对照可计算。

### 3.6.3 验证指标与展示

- 一致性：验证子集上的 $IAA_t$ 是否提升；
- 效率：相同预算/产出下 active time 是否下降；
- 鲁棒性：OOS 比例与子类分布是否更稳定，门控失败率是否下降；

展示包括：$r_u$ 与 active time 的关系；以及分配策略前后（一致性/效率/反例分布）的变化。

## 3.7 敏感性与消融（P0-1 相关）

为把“门控策略改变是否影响结论”说清楚，至少做一项可复现敏感性分析：

- **门控前后对比**：在同一批导出上，对比 “旧逻辑（layout 因 n_pairs_mismatch gate）” vs “P0-1（layout 不 gate mismatch）” 的：
  - in-scope 覆盖率（layout*used）、失败原因分布（gate_reason），以及 $|\Delta n*{pairs}|$ 的分布变化。
  - 关键结论的稳定性（RQ1：time 差异；RQ2：IAA/$r_u$；RQ3：分配收益）是否在分层后保持一致。
- **分层稳健性**：按 $|\Delta n_{pairs}|$ 分层报告，检查结论是否主要由某一层驱动（避免 Simpson’s paradox）。

---

# 4 报告与透明披露（Reporting & Transparency）

为避免 selection bias，主结果必须包含以下“固定输出”：

1. **覆盖率两口径**：overall 与 in-scope 的 `layout_used` 覆盖率。
2. **失败原因分布**：门控失败原因（gate_reason）在 overall 与 in-scope 条件下分别统计。
3. **分层表（最少两张）**：
   - 表 A：按 $|\Delta n_{pairs}|$ 分层的覆盖率/失败原因/改动幅度统计；
   - 表 B：按 `difficulty/model_issue` 分层的效率与一致性统计；

4. **门控敏感性披露（对应 P0-1）**：对至少一组核心结果同步给出“严格 gate（历史口径）”与“P0-1 口径”的对照，明确说明差异来自覆盖率变化而非指标定义漂移。

> 原则：不要把“不可计算样本”静默丢弃；要把“为什么不可算/不可比”作为结果的一部分。

---

# 5 用标注数据重训练的闭环计划（Iterative Training Plan, 可作为扩展实验/附录）

## 5.1 目标与假设

利用累积的 Manual/Semi 标注数据改进初始化模型，目标是：

- 提升初始化质量：提高 $\mathrm{IoU}_{edit}$（更接近最终结果，意味着更少改动）；
- 降低结构性错误：降低 $|\Delta n_{pairs}|$ 与“配对异常/预标注失效”等 `model_issue` 频率；
- 降低门控失败率：提升可计算性覆盖率，并在 in-scope 口径下保持稳定。

## 5.2 数据切分与防泄漏

- 以图像为单位进行 train/val/test 切分；
- 校准集与测试集严格不参与训练；
- Semi 条件下的最终标注可用于训练 label，但评估需在固定 holdout 上完成。

## 5.3 评估方式

- 在同一套 holdout 上对比“旧初始化 vs 新初始化”对标注流程的影响：active time、$\mathrm{IoU}_{edit}$、BoundaryRMSE、$|\Delta n_{pairs}|$ 分布变化；
- 检查是否出现“工具把人拉齐”导致 $r_u$ 估计偏移：保持 $r_u$ 仍只在 Manual 校准集估计。

---

# 6 局限性与威胁（Limitations & Threats to Validity）

- 标注目标不唯一（OOS）与 in-scope 边界判定带来的主观性；
- 不同经验水平导致的交互与学习效应（需在实验设计中平衡/隔离）；
- 门控导致的缺失机制（MNAR 风险），必须通过透明披露与分层报告缓解。
