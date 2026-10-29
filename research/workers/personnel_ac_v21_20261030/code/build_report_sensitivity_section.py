"""Use complete, independently masked sensitivity summaries for report section 8."""
from pathlib import Path
import importlib.util,json

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sections',ROOT/'code/build_report_supplement_sections.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
Section,f=mod.Section,mod.f

def main():
    s=Section()
    prefix='stage05_sensitivity/'
    s.source('S01',prefix+'member_variability_v2/MEMBER_VARIABILITY_VALID_GE2_SUMMARY.csv.gz','成员波动最终分母：每项至少两个有效值才估计跨度标准差翻转')
    s.source('S02',prefix+'member_variability_v2/MEMBER_VARIABILITY_DENOMINATOR_RECEIPT.json','单可评值不记为零波动的定向修正回执')
    s.source('S03',prefix+'report_tables/BACKGROUND_CHANGES_COMPACT_PRIMARY_MANUAL.csv.gz','全部258池完成后固定精确XZ、同n/m的背景敏感性')
    s.source('S04',prefix+'report_tables/FIXED_A_REPLACEMENT_STEPS_COMPACT_PRIMARY_MANUAL.csv.gz','精确固定A、嵌套扩大替换块的效果增量')
    s.source('S05',prefix+'report_tables/FIXED_BLOCK_BACKGROUND_STEPS_COMPACT_PRIMARY_MANUAL.csv.gz','精确固定XZ、嵌套扩大共同背景人数的效果增量')
    s.source('S06',prefix+'report_tables/SAMPLING_BATCHES_COMPACT_PRIMARY_MANUAL.csv.gz','两个独立种子批次的均值方向与幅度一致性')
    s.source('S07',prefix+'core_members_v2/AC_CELL_CORE_COVERAGE_SUMMARY.csv.gz','逐条件两侧固定成员块与全部成员必用的覆盖统计')
    s.source('S08',prefix+'core_members_v2/AC_CELL_MEMBER_CORES_AND_FREQUENCIES.csv.gz','26887条件的精确固定核心名单与逐人事件出现频次')
    s.source('S09',prefix+'report_tables/COMPACT_FULL_POOL_RECEIPT.json','全部258池已完成的紧凑图楼汇总回执')
    s.source('S10',prefix+'exact_outside_background_v1/EXACT_BACKGROUND_RECEIPT.json','更宽的精确XZ与外部背景锚点匹配，209池6364方法对照')
    s.source('S11',prefix+'exact_outside_background_v1/STRICT_BACKGROUND_OVERLAP_VALIDATION.json','外部背景与strict66四端点身份重叠及相反符号的逐项验证')
    s.h('8 类别相同以后，成员背景和替换比例还改变多少')
    s.p('类别作用不能由每图一组人员代表。本轮明确区分五种敏感性：同类别人数但成员可变；精确同D而X/Z成员可变；精确同XZ、同n/m而D成员或配比可变；精确同XZ增加D人数；精确同A嵌套扩大X/Z。以下统计来自全部258池完成后的派生表，主段限普通Manual原主目标。它们是有限已登记组合中的波动，不是新人员的预测准确率。','S09')
    s.p('成员跨度、标准差与正负翻转至少要求该面板该指标有两个有效值。原表的155个Q面板只有一个可评值，现已从波动分母排除，均值和原始端点不改；所有指标共排除8,078个单值波动条目。固定D的Q面板没有这项缺陷。单一小类块固定、单个可评分组合、多个组合但都缺Q，分别报告，不把无法估计写成稳定零。旧版保留，正文使用member_variability_v2。','S01/S02')
    s.h('8.1 固定同一背景，只改替换块的具体人选',2)
    methods=[('TARGET K3','TARGET_DSTRUCT_K3'),('RAW3 K3','V21_DSTRUCT_RAW3_K3'),('JOINT K3','OPPJOINT_K3'),('JOINT K4','OPPJOINT_K4')]
    rows=[]
    for label,method in methods:
        keys=dict(scope='primary',condition='manual',method=method,panel_kind='exact_fixed_D_member_panel',role_direction='1->2',n=20.0,m=10.0)
        q=s.row('S01',**keys,metric='B8L2_CA__span');d=s.row('S01',**keys,metric='D10_CA__span');flip=s.row('S01',**keys,metric='B8L2_CA__sign_flip')
        rows.append([label,str(int(q.valid_images))+'；'+str(int(q.valid_buildings)),str(int(q.valid_panels)),f(q.image_mean),f(d.image_mean),f(100*flip.image_mean,2)+'%'])
    s.table('固定D，n20/m10，角色1→2的成员面板',['方法','有效图；楼','有效面板','Q跨度图均','D10跨度图均','面板正负翻转率'],rows,'S01',[3.2,2.3,1.9,2.6,2.8,4.4])
    s.p('这里的跨度为一个固定D面板内跨类Δ的最大值减最小值；翻转率是图等权的面板内部同时出现正、负Δ的比例。它衡量同类别人数下换具体人的敏感性，不是严格同类B。TARGET十人的3图未翻转只能描述这3图；JOINT3的69图约44.93%面板翻转，说明其平均接近零的大块条件有相当部分方向取决于具体成员。','S01')
    s.p('这些方法的可评图片集合不同，不能按跨度大小排名分类稳定性。有些面板一侧类别已固定，没有同时扰动X和Z；完整表逐侧保留团队变体数。除明确标出的TARGET中→高20/7外，本节20/10比较均为各方法角色1→2，不代表该方法所有方向。','S01/S08')
    q=s.row('S01',scope='primary',condition='manual',method='TARGET_DSTRUCT_K3',panel_kind='class_count_preserving_members_D_not_fixed',role_direction='2->3',n=20.0,m=7.0,metric='B8L2_CA__span')
    flip=s.row('S01',scope='primary',condition='manual',method='TARGET_DSTRUCT_K3',panel_kind='class_count_preserving_members_D_not_fixed',role_direction='2->3',n=20.0,m=7.0,metric='B8L2_CA__sign_flip')
    s.p(f"若只固定两队的实际类别人数，允许替换块和D的具体成员一起变化，TARGET主方向20/7覆盖{int(q.valid_images)}图、{int(q.valid_panels)}个可评面板；Q跨度图均{f(q.image_mean)}，面板正负翻转率{f(100*flip.image_mean,2)}%。这较宽的波动包含D身份变化，不能拿它与上表固定D跨度直接相减当作背景方差贡献。",'S01')
    s.h('8.2 固定同一替换块，类别配比不变的背景换人',2)
    rows=[]
    for label,method,m,role in [('TARGET 中→高','TARGET_DSTRUCT_K3',7,'2->3')]+[(label,method,10,'1->2') for label,method in methods]:
        keys=dict(method=method,n=20.0,m=float(m),role_direction=role,comparison='same_composition_background_members',background_profile='neutral_members_1')
        q=s.row('S03',**keys,metric='B8L2_CA__effect_difference');d=s.row('S03',**keys,metric='D10_CA__effect_difference')
        rows.append([label,'20/'+str(m),str(int(q.valid_images))+'；'+str(int(q.valid_buildings)),f(q.image_mean,3,True),f(q.image_balanced_mean_absolute_within_pool),f(d.image_balanced_mean_absolute_within_pool),str(int(q.positive_images))+'/'+str(int(q.negative_images))])
    s.table('背景效果差＝新背景下(C−A)−基线背景下(C−A)',['方法方向','n/m','图；楼','效果差均值','Q均|效果差|','D10均|效果差|','效果差正/负图'],rows,'S03',[3.0,1.3,2.0,2.6,2.6,2.9,2.8])
    s.p('这张表要求精确XZ不变、n/m不变、实际D类别人数向量相同，只替换D的具体成员。JOINT3十人的效果差均值约−0.034，看似接近零，但逐次取绝对差后图等权约2.450；TARGET20/7为−0.388与4.564。正负抵消不等于背景无作用。背景类别构成也改变的source_enriched/target_enriched对照另存，不与这张表混合。','S03')
    s.p('上表绝对幅度先在每个实际背景比较内取绝对值，再池内平均、图等权。原汇总中的|图平均效果差|是另一描述量，通常更小；正文没有用后者替代逐比较幅度。背景劳动秒差在精确XZ固定且四队合法可比时应保持一致；百分比仍受基线总劳动分母影响，缺记录或来源不匹配的四端点不算合法劳动变化。','S03/S09')
    s.p('另将精确相同XZ与已有outside背景锚点匹配，209池得到6,364个方法对照、5,573个物理四端点对照，要求n/m相同且D确实不同。与strict66的120方法/108物理对照只有4对身份重叠，去重并集为6,480方法对照、5,677物理四端点对照。重叠的12项指标×4对逐项核对通过：广表为outside−neutral，strict表为F-neutral−B-outside，符号相反，绝对幅度一致。该外部背景匹配不冒充上一张同配比neutral背景表，也不新增融合或团队。','S10/S11')
    s.h('8.3 固定原队扩大替换块，与固定块扩大背景是两种实验',2)
    rows=[]
    for label,method,n,m1,m2,role in [('TARGET 中→高','TARGET_DSTRUCT_K3',20,7,8,'2->3'),('JOINT3 1→2','OPPJOINT_K3',20,9,10,'1->2'),('JOINT3 1→2','OPPJOINT_K3',20,10,12,'1->2'),('RFUSE 1→2','RFUSE_GEOM_K2',20,3,4,'1->2')]:
        q=s.row('S04',method=method,n_from=float(n),m_from=float(m1),m_to=float(m2),role_direction=role,metric='B8L2_CA__step_difference')
        rows.append([label,'n'+str(n)+',m'+str(m1)+'→'+str(m2),str(int(q.valid_images))+'；'+str(int(q.valid_buildings)),f(q.image_mean,3,True),f(q.image_balanced_mean_absolute_within_pool),str(int(q.positive_images))+'/'+str(int(q.negative_images))])
    s.table('精确同A且嵌套扩块 Q效果增量',['条件','人数与块变化','图；楼','均增量','均|增量|','增量正/负图'],rows,'S04',[3.2,3.1,2.1,2.5,2.5,3.8])
    s.p('TARGET20人的7→8人扩块增量均值−0.338，但7/11图为正；JOINT3的9→10人和10→12人也接近正负各半。这里已逐条核对A的team_key相同、X/Z嵌套，所以比跨不同图片直接比较m7和m12均值更能说明替换比例作用，但仍由具体新加入块成员决定。RFUSE3→4人有66/82图效果增量为正，保留小块反向分类的实用性。','S04')
    rows=[]
    for label,method in methods:
        q=s.row('S05',method=method,n_from=20.0,n_to=22.0,m_from=10.0,m_to=10.0,role_direction='1->2',metric='B8L2_CA__step_difference')
        rows.append([label,str(int(q.valid_images))+'；'+str(int(q.valid_buildings)),f(q.image_mean,3,True),f(q.image_balanced_mean_absolute_within_pool),str(int(q.positive_images))+'/'+str(int(q.negative_images))])
    s.table('固定同十人XZ，背景嵌套增加，n20→22',['方法','图；楼','均Q效果增量','均|增量|','增量正/负图'],rows,'S05',[3.4,2.4,3.4,3.5,4.5])
    s.p('JOINT3这条背景人数路径在72图上平均−0.165，但43正29负，绝对增量1.368。增加背景同时增加具体人员、降低m/n并可能改变MV50门槛；本表不能单独将变化归因于其中任何一项。S9h-04的完整票账在后节说明一次真实门槛与互斥表达机制。','S05')
    s.h('8.4 两批抽样方向与固定核心人员',2)
    rows=[]
    for label,method,m,role in [('TARGET 中→高','TARGET_DSTRUCT_K3',7,'2->3')]+[(label,method,10,'1->2') for label,method in methods]:
        keys=dict(method=method,n=20.0,m=float(m),role_direction=role)
        agree=s.row('S06',**keys,metric='B8L2_CA__direction_agreement');amp=s.row('S06',**keys,metric='B8L2_CA__mean_difference')
        rows.append([label,'20/'+str(m),str(int(agree.valid_images))+'；'+str(int(agree.valid_buildings)),f(100*agree.image_mean,2)+'%',f(amp.image_balanced_mean_absolute_within_pool)])
    s.table('两个不同种子且跨批组合去重的图片平均响应',['方向','n/m','可比较图；楼','Q均值方向一致率','两批均值差的绝对值图均'],rows,'S06',[3.2,1.6,2.8,4.0,5.6])
    s.p('TARGET主方向20/7的两批方向一致80/85＝94.12%，D10一致92.94%，同时Q批次差的绝对值图均2.903。它支持当前有限抽样下总体方向较稳定，同时幅度受人选影响。两批种子不同、组合跨批去重，人员仍可共享，并非独立人员样本。枚举格不计入两批盲抽验证；一致率不是预测准确率，也不能消除共享成员与楼的相关性。','S06')
    rows=[]
    for label,method in methods:
        r=s.row('S07',scope='primary',condition='manual',method=method,n=20.0,m=10.0)
        rows.append([label,str(int(r.images))+'；'+str(int(r.buildings)),str(int(r.cells)),str(int(r.source_block_fixed_cells)),str(int(r.target_block_fixed_cells)),str(int(r.both_blocks_fixed_cells))])
    s.table('20/10的所有实际方向：某侧在登记样本中没有成员变化',['方法','图；楼','条件数','来源块固定','目标块固定','两侧都固定'],rows,'S07',[3.2,2.4,2.3,3.1,3.1,3.1])
    s.p('完整核心表有26,887条件：25,641 Manual、1,246 Semi，逐条给出源/目标固定交集、每个成员在该条件内不同AC事件中的出现次数、是否每次用尽该图该类全部成员。固定核心是已抽样块的交集，不自动等于自然人群只有这些人；若整类只有8人全部进入，其作用无法从当前设计中拆成“类别的独立作用”和这8人的独立贡献。不同方法选中同一物理团队或同一端点对，按精确身份识别重叠，不当独立重复证据。','S07/S08')
    s.save('SECTION08_SENSITIVITY.json')
    print('Saved full section 08 from completed summaries with corrected denominators.')

if __name__=='__main__':main()
