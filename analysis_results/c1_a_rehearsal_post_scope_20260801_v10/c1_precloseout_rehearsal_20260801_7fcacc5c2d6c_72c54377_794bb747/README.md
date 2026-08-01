# C1-A 云端分析数据包

这是 C1-A `v10` 的 **pre-closeout rehearsal** 派生分析包，供云端 AI 复核和分析；它不是原始数据归档，也不是 C1 正式 freeze。

## 已纳入的事实

- C1 三个 cohort：A anchor、B Core、C semi；B Core 共 75 张，67 张 `in_scope`、8 张 `oos`。
- B Core 的最终 OOS 为 `B-008`、`B-019`、`B-029`、`B-030`、`B-037`、`B-049`、`B-061`、`B-063`。
- 结构异常、任务外提交、scope 和几何修复都保留审计字段；修复仅用于派生几何分析，原始几何与处置证据未被改写。
- primary annotation-level active time 因无法精确绑定到 annotation 而为 `unavailable`；不得以其他时长替代。
- C1 collection 仍未作正式 freeze/audit/finalize，C2-B 与 C1-A-RP 均未启动。

## 本包内容

提交的是 final scope、runtime mapping、row eligibility、canonical geometry、GT/peer/LOO 派生质量结果、worker state、结构/任务外/几何修复审计及 closeout 摘要。每个 CSV/JSON 均可由同目录的 `rehearsal_summary.json` 和 `c1_final_canonical_closeout_summary.json` 交叉定位。

## 明确不上传

- Label Studio 原始导出、原始 active-time 日志、导入 JSON、原图和 `raw_snapshots/`；
- 工作区 patch、运行期 manifests 及其他可复现但不适合云端默认保存的中间文件。

使用本包时，应把这些结果视为审计充分的 rehearsal 结果，而非后续 C2-B 的授权或替代输入真源。
