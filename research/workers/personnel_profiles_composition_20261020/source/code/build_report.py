"""Build the compact Chinese research report from the delivered result bundle."""
from pathlib import Path
import argparse, html
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from PIL import Image as PILImage


def build(bundle, destination, font):
    bundle=Path(bundle)
    pdfmetrics.registerFont(TTFont('CJK',str(font)))
    pdfmetrics.registerFontFamily('CJK',normal='CJK',bold='CJK',italic='CJK',boldItalic='CJK')
    ink=colors.HexColor('#203044'); navy=colors.HexColor('#17374B'); teal=colors.HexColor('#147D92')
    muted=colors.HexColor('#566879'); light=colors.HexColor('#EDF3F6'); line=colors.HexColor('#DCE5EB')
    styles={
      'title':ParagraphStyle('title',fontName='CJK',fontSize=25,leading=34,textColor=navy,spaceAfter=14,wordWrap='CJK'),
      'h1':ParagraphStyle('h1',fontName='CJK',fontSize=18,leading=25,textColor=navy,spaceAfter=11,wordWrap='CJK'),
      'h2':ParagraphStyle('h2',fontName='CJK',fontSize=12.6,leading=19,textColor=teal,spaceBefore=9,spaceAfter=6,wordWrap='CJK'),
      'body':ParagraphStyle('body',fontName='CJK',fontSize=10.25,leading=16.8,textColor=ink,spaceAfter=8,wordWrap='CJK'),
      'small':ParagraphStyle('small',fontName='CJK',fontSize=8.3,leading=12.7,textColor=muted,spaceAfter=6,wordWrap='CJK'),
      'cell':ParagraphStyle('cell',fontName='CJK',fontSize=8.8,leading=13,textColor=ink,wordWrap='CJK'),
      'headcell':ParagraphStyle('headcell',fontName='CJK',fontSize=8.8,leading=13,textColor=colors.white,wordWrap='CJK'),
      'hero':ParagraphStyle('hero',fontName='CJK',fontSize=12.5,leading=21,textColor=navy,spaceAfter=10,wordWrap='CJK'),
    }
    story=[]; width=178*mm
    def p(text,style='body'):
        story.append(Paragraph(text,styles[style]))
    def h(text): p(text,'h2')
    def page(title=None):
        if story: story.append(PageBreak())
        if title:p(title,'h1')
    def table(headers,rows,widths=None):
        widths=widths or [width/len(headers)]*len(headers)
        data=[[Paragraph(str(x),styles['headcell']) for x in headers]]
        for row in rows:data.append([Paragraph('—' if x is None else html.escape(str(x)),styles['cell']) for x in row])
        t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,light]),('LINEBELOW',(0,0),(-1,0),.5,navy),('LINEBELOW',(0,-1),(-1,-1),.5,line)]))
        story.append(t);story.append(Spacer(1,8))
    def fig(name,maxheight=160*mm):
        path=bundle/'figures'/name
        if not path.exists():path=bundle/'mechanisms/figures'/name
        if not path.exists():raise FileNotFoundError(path)
        with PILImage.open(path) as im:w,h=im.size
        scale=min(width/w,maxheight/h)
        story.append(Image(str(path),width=w*scale,height=h*scale,hAlign='CENTER'))
        story.append(Spacer(1,6))
    def source(text):p('数据：'+text,'small')

    p('HOHONET\u3000人员画像与<br/>人员组合效益','title')
    p('基于 2026-10-20 GitHub main 的独立研究｜Manual 与 Semi 分开','hero')
    p('主结论：把速度、低尾和错误纠正证据与均 Q 分开看；组队时保留能提供必要局部观察的人。高 Q 人数和慢者人数都不能直接代表每个墙角的有效支持。','hero')
    table(['发现','实际效应与适用条件'],[
      ['Manual 的省工候选','历史 Q 配平的 5 人团队：4 快＋1 慢对 5 慢，B8L2 +0.26，总劳动耗时比 0.536；142 图／22 楼。换成员后 −0.29、耗时比 0.539。'],
      ['少量高 Q 有价值','7 人普通 Manual：1 高＋6 低比 7 低 +1.87 分；3 高＋4 低 +4.45 分。170 图／22 楼。'],
      ['少用高 Q 的代价可量化','6 高＋1 低比 7 高平均 −1.03 分；10.3% 的有限成员比较损失超过 5 分。新批跨建筑复核的同一 29 图损失 −3.66 分。'],
      ['局部贡献可以逆转个体排名','jtc-26：换入者个体 Q 10.30，低于被换者 39.55，却补足一处角点的第三票，使团队 15.14→65.75；劳动增加 7.76%。'],
      ['Semi 需要自己的规则','探索中选出的 1 高＋6 低，跨建筑复核由 +5.22 变为 −2.62 分。高终稿 Q 也可能伴随确认错误初始化未纠正。'],
    ],[42*mm,136*mm])
    p('研究范围不包含新一轮全量人员分类、人员之间的教学或协商。所有组合均是独立标注融合。结果属于当前有限库存内的回顾性研究；正文给出失败、成员变化、来源条件和实际支持量。','small')
    h('本轮完成量')
    p('182 个实际人员画像格；42,521 个高低 Q 精确团队和 45,549 个快慢精确团队，两线合计 88,048 个不同团队键、覆盖 196 张图片。图片和建筑是效应汇总单位，大量同图团队不增加独立图片数。')
    source('[A1–A5] 画像小表；[B1–B5] 质量组合；[C1–C5] 速度组合；[D1–D4] 代表案例。来源代码表见末页及 provenance/source_index.csv。')

    page('1　实际输入、资格与研究库存')
    p('取得 main 提交 6503e2f54966a74352a6ec526f211fc3871c1427，检查当前进度、CONTEXT、研究目录及各实验说明，再读取综合底表、审核证据和冻结融合输入。GitHub Release 的原图可取得；按案例下载并仅保留所用少数图片。历史文档中的“当前／待返回”没有直接作为本轮状态。')
    table(['库存或用途','作答数','图数','本轮用法'],[
      ['全部输入','10,439','261','检查 OOS 与资格，不把全体用于 Q。'],
      ['全部非 OOS','9,217','233','画像和行为库存起点；62 个来源人员 ID。'],
      ['Manual 非门洞索引','7,523','216','保留既有普通、特殊及未记录状态。'],
      ['Manual 门洞','603','17','门洞单列；不并普通 Q。'],
      ['Semi','1,091','41','独立画像和选人；不用 Manual 历史替代。'],
      ['普通主 Q：Manual／Semi','5,719／901','177／32','主画像及普通融合效应。'],
      ['门洞 Q／特殊用途 Q','571／111','17／3 个池','特殊用途 Manual 66、Semi 45 独立保存。'],
    ],[56*mm,29*mm,28*mm,65*mm])
    p('正式质量合计 7,302 份、196 张图片。融合沿用 229 个资格池：普通 Manual 177、门洞 17、普通 Semi 32、特殊 Manual 2、特殊 Semi 1。不同条件可共用同一照片，池数不能当图片数。')
    h('保留原状态，不反向授予资格')
    p('GT 暂停或参考问题作答可进入已有资格允许的几何行为分析，不能因此恢复 Q 或投票。人工筛除、历史未接纳、清洗处置、图片／GT 暂停分别计数。门洞依据既有明确标志单列；doorway_status=not_recorded 等状态仍保留在逐对象索引，普通用途层并不构成一次新的门洞裁定。')
    h('明确缺口')
    p('新批 Semi 的 525 份作答缺逐份精确初始化几何，无法把“报告错误后编辑”判成成功纠正。当前用于研究的时间字段不能建立真实排队、等待与交付到达序列；本轮仅报告其源活动／报告耗时及明确假设下的最大活动耗时。scope 的相容人工裁定没有 OOS 正例，不能估计完整 scope 识别能力。')
    source('[S1–S4] 冻结输入及资格；[A1] record_index.csv.gz 保留逐对象引用和未知状态，不含原几何全集。')

    page('2　画像方案：少量清楚的连续维度')
    p('主画像分别展示通常 Q、同任务相对 Q、Q 低尾、实际耗时、任务调整速度、困难条件水平与变化。scope、错误初始化未纠正和筛除另列，不加入综合总分。')
    table(['维度','主定义','解释与支持'],[
      ['绝对 Q','合格作答 B8L2 均值、Q10、标准差','Q10 为经验第 10 百分位；无 Q 留空。'],
      ['同任务相对 Q','本人 Q 减同任务其余人 Q 的均值，再按本人任务取均值','任务键＝图片＋条件＋目标参考＋版本；单位仍为 B8L2 分。'],
      ['实际 T','本来源合格、正值源时间的中位数','不要求同份作答有正式 Q；分母 source_time_n。'],
      ['任务调整 T','源时间取 log 后减同任务同来源同行 log 均值，个人均值再 exp','小于 1 表示本来源内更快；分母 n_time。不混新旧时间语义。'],
      ['困难适应','困难实际 Q、困难相对 Q、困难相对 Q 减本人简单图相对 Q','同时给图数、楼数；正差本身不代表难图质量高。'],
    ],[30*mm,78*mm,70*mm])
    h('相对 Q 的独立方法比较')
    p('用目标建筑之外的记录预测目标图人员次序。同图排名略有优势，但实际提升很小；任务与人员固定效应没有支持其成为更复杂的主方案。因此沿用容易解释的同行残差，保留其他列供敏感性分析。')
    table(['面板','图／楼','原均 Q','同行残差','同图排名','任务＋人效应'],[
      ['Manual 普通','177／22','63.97%','64.13%','64.39%','64.10%'],
      ['Semi 普通','32／12','64.62%','64.53%','64.70%','64.71%'],
      ['Manual 门洞','17／9','59.96%','60.60%','59.84%','60.39%'],
    ],[36*mm,24*mm,29.5*mm,29.5*mm,29.5*mm,29.5*mm])
    p('表为每图人员配对次序一致率，再图等权；904 条方法×图结果实为 226 个目标任务面板。支持门槛为至少 8 张历史图、3 栋历史建筑。普通 Manual、Semi 各有 59 人达到主 Q 门槛；T 分别 57、54 人。小表仍保留未达门槛的人。','small')
    h('哪些维度重复，哪些有新信息')
    p('新批普通 Manual：绝对 Q 与相对 Q 的人员 Spearman 相关 0.989，相对 Q 与 D10 残差 0.992，与固定效应 0.999；这些主要是同一质量排序。相对 Q 与任务调整耗时只有 0.003，与 Q10 为 0.796。速度、低尾、困难局部表现及 Semi 纠错机会有独立用途。')
    source('[A1] worker_profiles.csv；[A2] quality_model_lobo_summary.csv、profile_correlations.csv。')

    page('3　质量与速度：逐人卡片')
    fig('profile_quality_speed.png',138*mm)
    p('图中 Q、T 至少各 8 图／3 楼；来源和条件分面。点的面积反映 Q 支持量。快慢不是高低 Q 的代名词。下面的时间是本人本来源中位数，Q 与时间分母不同。','small')
    people=pd.read_csv(bundle/'tables/profiles/worker_profiles.csv')
    rows=[]
    for worker,condition,desc in [('W109','manual','快速、整体高 Q'),('W112','manual','慢；难图部分优势'),('W122','manual','高 Q；低尾需关注'),('W126','manual','高 Q、较快、低尾较好'),('W002','manual','困难实际表现突出'),('W102','manual','困难优势且接近常速'),('W011','semi','终稿 Q 与纠错分离'),('W037','manual','筛除负担需并列')]:
        r=people[(people.worker_id==worker)&(people.condition==condition)&(people.panel=='ordinary')].iloc[0]
        rows.append([worker+('·S' if condition=='semi' else '·M'),str(int(r.n_quality)),f'{r.Q_mean:.2f}',f'{r.Q_q10:.2f}',f'{r.source_time_median:.1f}',f'{r.relative_time:.2f}',desc])
    table(['人／条件','Q 数','均 Q','Q10','秒','相对 T','画像提示'],rows,[22*mm,14*mm,20*mm,20*mm,20*mm,20*mm,62*mm])
    source('[A1] 完整 182 格及普通 Manual 62 人／Semi 61 人小表；person_cards.csv 和离线卡片保留更完整支持量。')

    page('4　同图比较揭示均值之外的差异')
    h('W109 与 W112：整体接近，具体条件决定慢者收益')
    p('99 张共同普通 Manual 图／21 楼：均 Q 84.32／84.99，W112 每张都更慢，配对耗时倍率中位数 7.67。图等权 Q 差为 +0.67，建筑等权为 −0.09；两种权重都支持整体接近。')
    table(['共同任务','图／楼','W112−W109 Q','W112／W109 耗时','实际含义'],[
      ['Manual 简单','66／20','+1.01','7.77 倍','大幅时间差，通常质量接近。'],
      ['Manual 中等','18／12','−6.78','5.79 倍','慢者没有收益。'],
      ['Manual 困难','15／11','+8.10','9.46 倍','11／15 图更好；短转折 2.93→3.13，点对 9.53→10.00。'],
      ['Manual 门洞','12／9','−6.54','6.76 倍','普通困难优势不直接迁移。'],
      ['Semi 普通','8／5','−4.80','7.21 倍','没有获得 Manual 同方向支持。'],
    ],[31*mm,23*mm,34*mm,37*mm,53*mm])
    h('W122 与 W126：均值近，低尾差约 11 分')
    p('106 张共同普通 Manual 图／22 楼：均 Q 86.08／86.42，Q10 为 50.11／61.00，同任务残差 Q10 为 −3.70／−0.94。W126 的全画像相对耗时 0.707，W122 为 1.150。低尾和速度可用于同等均 Q 核心的选择。W126 仅 46.2% 的共同图分数更高，因此低尾优势也不等于逐图胜出。')
    p('完整画像的分母不同：W122 为 125 图、Q10 48.89；W126 为 129 图、Q10 60.84。上段只使用共同图低尾，未拼接不同集合。既有 M01／M03 的实际结构例仍显示 W126 会简化别人保留的局部细节，相关资格和人审没有被本轮 Q 排序覆盖。','small')
    h('原图如何支持画像')
    p('本报告第 17 节并列简单正例、困难慢者正例和同角点数反例。尤其 jh4-04 两人都有 12 点对，Q 却为 97.27／47.04；定位和方向差异足以改变质量。不能用“点更多”替代结构是否必要、位置是否正确的检查。')
    source('[A3] W109_W112_paired_records.csv、共同任务摘要、matched_person_pairs.csv；[D4] profile_case_table.csv。')

    page('5　困难适应与额外时间的用途')
    table(['人／Manual','困难图／楼','困难实际 Q','困难相对 Q','困难减简单相对 Q'],[
      ['W002','11／8','87.44','+42.13','+39.85'],
      ['W102','19／13','71.61','+22.80','+8.30'],
      ['W112','20／13','66.47','+19.44','+3.47'],
      ['W109','19／12','59.46','+10.91','−5.67'],
      ['W128','21／13','43.56','−6.12','+0.71'],
      ['W037','10／8','41.20','−6.59','+3.09'],
    ],[29*mm,30*mm,33*mm,38*mm,48*mm])
    p('W002、W102 同时具有有用的困难实际水平和额外相对优势，是值得进一步使用的条件画像。W128、W037 虽然“困难减简单”正值，难图实际及相对质量仍弱；不给它们冠以困难专家标签。图／楼支持请以表中逐人实际记录为准。')
    p('Semi 主普通质量中没有粗难度“困难”的有效机会，相应轴留空。既有几何自遮挡条件另有 96 份、43 人的行为记录，但几何自遮挡不等于粗难度困难，也不等于照片遮挡。短边、小转折、结构简化、范围和高度偏移均在 worker_mechanisms.csv 按原资格保留。')
    h('控制任务和人员后，耗时与哪些变化同时出现')
    table(['来源／条件','每耗时翻倍的 Q 变化','短转折数量变化','解释'],[
      ['新批普通 Manual','+1.025','+0.204','Q 4424 份／175 图；残差相关仅 0.035。'],
      ['旧批普通 Manual','+0.196','+0.109','Q 的关联同样弱。'],
      ['新批门洞 Manual','+6.135','+0.148','仅 17 图，单独报告。'],
      ['新批 Semi','−4.833','−0.049','没有 Manual 的正向收益模式。'],
      ['旧批 Semi','−1.345','−0.046','与新批时间语义分开。'],
    ],[44*mm,41*mm,38*mm,55*mm])
    p('这些是任务＋人员固定效应后的过程关联，可能包含纠结、未记录困难、修改错误初始化等因素；不是延长耗时的干预效果。新批普通 Manual 有向底点偏移与耗时关联接近零（每翻倍约+0.023像素，残差相关0.004），但有向偏移会相互抵消，不能证明定位误差已消失。本轮未计算高度偏移的耗时效应。','small')
    source('[A4] worker_difficulty.csv、worker_mechanisms.csv、time_conditional_associations.csv；逐人难度图另附 PNG。')

    page('6　保留 Q 遗漏的审核与 Semi 行为证据')
    h('197 份筛除／未接纳，与 282 份用途受限分开')
    p('非 OOS 中 492 份不满足 pool_analysis_eligible，其中 282 份仍是 retained 且源独立合格，仅受图片／池用途限制。另有人工筛除 89 份、历史未接纳 108 份、待定 11 份，以及仍 retained 但源不独立 2 份。把 492 全算为人员筛除会误归因。')
    table(['普通 Manual','保留均 Q','筛除／库存','补充解释'],[
      ['W037','58.49','24／97','24 张图；保留 Q 没有计入这些作答。'],
      ['W032','61.58','6／99','与 W034 均分近，筛除负担不同。'],
      ['W034','62.08','14／114','12 份人工筛除＋2 份历史未接纳。'],
      ['W036','74.45','4／96','较好的保留 Q 也应并列审核记录。'],
    ],[38*mm,29*mm,36*mm,75*mm])
    p('当前高筛除主要伴随较弱的保留 Q，也存在同等 Q 下的负担差异。197 份不能全解释为严重误标：只有 10 份历史明确个人错误归因，另 12 份为具体错误文本候选；审核覆盖在来源之间也不统一。新批近零筛除率不等于绝对可靠。没有群体证据支持“越快筛除越多”。')
    h('Semi：成品质量与识别初始化错误分列')
    table(['证据集合','机会／图／楼','未改','可作的解释'],[
      ['旧批，已确认错误初始化','156／6／5','25','有精确初始化证据；138 份仍有当前 Q 资格。其余 131 份编辑后是否纠正未知。'],
      ['新批，报告错误但缺初始化','284 个机会','45','239 份编辑后结果未知；全部新批 525 份均缺逐份初始化。'],
      ['W011，旧批 Semi','确认机会 6 次','6／6','保留均 Q 82.91；不能仅凭终稿 Q 选作初始化错误复核者。'],
      ['W006，旧批 Semi','确认机会 6 次','5／6','保留均 Q 83.31，同样有独立行为信息。'],
    ],[49*mm,39*mm,22*mm,68*mm])
    p('scope：93 个相容人工裁定机会全部为 in-scope，93 次均答对；Manual 25、Semi 68。它只支持这些机会中的判断表现。新批非 OOS Manual 的 1082／5888 次 out-of-scope 回答、Semi 的 36／525 次，只是响应倾向，不能直接写成错误拒绝率。')
    source('[A5] worker_exclusion_reasons.csv、semi_error_opportunity_index.csv、confirmed_error_opportunities.csv；筛除的难度／场景分布在细表保留。')

    page('7　组合实验：选人、对照与统计单位')
    p('所有 H／L 和快／慢标签来自目标建筑之外的既有记录，且 Manual／Semi 各用自己的历史。楼外记录是回顾性历史代理，不声明严格时间先后预测。目标图仅用于确定已有合资格成员容量；目标评分和耗时不参与选人。H／L 是本次对照的历史 Q 水平，并非新发现的永久人员类别。')
    table(['设计','本轮覆盖','对照和边界'],[
      ['高／低 Q','历史同行残差≥0 为 H，<0 为 L；主 n7 全配比；n3–9 可行全比例，n11／13 关键比例','至少 8 图／3 楼；主格点每配比4次成员抽取，新批域2次。普通Manual宽网格按建筑×难度抽1图，其余层全可用池。'],
      ['固定高 Q 核心','H3、H5；追加 L 与追加 H 路径','固定实际核心，同新增人数比较；保存完整路径。'],
      ['精确块替换','n7 真换 2 人；n13 真换 5 人；新批同来源','A 原团队、B 同层换人、C 跨层换人，共同核心相同；比较 C−B。'],
      ['快／慢','新批 allQ n3–9；其余域 n3、5、7；受实际容量约束','同来源一对一匹配：历史相对 Q 差≤3，历史耗时差至少 1.5 倍。'],
      ['同图同人数基线','纯组、全部混合比例、随机组','速度随机组从同面板 2n 个已配平成员抽 n 人；质量随机组从同池历史合格人抽取。'],
    ],[34*mm,66*mm,78*mm])
    h('融合和指标不变')
    p('沿用原预处理、参考绑定、环序、gap=7.5°、MV50 的 ceil(n/2) 支持门槛和中位位置估计。主指标 B8L2，D10 只作同资格敏感性；未按结果修改评分。结构同时观察角点／墙覆盖、未匹配候选角、范围遗漏与扩展；自动“未匹配角”不自动等于语义错误新增结构。底面角点召回 diag_corner_recall_05 采用距离≤0.05×参考面积平方根，不是5%相机高度；角度参考节点／边诊断另标9°。')
    h('把有限团队与独立图片分开')
    p('先同图汇总成员抽取，再建筑等权；区间为 2000 次建筑重采样的描述性 95% 区间。失败独立报告，不填零 Q。配对差仅在双方能评分时计算。Q10、Q&lt;50 和“损失≤2”都是明确阈值下的描述，不冒充人审严重错误或经感知验证的非劣界限。')
    p('质量配比先用 6 栋探索建筑结果固定候选，再查看其他建筑。选人仍是逐目标楼排除的 LOBO，其他验证楼可出现在历史中；这属于已知库存内的跨建筑配比复核。速度 r0／r1 与 r2／r3 用于成员阶段对照，容量造成的精确重复另记。','small')
    source('[B0、C0] REGISTRATION、CANDIDATES_FROZEN 和选择表；[S3] 冻结融合引擎。')

    page('8　Manual：高低 Q 的实际交换价值')
    p('7 人普通 Manual，170 图／22 楼：提高高 Q 人员比例能稳定改善平均结果。单个高 Q 成员的价值已经可见；混合队不需要超过纯高 Q 队，才能体现减少高 Q 需求的用途。')
    table(['团队比较','B8L2 配对差［95%区间］','D10 差','角召回差\n5%尺度'],[
      ['1H6L − 7L','+1.87［+1.10, +2.70］','+1.72','+0.024'],
      ['3H4L − 7L','+4.45［+3.23, +5.72］','+4.16','+0.066'],
      ['5H2L − 7H','−2.16［−2.94, −1.44］','−1.97','−0.039'],
      ['6H1L − 7H','−1.03［−1.67, −0.44］','−0.94','−0.015'],
      ['6H1L − 随机7人','+5.10［+3.83, +6.45］','+4.68','见细表'],
    ],[48*mm,76*mm,23*mm,31*mm])
    p('纯低到纯高的可评分均 Q 约 79.56→89.24，可评分率约 98.0%→99.5%，条件 Q&lt;50 比例约 8.0%→3.6%。这些单独均值的分母可因失败而不同，正文的效应以成对结果为准。')
    h('6H1L：平均接近所需的条件')
    p('全来源比较中，79.1% 的有限成员比较损失不超过 2 分，10.3% 损失超过 5 分。166 张四次成员抽取都可评分的图片中，按建筑等权仅 46.3% 的图四次均在 −2 内，27.6% 至少一次下降超过 5 分。省掉一名高 Q 人员不能自动视作同类成员可任意互换。')
    table(['冻结候选 6H1L − 7H','图／楼','Q 差','含义'],[
      ['探索建筑，全来源','50／6','−0.88','按既定筛选容差选出的最少 H 比例。'],
      ['其他建筑，全来源','44／6','−1.23','平均代价仍较小；区间 −2.66 到 +0.22。'],
      ['相同 29 图，全来源','29／6','−1.29','控制图片容量域的对照。'],
      ['相同 29 图，仅新批','29／6','−3.66','区间 −7.13 到 −1.11；21.2% 比较损失超过 5。'],
    ],[62*mm,25*mm,24*mm,67*mm])
    p('新批全体共同 137 图，6H1L 相对 7H 平均劳动比 0.980、少 55.8 秒，Q −1.37；29 图复核中劳动比 0.965、少 53.8 秒，Q −3.66。其主要价值是少用一名历史 H，总劳动节省很小。这里时间比是逐对比值再图／楼算术汇总，与速度线的对数汇总分列。','small')
    source('[B1] composition_effects.csv；[B2] frozen_candidate_evaluation、n7_member_consistency_summary、source_common_image_comparison；[B5] new_only_n7_labor_summary.csv。')

    page('9　固定核心：追加低 Q 人员为何会稀释')
    fig('fixed_high_core_growth.png',142*mm)
    p('图为双方均能追加至 6 人的共同支持域，Manual H3 为 49 图、H5 为 46 图；全路径表保留各自所有可用图片。它控制了曲线随人数变化时的图片构成。','small')
    table(['固定 H5 核心追加 L','新增1人','新增2人','新增4人','新增6人'],[
      ['相对自身 B8L2（51图／22楼）','+0.09','−2.60','−3.07','−3.68'],
      ['参考边召回变化','+0.017','−0.034','−0.052','−0.068'],
    ],[67*mm,27.75*mm,27.75*mm,27.75*mm,27.75*mm])
    p('同一 H5 核心，同样追加 2 人，L 分支相对 H 分支低 4.44 分、参考边召回低 0.051。H3 加 L1 有 +1.29 分，但加 L2 为 −0.57，继续加 L10 为 −3.14；更多低 Q 票不是持续改善策略。')
    h('一个可直接解释人数门槛的条件')
    p('固定核心 c 人，某局部观察有 s 票。若新增 l 人都不支持这处观察，且原对应分组不变，则该处仅在 c+l≤2s 时保留。例如 H5 核心某处实际只有 3 票：追加 1 人的 n6 门槛仍为 3，追加第 2 人的 n7 门槛变为 4，就会失选。“5 个高 Q 人”并不意味着每个必要角都有 5 票。')
    source('[B3] growth_summary、growth_same_core_matched_summary；[D1–D2] 原成员分组保持不变的实际门槛案例。')

    page('10　来源、Semi 与精确块替换')
    fig('quality_mix_n7.png',123*mm)
    p('主图同时给出全来源、新批及相同图片上的全来源对照。Manual 梯度在新批仍同向；Semi 则依赖来源和成员背景。门洞17图／9楼，各n7配比可评分均Q多在37–39；7L／7H可评分率67.8%／87.0%。普通任务历史Q没有把门洞团队提升到较好的绝对水平。','small')
    h('Semi：本轮没有通过复核的统一高低 Q 配比')
    p('探索的 1H6L 相对 7H 为 +5.22（7 图／3 楼），其他建筑为 −2.62（5 图／4 楼，区间 −11.90 到 +4.01）。在共同 20 图／11 楼，7H−7L 全来源 +1.05，新批 −2.42；共同 5 张复核图为 +2.07 与 −4.10。反向不能仅归于图片容量变化。5H2L 的全体描述性收益约 +0.88，未作为一项已独立复核的新推荐。')
    h('同核心、同实际替换人数')
    table(['新批普通 Manual','L→H 相对换另一批 L','H→L 相对换另一批 H','支持'],[
      ['n7，实际换2人','+5.08［+2.71,+7.33］','−3.29［−5.59,−1.23］','47／46 可评分图，22楼'],
      ['n13，实际换5人','+3.68','−5.64','39／37 可评分图，19楼'],
    ],[40*mm,49*mm,49*mm,40*mm])
    p('同角点数且两边均有唯一循环对应时，n7 H→L 的同层／跨层 BEV 平均距离为 0.0279h／0.0373h（61 事件／35 图）；n13 为 0.0196h／0.0349h（48／27）。h 为相机高度。n13 L→H 距离也增大（0.0281h→0.0443h），Q 却提高：更大的几何更动可能是修正。异数、缺角、失败与距离分别保留。','small')
    source('[B1–B4] composition、source_common、block_summary、block_events；Semi 对应重分组的正向放大见 mechanisms/cases/semi_pruning_table.csv 及对应JSON。')

    page('11　快慢组合：一项实用的省工候选')
    p('新批普通 Manual，在同来源、历史 Q 相近的快慢对之间，5 人“4 快＋1 慢”相对“5 慢”：平均 B8L2 +0.26，D10 +0.25，总劳动耗时比 0.536；142 图／22 楼。Q 的建筑区间为 −1.19 到 +1.81。用约一半源劳动耗时达到近似均值，是此方案最明确的用途。')
    table(['条件／人员域','配比对5慢','图／楼','ΔQ','劳动比','最大活动比'],[
      ['Manual·全部历史Q','3快2慢','142／22','+0.16','0.642','0.682'],
      ['Manual·全部历史Q','4快1慢','142／22','+0.26','0.536','0.539'],
      ['Manual·全部历史Q','5快','142／22','−0.72','0.436','0.389'],
      ['Manual·历史相对Q≥0','4快1慢','77／19','−2.57','0.496','0.560'],
      ['Manual·历史相对Q≥0','5快','77／19','−2.86','0.366','0.320'],
      ['Semi·全部历史Q','3快2慢','18／10','+0.39','0.647','0.722'],
      ['Semi·全部历史Q','4快1慢','18／10','−0.77','0.543','0.593'],
      ['Semi·全部历史Q','5快','18／10','−1.15','0.401','0.377'],
    ],[46*mm,27*mm,27*mm,21*mm,28*mm,29*mm])
    p('“最大活动比”仅是假设同时开始、把源活动时间当作持续工作长度时的 max(T) 比，不是实际日历完成或排队交付时间。速度线时间比均先 log、再图／楼汇总、最后 exp；不把不同来源时间合并，不转为金钱成本。')
    h('与全快、低尾及失败同时比较')
    p('同样 5 人，4快1慢相对5快提高 B8L2 0.95［0.06,1.93］，劳动增加约 22.9%。相对5慢的质量均值接近，但22.8%的有限成员比较仍下降超过5分；“省工≥20%、Q损失≤2、双方完整”的联合比例约60.1%。纯快的对应大损失比例为26.1%。')
    p('4快1慢的每图有限成员 Q10 再图／楼汇总为78.43，5慢78.97、5快78.26。它没有显示对5慢的低尾改善。4快1慢与5慢分别有约0.9%／1.1%的不完整结果；有568次比较、559次双方可评分。失败不填零，不把好均值变成对每个团队的保证。','small')
    source('[C1] main_summary.csv；[C2] 主方案精确成员和结果；阈值为操作性描述。')

    page('12　为何“高 Q 中选快者”仍会掉结构')
    fig('speed_n5_quality_labor.png',131*mm)
    table(['新批 Manual，5人','简单 ΔQ','中等 ΔQ','困难 ΔQ','困难图／楼'],[
      ['全部历史Q·4快1慢','+0.03','+0.01','+0.91','21／12'],
      ['全部历史Q·5快','+0.10','−0.76','−2.47','21／12'],
      ['历史相对Q≥0·4快1慢','−0.69','+1.19','−7.91','14／8'],
      ['历史相对Q≥0·5快','−0.82','+2.77','−10.01','14／8'],
    ],[63*mm,27*mm,27*mm,27*mm,34*mm])
    p('高相对 Q 域的纯快难图参考角召回下降 0.142、墙覆盖下降 0.117；保留一名慢者仍不足以复制五名慢者的局部支持。在相同77张图片上，allQ 的4快1慢为−0.14，而高相对Q域为−2.57，差异不只是图片容量改变。')
    p('解释性连接进一步否定了一个过于简单的说法：高相对Q域的快者整体楼外Q只比慢者高0.003，困难历史相对Q反而高0.702；困难目标子集高0.841。慢者融合优势不能归因为其平均困难Q更高。局部结构的共同支持分布提供了均Q之外的信息，jtc-26 给出直接证据。','small')
    source('[C3] difficulty_summary、speed_n5_common_target_domains、speed_n5_historical_difficulty_summary；该连接未重新选人或融合。')

    page('13　成员、人数与不适用的情况')
    fig('speed_sizes_sources.png',134*mm)
    h('新成员组合保住的是省工幅度')
    p('Manual allQ 的4快1慢，r0／r1 为 Q +0.81、劳动比0.534；r2／r3 为−0.29、0.539。后两轮284个比较中有5个与前两轮完全重复，279个不同的比较覆盖全部142图。没有把重复团队当新成员证据，也没有稳定的质量超越。')
    p('新批 Manual 一慢方案 n3–9 的均Q变化为−1.03到+0.53，劳动比0.501–0.632；不同 n 的图片容量不同，不能把曲线当同一组核心不断加人。奇偶人数均能省工；门槛的解释应看固定成员路径。')
    h('Semi、门洞与旧批时间缺口')
    p('新批 Semi 一慢方案 n7／n8 质量差分别−4.04／−7.60，仅11图／7楼和5图／4楼；n3–6较接近，仍应独立验证。高相对Q域只够n3，2快1慢为−6.86（8图／6楼），没有n5结论。')
    p('门洞新批4快1慢为−0.77（13图／9楼），但纯慢可评分均Q仅26.66，双方仅约48.6%的图／楼加权比较均可评分；失败比例约38.0%／29.2%。此处小均值差不构成可用的近质省工方案。旧批 Manual n5纯快／纯慢136次比较只有16次时间齐全，n7为4／84；不能用目标匹配时间补源时间缺失。')
    source('[C1、C4] main、member_check、building_subset、capacity；本轮未声称重建真实到达阶段或现场带动。')

    page('14　原图机制：高 Q 仍占多数，也会失去必要角')
    fig('manual_Uw22_local_dilution.png',226*mm)
    p('Uw-22：固定5H，5H3L→5H4L时n8→9，局部4H支持未增加，门槛4→5，当前参考中的关键角点失选；B8L2 84.68→62.14。既有观察对应分组在关键步骤未变，证据支持局部支持／门槛解释。完整增长路径与每个成员的原观察已保存。[D1]','small')

    page('15　原图机制：较低 Q 人员补足高 Q 核心的缺口')
    fig('manual_e9z19_lowQ_complement.png',226*mm)
    p('e9z-19：固定5H，n9→10加入W101，原2H2L的4票成为2H3L的5票并达门槛；Q56.81→89.45，遗漏22.95%→2.79%。n11再加不支持该处的W031，门槛升6，Q回落55.26、遗漏23.58%。该局部的两条直接相邻边也获得补足，关键步骤无既有观察重分组。[D2]','small')

    page('16　原图机制：更低个体 Q 的慢者也能贡献关键信息')
    fig('manual_jtc26_speed_complement.png',225*mm)
    p('jtc-26：固定W103/W128/W104/W116，W113→W106；全队历史Q均差仅+0.067。W104/W116已有2票，W106补第3票，W113未表达。团队15.14→65.75；换入者个体Q反而39.55→10.30。新增节点的前接边仅1人直接画出、2人的完整来源环提供投影支持；仍缺3/8参考节点。源劳动3458.73→3727.09秒，max活动均1505.46秒。[D3]','small')

    page('17　原图画像：慢者的正例与反例同时保留')
    fig('profile_W109_W112.png',228*mm)
    p('原图来自Release；人员线为现有冻结预处理后的原人员标注，参考使用已绑定有效版本。b8c-07展示同质大时间差；yq-29展示慢者范围／结构收益；jh4-04同为12点对却定位与方向相差很大。未重新评分这些个体作答。[D4]','small')

    page('18　归因、实际建议与需要人工判断的点')
    h('画像怎样解释组合，以及哪些解释未成立')
    p('Q和速度为不同维度，所以能找到省工而均Q接近的人；低尾和审核记录防止只看保留均值；困难画像揭示W002/W102等额外条件优势。团队层面还需要局部观察支持：jtc-26中个体Q更低的人提供有用的一票，Uw/e9z则显示全局H比例不能决定每处结构是否过半。高Q快者的平均困难历史并不低，仍发生难图融合损失，说明仅靠更多连续均值也不能完整解释组队。')
    h('已见收益与未见收益')
    table(['建议优先实施','依据和边界'],[
      ['Manual普通图：以5快、4快1慢、5慢作小规模候选比较','4快1慢的省工在换成员后仍成立；质量大损失和低尾同时记录。以楼外Q/T选择，继续保持源时间语义。'],
      ['低Q团队：优先争取少量高Q名额','n7的1H、3H均有平均质量和结构增益；作用是改善有限低Q池。'],
      ['高Q名额紧张：6H1L作为有代价选项','平均省一名H的Q代价约1分，但新批其他建筑可到3.66分；总工时节省仅约2%。'],
      ['固定高Q核心：关注临界局部支持','不要以“加入更多独立票”作为默认改进；n6→7、n8→9等门槛变化前保留结构支持账本。该建议不修改当前融合规则。'],
      ['Semi：单列初始化错误机会与小队伍研究','本轮高低Q配比未通过稳定复核；不迁移Manual的快慢结论。'],
    ],[64*mm,114*mm])
    p('未见支持的方案：持续向H核心追加L、把5H2L当纯H近似替代、把高Q域全快视作无需结构代价、把Semi探索的1H6L直接应用到其他建筑。其失败分别表现为门槛失选、约2.16分均值下降及20.0%的&gt;5分损失、高Q困难图结构支持不足、来源／成员背景敏感。')
    h('一项进一步归因时需要人工核对的案例')
    p('本轮精选图没有新增必须暂停并重裁的参考。Z6-10 Semi值得保留作后续对应判读：n8→9、n10→11去掉额外节点使Q79.91→91.78、79.62→89.14，但新增低Q者也支持该点，旧成员W037/W134的观察发生重分组。若要进一步归因到具体人员或初始化，需人工核对这些观察是否属于同一真实墙角，并取得编辑证据。当前只能归为对应算法＋门槛的有利放大；n11底面5%参考尺度角点召回仅0.50，点数恢复不等于细部定位恢复。jtc-26保留前接边的1人直接支持、2人投影支持及仍缺3/8节点的限定，不据此新增参考暂停。')
    p('下一批最有价值的新增输入是逐作答精确初始化与纠错结果裁定、能区分活动／等待的记录，以及相容的scope OOS机会。这些是当前问题的输入缺口；本轮没有补造。','small')

    page('19　成果连接与复现')
    h('最短使用路径')
    p('先看主报告和 figures/、mechanisms/figures/，再按人员从 tables/profiles/ 的两个小表查看支持数。主要组合汇总在 tables/quality/ 与 tables/speed/。claims/ 保留主结论相关的成对成员、输入引用、参数和结果；mechanisms/ 保留少数代表团队的处理点、冻结参考、完整支持与必要原图。')
    table(['连接实体','主键／字段','用途'],[
      ['作答','object_id，worker_id，condition，origin','接回研究台对象；不把来源ID推为现实身份。'],
      ['任务与参考','image_id／image_code，pool_id，chosen_target_id，reference_id／reference_version','图片展示和参考绑定；条件、用途、版本必须一起看。'],
      ['历史画像','target_building＋worker_id＋condition＋origin＋panel','目标楼外选人；Q/T各自图数、楼数和支持布尔列。'],
      ['精确团队','team_key，member_workers，member_object_ids','同成员同池识别重复，连接保存几何与复算。'],
      ['组合设计','n，H/L或n_fast/n_slow，source_policy/domain，replicate，phase/member_stage','图区分探索、来源、成员复核；不扩大独立样本数。'],
      ['资格和缺失','quality_use，quality_usable，cleaning_disposition，source/pool/independent资格，score_status','无评分留空；失败、异数及暂停分别统计。'],
    ],[29*mm,80*mm,69*mm])
    h('实际新增计算与引用旧结果')
    p('画像重新计算同行Q／时间残差、LOBO特征、逐人统计与4种Q方法比较；个体B8L2/D10、原几何定义、审核与初始化证据沿用现有结果。质量主实验42,521个精确团队：42,503原生计算、18直接复用旧精确结果。速度45,549个团队全部原生计算，其中124个键在旧标量档案中已有记录，但新几何诊断仍需实际几何。两线有22个团队键重合，合计88,048个不同键。')
    p('质量线40,520个团队可评分，2,001个不可评分；速度43,922个可评分，1,627个不可评分（no_connection 1172、below_four 395、invalid_floor 60）。失败保留。50个机制团队重放及少量引擎点验不计为新增效益样本。旧F01 n13／换2人的时间结果、M01/M03人审、q9-30对应问题只作既有背景引用，未伪装成本轮新发现。')
    h('复现入口与依赖')
    p('README.txt 给出分支命令；code/replay_claim_teams.py 可只重算主结论成员，mechanisms/code/replay_selected_cases.py 可只重算少数案例。完整搜索可由固定seed与注册参数生成。需要本报告指定main的现有底表和冻结引擎；不需原图全集来评分，图像只用于叠加展示。')
    p('本轮运行：Python 3.12.14、NumPy 2.3.5、pandas 2.2.3、SciPy 1.17.0、Matplotlib 3.10.8、Shapely 2.2.0。PDF用ReportLab 4.4.9；中文绘图使用Noto Sans SC。依赖清单、精简输入哈希、代码和必要结果均附。未打包虚拟环境、仓库副本、全量逐队几何、原图全集或全量中间缓存。','small')

    page('20　来源索引与参考资料')
    table(['索引','本轮结果文件／原始入口'],[
      ['A1','tables/profiles/worker_profiles.csv；ordinary_manual_profiles_small.csv；ordinary_semi_profiles_small.csv；record_index.csv.gz。'],
      ['A2–A5','Q方法摘要、相关表；共同人员对；difficulty/mechanisms/time_associations；筛除理由和Semi机会。详细字段见notes/PROFILE_FIELDS.txt。'],
      ['B0–B5','provenance/quality_REGISTRATION.json；质量composition、冻结候选、growth、block、共同图片域和新批劳动表。'],
      ['C0–C5','provenance/speed_REGISTRATION.json；速度main/difficulty/member/building摘要；相同图片域和困难历史连接。'],
      ['D1–D4','mechanisms/cases/CASE_INDEX.csv；Uw-22、e9z-19、jtc-26、Z6-10输入与支持；profile_examples.json及对应图片。'],
      ['S1','research/statistics/v2_integrated_analysis_20261019/tables.json.gz：quality__shared_records。'],
      ['S2','research/statistics/v2_evidence_audit_20261019/records.json.gz；research/difficulty/difficulty_mechanisms_v2_20261020/record_conditions.csv.gz。'],
      ['S3','research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz；冻结fusion_engine、measurement_engine及working_models。'],
      ['S4','人员标法、难度机制、融合变化机制、人员可互换性和已归档组合研究；优先阅读文档及本次用户scope补充。'],
    ],[23*mm,155*mm])
    p('仓库：<link href="https://github.com/Sparkling-Flames/3D_Manhattan_label">https://github.com/Sparkling-Flames/3D_Manhattan_label</link>。本报告将当前仓库作为项目一手数据与代码来源，不把项目说明冒称已发表论文。固定提交、关键输入哈希、Release原图来源及本轮运行回执见 provenance/。','small')
    h('用于范围解释的英文一手研究')
    p('Yu-Ju Tsai, Jin-Cheng Jhang, Jingjing Zheng, Wei Wang, Albert Y. C. Chen, Min Sun, Cheng-Hao Kuo, Ming-Hsuan Yang. 2024. <i>No More Ambiguity in 360° Room Layout via Bi-Layout Estimation.</i> Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), pp. 28056–28065.','small')
    p('官方PDF：<link href="https://openaccess.thecvf.com/content/CVPR2024/papers/Tsai_No_More_Ambiguity_in_360deg_Room_Layout_via_Bi-Layout_Estimation_CVPR_2024_paper.pdf">CVF Open Access PDF</link>；预印本：<link href="https://arxiv.org/abs/2404.09993">arXiv:2404.09993</link>；项目：<link href="https://liagm.github.io/Bi_Layout/">liagm.github.io/Bi_Layout/</link>。该文把不同布局范围表达分开，支持将范围政策、可见性与可表达性分开讨论；它不为本轮人员或组队数值提供外部证明。','small')
    h('阅读限制')
    p('参考不确定性、被筛除作答的补人投入、真实交付次序与新人员泛化均未在本轮被消除。正文给出了这些边界对应的实际可见效应，没有把它们用于回避对当前库存的判断。所有未满足资格的评分、缺失时间和未知纠错结果保持为空。','small')

    class NumberedCanvas(canvas.Canvas):
        def __init__(self,*a,**kw):super().__init__(*a,**kw);self._pages=[]
        def showPage(self):self._pages.append(dict(self.__dict__));self._startPage()
        def save(self):
            n=len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self.setStrokeColor(line);self.setLineWidth(.5);self.line(16*mm,15*mm,194*mm,15*mm)
                self.setFont('CJK',7.6);self.setFillColor(muted)
                self.drawString(16*mm,10.5*mm,'HOHONET｜人员画像与组合效益｜2026-10-20')
                self.drawRightString(194*mm,10.5*mm,f'{self._pageNumber} / {n}')
                super().showPage()
            super().save()
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(destination),pagesize=(210*mm,297*mm),rightMargin=16*mm,leftMargin=16*mm,topMargin=16*mm,bottomMargin=20*mm,title='HOHONET 人员画像与人员组合效益研究',author='HOHONET research synthesis',pageCompression=1)
    doc.build(story,canvasmaker=NumberedCanvas)
    print(destination)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--font',type=Path,required=True)
    a=p.parse_args();build(a.bundle,a.out,a.font)
