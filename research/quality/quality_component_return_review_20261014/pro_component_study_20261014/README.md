# HOHONET分项得分组合研究 — 2026-10-14

**结论：采用分项解释界面有价值；不建议用本包的算术总分A或范围锚定总分RA替换WQ-LS08。分项调和平均是WQ-LS08的精确等价改写，不是新算法。**

本包是独立研究交付，不是仓库正式默认。完整论证见 `REPORT_ZH.md`。

## 实际完成范围

核对main：`134e7c775b9ea25a076851c0605571ba0ea0ac31`。
本轮从实际恢复的分项文本复算331条：197普通来源条件开发、125门洞条件、9严重例外；125门洞中117条件回归、8 Q01范围诊断。另92暂缓仍NA，1条截断隔离。**不是718条全量，不是3152条全量。** 320条可算记录未恢复manual/semi元数据，保留unknown；没有可靠的人员重排结论。

原始点未在本包逐份重建；原始3D IoU来自相同记录/参考的既存字段。合成几何另行显式计算。输入文件是Library提取文本，有自己的字节哈希；不能冒称与main归档逐字节核验完成。

## 复现

在Python环境安装 `requirements.txt`，然后在本目录执行：

```bash
python -B reproduce.py --output results_replay
python -m pytest -q tests
python plot_results.py --results results_replay --output figures_replay
```

`reproduce.py`拒绝覆盖非空输出目录。默认读取本包冻结的提取文本，所以准确重现的是本包331条比较，而不是下载完整仓库。

取得完整原交付的FINAL表和对象来源审核后，可使用：

```bash
python -B reproduce.py --tables /absolute/path/to/full/results \
  --source-audit /absolute/path/to/object_and_input_audit.json \
  --output full_native_replay
```

输入表名支持 `FINAL_ordinary.csv`、`FINAL_doorway.csv`、`FINAL_severe.csv`、`FINAL_history.csv`（或本包txt）。扩展输入必须保留原字段、对象/参考及哈希；不会自动获取图片、授予资格或猜测manual/semi。输出审核账本会显示实际覆盖。

`config.json`中的权重被执行；baseline中的常数是固定基线登记，与 `src/models.py` 对应，不支持只编辑baseline登记来更改正式基线。新的参数研究应独立命名，不能覆盖这份冻结结果。

## 文件

`results/per_case.csv`：全部424条用途/执行行，含331条完整分数、92条NA及1条截断隔离；继承原参考、来源、曝光、留出、资格限制和哈希。

`results/followup_review_manifest.csv`：31个绑定、21张图，29可算对象加2暂缓对照，保存参考与选择原因；`followup_review_bindings_without_scores.csv`去除数值但不把这些样例冒称盲验证。

`results/geometry_probes.csv`、`geometry_probe_inputs.json`：18个显式几何诊断。`height_probes.csv`：14个高度解析控制。`single_component_response.csv`：60个损失空间控制，均不算新增真人。

`stratum_summary.csv`、`cut_migration.csv`、`same_binding_pairs.csv`、`component_marginal_effects.csv`：分层数值、非标定切点迁移、参考绑定内配对、去分项的实际边际增分。`worker_support_and_available_means.csv`只报告可恢复的支持，样本不足时排名NA。

`results/TEST_RESULTS.txt`：28项测试通过。`results/CLEAN_REPLAY.json`：15个机器结果文件在新目录重跑后逐字节一致。它们验证执行，不证明人评效度或泛化。

`SOURCES_AND_LIMITATIONS.json`与`REFERENCES.md`：来源、访问限制、方法参考。`SHA256SUMS.txt`：交付文件完整性。
