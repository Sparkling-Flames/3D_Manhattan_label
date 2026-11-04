# 第06批：Q-only 同等人工处理机会与独立数值验收

结论：固定208事件、五政策臂、670去重团队范围内，29/29无连接引用对应的21/21团队全部处理并可评；没有遗漏需补排序或重评分。3条剩余失败为节点不足。

阅读入口：`research/fusion/manual_order_acceptance_20261104/q_only/REPORT_ZH.md`。
独立复审：`research/fusion/manual_order_acceptance_20261104/source_version/PEER_REVIEW_QONLY_ZH.md`。

## 使用与批次关系

保留并按顺序应用此前第01—05批。将本zip内相对路径解压到 `D:/Work/HOHONET`；本批增加新验收目录和脚本。第05批对第02批回执计数的修正应继续生效。

本批交付Q-only完整验收；AC全部翻向、同房/配比/联盟/人数/旧策略的定向验收与文档研究台总接续由第07批提供。

## 已完成的补充

- 从原始全部1040条链接和670端点独立核对机会；20/7七个不同选员事件的35条全臂全部检查。
- 独立重建832个比较、380条汇总与原建筑簇区间，227项核对通过。
- 第二位审查者用有理数自顶向下权重核对88条分解和5412条事件贡献，最大差3.55e-15。
- 旧Q缺失保留缺失；20/7新图的两个事件各占全局1/108，明确新增贡献和旧支持重权。
- 原自动及第05批辅助科学数值保持，新增团队/排序/融合评分均为0。

## 复现

```bash
python tools/thesis_main/analysis/audit_manual_order_qonly_fairness_20261104.py
python research/fusion/manual_order_acceptance_20261104/source_version/audit_version_and_design.py --restored-root .
python research/fusion/manual_order_acceptance_20261104/source_version/peer_review_qonly_acceptance.py --restored-root .
```

实际源文件、版本与hash见包内 `MANIFEST_BATCH06.json`、输入快照及来源审查清单。此包为定向辅助结果的验收，不将57组外推为全库无环修复率。
