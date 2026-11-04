# 既有曲线、当前类别混合与早期接近采用参考

本目录为本轮独立统计交付。首先阅读 [REPORT_ZH.md](REPORT_ZH.md)。冻结来源 commit 为 `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b`。

## 已完成内容

1. 206 个普通 Manual 主目标池、每池 256 条原有自然路径的读取与验证；195 个 N≥20 主过程池。
2. 当前 DSTRUCT K3、RFUSE K2、JOINT K3/K4 楼外标签与实际前缀成员的连接。
3. 固定前 6 人类别分组，追踪 6→20 人的完整路径 Q、逐 n 可评 Q、首次 / 曾经 / 持续达标概率、D10 对照和合法同源记录劳动。
4. 具体初始类别集合对照及难度响应；所有预设对照均有支持表，零支持对照也保留。
5. 真实 OPPJOINT K4 小池进入政策中 2 个辅助端点的补接，保留自动版；全部 1,081 现有子集端点上的精确跨 n 动态规划。
6. 数值校验、3 张 PNG/SVG 科研图及可复现代码。

没有新融合、重评分、选队、分类选型、参考重建或大池政策试验。

## 推荐读取顺序

| 目的 | 文件 |
| --- | --- |
| 结论、口径、来源与适用范围 | `REPORT_ZH.md` |
| 固定图片且固定完整路径的逐 n Q 曲线 | `LANDMARK_COMPLETE_PATH_CURVE_SUMMARY.csv` |
| 自然路径主结果 | `LANDMARK_ALL_SUMMARY.csv` |
| 具体混合与难度 | `NAMED_MIXTURE_SUMMARY.csv`、`NAMED_MIXTURE_DIFFICULTY_SUMMARY.csv` |
| 所有计划对照的覆盖，包括 0 支持 | `NAMED_MIXTURE_ALL_PLANNED_SUPPORT_COUNTS.csv` |
| 曾达到 / 持续达到与逐 n 支持 | `LANDMARK_CURVE_SUMMARY.csv`、`LANDMARK_CURVE_DIFFICULTY_SUMMARY.csv` |
| 劳动 | `LANDMARK_RECORDED_LABOR_SUMMARY.csv` |
| K4 当前采用辅助版 | `K4_EARLY_QUALITY_ALL_SUPPORT_SUMMARY.csv` 中 `version=manual_order_assisted` |
| K4 原自动版 | 同表中 `version=automatic`；原仓库 CSV 未覆盖 |
| K4 两个真实命中与消费者改动 | `K4_SMALL_POOL_ASSISTED_ENDPOINT_MATCHES.csv`、`K4_MANUAL_ASSISTED_CONSUMER_CHANGES.csv` |
| 完整数值验收 | `FINAL_NUMERICAL_VERIFICATION.json`、`K4_EXACT_PROCESS_RECEIPT.json` |

Figure 1 左图使用**固定完整路径版**，字段 `metric=Q_complete`，每方法的图片和路径集合在 n=6…20 恒定。`LANDMARK_CURVE_SUMMARY.csv` 的 `metric=Q` 则在每个 n 使用当时可评路径，图片队列固定但可评路径集合可变；两者不要混称。完整路径版逐 n 差的平均与主结果 `Q_mean_complete_paths` 严格一致。

主过程“首次”和“曾达到”的观察窗口为 **6→20**，小池为已执行的 **3→N**。这些是平行的描述阈值 Q≥80/90，不是官方质量验收或在线停止规则。Q 针对当前采用参考；分数稳定不能替代几何逐边稳定。

## 复现

在完整仓库根目录运行。依赖 Python 3、NumPy、pandas、Matplotlib；没有融合引擎依赖。

```bash
python research/workers/mixture_patterns_and_c13_half_20261104/curves/restore_natural_sources.py --verify
python research/workers/mixture_patterns_and_c13_half_20261104/curves/analyze_existing_natural_paths.py
python research/workers/mixture_patterns_and_c13_half_20261104/curves/analyze_named_initial_mixtures.py
python research/workers/mixture_patterns_and_c13_half_20261104/curves/build_complete_path_quality_curves.py
python research/workers/mixture_patterns_and_c13_half_20261104/curves/analyze_exact_k4_small_pool_policies.py
python research/workers/mixture_patterns_and_c13_half_20261104/curves/verify_and_finalize_curves.py
python research/workers/mixture_patterns_and_c13_half_20261104/curves/plot_curve_findings.py
```

206 个原始自然输入约 406 MB，已经存在于冻结 GitHub 源中，不在本交付重复打包。`NATURAL_SOURCE_MANIFEST.json` 保存每个文件的不可变 URL、Git blob、SHA-256、字节数。`restore_natural_sources.py --download-missing` 可补取缺少的原文件；它拒绝覆盖已存在但哈希不同的本地文件。

其他依赖在 `OTHER_INPUT_SOURCE_HASHES.csv`：当前标签与原答表来自前一解释批次；K4 端点/优先组来自既有 v2.1 研究；57 辅助端点来自人工顺序影响批次。本次完整交付按仓库路径覆盖本目录即可，原自动端点和自动聚合文件保持不变。

## 核心字段

- `method` 为当前确切分类 ID，不与旧 V3 政策同名。
- `anchor=6/10` 为分类组别的固定时点；`k` / `n` 是当前前缀人数。
- `min_arm_paths=16` 为主要对照，`8` 为支持敏感性。
- `with_value / without_value / effect` 均是同图两臂量；效应方向为含指定类 / 指定类集合减去基线。
- `images / buildings` 是该指标的真实支持；条件均值缺失时支持可比达标概率少。
- `mean_image` 是图片等权；`mean_building` 与 `building_bootstrap_*` 是楼等权。不要把楼均区间当成图片均值区间。
- `time_source` 必须保留；`not_same_source_complete_pool` 不参与累计劳动推断。
- `ever_Q80`：从观察窗起点至 n 曾有有限 Q≥80；`sustained_Q80_through20`：从 n 到 20 每个前缀均达到。
- `first_*_given_reached`：只在达到路径上计算；一定与未达标概率 / 达标概率一同阅读。
- K4 的 `automatic` 和 `manual_order_assisted` 两个版本并存。新增可评支持不构成原共同支持上的数值提升。

所有统计保持实际路径重复权重。Q 缺失从不变为 0 分。建筑 bootstrap 2,000 次、种子 20261104；区间用于显示现有建筑支持的异质性，不代表对全库或新部署的独立因果验证。
