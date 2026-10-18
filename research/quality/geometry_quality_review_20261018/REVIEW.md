# 几何质量 Pro 与 dot 补算的独立核验

日期：2026-10-18。核查对象是本目录 `received/pro/` 与 `received/dot/`，不是人员 Pro。仅新增核验副本与本报告，未改现用评分、参考、资格或人员分类。

## 判断

**同意暂时保留 B8L2 主工作指数、D10 敏感性，不把 EBC2.1 或 RBC-F8 整体替换进去；这项采用判断不算过于保守。但不能据此停止结构质量研究，或宣布 B8L2 已优于所有替代模型。**

现有证据足以推翻“竞争模型已普遍改善现有人类判断”的说法，也证明它们尚未解决结构误差的稀释；不足以估计三种模型在人类总体偏好上的准确率，更不足以证明所有边界对应方法都不值得继续研究。均值提高、某几个控制分数降低、难度均值更单调都不是模型正确性的证明。

N1 是有明确反例和真实数据回归支撑的数值修复，值得单独进入下一评分实现版；应保留冻结旧版，并对实际调用路径和诊断字段做适配。它不修复结构对应，不改变 0.8/0.25 高度尺度，也不提供锯齿免疫性。

## 已实际执行的检查

|检查|本轮执行结果|
|---|---|
|原件与仓库接收副本|Pro 150 文件、dot 36 文件逐文件字节相同；共 186 文件|
|原包完整复现|未改 `reproduce.py`，在新目录执行全部 7 阶段，约 133 秒；20 项测试通过|
|2710 份重算|1848 合格＋862 诊断，五项主分全部有限、状态完整；ID 全集及唯一性通过；相对原包最大差 8.53×10⁻¹⁴|
|库存与资格|3222 库存及 1911 合格集合与当前规范一一对应；图片、人员、条件、参考 ID/版本、用途无差异；不合格者主分仍为空|
|63 份补算重放|63 个 ID 恰等于 Pro 缺失的合格集合；五项主分与 dot 保存结果最大差 5.69×10⁻¹⁴|
|来源几何|原 1848 份的 3696 组答案/参考点数组、恢复 64 份的 128 组数组，与当前 `data.json` 和参考目录逐点相同；重建三维最大差 1.34×10⁻¹⁵|
|64 份恢复绑定|核验周期共享横坐标、点对、完整排列、人工确认环序及 binding，全部通过|
|N1 回归|同一运行环境下，全部 1911 份合格分数严格不变；863 份诊断对象的 B8/D10 最大变化分别 3.41×10⁻¹³、3.45×10⁻¹³|
|表达变换|1848×4＝7392 次环序起点、反向、完整三维冗余点、共同旋转检查完成；EBC2.1 最大差 8.53×10⁻¹⁴|
|原评论绑定|P01 原 manifest、审核结果、历史页面几何及当前规范对应；24 例旧 B8 展示值均与当前同对象同参考重算值四舍五入一致|
|验证器误报|在隔离副本将 891 行来源缩为 1 行、另一来源全部改成不存在的 ID、第三来源分数改为 NaN，Pro `verify_saved.py` 仍返回成功；漏洞确认|

本机使用现有 Python 3.11.7、NumPy 1.26.4、Pandas 2.3.1、SciPy 1.11.4、Shapely 2.0.4、pytest 9.1.1，没有安装包要求的固定版本。因此跨环境结果应写“在 1e-8 容差内复现”，不能照抄原报告的“最大差严格为 0”。N1 的同环境比较与跨环境末位差已经分开记录。

## 全部 1911 份的结果

完整合格面板含 136 图、21 建筑、25 个人员身份，其中普通 1699、门洞 188、其它条件 24 份。这里统计的是固定身份，不是重新认证人员质量。

|模型|逐份平均分|
|---|---:|
|B8L2|67.48093|
|D10|68.92547|
|EBC2.1-L2|74.85892|
|RBC-F8-L2|69.97530|

独立用保存分量重写 B8/D10 的标量公式，最大差 4.27×10⁻¹⁴。D10 在原 1848 面板为 397/15045 对排序翻转（2.639%）；补齐 1911 后为 406/15483（2.622%）。这些同图同条件同参考作答对大量共享记录，不能视为独立样本，也不代表准确率。

Pro 原包仍有“缺 63 份”的历史事实；**当前审查已经补齐并重放全部 1911 份，不需要等未来 v2 补标**。完整独立重算表是 [qualified1911_independent.csv](verification/qualified1911_independent.csv)。

## 竞争模型的得失是否支持当前采用判断

控制实验重放支持以下事实：

- 小凸起遗漏：B8 99.03、EBC2.1 97.07。新模型对这个小结构更敏感，但两分之差本身没有人工标定意义。
- 深凹槽删除：B8 65.76、EBC2.1 84.65、RBC-F8 64.87。移除球面底边项确实损失了该控制的重要响应；RBC 保留该信息后恢复响应。这支持保留相关信息，不证明当前权重就是最佳权重。
- P01：原记录明确“整体 A 略好”；B8 A/B＝57.38/49.19，EBC2.1＝57.12/71.16，RBC＝55.04/67.43。核验了对象、图片、参考、原页面几何，没有发现错绑。P01 已提前暴露分数，故是开发一致性反例，不是盲审验证。K07 的 57.38 仅为另一对象恰好四舍五入同分，不存在已查明的错行。
- K09/K10/K11 原评论指出简化、遗漏和歪连，但没有给出三者明确成对排序；新模型排序反转不能自动计为成功，也不能自动计为失败。
- 锯齿控制：不修复主要缺失，只给较正确墙段添加 400 组细锯齿，IoU 0.7500→0.7453；B8 48.81→51.88、D10 48.81→53.94、EBC 66.02→72.34、RBC 47.17→56.24。加密积分后仍存在。B8 也失败，不能用这个反例单独宣布 B8 比其它模型更正确；它说明四种分数均存在边长支持被放大的局限。

这 242 条控制含 209 个不同几何对；58 条裁切控制来自 6 个实际裁切参考；粗化控制来自 2 份真实作答、14 组修改。重复控制与衍生变体都不是新增真人证据。805 顶点的锯齿例属于压力测试，没有证据表明真实人员这样作答。

后续可直接推进“同范围、不同必要结构遗漏及局部歪连”的小规模候选诊断，保留 B8/D10 与独立结构描述并列。先要求候选方法在关键结构、真实等距、高度与表达稳定性上讲清得失，再对现有评论无法决定的少量冲突对提出人工判断；无需现在重新组织大批同类看图。

## N1 的具体边界与迁移条件

旧规则用平方距离差与 O(eps×L²) 比较，最近距离接近零时会把相隔 O(sqrt(eps)×L) 的墙误认为等距。N1 在距离单位比较 `sqrt(d2)`，容差为 `64*eps*max(perimeter_A, perimeter_G)`，保留最近底边、4096 采样、真正等距取最大残差及评分参数。窄槽自比旧 B8 约 17.25/17.23，修复恢复 100；真正等距的高度歧义仍保留。

周长尺度对环序、刚体旋转和真实共线细分不变，但不对改变几何的锯齿保持不变。它仍是浮点量级的误差预算，不是几何免罚区，也不是对任意巨大周长或极端输入的完整数值证明。该局限不能与已存在的周长平均稀释问题混同，更不能以 N1 宣称结构问题解决。

原补丁另将诊断键 `arithmetic_tie_tolerance_h2` 改为 `arithmetic_tie_distance_tolerance_h`，单位由平方距离变为距离。这属于接口/字段变更，生产迁移不能仅复制文件然后沿用旧字段解释。本轮保留 [NUMERIC_PATCH.diff](received/pro/NUMERIC_PATCH.diff) 为可审查补丁，不覆盖冻结引擎。

## 验证器缺陷与证据入口

Pro 验证器把缺失 ID 通过内连接丢掉，并在比较前剔除 NaN 差值；“超容差数量为 0”可以在有效比较数量为 0 时通过。这个缺陷真实存在，但不能据此推翻已做严格全集、有限值、来源几何核验且成功重算的本次数据。

未来导入门至少需要：规定对象全集、唯一 ID、相同参考与资格、明确缺失集合、有效行数、每个要求分项的有限值及数值容差；不能只检查保存的成功 receipt。dot 严格脚本明确针对本次 1848+63 合同，不宜原封不动当作任意版本验证器。

- [原包完整复现收据](verification/pro_reproduction/REPRODUCTION.json) / [20 项测试日志](verification/pro_reproduction/logs/step_07.log)
- [严格全集与数值核验](verification/strict_canonical_and_recovery.json) / [全量复跑严格检查](verification/strict_full_reproduction.json)
- [当前来源坐标与绑定](verification/current_source_coordinate_binding_parity.json)
- [P01 及 24 例绑定检查](verification/human_review_binding_check.json)
- [隔离误报实验](verification/verifier_mutation_probe.json)
- [64 份 N1 同环境比较](verification/n1_recovered64_same_environment.json)
- [186 文件归档字节核对](verification/received_byte_parity.json)
- 可执行入口：[Pro reproduce.py](received/pro/reproduce.py)、[63 份重放](received/dot/recovered_v1/replay_recovered.py)、[64 份 N1 重放](received/dot/recovered_v1/replay_n1.py)、[dot 严格规范核对](received/dot/verify_canonical.py)。

复现时输出目录须不存在，且在接收包之外。PowerShell 先设置 `PYTHONUTF8=1` 和 `PYTHONDONTWRITEBYTECODE=1`，然后可运行：

```powershell
python research/quality/geometry_quality_review_20261018/received/pro/reproduce.py --out research/quality/geometry_quality_review_20261018/verification/new_pro_run
python research/quality/geometry_quality_review_20261018/received/dot/recovered_v1/replay_recovered.py --pro-package research/quality/geometry_quality_review_20261018/received/pro --out research/quality/geometry_quality_review_20261018/verification/new_recovered63_run
python research/quality/geometry_quality_review_20261018/received/dot/recovered_v1/replay_n1.py --pro-package research/quality/geometry_quality_review_20261018/received/pro --out research/quality/geometry_quality_review_20261018/verification/new_n1_run
```

本轮未逐张重看 24 例原图，未开展新增盲评，未从全部原始 Label Studio 导出重建完整多表加载器；未对未知极端几何证明 N1 普遍正确。未截图、未安装依赖、未改默认评分，也未将诊断分回填人员分类。
