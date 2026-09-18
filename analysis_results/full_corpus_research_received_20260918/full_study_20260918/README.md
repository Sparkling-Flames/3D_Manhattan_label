# 全量标注分簇、模型候选与不确定性｜2026-09-18

## 结论与边界

当前应保留环序匹配等几何候选，把人工局部事件作为解释/验证层，不把某个默认参数失败等同整个方法失败，也不把局部事件方案称作已胜出。主研究对象是给定图像、规则、信息和人员构成下的真实布局标注分布。范围、局部表达、顺序/对应与定位不是同一个目标。

本轮实际执行全量分簇、模型候选对照和留建筑预测检查；未新增真人、未重新训练深度模型、未恢复暂停的虚拟人员生成、未逐图重新盲审全部214张图。main/原始导出/人工裁决/派发任务未修改。

## 最新来源与SOP

固定main d3477e700082c0a8482f1ffabd9dcc5649c9754d；历史包c61930ecac1a20c99cd0b73c10aa7e10bd9e65ac；上一轮研究58af46c5fdb250dab42a99d930358d1986a13abd。main的9月18日交接优先于下方旧状态；22张高人数图统一追加15人的建议已撤回，922份不是当前已完成/待直接派发的新增量。648张分类图片不等于有人类标注的214张。

权威处置：analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz、confirmed_processing_audit.csv及用户决定。已逐ID核对2501份，effective_points、processing_status、calculation_included、imputed_point与本次human/responses完全相同。原始点及18个导出来源保留；没有复活旧实验difficulty或Paper A路由方案。

## 全量口径

2501条canonical；先排除W019/W026的113条，保留2388条、24人、214图、239图片×原始条件单元。W011历史保留。

2364条可做配对几何；另17条可以做无序点集比较，但不能可靠配对；7条点集也不可用或已确认排除。配对几何分条件为Manual1620、Semi532、OOS212。OOS不因规范不接受而删除。库存无辅助1843与本轮配对无辅助1832不是同一个分母。

排除W019/W026后已确认处置：4条删点、2条补点、1条歧义整份排除。15条未确认奇数保持原状。effective=null不回填raw。两份补点（W030/q9-13、W037/uNb-47）参考了同图别人完整历史，不能当完全独立原始点；已单列no_borrowed_imputation，恢复原9/11点后仍用原点集参与OSPA，不把人从行为研究中删除。

P1 Project28 task3081的W002坐标百分比28→28、W018越界点21→20，按包中pending_export_update另行重算，不混入主版本。input_version_changes.csv、input_version_partition_sensitivity.csv与pointset_input_version_memberships.csv保存各版本。

## 全量分簇结果

18个配对配置，42552行方法×成员、20371成对特征。另有6种OSPA30配置（cut3/6/9度、有/无点数门）覆盖2381份。球面/立体角视图有单独的适用范围。组合、参数和成对数据不增加独立人图数量。239单元中21个只有1份配对几何，218个至少2份、73个至少8份。

|方法|总组数|单人组|
|---|---:|---:|
|A0旧点数门+墙带0.10|882|509|
|A1无点数门墙带0.10|743|366|
|A2局部边界|983|602|
|A3环序cap20 cut8|1394|1007|
|A3环序cap20 cut10|1154|727|
|A3环序cap20 cut12|887|473|
|A4局部尺度环序|910|488|
|A6局部尺度谱图|428|65|
|A7软角点密度+墙带|1068|653|

这些是配置的结果，不是语义准确率。HDBSCAN未分配保持独立标记，不作为确定语义模式。不能按簇少、单人少或曲线平选择“更正确”方法。

X7-19 Manual：A3 cut8精确得到{W011,W015,W033}/{W034}/{W037}，cut12全并。因此默认失败不足以否定环序类方法。另一方面，W015与另外两人的前缘/后连接计数相同，不代表顺序/对应也相同；旧导出不保存最终墙连接，不可由x排序推断人的连接意图。“存在性分组”和“完整结构/几何异常”须用不同评价关系。

## 模型输出实测

实际读取214图×HoHoNet/Bi/uLayout三族642份冻结NPZ。主要比较yaw0，其他3个yaw只形成旋转敏感性。Bi两种角点候选、HoHoNet一种、uLayout密集边界。uLayout官方wrapper的corner是GT，导出明确排除；未使用第二返回的角点logits不是校准/训练好的角点置信度。本轮未用它伪造预测角点。

使用同一球面墙带1−立体角IoU。人类可投影2299条，全部四候选共同可用2294条；其余人类在别的视图保留。阈值.05/.10/.20均保存，不是语义容忍度真值。

Bi双头距离中位数0.002395；214图中175图小于探索阈值0.02。2299条真人在cut0.10时，同时兼容两头1566、仅enclosed138、仅extended51、两头都不兼容544。不能把both/neither强制二选一，更不能命名两类人。

7y3-08的双头距离0.000346，但22份可投影OOS作答的平均相互距离约0.16947。这直接否定“模型两头相近足以说明人类没分歧”；不证明这些人类差异均合理。

共同2294条，Bi两头覆盖1755（76.50%），HoHoNet+uLayout边界两候选覆盖1773（77.29%），四候选并集1883（82.08%）。覆盖是几何接近，不是准确率；增加候选必然不降低并集覆盖，不能把四对二改善单独当作方法优越。四候选仍有411条未覆盖，需保留模型外表达/误差。

## 新的模型信息预测检查

115张至少5名可投影Manual作答的图、18个建筑。目标为历史真人平均成对立体角墙带距离。外层留一建筑，内层按建筑4折选Ridge正则；插补/标准化/选参只用训练侧。未把目标图真人几何作为输入。

|输入|外层MAE|
|---|---:|
|训练建筑总体均值|0.042295|
|Bi双头距离|0.037943|
|模型角点数量|0.034907|
|模型点数+模型间距离|0.031156|
|再加旋转变化|0.031211|

这支持模型反馈对真人几何分散度有候选预测价值，不是语义类/人数终点/新人员预测。目标受当前人群及可计算选择影响；留建筑只针对下游回归，不宣称预训练模型从未见有关图像/建筑。DINOv3和DA3本轮没有新拟合，不能由此声称其增益已经测过。

## 后续使用与论文方向

建议结构是：模型提供带来源的候选，真人提供频率，几何及未解释差异保留在完整结果中。先建立不由模型投票决定的真人分布，再检查Bi等候选覆盖哪些、遗漏哪些。允许一头覆盖多个几何组、两头覆盖同一组、模型候选没人支持、真人表达未被任何候选覆盖。

局部范围和细节可以组成联合表达，但同一个局部事件计数不等于完整顺序/邻接。手写ROI适合固定图的测量，但必须测未参与开发的作答及人工成本；疑似偏出ROI/对应不清时不能一概当零。所有未编码的几何与局部新差异需要实际残差监测，仅保存原点不等于指标会检测它们。

模型用法：HoHoNet给结构候选；Bi给范围政策候选，不给真人概率；uLayout给边界；DINOv3全局表示用于跨图条件预测，局部表示可探索对应。同图拼接相同全局向量不能直接区分该图各作答。DA3原多视角设置未通过9月16日已知相机几何检查，特征/相对信息与物理真值必须分开；同一全景的六个cubeface不是6次独立拍摄。

收齐后，冻结检验集与输入版本；人员画像从目标房间/建筑外形成；比较图像-only、人员-only、加性和有限交互；同人数比较构成，固定构成研究人数增长。前k人的预测不得读目标图余下人的簇中心、事件或修复信息。群体稳定允许非零熵，同时检查模式比例、对应/位置与未解释新差异；质量上限另需明确reference，不由分布平坦推出。

可辩护的贡献方向：①具有顺序/对应与残差的结构化分歧测量；②模型候选和真人分布的覆盖与失配；③真实人员构成下证据需求的可复现变化。第③项仍需新的实测，不包装成本轮已完成。Bi多解、保留分歧、按人群构成建模各自已有文献，不能单独称创新；新价值应来自完整布局任务中的可验证关系与迁移证据，而不只是阈值和ROI。

## 文件、复现与验收

code/完整数值入口：full_corpus.py、pointset_and_versions.py、model_linkage.py、model_prediction_check.py、source_validation.py，加上实际调用的三个旧表示/聚类helper。results/包含逐份成员、成对距离、输入版本敏感性、模型覆盖、外层预测、内层选参与检查日志。

GitHub Actions 35329148252已在独立运行环境成功执行并提交。取回输出后，24份共同CSV与本机计算按排序对照通过，绝对/相对容差1e-9；不是独立语义验收。原始点处置逐ID一致性和排除不变性测试已执行。

交付另有全量交互图册：239单元、27种可选结果视图、原始/有效点、模型叠加；39重点图有嵌入缩略图，其余175图原图需联网按固定提交读取。浏览器实测通过下拉、X7 cut8/cut12、模型/原始点切换等；不等于逐点审完2388份。完整报告、图册生成代码、补充误差比较和离线重算输入在用户下载包中。下载包不含权重或字体。

当前工作流复用前序临时模型artifact，过期需重新运行输入提取并更新run-id；离线复算包已含全部必要数值数组，不依赖artifact有效期。研究中的原始数据与main始终保持未修改。

## 主要原始文献

Tsai, Yu-Ju et al. (2024). No More Ambiguity in 360° Room Layout via Bi-Layout Estimation. CVPR,28056–28065. https://arxiv.org/pdf/2404.09993

Gordon, Mitchell L.; Lam, Michelle S.; Park, Joon Sung; Patel, Kayur; Hancock, Jeffrey T.; Hashimoto, Tatsunori; Bernstein, Michael S. (2022). Jury Learning: Integrating Dissenting Voices into Machine Learning Models. CHI2022. DOI10.1145/3491102.3502004. https://arxiv.org/pdf/2202.02950

Uma, Alexandra N.; Fornaciari, Tommaso; Hovy, Dirk; Paun, Silviu; Plank, Barbara; Poesio, Massimo. (2021). Learning from Disagreement: A Survey. JAIR72:1385–1470. DOI10.1613/jair.1.12752. https://www.jair.org/index.php/jair/article/download/12752/26751

Yan, Yan et al. (2010). Modeling Annotator Expertise: Learning When Everybody Knows a Bit of Something. AISTATS, PMLR9:932–939. https://proceedings.mlr.press/v9/yan10a/yan10a.pdf

Rahmathullah, Abu Sajana; García-Fernández, Ángel F.; Svensson, Lennart. (2017). Generalized Optimal Sub-pattern Assignment Metric. FUSION,1–8. DOI10.23919/ICIF.2017.8009645. https://arxiv.org/pdf/1601.05585
