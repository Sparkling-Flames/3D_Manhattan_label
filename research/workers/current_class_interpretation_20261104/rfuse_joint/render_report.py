#!/usr/bin/env python3
"""Render profile conclusions from saved results without recalculating models."""
import json
import numbers
import pandas as pd
from build_profiles import OUT, save

def table(d,cols,rename=None,digits=3):
    d=d[cols].copy()
    if rename:d=d.rename(columns=rename)
    def cell(v):
        if pd.isna(v):return ''
        if isinstance(v,numbers.Real) and not isinstance(v,numbers.Integral):return f'{v:.{digits}f}'
        return str(v).replace('|','\\|').replace('\n',' ')
    rows=['| '+' | '.join(map(str,d.columns))+' |','| '+' | '.join(['---']*len(d.columns))+' |']
    rows.extend('| '+' | '.join(cell(v) for v in row)+' |' for row in d.itertuples(index=False,name=None))
    return '\n'.join(rows)

def main():
    s=pd.read_csv(OUT/'SAME_IMAGE_PAIR_SUMMARY.csv')
    c=pd.read_csv(OUT/'ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv')
    qt=pd.read_csv(OUT/'Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv')
    p=pd.read_csv(OUT/'CLASS_ORIGINAL_PROFILE_SUMMARY.csv')
    r=pd.read_csv(OUT/'DIFFICULTY_RESPONSE_PAIR_SUMMARY.csv')
    check=json.loads((OUT/'CHECKS.json').read_text(encoding='utf-8'))
    cq=c[c.condition.eq('manual')&c.scope.eq('primary')&c.source_stratum.eq('all_origins')&c.metric.eq('B8L2')&c.difficulty.eq('ALL')]
    rf=s[s.method.eq('RFUSE_GEOM_K2')&s.condition.eq('manual')&s.scope.eq('primary')&s.source_stratum.eq('all_origins')&s.difficulty.eq('ALL')&s.metric.isin(['B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','omission','extension','matched_boundary_abs_deg','turn_n','short_turn_edges','unmatched_ref_9'])]
    rf_d=s[s.method.eq('RFUSE_GEOM_K2')&s.condition.eq('manual')&s.scope.eq('primary')&s.source_stratum.eq('origin=new')&s.metric.isin(['B8L2','turn_n','short_turn_edges','omission'])&s.difficulty.ne('ALL')]
    qmain=qt[qt.condition.eq('manual')&qt.scope.eq('primary')&qt.difficulty.eq('ALL')].copy()
    qmain['来源']=qmain.source_stratum.str.split('|').str[0]
    qmain['比较']=qmain.class_B+'−'+qmain.class_A
    qmain['Q图正向比例']=qmain.Q_positive_images.astype(str)+'/'+qmain.n_images.astype(str)
    joint=qmain[qmain.method.str.startswith('OPP')]
    dstruct=qmain[qmain.method.str.startswith('TARGET')]
    dist=p[p.condition.eq('manual')&p.scope.eq('primary')&p.source_stratum.eq('all_origins')&p.metric.eq('B8L2')&p.difficulty.eq('ALL')]
    semi=s[s.condition.eq('semi')&s.scope.eq('primary')&s.source_stratum.eq('all_origins')&s.metric.eq('B8L2')&s.difficulty.eq('ALL')]
    other=s[s.condition.eq('manual')&s.scope.ne('primary')&s.source_stratum.eq('all_origins')&s.metric.eq('B8L2')&s.difficulty.eq('ALL')]
    diff=r[r.condition.eq('manual')&r.scope.eq('primary')&r.source_stratum.eq('all_origins')&r.metric.isin(['B8L2','turn_n','short_turn_edges'])&((r.method.eq('RFUSE_GEOM_K2'))|(r.method.eq('OPPJOINT_K3')&r.class_A.eq('C2')&r.class_B.eq('C3')))]
    conclusions=pd.DataFrame([
        dict(topic='当前分类职责与实际标签',judgement='保持',finding='DSTRUCT正向、RFUSE反向、OPPJOINT联合画像；所有类别均复用冻结当前标签，未重新选型。',source='../basis/CURRENT_METHOD_CONTRACT.json',condition='ALL描述与目标建筑LOBO实验标签分开'),
        dict(topic='RFUSE反向类别与原答特点的联系',judgement='保持',finding='较高困难转折响应类在楼外原答中也表现为困难结构保留更多、遗漏较少、Q更高；原答证据补齐了训练响应的解释。',source='SAME_IMAGE_PAIR_SUMMARY.csv',condition='普通Manual主目标；当前合法、可评原答支持；不把4名ALL成员视作所有楼外折永久名单'),
        dict(topic='RFUSE的质量与劳动画像',judgement='条件变化',finding='同源new、同一批正时间原答中，192图Q差+14.106150、时间几何比1.059617；更高质量没有对应大幅更长记录劳动。',source='Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv',condition='method=RFUSE_GEOM_K2,manual,primary,new,ALL；v1无可用双类共同支持'),
        dict(topic='JOINT是否是从低Q到高Q的固定等级',judgement='需改写',finding='高训练Q类的楼外质量优势清楚，但低/中编号类Q重叠且方向依来源、建筑权重变化；四域联合分类不能简写为质量等级。',source='SAME_IMAGE_PAIR_SUMMARY.csv;ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv',condition='OPPJOINT原编号按每折训练Q中心升序；ALL角色并非永久楼外类型'),
        dict(topic='JOINT同等Q下时间差异',judgement='保持',finding='K4 C2−C1：new162图Q−0.133061、T比0.884693；v1 87图Q+0.678103、T比0.833982，体现Q接近而记录劳动不同。',source='Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv',condition='严格同源、同图、同一批时间合法原答；不是以混合Q支持匹配某一来源T'),
        dict(topic='长记录劳动是否统一换来更高Q',judgement='需改写',finding='K4 C3−C2：new143图T比2.949455但Q−4.170892；v1 49图T比3.684379且Q+9.096673。应保留来源条件下不同质量回报。',source='Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv',condition='观察性类别比较，不把时间比解释为个人增加耗时的因果收益'),
        dict(topic='困难响应',judgement='条件变化',finding='RFUSE同源new困难图转折差+2.746643、31/32图正，简单图仅+0.086136；相同人/相同楼的结构响应同向，Q响应差的建筑方向不齐。',source='SAME_IMAGE_PAIR_SUMMARY.csv;DIFFICULTY_RESPONSE_PAIR_SUMMARY.csv',condition='区分困难图横截面对比与相同人跨难度响应，不把二者当同一个估计量'),
        dict(topic='Semi和其它目标',judgement='幅度变化',finding='RFUSE Semi主目标Q差+3.161593，23图；其它目标Manual +10.319542，21图。支持和效应均独立列出。',source='SAME_IMAGE_PAIR_SUMMARY.csv',condition='Semi是Manual标签的跨模式表现；其它目标精确接自身reference/version分项'),
        dict(topic='新一轮Q/T选队、进入策略或重评分',judgement='保持',finding='本次缺口由原答画像、同图统计与来源解释补齐，未发现要求重跑这些实验的新输入。',source='CHECKS.json;../basis/LABEL_VERSION_CHECKS.json',condition='若以后提出新的人员分配/进入顺序效益主张，再按该主张设计验证'),
    ])
    save(conclusions,'CONCLUSIONS.csv')
    text=f'''# RFUSE / OPPJOINT 当前原答、Q、劳动与难度画像

## 核心发现

**当前分类已经能够解释有实质含义的标注差异，主要缺口是把这些差异按共同图片、合法时间来源和实际楼外类别完整呈现。本次已经补齐，不需要为此重新选择分类或新增一轮Q/T选队。**

RFUSE的较高困难结构响应类，在未用于该楼建类的原答中保留更多困难局部结构、遗漏更少，主目标同图Q平均高13.937分；同源new、同一批合法时间原答上，Q差为14.106分，记录时间几何比为1.060。这个结果把“融合响应类别”与“人在原图上怎样标”连接起来，同时显示质量差异并不必然对应较大的记录劳动差异。

OPPJOINT的价值主要在于联合画像。它能区分Q接近而劳动不同的类，也揭示长记录劳动的质量回报随来源而改变。例如K4的C2相对C1，在new和v1共同原答上Q分别仅−0.133和+0.678分，时间几何比分别为0.885和0.834；K4的C3相对C2则在new来源表现为更慢且Q较低，在v1来源表现为更慢且Q较高。将这些条件合并成“慢者统一更好”或“Q相同但慢三倍”，都会丢失重要的人群差异。

证据全部来自下列已保存的逐目标、逐图、逐建筑和类内分布表。当前标签形成过程、ALL名单、每图容量和每折中心见[分类合同](../basis/README_ZH.md)，完整原图与完整标注见[案例图册](../examples/index.html)。

## 1. 这次比较的对象和计算顺序

冻结源提交为`48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b`。普通Manual主目标6,512份、其它合法目标227份；普通Semi主目标960份、其它目标4份。571份历史门洞记录和111份特殊范围不进入本画像，当前门洞专题也没有因此被重新展开。

每个原答按目标建筑连接对应LOBO标签；ALL名单只用于描述。`OPPJOINT_K3/K4`都由普通Manual训练，不是Manual与Semi的联合建类。Semi的下列表现使用Manual标签跨模式评价。RFUSE的GEOM特征和α选择不直接用Q/T，训练合格支持仍要求几何和质量输出齐全；OPPJOINT直接使用历史Q/T，所以它的训练历史差异不是独立验证，本报告的实证结论来自楼外原答。

统计顺序为：原答→同工人同目标均值→同图同目标内类均值→B类减A类→同图不同目标等权→图片等权；另给楼内图片均值再建筑等权的结果。每个指标使用自己的有限值支持，不填零，不把支持变化当质量改善。所有配对表都保存方向、图片数、建筑数、图间分位数和每类实际人数。

原答Q和分项保持原值。主目标有{check['primary_exact_object_reference_version_component_matches']:,}份、其它目标有{check['other_exact_object_reference_version_component_matches']:,}份原答按`object_id + reference_id + reference_version`精确接回其正式分项，Q/D10一致性容差1e−9；没有把主目标分项套到其它目标。`iou_2d`保留0—1原尺度；`IoU3D100`和Q为0—100尺度。

时间仅使用正的`source_active_time_seconds`。new来源为`user_processed_reported_not_raw_log_replayed`，v1为`inherited_v1_audited_source`，两种来源不直接混合秒数。Q/T联合表进一步限定为**完全相同的一批正时间原答**，在同图、同目标、同来源内同时算Q和T。时间几何比为`exp(平均logT差)`，不是两个算术平均秒数相除；算术秒数与秒差也在完整CSV中保留。其它目标的T仍是原任务记录劳动，不能解释为该空间单独耗时。

## 2. 在每种方法自己的全类共同图片上，Q怎样分布

{table(cq,['method','class_id','n_images','n_buildings','image_equal_mean','building_equal_mean'],{'method':'方法','class_id':'类','n_images':'共同图','n_buildings':'楼','image_equal_mean':'图等权Q','building_equal_mean':'楼等权Q'})}

来源：[ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv](ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv)，条件`manual / primary / all_origins / B8L2 / ALL`。每个方法内所有类使用相同图片；不同方法的共同图片数量不同，因此本表不用于把方法按差值大小排优劣。

RFUSE C2与C1的差距清楚。OPPJOINT K3的C3、K4的C4也有明显的楼外Q优势；K3的前两类和K4的前三类没有形成稳固的逐级Q阶梯。这与四个域共同参与建类的目的相符：联合类主要组织多种行为与劳动特点，其编号只是每折训练Q中心的排序。

类内差异也保留。下表是各类现有支持上、按类内目标→图片→建筑计权的个体Q分位数，提供分布宽度，不替代上面的全类共同图比较：

{table(dist,['method','class_id','n_images','workers','weighted_individual_p10','weighted_individual_median','weighted_individual_p90'],{'method':'方法','class_id':'类','n_images':'有该类的图','workers':'跨折涉及人数','weighted_individual_p10':'Q P10','weighted_individual_median':'Q中位','weighted_individual_p90':'Q P90'})}

来源：[CLASS_ORIGINAL_PROFILE_SUMMARY.csv](CLASS_ORIGINAL_PROFILE_SUMMARY.csv)。各类分布有重叠，类别仍能组织分布重心和困难响应。RFUSE的ALL较高响应组是4人，但在所有目标楼的LOBO结果中该类累计涉及7人；OPPJOINT的类成员变化更明显。“跨折涉及人数”不能当作某一张图、某一折的类容量，更不能据此把ALL角色命名永久贴到每个人身上。

## 3. RFUSE：原答中具体改变了什么

### 3.1 同图分项和标法

以下均为C2−C1，普通Manual主目标192张共同图、22楼。更多转折、短墙不自动等于更好；Q、遗漏、延伸和参考匹配一起提供了实际质量联系。

{table(rf,['metric','image_equal_mean','building_equal_mean','positive_images','negative_images','zero_images'],{'metric':'指标','image_equal_mean':'图等权差','building_equal_mean':'楼等权差','positive_images':'正图','negative_images':'负图','zero_images':'相同图'})}

来源：[SAME_IMAGE_PAIR_SUMMARY.csv](SAME_IMAGE_PAIR_SUMMARY.csv)，`RFUSE_GEOM_K2 / manual / primary / all_origins / ALL`。例如Q高13.937分、二维重叠高0.0807、三维重叠高9.340分、遗漏比例低0.0545。位置和高度误差分项同时下降，不是只通过多保留几个转折抬高一个结构计数。

这里原答短墙指标沿用`short_turn_edges`：边长占底面周长小于4%，且两端转角均至少15°；有效转折大于5°，近共线点不超过5°。其计算来自冻结的原答特征表和原实现。RFUSE训练端点中的`floor_short_edge_03_n`是另一个保存字段，不能把两种名称相似的指标默认为同一特征。

### 3.2 差异集中在需要表达局部结构的困难图

RFUSE较高响应类来自new人员。将比较限定为new内部后，主要Q和结构差异仍保持，排除了仅由新旧来源混合造成均值差的解释：

{table(rf_d,['difficulty','metric','n_images','image_equal_mean','building_equal_mean','positive_images','negative_images','zero_images'],{'difficulty':'难度','metric':'指标','n_images':'图','image_equal_mean':'图等权差','building_equal_mean':'楼等权差','positive_images':'正图','negative_images':'负图','zero_images':'相同图'})}

来源为同一配对汇总的`source_stratum=origin=new`。简单图的转折差只有0.086，126图中108图完全相同；困难图差为2.747，32图中31图为正，短墙差为1.797，遗漏低0.1346。这支持“在需要时保留局部结构”的解释，比“某类人总是画更多点”更准确。难度不是本次重新评的，所有目标沿用当前确认的图片等级。

### 3.3 更高Q不要求更大的记录劳动差

同一批new、正时间原答的192图中，C2−C1的Q差为+14.106，图等权时间几何比1.0596；楼等权Q差+15.106、时间比1.0652。T方向在图间有变化，完整表还给出了时间差分位数及Q/T联合方向计数。没有v1内部的RFUSE双类共同支持，因此本结论的时间来源边界直接写为new，不借用v1均值补齐。

这解释了RFUSE为什么可以作为反向融合解释：训练范围内的较高困难结构响应，与楼外原答的局部结构、几何和Q差异有一致联系。它不是只复述RFUSE用于建类的响应系数，也没有把类平均优势写成每个成员、每张图都占优。

## 4. OPPJOINT：Q、时间与人群来源共同形成类别含义

### 4.1 全部同源Q/T类对

下表完整列出K3与K4的所有可用类对，都是同图、同目标、同来源、同一批正时间原答。T比大于1表示B类记录劳动更长，Q差始终为B−A。保留所有类对可以避免只挑选最符合故事的一组。

{table(joint,['method','来源','比较','n_images','n_buildings','image_equal_delta_Q','building_equal_delta_Q','image_equal_geometric_time_ratio','building_equal_geometric_time_ratio','Q图正向比例'],{'method':'方法','n_images':'图','n_buildings':'楼','image_equal_delta_Q':'Q图等权差','building_equal_delta_Q':'Q楼等权差','image_equal_geometric_time_ratio':'T图几何比','building_equal_geometric_time_ratio':'T楼几何比'})}

来源：[Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv](Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv)。逐图和逐目标表也已保存，能够追溯到原答对象与确切类人数。

### 4.2 可以采用的解释

**Q接近而劳动不同确实存在。** K4的C2−C1在new 162图上Q仅−0.133分，T比0.885；v1 87图Q+0.678分，T比0.834。楼等权下T方向保持，Q仍处于相邻类重叠范围。它说明联合画像提供了“质量接近、记录劳动不同”的信息；不需要先把类别命名为高中低质量，才能证明其解释用途。

**较高Q类也不一定更慢。** K3 C3相对C2在new 192图Q+15.349、T比0.872；在v1 50图Q+10.661、T比1.611。Q优势在两种来源中都存在，时间关系不同。K4 C4相对C1在new的Q+15.408而T比1.030，也表现为较大质量差与接近的记录劳动。

**长记录劳动的回报有明确条件。** K4 C3−C2的new 143图T比2.949、Q−4.171；v1 49图T比3.684、Q+9.097。对应楼等权结论方向相同。这不是要因new中的反向结果否定联合分类，而是它揭示的实际人群异质性：长劳动与质量关系依来源及具体类成员而变化。来源本身不是原因识别，不能把此表解释为同一个人被要求多花三倍时间后的质量效果。

全源Q的C3−C2平均差只有+0.293，但它使用183张Q可用图；把这一数值与new 143图的三倍时间直接拼在一起，会把来源和共同支持混为一谈。本报告用严格共同记录的Q/T表纠正这种解释，原分数均未改变。

## 5. 困难响应：区分横截面差异与同一人变化

除了简单/中等/困难图片分别配对，本次还只保留**同一人员、同一目标楼内同时有简单与困难图**的记录。每人先在各难度内按图片均值，再做困难−简单；类之间只在两类都具备这种支持的建筑内比较。因此这一表处理了某一类恰好作答更多困难图的问题，但研究的是同一楼内的难度响应，并不是跨图随机干预。

{table(diff,['method','metric','class_A','class_B','n_buildings','building_equal_response_difference','positive_buildings'],{'method':'方法','metric':'指标','class_A':'A类','class_B':'B类','n_buildings':'共同楼','building_equal_response_difference':'B−A的困难响应差','positive_buildings':'正向楼'})}

来源：[DIFFICULTY_RESPONSE_PAIR_SUMMARY.csv](DIFFICULTY_RESPONSE_PAIR_SUMMARY.csv)，全体原始记录见[DIFFICULTY_SAME_WORKER_BUILDING.csv.gz](DIFFICULTY_SAME_WORKER_BUILDING.csv.gz)。RFUSE结构转折响应差在14/14楼为正，OPPJOINT K3 C3−C2在15/15楼为正，结构规律相当清楚；Q的相对困难响应在楼之间方向不齐。可以说结构表达差异随困难增加得更稳定，不能据此写成Q优势必然随困难单调增大。这个限定没有取消前面楼外同图Q优势的证据，两张表回答的是不同问题。

## 6. Semi与其它合法目标分别保留

### Semi主目标：Manual标签的跨模式表现

{table(semi,['method','class_A','class_B','n_images','n_buildings','image_equal_mean','building_equal_mean','positive_images'],{'method':'方法','class_A':'A类','class_B':'B类','n_images':'图','n_buildings':'楼','image_equal_mean':'Q图等权差','building_equal_mean':'Q楼等权差','positive_images':'正图'})}

RFUSE平均Q差由Manual的13.937降到Semi的3.162，支持为23图、11楼。Semi的结构辅助可能改变个人标法差异如何体现，但本表本身并不识别其原因。应将其作为跨模式的幅度变化保留，不用较小的Semi差异全盘否定Manual上的分类解释。

### 其它合法目标：每个目标绑定自己的参考

{table(other,['method','class_A','class_B','n_images','n_buildings','image_equal_mean','building_equal_mean','positive_images'],{'method':'方法','class_A':'A类','class_B':'B类','n_images':'图','n_buildings':'楼','image_equal_mean':'Q图等权差','building_equal_mean':'Q楼等权差','positive_images':'正图'})}

这些结果既保留了新增合法空间的用途，也没有把它们与主目标合并。RFUSE在21图、8楼上Q差+10.320；OPPJOINT高Q类多数比较方向也保持。各类对支持不同，K4某些对仅7—9图，所有逐目标与分项在CSV中可追查。其它目标的记录劳动不能被称为单独空间劳动。

## 7. 与团队效果如何接上

本报告补的是“人员原答—类别含义”这层。严格ABC继续回答同类与跨类换人的差异，直接AC回答既定换入后的方向，有限配比和成员敏感性回答类别比例与具体成员的作用。它们不互相替代，现有真实团队结果见相邻[团队证据矩阵](../team_effects/UNIFIED_EVIDENCE_MATRIX.csv)。

原答类别在楼外表现出结构/Q/T差异，并不要求它在每个融合目标上都击败Q-only；融合可以消化部分输入差异，Q也不能概括所有结构和位置变化。反过来，也不能只因为某类融合均值较高，就把所有该类原答称为更精细。现在已经同时具备原答、分项、完整图例和团队端点证据，可以逐层对应，而无需再补一批相似选队。

## 8. DSTRUCT的同记录Q/T补表

为了使三体系的Q/T比较遵守同一合同，通用联合表同时补入当前DSTRUCT K2/K3。下面只展示其完整类对，不改变根报告中的DSTRUCT主要画像：

{table(dstruct,['method','来源','比较','n_images','image_equal_delta_Q','building_equal_delta_Q','image_equal_geometric_time_ratio','building_equal_geometric_time_ratio'],{'method':'方法','n_images':'图','image_equal_delta_Q':'Q图等权差','building_equal_delta_Q':'Q楼等权差','image_equal_geometric_time_ratio':'T图几何比','building_equal_geometric_time_ratio':'T楼几何比'})}

K3 C3−C2在new来源的202图上Q+15.262、T比1.066；v1 78图Q+8.563、T图比1.022、楼比0.960。因此质量优势保持，时间关系应解释为接近而非固定更快或更慢。C2−C1在两个来源中都表现出平均Q提高、记录时间较短，但保留其来源各自的支持图数与类内差异。

## 9. 逐条采用判断与复现

{table(conclusions,['topic','judgement','finding','source'],{'topic':'问题','judgement':'判断','finding':'采用解释','source':'来源表'})}

完整条件见[CONCLUSIONS.csv](CONCLUSIONS.csv)。没有为“显著性”反复加实验，也没有把个别逆向图当作全盘否定的理由。原答与楼外结果提供了足够的正面解释；条件变化在真实分母、来源、目标和模式上具体指出。

### 可复现命令

在仓库根运行：

```bash
python research/workers/current_class_interpretation_20261104/basis/build_basis.py
python research/workers/current_class_interpretation_20261104/rfuse_joint/build_profiles.py
python research/workers/current_class_interpretation_20261104/rfuse_joint/build_quality_time_pairs.py
python research/workers/current_class_interpretation_20261104/rfuse_joint/render_report.py
```

输入清单见[INPUT_MANIFEST.csv](INPUT_MANIFEST.csv)，数值和版本验收见[CHECKS.json](CHECKS.json)、[Q_T_COMMON_RECORDS_CHECKS.json](Q_T_COMMON_RECORDS_CHECKS.json)。本次普通原答三方法联表23,109行，未知类428行保留在覆盖表、未填入任何已知类；其余22,681行进入对应指标的有限值统计。所有图均使用目标建筑的楼外标签，主目标7,472份和其它目标231份分项精确绑定；新团队、新融合、新评分、新分类拟合均为0。

### 主要表的读法

- `CLASS_TARGET_METRICS.csv.gz`：每个确切目标的类均值、类内中位数/P10/P90与实际人数。
- `SAME_TARGET_CLASS_PAIRS.csv.gz` → `SAME_IMAGE_CLASS_PAIRS.csv.gz` → `SAME_IMAGE_PAIR_SUMMARY.csv`：逐目标、逐图和图/楼汇总的完整链。
- `CLASS_ORIGINAL_PROFILE_SUMMARY.csv`：类内分布和图片/建筑均值，按难度与来源分别保存。
- `ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv`：每种方法所有类同时可评的共同图片画像。
- `Q_T_COMMON_RECORDS_*`：五种方法、完全相同的正时间原答、同来源Q/T联合比较。
- `DIFFICULTY_SAME_WORKER_BUILDING.csv.gz`及响应表：相同人员在相同楼内的困难−简单差异。
- `ORIGINAL_ANSWERS_WITH_LOBO_LABELS.csv.gz`：保留对象、参考/版本、工人、原值、时间来源、楼外标签与目标范围，便于逐条查回。
'''
    (OUT/'REPORT_ZH.md').write_text(text,encoding='utf-8')
    print('REPORT_ZH.md bytes',len(text.encode('utf-8')))

if __name__=='__main__':main()
