# 方法采用与本轮覆盖的衔接表

主入口为 [`METHOD_SELECTION_AND_COVERAGE.csv`](METHOD_SELECTION_AND_COVERAGE.csv)。它沿用已合并 main 的 **11 个方法家族身份**，补上本轮实际保存的比较和选择理由；不是另一本人员主报告，也不是把所有家族组成一个统一分类层级。

实际读取 main 为 `ef148c82df18582228b2d23837faa2659e79eba7`，真人底层数据 v2。本目录新工作为整理与关联；新建类、新融合均为 0。

## 如何读取

- `classification_inputs` 保留原建类依据；`evaluation_condition` 表示实际效果评价条件，两者不同。原登记把 A2 的评价只写 Manual，但已保存的旧 n20 和直接 A/C 也包含 Semi。本表据此补齐评价范围，没有宣称本轮重新形成 Semi A2 分类。
- `people_support`、`hierarchy` 是原登记的整体描述。实际目标建筑应使用 `evaluation_label_identity` 指定的楼外或历史冻结映射；ALL 成员表与逐折成员表分开保存，跨折按角色语义对齐。
- `inherited_adoption_at_main` 保留入场结论；`current_maintext_status`、`current_selection_reason`、`current_retained_uses_and_findings` 是本轮完整比较后的用途判断。旧结果不因没有本轮新增计算而失效。
- `current_full_configuration_coverage` 与 `current_fine_configuration_coverage` 为 JSON 记录，可直接展开。前者按粗/细层分别给完整构成格、面板、图/楼、成员集合与失败/时间资格；后者报告固定完整父类人数向量后实际可细分的机会。**不是所有父类都存在额外细类。**
- `current_strict_ABC_coverage`、`current_legacy_n20_coverage`、`current_direct_AC_coverage` 为按 Manual/Semi 分开的 JSON 计数。`registered_rows` 是保存引用数；`unique_physical_sets`、`unique_backgrounds`、图/楼数更适合识别真实支持。各方法/阶段引用重叠，不能将这些数相加当独立实验次数。
- `current_*_condition_rows` 是本轮分析网格大小，不是新分类数。严格 ABC、旧 Y/Z 可重叠 ABC、没有 B 的直接 A/C、无向有限面板端点对具有不同解释口径，不能互相代替。
- `current_raw_role_*` 连接实际原答与当前难度，不是融合效应；含粗细、来源与角色的重复对照。0 表示本轮没有重新整理该模块，不表示历史方法不存在证据。
- `evidence_paths` 以 `|` 分隔仓库相对路径，全部实际存在。四主分类完整分布在相邻 `configurations/`；有限面板端点对及严格比较在 `exchanges/`；大比例构成变化在 `direct_ac/`；实际标法和难度解释在 `difficulty/`。

## 本轮粗细关系的实际支持

| 方法/条件 | 父构成格 | 可以继续细分的父构成格 | 细构成格 | 用途判断 |
|---|---:|---:|---:|---|
| Manual 结构 | 1,633 | 159 | 1,867 | ALL 三类没有独立细层，部分楼外折实际有细分；只在对应机会解释增量 |
| Manual 联合 Q/T | 3,297 | 0 | 3,297 | 本轮该面板粗细标签等价，不重复宣称细层贡献 |
| Semi 结构 | 284 | 162 | 954 | 简化/常规等父内表达差异保留，不能由单一均值跨度推出普遍互换 |
| Semi 联合 Q/T | 800 | 272 | 1,274 | 父内时间和质量构成有可评机会，须同时报告真实成员容量 |

所有完整格均保留，单一成员格的成员波动记不可估计。范围数值不作为正向升质效果，构成的分布差异、定向替换、效率和原答解释分别保留。

## 复现与接续

`python research/workers/personnel_mixture_comparison_20261022/integration/build_method_registry.py`

脚本读取已保存的事件关联和汇总，更新本目录表及相邻 `inputs/` 小输入副本；不修改 `configurations/`、融合端点或人员主报告。必要原标签、ALL 名单与中心均实际复制，入口为 [`../inputs/SOURCE_MANIFEST.csv`](../inputs/SOURCE_MANIFEST.csv)。原始与输出 SHA256、大小、行数、阶段身份和是否仅作 gzip 封装逐文件列明。读取至 EOF 并核对行宽、行数后才保存完成回执。
