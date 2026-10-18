# v1修订输入与人员粗细构成的真实融合

本包使用修订后的真实v1输入，恢复`rPc6DW4iMge-22`整池阻塞，并执行人员线程预先声明的有限组合。没有混入模拟标注，没有改B8L2／D10参数或接入N1，没有覆盖旧快照。

## 实际完成

|请求族|请求行|不同成员集合|完整几何／数值|允许主质量|
|---|---:|---:|---:|---:|
|粗细构成：8图／8建筑，含2门洞|528|502|438|424|
|原人员线程恢复请求：rPc-22|242|242|232|6|
|原失败池4条随机基线路径|96|93|92|6|
|R01424单成员对池参考诊断|1|1|1|0|

867请求全部返回。跨请求族合计836不同图池成员集合；25复用输入和参考一致的旧v1几何，811为本次真实融合。表内各族独特集合不能直接相加，因为同一成员集合可以被多个请求族调用。`DONE.json`的`new_subsets`表示最后一次运行新计算数，续跑后可能为0；总来源看`historical_v1_geometry_reused`和`current_revision_actual_subsets`。

细分类528行中，普通396行／312质量，门洞132行／112质量；24行k2按旧方法暂缓，65行没有可连接结果，1行底面无效。438个完整数值中14个因既有成员用途或目标资格不能进入质量比较。缺测没有填0，也没有删除请求。

## 几何修订与参考边界

当前输入为[修订manifest](../../data/processed_input_review_20261018/manifest.json)。9个所需图池按新bundle重新准备，只有`R01424`几何改变：恢复既有人工p8.y修订。没有删该人凑池，24名独立人员保留。

R01424按既有预评分局部结构路由绑定原GT，属于`bound_other_admitted_space`，仍只作诊断。直接个体对原GT的B8L2=85.07056、D10=88.52270，见[原绑定个体诊断](repaired_individual_score.json)；同一个人对该池声明参考的单成员共识诊断为44.60646／44.70328。两个参考不同，不能把分差解释为修订算法得失。个人质量1911份及分类训练1048份不因本包而增加。

团队始终按旧池声明目标评价，参考未重选。混合目标或任一成员不满足既有质量资格时，数值仅在`diagnostic_*`列。原留出继续限制主比较。rPc-22全24人结果为6节点，B8L2／D10诊断47.03322／47.19012；它是当前自动方法对这个有限池的结果，不是全员必然提高质量的证据。

## 人员构成与内容变化

分类请求来自[人员设计r3](../../workers/worker_fine_composition_20261018/TEAM_REQUESTS.json)，包含Q二分、Q三档、Q×T四格。固定k4的构成及成员抽组与固定终点的顺序路径分开。类别在目标建筑之外形成，本包不使用目标评分挑人。

- [同构成换人](same_composition_pairs.csv)：432对，327对底面V可算，178对节点数量不同，18对共享原始观察的墙线对应关系改变。
- [不同构成比较](between_composition_pairs.csv)：3312对，2464对底面V可算，1486对节点数量不同；只用同图、同scheme、固定k4的已有几何。
- [相邻人数变化](transitions.csv)：509条，其中72条细分类顺序路径、345条原人员请求路径、92条基础随机路径。

例如门洞q9-13，Q二分同样的“高2／低2”构成，FINE00004与FINE00006产生12／6节点、B8L2为58.25／22.09。Q×T不同构成FINE00016与FINE00021产生12／5节点、B8L2为70.16／26.28。这些是便于人工查看的内容差异例子，不是独立准确率或平均选人收益。

R是所选原答的两两底面对称差，归一化分母固定为该图池全员原答并集面积。V是两个实际融合底面的1−IoU，附面积对称差。Δ描述相邻加人前缀的节点／墙线对应／表决及底面变化。共享人员数、有效几何分母均保留；这些配对和路径有大量重叠，不能当作数千张独立图片。固定最终成员的三种顺序在每图k4终点均是同一集合，不将相同终点误称独立稳定性证据。

人员线程负责图／建筑层面的汇总及分类解释，本包不从这8图宣布通用最优类别组合。

## 文件与复现

[消费字段合同](CONSUMER_INTERFACE.json)；[逐请求结果](team_results.csv)；[唯一成员集合](unique_teams.csv)；[状态与分母](STATUS.json)；[核验](CHECKS.json)。

`input_snapshot.json`保存实际池、参考及成员坐标；`pools/<pool_id>/states.json.gz`的`states[].subset`是成员记录ID排序键，`automatic`包含墙线对应、节点、连接、底面和上下点对。`geometry_source`＋`geometry_state_pointer`可直接定位离线展示几何。该几何没有额外人审确认。

```powershell
python -m tools.thesis_main.analysis.worker_composition_fusion_20261018 prepare --requests research/workers/worker_fine_composition_20261018/TEAM_REQUESTS.json
python -m tools.thesis_main.analysis.worker_composition_fusion_20261018 run --jobs 3
python -m tools.thesis_main.analysis.worker_composition_fusion_20261018 verify
python -m pytest tests/test_worker_composition_fusion_20261018.py tests/test_wall_consensus_v1_process_20261017.py -q
```

12项相关测试通过；867个实际请求的成员、几何、参考、质量掩码、B8L2／D10共同缺失及用时缺失人数核验通过。普通与门洞各1组逆序输入从头重算，完整state与保存结果一致。未跑无关全库测试，未进行新的人工墙线身份认证。
