# 统计、参考重算与扩展接续

2026-10-16。本次完成41图506份原作答全量核验、空间参考目录、事先目标绑定、固定算法重算、独立统计快照及可视化。90份有完整评分，84份新增当前质量，总数891；manual828份/73图，semi63份/4图。135份唯一绑定，371份待绑定；39新空间中12份完整参考可确定、27份仍待补。两修订GT的10份作答均完成重算。

## 边界与来源

原始作答、原GT、难度v3、正式资格、人数门和评分参数均未修改；旧统计、融合及同房曲线保留。质量统计及既有同房描述比较由更新后的逐条数值重建，没有新融合实验。重算不补造新目标采集时间，IoU仍为均高棱柱口径。

空间目录保留原回执、参考版本、原完整源和新增边界构造。合法替代空间不擅自换成当前难度目标；371份待绑定中含2份只确认A/B族的作答。27份参考缺口不统一命名为“需重标全部顶部”，应按目录内域超出等准确原因处理。几何可计算仍不解除GT错误、旧暂停或人员限制。

## 验证

主线程执行下列定向测试，32项通过：

```powershell
python -m pytest tests/test_scope_reference_reconstruction_20261016.py tests/test_scope_quality_binding_20261016.py tests/test_scope_quality_scoring_20261016.py tests/test_scope_quality_rescore_20261016.py tests/test_descriptive_statistics_current_20261015.py tests/test_descriptive_statistics_current_figures_20261015.py tests/test_descriptive_snapshot_inputs_20261015.py -q
```

[独立审计](INDEPENDENT_AUDIT.md)逐对象核对506份来源、绑定与门，重建90任务队列，抽核冻结评分，复算121行主要统计、2673行人员对照及3780行同房配对。工作簿与图的视觉/数值检查另见新统计目录的WORKBOOK_VERIFICATION和figures说明；QA截图在检查后清理。

已同步docs/README_INDEX、PROJECT_MAP与agent上下文入口，并在四线程状态页登记本次新快照。新增工具均在tools/thesis_main/analysis，测试在tests；生成资料位于两个research目录，不改变真源层级。

## 后续安全接续

先查[接入指南](EXTENSION_GUIDE.md)及remaining_gaps，对具体原作答确认合法空间、对具体参考补足源几何；无需重新审核全部记录。新人员/图片通过现有正式loader和审核后，用归一化manifest登记新批次；新算法独立登记输入、参考与算法版本，在共同可评价集合比较。新增范围或参考必须另起快照。

未运行全库测试、未重新采集或估算时间、未修改路由阈值、未推送。完整重建参考仍依赖原始label_data.zip；本地源路径与迁移要求已明确记录，当前入口不承诺任意新增批次的全链路自动兼容。
