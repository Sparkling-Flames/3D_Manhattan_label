# 本次交付核验（2026-10-01）

本轮完成当前坐标来源合同收尾，以及74个合成对照、12张真实图片/24条参考版本记录的小实验。当前任务变更包括：

- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`及生成MD：按已确认来源区分C/P、尺寸转换及栅格采样，不新增schema。
- `tools/thesis_main/analysis/layout_metric_response_20261001.py`及对应pytest：复用已有重建、BEV和墙带核，补幅度扫描、固定证据选样、失败/缺版本记录及图表。
- `layout_metric_probe_20260926.polygon_metrics`：默认512采样保持，增加可选样本数及双向均值/步长，用于8192样本的细节复核。新增字段见本目录field_contract；历史工件未重生成。
- `layout_foundation_20260930.py`的来源解释、阶段1说明、研究方向：纠正同值C/P敏感性解释，更新阶段进度。
- `docs/README_INDEX.md`及`docs/PROJECT_MAP_CLEAN_20260308.md`：短条目登记本目录和新工具，测试为支撑文件，未升格为规范。

本轮开始前已有的geometry/viewer/公开范围等本地差异保留，没有回滚、提交或发布。

## 验证

```powershell
python -B -m pytest tests/test_layout_metric_response_20261001.py tests/test_consensus_contract_20260923.py tests/test_layout_metric_probe_20260926.py tests/test_research_round_20260929.py tests/test_layout_foundation_20260930.py -q -p no:cacheprovider -W error::RuntimeWarning
python -B -m tools.thesis_main.analysis.render_paper_a_method_contract --check
git diff --check
```

相关pytest **34项通过**。先用失败测试明确C/P等价、身份未匹配及近地平线失败边界，随后实现；补验证固定轴残差、有限采样上界、评论候选不升级、真实未对应与CSV字段合同。合同渲染及diff检查通过。

完整实验命令见REPORT.md，已成功生成74/12/24。74为5等价+19范围+14细节+36定位的参数化对照，不是74独立样本；24行为15条有参考比较与9条人工参考缺失记录。另将全部24条结果逐项绑定到同一最终manifest：点数组、原点对身份和两个gate精确一致；原始GT环确认状态仍为false；两个CSV表头等于字段合同、行数等于机器结果；失败IoU为null且有原因。阶段2报告及相关文档本地引用已检查，四张幅度图已目视检查。

交接解释补充不重跑数值：near_three_pairs同时改变两端共线路径的点数、尖凸几何和角度，不代表真实正交2对/3对完整规律，更未验证局部整体投票。0.5px的floor RMSE在4个对应底点上汇总，只有SE被扰动，单点SE位移为其2倍；near_horizon为更大房间，不是同房人员能力比较。真实Manhattan缺省是本轮共同轴未定义的设计边界，而非无GT/无共同轴就无法各自拟合最佳轴计算自洽残差；各自残差不代替跨layout距离。

本轮没有屏幕截图；交付PNG是科学结果图，不作临时截图清理。测试临时目录由pytest管理，无新浏览器包或下载缓存。

## 边界与后续

只修改当前坐标解释，没有修改历史v23、原始导出、配对、原环、清洗/资格、GT裁决、active-time、SOP纳入语义或历史数值。原始/人工GT版本分别报告，不以较近版本取代另一版本；真实面板不计算对应点RMSE或拟合共同轴，不做人员汇总分数。非水平墙顶只用声明列式代理，不构造真实屋顶/封闭体积。

未运行全仓库、历史研究、共识、训练或LS运营测试：本轮只新增受控指标编排及来源解释，不启用这些链路；已运行所复用的几何/研究/合同相关测试。浏览器代码本任务未再修改，沿用前一任务已通过的两组WebGL核验。

剩余限制：真实ERP采样和逐图重力调平缺批次记录；原生模型至LS半像素适配与训练重复缩小仍是已报告缺陷，使用相应链路前须修复。边界最大值是有限采样值，不称精确Hausdorff；真实12图为定向描述面板，不推断总体发生率或方法优劣。

下一步安全任务是审阅本报告的响应与盲点，再为细节对应/分簇、工人融合、合理候选各自制定独立评价；总分、阈值和权重仍不冻结。
