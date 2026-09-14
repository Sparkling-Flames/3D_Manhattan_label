# 648图图片画像工作包

本包用于探索图片特质、冻结模型反馈与人类标注结果的关系。**四个模型已完成本地提取；DINOv3访问申请被作者拒绝，未运行。本包不含A–E云端分析结论。**648图为画像覆盖；历史真人响应仅覆盖214图、26人、2501条canonical响应。

|本地交付|实际覆盖|
|---|---|
|HoHoNet、Bi-Layout、uLayout|各648图，每图4个水平旋转相位|
|DA3单图|648图，各6个独立推理透视面，四个完整768通道候选层|
|DA3同房辅助|316组固定配对，各2个拍摄位置、12个透视面共同推理|
|DINOv3|0图；648条受阻记录，无替代模型或随机权重|
|图片可见特质|648图盲评初筛，21图原分辨率复核；保留来源和局限|

覆盖及验证详见`output_coverage.json`、`local_validation.json`和各模型`validation.json`/运行记录。推理成功只说明输出可计算，不证明几何物理正确，也不证明能预测人类难度。

## 入口与使用顺序

1. 读取仓库AGENTS.md、本说明、`evaluation/metrics.md`及`evaluation/config.json`。
2. `metadata/images.jsonl`固定648个image_id；path仅用于本地定位原图，云端不需这些原图存在。
3. `metadata/`保留分类、空间关系、来源记录；`human/`保留逐份真实作答、参考、时间证据与历史Semi初始化。展示组不是独立物理房间普查。
4. 使用`evaluation/`固定划分。待定或不支持关系重叠的组件不进入同房评价；当前保守留房还排除了目标楼其他图，因此不是纯同楼跨房泛化。
5. `visual/`保存新增盲评可见证据及历史原文；人工、AI和未知来源分别保留。
6. `models/`保存每个模型的实际特征、预测及失败；五份可复制任务说明：[A 图片特质](prompts/A.md)、[B 模型反馈](prompts/B.md)、[C 模型层](prompts/C.md)、[D 同房几何](prompts/D.md)、[E 人员分类与组合](prompts/E.md)，输出分别写入`cloud/A`至`cloud/E`。

## 方法边界

- 冻结视觉模型，不训练视觉网络；模型差异、置信值、预测几何一致性均不是人类难度或GT。
- 固定保留数据source_split，并建议分层报告。多个布局模型使用MP3D训练；本轮人类目标留出不代表视觉模型没见过该图。具体权重的完整训练成员未核实，不能声称648图全部是视觉模型外部检验集。
- Manual与Semi分开，W011历史保留；W019/W026排除当前主分析。缺失、无效、低人数及观察内持续变化分别报告。
- 点数不同分开，支持簇至少两名不同人员；合理单人标法保留。最终收敛判据尚未冻结，本包不新造稳定人数目标。
- 六个透视面仅是一张全景的投影；旋转、重排和重采样均不增加独立图片或人员。
- 原图天底模糊区域仍可能产生模型深度。`projection/`提供向下纬度>60°的固定保守排除mask，仅作D的敏感性分析；它不是逐图真实模糊边界或可见性GT，也未修改模型输入。
- DA3单图条件为各透视面独立推理，深度尺度分别任意；辅助条件为两个拍摄位置的12面共同推理。比较时按面处理尺度，不直接相减深度。预测相机未施加已知六面共心/旋转约束；先报告同拍摄点相机一致性，再讨论可投影候选，5%预测深度一致不是物理对应验证。
- 本轮DA3配对相机不一致具有普遍性：每对六面恢复到全景坐标后的最大旋转差最小37.81°、中位138.31°、最大179.97°。因此当前12面联合预测不能当作已验证的房间重建或可靠信息补足证据。316对中180对满足主评价关系条件，另136对有待定/不支持关系重叠；关系合格也不代表预测几何合格。
- 标准化、降维、选层、调参、人员分型只能用当前训练侧。报告相同覆盖的配对比较及各模型全部覆盖。
- 可见特质为648图缩略图初筛，另有21张固定抽样原分辨率复核。连接空间和低对比字段接近常量；墙地/遮挡信息高度重复，反射/玻璃有漏辨。`visual/resolution_recheck.json`保留纠正，不把未复核图当作高清标签，不据此宣称精确边界可见率。
- 公共参考不是人工最终真值；历史Semi planned初始化一致不是参与者实际看过的证明，历史checkpoint仍可能未知。

## 预指定模型层及依据

论文给出有理由的候选，不证明哪层最能预测人类标注结果。候选在看本轮结果前固定。

|模型|候选|依据与限制|
|---|---|---|
|HoHoNet ep300 ResNet34布局|编码器stage2/4、水平压缩、水平精炼、共享latent、旧0°均值|[论文§3及§4.1](https://arxiv.org/pdf/2011.11498)区分编码器/压缩/精炼；原任务消融不能直接推广成人类难度。|
|Bi-Layout MP3D|Fc、enclosed/extended Fg、两头depth及height相关输出|[论文§4](https://arxiv.org/html/2404.09993v1#S4)。共享Transformer先new/enclosed后origin/extended；静态Global Context Embedding不是逐图特征。原模型最终ratio为两个原始ratio的均值，禁止GT挑头。|
|uLayout best_mp3d|全景压缩特征、最终SWG、上下边界|[论文§3.3](https://arxiv.org/html/2503.21562v1#S3.SS3)。该官方权重训练含MP3D与LSUN。|
|DINOv3 ViT-B/16|one-based block3/6/9/11/12 patch、最后CLS；全景及六面|[附录B.2](https://arxiv.org/html/2508.10104v1#A2.SS2)几何层比较来自7B，不能照搬层号到12层B模型。权重门禁失败时明确缺失。|
|DA3 Small|zero-based输出层5/7/9/11；深度、置信、相机、单图/同房条件|[论文§3.2](https://arxiv.org/html/2511.10647v1#S3.SS2)及[官方配置](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/src/depth_anything_3/configs/da3-small.yaml)。只在有效对应区域比较，新增视角是新增信息。|

## 布局模型数值字段

HoHoNet/Bi每图一个NPZ及同名JSON。NPZ不含Python对象，使用`numpy.load(path, allow_pickle=False)`。

- `yaw{0,90,180,270}__层名__global`：每通道均值后接标准差。
- `yaw…__层名__regions`：16个等宽方位区域，每区域同样为均值后接标准差。均已还原至原图方位；可在分析中对四相位平均，并独立研究相位敏感性。
- `legacy_single_phase_mean`：HoHoNet共享层0°按水平取均值，保留旧汇聚方法。本轮先用Pillow BILINEAR缩至1024×512；历史代码使用模型内Torch缩放，两者数值不保证相同。精确历史均值另见`history/historical_image_features.npz`的`legacy_mean_phase0`，不得混写，更不替代来源未核实的旧d_t。
- `yaw…__raw__字段`：未经后处理的浮点预测。HoHoNet bon为模型边界输出、cor为logit；Bi depth/new_depth为extended/enclosed水平深度，ratio为官方平均高度比；height_extended/enclosed保留平均前输出。
- `yaw…__post__字段`：官方后处理浮点角点或边界。角点为1024×512参考画布的连续像素坐标，横向周期；HoHo cor_id与Bi corners_*均上下交替。Bi高度统一采用官方ratio。
- JSON逐phase分别报告前向与后处理结果；失败不能补零。后处理回退警告保留，不能将回退当作未经限制的有效一般布局。
- 原始高维空间张量放本地`output/image_portrait_20260914_v1`，不上传。现代模型字段详见各自运行清单和脚本；不默认不同模型向量坐标可直接相减。
- DA3四层导出完整768通道（local384＋global384）；汇聚为1536维均值/标准差。官方辅助global流与后384通道完全重复，按清单索引可无损恢复。36列token按`array_split`分16段，前4段3列、其余2列，并非等宽或等角度区域。
- uLayout官方仅导出预测上下边界及四舍五入像素边界，没有官方预测角点。官方示例的GT corner不用于本包，训练忽略的corner logits也不能当作已训练角点置信；因此拓扑比较不能假定三个模型覆盖相同。
- `history/`保留214图旧d_model_feat及CPU复核值、历史参考特征、人员15信息组合及多组数候选；历史全数据拟合名单只可追溯，不能直接用于留出检验。旧d_t未找到可核实的历史分数与reference manifest，明确缺失。

## 复算与交付

```powershell
python -m tools.thesis_main.analysis.image_portrait.build_bundle --check
python -m pytest tests/test_image_portrait_bundle.py tests/test_image_portrait_common.py tests/test_image_portrait_layout.py -q
python -m tools.thesis_main.analysis.image_portrait.layout_models --model hohonet
python -m tools.thesis_main.analysis.image_portrait.layout_models --model bilayout --bi-root <本地官方Bi仓库>
python -m tools.thesis_main.analysis.image_portrait.modern_models --model ulayout
python -m tools.thesis_main.analysis.image_portrait.modern_models --model da3
python -m tools.thesis_main.analysis.image_portrait.modern_models --model da3 --multiview
```

前两项不需原图或模型权重；推理命令仅本地运行。模型依赖/权重位置由本地环境管理，云端不下载。代码和工作包在`codex/image-portrait-20260914`分支交付；不上传原图、权重、截图、ZIP。不修改正式Paper A合同、原始导出或采集安排。A–E任务完成后回本地复算关键表、复核视觉反例，再形成统一结论。
