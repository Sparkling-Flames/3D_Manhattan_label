# 数据v2：已接入正式分析输入

> 2026-10-19后续人工审核更新：右侧BEV点序及连接核验正确。用户采用1粉、2粉、3粉、5蓝、6粉；其余两份按既有底面IoU优先、边界距离次序回退，结果4蓝、7粉。7份均已绑定，其中5份人工指定、2份仅为自动fallback暂定；8份旧不可用仍不绑定。当前完整诊断9363份、正式质量7302份（196图、60人），普通Manual5719份。原坐标、点序和N1状态不变。

用户已确认W100—W134为新增真人标注，并要求与v1合并为v2。库存为10439份＝v1 3222＋新增保留7203＋新增排除14；62个来源人员ID、261图。这里的数量不是质量或投票资格数量。当前完整研究入口见[总说明](../../../../docs/thesis_main/v2数据研究台与Pro推进_20261019.md)。

详见[收件与缺口核验](../../intake_W100_W134_20261019/README.md)。`inventory.csv`列为data_release、origin_release、object_id、image_id、image_code、worker_id、condition、disposition、quality_status。v1对象ID保留，新记录采用v2:new命名空间；v1排除不恢复，新批用户排除不计票。v1对象的quality_status只表示继承历史库存，不能解释为v2已重算。

`RELEASE.json`中membership相对于本目录，其余公开路径均相对于仓库根。base_effective_manifest指向现有处理修订，后续适配不得退回原导出覆盖人工删点。GitHub版本包括新增最小化记录、预处理坐标、逐份审计和匿名分析证据；原始Label Studio账号导出及含自由文本/身份字段的完整分析包留在本机，不进入云端索引。

`new_batch_preprocessing_manifest`已登记新增坐标副本：沿用v1周期平均x，7199份保留记录ready（6138份改变），4份配对异常阻塞；14份用户排除继续排除。旧v1有效坐标直接继承base_effective_manifest，不重新处理。预处理完成不等于质量/投票资格已授予。

当前状态为`quality_scored_personnel_exploratory`。完整分析包的本机说明不作为云端入口；公开数据范围见本页和[接入核验](../../intake_W100_W134_20261019/README.md)。11图新增Manual341份以及b8cTxDM8gDG-04的暂停继续保留；原34份缺口已核查：19份补齐唯一参考身份但保留质量限制、8份旧不可用、7份新作答已采用5份人工选择和2份授权fallback；缺失不补零。当前评分绑定见`research/quality/quality_workers_v2_20261019/CROSS_MODULE_INPUTS.json`。

v2评分及描述性人员分类已完成：9363份完整诊断，7302份／196图通过正式质量资格。融合未重跑。[本轮说明](../../../quality/quality_workers_v2_20261019/README.md)。重现v1时显式指定10月18日有效manifest，历史v1统计消费者固定读自己的release，旧结果不改标签冒称v2。
