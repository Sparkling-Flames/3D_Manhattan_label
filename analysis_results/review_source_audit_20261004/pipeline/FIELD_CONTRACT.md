# 绑定核查字段合同

本目录是一次只读审计的派生结果，不是新的输入真源、人员资格或研究方法合同。`check_bindings.py` 只用Python标准库比较已保存字段，不导入融合、几何或统计算法。

| 文件 | 记录单位与字段 |
|---|---|
| `summary.json` | 审计总览；`stages`分别保存冻结输入图片数、全部作答／参考数、已确认对象数及差异数；`roster_checks`计实际名单；`global_source_pair_observations`是两规则下保存证据条数，不能当独立样本数。 |
| `current_source_checks.json` | 当前源每对象一行；`id`是按完整当前源重建的匿名ID，`object_id`保留本地原身份；`checks`是布尔比较，`failed_checks`列出失败字段。不可用坐标不冒充通过坐标比较。 |
| `*_record_checks.json` | 每份冻结记录一行；`compared_fields`为期望字段数，`differences`保存字段、期望值、实际值及是否缺字段。`kind`区分人员作答和参考；没有差异为`[]`。 |
| `*_image_population_checks.json` | 每个冻结图片一行；比较其全部作答和参考对象集合与当前源同图对象集合，保存`missing`、`extra`。此处不是投票集合。 |
| `roster_gate_checks.json` | 每份实际分析名单一行；核对当前源既有Manual／独立／共识gate所决定的人员集合及顺序。`n`是该名单的作答人数。人员画像的公共24人名单应用于全部10图。 |
| `global_pair_observation_checks.json` | 每图×投票规则一行；`n`是全员候选分母，`assignments`为保存的输入身份数，`source_pair_observations`为保存供体点对数；两规则重复保存同批观察，不是新增人员。 |
| `anomalies.json` | 所有对象字段差异、名单差异与全员点供体差异的合并清单；当前为空。 |

所有点比较采用JSON数值逐值相等，不使用容差掩盖差异。匿名映射复用已声明规则：原对象ID全局排序后编号为`Rxxxxx`，原人员ID全局排序后编号为`Pxxx`。期望点顺序独立依据当前源的确认状态和默认x规则生成。

审计范围只到当前manifest及其`received_orders`。本目录不声称人工审核接入完整，不评估难度标签新旧，不把保存的`geometry_status`比较等同于本次重算几何，也不把`ring_confirmed`等同于标注质量正确。
