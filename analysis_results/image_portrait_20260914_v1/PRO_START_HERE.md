# Pro研究唯一入口｜2026-09-15整理

**当前执行入口：[两轮资料、审核工具、验证状态与新Pro提示词](review_workflow_20260915/README.md)。**第二轮已从用户指定路径接收；本地复用空间标本，原图不上传Git。早期2—8，粗分类须经用户审核。

使用分支 `codex/image-portrait-20260914` 的最新提交。本文负责导航和版本状态；具体研究要求只读下面第一项，旧报告里的“下一步”和旧提示词不覆盖它。

后续两段Pro返回的[独立审读](Pro历史粗分类两轮独立审读_20260915.md)只评判定义、证据和推论，其中旧k范围及授权判断已撤回；新阈值作为工作候选，分类待用户审核，不称最终真值。

**当前任务：历史真实作答 → 独立难度粗分类 → 图片分类、特质、模型表示及人员构成的联系。**旧实验自带difficulty字段停用；106张用户亲填tag保留为独立对照。早期k比较2—8（含8），稳定多簇允许稳定，困难候选按当前观察范围解释。两轮历史研究已接入，候选粗类待用户审核。

## 最短阅读顺序

1. [唯一现行Pro任务／完整可复制提示词](../../docs/thesis_main/历史作答难度粗分类续研任务_20260915.md)。按它实际完成粗分类和A—E，不止写方法建议。
2. [主空间研究的接收方逻辑复核](../../docs/thesis_main/主空间与历史粗分层逻辑复核_20260915.md)。重点为收益集中、DINO同房信息条件、中等档定义及S9机制解释。
3. [最新返回报告](cloud/difficulty_tags_20260915_v1/mainspace_v1_9d19e4e7/REPORT_ZH.md)及[原复算说明](cloud/difficulty_tags_20260915_v1/mainspace_v1_9d19e4e7/REPRODUCE.md)。报告有据可查，不等于其中所有推论已确认；原来的路径和代码保留。
4. 按下表读取需要的数据。只有需要追溯旧过程时才读v2，v1无需默认通读。

## 资料分工与状态

|资料|位置|本轮用途与限制|
|---|---|---|
|648图身份与分类|[metadata](metadata/)|`images.jsonl`、`spatial_history.jsonl.gz`；同房支持见`relationships.jsonl`。展示组不是独立房间。|
|真实作答和有效性来源|[human](human/)|`responses.jsonl.gz`、参考、Semi初始化、时间来源分别记录。新粗类由真实作答派生，不能由旧difficulty或模型输出代替。|
|106人工tag对照|[difficulty_tags_20260915_v1](difficulty_tags_20260915_v1/README.md)|保留用户原值，与历史粗类分别分析；这里的旧Pro提示词已经停用。|
|数值模型输出|[models](models/)|HoHoNet、Bi、uLayout、DINO、DA3。2026-09-15逐ID存在性检查：五模型特征文件各覆盖648图；这是文件覆盖，不代表每个几何输出均有效或云端已取回全部数组。|
|图像可见特质|[visual](visual/)|人工／AI／未知来源分开，审图结论以实际记录为准。|
|固定评价与口径|[evaluation](evaluation/)|训练侧变换、房／楼隔离；新增粗类须另记版本，不冻结正式收敛判据。|
|最新主空间返回|[mainspace_v1_9d19e4e7](cloud/difficulty_tags_20260915_v1/mainspace_v1_9d19e4e7/)|结果、逐图预测、内层缓存、敏感性和审图清单均已迁入；数值特征`cache/*.npy`在阅读包中缺失，不能直接声称可全量重拟合。|
|历史过程v2|[v2报告](cloud/pro_exploration/v2_convergence_e086b2b9/REPORT_ZH.html)|`process/`是已有几何和人员重排的派生产物；需要时对照human真源。不是新数据结果。|
|更早探索v1|[v1报告](cloud/pro_exploration/v1_e086b2b9/REPORT_ZH.md)|历史参考；部分复现问题见[接收审查](../../docs/thesis_main/Pro收敛续研复核_20260915.md)。不能直接复用其研究优先级。|
|本地审查证据|[mainspace_logic_review_20260915](mainspace_logic_review_20260915/)|原报告镜像、定向拆解、[迁移清单](mainspace_logic_review_20260915/migration.json)。与Pro自报验证区分。|

## 从哪里继续计算

返回代码保留在 `tools/thesis_main/analysis/image_portrait/`：`pro_*.py`对应v1，`convergence_v2_*.py`对应v2，`difficulty_stratified_*.py`与`difficulty_history_*.py`对应最新主空间返回。迁入不代表这些旧入口自动满足新任务；尤其`difficulty_stratified_prepare.py`仍围绕106张人工标签，新任务须按实际历史作答目标扩展输入。

新结果写入 `cloud/history_difficulty_20260915_v1/`，该目录已保存第一轮实际结果；第二轮另存cloud/history_difficulty_review_20260915_v2/。保留旧输出，不能直接运行旧报告生成命令覆盖已归档结论。新粗类使用独立字段，不覆盖原difficulty。

原包的 [REPRODUCE.md](cloud/difficulty_tags_20260915_v1/mainspace_v1_9d19e4e7/REPRODUCE.md)记录旧分析复算方式；[requirements-mainspace.txt](../../requirements-mainspace.txt)原样保存，仅供独立环境参考，本地没有据此修改依赖。若需从原模型NPZ重新汇聚，先明确目标ID和缺少哪些缓存，不能把缺缓存补零或悄悄只分析106图。

仓库已有两个difficulty数值传输工作流固定到旧数据提交，其中一个仅取106图；它们是历史传输记录，不是这轮最新资料入口。不要依赖旧工作流的固定提交获取新报告，也不要把旧106图工件当全部历史目标特征。原图、权重和检查截图留在本地，不生成新的ZIP。

## 本次整理检查

- 最新主空间结果及其16个分析模块、1个测试文件共1,224个文件迁入原相对路径，103,700,437字节；逐文件内容与下载包一致，未覆盖不同内容。准确字节数以迁移清单为准。
- 本地测试：默认环境44通过、3项KNN对照因旧threadpoolctl读取OpenBLAS配置失败；仅在测试进程设置`sklearn.set_config(enable_cython_pairwise_dist=False)`后47项全部通过，没有跳过测试、修改数据或修改模型代码。
- 测试范围为`test_difficulty_stratified_followup.py`、`test_image_portrait_difficulty_tags.py`、`test_image_portrait_convergence_v2.py`。没有重拟合全量模型；更早v1已知复现限制仍见其接收审查，不因本次整理消失。
- 数值图表可以进入Git；原始图片、权重、检查截图、ZIP没有纳入这次提交。
- 主空间返回中`legacy/`的6份旧实验difficulty结果仅保留在本地归档，沿用Git忽略规则，不加入供Pro续研的提交；不复活这条已停用分析。迁移清单记录本地完整接收，不能把它误当远端逐文件清单。
- 行尾检查按原文件CRLF处理；7处已有日志行尾空格原样保留，其他暂存内容的空白检查通过，不为格式清理改写运行证据。

本次按研究版本和用途建立导航，保留原路径以免破坏脚本与报告引用。英文追加池、池外房间盘点和采集运营不是本次Pro研究提交的内容。
