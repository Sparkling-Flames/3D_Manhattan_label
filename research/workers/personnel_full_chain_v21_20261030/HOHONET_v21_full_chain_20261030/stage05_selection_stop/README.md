# v2.1选队、停止人数与历史取得成本

本模块已完成实际重算。主入口：[中文报告](REPORT_ZH.md)。冻结仓库13a7861334749805a86dc19e9ea79fcaa71020c0；保留原v2面板、候选、顺序、规则和历史身份。

## 阅读顺序

1. `FROZEN_DOWNSTREAM_DESIGN.json`：参数、范围、历史信息可用性与成本合同。
2. `selection/MAIN_N5_HEADLINES.csv`与`MAIN_N5_DIRECTION_COUNTS.csv`：当前选队均值、低尾、劳动与图/楼方向；原层及无待定主层分列。
3. `stopping/MAIN_RULE_HEADLINES.csv`与`MAIN_COLD_COST_HEADLINES.csv`：已有历史停止及冷启动完整成本。
4. `V2_TO_V21_CLOSEOUT.csv`：写作/总报告用的研究链对照。
5. `validation/NUMERIC_RECONSTRUCTION_CHECKS.json`：原选队汇总和原停止前缀重建验证。
6. `FILE_READABILITY.csv`：所有输入/结果完整读取清单。

## 结果可追溯链

选队：`design/SELECTION_DESIGN.csv.gz` → `team_key` → `endpoints/pools/<pool_id>.jsonl.gz` → `selection/POLICY_EVENT_RESULTS.csv.gz` → `POLICY_IMAGE_RESULTS`/`POLICY_BUILDING_RESULTS`/`POLICY_SUMMARY`。关联时保留version、domain、源/目标池与n；同队重复出现在源上下文中不当独立图证据。

停止：保留`inputs/research/same_room/same_room_multiview_20261020/{REPLAY_GROUPS,REPLAY_ORDERS,REPLAY_POOLS,replay_nodes}`，仅将`stopping/REPLAY_NODE_PATCHES.csv.gz`按request_id覆盖B8L2、D10和参考元数据，然后执行冻结规则。k2原deferred不改写、不填Q=0。使用全体源历史时源Q可用，目标Q不进入停止选择。

## 复现

在解压后总目录运行（Python 3.12，numpy、pandas及冻结引擎原依赖）：

```bash
python scripts/selection_stop_prepare.py
python scripts/selection_stop_endpoints.py plan
python scripts/selection_stop_endpoints.py run --jobs 4
python scripts/selection_stop_analyze.py all
python scripts/selection_stop_validate.py
python scripts/selection_stop_finalize.py
python scripts/selection_stop_report.py
python -c "import sys;sys.path.insert(0,'scripts');from selection_stop_finalize import accounting;accounting()"
```

已交付所有端点。复核汇总可直接从`selection_stop_analyze.py`开始，不必重跑融合。端点执行支持已完整完成池的恢复；旧缓存是可选加速来源，新复现无需取得已遗失的原团队库。prepare使用原历史与当前quality_inventory更新，不能把当前重新选择与旧人员固定评分混成一个版本。完整源输入位于总目录`source/`和本模块`inputs/`，各源blob清单保存在`CURRENT_SOURCE_BLOBS.json`、`ADDITIONAL_CURRENT_SOURCE_BLOBS.json`。

`selection_stop_late_pools.py`只是本次并行进程分配辅助，非科学规则，无需用于正常复现。`RUN_RECEIPT.json`可能把辅助进程已完成池记作resumed；去重实际复用/新增以`FINAL_ENDPOINT_ACCOUNTING.json`为准。

## 边界

分类最终采用尚未由用户确定；本模块不作决定。劳动是合法来源的记录活动量。关系待定不是图池OOS，原设计保留，主要说法另用无待定层；不同层、Manual/Semi、范围不可比面板各分开。冷启动回本只指有完整合法记录的原同房源面板，不估计未记录的参考人工成本或未定义的最小跨楼历史采集方案。
