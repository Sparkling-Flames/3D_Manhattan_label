# 独立审查交付

读取REPORT_ZH.md；全部新结果在latest_results。完整离线包是worker_building_review_core_20260909.zip，不是仅有脚本。

解压后安装requirements.txt，执行：

```bash
python code/latest_audit.py --repo evidence_repo --out rerun_results --part all
python code/focused_checks.py --repo evidence_repo --out rerun_results
python -m pytest -q code/test_latest_audit.py
```

实际输入固定c091c3457130d225967e2b62b8e484c9205ab638。离线窗口文件仅保存程序用到的q.95/OSPA与h1/h5投影；所有匹配行保留，原SHA和投影SHA分别记录，不冒充完整原文件。其他输入字节相同。不改原始标注、SOP或已确认规则；不决定论文方向。扩展中文报告、图表和前期旧底座对照另在本轮聊天附件。
