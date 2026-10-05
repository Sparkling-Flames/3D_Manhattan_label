# 局部路径有限域独立研究包

先读 REPORT_ZH.md / REPORT_ZH.html；EVIDENCE_VIEWER_ZH.html 可离线浏览完整候选、失败和政策返回。

最小环境：Python 3.10+、NumPy、SciPy、Shapely；测试需pytest。本包不包含真实原图或真实GT。

```bash
python -m pip install -r requirements.txt
python -m pytest tests -q
python reproduce.py --out NEW_results
```

已包含最终结果 results/final。reproduce.py 在新目录依次执行有限域构造、真值评价、冲突/识别诊断、两例真实连续回投和原51次单点回投。构造代码不读取 evaluation/synthetic_truth.json。

输入：
- inputs/domain.json：给定锚点、16条带来源路径、7名合成人员原赋值与相容关系。
- inputs/policies.json、PLAN.json：冻结政策、预算和证明范围。
- inputs/probes.json、evidence_streams.json：冻结的几何探针与缺失/冲突/误判控制；不是自动图像核验。
- inputs/rPc6DW4iMge-06.json、uNb9QFRL6hY-67.json：真实完整匿名名单，39作答/24不同worker ID。
- evaluation/synthetic_truth.json：四个评价真值世界，不用于构造。

结果：
- results/final/finite/all_candidates.json：324完整赋值，包括非法、不相容、待核。
- candidate_ledger.csv：简明失败和几何账本。
- policy_outputs_before_truth.json：所有政策候选集及排除依据。
- candidate_truth_evaluation.csv、policy_evaluation.csv、event_decisions.csv：逐候选/集合/局部事件的评价。
- search_equivalence.json：同域加法与域删减的完整比较及初始化计数。
- minimal_conflict_cores.json、probe_identification.json、evidence_identifiability.json：无GT候选诊断和穷举检查。
- outside_candidate_domain_control.json：独立域不完备评价反例。
- results/final/real/real_diagnostics.json：两处真实记录的同经度/连续局部投影诊断。
- results/final/upstream_projection/results.json：原入口51次操作重算。

没有运行有限预算搜索优劣实验；没有称完整候选为真实房间或人群票；没有真实删除结论。UPSTREAM_ACCESS.json列出新ZIP未挂载、原图缺失等材料范围。logs记录测试、重放和开发问题。
