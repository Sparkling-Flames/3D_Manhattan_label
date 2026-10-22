"""Integrate the completed population process into the existing personnel report.

Presentation-only: no class fitting, endpoint computation or metric reaggregation.
"""
from pathlib import Path
import re

ROOT = Path('/workspace/scratch/fe955c3c772c')
WORK = ROOT / 'population_work'
REPO = ROOT / 'HOHONET_population_latest'
DOC = REPO / 'docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md'
BASE = '../../research/workers/personnel_population_curves_v2_20261023/'
old = DOC.read_text()
assert '## 6. 难度、类别构成与随机人数曲线怎样连接' in old
head = old.split('## 6. 难度、类别构成与随机人数曲线怎样连接')[0]
head = head.replace(
    '更新：2026-10-23，本地独立核验及旧n20失败修正已完成。Pro本轮实际读取 main 提交 **`ef148c82df18582228b2d23837faa2659e79eba7`**，已包含用户指定的 `ef148c82d`。',
    '更新：2026-10-23，人员构成结果继续保留；本次已完成自然混合人数曲线及四种类别角色优先进入实验，结果接入第6节。本次实际读取并冻结 main 提交 **`72a44e80c344975962e1071bd54d894dd86bb4b4`**，已包含用户指定的 `ef148c82d`；[提交祖先关系凭据]('+BASE+'SOURCE_COMMIT_ANCESTRY.json)。第4—5节的完整构成比较仍保留原读取提交 **`ef148c82df18582228b2d23837faa2659e79eba7`** 和原阶段身份。')
head = head.replace('前轮[整合核验]', '既有[整合核验]', 1)
head = head.replace('本轮从实际保存的设计、端点与原答补出', '此前构成阶段从实际保存的设计、端点与原答补出', 1)
head = head.replace('新工作是条件实验的完整重组与分析，**没有重复运行原生融合**', '该阶段工作是条件实验的完整重组与分析，**没有重复运行原生融合**', 1)
head = head.replace('第5节是实际完成账，第7节给出收尾判断。', '第5节是此前构成完成账，第6节是本次自然人数与类别进入顺序的实算结果，第7节给出合并后的采用判断。')
head = head.replace('|简单图较快接近GT，困难/门洞较慢或难以接近|保留为人数过程的待检验预期；连接当前难度，质量、波动和失败分别观察，不按曲线反改难度。|', '|简单图较快接近GT，困难/门洞较慢或难以接近|第6节已实算：困难图也有多数早期改善；中后段缩波更普遍，门洞失败和降质单列。不按曲线反改难度。|')
head = head.replace('## 5. G1—G7完成账与实际覆盖边界', '## 5. 此前构成阶段的G1—G7完成账与实际覆盖边界')
head = head.replace('原生融合、评分和新拟合标签均为0；本轮不是一轮新的标注采集。', '上述构成重汇总阶段原生融合、评分和新拟合标签均为0；第6节的新前缀补算另计，两阶段均不是新的标注采集。')

intro = '''## 6. 自然混合人数曲线与类别进入顺序：已完成的v2过程研究

**本次完成了用户提出的两步实验。** 第一条线是在每图实际正式人员池内均匀随机无放回排列，逐个整数前缀重新形成共识；第二条线使用已有楼外类别，比较同一完整人员池的不同进入顺序。先计算每次实际团队的共识与质量，再平均测量值，没有先平均几何，也没有按目标图Q挑顺序。

**自然加人对简单和中等Manual图通常同时升质、改善低尾并降低成员波动；困难图也有清楚的早期改善，10→20人则更明显地表现为输出更一致而平均Q不再明显提高。** 对同一人员池，Manual历史高Q角色先进入和较多转折角色先进入，能显著改变前中段的质量、低尾、失败及局部结构；Semi快角色主要支持记录时间与质量取舍。以下同时保留四个方向的正向、负向和接近零结果。

本轮没有新拟合分类，未改GT、资格、B8L2/D10或融合合同。融合仍按冻结7.5°对应、团匹配、`ceil(k/2)`门槛、中位定位及投影环序进行。k=2沿既有合同暂停，不补成0分或失败。结构诊断5°/9°、旧原答9°/12°分簇与融合对应参数是不同对象。代码、精确顺序与完整结果见[本次成果入口](BASEREADME.md)。

'''.replace('BASE', BASE)

natural = (WORK/'difficulty/final24/SECTION6_NATURAL_FINDINGS.md').read_text()
natural = natural[natural.index('## 1. 实际完成范围'):natural.index('## 7. 与阶段01')]
natural = re.sub(r'^## (\d+)\. ', lambda m:'### 6.'+m[1]+'. ', natural, flags=re.M)
def natlink(match):
    text,target = match[1],match[2]
    if target=='NATURAL_ADJACENT_TRANSITIONS.csv.gz':
        target=BASE+'events/NATURAL_ADJACENT_TRANSITIONS_LINKED.csv.gz'
    elif not target.startswith(('https:', '#')):
        target=BASE+'natural/'+target
    return '['+text+']('+target+')'
natural=re.sub(r'\[([^\]]+)\]\(([^)]+)\)', natlink, natural)
natural += '\n![自然混合人数曲线：固定N≥20图片，经验分位带与失败分别展示]('+BASE+'natural/NATURAL_FIXED_PANEL_CURVES.png)\n\n'
natural += ('阶段01的旧4顺序保留为探索检查点，本节采用扩展后的24顺序。门洞10→20更新为明显负向，Semi简单3→20底面IoU更新为0.89319→0.90588，Uw-09更新为后段缩波兼均值下降；这来自增加实际成员顺序，并非修改评分或资格。\n\n')

policy = (WORK/'composition/final/POLICY_FINDINGS.md').read_text()
policy = policy[policy.index('## 2. 比较对象'):]
policy = re.sub(r'^## (\d+)\. ',lambda m:'### 6.'+str(int(m[1])+5)+'. ',policy,flags=re.M)
policy = policy.replace('`../LOBO_PRIORITY_ROLE_DEFINITIONS.csv`', '[逐折角色与历史中心]('+BASE+'design/LOBO_PRIORITY_ROLE_DEFINITIONS.csv)')
policy = policy.replace('`../POLICY_POOL_CAPACITY.csv`','[实际成员与容量]('+BASE+'design/POLICY_POOL_CAPACITY.csv)')
policy = policy.replace('`../../cases/final_context/CASE_CURVE_BACKGROUND.md`','[五案完整自然与配对策略背景]('+BASE+'cases/final_context/CASE_CURVE_BACKGROUND.md)')
policy = policy.replace('`POLICY_PAIRED_PREFIX_EVENTS.csv.gz`、`POLICY_DIRECT_PAIRED_PREFIX_EVENTS.csv.gz`', '[229,050条配对前缀事件]('+BASE+'events/POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz)、[112,520条直接角色事件]('+BASE+'events/POLICY_DIRECT_PAIRED_PREFIX_EVENTS_LINKED.csv.gz)')
policy = policy.replace('`../EXACT_ORDER_DESIGN.csv.gz`、`../ENDPOINT_CLASS_VECTORS.csv.gz`', '[完整顺序]('+BASE+'design/EXACT_ORDER_DESIGN.csv.gz)、[端点完整类别向量]('+BASE+'design/ENDPOINT_CLASS_VECTORS.csv.gz)')
policy = policy.replace('](POLICY_PROCESS_DIFFERENCES.png)',']('+BASE+'policies/POLICY_PROCESS_DIFFERENCES.png)')
for name in ['POLICY_MAIN_FIXED_N20.csv','POLICY_FOCAL_PER_IMAGE.csv','POLICY_FOCAL_SUMMARY.csv','POLICY_DIRECT_MAIN_FIXED_N20.csv','POLICY_PER_IMAGE_K.csv.gz','POLICY_PER_IMAGE_K_METRICS.csv.gz']:
    policy=policy.replace('`'+name+'`','['+name+']('+BASE+'policies/'+name+')')
for name in ['analyze_policy_curves.py','analyze_direct_policy_contrasts.py','extract_policy_main_tables.py','extract_direct_role_summary.py','summarize_policy_components.py','plot_policy_curves.py']:
    policy=policy.replace('`../'+name+'`','['+name+']('+BASE+'code/'+name+')')
policy=policy.replace('`../POLICY_FIELDS.md`','[策略字段说明]('+BASE+'policies/POLICY_FIELDS.md)')
policy=policy.replace('所有可行最终自然池都已计算', '全部229个达到当前正式资格且至少3人的自然池都已计算')
policy=policy.replace('高 Q 角色前半段席位比例从自然的约 15%–17% 提高到约 60%–66%；较多转折从约 21%–23% 提高到约 73%–76%。最多结构类策略则使前段接近纯该类，约 99.7%–100%。', '本节157图固定共同域中，高Q角色前半段平均席位比例从15.42%提高到60.93%，较多转折从22.24%提高到75.08%；最多结构类从65.53%提高到99.81%。这些是跨实际k的平均构成，不是每张图应采用的固定配额。')
role_note = '''
本节的角色不是把ALL固定类数搬到每折。Manual结构楼外折实际采用TURN 17折、JOINT 4折、CONTEXT 1折；Semi结构为STRUCTURE 19折、JOINT 3折。Manual联合为CQT 19折、EQT 3折，Semi联合为EQT 21折、GEQT 1折。它们均为此前冻结的建类选择，按历史中心选角色；因此本节准确称“已有结构类/联合类的楼外角色优先”，不声称每折都是同一套三类或五类。ALL名单仍按第1节用于整体描述。高Q和较多转折角色成员有重叠，其效果不计作两次独立发现。

'''
policy=policy.replace('四个策略共得到 6,974 条完整顺序',role_note+'四个策略共得到 6,974 条完整顺序')

closing='''### 6.15. 实际计算、组合覆盖与接续

本次共完成 **229池、196图、22楼、7,302条正式独立记录、60位实际人员**。普通Manual177池、门洞Manual17池、特殊Manual2池；普通Semi32池、特殊Semi1池。库存另外39池OOS、36池虽有至少3条独立非OOS答卷但正式参考/质量资格不足3人、9池独立合格支持不足3人，未据此恢复资格。[逐池库存](BASEcoverage/FORMAL_POOL_INVENTORY_COVERAGE.csv)

|空间/结果|本次实际完成|准确解释|
|---|---:|---|
|自然顺序|5,424条，175,032前缀；166,069个去重端点|225池各24条；其中6个N=4池全24种，4个N=3池全6种。大池为明确登记随机覆盖。|
|类别优先顺序|6,974条，229,050前缀|每种可行策略8个配对自然基础顺序，小池至多全6种；未知人员保留在余下部分。|
|合计|12,398条路径，404,082条完整前缀|每条从k=1到实际N的全部整数位置均保留；k2为明确暂停。|
|不同成员端点|318,816个|复用30,188个；新增288,628个成员集合结果。包含原答k1及k2暂停结果，不把每一行都称一次融合。|
|完整过程事件|557,138行|自然相邻169,608、路径区间45,960、策略对自然229,050、角色直接对照112,520；计的是关系，不是独立样本。|

复用来源为原v2流程29,578个、同房共同子池中恰好相同的成员集合545个、后续缓存65个；仅在成员、图片、条件及冻结合同一致时复用。同房子池路径没有冒充本图完整自然池。新补算遵循原融合与评分，只填真实缺口；每批完成即保存端点，4批检查点覆盖全部229池。最终[完成账](BASEresults/COMPLETION.json)和[成员/前缀关联检查](BASEresults/DELIVERY_VERIFICATION.json)均已落盘，缺失端点0，重复端点键0，全部满员终点一致。该关联检查未再次融合或评分。

可行配比、具体成员集合与加入顺序三个空间仍分别列出。[逐人数成员空间](BASEcoverage/PREFIX_MEMBER_SPACE_COVERAGE.csv.gz)记录C(N,k)和已计算不同集合；[完整类别向量空间](BASEcoverage/PREFIX_CLASS_VECTOR_COVERAGE.csv.gz)记录可行人数向量与已覆盖向量；[顺序空间](BASEcoverage/ORDER_SPACE_COVERAGE.csv)列出N!、自然与策略实际路径数。最大池N=46，46!约5.50×10^57；本次没有把24条自然顺序或8条策略称全排列穷尽。10个N≤4池完成自然全排列，其余大池采用固定随机种子，全部登记顺序和成员精确可重放。

本轮前缀作用属于同一最终人员池；不同最终构成的完整配比、严格ABC、旧重叠设计和直接AC继续读第4节，不将本次8条路径伪装成新的严格三队对照。目标建筑未参与建类，角色规则也不读取目标端点；数据经过多轮探索，主要采用判断是当前v2内部检验，不冒称新外部盲测。

交付将重复原始测量一次保存在端点表，完整557,138行事件保留差值、风险、精确成员差集、方向与端点键；可以按逐列映射恢复宽表。不是只交批次索引，也未删除负向或失败。成果入口为[README](BASEREADME.md)、[字段](BASEDATA_DICTIONARY.md)、[复现](BASEREPRODUCE.md)、[完整事件关联](BASEevents/README.md)、[过程采用表](BASEpolicies/ADOPTION_TABLE.csv)。大文件分包与独立报告/关键小表同时提供。

## 7. 合并后的采用判断与研究收尾

**人员分类、混合构成以及自然人数过程这条主线，已有可采用的连续证据，可以在当前数据支持范围内收尾。** 第1—5节保留“类别—完整有限配比—成员分布—同背景同规模比较—具体方向与难度”；第6节补齐“随机进入—每个人数的输出分布—既有类别改变进入过程—实际局部机制”。不需要再全面搜索一套唯一分类，也不以穷尽大池排列作为采用前提。

**当前采用三个清楚的过程用途。** Manual历史高Q角色优先用于加快前中段升质、抬高低尾、减少失败；较多转折角色优先用于有结构含义的补充和定位改善，允许一定时间代价及局部反例。Semi快角色优先用于记录时间与质量取舍，全质量域平均Q接近不变，不移植Manual的普遍排序。Manual快类与历史人数最多结构类的负向质量结果保留为明确对照。优先进入的优势多在3—10人，20人仍有较小多数正向；这不是统一停标人数或固定配比配方。

**自然加人有两种不同价值。** 简单、中等Manual多数图同时提高质量和一致性；困难图也在前段普遍改善，但后段降低波动比提高平均Q更普遍。共同的结构少数、范围或定位偏差可以在满员时仍存在。遇到后段低平台，应结合局部原答支持解释，不把零方差当正确，也不因个别反例否定多数图片的类别用途。门洞单列，失败与条件质量同时报告。

此前Manual联合的选队收益、匹配替换收益和本次优先进入收益是三个实验身份，均保留而不相互替代。旧M、A2、QTD、SP、F01与跨条件分类仍按其原用途保留；本轮没有重跑共同域连续QT实验或改写分类。与难度、质量、融合、画像和同房的连接沿既有专题维护；新增同房预测和研究台不在本轮范围。

实际文件按[本次入口](BASEREADME.md)与[此前构成入口](../../research/workers/personnel_mixture_comparison_20261022/README.md)分清。旧阶段00/01/02与4批计算检查点保留，主结论采用完整24顺序和最终配对结果；未覆盖的大池排列、Semi困难大人数、完整时间不足的图片均在表中显式注明。本次交付是已更新的仓库文件及可下载数据，不代表已代用户公开推送main。后续只需在新数据或明确用途出现时更新相应表与本报告对应节。
'''.replace('BASE',BASE)
new=head+intro+natural+policy+'\n\n'+closing
DOC.write_text(new)
print({'report':str(DOC),'bytes':DOC.stat().st_size,'section6_subsections':len(re.findall(r'^### 6\.',new,re.M))})
