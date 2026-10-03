# 全10图来源重复与四人共识风险分解

本补充包只读使用固定提交405f3041fdd76977f625d50c558c63dbf342699d的匿名B线输入，不修改原仓库、资格、分组规则或坐标。输入文件在inputs/；analyze.py独立实现几何细分、整数超几何概率和全四人组合交叉检验，不导入原实现。

## 复现

Python 3.12，安装requirements.txt后执行：

    python analyze.py
    python test_analysis.py
    python make_report.py

默认从本包inputs/读取，不需要网络。输出写入results/。提供--source路径可使用另一份同契约输入，但报告结论仅对应input_manifest.json记录的固定源字节。请保留原输入及清单以核验，不把替换输入后的输出当成本冻结源结果。

报告：REPORT_zh.md。全部数值：results/risk_decomposition_all10.csv；每图276个人员对检查：results/geometry_all_pairs.csv；P002/P012的逐图检查：results/P002_P012_all10.csv。

本包不会检索原始私密身份、原始评论或从上游重新生成预处理坐标。source_binding.json为来源文件里的声明；本包只核对当前输入与该清单的记录对应，不把声明升级为原始生成过程独立性证明。
