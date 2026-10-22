# 人员标注质量与可靠性：数据 v1 独立研究交付

研究日期：2026-10-17。固定仓库：[Sparkling-Flames/3D_Manhattan_label](https://github.com/Sparkling-Flames/3D_Manhattan_label)，提交 `c4dd8266c42a478c68b0dce8097c98e33e4b32b2`。单份布局继续采用 B8L2 主线、D10 敏感性。全部现有数据、补充分析与新增融合重放仍为 **数据 v1**。

## 先读哪些文件

本说明位于 `study/` 中；下列路径均相对该目录。压缩包根目录也放了一份本说明，便于查找。

| 入口 | 内容 |
| --- | --- |
| `report/personnel_quality_v1_report_zh.pdf` | 17 页完整中文报告：框架、全 27 人表、分类变化、楼外验证和真实共识过程。 |
| `integration/personnel_profiles_v1.csv` | 27 行、47 列的前台人员表，适合先筛选具体人员。 |
| `integration/FIELD_GUIDE_ZH.md` | 上述每列的中文定义、分母、零/空白及来源；也解释完整表和事件并集。 |
| `integration/personnel_profiles_full.csv` | 27 行、226 列，保留更多覆盖、置信区间、缺失与原字段。 |
| `integration/classification_candidates.csv` | 原 Q/T 类、边界敏感性与本轮有依据的补充标记。 |
| `integration/event_evidence_union.csv` | 3222 对象，E/C/scope 标签与去重并集；不是统一风险概率或扣分表。 |
| `q/REPORT_ZH.md` | Q/T 独立复现、任务图连通性、绝对质量、楼外表现与 D10 比较。 |
| `reliability/REPORT_ZH.md` | 实际初始化、语义纠错、scope、审核/剔除及逐人覆盖。 |
| `fusion/REPORT.md` | 固定人数构成、固定构成换人、真实排列逐个加入的几何与质量过程。 |
| `provenance/SOURCE_MANIFEST.json` | 仓库/附件优先级、真实数据内容和来源 SHA-256。 |

CSV 使用 UTF-8；各主要结果表可由 Excel 或 pandas 读取。空白数值表示未知、不可用或不支持，须结合相邻覆盖字段判断；有定义的计数 0 是真实零。不要把没有机会的人员与观察到零次事件的人员混为一类。

## 采用结论与适用边界

采用连续的任务调整 Q，并同时展示绝对产物质量与支持范围。Q 零点二分和 Q×T 四格用于描述、构成比较；T 保持独立效率轴。本轮不将绝对质量、相对 Q、Semi 最终质量、净改善、分数缺口和审核事件加成一个总分。

明确错误处理、scope 和具体个人剔除形成证据标记，必须携带机会、审核覆盖及未知。6 个专家确认实际初始缺陷任务共有 156 次机会，25 次明确未改残留，131 次改后具体结局未知；主 24 人对应 144/20/124。当前 85 个审核剔除中，25 个有具体个人严重错误机制，68 个有较宽个人不接受归因，前者包含于后者。全池当前兼容 scope 误拒为 48 次，与具体错误重叠 3 个对象；严格并集为 95 个不同对象，不能按 25+25+48 扣三次分，也不能把 95/3222 当作总体错误率。

574 份实际部署初始化已恢复，但 413 份没有独立确认的原生环序来源。初始分与净改善属于兼容环序计量诊断；已知坐标缺陷未改的语义残留证据独立保留。5 份研究者补删点不记为个人净改善。未改、改过、最终高分和正净改善均不自动对应一次正确纠错。

保留了不利结果：Semi 专项效应开发楼外预测较好，但原留出更差；定向审核风险的开发收益不稳定，原留出更差；高 Q 构成有平均质量优势但并非每栋建筑都占优，同类具体成员也不可视为可互换。全部验证的原留出、开发 LOBO、审核子样本和团队面板分别报告。

## 已经实际完成的运行证据

| 工作 | 实际证据与结果 |
| --- | --- |
| Q/T 独立重算 | `q/RUN_RECEIPT.json`、`q/run.log`；2068 个已发布折效应最大差约 7.1e-14，5927 个预测与 2400 个两半标签复现。 |
| 当前输入与可靠性 | `reliability/run_evidence.json`；11/11 步完成；全新输出目录复跑 54.63 秒，8 个核心 CSV 全列复现至 1e-12。 |
| 可靠性复跑比较 | `reliability/reproduction_comparison_receipt.json`；正式 loader、574 初始化、3222 scope/审核对象均保留。 |
| 来源与冻结测量 | `reliability/source_provenance_manifest.csv` 核 48 项；519 份 final B8L2/D10 最大复现误差约 1.14e-13。 |
| 定向审核风险 | `integration/REVIEWED_RISK_RECEIPT.json`、`reviewed_risk_run.log`；6372 个楼外预测，训练不含目标楼和原留出，未知画像回退楼外基率。 |
| 已有团队与前缀 | `fusion/RUN_RECEIPT.json`；4032 个主图真实前缀；独立重融 14 个既有前缀并核结构与浮点容差。 |
| 新固定构成重放 | `fusion/stage2/RUN_RECEIPT.json`；336 个预先写盘的真实顺序、2688 个前缀、2167 次新子集融合，约 106 秒。 |
| 独立跨模块审查 | `q/INTEGRATION_AUDIT_RECEIPT.json`、`q/STAGE2_SCOPE_AUDIT_RECEIPT.json`；核对折外身份/时间、风险、全部新排列和 200 项分层聚合。 |
| 逐人整合与去重 | `integration/INTEGRATION_RECEIPT.json`；27 人、3222 个对象、严格/较宽并集分别 95/138，主 24 人 81/124。 |
| PDF 排版 | `report/PDF_RENDER_RECEIPT.json`、`report/PDF_QA_RECEIPT.json`；17 页、11 表、4 图。独立 PNG/SVG 科学图位于 q 与 fusion。 |

这些日志记录原始实跑环境和时间。有些绝对路径是当时的运行证据，不是代码依赖。登记文件说明哪些方案沿用、哪些是看过已有数据后固定的开发性补充。首次融合核对的严格浮点字符串比较失败日志也保留，随后明确改为数值容差并保持离散结构严格一致，没有借此换人、调类或更改评分。

## 复现所需环境和仓库

实际环境为 Python 3.12.14。统一依赖版本见 `requirements.txt`。建议在新的虚拟环境安装，避免改变既有项目依赖。完整原图和数百 MB 原始导出没有重复打包；仓库提交是它们的可追溯来源。压缩包包含本轮新代码、结果、固定解释编码、图、回执和必要字体。

以下是可复现命令，不会提交或推送仓库。替换三个任务专用路径为本机路径。先复制本交付的 `study` 文件夹到新的运行目录，保留原交付作为对照；后续命令会在新的副本中覆盖对应结果。

```bash
# 如已有固定提交的仓库，可直接使用，免去重复下载。
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/Sparkling-Flames/3D_Manhattan_label.git /absolute/path/to/3D_Manhattan_label
git -C /absolute/path/to/3D_Manhattan_label checkout c4dd8266c42a478c68b0dce8097c98e33e4b32b2
git -C /absolute/path/to/3D_Manhattan_label lfs pull --include='analysis_results/research_input_20261017/data.json,analysis_results/research_input_20261017/comments.json'

export PANORAMA_REPO=/absolute/path/to/3D_Manhattan_label
export PANORAMA_STUDY=/absolute/path/to/fresh-run/study
export PANORAMA_RELIABILITY_OUT="$PANORAMA_STUDY/reliability"

python3.12 -m venv /absolute/path/to/personnel-venv
export PERSONNEL_PYTHON=/absolute/path/to/personnel-venv/bin/python
"$PERSONNEL_PYTHON" -m pip install -r "$PANORAMA_STUDY/requirements.txt"
```

`data.json` 必须是 60,487,925 字节，`comments.json` 必须是 108,396,832 字节，不应停留在 LFS 指针。冻结引擎 `research/quality/quality_joint_closeout_review_20261015/pro_closeout_delta.zip` 为 43,333,390 字节普通 Git blob。未取得另一个旧默认路径下的 `measurement_engine.zip`，本轮采用当前仓库评分函数实际指向的同一冻结引擎，并用现有数值复现核验。没有为缺失包重造评分，也没有要求新数据。

## 顺序执行

### 1. Q/T：独立拟合与报告

```bash
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/q/analyze_q.py" --repo "$PANORAMA_REPO" --out "$PANORAMA_STUDY/q"
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/q/plot_q.py" --input "$PANORAMA_STUDY/q" --out "$PANORAMA_STUDY/q"
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/q/report_q.py" --directory "$PANORAMA_STUDY/q"
```

Q 分数输入为冻结发布资产，但双向固定效应、支持、折内训练、相对预测及两半标签用独立约束最小二乘实现，未导入原拟合函数。绝对均分和训练 Q 的样本并不相同。

### 2. 实际初始化、审核、scope 与 Semi

```bash
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/reliability/run_reliability.py" --repo "$PANORAMA_REPO" --study "$PANORAMA_STUDY" --out "$PANORAMA_STUDY/reliability"
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/reliability/write_evidence_manifest.py"
```

此入口执行 11 步。`review_reason_adjudications_v1.json` 是本轮逐条读原因后的固定文本解释，绑定 object_id 和源评语 hash；保留原文件，不根据输出改写理由。这里会重新生成未打包的 loader 与逐测量缓存。

### 3. 共识重放与组合比较

```bash
export WORKER_PROFILE_REPO="$PANORAMA_REPO"
export WORKER_PROFILE_OUTPUT="$PANORAMA_STUDY/fusion"
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/fusion/analyze_fusion_profiles.py"
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/fusion/replay_registered_compositions.py"
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/fusion/prepare_readable_outputs.py"
```

保留 `REGISTRATION.json`、`STAGE2_REGISTRATION.json` 与脚本同目录。第二步在融合前写出排列文件并验证完成后 hash 未变。固定 seed=20261017、H=8、四策略、每图每策略 12 次，不根据结果换分类或重挑顺序。

### 4. 定向审核诊断、人员整合与综合报告

```bash
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/integration/analyze_reviewed_risk.py" --study "$PANORAMA_STUDY" --out "$PANORAMA_STUDY/integration"
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/integration/integrate_profiles.py" --study "$PANORAMA_STUDY" --out "$PANORAMA_STUDY/integration"
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/report/build_report_content.py" --study "$PANORAMA_STUDY" --out "$PANORAMA_STUDY/report"
"$PERSONNEL_PYTHON" "$PANORAMA_STUDY/report/render_report.py" --source "$PANORAMA_STUDY/report/REPORT_ZH.md" --out "$PANORAMA_STUDY/report/personnel_quality_v1_report_zh.pdf"
```

报告中的逐人表和构成表直接读取 CSV；叙述数值与本次冻结结果对应。该脚本是本次固定研究报告生成器，未来换数据、模型或参数时必须重新审查叙述，不应当作自动产生新结论的通用系统。报告使用附带的 Noto Sans SC 静态字体，许可证位于 `report/assets/NotoSansSC-OFL.txt`。

已有两个跨模块只读审查脚本位于 `q/audit_integration.py` 与 `q/audit_stage2_scope.py`，使用 `--help` 查看 `--study/--repo/--out` 参数。前者需要第二步生成的 `validated_annotations.json`；不应因为它没有重复打包就把已完成审查误认为无法复现。

## 打包省略项与尚未验证材料

省略了可重建的 `reliability/validated_*.json`、`*measurement_records.json`、Python 缓存、`fusion/inputs/` 的仓库重复副本、PDF 逐页 QA PNG 与字体可变源文件。保留完整研究结果、实际初始化坐标、原评语编码、所有新重放子集几何、真实顺序、可读日志、静态字体与矢量图。

尚未验证的事实包括：模型 checkpoint 与屏幕实际渲染/观看；131 次已改明确错误的缺陷级结局；其余 418 份初始化的错误/正确 gold；大量后续任务的独立 scope 裁定；4 条历史个人排除的具体机制和 1 个尚未解出的评语来源。定向审核不支持总体严重错误概率；7 图/6 楼有限人员池不支持永久人群、全策略完整团队成本或同房间自然重复性推断。上述缺口不阻止本轮已完成的描述、复现与诊断，也没有以未来补标作为交付条件。

压缩包中的 `PACKAGE_MANIFEST.json` 给出文件数量、相对路径、字节与 SHA-256，`PACKAGE_VERIFICATION.json` 给出交付时的完整性检查。源仓库工作树保持不变。
