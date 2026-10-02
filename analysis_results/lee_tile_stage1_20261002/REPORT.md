# Lee tile 第一阶段：固定方法的人数重放

本轮只改变参与人数和具体成员。BEV底面表示、等权投票固定；mv_strict仅检查平票。未分类人员，未加入d_model、BiLayout、质心权重、三维总分或难度回归。

固定面板：12图，195份作答；177份独立共识候选；其余按既有资格保留在覆盖表。
每组16个固定随机排列。每一当前k重新用当前成员切tile，不使用GT或未来成员生成分区。缓存只复用完全相同成员集。
原始/人工修订参考分别评价；特殊场景和参考存疑的GT距离仅为参考一致性。图间不混成总体准确率，不检验难度显著性。

| 图片 | 条件/资格 | 人数 | MV50：k=1 → 全员，原始参考IoU | 严格多数：全员IoU |
|---|---|---:|---:|---:|
| 2t7WUuJeko7-07 | manual / oos_doorway_exploratory | 8 | 0.5652 → 0.6259 | 0.6321 |
| 7y3sRwLe3Va-06 | manual / oos_doorway_exploratory | 7 | 0.4619 → 0.6268 | 0.6268 |
| 7y3sRwLe3Va-08 | oos / oos_doorway_exploratory | 24 | 0.5167 → 0.6376 | 0.6320 |
| 7y3sRwLe3Va-12 | oos / oos_doorway_exploratory | 24 | 0.4941 → 0.3883 | 0.3912 |
| 7y3sRwLe3Va-26 | manual / main_candidate | 5 | 0.8676 → 0.9335 | 0.9335 |
| B6ByNegPMKs-40 | manual / main_candidate | 22 | 0.6385 → 0.7628 | 0.7358 |
| B6ByNegPMKs-42 | manual / oos_doorway_exploratory | 8 | 0.2900 → 0.6033 | 0.6377 |
| e9zR4mvMWw7-16 | semi / main_candidate | 24 | 0.8221 → 0.8649 | 0.8570 |
| e9zR4mvMWw7-19 | manual / main_candidate | 24 | 0.4252 → 0.4694 | 0.4587 |
| jtcxE69GiFV-12 | manual / main_candidate | 9 | 0.5535 → 0.5808 | 0.5808 |
| jtcxE69GiFV-30 | manual / main_candidate | 1 | 0.7908 → 0.7908 | 0.7908 |
| yqstnuAEVhm-31 | manual / main_candidate | 21 | 0.4039 → 0.5237 | 0.5237 |

## 解释边界

- k=1均值来自固定排列实际抽到的不同单人；不是每图全部单人的穷举均值。
- ≥50%在两人时保留并集，>50%保留交集；偶数人数的起伏可能由平票规则产生，不能通过平滑隐藏。
- 全员时成员集合唯一，成员差异降到0是机制属性，不证明接近GT、未来人员不再改变或达到质量上限。
- p10/p90为采到的成员集分布，不是总体置信区间。当前小面板是开发材料，不是独立验证集。
- 几何交集有限性与面积上界单独检查；仅把约浮点舍入量级的IoU越界裁回[0,1]，不改变输入或聚合几何。
- 门洞交界可能含无法合理标注部分；OOS的GT未必适用。不能由这些图的参考距离直接推断人员能力。
- 捕获数值警告 97 条，见 warnings.json；未做坐标吸附、buffer修复或删除碎片。

## 工件

- replay.csv：完整排列前缀、成员、状态、参考距离和相邻变化。
- summary.csv：每图/条件/资格/方法/人数摘要、失败覆盖和成员差异。
- full_tiles.geojson：各组全员tile几何及支持者；为本地h单位坐标，不是地理经纬度。
- coverage.json、field_contract.json、warnings.json：分母、口径与数值诊断。
- reference_curves.png、stability_curves.png：逐图曲线，不混合不同图片面板。

本轮没有原图视觉裁决，也没有证明tile优于相同定义的逐点多数投票。下一步先检查这些曲线及覆盖，再决定扩展图片或增加一类质量指标。
