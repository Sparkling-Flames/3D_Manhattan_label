# 人员可靠性与 Semi 纠错实算（数据 v1）

先读 [REPORT_ZH.md](REPORT_ZH.md)。核心人表为 [worker_semi_summary.csv](worker_semi_summary.csv)、[worker_reliability_summary.csv](worker_reliability_summary.csv) 和 [worker_scope_summary.csv](worker_scope_summary.csv)。全部库存为 27 人；主 Q 队列仍为原来的 24 人，没有恢复历史剔除者的投票资格。

## 输入与环境

仓库固定为 `Sparkling-Flames/3D_Manhattan_label`，提交 `c4dd8266c42a478c68b0dce8097c98e33e4b32b2`。必须读取 `analysis_results/research_input_20261017/manifest.json`，并经过当前 `tools.thesis_main.data_prep.consolidate_research_input.load_current_bundle` 验证。不要改回旧批次目录；旧来源文件名中的版本字符不改变本轮所有数据属于 v1。

Python 3.12 环境的实跑版本列于 [reliability_provenance_receipt.json](reliability_provenance_receipt.json)。依赖见 [requirements.txt](requirements.txt)。至少需要 Shapely 2；本次测试版本为 2.1.2。几何测量使用仓库冻结引擎和 B8L2/D10 原模型代码，未另造评分。

两个当前入口大文件必须是 Git LFS 的真实内容：

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `analysis_results/research_input_20261017/data.json` | 60,487,925 | `de0a3eb328470c52604555a36f678e9e64401c9672cdf3b39840c2a814e98c88` |
| `analysis_results/research_input_20261017/comments.json` | 108,396,832 | `9b32ff1cbd5a759ec04aca22070abe0cafdb0d0fb09a341005886bb0ef5f897d` |

冻结测量引擎位于 `research/quality/quality_joint_closeout_review_20261015/pro_closeout_delta.zip`；这是该提交中的普通 Git blob。本任务未取得先前脚本默认指向的 `measurement_engine.zip`，改用仓库当前评分函数明确采用的上述同一冻结引擎，并以 519 份现有完整结果逐条复现验证。完整 48 项来源的路径、用途、字节数与 SHA-256 见 [source_provenance_manifest.csv](source_provenance_manifest.csv)。

## 复跑

保留分析包的 `q/` 与 `reliability/` 同级结构。默认仓库在分析包上级的 `repo/`。也可以显式设置以下路径；任何脚本均不依赖本次临时工作区的绝对路径。

```bash
export PANORAMA_REPO=/absolute/path/to/3D_Manhattan_label
export PANORAMA_STUDY=/absolute/path/to/study
python -m pip install -r "$PANORAMA_STUDY/reliability/requirements.txt"

# 首次复跑时先生成独立 Q 画像及覆盖全库存建筑的折内画像。
python "$PANORAMA_STUDY/q/analyze_q.py" \
  --repo "$PANORAMA_REPO" --out "$PANORAMA_STUDY/q"

# 单个命令运行全部 11 个可靠性步骤。
python "$PANORAMA_STUDY/reliability/run_reliability.py" \
  --repo "$PANORAMA_REPO" --study "$PANORAMA_STUDY" \
  --out "$PANORAMA_STUDY/reliability"

# 记录来源 hash、测试依赖与完整机会/未知分母。
python "$PANORAMA_STUDY/reliability/write_evidence_manifest.py"
```

如用单独输出目录复跑，应同时设置 `PANORAMA_RELIABILITY_OUT`，使后续的来源记录命令指向同一目录。脚本读取仓库，不写仓库，不修改资格、不改 GT、不发布任何内容。

11 个步骤依次为：当前 loader；按固定 object_id/证据 hash 重建 85 条排除解释；全量人工审核台账；实际初始化溯源；兼容环序；原数组计量诊断；兼容环序计量；语义纠错证据；scope 原答卷/gold；Semi 楼外验证；scope 楼外验证。`run_evidence.json` 与以 `01_` 到 `11_` 开头的输出日志是本次可读运行证据。

本次已经在全新输出目录执行 11 步，全部成功，并将 8 个核心结果表逐列比较到 `1e-12` 数值精度。证据见 [reproduction_comparison_receipt.json](reproduction_comparison_receipt.json)。

## 关键文件

| 文件 | 粒度与用途 |
|---|---|
| `worker_semi_summary.csv` | 27 人；最终质量、兼容计量净改善、覆盖、缺失、实际错误机会/残留、Semi 调整效应及楼外范围。 |
| `worker_reliability_summary.csv` | 27 人；85 当前剔除、133 历史不接受、25 具体严重与 68 宽个人不可接受、逐审覆盖。 |
| `worker_scope_summary.csv` | 27 人；原协议误拒/误收与当前兼容 clear 误拒；机会、响应未知、无任务裁定状态。 |
| `correction_object_ledger.csv` | 574 份 Semi；实际错误 gold、已知未改残留、已改后未知、评论语义及与剔除的重叠。 |
| `reliability_object_ledger.csv` | 全部 3222；逐条评论去重、理由、场景、原始资格和人工审核二元结果的确定性状态。 |
| `scope_object_ledger.csv` | 全部 3222；原答卷选择、确切源任务绑定、原协议 gold、later hold、当前语义兼容性。 |
| `exclusion_reason_candidates.csv` | 85 条当前剔除的可读原因账；不能把无理由 invalid 当个人错误，也不能把它当正确。 |
| `review_reason_adjudications_v1.json` | 本轮独立解释的固定编码；用 object_id 和源评语 hash 绑定，不靠记录位置或分数阈值。 |
| `initialization_evidence_574.csv` | 实际 import、runtime preview、raw final 三方溯源；427 改动、147 未改。 |
| `semi_scores_b8l2_d10.csv` | 574 尝试评分；保留 55 个最终评分失败、19 个初始评分失败及原因。 |
| `semi_payload_order_diagnostic.csv` | 原数组初始化与后处理 final 的故意不兼容诊断，用来复现 11 个虚假改善，不能给人记功。 |
| `initialization_ring_provenance.csv` | 43 个初始化的环序来源、原坐标身份、是否变更/冲突/未确认。 |
| `semi_lobo_performance.csv` | 409 普通开发样本与 28 原留出分别评价；B8L2 主线、D10 和特殊条件敏感性。 |
| `semi_final_gain_effect_equivalence.csv` | 同图/条件/参考/初始化后，final 与 gain 人员效应恒等的实际验证。 |
| `scope_lobo_performance.csv` | 小规模 scope 验证；不满足既有支持规则的端点保留不支持状态。 |
| `coverage_and_unknown_states.csv` | 机会分母、可判/可测数量、未知/不可用状态及适用边界。 |

`validated_annotations.json`、`validated_images.json` 与 `semi_*measurement_records.json` 是可重建缓存。无需重复交付 108 MB 的原评论，也不需要将仓库或原图复制到分析包。人员或 task 评分均只能使用表中适用的分母；不能因为某对象在数值评分中不可用，就删掉其审核或实际纠错机会。
