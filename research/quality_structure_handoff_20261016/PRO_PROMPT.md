请独立研究我们的全景布局标注质量评分，目标是得到测量含义更准确、对真实缺陷反应更合理、可复现且能解释的研究工作方案。请结合数学建模、真实原图/作答/认可参考和已有人工粗核验作判断，不默认支持任何旧Pro或Codex结论。你可以质疑或替换现有分项、组合方式及参数，不必为了保守而只添加旁列诊断，也不要为了新颖强行换公式；具体研究路径由你决定。

【资料与原图】
GitHub仓库：https://github.com/Sparkling-Flames/3D_Manhattan_label
本次最新整理先提交了本地main，尚未推送；因此请同时读取我附上的 quality_structure_handoff_20261016.zip。包内按仓库相对路径保存最新增量，优先于GitHub旧文件；先读 research/quality_structure_handoff_20261016/README.md 和 ALGORITHMS_AND_DECISIONS.md，再读原始证据，不要仅从本提示词推测数据。ZIP根目录的 DELIVERY.json 说明基线与覆盖方式。

原图公开入口：https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/tag/quality-original-images-20261015
三个文件为 quality_original_images_20261015_01_of_03.zip、quality_original_images_20261015_02_of_03.zip、quality_original_images_20261015_03_of_03.zip，共263张原图。先取同页IMAGE_INDEX.csv，按image_id/image_code定位；263不是研究作答图数。直接下载前缀为：https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/
包内不重复原图。更多来源说明：research/quality_scope_model_handoff_20261015/EXISTING_DATA_SOURCES.md。

作答与参考以 analysis_results/research_input_20260929/manifest.json 和 tools/thesis_main/data_prep/consolidate_research_input.py 的 load_current_bundle() 为入口，应用已有预处理、环序、质量审核及范围增量。preprocessed_source.json/comments.json含Git LFS实体；不要把短指针当作完整数据。真实内容可从 https://media.githubusercontent.com/media/Sparkling-Flames/3D_Manhattan_label/main/analysis_results/research_input_20260929/ 下获取同名文件，并核实可读完整JSON。新参考和绑定见 research/scope_quality_rescore_20261016/，不要从旧GT自动推导当前采用范围。

【我真正想解决的问题】
我认可的GT绝大多数三维表现很好，小差错仍按GT正确处理；明确错误GT继续排除或使用已确认修订。我经常见到作答漏掉明明凸起的墙角/凹凸细节，整体范围可能仍像GT、也很正交，这不应被范围指标掩盖。
我特别认同这个问题：当前D衡量“作答自身有多接近一套正交轴”，并不等于“墙面结构相对参考有多正确”。请研究质量应该由什么内容组成，以及如何有效评价必要结构遗漏、伪结构、对应墙间关系、位置/范围和局部/整体高度。不要把结构完整性简化成点数一致，也不要把所有合法非正交结构当错误。
我也担心IoU、底边和方向等项重复响应同一变形，联合扣分过重。但这只是需要认真检验的问题，不是要求你必须证明重复、删除D或让分数整体上涨。即使同一原因造成多个指标变化，也需要说明它们是否反映独立的重要损害。

【已有算法与反馈】
当前倾向B8L2作为可调整的研究工作指数，A10和原WQ作对照，同参考现用3D IoU并列。令F=(1/I-1)+Sb²/32，d_c=1.5D²/(D²+c²)，H=(Hm/0.8)²+(Hc/0.25)²，Q=100/(1+M+H)，I=0时Q=0。WQ使用c=sqrt(37.5)、M=F+d；A10使用c=10、相加；S8使用c=8、相加；B使用c=8、M=sqrt(F²+d²)。C8使用c=8、M=max(F,d)+(sqrt(2)-1)min(F,d)，仅为Pro的组合形状对照。
C与B在“单项”及“两个数值相等的分项”情况下分别一致，不是单问题与双问题得分相等。sqrt(2)来自选用L2，不能反过来当作该倍率符合人类判断的证明。F=d未必表示主观同等严重；向量坐标正交也不证明指标独立或已去重。根号/2/三次根都不是我指定的必须比较清单，不要把本轮缩成再选一个范数。
我之前粗略提出墙面夹角、底面IoU、局部高度、整体高度的重要性顺序，但不是固定百分比权重；现在要重新核实各项测量的究竟是什么。

30份粗核验在 research/quality_ab_feedback_handoff_20261015/：原JSON、FEEDBACK_30_JOINED.csv、geometries.json、manifest.json；prior_AB含前版报告/源码/1145份历史评分。还有 research/quality_coarse_review_20261015/ 的上一批人工记录。题号跨批次不稳定，要按作答ID、图片、参考连接。我总体觉得B更符合体感，但不要求每例满足主观感觉，也没有给五档规定精确分数边界。最终反馈有看分数后的调整，不能冒称全盲评。
组合机制Pro的精简原文/实现/结果在 research/quality_combination_review_20261016/；独立审查在 analysis_results/quality_combination_independent_review_20261015/。尤其查看参考轻微非正交时，“偏离参考但更正交反而高分”的合成控制及其适用边界。原报告里的建议和局部数学推导要自行审查，不当成规范。

【目前数据状态与比较边界】
最新统计在 research/descriptive_statistics_rescored_20261016/：891份当前完整质量，manual828/73图，semi63/4图；WQ/A10/B8L2/现用均高棱柱IoU并列。3152份/259图是库存，不是全部可评分。1145、931、836、807为不同历史集合，不能混作当前完整样本。
39个新空间加2个修订GT涉及41图506份作答，90份已重算，84份新增进入统计；27个新空间仍缺完整参考，371份作答待空间绑定。范围是整个空间体的竖向切分，不是只换底面，也不意味着切分边界必然是实体墙。新参考完整性与作答目标绑定分别核实；不按最高Q/IoU择参考，不补造顶界，不修改原作答来提高分数。
只有1—2名有效真人的图片×条件来源池暂不纳入实证分析，等待补人；GT错误及既有图片/人员限制继续保留。合格来源池曲线的k=1/2节点不因此删除。普通、门洞交界、OOS按资格分层；困难不预定低分，门洞不预定不可标。现有难度中等均分低于困难不能作为强行改分或改类的目标。
后续还会增加人员、图片、质量版本。旧快照保留，新旧指标应在相同作答与参考的共同集合比较，新增覆盖另报。已有人员/融合/同房实证很多仍用原WQ，不能把旧结果改称B结果；融合稳定不要求必然接近参考。统一背景见 docs/thesis_main/四线程成果与论文主线核对_20261015.md、研究模型_人员图片与融合不确定性_20261006.md 和 CONTEXT.md。

【希望得到的成果】
我们已有文献研究，请先复用 research/quality_structure_handoff_20261016/LITERATURE_REUSE.md，以及 research/quality_scope_independent_review_20261015/literature/ 下的 literature-list.md 和 reading-notes.md，不从零重复搜标题。RoomFormer的参考角点/角度precision-recall有助于研究结构漏标，Boundary IoU提供局部边界与区域组合思路，Surface DSC提供误差容忍思路；这些是候选依据，具体实现、适用性和更好替代由你判断。借鉴评价器不意味着要训练新网络；论文中的阈值、房间匹配和像素尺度不能直接移植。有序尺度文献适合解释五档，不能替代几何测量。旧58条候选并非全部全文核验，不把摘要筛选当效果验证。
请给出有实质判断的方案：哪些现有测量值得保留，哪些需要改造或替代；候选公式为何表达我们要衡量的质量、适用条件和失败情形是什么。允许参考相关领域的结构/边界/几何评价算法，核对原论文或官方实现，讲清借鉴内容与本任务差别。
数学自洽、单调性、尺度解释、同几何冗余表示不变性等是必要检查，但不是人类质量效度本身。请把必要结构遗漏、轻微定位/角度偏差、参考自比、范围错误、局部高度等真实响应讲清楚；检验已有粗判断及适当独立案例，不以均分上涨、相关性高或所有例子拟合为成功标准。可以采用你认为更有效的模型，不以沿用B/C或维护旧结论为目标。
如需校准，仍按我预设的普通粗调→门洞交界条件细调，不让少量困难例子牵动全域；具体探索与实现步骤由你决定。给出可复现代码、明确版本、逐例/逐分项证据、同资格对照及建议，并区分实际执行、仅推导、未完成。若新方案有足够证据，明确推荐可试用版本；若没有，指出真正缺的证据及最少必要的人工核验，不止笼统说“继续保守沿用”。工具无可读返回时不要宣称已运行成功。
