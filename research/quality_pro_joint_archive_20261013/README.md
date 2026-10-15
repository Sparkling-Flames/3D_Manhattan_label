# Pro联合质量研究：选择性归档与本地采用边界

2026-10-13。用户授权把Pro有用内容纳入HOHONET。这里保存97份原字节文件，共28,904,426字节；是研究证据归档，不是正式算法发布，也不是完整原包镜像。

**当前解释顺序：用户最新反馈与有效人工裁决 → [全量用途复核](../quality_data_admission_audit_20261013/README.md) → [本地推进方案](../../docs/thesis_main/topics/quality/质量研究推进方案_20261013.md) → 下方Pro历史报告。** 原报告中的“当前推荐”“采用主式”只描述Pro当时的研究选择，不代表HOHONET已经正式采用。所有原文不追改。

## 保留了什么，如何使用

|内容|本地入口|当前采用程度|
|---|---|---|
|完整研究论证、负结果、字段单位|[原报告](source/RESEARCH_REPORT_ZH.md)、[字段定义](source/FIELD_CONTRACT.json)|作为可追溯研究依据；结论须结合新反馈和准入规则|
|三套冻结候选与评分函数|[参数](source/calibration/recommended_parameters.json)、[数值函数](source/calibration/score.py)|可复算研究候选；不替换正式评分，不发布人类等级阈值|
|922条固定参考输入与分项|[输入](source/calibration/inputs/search_inputs.json)、[分项结果](source/calibration/results/selected_components_long.csv)|保留旧数值，来源/资格筛选由当前账本另行实施|
|35图参考登记、429份原始来源/几何和路由|[准备输入](source/routing/inputs/prepared_input.json)、[候选](source/routing/results/reference_candidates.json)、[路由](source/routing/results/routes.json)|可复核的参考材料；旧自动选择不升级为人工真值或人员资格|
|参考变化与公式变化四格比较|[结果](source/integration/results/reference_formula_four_way.csv)|采用这种分开归因的分析方法；原结果仍是旧条件样本|
|结构尾部、局部高度、投影耦合和漏结构反例|[实验报告](source/experiments/REPORT_ZH.md)、[构造几何](source/experiments/results/targeted_constructed_cases.json)、[轴切换](source/experiments/results/axis_switch_counterexample.json)|保留机制证据及失败边界，不把控制实验当新增人工标签|
|原始输入与条件三维的分开记录|[922影响表](source/integration/results/fixed_reference_922.csv)|采用两层输出边界，不自动给原始错误加统一权重|
|143条条件人员及220个融合版本账本|[人员结果](source/integration/results/worker_conditions_new.json)、[融合结果](source/integration/results/fusion_220_ledger_and_scores.csv)、[60个几何](source/integration/results/fusion_geometries_60.json)|保留历史重评分，不认证人员排名；无真实序列不生成k曲线|
|搜索范围、参数弱识别、删组和消融摘要|`source/calibration/results/`|说明为什么不能直接定参数；不重跑21,744配置|

两项值得明确保留的负结论：333份多候选自动路由与最大底面IoU全部一致，未证明局部模块有准确率增益；现有人评下仍有大量可行参数，暂定主式不是唯一确定的人类量表。另有正交漏分支D=0、固定L2最优轴上附加高阶损失不连续的反例，不能靠继续调D权重修复全部结构问题。

## 与当前审查的差异

- 922份内manual589，当前全量manual2344；此归档不取代3152份全量用途账本。
- 原24条等级中有5条semi trap；旧搜索证据未实施新的来源政策。原143条条件人员含manual71、semi72，也不是当前纯manual主校准分母。
- J02是未改坐标的semi trap，用户已撤回旧分差意见；不能继续用它要求增大分差或否定局部备选。J04最新为明显与严重之间；旧T13硬等级不当作未变的新标签。
- T20及P04仍可解释研究问题；当其来源/范围未满足新主池条件时，只作诊断和机制线索，不偷偷转为主校准硬约束。
- 路由可算、参考底面确认、顶面确认、人员资格分别判断；缺顶面不补高度。被排除人员的已审严重作答保留为例外候选，不恢复正式资格。

## 归档边界与复现

[ARCHIVE_MANIFEST.json](ARCHIVE_MANIFEST.json)逐项记录原路径、字节数、本次原字节相等检查及所有未复制文件的理由。`source/`只读解释为冻结外部研究快照；完整原包的说明、脚本和清单继续保留其原语义。

未复制大网格结果、全部中间描述量、重复JSON/CSV表示、原图/复核页面、运行日志和历史baseline/sources整包；它们仍在Downloads原包。原包目录在归档清单中明确记录。**本选择性归档不承诺原`assess.py`或全流程`reproduce.py`可独立运行**，相关原报告链接可能指向未归档成员，应按清单定位原包。归档的实验/路由脚本是方法快照，完整几何重放仍可能依赖旧冻结引擎和原包输入。

本仓库可独立进行冻结指标到分数的复算：

```text
python -B -m pytest -q tests/test_quality_pro_joint_archive_20261013.py
```

本地3项检查通过：922份×4套冻结候选逐值一致（容差1e-9）；主公式另用展开式核对922份；缺顶面必须保留空完整分，零重叠与缺失重叠不能混同。`LOCAL_VERIFICATION.json`保存这次导入核验。本地未重新运行Pro大网格、全部几何控制或浏览器验收；`source/verification/`是Pro的历史验证证据，不冒称本地执行。

新来源/准入工具的`--package`可以指向本目录`source/`，所需的搜索输入及路由结果均已保留；全量准入复核另需原20261012严重筛选归档和仓库现有正式快照，依赖没有凭此消失。

本次同步项目地图、文档索引和当前推进方案；未修改正式合同、原始作答、GT、历史人工回执、融合算法或评分参数。文件保存在本地工作树，未上传远端。
