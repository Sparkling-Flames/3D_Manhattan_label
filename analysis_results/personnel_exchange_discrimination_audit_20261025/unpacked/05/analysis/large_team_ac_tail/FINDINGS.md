# 固定7人换类块延伸至大团队：直接 AC 结果

## 采用判断

**大团队仍存在可用的换类方向。** 固定 N35 人员池，DSTRUCT_K3 的原 X7 与目标 Z7 不变，把原 Y7 源类人员逐步加入共同背景，n28 时两队共同背景有21人、实际替换7人（团队的25%）。在全部研究阶段，该方向平均 C−A 为 +2.868 Q，51/57可评图片、17/20楼正向；在选型保留建筑子域为 +4.016 Q，25/26图、9/10楼正向，52个注册事件中的C失败或相对A下降10分均为0。建议把 **n28/m7 的 DSTRUCT 方向保留为大背景中的定向质量用途**。

这不等于 n28 同类/跨类幅度已得到证明。严格 ABC 在该池容量下到 n21；Y 进入背景后 B 不再存在，本目录只有直接 AC。n21 的同/跨幅度证据应回到 `analysis/size_paths/`。

联合 Scope 方向在 n28 同样有正向质量结果：全部 N35 队列平均 +3.868 Q、37/39图正向；保留楼 +5.081 Q、14/14可评图和7/7楼正向。不过保留楼28事件有1次C融合失败；n22/n24/n26也出现失败。**按大团队升质候选保留，同时单列失败风险，不因为可评均值较高而忽略失效队伍。**

## 完成范围与设计身份

286条路径、2288个直接AC事件、2002个相邻步骤、90图22楼，底层真人v2。共4392个去重端点；其中572个复用严格路径末端，3820个登记集合由执行阶段补算。每路径k0…7全部完成，n实际从16至28；没有查看效果来选择进入顺序。

原 X7/Z7 始终固定，每次同一个原 Y7 源类人员进入 A/C 的共同背景。m恒7，不是“每步换1人”；逐步加背景与 A/C 间的7人替换是两个不同概念。路径覆盖1/7!的Y顺序，各k的具体可行背景子集数保存在设计中。n28仍不等于全员35人唯一终点，两队分别保留不同7人块。

## 固定 N35 队列：全部阶段与保留楼并置

图片内先平均注册路径，再图片等权。CA采用两队可评分的队对；失败仍在注册分母与下表之外的专门失败表中。各阶段分开，不能把全部阶段覆盖称为未参与选型的建筑覆盖。

| method | phase | n | B8L2_CA | B8L2_abs_CA | positive_images/valid_images | positive_buildings/valid_buildings |
| --- | --- | --- | --- | --- | --- | --- |
| DSTRUCT_K3 | ALL_PHASES | 21 | 4.377 | 5.380 | 55/57 | 18/20 |
| DSTRUCT_K3 | ALL_PHASES | 24 | 4.006 | 4.822 | 53/57 | 18/20 |
| DSTRUCT_K3 | ALL_PHASES | 26 | 3.343 | 4.953 | 51/57 | 17/20 |
| DSTRUCT_K3 | ALL_PHASES | 28 | 2.868 | 4.820 | 51/57 | 17/20 |
| DSTRUCT_K3 | selection_heldout_building | 21 | 5.826 | 6.232 | 25/26 | 9/10 |
| DSTRUCT_K3 | selection_heldout_building | 24 | 5.047 | 5.256 | 25/26 | 9/10 |
| DSTRUCT_K3 | selection_heldout_building | 26 | 4.934 | 5.090 | 25/26 | 9/10 |
| DSTRUCT_K3 | selection_heldout_building | 28 | 4.016 | 4.316 | 25/26 | 9/10 |
| MSDGEOM_SCOPE_K4 | ALL_PHASES | 21 | 4.527 | 4.657 | 39/39 | 15/15 |
| MSDGEOM_SCOPE_K4 | ALL_PHASES | 24 | 2.623 | 3.962 | 37/39 | 14/15 |
| MSDGEOM_SCOPE_K4 | ALL_PHASES | 26 | 2.745 | 3.652 | 35/38 | 14/15 |
| MSDGEOM_SCOPE_K4 | ALL_PHASES | 28 | 3.868 | 4.582 | 37/39 | 14/15 |
| MSDGEOM_SCOPE_K4 | selection_heldout_building | 21 | 4.556 | 4.917 | 14/14 | 7/7 |
| MSDGEOM_SCOPE_K4 | selection_heldout_building | 24 | 2.743 | 2.744 | 14/14 | 7/7 |
| MSDGEOM_SCOPE_K4 | selection_heldout_building | 26 | 2.897 | 2.897 | 13/13 | 7/7 |
| MSDGEOM_SCOPE_K4 | selection_heldout_building | 28 | 5.081 | 5.081 | 14/14 | 7/7 |

完整n21…28都在 `KEY_N35_AC_CONDITIONS.csv` 与图中。DSTRUCT保留楼从n21的+5.826缩到n28的+4.016；方向保留，净优势有所减弱。联合Scope不单调；有些n的均值会受具体成员、几何变化和失败可评分分母影响。

## 全部容量路径：相同286锚点的 k0 与 k7

各图片的实际池大小不同，k0为各自N−14、k7为N−7；这个比较保持全部锚点，回答原Y全部加入背景后的变化，不能和上面的固定N35人数曲线混为同一个估计。

| method | phase | tail_step | B8L2_CA | B8L2_abs_CA | positive_images/valid_images | positive_buildings/valid_buildings |
| --- | --- | --- | --- | --- | --- | --- |
| DSTRUCT_K3 | ALL_PHASES | 0 | 3.428 | 6.427 | 74/83 | 18/21 |
| DSTRUCT_K3 | ALL_PHASES | 7 | 3.731 | 5.515 | 72/83 | 20/21 |
| DSTRUCT_K3 | selection_heldout_building | 0 | 3.167 | 6.676 | 35/41 | 8/10 |
| DSTRUCT_K3 | selection_heldout_building | 7 | 4.036 | 4.866 | 37/41 | 10/10 |
| MSDGEOM_SCOPE_K4 | ALL_PHASES | 0 | 3.738 | 5.709 | 51/56 | 15/17 |
| MSDGEOM_SCOPE_K4 | ALL_PHASES | 7 | 4.048 | 5.452 | 51/56 | 16/17 |
| MSDGEOM_SCOPE_K4 | selection_heldout_building | 0 | 3.414 | 6.312 | 23/26 | 7/8 |
| MSDGEOM_SCOPE_K4 | selection_heldout_building | 7 | 4.177 | 5.600 | 24/26 | 8/8 |

## C 自身变化与 CA 差的变化

相对各自严格ABC末端的k7变化：

| cohort | method | phase | A_change_B8L2 | CA_change_B8L2 | C_change_B8L2 | C_change_nodes | C_new_failure_or_loss10_given_previously_scored | joint_AC_A_change_B8L2 | joint_AC_CA_change_B8L2 | joint_AC_C_change_B8L2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_fixed_anchors_by_k | DSTRUCT_K3 | ALL_PHASES | 0.129 | 0.281 | 0.262 | -0.052 | 0.041 | 0.108 | 0.281 | 0.388 |
| all_fixed_anchors_by_k | DSTRUCT_K3 | selection_heldout_building | 0.328 | 0.825 | 0.818 | -0.107 | 0.036 | 0.284 | 0.825 | 1.109 |
| all_fixed_anchors_by_k | MSDGEOM_SCOPE_K4 | ALL_PHASES | 0.370 | 0.741 | 1.145 | 0.035 | 0.026 | 0.376 | 0.741 | 1.117 |
| all_fixed_anchors_by_k | MSDGEOM_SCOPE_K4 | selection_heldout_building | 0.799 | 1.511 | 2.143 | 0.037 | 0.037 | 0.813 | 1.511 | 2.324 |
| fixed_pool_N35 | DSTRUCT_K3 | ALL_PHASES | 0.371 | -1.509 | -1.091 | -0.009 | 0.034 | 0.371 | -1.509 | -1.138 |
| fixed_pool_N35 | DSTRUCT_K3 | selection_heldout_building | 0.549 | -1.810 | -1.261 | -0.038 | 0.019 | 0.549 | -1.810 | -1.261 |
| fixed_pool_N35 | MSDGEOM_SCOPE_K4 | ALL_PHASES | 0.892 | -0.039 | 0.995 | 0.038 | 0.026 | 0.901 | -0.039 | 0.862 |
| fixed_pool_N35 | MSDGEOM_SCOPE_K4 | selection_heldout_building | 0.768 | 1.915 | 2.708 | 0.071 | 0.036 | 0.793 | 1.915 | 2.708 |

普通A/C自身变化各用可用队对；`joint_AC_*` 三列严格同分母，满足 CA变化=C变化−A变化。不能把CA均值增长直接称为C升质，或把CA缩小全部解释成C变差。完整逐步结果保留每一步的新进入者、前后端点和失败/恢复。

## n28质量分项

| method | phase | D10_CA | IoU3D100_CA | iou_2d_CA | nodes_CA | matched_ref_top_abs_deg_CA | matched_ref_bottom_abs_deg_CA |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DSTRUCT_K3 | ALL_PHASES | 2.594 | 1.498 | 0.012 | 0.078 | -0.209 | -0.130 |
| DSTRUCT_K3 | selection_heldout_building | 3.749 | 2.464 | 0.021 | 0.115 | -0.223 | -0.123 |
| MSDGEOM_SCOPE_K4 | ALL_PHASES | 3.738 | 2.270 | 0.020 | 0.192 | -0.214 | -0.128 |
| MSDGEOM_SCOPE_K4 | selection_heldout_building | 4.963 | 2.876 | 0.026 | 0.357 | -0.239 | -0.111 |

上下界绝对角度误差的负CA表示改善。n28仍有边界位置和三维差异，平均节点数变化较小；因此剩余作用并非仅是“画出更多节点”。具体结构正确与否须结合原图和已保存的投票/连接案例。

## n28失败与明显损失：精确事件计数

| method | phase | paths | A_failure_events | C_failure_events | C_failure_unique_endpoints | C_failure_or_loss10_CA_events | C_failure_or_loss10_CA_valid_events |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DSTRUCT_K3 | ALL_PHASES | 116 | 2 | 0 | 0 | 3 | 114 |
| DSTRUCT_K3 | selection_heldout_building | 52 | 0 | 0 | 0 | 0 | 52 |
| MSDGEOM_SCOPE_K4 | ALL_PHASES | 78 | 0 | 1 | 1 | 2 | 78 |
| MSDGEOM_SCOPE_K4 | selection_heldout_building | 28 | 0 | 1 | 1 | 1 | 28 |

同一终点可能在不同锚点复用，完整表同时给唯一端点分母，事件数不冒充独立证据。C失败没有填0分。全部阶段DSTRUCT仍有个别相对A超过10分的质量损失；保留楼子域在此n28范围没有这类损失，这两条都保留。

## 时间与适用范围

本尾段每次给A/C加入同一个人的原库存记录时间。固定X/Z的绝对CA秒差不随人数变化；百分比时间差随共同分母扩大。该路径不产生新的生产计时，也不是节时方向的重新发现。

这里只评价普通Manual、已具备对应源/目标容量的原锚点、上述历史角色方向。楼外标签与原阶段身份全部保留。部分困难图N不足35，已在全部容量k结果保留，不应从N35子域外推“所有困难图大团队均改善”。

## 可接续文件

- `KEY_N35_AC_CONDITIONS.csv`：实际n21…28、全部阶段与保留楼。
- `KEY_ALL_CAPACITY_AC_CONDITIONS.csv`：全部固定锚点k0…7。
- `KEY_AC_PER_ARM_MOVEMENT.csv`、`KEY_AC_FAILURE_COUNTS.csv`：自身/净变化与失败真实分母。
- `CURVE_BY_K_*`、`FIXED_N35_BY_N_*`：完整指标逐图、逐楼与汇总。
- `FROM_STRICT_TAIL_EXACT.csv.gz`、`STEP_EXACT.csv.gz`、`PATH_EVENT_MEASURES.csv.gz`：精确关联和可重聚合指标。
- `AC_TAIL_Q_CURVES.png`/`.svg`：完整固定N35曲线。
- `design/large_team_ac_tail/EVENTS_EXACT.csv.gz`：精确D/X/Z、原Y及进入顺序、A/C成员与端点。

同类/跨类区分度的正式结论仍由严格ABC提供；本目录补足“相同7人类别块在更大共同背景里是否还改变结果”。
