"""Compact new experiment summaries; read completed tables only, no fusion."""
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'integration'
S=ROOT/'structure_followup'
G=S/'background_gradient'
a=pd.read_csv(G/'ABC_SUMMARY.csv').iloc[0]
g=pd.read_csv(G/'GRADIENT_SUMMARY.csv').iloc[0]
f=pd.read_csv(S/'FIXED_A_COMMON_DECOMPOSITION.csv')

rows=[dict(
    result_id='NEW_FIXED_XYZ_BACKGROUND_ABC', source_data='real_v2',
    classification='Manual结构三类，常规→较多转折', n=20, m=7,
    design='39图×2个旧冻结XYZ锚点；每锚剩余14人选13人D全部枚举',
    registered=1092, valid=1058, images=39, buildings=15,
    same_B_minus_A_Q=a.same_B8L2, cross_C_minus_A_Q=a.cross_B8L2,
    net_C_minus_B_Q=a.net_B8L2, net_C_minus_B_D10=a.net_D10,
    same_abs_Q=a.common_quality_within_abs, cross_abs_Q=a.common_quality_cross_abs,
    cross_abs_definition='abs(C-A)', net_positive_images=26, net_positive_buildings=13,
    C_failures=23, C_attempts=1092, any_arm_failed_ABC=34,
    net_loss_gt5_count=42, net_loss_gt10_count=9, loss_known=1058,
    time_use='严格单一来源共同时间仅1个ABC；背景对无共同可靠时间；不新增效率结论',
    new_fusion=3040, reused_endpoints=236, endpoints=3276,
    new_physical_ABC=1014, prior_physical_ABC=78,
    interpretation='新的成员背景支持仍有多数图/楼升质，保留方向；未穷尽所有XYZ',
    evidence='structure_followup/background_gradient/EVENTS_COMPLETE.csv.gz'),
 dict(
    result_id='NEW_MATCHED_BACKGROUND_TARGET_PLUS_ONE', source_data='real_v2',
    classification='Manual结构三类，背景常规→较多转折', n=20, m=1,
    foreground_m=7, design='XYZ固定；两个D相差1人，D目标席位+1、源席位−1；六端点共同可评',
    registered=1448, valid=1397, images=39, buildings=15,
    background_A_change_Q=g.A_change_B8L2,
    background_B_change_Q=g.B_change_B8L2,
    background_C_change_Q=g.C_change_B8L2,
    net_advantage_low_Q=g.net_low_B8L2, net_advantage_high_Q=g.net_high_B8L2,
    net_advantage_change_Q=g.net_change_B8L2,
    net_advantage_change_D10=g.net_change_D10,
    net_weaker_images=23, net_weaker_buildings=11,
    time_use='六端点无可靠共同时间，不评价节时',
    new_fusion=0, interpretation='多数图/楼净优势减弱，主要B改善；C平均稍提高；4/13不是硬阈值',
    evidence='structure_followup/background_gradient/MATCHED_BACKGROUND_GRADIENT_PAIRS.csv.gz')]
for _,r in f.iterrows():
 rows.append(dict(result_id=f'FIXED_A_{r.source_role}_{int(r.m_from)}_to_{int(r.m_to)}',
   source_data='real_v2',classification='Manual结构三类',source_role=r.source_role,target_role=r.target_role,
   n=20,m=int(r.m_to-r.m_from),foreground_m_from=int(r.m_from),foreground_m_to=int(r.m_to),
   design='A固定，源/同类/目标块嵌套扩展；B和C各实际替换m_to-m_from人；五端点共同可评',
   registered=int(r.registered_paths),valid=int(r.common_scored_paths),
   images=int(r.C_change_images_evaluable),buildings=int(r.C_change_buildings_evaluable),
   background_A_change_Q=0,background_B_change_Q=r.B_change,background_C_change_Q=r.C_change,
   net_advantage_change_Q=r.net_advantage_change,
   C_change_positive_images=int(r.C_change_images_positive),C_change_positive_buildings=int(r.C_change_buildings_positive),
   net_advantage_change_positive_images=int(r.net_advantage_change_images_positive),net_advantage_change_positive_buildings=int(r.net_advantage_change_buildings_positive),
   new_fusion=0,interpretation='用于区分C自身变化、B自身变化和净优势；保留全部方向/规模，不声称单调人数效应',
   evidence='structure_followup/FIXED_A_PATHS_EXACT.csv.gz'))
pd.DataFrame(rows).to_csv(OUT/'新增规模与背景结果.csv',index=False,encoding='utf-8-sig')

lineage=[
 ('主源与合同','本轮接续','main cf053a6；真实v2；冻结引擎、参考与资格未改','MAIN_SOURCE.json','完成'),
 ('旧完整交付','实存恢复并保存','146031登记行、138244物理ABC；101092去重端点','STAGE01_ACTUAL_FILES.csv','完成'),
 ('11方法与26域组合','继承','保留旧分类与覆盖；本轮不重新全面搜类','integration/分类方案_采用总表.csv','保留'),
 ('Manual两种n20/m4角色','旧端点新共同支持分析','较快净Q+3.142/时间−1.565%；最高Q较慢+4.707/+7.165%','manual_qt_followup/ADOPTED_MATCHED_ABC_COMMON.csv','采用'),
 ('分类与连续QT10','旧端点新同候选比较','19896锚点实际成员相同；组织与解释价值成立，无额外数值收益','manual_qt_followup/CLASS_QT10_EXACT_IDENTITY.csv.gz','收尾'),
 ('类内连续选块','新分析，无新融合','104储备748个Z端点；m4 QT10相对均匀Z为−.419Q/−2.534%时间','manual_qt_followup/FINITE_SELECTION_INCREMENT_SUMMARY.csv','采用取舍'),
 ('固定A的m4→7','分母修正','五端点共同151路径：C+1.405、B+.111、净+1.294','structure_followup/FIXED_A_COMMON_DECOMPOSITION.csv','采用'),
 ('背景目标席位增加','新实验，3040端点补算','39图15楼；完整78×14背景；净优势−.841主要由B改善','structure_followup/background_gradient/GRADIENT_SUMMARY.csv','采用群体规律'),
 ('背景4/13界线','采用解释调整','旧67/11图仅1共同图；取消硬阈值，保留条件关联','structure_followup/OLD_BACKGROUND_WITHIN_IMAGE_ASSOCIATIONS.csv','已调整'),
 ('新背景时间','机会不足','严格三队单一来源仅1ABC，六端点无共同时间；不新增效率结论','structure_followup/background_gradient/ABC_QT_SUMMARY.csv','明确范围'),
 ('Semi新旧衔接','新分析，无新融合','同旧14格从+.153到+3.130；源块和D支持扩大解释主要差异','semi_followup/SUPPORT_DECOMPOSITION.csv','收尾'),
 ('Semi 7y-13','有限格完整枚举','固定目标Z；8源人35种分割×9个D=315物理ABC','semi_followup/CASE_7Y13_N12M4_SUPPORT_DECOMPOSITION.csv','机制采用'),
 ('外部新任务与全池巨量组合','未做','不称全池人员穷尽或新外部盲测；不影响当前v2用途收尾','../personnel_exchange_closure_20261022/integration/coverage/COVERAGE_FINAL_ZH.md','未覆盖范围')]
pd.DataFrame(lineage,columns=['对象','阶段身份','实际结果或范围','证据','本轮状态']).to_csv(OUT/'阶段来源与采用关系.csv',index=False,encoding='utf-8-sig')
print({'new_result_rows':len(rows),'lineage_rows':len(lineage),'new_fusion_in_this_script':0})
