# 字段与来源接口

接口身份：`personnel_profiles_composition_integration_v1`。主入口[INTEGRATION.json](INTEGRATION.json)；每张表列出路径、行数、字段名和接口生成时的`prepared_not_dashboard_integrated`状态；当前页面采用状态以[展示回执](../../statistics/research_explorer_v1_r2_20261017/PERSONNEL_RESULTS_20261021.json)与本包ACCEPTANCE为准。外部研究包名只记录包名，不暴露用户下载路径。所有表可由精简包内`source/`刷新。

## 人员与分母

人员画像键必须为 **worker_id + condition + origin + panel**。Manual/Semi分别研究，origin保留`new`/`v1`来源身份，panel保留ordinary/doorway。源表的special正式质量独立保存在`source/tables/profiles/special_quality_profiles.csv`，不能用普通主Q字段覆盖它。

库存9217份非OOS作答/233图、62个来源W身份；普通Manual62格、普通Semi61格。这不是62/61名正式可组队人员。正式质量7302份、60名W身份；普通Manual5719、普通Semi901、门洞571、特殊用途111（Manual66、Semi45）。W019/W026等无Q记录保留空白，不记0分，也不因此恢复组队资格。

|字段组|含义与必须并列的分母|
|---|---|
|n_inventory/n_images/n_buildings|本格库存对象/独立图片/建筑数。画像行不是互不相交的人员。|
|n_quality、n_quality_images/buildings|普通或门洞主Q资格的正式质量支持，Q_mean/Q_q10/Q_peer及D10_mean沿用该资格。n_quality_all_uses另含特殊用途，n_special_quality单列。|
|Q_mean、Q_q10|对应支持集合的B8L2均值/第10百分位；不是潜在能力或新合成等级。|
|Q_peer、Q_peer_q10|同图、condition、目标参考及版本内留一同行残差的个人均值/第10百分位。Q同行任务不按origin切开；不在时间列复用此任务键。|
|source_time_n、source_time_median|本格独立/池资格相容且源时间>0的真实活动/报告时间支持与中位数；不等于n_quality。新旧来源语义保留time_source_kind。|
|n_time、n_time_buildings、relative_time|有相容同行时间的任务调整支持、建筑数，及exp(平均留一同行log时间差)；另按origin和time_source_kind分任务。<1为较快，不能作跨来源统一秒数倍率。|
|target_time_n/target_time_median|与当前目标匹配的时间证据；缺失不由source时间、lead_time或0填补。|
|Q_supported/T_supported/hard_supported|各自支持门槛标志，详情沿用原PROFILE_FIELDS；不以Q支持替代T支持，也不是固定人员准入规则。|
|hard_n/hard_buildings、hard_Q_mean/peer|粗难度困难档的实际支持、水平及相对同任务同行表现；hard_minus_easy_peer为本人困难减简单的残差，不自动命名困难专家。|
|n_cleaning_excluded、n_excluded_by_review、n_historical_not_accepted|n_cleaning_excluded是后两列（人工筛除、历史未接纳）之和；库存是此画像数量比例的分母，不等于共同质量图分母或严重错误次数。|
|n_pending、n_pool_only_restricted、n_quality_missing_in_pool|待定、仅图片/池用途受限、池内质量缺失分别保留；不能全部写成人员筛除。|
|n_legacy_person_error/n_person_error_candidate|明确历史归因与候选证据，不等于当前独立严重错误gold；两列可能重叠，不简单相加。|
|n_scope_response/out、n_scope_judged/correct|前两项为回答及out-of-scope倾向，后两项才是相容人工裁定机会/答对。没有可评价OOS机会不补造OOS准确率。|
|confirmed_error_opportunities/unchanged|已确认错误且精确初始化相容的机会/未纠正，保留独立证据语义。|
|reported_error_opportunities/unchanged|新增批报告错误机会/未改；缺精确初始化，不与确认错误合并为同强度机会。|
|semi_edited_error_outcome_unknown_n、semi_exact_initializations|编辑后是否纠正未知的数量、具备精确初始化的数量；编辑不等于纠正。|
|n_geometry、short_turn_peer、pair_peer|几何表达支持及相对同行的短转折/点对表达差；可含质量暂停图，只描述表达，不恢复评分/投票。|

原完整字段说明见[source/notes/PROFILE_FIELDS.txt](source/notes/PROFILE_FIELDS.txt)。难度实际字段、零机会格及其它几何机制保存在source完整画像/worker_difficulty/worker_mechanisms，不在接入小表中另造定义。

`history_lobo.csv`在人员四键前加入 **target_building**；所有历史数值排除该目标楼，支持门槛分别保留`Q_supported_8images_3buildings`和`T_supported_8images_3buildings`。这是回顾性楼外历史，不宣称严格时间顺序预测。完整困难历史同键保存在`source/tables/profiles/lobo_difficulty_features.csv`。

## 原因与资格

`eligibility_counts.csv`在四键上按cleaning_disposition、quality_use、quality_usable、source_pool_eligible、pool_analysis_eligible、image_quality_gate联合分组；records/images/buildings分别是对象数/独立图/楼。每对象只在本联合分组出现一次。

`quality_unavailable_reason_counts.csv`在四键上按reason_code和cleaning_disposition分组。原因来自原逐对象索引的机器原因列表，GT暂停、几何/参考缺失、用途限制与清洗处置分别可见。一个对象可有多个原因，跨码相加不是唯一对象数。图数跨分组也不能相加作唯一图数。原字审核理由不归档；未凭原因猜测严重度或心理动机。

逐对象追溯用`source/tables/profiles/record_index.csv.gz`的object_id；它是派生来源索引，不是原始几何真源。几何/完整证据仍回到仓库`research/statistics/v2_evidence_audit_20261019/records.json.gz`，参考以reference_id/reference_version、chosen_target_id连接，不能只按图片码。

## 组合小表

- `quality_n7.csv`：从`source/tables/quality/composition_effects.csv`仅取n=7、phase=all，保留layer/source_policy/H/L/baseline，另从layer显式拆出condition/panel。该线可能混合来源，source_policy不能冒充个人origin；精确来源仍由团队成员与画像四键连接。`d_B8L2`等为指定构成减对应baseline的图内、建筑等权差；保留paired_images/buildings及可评分支持，不以请求次数充当独立样本。
- `speed_n5.csv`：从`source/tables/speed/main_summary.csv`仅取n=5、contrast=versus_slow。键包含layer/condition/origin/domain/n_fast/contrast。质量变化、source_time_ratio、loss_over_5及joint_save20_lose_at_most2分别解释；scored_comparisons/timed_comparisons为各自实际支持，缺失/失败不设0分。
- domain=above_peer_Q仅为历史相对Q非负的人群域，不是所有域的统一人员类。H/L随目标建筑历史变化；快慢配对在相同origin内历史Q差≤3、时间倍率≥1.5，不以目标图成绩或用时选人。
- 联合达标为总源劳动至少节省20%且质量损失不超过2分；超过5分损失率另列。时间比先log再图/楼等权后exp，不能改成两项总秒数均值之比。并行代理保留同时开工假设。

## 案例与资源

团队键为pool_id + team_key；精确人员列表来自已存请求及成员对象。`case_teams.csv`的member_object_ids为JSON对象ID数组，member_workers为同序W身份数组；condition/panel用于定位条件，不把团队origin伪造成单一人员来源。

geometry_path定位案例JSON，geometry_pointer是RFC6901形式的`/panels/i`；融合点为该面板的`state.candidate.points`，完整支持/对应/环序在同一state保存。参考位于顶层reference（含points_1024x512）。原答位于records，按object_id匹配；不要按显示顺序猜人。score和对象资格分别保留，不从展示恢复排除对象。精确设计请求/成员还在source/design及source/claims中保存。

image_references的source_path是仓库根目录相对路径，release_url是原图Release入口；未重复打包原图或字体。4个团队案例没有把6张原图都当成额外验证图；原始jtc/Uw/e9三张PNG主板与Semi几何均可被展示线程引用。新批原始初始化未补造。

## 验证身份

INTEGRATION只表示接入素材准备完成，不表示研究台已消费或浏览器交互验收。CHECKS记录本线程的实际接入检查；原包重放回执保留原作者身份，统筹4例12队有限核查独立说明。未重新执行88048队、原始活动日志、全量个体评分或新人员分类。
