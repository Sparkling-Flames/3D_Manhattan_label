"""Chinese synthesis with auditable source tables, plus a readable image index."""
from pathlib import Path
import json,html,base64,math,hashlib
import pandas as pd,numpy as np
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,KeepTogether
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage09_report';OUT.mkdir(exist_ok=True)
COMMIT='e1873bfadc1d0e61499809c91fba9dc39c717f83'
blocks=[]
def h(t):blocks.append({'type':'heading','text':t})
def p(t):blocks.append({'type':'paragraph','text':t})
def tab(headers,rows):blocks.append({'type':'table','headers':headers,'rows':rows})
def fig(path,caption):blocks.append({'type':'figure','path':path,'caption':caption})

def content():
 h('结论：平均Q先小变，低尾与成员波动仍继续改善')
 p('本轮已经完成普通 Manual 206 张图的逐图人数响应研究，并把最新584份筛前、439份筛后的17张门洞图单列。核心结果不是一个统一的“够用人数”：简单图的平均质量通常较早变化变小；困难图更常保留后段波动、升降抵消和结构切换。同一张图可以同时出现均值小变、低尾提高、成员波动下降，或者稳定地保留与当前参考不一致的表达。')
 p('按“每增加一人引起的路径内绝对Q变化”衡量，在容量至少30人的171张共同图片中，167张在3→6人阶段的平均变化最大，3张在6→10人最大，1张在20→30人最大。这里比较的是每次加人的变化强度，不是说全部累计变化都集中在最早阶段。后段仍有值得解释的局部跃变：k≥20的191张可比较图中，42张存在至少一个相邻步骤，其双端可评路径中至少10%发生超过5分的变化。[R12、R2]')
 tab(['观察对象','全尾小变主条件','有合格起点的图','检测子集起点中位数'],[
 ['平均B8L2','后续全部人数范围≤2分','163/206','11人'],['B8L2低尾P10','后续全部人数范围≤2分','127/206','19人'],['同人数换成员的Q标准差','后续全部人数范围≤1分','87/206','19人'],['完整可评输出率','后续全部人数范围≤5个百分点','196/206','3人']])
 p('以上人数均为回顾性描述：从该人数直到本池实际满员N，所有后续整数人数都要满足条件，且至少再观察max(5, ceil(0.15N))名人员。它不把短暂平稳、末端只剩一两个人或满员的一支确定团队自动认作平台。40张普通图只有在剩余观察太短时才满足均值2分条件；2张池太小，1张满员不可完整评分，因此没有给出主起点。[R1]')
 h('一、到底哪些图较早小变，哪些总体平台来自抵消')
 tab(['冻结人工等级','全部图片','平均Q有起点','起点中位数','未识别起点'],[['简单',130,'123/130',9,7],['中等',39,'25/39',16,14],['困难',37,'15/37',17,22]])
 p('“简单较早小变”得到明显支持。中等、困难的起点中位数只描述成功识别的子集；困难图15/37能给起点，不能把其余22张删掉后宣布所有困难图到17人便稳定。全部206张中，到10人已有80张达到均值小变条件，到15人为123张，到20人为141张。[R1、R3]')
 fig('stage08_figures/01_Onset_by_Difficulty.png','图1：各曲线的分母是该等级全部图片，包括没有合格起点的图片。右下图是“后续不同团队的底面分歧水平低”，与质量全尾范围小是不同定义，不能按中位数直接排列哪一种稳定更早。')
 p('总体平均曲线必须拆开看。在同一批N≥30的171图、22楼中，20→30人的平均Q增加0.500分，139图上升、32图下降，134/171图在±2分以内；楼等权均值增加0.692分。这个整体结果主要由多数小变图片构成，同时包含少数较大改善和恶化。冻结难度分层后，平台性质明显不同：')
 tab(['20→30，同一容量面板','图/楼','平均ΔQ','平均|逐图ΔQ|','升/降图','±2分内'],[['简单','116/22','+0.446','0.722','101/15','107/116'],['中等','28/14','+1.375','2.187','22/6','20/28'],['困难','27/14','−0.174','4.772','16/11','7/27'],['全部','171/22','+0.500','1.601','139/32','134/171']])
 p('困难图的均值接近零，主要包含相当大的正负变化抵消：16张改善、11张恶化，逐图绝对变化平均4.772分。10→20人也相似，困难27图平均−0.076分，但平均绝对变化4.895分，14升、13降，只有5/27图在±2分内。简单图则多数确实变化很小。这两种“平台”不能写成同一个结论。[R3]')
 p('这个差别并不只是人员池大小不同。严格固定N=35时，简单75图的20→30人平均绝对变化0.674分，69/75在±2分内；困难只剩8图，但平均绝对变化仍4.233分，仅2/8在±2分内。困难支持较小，结果作为容量控制后的条件证据保留。')
 p('结构条件也有解释力：有短结构的46图中，仅17图有平均Q小变起点，中位18人；无短结构160图中有146图，中位10人。在N≥30共同面板中，有短结构37图的20→30人平均绝对Q变化3.824分，仅16/37在±2分内；无短结构134图为0.987分，118/134在±2分内。短结构、难度和空间形状有关，本轮没有把它们改写为独立因果分类。[R3]')
 h('二、平均质量小变后，增加人员还改变什么')
 tab(['固定共同范围','指标','平均变化','多数图片方向'],[['171图，20→30','平均B8L2','+0.500','139/171提高'],['171图，20→30','P10 B8L2','+2.848','166/171提高'],['171图，20→30','Q标准差','−2.031','168/171下降'],['171图，20→30','团队底面平均1−IoU','−0.02054','170/171下降'],['98图均N=35，20→30','P10 B8L2','+2.396','95/98提高'],['98图均N=35，20→30','Q标准差','−1.454','96/98下降']])
 p('因此，20人以后仍可能有明确价值：在已有池内减少低质量团队和成员组合造成的波动，即使平均Q只提高很少。在163张达到平均Q起点的图上，该人数处154张的P10后续范围仍超过2分，全部163张的SD后续范围仍超过1分；8张的完整可评率仍变化超过5个百分点。[R3、R4]')
 p('30→35人的共同容量面板有98图，其中97图两端Q可评，另1图在满员时失败。97图平均Q增加0.281分，平均绝对变化0.759分，87/97在±2分内；P10增加2.736分，SD下降1.952分，均为97/97图同向。但35人就是这些池的满员，只有一支团队，SD归零包含有限组合收缩。前表N固定35、20→30的结果尚未到满员，也保留尾部和波动的多数改善；不能把全部收益归结为最后一个点的机械归零。[R3]')
 fig('stage08_figures/02_Fixed171_Count_Response.png','图2：同一批171图，分别展示均值、低尾、换组波动和几何分歧。冻结困难组的平均曲线低且有起伏，低尾不等同于平均值。')
 fig('stage08_figures/03_Image_Changes_20_to_30.png','图3：逐图变化的分布。均值变化小、低尾提高和SD下降是不同结果；各自保留正向与反向图片。')
 p('几何方面，普通206图已有精确的路径频率U统计，本轮直接复用177个未变池与29个新/变更池。若把“平均两支团队底面IoU至少0.90，且全部后续人数都满足”作为低分歧描述，196/206图能在足够长的观察段内达到；按质心平均距离≤0.05个相机高度，172/206图达到。它们测量当前池内不同团队的接近程度，不检验与参考是否一致，也不凭相同节点数声称是同一种表达。[R4]')
 h('三、暂时平稳、后段跃变与有限人员池')
 p('用连续4个人数点的均值范围≤2分寻找局部平段，会在173张图中遇到“局部很小、随后全尾范围仍超限”的情况；其中39张在k≥20以后仍出现这种局部平段。这里包括缓慢累积越界，并不全是单步跳变。另行按实际进入路径检查，k≥20的191图中42图、k≥30的159图中22图，至少有一个相邻加人步骤让≥10%的双端可评路径发生|ΔQ|>5。全尾判据与逐路径跳变表分别回答两个问题。[R2]')
 p('所有表都保存k、池容量N、k/N、路径数和不同团队数。主统计始终保留256条路径频数，同一团队被多个路径选中时不会被去重后错误等权。精确有限组合仅在明确穷尽时另列：普通206池中203池的N−1人数已覆盖全部N种缺一人团队；主256路径条件均值与这份有限精确均值的平均绝对偏差为0.0697分，最大2.1657分出现在VFua-04。它是本次抽样实现与有限真值的差，不是MCSE，也不是所有人数的误差上界。[R5]')
 p('低尾仍有局部敏感反例。wc2-46在N=28、k=27时，路径线性P10为74.958，完整28队等权线性P10为52.406，精确逆CDF为51.951。实际有4/28支低Q团队，路径访问这些队26/256次，线性10%分位恰跨越约52.60到97.31的双峰间隙。203个完整有限对照中，只有2图的线性P10差超过2分，但这类少数图必须保留，不能用均值估计的平均小误差代替尾分位精度。[R5]')
 p('对此已用保存的逆CDF分位列完成全206图敏感性。206/206图的“有无合格起点”判定一致，仍为127图有起点；201/206图的起点值或同为无判定也一致，仅5图的起点后移1—2人，中位数由19变20。固定171图20→30的平均P10变化由+2.848变+2.872，仍166升、5降，所有图片方向一致。wc2-46的路径逆CDF为52.601，该图两种定义都没有合格起点，满员98.032仍体现真实后段变化。原主口径继续保留线性分位，逆CDF独立报告，未借用不匹配的bootstrap带。[R13]')
 p('三种不确定性保持分开：同人数不同成员的SD和几何U描述真实换组波动；已有2000次整条路径bootstrap同时带描述256路径对当前有限池统计量的估计精度；不同图和不同楼的差异由逐图分布、楼支持与楼等权汇总描述。路径数不是独立图片数，当前池的结果也不被写成新人员或新房间预测。')
 h('四、门洞：筛除、空间一致性与后段人数效应')
 p('本轮固定当前439采用记录，不回退到553或533版本。17图筛前共584份、筛后439份，排除145份；筛后最终空间登记为空间1 66份、空间2 43份、全部323份、未定7份。未定记录保留在整图筛后池，但不会猜分到某个兼容池。人工裁决、历史人员排除及OOS边界均按当前冻结资料继承。筛查清单并非随机抽样，145/584不能外推为总体乱标率。[R6]')
 tab(['当前池','总人员支持','非空图','可做k≥3的图','N≥8的图','逐图容量'],[['整图筛前',584,17,17,17,'32—35'],['整图筛后',439,17,17,17,'14—34'],['空间1兼容',66,12,11,3,'0—12'],['空间2兼容',43,9,6,2,'0—13'],['全部兼容',323,17,17,17,'8—34']])
 p('筛前、筛后17图的共同人数上限是14。到20人只剩13张共同图、8楼，到30人5图、3楼，到35人没有共同图。空间1与空间2在同图各有3人容量的只有4图；各有4人只剩1图，各有5人没有支持。单侧池未识别出符合本轮全尾与后续长度要求的平均Q起点，不能据此概括单侧空间天生不稳定；大部分池的容量本来就不足以检验这一问题。[R6]')
 tab(['同17图、k=14，筛后−筛前','平均变化','方向支持'],[['平均B8L2','+3.262','8升、6降、3同'],['P10 B8L2','+5.363','10升、4降、3同'],['Q标准差','−2.337','12降、2升、3同'],['完整可评输出率','+6.25个百分点','9升、4降、4同'],['底面团队分歧1−IoU','−0.09651','12降、2升、3同']])
 p('筛除的作用不是每图平均Q都升高。其对低尾、成员波动和底面几何一致性的改善更广泛。k14仍有两图几何分歧增大：uNb-83增加0.03729，jh-09增加0.00997。整图同参考比较与不同空间参考的兼容池结果分开；不能看哪个空间Q高，就倒推该人员应该属于哪个空间。[R7、R8]')
 fig('stage08_figures/04_Doorway_Common14_Screening.png','图4：同17图、同整图目标、共同3—14人数范围。更高人数图集变小的结果另在容量面板表中，不接成同一条总体曲线。')
 p('门洞仍有明显的均值抵消。筛后10→14人，平均Q只增加0.324分，但逐图平均绝对变化3.185分，6升、11降；P10增加3.765分，12/17图提高，SD下降2.109分，14/17图降低。按各池实际满员判定，筛前平均Q有7/17图出现小变起点，筛后6/17，全部兼容池7/17；由于容量和观察尾段不同，不能直接用这三个数给筛查或兼容池排序。[R7]')
 p('质量条件均值还必须与失败状态并列。筛后k3→6，17/17图条件均Q上升，但完整可评率下降5.84个百分点。4352条路径尝试中，完整可评3770→3516，无连接335→775，不足四节点219→24，无效几何28→37。k14筛前到筛后，完整可评3763→4035，不足四节点313→73，无效几何36→3，而无连接240→241。该人数下的改善主要减少节点不足和其它无效几何，不能写成连接失败全面消除。[R9]')
 p('原先两套随机团队配对在部分门洞图误差过大，因此本轮对全部85池、1314个人数格，统一完成现有路径索引上的完整配对U统计，新增约2806万次池内不同几何状态配对计算；相同状态配对可以在不同池或人数格中重复。每个状态的路径频数保留，相同状态的零距离对也计入分母。这消除了额外配对近似噪声；它仍不是枚举人员池中所有可能团队。正式图表使用完整U，原匹配结果只作为精度诊断。[R8]')
 fig('stage08_figures/06_Doorway_Geometry_Response.png','图5：筛前与筛后同人数团队的底面分歧，以及同一路径加一人引起的底面变化。两者均与总Q不同；左图采用完整路径频率U。')
 h('五、五个案例把数值关系接到实际机制')
 tab(['图片与人数','实际结果','机制与解释'],[['VFua-04，34→35','满员Q缺失，完整率0','两个17票组未达到18票门槛，只剩3节点；仍有25人支持的投影连接环'],['pa4-11，3→35','均Q全范围0.752分，满员22.367','全部35份原答8点对，全票保留；当前参考4点对，共同参考不一致持续存在'],['e9z-17，11→12→13','Q 74.403→84.358→76.259','四节点、四转折、全票候选保持；变化来自定位和尺度'],['uNb-47，31→32','路径均ΔQ +17.877','临界组15→16票，并伴随身份组重组、定位和来源环改变'],['jh-09，23→24','路径均ΔQ +5.868','同一局部组11→12票入选；满员仍保留明显参考欠覆盖']])
 p('VFua-04：这是N=35的困难图。k30、33、34的完整可评率分别为231/256、118/256、230/256；k35为0/256，实质只有一支满员团队。完整诊断回放与原缓存47项核对一致：两个关键组各17票，在34人、门槛17时可形成不同四节点表达；35人门槛为18，两组都落选。最终三点投影环有25人来源支持，其中一条跨越未选节点的边，原答直接邻接支持0、投影支持25。失败原因是below_four，不是找不到连接；部分三角几何保留，正式Q缺失。[R10]')
 p('pa4-11：35份原答全部8个点对，恢复的k3、10、20、35团队中8个候选组均为全票，没有候选落选。满员Q=22.3668，参考相对遗漏0.2680、外扩0.1823，底边角误差9.4458°。继续增加人数显著缩小成员波动，却没有消除共同参考不一致。需要人工核对的是原图右侧入口/过渡区域是否属于当前四角主目标，而不是根据低Q先认定GT错误或人员乱标。[R10]')
 fig('stage08_figures/05_Stability_Is_Not_Accuracy.png','图6：拥有均值小变起点的图片，满员质量仍可很低。稳定描述的是曲线的后续变化，不是当前参考意义下的准确。')
 p('e9z-17：真实路径new256_225中，W108进入的11→12步使Q提高9.954分，W101再进入的12→13步使Q下降8.098分。三个端点始终4节点、4转折，四个候选组均获全员支持，无候选落选。两步底面1−IoU为0.06930、0.06115，面积变化+7.289%、−5.573%，质心移动0.07138h、0.07775h。主要变化在底面损失块，方向和高度变化较小。全图20→30人均Q下降约3.044分，P10却提高约3.977分，SD从9.476降至3.385。这是节点数量稳定、定位仍变、均值与低尾方向不同的明确案例。[R10]')
 fig('stage05_cases/manual/e9zR4mvMWw7-17/FIG_E9Z_POSITION_OVERLAY.png','图7：同四角点在底面坐标中的位置变化。完整原答、原图、参考及三队端点可在该图VIEWER.html中逐层查看。')
 p('uNb-47：选取最接近全部路径ΔQ中位数的replicate 51，W105最后进入；Q=52.963→81.876，节点与有效转折7→8。31、32人的门槛均为16，原15票组加一人后入选；另一处旧19票选中组与7票未选组的原答点对还发生重组，形成新21票组。最佳完整来源环支持14→8，整环支持并不套用MV50局部节点门槛。全部32种缺一人团队中，21/32升Q、19/32加节点，精确均ΔQ为+17.376，保留多数规律。该图筛前、筛后及全部兼容池完全相同，所以这不是筛查收益。[R11]')
 p('jh-09：replicate 3中W035最后进入，23、24人的门槛均为12，旧11个对应点对加上W035后达到12票，节点4→5、有效转折3→4，Q=21.593→31.691。全部24种缺一人团队中，17/24升Q，但恰好12/24加节点；不能把路径加权的137/256加节点改称精确多数。满员仍相对全部参考遗漏43.1%；同图13人全部兼容池满员Q=31.586、遗漏43.6%，说明剩余偏差不只来自混合单侧标注。具体应看参考中未覆盖区域是否清楚可见及是否为该目标必需结构。[R11]')
 h('六、判据、质量分项、精度与适用范围')
 p('设m(k)是某张图某个人数下的统计量，本轮全尾范围定义为R_m(k)=max{m(j):j≥k}−min{m(j):j≥k}。主容差为均值/P10 2分、SD 1分、状态率5个百分点；这些是在0—100质量尺度上便于解释的研究容差，不是v2.1新增验收阈值。主支持要求每个后续人数至少64/256条有效路径；短池和中途/满员缺失单列。几何低分歧使用所有后续U距离均低于阈值，语义与统计量全尾范围不同。')
 tab(['参数变化','平均Q有起点图数','平均Q起点中位数','P10有起点图数','P10起点中位数'],[['1分',145,15,76,'21.5'],['2分',163,11,127,19],['3分',170,8,148,14],['5分',184,5,168,11]])
 p('有效路径门槛改为32或128，主起点图数及中位数不变；更主要的敏感性来自对“小”的容差选择。现成整路径同时带显示，允许起点适当后移后，149/206图的均值全尾范围上界也≤2分，确认起点中位12人、相对各自点起点中位晚2人；P10为101/206图，中位20人、晚3人。最早贴阈值的人数有估计误差，并不抹去已有多数规律。[R2]')
 p('D10均值有164/206图识别起点，中位9人；IoU3D100为192/206图，中位6.5人。不同指标对位置、方向、顶部和体积的敏感性不同，不能拿IoU更早小变替换B8L2主解释。困难组P10有起点的仅16/37图，其满员Q中位43.855，14/16低于60；这个子集的P10中位起点14人，包含低尾稳定在低分区间，不代表困难图更早获得可靠高质量。[R2]')
 p('质量分项遵循冻结公式：Q=100/(1+hypot(F,D8)+Hg+Hl)。在IoU2D>0时，F=1/IoU2D−1+S_bottom²/32，D8=1.5d²/(d²+64)，Hg=(Hmean/0.8)²，Hl=(Hcenter/0.25)²；D10仅将方向块分母中的64换为100，其余组合与高度项不变。在完整可评分条件下，IoU2D=0沿用原算法连续极限Q=0，与不可评分的缺失分开。分项是损失，不能相加成Q分数变化，也不能把平均块代入公式代替平均Q。全部新增分项投影与既有Q核验，最大残差8.53e−14。结构、底面面积与质心、尺度、平均高度、遗漏/外扩及真实输出状态均有独立有效分母。[R9]')
 p('普通Manual主域之外，30个其他合法Manual目标池对应28张已有图片，分域保留，未当作新增独立图。Semi接续14个池、13图，保留旧24路径、新256路径或小池全排列各自身份；其中具256路径且N≥8的普通池只有2个，不据此给Semi总体平台人数。OOS单列，不进入正式Q结论。原答k1与当前两人补表k2独立保存，主人数稳定性分析从k3开始，未将旧两人延迟状态混入主曲线。')
 h('七、版本、复用、新增计算与验证')
 p(f'输入固定于Sparkling-Flames/3D_Manhattan_label提交{COMMIT}。研究采用记录来自paper_evidence_20261030、research_readiness_20261031与独立验收入口；普通Manual精确人员、参考、主轴、难度、排除及融合规则保持冻结。门洞采用screen439_results_20261031的正式池和路径；历史553/533资料仅用于精确端点或证据复用，不作为当前人池。')
 tab(['计算类别','本轮工作','是否改变正式结果'],[['原自然人数团队','复用每普通池256条完整进入排列及其精确端点','否；新增自然路径0，新增研究团队0'],['普通几何','复用206图现成U曲线，新增全尾/分层/同路径统计','不重融合、不重新评分'],['门洞几何','补齐全部1314人数格完整路径配对U；另存相邻步、到满员距离','只新增距离及统计'],['机制诊断','3个门洞既有团队与VFua满员既有团队，共4个不同端点回放','不替换缓存；全部几何/状态/票/分数验收一致'],['案例几何','e9z三端点之间新增距离和对应检验','不重融合'],['统计与图表','逐图、固定面板、敏感性、223页图册与5个完整案例','本轮新增交付']])
 p('独立身份核对覆盖普通206池1,667,072条路径×人数记录；门洞372,480条与当前采用曲线全部4365个格核对，最大数值差4.7e−13。普通256路径B8均值/P10的12198条有效带中心核对无差异；每个gzip和案例文件已完整读验。最终ZIP另做完整CRC和内部gzip解压检查。因并发写入曾发现少数生成文件尾部截断，已定向重写，并以最终完整读验与包内验证为准；源数据和研究结论未因此改写。')
 h('八、如何接续已有结论，以及仍需人工判断的内容')
 tab(['既有问题','本轮结论接续','可采用的研究说法'],[['总体均值平台','保留普通总体后段小增益；拆开真实小变与困难图抵消','多数简单图中后段平均Q变化小，困难条件仍可有显著正负响应'],['继续增加人数的价值','新增低尾、成员波动和几何分歧的逐图多数证据','即使均Q已小变，增加人数仍常减少低分尾部和换组不确定性'],['图难度与稳定','多数支持简单更早；困难出现无明确起点与低分稳态','报告可识别比例与支持图数，不只给条件中位人数'],['节点/结构数稳定','被e9z定位案例补充','同节点数不保证位置、尺度、布局或Q稳定'],['门洞筛除','切换为当前584/439；固定共同人数比较','低尾与几何一致性的改善比平均Q全图同向更普遍'],['满员或高票支持','被pa4共同偏差及VFua不足四节点补充','全票与低换组波动不保证参考准确；满员仍可能无法形成完整结果'],['预测或在线停止','未扩展','本轮结论是对当前人员池的回顾性描述，不是上线停止规则']])
 p('仍需人工语义判断的具体入口有两处：pa4-11右侧入口/过渡区域是否应由当前四角主目标包含；jh-09整图参考中持续未覆盖的区域是否可见、是否需要在该目标下标出。它们已有原图、完整原答、参考和融合叠图，不需要重新整理材料。本轮没有据低Q把这些写成GT已错。其它门洞中已登记的遮挡、闭合边和GT疑点继续保持原有裁决与证据等级。')
 p('本轮核心统计和所需诊断补算已完成。没有为了提高曲线一致性增加新人员、改变参考或重新选空间；也没有把人员分类重做成新方案。门洞最早起点尚无与普通主域同等的现成整路径同时带，因此本报告给其观察起点、容差/容量条件和完整逐图曲线，不给一个通用“门洞应到多少人”的精确常数。')
 h('九、文件阅读与复现')
 p('建议先读本报告和逐图结果索引，再查看Manual 206页、门洞17页图册。五个机制案例各有可脱网查看的HTML：原图、全部原答、参考、精确团队、融合几何及票账能够逐层追溯。全部CSV保留未评分缺失，下载包中的压缩表可直接由pandas或常规gzip工具读取。')
 tab(['交付目录','内容'],[['stage07_summary/integrated','206图主表、85门洞池主表、跨指标状态'],['stage03_response','逐k统计、全尾范围、主/敏感起点、逐路径变化'],['stage04_components','质量分项、结构、位置、尺度、高度、真实状态'],['stage04_geometry','普通缓存U、门洞完整U、相邻路径与到满员的几何距离'],['stage08_figures','PNG/PDF/SVG、绘图数据、223页图册与可检索HTML'],['stage05_cases/manual 与 stage04_doorway_cases','5个可追溯案例及完整诊断证据'],['scripts、source 与 stage02_normalized','统计复现代码、必要输入投影、冻结参考与身份索引；按交付目录直接解压'],['stage09_delivery','准确文件清单、SHA256、ZIP及内部表完整性结果']])
 p('为避免重复分发上游所有大缓存，提供统计复现所需的逐路径数值、精确成员、参考索引、几何目录及现成精度带；省去未用于统计的重复历史别名。该投影有文件级原哈希与新哈希，不覆盖来源。统计和图表可从这些输入重建；若要重新生成全部原始融合、查看所有206张原图或未选案例的全部历史状态，仍需指定提交的上游仓库/缓存包，依赖登记给出准确名称、路径和版本。本交付不声称包含整个上游研究工程。')
 h('数据依据与正文回连')
 sources=[
 ['R1','stage03_response/manual/PLATEAU_SENSITIVITY.csv.gz','domain=ordinary_manual_main, primary_rule=True；逐图起点、无结论原因与实际满员值'],
 ['R2','stage07_summary/manual/DIAGNOSTIC_FACTS.json；MC_ONSET_BRACKETS.csv','容差、支持门槛、整路径同时带、暂时平段与后段跃变'],
 ['R3','stage07_summary/manual/FIXED_PANEL_CHANGE_SUMMARY.csv.gz；ONSET_STRATA.csv','固定图片面板、难度/结构分层、正负方向、楼等权'],
 ['R4','stage04_geometry/ordinary_cached/GEOMETRY_U_CURVES.csv.gz；GEOMETRY_LOW_DISPERSION_SENSITIVITY.csv.gz','206图几何U、低分歧阈值与支持分母'],
 ['R5','stage07_summary/finite_tail/LEAVE_ONE_OUT_PATH_VS_EXACT.csv.gz','N−1全覆盖时的有限精确对照；不同P10定义单列'],
 ['R6','stage00_doorway_sources/CURRENT439_POOL_CAPACITY.csv；stage02_normalized/doorway/POOL_INDEX.csv','439采用链、当前逐图真实人员池、目标与参考'],
 ['R7','stage07_summary/doorway/RESULT_FACTS.json；SCREENING_FIXED_PANEL_IMAGE_CONTRASTS.csv.gz','同17图筛查比较、各容量面板与逐图方向'],
 ['R8','stage04_geometry/doorway_exact_U/GEOMETRY_U_CURVES.csv.gz；SCREENING_FIXED_PANEL_COMPARISON.csv','门洞完整路径配对几何、重复状态权重及分母'],
 ['R9','stage04_components/COMPONENTS_BY_K.csv.gz；NATIVE_STATUS_BY_K.csv.gz；METHOD.json','冻结公式、分项、结构与细分失败状态'],
 ['R10','stage05_cases/manual/CASE_INDEX.csv；各案例README_ZH.md与VIEWER.html','VFua、pa4、e9z的原图、完整原答、精确端点、票账与验收'],
 ['R11','stage04_doorway_cases/DOORWAY_LATE_CASES_ZH.md；DIAGNOSTIC_REPLAY_LEDGER.csv','uNb47、jh09的精确有限比较与完整候选/连接轨迹'],
 ['R12','stage07_summary/response_stages/IMAGE_STAGE_RESPONSES.csv.gz','167/171阶段强度结果；逐加人绝对变化定义与每步有效分母'],
 ['R13','stage07_summary/p10_definition_sensitivity/FACTS.json','线性P10与逆CDF的全206图判定和共同171图方向敏感性']]
 # The stage paragraphs cite the dedicated stage table as well as diagnostics.
 tab(['编号','结果文件','回连口径'],sources)
 return sources

def make_html():
 parts=['<!doctype html><html lang="zh"><meta charset="utf-8"><title>HOHONET v2.1逐图人数响应与稳定性研究</title><style>body{font-family:system-ui,"Noto Sans SC",sans-serif;max-width:1120px;margin:36px auto;padding:0 28px;color:#213547;line-height:1.85}h1{font-size:32px;line-height:1.35}h2{font-size:23px;margin-top:44px;border-bottom:2px solid #c9dce8;padding-bottom:8px}p{font-size:16px}table{border-collapse:collapse;width:100%;margin:18px 0;font-size:14px}th,td{border:1px solid #d4dfe6;padding:9px 11px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#e7f0f6}tr:nth-child(even){background:#f7f9fb}img{max-width:100%;height:auto}.caption{font-size:14px;color:#4c6576}.meta{color:#597181;font-size:14px}.top{background:#eaf3f7;padding:20px;border-radius:8px}</style><h1>HOHONET v2.1<br>逐图人数响应与稳定性研究</h1><p class="meta">研究批次：2026-11-01　普通Manual为主，门洞584/439单列<br>冻结提交：'+COMMIT+'</p>']
 for b in blocks:
  if b['type']=='heading':parts.append('<h2>'+html.escape(b['text'])+'</h2>')
  elif b['type']=='paragraph':parts.append('<p>'+html.escape(b['text'])+'</p>')
  elif b['type']=='table':parts.append('<table><thead><tr>'+''.join('<th>'+html.escape(str(v))+'</th>' for v in b['headers'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in b['rows'])+'</tbody></table>')
  else:
   data=base64.b64encode((ROOT/b['path']).read_bytes()).decode();parts.append('<figure><img src="data:image/png;base64,'+data+'"><figcaption class="caption">'+html.escape(b['caption'])+'</figcaption></figure>')
 parts.append('</html>');(OUT/'HOHONET_IMAGE_RESPONSE_REPORT_ZH.html').write_text('\n'.join(parts),encoding='utf8')

def make_pdf():
 font=ROOT/'assets/NotoSansSC-Regular.ttf';pdfmetrics.registerFont(TTFont('NotoSC',str(font)))
 pdfmetrics.registerFont(TTFont('NotoSCBold',str(ROOT/'assets/NotoSansSC-Semibold.ttf')))
 styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='ZH',fontName='NotoSC',fontSize=9.4,leading=15,spaceAfter=7,wordWrap='CJK'))
 styles.add(ParagraphStyle(name='ZHHead',parent=styles['ZH'],fontName='NotoSCBold',fontSize=14,leading=21,spaceBefore=14,spaceAfter=9,keepWithNext=True))
 styles.add(ParagraphStyle(name='ZHCell',parent=styles['ZH'],fontSize=8.1,leading=12,spaceAfter=0))
 styles.add(ParagraphStyle(name='ZHCap',parent=styles['ZH'],fontSize=8.2,leading=12,textColor=colors.HexColor('#506878')))
 styles.add(ParagraphStyle(name='ZHTitle',parent=styles['ZH'],fontSize=25,leading=34,spaceAfter=18))
 story=[Paragraph('HOHONET v2.1<br/>逐图人数响应与稳定性研究',styles['ZHTitle']),Paragraph('2026-11-01研究批次<br/>普通Manual 206图；门洞17图584/439双版本<br/>冻结提交 '+COMMIT,styles['ZHCap']),Spacer(1,8*mm)]
 width=A4[0]-36*mm
 for b in blocks:
  if b['type']=='heading':story.append(Paragraph(html.escape(b['text']),styles['ZHHead']))
  elif b['type']=='paragraph':story.append(Paragraph(html.escape(b['text']),styles['ZH']))
  elif b['type']=='table':
   rows=[b['headers']]+b['rows'];n=len(rows[0]);widths=[width/n]*n
   if b['headers'][0]=='编号':widths=[width*.075,width*.58,width*.345]
   elif n==3:widths=[width*.23,width*.34,width*.43]
   cells=[[Paragraph(html.escape(str(v)),styles['ZHCell']) for v in row] for row in rows]
   t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7f0f6')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f9fb')]),('BOX',(0,0),(-1,-1),.4,colors.HexColor('#c9d7df')),('INNERGRID',(0,0),(-1,-1),.25,colors.HexColor('#dbe3e8')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story.extend([t,Spacer(1,3*mm)])
  else:
   from PIL import Image as PILImage
   path=ROOT/b['path'];im=PILImage.open(path);height=width*im.height/im.width
   if height>155*mm:height=155*mm;ww=height*im.width/im.height
   else:ww=width
   story.append(KeepTogether([Image(str(path),width=ww,height=height),Paragraph(html.escape(b['caption']),styles['ZHCap']),Spacer(1,4*mm)]))
 def footer(can,doc):
  can.setFont('NotoSC',8);can.setFillColor(colors.HexColor('#657988'));can.drawString(18*mm,10*mm,'HOHONET v2.1 逐图人数响应');can.drawRightString(A4[0]-18*mm,10*mm,str(doc.page))
 doc=SimpleDocTemplate(str(OUT/'HOHONET_IMAGE_RESPONSE_REPORT_ZH.pdf'),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=16*mm,bottomMargin=18*mm,title='HOHONET v2.1 逐图人数响应与稳定性研究',author='HOHONET research analysis')
 doc.build(story,onFirstPage=footer,onLaterPages=footer)

def image_index():
 d=pd.read_csv(ROOT/'stage07_summary/integrated/MANUAL_206_IMAGE_RESULTS.csv');cols=['image','difficulty','N','B8L2_mean_onset_k','B8L2_mean_MC_confirmed_k','B8L2_p10_onset_k','B8L2_sd_onset_k','V_floor_low_dispersion_onset_k','full_B8L2_mean','full_complete_evaluable_rate']
 heads=['图片','难度','N','均Q小变起点','同时带确认起点','P10小变起点','SD小变起点','底面低分歧起点','满员Q','满员完整可评率']
 def fmt(v):
  if pd.isna(v):return '未识别/不可评'
  if isinstance(v,(float,np.floating)):return f'{v:.2f}' if v!=int(v) else str(int(v))
  return str(v)
 rows=''.join('<tr>'+''.join('<td>'+html.escape(fmt(r[c]))+'</td>' for c in cols)+'</tr>' for _,r in d.iterrows())
 htmltext='<!doctype html><html lang="zh"><meta charset="utf-8"><title>HOHONET逐图结果索引</title><style>body{font-family:system-ui,sans-serif;margin:24px;color:#234}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #ccd8e0;padding:8px}th{background:#eaf2f7;position:sticky;top:60px}input{position:sticky;top:0;width:90%;padding:12px;font-size:17px}tr:nth-child(even){background:#f7fafb}</style><h1>206图结果索引</h1><p>人数起点采用全尾范围和后续观察门槛。空值不是0。几何列定义为后续团队平均1−IoU均≤0.10，不是质量平台。完整字段与原因见CSV；全部曲线见图册。</p><input id="q" placeholder="按图名或难度筛选"><table><thead><tr>'+''.join('<th>'+v+'</th>' for v in heads)+'</tr></thead><tbody>'+rows+'</tbody></table><script>document.querySelector("#q").oninput=e=>document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.innerText.toLowerCase().includes(e.target.value.toLowerCase()))</script></html>'
 (OUT/'IMAGE_RESULTS_INDEX_ZH.html').write_text(htmltext,encoding='utf8')

if __name__=='__main__':
 sources=content();(OUT/'REPORT_CONTENT.json').write_text(json.dumps(blocks,ensure_ascii=False,indent=2));pd.DataFrame(sources,columns=['id','result_file','selection']).to_csv(OUT/'REPORT_EVIDENCE_INDEX.csv',index=False)
 make_html();make_pdf();image_index();print('Report HTML/PDF and readable image index created.')
