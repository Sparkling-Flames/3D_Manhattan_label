"""Report generator using executed tables; no new statistics or visual inference."""
from pathlib import Path
import json,base64,html,re
import pandas as pd
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_prepare import O,B,ROOT

def table(df):return df.to_markdown(index=False,floatfmt='.4f')
def main():
 counts=json.loads((O/'audit/execution_counts.json').read_text());s=pd.read_csv(O/'results/all_candidate_scores.csv');pair=pd.read_csv(O/'results/paired_increments.csv');d=pd.read_csv(O/'images/labels106.csv');cp=pd.read_csv(O/'controls/matched_intercept_scores.csv');hs=pd.read_csv(O/'historical_bridge/confirmation_sensitivity_counts.csv')
 coarse=pd.crosstab(d.scene_category,d.difficulty_tag).reindex(columns=['简单','中等','困难'],fill_value=0).reset_index();coarse.columns=['来源大类','简单','中等','困难']
 mainc=pd.crosstab(d.main_function_primary,d.difficulty_tag).reindex(columns=['简单','中等','困难'],fill_value=0).reset_index();mainc.columns=['AI主空间首句派生功能','简单','中等','困难']
 fm={'selected__existing':'已有四模型/反馈：训练侧选层','selected__feedback':'低维模型反馈：训练侧选择','selected__dinov3':'DINO：训练侧选层','selected__existing_plus_dino':'已有信息＋DINO：训练侧混合'}
 scored=[]
 for feat,base,name in [('baseline__global','none','总体标签频数'),('baseline__coarse','none','人工大类频数'),('baseline__main','none','主空间功能频数')]:
  q=s[(s.feature==feat)&(s.baseline==base)].iloc[0];scored.append(dict(方法=name,拟合='整体',RPS=q.rps_mean,准确率=q.accuracy,平衡准确率=q.balanced_accuracy))
 for design,label in [('pooled','整体＋主空间基线'),('within_coarse','大类内分别拟合'),('within_main','主空间功能内分别拟合')]:
  for feat,name in fm.items():
   q=s[(s.design==design)&(s.feature==feat)&(s.baseline=='main')&(s.algorithm=='ridge')].iloc[0];scored.append(dict(方法=name,拟合=label,RPS=q.rps_mean,准确率=q.accuracy,平衡准确率=q.balanced_accuracy))
 method_scores=table(pd.DataFrame(scored))
 h=hs[(hs.cut==.1)&(hs.rule=='G10_geometry')&(hs.late_h==19)&(hs.process_tier=='early_one_or_two_supported_modes')].pivot_table(index=['condition','confirmation'],columns='early_k',values='images').reset_index()
 room=pd.read_csv(O/'rooms/same_room_tag_scores.csv')[['feature','n_images','n_components','rps_mean','accuracy','hard_recall']]
 keys=['within_main existing[main,ridge] vs baseline__main','within_main existing vs feedback [main,ridge]','within_main dinov3 vs existing [main,ridge]','within_main existing_plus_dino vs existing [main,ridge]']
 pp=pair[(pair.scope=='all')&pair.comparison.isin(keys)][['comparison','n_images','rps_delta','rps_delta_lo','rps_delta_hi','accuracy_delta']]
 text=f'''# 主空间分层、模型表征与人工难易判断
## 106图实测，以及历史收敛粗分层的独立后续探索

版本：`mainspace_v1_9d19e4e7`。日期：2026-09-15。研究长期主线仍为标注不确定性及随真实人数增长的收敛。

## 1. 核心结论与证据等级

**你的分层建议得到有条件支持：把主空间当成一个可单独检验的分层因素，比把全部图片混在一起更有解释价值。但“分得越细越好”“DINO越深越能预测难易”“簇越多就越不能收敛”均不受本轮证据支持。**

本轮首先完成106张原人工难度标签的图片侧研究，随后才对历史收敛轨迹进行另一套粗分类探索。两种标签没有混合。人工难易判断是研究对象，不是已验证的几何质量、真实难度或收敛状态。

已有模型信息在主空间功能内分别拟合，留楼RPS为0.0682；同样分层、没有任何模型变量的截距基线为0.0950，配对差−0.0268，楼级重采样95%区间[−0.0679，−0.0040]。这是一项图片条件与既有难易判断有关的探索证据。进一步比较高维已有表示与仅低维模型反馈，差−0.0057，区间跨零；因此不能把全部增量归功于深层表示。

DINO的条件角色更明确：在同房其他视角已经有难易标签时，block12/CLS近邻在54个目标视角上预测正确52个；但在严格跨楼评价中，DINO没有带来超过已有模型信息的稳定增量。**视觉近邻、有用的局部标签迁移、跨场景难易预测和人类收敛，是四个不同命题。**

历史记录可以形成“早期少模式”“较晚少模式”“观察内碎片化”等派生标签，不能无区别地补入原106张人工标签。簇多、单人模式多仅说明某个观察人数与聚类口径下的状态；不能据此写成“无法收敛”。

本轮已经执行：81种模型层/反馈数值候选、8种语义/特质编码、3种拟合分层、Ridge与近邻比较、训练内选层及DINO组合、同房迁移、类别内对照、历史轨迹敏感性。全部固定候选与负面结果均保存。另执行匹配的无模型截距控制、35图历史精确均值比较。不是只交分析计划或脚本。

## 2. 实际取得的输入、来源差别和冲突裁决

### 2.1 最新版本不是旧快照

分支读取与结束复查的HEAD均为`9d19e4e7de5d49025f8844d1a02889a90e21b4b3`。数据树为`a36e307724a127b7c110b4e5039f2d62a121091b`；之后的e47与9d只新增数值转运工作流，未改变工作包。转运运行`34867369471`成功，本轮实际取得106张标签图的五模型文件，包括新增DINO。

2178个取得文件逐文件SHA-256核对通过；28个继承的关键人类/划分文件另与当前Git blob核对一致。`build_bundle --check`通过：648图、2501条canonical记录，不需要原图。根及跟踪清单内未找到`AGENTS.md`，记录为仓库文档缺口，而不是假装读过。

**实际DINO高维数组覆盖106图；648图的状态登记已取得。** 五模型在仓库中的648图完成状态，不等于本轮下载了648份新DINO数组。全648的另一转运运行`34865295736`已取消且没有artifact。106张标签监督研究无因此缺失；未对648图作全量新DINO近邻统计。DINO旧“拒绝访问、未运行”状态已被当前官方许可权重提取记录替代。

来源和核验见`audit/input_version.json`、`audit/TRANSPORT_MANIFEST.json`、`audit/latest_inherited_input_hash_check.csv`、`audit/loaded_model_files.csv`。没有下载原图、权重或重新运行视觉网络；DA3联合几何未被用于物理配准。

### 2.2 人工大类、细类、主空间不是同一证据层

648图中原人工标签：简单49、中等41、困难16，共106；另6未定、536无该版本标签。106图来自13个楼宇和21个展示组。

106图的大类来源中，95条是早期争议复核导出的`user_type`，11条是后续41图亲审的`coarse_type`。没有把它们改写成同一次盲审。人工明确主空间/focus只有11/106，95条缺失。新增AI主空间记录覆盖106图，其中90条沿用既有视觉记录，16条来自新增原图检查；本轮未重新看图。

大类回答“场景属于什么用途”，功能细类通常是多标签集合，主空间回答“这个拍摄位置主要呈现什么”。**三者是交叉因素，不天然构成一棵严格分类树。** 同一卫浴大类可主要呈现淋浴内部、洗漱区或门侧连接；描述中出现卧室和走廊，也不能自动把走廊当相机主空间。

本轮将主空间原文与来源保留，用首句关键词得到实验性主功能，同时单独编码入口、窗侧、淋浴内部、洗漱、浴缸、边缘等位置因素。全文字符TF-IDF作为另一种明确标注的探索；它可能包含次要空间文字，不冒充纯主空间测量。映射见`method/semantic_mapping.json`，没有按预测表现改标签。648条中检出1条含难度式措辞的AI主空间描述，该段未进入文字预测；该图不在106张监督标签内。

人工大类覆盖：

{table(coarse)}

主空间首句派生功能覆盖：

{table(mainc)}

这里的sleep/living等是明确规则派生，不是新人工真值。粗类别“厨房与用餐”原有10简单/3中等；进一步拆开可见8张用餐主空间全简单，5张厨房主空间2简单/3中等。**这5张厨房图全在同一楼宇/展示组，因此该内部差别还不能跨楼稳定识别。**

可见特质仍为AI粗筛。全648有21张原分辨率复核，与106监督标签重合5张；修订前后分别预测，不把其他643/未复核图当成精确高清测量。

## 3. 评价设计：分层方法确实不同，而非只拼接更多变量

主比较使用父工作包固定留楼成员关系。25个原留楼折中，13个有本轮标签目标；零标签折也保存在`audit/fixed_fold_label_intersections.csv`。未以随机视角划分代替。待定/重叠关系不进入同房评价。

三种方式分别执行：

1. 整体拟合：全体训练图建立模型；另比较总体、大类或主空间的概率基线，以及基线后的模型残差信息。
2. 大类内拟合：当前目标的大类内形成训练、标准化、PCA、调参和选层。
3. 主空间功能内拟合：在当前目标主功能内完成同样步骤，不把其他主功能的拟合结果混入。

两个局部分层方案分别有17/106和21/106个目标在楼外没有同层训练标签。这些图仍在106图主分母，明确回退总体训练频数，没有删除。分别保留所有106、局部可训练覆盖及两种分层共同可训练覆盖。局部内部没有可用验证楼时固定PCA=None、Ridge α=10、近邻k=1，按确定顺序采用候选，不偷看外层标签。

内层沿用父工作包候选：PCA=None/16/32，Ridge α=0.1/1/10/100，近邻k=1/3/5。所有学习变换、字符词表、参数、层和混合权重只用训练侧。层固定结果全部报告，另有内层选层的独立评价。DINO组合权重0/.25/.5/.75/1在内层选取；无内层依据时不强加DINO。

因本任务目标是有序的三个主观标签，主选参量采用累积概率平方误差：

`RPS = 1/2 × Σ[j=0,1] (P(Y≤j) − I(y≤j))²`。

它只按两个有序界限评分，不宣称“简单到中等”和“中等到困难”的真实难度距离相等。原父合同对连续结果使用MAE，本轮没有覆盖该合同；此处是新增标签任务的版本化评分。分类准确率、平衡准确率、各类召回、Brier和楼/支持组件宏平均同时保存。Ridge拟合类别指示残差，截断并归一化得到概率；这不是已校准似然的保证。

匹配的零协变量Ridge控制保留相同分层和截距，避免把局部频数的重估误称成模型信息。近邻的原实现使用确定顺序处理相等距离；零变量近邻会产生任意并列，不作为无信息控制，主增量解释用Ridge。

楼级配对重采样给出相同覆盖的区间；同房分析另报组件宏平均。同楼的视角、人群重排、模型旋转和六面不增加独立样本。全体比较包含{counts['n_oof_prediction_rows']:,}条逐图折外预测，来自{counts['n_unique_oof_methods']:,}个方法配置，**不是这些数量的独立研究样本**。

这些均是已见过旧结果后的后续探索。区间未包含人为标签误差、选择偏差及继续探索多个方案的不确定性，尤其三楼内部对照不宜升级成普遍规律。

## 4. 图片类别、主空间与模型的实际联系

### 4.1 全部106图同覆盖结果

下表各模型方案为Ridge、主空间条件基线；“训练侧选层”不会选用外层最佳层。

{method_scores}

![主空间分层预测](figures/tag_prediction_mainspace.png)

大类基线预测82/106正确，主空间功能基线86/106。两者RPS差−0.0110，95%区间[−0.0358，0.0004]：点估计支持细分，尚不足以宣称稳定优于大类。把完整AI细类组合直接当类别时RPS为0.1580，明显不如大类；多标签功能编码和直接细分为大量组合不是一回事。

主空间内已有信息RPS0.0682，对匹配截距的差−0.0268，区间[−0.0679，−0.0040]。仅低维模型反馈RPS0.0739；全部既有表征在其上的差−0.0057，区间[−0.0167，0.0017]。**主要可复现线索并不需要先诉诸高维“深度难度表示”。**

整体拟合时，低维反馈家族13个外层折全部在内层选中了“HoHoNet与Bi双头的三个预测点数”方案。卧室简单/中等的HoHoNet预测点数中位数为8/10、Bi为8/12；卫浴中等/困难对应HoHoNet10/17.5、Bi8/16；厨房与用餐简单/中等约8/12。这些是模型结构输出与用户判断的联系，不是人工角点真值，更不是收敛因果机制。

原始AI位置细节、反射/遮挡字段和文字编码没有表现为普适增量。粗筛近常量、来源不同、标签选择集中，都能限制识别；不能以弱预测否定真实图片因素。

### 4.2 一个不能省略的反面结果

主空间分层已有信息总体正确89/106，但其困难召回仅13/16；主空间功能基线困难召回为16/16。中等召回由21/41增为27/41，简单均49/49。平衡准确率反而从0.8374变为0.8237。

因此，总体准确率或RPS改善**不是每类都改善**。在只有16张困难且全为卫浴的标签分布中，简单地把卫浴一律判困难能拿到很高困难召回，却不能区分6张中等卫浴；模型减少一部分这种错误，也会漏掉原困难图。必须一起看混淆矩阵。

### 4.3 类别内、楼宇内的对照有多少？

大类中有4类包含不同难度，共75图；同时固定大类和楼宇后，只剩37图、5个混合分层单元，来自3个楼宇。可构成62个不同标签图片对；这些图片对互相重叠，不是62个独立房间。

用完全在该楼以外训练的预测比较这62对：整体条件反馈的顺序一致率约0.645；DINO约0.419。主空间内选模型约0.677，DINO约0.387。但独立楼数仅3，不能据此对任意新房间作精确性能保证。

关系合格且同类别的同房异标签对仅18对、17图、3楼。该覆盖上，整体条件反馈顺序一致率0.750；局部分层方案约0.500。**一个方案总体概率更好，也可能没有改善同房的异标签区分。**

证据见`contrasts/heldout_label_pair_summary.csv`、`stratification/source_strata.csv`、`results/paired_trainable_coverage_scores.csv`。经验条件熵只作分布盘点；分得稀碎会机械降低熵，未被当作泛化证据。

## 5. DINO不同层、投影、汇聚：什么有用，什么没有？

### 5.1 跨楼预测没有得到超过既有表示的增量

{table(pp)}

在主空间内分别拟合，DINO RPS0.1043，相对已有信息增加0.0361，区间[0.0119，0.0800]；增加DINO的混合方案为0.0695，相对已有信息增加0.0013，区间[0，0.0047]。这批数据没有显示正向新增信息。它不证明DINO对其他目标无用，更不证明它永远不能解释人类不确定性。

所有block3/6/9/11/12都比较了全景全局、全景局部16、均值、六面全局均值、六面局部均值、六面全局有序拼接、六面局部96有序拼接；最后CLS的全景、六面均值和拼接也保留。六面仍是一张全景，不是六个独立拍摄位置。DA3四层也比较了完整768通道汇聚及有序96条带，未把独立面深度当公制尺度。

![DINO层与汇聚](figures/dino_layers_pooling.png)

固定层中，有些六面汇聚的分数比全景更低，有些早层优于末层；但外层结果可见后再挑最低者，会高估选层效果。因此同时保留内层选层的0.1043/0.1212等真实外推结果，不能只引用图中最低点。

### 5.2 深层“近邻更像”同时伴随楼宇背景集中

在106标签图的五近邻中，DINO全景均值block3→12：同楼比例从46.8%升至80.8%，同主功能从49.6%升至90.4%，同难易标签从57.7%升至77.4%。最后CLS同楼达84.5%。

排除同楼后，block12同标签近邻比例降至54.2%，CLS为58.5%。这是描述性近邻统计，不是新的独立试验，也不是648图总体结论。

这些结果与“深层具有更强语义和环境上下文信息”相容；**不能据此断言DINO只看装修，也不能把同标签邻近当作已识别收敛机制。** 本轮保留高相似但不同标签的跨楼同类对，供局部边界、主空间和标签语义核查。

![DINO近邻的类别与楼宇背景](figures/dino_neighbor_context.png)

### 5.3 同房标签迁移出现了不同的结果

54个目标图属于9个无待定重叠的支持组件，来自8楼；另52张标签图不符合这套同房评价关系资格。54图标签为23简单、29中等、仅2困难，因此不与106图准确率直接比较。

这里只用同支持组件的其他已标难度视角作历史依据，目标自己的标签不进入训练。固定DINO近邻，无目标标签调层。结果如下：

{table(room)}

DINO block12/CLS均正确52/54，但困难仅1/2。相同54目标上，房内标签频数RPS0.0510，楼外主空间基线0.0944；DINO block12近邻0.0185，相对房内频数差−0.0325，楼级区间[−0.0776，−0.0100]。

这是一项**给定同房其他标签的局部迁移证据**。它增加了标签与房间身份信息，不是与纯图片冷预测相同的信息条件；更没有观察真实人员增长，不能升级成人类收敛迁移。

![同房难易标签迁移](figures/same_room_tag_transfer.png)

### 5.4 旧均值与其他模型的边界

历史精确HoHoNet 0°均值只能关联当前35张标签图，与本轮预处理产生的0°均值分开比较。相同35图、主空间条件Ridge下，旧精确均值RPS0.1201，当前均值0.1269；不能在35与106不同分母间比较。结果、参数和缺71图覆盖见`legacy/`。旧d_t没有可核实分数/参考池，不以其他risk字段替换。

Bi两头输出、旋转、模型间差异、DA3单图尺度无关形态及置信均已实算，见`models/numeric_feedback106.csv`。本轮没有把公共参考或模型一致性当标签真值。DA3联合相机已知不一致，未尝试宣称物理信息补足。

## 6. 对“用历史标注补充粗难度”的判断与实算

### 6.1 可以建立另一种目标，但不能与106标签合并

**可以按历史观察形成“收敛过程粗类型/收敛难度候选”。不能将其无来源区分地写进原人工难易标签，也不能将碎片化命名为永不收敛。**

当前几何过程资料实际为205张独立image_id、230个Manual/Semi图×条件；OOS九图规则语义另保留。与106原标签重合35图，原标签构成为13简单、11中等、11困难。35张是检验两种概念是否相关的重叠，不足以先假设它们完全相同。

本轮复用上一轮逐真实人员重排结果重新计算粗分层，不把旧结论直接当标签；人类输入与当前数据树的哈希一致。未声称重新执行完整视觉/几何重建。原始点、原标签和旧报告不变。

“单一簇很多”在本分析中明确解释为**仅一名不同人员支持的单人模式很多**，不是“一张图总体只有一个簇”。每一支持簇仍需至少两名不同人员，点数不同不进入同一几何簇。

### 6.2 实际比较的定义网格

早期人数k=2、3、4、5、6、7，均严格小于8；早期允许1或2个受支持模式。较晚窗口h=10、12、15、18、19；少模式上限x=2、3、4；单人模式质量占比容差0/10%；顺序敏感性通过比例80%/90%。几何切分阈值0.05/0.10/0.20，以及P模式、D10/D20分布、G10几何规则全部保留。

每图保留自己的实际n，不按固定十人窗口作为主准入；本次沿用上一轮至少4名才能检查该探索过程的计算版本，4也不是正式最小标注人数。观察4–7人即可产生相应候选，不机械要求追加到10或更多。n不足以检验某一较晚窗口时记录不足，不自动判困难。

网格共有993,600条“图×条件×定义”记录，来自205张图，不是扩大样本量。每条保留实际n、单人比例、支持模式数、起点概率、后期新几何率和状态；这是不同定义下的结果，不是993,600个独立训练样本。

### 6.3 k小于8的敏感性结果

在τ=0.10、G10、支持模式≤2、单人比例≤10%、顺序比例≥80%的显示版本中：

{table(h)}

`suffix_only`要求从某个k起一直到实际n的模式/分布/几何检查持续满足；但这个后缀在n很小时可能只包含一次后续加入。`suffix_and_tail`另外要求上一轮的整个尾段也满足规则。两者不是等价定义。

只看后缀时，k=7有15张Manual、3张Semi早期候选；加入旧尾段检查后为10与2。后缀版Manual15图中12图实际上只有5或6名人员，另外3图24人；因此早期曲线在k≥5附近的平台，不能解释成普遍“5人足够”。

![Manual早期敏感性](figures/history_early_k_manual.png)

![Semi早期敏感性](figures/history_early_k_semi.png)

保留真实低人数观察是合理的，**但“这5人的记录统一”和“从目标人员总体再来人也不会出现新模式”不是同一强度的证据**。没有据此要求所有图增加人员；它改变的是结论措辞与不确定范围。

### 6.4 中等与困难不能只由簇数决定

在后缀版τ=0.10、G10、k=7、x≤3、80%顺序条件下，h≤15没有中程少模式候选；延长到19后出现1张Manual候选，Semi仍无。这个阴性结果说明该三档规则没有自然覆盖多数现有轨迹，不能为填满“中等”而改阈值。

具体图`S9hNv5qa7GM_bd9faec23bb3462c94a5fbc6c0a3d5cf`：原人工标签是简单，实际20名Manual人员，1个支持主簇、5%单人比例；G10条件起点中位数14，86%的顺序在8–19之间出现该后缀起点。它提示：**单一支持主簇也可能较晚才满足定位稳定，不等于几个簇决定了一切。** 新旧标签不一致应作为待解释结果，而不是修改原标签。

图`uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d`只有6名人员、2个支持模式，在后缀定义中可成为早期候选；是否真有两个合理空间解释必须本地审图。两簇可以早稳，这部分与你的设想相容。

图`uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97`有23名Manual人员、4个支持模式和2名单人记录。任意稳定后缀出现比例84%，旧尾段G10稳定比例54%，条件起点中位数20。**它不能仅因4簇而归为无法收敛，也不能用84%后缀存在改写成84%完整尾段稳定。**

τ=0.10的显示网格中，10张Manual和1张Semi满足“观察人数至少10、单人质量占比至少20%、模式较多”的碎片化描述，并存在后半程新几何。它们被标为`observed_fragmented_late_changes`，未写成`cannot_converge`。模式数量随n和τ变化；单人记录可能是合理少数解释、持续坐标变化、分区不稳定或无效作答之外的问题，需分开核查。

### 6.5 切簇不等于解释已识别

旧代表图`X7HyMhZNoso_987fd31155514f6facb131bd5c14881d`的18＋6同点数分区已有弱分离证据：大量跨簇人员配对仍在相同几何阈值内。这提醒粗分类前必须保存模式间距离、分区恢复性和单人模式，而不能只拿算法返回的簇数当真实解释数量。

稳定分布可以是多峰，模式数也不是收敛速度的定义。相同人数向量的模式占位发现过程与几何上能否辨认分区还需区分。新增派生粗类没有替代原逐图曲线和多维不确定性记录。

## 7. 接下来该如何继续研究，而不改变主线？

建议保留两个不同来源字段：

`expert_difficulty_tag`：原106张图片判断，来源和原文不变。

`observed_convergence_profile`：条件、实际n、聚类/距离版本、支持模式数、单人比例、结构差异、簇内波动、模式比例变化、后续人员覆盖、起点区间及其不确定性。

需要粗类时再派生`historical_process_tier_v...`，允许早期统一、早期双簇、较晚少模式、观察内碎片化、其他轨迹、无法判断等状态。**不强制把所有图压成一条简单—中等—困难等距轴。** 这样可以有早期双簇与晚期单簇，并保留持续但合理的少数模式。

下一步的实质检验不是找一个更漂亮的分数，而是：这些独立来源的图片判断，是否与真实人员轨迹关联；同主空间/相近结构的图片是否具有相近过程；同房不同视点是否改变可辨认模式；人员子类和真实组合是否改变模式构成。现有人员Q/T/S/B十五组合及质量＋时间＋修改幅度、真实组合结果保持后续研究身份，没有被本轮图片标签研究废弃。

对历史派生类做图片预测时，派生类是目标，不允许把生成它的当前图分歧、人数/计划、质量、时间或组号反过来做纯图片输入。标准化、选层和人员分型继续留在训练侧；Manual与Semi分别预测，不把共享初始化的分布写成人类自然不确定性。当前只有106张新DINO数值的实际覆盖，不能把历史205图当成已经完成全量新DINO收敛预测。

## 8. 本地审图、失败与不可支持的结论

`review/local_image_review_queue.csv`包含61项问题、连同配对成员共50个image_id。重点包括G002厨房内部、G179卧室内部、G184淋浴内部与主浴室、G202浴缸中央与门/通道视点、DINO高相似异标签、折外错例、早期双簇及后缀/尾段冲突。

每项记录原标签、分类来源、AI主空间原文、关系资格、数值触发、受影响结论；已有人工几何时绑定canonical IDs和人员IDs。`review/review_modes.csv.gz`保留三阈值模式，`review/raw_response_geometries.jsonl.gz`提供对应原始数值供本地覆盖显示。本轮没有凭多数票、模型或公共参考裁决哪个模式合理。

不能支持的结论：图片固有难度已被识别；DINO能普适预测收敛；所有相似视觉都有相似人类增长过程；无显著特质增量等于图片因素无作用；困难就是无法收敛；人工与派生标签可无条件互换；在现有工作者/历史界面下稳定即可推广到新人员总体；所有同组图是同一物理房间。

本轮23项必要测试全部通过，覆盖训练侧PCA/正则回归与直接实现一致、完整嵌套选择不读取目标楼标签、标签来源、固定划分、失败回退、人员排除、同房隔离、历史覆盖和后缀/尾段差别。第一次CV写参数记录时出现重复关键字错误，修复后全部重跑；失败日志保留。第一次可见绘图工具传输超时，第二次成功生成6张数值图。没有把失败尝试写成成功结果。

## 9. 交付、复算和远端状态

全部新结果放在`cloud/difficulty_tags_20260915_v1/mainspace_v1_9d19e4e7/`，旧v1/v2报告保留。`results/all_candidate_scores.csv`及`results/all_oof_predictions.csv.gz`是主查阅入口；`results/stratified_scores.csv`、`controls/`、`rooms/`和`historical_bridge/`给出条件解释，`REPRODUCE.md`给出命令。

报告、代码、结果与输入数值缓存打包；轻量包省略高维缓存但保留全部统计结果和参数。完整包用于不下载模型权重的数值重算。重新从原始导出生成这些汇聚时需使用已在仓库中的106图数值NPZ，不需要原图；原NPZ未在ZIP中重复打包，SHA和转运记录保留。

**本轮尚未回写GitHub。** `PENDING_GITHUB_RETURN.csv`列出需要回传的新代码、结果与入口。没有声称已提交main。此前已生成的历史报告仍有独立版本，不因新结果覆盖。

本轮最终裁决：**主空间值得成为独立条件层；模型的有用信息依赖该条件和是否拥有同房标签。历史收敛粗分类可以成为另一套研究目标，但应作为带实际人数和定义版本的过程描述，不能为了增加标签数而把它当成人工难度真值，也不能以簇数宣判永不收敛。**
'''
 (O/'REPORT_ZH.md').write_text(text,encoding='utf-8')
 try:
  import markdown
  body=markdown.markdown(text,extensions=['tables','fenced_code','toc'])
 except ImportError:
  import mistune
  body=mistune.create_markdown(plugins=['table'])(text)
 # Embedded numeric figures keep a downloaded report self-contained.
 for path in (O/'figures').glob('*.png'):
  body=body.replace('figures/'+path.name,'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode())
 page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>主空间分层与历史收敛粗分类</title><style>body{{font-family:system-ui,"Microsoft YaHei",sans-serif;max-width:1120px;margin:40px auto;padding:0 24px;line-height:1.85;color:#20242a}}h1,h2,h3{{line-height:1.45}}h2{{margin-top:2.2em;border-top:1px solid #ddd;padding-top:1em}}table{{border-collapse:collapse;font-size:14px;display:block;overflow-x:auto;margin:20px 0}}th,td{{padding:8px 12px;border-bottom:1px solid #ddd;text-align:left}}th{{background:#f3f5f7}}code{{background:#f3f3f3;word-break:break-word}}pre{{white-space:pre-wrap}}img{{max-width:100%;height:auto}}a{{color:#18558b}}.status{{border:1px solid #aaa;padding:12px}}</style><body><div class="status">探索结果；原人工标签与历史过程标签分开。完整数值、代码、哈希和复算命令见ZIP。</div>{body}</body></html>'''.format(body=body)
 (O/'REPORT_ZH.html').write_text(page,encoding='utf-8');print('REPORT',len(text),'Chinese chars/text',flush=True)
if __name__=='__main__':main()
