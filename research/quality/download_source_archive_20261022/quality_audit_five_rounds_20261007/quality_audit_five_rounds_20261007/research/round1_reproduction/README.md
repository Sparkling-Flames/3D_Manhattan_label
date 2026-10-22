# 第一轮数值复现：代码与证据

中文结论见 REPORT_ZH.md。此目录是对现有研究输入的计算复核，不是新的人工真值认证。

## 文件

- audit.py：输入绑定、官方产出比较、独立数值核、独立LOBO优化
- diagnostics.py：纯细分密度反例、NA来源、API反例
- optional_api_patch/：未应用到源包的可选最小补丁及11项测试
- official/、official.log：已完成的官方数值复算
- 其余JSON/CSV/log：本轮实际运行的逐项证据

## 路径与依赖

需要Python及原包requirements.txt中的依赖。先解压原研究包与expanded输入到任意目录。源包中应有src/evaluator.py，expanded中应有current/panel.json。无需把数据放进本次审计机器的路径。

三个参数与对应环境变量：

- --source / QUALITY_AUDIT_SOURCE：解压后的quality_deep_20261007目录
- --expanded / QUALITY_AUDIT_EXPANDED：解压后的expanded输入目录
- --official-output / QUALITY_AUDIT_OFFICIAL_OUTPUT：已有官方复算产出目录

命令行优先于环境变量。未设置时，默认沿此交付原目录结构使用相对位置。输出保存在脚本所在目录，不覆盖源包。

## 完整运行

在此目录执行，将示例路径替换为实际路径：

```bash
export QUALITY_AUDIT_SOURCE="/path/to/quality_deep_20261007"
export QUALITY_AUDIT_EXPANDED="/path/to/expanded_input"
export QUALITY_AUDIT_OFFICIAL_OUTPUT="/path/to/new_official_output"
# 官方入口要求输出目录尚未存在；若已有复算结果，跳过此行
python "$QUALITY_AUDIT_SOURCE/reproduce.py" --out "$QUALITY_AUDIT_OFFICIAL_OUTPUT" --no-figures
python audit.py > audit.log 2>&1
python diagnostics.py > diagnostics.log 2>&1
```

也可显式传路径：

```bash
python audit.py --source "$QUALITY_AUDIT_SOURCE" --expanded "$QUALITY_AUDIT_EXPANDED" --official-output "$QUALITY_AUDIT_OFFICIAL_OUTPUT"
```

## 分项或轻量检查

```bash
python audit.py --checks binding
python audit.py --checks comparison
python audit.py --checks geometry predictor
python diagnostics.py --checks api
python diagnostics.py --checks density na
python optional_api_patch/make_patch.py --source "$QUALITY_AUDIT_SOURCE"
python optional_api_patch/test_patch.py --source "$QUALITY_AUDIT_SOURCE"
```

所有命令均读取相同环境变量；--help列出参数。补丁工具仅需--source。

可移植整理后实际执行了显式路径的binding/API轻量检查及11项补丁测试，全部通过；没有重新运行全套研究。日志：portability_binding_check.log、portability_api_check.log、optional_api_patch/tests.log。
