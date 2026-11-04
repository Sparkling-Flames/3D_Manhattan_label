# 同房预测、Q/QT选队与停止：真实间接依赖核查

## 结论

本批57组不会经半队、同房ABC或AC的新结果继续改变同房公共/个人预测、Q/QT选员或停止决策。预测与选员历史读取原答质量及劳动，输入未改；停止确实读取源视角融合Q和目标几何，但完整停止源表也与57组零交集。因此这几条链保持原结果，没有为统一版本而重新拟合、重选或重跑停止。

本核查只读代码与原表，不改变已冻结统计。逐消费者路径、筛选和特征见 [INDIRECT_PREDICTION_STOP_AUDIT.csv](INDIRECT_PREDICTION_STOP_AUDIT.csv)，全部来源哈希见 [INDIRECT_PREDICTION_STOP_CHECKS.json](INDIRECT_PREDICTION_STOP_CHECKS.json)。

## 1. 预测读取原答，未读取换人效应

真实预测实现位于`stage02_same_room/prediction`链，代码为 [same_room_prediction.py](../../../workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/scripts/same_room_prediction.py)。它由 `legacy_common.load` 读取原答审计记录、训练准入、直接同房关系及原历史面板；通过`object_id`接入v2.1 `quality_inventory`和图片难度。原答入口见 [common.py: load](../../../same_room/same_room_profile_return_review_20261021/pro/room_similarity/code/common.py)。

正式原答门控为`pool_analysis_eligible & quality_usable & !is_oos & target_aligned`，限`ordinary_primary/doorway_quality`。直接普通Manual关系要求可比、无实质冲突、至少4个共同人员。楼外历史仅取其它建筑、ordinary且training_allowed的原答。公共均值、个人theta、同房源均值和原楼外校准均从这些原答计算；个人模型的0.5倍源残差是原固定系数，不来自50%换人统计。本批固定源记录与参考，只改变选定融合节点的连接，没有把人工辅助Q写回原答quality_inventory，也没有改变历史训练样本。

## 2. Q/QT选择与结果

[selection_stop_prepare.py](../../../workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/scripts/selection_stop_prepare.py) 的 `history` 使用原`record_index`与当前原答`quality_inventory`，保留楼外8图/3楼支持、来源分开的时间字段、固定原候选、原2分Q容忍及随机种子。选员特征是楼外个人Q_peer、源视角个人Q和原劳动，不读取半队或AC均值；目标融合结果用于评价，不进入历史特征。

[selection_stop_analyze.py](../../../workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/scripts/selection_stop_analyze.py) 将冻结设计与端点标量合并，生成`POLICY_EVENT_RESULTS.csv.gz`。本次完整检查 **71,608行**，同时扫描 `team_key, base_team_key`，与57组引用交集为0。[selection_stop_finalize.py](../../../workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/scripts/selection_stop_finalize.py) 的关系主层只是这些行的`ordinary_manual + scope_comparable`子集，并排除pending与substantive_conflict；其它分层、图片/建筑聚合及共同支持同样没有新输入，保持原结果。

## 3. 停止检查覆盖全部前缀

不能仅凭1,534行`STOPPING_SCALARS`零命中判断整个停止链。该表只覆盖历史v2→v2.1四个参考变化池；真正的停止代码还读取全部旧`replay_nodes.csv.gz`并沿用其它池的前缀。

本次完整读取 **124,924行、60,129个唯一(pool,成员集合)、43池、20个原组**。按原函数重建精确team_key，同时直接按`(pool_id, sorted(member_workers))`做不经哈希的集合交集，两者与57均为 **0**。参考筛选尚未施加就已零交集，所以不是旧/新参考版本筛选造成的伪零。原完整行数、图数与组数均与STOPPING_CONTRACT一致；源表按历史规则会覆盖5,100条参考变化前缀，剩余前缀也已检查。

团队键合同为：

```python
payload = json.dumps(sorted(workers), sort_keys=True, separators=(',', ':')).encode()
team_key = pool_id + '__' + hashlib.sha256(payload).hexdigest()[:20]
```

先对57端点的已保存pool_id及成员重建，**57/57等于原team_key**，再应用于停止源表；自校验明细见[INDIRECT_PREDICTION_STOP_TEAM_KEY_SELF_CHECK.csv](INDIRECT_PREDICTION_STOP_TEAM_KEY_SELF_CHECK.csv)。并行的直接集合比较不依赖该哈希，避免错误命名合同导致伪零。匹配结果表保留空表头，见[INDIRECT_PREDICTION_STOP_MATCHES.csv](INDIRECT_PREDICTION_STOP_MATCHES.csv)。

原规则 [rebuild_stopping.py](../../../workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage05_selection_stop/inputs/research/same_room/same_room_profile_return_review_20261021/pro/prior_integration/rebuild_stopping.py) 用已取得源视角Q曲线找距峰值2分的最早k≥3；目标只按几何ok、至少4节点、连接可用补收。在线规则在k≥5时检测连续三次完整输出节点数一致。k2继续排除，源不足不插值，目标Q不参与选择。源曲线、几何序列、人员顺序和劳动都无本次命中，所以停止决定及冷启动成本不会被其它链的新统计间接改变。

## 4. 保留边界与复现

同房有限配比原PANEL_TEAM_LINKS另核查92,342行，零命中；这不构成预测的训练集。新增同房ABC六端可评支持不能等同原答预测支持扩展。旧Q/QT同房选队也不是本次半队DSTRUCT与Q-only公平对照，两者的历史特征与评估端点应按实际路径分别保留。

复现本只读核查：`python -m tools.thesis_main.analysis.audit_manual_order_prediction_stop_20261104`。脚本不会导入执行原统计脚本，不拟合预测、不生成团队、不重评分、不重跑停止。源提交为`ac395e703d1fef573d1ef3e105df0286d62a0468`。预测代码中的`source/`表示原归档的冻结源映射，历史版本说明以该归档的源合同为准；本审计不修改其参考、关系、准入或旧统计身份。
