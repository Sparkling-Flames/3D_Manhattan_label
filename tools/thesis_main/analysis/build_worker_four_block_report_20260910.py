"""把四类信息探索整理成易读报告；所有数值读取分析输出。"""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'analysis_results/worker_four_block_exploration_20260910_v1'
NAMES={'Q':'质量自动二分','Q_median2':'质量粗分（方案一）','T':'快慢分组','S':'scope判断分组',
       'B':'半自动行为分组','QT':'质量＋时间','QS':'质量＋scope','QB':'质量＋半自动行为',
       'TS':'时间＋scope','TB':'时间＋半自动行为','SB':'scope＋半自动行为',
       'QTS':'质量＋时间＋scope','QTB':'质量＋时间＋半自动行为','QSB':'质量＋scope＋半自动行为',
       'TSB':'时间＋scope＋半自动行为','QTSB':'四项一起分组'}


def content():
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    v=pd.read_csv(OUT/'validation.csv');h=pd.read_csv(OUT/'stability_summary.csv')
    groups=pd.read_csv(OUT/'group_explanations.csv');cover=pd.read_csv(OUT/'coverage.csv')
    curves=pd.read_csv(OUT/'stage_curves.csv.gz');quality=pd.read_csv(OUT/'stage_quality.csv')
    manual=pd.read_csv(OUT/'manual.csv.gz')
    compare=pd.read_csv(OUT/'cross_method_stage_comparison_reference_allowed.csv')
    def gains(cohort='current20'):
        return v[(v.variant=='primary')&(v.cohort==cohort)&(v.panel=='common')].pivot(index='model',columns='axis',values='group_gain')
    gain=gains()
    def pct(x):return f'{100*x:+.2f}%'
    d=curves[(curves.cohort=='current20')&(curves.panel=='common')&(curves.config=='q95')&
             (curves.horizon==8)&(curves.k==3)&curves.image_id.isin(manual[manual.reference_allowed].image_id)]
    cols=[(m,a) for m in ['Q_median2','T'] for a in ['G1','G2','ALL']]
    wide=d.pivot(index=['image_id','building_id'],columns=['model','arm'],values='lower').reindex(columns=pd.MultiIndex.from_tuples(cols)).dropna()
    ids=set(wide.index.get_level_values('image_id'))
    assert len(ids)==39 and wide.index.get_level_values('building_id').nunique()==12
    comparison_rows=[]
    for model,arm,label in [('Q_median2','G1','质量偏差较低组'),('Q_median2','G2','质量偏差较高组'),
                            ('T','G1','较快组'),('T','G2','较慢组'),('T','ALL','全体随机组合')]:
        z=d[(d.model==model)&(d.arm==arm)&d.image_id.isin(ids)]
        assert len(z)==39
        bounds=z.groupby('building_id')[['lower','upper']].mean().mean()
        q=quality[(quality.cohort=='current20')&(quality.panel=='common')&(quality.horizon==8)&quality.image_id.isin(ids)&quality.model.eq(model)&quality.arm.eq(arm)]
        assert len(q)==39 and q.medoid_reference_error.notna().all()
        comparison_rows.append(dict(name=label,confirmed=int((z.lower>=.8-1e-12).sum()),
            undetermined=int(((z.lower<.8-1e-12)&(z.upper>=.8-1e-12)).sum()),
            not_reached=int((z.upper<.8-1e-12).sum()),lower=bounds.lower,upper=bounds.upper,
            reference_error=q.groupby('building_id').medoid_reference_error.mean().mean()))
    comparison=pd.DataFrame(comparison_rows)
    comparison.to_csv(OUT/'readable_same39_comparison.csv',index=False)
    assert comparison.confirmed.tolist()==[17,9,18,8,8]
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei'],'axes.unicode_minus':False,'font.size':11})
    fig,axes=plt.subplots(1,2,figsize=(10,3.6),gridspec_kw={'width_ratios':[1,1.05]})
    y=np.arange(len(comparison));colors=['#287C8E','#B4D0D4','#466AA7','#B1BFDA','#737C87']
    axes[0].barh(y,comparison.confirmed,color=colors,height=.62)
    axes[0].set_yticks(y,comparison.name);axes[0].set_xlim(0,39);axes[0].set_xlabel('39张共同图片中，可确认稳定的图数')
    for i,n in enumerate(comparison.confirmed):axes[0].text(n+.6,i,str(n),va='center')
    axes[1].barh(y,comparison.reference_error,color=colors,height=.62)
    axes[1].set_yticks(y,[]);axes[1].set_xlim(0,5.1);axes[1].set_xlabel('代表标注与参考的差距（越小越好）')
    for i,n in enumerate(comparison.reference_error):axes[1].text(n+.07,i,f'{n:.2f}',va='center')
    for ax in axes:
        ax.invert_yaxis()
        for edge in ['top','right']:ax.spines[edge].set_visible(False)
    fig.tight_layout();fig.savefig(OUT/'同图同人数_稳定与参考差距.png',dpi=180,bbox_inches='tight');plt.close(fig)
    selected=['Q_median2','T','S','QB','QTSB']
    fig,ax=plt.subplots(figsize=(8.5,3.4));y=np.arange(len(selected))
    ax.barh(y-.16,gain.loc[selected,'quality']*100,height=.3,label='预测质量表现',color='#287C8E')
    ax.barh(y+.16,gain.loc[selected,'time']*100,height=.3,label='预测用时',color='#7292BC')
    ax.set_yticks(y,[NAMES[x] for x in selected]);ax.invert_yaxis();ax.axvline(0,color='#999',lw=.6)
    ax.set_xlabel('预测误差减少比例（%）；负数表示变差');ax.legend(frameon=False,loc='lower right')
    for edge in ['top','right']:ax.spines[edge].set_visible(False)
    fig.tight_layout();fig.savefig(OUT/'分类方案_质量与用时预测.png',dpi=180,bbox_inches='tight');plt.close(fig)
    pages=[]
    def p(text):return {'type':'p','text':text}
    def table(headers,rows):return {'type':'table','headers':headers,'rows':rows}
    def page(title,*blocks):pages.append({'title':title,'blocks':list(blocks)})
    page('人员分类：四类信息的探索结果',
        p('2026年9月10日｜质量、时间、半自动行为、scope判断｜后续方案仍为候选'),
        p('本轮比较了四类信息的15种组合，并保留方案一的质量粗分作为对照。结论是：复杂组合没有显示出稳定、全面的优势。质量粗分可以继续作为主线；快慢分组值得保留为独立对照；scope和半自动行为暂时更多用于解释人员差异。'),
        table(['方向','这次发现','目前怎样使用'],[
            ['质量粗分','在共同图片上，较低偏差组的稳定表现和代表结果都有积极迹象；但换图后，部分人员仍会换组。','保留为主线候选；不称为已经固定的人员类型。'],
            ['快慢分组','换一批图片后较容易得到相似分组；较快组也有稳定迹象，但稳定后的结果未更接近参考。','保留为对照；不把快慢当作品质高低。'],
            ['scope判断','能解释部分人员是否容易误判不可标图，但可用的不可标图只有9张。','保留为规则判断证据，暂不单独冻结人员类型。'],
            ['半自动行为及多项组合','部分组合更能预测修改幅度；没有证明能同时改善人员归类、质量和稳定阶段。','保留结果与行为解释，不强行增加类别。']]),
        p('这不是证明方案一最好，也不是要求只保留一个指标。更稳妥的下一步是用少量、含义清楚的粗类继续验证，允许新增数据推翻当前判断。'),
        p('本轮没有按“哪条收敛曲线最好看”反选人员。各项分类先使用其他楼的记录建立，再检查目标楼的真实标注；这些结果仍来自历史探索，尚无新增人员的独立验证。'))
    page('1  四类信息到底测了什么',
        table(['信息','本轮具体测量','解释范围'],[
            ['质量','无初始轮廓时，最终点集与可评分参考的差距。','是参考偏差，不等于已经逐条确认的规则违规。'],
            ['时间','无初始轮廓时的合格操作日志，考虑不同任务的耗时差异。','是相对快慢，不等于认真程度。'],
            ['scope判断','把可标图判为不可标、把不可标图判为可标，两种错误分开看。','是规则适用范围判断，不包括所有边界细节的执行。'],
            ['半自动行为','初始到最终改动多少，以及与参考相比净改善多少。','修改大不一定好；净改善在同一道任务内也与最终偏差有关，并非全新独立能力。']]),
        p('本轮与上一轮三指标报告不同：质量和时间来自无辅助标注，半自动行为单独提供修改信息；不再要求同一份半自动记录同时具备时间。因此，后续20人均有足够资料参加本轮四类信息的完整比较，不能直接把两轮百分比当成同条件结果。'),
        table(['人员范围','达到数据要求的人数','需要注意'],[
            ['后续20人','四类信息共同覆盖20人。','每次预测前，都重新检查用于分类的历史资料是否足够。'],
            ['全部26人','四类信息共同覆盖24人。','W14、W26缺少本轮合格时间；W26可用于质量计算的记录仅3份，未达到6份要求。'],
            ['只用scope或半自动行为','全部范围均可覆盖26人。','不能把较大覆盖与24人的公平比较混为一谈。']]),
        p('分类前，每个测量方向至少需要6份记录、覆盖3栋楼。四类信息各占相同的总权重，避免scope或半自动因为各有两个数值就自动占更大比重。只尝试两类；若自动分组只分出一个人，则记录为不采用该次分类。另保留按质量排序从中间分开的方案一。'))
    page('2  怎样检验，怎样读数字',
        p('例如要预测某人在甲楼的表现，就先只看他在其他楼的历史记录。分类和预测完成后，再用甲楼的实际标注检查。甲楼的质量、时间、scope和半自动结果，都不参与这次人员分类。'),
        p('预测检查的是同一道任务中一个人的相对表现，不是只凭类型就预测绝对秒数或一张图的绝对误差。下面“+20%”表示相对不区分人员的做法，预测误差减少20%；不是正确率20%。各楼在总结果中占相同分量。'),
        table(['后续20人：同条件比较','质量预测改善','用时预测改善','修改幅度预测改善'],[
            [NAMES[m],pct(gain.loc[m,'quality']),pct(gain.loc[m,'time']),pct(gain.loc[m,'edit'])] for m in selected]),
        {'type':'figure','path':str(OUT/'分类方案_质量与用时预测.png'),'width':6.35,
         'caption':'图1  相同人员与相同目标记录下的比较。质量评价1,245份记录、22栋楼；时间评价1,323份、22栋楼；每一列内部各方法使用完全相同的记录。'},
        p('质量＋半自动行为对质量预测改善3.66%，高于质量粗分的0.43%；但按楼重新抽样后，前者相对“不分人”的改善范围约为−0.12%至7.99%，尚不足以确认稳定优势。这些范围仅反映已算出预测的楼间变化，没有消除尝试多种方案带来的选择偏差。'),
        p('快慢分组主要提高用时预测，对质量预测没有改善。四项一起分组也没有在所有目标上更好。所有组合均有完整结果留存，未只保留表现较好的方法。'))
    page('3  scope：补上了规则判断的直接证据',
        p('本轮从原始导出重新读取每个人填写的scope，再与最终裁定逐条核对。无辅助条件共1,013份记录；主分析暂不使用后来出现争议的两张图，剩余961份，并另算保留它们的结果。不可标图为9张，可标图为28张。'),
        table(['后续20人：全量资料下的scope分组','人数','可标图误判为不可标','不可标图误判为可标'],[
            [f'候选组{int(r.label)}',str(int(r.n)),f'{100*r.in_scope_error_person_mean:.1f}%',f'{100*r.oos_error_person_mean:.1f}%']
            for r in groups[(groups.cohort=='current20')&(groups.model=='S')].itertuples()]),
        p('这是每个人错误比例先计算、再组内平均的描述。这两个候选组在识别不可标图方面差异较明显；但不能只凭全量资料上的差异就宣布类型已经成立。'),
        p('关键限制是只有9张不可标图。如果把图片分成互不重叠的两批，两边都要求每人至少6份记录，就无法同时满足。因此，按原要求没有一次能够完整比较scope分组是否重复出现。'),
        p('为了解样本限制的影响，额外做了较宽松的检查：每半至少3份记录、2栋楼。100次中有68次可以比较，分组一致程度中位数约−0.014；1表示完全相同，0附近表示与随机对应接近。这个补充结果也没有显示出稳定分型，不能替代原要求下的验证。'),
        p('scope仍然有价值：它能说明具体判断错误，不必只依赖与参考轮廓的距离。当前更适合保留两种错误记录，并检查它们是否在更多明确裁定的图片上重复出现。错误判断不自动等于故意不执行规则。'))
    stab=h[(h.variant=='primary')&(h.cohort=='current20')&(h.panel=='native')&(h.half_support=='full_requirement')].set_index('model')
    page('4  换一批图片，人员会不会换组',
        p('把楼随机分成互不重叠的两批，分别给同一批人员分类，重复100次。这里检查的是人员分组是否重复，不是标法是否收敛。'),
        table(['分组方法','能够比较的次数','一致程度中位数'],[
            [NAMES[m],f"{int(stab.loc[m,'valid'])}/100",f"{stab.loc[m,'ari_median']:.3f}" if pd.notna(stab.loc[m,'ari_median']) else '资料不足，不能估计'] for m in selected]),
        p('一致程度1表示两次完全相同，0附近表示与随机对应接近。各方法用自己的可用资料检查，因此还要看能够比较的次数，不能把无法比较当作成功。'),
        p('快慢分组在这项检查中最容易重复得到。方案一的质量粗分虽然每次都能进行，但边界附近的人员会换组。它仍可作为按历史表现分档的实验办法，却不能称为天然固定的两类人。'),
        p('质量＋半自动行为的一致程度约0.244，80次能比较；未显示出足够强的名单稳定性。增加信息并没有自动解决分类不稳定的问题。'),
        p('其他检查也显示条件依赖：换一种质量距离设置后，质量＋半自动的质量预测改善为2.30%；四项组合为1.55%。去掉构造错误的初始标注后，四项组合的质量预测改善变为−1.08%。较强的历史速度重复性，也不等于已经证明跨任务阶段或新人员仍然成立。'))
    page('5  同类人的标法是否进入稳定阶段',
        p('公平比较使用同样39张有可评分参考的图片，来自12栋楼；质量粗分、快慢分组和全体随机组合，都取8名不同人员。检查从第3人开始，标法及其比例能否持续稳定到第8人。'),
        table(['8人组合','可确认进入稳定阶段','尚无法明确判断','第3人及以前未达标'],[
            [r.name,f'{r.confirmed}/39',str(r.undetermined),str(r.not_reached)] for r in comparison.itertuples(index=False)]),
        p('每张图使用200个随机人员顺序，每次无放回抽取。至少80%的顺序明确达到稳定要求，才记入“可确认”。第三列的未达标只针对这次允许检查的起点范围，不表示到第8人仍在变化，更不表示以后永远不会稳定。'),
        p('稳定允许有多种标法。点数不同必须分开，一种新标法至少得到两人支持才算受支持的新簇；单人标法仍保留。检查还包括原有标法成员关系和人数比例是否明显变化。'),
        p('“17张”与“18张”的差别很小，不能据此宣布快慢分组更优。两种分法都比随机组合出现更多可确认的图片，但这是历史有限人员池中的探索结果，还没有新人员验证。'),
        p('若要判断大约第8人开始稳定，按本轮要求还需往后至少观察5人，即同一张图需要至少13名该类人员。当前全量质量粗分为10／10人，快慢分组为8／12人，不能据本表判断第8人的稳定起点。'))
    page('6  稳定以后，结果是否更接近参考',
        {'type':'figure','path':str(OUT/'同图同人数_稳定与参考差距.png'),'width':6.4,
         'caption':'图2  同样39张图、每组8人。左图是可确认稳定的图片数；右图是代表标注与参考的差距。两件事分别评价，不能互相替代。'},
        table(['8人组合','代表标注与参考的差距'],[[r.name,f'{r.reference_error:.2f}'] for r in comparison.itertuples(index=False)]),
        p('每次先只根据组内标注之间的距离，选出最具代表性的一份；若并列则平均计分。选取时不看参考答案，之后才与参考比较。分数越小，表示与参考更接近；它不是人工确认的正确率。'),
        p('质量偏差较低组为3.30，全体随机组合为3.81，较快组为4.06。较快组的稳定图片略多，但代表结果没有更接近参考。因此，快慢分组可以是有意义的人群描述，却不能替代质量判断。'),
        p('换另一种标法距离重新检查时，同样39张图中，质量较低偏差组的已确认稳定比例下界约41.6%，较快组37.4%，随机组合36.6%。绝对数值随标法判据变化，不能只挑较有利的设置。'))
    ga=gains('all26')
    page('7  全部人员范围的结果与覆盖限制',
        p('全部名册是26人，但四类信息同时可用的共同人员为24人。下面是在这24人的共同记录上比较，不能直接称为26人全部完成四项分类。'),
        table(['方法','质量预测改善','用时预测改善'],[[NAMES[m],pct(ga.loc[m,'quality']),pct(ga.loc[m,'time'])] for m in selected]),
        p('质量＋半自动、四项组合在这一共同人员范围内经常产生单人小组，按事先规则不采用分类，预测退回不区分人员。所以表中的0%表示分类没有被采用，不表示这些人完全没有差异。'),
        p('W26仅有3份可用于这次质量计算的记录，未满足6份要求；W14、W26缺少合格时间。这也会改变早期报告中由极少数人员形成的小组，不能把不同覆盖范围的分类结果直接拼接。'),
        p('全部范围和后续人群的结果共同表明：复杂组合的效果依赖人员组成，当前没有理由用它全面替换质量粗分。每个方法原本能覆盖多少人、每次训练是否采用分类，都保留在结果表中。'),
        p('收敛回放覆盖57张至少有7份无辅助标注的图片；其中43张有可评分参考。报告的39张是质量粗分与快慢分组同时具备比较人数、又有可评分参考的共同图片。另保留全部图片以及明确裁定为可标图片的结果，避免把不可标图上的一致性推广为正常任务表现。'))
    member_rows=[]
    for model in ['Q_median2','T']:
        for r in groups[(groups.cohort=='current20')&(groups.model==model)].itertuples():
            label=('较低参考偏差' if r.label==1 else '较高参考偏差') if model=='Q_median2' else ('较快' if r.label==1 else '较慢')
            member_rows.append([label,str(r.n),'、'.join('W'+w for w in r.worker_ids.split('|'))])
    page('8  当前保留的候选与下一步',
        p('质量粗分继续作为主线候选，快慢分组作为独立对照；不把二者再交叉切成四个小类。scope与半自动行为保留为解释和补充指标，新增资料后再检查是否值得加入分类。'),
        table(['全量历史资料下的候选描述','人数','人员编号'],member_rows),
        p('这份名单只是用全部历史资料得到的描述。前面的预测与稳定性检验都重新排除了目标楼资料，实际组员可能不同；不能拿本表直接宣称每个人已被固定归类。'),
        p('后续采集可先用一批明确规则和参考的图了解新人员，再按事先固定的办法归类，最后用另一批图检查标法是否稳定。每人独立标注的结果仍可组合为纯类或混合人群，不必为每种比例重新组织标注。'),
        p('需要补充的关键证据包括：scope在更多明确不可标图上的表现、边界人员换图后是否仍属于同一档，以及同类人数增加后早期稳定是否仍能保持。不能只补到曲线看起来稳定就停止，也不能根据目标图的标法反过来修改人员类型。'),
        p('本轮只作历史探索，不修改正式人员资格、任务分发、原始标注、最终裁定或方法合同。技术结果、全部组合、来源核对和可运行命令见同目录说明文件。'))
    page('附录  全部组合的比较结果',
        p('以下均为后续20人共同记录上的误差改善。自动质量二分与方案一按质量排序从中间分档，是不同的分组办法。其他指标、全部人员范围及各项检查版本保留在同目录数据表。'),
        table(['方法','质量预测','用时预测','修改幅度预测'],[
            [NAMES[model],pct(row.quality),pct(row.time),pct(row.edit)] for model,row in gain.iterrows()]),
        p('没有一行可以仅凭单个最大的百分比认定为最佳方案。还需同时考虑分类是否重复、人数是否足够、标法是否稳定，以及稳定后的参考差距。所有数值均为历史探索。'))
    payload=dict(preset='standard_business_brief; memo_masthead; Chinese font override Microsoft YaHei',
                 header='人员分类 · 四类信息探索',date='2026-09-10',filename='人员分类四类信息探索_易读报告.docx',pages=pages)
    assert '导师' not in json.dumps(payload,ensure_ascii=False)
    (OUT/'document_content.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
    md=[]
    for page_data in pages:
        md+=['# '+page_data['title'],'']
        for b in page_data['blocks']:
            if b['type']=='p':md += [b['text'],'']
            elif b['type']=='figure':md += ['!['+b['caption']+']('+Path(b['path']).name+')','']
            elif b['type']=='table':
                md += ['| '+' | '.join(b['headers'])+' |','|'+'|'.join(['---']*len(b['headers']))+'|']
                md += ['| '+' | '.join(map(str,row))+' |' for row in b['rows']];md.append('')
    md+=['# 附录：全部组合的预测结果','', '以下均为后续20人共同记录上的误差改善。自动质量二分与按中间位置分档的方案一是不同办法。','',
         '| 方法 | 质量 | 用时 | 修改幅度 | 半自动净改善 | 误拒可标图 | 误收不可标图 |','|---|---|---|---|---|---|---|']
    for model,row in gain.iterrows():md.append('| '+NAMES[model]+' | '+' | '.join(pct(row[a]) for a in ['quality','time','edit','benefit','scope_reject','scope_accept'])+' |')
    md+=['','# 复现与结果表','',
         '`python -m tools.thesis_main.analysis.worker_four_block_exploration_20260910 prepare`：重核原始点、参考、初始化、时间、scope与最终裁定。',
         '`screen`：15组合和质量中位数对照；`diagnostics`：人员行为解释和楼间变动范围；`replay`：逐前缀重分簇；`stage_subsets`：同图同人数汇总；`stage_quality`：代表结果评分。','',
         '`validation.csv`每行是版本×人员范围×共同/原覆盖×方法×评价方向；正值表示预测误差改善。`members.csv`为全量候选，`fold_members.csv.gz`为排除目标楼后的实际候选。`label=0`为拒绝分类，不是一种人员类型。',
         '`half_stability.csv`区分原6份/3楼要求和补充3份/2楼检查；`stage_curves.csv.gz`每行包含图片、人员范围、方法、组合、距离、观察终点及候选起点；lower/upper来自未知状态，不是置信区间。',
         '`stage_onsets.csv`区分可确认进入阶段、观察起点范围内未达标、无法判定；earliest_possible与earliest_confirmed允许给出范围，不要求是完全相同的人数。',
         '`stage_quality.csv`是组内代表的参考偏差；`readable_same39_comparison.csv`对应报告共同39张图。`cross_method_stage_comparison*.csv`在每对方法共同图片上比较，不能直接比较不同图片集合的平均值。','',
         '来源核对：6份P1原始导出与快照内容一致；61份scope裁定回连人工精标原导出，唯一scope变化696已与原有修订记录核对；两张后来有争议的图单独保留。有效时间重查原始日志，未用lead_time补值。','',
         '统计边界：按楼隔离全部分类输入；本轮是已知人员跨图片的历史探索。楼级重抽样区间不重新拟合、不校正多方案选择，不当作新人员或正式验证。200个顺序不增加独立样本量。标法图的快捷计算与原程序做过真实子集及随机图等价检查。']
    (OUT/'README_ZH.md').write_text('\n'.join(md),encoding='utf8')
    print('report content and figures ready',flush=True)


def inventory_groups(p, model, roster):
    """完整呈现分类前的人数；单人分组仅作诊断，不冒充已采用的类型。"""
    import numpy as np
    from scipy.cluster.hierarchy import linkage, cut_tree
    blocks={'Q':['quality'],'T':['time'],'S':['scope_reject','scope_accept'],'B':['edit','benefit']}
    assert p.status.nunique()==1 and not p.worker_id.duplicated().any()
    status=p.status.iloc[0]; labels=p.label.to_numpy().copy()
    if status=='singleton_rejected':
        if model=='Q_median2':
            labels=(p.quality.to_numpy()>p.quality.median()).astype(int)+1
        else:
            parts=[]
            for b in model:
                x=p[blocks[b]].to_numpy(float)
                assert np.isfinite(x).all() and (x.std(0)>1e-10).all()
                parts.append((x-x.mean(0))/x.std(0)/np.sqrt(x.shape[1]))
            labels=cut_tree(linkage(np.concatenate(parts,axis=1),method='ward'),n_clusters=2).ravel()+1
            means=p.assign(raw_label=labels).groupby('raw_label')[blocks[model[0]][0]].mean()
            if means.loc[1]>means.loc[2]: labels=3-labels
        assert min(np.bincount(labels)[1:])==1
    else:
        assert status=='usable' and set(labels)=={1,2}
    rows=[]
    for label,g in p.assign(raw_label=labels).groupby('raw_label'):
        rows.append(dict(label=int(label),n=len(g),worker_ids=sorted(g.worker_id.astype(int)),
                         missing_ids=sorted(set(roster)-set(p.worker_id.astype(int))),
                         accepted=status=='usable',status=status))
    assert sum(r['n'] for r in rows)==len(p)
    return rows


def revised_content():
    """以指标组合、各组人数和含义为主体；原实验结果及旧报告保留。"""
    import pandas as pd
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    target=OUT/'report_revision_v2';target.mkdir(exist_ok=True)
    members=pd.read_csv(OUT/'members.csv')
    members=members[members.variant.eq('primary') & members.panel.eq('native')].copy()
    coverage=pd.read_csv(OUT/'coverage.csv')
    validation=pd.read_csv(OUT/'validation.csv')
    stability=pd.read_csv(OUT/'stability_summary.csv')
    names={**NAMES,'Q':'质量（自动分组）','T':'时间','S':'规则判断','B':'半自动',
           'QS':'质量＋规则','QB':'质量＋半自动','TS':'时间＋规则','TB':'时间＋半自动',
           'SB':'规则＋半自动','QTS':'质量＋规则＋时间','QTB':'质量＋时间＋半自动',
           'QSB':'质量＋规则＋半自动','TSB':'时间＋规则＋半自动','QTSB':'质量＋时间＋规则＋半自动'}
    order=['Q_median2','Q','T','S','B','QT','QS','QB','TS','TB','SB','QTS','QTB','QSB','TSB','QTSB']
    blocks={'Q':['quality'],'T':['time'],'S':['scope_reject','scope_accept'],'B':['edit','benefit']}
    axnames={'quality':'参考偏差','time':'操作用时','scope_reject':'误拒可标图','scope_accept':'误收不可标图','edit':'修改幅度','benefit':'净改善'}
    directions={'quality':('偏差较低','偏差较高'),'time':('较快','较慢'),
                'scope_reject':('较少误拒可标图','较多误拒可标图'),
                'scope_accept':('较少误收不可标图','较多误收不可标图'),
                'edit':('修改较少','修改较多'),'benefit':('净改善较少','净改善较多')}
    inventory=[]; profiles={}
    for cohort in ['current20','all26']:
        roster=set(members[members.cohort.eq(cohort)].worker_id.astype(int))
        assert len(roster)==(20 if cohort=='current20' else 26)
        for model in order:
            p=members[members.cohort.eq(cohort)&members.model.eq(model)]
            rows=inventory_groups(p,model,roster)
            c=coverage[coverage.variant.eq('primary')&coverage.panel.eq('native')&coverage.cohort.eq(cohort)&coverage.model.eq(model)].iloc[0]
            assert sum(r['n'] for r in rows)==c.workers
            if rows[0]['accepted']:assert '|'.join(str(r['n']) for r in rows)==c.group_sizes
            axes=[a for b in ('Q' if model=='Q_median2' else model) for a in blocks[b]]
            means=[p[p.worker_id.isin(r['worker_ids'])][axes].mean() for r in rows]
            for i,r in enumerate(rows):
                desc=[]
                for a in axes:
                    diff=means[i][a]-means[1-i][a]
                    desc.append(axnames[a]+'接近' if abs(diff)<1e-9 else directions[a][int(diff>0)])
                r.update(cohort=cohort,model=model,description='、'.join(desc),
                         axis_means={a:float(means[i][a]) for a in axes})
                inventory.append(r)
            profiles[(cohort,model)]=rows
    (target/'classification_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf8')
    def size(cohort,model):
        rr=profiles[(cohort,model)]
        return '／'.join(str(r['n']) for r in rr)+('（单人组，未采用）' if not rr[0]['accepted'] else '')
    def ids(values):return '、'.join('W'+str(w) for w in values) or '无'
    pages=[]
    def p(s):return {'type':'p','text':s}
    def t(headers,rows):return {'type':'table','headers':headers,'rows':rows}
    def page(title,*items):pages.append(dict(title=title,blocks=list(items)))
    page('人员分类方案与各组人数',
         p('2026年9月10日修订｜先比较方案，再查看分组、名单与验证证据｜本报告不选定最终方案'),
         p('要回答的问题：用哪些历史表现给人员分类？每组有多少人、有什么可解释的差异？换一批图片后还能否得到相似分组？同类人员独立标注后，标法是否能进入稳定阶段？'),
         p('方案一：历史质量分档对照。根据无辅助标注与最终参考的差距给人员排序，从中间分成两档。后续20人为10人和10人；全部26人中25人资料足够，分为13人和12人，1人暂不能分。此法带有均分倾向，仅作历史对照，不能视为已发现自然人群类型，也不预设为最终应退回的分类方案。'),
         p('方案二：选择若干指标，联合分类。候选信息为质量、时间、规则判断和半自动行为。例如质量＋半自动、质量＋时间、质量＋规则、质量＋规则＋时间；每个组合都单独重新给人员分组。'),
         p('本轮共检查4种单项、6种双项、4种三项、1种四项，共15种指标组合，另加方案一作对照。方案二不是一个已经选定的组合，也不是把四项全部加入就算完成。'),
         p('两种方案都先尝试分为两组。这是本轮的小样本探索设定，尚未证明人员天然只有两类，也没有系统比较三类、四类。具体结果见后面的完整人数表。'))
    page('两版方案的优势与不足',
         p('方案一的用途：含义直接、便于复算，可用来对照其他分类方法。但按中间位置切开会使人数接近，这不是支持分类成立的证据。'),
         p('方案一的不足：两档是人为切分的历史表现，不代表两种固定人格；中间附近的人员换一批图后容易换档。与参考接近也不能代替逐条规则执行检查。'),
         p('方案二的优势：可以描述更具体的行为，例如偏差较低且较快，或修改较多且净改善较多；能够检验规则判断或半自动信息是否提供额外帮助。'),
         p('方案二的不足：加入指标可能改变人员名单并形成很小的组；指标可能互相重复，规则资料也有限。某项预测更好，不意味着标法更容易稳定。'),
         p('目前仍有三件不同的事需要分别检查：第一，分组能不能解释；第二，换图片后同一个人会不会频繁换组；第三，组内人数增加后标法是否稳定。优先确认一个具体子类能收敛，不要求全体均分或所有组同时收敛。'),
         p('本报告保留全部组合，先展示人数、名单和组平均差异，再给验证结果。不依据一条有利曲线宣布某个组合最好。'))
    page('四个指标的具体含义与分法',
         t(['信息','这次实际使用的内容'],[
             ['质量','无辅助最终标注与可评分参考的偏差；越低表示越接近参考。'],
             ['时间','无辅助标注的合格有效操作时间；比较同任务条件下的相对快慢。'],
             ['规则判断','scope与最终裁定比较：误拒可标图、误收不可标图，两种错误分别记录。'],
             ['半自动','初始轮廓到最终轮廓的修改幅度，以及相对参考的净改善。']]),
         p('“规则”目前只覆盖能否标注的范围判断，不覆盖所有布局细则。“半自动”不是是否使用工具的二元标签，而是使用初始轮廓后的行为表现；本轮也没有把半自动用时再作为第五个指标。'),
         p('联合分组的做法：先考虑不同任务本身的差异，再统一各指标的尺度，按人员表现的相似程度自动分为两组。每个大项占相同总权重；规则和半自动虽然各有两个数值，也不会因此获得双倍权重。'),
         p('例如“质量＋时间”只用这两项一起分组，不用规则和半自动决定名单；“质量＋规则＋时间”则只用这三项。这里没有先把每项分成高低档再交叉成四类或八类，那是另一种尚未运行的方法。'),
         p('每个所选测量方向至少需要6份记录、覆盖3栋楼。若自动分组产生单人组，本轮记为未采用；后文仍列出原始人数，不能把未采用写成不存在差异。'))
    for cohort,title,total in [('current20','后续20人：所有指标组合的人数',20),('all26','全部26人：所有指标组合的人数',26)]:
        rows=[]
        for m in order:
            rr=profiles[(cohort,m)]
            rows.append([names[m],str(sum(r['n'] for r in rr)),size(cohort,m),str(len(rr[0]['missing_ids']))])
        page(title,p('以下使用每种组合自身所需的资料；人数来自全部历史资料下的一次分类。前一列／后一列依次对应后文组1／组2，同一组号在不同组合中不代表同一种人。'),
             t(['所用指标','资料足够人数','组1／组2人数','资料不足人数'],rows),
             p('“单人组，未采用”保留自动分组的原始人数，但不将它作为已成立的人群子类。总人数＝两组人数之和＋资料不足人数。'))
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei'],'axes.unicode_minus':False,'font.size':10})
    fig,ax=plt.subplots(figsize=(8.2,6.5));y=np.arange(len(order))
    first=np.array([profiles[('current20',m)][0]['n'] for m in order]);second=20-first
    ax.barh(y,first,color='#287C8E',label='组1');ax.barh(y,second,left=first,color='#A6BACF',label='组2')
    for i,m in enumerate(order):
        ax.text(first[i]/2,i,str(first[i]),ha='center',va='center',color='white',fontsize=9)
        ax.text(first[i]+second[i]/2,i,str(second[i]),ha='center',va='center',fontsize=9)
    ax.set_yticks(y,[names[m]+('〔未采用〕' if m=='Q' else '') for m in order]);ax.invert_yaxis()
    ax.set_xlim(0,20);ax.set_xticks([0,5,10,15,20]);ax.set_xlabel('人数（每个组合单独分类）')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.09),ncol=2,frameon=False)
    for edge in ['top','right']:ax.spines[edge].set_visible(False)
    fig.tight_layout();chart=target/'后续20人_各组合人数.png';fig.savefig(chart,dpi=180,bbox_inches='tight');plt.close(fig)
    page('人数分配的直观比较',{'type':'figure','path':str(chart),'width':6.4,'caption':'图1  后续20人的完整分组人数。自动质量分组形成单人组，按本轮规则未采用；方案一的质量粗分是另一种人为分档方法。'},
         p('同为20人，不同指标组合可以得到12／8、16／4、6／14等不同人数。人数比较均衡只说明便于继续采集，不能证明分组更有意义或更容易收敛。'))
    detail_order=['Q_median2','QB','QT','QS','QTS','QTB','QSB','QTSB','T','S','B','TS','TB','SB','TSB','Q']
    for m in detail_order:
        items=[p('使用信息：'+names[m]+'。以下是全量历史资料下的候选名单；不是已经冻结的人员身份。')]
        for cohort,label in [('current20','后续20人'),('all26','全部26人')]:
            rr=profiles[(cohort,m)]
            items.append(p(label+'：'+size(cohort,m)+'；资料不足：'+ids(rr[0]['missing_ids'])+'。'))
            items.append(t(['组别／人数','成员编号'],[[f"组{r['label']}／{r['n']}人",ids(r['worker_ids'])] for r in rr]))
            if rr[0]['accepted']:
                for r in rr:items.append(p(f"组{r['label']}平均表现：{r['description']}。"))
            else:items.append(p('该结果因单人组而未采用。这里列名单用于查看自动算法分出了什么，不把单个人的表现称为已验证的一类。'))
        items.append(p('上述“较高／较低／较快”等仅比较本组合的两个组平均值，不表示组内每个人都满足同一特征，也不表示差异已经通过独立验证。不同范围重新分类，名单及含义可能改变。'))
        page('组合详情｜'+names[m],*items)
    v=validation[validation.variant.eq('primary')&validation.cohort.eq('current20')&validation.panel.eq('common')]
    g=v.pivot(index='model',columns='axis',values='group_gain')
    h=stability[stability.variant.eq('primary')&stability.cohort.eq('current20')&stability.panel.eq('native')&stability.half_support.eq('full_requirement')].set_index('model')
    def pc(value):return f'{100*value:+.2f}%'
    page('验证数据一：换图片后，分组是否相似',
         p('把楼分成互不重叠的两批，分别给同一批人分类，重复100次。每一批仍要求至少6份记录、3栋楼；资料不足或分出单人组时，不记为有效比较。'),
         t(['后续20人：方法','可以比较的次数','分组一致程度'],[[names[m],f"{int(h.loc[m,'valid'])}/100",f"{h.loc[m,'ari_median']:.3f}" if pd.notna(h.loc[m,'ari_median']) else '不能估计'] for m in order]),
         p('一致程度为1表示两次分组完全相同，0附近表示与随机对应接近。规则判断包含的不可标图只有9张，拆成两批后无法两边都达到6份要求，因此相关组合的“不能估计”不等于分类失败。'),
         p('这项检查评价人员名单能否重复，不是标法收敛。较宽松的scope补充检查也未显示稳定名单，具体数值保留在上一轮分析文件中。'))
    page('验证数据二：分类能否帮助预测表现',
         p('预测甲楼表现时，只用其他楼的历史记录给人员分类，再与甲楼的实际表现比较。每次都重新分类，所以本页数据不能理解为前面固定名单的考试成绩。'),
         t(['后续20人：方法','质量预测改善','用时预测改善','修改幅度预测改善'],[[names[m],pc(g.loc[m,'quality']),pc(g.loc[m,'time']),pc(g.loc[m,'edit'])] for m in order]),
         p('正数表示相对不区分人员，预测误差减少；负数表示变差，不是正确率。每一列内各方法使用相同目标记录。这里展示的是20人的公平比较；全部26人的公平比较只能共同覆盖24人，与前面各组合自身的覆盖人数不同。'),
         p('质量＋半自动对质量预测改善3.66%，但楼间重抽样的改善范围仍包含零。这是探索结果，不能仅据最大百分比确定方案，也不能由预测分数推断组内标法已收敛。'))
    curves=pd.read_csv(OUT/'stage_curves.csv.gz')
    manual=pd.read_csv(OUT/'manual.csv.gz')
    curves=curves[curves.cohort.eq('current20') & curves.panel.eq('common') & curves.config.eq('q95') &
                  curves.horizon.eq(8) & curves.k.eq(3) & curves.image_id.isin(manual[manual.reference_allowed].image_id)]
    stage_rows=[]
    for m in order:
        z=curves[curves.model.eq(m)]
        image_sets=[set(z[z.arm.eq(a)].image_id) for a in ['G1','G2','ALL']]
        images=set.intersection(*image_sets)
        values=[]
        for a in ['G1','G2','ALL']:
            s=z[z.arm.eq(a)&z.image_id.isin(images)]
            assert len(s)==len(images)
            b=s.groupby('building_id')[['lower','upper']].mean().mean()
            values.append(f'{100*b.lower:.1f}—{100*b.upper:.1f}%' if images else '人数不足')
        stage_rows.append([names[m],str(len(images)),*values])
    page('验证数据三：每种组合的标法稳定性',
         p('后续20人范围；每组取8人，从第3人持续观察到第8人。每种方法内部只比较组1、组2和全体都够人数的同一批图片，且图片必须有可评分参考。各方法的图片数不同，因此本表不能直接排优劣。'),
         t(['分类指标','可比较图数','组1稳定比例','组2稳定比例','全体稳定比例'],stage_rows),
         p('比例来自每张图200个顺序的回放，先按图、再按楼平均。区间下端仅计算明确稳定的顺序，上端把无法判断的顺序也包括在内；这是未知状态带来的范围，不是统计置信区间。'),
         p('分类时始终不用目标楼的记录，因此每张图对应的人员名单可能不同；这里不是前面全量名单固定不变的回放。没有可比较图片只表示本次8人条件下证据不足，不表示该组永远不能稳定。'))
    same=pd.read_csv(OUT/'readable_same39_comparison.csv')
    page('验证数据四：同一批图片上的具体比较',
         p('人员分类确定后，才进行标注回放。这一步才涉及随机抽取人员顺序，与前面的15种指标组合是两件事。每次8名不同人员，同样39张图片，使用200个随机顺序。'),
         t(['人员组合','达到本次稳定判据的图数','代表标注参考偏差'],[[r.name,f'{r.confirmed}/39',f'{r.reference_error:.2f}'] for r in same.itertuples(index=False)]),
         p('判据允许稳定形成多个簇，点数不同必须分簇，每个受支持簇至少2人。表中检查从第2或第3人开始，到第8人是否持续稳定，至少80%的排列明确达标。未达标不是永远不收敛。'),
         p('这里只展示质量粗分与时间分组在共同39张图上的可比实例，不能代替全部指标组合的收敛比较。全部组合的回放已计算，但各组合每张图可用的组内人数不同，不能把不同图片、不同人数的结果拼成一个优劣排名。'),
         p('例如质量＋规则的较小组全量只有4人，无法用这份固定名单观察该类到第8人的稳定性。若希望判断大约第8人开始稳定，并继续观察至少5人，同一张图需至少13名该类人员。200次排列不会增加真实人数。'),
         p('当前结论保持开放：人数、平均特征、名单重复性和标法稳定性是四类证据。方案一可保留为对照，其他组合继续作为候选；尚不能确认哪一套分类最符合子类收敛的要求。'))
    payload=dict(preset='standard_business_brief; memo_masthead; Chinese font override Microsoft YaHei',
                 header='人员分类 · 指标组合、人数与证据',date='2026-09-10',filename='人员分类方案_指标组合与各组人数_修订版.docx',pages=pages)
    assert '导师' not in json.dumps(payload,ensure_ascii=False)
    (target/'document_content.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
    md=[]
    for page_data in pages:
        md += ['# '+page_data['title'],'']
        for b in page_data['blocks']:
            if b['type']=='p':md += [b['text'],'']
            elif b['type']=='figure':md += [f"![{b['caption']}]({Path(b['path']).name})",'']
            else:
                md += ['| '+' | '.join(b['headers'])+' |','|'+'|'.join(['---']*len(b['headers']))+'|']
                md += ['| '+' | '.join(map(str,row))+' |' for row in b['rows']];md += ['']
    md += ['# 复核说明','',
           '源实验、全部敏感性与回放结果均保留在上一级目录。本次重组报告，不重跑或改变原分类、预测与收敛判据。',
           '`classification_inventory.json`每行为一个人员范围×指标组合×候选组；包含人数、名单、资料不足名单、是否采用、状态、组平均指标与描述。所有自动单人组从原人员指标重建，仅作未采用结果的审计。',
           '复现：`python tools/thesis_main/analysis/build_worker_four_block_report_20260910.py --revised`；使用Word运行环境追加`--docx`生成文档。',
           '说明：方案二探索的是选择哪些指标联合分类，未系统比较不同组数、指标权重或逐项高低档交叉分类。组平均描述不等于每个人都符合，也不说明差异已获独立验证。']
    (target/'README_ZH.md').write_text('\n'.join(md),encoding='utf8')
    (target/'CONTENT_QA.json').write_text(json.dumps(dict(combinations=15,additional_baseline=1,cohorts=2,
        inventory_rows=len(inventory),membership_counts_checked=True,singletons_reconstructed_for_audit_only=True,
        all_combinations_have_rosters=True,pages_planned=len(pages),original_analysis_changed=False),indent=2),encoding='utf8')
    print(target,flush=True)


if __name__=='__main__':
    if '--docx' in sys.argv:
        import build_research_validation_report_20260909 as layout
        layout.OUT=OUT/'report_revision_v2' if '--revised' in sys.argv else OUT;layout.build_docx()
    elif '--revised' in sys.argv:revised_content()
    else:content()
