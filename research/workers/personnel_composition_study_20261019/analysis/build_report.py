"""Build the compact Chinese scientific report from frozen, small result tables.

Run from the deliverable root.  This script does not refit labels, change references,
or select new fusion rules.  Tables used in the main report are exported alongside
the report with source row identifiers.  Figure sources remain separate and exact.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, re
from pathlib import Path
from xml.sax.saxutils import escape
import pandas as pd
from PIL import Image as PILImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
    Spacer, Table, TableStyle, Image, PageBreak, KeepTogether, Flowable)

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / 'analysis'
OUT = ROOT / 'output'
W, H = A4
MARGIN = 42
CW = W - MARGIN * 2
CH = H - 88
INK = colors.HexColor('#183242')
MUTED = colors.HexColor('#526676')
TEAL = colors.HexColor('#176F86')
ORANGE = colors.HexColor('#B56427')
LIGHT = colors.HexColor('#EDF3F6')
GRID = colors.HexColor('#D4E0E7')
styles = {}
pages = []
source_tables = {}


def norm(s):
    return str(s).replace('\u2011','-').replace('\u2013','-').replace('\u2014','-').replace('\u2212','-')


def P(text, style='body'):
    return Paragraph(norm(text), styles[style])


def plain(text, style='body'):
    return P(escape(norm(text)), style)


def p(text):
    return P(text)


def h(text):
    return P(text, 'h2')


def note(text):
    return P(text, 'note')


def tag(text):
    return P(text, 'tag')


def gap(h=6):
    return Spacer(1,h)


def table(rows, widths, font=9.2, header=True):
    if max(widths) <= 1:
        widths=[CW*x for x in widths]
    assert abs(sum(widths)-CW)<1.0, (sum(widths),CW)
    body_style = ParagraphStyle('table'+str(font),parent=styles['table'],fontSize=font,leading=font*1.35)
    head_style = ParagraphStyle('thead'+str(font),parent=body_style,fontName='NSCB',textColor=colors.white)
    body=[]
    for i,row in enumerate(rows):
        sty=head_style if header and i==0 else body_style
        body.append([Paragraph(escape(norm(v)).replace('\n','<br/>'),sty) for v in row])
    t=Table(body,colWidths=widths,hAlign='LEFT',repeatRows=1 if header else 0)
    commands=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),
              ('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),
              ('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,-1),.4,GRID)]
    if header: commands += [('BACKGROUND',(0,0),(-1,0),TEAL)]
    for i in range(1 if header else 0,len(body)):
        if i%2:commands += [('BACKGROUND',(0,i),(-1,i),LIGHT)]
    t.setStyle(TableStyle(commands))
    return t


def fig(path, max_h=420, width=CW):
    path=ROOT/path
    iw,ih=PILImage.open(path).size
    scale=min(width/iw,max_h/ih)
    im=Image(str(path),width=iw*scale,height=ih*scale)
    im.hAlign='CENTER'
    return im


def page(title, items, kicker='人员类别构成与融合结果研究'):
    flow=[P(kicker,'tag'),P(title,'title')]+items
    pages.append((title,flow))


def load_results():
    return pd.read_csv(A/'composition/frozen_grid_results/frozen_rule_compact.csv')


def exact_rule(df, rule, n, comparison, phase='validation', difficulty='all', stage=None):
    s=df[(df.rule_id==rule)&(df.k==n)&(df.comparison_label==comparison)&
         (df.phase==phase)&(df.reported_difficulty==difficulty)]
    if stage:s=s[s.stage==stage]
    assert len(s)==1,(rule,n,comparison,phase,difficulty,len(s))
    return s.iloc[0]


def fmt(v, n=2, sign=False):
    if pd.isna(v):return '缺失'
    return f'{float(v):+.{n}f}' if sign else f'{float(v):.{n}f}'


def setup(font, bold):
    pdfmetrics.registerFont(TTFont('NSC',str(font)))
    pdfmetrics.registerFont(TTFont('NSCB',str(bold)))
    pdfmetrics.registerFontFamily('NSC',normal='NSC',bold='NSCB',italic='NSC',boldItalic='NSCB')
    for name,size,lead,color,fontname in [
       ('body',10.4,16.1,INK,'NSC'),('note',8.5,12.5,MUTED,'NSC'),
       ('table',9.2,12.7,INK,'NSC'),('title',21,28,INK,'NSCB'),
       ('h2',12.1,18,TEAL,'NSCB'),('tag',8.4,12,TEAL,'NSCB'),
       ('small',9.4,14,INK,'NSC')]:
        styles[name]=ParagraphStyle(name,fontName=fontname,fontSize=size,leading=lead,
            textColor=color,wordWrap='CJK',alignment=TA_LEFT,spaceAfter=7 if name=='body' else 5,
            allowWidows=0,allowOrphans=0)


def make_main_pages():
    df=load_results()
    selections=[
      ('历史相对Q：纯高 - 纯低',exact_rule(df,'H1_Q_quantile',5,'higher_class_pure_minus_lower_class_pure')),
      ('历史相对Q：纯高 - 纯低',exact_rule(df,'H1_Q_quantile',9,'higher_class_pure_minus_lower_class_pure')),
      ('历史关系：纯G2 - 纯G1',exact_rule(df,'H3_reverse_relation',9,'higher_class_pure_minus_lower_class_pure')),
      ('几何角色：纯R5 - 纯R2',exact_rule(df,'H4_detail_role',5,'detail_pure_minus_common_pure')),
      ('困难角色：H2从2人增至3人',exact_rule(df,'H5_hard_structure',5,'detail_count_2_to_3',difficulty='hard')),
      ('困难角色：H2从3人增至6人',exact_rule(df,'H5_hard_structure',9,'detail_count_3_to_6',difficulty='hard'))]
    saved=[]
    rows=[['冻结比较','人数','ΔB8L2','有效图 / 楼','正图 / 负图']]
    for label,r in selections:
        saved.append(dict(report_label=label,**r.to_dict()))
        rows.append([label,int(r.k),fmt(r.building_B8L2_change_mean,2,True),
                     f'{int(r.quality_paired_images)} / {int(r.paired_buildings)}',
                     f'{int(r.positive_gt0_images)} / {int(r.negative_ltminus0_images)}'])
    source_tables['main_frozen_effects.csv']=pd.DataFrame(saved)

    page('类别构成确有作用，但作用有边界',[
       p('<b>最可复用的结果，是提高历史质量较好人员的比例；最清楚的条件机制，是细节角色比例与融合票数门槛的交互。</b>反向类别能够解释一部分形状与结构差异，但本轮没有得到跨建筑稳定胜过相关最佳纯类的通用混类配方。'),
       table(rows,[.39,.08,.13,.20,.20],9.5),
       note('ΔB8L2 为同图构成均值之差，先在建筑内平均，再对建筑等权。正负图数按可评分的配对图片计。每行使用冻结规则，具体团队与失败分母见第7页和证据 [E2]。困难角色只适用于已有同口径、目标范围与参考版本相符的困难判定。'),
       h('同类换人：有稳定构成，也有稳定但错与近分异形'),
       p('验证中，历史Q纯高类的9人构成，类内平均 |ΔQ| 为 <b>2.01</b>，主联合稳定率 <b>71.2%</b>；纯低类相应为 <b>4.26</b> 和 <b>48.0%</b>。实际平均只换约1.64人，不能解释为整队可随意互换。高细节角色全局仅6人，其5人纯类的换人机会更有限。[E3]'),
       h('保留赢家，也保留代价和反例'),
       p('一个13人混类构成在同图新团队中重现了 <b>+11.51</b> 的平均增益，但同构成分数仍横跨38.87-78.67。另一个初筛很突出的9人混类，在新成员复查中不再胜过较好纯类。加1人的门槛案例可使Q从94.69降至51.40；另有案例Q上升19.72分而真实转角召回下降。[E2、E5、V1]'),
       note('本轮实际执行589,990条请求，跨阶段去重583,261个池内人员集合，覆盖106张图、12座非历史建筑、59人。独立性来自图片与建筑，不能来自重复团队数量。既有v2已多轮探索，本轮是回顾性建筑留出与已知人员的新团队复查，不是全新外部盲测。[D1、D2、A1]'),
       h('阅读路线'),
       p('第2-6页说明数据、覆盖与类别；第7-12页看冻结构成、换人稳定、来源/Q/人员及人数效应；第13-22页为正例和反例图解；第23-27页说明任务条件、选人规则、评价边界与精确复现。')
    ],'研究报告 | 2026-10-19 | 固定融合 / 固定参考 / B8L2主评价')

    page('研究对象、数据资格与建筑隔离',[
       p('研究单位是 <b>方法×类别人数向量×总人数×图片条件</b>。例如“3G1+10G2”是13人的构成；类别字母或编号不意味着固定五类、固定四人团队。各方法的C01只在该方法内有意义，不能跨方法当成同一群人。'),
       table([
         ['输入层','冻结池数','本轮的用途'],
         ['普通Manual','177池 / 5,719份','主分析；按建筑分历史、发现、验证'],
         ['门洞Manual','17池','本层历史分类与本层对照；失败单独呈现'],
         ['普通Semi','32池','新旧来源分别分析；最终Q与纠错机会分开'],
         ['特殊Manual / Semi','2池 / 1池','没有历史支持可训练的本层类别；仅描述性实算'],
         ['正式质量与库存','7,302份 / 10,439份','正式质量196图、60人；库存不等于可评分样本']
       ],[.26,.24,.50],9.5),
       gap(5),
       table([
         ['建筑层','普通Manual支持','难度：易 / 中 / 难','用途'],
         ['历史：10楼','81图 / 2,578份','53 / 16 / 12','只由这些建筑生成历史特征与类别'],
         ['发现：6楼','51图 / 1,698份','32 / 9 / 10','广覆盖搜索、提出和冻结比较规则'],
         ['验证：6楼','45图 / 1,443份','29 / 7 / 9','冻结后首次计算本轮验证结果']
       ],[.20,.27,.23,.30],9.3),
       p('划分只使用元数据的覆盖与平衡：固定种子2026101901，在20,000个候选划分中确定10/6/6楼。目标建筑的Q、几何、参考或投票不进入人员标签；FULL画像仅作描述。验证前于 <b>2026-10-19 09:40:19 UTC</b> 冻结H1-H11、类别、参数、种子与生成代码。[D2]'),
       p('继承既有坐标、平均x、历史删点、环序、人工参考、暂停/GT处理与OOS资格，不从原始导出重加工。逐项核对7,302份正式记录的人员、来源、点坐标、Q及参考与冻结输入一致。普通/门洞/Semi/特殊层不互相填补机会。[D1、A1]'),
       note('主仓库：e572eb73bedc4fe9056df838e458bab83c3fa423；科学运行时：82c6164b0d4630de5316199c92aa405930973168。完整建筑名单在SPLIT.json。既有A、独立审查、B3和局部簇构成研究用于复用输入、代码及提出问题；这些单人或局部簇结果没有被当成构成研究已完成的证明。同房预测仍为旁支。')
    ])

    coverage=pd.read_csv(A/'composition/coverage/stage_coverage.csv')
    names=['均匀真实团队筛查','广覆盖构成发现','同规模类别块发现','整数比例/人数发现','门洞与Semi发现','新成员复查：发现楼','固定成员递增链：发现楼','整数比例/人数验证','新成员复查：验证楼','同规模类别块验证','固定成员递增链：验证楼','门洞与Semi验证','特殊条件描述']
    rows=[['阶段','请求数','不同团队*','图 / 楼']]
    for label,(_,r) in zip(names,coverage.iterrows()):
        rows.append([label,f'{int(r.requests):,}',f'{int(r.unique_teams):,}',f'{int(r.images)} / {int(r.buildings)}'])
    page('搜索覆盖：做了什么，哪些没有穷举',[
       table(rows,[.46,.18,.19,.17],8.8),
       note('*阶段内不同团队不能相加。跨阶段以“冻结池＋排序后的实际人员集合”去重后为583,261队；重复输出逐一核对一致。13阶段共589,990条请求，全部完成，无缺计算。[D1]'),
       p('<b>类别数与方法：</b>实际探索K=2、3、4、5、6、8；未试K=7。157个正向方法、62个反向方法及10个基线，共229个方法ID，域展开为245个实例，其中16个没有普通Manual筛查机会；并非245套都做了完整配比网格。均匀筛查不依赖哪个方法获胜。[F1、F2、E1]'),
       p('<b>组合覆盖：</b>广覆盖入选的932个方法×池×人数范围内，共269,732个可行构成，取36,009个、省略233,723个；其中590组的构成全枚举。超上限时保留纯类、等额、池比例并用最远L1抽样，上限64或32，每向量至多4或3个实际团队。K6/K8各只测30/51个发现池。后续仅对声明比例线全取可行整数位置，每点至多6或10队；不是高维全部配比的全面遍历。[D2]'),
       p('<b>人数与遗漏：</b>筛查包括3-7、9、13、17、21、25、29、33人及实际全池；稠密曲线的总体并集含3-21、25、29、33人，但不是每种方法在每张图上都全覆盖。没有新外部图片、新未见人员、N1或改良融合实验。容量不足、零可行曲线、单队构成、抽样核心未找到都保留在台账，未找到不自动等于数学上不可能。'),
       note('简要台账：SEARCH_LEDGER.csv；完整候选筛查：screen_final/candidate_search_ledger.csv.gz；逐构成覆盖缺口：frozen_contrast_coverage_gaps.csv.gz 与 integer_curve_availability.csv.gz。')
    ])

    page('正向与反向：都从历史重新建立类别',[
       table([
         ['路线','实际采用的表达与方法','保留的限制'],
         ['正向：157个定义','绝对/相对Q，残差低尾与波动；T的来源内校正；困难适应；点数、垂直结构、scope；Semi机会特征。规则分层、交叉规则、缺失感知距离、平均连接、中心成员、KMeans与GMM。','151个定义形成至少2个有支持类别，147个不同的有效划分；6个机会不足定义保留失败。没有把所有变量合成一个总分。'],
         ['反向：62个方法ID / 78个方法×域','81张历史图的标法共簇关系、9°/12°相似性、层次/谱聚类、来源基线残差关系；13维几何角色的稳健聚合与Ward分类；另做易/中/难条件角色。','训练只读历史标注几何，不读目标评价，也不以当前图片的簇直接给人员跨图贴标签。Q只在训练后解释。'],
         ['必要对照','仅来源分组及9个固定随机划分；相同实际团队、相同交叉验证模型容量；多类、小类与条件类机会审查。','随机划分是有限基线，不是完整零分布。小类“赢家”可能只对应特定人员。']
       ],[.20,.49,.31],9.1),
       h('质量、时间与机会不混为一个能力'),
       p('相对Q为历史任务效应校正后的人员效应β；另保留绝对均值、低10%分位、残差波动及难度细分。全域Q历史支持55人，T支持54人，中等/困难质量支持40/37人。5人没有合格全域历史标签，记未知，不塞入低类。[F1]'),
       p('旧Semi的已确认错误后未改、新Semi的报告错误后未改与一般修改倾向分别建特征；确认纠正单独对待，没有由修改或质量增益推定后混入标签。旧批有185个可归属初始/最终质量对；新批缺少逐份初始几何的部分没有净改善结论。旧已确认错误未改特征无人满足3次机会且跨2楼，不能产生可靠“盲信类”。[F1]'),
       p('scope回答倾向有充分支持的35人全部为新批；有限的范围内兼容裁定机会只有47条，来自另外24名旧批人员，每人1-2条。这不是双向scope判断金标准，不能用来验证新批回答倾向等于裁定正确能力。缺机会、未知与来源缺失模式分别保留。新批T为已处理的报告时间，不重新解释为已审计原始日志。[F1、A1]'),
       note('独立泄漏检查：正向的非历史记录扰动不改变历史特征；反向在4,033条非历史记录、16,132处赋值被扰动后标签不变。历史删楼稳定性用于诊断标签敏感性，不充当目标建筑验证。[F1、F2、A1]')
    ])

    page('可解释类别：用方法内名称，避免混名',[
       table([
         ['简写 / 方法','类别与人数','历史解释及用途'],
         ['Q低 / Q中 / Q高\nF_rule_Q_quantile_K3','19 / 18 / 18人','历史相对Q三分位：β≤-4.50724、-4.50724至0.82217、>0.82217。H1主构成；只是明确分层，未证明自然存在三种人。'],
         ['Q阈低 / 中 / 高\nF_rule_Q_threshold_K3','22 / 20 / 13人','β≤-3、居中、β≥3。类别块与若干曲线用此法；它与Q三分位不是同一批成员。'],
         ['G1 / G2\n来源基线调整的历史共簇关系两群','27 / 28人','G1：旧14新13，历史β均值-4.95、绝对Q65.37；G2：旧6新22，β+4.24、Q74.28，历史主簇占比更高。Q未参与聚类，但群仍携带Q和来源信息。'],
         ['R1-R5\n历史几何角色五类','18 / 19 / 7 / 5 / 6人','R5相对细节较多且历史Q高：β+16.07、绝对Q86.08；R4五人全旧批、相对点数较少。R1/R2是两个常见角色，不能简单等同低/高能力。'],
         ['H1 / H2\n已有困难条件的历史几何角色两类','30 / 7人','H1含28新2旧；H2全新，历史β+15.66、绝对Q85.63，细节角色更集中。适用难度条件必须独立明确。']
       ],[.29,.17,.54],9.2),
       h('关键小类的精确成员'),
       p('<b>R5：</b>W109、W112、W115、W122、W126、W130。<br/><b>H2：</b>W102、W109、W112、W115、W122、W126、W130。<br/><b>Q三分位高类：</b>W002、W008、W015、W030、W033、W035、W036、W102、W104、W108、W109、W112、W115、W118、W122、W126、W130、W134。'),
       p('G2不是“已去除所有来源效应”的类型。来源NMI从原始关系二类的0.488降至0.076，但其Q方差解释仍为35.4%，仅新批中为46.6%。G类历史删一楼ARI均值0.854、最低0.663；R五类为0.579。另一关系二类ARI仅0.113，未作为稳健类别主推。[F2]'),
       note('精确映射：SELECTED_WORKER_CLASSES.csv；全部候选映射保留于forward/results/worker_labels.csv.gz及reverse/worker_labels.csv.gz。R5的“细节较多”是历史相对点数/角色描述，不等于每张困难图都好；其困难减容易历史差值均值为-1.87。[F1、F2]')
    ])

    page('整体分类有用，控制Q后增量依赖条件',[
       fig('analysis/figures_summary/01_candidate_utility_coverage.png',max_h=390),
       p('筛查固定14,187个真实团队，比较245个方法×域（含10基线）。七个主要全域候选共同覆盖12,250队，11,981队可用于两折质量预测，仍只有51张图、6楼。按团队哈希切折，在训练折拟合池×人数基线；这项结果检验同图的新成员团队预测，不能写成新图片的采集前成功。[E1]'),
       p('全域线性构成模型使B8L2均方误差降低约4.47%-10.66%。这些是<b>类别整体效用</b>。在相同灵活度的全域Q＋来源控制之上，七候选的额外质量增益约-0.58%至+0.87%，说明大部分全域效用可由已有质量信号解释；这不否定Q本身用于分类。'),
       p('困难角色更有结构增量：在相同876队、6图、3楼上，参考节点/邻接诊断的预测误差分别降低23.22%/24.47%；再控制全域Q、困难Q与来源后，仍保留约6.88%/7.23%。质量增量只有1.33%。这是局部条件证据；原始邻接诊断不是必要结构的人工真值。'),
       note('图中效用为1-MSE(模型)/MSE(相应基线)，蓝点与控制后的方点分母不同，不能相减。难度包括既有参考几何与人工复核。模型的原scene字段是scope/OOS条件，不是功能房型；功能房型另见第23页。')
    ])

    rows=[['验证构成：B - A','两端可评分 / 实际队','ΔQ / ΔD10','低尾Δ / 墙 / 角']]
    for label,r in selections:
        rows.append([f'{label}，n={int(r.k)}',
           f'A {int(r.scored_teams_a)}/{int(r.unique_teams_a)}；B {int(r.scored_teams_b)}/{int(r.unique_teams_b)}',
           f'{fmt(r.building_B8L2_change_mean,2,True)} / {fmt(r.D10_mean_change_building_equal,2,True)}',
           f'{fmt(r.B8L2_p10_change_building_equal,2,True)} / {fmt(r.diag_wall_coverage_05_mean_change_building_equal,3,True)} / {fmt(r.diag_corner_recall_05_mean_change_building_equal,3,True)}'])
    page('冻结验证：质量方向、低尾与结构并看',[
       table(rows,[.31,.25,.20,.24],9),
       note('低尾Δ是“每图B构成的团队Q第10百分位 - A构成第10百分位”再楼等权；不是配对事件差值的p10。墙为0.05尺度墙覆盖，角为转角召回。A/B与图/楼支持见第1页；其他缺失的诊断支持单独列在核心表。[E2]'),
       h('质量类别：平均改善与尾部改善都重现'),
       p('Q三分位高减低在发现新成员复查中，n5为+12.82、n9为+11.71；验证减至+9.87、+7.98，仍覆盖6楼。n5验证37/43图正向、5/6楼正向；n9为30/35图正向。不同构成所用的全部团队评分失败比例单独保留，不以“只看成功者”冒充总效用。'),
       h('反向角色：差异清楚，但不独立于历史Q'),
       p('G2相对G1在n5/n9/n13验证分别+6.79/+6.40/+7.59；n9六楼均值全正。R5相对R2的5人纯构成+10.11，26/28图正向、六楼均值全正。但R5只由六个历史高Q新批成员组成，必须结合具体人员敏感性与容量阅读。'),
       p('困难角色在n5把H2由2人变3人，六张可比图全部改善，平均节点+1.24、墙覆盖+0.114、角点召回+0.118。n7把H2由2变5人仍有2/5图变差；n9把3变6人有1/5图略降。因此条件角色提供配比线索，而非“超过某比例就每图成功”的定律。'),
       h('重要反例已纳入分母'),
       p('X7HyMhZNoso-19中，Q三分位纯高减纯低在n5为-8.65、n9为-16.84。某些高Q人员在此图的局部标法、范围或结构错误会在构成中集中。它与第22页高Q类别块反例共同说明：历史Q是概率性的选人信号，不能替代本次结构检查。')
    ])

    page('配比曲线：固定可比图片看整体趋势',[
       fig('analysis/figures_summary/composition_ratio_curves.png',max_h=405),
       p('图中Q三分位低/高两端线与G1/G2线按每一个可行整数人数实算。每条线只使用能覆盖整条声明比例线的共同图片，避免比例变化时偷偷更换图片难度；Q三分位发现n5/n9为50/47图，验证为43/35图，G线对应50/50与43/42图。[E2]'),
       p('实线是构成的平均Q，虚线是每图团队低10%分位再聚合。更高的历史质量比例总体向好，但路径不是每个整数点都单调；人数增加还会改变节点保留门槛和同类实际换人容量。整张图的较好纯类是观察后的比较基准，不是可在采集前直接知道的策略。'),
       p('另已生成45,150条同图比例/人数相邻步进，按精确方法、线、n及整数向量分别汇总；没有把不同方向折叠成一个“混类优于纯类”数值。大逐图步进表保留代码可重建；精简包保存曲线汇总、可行性、主规则逐图对照与本图精确绘图数据。'),
       note('这张图固定了本方法的共同支持；其他表可以使用较大的各对比共同支持，所以表和曲线的平均值并非在所有点上应相同。每个构成中只有一个实际团队时，其质量可展示，类内换人方差仍为未知。')
    ])

    page('构成内部换人：稳定性必须带着实际m',[
       table([
         ['验证构成','实际队 / 图 / 楼','有换人图 / 单队图','|ΔQ| / p90','联合稳率 严 / 主 / 宽','平均m'],
         ['Q高纯类，n9','354 / 39 / 6','35 / 4','2.01 / 4.08','54.8 / 71.2 / 82.7%','1.638'],
         ['Q低纯类，n9','343 / 37 / 6','34 / 3','4.26 / 8.64','26.7 / 48.0 / 68.3%','1.636'],
         ['3Q低+6Q高，n9','434 / 44 / 6','44 / 0','4.45 / 9.16','22.5 / 43.9 / 61.6%','4.609'],
         ['R5纯类，n5','88 / 28 / 6','12 / 16','1.27 / 2.53','79.6 / 88.2 / 89.8%','1.000']
       ],[.20,.20,.17,.15,.20,.08],8.8),
       note('以上按每图内实际团队对统计，再建筑等权；p90先在每图内取分位再聚合。各构成的可用图片不完全相同，共同图片与逐m结果另存。没有把354队理解为354个独立验证样本。[E3]'),
       h('主联合稳定的操作定义'),
       p('两队都可评分，同时满足：|ΔB8L2|≤2、地面多边形1-IoU≤0.05、环序允许循环对齐后的绑定角差≤3°、节点数相同。严格阈值为1/0.02/2°，宽阈值为5/0.10/5°。该定义测结果接近，不要求结果正确；没有可比环序或有效几何时，不伪造零距离。'),
       h('有限人数对“可互换”的硬约束'),
       p('若某图某类可用人数为a，构成要c人，该类两队最多能换min(c,a-c)人；多个类别相加。R5全局仅6人，5人纯队最多换1人，许多图实际只有唯一五人集合。其主稳定率较高不能直接与一次换3-4人的大类排名，也不能据此推荐任意五位“同类新人”。'),
       h('稳定但错、分数接近而形状不同都真实存在'),
       p('验证R1纯9人构成中，UwV83HsGsw3-12与pa4otMbVnkk-05各有10个可评分团队，平均Q60.39、主稳定率90.0%、平均m1.6，是有多队支持的“稳定且低质量”。第20页同一纯类的三队则同时展示近分近形与近分异形。[E3、V1]'),
       p('G2并非在所有定义上更可互换：验证n9其主稳定率46.2%，略高于G1的40.6%；但类内|ΔQ|为5.62，对照G1为3.58，实际m也分别为4.08与3.12。单一“类内/类间均值”会遮蔽这种差异。'),
       note('131个单团队构成单元的差异、p90与联合稳定率均保留缺失；没有补零。稳定低质量单元的Q阈值70/80与稳定率≥0.8只是展示筛选，属于描述性观察，未伪装成另一个冻结验证假设。')
    ])

    page('同规模类别块：直接隔开构成与换人规模',[
       p('每个事件以原队A为中心，保留同一组公共成员。B换入其他具体成员但保持类别人数向量；C以相同实际换人人数m换入另一类别向量。因此A→B与A→C的总人数、图、参考、核心与m相同，再看C-B的方向。C与B之间实际有多少人不同另列，不能自动等同m。[E4]'),
       fig('analysis/figures_summary/02_specific_replacements_discovery_validation.png',max_h=390),
       p('发现25,744个事件，验证22,340个事件；其中实际m≥2分别20,267与17,312个。验证有17,754个实际来源匹配事件，包含设计强制匹配与抽样中恰好匹配；不是所有事件都来源匹配。换一个类别、换多个类别及不同方向分别保留。'),
       p('固定13条说明方向在发现与验证中共保留1,064个事件，全部3臂成员均核对原请求。图中有明确正向，也有反向、弱复现与低尾。验证的正向说明规则，其事件差值p10均为负；类别构成提升的是平均机会，仍会产生明显变差的团队。'),
       p('具体比较：Q阈低→高的n5/m2验证，同类换人|ΔQ|为5.26、改类为8.26；困难H1→H2同n/m则为8.99与22.30。后者的同类/改类底面差为0.157/0.208，C-B质量却平均改善14.13。更不稳定的变化可能是向参考明显改善，不能把“变化大”直接等同坏。'),
       note('13条方向是在发现结果中挑出的解释层，随后按相同规则复查；其余49,219行精确层/难度/来源/Q控制摘要与失败未删除，保存于compact_block_evidence/。误差线或建筑点用于展示异质性，不把大量事件当作同等独立图片，也不以p值作为取舍唯一依据。')
    ])


def make_later_pages():
    blocks=pd.read_csv(A/'composition/block_fixed_highlights_compact.csv')
    pick=[1,2,3,5,6,7,8,10,11,13]
    rows=[['固定方向，n / m','发现ΔQ','验证ΔQ','验证事件 / 图 / 楼','验证差值p10']]
    aliases={1:'Q阈低→高，5 / 2',2:'Q阈中→高，9 / 4',3:'Q阈高→低，5 / 2',
             5:'Q×细节多类，5 / 2',6:'G1→G2，5 / 2',7:'R2→R5，5 / 2',
             8:'R1→R5，9 / 4',10:'H1→H2，5 / 2',11:'H1→H2，9 / 4',13:'H2减员混入H1，13 / 2'}
    for no in pick:
        r=blocks[blocks.highlight_no==no].iloc[0]
        rows.append([aliases[no],fmt(r.discovery_net_B8L2_change_equal_building_mean,2,True),
          fmt(r.validation_net_B8L2_change_equal_building_mean,2,True),
          f'{int(r.validation_net_B8L2_change_n)} / {int(r.validation_net_B8L2_change_finite_images)} / {int(r.validation_net_B8L2_change_finite_buildings)}',
          fmt(r.validation_net_B8L2_change_event_p10,2,True)])
    page('来源、Q与具体人员：分别起了什么作用',[
       table(rows,[.35,.13,.13,.23,.16],8.8),
       note('所有ΔQ均为共同核心下C-B的楼等权值；有限事件分母不含没有配对评分的事件，缺失数另表保留。这里的p10为事件差值低尾，和第7页构成内质量p10不同。[E4]'),
       p('<b>来源：</b>Q与R/H角色的若干方向在来源匹配后仍同向，例如Q阈低→高n5/m2仍为+4.31。但G1→G2的n5/m2验证由+1.53变为来源匹配下-0.08（72事件、45图、6楼）。G类整体质量有效，不能据此说它具有来源以外的普遍组合增益。'),
       p('<b>进一步限制历史Q：</b>保留整体效用后，再比较入队块平均历史Q相差≤3的来源匹配子集。G方向在发现只剩5事件/5图/3楼，为+5.97；验证只剩5事件/5图/4楼，为-4.76。许多高低Q比较完全没有这种重叠机会。应报告条件性与覆盖收缩，不能先把Q信号匹配掉再宣布分类无用。'),
       p('<b>具体人员：</b>删除所有含某人的事件后，Q低→高、Q高→低及困难n5/m2方向在仍有至少3楼的删除中保留符号；但R1→R5的n9/m4由+8.43，在删除W129相关事件后变-0.46，只剩7事件、6图、4楼。R5→R2的n5/m2删除W126相关事件后也反向。这同时改变背景与图片覆盖，说明个体与机会敏感性，不能当成已验证的新人员泛化。'),
       note('类别人数是具体人员指示变量的线性组合，不能声称在饱和人员固定效应之上另识别出类别因果效应。本轮提供受控实际融合、来源/Q分层与删人敏感性，未进行真实随机招募或未知人员验证。全部1,157个删人层概要与支持台账保留。')
    ])

    page('人数临界：固定细节成员，逐个加入背景成员',[
       fig('analysis/figures_summary/vote_threshold_interaction.png',max_h=360),
       table([
         ['固定H2人数m','人数2m→2m+1','发现ΔQ','验证ΔQ','验证图 / 楼','验证角点Δ'],
         ['3','6→7','-9.37','-7.10','6 / 5','-0.060'],
         ['4','8→9','-4.39','-6.51','5 / 4','-0.082'],
         ['5','10→11','-3.97','-3.95','5 / 4','-0.068'],
         ['6','12→13','-6.00','-2.72','5 / 4','-0.070']
       ],[.19,.22,.14,.14,.17,.14],8.7),
       p('这些链保留同一批m位H2成员，逐个加入H1，成员集合严格嵌套。冻结规则的保留门槛由m票变为m+1票时，困难角色条件下出现可重复质量下降。前一步/后一步通常更小；全域R5对应临界效应很弱，并非所有类别、所有图片都有同一断点。[E5]'),
       p('本轮发现710条链、验证518条链；m=7没有实际可用链，明确留空。人数与比例在这项设计中同时改变，不能把所有下降都归给票数；第14页另用相同旧身份组、相同节点中心及相同票数的个案直接核对门槛机制。'),
       note('图中两种方法共用纵轴，实心线为临界步进，虚线为前一步进，点为建筑均值。失败变为可评分或相反另列，不补零；图与表是条件均值，不是保证每次加1人都更差。')
    ])


def case_page(case_id, title, lead, commentary, selection_note, appendix_members=True):
    case=json.loads((A/'representative_cases/cases'/f'{case_id}.json').read_text())
    items=[p(lead),fig(f'analysis/representative_cases/figures/{case_id}/comparison.png',max_h=408),p(commentary)]
    if appendix_members:
        rows=[['图中臂','精确人员（完整对象ID、类别和几何见同名JSON）']]
        for i,t in enumerate(case['teams']):
            rows.append([f'{chr(65+i)}：n={t["k"]}，Q={t["B8L2"]:.2f}', '、'.join(t['member_workers'])])
        items.append(table(rows,[.23,.77],8.2))
    items.append(note(selection_note+' [V1]'))
    page(title,items,'代表案例 | '+case['meta']['image']+' | '+case_id.split('_')[0])


def make_case_pages():
    case_page('C05_matched_block_improvement','同样换2人：遗漏显著减少',
      'UwV83HsGsw3-09，已有困难标签，n5/m2；A、B、C共享W030、W031、W121，来源比例相同。H1换入其他H1的B，与换入两位H2的C相比，改变的是类别构成。',
      'B→C：Q <b>24.57→89.60</b>，3D IoU 36.73→92.54，遗漏0.628→0.027，角点召回0.50→0.75。A/B虽都低分且只差0.34分，节点5→4、底面差0.093，<b>不满足联合稳定</b>。2位H2也可能与背景成员共同给某节点投票；类别比例不是节点票数比例。',
      '从留出事件中选择的清楚改善例，展示差值不是总体均值。配对事件block__a156aafbe51ca0288a193d07。')

    case_page('C03_hard_vote_threshold','加1人后，原4票节点失去资格',
      'UwV83HsGsw3-22。固定四位H2：W102、W112、W122、W126；由8人增加到9人、再到10人。8→9人只新增W103，融合与评分规则完全未变。',
      'Q <b>94.69→51.40→53.78</b>；8→9人节点6→5，墙覆盖0.979→0.594，角点召回1.00→0.50。旧观测的身份分组变化数为0，一个原节点仍是同样4个观测、同样中心、同样4票，但门槛从4升到5，因此失选。下一页显示对应局部。',
      '描述性极端展示，来自冻结后的验证链nested__aaa48d5a2ca0dbd72fd7f606；不是盲选视觉样例。')

    page('局部结构与类别成员标法',[
       fig('analysis/representative_cases/figures/C03_hard_vote_threshold/local_zoom.png',max_h=338),
       p('上图r1/r2是固定参考边索引。粉色表示按独立0.05尺度墙覆盖诊断未被覆盖的参考墙段；它不改变主评分。这里从接近参考的拐角变成斜连线，ERP、BEV与三维结果相互对应。'),
       fig('analysis/representative_cases/figures/C05_matched_block_improvement/member_overlays.png',max_h=240),
       note('下图是C05图池内两个活动类别的全部成员标法叠图，一条细线代表一人；不是只选当次获胜者叠图。类别来自历史，图上的集中、遗漏与分歧仅作作答后机制解释，不作为采集前成功特征。各案例均另附完整member_overlays.png。[V1]')
    ],'代表案例 | C03局部与C05成员叠图')

    case_page('C04_score_up_structure_down','Q上升，不代表所有必要结构更完整',
      'X7HyMhZNoso-07。固定六位R5，加入R2背景：纯R5为6人，随后比较12人和13人。12→13人新增W125，三个旧6票组因门槛6→7而失选，旧观测分组不变。',
      'Q从<b>44.91升到64.63</b>，但节点7→4、参考转角召回0.20→0.10；墙覆盖却从0.395升到0.526。必须写成<b>部分结构诊断下降、另一些改善</b>。纯R5本身Q也仅47.37，不能称为正确参考的替身。请结合原图核对锯齿墙段的目标范围。',
      '展示Q上升而部分结构损失的反例，链nested__daa71ba6d32a2f9a294487b1；不是据此更换参考或评分。')

    page('应人工复核的局部：范围与真实转角',[
       fig('analysis/representative_cases/figures/C04_score_up_structure_down/local_zoom.png',max_h=385),
       h('为什么这不是“总分修正后的赢家”'),
       p('三维底面更像一个简化四边形，并不自动等同目标房间的正确轮廓。参考包含的凹凸边段应由既有任务范围和人工参考来解释；本研究保持这些输入不动。这里需要人工确认的是哪些凹角属于当前应标范围、是否可从照片辨认，以及原参考是否有已知资格问题。'),
       p('新增的墙覆盖与真实角点诊断只是补充主评分：墙覆盖允许共线分段，避免“拆得多”机械扣分；转角只计大于10°的真实转向。原始节点/邻接对应容易受多加共线点、阈值匹配或环序影响，因此不把邻接对应率直接叫作必要结构正确率。[A1]'),
       p('同类人员可能共享范围假设，也可能只是共享局部几何习惯。现有数据不能把这两种机制全部分开。scope裁定正确率的历史支持又很薄，所以本轮没有制造“范围专家”标签。对C04这样的案例，人工检查比继续增加随机团队数量更有价值。'),
       note('ERP局部跨经度接缝，显示按原点坐标周期展开；BEV和3D用共享坐标/相机高度=1，顶部从配对射线推得，不是额外米制三维GT。所有几何未经曼哈顿拟合美化。[V1、A1]')
    ],'代表案例 | C04必要结构局部放大')


def make_mixture_pages():
    page('混类互补：与两端中较好者直接比较',[
       table([
         ['冻结混类规则','发现或新成员线索','验证对每图较好纯类','有效图 / 楼'],
         ['R5×4 + R2×1，n5','明显胜过R2，接近R5','-1.45；8正 / 20负','28 / 6'],
         ['G1×3 + G2×10，困难n13','初筛部分图正；yqst-25新成员仍+11.51','-6.10；3图全负','3 / 3'],
         ['同上，每端≥3可评分队','更严格的真实重复支持','-7.97；2图全负','2 / 2'],
         ['R1×3 + R2×6，n9','yqst-27初筛比纯端好','-3.12；3正 / 28负','31 / 6'],
         ['R1×4 + R2×5，n9','另一邻近比例一并冻结','-3.74；3正 / 28负','31 / 6'],
         ['旧Semi倾向类3+2，n5','胜过某一纯端','-1.97；2正 / 3负','5 / 4'],
         ['门洞Q类6低+3高，n9','胜过低端但低端多失败','-6.64；2图全负','2 / 2']
       ],[.30,.30,.25,.15],9),
       note('每图较好纯类要求两端真实存在且质量可评分，再同图配对。它是观察后的比较基准，不是采集前可知的最优策略。支持不足或失败单列；H7完整共同支持与每端至少3队并列，不择优换口径。[E2]'),
       fig('analysis/figures_summary/mixture_member_replication.png',max_h=215),
       p('yqst-27初筛3R1+6R2四队均值94.64，比较好纯类高13.37；新成员每构成十队，纯R2均值84.57，两种混合81.86/83.46，分别低2.71/1.11。原来“好看”的形状值得解释，但其混类优势未在新团队中保住。全部点保留，不只显示低尾或赢家。'),
       note('H7发现也有反例：yqst-09的增益+3.72变-7.41，7y3-21的+0.04变-8.34。H4困难子层在验证看似混类改善，但发现困难子层为负，属于事后局部线索，未升级为已复现规则。')
    ])

    case_page('C01_member_sensitive_mixture','同一3+6构成，可以差三十多分',
      'yqstnuAEVhm-27，R角色五类的3R1+6R2，n9。左为初筛下中位团队，中为新成员复查的低尾团队，右为复查纯R2下中位团队。',
      '两支混类构成完全相同，实际换6人，Q <b>95.82→63.99</b>，节点同为8，但底面1-IoU为0.131、绑定角差6.95°，对应局部边界与角点偏移。右侧纯R2可达到88.26。展示团队说明成员风险；本图总体结论由上一页所有4/10队计算。',
      '初筛中位与复查低尾是明确的事后展示规则，差31.83分不是该构成的平均复现差。局部放大另见同名目录local_zoom.png。')

    case_page('C02_stable_wrong_same_score_shape','同一纯类：稳而错，也会近分异形',
      '同一yqst-27的9人纯R1构成。A→B同类换2人，A→C同类换3人；三队Q都约48.5，不能只凭分数差判断结构。',
      'A/B：|ΔQ|=0.05、底面差0.011、绑定角差1.12°，满足主联合稳定，但两者都低质量。A/C：|ΔQ|=0.46，底面差<b>0.270</b>、绑定角差<b>41.58°</b>，明显不同形。C01与本页是同图，不计成两个独立图片证据。',
      '按“稳定低分＋相近分数但异形”选择的机制展示。多图稳定低质量支持另见within固定构成表，不能由这一组案例替代。')

    case_page('C07_local_complement_replicates','局部互补重现：均值有效，成员不稳',
      'yqstnuAEVhm-25，G关系两群，n13。每种构成的新团队各6队、全部可评分；图示每种构成的下中位代表。',
      '所有六队均值：纯G1 <b>37.50</b>、纯G2 <b>51.51</b>、3G1+10G2 <b>63.02</b>，混合比每图较好纯类+11.51（初筛+13.52）。但混类Q范围38.87-78.67、类内|ΔQ|20.26、主稳定率仅6.7%。节点与3D IoU改善，平均角点召回却略降；这是局部平均互补，不是稳定配方。',
      '图中代表队间差值不能代替所有六队均值。新团队仍是同一张图，H7在验证建筑对较好纯类为负。')

    case_page('C06_highQ_replacement_counterexample','高历史Q类别，也会让本次融合变差',
      'q9vSo1VnCiC-03，Q阈值三类，n5/m2。所有成员均为新批，公共成员W102、W103、W105完全相同；把两位低类换成高类。',
      'B→C：Q <b>94.31→70.89</b>，3D IoU 95.61→86.89，角点召回1.00→0.75，墙覆盖0.983→0.847；节点仍为4，主要变化是边界偏斜。A/B分数只差0.21，但底面差0.072，也没有满足主联合稳定。来源相同无法消除本次具体标法误差。',
      '配对事件block__29ff28657072581ba4a60480。它是验证中的负尾展示，不推翻整体Q方向，也不被整体均值掩盖。')


def make_end_pages():
    page('任务与房型：条件规律不能混成总体结论',[
       table([
         ['条件','冻结结果与真实支持','应如何解释'],
         ['新Semi最终Q两类','n5高-低：发现+7.33（7图/3楼），验证+0.53（5图/4楼；3正1负1平）；两端各20/20队可评分。','效应减弱。这里只是最终质量分类；没有逐份初始几何的部分不报告净纠错收益。'],
         ['旧Semi编辑倾向两类','3+2混类对纯C01 +5.39，对纯C02 -1.39；较好纯端 -1.97（5图/4楼）。B6-22对纯C02 -18.90。','修改倾向不等于确认纠正能力。混类可超弱端，未普遍超强端。'],
         ['门洞本层Q三类','n9的6低+3高对纯高 -6.64（2图/2楼）；纯高8/8、混类6/8可评分。对纯低 +8.80，但纯低仅3/12队可评分。','先看失败分母。生存者质量差不能当整体选人价值；支持只有少量楼。'],
         ['特殊条件','3池、2图、2楼，描述性183队；无历史条件类别可训练。','保留直接结果，不能借普通层标签宣称特殊任务验证成功。']
       ],[.17,.48,.35],9.1),
       h('功能房型：补充探索，不另称冻结验证'),
       p('原pool.meta.scene是OOS/doorway标记。真正房型来自image_evidence中的room_spatial_classification；保留10种粗类、缺失与“无法判断”，没有把缺失当普通房间。房型的作者/时间没有嵌入字段，来源细节保留为缺口。[E6]'),
       table([
         ['Q三分位高-低，n5验证','卧室','卫浴','起居/休闲','通行/连接'],
         ['楼等权ΔQ','+13.91','+3.31','+17.24','+7.27'],
         ['图 / 楼；正 / 负','6/4；6/0','12/5；9/3','5/3；5/0','11/5；9/2']
       ],[.36,.16,.16,.16,.16],9.1),
       p('这是冻结类别后新增的房型分层，不能把看到的房型差异再称为预注册验证。卫浴类的质量优势较小且有反例，提示难度、范围和几何习惯可能共同作用；房型、建筑、人数可行性相互混杂。全房型和同难度分层表均保留，薄支持的一楼工作/学习类不主推。'),
       note('困难标签也包含参考节点/转角/高度与先前人工复核。条件研究回答“在这样的已知任务条件中如何变化”；全域历史Q规则才不需要读取目标图的困难评价。')
    ])

    page('可用于选人或预测的规则，以及适用范围',[
       table([
         ['使用时点','可执行规则','证据强度与限制'],
         ['采集前：已有历史的人员','以历史任务校正后的Q分层作为主选人信号；在普通Manual的n5/n9中，提高高类比例。保留低尾、历史覆盖及来源。','跨6座留出楼、35-43图支持平均收益；不是每队更好。没有未知人员、不同采集流程或外部图片验证。'],
         ['采集前：明确困难任务条件','已有同口径范围/参考难度判定时，可优先保证历史细节角色的数量与比例，并考虑成员容量。','H2增至3/5或6/9有结构收益，但仅5-6图、4-5楼；类别含7人。不能自动识别新图困难，也不能外推普遍专家类别。'],
         ['预算/人数调整','不要只按总人数排队。声明比例和实际人选，比较同n下构成；增员时关注固定细节群是否被稀释到保留门槛以下。','人数与比例交互在困难链上重复；全域效应较弱。没有得到通用最佳总人数或最佳混类比例。'],
         ['作答后：融合诊断','并看节点票数、范围遗漏/扩张、转角/墙覆盖、3D几何；遇临界丢点或近分异形，优先人工看关键局部。','这些都是观察到作答后的信息，只用于解释和复核，不能混入采集前预测准确率。'],
         ['不宜直接使用','把R5、G2或Semi修改倾向当成万能专家；把单图最佳混类固化为全图配方；把稳定性当正确性。','原始正例、留出反例和具体成员敏感性已经直接否定这些过强规则。']
       ],[.20,.41,.39],9.2),
       h('最值得人工确认的少量案例'),
       p('<b>优先C03：</b>确认新增成员没有支持原凹角后，门槛丢点造成的斜连线与遗漏。<br/><b>优先C04：</b>确认参考锯齿墙段与目标范围，理解Q上升而转角损失。<br/><b>优先C07：</b>比较两端漏掉的局部是否互补，以及为何同一构成有高低两群结果。<br/><b>再看C06与C02：</b>分别确认高历史Q的局部偏斜反例、相同分数的不同轮廓。'),
       p('七个案例共6图、4楼、21个不同实际团队、52位实际入队人员。所有类别成员叠图、同图ERP/BEV/3D和必要局部均在包中，不需要逐个人工判断大量作答对。人工复核将检验机制与参考适用性；本轮没有自行更改任何主参考、评分或融合规则。[V1]')
    ])

    page('评价口径、失败与解释边界',[
       h('沿用冻结主评价，新增诊断明确另列'),
       p('主比较使用consensus_delivery_20261008.fuse，gap=7.5，自动融合，无人工分区或手动环序替换，B8L2为当前主评价。<b>D10实际实现是方向尺度参数从8°到10°的敏感性</b>，不是修改节点匹配或融合。N1尚未接入。本轮没有通过更换参考、评分或融合制造分类效果。[D1、A1]'),
       table([
         ['观察对象','保留的指标','解释边界'],
         ['质量与范围','B8L2、D10、IoU2D/3D、遗漏/扩张、质量低尾和失败','稳定错误、质量提升、范围改变可分开；同Q不保证同轮廓。'],
         ['两队形状接近','底面1-IoU、循环绑定角差、节点差、高度/柱体IoU、联合稳率','不同节点数可能没有可比绑定角，保留原因；不补0。'],
         ['结构与连接','原始参考节点/邻接对应；新增墙覆盖、真实转角召回','旧邻接受共线拆点影响。新增墙/角指标是固定参考的几何诊断，不是N1或逐结构人工真值。'],
         ['墙/角诊断参数','墙方向容差10°，距离带宽为参考面积平方根的0.03/0.05；角只计>10°转向，0.05尺度内最大基数匹配后最小距离','测试了共线拆分、方向/距离、缺失、退化与匹配反例。结果辅助解释，不改总分。']
       ],[.20,.36,.44],9.2),
       p('跨阶段不同真实团队583,261个，其中577,401个complete_conditional；no_connection 3,432、below_four 2,203、invalid_floor 225，共5,860队无法得到主分。complete_conditional表示冻结算法的计算资格，不表示已人工确认几何完全正确。失败不补零；同时报告成功率与可评分条件下质量。[D1]'),
       p('多数验证只有6楼，条件类更少。建筑等权是主汇总，图片等权、各楼方向、全部反例和支持量一并保存；建筑重抽样区间若使用也只是小样本描述。没有以大量团队构造虚假的高精度，也没有把p值过线当成结果价值的唯一依据。'),
       note('scope多义性在公开布局文献中确有不同协议，例如Bi-Layout的两种目标布局以及ZInD的完整房间/可见部分/合并房间表示；这些仅提供机制背景，不能代替当前任务的固定参考。文献详见第27页。[L1、L2]')
    ])

    page('从主结论追到成员与最终几何',[
       table([
         ['入口','精简包内路径','能重建什么'],
         ['先读本报告','output/personnel_composition_report_zh.pdf','主结论、支持范围、解释、反例与图'],
         ['主效应与逐图证据','analysis/report_tables/；analysis/composition/frozen_grid_results/','6条主效应、8,902条固定逐图对照、建筑等权与较好纯端比较、类内换人和覆盖缺口'],
         ['类别与历史解释','analysis/SELECTED_WORKER_CLASSES.csv；analysis/forward/results/；analysis/reverse/','全部方法固定标签、历史特征、候选及解释；不读目标建筑评价'],
         ['类别块证据','analysis/composition/compact_block_evidence/','13条说明层全部1,064事件；所有精确层摘要；来源/Q/删人敏感性与失败'],
         ['临界人数与房型','analysis/composition/nested_*/；scene_analysis/','固定成员链的实际团队键、步进、结构结果；额外房型分层'],
         ['7个精确案例','analysis/representative_cases/cases/','21臂精确人员/对象ID、固定参考、参数、必要最终几何、参与类别全体冻结记录与节点票'],
         ['图和获取原图','analysis/representative_cases/figures/；analysis/visual_sources/','ERP/BEV/3D、成员叠图、局部；Release中6张原图的精确索引/CRC/哈希和按需提取代码'],
         ['运行与完整性','analysis/REPRODUCE_ZH.md；analysis/reproduce.py；MANIFEST.json；SHA256SUMS','快速案例重放、全部13阶段请求重建、完整实算命令、文件哈希']
       ],[.16,.40,.44],8.9),
       h('复现层级'),
       p('<b>快速：</b>用案例内嵌的冻结记录与固定参考重放21队，不需读取整库融合输入、完整请求或缓存。<b>请求：</b>用固定分类、规格与种子重建全部589,990条请求，逐条成员一致且13个gzip文件SHA逐字一致。<b>完整：</b>按官方恢复器取得冻结运行时，再按13阶段重新融合与汇总；恢复文件成功本身不等于科学实验重跑。'),
       p('最终包不含逐队全流程状态、全部距离矩阵、逐折模型缓存、重复仓库数据、原图全集、虚拟环境或大量日志。589,990条大请求清单也不重复打包，保留生成器、精确规格、种子、完整SHA与成员重建审计。主结论的小表和代表最终几何仍可直接审阅。'),
       note('代表6张原图均已从既有Release取得并核对ZIP条目CRC、大小、尺寸与本地SHA。未把其余数值样本假称为全部人工看图；原图索引中的2张历史图缺图仍保留为缺口，不影响本轮6个展示图的视觉重建。'),
       note('请优先执行REPRODUCE_ZH.md中的quick与requests。包中路径保留analysis相对布局；JSON内原始绝对路径有时只是历史provenance字符串，不作为本地必须存在的路径。没有修改或推送GitHub main。')
    ])

    refs=[
      ('D1','输入与全研究覆盖','composition/INPUT_AUDIT.json；composition/coverage/STUDY_COVERAGE_RECEIPT.json；stage_coverage.csv。仓库交接README/INPUTS/CHECKS按主提交固定，30项来源逐一核对。'),
      ('D2','设计与冻结','composition/SPLIT.json；VALIDATION_FREEZE.json；各SPEC.json。冻结SHA：dfa0d80a6668e55fee58df9efbcaf43a76c062d1941db26c922c3f46f02893fd。'),
      ('F1 / F2','两路分类','forward/results/feature_fit_receipt.json、candidate_ledger.csv、worker_labels.csv.gz；reverse/CANDIDATE_MANIFEST.json、class_explanations.csv、history_stability_summary.csv。'),
      ('E1','固定团队筛查','forward/screen_final/：screen_outcomes.csv.gz、candidate_search_ledger.csv.gz、hard_control_sensitivity.csv与receipt。'),
      ('E2 / E3','构成效用与内部换人','composition/frozen_grid_results/：frozen_rule_compact.csv、逐图/逐楼对照、混合对较好纯端、within_fixed_compositions及可行性。'),
      ('E4 / E5 / E6','类别块、人数、房型','composition/compact_block_evidence/；nested_discovery/、nested_validation/；scene_analysis/；independent/POOL_IMAGE_CONDITIONS及provenance。'),
      ('V1 / A1','精确案例与独立核验','representative_cases/cases/；independent/REPRESENTATIVE_CASE_PARITY.json、PORTABLE_REPLAY_READ_AUDIT.json、REPRODUCTION_AUDIT.json、HISTORICAL_PARITY_SUMMARY.json与几何探针。')]
    page('证据索引与方法背景',[
       table([['引用','主题','路径（均在analysis/下，除另注）']]+[list(r) for r in refs],[.15,.21,.64],8.7),
       h('独立核验完成了哪些关键检查'),
       p('26个历史原生团队包含成功与失败，覆盖24图、14楼、58人，B8L2/D10和几何逐项一致。8,902条逐图主对照独立检查有限值与差值，897个建筑汇总最大误差6.7e-9；H2的504个总难度汇总行独立重算一致。最终7例21臂重放得分差为0，几何与成员逐字一致；禁止读取完整输入/缓存的快速重放也通过。[A1]'),
       h('仅用于范围与布局表示背景的原始文献'),
       p('[L1] Yu-Ju Tsai, Jin-Cheng Jhang, Jingjing Zheng, Wei Wang, Albert Y. C. Chen, Min Sun, Cheng-Hao Kuo, Ming-Hsuan Yang (2024). <b>No More Ambiguity in 360° Room Layout via Bi-Layout Estimation.</b> CVPR, pp.28056-28065. 作者论文：<link href="https://liagm.github.io/Bi_Layout/pdf/3739.pdf" color="#176F86">liagm.github.io/Bi_Layout/pdf/3739.pdf</link>。讨论不同目标布局协议，不用于改变本轮参考。'),
       p('[L2] Steve Cruz, Will Hutchcroft, Yuguang Li, Naji Khosravan, Ivaylo Boyadzhiev, Sing Bing Kang (2021). <b>Zillow Indoor Dataset: Annotated Floor Plans With 360° Panoramas and 3D Room Layouts.</b> CVPR, pp.2133-2143. 官方数据说明：<link href="https://github.com/zillow/zind" color="#176F86">github.com/zillow/zind</link>。房间表示与合并说明仅作范围背景。'),
       note('本报告的人员类别、组合效应、统计分母与案例数字均来自本轮冻结数据实算；文献不为这些数字背书。中文图使用Noto Sans SC，字体及其子集遵循SIL Open Font License。')
    ])


def build_selected_worker_table():
    f=pd.read_csv(A/'forward/results/worker_labels.csv.gz')
    r=pd.read_csv(A/'reverse/worker_labels.csv.gz')
    # The two route exports use slightly different metadata columns.  Match only
    # the explicit method/domain/worker/class fields, never rederive membership.
    methods=[('Q_tertile','F_rule_Q_quantile_K3','all',f),
             ('Q_threshold','F_rule_Q_threshold_K3','all',f),
             ('G_relation','R_geo9_source_signed_p2_K2','all',r),
             ('R_role','R_role_ward_K5','all',r),
             ('H_hard_role','R_role_ward_difficulty_K2','hard',r)]
    workers=pd.read_csv(A/'forward/results/features_train.csv.gz')[['worker_id','person_origin','core_supported','q_beta','q_abs_mean','q_abs_p10','q_residual_sd','hard_supported','theta_hard']]
    for short,mid,dom,data in methods:
        domain_col='domain'
        sub=data[(data.method_id==mid)&(data[domain_col].isin([dom,'global'] if dom=='all' else [dom]))]
        assert sub.worker_id.is_unique,(mid,sub.shape)
        cls='class_id' if 'class_id' in sub else 'label'
        workers=workers.merge(sub[['worker_id',cls]].rename(columns={cls:short}),on='worker_id',how='left',validate='one_to_one')
    workers.to_csv(A/'SELECTED_WORKER_CLASSES.csv',index=False,float_format='%.12g')


def footer(canvas,doc):
    canvas.saveState()
    canvas.setStrokeColor(GRID);canvas.setLineWidth(.6)
    canvas.line(MARGIN,31,W-MARGIN,31)
    canvas.setFont('NSC',7.8);canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN,18,'固定参考的实际融合研究  |  2026-10-19  |  回顾性建筑留出')
    canvas.drawRightString(W-MARGIN,18,f'{doc.page}')
    canvas.restoreState()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--font',type=Path,default=A/'fonts/NotoSansSC-Regular.ttf')
    ap.add_argument('--bold-font',type=Path,default=A/'fonts/NotoSansSC-Bold.ttf')
    ap.add_argument('--out',type=Path,default=OUT/'personnel_composition_report_zh.pdf')
    args=ap.parse_args()
    setup(args.font,args.bold_font)
    make_main_pages();make_later_pages();make_case_pages();make_mixture_pages();make_end_pages()
    build_selected_worker_table()
    table_dir=A/'report_tables';table_dir.mkdir(parents=True,exist_ok=True)
    for name,data in source_tables.items():data.to_csv(table_dir/name,index=False,float_format='%.12g')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    doc=BaseDocTemplate(str(args.out),pagesize=A4,leftMargin=MARGIN,rightMargin=MARGIN,
                        topMargin=42,bottomMargin=46,title='人员类别组合替换与融合结果研究',
                        author='ChatGPT',subject='冻结融合、类别构成、建筑留出与可重放案例')
    frame=Frame(MARGIN,46,CW,CH,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0,id='main')
    doc.addPageTemplates(PageTemplate(id='study',frames=[frame],onPage=footer))
    story=[];budget=[]
    for n,(title,items) in enumerate(pages,1):
        estimated=0
        for x in items:
            _,hh=x.wrap(CW,CH)
            estimated += hh+getattr(x,'spaceBefore',0)+getattr(x,'spaceAfter',0)
        budget.append(dict(page=n,title=title,estimated_height=estimated,available_height=CH))
        if estimated>CH-3: print('LAYOUT WARNING',n,round(estimated,1),round(CH,1),title)
        if n>1:story.append(PageBreak())
        story.extend(items)
    doc.build(story)
    receipt=dict(report=str(args.out.relative_to(ROOT)) if args.out.is_relative_to(ROOT) else str(args.out),
      bytes=args.out.stat().st_size,sha256=hashlib.sha256(args.out.read_bytes()).hexdigest(),
      designed_pages=len(pages),pages=budget,source_tables=list(source_tables),
      note='Visual PDF inspection is performed separately; estimated heights are a layout aid, not a correctness gate.')
    (OUT/'REPORT_BUILD_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ['report','bytes','sha256','designed_pages']},ensure_ascii=False))


if __name__=='__main__':main()
