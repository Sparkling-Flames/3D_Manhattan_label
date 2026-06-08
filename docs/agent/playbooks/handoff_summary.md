# 交付摘要

## 触发条件（Trigger）

- 每次 Codex 完成较大改动
- 任何触及 protocol docs、agent context、脚本、测试、schema 或正式索引的改动

## 必须检查（Required checks）

- 运行 `git status --short`。
- 列出 changed files。
- 说明 unchanged protocol boundaries。
- 汇总 verification commands and results。
- 说明 tests not run and why。
- 说明 project map / README sync decision。

## 禁止事项（Forbidden actions）

- 不省略跳过测试的原因。
- 不隐藏 protocol、schema 或 CE-only 风险。
- 未运行测试时，不声称测试通过。

## 预期交付（Expected handoff）

- Changed files。
- What was intentionally not changed。
- Protocol guard result。
- 相关时给出 Label Studio CE guard result。
- Verification。
- Map / README sync result。
- Remaining risks。
- Next safe task。
