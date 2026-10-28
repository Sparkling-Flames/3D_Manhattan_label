# 当前新增人工裁定

真源为 `decisions.json`，记录用户2026-10-17在“接手统计数据任务”的直接裁定。

- **b8cTxDM8gDG-04：待定。** 原26人、保留24人继续作为库存保留；暂停当前分析，不将待定自动写成GT错误或永久排除。`descriptive_pool_gate_20261015.build_pool_gate` 读取这层裁定，生成 `current_user_review_pending` 图片级暂停原因；逐作答/人员排除不被覆盖。已有质量、难度v6及历史结果快照不追改，新分析应读取当前门。
- **2t7WUuJeko7-02、2t7WUuJeko7-03：中等（偏简单）。** 两图为新增批独有图片，只登记用户难度与补人规划标签，新增标注仍待纳入。它们不因难度已有裁定而自动获得人员、几何、参考、时间或scope分析资格。

图库读取同一裁定层：待定显示为“问题待定／分析暂缓”；新两图显示“中等 · 偏简单”，难度筛选仍归入“中等”。不改原始GT、标注、日志、冻结输入或补人计划。

当前 `decisions` 表只允许pending状态且图片ID唯一；`new_batch_difficulty_decisions` 只用于新增独有图片，不能覆盖原259图的难度裁定。解除或进一步裁定应另留明确用户依据，不能由分数、补人数量或模型自动解除。

核验：待定不删库存、不恢复此前排除作答、不改变原难度或GT错误标记；当前实图仍24名保留人员且 `pool_analysis_eligible=false`。相关测试见 `tests/test_descriptive_pool_gate_20261015.py`、`tests/test_annotation_gallery_data_20261017.py`、`tests/test_annotation_counts_20261017.py`。

**后续接入状态：** 上述“待纳入”和decisions中的analysis_included=false是当时规划层状态。经本次独立身份/几何/时间审计后，Project98已进入当前manifest；新两图继续采用此人工中等标签，70份质量仍待绑定。正式采用状态以batch_admission及接入审计为准，不更改原用户裁定或b8c04暂停。
