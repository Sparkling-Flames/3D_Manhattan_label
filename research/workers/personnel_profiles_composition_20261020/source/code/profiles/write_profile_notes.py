"""Create concise Chinese findings, field notes, and eight offline personnel cards."""
from pathlib import Path
import argparse,json,html
import pandas as pd


def markdown(frame):
    def value(x):
        return '—' if pd.isna(x) else str(x)
    lines=['|'+'|'.join(frame.columns)+'|','|'+'|'.join(['---']*len(frame.columns))+'|']
    lines+=['|'+'|'.join(value(v) for v in row)+'|' for row in frame.itertuples(index=False,name=None)]
    return '\n'.join(lines)


def main():
    pa=argparse.ArgumentParser();pa.add_argument('--out',type=Path,required=True);a=pa.parse_args();o=a.out
    p=pd.read_csv(o/'worker_profiles.csv');base=p[p.panel.eq('ordinary')]
    sample=base[((base.condition=='manual')&base.worker_id.isin(['W109','W112','W122','W126','W102','W002','W037']))|((base.condition=='semi')&base.worker_id.isin(['W011','W006','W128']))]
    table=markdown(sample[['worker_id','condition','n_quality','Q_mean','Q_peer','Q_q10','source_time_median','relative_time','hard_n','hard_Q_mean','hard_Q_peer','hard_minus_easy_peer','n_cleaning_excluded','n_inventory']].round(3))
    checks=markdown(pd.read_csv(o/'quality_model_lobo_summary.csv').round(4))
    paired=markdown(pd.read_csv(o/'W109_W112_common_task_summary.csv')[['condition','panel','difficulty','n_images','n_buildings','delta_Q','delta_Q_building_equal','W112_better_images','paired_time_ratio_median']].round(3))
    text=fr'''# Part A 人员画像：本轮实算发现

## 核心结论

应保留 **通常质量、同任务相对质量、质量低尾、任务调整速度、困难条件水平及变化** 六类连续信息；scope回答和初始化错误未纠正、人工筛除另列。新批普通Manual的相对Q与相对耗时的人员Spearman相关仅0.003，Q与T不能合并成一条等级轴。全库简单均Q、同伴残差、排名与任务—人员固定效应高度一致，但低尾、困难条件和Semi纠错记录能够改变对具体人员的判断。

最有实用价值的画像联系是：**整体Q相近的快者可以显著减少基础劳动量，慢者是否值得保留需要看具体困难条件和原标注贡献。** W109/W112在相同99张普通Manual图上总体Q几乎相同、耗时相差7.67倍；困难15图慢者平均多8.10分，中等18图却少6.78分。另一条独立信息是：W011的Semi终稿均Q82.91，但6/6已确认错误初始化未纠正。终稿接近参考和识别/纠正模型错误是不同能力证据。

## 1. 本轮使用了什么

源文件为最新main现有的`research/statistics/v2_integrated_analysis_20261019/tables.json.gz`中的`quality__shared_records`，几何表达连接`research/difficulty/difficulty_mechanisms_v2_20261020/record_conditions.csv.gz`。本轮独立重算同任务Q与log时间残差，与已有值最大差分别3.55e−15、1.69e−15；没有重算或调整B8L2、D10、参考、环序、投票资格。

全部非OOS库存9217份、233图、62个来源人员ID。普通Manual 7523份，门洞Manual603份，Semi1091份。正式质量7302份中，主普通Manual5719、主普通Semi901、门洞571；另111份`special_conditional_only`保持特殊用途：Manual66、Semi45，单表保留，未混进主普通画像。GT暂停/参考问题作答仍进入有证据的几何行为统计，不恢复质量或投票。

画像表有182个实际存在的人员×条件×普通/门洞格；普通Manual62人、Semi61人。普通Q至少8图/3楼支持各59人；同口径T支持Manual57人、Semi54人。没有把无Q的W019/W026写成0分，也未给未出现的条件补行。门洞T的旧批只有83份调整时间、19人，单人支持不足；新批386份、33人，其支持门槛达到者27人。小表保留机会数，不因未达图示门槛删库存。

## 2. Q的主方案及其价值

主相对Q为同图、同condition、同目标参考和版本的leave-one-out同行均值差：\(r_{{wi}}=Q_{{wi}}-\frac{{1}}{{n_i-1}}\sum_{{v\ne w}}Q_{{vi}}\)，个人画像取本人合格任务的均值。它保留“比同任务同行高/低多少B8L2分”的直观含义，Q的任务键不额外按新旧来源切开；D10完全沿用相同分母。辅助列保留同图百分位与任务—人员固定效应。

目标建筑之外的历史表现用于选人。逐图比较这些历史分数能否正确排序目标图人员，得到下表。表中每个图先计算一次，再图等权；这里没有把同图人员对当独立图片。只评估本人历史至少8图、3楼，且目标任务至少3名这类人员的图片。

{checks}

普通Manual：残差与固定效应的人员配对次序一致率分别64.13%、64.10%，同图排名64.39%；Semi分别64.53%、64.71%、64.70%。差异不足以支持为了画像另建复杂主模型。任务调整的用途主要是使比较含义清楚、减轻任务分配影响；不能声称它在当前库存中比原均值产生大幅预测跃升。本轮采用残差为主，不把它命名为已验证的潜在能力。

## 3. 质量近、速度差大，但困难条件会改变判断

下面均使用W109/W112相同图片、相同参考。delta表示W112−W109，耗时倍率为逐图W112/W109的几何中位数。

{paired}

普通Manual99图/21楼：均Q84.322/84.990，图等权慢者+0.668分，建筑等权−0.087分；每图W112都耗时更多，配对倍率7.669。困难15图/11楼：均Q55.311/63.408，图等权+8.097、建筑等权+10.503，11/15图和8/11楼方向更好；短转折均2.933/3.133、点对9.533/10.000。耗时9.464倍。它支持保留特定困难任务的慢者价值，但远非“一概越慢越细越好”。

三张原图例由机制分支制作：b8c-07双方6点对、Q98.42/97.00，24.94/207.72秒，展示质量近而耗时差；yq-29双方11/14点对、Q41.06/91.46，172.36/1825.21秒，慢者表达的范围和定位更接近有效修订参考；jh4-04双方均12点对，Q97.27/47.04，慢者在短边附近定位/方向更差。最后一例必须保留，不能把前例差异全归为多点或细致。

Semi仅8张共同图/5楼：W112−W109为−4.797分、耗时7.211倍。Manual的困难优势没有获得Semi支持，且Semi的粗难度“困难”主质量机会本身为零。

## 4. 低尾不是均值的重复标签

新批普通Manual相对Q与原Q10的人员Spearman相关0.796，但不是一一对应。W122/W126在106张共同图/22楼，均Q86.083/86.419，Q10为50.110/61.003；同行残差Q10为−3.704/−0.937，方向一致。二者原任务集相对耗时1.150/0.707倍。

这提示在同等高Q核心中仍可考虑低尾和时间。不能据此宣布W126在全部结构机会更好：既有M01/M03表明W126仍会简化其他成员保留的局部结构，尤其参考暂停的真实细节不能用主Q表反向抹去。低尾、实际结构和平均分分别描述。

## 5. 困难水平与“难减易”必须同时保留

W102普通Manual整体Q84.361，困难19图/13楼Q71.612、同行残差+22.802，难减易同行残差+8.299，整体相对耗时0.909。W002旧批整体Q81.905，但困难11图/8楼Q87.442、同行残差+42.127，简单31图Q79.024、同行+2.276，难减易+39.850。这些是可用于组合解释的条件优势候选，不能因整体已高Q就忽略其额外信息。

反例W128普通Manual困难21图Q43.559、同行−6.123，难减易虽为+0.711，仍不适合命名为困难专家。W037困难10图Q41.196、同行−6.592，难减易+3.087，同理。

几何机制和粗难度不是同一字段。Semi普通正式Q没有粗难度“困难”支持，但按既有参考几何定义仍有96份/43人的几何自遮挡行为记录；单人机会较少，单独保留短边/自遮挡机制表，未补成“困难专家”。几何自遮挡不能替换照片遮挡的概念。

## 6. 多耗时对应何种收益

在每个condition×来源×场景面板内，分别消去任务与人员固定效应，估计log源时间与Q或表达特征的关联。新批普通Manual每多一倍时间对应B8L2约+1.025分（4424份/175图，残差相关0.035），短转折+0.204条（5238份/206图）、相对点对数+0.422；底点有向偏移只有+0.024像素的近零关联。旧批普通Manual的Q对应+0.196分，短转折+0.109条。

新批门洞每2倍时间对应+6.135分、短转折+0.148条，但只有17图。Semi新/旧相应Q为−4.833/−1.345分，短转折−0.049/−0.046条。合理的结果解释是：当前Manual额外投入更常伴随表达更多结构，普通图总分关系很弱；Semi没有同样的正向信号。这是同时发生的过程关联，可能含纠结、遇到未记录困难或初始化问题，不等于延长时间会改善/损害标注，也不证明所有新增点都是必要结构。

## 7. 保留Q会遗漏哪些风险

非OOS中492份不满足`pool_analysis_eligible`，其中282份仍是retained且source独立合格，只因图片/池用途规则受限；它们不计作人员筛除。余下包括197份明确清洗处置为人工筛除/历史未接纳（89/108）、11份pending、2份仍retained但source不独立。画像分别保留这些数量。

W037普通Manual保留Q58.492，人工筛除24/97份（24图），原Q并未包含这些作答。W032/W034保留均Q61.578/62.079接近，筛除6/99与14/114；W034的14由12份人工筛除和2份历史未接纳组成。W036保留Q74.452、同行+4.740，但仍有4/96人工筛除。W019/W026的历史未接纳没有可用Q，必须保留为空。

这不是“大批高Q人员暗藏严重错误”的结论：当前高筛除主要伴随较弱保留Q，同时同等均Q之间也有不同筛除负担。非OOS仅10份有历史明确个人错误归因，另外12份为具体个人错误候选；197份不能全解释为严重误标。不同来源的审核覆盖也未统一，不宜把新批接近零的筛除率当绝对可靠性证明。

当前没有“越快筛除越多”的群体证据：新批Manual时间与筛除率Spearman 0.039；旧批为+0.514，方向反而是较慢者更多，来源内支持各35/22人。这些是描述性关联，最稳妥的用途是同时显示时间与筛除记录，不加权成惩罚总分。

## 8. Semi高终稿Q不代表纠错能力；scope尚无完整判定表现

旧Semi在全非OOS有156个已确认错误初始化机会，6图/5楼，25份原样未纠正、131份编辑后是否纠正仍未知；其中138份可正式Q评分。W011的普通Semi均Q82.913，却6/6确认错误未纠正，六份全为当前可评分；W006均Q83.308、5/6未纠正。建议将这类人描述为“终稿质量尚好，但已确认错误识别/纠正证据弱”，不能只凭Q选为复核者。

新Semi525份都缺逐份精确初始化，284个报告错误机会中45份未改、239份编辑后纠错未知。W128的Semi均Q80.960、同行+2.906，但9个报告错误机会中4次未改；这不是与旧批同强度的确认盲信证据。编辑不等于纠正，未编辑普通作答也不等于盲信。

scope只有93个语义相容人工裁定机会，全部in-scope且93次均答对：Manual25、Semi68，没有可评价误收OOS的机会。新批非OOS Manual5888份scope回答中1082次out-of-scope、Semi525份中36次；这仅是响应倾向，未知/门洞/欠定目标不自动转成错误拒绝率。

## 代表人员数字索引

`n_quality`为对应条件的普通主Q；相对时间按本人来源调整；hard字段无机会保留NaN。

{table}

## 本轮新增与复用边界

本轮新增：182格人员画像；3997行楼外Q/T历史特征及同规模独立困难特征；逐人机会/筛除/几何机制汇总；四种Q摘要的904条逐图方法比较；全部符合至少5张共同图的人员配对检索；任务/人员调整的时间关联；三张正式画像图和八张简洁卡片。各方法的逐图结果不构成904张独立图片。相同人员对在不同面板不相加为独立人群。

复用而未重新验证：B8L2/D10的测量、既有原标注预处理/绑定/资格、短转折与近共线等逐份几何定义、已确认初始化及历史审核语义、M01/M03等既有人审。未做新全量人员分型；未修改融合；未声称开展前瞻招募/交互式指导或目标楼外未见新人员验证。LOBO是现有人历史的跨建筑检查，不是严格时间顺序预测。

## 与组合效益的连接建议

1. 同人数、同历史Q水平先比较更快的核心；W109型证明速度不能由Q推断。
2. 在难图追加/保留慢者前，检查其楼外困难Q是否确有额外优势；原图需要能定位到其提供的结构或位置证据。W112同时保留正例与反例。
3. 在均Q接近的高Q池内查看低尾，尤其比较W122/W126型差异；不以低尾替代GT暂停图上的细节贡献。
4. 将Semi终稿Q和确认错误未纠正分列，用于区分普通独立标注与需要识别错误初始化的复核角色；新批机会证据不足的部分留空。
5. 现阶段无需重新搜索大量类型或建立Q/T/scope加权总分。
'''
    (o/'PROFILE_FINDINGS.md').write_text(text,encoding='utf-8')
    field='''# 人员画像字段与复现说明

## 数据入口与粒度

- `worker_profiles.csv`：worker_id×condition×origin×panel，182行；普通/门洞单列。`n_quality`只取`ordinary_primary`或`doorway_quality`；`n_quality_all_uses`包含本格特殊用途正式Q，`n_special_quality`另外计数。
- `ordinary_manual_profiles_small.csv` / `ordinary_semi_profiles_small.csv`：普通条件62/61名人员的主要列。
- `special_quality_profiles.csv`：111份既有`special_conditional_only`的逐人描述，不并主普通Q。
- `record_index.csv.gz`：9217份非OOS逐对象身份、评分、资格、难度、时间及任务调整值；链接字段为object_id、worker_id、image_id、image_code、condition、origin、chosen_target_id、reference_id、reference_version。此表为来源索引和计算派生值，不是原始几何输入副本。
- `worker_difficulty.csv`：人员×条件×来源×场景×简单/中等/困难，含零机会格；只在difficulty_reference_match时进入正式难度Q/时间解释。
- `worker_mechanisms.csv`：同键再按既有reference几何机制分层，含plain_H0/short_edge_H0/geometric_self_occlusion；几何自遮挡不等于照片遮挡。
- `worker_exclusion_reasons.csv`：人员×条件×场景×难度×清洗处置×归因类别×原文字理由，含对象/图/楼计数。上下文限制也存在本表，过滤时先看cleaning_disposition，不把所有quality缺失算筛除。
- `semi_error_opportunity_index.csv`：确认/报告错误逐对象机会与编辑状态；确认与报告标志不合并。`confirmed_error_opportunities.csv`额外列出156份确认机会的当前可用性。

## 核心列

|列|定义与缺失|
|---|---|
|Q_mean/Q_median/Q_q10/Q_sd|正式B8L2的均值、中位数、10百分位、样本标准差；无Q为空，不设零分。|
|Q_peer|同图×condition×target×reference version的leave-one-out同行均值残差，个人任务等权均值；单位为B8L2分。|
|Q_peer_q10|上述逐份同行残差的10百分位；可辅助区分任务组合与个人低尾。|
|Q_rank|同任务百分位的个人均值；有并列用平均秩，singleton为空。|
|Q_task_worker_effect|OLS任务与人员固定效应的人员项，作为敏感性；当前没有显著改善楼外次序预测。|
|D10_mean/D10_q10/D10_peer|对完全相同Q资格使用D10；未按目标效果换主评分。|
|source_time_median/source_time_q90|本来源pool合格作答的真实源活动/报告秒数；新旧语义不同，均不填补。|
|relative_time|exp(个人log源时间减同任务其余人log时间均值的均值)；任务键另含origin、time_source_kind。小于1更快，但不是统一跨来源工时倍数。|
|target_time_n/target_time_median|原证据中与当前目标匹配且资格相容的时间；不能用source时间填这些空白。|
|easy/medium/hard_Q_mean|粗难度各档实际Q；同时给n和楼数。|
|easy/medium/hard_Q_peer|各档同任务同行残差。|
|hard_minus_easy_peer|困难同行残差减本人简单图同行残差；正值不自动表示难图高Q。|
|short_turn_peer|本人短转折边数减同图同参考同行中位数，沿既有个人几何资格；0.329表示平均多0.329条，非正确结构比例。|
|n_geometry|个人比较资格内的可描述作答数，包含某些质量暂停但可描述几何的作答；不恢复投票。|
|n_cleaning_excluded|excluded_by_review + historical_not_accepted数量；n_inventory为本格全部对象分母。|
|n_excluded_images/…_buildings|上述筛除涉及的独立图/楼数；保留对象数与图片数不同粒度。|
|n_pool_only_restricted|source_pool_eligible为真而pool_analysis_eligible为假，共282，不能算人员筛除。|
|n_pending|retained_pending，不计为人工筛除。|
|n_legacy_person_error|历史明确个人错误证据数量，不等于当前独立严重度gold。|
|n_person_error_candidate|具体人员错误文本候选，可能与legacy重叠；不能与legacy简单相加。|
|n_scope_out/n_scope_response|回答倾向分子/机会；n_scope_correct/n_scope_judged才是相容裁定表现。|
|confirmed_error_*|精确初始化和历史确认错误机会，未纠正要求坐标身份仍一致。|
|reported_error_*|新批报告错误机会/未改，只保留来源强度；无精确初始几何。|
|semi_edited_error_outcome_unknown_n|报告/确认错误后编辑，但不能由编辑推断纠正。|

## 历史选人与防止目标使用

`lobo_features.csv`有3997行。键为target_building,worker_id,condition,origin,panel。所有数值只用该target_building之外的该人员历史；任务嵌套于建筑，因此预先计算同任务同行残差后删整栋建筑不会混入目标分数。Q任务键不含origin；时间必须同来源。主支持列Q_supported_8images_3buildings和T_supported_8images_3buildings仅指当前有限池容量门槛，不是终身类型资格。

`lobo_difficulty_features.csv`使用完全相同键，另列三档质量和机会。不覆盖已冻结Q/T选人表。门洞专属历史容量不足时可评价“按普通历史Q选的人在门洞的结果”，但必须标明此迁移，不冒充门洞专属已验证画像。Semi任何选人只用其自身Semi历史。

`quality_model_lobo_images.csv`按目标图先汇总，904行是4方法×226目标任务面板；普通Manual177图/22楼、门洞17图/9楼、Semi32图/12楼，跨条件图片可以重复。pair_order_agreement对同目标人员配对按历史分与实际Q的方向一致给1，反向0，并列0.5；不把这些对当独立样本。`quality_model_lobo_summary.csv`为图等权摘要。

## 时间关联和人员配对

`time_conditional_associations.csv`在各condition×origin×panel内控制task+worker固定效应。每个结局在其自身非缺失合格集合上计算；Q必须正式资格，几何沿personal_comparison。`outcome_change_per_time_doubling`是OLS slope×log(2)，仅过程关联，不是干预效应。bottom_bias_9是有向像素偏移，近零不能等价绝对定位误差完全无关。

`matched_person_pairs.csv`检索每个condition×origin×panel中至少5张共同正式Q且时间非缺失的真实人员对；相同task_key必须相同图、参考、版本。配对耗时比为exp(median(log(T_b/T_a)))。`W109_W112_paired_records.csv`保存99个共同普通Manual目标的精确对象ID及结果；`W109_W112_common_task_summary.csv`另含条件、难度与建筑等权差。

## 复现

```bash
python build_profiles.py --repo /path/to/3D_Manhattan_label --out /path/to/profile_results
python plot_profiles.py --out /path/to/profile_results --font /path/to/NotoSansSC-Regular.ttf
python write_profile_notes.py --out /path/to/profile_results
```

依赖：Python3.12、numpy2.3.5、pandas2.2.3、scipy1.17.0（pandas Spearman使用）和matplotlib。图已提供PNG；仅重画中文图需要Noto Sans SC或其它同等中文字体。工作目录需可写；不需要原图全集、LFS缓存、融合引擎或HTTP服务器来重建画像。画像使用已有源表的精确Q、时间和证据；不是重新运行原始采集日志、重评分或重新裁定人员错误。

本轮作为源输入引用、未在代码中复制其全部内容的研究文件：

1. 3D_Manhattan_label项目（2026），《v2综合统计与研究台底表》，项目研究数据及README。https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/main/research/statistics/v2_integrated_analysis_20261019
2. 3D_Manhattan_label项目（2026），《v2证据审查记录》，项目数据证据。https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/main/research/statistics/v2_evidence_audit_20261019
3. 3D_Manhattan_label项目（2026），《v2：难在哪里、对谁难、造成什么标法变化》，项目研究数据及README。https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/main/research/difficulty/difficulty_mechanisms_v2_20261020
4. 3D_Manhattan_label项目（2026），《人员具体怎样标：v2标法解释与实例》，项目研究数据及README。https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/main/research/workers/personnel_marking_patterns_20261020

以上为本项目代码/数据来源，不冒称期刊或会议论文；统计定义为本轮方法，未伪造外部算法出处。
'''
    (o/'FIELD_NOTES.md').write_text(field,encoding='utf-8')
    defs=[('W109','manual','整体高Q、明显更快','相同99图与W112的均Q差仅0.668分；困难图仍可能损失局部结构或位置。'),
      ('W112','manual','慢者的条件价值','相同困难15图平均比W109高8.097分；中等图和Semi未获同向优势，必须看具体结构。'),
      ('W122','manual','高Q与局部结构保留并存','与W126在共同图均Q接近但低尾较弱；既有M01/M03仍保留W126省略的局部细节，不能只按低尾删人。'),
      ('W126','manual','高Q、较快、低尾较好','与W122在106张共同图均Q接近，Q10高10.893分；既有M01/M03仍有局部简化反例。'),
      ('W002','manual','困难条件额外优势候选','困难11图/8楼Q87.442、同行+42.127；此为现有来源的条件证据，不把人固定成永久专家。'),
      ('W102','manual','高Q且困难表现突出','困难19图/13楼Q71.612、同行+22.802，难减易+8.299；常规相对耗时0.909。'),
      ('W011','semi','终稿Q好，确认纠错弱','六个已确认错误初始化均原样未纠正；六份仍Q可用，不能仅凭终稿Q选其担任错误复核。'),
      ('W037','manual','均Q之外有明显筛除负担','人工筛除24/97份；慢并未免于低尾和筛除。墙面分段行为不自动等于必要结构。')]
    cards=[];card_rows=[]
    fmt=lambda x,n=2:'—' if pd.isna(x) else f'{x:.{n}f}'
    for worker,cond,title,desc in defs:
        r=base[base.worker_id.eq(worker)&base.condition.eq(cond)].iloc[0]
        card_rows.append(dict(worker_id=worker,condition=cond,title=title,description=desc,**{k:r[k] for k in ['origin','n_quality','Q_mean','Q_peer','Q_q10','source_time_median','relative_time','hard_n','hard_Q_mean','hard_Q_peer','hard_minus_easy_peer','n_cleaning_excluded','n_inventory','confirmed_error_opportunities','confirmed_error_unchanged']}))
        cards.append(f'''<article><div class="eyebrow">{cond.upper()} · {'新批' if r.origin=='new' else '旧批'} · 普通面板</div><h2>{worker}<span>{html.escape(title)}</span></h2><div class="values"><div><b>{fmt(r.Q_mean)}</b><small>B8L2均值 · n={int(r.n_quality)}</small></div><div><b>{fmt(r.Q_peer)}</b><small>同任务相对Q</small></div><div><b>{fmt(r.Q_q10)}</b><small>质量第10百分位</small></div><div><b>{fmt(r.source_time_median,1)}s</b><small>本来源活动时间中位数</small></div><div><b>{fmt(r.relative_time)}×</b><small>同来源任务调整耗时</small></div><div><b>{int(r.n_cleaning_excluded)}/{int(r.n_inventory)}</b><small>筛除/库存 · 归因另列</small></div></div><p>{html.escape(desc)}</p></article>''')
    doc='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HOHONET 人员画像卡片</title><style>body{font-family:system-ui,'Microsoft YaHei',sans-serif;color:#162b3e;background:#f1f5f7;margin:0;padding:40px;line-height:1.55}main{max-width:1280px;margin:auto}h1{font-size:32px;margin:0 0 8px}header p{max-width:1000px;color:#526373}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin-top:26px}article{background:white;border:1px solid #d4dfe6;border-radius:12px;padding:24px;break-inside:avoid}.eyebrow{letter-spacing:.08em;font-size:11px;color:#567285}h2{margin:8px 0 18px;font-size:25px}h2 span{display:block;font-size:17px;font-weight:500;margin-top:3px}.values{display:grid;grid-template-columns:repeat(3,1fr);gap:16px 14px}.values b{font-size:23px;color:#246b83;display:block}.values small{font-size:11px;color:#617484}article p{margin-bottom:0;font-size:14px;border-top:1px solid #e2e9ef;padding-top:14px}footer{margin-top:25px;color:#536a79;font-size:13px}a{color:#246b83}@media(max-width:800px){body{padding:20px}.grid{grid-template-columns:1fr}.values{grid-template-columns:repeat(2,1fr)}}@media print{body{background:white;padding:15px}.grid{gap:12px}article{padding:15px}h1{font-size:25px}}</style><main><header><h1>HOHONET 人员画像：八个有用途的例子</h1><p>画像分别描述质量、速度、困难适应和辅助行为；标签是当前证据的简写。Manual与Semi分别评价，普通与门洞分列。空值表示没有相应支持，不补成0；本文活动耗时不代表排队或实际交付时长。</p></header><div class="grid">'''+''.join(cards)+'''</div><footer>完整人员数据见 ordinary_manual_profiles_small.csv、ordinary_semi_profiles_small.csv 和 worker_profiles.csv。方法、分母、困难/门洞及筛除归因详见 PROFILE_FINDINGS.md、FIELD_NOTES.md。本页自包含，可离线打开，无需服务器。</footer></main></html>'''
    (o/'personnel_cards.html').write_text(doc,encoding='utf-8')
    pd.DataFrame(card_rows).to_csv(o/'person_cards.csv',index=False)
    print('wrote PROFILE_FINDINGS.md FIELD_NOTES.md personnel_cards.html')


if __name__=='__main__':main()
