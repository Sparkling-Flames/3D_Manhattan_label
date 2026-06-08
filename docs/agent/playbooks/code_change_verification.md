# 代码变更验证

## 触发条件（Trigger）

- 修改 `tools/`
- 修改 `tests/`
- 改变脚本行为、schema、manifest、CSV 字段或输出合同

## 必须检查（Required checks）

- 先运行 `git status --short`。
- 找到最小相关测试文件。
- 运行相关 pytest 命令。
- 若输出字段或 schema 改变，更新或补充测试/字段合同。
- 汇总命令结果和未运行检查的原因。

## 禁止事项（Forbidden actions）

- 不在没有验证计划时修改代码。
- 不静默忽略 schema drift、missing fields 或 active-log source mismatch。
- 不把 `analysis_results/` 当作输入真源。
- 不扩大到无关重构。

## 预期交付（Expected handoff）

- 代码/测试改动。
- 运行的测试及结果。
- 未运行的测试及原因。
- schema / manifest 影响。
- 剩余风险。
