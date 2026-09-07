# 2026-09-08 core logic audit delivery

Read REPORT_ZH.md and LITERATURE.tsv. A=targeted methods/results reading; B=primary abstract/metadata. No claim all 45 papers were fully read. R45 is a preprint.

Plain source is code/logic_audit.py. Offline reproduction after installing the recorded dependencies:

```bash
python code/logic_audit.py --repo evidence_repo --out rerun_results
```

The evidence subset is pinned to a704dd3d07070c3442c05041dee7ed61e91e3fad. No new human observations or neural inference. ZIP and ordinary files are both published. The fuller Chinese report and individual literature cards are also provided in the conversation download package.

A preliminary CI attempt reproduced all audit numbers but omitted preview-test fixtures; this run includes the fixtures and reruns all 16 tests. No test is bypassed.
