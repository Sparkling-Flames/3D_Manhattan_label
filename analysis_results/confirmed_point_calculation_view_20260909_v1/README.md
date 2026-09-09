# 用户确认孤点的计算视图

本包只应用用户提供的四条历史确认：三个精确响应删除指定孤点，一个歧义响应排除。全部 2501 个 canonical 响应仍保留索引，2513 个版本没有增加独立样本。生成时已逐条核对 18 份本地 `export_label/` 的坐标与点序。原始文件和旧结果未修改。

| canonical ID | 原始身份 | 原始点数 | 删除索引（从0开始） | 有效点数 |
| --- | --- | ---: | ---: | ---: |
| 63001f819a4a6b408ae2 | C1\|0\|67\|3239\|32\|6372 | 9 | 4 | 8 |
| 9e5409147dcedaf906b7 | C1\|0\|71\|3322\|2\|6140 | 17 | 10 | 16 |
| ba5291230a2bbae1658b | C1\|0\|72\|3398\|13\|6247 | 9 | 6 | 8 |
| 837d51d499c08b0e0765 | C1\|0\|71\|3354\|2\|6147 | 15 | 未确定 | 空值，排除 |

身份格式为 stage、block、project、runtime task、worker、annotation。第三条属于 Semi，不能进入无辅助 Manual。第四条旧算法找到四个候选，不能任取一个。零基索引的证据是旧 `c1_geometry_repair_audit.csv` 与 `geometry_consensus/representation.py` 中 `range(len(raw_points))` 的删除实现；四条均已复现其候选数量。

## 文件与字段合同

- `calculation_view.jsonl.gz`：2501 行；`canonical_annotation_id` 唯一键。身份、context、building、stage、block、worker、condition、assistance 与数据底座一致；版本及 export 路径可追溯。坐标尺寸为 1024×512。
- `raw_points_1024x512` / `raw_point_count`：所选原始版本点序与数量，不配对、不排序。
- `effective_points_1024x512` / `effective_point_count`：仅三个已确认响应删除一点后保留剩余原序。歧义排除记录为 JSON null；其他记录为原始副本。
- `processing_status`：`confirmed_point_removed` 3条、`confirmed_ambiguous_excluded` 1条、`unconfirmed_odd_unchanged` 28条、`unchanged` 2469条。状态不表示几何正确性。
- `dropped_point_index_zero_based`：删除点的原始零基索引，无删除为 null。不是界面点标签编号。
- `calculation_included` / `exclusion_reason`：仅针对无序球面点集计算的可用性；2465条可计算，30条空点、5条坐标异常、1条确认歧义排除。**不证明墙面布局有效或语义正确**。未确认奇数不会自动删除，也未按奇偶性整体排除。
- `unassisted_manual_included`：上述可用且 assistance_exposure=none；保留用户纳入的历史 oos 无辅助响应，条件字段仍原样记录。不是旧资格或质量门槛。
- `distance_recompute_required`：3条删除响应为 true。任何涉及它们的距离必须由有效点集重新计算，不能连接原始点距离后沿用。
- `confirmation_source` / `legacy_repair_audit_source`：用户四条确认及旧审计来源，仅四条有值。
- `confirmed_processing_audit.csv`：四条处理审计，另含旧算法候选数与被删除坐标。保留版本与条件，不扩散到同图其他人员或其他阶段。
- `verification.json`：数量、源核验和排除原因；不包含稳定性分析结果。

## 复现与接入

从仓库根目录运行（复用现有环境及 numpy/scipy/pandas，不安装新依赖）：

```powershell
.venv/Scripts/python.exe -m tools.thesis_main.data_prep.prepare_confirmed_point_calculation_view_20260909
.venv/Scripts/python.exe -m pytest tests/test_prepare_confirmed_point_calculation_view_20260909.py -q
```

读取已生成文件不需要外部目录或上述计算依赖：

```python
import gzip, json
from pathlib import Path
package = Path('analysis_results/confirmed_point_calculation_view_20260909_v1')
with gzip.open(package / 'calculation_view.jsonl.gz', 'rt', encoding='utf-8') as f:
    rows = [json.loads(line) for line in f]
manual = [r for r in rows if r['unassisted_manual_included']]
```

后续硬隔离应使用 `effective_point_count`，距离应读取 `effective_points_1024x512`。全历史、各前缀、历史加验证及验证分配应采用一致规则；仅生成本包不会自动修改旧消费者。本轮未重跑距离、分簇、稳定性或场景迁移。三个已确认删除并非授权全局启用自动孤点修复；旧 helper 在本入口仅用于四个精确响应的核查，未用于其他响应。

验证：先运行缺失实现的测试确认失败，再实现；两项测试通过，覆盖精确身份拒绝、原始点序与指定删除、未确认奇数不改、歧义排除、Semi不进入无辅助Manual，以及全部本地原始响应核验。
