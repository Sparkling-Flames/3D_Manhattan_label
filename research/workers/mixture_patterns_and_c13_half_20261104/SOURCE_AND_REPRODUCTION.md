# 来源与复现

## 当前来源

正式仓库为 `Sparkling-Flames/3D_Manhattan_label`，本轮核实并固定的 GitHub 提交为 `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b`。本专题另外接续第 08–10 批已完成的当前类别画像、楼外标签和原图说明。当前输入的完整 URL、版本与 SHA-256 见 [SOURCE_INDEX.csv](SOURCE_INDEX.csv)；各分工仍保留实际读取的细分清单。

| 内容 | 主要原始来源 | 本轮使用方式 |
|---|---|---|
| 当前楼外类别与容量 | `current_class_interpretation_20261104/basis/WORKER_LABELS_ALL_LOBO.csv.gz`、`CLASS_CAPACITY_PER_POOL.csv.gz` | 使用实际目标建筑被留出的标签；不重新拟合 |
| 原有效研究池 | v2.1 正式融合输入与各池参考 | 保留原预处理、坐标、成员、参考与版本 |
| 当前难度与结构条件 | `image_difficulty_20261030/POOL_TARGET_CONDITIONS.csv` | 既有分层与交叉支持 |
| 房间用途 | `room_type_similarity_scoping_20261027/IMAGE_TYPE_INDEX.csv` | 已登记用途；几何 scene 不代替用途 |
| 联盟与固定配比 | 当前 DSTRUCT 联盟、四法配置分布、固定块背景路径 | 重新汇总已存在端点，不新增类似团队 |
| 自然进入序列 | v2.1 `natural_analysis_restored/inputs/` 的 206 池 | 52,736 条已有路径，保留原重复频率；不重新融合 |
| K4 小池政策 | `exact_small_pool_policies_OPPJOINT_K4/` 的优先组与全部子集端点 | 原政策不改，仅补接两个精确辅助端点并计算过程概率 |
| 批准人工端点 | `manual_order_impact_20261104/endpoints/` | 精确池、参考和成员绑定；自动与辅助并存 |
| 新 C1↔C3 | 本专题 `c13_half/inputs/`、`design/` | 冻结选样后运行正式 native engine；不借用其它团队人工顺序 |

本地第 07 批验收的三份联盟/AC 辅助副本，已与上述固定 GitHub URL 的实际文件比对：压缩字节、解压文本、列和所有数值完全相同，见 [语义与文件比对记录](audit/ASSISTED_SOURCE_LOGICAL_COMPARISON.json)。源码的递归导入依赖按固定提交恢复，未改正式融合或评分代码。

## 两个交付包

第 11 批包含 `mixtures/`、`curves/` 的全部研究产物，以及阅读说明；第 12 批包含新 `c13_half/`、整合报告、方法、源索引、研究台、代码与七个项目入口更新。保持仓库相对路径，依次解压至 `D:/Work/HOHONET`。需要已有 v2.1 仓库和前面批次；这两个包是增量，不重复打包整个历史仓库。

阅读可直接双击 `workbench/index.html` 或 `REPORT_ZH.html`，无需网络、Python 或重新运行融合。所有科研图同时保存 PNG 和 SVG，部分新 ABC 图另有 PDF；图中真实几何由端点坐标直接绘制，未使用生成式图像改写数据。

## 复现层次

**只重建展示：** 已有数值表即可运行下列命令。Python 需要 pandas；报告渲染需要 Node 与 `marked`。`marked` 可由项目 Node 环境提供，或通过 `CODEX_PRIMARY_RUNTIME_NODE_MODULES` 指定已安装模块位置。

```text
python research/workers/mixture_patterns_and_c13_half_20261104/build_conclusion_ledger.py
python research/workers/mixture_patterns_and_c13_half_20261104/build_workbench.py
node research/workers/mixture_patterns_and_c13_half_20261104/render_reports.mjs
python research/workers/mixture_patterns_and_c13_half_20261104/update_project_entries.py
```

**重新汇总已有计算：** 依次运行各专题 README 中的分析脚本。混合分析只读取保存的联盟、配置和背景；曲线只读取保存的自然路径与小池子集端点。206 个自然原输入约 406 MB，不在 ZIP 中重复；`curves/restore_natural_sources.py --download-missing` 使用固定版本来源补取缺少文件，并拒绝覆盖内容不同的本地文件。

**重放新增严格 ABC：** 见 [C13 README](c13_half/README.md)。设计、选样种子、完整所需池、实际人员与对象、参考、记录时间和请求均随包保留；运行直接复用正式 native engine，已保存逐池结果可恢复，读取现成结果无需重新计算。原模型/评分工具的固定源码属于已有仓库，导入清单见 `c13_half/audit/ENGINE_IMPORT_RECEIPT.json`。

本次实际依赖为 Python 3.12、NumPy、pandas、SciPy、Shapely 2.2.0、Matplotlib 与 Pillow。新增端点运行前已用旧正式简单/中等/困难成功端点及无连接端点做一致性核对，15 个数值字段最大差 1.42×10⁻¹⁴，状态与参考一致。不能只因依赖能 import 就声称复现一致；这里已经进行了数值验证。

绘图如需中文字体，可提供 `--font` 或 `HOHONET_CJK_FONT`；默认尝试 Windows 微软雅黑/黑体、Linux Noto 和 macOS PingFang。已生成图无需重新装字体。

## 统计与版本验收

新 ABC 的成员与块互斥、参考绑定、原始节点、共享 x、底面自交/面积、质量公式、三端/四端支持和计权已核对。可见核是额外几何诊断，单列敏感性，没有升格为新的正式有效性条件。原共同 Q 与新增可评支持分别保留。

曲线检查实际路径池与参考，固定完整路径的逐 n 均值与主汇总闭合；首次、持续与劳动使用各自明确分母。K4 原自动统计复现、动态规划前缀概率、原共同端点零变化和两个新支持均有独立记录。

网页检查覆盖离线 JavaScript 的数据装载与筛选条件、静态链接、图片解码和科研图目视检查。没有实际浏览器截图的检查不会标称浏览器验收。各分工详表与根 `DELIVERY_CHECKS.json` 保留检查范围。ZIP 另有包含文件清单；这些清单用于复现和安装，不代替科学证据。

## 引用格式

本轮数值来自项目自身的原始数据、冻结实验及新增计算，不引用未核实的二手结论。报告中每个主要结论直接链接对应表和专题。需要在论文材料清单中引用本轮产物时，可以使用：

- HOHONET 项目，2026。《不同类型混合后，有哪些可重复的规律？》HOHONET v2.1 仓库研究报告，2026-11-04，`mixture_patterns_and_c13_half_20261104/REPORT_ZH.md`。
- HOHONET 项目，2026。《当前类别混合与更早接近采用参考：既有曲线的深挖与实际消费者补接》。同仓库 `curves/REPORT_ZH.md`，来源版本与逐项数值见对应来源清单。
- 新 C1↔C3 的设计与结果同时引用 `c13_half/design/DESIGN.json`、`analysis/SUPPORT.csv`、`analysis/PAIRED_FOUR_SUMMARY.csv`；明确 6/3 或 8/4、方向和共同支持。

这些是仓库研究报告与数据附件，不伪称已经发表的期刊论文或独立外部复现。
