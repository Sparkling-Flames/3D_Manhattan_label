# 可选诊断补丁：避免无有效参考时误报可比较

这是独立补丁提案，不是本轮质量研究的主要成果；未应用到返回的研究源文件，也不改变已复现的任何数值指标。

## 最小变更

1. 为 footprint-only 成功区域比较补充 reference_status=ok，和完整布局的区域状态保持一致。
2. 每个参考结果新增 spatial_reference_cost_comparable_with_same_context。只有原有目标/参考可用/无已知要求冲突条件成立，且该参考的范围比较成功、IoU与标准化质心数值有限，才为true。
3. 原全局布尔值只在参考列表非空且所有提供参考均满足上述条件时为true。混合可算/不可算参考不会掩盖局部可用结果，可读每个参考的标志。

此标志只表示空间参考分项的数值与已提供上下文可比较，不认证上界、三维量、语义细节或整体质量。仍使用调用者提供的全局context；本补丁没有解决多个参考版本之间目标或可用性可能不同的问题。未来如需参考级语义context，应另行设计，不能由此次数值防护推断。

## 文件

- evaluator_optional.patch：针对 src/evaluator.py 的可读统一diff
- evaluator_proposed.py：独立可运行实现副本
- make_patch.py：从原文件生成副本与diff，绝不写回源文件
- test_patch.py：反例及回归测试
- test_results.json、tests.log：实际执行结果

## 测试

实际执行11项测试并通过，包括：底点地平线导致不可算、空参考、坏参考、混合参考、正常完整布局、未知上下文、已接受不同目标、明确必要细节冲突、footprint-only、四份真实案例数值回归、源文件SHA保持不变。

现有正常完整布局和四份真实案例的所有既有返回值完全保持，除新增逐参考标志；footprint-only另新增成功状态标签。计算函数本身未修改。

```bash
python make_patch.py --source "/path/to/quality_deep_20261007"
python test_patch.py --source "/path/to/quality_deep_20261007"
```

两个脚本也可通过QUALITY_AUDIT_SOURCE环境变量指定源包；默认仅使用相对目录，不包含机器专属绝对路径。
