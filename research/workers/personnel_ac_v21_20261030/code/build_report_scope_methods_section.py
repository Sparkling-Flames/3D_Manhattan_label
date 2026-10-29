"""Connect existing strict ABC, current AC and supplementary target domains."""
from pathlib import Path
import importlib.util
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sections',ROOT/'code/build_report_supplement_sections.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
Section,f=mod.Section,mod.f

def main():
    s=Section()
    s.source('R00','stage00_intake/current_source/research/workers/personnel_v21_reselection_20261029/independent_review/reaudit_20261029/README.md','现行独立审查已确认的主方法与严格七八人结果，本轮不重复计算')
    s.source('R01','stage05_funnel_bridge/STRICT_M10_COMMON_CONDITION_BRIEF.csv','旧严格十人和新AC同条件参照')
    s.source('R02','stage05_funnel_bridge/STRICT66_BACKGROUND_PHYSICAL_SUPPORT_SUMMARY.csv','66严格条件内精确固定XZ的108物理背景对照')
    s.source('R03','stage05_funnel_bridge/README_ZH.md','完整容量漏斗、旧ABC规范化、共同条件与背景匹配的口径')
    s.source('R04','stage08_report/scope_supplement_evidence/SCOPE_SELECTED_CONDITION_BRIEF.csv','按登记支持选定的15个补充域条件、质量几何劳动独立分母')
    s.source('R05','stage08_report/SCOPE_SUPPLEMENT_VERIFIED_ZH.md','普通Semi、其它准入目标及OOS已有状态的独立补充核验')
    s.source('R06','stage08_report/scope_supplement_evidence/SCOPE_SUPPLEMENT_VERIFICATION_RECEIPT.json','294入口与258执行池全域核验和450个原始指标行')
    s.source('R07','stage05_context_common/COMMON_POOL_METHOD_COMPARISONS.csv.gz','同图片目标n/m的描述性方法比较，具体成员与类别语义未固定')
    s.source('R08','stage08_report/FROZEN_ALL_DESCRIPTIVE_CLASS_MEMBERS.csv','ALL描述性名单，不能代替LOBO逐图容量')
    s.source('R09','stage01_capacity/FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv','各楼外折类别的原有历史标法语义、角色轴与父类映射')
    s.source('R10','stage06_cases/CASE_EVENT_SUMMARY.csv','代表图精确D/X/Z与该图类别可用人数')
    s.h('11 与严格ABC串联，以及Semi和其它合法目标的边界')
    s.h('11.1 三类设计分别回答什么',2)
    s.table('应并用的证据链',['设计','可以回答','保留的限制'],[
        ['严格ABC','同类具体成员变化为基线，估计跨类额外幅度GA或GS','D/X/Y/Z真实互斥；需n+2m人，来源类需2m人，容量较窄'],
        ['直接AC','同图同目标同n/m同D的实际类别调整结果','只需n+m人，更宽覆盖；没有B不估计跨类超过同类'],
        ['整类等量及类别联盟','模拟完整类别进入/退出、真实混合人群接近全池的结果','m或n可以随图改变；不等人数路径须与等量锚点分开']
    ],'R00/R03',[3.2,6.5,7.5])
    s.p('已独立核验的TARGET主方向严格ABC：14/7登记85图、三队共同可评83图，平均同类|ΔQ|4.577、跨类|ΔQ|8.089，GA=+3.512，61/83图GA>0；20/7登记72图、三队共同可评70图，同类3.533、跨类4.998，GA=+1.465，54/70图GA>0。对称GS的多数比例分别62/83、47/70，不能只选一个定义。新直接AC在同样20/7有85图，实际Q平均+4.576、78/85图正向；这是新的成员/背景设计，没有把旧GA解释成新85图的GA。严格14/7适合展示额外区分，AC20/7与整类n20适合展示实际调整与广覆盖。','R00/R03')
    s.p('本轮接入18,847个旧严格事件：m7/m8为6,367，m9/m10为12,480；已合并的旧源含此前6,548条，不重复叠加。旧AC/BC去重35,051个物理对，与本轮登记的完整AC端点对交集为0；单个端点仍精确复用。2,037个旧有向条件得到相容新AC参照，未新增B或严格ABC。','R03')
    rows=[]
    for im,method,n in [('q9vSo1VnCiC-34','V21_DSTRUCT_RAW3_K3',12),('q9vSo1VnCiC-34','V21_DSTRUCT_RAW3_K3',15),('yqstnuAEVhm-04','TARGET_DSTRUCT_K3',12),('yqstnuAEVhm-04','TARGET_DSTRUCT_K3',14)]:
        r=s.row('R01',image=im,method=method,n=n,metric='B8L2',new_reference_set='F_neutral_common_n')
        rows.append([im,'RAW3' if 'RAW' in method else 'TARGET',str(n)+'/10',r.strict_role_direction,f(r.strict_signed_CA_mean,3,True),f(r.within_AB_mean),f(r.G_A_mean,3,True),f(r.new_strict_direction_signed_or_distance_mean,3,True)])
    s.table('十人共同条件 方向沿用原严格登记',['图','方法','n/m','原严格方向','旧严格ΔQ','旧同类|ΔQ|','旧GA','新ACΔQ'],rows,'R01',[3.2,1.6,1.3,2.5,2.2,2.3,2.0,2.1])
    s.p('TARGET这张图十人旧GA为负，RAW3那张为正；分别只有一图，不能据此重排主方法。新AC与旧ABC的均值差也不能直接归因于取消B，因为具体XZ和D可不同。严格方向在TARGET这里是中→低，与主表低→中相反，符号已保留。','R01')
    bg=s.row('R02',metric='B8L2')
    s.p(f"66个严格条件里按相同pool/method/n/m和精确XZ匹配F-neutral与B-outside，得到120个方法对照、{int(bg.registered_physical_background_comparisons)}个唯一物理四端点对照，覆盖21/66条件。Q四端点可评{int(bg.metric_valid_physical_comparisons)}对、{int(bg.valid_images)}图{int(bg.valid_buildings)}楼；{int(bg.effect_sign_flips)}个物理对照使跨类Q效果反向，涉及{int(bg.target_pools_with_effect_sign_flip)}图。此严格子集120对全部同时改变D类别人数向量，不属于同配比只换背景成员；本轮更宽的固定XZ敏感性另有后一种对照。",'R02/R03')
    s.p('108个登记物理背景对照中，99个四端点共同Q可评者的Q效果差绝对值均值5.187、中位数1.633，其余9个不可评者未进入分布。这是可评四端点对的描述分布，不能当图等权总体值。劳动作差没有合法共同有效对，保留缺失。F−B方向与更宽敏感性表B−F的符号相反，引用时先核对方向。','R02/R03')
    s.h('11.2 其它准入目标：保留全部方向与输出状态',2)
    rows=[]
    for sid in ['other_target_fixed_1','other_target_fixed_2','other_target_fixed_3','other_target_frontier_1','other_target_frontier_2','other_target_frontier_3']:
        r=s.row('R04',selection_id=sid)
        rows.append([('6/3 ' if 'fixed' in sid else '整类前沿 ')+r.role_direction,str(int(r.B8L2_valid_pairs))+'/'+str(int(r.registered_pairs)),str(int(r.B8L2_valid_images))+'/'+str(int(r.registered_images))+'；'+str(int(r.B8L2_valid_buildings)),f(r.B8L2_image_mean,3,True),f(r.D10_image_mean,3,True),f(r.B8L2_image_balanced_mean_absolute),'/'.join(str(int(r['B8L2_'+k+'_images'])) for k in ['positive','negative','tied'])])
    s.table('其它合法目标TARGET K3 逐图等权，合法目标不混队',['方向与条件','Q有效/登记对','图有效/登记；楼','ΔB8L2','ΔD10','均|ΔQ|','正/负/零图'],rows,'R04',[3.1,2.7,2.9,2.1,2.1,2.1,2.2])
    s.p('其它准入目标30个Manual入口池实际执行20池、18图、7楼；同图不同目标分别组队评分，图汇总才目标等权。TARGET中→高整类前沿登记18池、17图，17池103/107对Q可评，13正4负。固定6/3同方向虽然5图全正，但只26/48对可评；全部尝试A→C缺Q图等权率38.75%→5.00%。成功对的升Q与可形成完整输出的变化分别报告。其劳动只有4对1图，不能代表整个目标域。','R04/R05/R06')
    s.h('11.3 普通Semi：自身冻结V3分类的次要结果',2)
    rows=[]
    for sid,label in [('semi_behavior_coarse','行为粗 S1→S2'),('semi_behavior_fine','行为细 S1.1→S2.1'),('semi_joint_coarse','QT粗 K1→K2'),('semi_joint_fine','QT细 K1.1→K2.1')]:
        r=s.row('R04',selection_id=sid)
        rows.append([label,str(int(r.B8L2_valid_pairs))+'/'+str(int(r.registered_pairs)),str(int(r.B8L2_valid_images))+'/'+str(int(r.registered_images))+'；'+str(int(r.B8L2_valid_buildings)),f(r.B8L2_image_mean,3,True),f(r.D10_image_mean,3,True),f(r.B8L2_image_balanced_mean_absolute),'/'.join(str(int(r['B8L2_'+k+'_images'])) for k in ['positive','negative','tied'])])
    s.table('Semi整类前沿 方向是类别ID，不是历史Q排名',['自身分类与方向','Q有效/登记对','图有效/登记；楼','ΔB8L2','ΔD10','均|ΔQ|','正/负/零图'],rows,'R04',[3.1,2.7,2.9,2.1,2.1,2.1,2.2])
    s.p('Semi用V3_BEHAVIOR_COARSE/FINE与V3_JOINT_QT_COARSE/FINE，没有套用Manual的TARGET。粗层按登记图支持最多的方向、细层按对应方向选取，未按收益选型。固定n20通常仅1–2图，故报告池前沿；行为粗层n3–42、m1–13，QT粗层n3–43、m1–13。行为粗层Q均值−2.612，但4正、11负、12近零，不是多数图下降；其A→C缺Q率7.143%→0，质量均值降低与输出更常可评同时存在。劳动−15.846%仅16对6图4楼，不和27图Q合成整体质量—时间权衡。','R04/R05')
    s.p('普通Semi共38池执行32池；其它准入目标只有uNb9QFRL6hY-68一个Semi池（N4），8个不同物理对均可评分，单列而不声称多图规律。门口/特殊20池没有新增执行。当前提交的既有空间审查另有1,222份OOS或待定OOS原答仍无正式质量准入；单位是原答库存，非池，不与294入口池或20特殊池相加，本轮未重做其审查或解除资格。','R05/R06')
    s.h('12 分类解释具体人员和共同图片比较')
    s.p('本轮保持既有分类定义，没有用这次团队结果重新选择特征或调整标签。TARGET与RAW3的低/中/高主角色按楼外困难图有效转折历史排序，OPPSTRUCT按复杂结构机会响应排序；OPPJOINT按对应楼外折历史Q角色对齐，RFUSE按原有融合响应排序。标签编号不等于永久能力等级，实际标法解释同时看短结构、近共线冗余、相对面积/高度、质量和合法记录劳动。','R09')
    roles=[]
    for cid in ['C1','C2','C3']:
        r=s.row('R09',method='TARGET_DSTRUCT_K3',heldout_building='VFuaQ6m2Qom',class_id=cid)
        roles.append([cid,r.semantic_training_role])
    s.table('一个具体楼外折的TARGET原有画像 VFuaQ6m2Qom',['类','原始历史标法与伴随画像'],roles,'R09',[1.8,15.4])
    s.p('这是VFua楼外折的历史群体画像，不是对目标图原答的逐人承诺。wc2中W027属高结构类却在该图只有四点，W017/W126各有八点，就是类别与单图具体行为不可等同的直接例子。TARGET未因此被改成质量分类；Q/T伴随差异作为画像信息保留。','R09/R10')
    common=[]
    for left,right,n,m in [('TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3',20,7),('TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3',20,7),('OPPJOINT_K3','TARGET_DSTRUCT_K3',20,7),('OPPJOINT_K3','OPPJOINT_K4',20,10),('OPPJOINT_K3','OPPJOINT_K4',20,12)]:
        r=s.row('R07',method_left=left,method_right=right,n=n,m=m,metric='B8L2_CA')
        short=lambda x:x.replace('TARGET_DSTRUCT_','TARGET ').replace('V21_DSTRUCT_RAW3_','RAW3 ').replace('OPPJOINT_','JOINT ')
        common.append([short(left)+' / '+short(right),str(n)+'/'+str(m),str(int(r.valid_common_images))+'；'+str(int(r.valid_common_buildings)),f(r.left_image_mean_absolute_change),f(r.right_image_mean_absolute_change),str(int(r.right_absolute_larger_images))+'/'+str(int(r.valid_common_images))])
    s.table('共同图片目标n/m下的描述性比较 左/右对应方法顺序',['方法左/右','n/m','共同图；楼','左均|ΔQ|','右均|ΔQ|','右幅度更大图'],common,'R07',[4.7,1.4,2.4,2.4,2.4,3.9])
    s.p('共同图片比较每个方法内部对可用角色方向等权，不保证具体成员、类别语义及D配比一致；因而控制了图片目标和n/m，却不能把右侧更大的幅度等同分类更好，也不是控制历史Q后结构的独立增益。本轮没有重复已核验的Q二分、Q/T匹配与父子分类实验。JOINT新增的是联合解释和较大混合人群容量，RAW3新增的是特征定义/大块敏感性，RFUSE保留从融合响应解释的反向互补。','R00/R07')
    s.h('12.1 名单可以直接使用，但组队必须回到逐图楼外折',2)
    rows=[]
    for cid in ['C1','C2','C3']:
        r=s.row('R08',method='TARGET_DSTRUCT_K3',class_id=cid)
        rows.append([cid,str(int(r.people)),r.workers.replace('|','、')])
    s.table('TARGET K3 ALL描述名单 此表不是每图容量',['类','人数','名单'],rows,'R08',[1.1,1.1,15.0])
    s.p('ALL中W019/W026仍排除，不得加入背景；W022历史不足但有合法原答时可作为未分类D。其它方法及所有楼外折的完整名单已保存。实际组队唯一使用POOL_CLASS_MEMBERS.csv.gz中的图/目标/折/原答ID，不从这张ALL表推断某图有十名或十二名可换人员。','R08/R09')
    r=s.row('R10',event_id='bded3837a41e1443a8d3e0c0')
    s.table('VFuaQ6m2Qom-07整类七人换入的精确成员',['块','人数','实际人员'],[
        ['D，共同背景','13',r.D_workers.replace('|','、')],['X，C2换出','7',r.X_workers.replace('|','、')],['Z，该图全部C3','7',r.Z_workers.replace('|','、')]
    ],'R10',[3.7,1.2,12.3])
    s.p('全部471,758条方法事件都保存同等级的精确成员、类别、n/m、背景、合法目标和两个team_key。核心成员频次表按26,887个实际条件列出固定交集、各侧可用人数和逐人出现次数；同一端点跨方法选中仅为多重解释，不累计为独立人员证据。','R10')
    s.save('SECTION11_STRICT_AND_SCOPE.json')
    print('Saved sections 11 and 12 with exact source rows.')

if __name__=='__main__':main()
