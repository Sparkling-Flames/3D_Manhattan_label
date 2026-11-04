# 当前 DSTRUCT 直接 AC：分析模块

本目录是本轮数值接续、质量分项、同源记录劳动、条件规律和不确定性分析的完整产物。首先读 [REPORT_ZH.md](REPORT_ZH.md)；根目录报告负责与容量审计、原生机制轨迹、原图图册及整批交付衔接。

## 核心入口

| 内容 | 文件 |
| --- | --- |
| 中文结果与条件解释 | `REPORT_ZH.md`、`KEY_FINDINGS.csv` |
| 六方向所有实际预算与支持 | `SIX_DIRECTION_Q_BY_BUDGET.csv` |
| 14/7、20/7及其它核心预算易读表 | `CORE_READABLE_RESULTS.csv`、`CORE_SIX_DIRECTION_Q.csv` |
| 存量6/3、8/4、10/5全部六方向 | `SMALL_BUDGET_SIX_DIRECTION_RESULTS.csv` |
| 自动与批准辅助版本的逐物理对完整数据 | `PHYSICAL_PAIRS_AUTOMATIC.csv.gz`、`PHYSICAL_PAIRS_ASSISTED.csv.gz` |
| 原事件身份、登记方向与去重映射 | `PAIR_EVENT_ALIASES.csv.gz`、`REGISTERED_ORIENTATION_ENDPOINTS.csv.gz` |
| 逐图Q及分项 | `MAIN_IMAGE_EFFECTS.csv.gz`、`COMPONENT_IMAGE_EFFECTS.csv.gz` |
| 分项汇总及实际指标分母 | `COMPONENT_SUMMARIES.csv.gz`、`COMPONENT_NATIVE_SUPPORT.csv` |
| 难度、结构、用途、难度×用途、D和设计合同 | `CONDITION_STRATIFIED_Q.csv`、`CONDITION_STRATIFIED_COMPONENTS.csv.gz`、`CONDITION_IMAGE_EFFECTS.csv.gz` |
| 高分集中与同图关联 | `HIGH_SCORE_BAND_EFFECTS.csv`、`WITHIN_IMAGE_CEILING_ASSOCIATIONS.csv.gz`、`WITHIN_IMAGE_CEILING_ASSOCIATION_SUMMARY.csv`、`IMAGE_SCORE_CONCENTRATION.csv.gz` |
| 节点数不变时的独立几何变化 | `SAME_NODE_COUNT_COMPONENTS.csv.gz`、`SAME_NODE_COUNT_SUPPORT.csv` |
| 同源劳动及严格同支持Q/T | `RECORDED_LABOR_AND_JOINT_Q.csv`、`RECORDED_LABOR_IMAGE_EFFECTS.csv.gz`、`RECORDED_LABOR_SUPPORT.csv`、`CORE_RECORDED_LABOR_SAME_Q_SUPPORT.csv` |
| 记录劳动成员来源与排除理由 | `CURRENT_RECORD_LABOR_INDEX.csv.gz`、`ENDPOINT_RECORDED_LABOR.csv.gz`、`LABOR_EXCLUSION_REASONS.csv` |
| 原共同、新增共同、扩展支持 | `MANUAL_ORDER_SUPPORT_DECOMPOSITION.csv`、`MANUAL_SUPPORT_CHANGED_CONDITIONS.csv` |
| 输出状态 | `OUTPUT_STATE_TRANSITIONS.csv`、`UNIQUE_ENDPOINT_STATUS_BY_BUDGET.csv` |
| 特定原设计合同敏感性 | `CORE_LEGACY_DESIGN_LINK_SENSITIVITY.csv` |
| 补缺抽块层级及计权敏感性 | `GAP_BLOCK_SUPPORT.csv.gz`、`GAP_WEIGHTING_SENSITIVITY.csv`、`GAP_WEIGHTING_IMAGE_EFFECTS.csv.gz` |
| Q固定公式精确分解 | `Q_FORMULA_ATTRIBUTION_PAIRS.csv.gz`、`Q_FORMULA_ATTRIBUTION_IMAGES.csv.gz`、`Q_FORMULA_ATTRIBUTION_SUMMARY.csv` |
| 全部七张20/7 C23图均降Q图 | `C23_20_7_SEVEN_Q_DECLINE_IMAGES.csv` |
| 静态科学图PNG及SVG | `figures/A01_CONDITIONAL_MAGNITUDE_AND_GEOMETRY.*`、`figures/A02_QUALITY_COMPONENT_TRADEOFFS.*` |

`PHYSICAL_PAIRS_*`的一行是一对物理A/C，不是一次独立的人群实验。六方向汇总中反向是同一对的代数变换。`analysis_cohort`及`scope`必须保留筛选，不能把其它目标、批12腿、存量和补缺队列无差别拼接。字段及单位见 [METRIC_DICTIONARY_ZH.md](METRIC_DICTIONARY_ZH.md)。

## 输入与版本

main固定提交为 `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b`。本目录不依赖任何scratch临时索引、当前工作路径或私人凭证。所有路径由脚本自身位置找到仓库根；将交付目录按原相对路径解压到完整仓库即可。Windows仓库可为 `D:/Work/HOHONET`，Linux亦可。

`ANALYSIS_INPUT_MANIFEST.csv`列出直接输入的仓库相对路径、字节数与SHA256，包含登记表、旧指标提取、人工接续、批12端点、逐成员时间/条件索引、新补队及冻结几何测量函数。各模块的源数据和原生运行环境另见根目录说明。

旧TARGET原始指标为225个分片、52,544条方法事件。交付的`LEGACY_TARGET_METRICS_AUTOMATIC.csv.gz`是保留原列和原身份的完整TARGET提取，可以直接接续，不必重新获取约603MB原始混合方法分片。若需要回源，`METRIC_SOURCE_MANIFEST.json`固定每个分片的路径、Git提交及Git blob SHA1；运行提取脚本会验证，缺失时可从该提交的GitHub下载，绝不静默替换不匹配的现有文件。

`raw_target_metrics/`是逐分片提取缓存，与上述完整文件重复，可不放入精简下载包。下载包必须保留完整提取文件、清单、receipt和代码；不能只留下汇总表。

## 安装与运行

本轮使用Python 3.12、NumPy 2.3.5、pandas 2.2.3、SciPy 1.17.0、Shapely 2.2.0、Matplotlib 3.10.8。分析不调用fusion、不调整标签、不生成新人工顺序；新增团队的原生运行代码在`../supplement/`，容量/合法性脚本在`../audit/`。

在仓库根运行：

```bash
python -m pip install -r research/workers/current_dstruct_ac_final_20261104/analysis/requirements-analysis.txt
python research/workers/current_dstruct_ac_final_20261104/analysis/build_dataset.py
python research/workers/current_dstruct_ac_final_20261104/analysis/summarize_ac.py
python research/workers/current_dstruct_ac_final_20261104/analysis/explain_quality_formula.py
python research/workers/current_dstruct_ac_final_20261104/analysis/create_analysis_deliverables.py
python research/workers/current_dstruct_ac_final_20261104/analysis/plot_analysis.py --font /path/to/NotoSansCJKsc-Regular.otf
```

如系统已安装Noto Sans CJK SC、思源黑体、微软雅黑或SimHei，绘图可省略`--font`；也可设`HOHONET_CJK_FONT`为字体文件。只有作图需要字体，数值代码不依赖字体或图像生成服务。PNG是直接数值绘图，SVG保留文本便于编辑。

如完整TARGET提取文件不存在，先运行：

```bash
python research/workers/current_dstruct_ac_final_20261104/analysis/extract_legacy_metrics.py --download-missing --workers 8
```

若原始225个分片已在仓库内，省略`--download-missing`即可；`METRIC_SOURCE_MANIFEST.json`随交付固定。其它源文件可按`ANALYSIS_INPUT_MANIFEST.csv`从固定Git提交恢复，其中本轮新`registry/`与`supplement/`由同批交付提供。运行`build_dataset.py --without-supplement`只用于复现存量和批12来源，会生成一个不同的、未补缺的数据集；最终交付主结果不使用此参数。

`finalize_analysis_outputs.py`是幂等收尾脚本：清除T-only行上不应联用的Q字段、保留补缺块权重、统一完全相同支持的区间。最终`summarize_ac.py`已内置这些规则；无需在正常全流程后再跑一次。重跑会原子写入本分析目录，输入文件保持冻结。

## 预先固定的分析规则

`ANALYSIS_CONTRACT.json`记录口径。ΔQ是C−A；±1Q为小变化阈值，另附±0.5和±2。主结果在同图内汇总，再图片等权；建筑等权另列，区间按建筑聚类，不在队对层直接bootstrap。重采样2,000次，基础种子202611041302。补缺队列先D背景、再X/Z块、再图片；旧队列按物理对条件平均。反向均值/区间/正负数由同一正向估计精确变换。

同支持的自动/辅助显示行共用同一组区间；分项`delta_B8L2`就是主Q，直接绑定同条件主表的区间。T-only汇总不附另一个事件子集上的Q平均；只有`same_pairs_Q_and_labor`可解释联合Q/T。missing Q和missing T始终为缺失，不填0。

## 验收文件

| 验收范围 | receipt |
| --- | --- |
| 225分片回源、TARGET行提取 | `METRIC_EXTRACTION_CHECKS.json`、`METRIC_EXTRACTION_RECEIPT.csv` |
| 标签登记与旧/辅助/批12/新增端点、劳动身份接续 | `DATASET_CHECKS.json`、`ANALYSIS_INPUT_MANIFEST.csv` |
| 图楼计权、反向恒等式、未填补缺失 | `STATISTICAL_CHECKS.json` |
| 主表同支持区间及最终SHA | `MAIN_SAME_SUPPORT_INTERVAL_CHECKS.json` |
| 其它同值图集的相同区间 | `SAME_SUPPORT_INTERVAL_CHECKS.json` |
| 主Q与分项Q区间相同 | `Q_COMPONENT_INTERVAL_IDENTITY_CHECKS.json` |
| 主表不变及同支持Q/T清理 | `FINAL_OUTPUT_CONSISTENCY_CHECKS.json` |
| 五输入Q公式及分解残差 | `Q_FORMULA_ATTRIBUTION_CHECKS.json` |
| 中文报告辅助表、七图与人工支持变化 | `INTERPRETATION_OUTPUT_CHECKS.json` |
| 图文件及字体、视觉检查 | `FIGURES_RECEIPT.json` |
| 独立端点、公式、物理对计权及主统计复核 | `../audit/INDEPENDENT_*` |

独立验收绑定最终`SIX_DIRECTION_Q_BY_BUDGET.csv`的SHA256：`aaa59f2cbf5cd3356d9a4c760052ddffae4484a6693fcb91c6bb36793e78ccd3`。全流程可重新复现数值；CSV格式化或版本变化可能改变字节哈希，届时须重新记录receipt，不应宣称沿用旧哈希。
