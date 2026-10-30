"""Assemble the scientific v2 -> v2.1 crosswalk from completed module tables.

This script does not recompute experiments.  It keeps source identities and
scope-specific denominators explicit, checks the principal quoted values,
and writes machine-readable Chinese closeout tables.  Paths in delivery
columns are relative to the delivered study root; repository-only paths
refer to the separately frozen repository commit.
"""
from pathlib import Path
import csv
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'stage06_synthesis'
OUT.mkdir(exist_ok=True)
SHA = '13a7861334749805a86dc19e9ea79fcaa71020c0'
checks = []


def one(path, **filters):
    d = pd.read_csv(ROOT / path)
    for key, value in filters.items():
        d = d[d[key].eq(value)]
    if len(d) != 1:
        raise AssertionError((path, filters, len(d)))
    return d.iloc[0]


def check(path, filters, column, value, tol=1e-5):
    actual = one(path, **filters)[column]
    assert math.isclose(float(actual), value, abs_tol=tol, rel_tol=0), (path, column, actual, value)
    checks.append(dict(source=path, filters=filters, column=column, actual=float(actual), expected=value))


check('stage01_half_team/MAIN_CHECKED_SUMMARY.csv', dict(n=14, m=7), 'events', 197, 0)
check('stage01_half_team/MAIN_CHECKED_SUMMARY.csv', dict(n=14, m=7), 'gap_A_positive_images', 61, 0)
check('stage01_half_team/MAIN_CHECKED_SUMMARY.csv', dict(n=14, m=7), 'gap_sym_nonpositive_images', 21, 0)
check('stage01_half_team/MAIN_CHECKED_SUMMARY.csv', dict(n=14, m=7), 'CB_mean', 6.5775005483)
check('stage01_half_team/MAIN_CHECKED_SUMMARY.csv', dict(n=20, m=7), 'CB_mean', 4.5249667401)
abc = dict(final_method='TARGET_DSTRUCT_K3', analysis_scope='ordinary_comparable', condition='manual', metric='B8L2', level='direction_nm', role_direction='2→3')
check('stage02_same_room/abc/SUMMARY.csv', dict(**abc, n=10, m=5), 'events', 268, 0)
check('stage02_same_room/abc/SUMMARY.csv', dict(**abc, n=10, m=5), 'valid_events', 237, 0)
check('stage02_same_room/abc/SUMMARY.csv', dict(**abc, n=10, m=5), 'building_equal_CB_mean', 13.749295)
check('stage02_same_room/abc/SUMMARY.csv', dict(**abc, n=14, m=7), 'building_equal_GA_mean', -2.240602)
cap = dict(method='TARGET_DSTRUCT_K3', condition='manual', ordinary_comparable=True, role_direction='2→3')
check('stage02_same_room/abc/HALF_CAPACITY_SUMMARY.csv', dict(**cap, n=14, m=7), 'legal_pairs', 2, 0)
check('stage02_same_room/abc/HALF_CAPACITY_SUMMARY.csv', dict(**cap, n=10, m=5), 'legal_pairs', 32, 0)
check('stage02_same_room/abc/HALF_CAPACITY_SUMMARY.csv', dict(**cap, n=10, m=5), 'executed_pairs', 19, 0)
main = dict(metric='B8L2', scenario='v21_all', scope='ordinary_no_relation_oos_pending')
check('stage02_same_room/prediction/DIRECT_MEAN_SUMMARY_BY_SCOPE.csv', dict(**main, method='source_mean'), 'mae', 6.463518)
check('stage02_same_room/prediction/DIRECT_MEAN_SUMMARY_BY_SCOPE.csv', dict(**main, method='external_image_mean'), 'mae', 9.496483)
check('stage02_same_room/prediction/PERSONAL_SIMILARITY_BY_SCOPE.csv', main, 'symmetric_corr_surprise', .012878)
check('stage02_same_room/prediction/PERSON_PREDICTION_SUMMARY_BY_SCOPE.csv', dict(**main, budget='single_direct', stage='single', method='public_external'), 'mae', 13.385294)
check('stage02_same_room/prediction/PERSON_PREDICTION_SUMMARY_BY_SCOPE.csv', dict(**main, budget='single_direct', stage='single', method='public_external'), 'unique_people', 56, 0)
check('stage02_same_room/prediction/DECLARATION_VARIATION_SUMMARY.csv', main, 'building_equal_worker_share', .5264506)
check('stage02_same_room/prediction/DECLARATION_VARIATION_SUMMARY.csv', main, 'building_equal_view_share', .0826716)
check('stage02_same_room/prediction/DECLARATION_VARIATION_SUMMARY.csv', main, 'building_equal_interaction_share', .3908778)

OLD_USES = 'source/research/same_room/same_room_acceptance_20261022/USES_CLOSEOUT.md'
OLD_CHAIN = 'source/research/statistics/research_closeout_20261022/CONCLUSIONS_ZH.md'
DEPS = 'source/research/data/releases/v2.1/personnel_reselection_dependencies/README.md'
FINAL_OLD = 'source/research/data/releases/v2.1/final_classification_downstream/README.md'
SPEED = 'stage03_speed_difficulty/'
ROOM = 'stage02_same_room/'
SEL = 'stage05_selection_stop/'
HALF = 'stage01_half_team/'

rows = []


def add(id, topic, old, current, reason, support, paper, action, sources, old_sources='', repo_sources='', boundary='', filters=''):
    rows.append(dict(条目ID=id,研究问题=topic,原结论与版本=old,当前结果=current,变化原因=reason,
                     支持范围与统计单位=support,论文采用表述=paper,本轮处理=action,
                     当前证据源表_交付根目录相对路径=sources,原结论来源_交付根目录相对路径=old_sources,
                     保留成果源表_冻结仓库相对路径=repo_sources,精确筛选条件=filters,边界与反例=boundary,
                     冻结仓库提交=SHA))


add('C01','人员分类的研究身份',
    'v2与前轮v2.1分别形成结构类、联合画像及融合响应等路线；归档文档曾使用采用或主分类措辞。',
    '本轮TARGET_DSTRUCT K3/K2仅为已归档工作分析对象；OPPJOINT用于联合画像，RFUSE保留反向融合解释，RAW3保留原答敏感性和较大块补充。没有新拟合或最终选型。',
    '遵守用户最新研究立场，区分科研选型决定与已有证据完整性。',
    '方法、楼外折、源设计、空间和条件各保留身份。ALL名单只作描述，不能替代留出楼标签。',
    '人员分类用于组织不同标法及人群响应，本轮报告各工作方法已获支持的用途，最终方法选择尚待研究者决定。',
    '解释口径修订', FINAL_OLD+';'+DEPS, OLD_CHAIN,
    boundary='不按最大Q差或覆盖数重选主分类，不把其它方法说成已被否定。')

add('C02','质量与资格更新的基底',
    'v2正式质量7,302份、196图；原答、源资格、目标归属和评分是不同层。',
    'v2.1正式主目标质量8,154份；普通Manual为6,512份/206图。快慢匹配另保留可用于表达研究但无正式Q的原答，缺Q不填0。其它合法空间231份/31池单列。',
    '当前正式参考及资格增加支持；原始作答几何没有因评分版本而被修改。',
    '质量原答数、表达原答数、团队数、事件数、图片数不互换；各指标有效分母保留。',
    '本研究在相同空间与当前资格内比较人群，更新评分与扩大研究支持分开解释。',
    '复用现有基底，仅更新受影响依赖',
    'source/research/data/releases/v2.1/quality_inventory.csv;'+ROOM+'prediction/SUPPORT.csv;'+SPEED+'RECORD_SUPPORT.csv',
    OLD_CHAIN, boundary='OOS不计正式Q；关系表oos_pending不等同当前图片已认定OOS。')

add('C03','最新半队严格ABC多数规律',
    'v2建立同类B与跨类C双对照。前轮v2.1 focused-only TARGET14/7为192事件，83共同Q图，对称正差61图；不是本轮最新综合集合。',
    '综合197事件/85登记图/21楼。83共同可评图GA均值+3.511869、61图正；GS+3.397135、62图正。C−B按自身有效事件为+6.577501、76/83图正。',
    '接入综合事件并按背景→替换块→池→图片重新聚合，非更换分类或融合规则。',
    'GA/GS为185个ABC共同可评事件；C−B为187个BC共同可评事件。两者均覆盖83图但事件分母不同。',
    '在已观察的中间转折角色换入较多转折角色条件中，半队替换在多数图片上产生超过同类换人的质量变化幅度，并多数升质；同时保留非正幅度与下降。',
    '本轮独立重聚合与逐事件验证', HALF+'MAIN_CHECKED_SUMMARY.csv;'+HALF+'EVENTS_METRIC_SPECIFIC_SUPPORT.csv.gz;'+SPEED+'cross_review/HALF_TEAM_INDEPENDENT_CHECKS.json',
    FINAL_OLD, boundary='GA=|C−A|−|B−A|；GS=(|C−A|+|C−B|)/2−|B−A|。幅度与质量方向不互换。',filters='普通主目标Manual；TARGET K3；主角色方向；n=14,m=7')

add('C04','最新半队全部反例及局部门槛',
    '前轮focused-only对称非正22图，不能用于197事件的最新综合名单；部分案例只有分项或选中节点票数。',
    '最新GA非正22图、GS非正21图、C−B非正7图；数值与不可评集合并为32图，再纳入4张图均值可评而部分事件不可评的图片，共36案例。348精确团队轨迹完成局部票数、定位、连接与失败索引。',
    '从综合事件确定集合，补查/恢复真实缓存轨迹，区分数值诊断与算法过程证据。',
    '36案例不是36个互斥原因；同一图可同时有高分集中、C居中、类内波动、分项抵消或共同偏离。348轨迹状态为330完整、16无连接、2不足四节点。',
    '半队仅在某身份组由该7人实际共同支持时能独立达MV50门槛。共同背景、归组、位置与连接使部分图片不呈现额外跨类幅度。',
    '本轮新增完整反例衔接及轨迹定向重放', HALF+'ALL_36_CASE_READING_INDEX.csv;'+HALF+'ALL_36_EXCEPTION_NUMERIC_AND_MECHANISM_INDEX.csv;'+HALF+'mechanism_tables/ARM_MECHANISM_FACTS.csv;'+HALF+'mechanism_tables/VOTE_GROUPS_BY_EVENT.csv.gz',
    FINAL_OLD, boundary='“背景D达票”指保存端点归组下D成员票数达阈值，不是独立运行D-only融合。近参考几何关系不证明真实墙体语义。')

add('C05','14/7与20/7背景衔接',
    '前轮已有固定块改变背景、固定XYZ增n以及较大团队，不应把它们混成纯替换比例效应。',
    '20/7为82事件、72登记图、70共同Q图：GA+1.464950且54图正，GS+1.346836且47图正，C−B+4.524967且65图正。存在100条精确XYZ的14/7→20/7链接，覆盖72图，其中56条D嵌套。',
    '相同替换块允许连接结果，但增n同时改变背景具体成员及MV50门槛；非嵌套背景更不能只归因比例。',
    '100链接涉及81个不同14/7事件及82个20/7事件，不是100独立图片。各指标仍按共同可评支持。',
    '半队与较大背景条件均显示多数正向响应，幅度大小须结合相同XYZ链接和实际背景解释，不能用两张总均值表相减推导纯人数因果效应。',
    '本轮精确身份连接与逐链接核对', HALF+'MAIN_CHECKED_SUMMARY.csv;'+HALF+'EXACT_XYZ_14_7_TO_20_7.csv;'+SPEED+'cross_review/HALF_TEAM_INDEPENDENT_CHECKS.json',
    DEPS)

add('C06','旧同房ABC在当前标签下的实际单位',
    '前轮只验证TARGET K3有8,904条旧同房事件满足新标签下X/Y同类且Z异类，尚不能据此声称双视角作用已验证。',
    '8,904是物理D/X/Y/Z替换事件，每事件同时在两视角融合，覆盖35直接图对/14楼/全部空间层；普通可比半队子集458事件，其中404六端共同Q、21对/7楼。',
    '由适用性登记继续连接实际两视角端点、当前评分、几何、劳动与输出状态。',
    '固定旧团队条件子集；同一物理事件被多方法接受时显式标注重叠。8,904不是视角行，也不是独立房间数。',
    '当前标签能解释一部分历史严格替换的双视角响应；这批证据保持原选队身份。',
    '本轮新增实际双视角计算', ROOM+'abc/EVENT_IDENTITIES.csv.gz;'+ROOM+'abc/SUPPORT_STATUS.csv;'+ROOM+'abc/PHYSICAL_EVENT_OVERLAP.csv.gz;'+ROOM+'abc/SUMMARY.csv',
    FINAL_OLD, boundary='其余旧事件保留原分类解释，不因新标签关系不成立而被判为无效实验。')

add('C07','同房主方向10/5的复现性',
    'v2旧结构类混合大块在61/78图对、9/9楼跨类Q幅度更大；该混合n/m支持不能直接当当前主方向半队结果。',
    '当前TARGET K3角色2→3、10/5：268事件/237六端共同Q，19图对/7楼。建筑与原声明组层级等权GA+5.248292、GS+6.066600、C−B+13.749295。图对均值正向17/19、16/19、19/19；两视角均正分别14/19、13/19、18/19。',
    '按当前楼外角色方向及n/m拆分旧设计，避免混合条件均值掩盖跨视角翻转。',
    '同事件六端共同可评；图对内先聚合旧事件，原声明关系组及楼保留。源视角|C−B|>2时另一视角同向71.45%、反向8.43%。',
    '在这批固定旧团队的主方向半队条件中，质量效应在多数同房图对的两视角重复；仍有S9h-10/19一对的质量方向翻转。',
    '本轮新增方向与双视角实际效果', ROOM+'abc/SUMMARY.csv;'+ROOM+'abc/PAIR_VIEW_REPETITION.csv;'+ROOM+'abc/PAIR_METRICS.csv.gz',
    OLD_CHAIN, boundary='19/19图对均值升质不等于19/19两视角均升质；复现率不是预测模型准确率。',filters='TARGET_DSTRUCT_K3;ordinary_comparable;manual;direction_nm;2→3;n=10;m=5;B8L2')

add('C08','同房结构与劳动是否一起重复',
    '既有固定配比面板显示结构数量及劳动的构成响应比总Q相关更清楚；它与严格换人是不同设计。',
    '主方向10/5的19可评图对中，C−B有效转折两边均增4对、均零13对；劳动仅13对可评，两边均增4对、均减3对、反向6对。',
    '同一换人作用分别落到质量、结构、劳动上；相同点数可伴随定位与Q变化，劳动也不必随Q同向。',
    'Q/转折19图对与合法来源劳动13图对分别计数，不以Q分母替代时间分母。',
    '同房质量重复不要求结构数量同步增加，也不保证劳动方向重复；应将结构位置与来源劳动作为独立结果。',
    '本轮新增分指标双视角对照', ROOM+'abc/PAIR_VIEW_REPETITION.csv;'+ROOM+'abc/CONDITION_METRICS.csv.gz;'+ROOM+'abc/Q_COMPONENT_CONDITIONS.csv.gz',
    FINAL_OLD, boundary='转折数不变不等于两份共识相同；结构正确性须看参考对应与位置。')

add('C09','同房半队容量与新增实验必要性',
    '此前新分类同房ABC是否必须另选队尚未明确；全局人员数不能代表同房共同原答容量。',
    '128个普通可比直接图对中，TARGET K3主方向14/7仅2对合法，2对已全部执行：10事件、6六端共同Q，GA−2.240602、GS+0.333457、C−B+11.364133。10/5合法32对，旧设计已覆盖19对，另13对有容量。',
    '逐对实际共同合格原答、楼外标签及互斥D/X/Y/Z限制决定可行性；新14/7选队不能扩增图对覆盖。',
    '14/7只有2对/2楼，10事件的Z固定为W102/W109/W112/W115/W122/W126/W130，各人均使用10次；10/5现有19对/7楼。容量未执行不等于文件缺失。',
    '现有证据已能研究同房半队主方向；本轮无需新增14/7。若以后研究新分类重新选队的代表性，可将10/5扩至全部32个可行图对，另存新设计身份。',
    '本轮实际容量核验与不新增设计决定', ROOM+'abc/HALF_CAPACITY_SUMMARY.csv;'+ROOM+'abc/HALF_CAPACITY_ALL_DIRECTIONS.csv.gz;'+ROOM+'abc/MAIN_HALF_MEMBER_FREQUENCY.csv;'+ROOM+'abc/SUMMARY.csv',
    DEPS, boundary='14/7的2对不能推广为普通图片14/7失效；其负GA与正C−B也回答不同问题。')

add('C10','快慢人员×难度：原63对结论',
    'v2固定同类、近楼外历史Q、同来源且简单/困难均有支持的63对快慢人员中，42对困难图增加慢者转折优势，44对增加短边优势；63对共享35人。',
    '当前资格及评分下原63对仍为42/63转折、44/63短边优势增大；平均硬减易差分别+0.335362和+0.349919。Q差由旧−2.454143变为−2.496012，升质方向26/63。',
    '固定原人员对和实际图片，原答表达不变；更新正式Q及指标支持。',
    '新来源普通Manual、至少2简单和2困难图的同一有向人员对；图先在楼内平均、楼等权到每人对。人对不是独立人员。',
    '原支持上的多数表达规律在当前v2.1仍成立，但更多表达不自动带来更高参考质量。',
    '本轮原支持桥接与匹配研究恢复', SPEED+'PAPER_FIXED_PEOPLE_BRIDGE.csv;'+SPEED+'V2_FROZEN_SAME_PEOPLE_SUMMARY.csv;'+SPEED+'V21_FIXED_V2_SAME_PEOPLE_SUMMARY.csv',
    SPEED+'inputs/V2_README.md', boundary='历史快慢标签不保证每张目标图都按该速度排序。')

add('C11','快慢人员×难度：当前扩展与共同52对',
    '一般画像或困难分层不能替代同类近Q快慢匹配；不能把原63对直接当当前TARGET匹配支持。',
    '当前TARGET K3完整匹配105对/35人：硬减易转折差+0.019800，55/105正；短边+0.010263，59/105正；Q−0.163154，48/105正。限于原v2细类精确人对×图片交集的52对：转折+0.248512、37/52正；短边+0.289181、39/52正；Q−2.530654、22/52正。',
    '当前标签、楼外Q匹配及人员/图片支持共同改变样本；同支持交集保留原条件规律，扩展总体平均更小。',
    '六类方法共52,851方法×有向人对×图片行，实际不同有向人对×图片14,528个；不同方法重复选中同一原答对不算独立证据。',
    '快慢结构响应具有人员与图片条件性：原支持及其当前匹配交集保留多数规律，当前扩展人群平均效应减弱，不能仅归因分类更换。',
    '本轮当前匹配、共同支持及重叠分析', SPEED+'PAPER_FIXED_PEOPLE_BRIDGE.csv;'+SPEED+'CURRENT_SAME_PEOPLE_SUMMARY.csv;'+SPEED+'CURRENT_ON_V2_FINE_PAIR_SAME_PEOPLE_SUMMARY.csv;'+SPEED+'MATCH_METHOD_OVERLAP.csv.gz',
    SPEED+'inputs/V2_README.md', boundary='匹配使用楼外Q差≤3、历史劳动比≥1.5、同来源/同计时语义。没有本图Q选人或新融合。')

add('C12','快慢难度的建筑敏感性与实际机制',
    'v2已提醒表达更多不等于补画正确；同人跨难度仍可能受建筑和具体图影响。',
    'TARGET当前同人同楼814个人对×楼上下文/15楼：转折硬减易上下文等权+0.050774，建筑等权−0.018842且8/15楼正；Q分别−0.734586与+0.506083且7/15楼正。历史慢者简单/困难记录劳动约为快者2.34/2.41倍。',
    '共享人员、不同楼支持与指标权重使均值和多数可不同；定位、方向、高度、遗漏与外扩互相抵消。',
    '同楼至少1简单与1困难；主105对的≥2每难度分析另保留。劳动为合法记录活动量。',
    '劳动差异较稳定，结构与质量响应受具体人员及建筑影响；报告两种权重和删人/删楼结果，不将平均接近零写成没有任何作用。',
    '本轮同楼、敏感性与3个原答完整案例', SPEED+'SAME_PEOPLE_SAME_BUILDING_BUILDING_SUMMARY.csv;'+SPEED+'PAPER_MEMBER_BUILDING_SENSITIVITY.csv;'+SPEED+'PAPER_TARGET_K3_DIFFICULTY.csv;'+SPEED+'CASE_INDEX.csv;'+SPEED+'CASES_EXACT_PAIRS.csv',
    SPEED+'inputs/V2_README.md', boundary='VFua-04多转折而Q降，pa4-10多转折且Q升但仍低，VFua-10转折不变而分项/劳动变化。不是因果难度操纵。')

add('C13','同房源均值预测：原支持桥接',
    'v2 123直接图对/64图/12楼：源均值MAE5.080850，对比楼外图片均值9.303137；9/12楼改善。',
    '当前质量在同旧记录支持上源均值MAE5.081438，对比楼外9.305423；同为123对/64图/12楼，原规律近似不变。',
    '相同实际原答与直接关系，仅更新质量；参考更新的影响极小。',
    'legacy_combined保留旧研究范围；原关系中4对oos_pending单列，不改为已确认OOS，也不删除原记录。',
    '同房公共质量信息在原支持下可重复，用当前参考重计后仍优于楼外公共均值。',
    '本轮源→目标实际预测重建', ROOM+'prediction/DIRECT_MEAN_SUMMARY_BY_SCOPE.csv;'+ROOM+'prediction/V2_V21_DIRECT_PAIR_SUPPORT_BRIDGE.csv;'+ROOM+'prediction/RELATION_PENDING_EDGES.csv',
    OLD_USES, filters='B8L2;legacy_combined;v2_frozen与v21_on_v2_records;source_mean/external_image_mean')

add('C14','同房源均值预测：当前全部普通支持',
    '旧无关系待定分层为119对/59图/11楼，旧报告曾与待定关系合并。',
    '当前无待定主层128对/65图/13楼：源均值MAE6.463518，楼外基线9.496483；39/65图、8/13楼改善。全部旧式范围132对/70图/14楼单列。',
    '新正式质量支持扩大图片/建筑；同时明确关系待定层，不能将与旧总MAE之差解释为模型退步。',
    '256个源→目标方向，先目标内平均来源，再楼内目标平均，建筑等权；预测对象为目标图实际合法人员均Q。',
    '已有同房可评分历史能改善多数目标与建筑的公共质量估计，仍保留5栋反向建筑及具体图误差。',
    '本轮扩展支持及逐图/楼验证', ROOM+'prediction/DIRECT_MEAN_SUMMARY_BY_SCOPE.csv;'+ROOM+'prediction/DIRECT_MEAN_IMAGE_ERRORS.csv;'+ROOM+'prediction/v21_all/DIRECT_MEAN_BUILDINGS_ordinary_no_relation_oos_pending.csv',
    OLD_USES, boundary='源参考Q已知是前提，不是无GT在线预测。')

add('C15','同房公共差异的共同人和结构匹配',
    'v2同难度及结构匹配、固定三图共同人员后，同房仍较未知关系接近。',
    '当前无待定主层固定三图共同人员，并匹配正式难度、参考有效转折数及隐藏/不可见转折数H：同房Q差5.051395、未知关系8.930673，9楼中8楼差距正向。',
    '当前合法原答与Q更新后复用原背景对照算法；不以同楼或传递关系新增同房事实。',
    '215源方向、113直接同房图对、9楼；背景是未知关系，非确认异房。',
    '同房公共质量接近不完全由共同人员和这组结构条件解释，但匹配仍不足以隔离布局的因果贡献。',
    '本轮匹配对照恢复', ROOM+'prediction/MATCHED_UNKNOWN_SUMMARY_BY_SCOPE.csv;'+ROOM+'prediction/v21_all/MATCHED_UNKNOWN_CONTROLS.csv.gz',
    OLD_USES, boundary='H是隐藏转折数，不是顶部高度；差值不是预测MAE，也不是解释方差。',filters='B8L2;v21_all;ordinary_no_relation_oos_pending;strict_class_turns_hidden;triple')

add('C16','个人绝对、同行相对及楼外残差相似性',
    'v2 2,581个人图对/57人：绝对Q相关0.405、相对同行0.239、扣稳定楼外水平0.031；105/123对排序正，42/57人相对好坏重复率超过半数。',
    '当前无待定主层2,600个人图对/57人：相关依次0.400762、0.198644、0.012878；105/128直接图对排序正，40/57人相对好坏重复率超过半数。残差合法支持2,599行。',
    '公共任务水平、稳定个人差异和剩余房间响应分层描述；扩展范围及待定层分开。',
    '128图对/65图/13楼；对称建筑→图对→共同人员加权；同行均值排除本人，历史排除目标建筑。',
    '多数图对和多数人员保留跨视角重复倾向；扣除稳定历史后额外关联很小，不能因此否定原始个人相似性。',
    '本轮个人残差与多数口径恢复', ROOM+'prediction/PERSONAL_SIMILARITY_BY_SCOPE.csv;'+ROOM+'prediction/v21_all/DIRECT_PERSON_VALUES.csv.gz;'+ROOM+'prediction/v21_all/PERSON_REPETITION_B8L2.csv',
    OLD_USES, boundary='相关下降不是因果方差拆分，也不是各因素解释百分比。')

add('C17','个人预测相对公共均值及个人历史的增量',
    'v2强基线P+θ在全直接支持MAE12.579优于本人源Q15.808；多人历史加入半份本人残差未改善总体MAE。',
    '当前同支持个人预测：P+θ MAE13.385294，公共P14.755321，楼外个人绝对历史15.644760，本人单源16.734612；加入半份本人剩余项为14.193408，变差。',
    '同一个人目标原答上公平比较当前公共信息、稳定相对历史和本人单源信息；保留原固定预测规则。',
    '无待定主层1,793目标原答/56人/65图/13楼，5,198方向预测行；不同源预测在目标原答层聚合。',
    '公共源水平与稳定个人相对历史的组合增加实用预测信息；固定半份本人残差在此面板未提高MAE。',
    '本轮同支持预测误差重建', ROOM+'prediction/PERSON_PREDICTION_SUMMARY_BY_SCOPE.csv;'+ROOM+'prediction/v21_all/PERSON_PREDICTION_VALUES.csv.gz;'+ROOM+'prediction/v21_all/PERSON_PREDICTION_TARGET_WORKERS.csv.gz',
    OLD_USES, boundary='个人预测MAE不能与图均值MAE相减；未检验所有复杂模型，不能声称个人信息永无价值。',filters='B8L2;v21_all;ordinary_no_relation_oos_pending;single_direct;single')

add('C18','多份已有同房历史的增量',
    'v2 9组/44图/7楼：公共均值单源MAE4.804→最低严格多数4.110→最大历史4.062；P+θ同支持11.360→11.170→11.145。',
    '当前无待定固定历史面板41图/6楼：公共均值5.163372→4.358475→4.302483；P+θ在1,284目标原答/55人上11.707244→11.504920→11.474346。最大历史加半本人残差11.535262，排序相关0.394432→0.414479。',
    '保留原历史面板、合法直接关系与全部实际预算组合，当前Q与关系分层更新。',
    '实际人员池与全视角共同人员池单列；后者21图/5楼公共均值4.524744→3.566396→3.551574。',
    '已有历史从单源增加到严格多数有可见收益，多数后增量较小；排序改善与MAE改善须分别陈述。',
    '本轮多历史完整用途恢复', ROOM+'prediction/MEAN_HISTORY_SUMMARY_BY_SCOPE.csv;'+ROOM+'prediction/PERSON_PREDICTION_SUMMARY_BY_SCOPE.csv;'+ROOM+'prediction/HISTORY_PANEL_DIRECT_EDGE_VALIDATION.csv.gz',
    OLD_USES, boundary='264直接方向及289,875历史面板行逐条验证无传递新增关系；固定41图性能不推广到全部65图。')

add('C18V','同房共同人员×视角的平方和分解',
    '本轮对v2冻结数据统一回算：无关系待定共同人员面板为14声明组/39图/11楼/53人/634矩阵格，人员、视角、剩余交互平方和占比0.551606/0.061167/0.387226；不是冒称旧报告已发布该分解。',
    '当前同旧原答下比例几乎不变。扩展当前普通无待定面板为15声明组/40图/13楼/52人/685原答及矩阵格，比例0.526451/0.082672/0.390878；交互RMS为10.027617 Q分，图均值范围7.817768。',
    '同旧原答结果几乎相同，主要变化来自支持扩展；按同组全视角共同人员构成矩阵，描述人员稳定差异、公共视角差异与剩余交互。',
    '每声明组平方和严格加和为1，再楼内组等权、楼等权；组内每两视角均核对既有直接关系。不是把全部685格视为独立样本。',
    '在当前共同人员面板中，稳定个人差异占较大比例，仍存在可观的人员×视角剩余波动；这为个人相似性与单图不确定性并存提供描述性证据。',
    '本轮新增人员×视角共同矩阵与分解', ROOM+'prediction/DECLARATION_VARIATION_SUMMARY.csv;'+ROOM+'prediction/DECLARATION_VARIATION_PARTITION.csv;'+ROOM+'prediction/DECLARATION_VARIATION_SUPPORT.csv;'+ROOM+'prediction/DECLARATION_COMMON_MATRIX.csv.gz',
    ROOM+'prediction/DECLARATION_VARIATION_SUMMARY.csv', boundary='这里不是类别配比解释率，不是因果贡献，也不是跨视角相关或预测准确率；与有限团队构成方差分开。',filters='B8L2;v21_all;ordinary_no_relation_oos_pending')

add('C19','已有历史下的具体Q选队',
    'v2 n5全来源同候选支持楼外Q队92.957617，本人源Q队89.279813。',
    '当前原层楼外Q93.050060对单源Q89.275422；无待定主层92.343484对88.085470，43/59图、10/11楼楼外Q更高。',
    '当前楼外历史重建、原候选池重选；同时保留旧人员仅更新评分的桥接版本。',
    '原层242源→目标情境/64图/12楼；主层234情境/59图/11楼；n=5固定，候选数>n。',
    '在已有稳定楼外历史且原共同候选可用时，楼外Q是有效具体质量选队基线，单源个人高Q不宜替代它。',
    '本轮恢复设计并补算精确缺队', SEL+'selection/MAIN_N5_HEADLINES.csv;'+SEL+'selection/MAIN_N5_DIRECTION_COUNTS.csv;'+SEL+'selection/POLICY_EVENT_RESULTS.csv.gz;'+SEL+'validation/NUMERIC_RECONSTRUCTION_CHECKS.json',
    OLD_USES, boundary='目标Q不参与选人；随机不同端点有失败时边际均值差与共同可评配对差不同。')

add('C20','Q/T选队的记录劳动与坏尾',
    'v2原时间池Q/T相对楼外Q劳动比0.787316，Q93.470609对93.691115，11/11楼省劳动而5/11楼升质。',
    '当前原层劳动比0.802734、净Q+0.112312，31/62图升23降8同，11/11楼省劳动；主层劳动比0.826679、净Q+0.124134，29/57图升20降8同，48图省1图增8图同，9/10楼省1楼同。主层>5分损失加权比例8.6481%。',
    '当前Q历史改变重选成员。旧Q队当前评分93.691195→当前重选93.362740；Q/T93.469330→93.475052。净Q由负转正主要因Q基线改变。',
    '合法新来源时间主层232情境/57图/10楼，原层240/62/11；劳动比按配对对数比逐层平均后指数化。',
    'Q/T在多数图片和建筑减少记录劳动，平均Q接近Q基线，但质量损失尾部仍须报告；历史均Q约束不保证本图保质。',
    '本轮当前历史重选、端点实算及旧队桥接', SEL+'selection/MAIN_N5_HEADLINES.csv;'+SEL+'selection/MAIN_N5_DIRECTION_COUNTS.csv;'+SEL+'selection/POLICY_SUMMARY.csv;'+SEL+'V2_TO_V21_CLOSEOUT.csv',
    OLD_USES, boundary='原层31/62恰为半数，不能写多数图片升质；劳动不是并行耗时或工资。')

add('C21','选队人数及原精确端点补齐',
    'v2算法已研究n=3、4、5、6、7、9、13；归档精简遗漏部分设计/团队库，但规则与固定输入可恢复。',
    '本轮恢复71,608上下文事件行/400汇总条件；所需25,826唯一端点/99池，其中310精确复用、25,516实际计算。原400汇总单元重建误差<3e−14。Q/T的Q效应随n改变，劳动节约方向较稳定。',
    '查缓存后仅补不存在的精确团队，非重跑256自然路径；用旧数值回算验证恢复原算法身份。',
    '上下文、版本、人数、来源分开；n5为v2原主条件，未按本轮收益选取。',
    '具体选队的质量与劳动取舍依赖团队规模，不能将n5的小均值优势推广到所有人数。',
    '本轮必要精确团队实际计算与复现验证', SEL+'endpoints/FINAL_ENDPOINT_ACCOUNTING.json;'+SEL+'validation/NUMERIC_RECONSTRUCTION_CHECKS.json;'+SEL+'selection/RELATION_LAYER_SUMMARY.csv',
    OLD_USES, boundary='原始遗漏团队经可核验重建恢复，不冒称找回遗失原文件；类别未重新拟合。')

add('C22','已有同房历史指导停止人数',
    'v2 6完整组/24图：源within2+几何补收Q87.763546对fixed7 86.958125，人数7.357对7.029，低尾仍有代价。',
    '当前原层Q87.763501对86.958004、16/24图提高；无待定主层5组/21图Q86.054254对85.189302、13/21图提高。主层P10 78.565对78.984，损失>5比例15.76%对17.19%。',
    '仅4池参考变化影响5,100旧前缀；规则、顺序、候选及停止选择保持，实际重评分后近似不变。',
    '原124,924前缀复用119,824行；质量5/6组与合法劳动3/4组分开。来源完整曲线及其峰值已存在是前提。',
    '已有同房源历史可在多数当前目标条件下改善停止质量，但低尾和记录劳动仍可能变差，不能给出统一最优人数。',
    '本轮受影响前缀补评分及冻结规则复算', SEL+'stopping/MAIN_RULE_HEADLINES.csv;'+SEL+'stopping/SOURCE_VS_FIXED7_IMAGE_EFFECTS.csv;'+SEL+'stopping/REPLAY_NODE_PATCHES.csv.gz',
    OLD_USES, boundary='目标只按几何完整性补收，不看目标Q；8张Q下降图完整保留。')

add('C23','更多源历史与目标节点稳定停止',
    'v2源历史与纯目标几何稳定是不同规则；点数稳定不保证定位或质量充分。',
    '主层5组/21图单源、最少多数、最大历史Q85.248→86.025→86.054，实际人数6.589→7.173→7.181。目标连续三次完整且点数相同规则Q83.732、人数5.848、P10 76.214，损失>5比例22.90%。',
    '复用原冻结停止设计和实际m历史预算，分别分析更多历史与更早停的代价。',
    '停止中的m是源视角数，不是换人实验的替换人数；规则各有质量和时间支持。',
    '多数源历史改善该固定面板的人数建议，多数后增量有限；点数短期稳定可以减少劳动但不是充分质量证据。',
    '本轮完整历史预算与规则对照复算', SEL+'stopping/RELATION_LAYER_STOPPING_SUMMARY.csv;'+SEL+'stopping/MAIN_RULE_HEADLINES.csv',
    OLD_USES, boundary='未调参选择最佳规则，未将不同支持的n曲线混接。')

add('C24','已有历史劳动与从零获取成本',
    'v2合法4组/14图源规则目标劳动比fixed7为1.235131；从零完整项目比2.394848，4/4组未在实际剩余视角内回本。',
    '本轮逐项复算后原4组结果相同；无待定3组/11图目标劳动比1.255631，从零项目比fixed7为2.115261、比满共同池0.871，3/3未回本。',
    '实际源原答、计时及所选人数未变；当前Q更新不能改变记录劳动。新主层移出关系待定G124。',
    '历史原答每源只计一次，256重放共享原答不乘历史成本；参考构建与评审未记录。',
    '在已有历史条件下可复用同房经验，但为当前少数剩余目标从零建立完整源历史，尚未相对fixed7摊平记录劳动。',
    '本轮完整成本复算，不沿用旧声明代替计算', SEL+'stopping/MAIN_COLD_COST_HEADLINES.csv;'+SEL+'stopping/RELATION_LAYER_ACQUISITION_SUMMARY.csv;'+SEL+'stopping/source_acquisition_project_cost.csv.gz',
    OLD_USES, boundary='相对满池省劳动与相对fixed7未回本可同时成立；未记录人工成本保持未知。')

add('C25','跨楼Q/T历史的最低采集成本',
    'v2具有现成楼外历史面板，但未定义最少采集计划及跨任务长期摊销规则。',
    '当前已有历史用途完成，原9,217历史记录形成3,997人员×留出楼×条件/来源单元。没有把8图/3楼支持门槛伪装成最小采集算法或报告虚构回本点。',
    '历史支持规则只能判断可用性，不能自动确定最佳采集和服务复用计划。',
    '同房完整源历史冷成本已完成；跨楼历史最低成本是另一个新设计问题。',
    '本研究支持已有历史的选队用途；从零最经济地取得楼外Q/T资料需要明确采集预算、候选和长期复用范围后另行评价。',
    '保留明确新设计边界', SEL+'history/HISTORY_CONTRACT.json;'+SEL+'REPORT_ZH.md',
    OLD_USES, boundary='不阻塞本轮已有历史下的效果结论。')

add('C26','完整有限配比与同配比内部差异',
    'v2已完成有限12选6配比；并非全人员池、所有n/m和全部组合的穷举。',
    'v2.1既有45方法全指标配比、Manual/Semi及其它合法目标已接齐。Manual45共同域182面板/38图/22楼；98是数据域×配置数。新分类固定旧同房面板的构成方差分解亦已保存。',
    '已有材料足够，分类标签改变只触发对应分组，不触发相同团队融合全重算。',
    '配比格、团队端点、面板与图楼分别统计；细分类样本内构成间占比增加不单独证明更有用。',
    '类别配比组织部分团队差异，同配比内具体成员仍造成显著不确定性；方差比例是有限面板描述，不是预测准确率。',
    '保留已核成果，本轮不重复计算', DEPS+';'+FINAL_OLD, OLD_CHAIN,
    'research/data/releases/v2.1/simulated_population_evidence/composition/SOURCE_INDEX.csv;research/workers/personnel_v21_reselection_20261029/additional_delivery/packages/03B_core/composition/primary_mixture_results/ALL45_ALL_METRICS_BOTH_SUPPORTS.csv;research/data/releases/v2.1/final_classification_downstream/SAME_ROOM_SUMMARY.csv',
    boundary='当前分类仅为工作对象；不将不同方法不等容量支持的均值排名。')

add('C27','自然人数与旧进入策略',
    'v2自然256和旧V3角色策略32形成完整人数、低尾、失败与顺序研究；两者不等于Q/QT选队或停止用途。',
    '现有v2.1自然路径与旧V3策略已更新，继续保留；本轮无新自然随机顺序、无256条全库重跑。',
    '自然原答到达顺序、精确团队和同参考几何不因标签名称而变化；本轮只补具体用途的缺队及受参考影响前缀。',
    '不同容量人数段保持固定共同图集，普通/门洞/OOS及来源各有独立状态和分母。',
    '人数、进入顺序和类别构成共同影响共识分布，但已有自然路径不能替代当前类别约束策略的评价。',
    '保留已核成果，避免重复实验', DEPS+';'+SEL+'endpoints/FINAL_ENDPOINT_ACCOUNTING.json', OLD_CHAIN,
    'research/data/releases/v2.1/README.md;research/data/releases/v2.1/current_policy_results/README.md',
    boundary='旧V3策略不能改名TARGET/OPPJOINT大池策略；并行门洞工作不计本轮验收。')

add('C28','直接AC、整类替换与完整类别并集',
    '前轮v2.1已实际完成直接AC、每图整类替换和纯类/两类/全类原答合并融合。无需因本轮全链路补齐再重跑。',
    '保留已独立核验：TARGET20/7为85图中78图升Q、均值+4.576；固定20人整目标类换入m=1—8，185图中155升、+3.615。OPPJOINT20/10为42升40降、均值+0.297、绝对+3.282；RAW3 23/12为4图/1楼全降。',
    '现有结果已经回答不同类型人群合并和等量调整的问题，本轮新增的是其下游重复性及用途。',
    '完整类别组合人数可变，AC无B；不同方法大量共享原答及团队，不将事件数相加当独立样本。',
    '构成变化可带来升质、降质及明显双向波动；人数更多、类别更多不保证共识更接近参考。',
    '保留现有实际结果及核验范围', 'source/research/workers/personnel_ac_review_20261030/README.md;source/research/workers/personnel_ac_v21_20261030/README.md',
    OLD_CHAIN,
    'research/workers/personnel_ac_review_20261030/MAIN_EFFECTS_RECOMPUTED.csv;research/workers/personnel_ac_review_20261030/MAIN_EFFECTS_BY_IMAGE.csv;research/workers/personnel_ac_review_20261030/COALITION_COVERAGE.csv;research/workers/personnel_ac_review_20261030/SEVEN_COALITIONS_VERIFIED.csv',
    boundary='AC不能单独证明跨类幅度大于同类；完整类别并集与固定n配比也分开。')

add('C29','同配比背景成员作用',
    '前轮已核验固定替换块和类别人数而改变背景具体成员的作用。',
    'TARGET20/7保持X/Z、n/m及D类别人数，仅换背景具体人：85图平均效果差−0.388，平均绝对效果差4.564。',
    '正负抵消使均值接近零，实际背景影响仍大；不是类别数量足以决定输出。',
    '680背景比较，逐图聚合85图；与普通14/7→20/7改变背景数量/门槛的设计不同。',
    '类别配比提供可解释组织，但同配比内具体成员及共同背景仍是模拟标注不确定性的必要维度。',
    '保留已核成果并与本轮身份链连接', 'source/research/workers/personnel_ac_review_20261030/README.md;'+HALF+'EXACT_XYZ_14_7_TO_20_7.csv',
    OLD_CHAIN,
    'research/workers/personnel_ac_review_20261030/BACKGROUND_SAME_COMPOSITION_RECOMPUTED.csv',
    boundary='未将本轮核对来源报告等同重新计算全部AC原生几何。')

add('C30','新分类大池策略与新选队同房ABC',
    '既有材料没有把旧V3大池进入顺序当成新TARGET/OPPJOINT策略；前轮列为潜在新设计。',
    '本轮解释链和已有历史用途已闭合，无必须由新大池策略或新14/7同房选队填补的结论缺口。10/5另13对有容量，若研究当前分类重新选队的广域代表性可作为未来扩展。',
    '已完成当前类别旧队条件效果、半队容量、Q/QT选队、预测、停止和成本后，能明确剩余问题是新设计而非旧文件缺交付。',
    '同房主向14/7全部2合法图对已用；10/5当前19/32。大池进入须先定义相对连续Q/T新增什么信息，再冻结角色顺序、未知组规则及团队键。',
    '现有证据足以研究观察到的人群标注不确定性；新策略评价用于推广或决策增益，须保持独立研究身份。',
    '本轮结论：暂不新增，不阻塞交付', ROOM+'abc/HALF_CAPACITY_SUMMARY.csv;'+SEL+'V2_TO_V21_CLOSEOUT.csv;'+DEPS,
    DEPS, boundary='未来先查精确端点缓存再只补缺队，不因最终类别决定而全面重跑原生融合。')

add('C31','人工语义判断与已算数值的界限',
    'v2及前轮已指出局部结构、镜面、门洞视点和参考目标语义不能单靠Q判定。',
    '本轮半队36图及快慢3案例保留原图/完整原答/参考/融合或原答几何和票账。VFua-04的W125节点5—8需人工辨别镜面、柜体与实际墙段；Q/T uNb-01/43坏尾需对照真实墙体。',
    '完整数值链能定位差异，不能凭近参考距离或投票一致性判真实几何语义。',
    '具体问题可直接从案例索引打开；现有参考、资格与空间归属保持，不因机制解释自行改规则。',
    '多数规律与不确定局部语义并存，人工判断限定到具体结构，不将个别未决语义扩写为整套方法未验证。',
    '本轮案例可视化与人工问题索引', HALF+'ALL_36_CASE_READING_INDEX.csv;'+SPEED+'CASE_INDEX.csv;'+SPEED+'CASES_VIEWER.html;'+SEL+'selection/REPRESENTATIVE_CASE_INDEX.csv',
    OLD_USES, boundary='pa4-11当前四角目标已获确认，不重列为缺失空间路由。')


gaps = []


def gap(id, topic, kind, state, question, done, next_step, blocks, sources, reason):
    gaps.append(dict(缺口ID=id,模块=topic,缺口类别=kind,状态=state,具体问题=question,
                     已有证据与本轮工作=done,下一步或判定=next_step,是否阻塞本轮结论=blocks,
                     证据路径_交付根目录相对路径=sources,判定理由=reason,冻结仓库提交=SHA))


gap('G01','半队全部反例','必须补算','已关闭','综合197事件的21张对称非正图及全部不可评是否已与机制衔接？',
    '完成逐事件/图/楼复算，36图完整索引和348真实端点轨迹；GA/GS185与BC187分母独立验证。',
    '使用最新ALL_36索引；旧focused-only名单保留历史身份。','否',HALF+'ALL_36_CASE_READING_INDEX.csv;'+SPEED+'cross_review/HALF_TEAM_INDEPENDENT_CHECKS.json',
    '原缺口是最新事件衔接和真实轨迹，本轮已完成；语义人工问题另列。')
gap('G02','旧同房ABC实际双视角','必须补算','已关闭','8,904适用事件的实际效果、复现性及分母是什么？',
    '完成物理事件身份、角色/n/m/scope、Q分项/几何/劳动/状态及双视角正反向。',
    '按原设计条件子集引用，不改称新分类重选队。','否',ROOM+'abc/SUMMARY.csv;'+ROOM+'abc/PAIR_VIEW_REPETITION.csv;'+ROOM+'abc/FINAL_JOIN_CHECKS.json',
    '适用条数已转成实际结果；不用另建全套团队才能采用。')
gap('G03','同类近Q快慢×难度','必须补算','已关闭','原63对、当前匹配与共同支持是否分开？',
    '完成原63/current105/交集52桥接、同人同楼、删人删楼、31指标及完整原答案例。',
    '报告表达与正确性、历史速度与单图劳动的区别。','否',SPEED+'PAPER_FIXED_PEOPLE_BRIDGE.csv;'+SPEED+'README.md;'+SPEED+'VALIDATION.json',
    '已有原答和当前历史/标签足够，本轮新融合0。')
gap('G04','同房均值/个人预测/多历史','必须补算','已关闭','是否只是相关表存在而无实际预测？',
    '源→目标预测、楼外基线、个人残差、同支持个人MAE、多历史全部预算、匹配对照及人员×视角平方和分解均已实际计算。',
    '原支持、扩展支持及关系待定层分开引用。','否',ROOM+'prediction/DIRECT_MEAN_SUMMARY_BY_SCOPE.csv;'+ROOM+'prediction/PERSON_PREDICTION_SUMMARY_BY_SCOPE.csv;'+ROOM+'prediction/RELATION_SCOPE_CHECKS.json',
    '预测误差、相关、配比方差各自解释；直接边验证不增加传递同房关系。')
gap('G05','Q/QT选队、停止与冷成本','必须补算','已关闭','精确原设计团队缺缓存和受影响前缀是否补齐？',
    '25,516缺少精确端点实际算完，310精确复用；5,100受影响旧前缀补评分；原算法数值重建通过，当前新旧历史版本分开。',
    '使用当前0.802734/0.826679劳动比与当前实际成本，不将旧0.787改标签。','否',SEL+'endpoints/FINAL_ENDPOINT_ACCOUNTING.json;'+SEL+'validation/NUMERIC_RECONSTRUCTION_CHECKS.json;'+SEL+'V2_TO_V21_CLOSEOUT.csv',
    '此项已完成实际计算，不再列为待找原ZIP或团队库。')
gap('G06','本轮结果的既有目录和网页接续','已有数据待整理','更新包已完成，Windows应用待实际环境执行','新模块是否进入既有依赖登记、目录和可下载交付？',
    '9目标路径更新包已完成，保留7旧文件历史内容并增加2入口；DEPENDENCIES追加8当前验收行。冻结原字节SHA防覆盖、git apply --check及实际应用字节核对通过。',
    '合并最终交付后按repository_update说明在实际Windows仓库读取其AGENTS并应用；本会话未写D盘或远端。','否，实际环境应用属于交接状态','repository_update/README_ZH.md;repository_update/UPDATE_RECEIPT.json;'+SEL+'FILE_READABILITY_RECEIPT.json;'+SPEED+'FILES_READABILITY_AND_HTML_CHECKS.json',
    '不是缺数据或科学补算。程序读回、压缩包内部读取和真实浏览器是不同验收，不能互相替代。')
gap('G07','新分类大池进入策略','需要新设计','可选后续，本轮不执行','最终类别约束的进入顺序比自然顺序或连续Q/T增加什么？',
    '已有自然256、旧V3策略32、小池OPP以及当前Q/QT具体选队，现有全链路结论不依赖新大池策略。',
    '先定义新增研究问题和公平历史/容量基线，冻结楼外角色与未知类顺序，再查精确团队缓存补缺。','否',DEPS+';'+SEL+'REPORT_ZH.md',
    '它不是一个遗失旧结果文件，不能将旧V3轨迹改名或因分类更换全量重跑。')
gap('G08','新选队同房14/7严格ABC','需要新设计','本轮无需新增','新设计能否扩大主方向半队14/7的同房图对支持？',
    '128普通直接图对中仅2对容量合法，2对已全部执行；其它原答容量不允许。',
    '保持现有2对实际结果及容量限制；无需另建同范围14/7以求更大覆盖。','否',ROOM+'abc/HALF_CAPACITY_SUMMARY.csv;'+ROOM+'abc/SUMMARY.csv',
    '容量限制是证据边界，不是缺文件或应重复运行的问题。')
gap('G09','新选队同房10/5严格ABC','需要新设计','可选未来扩展','当前标签重新选队能否在旧设计未覆盖图对复现？',
    '主方向10/5有32对容量合法，旧事件已覆盖19对/7楼；另13对有容量未进入旧设计。12/6亦有2对未执行，精确名单均已保存。',
    '若需要超出旧选队条件身份的代表性，可新冻结全32对10/5抽样、保留成员/背景重复，并查询缓存。','否',ROOM+'abc/HALF_CAPACITY_SUMMARY.csv;'+ROOM+'abc/HALF_CAPACITY_ALL_DIRECTIONS.csv.gz;'+ROOM+'abc/CAPACITY_SUFFICIENT_UNEXECUTED_MAIN_HALF_PAIRS.csv',
    '未来实验回答新分类重新选队的推广问题，不能冒称补齐丢失旧ABC文件。')
gap('G10','跨楼历史最低采集与长期摊销','需要新设计','可选后续','从零最少收多少跨楼历史，服务哪些后续房间才回本？',
    '已有历史Q/QT用途完成；同房完整历史实际冷成本已重算。8图/3楼是支持门槛而非最优采集方案。',
    '先定义真实采集日程、候选覆盖、参考劳动及复用范围，再比较同预算方案。','否',SEL+'history/HISTORY_CONTRACT.json;'+SEL+'stopping/MAIN_COLD_COST_HEADLINES.csv;'+SEL+'REPORT_ZH.md',
    '未定义成本合同不能由现有面板自动推出最小回本点。')
gap('G11','快慢原答的局部空间语义','需要人工判断','具体问题保留','VFua-04 W125节点5—8对应实际墙段、柜体还是镜面区域？',
    '原图、全原答点、正式参考、BEV和全部分项在自包含案例页，转折增加而Q下降已数值确认。',
    '查看VFuaQ6m2Qom-04，ERP约x=286—349/1024区域及W125节点5—8；判断实际边界语义。','不影响数值与多数规律，仅限制该局部语义解释',SPEED+'CASES_VIEWER.html;'+SPEED+'CASES_EXACT_PAIRS.csv;'+SPEED+'CASE_INDEX.csv',
    '现有数据定位差异，真实表面语义需人看；不自动改正式参考。')
gap('G12','半队机制中真实结构语义','需要人工判断','按逐图问题索引保留','近参考组、镜面/遮挡或候选环所表示的真实结构是否正确？',
    '全部反例原图/原答/参考/输出和投票/连接过程已连接，数值解释与机制证据分开。',
    '逐图按ALL_36阅读索引的具体结构问题确认；若无语义歧义则直接使用已证实算法原因。','仅限制对应局部原因，不阻塞半队总体结论',HALF+'ALL_36_CASE_READING_INDEX.csv;'+HALF+'ALL_36_CASES_ZH.md;'+HALF+'mechanism_tables/REFERENCE_NEAR_GROUP_DIAGNOSTIC.csv',
    '不凭总Q、被选节点票数或近参考距离推导真实墙体。')
gap('G13','Q/T坏尾的真实墙体解释','需要人工判断','具体案例保留','uNb-01/43大降质是否来自特定墙段定位/遗漏，哪些具体成员造成？',
    '两队完整几何、实际原答、正式参考与分项已保存；两例完整共识且ΔQ约−28.95/−28.77，非融合失败。',
    '查看源uNb-40→目标uNb-01/43的案例，必要时再按具体未解问题补投票轨迹，而非泛化全量重跑。','不影响政策坏尾数值和节劳动结论',SEL+'selection/REPRESENTATIVE_CASE_INDEX.csv;'+SEL+'REPORT_ZH.md',
    '历史Q约束不保证目标Q；当前无证据仅凭总分断言某一临界票原因。')
gap('G14','Semi与其它合法空间的推广','需要新设计','当前有限支持明确单列','Manual已观察规律能否推广到Semi困难图或其它合法目标完整用途链？',
    'Semi和其它空间已有合法原答、配比/AC及各自可评结果；快慢Semi当前没有足够困难支持，正式难度未知目标不补成简单。',
    '仅在推广成为明确研究目标时检查实际容量和必要新设计；不从主Manual或主目标拼接分母。','否',SPEED+'CURRENT_MATCHED_SUMMARY.csv;'+DEPS,
    '无支持是未知，不写零效应；用户本轮主分析为普通Manual。')


def save_csv(name, data):
    p = OUT / name
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
    with p.open(encoding='utf-8-sig', newline='') as f:
        actual = list(csv.DictReader(f))
    assert len(actual) == len(data)
    assert all(None not in x for x in actual)
    return actual


assert len({r['条目ID'] for r in rows}) == len(rows)
assert len({r['缺口ID'] for r in gaps}) == len(gaps)
paths = set()
for r in rows:
    for col in ['当前证据源表_交付根目录相对路径', '原结论来源_交付根目录相对路径']:
        paths.update(x for x in r[col].split(';') if x)
for r in gaps:
    paths.update(x for x in r['证据路径_交付根目录相对路径'].split(';') if x)
missing = sorted(p for p in paths if not (ROOT / p).exists())
assert not missing, missing
save_csv('V2_TO_V21_CROSSWALK.csv', rows)
save_csv('GAP_REGISTER.csv', gaps)
receipt = dict(frozen_repository_commit=SHA, crosswalk_rows=len(rows), gap_rows=len(gaps),
               local_source_paths_checked=len(paths), missing_source_paths=missing,
               numerical_contracts=checks, new_experiments=0,
               source_path_contract='交付根目录相对路径已逐项确认存在；冻结仓库路径保留原成果身份，不宣称本轮重新验证所有原端点。',
               classification_status='工作分析对象；非用户最终选型',
               status='CSV完整读回；源表及关键数值核对通过')
(OUT / 'CROSSWALK_VALIDATION.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k != 'numerical_contracts'}, ensure_ascii=False, indent=2))
