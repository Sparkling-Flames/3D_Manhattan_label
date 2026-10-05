# 有限路径证据审核最小包

先读 REPORT_ZH.md。核心：原 E0/E1 条件包含性正确；没有一般一错唯一恢复保证；给定假设成立时，多候选仍可作局部一致决定；错误超预算、域遗漏或硬约束错定会破坏真值覆盖。

Python 3.10+，仅标准库：

    python -B independent_audit.py --out NEW_results
    python -B -m unittest discover -s . -p 'test_*.py' -v
    python -B verify_reproduction.py

默认独立从 inputs 重新构造，不需要原研究包，不导入原代码，也不需 Shapely/NumPy。可选 --source 指向原研究目录，只作只读对照。

原包对照成功记录在 results/delivered_comparison.json。其它确定性结果均可由 verify_reproduction.py 在新临时目录逐字节复现。

5040 是 70×(1干净+7单翻+7单缺失+21双翻)×2预算，不是独立人群样本数。全部指定有限情形已枚举完毕；未扩展调参或改真实数据。
