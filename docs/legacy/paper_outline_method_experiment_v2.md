# 2 方法（Metrics & Definitions）

本节给出用于量化“改动幅度/工作量”与“质量/可靠性”的指标体系，并明确各指标适用范围与局限性。核心原则是将 **工作量幅度** 与 **质量/可靠性** 解耦：

- 改动幅度只回答“改了多少”，不回答“改得对不对”；
- 质量/可靠性通过一致性（IAA、LOO 共识）、门控后的标准 layout 指标、以及不确定性（bootstrap CI）回答。

## 2.1 标注对象与元信息（Scope/Difficulty/Model）

我们的标注输入为角点（Corner）为主；墙面 polygon 不要求绘制。

每次提交建议记录三类元信息（均来自 Label Studio choices 的显示文本）：其中 `scope` 必填；`difficulty/model_issue` 仅在适用时填写（否则留空），以减少噪声。

1. `scope`（单选，决定是否进入主指标）
   - `In-scope：只标相机房间 (Normal / Camera room only)`：能形成唯一、可复现的包络，即墙-天花与墙-地面外边界存在稳定的 y_ceil(x), y_floor(x)
   - 若不满足可复现闭合条件，则分流到一个 OOS 子类（几何假设不成立 / 边界不可判定 / 错层多平面 / 证据不足）
2. `difficulty`（多选，解释耗时/误差来源）：遮挡、低纹理、拼接缝、反光、低质、`residual`（尽力调整但 3D 仍不佳）等
3. `model_issue`（仅半自动条件，多选；初始化很好无需修改可不选；OOS 时允许留空）
   - 跨门扩张：模型把门后/相邻空间当作同一房间
   - 漏标：模型没有覆盖完整 camera room（漏掉部分墙角/边界）
   - 漂移：角点整体或局部位置有偏移
   - **角点重复/一角多点（新）**：同一物理拐角被标了多个点（如某处 3 个点），导致配对不稳定；人工应删掉多余点
   - 配对异常：predict 与 annotation 角点总数相差大且无法配对，或配对严重错乱（区别于 corner_duplicate，强调整体数量/拓扑问题）
   - 预标注失效：大范围错误需从零重画；仅当其他类型都无法概括时选此项

**门洞规则（写死以避免“需要理解算法”）**：

- 若门框/墙垛清晰：边界止于门框/墙垛处，不跨门洞，仍为 `scope=In-scope`。
- 若没有可靠停止点、必须靠语义“猜”才能闭合：选 `scope=OOS：边界不可判定`，不硬凑 cuboid。

## 2.2 改动幅度 / 工作量（主要用于 Semi 条件）

设任务 $t$ 的模型初始化结果为 $P_t$，标注者 $u$ 的提交结果为 $A_{t,u}$。

### 2.2.1 图像空间 Layout Polygon IoU（改动幅度）

用图像空间 polygon 的交并比刻画从初始化到最终结果的形状改动规模：

$$
\mathrm{IoU}(X,Y)=\frac{|X\cap Y|}{|X\cup Y|}.
$$

在我们的 Corner-only 标注计划中，$X,Y$ 均由角点生成的 layout polygon 得到（不依赖墙面手绘 polygon）。半自动初始化条件下默认比较：

$$
\mathrm{IoU}_{\text{edit}}(t,u)=\mathrm{IoU}(P_t, A_{t,u}).
$$

> 解释：IoU 越低通常表示改动越大，但它不保证改动是正确的，因此它仅作为工作量/改动幅度信号。

### 2.2.2 边界 RMSE（改动幅度，更鲁棒）

当角点数量不一致或配对不稳定时，点对点 RMSE 会失真。我们用从角点生成的上/下边界曲线 $y_{ceil}(x),y_{floor}(x)$ 在离散网格上的误差作为鲁棒几何改动幅度指标（实现上可做可选平滑与周期插值）：

$$
\mathrm{BoundaryRMSE}(X,Y)=\sqrt{\mathbb{E}_x\big[(\Delta y_{ceil}(x))^2+(\Delta y_{floor}(x))^2\big]}.
$$

### 2.2.3 角点匹配 RMSE（辅，需门控）

设预测角点集合为 $\{p_i\}_{i=1}^{n}$，标注角点集合为 $\{g_j\}_{j=1}^{m}$，定义距离 $d(p,g)$。用 Hungarian 匹配得到：

$$
\mathrm{RMSE}=\sqrt{\frac{1}{N}\sum_{i=1}^{N} d\big(p_i, g_{\pi(i)}\big)^2},\;N=\min(n,m).
$$

该指标仅在“角点配对覆盖率足够高”等门控通过时启用，用于补充解释改动来自哪里。

## 2.3 质量与可靠度（必须独立于“改动幅度”）

本节定义标注者间一致性（IAA）与标注者可靠度 $r_u$。关键原则：

- **不允许 circularity**：共识不能包含被评估者自身，否则 $r_u$ 系统性偏高。
- **方案 A（推荐）**：$r_u$ 只在“统一基准条件”的校准集上估计（纯人工 Manual），避免半自动初始化把大家“拉齐”导致专家评分被工具污染。

### 2.3.1 In-scope 任务级一致性 $IAA_t$

对任务 $t$，收集所有标注者的提交结果 $\{A_{t,u}\}_{u\in U_t}$（仅在 $|U_t|\ge2$ 时定义）。

**仅对 `scope=In-scope` 的样本** 计算任务内一致性：

$$
IAA_t = \mathrm{median}_{u\ne v,\;u,v\in U_t}\; \mathrm{IoU}(A_{t,u}, A_{t,v}).
$$

> 解释：OOS 样本被定义为“任务目标不可复现/假设不成立”，强行纳入 IAA 会把“目标不唯一”的方差混进“人的稳定性”，因此主一致性与 $r_u$ 都只在 In-scope 上估计。

### 2.3.2 Leave-One-Out 共识与 $r_u$

在任务 $t$ 上定义 leave-one-out 共识：

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

用 percentile bootstrap 估计 $r_u$ 的置信区间（CI），并在有效任务数达到阈值时报告（例如至少 $\ge5$ 个多标注 In-scope 任务）。

### 2.3.3 标准 layout 指标与门控

为了与 HoHoNet/HorizonNet 常用指标对齐，我们在 **满足门控** 且 `scope=In-scope` 的样本上额外报告标准 layout 指标（例如 2D/3D IoU、深度 RMSE、$\delta_1$）。

门控失败原因（如角点归一化失败、配对覆盖率低、角点对数不一致、深度渲染失败）需记录并在报告中披露，避免“只报能算的样本”带来偏差。

## 2.4 OOS（超出假设）统计（不进入主指标池）

当 `scope` 选择为任一 OOS 子类时：

- 主 layout 指标（标准 2D/3D/depth 指标）默认剔除；
- IAA 与 $r_u$ 的主估计默认剔除；
- 仍需单列报告：OOS 比例、OOS 子类分布，以及（可选）OOS 判定本身的一致性（例如 label agreement）。

---

# 3 实验设置（Study Design）

目标是同时检验：半自动初始化的效率收益（RQ1）、质量影响（RQ2）、以及基于一致性/LOO 可靠度的专家识别与任务分配收益（RQ3）。

## 3.1 实验目的

通过对照实验收集标注过程数据（active time）与结果数据（角点 + `scope/difficulty/model_issue`），并在统一评估框架下输出指标、门控原因、反例案例库与统计置信区间。

## 3.2 参与者

共约 $N\approx 10$ 名参与者（可按经验分层）。所有人接受统一培训，尤其是：

- “只标相机所在主房间（camera room only）”
- 门洞停止规则
- 何时必须分流到 OOS（边界不可判定/错层多平面/证据不足/几何不成立）

## 3.3 条件分组与数据组织（最终 5 项目/5 导出）

### 3.3.1 条件定义

- **Semi（实验组）**：提供模型初始化，标注者可修改或保留。
- **Manual（对照组）**：不提供初始化，从零完成标注。

除初始化与否外，界面、字段与导出解析规则保持一致。

### 3.3.2 五组数据划分

为便于工程落地与统计分析，我们将导出数据按 **5 个项目/5 份导出**组织：

- `Manual_Test`（100）：纯人工主对照
- `SemiAuto_Test`（100）：半自动初始化主对照
- `calibration_manual`（30，多标注）：统一基准校准集（用于估计 $r_u$）
- `validation_manual`（60）：验证集（纯人工）
- `validation_semi`（60）：验证集（半自动初始化）

数据划分原则：

- `Manual_Test` 与 `SemiAuto_Test` 可使用同一批 100 张图像，但应由不同参与者组完成，避免同一人跨条件学习/记忆。
- `calibration_manual` 与两份 `validation_*` 默认与主对照互斥。
- 全部集合的抽样规则预先固定，并采用分层规则保证难度 proxy 分布可比。

## 3.4 效率评估（RQ1）

指标：`active time`（会话内取 max、跨会话求和）。展示至少包含：

- Level 1：Manual vs Semi 的 active time 分布（中位数/四分位/降幅），按经验分层。
- Level 2：active time 与改动幅度（$\mathrm{IoU}_{edit}$、BoundaryRMSE 等）的关系，排查“省时是否来自少改/瞎改”。

## 3.5 可靠性、一致性与反例（RQ2/RQ3 基础）

### 3.5.1 校准集合 $C_{manual}$（30 张，多标注）

`calibration_manual` 对应 $C_{manual}$：每张至少由 $k\ge3$ 人在 Manual 条件下独立标注。该集合用于：

- 估计 In-scope 的 $IAA_t$ 分布
- 构建 LOO 共识并估计 $r_u$（中位数 + bootstrap CI）
- 构建“稳定共识/不稳定任务”的反例候选池

### 3.5.2 反例定义（自动候选 + 人工复核）

反例候选由可复现规则筛选（并按 `scope/difficulty/model_issue` 分层展示）：

- 低一致性：$IAA_t$ 位于分布尾部；
- 修改模式异常：改动幅度极大但一致性不升，或幅度很小但与他人显著不一致；
- 门控失败：标准 layout 指标因门控不可用但图像差异显著；

最终由人工复核确认并写入论文“局限性/失败案例”。

## 3.6 专家识别与分配策略验证（方案 A，RQ3）

### 3.6.1 方案 A：统一基准条件（Manual）估计 $r_u$

为避免工具效应污染，$r_u$ 只在 `calibration_manual` 上估计（In-scope、多标注任务）。

### 3.6.2 验证集合 $V$ 与任务分配对照

在 `validation_manual` 与 `validation_semi` 内分别比较两种分配策略：

- **Baseline**：分层随机分配（按难度/OOS proxy 平衡）。
- **Proposed**：按 $r_u$ 加权分配（例如难例/复核优先给高 $r_u$），但保持相同的分层抽样与预算约束。

> 备注：若验证集全部为单标注，将无法直接比较 $IAA_t$。工程上可采用“验证集内抽取子集做 2–3 人复核”的方式，使一致性对照可计算。

### 3.6.3 验证指标与展示

- 一致性：验证子集上的 $IAA_t$ 是否提升；
- 效率：相同预算/产出下 active time 是否下降；
- 鲁棒性：OOS 比例与子类分布是否更稳定，门控失败率是否下降；

展示包括：$r_u$ 与 active time 的关系；以及分配策略前后（一致性/效率/反例分布）的变化。
