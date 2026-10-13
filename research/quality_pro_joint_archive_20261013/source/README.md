# 多空间参考与联合质量校准：可复现交付

本包基于 `Sparkling-Flames/3D_Manhattan_label` 的 main **fdfc8a51ad668c83172ca4a9cf0105f417dac61c**，父提交 **2ad1fda97ae2b71d4fa3b92ebf3646741e69ff2d**。目录日期沿用研究批次命名；实际来源读取、计算和核验时间记录在各证据文件中。本包不要求等待其他线程，也不要求重新下载两个旧研究包或原图全集。

## 当前推荐

`J_main_hill_tail12_g1_l025`：

```text
Q = 100 I / [1 + Sb²/32 + 1.5 D²/(D²+37.5) + (D/12)⁴
             + Hm² + (Hc/0.25)²]
```

先在已确认合法的候选参考中路由，再评分。没有确认顶面的候选只输出底面质量，完整 Q、Hm、Hc、3D IoU 为 null；路由不授予正式资格。参数是当前可执行选择，不是已独立验证的人类等级量表。

先读 [中文研究报告](RESEARCH_REPORT_ZH.md)。报告明确列出获支持、被否定和仍不确定的假设；不是所有分数上涨都属于公式改进，也没有宣称局部路由已经比最大底面 IoU 准确。

## 运行

已验证环境：Python 3.12.14；精确依赖版本见 `requirements.txt`。

```bash
python -m pip install -r requirements.txt
python assess.py --record-id R00397
python assess.py --record-id R03197 --out assessed_R03197.json
python assess.py --record-id R03258 --candidate J_simple_power8_g1_l025
```

新几何只能使用本包已经准入的图像候选集：

```bash
python assess.py --geometry my_geometry.json --image-code uNb9QFRL6hY-67
```

输入为 `{"bottom3d": [[x,-1,z],...], "top3d": [[x,y,z],...]}`。环次序及上下配对须有来源，长度单位为相机高度；本入口不猜测配对。`top3d` 可缺省。原始配对层可另提供 `before_preprocessing_points` 与 `links_zero_based`；未提供则原始输入诊断为 unavailable，不把缺测写成零。

一条命令重新生成科学结果并逐值比较，`--out` 必须是包外新的空目录：

```bash
python reproduce.py --out /absolute/path/to/new_quality_replay
```

复现程序复制冻结输入，清除副本中的计算结果，运行路由、方向描述量、真实参考扰动、极端反例、采样核验、21,744 配置搜索、922/143/融合重算和复核页面生成。计算不需要网络。若 Node 可用，还会执行离线页面的 DOM/canvas 交互验收；没有 Node 时科学计算继续，UI 验证状态明确标记未执行。交付源文件保持不变。

## 文件入口

|内容|入口|
|---|---|
|完整中文报告|`RESEARCH_REPORT_ZH.md`|
|实际资料与缺口、字段定义|`DATA_INVENTORY_ZH.md`、`FIELD_CONTRACT.json`|
|主方案和最多两个备选|`calibration/recommended_parameters.json`、`calibration/score.py`|
|35 图、65 个准入候选|`routing/results/image_manifest.csv`、`reference_candidates.json`|
|429 份逐作答路由与完整理由|`routing/results/routes.csv`、`routes.json`|
|全部候选指标及 oracle 单列诊断|`routing/results/all_candidate_metrics.json`、`oracle_diagnostic_separate.json`|
|搜索范围、全部配置及筛选|`calibration/results/SEARCH_DESIGN.json`、`all_search_configs.json.gz`、`all_search_results.csv.gz`|
|922 份新旧分和逐项损失|`integration/results/fixed_reference_922.csv`、`calibration/results/selected_components_long.csv`|
|参考/公式四格归因|`integration/results/reference_formula_four_way.csv`、`historical_original_four_way.csv`|
|143 条条件人员及冻结融合影响|`integration/results/worker_conditions_new.json`、`fusion_220_ledger_and_scores.csv`|
|反例、采样和独立方向核验|`experiments/REPORT_ZH.md`、`experiments/results/`|
|三项盲审与数值诊断|`review/blind_review.html`、`review/diagnostic_review.html`|
|当前来源与原始审查证据|`sources/`、`provenance/`、各模块 `SOURCE_DEPENDENCIES.json`|
|实际验证结果|`verification/`、模块内验证 JSON|

其中 `baseline/` 是自给复现所需的冻结源代码、点坐标及证据子集；没有用报告摘要替代计算输入。整个原图全集不重复打包，三张复核原图已经包含。

## 查看复核材料

解压后直接打开 `review/blind_review.html`。原图、参考、同步旋转三维、共同尺度底面均在本地加载，判断可导出 JSON。请先用盲审页；`diagnostic_review.html` 会展示数值。所有复核只是区分后续方案的少量材料，本轮推荐和实验已经完成。

另提供两个可单文件打开的 `*_standalone.html`，内容与对应页面相同、只是嵌入原图。为避免同一原图重复占用空间，它们不进入 ZIP；运行 `python review/build_review.py` 可以从包内原图重新生成。**ZIP 内的标准页面、数据和图片已经完整。**

原生浏览器布局和实际下载点击未完成验收；已完成交付 JavaScript 的 DOM/canvas 执行、原图解码和静态联系图目视核验。详见 `review/UI_EXECUTION_VERIFICATION.json`。

## 压缩包核验

`PACKAGE_MANIFEST.json` 列出除清单自身外的全部 ZIP 载荷及 SHA256。可用下列命令复查，不需要原旧包：

```bash
python package_delivery.py verify /absolute/path/to/quality_multispace_joint_calibration_20261013.zip
```

本交付为单个可独立解压 ZIP，无需二进制拼接。核验结果包含 CRC、安全路径、精确成员集合、逐文件大小/SHA256 和 PNG 解码；完整重跑证据与最终包核验应结合查看。新包不要求与任何旧整包 SHA 相同。
