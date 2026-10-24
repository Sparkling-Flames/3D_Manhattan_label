# 人员研究第5步：后段人数接入验收（2026-10-24）

入口：[离线研究台第5步](index.html#release=v2&module=personnel_main&tab=4)。读取[人员图包接口](../../workers/personnel_main_figures_v2_20261023/CONSUMER_INTERFACE.json)声明的4张后段人数表和18张固定图；`v2-resources/` 为本地生成且被 Git 忽略的浏览载荷，首次打开前运行 `python -m tools.thesis_main.analysis.build_research_workbench_v2_20261019`。

## 展示边界

- 固定 N≥30 为157图，固定 N=35 为92图，历史 N≥20 为168图；范围互相重叠，不相加。人工难度、观察人数、指标、前后比较和逐图可以切换，静态图及保存值不随筛选重新计算。
- 30→35 的质量 Q 差 +0.227 来自91张两端共同可评分图；失败率 0.725%→1.087% 使用92张候选图。失败和 Q 缺失保留原值，不以0补齐。失败率、缺失率的差值以**百分点**展示；其他指标的差值沿用指标单位。“增加/减少”仅描述数值方向。
- `VFuaQ6m2Qom-04` 在35人满员时 Q、SD、V 缺失，24条自然路径全部不可评分；浏览器逐图显示空值和100%失败。满员的 SD/V 归零只说明有限人员池的同队设计，不代表质量正确。
- 本页只搬运自然前缀保存结果；Semi 为次要分析，门洞与 OOS 各自保持独立，结论不外推至新人或新房间。

## 验证

- `python -m pytest tests/test_population_late_curves_20261024.py tests/test_personnel_main_figures_20261023.py tests/test_research_workbench_v2_20261019.py -q`：15项通过。
- `node --check research/statistics/research_explorer_v1_r2_20261017/personnel-main.js`：通过。
- 离线构建：成功，10,439份原答、261图、7,302份正式质量、60名保留人员、176张保存表。
- Microsoft Edge `file://` 实测：N≥30 默认157图；N=35 的 Q 显示91张共同可评图和 +0.227，失败单列92图及0.725%→1.087%；失败变化显示“百分点”；满员失败图显示 Q 缺失和8.333%→100.000%失败；历史 N≥20 满员范围20–35人；390px视口页面宽度390px，无脚本异常。
- `git -c core.whitespace=cr-at-eol,-blank-at-eol diff --check`：通过。项目地图与文档索引已有研究台入口，本回执只从研究台 README 链入。

未重跑评分、融合或全库浏览器逐图检查；可交互表保留上游保存结果的口径与覆盖边界。
