# Z6-10：旧P1 trap来源与本轮判断

2026-10-21，针对用户要求回查旧P1；只读原始输入及既有逐份证据，不改数据、资格或融合规则。

**结论：Z6MFQCViBuw-10的旧P1 Semi任务确为人工构造的角点重复trap；本轮展示的W017作答保留了该重复。** trap属于具体Semi初始化任务，不能据此把同图Manual作答或其它来源一并称为trap。

## 直接证据

- [旧导入任务](../../../import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json)中该图的`task_id=synthetic::legacy_disjoint_source_006_corner_duplicate`，`semi_role=trap`、`trap_family=corner_duplicate`、`init_type=misleading`、`source_type=trap_synthetic`。
- [旧专家审核第4行](../../../analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/prescreen_synthetic_expert_review.csv)：运行任务3169／镜像任务3097，`trap_effective=true`，备注“角点重复，trap 有效且匹配”。
- [旧P1作答账本](../../../analysis_results/prescreen_closeout_final_gold_v2_20260701/p1_exact_copy_low_time_audit/p1_exact_copy_low_time_event_audit.csv)：任务3097、项目29、作答3400，`stage_filter_bucket=explicit_p1`。本轮未采用该账本的时长或异常分类作研究判决。
- [当前v2逐份证据](../../statistics/v2_evidence_audit_20261019/records.json.gz)：`object_id=1445e3889419575a`、W017，旧阶段P1／任务3097／作答3400，`exact_initialization_bound=true`；初始化数组与原始最终数组完全相同，`edited=false`、`known_error_unchanged=true`。重复的两对分别位于x=363和369.144。

这能确认“重复trap未被改正”，不能证明标注者没有查看或没有思考。

## 本轮人工判断及机制解释

用户确认蓝色8人组与橙色6人组意图表达同一墙角，橙色组偏移较大；这不是精确坐标认证，也不是其它来源的trap证据。原始人工回执保留在本机，不随公开资料提交。

采用目标身份判断：蓝8人与橙6人组表达同一墙角，而非两个确认的不同目标。两组共享W017、W125、W129、W132，不能相加为14名独立支持者。候选修正锁住原达票组后又补出第二组，在本例形成同角重复输出，因此仍不能直接采用为生产方法。

W125和W129的当前记录报告做过修改，但没有可精确绑定的初始几何；W132报告保留已知错误，同样缺少精确初始绑定。不能把W017的确证扩成四人均已独立证实未改trap。

本例应解释为**共享错误初始化可能被多人保留，随后参与融合**。不能再把新增节点解释成多人独立发现了另一处真实细节；也不据此删除作答或改变投票权重。

## 本次检查范围

已核查上述旧导入、专家审核、P1账本及当前逐份初始化／最终坐标相等关系。未重跑历史部署审核、全库融合或测试；本次没有改代码。此文件为本主题支撑记录，已检查全局地图和README的主题入口；全局目录同步留给统筹线程。
