# 6／8／12／16人固定背景单人替换：真实融合结果

本包接收[人员替换实验设计](../../workers/worker_exchangeability_20261018/TEAM_REQUESTS.json)，以绝对Q三档、相对Q三档、相对Q×速度四格构造同类／跨类单人替换。不将scope或Semi作为本轮人员分类维度。

沿用修订后的真实v1输入、既有墙线对应／MV50／中位数定位／连接路线及B8L2、D10。未接入N1，未重新选参考，未覆盖原4人组合研究包。

## 完成与分母

8图／8建筑，含2门洞。3840请求全部返回，3839不同成员集合；其中1集合复用既有精确同输入几何，3838为本次实际融合。2560指定替换比较全部完成，不额外遍历所有团队两两配对。

|团队人数|请求数|完整几何／数值|主质量数值|来源时间全部可用|
|---:|---:|---:|---:|---:|
|6|960|866|813|101|
|8|960|892|806|36|
|12|960|892|785|5|
|16|960|894|776|0|
|合计|3840|3544|3180|142|

另外160请求无连接、136请求少于4个共识节点；全部保留状态。3544完整数值中364项不满足既有成员质量／同目标用途，只在诊断列保留。不能把人数间不同有效面板的均值直接解释为增人效应。16人组没有完整来源时间支持，不作团队耗时效率结论。

## 单人替换与跨人数控制

每个block含同一背景下的A锚点、B同类替换、C跨类替换三组。2560比较中，每对同图同k，实际共同成员严格等于k−1；同时验证声明背景等于实际交集。改变输入排列但成员集合相同不作为替换实验。

ABC及背景链由人员模块预先声明，背景按6→8→12→16嵌套，类别在目标建筑之外估计。入口不读取目标结果选人。不同k的同背景链、A-B与A-C的共享锚点、同一图片上的不同类别方案都不是独立样本；统计消费应按原设计配对并保留图片／建筑单位。

## 共识内容怎样变化

[exchange_pairs.csv](exchange_pairs.csv)保留V、节点数量、共享原观察的墙线对应变化、B8L2／D10、遗漏／外扩和R的有符号差（B−A），及共同完整／质量资格。

- `floor_geometry_equal`：两个有效底面坐标环序严格相同，允许循环起点及反向。
- `full_geometry_equal`：完整几何的底面XZ＋上下UV点对联合环序严格相同，允许循环起点及反向；UV横坐标按1024周期处理。任一完整几何不可用则留空。
- `node_content_equal`：共识节点上下UV坐标多重集严格相同，忽略节点名称、输入顺序及投票成员标签；不表示连接或支持票数相同。

这些判断没有数值容差，不将微小浮点变化自动归为“稳定”。变化大小仍看连续底面`floor_jaccard_difference`（1−IoU）和`floor_symdiff_h2`；节点数相同不代表内容相同。

一个供人工查看的反例：`SWAP000927`，Uw-09中固定15人，将同为相对Q×速度“较低且较快”的W010换成W012，两个16人组仍均为4节点，但底面V=0.46734，B8L2为14.41413→26.15130。该例按高V选择用于检查，不能用于估计总体频率或证明某人普遍更好。

## 消费入口与复现

- [逐请求结果](team_results.csv)、[唯一团队](unique_teams.csv)、[指定单人替换比较](exchange_pairs.csv)
- [输入与几何指针合同](CONSUMER_INTERFACE.json)、[状态](STATUS.json)、[核验](CHECKS.json)
- `input_snapshot.json`保存当前完整pool、成员及参考；`pools/<pool_id>/states.json.gz`中按`subset`查找`automatic`，包含节点、连接、底面和上下点对。
- `request_inputs/source_requests.json`是本次执行时的设计副本；`requests.json`保留全部成员数组和comparisons。

```powershell
python -m tools.thesis_main.analysis.worker_composition_fusion_20261018 prepare --requests research/workers/worker_exchangeability_20261018/TEAM_REQUESTS.json --out research/fusion/worker_exchangeability_fusion_20261018 --request-family exchangeability --skip-recovery
python -m tools.thesis_main.analysis.worker_composition_fusion_20261018 run --out research/fusion/worker_exchangeability_fusion_20261018 --jobs 3
python -m tools.thesis_main.analysis.worker_composition_fusion_20261018 verify --out research/fusion/worker_exchangeability_fusion_20261018
python -m pytest tests/test_worker_composition_fusion_20261018.py tests/test_wall_consensus_v1_process_20261017.py -q
```

14项定向测试通过；3840请求的人员／几何／参考／资格／时间缺失分母和2560单人替换全部核验通过。普通与门洞各1个16人组逆序输入从头融合，完整state与已保存结果一致。

旧快照保持原样，新增参数只用于指定独立输出；公共目录及展示接入由统筹维护。未进行全库无关回归或新增人工墙线身份认证，结论限当前8图和有限人员池。
