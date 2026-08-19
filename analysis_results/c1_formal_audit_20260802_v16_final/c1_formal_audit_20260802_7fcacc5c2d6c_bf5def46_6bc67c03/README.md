# C1-A v16 正式 freeze 云端复核包

这是绑定 Git commit `6b2564c66295f4cd1a3b2516dee2feffb661896e` 与方法合同 `paper_a_method_20260802_v16` 的精简正式证据包，供云端 AI 复核和后续分析。

正式状态：`C1_EVIDENCE_FROZEN=true`、`C1_CANONICAL_CLOSED=true`、`C1_MEASUREMENT_FROZEN=true`，三轴 `Q_GT`、`R_peer`、`F_struct` 均为 `frozen`，closeout blocker 为 0。Timing 仅为辅助 operational measure，不参与三轴、正式排名或 C2-B roster。

几何 crowd 主规则为 boundary grid 256、cutoff 0.95，并要求 pointwise topology compatible；0.93/0.97 仅用于敏感性分析。正式 task-condition 分类为：31 unimodal、42 dominant_with_dissent、18 supported_multimodal、10 not_evaluable；最大团/划分搜索截断为 0。

Public GT 共 458 项：456 项走严格解析，2 项使用只依赖冻结点序的 ordered duplicate-x reference fallback；没有利用工人结果修订 GT。W034 的 17 项授权 replacement timing 均为 `eligible_with_protocol_deviation`，基于 task-worker 日志与事前人工确认回溯声明，`annotation_exact_validated=false`。

本目录只跟踪正式摘要、freeze manifest、worker profile、三轴证据、crowd 分类、task-worker timing、scope/eligibility、canonical geometry，以及 topology sequential preflight 直接消费的 GT quality evidence、task-building binding、operational reference audit 和空 conflict queue。未在本目录重复上传 Label Studio 原始导出、active logs、原图、raw snapshots 或其他中间缓存。
