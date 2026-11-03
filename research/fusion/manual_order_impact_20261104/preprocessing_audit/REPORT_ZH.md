# 全研究输入流程与预处理复核

## 核心结论

这批57组不是从未经预处理的原导出重新起步。它们使用的是当前v2.1有效原答视图和已冻结的融合节点。沿GitHub固定提交 `ac395e703d1fef573d1ef3e105df0286d62a0468` 的当前显式输入、文档、函数和数值逐层核查，未发现本次顺序接入遗漏既有的共享x预处理。

全库存10,730个对象包含10,439份人员作答及291份参考对象。10,597个ready对象的共享x函数重放、点数、y、幂等性、最终环序回源映射均通过，数值最大差为0。133个不可用对象（129 unavailable、4 blocked）继续保持坐标空值，没有回退原点。57组的654次人员记录引用去重为315份原答，全部与显式v2.1有效输入坐标逐点相等；436个冻结融合节点的原medoid锚定周期中位数规则也精确复现，最大差0。来源见 `CHECKS.json`、`ALL_INVENTORY_PREPROCESSING_CHECKS.csv.gz`、`57_TEAM_SOURCE_COORDINATE_CHAIN.csv.gz`、`57_TEAM_NODE_CENTER_CHECKS.csv`。

这是输入与计算流程的数值核验，不是全库存语义正确性认证，也没有重新运行全库融合。

## 实际流程及本次接入位置

| 层次 | 当前实际处理 | 本次处理与边界 | 主要证据 |
|---|---|---|---|
| 原始来源与已确认编辑 | 保留原导出、人工删补/改点、借用及资格证据；共享x之前的有效坐标可能已含确认修订 | 不用原导出覆盖有效输入；库存中33份有原导出的人员记录，其处理前视图已与原导出不同 | `docs/thesis_main/研究数据说明_来源预处理与用途_20261006.md`；`processed_input_review_20261018/README.md`及坐标修订台账 |
| 新增W100—W134收件 | 新收件本身为用户已处理数据；核对提供配对、完整边界环和坐标，再做共享x | `original_export_points`为空有明确来源含义，不能补称原始采集导出；用户处理后的时间不冒称已重放原日志 | `intake_workers_v2_20261019.py`；`admit_workers_v2_20261019.py` |
| 单份作答预处理 | 对同一上下点对，在1024周期上取最短弧x中点；上下y均不变；完整配对异常阻塞 | 全库存ready对象按原函数重放通过；不把“ready”当作质量或投票资格 | `shared_x_reanalysis_20260922.shared_x`；`intake_W100_W134_20261019/PREPROCESSING.json` |
| 最终环序与源索引 | 已确认环及默认环有各自明确来源，最终视图按top/bottom交替，保留回源点/点对映射 | 直接使用已保存的有效环；不把原答默认x排序再次施于人工确认的融合节点 | `analysis_input/data.json.gz`；`research_round_20260929.prepare_record` |
| 当前参考与分析资格 | v2.1显式manifest接合当前目标、已采用底面/顶面参考及一图一个难度；主目标、其它合法目标、门洞、OOS分层 | 不从旧全局CURRENT推断本实验版本；逐团队核对reference ID/version和目标池，参考不按得分择优 | `v2.1/analysis_input/manifest.json`、`CROSS_MODULE_INPUTS.json`、`reference_catalog.json`、两份池快照 |
| 人员画像及选队 | DSTRUCT从原答结构/参考对应等形成当前标签；Q历史及JOINT保留原定义；RFUSE读取其规定自然融合训练人数 | 本次固定所有标签和既定团队；RFUSE训练28,312行精确查交集为0，故没有重拟合依据 | `../dependencies/RFUSE_EXACT_TRAINING_INTERSECTION.csv`、`INDIRECT_DEPENDENCIES.csv` |
| 自动融合 | 逐两份作答保序匹配，完全连接相容身份组；全队MV50；同身份成员等权、medoid锚定周期中位数x，top/bottom y各自中位数 | 本次不重匹配/重聚类/重筛点。436个已存节点的中心来源审核通过 | `ring_correspondence_20261007.build`、`consensus_delivery_20261008.fuse` |
| 连接 | 自动选覆盖全部保留节点的来源环，无完整环则保留无连接；人工可另给完整节点顺序 | 57组直接接已确认顺序，自动分支保留；不把人审说成历史算法自动成功 | `assemble_fusion`；`user_order_return`与`../endpoints` |
| 几何与评分 | 1024×512连续坐标反投影；`compute_fit=False`；不拟合、修点或偷偷重排；合法性和可见核分别记录；复用冻结B8L2/D10 | 固定坐标56组完整可评、1组自交；未评分保持空值。评分环境30项原已评分几何复核最大差4.27e−14 | `research_round_20260929.reconstruct`、`panorama_studio/geometry.py`、`wall_consensus_quality_20261015.measured` |
| 下游统计 | 按原实验的事件、块、图、图对、楼层级分别聚合；人数路径保留同队重复频数，有限配比保留完整成员组合 | 仅实际引用进入增量计算；可评支持扩展与原共同支持数值变化分别交付 | `../dependencies`及各专题结果目录 |

### 数值核验的两个容易误读处

`57_TEAM_SOURCE_COORDINATE_CHAIN.csv.gz` 中212次引用保留了显式回源索引，均相等；442次旧保存记录未带该元数据。后者仍能用对象ID和完整有效坐标与当前bundle精确绑定，不能把“未保存索引字段”误报成坐标不一致。没有出现双方均有索引却不同的记录。

当前原图为2048×1024，而研究坐标明确为1024×512连续坐标。显示时按2倍映射；不能为了贴合原图把评分坐标再乘2。所有57个团队使用的参考点及底面与实际消费池精确一致；当前参考包含既有底面/顶面修订，不能再套用旧原GT共享x后假称同一参考。

## F2／F9候选为什么单列

pa4-18中，显示F2对应 `node_001`，显示F9对应 `node_010`。两者各有2票、来自不同身份组；原各自上下点已经同x。把二者共同设为438.8037，是把两个不同融合中心拉到同一经度，不属于“同一个点对的上点与下点取平均”的既有预处理。

依用户新提出的方案，已单独执行4个x标量编辑，保留全部9节点、y、票数、来源人员、顺序和参考，结果见 `../coordinate_candidate/README.md`。该候选完整链评分可算：B8L2=39.61561918763198，D10=41.30578782236161，无自交；相机可见核诊断仍为false。`geometry.py` 明确将 `camera_visibility_unresolved` 与阻断合法面的错误区分；因此“代码接受条件评分”与“视觉/语义几何全部确认”仍是不同结论。

固定坐标第一批56/57结果仍然有效；新候选是另一种干预版本，不能改写成57/57单纯顺序成功，也不能把原无Q当0计算改善。其真实引用仅AC50条、联盟2条，未命中半队、Q-only或同房；另行核算候选影响。

## 复现

在固定基线仓库根目录运行：

```bash
python -m tools.thesis_main.analysis.audit_manual_order_preprocessing_20261104
python -m tools.thesis_main.analysis.evaluate_manual_coordinate_candidate_20261104
```

脚本读取显式v2.1输入而不调用默认CURRENT加载替代版本；不写回原作答、预处理包、参考、资格或原自动实验。所有检查表在本目录；本次未新增人工作答问题，也没有要求重复57组排序。
