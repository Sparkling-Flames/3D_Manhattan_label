# v2质量评分与34份绑定核验

> 2026-10-19后续人工审核更新：右侧BEV点序及连接核验正确。用户采用1粉、2粉、3粉、5蓝、6粉；其余两份按既有底面IoU优先、边界距离次序回退，结果4蓝、7粉。7份均已绑定，其中5份人工指定、2份仅为自动fallback暂定；8份旧不可用仍不绑定。当前完整诊断9363份、正式质量7302份（196图、60人），普通Manual5719份。原坐标、点序和N1状态不变。

2026-10-19，输入为`research/data/releases/v2/analysis_input/manifest.json`，旧作答来自10/18已处理修订，未退回原导出。B8L2主指标、D10方向尺度敏感性均使用既有冻结引擎；N1未接入。

## 实际结果

10439份库存，9363份完整诊断计算，7302份正式质量作答、196图、60人；正式质量含旧作答1948、新作答5354。v1原1911份有效分数与本轮一致（误差<1e-9）；新增37份旧作答因有效人员池扩展通过人数门，详见`old_membership_expansion.json`。这不是解除GT/OOS或人工限制。

正式质量分层：普通Manual 5719、普通Semi 901、门洞Manual 571、其它条件Manual 66、其它条件Semi 45。完整诊断分数与正式质量分数分列；不能把9363当作人员质量样本量。12张图的既有暂停全部保留，用户强调的11图仍不进入主分析。

## 34份的处理

- 19份补齐唯一准入参考身份：B6ByNegPMKs-43（8）、jh4fc5c5qoQ-14（2）、q9vSo1VnCiC-24（6）、uNb9QFRL6hY-36（3）。原质量限制继续保留，仅允许诊断，不由参考唯一性恢复资格。
- 8份旧不可用/排除：UwV83HsGsw3-10、rPc6DW4iMge-06、rPc6DW4iMge-22各W019/W026；uNb9QFRL6hY-59 W037；uNb9QFRL6hY-68 W034。7份无可用点对，1份底面点不可用，不追加人工绑定任务。
- 7份新作答已审核：uNb9QFRL6hY-18 W131（104709）；-41 W121（104889）/W132（104895）；-59 W104（105195）；-66 W117（105246）/W131（105251）；wc2JMjhGNzB-26 W124（105708）。它们投影后的底面不包含相机，已有多空间路由返回`camera_not_inside_floor`，随后用户明确指定1粉、2粉、3粉、5蓝、6粉，其余授权fallback为4蓝、7粉。未按质量分数选参考，未复制他人的绑定。

入库阶段的`analysis_input/reference_bindings.json.gz`保留原34份缺口证据。当前评分消费者读取本包`reference_bindings.json/csv`，为19份身份补齐及7份审核采用后的状态；仅8份旧不可用保持未绑定。7份中4份仅底面、2份完整但仅诊断、1份新增正式质量；绑定不解除原资格限制。叠图位于[人员v2页](../../statistics/research_explorer_v1_r2_20261017/personnel_v2.html)。

## 字段与复现

- `quality_inventory.json/csv`：全10439份，`quality_usable`为正式用途；`B8L2/D10`仅正式有效者有值；`diagnostic_B8L2/D10`为能计算者的诊断值；缺失不补零。
- `quality_records.csv`：仅7302份正式有效记录；`reference_id/reference_version`是实际评价参考，`quality_use`保留普通、门洞、其它条件。
- `binding_audit.json/csv`：34份原缺口、处理和保留限制；`reference_bindings`保留原路由证据。
- `CROSS_MODULE_INPUTS.json`：当前评分消费者入口，包含库存/正式分母、版本及文件映射。
- `measurements.jsonl`：本地计算缓存，逐条存完整任务几何、参考几何和结果；只有任务完全相同才复用，不以ID单独复用。
- `source_active_time_seconds`：源作答耗时，非保证目标匹配时间；新批为用户处理字段，旧批沿用审计源时间。`semi_reported/worker_scope_response`为输入证据，不参与Q计算。

仓库根运行：
```
python -m tools.thesis_main.analysis.quality_workers_v2_20261019
python -m tools.thesis_main.analysis.personnel_v2_20261019
python -m pytest tests/test_quality_workers_v2_20261019.py tests/test_current_annotation_context_20261017.py tests/test_admit_workers_v2_20261019.py -q
```

本包原始逐人中间文件及计算缓存留本地。匿名逐份几何、分项、参考和证据已由[证据包](../../statistics/v2_evidence_audit_20261019/README.md)汇总，供研究台与Pro使用；匿名研究输入和原始账户导出不是同一资料。

审核字段补充：`USER_REFERENCE_REVIEW.json`留本地，保存显示编号、人员/作答ID、人工颜色选择、审核时坐标和本次fallback授权；评分绑定新增`user_reference_review`，审计新增`adopted_review`。自动回退保留两个候选底面IoU及边界距离，不使用B8L2/高度选参考。仅这7份采用本次审核，无全库路由规则修改；没有以人工归类解除缺顶界或其它历史限制。
