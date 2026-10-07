# 来源与复现边界

本目录保存冻结选样、必要匿名几何输入、数值诊断、评分协议和结果接收规则。它是本轮精选归档，完整上游 ZIP 与所有原图没有再次复制进公开仓库。

## 来源层次

1. 现行输入沿用仓库既有[研究数据说明](../../docs/thesis_main/研究数据说明_来源预处理与用途_20261006.md)及[统一输入 manifest](../../analysis_results/research_input_20260929/manifest.json)
2. 最近质量交接与独立审核提供分项计算、案例解释和数值复现证据，来源收据保存文件名、角色、大小与 SHA-256
3. 本轮选样清单把源记录绑定到工作台记录，冻结最小坐标和参考版本；不重建上游统一包
4. 新人工评分属于新结果，必须与初始空白模板、历史六对比较及算法诊断分别保存

来源收据记录可识别的研究工件与哈希，不公开本机绝对路径、登录信息、原始聊天标识或人员真实身份。哈希用于核对同一文件字节，不证明语义判断正确。

## 坐标与连接

现有坐标是共享 x 预处理后的 1024×512 ERP 连续画布坐标 C，不宣称是未经处理的原始导出点。原始点身份顺序和最终环序视图是两套相关数组，必须使用各自配套的链接／映射。

- 原身份数组配原 links_zero_based
- 最终环序 points_1024x512 配最终环点对链接及 ordered_source_point_indices／ordered_source_pair_indices
- 原有确认环和默认环状态分别保留；能画出图形不能自动升级为已确认环
- 原 GT 与人工修订 GT 分开，参考对象 ID 与版本随每条比较保留

三维固定相机原点、地面 y=−1，以相机高度 h 为单位；面积为 h²，不是平方米。多个视角没有因此被注册到同一世界坐标系。条件重建、正交方向残差、拟合平顶残差各自有假设，不能冒称场景真实性。

## 缺失和可计算性

NA 保持为空并附原因，不补零。single-valued、camera_visibility 等限制按输入保留，某些条件几何有限不代表 ERP 或完整三维适用性已经解除。技术可算、候选资格、human_confirmed 与整体语义正确分别说明。

## 本目录实际文件与命令

[选择来源收据](provenance/selection_source_receipts.json)保存本轮上游 panel、records、指标表、计算内核及六张原图的哈希，原图只记录收据。[冻结工件清单](provenance/frozen_artifacts.json)记录实际纳入文件的大小与哈希。

36 份作答加 8 份参考，共 44 个几何对象。两份修订参考仅用于 Uw-09、yq-31；其余四图只有原参考。新评分默认参考为原版，不把不同参考下的同一份作答当两个人工样本。

较大的选样清单、冻结几何与 Three.js 库使用 [小文件分片](packed/manifest.json) 保存。必须先运行 `restore_packed.py`，脚本核对分片和原文件的大小／SHA-256 后恢复原始字节；不会改变几何、GT 或指标定义。原始工件清单中的哈希仍对应恢复后的原文件。

在本目录运行，无第三方依赖的检查命令：

```sh
python restore_packed.py
python replay_public.py --manifest data/selection_manifest.json --geometry data/frozen_geometry.json --ratings data/ratings_initial.json
```

该命令复核固定抽样、Q/R 映射、44 个几何对象、88 条接缝边和 88,076 个 ERP 采样点。几何检查结果不认证语义质量。

如环境已有 `requirements_metrics.txt` 中的 NumPy、SciPy、Shapely，可再运行：

```sh
python restore_packed.py
python replay_public.py --manifest data/selection_manifest.json --geometry data/frozen_geometry.json --ratings data/ratings_initial.json --metrics --vendor vendor
```

指标检查覆盖 48 条分参考比较的 624 个字段，NA 保持原状。`vendor/` 四文件原样保留计算定义，脚本只做数据读取与重放，不需要访问原图、人员身份表或外部服务。已有成功环境的版本记录见 [runtime_versions.json](validation/runtime_versions.json)。

## 可以复现的范围

完整选样应能从冻结候选池和种子重建；冻结输入应能逐条核验点坐标、连接、参考版本和哈希；数值字段须说明是原样复制还是本轮重算。具体运行命令、依赖和实际通过项目以随批脚本与验证记录为准，不把仅有报告摘要说成全流程已在公开小包重跑。

原图仅在受控工作台提供。离开原图，公开几何和数值可以支持部分算法复核，不能完成相同深度的视觉语义评分。上游完整材料的来源哈希与本目录实际已包含的文件必须分别列出，不能对精选目录套用完整 ZIP 的验收清单。

## 公开范围

公开仓库只保存匿名研究 ID、必要冻结坐标、数值结果、代码和协议摘要。真实身份映射、原始评论／聊天、原图、访问凭证、会话数据及完整重复 ZIP 不在本次新增公开内容中。私有工作台地址只作为访问入口，不赋予仓库读者原图或私有评分的访问权限。
