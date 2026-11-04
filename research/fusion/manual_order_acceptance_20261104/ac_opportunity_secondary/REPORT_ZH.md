# AC 两方法幅度比较与漏斗：完整注册范围的机会残留审计

## 核心结论

**已确认的 57 队顺序没有漏接；完整注册条件仍不能概括为所有人工处理机会均已覆盖。** 方法比较的 55/55 和 53/53 个共同注册池都有可评均值，但内部仍分别有 15/1042、8/969 个注册事件无 Q。按池有数值不能推导为该池内所有事件、所有方向或所有失败端点都得到同等人工处理。

本次仅核对 `ac/Q_REVERSALS.csv` 中 2 行 `method_comparison` 和 3 行 `funnel`；其中 OPP 漏斗具名方向与 ALL_CANONICAL 是同一个 14 事件集合的别名。没有扩至 AC 全库、选择新团队、增加人工顺序、融合、评分或分类选型。`audit_completed=true` 表示这五行条件的登记范围及残余均已核对，不表示剩余失败端点已经获得新人工顺序。

## 完整分母和残余

| 条件 | n/m | 完整注册池 | 原→辅助可评池 | 完整注册事件 | 原→辅助可评事件 | 残余事件 | 残余独立端点：无连接 / 少于4点 / 无效底面 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RAW3−OPP | 28/7 | 55 | 54→55 | 1042 | 1018→1027 | 15 | 3 / 10 / 3 |
| RAW3−TARGET_K2 | 28/7 | 53 | 52→53 | 969 | 952→961 | 8 | 2 / 3 / 3 |
| OPPSTRUCT_K3 1/3->3/3 | 28/1 | 2 | 1→2 | 14 | 7→13 | 1 | 0 / 1 / 0 |
| OPPSTRUCT_K3 ALL_CANONICAL_DIRECTIONS | 28/1 | 2 | 1→2 | 14 | 7→13 | 1 | 0 / 1 / 0 |
| V21_DSTRUCT_RAW3_K3 1/3->2/3 | 4/4 | 2 | 1→2 | 16 | 7→13 | 3 | 3 / 0 / 0 |

两个方法比较中，事件数是左右方法各自注册事件之和，不能解释为同成员成对实验。它们按每方向内可评事件的绝对 ΔQ 均值，再对该方法已有方向等权，最后在两方法共同注册池比较。完整注册事件分母分别 1042、969，与池层 55、53 分母不同。所有计算继续保留无 Q 的缺失状态，未把无 Q 当成 0 分或 0 效应。

## 方法幅度比较的边界

两个比较合并后共有 **17 个剩余事件、18 个缺 Q 端点**；这不是 15+8 个独立新案例。18 个端点都在确认 57 队之外，其中 4 个 `no_connection`、11 个少于 4 点、3 个 `invalid_floor`。这 17 个方法事件的对手也都不在 57 队内。

4 个无连接端点为 S9h-04 的两队（各 6 点）、VFua-04 的一队（6 点）、x8-08 的一队（4 点）。节点数足够不等于已证明能靠排序修复；目前只确认它们没有已提交人工顺序。3 个无效底面端点是另一种几何失败，不将其自动纳入排序修复。少于 4 点的端点在固定节点条件下不能靠重排补足。

当前辅助可评支持上的 RAW3−OPP = −0.103143、RAW3−TARGET_K2 = −1.156838 仍是实际计算结果；原共同可评事件的保持性由 AC 主验收提供。若改问“完整注册事件都在同等机会下处理后，两个方法的效应方向如何”，现有顺序不足以给出该结论，标记为 **尚不能判断**。这是支持与处理机会的条件限制，不是分类优劣证据，也不是漏接已确认结果。

## 漏斗：结构不合格与未覆盖机会分别记录

OPP、primary、28/1 的 1/3→3/3 与 ALL_CANONICAL 都是 14 个注册事件、13 个现可评事件。残余 C 端只有 3 个节点；其 A 端在 57 队内并已接入。这里不存在一个尚未处理、节点足够的无连接对手。该条件的 `all_registered_opportunities_covered=true` 仅依照下述固定节点排序机会合同；`all_registered_events_Q_evaluable=false` 仍明确保留，不能称 14 个事件全部可评。

RAW3、other_admitted、4/4、1/3→2/3 有 16 个注册事件，现可评 13 个。其余 3 个 C 端均在 57 队之外，状态 `no_connection`，节点数 11、8、8。wc2-26 的两个 C 端所对应的 A 端属于已确认 57 队并已接入；rPc6-22 的第三个 C 端及其 A 端都不在队列中。因此，这一完整比较范围确实存在不对称的处理机会。三个端点的冻结原记录与图形核对已由 `ac_peer/RAW3_RESIDUAL_FROZEN_ENDPOINT_RECORDS.json` 保存；此处不重复恢复几何或猜测顺序。

当前 13/16 支持的 −13.675955 不被这项机会审计推翻。AC 同行验收已证明：在其余已评分端点固定、三个未知 C 分数遵守原公式的 [0,100] 范围时，保留缺失或按任一可评子集补入，效应界限均为 **[−20.722480, −1.972480]**，方向仍负。这里的 0/100 是数学界限，不是把缺失 Q 写成观测 0；具体完成后的 Q 与幅度仍未观测。其证据为 [同行界限回执](../ac_peer/RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json) 和 [27 个边界/可评子集场景](../ac_peer/RAW3_PURE_CLASS_MISSING_Q_BOUNDS_SCENARIOS.csv)。本脚本核对该回执的条件、三个残余团队身份和 13/16 支持后引用，不重复评分。不能把“仍有未处理端点”直接等同于“任何方向都不可判断”，也不据此自动开启新的人工任务。

## 机器可读合同与来源

- `CONDITION_OPPORTUNITY_AUDIT.csv`：每个 reversal_id 的完整注册池/事件、原和辅助可评数、残余事件与端点、57 内外及最终字段。
- `RESIDUAL_EVENTS.csv.gz`：五个表行条件逐事件残余；别名和方法共用事件保留 reversal_id，不能跨行求和充当独立样本。
- `RESIDUAL_ENDPOINTS.csv`：每个残余事件的每个缺 Q 端点及对手是否在 57 内。
- `DISTINCT_RESIDUAL_ENDPOINTS.csv`：按 family/team_key 去重，列明所有关联条件和事件。
- `METHOD_COMPLETE_DIRECTION_SUPPORT.csv.gz`：方法比较原和辅助的完整方向层数值与分母。
- `METHOD_ARM_SUPPORT.csv` 与 `POOL_VALUES.csv`：左右方法及池层值；原共同注册池身份保持。
- `inputs/FULL_COHORT_EXTRACTION_RECEIPT.json`：完整原 68858 行池表和 550794 行设计链接的抽取条件、原 SHA-256、输出 SHA-256；离线运行只用已保存精确范围。
- `source_cache/DOWNLOAD_MANIFEST.json`：仅补读 4 个存在实际残余的原池分片；固定 GitHub commit、下载 URL、SHA-256 和精确 Git blob 校验。

`all_registered_opportunities_covered` 的合同是：每个剩余失败端点都有已确认处理，或已证明在固定节点排序条件下结构不合格。队列外的 `no_connection` 与未解决几何问题不算机会覆盖；少于 4 点作为结构不合格单列。它与 `audit_completed`、`confirmed_order_propagation_complete`、`all_registered_events_Q_evaluable` 是四个不同判断。

复现：`python research/fusion/manual_order_acceptance_20261104/ac_opportunity_secondary/audit_opportunity.py`。输入逐文件 SHA-256 见 `INPUT_MANIFEST.json`；使用前五批、本次 AC 验收及同行验收文件。源版本固定为 `ac395e703d1fef573d1ef3e105df0286d62a0468`。
