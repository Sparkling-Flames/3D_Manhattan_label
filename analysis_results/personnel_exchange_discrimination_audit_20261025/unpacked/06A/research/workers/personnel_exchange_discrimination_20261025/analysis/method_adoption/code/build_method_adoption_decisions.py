#!/usr/bin/env python3
"""Finite adoption ledger for the 31 actually measured method instances.

Uses completed summaries and frozen labels only. It does not change labels,
search parameters, membership, qualification, scoring, or run fusion.
"""
from pathlib import Path
import hashlib,json
import pandas as pd

ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'analysis'
S='analysis/screen/METHOD_N_M_COMPARISON.csv'
C='analysis/confirm/METHOD_N_M_COMPARISON.csv'
R='analysis/confirm/SEMANTIC_ROLE_COMPARISON.csv'
RC='analysis/reverse_confirm/REVERSE_BRANCH_COMPARISON.csv'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(d,p):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);d.to_csv(p,index=False,encoding='utf-8-sig')

specs=[]
def add(method,family,inputs,status,use,reason,increment,source=S,n=20,m=6,role=None,shape='geometry_bev_distance'):
 specs.append(dict(method=method,family=family,input_conditions=inputs,adoption_status=status,retained_use=use,
  adoption_reason=reason,fine_increment_judgment=increment,source=source,n=n,m=m,role=role,shape=shape))

# New forward families: conservative about claims, affirmative about supported uses.
add('DSTRUCT_K2','Manual难度结构','Manual','保留粗类解释','实际转折/短边表达；粗结构对照',
 '原答中困难图非冗余转折、短边及同点数上下界差异有重复证据；本轮更具体的融合角色由K3承接。',
 'K2是粗层；K3主要帮助组织不同源角色，并非已证明所有细类普遍更好。')
add('DSTRUCT_K3','Manual难度结构','Manual','主推荐','同图大块区分；定向升质；固定块人数路径',
 '保留楼18/7高历史Q且相对更快、更多转折角色：同/跨3.438/6.386，31/40图10/10楼跨类更大；另有严格n10至21及直接AC至n28。',
 '采用具体源→目标角色；不把其它方向或K4额外细分一并升为主推荐。',R,18,7,'higher_Q|faster|more_turns')
add('DSTRUCT_K4','Manual难度结构','Manual','保留探索细层','结构细节解释候选',
 '筛查有正信号，但也有负条件；没有比K3更完整的保留楼具体角色与规模链。',
 '本轮未证明固定父类后新增细分的普遍增量；不因类数多而优先。')
add('DSTRUCT_AXIS2','Manual难度结构轴','Manual','保留透明对照','困难非冗余转折连续轴的中位离散化',
 '为均衡容量和可解释单轴提供对照；筛查部分大块有区分，但未进入本轮保留楼扩展。',
 '不属于Ward细分；不能从其个别高均值推出优于结构K3。')

add('DBOUNDARY_K2','Manual难度位置尺度','Manual','保留探索解释','有符号上下界、面积/高度响应',
 '可描述位置/尺度历史差异；筛查的高Q差条件支持较少，当前定位证据采用K3和轴切分更清楚。',
 '不将Q弱等同于位置类无效；尚无K2独立广覆盖融合用途确认。')
add('DBOUNDARY_K3','Manual难度位置尺度','Manual','保留形状补充','上下界及质心几何差异',
 '保留楼18/7 Q同/跨4.058/4.000，顶点角距离却为0.440/0.550度，41/61图7/9楼跨类更大；质量与形状用途分开。',
 '具体位置用途成立；未证明该细层一般提高Q区分。',C,18,7,None,'geometry_top_angle')
add('DBOUNDARY_K4','Manual难度位置尺度','Manual','保留探索细层','位置/尺度细分候选',
 '筛查未形成比K3/轴切分更清楚的已扩展用途，保留全部正负配置。',
 '额外细分的重复用途未建立，不宣称所有细分无效。')
add('DBOUNDARY_AXIS2','Manual难度位置尺度轴','Manual','保留形状补充','大比例替换的质心位移',
 '保留楼12/10 Q幅度比1.042，但质心位移同/跨0.0689/0.0966摄像机高度单位，18/27图7/9楼支持跨类更大。',
 '这是方向轴离散化用途；不作为质量升降主分类。',C,12,10,None,'geometry_centroid_distance')

add('DJOINT_K2','Manual结构位置QT联合','Manual','保留探索粗层','结构/位置与质量时间角色解释',
 '原答解释保留；部分筛查强信号来自较少图片，尚未形成独立保留楼主条件。',
 '不据单个高效应量宣布最佳；K4具体角色已有更直接用途证据。')
add('DJOINT_K3','Manual结构位置QT联合','Manual','保留竞争候选','联合角色及大块构成解释',
 '筛查有多个正向幅度条件，但本轮没有独立扩展到与K4同样的角色链。',
 '未做足够同父类配平比较，不能断言K4普遍优于K3。')
add('DJOINT_K4','Manual结构位置QT联合','Manual','保留条件用途','历史较高Q且较慢、更多转折方向',
 '保留楼20/6该角色同/跨3.412/5.501，36/48图9/10楼跨类更大，CA约+3.546；较快角色没有同样的质量效应。',
 '有用的是具体质量时间角色，不是所有四类方向均成立。',R,20,6,'higher_Q|slower|more_turns')

add('MSDGEOM_K2','ManualSemi难度几何联合','Manual+Semi','保留探索粗层','跨条件结构与上下界历史',
 '与旧XCOND不同，加入Manual难度响应；筛查有条件信号，但没有形成当前主确认路径。',
 '联合两条件本身不保证融合更可区分；保留与scope家族的参照身份。')
add('MSDGEOM_K3','ManualSemi难度几何联合','Manual+Semi','保留探索细层','跨条件结构角色候选',
 '部分条件均值正向，图间支持并非始终占多数；原答表达用途仍保留。',
 '未确认比粗层新增的可重复融合增量。')
add('MSDGEOM_K4','ManualSemi难度几何联合','Manual+Semi','保留探索形状候选','跨条件几何与大团队形状差异',
 '筛查20/6的底面几何幅度比约2.295，质量幅度比约1.348；仍是筛查发现，未在本轮保留楼复核。',
 '保留特定形状信号，不用小类容量或非普遍升质直接删除。')

add('MSDGEOM_SCOPE_K2','ManualSemiScope难度联合','Manual+Semi+scope','保留粗类替换备选','大块区分与定向质量',
 '保留楼10/7全登记方向同/跨6.087/9.367，35/42图7/8楼跨类更大；粗分本身已有用途。',
 'K4不能被表述为全面胜过K2；两者容量和角色不同。',C,10,7)
add('MSDGEOM_SCOPE_K3','ManualSemiScope难度联合','Manual+Semi+scope','保留探索细层','联合角色解释候选',
 '筛查有较强条件，但部分极高均值只涉及很少图片；本轮主扩展为K2/K4。',
 '未确认相对K2或K4的新增固定父类用途。')
add('MSDGEOM_SCOPE_K4','ManualSemiScope难度联合','Manual+Semi+scope','主用条件方案','定向升质；规模/背景过程；风险取舍',
 '保留楼20/6高Q较慢更多转折角色同/跨4.611/7.246，40/49图9/10楼支持，CA约+6.802；另有严格规模与n28直接AC。',
 '保留具体目标角色；不能把表现归因于scope单域因果增益，也不声称四类一般优于二类。',R,20,6,'higher_Q|slower|more_turns')
add('MSDGEOM_SCOPE_AXIS2','ManualSemiScope难度联合轴','Manual+Semi+scope','保留大团队探索候选','均衡容量的联合连续轴',
 '筛查24/5 Q幅度比约1.696、角位置距离比约2.610，有大团队信号；未纳入本轮保留楼确认。',
 '是连续轴离散化对照，不是Ward细类证明。',S,24,5,None,'geometry_pair_angle')

add('Q_MEDIAN2','单域Q基线','Manual','保留有效基线','透明的质量幅度区分',
 '保留楼17/9同/跨3.366/6.308，38/46图9/10楼支持；不能宣称复杂分类普遍超过Q。',
 '用于检验结构/反推的额外解释；不把双方向平均CA当作定向升质。',C,17,9)
add('Q_HARD_MEDIAN2','单域困难Q基线','Manual','保留负向/弱增量对照','困难Q分组是否自动增强区分',
 '保留楼12/8幅度比约1.051；困难Q单指标分组不自动带来强区分。',
 '该负结果针对这条单域轴，不能否定多域困难响应分类。',C,12,8)

# Seven already-existing classifiers re-evaluated in this round.
add('V3_BEHAVIOR_coarse','既有Manual结构分类','Manual','保留旧成果与比较','既有结构解释；混配与条件换类',
 '保留楼10/7同/跨6.789/8.845，48/66图8/10楼支持；新主线不撤销其既有结构和配比用途。',
 '不是旧M的重新命名；与本轮DSTRUCT保持不同标签身份。',C,10,7)
add('V3_BEHAVIOR_fine','既有Manual结构分类','Manual','保留旧细层/不升新主推荐','既有结构细分与配比内波动',
 '筛查有条件信号，未形成比既有粗层更清楚的本轮确认结果。',
 '额外细类不自动更可互换；既有细层用途与本轮筛查均保留。')
add('V3_JOINT_QT_coarse','既有Manual结构QT联合','Manual','保留既有主用途','选队质量时间收益；条件大块替换',
 '原选队收益仍以选队身份保留；本轮保留楼10/7同/跨6.210/10.487，17/24图6/9楼支持，CA约+7.667。',
 '不能用选队收益代替换类；本轮已有直接换类证据，但并非所有规模均强。',C,10,7)
add('V3_JOINT_QT_fine','既有Manual结构QT联合','Manual','保留旧细层/不升新主推荐','既有质量时间角色细层',
 '筛查10/7有信号、20/6较弱；未确认细层对粗层具有普遍增量。',
 '保留全部成员/标签；不以更细类数作为优势。')
add('XCOND_GEOM_coarse','既有跨条件几何','Manual+Semi','保留历史解释/本轮不主用','跨条件尺度和位置历史对照',
 '本轮8个实际可行筛查配置的Q幅度差均为负；说明该原方案不适合本轮强同跨Q区分目标。',
 '不否定联合Manual+Semi路线，也不撤销原标法解释用途。')
add('XCOND_GEOM_QT_coarse','既有跨条件几何QT','Manual+Semi','保留历史对照/本轮不主用','跨条件几何与QT角色',
 '筛查正负配置并存，没有形成广覆盖保留楼的新主条件。',
 '本轮未证明显著超出原方案的增量；不与新MSDGEOM合并为同一标签。')
add('XCOND_PAIRED_coarse','既有跨条件个人差分','Manual+Semi','保留机会有限的对照','同人两条件差分',
 '正式共同支持较少，实际仅两个n/m筛查配置；一个正、一个负，保留具体分母。',
 '缺跨条件历史者未知；不以补0扩大人员域，不将容量不足写成方法无效。')

# New reverse family, learned from real natural-prefix team responses.
add('RFUSE_GEOM_K2','真实融合响应反推','Manual真实自然前缀团队','主推荐','小类几何响应进入方向；同跨差异',
 '保留楼12/4进入小类同/跨3.642/6.492，23/29图9/10楼支持；分类输入不含Q，补足前向结构主线。',
 '较小目标类仍可有用途；m4不是预设上限，而是该类实际容量。',RC,12,4,'into_smallest_class')
add('RFUSE_GEOM_K3','真实融合响应反推','Manual真实自然前缀团队','保留具体小类方向/大分支不主用','进入小类的条件用途；反推细层负结果',
 '进入小类12/4同/跨4.616/7.183，20/30图10/10楼支持；非小类间12/4幅度比约1.021。',
 '有效信号主要保留小类角色，大类再分没有普遍新增强区分；不能写成整个K3无效。',RC,12,4,'into_smallest_class')
add('RFUSE_GEOMQ_K2','真实融合几何质量响应反推','Manual真实自然前缀团队','保留条件用途','更宽支持的目标小类进入方向',
 '保留楼12/4同/跨4.336/6.666，44/63图9/10楼支持；20/4、24/5等条件另表保留。',
 '质量进入建类后仍需实际换类检验；本轮已有，不等同于原答Q二分。',RC,12,4,'into_smallest_class')
add('RFUSE_GEOMQ_K3','真实融合几何质量响应反推','Manual真实自然前缀团队','保留重点条件发现','n20/m6进入小类；特定源角色的细层用途',
 '保留楼20/6进入小类同/跨1.828/5.642，差3.814、比3.086，16/21图8/9楼支持，CA约+4.252、CB约+3.971。',
 '特定源→小类方向强；非小类间同人数幅度比约1.115。不能把大分支弱推广为所有K3方向无效；后验选择的细条件标为内部发现。',RC,20,6,'into_smallest_class')

def main():
 tables={f:pd.read_csv(ROOT/f,low_memory=False) for f in [S,C,R,RC,'analysis/reverse_screen/METHOD_N_M_COMPARISON.csv']}
 forward=tables[S];reverse=tables['analysis/reverse_screen/METHOD_N_M_COMPARISON.csv']
 actual=set(forward.method)|set(reverse.method)
 assert len(specs)==31 and {s['method'] for s in specs}==actual and len(actual)==31
 labels=pd.concat([pd.read_csv(ROOT/'design/screen/FROZEN_LABELS.csv.gz'),pd.read_csv(ROOT/'reverse/REVERSE_LABELS_ALL_LOBO.csv.gz')],ignore_index=True)
 labels=labels[['worker_id','heldout_building','method','class_id','known']].drop_duplicates();labels=labels[labels.known.astype(str).str.lower().eq('true')]
 rows=[];evidence=[]
 for spec in specs:
  method=spec['method'];origin='new_reverse' if method.startswith('RFUSE_') else 'old_retested' if method.startswith(('V3_','XCOND_')) else 'new_forward'
  screen=reverse if origin=='new_reverse' else forward;sq=screen[(screen.method==method)&screen.metric.eq('B8L2')]
  source=spec['source'];d=tables[source];phase='screen' if source==S else 'selection_heldout_building'
  select=d.method.eq(method)&d.n.eq(spec['n'])&d.m.eq(spec['m'])&d.phase.eq(phase)
  rolefield='semantic_role' if source==R else 'branch' if source==RC else None
  if rolefield:select &= d[rolefield].eq(spec['role'])
  chosen=d[select];q=chosen[chosen.metric.eq('B8L2')];assert len(q)==1,(method,source,spec['role'],len(q))
  q=q.iloc[0];sh=chosen[chosen.metric.eq(spec['shape'])];assert len(sh)==1;sh=sh.iloc[0]
  ll=labels[labels.method.eq(method)];all_labels=ll[ll.heldout_building.eq('ALL')];folds=ll[ll.heldout_building.ne('ALL')]
  counts=folds.groupby('heldout_building').class_id.nunique();sizes=all_labels.groupby('class_id').size()
  selector=dict(method=method,phase=phase,n=spec['n'],m=spec['m'],**({rolefield:spec['role']} if rolefield else {}))
  row={k:spec[k] for k in ['method','family','input_conditions','adoption_status','retained_use','adoption_reason','fine_increment_judgment']}
  row.update(actual_tested_this_round=True,origin_group=origin,evaluation_condition='ordinary_manual',
   ALL_known_workers=len(all_labels) if len(all_labels) else None,ALL_class_size_vector='|'.join(f'{k}:{v}' for k,v in sizes.items()) if len(sizes) else '',
   ALL_label_note='ALL仅描述，效果使用对应楼外标签' if len(sizes) else '本轮冻结旧方案仅收录楼外；ALL继续引用原阶段，不拼接楼外编号',
   LOBO_known_worker_union=folds.worker_id.nunique(),LOBO_folds=folds.heldout_building.nunique(),LOBO_class_count_min=int(counts.min()),LOBO_class_count_max=int(counts.max()),
   tested_screen_n_m_configs=len(sq),screen_Q_gap_min=sq.gap_image_equal.min(),screen_Q_gap_median=sq.gap_image_equal.median(),screen_Q_gap_max=sq.gap_image_equal.max(),
   screen_Q_ratio_min=sq.ratio_of_image_means.min(),screen_Q_ratio_max=sq.ratio_of_image_means.max(),
   representative_source=source,representative_phase=phase,representative_n=spec['n'],representative_m=spec['m'],
   representative_role=spec['role'] or 'all_registered_directions',source_row_selector=json.dumps(selector,ensure_ascii=False,sort_keys=True),
   representative_Q_within=q.within_image_equal,representative_Q_cross=q.cross_image_equal,representative_Q_gap=q.gap_image_equal,representative_Q_ratio=q.ratio_of_image_means,
   Q_gap_positive_images=int(q.gap_positive_images),Q_valid_images=int(q.valid_images),Q_gap_positive_buildings=int(q.gap_positive_buildings),Q_valid_buildings=int(q.valid_buildings),
   representative_Q_CA=q.CA_image_equal,representative_Q_CB=q.CB_image_equal,
   Q_CA_valid_images=q.CA_valid_images,Q_CA_positive_images=q.CA_positive_images,Q_CA_valid_buildings=q.CA_valid_buildings,Q_CA_positive_buildings=q.CA_positive_buildings,
   shape_metric=spec['shape'],shape_within=sh.within_image_equal,shape_cross=sh.cross_image_equal,shape_gap=sh.gap_image_equal,shape_ratio=sh.ratio_of_image_means,
   shape_gap_positive_images=int(sh.gap_positive_images),shape_valid_images=int(sh.valid_images),shape_gap_positive_buildings=int(sh.gap_positive_buildings),shape_valid_buildings=int(sh.valid_buildings),
   classification_input_leakage_rule='目标建筑在两条件历史中排除；原答或训练侧自然团队响应建类；ALL不用于目标效果',
   evidence_role='screen探索展示，未声称独立确认' if phase=='screen' else '本轮选型保留建筑内部检查；v2并非全新外部数据',
   labels_reference='reverse/REVERSE_LABELS_ALL_LOBO.csv.gz' if origin=='new_reverse' else 'design/screen/FROZEN_LABELS.csv.gz',
   all_result_reference='analysis/reverse_screen/METHOD_N_M_COMPARISON.csv;analysis/reverse_confirm/REVERSE_BRANCH_COMPARISON.csv' if origin=='new_reverse' else 'analysis/screen/METHOD_N_M_COMPARISON.csv;analysis/confirm/METHOD_N_M_COMPARISON.csv;analysis/confirm/SEMANTIC_ROLE_COMPARISON.csv')
  rows.append(row)
  c=chosen.copy();c['adoption_method']=method;c['evidence_source']=source;evidence.append(c)
 result=pd.DataFrame(rows);save(result,OUT/'METHOD_ADOPTION_DECISIONS.csv')
 # Preserve every screen n/m result for these 31 instances, not only examples.
 allscreen=pd.concat([forward,reverse],ignore_index=True);save(allscreen,OUT/'method_adoption/ALL_31_SCREEN_CONFIGURATION_METRICS.csv')
 save(pd.concat(evidence,ignore_index=True),OUT/'method_adoption/ADOPTION_REPRESENTATIVE_ALL_METRICS.csv')
 history=[]
 descriptions={
  '旧M粗细结构':'原结构表达与父内细类；m5/m6及大块结果按旧身份保留，不将其当成本轮DSTRUCT或V3_BEHAVIOR。',
  'A2原答关系':'原答几何关系与大块替换区分；旧n17/m9出现跨类幅度更大且Q下降，下降本身也是有效用途。',
  'QTD':'旧质量时间难度组织与父内换人/换类，保留原实际m和Y/Z重叠设计。',
  'Semi SP':'Semi位置/尺度及直接AC、较大块替换，效果仍限定Semi。',
  'F01':'高历史Q域的快慢构成；37配比1874成员集合的效率范例继续保留。',
  'Rnew2':'既有真实替换关系反推及负/正结果继续保留，不与本轮自然前缀融合响应RFUSE混名。',
  'Semi自身结构/联合分类':'既有终稿结构与效率质量取舍成果继续保留；本轮31实例主效果为普通Manual，不声称重新评估Semi。'}
 for name,note in descriptions.items():history.append(dict(method_family=name,tested_in_current_31=False,action='保留既有成果，本轮未重算',retained_use=note,
   source_reference='HOHONET_exchange_latest/docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md;research/workers/personnel_mixture_comparison_20261022/integration/METHOD_SELECTION_AND_COVERAGE.csv'))
 save(pd.DataFrame(history),OUT/'HISTORICAL_METHODS_RETAINED_NOT_RETESTED.csv')
 receipt=dict(actual_methods=31,new_forward=20,old_retested=7,new_reverse=4,new_fusion_run=False,labels_changed=False,
  status_counts=result.adoption_status.value_counts().to_dict(),reference_n_m_rule='Screen-only methods show n20/m6 for consistent scale, except explicitly retained n24/m5 axis signal; confirmed methods use named role/branch conditions, not a maximum selected over all rows.',
  historical_methods_not_counted_in31=len(history),source_sha256={p:sha(ROOT/p) for p in tables},code_sha256=sha(__file__))
 (OUT/'method_adoption/RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:receipt[k] for k in ['actual_methods','new_forward','old_retested','new_reverse','new_fusion_run','labels_changed','status_counts']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
