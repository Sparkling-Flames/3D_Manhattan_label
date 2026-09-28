# 独立研究复算入口与字段说明

阅读：[独立研究判断](独立研究判断.md)。结果属于探索，未替代正式方法。

## 复算

在仓库根目录依次执行：

```powershell
python -X utf8 -B -m tools.thesis_main.analysis.audit_supervisor_gt_sensitivity_20260922
python -X utf8 -B -m tools.thesis_main.analysis.audit_supervisor_gt_sensitivity_20260922 --wall-only
python -X utf8 -B -m tools.thesis_main.analysis.audit_supervisor_gt_sensitivity_20260922 --summarize
python -m pytest tests/test_supervisor_gt_sensitivity_20260922.py tests/test_shared_x_reanalysis_20260922.py tests/test_reviewed_manual_20260921.py -q
```

默认64次顺序，seed=20260922。先完整地面运行以生成GT审计，再运行二维支路，最后汇总。只覆盖本目录数值输出，不写原始输入、正式资格或其他分析结果。图表为相应CSV的静态绘图，不是另一次实验；正文人工综合研究判断，不由脚本自动重写。

## 输入及资格

通过`reviewed_manual_20260921.prepare`重建当前有效点和已确认审核规则，再用`shared_x_reanalysis_20260922.verify_raw`核对2444份原始导出。历史已处理点仍依据已有审核证据；没有把Pro输入包当成原始真源。上下绑定包括人工确认和既有条件唯一匹配，不冒称逐份人工认证。

GT从`data/mp3d_layout/{test,valid}/label_cor`和`export_label/groudTruth.json`读取，修订30张按既有1px点集容差及数量改变识别；不同点数不自动对应，不使用no-occ/HoHoNet GT。人工GT来源已获此前用户确认，本次没有重新判断其语义正确性。

描述2481份→无借点且有上下绑定2444份（33份绑定未定、4份借点不计独立计算）→排除既有明确错误2份→二维包络2份不可定义→两张GT经度重复导致35份无法按当前单值包络定义评价→最终2405份/238图。未纳入者仍留在原始数据及审计中，不能统一记作人员错误。

地面资格另算：2396份/240图通过本轮地面计算门，随后按各GT版本可评价性选择共同面板。不要求这些计数与二维相同；比较GT始终使用共同图/人。投影相机高度单位化，不进行逐份平移、旋转或尺度对齐。

模型读取Test的`output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34`和Validation的既有冻结`analysis_results/c2b_validation_static_20260802_v16/validation_prediction_txt`，来源沿用此前模型初始化审计。未把缓存当作新的模型运行证据；逐图源路径保存在诊断CSV。

## 字段合同

| 文件 | 行粒度与主要字段 |
|---|---|
| `source_verification.json` | 作答：id/source/task/annotation；原始点逐份核对 |
| `gt_source_audit.csv` | 图：split/changed/源路径/点对数/源环与角度表示是否可评价/失败理由/两表示IoU |
| `response_screen.csv` | 作答：地面资格理由和配对来源；空reason表示通过计算门 |
| `individual_quality.csv` | 作答×GT版本：IoU、面积质心距离/√GT面积；version区分original/revised与ring/angular |
| `consensus_curves.csv` | 图×GT版本×方法×k：mean_iou/q10/q90/draws；方法含≥半数、>半数和真人medoid |
| `fixed_panel_summary.csv` | panel/kmax/version/method/k；固定共同图面板的图等权均值 |
| `worker_effects.csv` | 人×GT版本：在各表示共同图/人面板拟合的人员效应；adjusted_loss越低表示相对误差越小 |
| `error_decomposition.csv` | 图×GT版本：有限池区域误差的shared_bias/disagreement，均除以该GT面积；因此跨GT分母可变，不能称人/图方差比例 |
| `wall_individual.csv` | 作答×GT版本：512×256墙带IoU、水平圆质心差（整圈单位）、有符号垂直差（图高单位）、圆均值集中程度 |
| `wall_curves.csv` | 图×GT版本×k：512×256、≥半数投票的mean_iou/q10/q90；GT不参与聚合 |
| `wall_resolution.csv` | 作答×GT版本：iou_512与iou_1024；只是逐份分辨率敏感性，不是全轨迹双分辨率验证 |
| `wall_worker_effects.csv` | 人×GT版本：同一二维面板的描述性加性人员效应及样本/建筑数 |
| `wall_unresolved.json` | 无法构造单值二维包络的作答/GT及理由；不补零 |
| `model_difficulty_diagnostic.csv` | 图×GT版本：模型TXT源路径、角点数、模型二维墙带IoU |
| `model_unresolved.json` | 5张模型预测经度重复，当前墙带定义不能唯一处理；84图曲线面板不含这些缺失 |
| `SUMMARY.json` | 地面支路的数据盘点、资格和参照边界 |
| `readouts.json` | 二维固定面板均值、GT敏感性、人员排序变化、分辨率差和模型诊断汇总 |

`changed`表示30张实质人工GT修订之一；`N`为该表示可用真人数；`k`为当前聚合人数。`q10/q90`是同图人员子集重放分位数，不是人群置信区间。单人曲线精确平均所有可用人员，不受64次随机抽样误差影响。不存在未观测人员补票。

圆均值集中程度接近零时水平质心方向不稳定；小于数值门1e-8时水平质心差为空。二维坐标区域使用经纬图像像素面积，不是球面等面积；地面面积指标也不是同一种量，禁止直接比较绝对分数大小。

`ring`保留来源列表连接；人工相邻上下点只做周期共享x。`angular`是明确的角度包络表示敏感性，并非恢复真实遮挡拓扑。对不能构环的人工GT不自动修环，不因此将对应图删除出二维研究。

## 验证与边界

相关6项测试通过；地面tile可复原每份区域面积，误差分解满足恒等式；所有个人IoU、质心地面距离与聚合IoU有限，IoU在[0,1]。未改export_label、import_json、active_logs或正式协议。没有新建任何正式入口。项目地图和README各增加一条探索性索引，未重写既有内容。

下一步是验证指标与标注目标的契合度、人员分数在留出建筑的稳定性、模型特征对真人曲线的外部预测；不是根据本轮结果冻结类别、权重或停止人数。
