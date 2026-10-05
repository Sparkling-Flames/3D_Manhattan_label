# 最终审核研究输入

唯一完整分析入口：[manifest.json](manifest.json)，由当前机器合同`data.analysis_bundle`指定。预处理、研究解释、评论和最终统计均在本目录内；原目录作为历史来源保留。

公开范围更新（2026-10-01）：用户授权“这些映射和原评语允许公开”。当前公开仓库含[内部编号与别名映射](../research_round_20260929/private_alias_map.json)及[历史评语来源索引](final_review/历史评语_去重来源索引.csv)；映射连接27个人员编号及3441个对象编号，不是姓名表。独立研究包的 `inputs/panel.json` 继续使用别名投影。9/29生成manifest内的“仅本地分析”文字为当日状态，当前授权范围以本段为准；不据此扩大其他材料的公开范围。

```python
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
bundle = load_current_bundle()  # 读取时校验跨表一致性，不一致则报错
data = bundle['data']           # points_1024x512为最终环序坐标
research = bundle['research']   # 研究解释与交叉表
comments = bundle['comments']   # 原话及来源明细
```

完整重建：`python -m tools.thesis_main.data_prep.consolidate_research_input`。不要只重建一个组件后直接进入分析；读取函数会核对包内状态。旧`load_current_input()`仅为包内坐标/状态视图的兼容读取，不包含全部汇总。

本目录文件：`preprocessed_source.json`（坐标、GT及审核状态）、`research_tables.json`（研究解释）、`comments.json`（全批次评论）、`final_review/`（全部最终JSON/CSV统计）、`validation.json`（机器一致性结果）。`manifest.json`登记每个入口及来源。

- [读取示例、字段合同及边界](../../docs/thesis_main/最终审核数据接入_20260929.md)
- [机器字段说明](field_contract.json)、[数量汇总](summary.json)
- [原最终统计与分类入口](../final_review_summary_20260929/index.html)
- [研究解释与交叉机器表字段入口](../review_research_tables_20260929/field_contract.json)：GT、场景、Trap、范围/细节、排除原话及表示转换；只补解释证据，不改变当前数据。

3152份人员记录/259研究图＋259原始GT＋30人工GT。人工GT另有2张仅参考图，不进入人员样本分母。完整保留最终配对、共享x、1295份确认环及默认未审状态、同房分类、OOS/门洞、范围/细节证据、借用点来源和各分析用途限制。

`points_1024x512`使用最终环序，配对索引为`matterport_links_zero_based`；`preprocessed_points`保持源身份顺序，配对索引为`links_zero_based`。二者不可混用。原始点未覆盖，近180°中间点未删除。

验证：合包生成及读取一致性检查通过；9项定向pytest通过（含配对预处理、最终统计、评论、研究表和合包校验），当前合同渲染及diff检查通过。此轮未运行新质量/共识实验或浏览器测试（数据接入无UI变动），无新增截图。validation.json保留检查范围及限制。
