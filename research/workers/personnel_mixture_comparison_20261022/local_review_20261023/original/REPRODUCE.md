# 实际运行代码与恢复方式

基线：`Sparkling-Flames/3D_Manhattan_label@ef148c82df18582228b2d23837faa2659e79eba7`。数据是真人v2，研究阶段v3不改变数据版本。建议在该提交的独立工作目录接入本轮文件：**阶段02解压到`research/workers/`，阶段03A、03B和核心包解压到仓库根。** 阶段02早期采用研究目录名作为包根，03和核心包使用仓库相对路径，这一解压位置差异保留在交付索引。不需要改GT、资格、环序、B8L2/D10或融合门槛。

实际环境：Python 3.12.14、pandas 2.2.3、numpy 2.3.5、matplotlib 3.10.8。各模块以脚本位置推导仓库根路径，不依赖本次绝对scratch目录。所有关键结果均已保存，阅读和下列重聚合不需要调用融合。

## 1. 最少下载即可读取或重聚合

完整配比与现有端点在阶段02；严格ABC和旧n20在03A；有限配对背景统计在03B；标签、难度和主报告在核心包。对应的确切文件、字节和SHA256在各ZIP的manifest及最终交付索引。无需同时取已被完整阶段覆盖的01检查点。

在仓库根目录运行（命令之间逐条执行）：

```bash
python research/workers/personnel_mixture_comparison_20261022/integration/build_recommendation_table.py
python research/workers/personnel_mixture_comparison_20261022/difficulty/analyze_exchange_difficulty.py
python research/workers/personnel_mixture_comparison_20261022/configurations/build_configuration_distributions.py rebuild-overview --condition manual
python research/workers/personnel_mixture_comparison_20261022/configurations/build_configuration_distributions.py rebuild-overview --condition semi
```

第一条只读已交付的完整比较和精确成员。难度重聚合另外使用基线仓库现有的 `research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/image_scope_support.csv`，沿用当前人工难度、门洞和目标资格。

有限配对的全部无向机会可从交付端点再枚举，计算量大于读取汇总，但不涉及融合：

```bash
python research/workers/personnel_mixture_comparison_20261022/exchanges/compare_finite_panel_pairs.py --condition manual
python research/workers/personnel_mixture_comparison_20261022/exchanges/compare_finite_panel_pairs.py --condition semi
```

实际n来自原D+6，m按集合差计算。父内细分使用版本2合同：共同D、m和完整粗类向量同时固定。不要改回只在每对内部固定父类的旧临时实现。

## 2. 从已接收closure请求重新生成严格结果

基线main已经实存101,092个完整端点及四批请求，代码直接读这些路径：

- `research/workers/personnel_exchange_closure_20261022/delivery/endpoints/ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz`
- 同目录 `ALL_REQUIRED_ENDPOINT_GEOMETRY.csv.gz`
- `manual_joint/EVENTS_REGISTERED.csv.gz`
- `manual_joint/phase_b_highq_slower/EVENTS_REGISTERED.csv.gz`
- `structure/ALL_EVENTS_REGISTERED.csv.gz`
- `semi/EVENTS_REGISTERED_ALL.csv.gz`

后四项相对 `personnel_exchange_closure_20261022/`。使用main现有几何，勿用旧下载包的过时元数据覆盖。

```bash
python research/workers/personnel_mixture_comparison_20261022/derive_frozen_expression.py
python research/workers/personnel_mixture_comparison_20261022/exchanges/compare_saved_exchanges.py
python research/workers/personnel_mixture_comparison_20261022/exchanges/complete_comparison_products.py
```

第一条只从实际已存坐标派生转折、短转折边和近共线冗余；参数及源SHA在 `inputs/CLOSURE_ENDPOINT_EXPRESSIONS.json`。它不改几何也不改质量。严格结果原生量均从标量库存连接，失败保持原status和缺失Q。

## 3. 从历史源包重新生成有限配比和直接AC

历史有限设计从实际保存的源包恢复，而非根据报告数字造表。源包按原路径解压形成一个 `composition/` 目录，其中有 `PANELS.csv`、`DESIGN_TEAMS.csv.gz`、`PANEL_MEMBERSHIP.csv.gz`、17个常规端点批次及large/pure批次。来源文件名和哈希见 `SOURCE_RECOVERY_INDEX.json`；必要源哈希还在 `configurations/ENDPOINT_SOURCE_MANIFEST_*.csv`。

将命令中的 `/path/to/recovered/composition` 替换为已恢复目录：

```bash
python research/workers/personnel_mixture_comparison_20261022/configurations/build_configuration_distributions.py census --composition-dir /path/to/recovered/composition
python research/workers/personnel_mixture_comparison_20261022/configurations/build_configuration_distributions.py aggregate --condition manual --composition-dir /path/to/recovered/composition
python research/workers/personnel_mixture_comparison_20261022/configurations/build_configuration_distributions.py aggregate --condition semi --composition-dir /path/to/recovered/composition
python research/workers/personnel_mixture_comparison_20261022/configurations/summarize_and_render.py
python research/workers/personnel_mixture_comparison_20261022/configurations/finalize_files.py
python research/workers/personnel_mixture_comparison_20261022/direct_ac/analyze_direct_ac.py --composition /path/to/recovered/composition
```

本轮交付已包含其全部结果及所需精确成员/标量；不为重复交付而再次打包约184MB历史原包。直接AC所用3,863个必要标量/几何端点在本轮阶段02已存在。

## 4. 旧n20的完整事件恢复

实际恢复了165个输入分片，269,814 Manual＋1,517 Semi，保留Y/Z可重叠原设计；每队集合与实际m/r重新核算，事件不缺行。原源包恢复索引和每片行数见 `exchanges/legacy_n20/SOURCE_SHARDS.csv` 与恢复总索引。

```bash
python research/workers/personnel_mixture_comparison_20261022/exchanges/compare_legacy_n20.py --source /path/to/recovered/n20
```

03A已包含完整窄列事件、全部结果和来源定位，使用它们即可重聚合父内m响应，不必再次取约591MB历史原ZIP。窄表保留研究必需的精确成员和全部比较结果，不重复附带每行大段相同几何。

## 5. 原答与案例

`difficulty/analyze_difficulty.py`读取基线真实行为、历史特征、冻结标签与scope难度；`analyze_exchange_difficulty.py`使用本轮完整逐图换类结果；`analyze_qdown_condition.py`定位pa4-18的中位附近事件，保存100条图内事件、三队端点和26位原答。

`difficulty/render_7y13_background.py --cache /path/to/recovered/composition/batches/batch_001`将同候选924条路径的正向、近零、负向代表定位到既有几何，并读已保存的真实Release原图。案例目录已经保存六个必要端点、37位原答、参考、坐标、分项、图像和来源，无需重新融合。pa4本轮仅绘制实际原答/融合BEV，未新取得其原图；不把别的旧事件ERP冒充本次三队。

`integration/reused_cases/copy_selected_cases.py`只从main的closure机制档案选取必要结构、门槛失选和invalid_floor的少量证据，保留源文件SHA；没有重放或新增人工语义裁定。

## 6. 聚合、空值与完整性

- 不将失败Q填0；每分项使用真实可计算分母，所有尝试进入失败统计。
- 记录时间要求来源一致、团队每人已知，缺失不补0；严格表使用先平均log比再取指数，直接AC另保留算术相对变化，不混排名。
- 事件先去重/背景等权，继而图、楼；大量复用端点不当独立样本。同D只允许一个目标块时，目标内波动是NA。
- 完整配比格以完整团队人数向量分组，D向量另存；细类父内对照固定完整粗向量。
- 所有交付gzip已读至EOF、图像已完整解码、ZIP已CRC验证；`COMPLETE_FILE_INDEX.csv`列实际文件。通过保存不是证明所有方法都有效，结论仍由具体效果和支持决定。

本轮对照范围已完成。全人员池所有背景/组合、所有进入顺序、Semi困难图新采集和新同房预测没有被悄悄计入完成范围。
