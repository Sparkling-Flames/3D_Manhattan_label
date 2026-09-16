# Pro研究唯一入口｜2026-09-16更新

**本轮Pro目标：[图片信息与人员类型条件模拟的假说探索](prompts/PERSON_TYPE_HYPOTHESIS.md)。**用户现授权以目标为导向自主探索，具体方法由Pro选择；假说仍未证实，暂不纳入正式方案或改变当前采集。请先读[讨论备忘及既有原型审读](../../docs/thesis_main/人员模拟建议独立审读与最小验证方案_20260916.md)，其中详细设计只是备选，不是强制执行步骤。旧保守模拟及种子点数遗漏已复核；新版评分在该次审读中因工件下载401未验收，须核对实际可取得的后续结果。

本轮提示词已准备，尚未收到对应新研究结果。既有模拟代码／运行记录另在`codex/simulated-annotators`，与本分支图片工作包分开；参考时注明实际版本，不把分支名或工作流成功状态当作结果已经验收。39图本地审核工具已生成，见[入口与无图依据](review_workflow_20260915/key39/README.md)；审核和裁决由用户亲自完成，Pro只可提出问题，不能代填审核值。云端可读问题和数值，原图及展示缓存仅本地保留。

**最新：[多轮发现、导师讨论证据及DA3独立复核](../../docs/thesis_main/图片难度与收敛_多轮证据及导师讨论对照_20260916.md)。**按第二轮候选重新分析的A—E已接收，9张OOS几何已补回；[本轮原报告](cloud/image_links_after_review_20260915_v1/run_b02a97e2/REPORT_ZH.md)。原[审核入口与已执行提示词](review_workflow_20260915/README.md)保留；当前需补的是用户审核、精细图片证据与后续新数据检验，不要从旧提示词重复开始。

使用分支 `codex/image-portrait-20260914` 的最新提交。本文负责导航和版本状态；历史任务保留要求来源，不把旧报告里的“尚未执行”当当前状态。

后续两段Pro返回的[独立审读](Pro历史粗分类两轮独立审读_20260915.md)只评判定义、证据和推论，其中旧k范围及授权判断已撤回；新阈值作为工作候选，分类待用户审核，不称最终真值。

**既有研究背景：历史真实作答 → 候选难度粗分类 → 图片分类、特质、模型表示及人员构成的联系。**两轮历史研究和新候选A—E已接入，粗类待用户审核；新假说探索不必先冻结或预测这套粗类。旧实验difficulty字段停用；106张人工tag保留独立对照，稳定多簇允许稳定，困难候选按当前观察范围解释。

## 最短阅读顺序

1. [本轮目标提示词](prompts/PERSON_TYPE_HYPOTHESIS.md)与[假说及原型审读](../../docs/thesis_main/人员模拟建议独立审读与最小验证方案_20260916.md)，再读[多轮证据综合复核](../../docs/thesis_main/图片难度与收敛_多轮证据及导师讨论对照_20260916.md)：已有发现、证据限制、模型分别揭示什么。
2. [最新A—E报告](cloud/image_links_after_review_20260915_v1/run_b02a97e2/REPORT_ZH.md)及[复算说明](cloud/image_links_after_review_20260915_v1/run_b02a97e2/REPRODUCE.md)。代码`image_links_followup_*.py`；517个文件原样接入，33项测试在隔离副本通过。
3. [历史任务及授权边界](../../docs/thesis_main/历史作答难度粗分类续研任务_20260915.md)：k=2—8，原106tag与候选／用户审核分开，旧实验difficulty停用。
4. 按下表读取需要的数据；[106tag主空间研究](cloud/difficulty_tags_20260915_v1/mainspace_v1_9d19e4e7/REPORT_ZH.md)只在相应目标下引用，不能与新候选分数直接横比。

## 资料分工与状态

|资料|位置|本轮用途与限制|
|---|---|---|
|第二轮候选下的新A—E|[image_links_after_review](cloud/image_links_after_review_20260915_v1/run_b02a97e2/)|214历史图、239图×条件；与106tag并集285。未收到人工审核版；DA3物理信息补足仍未通过几何检查。|
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

历史第一轮结果在`cloud/history_difficulty_20260915_v1/`，第二轮在`cloud/history_difficulty_review_20260915_v2/`。本轮假说探索另选独立输出目录并更新入口，不覆盖这些已归档结果。若使用新粗类，保持独立字段，不覆盖原difficulty。

原包的 [REPRODUCE.md](cloud/difficulty_tags_20260915_v1/mainspace_v1_9d19e4e7/REPRODUCE.md)记录旧分析复算方式；[requirements-mainspace.txt](../../requirements-mainspace.txt)原样保存，仅供独立环境参考，本地没有据此修改依赖。若需从原模型NPZ重新汇聚，先明确目标ID和缺少哪些缓存，不能把缺缓存补零或悄悄只分析106图。

仓库已有两个difficulty数值传输工作流固定到旧数据提交，其中一个仅取106图；它们是历史传输记录，不是这轮最新资料入口。不要依赖旧工作流的固定提交获取新报告，也不要把旧106图工件当全部历史目标特征。原图、权重和检查截图留在本地，不生成新的ZIP。

## 2026-09-16本次整理交付

- 本轮目标提示词与假说备忘已同步；具体设计为参考，未将假说纳入正式方案。清理工作包首页的重复入口及“DINO尚未分析”等旧状态。
- 39图专项审核代码、问题和无图数值依据纳入研究交付；含原图的本地页面继续Git忽略，用户裁决仍待完成。
- 审核工具定向检查本地4项通过，JavaScript语法通过；独立无原图副本3项通过、1项本地显示资源检查明确跳过。浏览器交互仍未验收，不能由数值检查替代。
- 修正当前文档中的旧k范围、A—E执行状态和同楼概念；采集运营状态仅据已有用户确认补记，未调用线上接口。其他任务的英文追加池、池外盘点及其脚本未混入本次研究提交。
- 既有模拟分支代码保持独立；本次未重新训练模拟器，也未重新拟合历史A—E。Git提交／推送是否完成，以实际提交记录为准。

## 此前主空间包接收检查（历史记录）

- 最新主空间结果及其16个分析模块、1个测试文件共1,224个文件迁入原相对路径，103,700,437字节；逐文件内容与下载包一致，未覆盖不同内容。准确字节数以迁移清单为准。
- 本地测试：默认环境44通过、3项KNN对照因旧threadpoolctl读取OpenBLAS配置失败；仅在测试进程设置`sklearn.set_config(enable_cython_pairwise_dist=False)`后47项全部通过，没有跳过测试、修改数据或修改模型代码。
- 测试范围为`test_difficulty_stratified_followup.py`、`test_image_portrait_difficulty_tags.py`、`test_image_portrait_convergence_v2.py`。没有重拟合全量模型；更早v1已知复现限制仍见其接收审查，不因本次整理消失。
- 数值图表可以进入Git；原始图片、权重、检查截图、ZIP没有纳入这次提交。
- 主空间返回中`legacy/`的6份旧实验difficulty结果仅保留在本地归档，沿用Git忽略规则，不加入供Pro续研的提交；不复活这条已停用分析。迁移清单记录本地完整接收，不能把它误当远端逐文件清单。
- 行尾检查按原文件CRLF处理；7处已有日志行尾空格原样保留，其他暂存内容的空白检查通过，不为格式清理改写运行证据。

本次按研究版本和用途建立导航，保留原路径以免破坏脚本与报告引用。英文追加池、池外房间盘点和采集运营不是本次Pro研究提交的内容。
