# 同房链路补齐（2026-10-30）

正式中文结果：[REPORT_ZH.md](REPORT_ZH.md)。冻结来源提交 `13a7861334749805a86dc19e9ea79fcaa71020c0`；分类只作为工作对象。本模块没有新增融合、团队或同房事实。

## 先读哪些文件

|问题|优先入口|
|---|---|
|旧 8904 条的单位及逐事件身份|`abc/EVENT_IDENTITIES.csv.gz`、`abc/CHECKS.json`|
|旧 ABC 当前标签双视角实际效果|`abc/SUMMARY.csv`、`PAIR_VIEW_REPETITION.csv`、`SUPPORT_STATUS.csv`|
|质量分项和失败/不可评|`abc/Q_COMPONENT_SUMMARY.csv`、`CONDITION_ENDPOINT_STATUS_COUNTS.csv`、`EVENT_ENDPOINT_STATES.csv.gz`|
|主半队容量与尚未执行的真实图对|`abc/HALF_CAPACITY_SUMMARY.csv`、`HALF_CAPACITY_ALL_DIRECTIONS.csv.gz`、`CAPACITY_SUFFICIENT_UNEXECUTED_MAIN_HALF_PAIRS.csv`|
|固定核心成员限制|`abc/MAIN_HALF_MEMBER_FREQUENCY.csv`|
|原图、完整原答、参考、融合、真实局部票数|`abc/cases/CASE_VIEWER.html`，与同目录 `images/` 一起解压|
|均值预测、个人相关、个人预测、多历史|`prediction/*_BY_SCOPE.csv`；三套原答支持分别置于三个 scenario 子目录|
|关系不传递审计|`prediction/HISTORY_DIRECT_EDGE_VALIDATION.csv`、`HISTORY_PANEL_DIRECT_EDGE_VALIDATION.csv.gz`|
|反例及支持扩展|`prediction/DIRECT_MEAN_IMAGE_ERRORS.csv`、`V2_V21_DIRECT_PAIR_SUPPORT_BRIDGE.csv`|
|共同人员及难度/参考结构匹配|`prediction/MATCHED_UNKNOWN_SUMMARY_BY_SCOPE.csv`，对应 scenario 的完整候选表|
|均值差与构成变化|`prediction/COMPOSITION_AND_MEAN_GAP_SUMMARY.csv`|
|平衡人员×视角平方和构成|`prediction/DECLARATION_VARIATION_SUMMARY.csv`、`DECLARATION_COMMON_MATRIX.csv.gz`|
|次要 Semi/门洞|`prediction/SECONDARY_SEMI_DOORWAY_SUPPORT.csv`|

## 复现，不需要原 21 GB 仓库

完整交付需要本目录、研究根 `scripts/same_room_*` 以及 `MINIMUM_REPRODUCTION_INPUTS.csv` 列出的共享 `source/` 文件。全部路径以研究根 `HOHONET_v21_full_chain_20261030` 为基准。Python 需要 pandas、NumPy、SciPy；查看器无需联网。现成几何、当前标量及原答都作为冻结输入复用，未重运行融合。

从已保存最小输入重新聚合时依次运行：

```bash
python scripts/same_room_abc.py
python scripts/same_room_capacity.py
python scripts/same_room_finish_abc.py
python scripts/same_room_prediction.py
python scripts/same_room_scope_finalize.py
python scripts/same_room_summary_tables.py
python scripts/same_room_variation_partition.py
python scripts/same_room_evidence.py
python scripts/same_room_case_viewer.py
node scripts/same_room_validate_viewer.js
python scripts/same_room_validate.py
```

ABC 重新聚合优先读取本目录 `EXISTING_VALID_EVENT_SOURCE.csv.gz`、`VALID_CLASS_RELATION_SOURCE.csv.gz` 和 `abc/EXISTING_GEOMETRY_SOURCE.csv.gz`，端点状态使用 `abc/EXISTING_ENDPOINT_STATUS_COMPONENTS.csv.gz`；容量使用 `minimal_inputs/PRIMARY_POOL_INPUT_SNAPSHOT.json.gz`（原 263 池完整输入的 2 MB 无损压缩）。病例脚本优先使用已提取的 84 端点完整轨迹、六图原答输入和六张真实原图。

`same_room_extract_events.py` 与 `same_room_endpoint_status.py` 是**可选的一次性存档采集器**。现成缓存存在时读取验证后退出；只有从未提取时才需要原 Git 对象库和原大文件分片。其原始 SHA256/分片定位保留在 `EVENT_SOURCE_RECEIPT.json` 与 `abc/ENDPOINT_STATUS_SOURCE_RECEIPT.json`，下游最小复现不要求重新下载那些大包。读取缺文件时会指出精确名称，不自行换旧版。

三套预测情景不得合并：`v2_frozen` 是原结论复现；`v21_on_v2_records` 保留原答身份，定位重评分影响；`v21_all` 是当前资格扩展。每套均保留旧含关系待定支持与无待定/待定分层。`oos_pending` 仅是冻结关系标记，不等同于当前原答 `is_oos`，本轮没有新裁定。

缓存复现已另行运行 `scripts/same_room_portability_check.py`：事件采集缓存、端点采集缓存、容量、病例证据及查看器五条路径在禁止任何存档子进程的情况下全部通过；回执为 `PACKAGED_INPUT_PORTABILITY_CHECK.json`。此检查验证的是已有打包输入可以离开旧仓库使用，不新增研究实验。

## 主要采用边界

- 主向 TARGET K3 10/5：268 事件、237 六端共同 Q、19 图对/7 楼；图对均值 C−B 19/19 正，两视角分别均正 18/19。GA/GS 两视角均正分别 14/19、13/19。
- 14/7：两对普通容量已全部执行；目标 Z 是固定同一七人。10/5 尚有 13 对容量合法却旧设计未执行，12/6 有 2 对；精确名单另表。
- 当前普通无关系待定均值：128 直接图对、65 图、13 楼；源 MAE 6.464 对楼外 9.496，39/65 图、8/13 楼改善。个人目标与图片均值目标的 MAE 不可直接相减。
- 人员×视角描述性平方和占比、残差相关与预测误差分开解释；任何一个都不是分类预测准确率。

保存本目录历史生成初检回执与最终验证回执；不把历史截断的中间文件继续作为正式输入。统一 ZIP 的内部可读性由总交付另做验证。
