# 全景layout质量研究独立审核与复现

先读独立审核结论.md。审核针对2026-10-01 20:07 UTC返回包，以及固定提交bba3dc7c9a79b8342ecb4ce2487affe41886eb56下research/pro_quality_handoff_20261002。日期按悉尼为2026-10-02。

## 内容

- original_return.zip：收到的原始返回包，未修改
- fixed_handoff：固定提交的42文件有限交接，保留原始文件与清单
- handoff_verification：来源差异和全量复算证据；官方失败日志保留
- return_reproduction：返回包隔离复跑和独立方程检查
- validity：新增合成效度反例、脚本与结果
- research_design：完整研究判断、可实施盲评方案及统计设计示例

不含全库3152份加载链、不含原照片、不含真实人员身份表。不宣称已经执行人工实验。

## 环境

Python 3.12.14，NumPy 2.3.5，SciPy 1.17.0，Shapely 2.1.2，pandas 2.2.3，Matplotlib 3.10.8；测试另需pytest。可在隔离虚拟环境安装所需依赖。原交接requirements保留，不承诺其他版本严格逐位一致。

## 执行

在本包根目录运行：

```sh
(cd fixed_handoff && python -B -m pytest tests -q -p no:cacheprovider -W error::RuntimeWarning)
(cd fixed_handoff && python -B verify.py)
python -B handoff_verification/collect_full_recompute_diffs.py --root fixed_handoff --out fresh_handoff_diagnostics
```

本次10测试通过。原样verify.py失败于方向轴角极小浮点差；不能把独立诊断收集器继续执行的结果说成原验证器通过。收集器不修改原源码，替换进程内比较回调用于完整收集差异。所有超原容差差异在direction系列；详见报告与JSON。若未来环境有不同差异，应重新解释而非自动忽略。

返回包检查：先把original_return.zip解压到新的目录returned，确认实际根目录后执行：

```sh
python -B return_reproduction/portable_reproduce.py --source returned/layout_quality_audit_20261002 --out fresh_return_reproduction
python -B return_reproduction/independent_checks.py --package returned/layout_quality_audit_20261002 --out fresh_independent
python -B validity/independent_checks.py
```

新输出目录需不存在。前两个脚本参数化路径，详细说明见return_reproduction/README_复跑.md。效度脚本在validity内写JSON，若要保存本包原结果，先复制validity目录再执行。

## 证据解释

253可算参考行不等于253独立人员样本；390是双参考版本行数；195是作答数；本面板26匿名人员/12图。上轮74参数设置、仓库17改序、新返回17控制及本审核8组新合成检查是不同实验，不能相加为真人样本。

只读审查已完成范围包括固定嵌入输入及来源摘录绑定。完整上游源表绑定、实际图像语义和外部效度仍需另外验证。未来执行人审须保持现有资格和参考政策。

来源绑定复查：

```sh
python -B handoff_verification/check_return_source_binding.py --root fixed_handoff --returned returned/layout_quality_audit_20261002 --out fresh_binding
```
