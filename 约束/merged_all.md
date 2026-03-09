# merged_all.csv 约束规范（2026统一口径版，详细执行稿）

## 0. 文档定位

本文档是 Dev A 发布 merged_all.csv 的 schema 真源。

它直接对齐以下上游来源：

1. 论文正文 01-04 章。
2. 附录 A1 扰动算子库。
3. Label Studio 元标签协议与提交时硬校验。
4. C1 扰动算子规范、C2 d_t 规范、visualize_output_v2 下游契约。

若其他约束文件与本文冲突，以论文正文和本文为准；其余文件应继承本文，而不应重新发明字段语义。

---

## 1. 总体原则

1. merged_all.csv 是 Single Source of Truth。
2. 每一行表示一个 annotator 对一个 task 的一次最终提交记录。
3. 所有图表、审计表、路由模拟和附录输出都必须可由该表追溯。
4. 不允许下游 Notebook 通过私有中间表重定义字段语义。
5. 所有 NA、拒收、冲突、intentional-invalid 都必须显式记录，不允许静默过滤或补值。

---

## 2. 行粒度与主键

### 2.1 行粒度

一行 = 一个 (task_id, annotator_id) 最终有效提交。

### 2.2 主键字段

| 字段         | 类型   | 约束                                |
| ------------ | ------ | ----------------------------------- |
| task_id      | string | 当前任务实例唯一标识，不可缺失      |
| base_task_id | string | 同源图像/同源任务去重主键，不可缺失 |
| image_id     | string | 原始图像标识，不可缺失              |
| annotator_id | string | 标注员唯一标识，不可缺失            |

补充：

- 若存在多个 session，同一 (task_id, annotator_id) 先在 active_time 聚合层合并，再进入 merged_all.csv。
- 发布层统一使用 annotator_id，不再使用 worker_id 作为主字段名。

---

## 3. 实验分组字段

### 3.1 基础字段

| 字段          | 类型   | 约束                                                                                        |
| ------------- | ------ | ------------------------------------------------------------------------------------------- |
| dataset_group | string | 阶段-条件联合标识，如 PreScreen_manual / Calibration_manual / Validation_semi / Manual_Test |
| condition     | string | 仅允许 manual / semi                                                                        |
| subset        | string | 如 anchor / core / reserve / blind_trust / correction / audit，可为空                       |

### 3.2 口径要求

- dataset_group 是当前导入链路和分析链路的发布层真源字段。
- condition 是 dataset_group 的规范化条件轴，不得与 dataset_group 语义冲突。
- 若需要更粗粒度阶段汇总，可在下游派生 stage_family，但 stage_family 不是主表真源字段。

### 3.3 合法示例

- PreScreen_manual
- PreScreen_semi
- Calibration_manual
- Calibration_semi
- Validation_semi
- Manual_Test
- SemiAuto_Test
- Gold_manual

---

## 4. 元标签字段

### 4.1 Scope

| 字段   | 类型   | 约束                                                                                                              |
| ------ | ------ | ----------------------------------------------------------------------------------------------------------------- |
| scope  | string | 发布层 raw alias，仅允许 normal / oos_geometry / oos_open_boundary / oos_split_level / oos_insufficient / missing |
| is_oos | bool   | 由 scope 派生                                                                                                     |

规则：

- scope = normal 时，is_oos = False。
- 其余 OOS 子类时，is_oos = True。
- 若系统侧缺失 scope，发布层应将 scope 记为 missing，同时 scope_filled = False。

### 4.1.1 XML alias 与报告层标签映射

为了同时对齐 XML、现有 tools 实现与论文文字表述，发布层采用如下分层：

| XML / CSV raw alias | 报告层 canonical label | 含义                    |
| ------------------- | ---------------------- | ----------------------- |
| normal              | in_scope               | 相机房间、进入主 I 口径 |
| oos_geometry        | oos_geometry           | 几何假设不成立          |
| oos_open_boundary   | oos_open_boundary      | 边界不可判定            |
| oos_split_level     | oos_multi_plane        | 错层 / 多平面           |
| oos_insufficient    | oos_insufficient       | 证据不足                |
| missing             | missing                | 系统侧缺失              |

要求：

- `scope` 字段本身存 raw alias，以便与 XML 和 `tools/analyze_quality.py` 保持一致。
- 若报告层或 Notebook 需要使用 `in_scope` / `oos_multi_plane` 等论文表述，必须由固定映射派生，不得反写覆盖 `scope` 原值。

### 4.2 Difficulty

| 字段       | 类型   | 约束                  |
| ---------- | ------ | --------------------- |
| difficulty | string | 多选 alias，以 ; 拼接 |

允许 alias：

- trivial
- occlusion
- low_texture
- seam
- reflection
- low_quality

规则：

- 必须使用 ; 分隔，不带空格。
- 若包含 trivial，则不得与其他 difficulty 共存。
- 空字符串、NA、互斥冲突都必须进入 Type 4 审计链。

### 4.3 Model Issue

| 字段                | 类型         | 约束                                        |
| ------------------- | ------------ | ------------------------------------------- |
| model_issue         | string or NA | 仅 semi 条件要求填写；多选 alias，以 ; 拼接 |
| has_model_issue     | bool or NA   | semi 下由 model_issue 派生；manual 可为 NA  |
| model_issue_primary | string or NA | 仅在 semi 且存在非 acceptable issue 时填写  |

允许 alias：

- acceptable
- overextend_adjacent
- underextend
- over_parsing
- corner_drift
- corner_duplicate
- topology_failure
- fail

规则：

- 仅 semi 条件必填。
- acceptable 若出现，不得与其他 issue 共存。
- manual 条件不强制要求 model_issue，建议写 NA，而不是空字符串。
- model_issue_primary 必须从已勾选 issue 中按固定优先级派生，不得人工随意填写。

建议优先级：

1. topology_failure
2. fail
3. overextend_adjacent
4. over_parsing
5. underextend
6. corner_drift
7. corner_duplicate
8. acceptable

---

## 5. 元标签合规审计字段

以下字段用于 Type 4 和过程性证据披露，不能省略。

| 字段                         | 类型 | 语义                               |
| ---------------------------- | ---- | ---------------------------------- |
| scope_filled                 | bool | scope 是否非缺失                   |
| difficulty_filled            | bool | difficulty 是否非空                |
| difficulty_conflict          | bool | trivial 是否与其他 difficulty 共存 |
| model_issue_required         | bool | 当前记录是否应填写 model_issue     |
| model_issue_missing_required | bool | semi 条件下 model_issue 是否缺失   |
| model_issue_conflict         | bool | acceptable 是否与其他 issue 共存   |

规则：

- 这些字段由清洗层兜底生成，即使前端 required 与 userscript 已阻断也不能省略。
- 任何一个冲突/缺失条件触发，都必须能追溯到 type4_flag = True。

### 5.1 当前实现兼容字段

考虑到 `tools/analyze_quality.py` 当前仍会输出部分兼容/过渡字段，发布层允许保留以下字段，但不得让它们取代主字段语义：

| 字段                    | 类型       | 说明                                                                      |
| ----------------------- | ---------- | ------------------------------------------------------------------------- |
| scope_missing           | bool       | 与 `scope_filled` 互补的旧兼容字段                                        |
| difficulty_missing      | bool       | 与 `difficulty_filled` 相关的旧兼容字段                                   |
| model_issue_missing     | bool       | 与 `model_issue_filled` / `model_issue_missing_required` 相关的旧兼容字段 |
| model_issue_types       | string     | 去掉 `acceptable` 后的 issue 集合，供旧分析链兼容                         |
| difficulty_conflict_v2  | bool       | 旧版冲突兼容字段                                                          |
| model_issue_conflict_v2 | bool       | 旧版冲突兼容字段                                                          |
| is_normal               | bool or NA | 旧版由 scope 派生的兼容字段                                               |

要求：

- 新文档与新图表优先读取主字段，如 `scope_filled`、`is_oos`、`model_issue_primary`。
- 兼容字段可以保留，但不能成为新的真源或替代冻结映射规则。

---

## 6. 几何与一致性字段

| 字段                 | 类型               | 约束                                       |
| -------------------- | ------------------ | ------------------------------------------ |
| iou                  | float or NA        | [0, 1]                                     |
| iou_edit             | float or NA        | semi 下用于工作量代理；manual 为 NA        |
| IAA_t                | float or NA        | 任务内一致性，两两 IoU 中位数              |
| iou_to_consensus_loo | float or NA        | leave-one-out 共识 IoU                     |
| boundary_rmse        | float or NA        | 非负                                       |
| corner_rmse_match    | float or NA        | 非负，仅在匹配稳定时可用                   |
| W_tot                | float or int or NA | 加权共识权重总和；为 0 时相关派生量必须 NA |

规则：

- iou_edit 只表示改动幅度，不表示正确性。
- W_tot = 0 时，任何依赖加权共识的输出必须记为 NA，不允许补 0 或 fallback。
- topology_failure / fail / intentional-invalid 相关不可比样本，主质量指标可为 NA，但必须有明确状态说明，不得伪装成 0。

---

## 7. 工人可靠度与画像字段

| 字段                | 类型         | 约束                                            |
| ------------------- | ------------ | ----------------------------------------------- |
| r_u                 | float or NA  | 全局可靠度                                      |
| r_u_lcb             | float or NA  | 可靠度下界                                      |
| r_u_ucb             | float or NA  | 可靠度上界                                      |
| h_u                 | float or NA  | CI 半宽                                         |
| S_u                 | float or NA  | spammer score                                   |
| worker_group        | string or NA | stable / vulnerable / noise / ungrouped         |
| worker_group_reason | string or NA | 分组触发原因代码                                |
| group_rule_version  | string or NA | 分组规则版本                                    |
| core_scene          | string or NA | 核心场景标签或 other                            |
| r_u_s               | float or NA  | 场景特异可靠度                                  |
| r_u_s_lcb           | float or NA  | 场景特异可靠度下界，若表 C 采用保守口径建议保留 |

规则：

- worker_group 不能脱离 worker_group_reason 与 group_rule_version 单独发布。
- worker_group_reason 建议使用规则码，而不是长句自然语言，例如 noise_low_lcb、vuln_gap、vuln_bucket_fail。
- core_scene 主文不应超过 4 个核心场景，其余合并为 other。

---

## 8. 标注前风险信号字段

### 8.1 d_t 相关

| 字段               | 类型            | 约束                                                                             |
| ------------------ | --------------- | -------------------------------------------------------------------------------- |
| d_t                | float or NA     | OOD 风险代理                                                                     |
| d_t_status         | string          | success / extract_fail / ref_hash_mismatch / embed_dim_error / knn_runtime_error |
| d_t_k              | int or NA       | 主分析固定 10                                                                    |
| d_t_ref_hash       | string or NA    | 参考池 hash                                                                      |
| d_t_model_ver      | string or NA    | embedding 模型版本                                                               |
| d_t_metric         | string or NA    | 主分析固定 euclidean                                                             |
| d_t_pool_size      | int or NA       | 主分析固定 100                                                                   |
| d_t_failure_reason | string or empty | 失败时必填                                                                       |
| d_t_compute_ts     | string or NA    | ISO 时间戳                                                                       |

### 8.2 g_t 相关

| 字段          | 类型         | 约束                                                  |
| ------------- | ------------ | ----------------------------------------------------- |
| g_t_triggered | bool or NA   | 结构风险是否触发                                      |
| g_t_status    | string or NA | success / missing_input / rule_error / not_applicable |

规则：

- d_t 字段必须完全继承 C2 输出，不得由 Dev A 自行补写。
- d_t 或 g_t 失败时只能写 NA + 状态，不能补默认值。

---

## 9. active_time 审计字段

| 字段                | 类型         | 约束                                                 |
| ------------------- | ------------ | ---------------------------------------------------- |
| active_time         | float or NA  | 单位秒，非负                                         |
| session_count       | int or NA    | 同一 task-annotator 聚合的 session 数                |
| has_short_time_flag | bool or NA   | active_time < 1 秒                                   |
| has_long_time_flag  | bool or NA   | active_time > 3600 秒                                |
| has_unknown_id_flag | bool or NA   | task_id / annotator_id / project_id 是否存在 unknown |
| project_id          | string or NA | active_time 日志来源项目标识，用于审计追溯           |
| script_version      | string or NA | active_time 采集脚本版本                             |

规则：

- active_time 是 RQ1 主终点相关字段，必须可审计。
- unknown ID、script_version 缺失、多 session 都应能在口径 T 中披露。

---

## 10. 反例标记字段

| 字段       | 类型 | 语义                       |
| ---------- | ---- | -------------------------- |
| type1_flag | bool | 低一致性反例               |
| type2_flag | bool | 异常编辑反例               |
| type3_flag | bool | 几何合法性失败反例         |
| type4_flag | bool | 流程 / 字段 / 格式失败反例 |

规则：

- type3_flag 的语义已锁定为几何合法性失败，不再使用“门控失败反例”旧口径。
- type4_flag 必须可由元标签合规字段、系统 NA、导出缺损等残余问题追溯。

---

## 11. 与 intentional-invalid / 扰动来源的连接字段

若记录来自 semi trap 或下游需要追溯其初始化来源，建议至少保留：

| 字段                     | 类型         | 约束                                                        |
| ------------------------ | ------------ | ----------------------------------------------------------- |
| source_type              | string or NA | manual_anchor / synthetic_operator / natural_failure        |
| perturbation_operator_id | string or NA | 必须与 C1 alias 一致                                        |
| lambda_level             | string or NA | weak / medium / strong / fixed                              |
| iou_status               | string or NA | computed / na_intentional / na_geometric / na_runtime_error |

规则：

- 若 perturbation_operator_id 存在，必须与 A1 和 C1 的 alias 完全一致。
- topology_failure / fail 进入主表时，不得伪装为正常可比样本。

---

## 12. 下游最小可支持输出

merged_all.csv 必须足以直接支持：

1. T / I / M 三级口径统计。
2. IAA 分布和 IoU_edit 散点图。
3. Type 1-4 频次图。
4. active_time 审计图与审计表。
5. 图 D 工人画像。
6. 表 C worker × scene 矩阵。
7. d_t / g_t 驱动的分层与路由模拟。

若某输出仍依赖表外中间文件，必须在发布说明中明确依赖，不能隐式存在。

---

## 13. 最小 manifest 要求

发布 merged_all.csv 时，应同时产出 manifest，例如：

```json
{
  "schema_version": "merged-all-v2026-unified",
  "generated_at": "2026-03-07T00:00:00Z",
  "code_git_hash": "<commit>",
  "group_rule_version": "group-rule-v1",
  "dt_rule_version": "c2-v2026-detailed",
  "perturbation_rule_version": "c1-v2026-rebuilt",
  "perturbation_manifest_hash": "sha256:...",
  "reference_pool_hash": "sha256:...",
  "notes": "对齐论文 01-04 章、附录 A1 与约束目录统一口径"
}
```

---

## 14. 验收清单

1. 字段集合是否覆盖本文最小必需列。
2. dataset_group 与 condition 是否语义一致。
3. condition 是否统一为 manual / semi。
4. scope / difficulty / model_issue 是否使用锁定 alias。
5. type3_flag 是否已统一为几何合法性失败语义。
6. type4_flag 是否可由合规审计字段追溯。
7. worker_group 是否伴随 worker_group_reason 与 group_rule_version 一起发布。
8. d_t 失败样本是否完整保留状态与原因。
9. W_tot = 0 是否始终输出 NA 而非 fallback。
10. active_time 审计字段是否足以支撑口径 T 披露。

---

## 15. 当前结论

merged_all.csv 不是“清洗后的普通宽表”，而是论文主分析、审计披露与路由模拟共享的发布层真源。主线要求只有一句话：

上游规则先冻结，主表字段一次定义，下游只能继承，不能重解释。
