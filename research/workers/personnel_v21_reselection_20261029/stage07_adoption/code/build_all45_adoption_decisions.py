#!/usr/bin/env python3
"""Adoption ledger using completed results only; no classifier/fusion fitting."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
W=Path(__file__).resolve().parents[2];O=W/'stage07_adoption'
registry=pd.read_csv(W/'stage02/CURRENT_45_METHOD_FORMATION_REGISTRY.csv')
labels=pd.read_csv(W/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
screen=pd.read_csv(W/'stage05/ALL7356_CONDITIONS_KEY_RESULTS.csv')
raw=pd.read_csv(W/'raw_similarity/MANUAL_COMMON45_ALL_METHOD_RESULTS.csv')
raw=raw[raw.subset.eq('same_corner_count')&raw.metric.eq('geometry_pair_angle')]
gsummary=pd.read_csv(W/'analysis/global_screen_summary/METHOD_GRID_RESULTS.csv')
fsummary=pd.read_csv(W/'analysis/focused_summary/ALL_DIRECTION_N_M_RESULTS.csv.gz',low_memory=False)
primary=pd.read_csv(W/'composition/primary_manual45/ALL_METHOD_COMPARISON.csv')
other=pd.read_csv(W/'composition/other_targets_manual45/ALL_METHOD_COMPARISON.csv')
primary=primary[primary.summary_axis.eq('all')];other=other[other.summary_axis.eq('all')]
stage_events={}
for stage in ['global_screen','focused','refinement_baseline']:
 p=W/f'experiment/{stage}_design/EVENTS_EXACT.csv.gz'
 stage_events[stage]=pd.read_csv(p,usecols=['event_id','pool_id','image','building','method','n','m','background_id','block_id','A_team_key','B_team_key','C_team_key'],low_memory=False)

# Editorial choices anchored to explicit evidence fields below; non-main never means invalid.
choices={
'OPPJOINT_K3':('主方法_粗层','大块质量差异；整体成员角色','与K4同一冻结树的三粗层；精确父方向共同56池已承担约+8.06净Q，不把它重复归为K4细分收益。'),
'OPPJOINT_K4':('主方法_细层','可操作方向；时间与成员组织；有限父内用途','与K3共同采用为一家族；n12/m6主方向全部跨K3父类。细层辨识长记录时间小组，不宣称新产生+8分。'),
'TARGET_DSTRUCT_K3':('主文结构补充','可见标法；较大转折块；背景/门槛机制','同点数原答分离明确，重点规模/背景与真实RGB短折返机制完整；与联合类分工，不直接输入Q/T。'),
'DSTRUCT_K3':('保留旧主基线','新旧标签与难度结构对照；定位/高度','已重新比较并重点扩展，仍有多数方向支持；不再固定18/7为唯一条件，保留原发现不整体否决。'),
'RFUSE_GEOM_K2':('主文反推补充','实际融合响应反推；3—4人目标块','重点扩展支持小块用途。ALL少数类4人，原答同点数几何平均差小，故不把它写成最强可见标法大类。'),
'MSDGEOM_SCOPE_K4':('主文跨条件补充','Manual+Semi+scope历史；Manual尺度/构成','共同面板和重点ABC均有竞争力，保留跨条件域用途；不能据Manual效果冒充Semi验证，也不等同OPPJOINT输入。'),
'OPPGEOM_K3':('主文几何机制补充','位置/尺度响应；同点数定位变化；人数门槛','有大覆盖重点方向和定位/固定XYZ反转完整病例；与结构主补充分工，未另设统一人员主体系。'),
'V3_JOINT_QT_COARSE':('保留整体配比用途','有限完整配比的质量—时间解释；历史选队/策略接口','共同成员面板Q与时间解释强，保留旧阶段身份；不把配比方差解释或旧选队收益替代本轮严格ABC。'),
'V3_JOINT_QT_FINE':('保留但当前增量有限','逐折细标签和历史接口','当前共同有限面板与粗层Q/时间解释相同；ALL+22折有22折分区相同，另1折仍保存，不把新名字算新类效用。'),
'DJOINT_K4':('有竞争力的旧联合备选','质量—时间方向；已重点扩展','n10/m7、n20/m5实际有有益方向，不能判无效。主文统一使用目标机会历史OPPJOINT层级，避免两套近似联合主体系重复叙事。'),
'OPPSTRUCT_K3':('保留机会结构备选','无人工难度目标的结构机会响应','已有重点扩展，完整配比结构解释优于部分旧结构基线；主文结构例证集中TARGET_DSTRUCT，不否定此机会路线。'),
'Q_MEDIAN2':('必要质量基线','质量中位数二分；双向换类对照','容量均衡且广泛有效，但几何/时间解释较少；共同56池大块分离小于联合家族，是实际基线而非废弃方法。'),
'Q_HARD_MEDIAN2':('必要困难质量基线','困难历史Q二分；难度域对照','已广筛和完整配比，保留困难域的可解释对照；不因未追加重点成员背景就称无效。'),
'DSTRUCT_K2':('保留粗度敏感性','结构二分；大目标块对照','二分有实际分离信号，但合并简化/常规角色；三类结构补充更便于解释，二分不另立主方法。'),
'DSTRUCT_K4':('保留细分候选','固定父类细分；结构/高度配比','完整配比有细分增量；ALL新增小类4人，较大同类对照容量受限，细层效果不能由配比方差增加单独认定。'),
'DSTRUCT_AXIS2':('保留连续轴分组基线','结构轴的均衡二分','ALL30/29便于大块比较；保留其轴阈值对照，未用均衡人数替代更可解释的聚类角色。'),
'DBOUNDARY_AXIS2':('保留定位轴基线','定位/尺度轴二分','容量均衡；同点数平均原答角距差较小且图片正向比例有限，仍保留其它位置分项结果，不作为主要人员分型。'),
'DBOUNDARY_K2':('已比较_定位候选','上下界与尺度的二分差异','ALL目标小类6人，部分大块容量不足；重点定位解释采用已扩展的OPPGEOM，不将此候选未扩展写成无效。'),
'DBOUNDARY_K3':('已比较_定位候选','三个定位/尺度角色','原答与配比有区别；与OPPGEOM定位用途重叠，本轮没有同等成员背景扩展，保留全比较而不另增主体系。'),
'DBOUNDARY_K4':('保留定位细分候选','定位/尺度细构成','完整配比解释高于较粗同族，但细类别更多也会增加样本内解释；缺少对应重点用途增量，不仅按这一比例采用。'),
'DJOINT_K2':('保留旧联合粗度对照','Manual质量—时间与结构二分','广筛存在清楚差异，不能因未选为主方法否定；作为旧历史范围/类数对照，与新OPPJOINT来源分开。'),
'DJOINT_K3':('保留旧联合对照','Manual联合三类；配比解释','共同面板与原答均有信号；当前主文用OPPJOINT真实三粗四细组织，保留本法完整历史与新版结果。'),
'MSDGEOM_K2':('保留跨条件域对照','Manual+Semi几何历史二分','与带scope方法作域对照；本轮未选定需要另立的重点方向，所有已算方向及符号保留。'),
'MSDGEOM_K3':('保留跨条件域对照','Manual+Semi几何三类','原答/配比有区别，ALL出现5/6人小类；不要求各类均衡，当前用途与scope补充重叠。'),
'MSDGEOM_K4':('保留跨条件备选','跨条件几何细构成','共同面板Q解释接近scope四类，不能称无效；scope四类有重点ABC扩展，因此主文优先其具体用途。'),
'MSDGEOM_SCOPE_AXIS2':('保留联合轴基线','跨条件scope轴均衡二分','ALL30/29为大块轴阈值对照；保留总体比较，不把它与非scope结构轴混同。'),
'MSDGEOM_SCOPE_K2':('保留scope粗度对照','跨条件scope粗角色','二类已有原答与融合分离；主文以已扩展K4展示特定尺度方向，其余粒度保留。'),
'MSDGEOM_SCOPE_K3':('保留scope粒度对照','跨条件scope三类','与二/四类作用重叠，ALL小类4人限制部分同类全块对照；并未因小类而删除其它合法方向。'),
'TARGET_DSTRUCT_K2':('保留目标感知粗度对照','合法全部目标的结构二分','有支持方向且可形成较大块；三类增加简化/常规解释，二类用于粒度敏感性，不认定无效。'),
'TARGET_DSTRUCT_K4':('保留目标感知细分','困难结构父类内细分','完整配比增量存在，ALL多出4人小类；主文三类已有充分结构解释，细分是否有用按父内结果另报。'),
'OPPSTRUCT_K2':('保留机会结构粗度对照','可计算机会下的结构二分','广筛多条件有分离，合并角色后更粗；保留与人工难度结构路线的对照。'),
'OPPSTRUCT_K4':('保留机会细分候选','机会结构细构成','配比解释增加但不是普遍互换证据；已保存固定父类与细分结果，暂不额外增加主文分类。'),
'OPPSTRUCT_K5':('保留探索细分','机会结构更细分支','ALL有1人分支，不能估计该分支同类换人；其余大类合法实验仍保留。配比样本内小幅增量不足单独支撑新主类别。'),
'OPPGEOM_K2':('保留几何粗度对照','机会几何二分','广筛有支持信号；三类能解释中间尺度角色与已有机制，二类保留作简化方案。'),
'OPPGEOM_K4':('保留几何细分候选','位置/尺度细分','ALL将小端分成4/3人，较大类内对照机会减少；没有另增主文的必要解释，结果不是无效。'),
'OPPJOINT_K2':('主家族粗度对照','极简质量方向；二分容量','48/8二分已有差异；三类进一步区分常规/简化或时间角色，四类补成员组织，二类保留敏感性。'),
'RFUSE_GEOM_K3':('保留反推粒度对照','响应三类与细构成','总体原答几何分离较弱但有融合用途信号；现有明确反推用途由K2小块体现，不把三类未扩展判成失败。'),
'RFUSE_GEOMQ_K2':('保留反推目标消融','几何+质量响应二分','加Q目标后部分折名单改变；已完成广筛/配比，未形成需要替换主反推补充的证据，保留全部结果。'),
'RFUSE_GEOMQ_K3':('保留反推目标消融','几何+质量响应三类','同点数原答分离及共同面板解释均有实际数值；目的与几何反推不同，不按最大Q方向宣称优胜。'),
'TARGET_RFUSE_GEOM_K2':('与反推补充等价保留','目标等权反推；与RFUSE_GEOM_K2同分区','ALL及22LOBO分区与RFUSE_GEOM_K2完全相同；这是再权重未改名单的实际结果，不计作第二套独立有效分类。'),
'TARGET_RFUSE_GEOM_K3':('保留目标权重敏感性','目标等权几何响应三类','与旧权重部分名单/构成解释不同，保存新旧转移；没有新增同等力度重点验证，作为权重敏感性保留。'),
'TARGET_RFUSE_GEOMQ_K2':('保留目标权重敏感性','目标等权几何+质量响应','ALL少数类由旧响应方案的4人变7人，实际容量改变；已算方向保留，不因未入主文否定新的可行范围。'),
'TARGET_RFUSE_GEOMQ_K3':('保留目标权重敏感性','目标等权响应三类','主目标与其它合法空间均有完整配比/广筛；原答同点数几何均值差较小，主要作为响应和权重对照。'),
'V3_BEHAVIOR_COARSE':('保留历史结构/策略用途','旧V3标法粗类；自然进入策略接口','完整配比和原答有信号，旧进入策略与当前分类保持身份；不重命名为DSTRUCT或OPPJOINT验证。'),
'V3_BEHAVIOR_FINE':('保留有限细分用途','旧V3标法细类；折内成员差异','ALL名单未增加类数，23折有17折与粗类同分区；其它折和配比小幅增量保存，不把编号细化当普遍新类型。'),
}
assert set(choices)==set(registry.method),(set(registry.method)-set(choices))

def mix_value(frame,method,metric,support='shared_known',time='not_time'):
 x=frame[frame.method.eq(method)&frame.metric.eq(metric)&frame.support.eq(support)&frame.time_source.eq(time)]
 return x.iloc[0]if len(x)else None
rows=[];focus_examples=[]
for rr in registry.to_dict('records'):
 method=rr['method'];status,use,why=choices[method];g=screen[screen.method.eq(method)];valid=g[(g.B8L2_gap_valid_images>=8)&(g.B8L2_gap_valid_buildings>=4)]
 row={k:rr[k]for k in ['method','route','input_conditions','source_stage','classification_scope','ALL_known_workers','ALL_unknown_workers','ALL_k','ALL_class_sizes','uses_Q_as_classification_input','uses_T_as_classification_input','uses_scope_as_input']}
 row.update(adoption_status=status,retained_use_zh=use,adoption_reason_zh=why,not_main_is_not_invalid=True,screen_conditions=len(g),supported_screen_conditions=len(valid),supported_Q_gap_positive_conditions=int(valid.B8L2_gap_mean_image.gt(1e-8).sum()),supported_Q_gap_negative_conditions=int(valid.B8L2_gap_mean_image.lt(-1e-8).sum()),supported_Q_gap_near_zero_conditions=int(valid.B8L2_gap_mean_image.abs().le(1e-8).sum()),supported_Q_gap_median_across_cells=valid.B8L2_gap_mean_image.median(),screen_summary_scope='all registered directions,n,m,primary and other targets; cell median is descriptive, not matched-method ranking')
 allteams=set();allevents=set();allpools=set();allimages=set();allbuildings=set()
 for stage,ev in stage_events.items():
  e=ev[ev.method.eq(method)];row[stage+'_events']=len(e);row[stage+'_pools']=e.pool_id.nunique();row[stage+'_images']=e.image.nunique();row[stage+'_buildings']=e.building.nunique();row[stage+'_n_values']='|'.join(str(v)for v in sorted(e.n.unique()));row[stage+'_m_values']='|'.join(str(v)for v in sorted(e.m.unique()));row[stage+'_backgrounds']=e.background_id.nunique();row[stage+'_blocks']=e.block_id.nunique()
  allevents.update(e.event_id);allpools.update(e.pool_id);allimages.update(e.image);allbuildings.update(e.building)
  for arm in 'ABC':allteams.update(e[arm+'_team_key'])
 row.update(strict_events_union_selected_stages=len(allevents),unique_teams_union_selected_stages=len(allteams),images_union_selected_stages=len(allimages),buildings_union_selected_stages=len(allbuildings),strict_scope='global_screen+focused+refinement_baseline; fixed-A paths, direct AC, leave-member and parent-only panels separately referenced')
 fs=fsummary[fsummary.method.eq(method)]
 if len(fs):
  example=fs.sort_values(['B8L2_gap_valid_images','buildings','n'],ascending=[False,False,False]).iloc[0]
  erow={k:example[k]for k in ['method','condition','scope','n','m','role_direction','events','images','buildings','B8L2_within_mean_image','B8L2_cross_mean_image','B8L2_gap_mean_image','B8L2_CA_mean_image','B8L2_CB_mean_image','B8L2_gap_valid_images','B8L2_gap_positive_images','B8L2_gap_valid_buildings','B8L2_gap_positive_buildings','record_time_CB_pct_source_matched_mean_image','record_time_CB_pct_source_matched_valid_images']}
  erow['display_selection']='largest image support, not maximum Q/gap; full direction table preserved';focus_examples.append(erow)
  row['focused_broad_coverage_example']=f"{example.role_direction};n={int(example.n)};m={int(example.m)};gap={example.B8L2_gap_mean_image:.3f};CB={example.B8L2_CB_mean_image:.3f};gap_positive={int(example.B8L2_gap_positive_images)}/{int(example.B8L2_gap_valid_images)}"
 else:row['focused_broad_coverage_example']='no focused32 extension; targeted parent comparison separately counted'if method=='OPPJOINT_K3'else'no focused32 extension; completed screen and finite mixtures retained'
 gr=gsummary[gsummary.method.eq(method)]
 for metric in ['A_failed_events','B_failed_events','C_failed_events','ABC_scored_events']:row['global_'+metric]=int(gr[metric].sum())
 rx=raw[raw.method.eq(method)].iloc[0]
 for k in ['image_within','image_cross','image_gap','images','buildings','images_cross_larger','buildings_cross_larger']:row['raw_same_count_angle_'+k]=rx[k]
 for scope,frame in [('primary',primary),('other_targets',other)]:
  for metric,name in [('B8L2','Q'),('D10','D10'),('fusion_turn_n','turn'),('geometry_area_h2','area'),('height_mean_h','height'),('failure','failure')]:
   mix=mix_value(frame,method,metric)
   row[f'mixture_{scope}_{name}_between_share']=mix.between_share if mix is not None else np.nan
   if metric=='B8L2':
    for k in ['panels','pools','images','buildings','valid_team_links','constant_panels']:row[f'mixture_{scope}_shared_{k}']=mix[k]if mix is not None else 0
  t=frame[frame.method.eq(method)&frame.metric.eq('recorded_time_total_seconds')&frame.support.eq('shared_known')]
  row[f'mixture_{scope}_time_by_source_json']=json.dumps({str(z.time_source):dict(between_share=z.between_share,panels=int(z.panels),images=int(z.images))for z in t.itertuples()},ensure_ascii=False)
 row['actual_findings_zh']=f"广筛{len(g)}个角色/n/m/空间条件，其中{len(valid)}个达8图4楼支持；这些条件幅度差正/负/近零={row['supported_Q_gap_positive_conditions']}/{row['supported_Q_gap_negative_conditions']}/{row['supported_Q_gap_near_zero_conditions']}。共同人员同点数原答角距差{rx.image_gap:.3f}°，{int(rx.images_cross_larger)}/{int(rx.images)}图类间更大。共同有限面板Q配比间占比{row['mixture_primary_Q_between_share']:.2%}，用途与ABC分开。"
 paths=['stage02/CURRENT_45_METHOD_FORMATION_REGISTRY.csv','classification/MAIN45_LABELS_ALL_LOBO.csv.gz','stage05/ALL7356_CONDITIONS_KEY_RESULTS.csv','experiment/global_screen_design/EVENTS_EXACT.csv.gz','analysis/global_screen_summary/ALL_DIRECTION_N_M_RESULTS.csv.gz','raw_similarity/MANUAL_COMMON45_ALL_METHOD_RESULTS.csv',f'composition/primary_manual45/by_method/{method}/CONFIGURATION_COUNTS.csv.gz',f'composition/primary_manual45/by_method/{method}/CONFIGURATION_DISTRIBUTIONS.csv.gz',f'composition/other_targets_manual45/by_method/{method}/SUMMARY.csv']
 if len(fs):paths+=['experiment/focused_design/EVENTS_EXACT.csv.gz','analysis/focused_summary/ALL_DIRECTION_N_M_RESULTS.csv.gz']
 if method in ['OPPJOINT_K3','OPPJOINT_K4','Q_MEDIAN2']:paths+=['analysis/joint_baseline_comparison/SAME_SUPPORT_COMPARISON.csv']
 if method=='OPPJOINT_K4':paths+=['analysis/fine_increment/oppjoint_small_slow/SMALL_SLOW_ROLE_SUMMARY.csv','stage07_adoption/PERSONNEL_ROLES_AND_MEMBERS_ZH.md']
 if method in ['TARGET_DSTRUCT_K3','OPPGEOM_K3','OPPJOINT_K4']:paths+=['stage06_cases/CASE_MECHANISMS_ZH.md']
 if method.startswith('V3_'):
  row['semi_own_label_results']='composition/primary_semi4/ALL_METHOD_COMPARISON.csv;composition/other_targets_semi4/ALL_METHOD_COMPARISON.csv'
  paths+=['composition/semi_mixture_results/README.md']
 else:row['semi_own_label_results']='not claimed from this Manual45 ledger'
 for p in paths:assert (W/p).is_file(),(method,p)
 row['evidence_paths']=';'.join(paths);row['evidence_filter']='method='+method;row['new_old_label_changes_reference']='classification/OLD_V2_TO_CURRENT_V21_WORKER_LABEL_TRANSITIONS.csv.gz;classification/NEW_TO_OFFICIAL_BASELINE_WORKER_TRANSITIONS.csv.gz;classification/target_rfuse/OLD_EXTENDED_TO_TARGET_EQUAL_WORKER_TRANSITIONS.csv.gz';rows.append(row)
out=pd.DataFrame(rows);assert len(out)==45
out.to_csv(O/'ALL45_METHOD_ADOPTION_DECISIONS.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(focus_examples).to_csv(O/'METHODS_FOCUSED_BROAD_COVERAGE_EXAMPLES.csv',index=False,encoding='utf-8-sig')
# Exact equivalence of a few meaningful controls, including differing fine folds.
eq=[]
for aa,bb in [('V3_BEHAVIOR_COARSE','V3_BEHAVIOR_FINE'),('V3_JOINT_QT_COARSE','V3_JOINT_QT_FINE'),('RFUSE_GEOM_K2','TARGET_RFUSE_GEOM_K2'),('RFUSE_GEOM_K2','RFUSE_GEOMQ_K2')]:
 a=labels[labels.method.eq(aa)][['worker_id','heldout_building','class_id','known']];b=labels[labels.method.eq(bb)][['worker_id','heldout_building','class_id','known']];j=a.merge(b,on=['worker_id','heldout_building'],suffixes=['_a','_b'])
 for fold,g in j.groupby('heldout_building'):
  k=g[g.known_a&g.known_b];same=bool(g.known_a.equals(g.known_b)and k.groupby('class_id_a').class_id_b.nunique().max()==1 and k.groupby('class_id_b').class_id_a.nunique().max()==1)
  eq.append(dict(method_a=aa,method_b=bb,heldout_building=fold,same_known_support=bool(g.known_a.equals(g.known_b)),same_partition_ignoring_ids=same,known_both=len(k)))
pd.DataFrame(eq).to_csv(O/'METHODS_EXACT_PARTITION_EQUIVALENCE.csv',index=False,encoding='utf-8-sig')
print(json.dumps(dict(methods=len(out),screen_conditions=len(screen),supported_conditions=int(((screen.B8L2_gap_valid_images>=8)&(screen.B8L2_gap_valid_buildings>=4)).sum()),focused_methods=len(focus_examples),new_fits=0,new_fusions=0),ensure_ascii=False))
