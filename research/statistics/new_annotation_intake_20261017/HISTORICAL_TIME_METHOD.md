# 最近项目 active_time 实际实现与本批适用边界

本次只读复核，主范围为本批 Project 98 之前、按实际作答创建时间最近的两个既有项目 **93、94**。没有运行旧分析入口、重算旧有效秒、解压修改原档或修改当前接入审计。更早 C1/C2/Block2 仅作计算来源背景。

**核心结论：93、94 的日志主要来自与 98 相同的 v10 累计采集，也混有其它版本；最近实际分析消费者将其时间标为 `unfrozen`、秒数为空，没有正式采用有效秒计算。** 可以复用本批 v10 的采集语义及既有通用 loader 的“每 session 取峰值、跨 session 求和”计算；不能据此声称最近项目已冻结采用该计算，也不能搬用旧人员资格。缺 annotation ID、多 session、提交后日志本身，均不等于 task-worker 测量无效。

## 1. 为什么选 93、94；当时实际如何使用

以下时间直接读导出中的 annotation `created_at`，不是文件名导出日期。导出 JSON 均为单行文件（第 1 行）。

| 项目 | 当前保留导出 | 作答数 | 首次至末次创建时间（UTC） |
|---|---|---:|---|
| 93 | [project-93](../../../export_label/新增中文20图/project-93-at-2026-09-21-09-42-4609125d.json) | 186 | 2026-09-13 11:24:35.189425 至 2026-09-21 09:37:33.843318 |
| 94 | [project-94](../../../export_label/新增英文30+20图/project-94-at-2026-09-20-13-45-d09d9d53.json) | 304 | 2026-09-13 14:28:02.393730 至 2026-09-20 22:55:13.895008 |

同期 95 的 161 份作答末次创建为 2026-09-20 02:47:00.279042Z，早于上述两者；其最后日志却晚至 9 月 24 日。因此按作答时间选 93/94，不能用最大项目号、导出日期或日志最后收件时间替代。当前 `export_label` 未见 96/97 导出，不推断它们不存在于服务器。本批 98 的 70 份作答创建范围为 9 月 23 日 06:16:44.753053Z 至 9 月 28 日 13:04:22.432474Z，与上述既有批次区分。

实际消费者及落盘证据：

- [analyze_new_manual_20260921.py](../../../tools/thesis_main/analysis/analyze_new_manual_20260921.py) 第 21–23 行列出 93/94/95 输入；第 **71 行**直接写 `active_time_status='unfrozen', active_time_seconds=None`，第 195 行明言未冻结、不用 lead_time 替代。
- [reviewed_manual_20260921.py](../../../tools/thesis_main/analysis/reviewed_manual_20260921.py) 第 **16 行**换用当前 93 导出，第 **109 行**仍调用上述 intake，第 **141 行**说明“新增 active_time 未冻结，原冻结时间不变”。该脚本没有另行计算本批有效时间。
- [实际 responses.jsonl.gz](../../../analysis_results/new_manual_reviewed_20260921/responses.jsonl.gz)：解压文本行 **2502** 为首条 93、**2688** 为首条 94，均 `unfrozen/null`。本次只读逐条核对，93 的 186 条、94 的 304 条以及同期 95 的 161 条全部如此。
- 后续 [descriptive_inventory_20261015.py](../../../tools/thesis_main/analysis/descriptive_inventory_20261015.py) 第 **44–48 行**将无旧时间事实的新记录置为 `new_collection_time_unfrozen`；第 55–68 行只保留匹配上的历史来源、状态和有效资格，不为这些新记录补算。

因此，对“最近一两个项目实际上怎么算”的严格回答是：**客户端已采集累计时间，分析端尚未冻结采用；不存在可如实引用为这两项目正式结果的另一个新公式。**

## 2. 最近项目的真实脚本分布，而非由当前代码倒推

只读逐行扫描 `active_logs/new_server/*.jsonl`，以 `project_id` 分类。下表是原始行数，含网络重传，不是作答数、独立事件数或有效样本数。

| 项目 | script_version | 原始日志行数 | schema |
|---|---|---:|---|
| 93 | `manual_scope_only_20260913_v10` | 992 | `c2plus_task_worker_v1` |
| 93 | `uncertainty_meta_supervisor_draft_20260825_v4` | 7 | 同上 |
| 93 | `uncertainty_meta_supervisor_draft_20260828_v9` | 3 | 同上 |
| 93 | `stage1_helper_ordercache_hotfix_20260617_v1` | 2 | 未记录 |
| 94 | `manual_scope_only_20260913_v10` | 3378 | `c2plus_task_worker_v1` |
| 94 | `c2plus_task_worker_active_time_20260802_v2` | 325 | 同上 |
| 94 | `uncertainty_meta_supervisor_draft_20260828_v9` | 1 | 同上 |
| 94 | `stage1_helper_ordercache_hotfix_20260617_v1` | 3 | 未记录 |
| 98 | `manual_scope_only_20260913_v10` | 279 | `c2plus_task_worker_v1` |

93 共 1004 行，客户端 epoch 时间范围 9 月 13 日 11:23:51.732Z 至 9 月 23 日 06:11:17.131Z；94 共 3707 行，范围 9 月 13 日 11:25:34.711Z 至 9 月 23 日 10:05:22.218Z。98 全部 279 行确为同一 v10，不能把 93/94 的少量其它版本也默认为 v10。

直接原文例证：[active_times_2026-09-23.jsonl](../../../active_logs/new_server/active_times_2026-09-23.jsonl) **第 1 行**是 93 的末条日志，第 **2 行**是 98 首条日志，二者同一 session、同一 v10、同一 task-worker schema；第 **68 行**是 94 末条日志。93 的 `active_time_key="93|3605|6"`，98 为 `"98|3674|6"`，均无 annotation ID。完整版本计数来自以上指定目录原始行复核，不以零散样例替代。

## 3. v10 客户端确实如何计数

证据为 [ls_userscript_annotator.js](../../../tools/label_studio/official/ls_userscript_annotator.js)；第 **272 行**声明 `manual_scope_only_20260913_v10`。[正式 README](../../../tools/label_studio/official/README.md) 第 **7–9 行**也说明 v10 增加 Manual scope 校验、保留既有 active_time 逻辑。

1. **测量身份**：第 2690–2696、2772–2784 行使用 project × runtime task × worker 三段 key，并携带 `session_id`。不是 annotation 专属计时。[ACTIVE_TIME_README.md](../../../docs/label_studio/ACTIVE_TIME_README.md) 第 **13 行**明确该 schema 刻意不采 annotation、selected annotation、owner 身份。
2. **活动秒**：第 2576–2586 行初始化片段和累计 Map，idle 阈值 15 秒；第 3020–3082 行在页面可见、焦点/页面门禁/身份合格且近期有交互时，每秒 tick 加 1。不是用提交减开始时间，也不是时间戳差。
3. **累计与片段**：第 **2735 行**明确 `active_seconds_fragment` 是当前连续活动片段，非自上次网络上报的增量；第 **2746–2747 行**计算 `active_seconds = previousCumulative + currentFragment`。第 3308–3319 行每 30 秒发送累计，不因此清零片段。因此不能把所有行的累计值或 fragment 相加。
4. **reset**：第 2612–2614、2974–2990 行清零当前片段时，已完成片段进累计 Map。第 3243–3253 行每个脚本实例创建新 session；刷新/不同标签可能产生多个 session。跨 session 求和是测量约定，并不证明多个标签的活动物理时间不重叠。
5. **重传**：第 2821–2823 行按 session + task-worker key 排队；第 2843–2860 行保留较大累计 payload；第 **2869–2892 行**重发原 `item.payload`，客户端 timestamp 不重写。服务端收件时间可更晚，重复收件不应再次加秒。
6. **manualFlush 不是提交**：第 2974–2990、2994–3010、3221–3223 行显示切任务、隐藏页面、pagehide 都可触发关闭与 flush；第 3227–3240 行定义的 `flushActiveTime` 不能据名称推定一定绑定 LS 提交。本次检索未发现该 helper 调用点。

## 4. 可复用的聚合实现及不可混淆的边界

[quality_core/active_time.py](../../../tools/thesis_main/analysis/quality_core/active_time.py) 第 **142–163 行**的通用 loader 合同明确：同 session 取最大累计值，再跨 session 求和。第 **198–206 行**读取 `active_seconds`，区分字段缺席与显式 unknown annotation；第 **301–302 行**取峰值；第 **372–388 行**累加。

对本批无 annotation 字段的 v1，可表达为：

`T(project, task, worker) = Σ_session max(active_seconds)`

其中项目、任务、人员和 session 必须真实对应；这里描述的是采集聚合，当前是否可用于统计还须由本轮审计决定。该 loader 的第 98–103 行“四段 key parser”只在第 **207 行**解析 `active_time_alias_from`，并不是三段 v1 主 key 的拒绝条件；第 **493–495 行**明确可返回 project+task+annotator 匹配。第 189–196 行只有调用时提供日期边界才做窗口过滤，没有内置“必须在 annotation.updated_at 之前”的单作答截断。

**不能混用的情况**：显式 unknown/跨 worker/项目缺失或歧义、缺 session、版本改变了计数语义、同 session 累计回退/重置、重复冲突、页面身份不匹配等，应保留证据单独审计。旧 loader 本身的取最大值会吞掉回退信息，不能把它当作已经验证这些异常安全的证明。多次提交/修改/多参考空间共用同一 task-worker 时，累计时间也不能无证据拆给某一次 annotation 或某个目标；annotation-exact 归属与 task-worker 总活动秒是不同问题。

93/94 的实际消费者没有调用该公式生成正式时间。因此本轮若采用此式，应写成“本轮在同 schema 原始日志上沿用既有通用聚合语义”，保留来源/版本/异常状态；不能写成“复现93/94已冻结秒数”。不要补零或用 lead_time 代替，不改既有历史有效时间。

## 5. clock、时区与提交后日志的直接证据

- [cors_server.py](../../../tools/label_studio/cors_server.py) **第 58 行**以 `datetime.datetime.now().isoformat()` 加 `server_received_at`，是无时区的服务器本地墙钟；第 66 行文件日期亦按服务器本地时间。第 55–74 行只追加 payload，不推断 annotation/提交身份。
- v10 **第 2782 行**的 `timestamp=Date.now()` 是客户端 epoch 毫秒，转换 UTC 不应加本地 offset。Project98 原始日志 [2026-09-23 第 2 行](../../../active_logs/new_server/active_times_2026-09-23.jsonl) 的 `1790144129110` 对应 **2026-09-23T06:15:29.110Z**，而 `server_received_at=2026-09-23T14:15:30.500541`。若直接给后者贴 UTC，会凭空多约 8 小时。该样例与 +08 墙钟一致，但未独立验证服务器时区配置，不将 offset 当全时期既定事实。
- 旧 loader 第 **38–58 行**优先解析 server 时间，带时区时直接去 tzinfo，fallback `datetime.fromtimestamp` 又依赖本机时区；它不是统一 UTC 转换的可靠范本。其聚合公式可复用，不代表旧日期解析可无审计复用。
- 93/94 最后日志真实晚于其最后提交；重试可能改变接收时刻，manualFlush 也不代表提交。因此客户端 epoch 与 annotation UTC 可作“发生时间在提交前/后”的描述诊断，不能仅以晚于 updated_at 一刀切否定 schema 级总活动秒；也不能反向把晚到日志全说成重试。需区分原 payload timestamp、server 收件和每条 session 证据。

## 6. 归档只作背景及本次检查

只读 ZIP 成员复核，没有解压落盘：

- `analysis_results/审核资料_原清单与最终入口_20261010.zip` → `原清单123项/061_b56f856e41a8_prescreen_active_time_fallback_case_audit.md`，成员第 **25–27、80–87 行**区分 task-worker 有日志与 annotation-exact 无法归属，保留 direct/fallback/missing，不证明本轮资格。该 ZIP 的 `063_bba6c52cfa42_prescreen_active_time_source_audit.csv` 第 **1 行**也分列三类来源。
- `analysis_results/legacy/research_cleanup_20260928/pre_v17.local.zip` → `analysis_results/repo_cleanup/legacy/archived_pre_v17_20260802/c1_formal_audit_20260802_v16_r2/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_3ef7d92d/c1_task_worker_active_time_session_audit.csv`，成员第 **1–4 行**保留 raw/dedup/retry/session max；同目录 summary 第 **16–17 行**声明 task_worker 与旧 rule version。仅证实旧聚合有实际落盘，不作为最近93/94的已采用结果。

本次仅修改此研究说明；源码、采集日志、冻结时间及当前审计输出不变。已检查相关统计 playbook 和文档同步规则；本文件为支撑证据，地图/目录登记由主线程统一处理。未运行旧入口或测试：这是只读追溯，逐行源码、原始 JSONL、导出与既有落盘结果交叉核对，不涉及实现变更。
