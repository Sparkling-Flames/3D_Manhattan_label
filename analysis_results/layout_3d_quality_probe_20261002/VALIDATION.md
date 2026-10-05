# 交付核验（2026-10-02）

## 改动与边界

新增 `tools/thesis_main/analysis/layout_3d_quality_probe_20261002.py`、对应 `tests/test_layout_3d_quality_probe_20261002.py` 和本结果目录。复用现有几何及阶段2测量，不改共享实现。地图与索引各新增一条探索入口。

人员人工确认环保留；未确认环使用已有预处理共享x稳定升序，不重复平均、重配对、移动或补点。原始GT保留来源参考环；人工GT遵从确认状态。实际由统一bundle读取195份作答，134确认、48默认、13无可用点。原始导出、清洗、分析资格、历史合同及既有数值均未修改。Pro/dot归档原件未改动。没有提交或上传。

结果390行：原始GT182可计算＋13几何不可用；人工GT71可计算＋7几何不可用＋117参考缺失。不能把273条存在参考的记录都称为有效比较。17份改序均成功按审核绑定标签映射至最终点对；只重放邻接，不重放历史坐标。

## 验证

先新增测试，确认新模块缺失导致测试收集失败，再实现。最后运行：

```powershell
python -B -m pytest tests/test_layout_3d_quality_probe_20261002.py tests/test_layout_metric_response_20261001.py tests/test_layout_foundation_20260930.py tests/test_research_round_20260929.py tests/test_layout_metric_probe_20260926.py tests/test_consensus_contract_20260923.py -q -p no:cacheprovider -W error::RuntimeWarning
python -B -X utf8 -m tools.thesis_main.analysis.layout_3d_quality_probe_20261002 --out analysis_results/layout_3d_quality_probe_20261002
python -B -X utf8 -m tools.thesis_main.analysis.render_paper_a_method_contract --check
git diff --check
```

- 40项通过，其中本轮6项覆盖排序与身份、连续高度积分、体积退化关系、非平顶、地平线失败及缺失输入。
- 实验成功；15条既有有效比较的底面/边界/墙带逐字段一致，嵌入源点与当前bundle身份一致。
- 独立只读检查：195份作答逐项核对源坐标、质量/共识gate、确认环及默认x顺序；17份改序的前后点集完全相同；两CSV表头与字段合同一致，分别390/17行。
- 三张科学结果图已目视检查，没有截图或临时检查图片需要清理；交付PNG保留。
- 当前合同渲染及diff检查通过；仅索引登记，不修改正式评分或资格语义。

未运行全仓库、训练、浏览器或LS运营测试：本轮没有修改这些链路。未运行人员分类和融合实验，属于后续研究。

## 剩余限制与下一步

水平顶面模型体积依赖单一房高假设；不是实测封闭空间。自身主轴残差不是与GT的空间距离；非Manhattan场景只保留诊断。12图为既有定向面板；改序的17份仅来自两图，默认环不冒充人工确认。科学图的边编号及周长分别沿各自环，不代表已建立墙对应。

下一步审阅模型体积、底面及墙高/方向指标的具体分歧，再决定质量测量保留项；不由本次结果冻结人员权重或扩展候选生成。
