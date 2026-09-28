# 2026-09-21 Pro研究返回接收与本地复核

**先读[独立审查与纳入决定](独立审查与纳入决定.md)。** 原返回有可用证据，但07人员配比模型存在外层隔离问题；项目采用另存修正值，不整体照搬报告。

- `original_package/`：用户下载的原返回完整副本，包括报告、结果、日志、原代码和冻结源ZIP。这里的代码为收到的证据，不作为新维护的正式分析入口。
- `Pro返回原文.txt`：用户粘贴的摘要原件。
- `local_recompute/`：本机新建副本的完整八组重跑、日志与图表；没有复用原逐图重放缓存。冻结源解压及工作副本不纳入Git。
- `audit/`：58文件比较、532项真实小池穷举检查、同栋其他房间对照、修正后的模型预测、不同点数案例的候选原点对应。
- 项目维护的复核入口：`tools/thesis_main/analysis/audit_pro_research_20260921.py`；回归检查：`tests/test_audit_pro_research_20260921.py`。

## 已执行验证

本机Python3.11.7、NumPy1.26.4、pandas2.3.1、SciPy1.11.4、scikit-learn1.2.2、Shapely2.0.4、Matplotlib3.8.0、pytest9.1.1、Node24.18.0。未改全局依赖。Pro环境版本另见原包requirements，不能把本机运行当作其精确环境复现。

源严格校验通过；源4项、返回12项及新增1项测试通过。58份结果中51份在1e-9绝对/相对容差下相符；7份差异已有具体解释，详见审查与机器记录。统计护栏通过：仅探索与审计，不替代正式T1/V1或改变方法合同。未运行无关业务测试；未做新视觉裁决。

## 复核命令

在保留原件的前提下，新建`local_recompute`，复制原包`code/`、`requirements.txt`及`source_snapshot.zip`，然后在该工作副本运行；Windows需UTF-8：

```powershell
$env:PYTHONUTF8='1'
D:/anaconda/python.exe -X utf8 -B code/run_all.py --fresh --jobs 4
```

回到仓库根目录运行项目修正与检查：

```powershell
D:/anaconda/python.exe -X utf8 -B -m tools.thesis_main.analysis.audit_pro_research_20260921
D:/anaconda/python.exe -X utf8 -B -m pytest tests/test_audit_pro_research_20260921.py -q
```

新作者代码只进入`tools/thesis_main/analysis/`；收到的原代码保留证据身份。文档索引和项目地图仅增加本入口，不提升为正式协议。原导出和其他进行中的仪表盘/采集工作不修改。本轮未提交或推送云端。
