# 新参考依赖重算：阶段1完成，完整任务未完成

当前已完成71个变化参考与2480份原答依赖登记、全分项重新评分：Manual 2098份、Semi 382份；2445份完整、35份因原始点对缺失不可评分。未将缺失填0，未自动放开资格。ORIGINAL_MEASUREMENTS.jsonl按精确task（含原答点、参考点、版本）校验续跑缓存；ORIGINAL_SCORE_LEDGER.json保留旧排除与新评分。原始冻结库存未改。

已发现自然256中35个受影响池，新增208路径部分保存225660个端点，分布于1025片；这不包括旧48路径和其它团队实验，不能作为全部端点数量。AFFECTED_NATURAL256_POOLS.csv与SHARDS.csv仅登记依赖，尚未重评分团队端点。

剩余：完整绑定/资格与pa4难度接入、其余团队缓存清点与重评分、新空间256与构成分析、依赖训练/选员重拟合、同房/用途及全部新旧结论比较。不得将阶段1作为完整交付或把旧团队分数标为新版本。

验证：tests/test_adopted_reference_rescore_20261028.py通过，检查2480身份唯一、参考点/版本准确、2445完整分项与35缺失状态。原答JSON任务/result沿用scope_quality_scoring字段；新依赖表old_target/new_target/old_exclusions逐条保留，eligibility_status=pending_full_inventory_reconciliation。

原底面采用回执中文已从USER_ORTHOGONAL_REVIEW_20261028.json恢复；采用语义不变。文件均位于既有analysis/tests和多空间研究包，项目地图既有专题入口适用，无新增顶层结构。未启动定时器或额外服务。
