"""Assemble adopted conditions from saved, explicitly matched estimands. No fusion."""
from pathlib import Path
import pandas as pd
import numpy as np
import json

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'personnel_exchange_closure_20261022'
OUT=ROOT/'integration';OUT.mkdir(exist_ok=True)
old=pd.read_csv(OLD/'integration/有效换类条件表.csv')
current=old.copy()
current['prior_research_stage']='personnel_exchange_closure_20261022'
current['current_read_main']='cf053a6e31d17393c0e8216ce15660fa37b8b7bb'
current['this_round_status']='继承完整事件与端点；未重复融合'
current['new_interpretation']=''
mc=pd.read_csv(ROOT/'manual_qt_followup/ADOPTED_MATCHED_ABC_COMMON.csv')
for _,r in mc.iterrows():
 key=f"MANUAL_{r.stage}_{r.direction};n{r.n};m{r.m}"
 mask=current.condition_id.eq(key)
 if not mask.any():continue
 for target,source in [('Q_B_minus_A','same_B8L2'),('Q_C_minus_A','cross_B8L2'),('Q_C_minus_B','net_B8L2'),('D10_B_minus_A','same_D10'),('D10_C_minus_A','cross_D10'),('D10_C_minus_B','net_D10')]:
  current.loc[mask,target]=r[source]
 current.loc[mask,'time_C_minus_B_common_pct']=r.net_recorded_time_geomean_pct
 for target,source in [('Q_net_positive_images','image_net_Q_positive'),('Q_net_known_images','image_net_Q_known'),('Q_net_positive_buildings','building_net_Q_positive'),('Q_net_known_buildings','building_net_Q_known')]:
  current.loc[mask,target]=r[source]
 for target,source in [('Q_net_positive_backgrounds','panel_net_Q_positive'),('Q_net_known_backgrounds','panel_net_Q_known'),('joint_quality_time_positive_images','image_net_both_Q_up_time_down'),('joint_quality_time_known_images','image_net_QT_known'),('joint_quality_time_positive_buildings','building_net_both_Q_up_time_down'),('joint_quality_time_known_buildings','building_net_QT_known')]:
  current.loc[mask,target]=r[source]
 current.loc[mask,'this_round_status']='本轮用完整事件重聚合共同ABC的有符号变化和双优比例；0新融合'
 current.loc[mask,'new_interpretation']='净Q、净时间和双优比例统一到共同ABC；对称量及全时间原字段继续独立保留'
for key in ['STR_M7_BG_low_0_to_1_3','STR_M7_BG_middle_1_3_to_2_3']:
 mask=current.condition_id.eq(key)
 current.loc[mask,'new_interpretation']='旧跨图条件关联保留；67/11图仅1共同图，不采用目标类≤4作为硬门槛。新固定XYZ背景枚举支持多数图边际净收益减弱，主要B改善。'
 current.loc[mask,'adoption']='作为旧分层关联；背景用途由本轮同图同XYZ结果解释，非硬阈值'
current.to_csv(OUT/'全部43条件_继承与采用更新.csv',index=False,encoding='utf-8-sig')

keys=[
 'MANUAL_A_q_up__faster;n20;m4', 'MANUAL_B_q_up__slower;n20;m4',
 'STR_MAIN_M4','STR_MAIN_M7','SEMI_n12_m4','SEMI_n14_m3','SEMI_n16_m3',
 'MANUAL_A_q_up__faster;n20;m3','MANUAL_A_q_up__faster;n20;m5','MANUAL_A_q_up__faster;n20;m6','SEMI_n14_m4'
]
rows=[]
for key in keys:
 r=current.loc[current.condition_id.eq(key)].iloc[0]
 time_val=r.time_C_minus_B_common_pct
 time_note='同一三队共同可评分/有记录时间支持；C/B几何平均比'
 if not np.isfinite(time_val):
  time_val=r.time_pct
  time_note=f"独立可比时间子集，{r.get('time_images',np.nan)}图/{r.get('time_buildings',np.nan)}楼；不能把全质量支持当同时节时支持"
 role={'STR_MAIN_M4':('常规转折表达','较多转折与短细节表达'),'STR_MAIN_M7':('常规转折表达','较多转折与短细节表达')}.get(key)
 if role is None:
  if key.startswith('MANUAL_B'):role=('相对较低历史Q、较快源角色','目标折最高历史Q、相对较慢角色')
  elif key.startswith('MANUAL'):role=('相对较低历史Q、较慢源角色','较高历史Q且相对更快的角色')
  else:role=('Semi常规源角色','Semi楼外较高历史Q、相对更快角色')
 advice={'MANUAL_A_q_up__faster;n20;m4':'主采用：质量与时间兼顾；类内QT10可进一步省时但对均匀目标块有小Q代价',
 'MANUAL_B_q_up__slower;n20;m4':'主采用：时间换质量；限最高训练Q目标语义',
 'STR_MAIN_M4':'主采用：覆盖较广的结构角色替换',
 'STR_MAIN_M7':'主采用：容量允许时的较大结构块；无背景4人硬阈值',
 'SEMI_n12_m4':'Semi首选：平均升质与省时；具体成员低尾保留',
 'SEMI_n14_m3':'Semi广覆盖补充：多数图片改善，不能称多数背景升质',
 'SEMI_n16_m3':'Semi较大团队效率补充；建筑升质仅2/4',
 'MANUAL_A_q_up__faster;n20;m3':'更广容量补充；净升质小，类内按Q选块有小耗时换质量价值',
 'MANUAL_A_q_up__faster;n20;m5':'有益补充；同跨幅度分离弱',
 'MANUAL_A_q_up__faster;n20;m6':'有限容量积极结果；目标块唯一，类内可互换性不可估',
 'SEMI_n14_m4':'省时补充；2/4图升质，质量方向不称多数'}[key]
 def ratio(num,den):
  return '' if pd.isna(num) or pd.isna(den) else f'{int(num)}/{int(den)}'
 rows.append({'条件ID':key,'分类方案':r.classification,'输入条件':r.input_condition,'评价条件':r.evaluation_condition,'层级':r.class_level,'源角色':role[0],'目标角色':role[1],
  'n':int(r.n),'m':int(r.m),'替换比例':r.m/r.n,'类别席位变化':f'源类−{r.m};目标类+{r.m};共同D={r.n-r.m}',
  '严格ABC至少池人数':int(r.n+2*r.m),'人员域':r.personnel_domain,'背景规则':r.background_rule,
  '登记事件行':r.registered_event_rows,'物理ABC':r.physical_ABC,'共同ABC可评行':r.common_ABC_rows,'图片':r.images,'建筑':r.buildings,'背景':r.backgrounds,
  'Q_B-A':r.Q_B_minus_A,'Q_C-A':r.Q_C_minus_A,'Q_C-B':r.Q_C_minus_B,'D10_B-A':r.D10_B_minus_A,'D10_C-A':r.D10_C_minus_A,'D10_C-B':r.D10_C_minus_B,'同类绝对Q变化':r.same_abs_Q,'跨类绝对Q变化':r.cross_abs_Q,'绝对变化定义':r.abs_cross_definition,
  '净Q改善图片':ratio(r.Q_net_positive_images,r.Q_net_known_images),'净Q改善建筑':ratio(r.Q_net_positive_buildings,r.Q_net_known_buildings),
  '净Q改善背景':ratio(r.get('Q_net_positive_backgrounds'),r.get('Q_net_known_backgrounds')),
  '原队A失败端点':ratio(r.A_failed_unique_endpoints,r.A_unique_endpoints),'同类B失败端点':ratio(r.B_failed_unique_endpoints,r.B_unique_endpoints),
  'C比B记录时间变化_pct':time_val,'时间支持':time_note,'目标C失败端点':ratio(r.C_failed_unique_endpoints,r.C_unique_endpoints),
  '较大损失_5分_层级比例':r.loss_gt5_weighted,'较大损失_10分_层级比例':r.loss_gt10_weighted,'损失定义':r.loss_contrast,
  '分项比较定义':r.components_contrast,'三维代理变化':r.component_IoU3D100,'底面IoU变化':r.component_iou_2d,'底点角距变化_deg':r.component_S_bottom_deg,'自身正交方向残差变化_deg':r.component_dir,
  '均高误差变化':r.component_Hmean,'中心高度误差变化':r.component_Hcenter,'遗漏变化':r.component_omission,'外扩变化':r.component_extension,'节点变化':r.component_nodes,
  '转折变化':r.component_fusion_turn_n,'短转折边变化':r.component_fusion_short_turn_edges,'近共线冗余变化':r.component_fusion_redundancy_n,'参考节点召回变化_9deg':r.component_ref_node_recall_9,'参考边召回变化_9deg':r.component_ref_edge_recall_9,
  '顶界平均y变化_px':r.component_top_y_mean_px,'底界平均y变化_px':r.component_bottom_y_mean_px,'底面面积变化_h2':r.component_geometry_area_h2,'均高变化_h':r.component_height_mean_h,'质心x变化_h':r.component_centroid_x_h,'质心z变化_h':r.component_centroid_z_h,
  '成员与折标签':r.class_members_reference,'完整事件':r.exact_events_file,'容量表':r.capacity_reference,'成员覆盖':r.member_coverage_note,'采用建议':advice,'本轮身份':r.this_round_status})
pd.DataFrame(rows).to_csv(OUT/'推荐条件_阅读表.csv',index=False,encoding='utf-8-sig')

definition=pd.read_csv(OLD/'classification/CLASS_DEFINITIONS.csv')
definition['label_usage']='ALL描述；目标用途须用对应建筑外标签和语义角色'
definition.to_csv(OUT/'分类定义与完整ALL成员.csv',index=False,encoding='utf-8-sig')
catalog=pd.read_csv(OLD/'classification/CLASSIFICATION_SCHEME_CATALOG.csv')
catalog['current_adoption']='保持原阶段和独立方法身份；本轮不重新全面搜索'
catalog.loc[(catalog.method=='V3_JOINT_QT') & catalog.evaluation_condition.eq('manual'),'current_adoption']='优先n20/m4较快高Q与最高Q较慢两种角色；连续Q/T同支持衔接已完成'
catalog.loc[(catalog.method=='V3_BEHAVIOR') & catalog.evaluation_condition.eq('manual'),'current_adoption']='结构解释+n20/m4或m7；新增固定XYZ背景规律，取消4/13硬界线'
catalog.loc[(catalog.method=='V3_JOINT_QT') & catalog.evaluation_condition.eq('semi'),'current_adoption']='优先n12/m4，n14/m3广覆盖；新旧收益来源已解释'
catalog.to_csv(OUT/'分类方案_采用总表.csv',index=False,encoding='utf-8-sig')
print(json.dumps({'inherited_conditions':len(current),'reader_recommendations':len(rows),'class_definition_rows':len(definition),'method_families':len(catalog),'new_fusion_in_this_script':0},ensure_ascii=False))
