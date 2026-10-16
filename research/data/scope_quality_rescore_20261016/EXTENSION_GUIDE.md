# 新人、新数据、质量算法与参考修订的接续边界

2026-10-16。本说明只登记已有入口及尚需核查的边界，不新增采集、正式资格、路由规则或评分公式。当前空间重评分与旧描述统计分别保存；原GT、作答、时间来源及已发布快照不覆盖。

## 1. 两种现有入口各负责什么

**空间重评分入口**读取难度`CURRENT.json`指向的实际详情，构造可追溯参考、逐作答绑定空间，再用冻结算法重评分并生成独立统计快照。现有命令：

```powershell
python -m tools.thesis_main.analysis.scope_quality_rescore_20261016 --out research/data/scope_quality_rescore_20261016 --stats-out research/statistics/descriptive_statistics_rescored_20261016
```

上述是本次快照的复现路径；同版本可以重建其派生输出，不能拿它覆盖不同版本的快照。改变输入、参考、审核或算法版本时，应给两个参数分别指定新的目录，保留本次目录。该入口不会自动生成所有后续图表或工作簿；这些交付仍使用各自已登记的生成入口。

**归一化批次／算法接入口**用于把已审核输入和已有评分按版本接入长表、覆盖与共同集合比较，不重新评分、不推断空间。已有基线配置为[SNAPSHOT_INPUTS.json](../../statistics/descriptive_statistics_20261015/SNAPSHOT_INPUTS.json)，完整字段见[原接入指南](../../statistics/descriptive_statistics_20261015/EXTENSION_GUIDE.md)。以下命令演示另起一个输出目录，不覆盖原扩展快照：

```powershell
python -m tools.thesis_main.analysis.descriptive_snapshot_inputs_20261015 --manifest research/statistics/descriptive_statistics_20261015/SNAPSHOT_INPUTS.json --out research/statistics/descriptive_statistics_extension_recheck_20261016
```

manifest中的CSV路径相对manifest目录解析。输出保留`INPUT_MANIFEST.json`和`SOURCE_LOCATIONS.json`，后者记录实际解析后的来源位置。输出目录必须为空或不存在。归档manifest不意味着把其相对路径改成相对输出目录。

## 2. 新人、新图与新批次

先经正式loader、既有预处理和必要审核，取得稳定`object_id/image_id/worker_id/condition`，再形成归一化记录／图片CSV。manifest的`batches`追加`batch_id,input_version,reference_version,records_csv,images_csv`即可接入身份与来源层；人数、图片数没有写死。不能为通过连接而换ID、把重复提交当新人，或把GT、修订GT、融合终点加入真人计数。

批次记录必须保存`reference_id,use_panel`，以及有效时间的`active_time_seconds,time_status,time_source,time_source_file,time_rule_version`。有效时间要求来源与规则明确、数值有限且大于零；缺失保持缺失，不用lead_time代替。新增来源仍需核对秒单位和记录绑定，不能因列名相同就自动认为来源相同。

同图的新人员可以加入；稳定图片轴（目标、难度、门洞、OOS等）冲突必须先解决。旧`all_answer_count`等派生计数不应阻止新增人员，也不作为新快照分母。人数门按图片×条件、稳定真人ID去重，补人以后重新检查GT／旧暂停、来源池人数及逐指标参考；人数达到3不是自动准入。建筑不等于房间，同房事实及时间匹配仍独立核查。

**当前空间重评分主线仍依赖固定历史库存、既有审核及旧质量来源的明确连接。** 归一化接入口接受新批次，不等于整个旧统计／重评分主线已经自动适配任意新增对象。真有新增库存时，需要先审核主线的历史集合连接和新对象来源，再运行新版主线；不得删除集合一致性检查来硬塞数据。

## 3. 新算法与长表比较

独立计算并审核新算法结果后，在manifest的`algorithms`登记`algorithm_id,version,source_csv,value_column,input_version,reference_version,direction,minimum,maximum`。算法CSV必须同时保存`object_id,image_id,worker_id,condition,reference_id`和结果列；已有输入／参考版本列也必须逐行匹配登记。批次的参考版本声明与算法版本声明相互核对，不能由算法自行宣布已完成参考审核。

接入口输出的`score_measurements.csv`保留算法ID、独立版本、完整身份、输入／参考版本、源文件、值列及缺失状态。允许部分覆盖或空值，不补0。只在相同对象、输入版本、参考ID、参考版本及相同用途层的共同非缺失集合比较；分别报告未覆盖和不完整配对。相同量纲不表示公式语义相同，跨版本差值不直接解释为人员进步。

适用性需随算法说明和结果保留，例如完整顶界要求、非正交是否适用、底面限定或虚拟裁切边界的解释。当前接入口只核对身份、来源、数值范围和既有用途字段，**不会替新算法认证几何适用性，也没有通用的逐算法适用性推理器**。不适用对象应保持空结果并保留原因，不应以0分或另一个空间的分数替代。

新增manifest项不会把新公式自动装进当前冻结评分器。需另做有明确版本的评分接入与关键验证，才能让主重评分表使用新公式；本次不改权重或调参。现用3D IoU仍是均高棱柱口径，不能据其口径倒推参考顶高。

## 4. 参考修订与多个空间

参考几何或审核改变时，保存新参考版本及源点对应，保留旧文件和旧分数，另起归一化快照。原GT与人工修订GT通常是版本关系，不能仅因存在两个对象就宣布两个合法空间。只有已登记、可追溯的空间确认才进入合法空间候选。

当前参考目录区分`current_target`、`version_alias`、`is_admitted_space_candidate`、完整几何可计算性及图片暂停。人工明确指定优先，已有空间族限制继续保留；仍不唯一的原作答留下最小缺口。不能按最高WQ、B8L2或IoU挑参考，也不能因为当前目标缺顶界就悄悄回退到另一个完整空间。参考可计算不解除GT错误、旧hold或作答限制。

新空间不因历史`top_pending`字面而永久阻断：严格同底面的完整参考可以保留原有上下对应与共线高度折点；原JSON明确顶平面、且新空间严格位于其完整域内时，可以确定性竖切。来源、公式、原始索引和新增裁切边必须留档。若P部分超出完整源域，交集只能作为诊断，不能冒称完整P；不自动snap、扩大容差、补高度，或把虚拟裁切边界称为实体墙。

当前归一化接入口一轮不合并重复对象的多个输入／参考修订；多参考诊断保留在本次空间目录和作答绑定表中，不通过复制对象行绕过去重。参考改后必须重新核对原作答空间，事后重评分也不证明原采集时间对应新任务。

## 5. 外部原始JSON与换机复现

原ZIP默认位置为仓库根目录 `data/external/label_data.zip`。`scope_reference_reconstruction_20261016.py` 与 `difficulty_user_revision_20261015.py` 共享路径解析；从任意工作目录运行都相对仓库根目录解析。可用环境变量 `HOHONET_SOURCE_ZIP` 指定同一份可信原ZIP的新路径，Python调用也可显式传给 `source_zip(path)`；构造模块已有 `ORIGINAL_LAYOUTS` 显式覆盖仍可使用。不存在 `--source-zip` CLI参数。

```powershell
$env:HOHONET_SOURCE_ZIP = 'data/external/label_data.zip'
```

读取每图原JSON的 `cameraHeight/layoutHeight/layoutPoints`，核对既定转换与原GT点坐标逐值一致，才采用明确顶平面。缺失文件立即报错；显式路径错误不会回退到默认位置或下载目录。不能用近似ZIP替代、由分数反推高度或跳过来源核验。

本次仅修改路径管理，**没有访问或搬移本机原ZIP**。本机须核对原件身份和SHA256，再将其保存在上述位置；保留原件。ZIP及本地回执目录受忽略规则保护，不提交原始大数据。既有来源记录和已发布快照不重写；新运行记录实际选定路径。

[参考目录](references/reference_catalog.json)保存已有构造证据，但主入口仍重新打开原ZIP，不能宣称克隆仓库即可完整重跑。完整清单与迁移步骤见[本机输入路径迁移](../../catalog/local_path_audit_20261016/README.md)。本指南从迁移前版本恢复至当前目录，统计输出位置也按现有分类目录修正。

## 6. 每次变更最少核查

1. **身份与输入**：新对象／真人／图片／条件是否稳定，去重及源坐标是否仍可追溯？新批次不是旧对象的无说明覆盖。
2. **目标与参考**：当前难度指针、目标范围、人工指定／空间族、GT错误与旧hold是否保留？新参考完整性和来源是否足够，未知是否明确留空？
3. **分母与适用性**：图片×条件人数门、作答限制和逐指标有效数是否分别报告？完整分数、底面诊断、时间来源及新目标时间有没有混用？
4. **版本与比较**：算法独立版本、输入／参考版本、相同资格集合是否一致？未覆盖、不适用及多空间未决有没有被补0、择高或隐式回退？

本说明未增加新框架或全链路自动接入承诺。真正新增数据／算法后，按实际改动做连接、去重、来源和关键边界验证，再更新独立快照、字段合同与报告入口。
