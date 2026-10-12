# 既有冻结融合终点：三候选研究重评分

日期：2026-10-13。原融合算法、gap=7.5、原成员、节点、连接和人工介入全部保持；本次只对现有真实终点重新计算质量。没有生成任何k曲线。

## 接入与覆盖

完整包来自 `source_package/quality_parameter_calibration_20261012/`，读取其冻结配置和几何评分接口；身份守卫通过。三候选为 `P_tied_quad08`、`P_tied_mix08`、`B_main_relative2`，并保留旧Q_v11、官方角点均高3D IoU×100、底面IoU×100。参数及哈希、包计算源版本、运行checkout版本均保存在 `fusion_rescore.json`。

| 冻结版本 | 实际输出 | 可重评分 | 不可评分原因 |
|---|---:|---:|---|
| 纯自动 | 177 | 54 | 103缺包内明确参考；17两人排序暂缓；3无覆盖所有节点的来源环 |
| 人工辅助 | 43 | 6 | 36缺参考；1上端跨地平线导致常规投影不可用 |

60个可算版本仅覆盖54幅图，辅助与自动不是独立N。另保留rPc-22整池输入失败，不将它从原始178池分母中悄悄抹去。所有参考只按完整image_id匹配922包中唯一reference_object_id；本次没有遇到多参考歧义，多参考/缺参考的接口均返回null而不挑高分。69个版本找到参考，部分因无连接不能评分。

**上述60个分数全部是研究诊断，不是已获范围资格的正式比较。** `formal_comparison_eligible=false`；融合表达范围、参考接受程度及研究曝光仍需独立账本。Uw-09的 `incomplete_consensus_observed` 原状态保留，本包无其可绑定参考，未评分。60份可算版本的成员未发现W019；全部成员经record_id→冻结population.object_id→质量loader.worker_id桥接，并核对image_id，未将P/W编号按数字等同。

已继承既有参考排除/人工hold/证据冲突隔离注册表及成员的cleaning、worker_quality_gate、independent_vote。220版本中7个带明确GT排除或隔离，56个带成员资格障碍；它们没有因本次接口而获准。60份可算版本无上述已知障碍，但仍全部有 `fusion_scope_not_adjudicated`。原holdout房间组也单独保留，不升格为未曝光验证。

## 投影与独立检查

采用既有 `research_round_20260929.reconstruct` 的 **continuous x/W,y/H**，ERP1024×512，相机高度为1，保留冻结环序，未平均、修复或重新排序。不能用pixel_center替代：初核3例会产生0.0116—0.0325相机高度的坐标差。

从包中按原记录顺序各取一种点对数，覆盖3/4/5/6/8/12点对共6例，重建几何与包内冻结坐标最大误差1.33e-15。其余评分复用包内evaluate：球面采样2048、高度4096，每份只算一次几何分项，再由原scalar_terms算三个冻结候选。

已运行1项重要边界测试：多参考歧义、缺参考均不产生任意绑定，地平线不可投影保留null。实际输出JSON禁止NaN，几何不适用不填零。新增15份旧审记录的gate不总有reference_version；此时保留完整reference_object_id，版本标签显式记 `not_recorded_in_calibration_gate`，不自行补认版本。

## 实际改变什么

下表仅描述相同终点、相同参考上的代数变化，不据此声称新算法更符合人类。

| 版本 | 候选相对B_main_relative2 | 最小变化 | 最大变化 | 均值变化 |
|---|---|---:|---:|---:|
| 自动54 | P_tied_quad08 | -5.597 | +5.165 | -1.075 |
| 自动54 | P_tied_mix08 | -5.575 | +5.422 | -1.000 |
| 辅助6 | P_tied_quad08 | -5.339 | +0.032 | -2.465 |
| 辅助6 | P_tied_mix08 | -5.339 | +0.047 | -2.443 |

- `uNb9QFRL6hY-40`自动：结构残差10.416°，新二次候选42.166→36.568；结构损失0.813→1.115，整体高度损失反而降低。主要变化是结构处罚增大，而非局部高度加强。
- `B6ByNegPMKs-50`自动：均高相对差0.2267，新二次候选58.539→63.704；整体损失0.206→0.080，局部项保持0.00683。主要变化是整体高度处罚放松。

这两例定位了新候选在真实融合终点上的作用来源，但范围资格与人工质量意见尚未由此次计算补齐，不能当作胜负验收。

## 复算和下一步

```powershell
python -B -m tools.thesis_main.analysis.quality_frozen_fusion_rescore_20261013
python -B -m pytest tests/test_quality_frozen_fusion_rescore_20261013.py -q -p no:cacheprovider
```

JSON字段合同：rows按image_id+version一行；scores/components为候选名映射，未评分为null；reference_status、projection、geometry_status_frozen、review_status、scope_eligibility彼此独立；members保存原成员身份桥接；全局candidate_configs携带冻结参数及config_sha256；sequence_id始终null，明确不是人数路径。

下一步先由主线程的资格/曝光账本接入上述终点。缺参考继续列明，不从其他GT版本择优。人数轨迹仍缺当前方法逐k冻结输出和子集政策，详见FUSION_INVENTORY.md；没有启动新的融合实验设计。

未运行大规模融合、参数搜索和无关测试；新分数不替代正式分数，数值可算不等于语义正确或资格成立。
