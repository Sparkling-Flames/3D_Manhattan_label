"""Generate Chinese synthesis directly from verified result tables.

No positive result is inferred from a method name. Failed/unsupported questions,
actual n and previously viewed holdouts stay explicit. No original images read.
"""
from __future__ import annotations
import base64,html,json,re
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import *


def table(d,columns=None,head=None):
    if columns is not None:d=d[[c for c in columns if c in d]]
    if head is not None:d=d.head(head)
    if not len(d):return '当前覆盖下无可计算记录。'
    return d.to_markdown(index=False,floatfmt='.4f')

def section(md,title,text):md.extend(['\n## '+title+'\n',text+'\n'])

def make_figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    dest=OUT/'figures';dest.mkdir(exist_ok=True);inventory=[]
    def save(fig,name,caption):
        fig.tight_layout();fig.savefig(dest/(name+'.png'),dpi=160);plt.close(fig);inventory.append(dict(file='figures/'+name+'.png',caption=caption))
    cov=read(OUT/'targets/coverage.json')
    fig,ax=plt.subplots(figsize=(9,4.7));labels=['Expert tags','Historical images','History outside expert','Assigned tier images','New assigned','Robust new assigned'];values=[cov['expert_images'],cov['historical_unique_images'],cov['historical_outside_expert'],cov['primary_assigned_images'],cov['new_primary_assigned_images'],cov['new_robust_assigned_images']]
    ax.barh(labels,values);ax.invert_yaxis();ax.set_xlabel('Unique images, not replay rows')
    for j,v in enumerate(values):ax.text(v+.8,j,str(v),va='center')
    ax.set_xlim(0,max(values)*1.16);save(fig,'coverage','真实覆盖分层：有历史作答、能够粗分类、跨定义一致不是同一个分母。')
    counts=pd.read_csv(OUT/'targets/definition_counts.csv').fillna('')
    for arm in ('manual','semi'):
        q=counts[(counts.condition==arm)&(counts.cut==.1)&(counts.rule=='G10_geometry')&(counts.late_h==19)&(counts.max_few_modes==3)&(counts.max_singleton_mass==.1)&(counts.order_fraction_required==.8)&(counts.medium_definition=='cumulative')]
        fig,ax=plt.subplots(figsize=(7.8,4.7))
        for confirmation in ['suffix','suffix_and_tail']:
            z=q[(q.confirmation==confirmation)&q.grade.eq('simple')].groupby('early_k').n_images.sum().reindex(range(2,9),fill_value=0)
            ax.plot(z.index,z.values,marker='o',label=confirmation)
        ax.set(xlabel='Early threshold k',ylabel='Images assigned early/simple',xticks=list(range(2,9)),title=arm+' | actual observation limits retained');ax.legend();ax.grid(axis='y',alpha=.2)
        save(fig,'early_k_'+arm,'逐一保留k=2至8；达到实际观察上限后曲线平台不能解释成未来永远稳定。')
    p=pd.read_csv(OUT/'targets/primary_per_image.csv');z=p[p.condition.eq('manual')&p.grade.isin(GRADES)];rng=np.random.default_rng(SEED)
    fig,ax=plt.subplots(figsize=(7.8,4.7))
    for j,label in enumerate(GRADES):
        q=z[z.grade==label];ax.scatter(q.n_valid,np.full(len(q),j)+rng.uniform(-.08,.08,len(q)),label=label)
    ax.set(yticks=range(3),yticklabels=GRADES,xlabel='Actual distinct valid annotators',title='Manual | tier and observation-count confounding');ax.grid(axis='x',alpha=.2)
    save(fig,'actual_n_by_tier','类别与实际观察人数共变。每点是一张图；位置轻微错开只用于显示重叠，不增加样本。')
    s=pd.read_csv(OUT/'extra/singleton_future_support_summary.csv')
    fig,ax=plt.subplots(figsize=(8,4.7))
    for arm in ('manual','semi'):
        q=s[(s.condition==arm)&(s.cut==.1)&s.isolated_from_all_observed.eq(True)].sort_values('k')
        ax.plot(q.k,q.image_macro_future_support,marker='o',label=arm)
    ax.set(xlabel='Observed prefix people',ylabel='Image-macro probability of future compatible person',ylim=(0,1.02),title='Prefix-isolated singletons | disjoint real future people');ax.legend();ax.grid(axis='y',alpha=.2)
    save(fig,'singleton_future','前缀单人模式是否得到未观察人员的几何兼容支持。各k剩余人员数不同；兼容不等于语义真值。')
    e=pd.read_csv(OUT/'E_conditioned/composition_summary.csv')
    fig,ax=plt.subplots(figsize=(8,4.7))
    for composition in ['lower_axis','higher_axis','mixed_axis','random_same_panel']:
        q=e[e.condition.eq('manual')&e.axis.eq('Q')&e.composition.eq(composition)].sort_values('n_people')
        ax.plot(q.n_people,q.p_early7,marker='o',label=composition)
    ax.set(xlabel='Distinct people in subset',ylabel='Finite-pool early suffix fraction',title='Manual | outside-building reference-alignment axis');ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
    save(fig,'composition_process','人员轴在目标楼宇之外、且按Manual/Semi分别计算。曲线是历史池条件过程，不是随机分配因果效应。')
    csv('figures/inventory.csv',inventory);return inventory


def run():
    f=read(OUT/'VERIFIED_FINDINGS.json');cov=f['coverage'];p=pd.read_csv(OUT/'targets/primary_with_robustness.csv').fillna('');scores=pd.read_csv(OUT/'prediction/compact_primary_scores.csv');paired=pd.read_csv(OUT/'prediction/paired_increment.csv');traits=pd.read_csv(OUT/'A/stratified_tiers_and_process.csv');effects=pd.read_csv(OUT/'E_conditioned/paired_composition_effects.csv')
    figures=make_figures();md=['# 历史真实作答难度粗分类与图片特质：主空间研究续篇\n','输入基线：`'+BASE+'`。结果版本：`history_difficulty_20260915_v1/run_13859d59`。性质：在已经查看同批历史留出结果之后开展的后续探索；不是新的独立确认性试验。\n']
    section(md,'1. 先回答真正扩展了多少图片',f'''本轮实际完成三档派生、A—E数值分析和独立人工tag对照。历史几何作答覆盖**{cov['historical_unique_images']}张**，其中**{cov['historical_outside_expert']}张**不在106张人工tag内；这是扩展的过程研究覆盖，不是新增同口径人工真值。\n\n展示定义得到**{cov['primary_assigned_images']}张**粗类，其中**{cov['new_primary_assigned_images']}张**在106张之外，所以“人工tag或当前历史粗类”的并集是**{cov['union_expert_or_primary_assigned']}张**。在声明的敏感性家族中达到至少80%相同粗类的有**{cov['robust_assigned_images']}张**，其中新增**{cov['new_robust_assigned_images']}张**。这里的80%是定义一致性摘要，绝不是未来标注者的置信概率。\n\n源表：`targets/coverage.json`、`targets/primary_with_robustness.csv`、`targets/robust_assigned_images.csv`。未能归类的图保留连续过程、人数、失败状态；没有强行变成困难。''')
    section(md,'2. 三类资料必须严格分开','旧实验difficulty及其同义难度分组不进入新目标、特征、分组或调参。原始文件保持不可变，但分析投影采用白名单。106张用户tag仅从确认的`latest_selection_record`命名空间取出，连同逐图及组级评论独立保存，绝不成为历史粗类的标签真值或图片预测特征。OOS按钮原因合并为统一`oos`方向，仍区分几何任务中的Scope回答和独立OOS规则任务。\n\n'+table(pd.read_csv(OUT/'inputs/response_coverage.csv'))+'\n\n人工、AI主空间描述、可见特质与物理同房关系分别保存。AI关键词构成的主空间功能不是用户逐图精确复核的空间掩膜。旧的“主空间改善106tag预测”结果不能直接替代本轮历史过程检验。')
    section(md,'3. 粗类与连续过程如何定义','每图保留实际不同人员数；Manual/Semi分开，保留W011、排除W019/W026。按有效点数分别聚类，支持模式至少两名不同人员；单人标法不自动认定错误。几何距离采用已审计二维布局区域d_mask。完整链接簇是数值候选，不自动代表离散合理标法。\n\n早期k逐一比较2—8；晚期窗口10、12、15、18、19；支持模式数上限x=2、3、4；单人比例0或10%；顺序达标比例80%或90%；几何阈值0.05/0.10/0.20；并列P、D10、D20、G10和后缀/后缀加尾段确认。所有版本完整保存，未按预测成绩择阈值。\n\n展示定义使用k=7、h=19、x上限3、单人比例≤10%、G10、至少80%顺序稳定后缀。简单要求1—2个支持模式且较早达标；中等要求早期未达标，但到实际可观察的晚期窗口累计达标。困难候选要求n≥10、较多模式和单人记录，以及观察后半程仍有结构/几何变化。稳定多簇、证据不足、无效和顺序敏感另记。\n\n**x在主实现中是上限，允许较晚稳定的单主簇。** 用户更窄的2..x和恰好x语义另存`targets/medium_mode_semantics.csv`，不能把三者混写。k=8来自本轮最新指令，覆盖仓库旧任务的k<8。\n\nG10的“簇内几何检查”、模式分区检查与模式比例检查分别保留；较晚达标不必由几何项造成。`targets/stability_rule_increment_per_image.csv`检验实际增加了哪个限制。特别是S9旧案例G10/D10同起点，撤回此前“因为追加几何检查才较晚”的归因。\n\n完整网格只是敏感性输入，不是研究终点，更不是新增独立样本。预测目标另保留早期累计比例、观察上限内累计比例、后半程新几何、半程模式比例偏差、单人比例、簇内几何波动。')
    section(md,'4. 实际粗类与稳健程度',table(p[p.grade.isin(GRADES)].groupby(['condition','grade']).agg(images=('image_id','nunique'),n_min=('n_valid','min'),n_median=('n_valid','median'),n_max=('n_valid','max')).reset_index())+'\n\n'+table(p[p.robust_assigned_grade.isin(GRADES)].groupby(['condition','robust_assigned_grade']).size().reset_index(name='images'))+'\n\n每个条件仅一个中等图，不能建立有代表性的三分类泛化结论。早期简单图有多少仅观察5—6人、多少已经观察20多人，见`targets/early_tier_actual_horizon.csv`。短后缀达标不是长时稳定证明，也不机械要求再招人。\n\n“观察到19以内”的累计量在n<19时只截止到实际n−1，不预测从未发生的第19人。短尾段模式比例差还会受到(n−k)/n的算术上界约束，因此“尾段变化小”不能独立证明分布稳定。')
    section(md,'5. A：类别、主空间与可见特质','主要类别内存在不同过程类型，而不是“卫浴全困难、卧室全简单”。但简单候选与困难候选的实际人数构成也明显不同；类别内配对必须连同人数和人员证据解释。\n\n'+table(traits[(traits.condition=='manual')&traits.field.eq('scene_category')],['value','images','buildings','median_people','simple','medium','difficult_candidate','unassigned','late_new_geometry_mean','singleton_mass_mean'])+'\n\n功能细类、主呈现空间、门洞、边界、遮挡、反射及其共现均已分别统计；完整来源和值覆盖见`A/coverage_and_trait_values.csv`。未知不是“没有”，近常量和高度共线的AI字段也不支持独立机理判定。\n\n观测人数、楼宇与类别的诊断控制见`A_B/associations_verified.csv`和`A/category_process_adjusted_diagnostics.csv`。它们可以揭示关联是否明显减弱，但不能把未测量的人员、协议、视角和采集选择差异完全消除。未经调整的关系不能写成因果。42项类别内粗类差异配对全部保存，不只挑成功案例。')
    section(md,'6. B/C：图片反馈和表征能预测什么','205张历史目标图均实际读取五模型导出，构成70种固定候选/数值汇聚。不是用旧106图缓存伪装覆盖扩展。Bi extended两张后处理角点不可计算，因此含双头的反馈覆盖为203张；对应影像、失败和原值保留，未补零。DINO不同层、全景/六面、局部16/96区与CLS均实际比较；DA3仅已有单图表征，不把错误联合相机当物理对应。\n\n本轮为控制高维数值与复算体量采用新增的**逐图L2归一化精确Gram表示**，随后只在当前训练侧中心化、按训练总方差缩放、PCA及调参。它不是上一轮逐通道标准化的同一个预处理，不能把分数变化全归因于新增图。Ridge与kNN使用固定候选参数；外层留楼，内层留楼选参数及层。全部固定层和训练选层结果、失败、同覆盖和native覆盖均保存。\n\n“selected_all_deep”表示训练侧在全部候选中选择，不是把五模型融合成一个新模型；真正联合输入另列counts_plus或main_plus。\n\nManual展示结果（RPS为序数概率误差，其他为各目标MAE，不能跨列当总难度）：\n\n'+table(scores[(scores.condition=='manual')&scores.feature.isin(['constant','scene_frequency','main_frequency','feedback_counts','feedback_all','selected_existing_deep','selected_dino','selected_counts_plus_dino','selected_main_plus_existing'])],['target','feature','target_images','predicted_images','image_loss','building_macro_loss','accuracy'])+'\n\n配对增量见`prediction/paired_increment.csv`。不能因某层在一个目标成功就称其“最好地解释收敛”；预测后期新几何、早期稳定后缀、模式比例和簇内波动的结果分别裁决。稀少中等档和条件化可判断子集限制三分类外推。所有原留出已在之前探索中查看，本轮仅是内部留出检查，不是全新独立验证。')
    section(md,'7. D：同房、同类跨楼的迁移','已实际执行同房留视角、同类跨building、同主空间跨building以及同building诊断。后者不叫相似场景，也不自动叫不同物理房间。所有条件迁移读取的是来源图片的历史结果，目标图结果留出；与完全不看目标标注的纯图片预测分开。\n\n**当前同房粗类迁移覆盖为0。** 原因是关系合格的同条件视角没有同时获得主展示三档粗类，不是D没有运行，更不是同房规律不存在。具体目标与潜在邻居的缺失原因见`D/assigned_tier_room_source_coverage.csv`。连续过程量的迁移已经完成；实际邻居ID、来源人类结果、各层失效、同覆盖配对都在`D/conditional_predictions_with_neighbors.csv.gz`。不存在可用于主粗类检验的混合标签房间，因此不能从均质房间高分宣称跨视角难度解释。\n\n'+table(pd.DataFrame(f['selected_transfer']).query('design=="same_room" and method in ["source_frequency","dinov3__block12__panorama_global"]'),['condition','target','method','images','rooms','image_loss','room_macro_loss'])+'\n\n同房过程量只有小规模重叠；模型邻近只是检索工具，不提供可靠DA3物理对应，也不自动代表相同收敛规律。')
    section(md,'8. E：人数和构成会不会改变结果','共同人员同房比较使用完全相同的真实worker名单；相同人数的构成实验另用Q和T连续轴，在**目标楼之外、且Manual/Semi各自内部**估计，未知人员不构成类型。Q是相对当前参考的对齐残差，不是无误能力真值；T是有效时间残差，不是认真程度。\n\n'+json.dumps(f['person_summary'],ensure_ascii=False,indent=2)+'\n\n`E_conditioned/`为主分析。先执行的`E/`混合条件Q/T画像保留作历史运算记录，不用作主结论；其中不依赖画像的共同人员和原始几何复核仍有效。每图比较lower/higher/mixed与同池随机真实子集；人数4/6/8/10/12只在实际人数足以形成对应不重叠轴端时使用，没有复制人员。\n\n'+table(effects[(effects.condition=='manual')&(effects.axis=='Q')&effects.n_people.isin([4,8])&effects.measure.isin(['point_count_disagreement','singleton_mass','p_early7','late_new'])],['n_people','composition_a','composition_b','measure','n','delta','lo','hi'])+'\n\n构成改变模式比例、结构与有限池后缀稳定，并不自动表示哪类人更正确。两三人不用于完整收敛宣称。同一图片在相同人数下随真实名单改变，可直接反驳“全部粗类差别都由图片造成”，但观察性选择不能估计随机派工的因果效应。')
    section(md,'9. 与106张人工tag及评论的独立对照',table(pd.read_csv(OUT/'expert/independent_comparison_summary.csv'))+'\n\n'+json.dumps(f['expert_comment_audit'],ensure_ascii=False,indent=2)+'\n\n35张重叠图有41个条件记录，大多数暂不能给三档粗类。中等预期而Semi较早稳定的实例、简单预期而Manual较晚稳定的实例均保留。当前主定义没有足够的“专家困难而历史早期简单”支持实例，不能为了叙事补造。每条原评论的逐图/组级身份均保留；一句组评论应用到多张图，不等于多次独立专家证据。`expert/independent_tag_comment_process_comparison.csv`记录差异而不纠正任一标签。')
    section(md,'10. 自由探索：单人模式可能只是尚未获得支持','直接以逐前缀聚类中的单人模式为对象，再检查**未进入前缀的真实不同人员**是否出现几何兼容作答。特别分开真正与全部已观察人员不兼容的单人模式，以及完整链接分区造成、其实已有近邻的单人簇。\n\n'+table(pd.DataFrame(f['singleton_future']))+'\n\n后续兼容支持能检验“把所有单人簇都当噪声”是否错误，但不能裁决模式的物理合理性。剩余人数和当前k不同；平均率不能直接充当新的独立人员总体概率。另将真实六人子集与其后续全池比较，保留后续覆盖及变类结果于`extra/six_person_vs_full_history.csv`，没有用同一成员的自覆盖当未来检验。\n\n人数本身的留楼诊断（**禁止作为纯图片输入**）：\n\n'+table(pd.read_csv(OUT/'diagnostics/count_only_summary.csv'))+'\n\n这项对照用于揭示粗类被观察上限和历史人员分配影响的程度，不是建议把人数当图片难度特征。')
    section(md,'11. 本地审图与尚不能支持的结论',f'''审图清单共{f['review_queue_rows']}项，连同配对成员覆盖{f['review_unique_images']}个image_id。逐项含原评论、真实worker/canonical/mode记录、数值触发和受影响结论。优先判断：少数模式是否合理；弱分离同点数簇是否只是连续定位；相同功能空间的视角差异是否改变边界/门洞可见性；Bi extended失败图的后处理几何。\n\n当前不能支持：普适稳定人数、永久无法收敛、全部模式语义真实、粗类等同本体难度、某人员轴等同认真程度、主空间导致收敛的因果解释、DINO视觉相似等同收敛、未完成新标注的未来验证结果。也不能把无参考、无效、观察不足全并为困难。''')
    section(md,'12. 怎样组织不确定性论文，而不等待虚构的完整结果','**建议主问题：在结构化全景布局标注中，增加独立作答究竟消除了不确定性，还是逐步揭示了需要保留的稳定解释？这种过程如何随图像证据与真实人员构成变化？**\n\n现有证据足以组织四段，而不预先决定所有后续结果必须为正。第一段建立可审计的观测对象，分开点数、数值模式、比例、定位、Scope和无效记录。第二段展示人数增长的不同过程：早期主体统一、较晚稳定、稳定多簇、观察内碎片化、无法判断；强调短观察和罕见模式。第三段检验条件解释：类别/主空间只提供部分信息，简单布局反馈与DINO各自有目标相关的增量和失败；不把表征排行榜作为贡献。第四段展示人员构成与同房关系的复现/不复现边界，避免把一切差异归到图片或标注者之一。\n\n三档粗类是便于检索与分层的**接口**，不是替代完整分布的理论贡献。最值得写成实质发现的是“何种未稳定”：模式未发现、已有模式未获支持、分区不可识别、比例未稳定、簇内几何仍变、或者只是观察上限太低。这种区分决定后续该如何验证，而不是机械增加人数。\n\n仍未回来的新作答不能算入当前结果。可在其结果未查看前固定本轮候选分析、图像/房间隔离和局部审图编码，让新作答检验：早期单人候选是否获支持；既有支持多模式是否保留；同房不同视角过程是否一致；同一人员子群的行为是否复现。不改变既定采集安排，也不根据新结果改旧标签阈值。\n\n相关论文提供边界而不是代替本次证据：Tsai等(2024)证明布局范围策略歧义，但没有证明本研究每个数值簇都合理；Pavlick和Kwiatkowski(2019)的原论文摘要讨论增加判断后分歧可持续，本报告仅将其作为跨任务背景，不借此推断本数据的永久不收敛。\n\n- Yu-Ju Tsai, Jin-Cheng Jhang, Jingjing Zheng, Wei Wang, Albert Y. C. Chen, Min Sun, Cheng-Hao Kuo, Ming-Hsuan Yang. 2024. *No More Ambiguity in 360° Room Layout via Bi-Layout Estimation*. Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition, 28056–28065. 官方PDF：https://openaccess.thecvf.com/content/CVPR2024/papers/Tsai_No_More_Ambiguity_in_360deg_Room_Layout_via_Bi-Layout_Estimation_CVPR_2024_paper.pdf 。本轮阅读官方记录及arXiv全文HTML，未调用原图。\n- Ellie Pavlick, Tom Kwiatkowski. 2019. *Inherent Disagreements in Human Textual Inferences*. Transactions of the Association for Computational Linguistics, 7:677–694. DOI:10.1162/tacl_a_00293。官方PDF：https://aclanthology.org/Q19-1043.pdf 。本轮核对ACL官方元数据/摘要；全文页面访问失败，未冒称完成全文阅读。')
    section(md,'13. 实际交付、失败与复算','全部新代码、逐图目标、70种精确数值核、每折预测及内层选择、真实组合、定义网格、源哈希、失败日志、审图队列均在新目录保存；旧mainspace_history与v2报告未覆盖。\n\n首次本地运行器不可用，改在GitHub Actions实际执行。首次prepare遇无效响应缺失点数，修正缺失处理后成功；Bi依赖缺件补齐后剩两张真实后处理无效，明确203/205反馈覆盖。评论“非空”计数与未调整诊断标志的实现错误已独立复核，修正表与原计算记录并存；不影响已隔离的纯图片训练。\n\n完整重拟合使用工作包固定划分及kernel缓存；kernel由实际205图每模型数组生成，支持本轮声明的L2/训练中心化方案，不声称可由Gram恢复原始空间张量。复算命令与缺失原NPZ时的明确行为见`REPRODUCE.md`。ZIP通过逐文件hash和独立解压测试后另给交付核验。')
    md.append('\n## 数值图\n')
    for q in figures:md.append('!['+q['caption']+']('+q['file']+')\n\n'+q['caption']+'\n')
    text='\n'.join(md);(OUT/'REPORT_ZH.md').write_text(text,encoding='utf-8')
    import markdown
    htmlbody=markdown.markdown(text,extensions=['tables','fenced_code'])
    for q in figures:
        data=base64.b64encode((OUT/q['file']).read_bytes()).decode();htmlbody=htmlbody.replace('src="'+q['file']+'"','src="data:image/png;base64,'+data+'"')
    htmltext='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>历史作答粗分类与不确定性过程</title><style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 24px;line-height:1.8}table{border-collapse:collapse;display:block;overflow-x:auto;font-size:.88em}th,td{padding:7px 10px;border:1px solid #ccc}pre{white-space:pre-wrap;background:#f4f4f4;padding:18px}img{max-width:100%;height:auto}h2{margin-top:2.4em}</style><body>'+htmlbody+'</body></html>'
    (OUT/'REPORT_ZH.html').write_text(htmltext,encoding='utf-8')
    js('execution/REPORT_GENERATION.json',dict(status='generated_from_verified_tables',figures=len(figures),markdown_bytes=len(text.encode()),html_bytes=len(htmltext.encode()),source='VERIFIED_FINDINGS.json and named CSV tables',original_images_read=False))
    print('Report generated',len(text),'chars;',len(figures),'figures',flush=True)

if __name__=='__main__':run()
