"""Assemble completed coalition and mechanism evidence without new inference runs."""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage08_report'

class Section:
    def __init__(self):self.blocks=[];self.sources={};self.ledger=[];self.cache={}
    def source(self,key,path,description):self.sources[key]={'relative_path':path,'description':description}
    def data(self,key):
        if key not in self.cache:self.cache[key]=pd.read_csv(ROOT/self.sources[key]['relative_path'],low_memory=False)
        return self.cache[key]
    def row(self,key,**filters):
        d=self.data(key)
        for c,v in filters.items():d=d[d[c].astype(str).eq(str(v))]
        assert len(d)==1,(key,filters,len(d))
        r=d.iloc[0]
        values={str(k):(None if pd.isna(v) else v.item() if hasattr(v,'item') else v) for k,v in r.items()}
        self.ledger.append({'source':key,'filters':json.dumps(filters,ensure_ascii=False),'values':json.dumps(values,ensure_ascii=False,allow_nan=False)})
        return r
    def h(self,text,level=1):self.blocks.append({'kind':'h','text':text,'level':level})
    def p(self,text,source=None):self.blocks.append({'kind':'p','text':text,'source':source})
    def table(self,title,headers,rows,source,widths=None):self.blocks.append({'kind':'table','title':title,'headers':headers,'rows':rows,'source':source,'widths':widths})
    def picture(self,path,caption):self.blocks.append({'kind':'image','path':path,'caption':caption})
    def save(self,name):
        (OUT/name).write_text(json.dumps({'blocks':self.blocks,'sources':self.sources,'ledger':self.ledger},ensure_ascii=False,indent=2)+'\n')

def f(x,n=3,signed=False):return '不可评' if pd.isna(x) else format(float(x),('+' if signed else '')+f'.{n}f')

def alliances():
    s=Section()
    s.source('A01','stage05_sensitivity/preselected_four_complete/PRESELECTED_8_17_10_TEAMS.csv.gz','四图七种完整类别联盟的28支精确团队')
    s.source('A02','stage05_sensitivity/preselected_four_complete/compact_tables_v2/PURE_WHOLE_EQUAL_ANCHOR_SUMMARY.csv.gz','96个既有同人数纯类锚点的逐图12条件结果，劳动中位数与方向保留')
    s.source('A03','stage05_sensitivity/preselected_four_complete/compact_tables_v2/TWELVE_PARENT_DECOMPOSITION_SUMMARY.csv.gz','12条整类父对照，每条4个等人数中间路径')
    s.source('A04','stage05_sensitivity/PRESELECTED_FOUR_CASES_REPORT_ZH.md','四图全部联盟、纯类锚点、路径与精确人员的完整解释')
    s.source('A05','stage05_sensitivity/PRESELECTED_8_17_10_CASES.json','读取结果前按17/10/8容量形状指定的四图及成员')
    s.source('A06','stage05_sensitivity/three_leg_common_support_v2/REQUESTED_ALL_OUTSIDE_D_DIRECTIONS_WITH_SIZES.csv.gz','完整较高角色小类退出的预定七方向，三段共同有效并按父对照等权，含实际人数范围')
    s.source('A07','stage05_sensitivity/three_leg_common_support_v2/COMMON_VALID_DECOMPOSITION_RECEIPT.json','全部不等人数整类路径按共同有效支持与外部背景分层的验证')
    s.h('9 35人池里的完整类别联盟与两两组合')
    s.p('按实际容量在结果出现前指定pa4otMbVnkk的06、11、42、44四图：OPPJOINT K3楼外标签下，C1有17人、C2有10人、C3有8人。每图七种非空类别联盟全部计算，人数为8、10、17、18、25、27、35；七队的21个无向对全部保留，四图合计28队、84对。另有12个同人数纯类条件、96个精确AC对，以及12条不等人数父对照、48条中间路径；都使用已登记执行的端点。','A01/A02/A03/A05')
    s.p('四图同属一楼，不能当四次独立的类别人群复现。C3的固定八人是W102、W109、W112、W115、W121、W122、W126、W130；这八人在完整C3进入时每人使用率100%，该图没有其它C3成员可扰动。C1四图共同16人，C2共同8人，全池共同32人；各图35人并非完全同一名单。历史画像中C3转折/复杂机会转折较多、历史Q较高、来源内劳动较长；这不保证单图Q始终按C1<C2<C3排序。','A04/A05')
    images=['pa4otMbVnkk-'+x for x in ['06','11','42','44']]
    teams=[('C3',8),('C2',10),('C1',17),('C2|C3',18),('C1|C3',25),('C1|C2',27),('C1|C2|C3',35)]
    for metric in ['B8L2','D10']:
        rows=[]
        for im in images:
            rows.append([im.split('-')[-1]]+[f(s.row('A01',image=im,alliance_classes=c)[metric]) for c,n in teams])
        s.table(f'七联盟{metric} 全部结果',['图尾号']+[c.replace('|','+')+'\n'+str(n)+'人' for c,n in teams],rows,'A01',[1.8]+[2.2]*7)
    s.p('28队全部产出可评分完整输出。06、42、44每队四节点，11每队八节点；这组联盟间的差异不能用节点数增减解释。06、42、44中C3单类比分更多人的全部35人更高，但这不是人数本身的独立效应。11所有联盟共同低分（约21.98–29.73），全35人也未消除与当前参考的共同差异。','A01')
    s.h('9.1 同人数纯类锚点保留具体成员的不确定性',2)
    rows=[]
    for im in images:
        for sc,tc in [('C1','C2'),('C1','C3'),('C2','C3')]:
            r=s.row('A02',image=im,source_class=sc,target_class=tc)
            rows.append([im.split('-')[-1],sc+'→'+tc,str(int(r.n)),f(r['B8L2_CA__mean'],3,True),f(r['D10_CA__mean'],3,True),f(r['B8L2_CA__min'])+'～'+f(r['B8L2_CA__max']),str(int(r['B8L2_CA__positive_pairs']))+'/'+str(int(r['B8L2_CA__valid']))])
    s.table('D为空，来源抽样八组，目标小类全部换入',['图','整类方向','n=m','均ΔQ','均ΔD10','ΔQ全范围','Q增加对'],rows,'A02',[1.0,2.1,1.2,2.4,2.4,5.3,2.8])
    s.p('四图的C3整类换入在所有已抽来源组合中均升Q，幅度仍明显受成员影响：44的C1→C3约+2.20至+22.53。相反，06的C1→C2八对全部降Q，42与44的同方向同时有正负结果。这些是固定人数、固定空背景下的类别与具体成员共同作用；没有B队，不由此估计“跨类超过同类”。','A02')
    rows=[]
    for im in images:
        r=s.row('A02',image=im,source_class='C2',target_class='C3');pre='record_time_CA_seconds_source_matched__'
        rows.append([im.split('-')[-1],str(int(r[pre+'valid'])),f(r[pre+'mean'],1,True),f(r[pre+'median'],1,True),str(int(r[pre+'positive_pairs']))+'/'+str(int(r[pre+'negative_pairs'])),f(r[pre+'min'],1)+'～'+f(r[pre+'max'],1)])
    s.table('C2→完整C3，n=m=8的合法记录劳动',['图','有效对','均Δ秒','中位Δ秒','增加/减少对','Δ秒全范围'],rows,'A02',[1.1,1.5,2.3,2.5,3.0,6.8])
    s.p('11这8对Q全升，但劳动6减2增，中位差−26.175秒、均差+10.645秒；少数增加值改变均值。06、42、44则8对劳动全部增加。完整联盟人数不同，每图严格来源计数匹配为0/21对；只有C2、C3和C2+C3三支单来源队之间每图3/21对，可按单一来源规则另看不等人数总劳动，四图合计12/84对。06的完整C2十人总劳动1084.741秒，完整C3八人1451.845秒，多367.104秒（33.84%），尽管人数更少且Q更高。记录劳动不等于同步标注墙钟速度。','A01/A02/A04')
    s.h('9.2 整类人数不等时，沿明确中间队拆开变化',2)
    rows=[]
    for im in images:
        for role in ['2->1','3->1','3->2']:
            r=s.row('A03',image=im,role_direction=role)
            rows.append([im.split('-')[-1],role.replace('->','→'),str(int(r.n_small))+'→'+str(int(r.n_large)),f(r['B8L2_CA__total_mean'],3,True),f(r['B8L2_CA__equal_mean'],3,True),f(r['B8L2_CA__equal_min'])+'～'+f(r['B8L2_CA__equal_max']),f(r['B8L2_CA__addition_mean'],3,True)])
    s.table('全部12个父对照 父差计一次，中间两段平均4条路径',['图','整类方向','团队n','总ΔQ','等量段','等量段范围','追加段'],rows,'A03',[1.0,2.0,1.7,2.1,2.3,5.0,2.1])
    s.p('每条路径先等量换类，再加入目标类剩余成员；父对照D固定为第三个完整类别，追加段的共享人员还包括已换入的目标子集。质量标量满足总差＝等人数段＋追加成员段，48条路径的B8L2闭合误差最大5×10⁻¹⁶。42和44在D=C3、C2十人换C1十七人时，总Q分别−0.515、−0.480，但等人数段均值为+0.012、+0.091；追加七名具体C1成员段为−0.528、−0.571。等量段内部仍有正负路径。不能把追加段称作与身份无关的纯人数因果效应，也不能让同一父差因四条路径被重复加权四次。百分比按端点比值复合，几何距离不满足这种标量加法。','A03/A04')
    s.h('9.3 全范围整类不等人数互换：小类退出和追加大类成员',2)
    s.p('全范围保存12,922个不等人数父对照、63,491条等人数中间路径。为了让“总差＝两段之和”有共同统计含义，每个指标要求同一路径三段全部有效，先中间队平均到父对照，再池/图/楼等权；无D、部分外部D、全部外部D分开。这里按“完整较高结构或较高历史Q的小类退出”这个问题，展示TARGET/RAW3的3→2、JOINT3的3→1与3→2、JOINT4最高角色4退出的全部三个方向，没有按最大收益筛选。其它方向完整保留。','A06/A07')
    specs=[('TARGET 3→2','TARGET_DSTRUCT_K3','3->2'),('RAW3 3→2','V21_DSTRUCT_RAW3_K3','3->2'),('JOINT3 3→1','OPPJOINT_K3','3->1'),('JOINT3 3→2','OPPJOINT_K3','3->2'),('JOINT4 4→1','OPPJOINT_K4','4->1'),('JOINT4 4→2','OPPJOINT_K4','4->2'),('JOINT4 4→3','OPPJOINT_K4','4->3')]
    rows=[]
    for label,method,role in specs:
        keys=dict(scope='primary',condition='manual',method=method,role_direction=role,background_profile='outside_swapped_classes_neutral_members_0',parent_background_stratum='all_outside_D')
        q=s.row('A06',**keys,metric='B8L2_CA');d=s.row('A06',**keys,metric='D10_CA')
        ntext=f"n{int(q.common_valid_n_small_min)}–{int(q.common_valid_n_small_max)}→{int(q.common_valid_n_large_min)}–{int(q.common_valid_n_large_max)}\nm{int(q.common_valid_small_class_n_min)}–{int(q.common_valid_small_class_n_max)}"
        assert q.registered_images_x==q.registered_images_y
        rows.append([label,f'{int(q.valid_images)}/{int(q.registered_images_x)}；{int(q.valid_buildings)}',ntext,f(q.total_image_mean,3,True),f(q.equal_image_mean,3,True),f(q.addition_image_mean,3,True),f(d.total_image_mean,3,True),f'{int(q.total_negative_images)}/{int(q.valid_images)}'])
    s.table('固定该图全部外部D：小类全出，大类全入，人数不等',['方向','Q有效/登记图；楼','共同可评n/m范围','总ΔQ','等量ΔQ','追加ΔQ','总ΔD10','Q负向图'],rows,'A06',[3.2,2.5,2.9,1.7,1.7,1.7,1.7,1.8])
    s.p('TARGET3→2有197图、22楼共同可评，145图总Q下降：总差−4.722＝等人数段−7.408＋追加剩余目标成员+2.686。JOINT3的3→1为176图、20楼，135图下降，总−4.547＝−6.252＋1.705。追加更多具体大类成员可以部分抵消等量换类的退化，但平均未恢复原小类输出。这个结果将“完整类别退出”的负向作用扩展到多图多楼，并与前文整目标高角色换入的正向作用形成互补。','A06')
    s.p('这些方向的来源小类常只有1–8人，属于整类研究，不等于十人或十二人大块覆盖；n范围随实际池改变。对照的另一个合法方向可从端点反向读取，但不会作为第二个独立样本。三段统计共同有效不等于所有父对照可评，原始失败仍保留。不同D层的图片和人数范围也不同，不能把层间均值差直接当成纯背景因果效应。','A06/A07')
    s.save('SECTION09_ALLIANCES.json')

def cases():
    s=Section()
    s.source('C01','stage06_cases/CASE_EVENT_SUMMARY.csv','51个展示事件与质量几何劳动的完整精确行')
    s.source('C02','stage06_cases/CASE_ENDPOINT_SUMMARY.csv','32支去重团队的未选组、定位、来源环和全部边票')
    s.source('C03','stage06_cases/representative_cases/REPORT_REPRESENTATIVE_MECHANISMS_ZH.md','正负微变和固定十人块扩大背景的全状态机制核查')
    s.source('C04','stage06_cases/background_wc2_53/REPORT_BACKGROUND_WC2_53_ZH.md','固定九人块、两人背景改变的逐观测与连接机制')
    s.source('C05','stage06_cases/alliance_pa4_11/REPORT_ALLIANCE_PA4_11_ZH.md','共同八点表达和现行四点参考的可检查案例')
    s.source('C06','stage06_cases/alliance_pa4_06/REPORT_ALLIANCE_PA4_06_ZH.md','七联盟同一四点结构的位置尺度高度和劳动变化')
    s.source('C07','stage06_cases/CASE_DELIVERY_VALIDATION.json','9图32队51事件全读、图形渲染和离线查看器验收')
    s.source('C08','stage06_cases/representative_selection/SELECTED_EVENT_IDS.csv','全结果后机制选例的规则与所选事件，不参与团队设计')
    s.h('10 为什么会变化：原答分组定位连接三层证据')
    s.p('案例包含9图、32支既有唯一团队、51条展示事件、252个完整身份组。四个离线HTML查看器嵌入原图、完整原答、正式参考、融合输出、所有入选和未选组、来源顺序与逐边票账。14个代表端点完整几何哈希相同；全32队中只有wc2背景①A的一个派生footprint坐标回放相差1 ULP（4.44×10⁻¹⁶），ERP点、节点身份顺序与拓扑相同，原核心端点保留。这些追踪不增加物理样本。','C07')
    s.p('正、负、小变化代表从完整研究结果按确定性规则选取，靠近相应条件的图片均值或中位响应；候选全集保存。容量预选的四图联盟另列。选例可以说明机制，发生频率必须回到逐图全结果，不以几个展示事件替代总体统计。','C08')
    selected=[('bded3837a41e1443a8d3e0c0','TARGET 正'),('40317b257c8fcbf05d19b432','TARGET 负'),('15da8ffcf872e5b382923b76','TARGET 小变化'),('e97305b1de2620cdfecc0991','RAW3 降质'),('568a18aa50c6ef9f71c2d9ce','JOINT 正'),('1883f7c444eec56b77d2bee9','JOINT n20'),('c9d196878be82330b752a7fc','JOINT n22')]
    rows=[]
    for eid,label in selected:
        r=s.row('C01',event_id=eid)
        rows.append([r.image,label,str(int(r.n_A))+'/'+str(int(r.m_X)),str(int(r.A_nodes))+'→'+str(int(r.C_nodes)),f(r.A_B8L2)+'→'+f(r.C_B8L2),f(r.B8L2_C_minus_A,3,True),f(r.D10_C_minus_A,3,True),'不可比' if pd.isna(r.record_time_CA_seconds_source_matched) else f(r.record_time_CA_seconds_source_matched,1,True)])
    s.table('代表事件均为原规范方向C−A 缺Q保持缺失',['图片','条件','n/m','节点','B8L2 A→C','ΔQ','ΔD10','劳动Δ秒'],rows,'C01',[3.2,2.2,1.1,1.0,3.0,2.1,2.1,2.5])
    s.p('S9的两行劳动−44.028秒按相同来源计数向量可比，但两队均含旧、新混合来源，不称单一来源。VFua与x8来源计数不匹配；uNb-14还含未知劳动记录，均保持不可比。','C01/C03')
    s.h('10.1 结构保留增加可以伴随升Q或降Q',2)
    s.p('VFuaQ6m2Qom-07：TARGET中→高20/7，换入该图全部七名C3。七人本身达不到MV50=10；参考r3（ERP横向约992）附近，A的两个相关组各6票，C出现5D＋6Z＝11票的新对应组。节点8→9，5°参考点8/16→9/16、边5/16→7/16，Q+5.016。但r9–r14密集小结构仍有4–9票未选，不能称完整恢复。共同D的归组也改变，不是固定旧组直接加七票。','C01/C03')
    s.p('x8F5xyUWy9e-03：同一TARGET方向、同样整类七人换入，r5（u≈403.8）由9票到恰好10票，邻近r4（u≈391）仍9票未选。节点4→5，参考点4/6→5/6、边3/6→4/6；Q却−1.188。底面角误差0.552°→0.623°、方向误差1.845°→2.014°，补充WQ诊断height_loss略降，而原Hmean分项略增。参考结构保留改善与Q下降同时出现；新增一个点没有恢复成对转折，也未保证整体几何质量提高。参考点边保留不是B8L2的加法评分分项，不能据总Q下跌否认结构分类产生了作用。','C01/C03')
    s.h('10.2 同一基本结构里，位置和劳动仍会变',2)
    s.p('uNb9QFRL6hY-56：两队四组与四条边均全20人支持，没有未选组；D13人的实际组支持已超过门槛10。Q98.024→98.111，底面1−IoU仅0.003208、质心差0.000252h，但同源劳动少266.940秒。它属于高分结构内的细微位置/顶部变化。这里证实的是当前组内D已足票，没有另运行纯D队，不把它说成独立D反事实。','C01/C02/C03')
    s.p('RAW3的B6ByNegPMKs-22：20/12，两队都四组全员支持，来源环和边也全员支持；12人块在每组都能独立达门槛10。Q−10.917而IoU3D×100只−0.282，方向误差2.217°→3.974°，底面角误差0.390°→0.564°。长窄空间中的位置偏移放大方向损失，高度补充损失反而改善；记录劳动少196.510秒。它是降质、省记录劳动、同节点数的几何变化，不是融合失败。','C01/C02/C03')
    s.p('OPPJOINT的uNb9QFRL6hY-14：20/12只抽部分C1/C2，非整类；两队四点保留均完整。参考r1主表达支持12→17，另一未选表达8→3，共同D也改变归组，定位/高度改善，Q+0.872。劳动记录不全且来源计数不匹配，劳动差留空。','C01/C03')
    s.h('10.3 同一九人块只换两人背景，响应可以反向',2)
    s.p('wc2JMjhGNzB-53，TARGET n11/m9，X/Z九人固定，门槛6。D从W027/W122（两名C3）换成W017/W126（C2＋C3），同时改变身份和类别构成。背景①Q差−2.756，背景②+30.702，差33.458；所选值最接近该图该条件六个可评物理背景候选的均值31.646，未选最大76.236。这不是整个背景研究的平均差。','C04')
    s.p('关键在ERP拼接边界r3（u≈16.23）附近。同一Z成员W034的一份原始观测从旧2票组移入W008/W013/W029三观测组，新组得到4Z＋2D＝6票，恰好过门槛；C从四点变五点。固定Z43个观测的903对同组关系中，13对新增同组、4对解除。A也有归组变动，并非完全不变。九人块人数大于门槛，不等于对这个局部节点已有九张一致票。','C04')
    s.p('新五点输出只有W034的一条完整投影来源环，某条边直接/投影支持均3票，低于节点门槛6。冻结规则选支持最多的完整来源环，不要求每条边都获MV50。Q大幅改善并不意味着所有连接得到多数支持；参考边保留仍25%，扩展和高度损失还变差。两种背景劳动均不可比，保持缺失。','C04')
    s.picture('stage06_cases/background_wc2_53/four_endpoint/FOUR_ENDPOINTS_FIXED_XZ.png','图3 固定九人X/Z与n11，只改变两人背景。四端点和全部票数同时展示，背景身份与类别构成均改变。完整大图见案例包。')
    s.h('10.4 两种互斥表达同时过票，及增加背景后的低分恢复',2)
    s.p('S9hNv5qa7GM-04，JOINT K4，固定十人X/Z。n20的A含两套各10人的四角位置表达：两节点共同20票，另外两对互斥位置各10票。MV50接受正好半数，六节点全部入选且位置均确定，但没有任何完整来源环同时经过六节点，原生原因no_source_ring_covering_all_selected_nodes，因此Q缺失。不能当Q=0后计算改善。','C01/C02/C03')
    s.p('D加入W113/W121后n22、门槛11。两人支持更远离参考的那套位置，使其12票通过，近参考一对仍10票落选；A恢复四节点完整输出，Q仅58.407。C维持近参考一对15票，Q98.639。因此恢复输出不等于恢复高质量。该过程同时改变具体D成员、人数和票门槛，不能只归因于替换比例下降。全登记候选中这类所选恢复条件只涉及一图，未当普遍发生率。','C01/C03')
    s.picture('stage06_cases/representative_cases/fixed_xz_n20_n22/FOUR_ENDPOINTS_FIXED_XZ.png','图4 固定十人替换块，从n20到n22，互斥表达和MV50门槛共同决定输出；左上缺Q没有画成0分。')
    s.h('10.5 七联盟共同低分：需要人工判断目标范围的具体位置',2)
    s.p('pa4otMbVnkk-11的35份完整原答均八点，七队56个对应组全员支持，来源环和八条边也全部有效；正式参考却是四点矩形。Q21.984–29.725来自共同八点外伸表达及底面位置偏差，既非漏掉过票节点，也非融合失败。C3更接近当前参考，仍保留同一八点轮廓；不能仅据现有Q认定所有人的语义表达都错误。','C02/C05')
    s.picture('stage06_cases/alliance_pa4_11/figures/SEVEN_ALLIANCES_BEV.png','图5 pa4-11七队均八点，当前正式参考为四点。坐标统一，没有按队单独缩放；共同外伸与整体偏移同时存在。')
    s.table('可直接人工检查的具体问题',['图片','位置或结构','需要判断什么'],[
        ['pa4otMbVnkk-11','ERP x约525–1010；参考r2→r3闭合边','当前目标是否包含入口/外伸轮廓？保持正式参考，先判断空间语义。'],
        ['VFuaQ6m2Qom-07','r3 u约992；r9–r14 u约417–466','新增角和仍未保留的密集小转折应如何表达，是否有可接受简化？'],
        ['wc2JMjhGNzB-53','拼接处r3/r4 u约16–18；五点输出u约939.7短接','新增组是否对应目标真实角，残留短接是否遗漏真实结构？'],
        ['S9hNv5qa7GM-04','u约171/223与359/412两对位置','柜体/墙体附近哪套位置表达符合冻结目标空间？']
    ],'C03/C04/C05',[3.5,5.3,8.4])
    s.p('这些人工问题不会触发本轮改参考、改空间或改类别。完整原图与全部原答都在案例查看器中，人工判断后若需修订正式目标，应作为另一个明确版本，而非选择最高Q参考消除反例。','C07')
    s.save('SECTION10_CASES.json')

if __name__=='__main__':
    alliances();cases()
    print('Saved completed sections 09 and 10 with exact source rows.')
