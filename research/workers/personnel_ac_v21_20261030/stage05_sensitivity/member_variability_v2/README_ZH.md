# 成员变化的最终有效分母

研究“成员波动”时至少要有两个该指标的有效观察。此目录是成员跨度、标准差、正负翻转比例的最终统计入口。

`MEMBER_VARIABILITY_VALID_GE2_SUMMARY.csv.gz` 对每种指标分别要求 `metric__valid >= 2`，之后先池内平均、再同图平均、再图等权；同时保留楼等权、低尾、图楼支持与实际有效面板数。固定 D 与类别配比相同但 D 成员不固定两个 panel_kind 分开。

原 `results_v1/MEMBER_PANELS.csv.gz` 完整保留，单个有效值的描述性 max−min 数学上为0；本目录不将这种0用于推断稳定性。`SINGLE_VALID_VALUE_EXCLUDED_FROM_VARIABILITY.csv.gz` 精确列出从可变性推断中排除的单值条目。旧均值、Q、几何、状态、事件身份和团队均没有改变。

全体28,751个面板中952个只有一个物理对，首先不进入可变性估计；其余27,799个面板再逐指标检查有效观察数。其中Q跨度有155个单有效值面板，固定D的Q面板没有这种情况。记录劳动沿用严格同源有效口径，不能用一个合法劳动对推断劳动波动为0。

注意 class_count_preserving 面板ID是条件描述散列，跨图可重复，完整主键为 `(pool_id,panel_id)`。输入与排除记录、完整CSV/GZIP可读性及哈希见 `MEMBER_VARIABILITY_DENOMINATOR_RECEIPT.json`。

完整总汇v1/v2的成员均值仍可使用；成员跨度/SD/翻转的正文请引用本目录。背景差分、固定A、固定XZ、三段分解和两批稳定性不受这项可变性分母修正影响。
