# 安装、下载目录与复现

## 分批安装

本轮接续第 08–12 批，按 **第 13 → 14 → 15 批**的顺序解压到已有仓库 `D:/Work/HOHONET`，保留 ZIP 中的 `research/`、`docs/` 等相对路径。分批包各自包含安装说明和文件清单。原自动实验、标签、参考及此前图册不被新的结果替换。

| 批次 | 文件内容 | 安装后的主要位置 |
|---|---|---|
| 13 | 标签与旧事件审计、逐图容量、事件和团队登记、有限补充的冻结输入及完整原生端点 | `audit/`、`registry/`、`supplement/`、`inputs/` |
| 14 | 全部当前合法 AC 底表、逐图/逐楼/分层结果、状态与合法记录劳动、统计代码 | `analysis/` |
| 15 | 原图案例和机制证据、科学图、完整中文报告、离线研究台、最终验收及研究入口更新 | `mechanisms/`、`workbench/` 及根目录文档 |

解压完成后，直接打开：

`research/workers/current_dstruct_ac_final_20261104/workbench/index.html`

完整报告为同目录上一级的 `REPORT_ZH.html`。HTML 页面和案例数据均随包提供，常规阅读不需要启动服务器或再次运行融合。较大的 CSV 使用 gzip 压缩，可由 pandas、R 或解压工具读取。

## 版本与运行环境

基础来源是本轮开始时最新 main `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b`，以及第 08–12 批已交付增量。详见 [版本优先关系](VERSION_PRIORITY.html)。本轮代码按脚本位置解析仓库根目录，不要求使用当前云端绝对路径。

数值脚本使用 Python 3.10+，依赖项目已有的 numpy、pandas、scipy、shapely；绘图额外使用 matplotlib、Pillow。生成 Markdown 对应 HTML 使用 Node.js 与 `marked`。只阅读已生成结果不需要安装这些依赖。科研图字体可用 `--font` 或 `HOHONET_CJK_FONT` 指定本机中文字体。

## 推荐的核验顺序

以下命令在仓库根目录执行。它们首先利用已交付结果，不重新抽样。

```bash
python research/workers/current_dstruct_ac_final_20261104/check_input_versions.py
python research/workers/current_dstruct_ac_final_20261104/audit/review_supplement_design.py
python research/workers/current_dstruct_ac_final_20261104/supplement/validate_results.py
```

第一条核验核心源文件版本；第二条不读取 Q/GT 结果，独立重建补充选择；第三条核验冻结请求、成员/参考、投票阈值、几何、Q/D10 公式及缺失状态。评分与汇总独立验收的其它脚本和结果位于 `audit/`，最终目录见 [验收记录](DELIVERY_CHECKS.json)。

## 重聚合已有结果

```bash
python research/workers/current_dstruct_ac_final_20261104/analysis/build_dataset.py
python research/workers/current_dstruct_ac_final_20261104/analysis/summarize_ac.py
python research/workers/current_dstruct_ac_final_20261104/analysis/explain_quality_formula.py
python research/workers/current_dstruct_ac_final_20261104/analysis/create_analysis_deliverables.py
```

上述步骤读取旧已保存指标、本轮端点和批准辅助接续结果，重新构建物理对及统计，不计算新融合。来源与条件具有不同抽样身份：旧存量按条件内不同物理对汇总到图片；本轮缺口补充先在固定 X/Z 块内平均 D，再平均块及图片；主报告同时给图片和建筑层面结果。

交付的 `LEGACY_TARGET_METRICS_AUTOMATIC.csv.gz` 保留 52,544 条旧 TARGET 事件的原指标，因而正常重聚合不必先重新下载原来分散的指标文件。若需要从固定 main 的原分片重新提取，可运行：

```bash
python research/workers/current_dstruct_ac_final_20261104/analysis/extract_legacy_metrics.py --download-missing
```

下载仅用于恢复固定版本的源数据，不用于查找新实验或更新参考。

## 原生补充与机制重放

```bash
python research/workers/current_dstruct_ac_final_20261104/supplement/run_native.py --jobs 3
python research/workers/current_dstruct_ac_final_20261104/mechanisms/code/replay_native_traces.py --jobs 4
```

补充程序只执行已经冻结的 1,408 支请求团队，并复用现存逐池检查点；它不会因结果不理想重新选人。机制程序对已经存在的团队重放诊断，必须与原保存端点的分数、状态和几何一致，不能把重放当作新增团队验证。

`supplement/design.py` 默认拒绝覆盖已有冻结设计。独立重建应在隔离副本中进行，保留原始交付及设计合同；不要在正式采用目录中删除现有结果后改变选择规则。

## 支持和缺失值的读取

- 六方向表的反向行由相同物理对代数翻号产生。对方向求和会重复计算证据。
- `registered_*` 表示真实登记容量/团队；`common_Q_*` 表示两端均有 Q。注册覆盖不保证共同可评。
- 自动、辅助原共同支持、辅助新增共同支持、辅助扩展支持分别读取。原无 Q 不填零。
- 完整团队同源劳动与 X/Z 同源增量劳动是不同支持域；后者可因 D 严格相同而相消，不能冒称全队总劳动已知。
- 原目标、其它准入目标、不同 n/m、历史背景设计和各来源队列不能无条件合并为一种受控效应。

本轮新文件全部保存在 `current_dstruct_ac_final_20261104/`；包内另列的已有项目入口仅添加新的采用说明和链接。没有推送 GitHub，也没有直接访问用户计算机的 D 盘；解压上述分批包即完成本地接入。
