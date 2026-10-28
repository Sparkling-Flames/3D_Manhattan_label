# v2.1 DSTRUCT／RFUSE 既存团队端点重评分

对 `pools/DEPENDENCIES.json` 中 reuse_geometry_rescore 的45池，读取当前分类实验四组原有几何和标量；实际四组涵盖30池。输入路径相对 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/`：

| 来源 | 原生标量 | 已存几何 | 受影响行 |
|---|---|---|---:|
| screen | `02B/results/screen/NATIVE_ENDPOINT_SCALARS.csv.gz` | `02B/results/screen/NATIVE_ENDPOINT_GEOMETRY.json.gz` | 11346 |
| confirm | `04B/results/batch02/ENDPOINT_SCALARS.csv.gz` | `04C/results/batch02/ENDPOINT_GEOMETRY.json.gz` | 28204 |
| size | `05/results/size_paths/NATIVE_ENDPOINT_SCALARS.csv.gz` | `05/results/size_paths/NATIVE_ENDPOINT_GEOMETRY.json.gz` | 1260 |
| tail | `05/results/large_team_ac_tail/NATIVE_ENDPOINT_SCALARS.csv.gz` | `05/results/large_team_ac_tail/NATIVE_ENDPOINT_GEOMETRY.json.gz` | 548 |

各源内标量和几何逐 team_key 齐全；跨源重复身份、成员、对象、状态和几何一致，去重后41142队。保留精确团队成员、object ID、旧参考/状态、源路径及旧标量；通过 pool_id 在 v2.1 输入快照中绑定对应新参考，不改变成员或原始几何。

六组主事件表（02A screen、04A1 confirm、04A2 reverse screen/confirm、05 size/tail）按受影响pool扫描，引用的40854个唯一团队均被这四组几何覆盖；`MISSING_EVENT_TEAMS.jsonl.gz`为空。该结论限于以上六个事件表，不表示仓库所有历史事件已覆盖。

结果见 `shards/*.jsonl.gz`，完整评分40247队、少于四节点264队、原连接失败631队。完整评分输出B8L2、D10、WQ、A10、working子项及 omission/extension。参考节点／边召回和墙线／角点诊断重算；事件使用的9°匹配顶界、底界、水平偏差和配对比例也用原事件算法重算，位于 `reference_dependent_diagnostics`。无候选点631队标记 not_applicable，不填0。`COVERAGE.json` 与 `CHECKS.json` 含精确来源和状态。

可复现适配脚本为 `tools/thesis_main/analysis/rescore_v21_discrimination_20261028.py`，依序运行 `--part inventory`、`--part score --jobs 4`、`--part boundary_diagnostics`；评分拒绝覆盖既有分片。四个来源的旧参考样例均复现原B8L2／D10和节点召回。参考与历史身份独立保留；事件分母、比较结果和类别标签尚待主线程连接与独立验收，未重融或重选队。
