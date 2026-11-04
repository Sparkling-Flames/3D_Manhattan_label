# v2.1 次级消费者独立验收

结论、数据与边界见 [REPORT_ZH.md](REPORT_ZH.md)。逐条判定见 [CONCLUSIONS.csv](CONCLUSIONS.csv)，实际消费者见 [CONSUMER_ACCEPTANCE.csv](CONSUMER_ACCEPTANCE.csv)。

- `CHECKS.csv` / `CHECKS.json`：独立数值、支持、计权、版本与原共同支持核查。
- `SAME_ROOM_*`：六端分母、全部分项重派生及保存 CSV 的无损读取证据。
- `COMPOSITION_*` / `ALLIANCE_*`：固定标签/成员、有限面板、池内排名和分层方差。
- `NATURAL_*` / `POLICY_*`：现有路径频数、固定 k、真实汇总消费者与原重抽区间核对。
- `CANDIDATE_*`：F2/F9 候选四个坐标编辑与主分支隔离。
- `repairs/`：8 格成员字段格式修正、三个覆盖路径、前后哈希和精确修正前副本。
- `source/`：冻结 GitHub 原始源文件与来源说明；为离线复现保留。
- `REPRODUCE_INPUTS.csv`：脚本实际读取路径与 SHA-256。需要前五批结果及本补充覆盖层。

运行：`python -m tools.thesis_main.analysis.audit_manual_order_secondary_acceptance_20261104`。本补充不选新队、不重新排序、不重新融合或评分，不进行分类选型。
