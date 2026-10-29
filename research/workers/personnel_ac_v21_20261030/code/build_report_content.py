"""Build the Chinese synthesis from finalized saved evidence and exact row keys.

No fitting, team generation, fusion or scoring occurs in this report builder.
All numeric table rows are copied into REPORT_NUMBER_LEDGER.csv for traceability.
"""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage08_report';OUT.mkdir(exist_ok=True)
B=[];S={};L=[];CACHE={}

def source(key,path,description):
    S[key]={'relative_path':path,'description':description}
def read(key):
    if key not in CACHE:CACHE[key]=pd.read_csv(ROOT/S[key]['relative_path'],low_memory=False)
    return CACHE[key]
def row(key,**filters):
    d=read(key)
    for k,v in filters.items():d=d[d[k].astype(str).eq(str(v))]
    assert len(d)==1,(key,filters,len(d))
    r=d.iloc[0]
    values={str(k):(None if pd.isna(v) else v.item() if hasattr(v,'item') else v) for k,v in r.items()}
    L.append({'source':key,'filters':json.dumps(filters,ensure_ascii=False),'values':json.dumps(values,ensure_ascii=False,allow_nan=False)})
    return r
def h(text,level=1):B.append({'kind':'h','text':text,'level':level})
def p(text,src=None,small=False):B.append({'kind':'p','text':text,'source':src,'small':small})
def table(title,headers,rows,src,widths=None):B.append({'kind':'table','title':title,'headers':headers,'rows':rows,'source':src,'widths':widths})
def picture(path,caption):B.append({'kind':'image','path':path,'caption':caption})
def fmt(x,n=3,signed=False):return '不可评' if pd.isna(x) else format(float(x),('+' if signed else '')+f'.{n}f')
def fraction(a,b):return f'{int(a)}/{int(b)}'
def get(method,n,m,role,metric='B8L2_CA',view='A_fixed_n',scope='primary',condition='manual'):
    return row('E04',method=method,n_condition=n,m_condition=m,role_direction=role,metric=metric,analysis_view=view,scope=scope,condition=condition)
def effect_line(label,method,n,m,role,view='A_fixed_n'):
    q=get(method,n,m,role,view=view);d=get(method,n,m,role,'D10_CA',view)
    return [label,str(n)+'/'+str(m),str(int(q.valid_images))+'/'+str(int(q.registered_images))+'；'+str(int(q.valid_buildings)),fmt(q.image_mean,3,True),fmt(d.image_mean,3,True),fmt(q.image_balanced_mean_absolute),fraction(q.positive_images,q.valid_images)]

source('E01','stage00_intake/SOURCE_COMMIT.json','开始时远端提交、旧本地工作树与冻结来源')
source('E02','stage01_capacity/MAIN_SCALE_BRIEF.csv','逐图真实原答与楼外标签的全容量')
source('E03','stage01_registered/FINAL_REGISTRATION_DOMAIN_COVERAGE.csv','最终设计覆盖，方法事件和物理对分开')
source('E04','stage05_main/CONDITION_METRIC_SUMMARY.csv.gz','完整直接AC及整类主结果；逐指标分母，图等权与楼等权')
source('E05','stage05_context_common/FROZEN_CONTEXT_EFFECT_SUMMARY.csv.gz','既有正式难度与结构条件下的响应')
source('E06','stage05_context_common/COMMON_POOL_METHOD_COMPARISONS.csv.gz','相同图片目标人数替换量的描述性方法比较')
source('E07','stage05_funnel_bridge/MAIN_SCALE_FUNNEL_BRIEF.csv','合法容量到登记执行可评与方向的完整漏斗')
source('E08','stage05_funnel_bridge/independent_main_summary_check/WHOLE_DEFINITION_SPLIT_SUMMARY.csv','整来源换出、整目标换入、等大两类全换的独立拆分')
source('E09','stage05_funnel_bridge/STRICT_M10_COMMON_CONDITION_BRIEF.csv','已有严格ABC九十人及本轮AC的共同条件参照')
source('E10','stage05_funnel_bridge/STATE_DOMAIN_DENOMINATOR_SUMMARY.csv','目标域、物理对与团队状态分母')
source('E11','stage05_funnel_bridge/STRICT66_BACKGROUND_PHYSICAL_SUPPORT_SUMMARY.csv','严格桥接中的同精确XZ背景对照及物理去重')
source('E12','stage06_cases/CASE_EVENT_SUMMARY.csv','51个机制展示事件与原始方向、所有质量和几何分项')
source('E13','stage06_cases/CASE_ENDPOINT_SUMMARY.csv','32支独立既有团队的全组票账、定位和来源环')
source('E14','stage05_sensitivity/preselected_four_complete/compact_tables_v2/SEVEN_TEAM_Q_BY_IMAGE.csv.gz','容量事前指定四图的七联盟完整结果')
source('E15','stage05_sensitivity/preselected_four_complete/compact_tables_v2/PURE_WHOLE_EQUAL_ANCHOR_SUMMARY.csv.gz','四图已有同人数纯类锚，质量与同源劳动')
source('E16','stage05_sensitivity/preselected_four_complete/compact_tables_v2/TWELVE_PARENT_DECOMPOSITION_SUMMARY.csv.gz','12个不等人数父对照与48个等人数中间路径')
source('E17','stage01_capacity/POOL_CLASS_MEMBERS.csv.gz','逐图逐目标逐楼外折的实际类别成员和原答ID')
source('E18','stage08_report/FROZEN_ALL_DESCRIPTIVE_CLASS_MEMBERS.csv','冻结ALL描述名单，不能代替逐图容量')
source('E19','stage02_engine/EXECUTION_ACCOUNTING_CLARIFICATION.json','新增实体、完整端点复用与旧标量回放的精确记账')
source('E20','stage07_reproduction/verification/REPRODUCTION_PARITY.json','最小导出源码实际复现一队的完整数值与几何验证')


def build_main():
    assert json.loads((ROOT/'stage05_main/SUMMARY_RECEIPT.json').read_text())['complete']
    h('HOHONET v2.1 直接AC与整类人群模拟研究',0)
    p('普通 Manual 为主　冻结分类与融合规则　两队比较、整类替换、类别联盟及成员背景敏感性　2026-10-29')
    h('1 可以实际采用的研究安排')
    p('继续采用 TARGET_DSTRUCT K3 作为普通 Manual 的主解释分类，K2 保留粗层。主研究应并用两种条件：固定 n20/m7 的中结构角色→高结构角色，及固定 n20、将该图高结构类全部可用成员等量换入。前者把人数和替换量固定，后者把整类人群的含义固定；两者回答不同问题。大块十、十二人替换作为条件研究保留，不因为人数更大就取代覆盖更广的主条件。','E02/E04/E08')
    q=get('TARGET_DSTRUCT_K3','20','7','2->3');w=get('TARGET_DSTRUCT_K3','20','whole_class_actual_m','2->3',view='whole_equal_fixed_n_all_m')
    p(f"固定20/7主方向覆盖{int(q.valid_images)}图、{int(q.valid_buildings)}楼，B8L2平均{fmt(q.image_mean,3,True)}、逐次平均绝对变化{fmt(q.image_balanced_mean_absolute)}，{fraction(q.positive_images,q.valid_images)}图平均上升。整目标类换入覆盖{int(w.valid_images)}图、{int(w.valid_buildings)}楼，m为1–8，B8L2平均{fmt(w.image_mean,3,True)}，{fraction(w.positive_images,w.valid_images)}图上升。这支持研究不同人群如何改变共识，也保留了明确的负向图片。",'E04/E08')
    p('TARGET主方向的结构变化主要集中在有结构挑战的图片；简单图也常在有效转折数不变时升Q，需结合定位、方向和高度分项解释。类别构成有解释作用，具体成员和共同背景也能使方向反转。稳定输出、输出失败、低分完整输出必须分别解释。除另注明，核心结果表均指普通Manual原主目标。','E05/E12/E13')
    table('各方法的正式用途',['方法','采用用途','本轮新增证据与限制'],[
      ['TARGET K3 与 K2','主解释分类；K2说明粗边界，K3保留父内差异','20/7及整目标类换入有跨多图多楼的方向支持；K3十人方向仅在K2同一父类内部，覆盖3图。'],
      ['OPPJOINT K3 与 K4','联合质量、劳动和标法画像；大块混合人群模拟','十、十二人容量较宽；这些大块没有换入最高历史Q类，平均升质弱、双向变化明显。K4用途保留，不能只用可行图更多判断优越。'],
      ['RAW3 K3','原答定义敏感性和较大替换块','八人高结构方向扩展覆盖；十二人出现同楼四图全负及另一楼两图全正，角色与建筑必须分开。'],
      ['RFUSE GEOM K2','从融合响应反看人员作用','四人方向在82图有77图升Q，同时输出失败增加；继续作为反向互补，不能担当十人纯类块。'],
      ['OPPSTRUCT K3','结构机会响应补充','在可计算结构条件下组织对照；有自己的容量与响应，不因本轮主位固定而删去。']],'E02/E04/E05',[3.3,4.4,9.5])

    h('2 接续的数据与本轮实际新增')
    p('开始时远端为 ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff，本地旧工作树仍在519c7447278dd16c3d69f505b807fb5b53792b36。本轮从前者导出所需现行来源，已读独立审查README第8、9节、十人容量表、最终下游标签与另线程严格大块结果，没有退回旧参考或补造资格规则。当前完整来源已包含严格九、十人研究，因此仅将其接入比较，没有重复计算。','E01/E09')
    p('数据采用现行v2.1主目标快照及其它准入目标快照；同一图不同合法目标独立组队和评价。W019、W026的排除与原答资格保持不变；没有足够分类历史但有合法原答的人员只能作为未分类背景，不能放进声称纯类的替换块。空间归属不通过最高Q选择。正式难度、冻结LOBO标签、正式参考和融合参数均未改。','E17')
    table('容量入口与实际执行域',['域','全部合法池','实际执行池','说明'],[
      ['普通Manual主目标','206','206','206独立图片、22楼，主分析'],['普通Manual其它准入目标','30','20','实际20池涉及18图、7楼；其余10池只有3–4人，未进入本轮选定设计，逐池保留原因'],
      ['普通Semi主目标','37','31','用已有Semi自身标签，作为次要补充'],['普通Semi其它准入目标','1','1','独立目标，不与主目标人员混队'],
      ['门口与特殊空间库存','20','0','17个门口Manual、2个特殊Manual、1个特殊Semi单列；不与普通域混合']],'E03/E17',[4.3,2.2,2.2,8.5])
    p('两个输入快照合计294池＝236普通Manual＋38普通Semi＋20门口/特殊空间。容量材料中的“普通Manual以外58池”包含38个普通Semi，不能把58全部称作OOS或未执行空间；本轮执行258池＝226普通Manual＋32普通Semi。')
    p('最终登记478,012支不同团队、471,758条方法事件、412,839个无向物理端点对、550,794条设计关联。方法事件、设计关联、团队和图片是不同计数；反向展示与多方法命中相同端点不构成独立重复。核心运行474,332支是真正新增实体，2,027支为已有标量而缺完整几何的必要回放，1,653支直接复用已有完整端点。','E03/E19')
    p('核心原生评价476,359次，分为首波10,991次与续算465,368次。2,027次旧标量回放的状态和Q可得性全部一致，数值最大差1.42×10⁻¹³；没有例外。机制追踪32支既有团队和单队最小复现另记，不增加研究样本。本轮没有新增人员、房间、全新同房ABC或256条自然人数曲线。','E19/E20')

    h('3 比较设计与读数口径')
    p('直接AC固定图片、目标、参考、n与m：A=D∪X，C=D∪Z，D完全相同且D/X/Z互不重叠，X与Z是不同冻结类别的等量成员。它估计这次跨类调整的实际效果；没有B队时不估计“跨类比同类更大”。整类是该图该目标该楼外折中的全部合格成员，而非全历史名单。','E17')
    table('相互补充的设计',['设计','固定与改变','回答的问题'],[
      ['等人数AC','同D、同n/m；X换成同样大的Z','实际跨类调整改变质量、几何、劳动或状态多少'],
      ['整类等量替换','来源全出、目标全入、两类等大全换分列','完整一个类别进入或退出真实图片池的影响'],
      ['两类全部不等量互换','同外部D；两类全员但人数不同','人数与类别共同改变的结果；用既有等量中间队分解路径'],
      ['完整类别联盟','每个非空类别组合全部成员；必要时另列固定未知背景','模拟类1、类2、类3及两两或三类叠加'],
      ['固定D或固定XZ','分别改变替换成员、背景成员/配比、背景人数','拆开类别、具体成员与共同背景的敏感性'],
      ['固定A扩大块','原队和既定嵌套成员顺序固定，逐步扩大m','避免把不同图片或不同方向的m7/m12均值当纯比例效应']],'E03/E04',[3.4,6.7,7.1])
    p('主A面板m取7、8、9、10、12；RFUSE补3、4人，其他准入Manual补3、4人。n由容量事前选取m、ceil(1.5m)、2m、2m+2、20及N−m中的合法值。一般保存8组XZ，分两批不同种子并对跨批组合去重；组合数≤16时枚举。整类方案通常抽4组，支持少时枚举。固定D、固定A及多背景另有独立登记。参数和具体成员选择不依据目标Q或替换收益。')
    p('固定人数AC与整类等量主表采用事前登记的neutral_members_0背景路径；联盟、不等人数整类和背景敏感性分析使用各自登记的设计。先在目标池内平均可评成员组合，再按图等权；同图多目标先等权合并，并另报楼等权。覆盖漏斗含所有登记背景，所以其总体均值可能与主效果不同。全部背景结果保留在敏感性表，没有只留下表现好的背景。相同政策名称不保证各方法的实际D类别配比相同。','E04/E07')
    p('Δ一律指C−A；B8L2与D10正值为提高，结构、面积、高度和劳动正值只表示增加。平均绝对变化先对每个实际事件取|Δ|再汇总，不能用|平均Δ|替代。Q分项、几何、劳动及状态各有自己的有效分母。缺Q不填0；几何表同时保留可成有效底面的对和双方完整输出的严格子集。BEV距离为1−IoU，无量纲；质心为相机高度h，面积h²，角度为度。')
    p('劳动是已有标注记录的劳动量。主劳动比较要求两队全部有记录、各计时来源的人数向量相同；单一同源的其他对照另列。总劳动不是并行团队的墙钟完成时间，也不是程序运行耗时。固定XZ时劳动秒数差不随D改变，百分比仍会因A的分母改变。')

    h('4 从合法图片池到大块执行范围')
    p('等量AC的容量条件是1≤m≤n、n≥3、N≥n+m、来源类≥m、目标类≥m；未知标签可留D。N−m是固定XZ后最大相同队伍人数。在当前普通Manual的N最大35人池里，24人换12人的AC需要至少36人，实际不可能；23人换12人则可以。整类联盟可用全35人，但全员35人只有一支队，不能在同一个35人池内再做35人等量换人。Semi有自身更大的人员池，另节报告。','E02/E07')
    rows=[]
    for method,label in [('TARGET_DSTRUCT_K3','TARGET K3'),('V21_DSTRUCT_RAW3_K3','RAW3 K3'),('OPPJOINT_K3','OPPJOINT K3'),('OPPJOINT_K4','OPPJOINT K4'),('OPPSTRUCT_K3','OPPSTRUCT K3')]:
        vals=[]
        for m in [7,8,9,10,12]:
            r=row('E02',method=method,m=m);vals.append(str(int(r.any_n_pools)))
        r10=row('E02',method=method,m=10);r12=row('E02',method=method,m=12)
        rows.append([label,*vals,str(int(r10.n20_pools)),str(int(r12.n20_pools))])
    table('主目标逐图类别容量 这些不是不同分类思想数量',['方法','m7任意n','m8','m9','m10','m12','20/10','20/12'],rows,'E02',[3.2,2.0,1.6,1.6,1.6,1.6,2.0,1.6])
    p('20/10的206个合法池中，35池先因总人数退出；剩171池的已分类人员总量均足够。类别分布再使TARGET、RAW3、JOINT3、JOINT4分别退出168、152、89、64池，最终3、19、82、107池全部登记并执行，且各池至少有一个Q可评事件。但所有登记事件都可评的池只有3、17、75、98；不能把“池可评”写成“每次成功”。','E07')
    p('TARGET全部m9/m10可行方向均在同一个K2父类内部；其主高结构粗边界最多支持8人。OPPJOINT K3/K4的m10/m12均未涉及最高历史Q类。类别容量更宽说明可研究范围更宽，不说明替换更优。RAW3十二人容量的6图还分为两种方向和两栋楼，不能把所有十二人结果当同一类人变化。','E02/E17')
    p('实际23/12前沿已覆盖RAW3 4图1楼、JOINT3 19图6楼、JOINT4 27图10楼；25/10前沿分别覆盖TARGET 1图1楼、RAW3 9图4楼、JOINT3 52图11楼、JOINT4 73图16楼。中间22/12不在所有池的冻结人数网格中：RAW3登记0/4、JOINT3 11/24、JOINT4 16/35。前沿条件已回答较大队问题，未选中间n明确记录为未登记，不称失败或容量不足。','E07')

    h('5 固定人数和固定替换块的结果')
    specs=[('TARGET K3 中→高','TARGET_DSTRUCT_K3','14','7','2->3'),('TARGET K3 中→高','TARGET_DSTRUCT_K3','20','7','2->3'),('TARGET K2 粗边界','TARGET_DSTRUCT_K2','20','7','1->2'),('TARGET K3 中→高','TARGET_DSTRUCT_K3','20','8','2->3'),('RAW3 中→高','V21_DSTRUCT_RAW3_K3','20','8','2->3'),('OPPJOINT K3 Q1→3','OPPJOINT_K3','20','7','1->3'),('OPPSTRUCT 中→高','OPPSTRUCT_K3','20','7','2->3'),('RFUSE 响应1→2','RFUSE_GEOM_K2','20','4','1->2')]
    table('主结构解释与既有七八人条件的连接',['方向','n/m','可评/登记图；楼','ΔB8L2','ΔD10','均|ΔQ|','Q正向图'],[effect_line(*x) for x in specs],'E04',[3.6,1.3,3.2,2.1,2.1,2.1,2.8])
    p('这些是各方法实际覆盖范围上的结果，不是同一组人员的算法竞赛。K2与K3的20/7都覆盖85图，但源类候选与抽到的具体人员不同，不能用4.65与4.58的微小均值差评判粗细层优劣。K3增加的是低、中结构角色及其条件响应的解释；K2提供不再细分低、中角色的粗边界。RAW3八人高结构方向扩展到38图15楼，是容量与定义的补充。','E04/E06')
    specs=[('TARGET K3 低→中','TARGET_DSTRUCT_K3','20','10','1->2'),('RAW3 低→中','V21_DSTRUCT_RAW3_K3','20','10','1->2'),('RAW3 低→高','V21_DSTRUCT_RAW3_K3','20','10','1->3'),('RAW3 中→高','V21_DSTRUCT_RAW3_K3','20','10','2->3'),('JOINT3 Q1→2','OPPJOINT_K3','20','10','1->2'),('JOINT4 Q1→2','OPPJOINT_K4','20','10','1->2'),('JOINT4 Q2→3','OPPJOINT_K4','20','10','2->3'),('RAW3 低→中','V21_DSTRUCT_RAW3_K3','20','12','1->2'),('RAW3 中→高','V21_DSTRUCT_RAW3_K3','20','12','2->3'),('JOINT3 Q1→2','OPPJOINT_K3','20','12','1->2'),('JOINT4 Q1→2','OPPJOINT_K4','20','12','1->2'),('JOINT4 Q2→3','OPPJOINT_K4','20','12','2->3'),('RAW3 低→中','V21_DSTRUCT_RAW3_K3','23','12','1->2'),('JOINT3 Q1→2','OPPJOINT_K3','23','12','1->2'),('JOINT4 Q1→2','OPPJOINT_K4','23','12','1->2'),('JOINT4 Q2→3','OPPJOINT_K4','23','12','2->3')]
    table('十人十二人及较大团队 保留全部实际方向',['方向','n/m','可评/登记图；楼','ΔB8L2','ΔD10','均|ΔQ|','Q正向图'],[effect_line(*x) for x in specs],'E04',[3.6,1.3,3.2,2.1,2.1,2.1,2.8])
    p('OPPJOINT K3的20/10有42/82图升Q、40图下降，均值仅+0.297但平均绝对变化3.282；这是一种双向不确定性，不能写成稳定升质。RAW3的23/12低→中方向4/4图下降，均值−7.492，却只来自B6ByNegPMKs一楼；其20/12中→高的另两图来自q9vSo1VnCiC，均为正。这样的方向与建筑分离比合成一个“十二人好/坏”的结论更准确。','E04')
    picture('stage08_report/figures/FIG01_EQUAL_SIZE_EFFECTS.png','图1 重点条件的有符号均值、图片P10–P90与多数方向。线段是分布，不是置信区间；全部方向见前表。')

    h('6 整个类别进入或退出怎样改变结果')
    rows=[]
    definitions=[('TARGET 低→中 来源全出','TARGET_DSTRUCT_K3','1->2','whole_source_out_only'),('TARGET 中→高 目标全入','TARGET_DSTRUCT_K3','2->3','whole_target_in_only'),('TARGET 低→高 来源全出','TARGET_DSTRUCT_K3','1->3','whole_source_out_only'),('TARGET 低→高 目标全入','TARGET_DSTRUCT_K3','1->3','whole_target_in_only'),('TARGET 低→高 两类全换','TARGET_DSTRUCT_K3','1->3','both_classes_entire_equal')]
    available=read('E08').whole_definition.unique().tolist()
    for label,method,role,definition in definitions:
        if definition not in available and definition=='both_classes_entire_equal':definition=next(v for v in available if 'both' in v)
        q=row('E08',scope='primary',condition='manual',analysis_view='whole_equal_fixed_n_all_m',method=method,role_direction=role,n_condition='20',metric='B8L2_CA',whole_definition=definition)
        z=row('E08',scope='primary',condition='manual',analysis_view='whole_equal_fixed_n_all_m',method=method,role_direction=role,n_condition='20',metric='D10_CA',whole_definition=definition)
        rows.append([label,f'{int(q.actual_m_X_min)}–{int(q.actual_m_X_max)}',str(int(q.valid_images))+'/'+str(int(q.registered_images))+'；'+str(int(q.valid_buildings)),fmt(q.image_mean,3,True),fmt(z.image_mean,3,True),fmt(q.image_balanced_mean_absolute),fraction(q.positive_images,q.valid_images)])
    table('固定n20且等量的三种整类定义',['定义与方向','实际m','可评/登记图；楼','ΔB8L2','ΔD10','均|ΔQ|','Q正向图'],rows,'E08',[4.5,1.1,3.0,2.0,2.0,2.0,2.6])
    p('推荐的TARGET中→高185图全部属于“整个目标类换入”：来源类抽出等量人员，目标类使用该图全部1–8人。它不是把37人的全局中类全换掉。相反，低→中的186图全部是整个来源类换出，Q均值较弱，但逐事件绝对变化仍约2.96分。低→高又包含来源全出、目标全入和两边全换三种，分别保留。','E08/E17')
    specs=[('TARGET K2 粗层','TARGET_DSTRUCT_K2','20','whole_class_actual_m','1->2'),('RAW3 中→高','V21_DSTRUCT_RAW3_K3','20','whole_class_actual_m','2->3'),('JOINT3 Q1→3','OPPJOINT_K3','20','whole_class_actual_m','1->3'),('JOINT3 Q2→3','OPPJOINT_K3','20','whole_class_actual_m','2->3'),('JOINT4 Q2→4','OPPJOINT_K4','20','whole_class_actual_m','2->4'),('RFUSE 响应1→2','RFUSE_GEOM_K2','20','whole_class_actual_m','1->2')]
    rows=[]
    for label,method,n,m,role in specs:
        x=effect_line(label,method,n,m,role,'whole_equal_fixed_n_all_m');x[1]='20/逐图m';rows.append(x)
    table('其它解释路线的整类等量结果',['方向','n/m','可评/登记图；楼','ΔB8L2','ΔD10','均|ΔQ|','Q正向图'],rows,'E04',[3.6,1.9,3.0,2.1,2.1,2.1,2.4])
    p('此表采用三种整类定义合并后的覆盖口径；来源全出、目标全入、两类全换各自结果见E08，不能全部解释为整目标类换入。','E08')
    p('TARGET中→高的池前沿整目标类换入登记205图，200图22楼有共同可评Q；n为5–32、m为1–8。B8L2平均+2.390、156/200图上升；D10平均+2.206、157/200上升。n随池容量改变，额外图片也不同，不能拿它与n20的均值差当“背景变多导致衰减”。同一XZ改变背景人数的严格嵌套对照另外分析。','E08')

    h('7 质量分项几何劳动和失败分别说明什么')
    items=[('TARGET 20/7','TARGET_DSTRUCT_K3','20','7','2->3','A_fixed_n'),('TARGET整目标 n20','TARGET_DSTRUCT_K3','20','whole_class_actual_m','2->3','whole_equal_fixed_n_all_m'),('JOINT3 20/10','OPPJOINT_K3','20','10','1->2','A_fixed_n'),('RAW3低→中 20/12','V21_DSTRUCT_RAW3_K3','20','12','1->2','A_fixed_n'),('RFUSE 20/4','RFUSE_GEOM_K2','20','4','1->2','A_fixed_n')]
    rows=[];labor=[];loss=[];native=[];scale=[];tails=[]
    for label,method,n,m,role,view in items:
        ts=[get(method,n,m,role,x,view) for x in ['fusion_turn_n_CA','ref_node_recall_5_CA','ref_edge_recall_5_CA','geometry_bev_distance_AC_complete_outputs_only','geometry_centroid_distance_AC_complete_outputs_only']]
        rows.append([label,fmt(ts[0].image_mean,3,True),fmt(100*ts[1].image_mean,2,True),fmt(100*ts[2].image_mean,2,True),fmt(ts[3].image_mean,4),fmt(ts[4].image_mean,4),str(int(ts[3].valid_pairs))+'对'])
        tt=get(method,n,m,role,'record_time_CA_pct_source_matched',view);sec=get(method,n,m,role,'record_time_CA_seconds_source_matched',view)
        aa=get(method,n,m,role,'A_Q_missing',view);cc=get(method,n,m,role,'C_Q_missing',view)
        labor.append([label,fmt(sec.image_mean,1,True),fmt(tt.image_mean,2,True)+'%',fraction(tt.positive_images,tt.valid_images),str(int(tt.valid_pairs))+'对/'+str(int(tt.valid_images))+'图',fmt(100*aa.image_mean,2)+'%→'+fmt(100*cc.image_mean,2)+'%'])
        ls=[get(method,n,m,role,x,view) for x in ['boundary_loss_CA','direction_loss_CA','height_loss_CA']]
        loss.append([label,*[fmt(x.image_mean,5,True) for x in ls],str(int(ls[0].valid_pairs))])
        ns=[get(method,n,m,role,x,view) for x in ['IoU3D100_CA','S_bottom_deg_CA','dir_CA','Hmean_CA','omission_CA','extension_CA']]
        native.append([label,*[fmt(x.image_mean,4,True) for x in ns]])
        gs=[get(method,n,m,role,x,view) for x in ['fusion_short_turn_edges_CA','geometry_area_h2_pct_CA','height_mean_h_pct_CA','geometry_top_angle_AC','geometry_bottom_angle_AC']]
        scale.append([label,*[fmt(x.image_mean,4,i<3) for i,x in enumerate(gs)]])
        qq=get(method,n,m,role,view=view); qa=get(method,n,m,role,'A_B8L2',view); qc=get(method,n,m,role,'C_B8L2',view)
        tails.append([label,fmt(qq.image_p10)+'～'+fmt(qq.image_p90),fmt(qq.image_min),fmt(100*qq.image_balanced_event_loss10_fraction,2)+'%',fmt(qa.image_p10)+'→'+fmt(qc.image_p10),str(int(qa.valid_images))+'/'+str(int(qc.valid_images))])
    table('结构保留与完整输出对的几何变化',['条件','Δ有效转折','Δ节点保留pp','Δ边保留pp','BEV距离','质心距离h','几何分母'],rows,'E04',[3.8,2.0,2.3,2.1,2.0,2.4,2.6])
    p('TARGET20/7的85图中只有14图平均有效转折增加，71图均值不变；参考节点保留平均增加3.98个百分点，但质量改善覆盖78图。人员作用因此需要结合定位和边方向指标，不能只用增删节点定义作用。在RAW3低→中20/12的四图中，有效转折数均不变，但5°参考节点保留的图均值下降，方向和高度损失的图均值上升；各图及9°阈值仍有不同响应。','E04')
    table('已有质量分项 IoU提高为好，其余为误差或分量变化',['条件','ΔIoU3D×100','Δ底面边界角°','Δ正交残差°','ΔHmean','Δ遗漏','Δ扩展'],native,'E04',[3.6,2.4,2.3,2.3,2.2,2.2,2.2])
    p('dir是各输出相对自身最佳正交轴的方向残差（度），不是对正式参考朝向的角误差；Hmean是周长加权平均高度比的绝对残差，不是实际平均高度。实际高度和面积变化另列。补充WQ的height_loss与原Hmean定义不同，同一事件可以有不同方向，不能统称某个“高度分项”改善。','E04')
    table('补充质量损失 数值下降表示该损失减小',['条件','Δ边界损失','Δ方向损失','Δ高度损失','共同有效对'],loss,'E04',[4.6,3.2,3.2,3.2,3.0])
    table('短结构尺度和上下边界的几何变化',['条件','Δ短边数','Δ面积%','Δ平均高度%','顶部角距离°','底部角距离°'],scale,'E04',[3.7,2.2,2.5,2.7,3.0,3.1])
    p('面积、高度的有符号差说明尺度向哪边变化，不自动等于质量升降；百分比为100×(C/A−1)。顶部/底部角距离是两队匈牙利匹配后已匹配角点的角差，非对参考误差；未匹配角点数另外保存，不能因匹配部分角距小就忽略新增或缺失结构。各项全部有效数保存在源表，未要求所有几何字段使用Q共同有效分母。','E04')
    table('响应分布与低尾 不用均值覆盖负向尝试',['条件','图均ΔQ P10–P90','最小图均ΔQ','逐图等权降>10分事件比例','端点图均Q P10 A→C','A/C可评图'],tails,'E04',[3.2,3.4,2.3,3.1,3.8,1.4])
    p('响应分布仅用共同Q可评事件，下降超过10分的比例先在每图内部计算再图等权。最后两列为A与C各自可评图片的平均端点Q分布低尾，可能使用不同图集；即使图集相同，各图内有效登记事件也可不同，按事件出现次数汇总而非唯一端点等权。它们属于状态相关的描述，不是匹配低尾的因果效应。全部Q缺失另列，未纳入0分尾部；这些区间是有限图片的描述分布，不是预测区间或统计置信区间。','E04')
    table('同源记录劳动与所有登记队的缺Q状态',['条件','劳动秒差','劳动百分比','劳动增加图','劳动有效支持','A→C缺Q图等权率'],labor,'E04',[3.5,2.0,2.0,2.2,3.3,4.2])
    p('RFUSE20/4在77/82图升Q，但656个登记对中A端缺Q5次（3次below_four、2次legacy no_connection），C端缺Q12次（9次legacy no_connection、3次invalid_floor）；共同Q可评640对。A缺Q图等权率约0.76%、C约1.83%，须并列报告这一输出风险。TARGET20/7登记680对；Q共同可评659对，有效转折及可用几何669对，双方完整输出的几何比较659对，同源劳动344对、65图，状态比较用全部680对。事件侧出现次数不是独立失败团队数。不同分母保留其真实含义，不用可评事件的质量优势覆盖失败事件。','E04')
    p('所有设计合并的478,012支团队中，471,454支产出complete_conditional，4,635支为legacy no_connection，1,817支below_four，106支invalid_floor，合计6,558支缺Q；没有执行异常或测量异常。这是登记设计内的端点计数，不是自然人群的失败概率。complete_conditional表示按冻结路径形成完整可评价输出，不保证符合参考或人工语义正确。legacy no_connection仅表示未形成可用点序列，不能靠状态名断定纯连接原因。','E19')
    p('在412,839个不同物理端点对中，997对两端均缺Q，其中71对的原始状态还不相同。缺Q风险差等于0并不等于两端成功，也不等于几何相同。完整状态迁移与失败类别单列。','E10')
    picture('stage08_report/figures/FIG02_FROZEN_DIFFICULTY_RESPONSE.png','图2 正式难度保持原定义。结构响应集中于困难图片，质量响应也可出现在转折不变的简单图。')
    p('TARGET20/7的简单、中等、困难层分别60、15、10图；B8L2均值变化为+3.632、+3.168、+12.347，正向57/60、12/15、9/10。有效转折均值分别+0.008、+0.117、+1.654。按可计算条件看，边界自遮挡12图平均Q增加11.616，11/12图为正；无短转折且无边界遮挡65图仅有1图平均转折增加，但61/65图升Q。这支持当前主分类的条件化解释，不要求所有图出现同一种结构响应。','E05')


def append_section_file(name):
    pth=OUT/name
    if not pth.exists():raise FileNotFoundError('Final synthesis section not yet complete: '+str(pth))
    obj=json.loads(pth.read_text());B.extend(obj['blocks']);S.update(obj.get('sources',{}));L.extend(obj.get('ledger',[]))


def finish():
    h('13 采用方案的保留新增与复现')
    p('保留主分类TARGET K3、K2粗层及OPPJOINT、RAW3、RFUSE的既定分工。本轮新增的采用建议是：把n20整目标类换入作为广覆盖的主要人群模拟，与固定20/7及既有严格ABC并列；按逐图容量可行的具体角色方向研究十、十二人纯类块、较大团队和背景敏感性，其中TARGET九、十人方向仍限于K2父内低、中细分。不能因某个最大Q差或可行图更多重新决定主分类。')
    p('既有独立审查已回答分类参数来源、v2.1重算、RAW3定义敏感性、Q/QT基线控制、有限配比解释及严格同类B问题，本轮不重复这些计算。新增的是冻结标签下的完整容量登记、实际直接AC、整类三种定义、完整类别联盟、成员和背景变化、较大队及其完整几何与机制。正反向分类的互补性仍保留；不为名称对称再造反向方法。')
    p('全部结果针对现有有限人员和图片池。楼外标签避免把目标楼历史用于拟合，并不把本轮方法选择变成新人员或新建筑的外部预测验证。多个图片反复使用同一小类核心人员，必须与成员频率一起解释。Q序、历史结构角色也不是每图每人的永久顺序。')
    p('交付按阶段保存：容量及来源、冻结设计、四批完整原生端点、两批逐事件指标、全部图楼汇总与敏感性、九图机制案例、最小复现源码和本综合报告。源包与旧版本保留。大文件冗余总拼接不作为唯一数据源，完整逐池分片已逐项验证并交付；分片可以恢复全部端点与事件。源代码复现使用当前提交导出的142项文件，无需重新获取整个大仓库。','E20')
    p('最小复现已实际运行一支登记团队：23个数值字段、状态和完整几何与保存结果完全一致。报告表格的实际源行、筛选键和完整精度写入REPORT_NUMBER_LEDGER.csv，研究图都有精确CSV数据。各压缩包均逐文件读取、哈希校验，内部gzip读至EOF并校验CRC，CSV检查行宽，JSON/JSONL完整解析。准确文件名、SHA-256与下载链接见DOWNLOAD_INDEX_ZH。','E20')
    h('14 证据文件索引')
    for key,item in S.items():
        path=ROOT/item['relative_path'];assert path.exists(),path
        sh=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1<<20),b''):sh.update(block)
        item['sha256']=sh.hexdigest();item['bytes']=path.stat().st_size
        p('['+key+'] '+item['description']+'。'+item['relative_path'],small=True)
    (OUT/'REPORT_BLOCKS.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n')
    (OUT/'REPORT_EVIDENCE_INDEX.json').write_text(json.dumps(S,ensure_ascii=False,indent=2)+'\n')
    pd.DataFrame(L).to_csv(OUT/'REPORT_NUMBER_LEDGER.csv',index=False,encoding='utf-8-sig')
    print(json.dumps({'blocks':len(B),'tables':sum(x['kind']=='table' for x in B),'sources':len(S),'extracted_rows':len(L)},ensure_ascii=False))


if __name__=='__main__':
    build_main()
    for name in ['SECTION08_SENSITIVITY.json','SECTION09_ALLIANCES.json','SECTION10_CASES.json','SECTION11_STRICT_AND_SCOPE.json']:append_section_file(name)
    finish()
