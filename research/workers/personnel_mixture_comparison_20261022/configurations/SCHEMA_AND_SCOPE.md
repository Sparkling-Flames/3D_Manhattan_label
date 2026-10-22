# 完整团队配比与成员分布：已完成范围与字段

本轮从 main `ef148c82df18582228b2d23837faa2659e79eba7` 接续，底层真人 **v2**。已完整读取 5,456 行目标楼外标签（22 折、两条件、两种方法），复用原 17 批 310,458 个唯一端点，并保存 13,406 个配比格和 616,676 行指标分布。分类保持冻结；本目录没有重新拟合类别，没有重跑既有整体方差/连续特征模型，**新增融合次数为 0**。

## 分析单元

固定图、Manual/Semi、候选人员域、分类、粗/细层级、团队人数及已登记背景面板。每个面板固定 D，在 12 个候选人中选 6 人，原有完整枚举为 924 个成员集合。完整团队类别向量为 D 加入被选 6 人后的向量；D 自身向量和可变块向量另列。

主表使用完整团队的每位成员均有相应目标楼外标签的支持，未知人员保留在覆盖账并排除出可分类团队。原 geometry_common/qt_common 更严格共同域作为明确标记，用于接续旧结果。全数据 ALL 类名不直接套用到目标楼外数字编号。

在本批实际团队中，主标签支持与对应旧共同域恰好一致；`common_domain_eligible` 仍逐团队保存，这个实际相等关系不能外推为全库特征资格相等。原 `panel_id` 内 `__v1__`／`__v2__` 指候选面板 1／2，不是底层数据版本，也不是旧批／新批标签。来源域以 `source_domain=all_formal/new_only` 为准。

## 已完成输出字段

- 身份：panel_id、pool_id、image、building、condition、difficulty、source_domain、n、method、tier、configuration_id。
- 构成：class_counts（完整团队）、background_class_counts、selected_variable_counts、variable_class_capacity、domain_class_capacity、parent_class_counts。
- 覆盖：理论配置数、每格理论成员集合数、实际唯一团队数、有效数、失败数、未知标签数；单个可评团队的成员波动记不可估计。
- 分布：各质量分项、记录总时间、结构与几何的有效分母、均值、p05/p25/中位数/p75/p95、标准差、IQR、极差。
- 关联：team_key → 精确人员、对应 panel/configuration、原端点批次；同一确定性团队端点只复用一次。
- 范围：有限面板的已知标签成员集合可以穷举；全候选人员域只枚举可行类别人数向量及组合数量，不冒称全池成员集合已评分。

每格有 **46 个指标**：45 个继承或按旧代码派生的质量、结构、几何、投票及失败量，再加记录总秒数。主指标为 B8L2；D10、底面 IoU、IoU3D100、底边球面距离、方向、均高与局部高度、遗漏／外扩、参考节点／边召回、实际转折／短边／近共线冗余、位置／边界／尺度与失败均保存。完整字段解释见 [METRIC_FIELD_GUIDE.csv](METRIC_FIELD_GUIDE.csv)。

`valid_n` 是该指标真实有效团队数；`missing_n` 是该格其余团队数。`teams`、`scorable_teams`、`failed_teams` 均保留。`failure=1` 表示冻结端点未完整可评，原因为少于四节点、连接不可用或底面无效，见 [ENDPOINT_STATUS_COUNTS.csv](ENDPOINT_STATUS_COUNTS.csv)。失败不编码为质量零分。每项只有一个有效团队时，均值与位置分位可读，但 `sd/iqr/range` 为缺失、成员波动不可估计。

时间只在全员记录完整、总秒数为正且只有一种来源的团队内统计；长表按 `time_source_kind` 分开。可比较字段是 `recorded_time_total_seconds`，原始 `source_time_total_seconds` 仅保留来源。时间是继承的标注记录总和，不能写成新测生产耗时。分位区间表示成员集合分布，不是置信区间。

## 文件与复现

完整文件索引为 [FILE_INDEX.csv](FILE_INDEX.csv)，读法与七个完整配比例为 [README.md](README.md)。入口依次为 `COMPLETE_COVERAGE_BY_METHOD.csv` → `PANEL_CONFIGURATION_CENSUS.csv.gz` → `CONFIGURATION_OVERVIEW_manual/semi.csv.gz` → `CONFIGURATION_DISTRIBUTIONS_manual/semi.csv.gz`。精确成员按 `TEAM_CONFIGURATION_LINKS` → `PANEL_TEAMS` / `TEAM_MEMBERS` 连接；逐折语义按 `LOBO_LABELS_USED` / `FOLD_CLASS_DEFINITIONS` 连接。

依赖 Python、pandas、NumPy、Matplotlib。恢复输入的包名、校验与下载身份见 [SOURCE_PACKAGES.csv](SOURCE_PACKAGES.csv)，实际端点批次见 `ENDPOINT_SOURCE_MANIFEST_manual/semi.csv`。恢复目录通过参数指定，不覆盖 main 的代码：

```bash
python build_configuration_distributions.py census --composition-dir /path/to/recovered/composition
python build_configuration_distributions.py aggregate --condition manual --composition-dir /path/to/recovered/composition
python build_configuration_distributions.py aggregate --condition semi --composition-dir /path/to/recovered/composition
python build_configuration_distributions.py rebuild-overview --condition manual
python build_configuration_distributions.py rebuild-overview --condition semi
python summarize_and_render.py
python finalize_files.py
```

`rebuild-overview` 只从完整长表形成便读宽表。保存采用一次性压缩字节写入、临时文件原子替换，并核对 gzip 尾与精确行数。全部格保存；七个代表面板也展示每一格，包括失败、反向／弱差异与单团队格。代表图选取属于内部探索解释，完整总体统计是其范围依据。
