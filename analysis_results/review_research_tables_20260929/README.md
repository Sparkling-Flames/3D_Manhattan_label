# 研究解释与交叉机器表

AI读取顺序：`field_contract.json` → `research_tables.json`中的`purpose`、`rules`、`summary` → 相应交叉表与对象明细。统计单元、分母和ID索引见字段合同。

六项均有证据：GT状态、场景适用性、Trap/模型影响、空间/细节/执行差异、重点人员排除原话、配对/环序/表示前后状态。同房继续引用完整原分类。关键词命中是线索，不是新裁决；缺记录不是否定。近180°中间点的两种解释独立保留，不自动删点。

生成：`python -m tools.thesis_main.analysis.build_review_research_tables_20260929`。

验证：`python -m pytest tests/test_review_research_tables_20260929.py tests/test_current_research_input.py -q -p no:cacheprovider`，3项通过。未改坐标、清洗、资格或网页；不新增复审任务，未做浏览器检查，无新增截图。
