# 字段与关联说明

底层数据为真人v2；研究轮次20261025。主评价域为普通Manual，门洞和特殊范围没有混入本轮换类主效应。部分新分类使用同人的Semi终稿与scope历史，但不混合两条件原答组成评价队伍。

## 1. 标签

`final/LABELS_ALL.csv`是31个实际比较实例、62人名册的描述标签，共1,922行；旧方法的ALL来自原归档，未用楼外多数投票重建。`LABELS_LOBO.csv.gz`为42,284条实际楼外标签。键为`method + heldout_building + worker_id`。

`class_id`只在本方法和本折内解释；跨折采用历史中心、人数角色和真实成员对应。`known=False`及空类标识表示证据不足，不表示低Q、简化或零响应。完整新类中心及支持在classifications/、reverse/；旧方法来源由label_source定位。ALL用于介绍人员，实际事件使用与building对应的LOBO折。

## 2. 精确事件

`final/ALL_EVENTS_EXACT.csv.gz`一行一个真实登记事件，共97,552行：95,264个严格ABC，2,288个直接AC。`event_id`全局唯一。`stage`保留探索、扩展、7选6、固定块人数路径和大团队AC的来源。

- `pool_id`定位图片、条件与冻结参考；`image/building/difficulty`沿用原库存。
- `method/source_class/target_class`为当前折标签；`history_target_minus_source_*`来自训练侧历史，非目标图成绩。
- `D/X/Y/Z`及`A/B/C_members`是用`|`分隔的真实worker_id集合。严格ABC四块互不重叠，A=D+X、B=D+Y、C=D+Z。直接AC没有B。
- `n`为完整团队人数，`m`为两队成员集合实际替换人数；`actual_m_*`保留各队对核算。
- `*_class_vector`是完整团队的类别人数向量；`seat_net_change_l1=2m`表示源类减m且目标类增m，不能再把2m叫作换人数。
- `replacement_fraction`或`replaced_fraction_of_team=m/n`；`replaced_fraction_of_original_source_seats=m/(D内源类人数+m)`；`source_block_fraction`/`replaced_fraction_of_source_pool=m/源类池容量`。三种比例不同。
- `background_id/block_id`标识实际D及XYZ；事件数不代替独立图片/建筑数。
- `parent_anchor_id/previous_event_id/entrant_worker`等连接固定块和逐人进入背景的路径。
- `feasible_*`给登记网格内精确可行容量；已抽样数与完整组合数分开。未覆盖的大空间不写成穷举。

`final/EVENT_ENDPOINT_LINKS.csv.gz`一行事件×臂，共290,368行；`team_key`连接端点。相同成员集合的确定性终点仅计算一次，可能被多条事件复用。

## 3. 去重端点

`final/UNIQUE_ENDPOINT_INVENTORY.csv.gz`有283,211个必要端点；每行的`scalar_source/geometry_source`定位已交付批次。原生新端点283,092，直接复用旧population端点119。原反推另复用了24,237个历史训练端点（其中24,004用于拟合），不能与新效果端点数相加充作新融合。

279,013个效果端点正式Q可评；4,198个保留不可评分/失败原因，未填Q=0。`score_status/geometry_status/below_four/complete_evaluable`等区分可评性。部分三节点或局部几何仍可用于非正式形状诊断，不因此恢复正式质量资格。

标量表保留Q、D10、分项、时间、成员、参考及节点票数；几何文件按team_key保存点列、底面和支持票数。完整自动分组、中位数来源和原观察关联只对六个机制案例保存；其它端点可按代码及小输入复放。

## 4. 质量、几何与幅度

正式Q为冻结B8L2；D10为敏感性。`iou_2d`为0—1底面IoU；`IoU3D100`为0—100均高棱柱代理，不是真实完整房间体积IoU。`dir`、`S_bottom_deg`、`Hmean/Hcenter`及误差量较小通常较好；节点、短边、尺度数值没有自动的正确方向。

严格ABC逐事件指标中：`*_BA=B−A`、`*_CA=C−A`、`*_CB=C−B`；`*_within=|B−A|`、`*_cross=(|C−A|+|C−B|)/2`、`*_gap=cross−within`。幅度和有符号收益分开。幅度要求相应三队共同可评价；CA/CB单独保留各自队对分母。

`geometry_bev_distance=1−两队有效底面的IoU`衡量输出形状距离，与到参考的质量IoU不同。`geometry_*_angle`用球面匹配点对角距离，未对应节点数另记；`geometry_same_pair_count`是相同节点数的指示量，方向与距离相反。

`matched_ref_*`用9°方位门限诊断对应位置，仅辅助解释；不改变正式评分或融合参数。它也不是整份原答9°/12°分簇阈值。冻结融合仍采用原7.5°对应与MV50门槛。

节点/非冗余转折/近共线与短边按已保存代码定义；有更多转折不自动等于正确。参考定义的遮挡结构与图上直接可见证据在案例说明中区分。

## 5. 失败与时间

`*_failed`是正式Q不可评；失败在全部登记尝试中保留。`C_loss10_CB`只在C/B都可评时计C下降超过10分；`C_failure_or_loss10_CB`以B可评为条件，将C失败或大损失一起计入。最终条件表同时给原始事件分子/分母、影响图片及图片等权率，两者不互换。

`source_time_total_seconds`仅在队内全部记录有时间时求和；来源、旧/新批、秒单位保留。它是原库存记录时间，不是本轮新测工时。时间差百分比按各事件C/A或C/B计算后按指定层级平均；不是预测误差改善的换算。固定背景路径加入同一人的时间，因此绝对秒差不变，百分比差随分母扩大。

## 6. 汇总与选择身份

主实验先在同XYZ和目标类背景人数层内平均，再对块/方向/图片分层等权，另给建筑等权。固定块规模分析先图片内路径平均，再图片等权。各自代码、phase与分母留存，事件数只表示覆盖。

`screen`用于本轮比较与候选筛选；`within_building_extension`为同批建筑的其它图片；`selection_heldout_building`为本轮初筛未用的10栋楼。方法/方向最终重点仍由这轮完整结果比较后选择；整套v2已多次使用，属于内部楼外研究。不要把它称为新的外部盲测。

## 7. 恢复

按DOWNLOAD_INDEX中的阶段包解压到同一研究根目录，再运行`restore_endpoint_cache.py --batch screen`、`--batch batch02`、`--batch size_paths`、`--batch large_team_ac_tail`。该脚本只关联已保存标量与几何，不执行融合。`run_native.py`会按精确成员键复用这些缓存，仅计算真正缺失的请求。
