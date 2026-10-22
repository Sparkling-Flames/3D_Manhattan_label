#!/usr/bin/env python3
"""Integrate frozen method identities, members, support and completed uses.

No feature fitting, class discovery, endpoint evaluation, fusion or scoring.
"""
import hashlib,json,os
from pathlib import Path
import pandas as pd

HERE=Path(__file__).resolve().parent
NEW=HERE.parent
ROOT=NEW.parents[2]
X=NEW/'cross_condition_taxonomy'
V3=ROOT/'research/workers/personnel_useful_taxonomy_v3_20261021'
ROSTER_N=62

def atomic(path,b):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.partial')
 with temp.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 os.replace(temp,path)
def savecsv(name,d):atomic(HERE/name,d.to_csv(index=False).encode('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def relative(p):return str(Path(p).relative_to(ROOT))
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if hasattr(v,'item'):v=v.item()
 if v is None or (isinstance(v,float) and pd.isna(v)):return None
 return v
def jsontext(v):return json.dumps(clean(v),ensure_ascii=False,sort_keys=True,separators=(',',':'))

USES={
 ('M_structure','manual'):('采用：结构表达、必要结构补票、质量选择；细类条件性替换风险',
  '旧M粗2/细4独立保留。父类固定的细分块结果有增量，主要由n10等支持；n20不普遍。',
  'research/workers/personnel_useful_taxonomy_v3_20261021/composition/FINAL_FINDINGS_ZH.md'),
 ('SP_scale','semi'):('采用：Semi尺度/高度差异与条件性互换风险',
  '旧SP粗2/细3独立保留；父内细分支持较小且依人数，不能写整条人数曲线更稳定。',
  'research/workers/personnel_useful_taxonomy_v3_20261021/composition/FINAL_FINDINGS_ZH.md'),
 ('A2_relation','manual'):('采用：跨图原答关系、条件性换类风险分区',
  '跨类变化通常更大可用于风险识别，不等于推荐跨类替换；单层3类，不冒称粗细两层。',
  'research/workers/personnel_useful_taxonomy_v3_20261021/composition/FINAL_FINDINGS_ZH.md'),
 ('A2_relation','semi'):('采用：跨图原答关系、条件性换类风险分区',
  'Semi独立的原答关系类型；单层3类，不直接沿用Manual标签。',
  'research/workers/personnel_useful_taxonomy_v3_20261021/composition/FINAL_FINDINGS_ZH.md'),
 ('V3_BEHAVIOR','manual'):('采用：Manual历史结构表达、必要结构补充及质量构成用途',
  '旧V3行为类独立保留。ALL为3/3，无额外ALL细层；部分外折有细层，按真实父内支持判断。',
  'research/workers/personnel_useful_taxonomy_v3_20261021/taxonomy/REPORT_ZH.md|research/workers/personnel_useful_taxonomy_v3_20261021/composition/FINAL_FINDINGS_ZH.md'),
 ('V3_BEHAVIOR','semi'):('采用：Semi终稿结构与近共线分段描述；质量/替换仅条件性',
  'Semi独立拟合；近共线不自动等于错误，缺精确初始化不推断编辑动机或轨迹。',
  'research/workers/personnel_useful_taxonomy_v3_20261021/taxonomy/REPORT_ZH.md'),
 ('V3_JOINT_QT','manual'):('采用：可解释结构×QT；更高历史Q且更快的纯块方向有实际双优用途',
  '自身Manual输入，非M+S。新批64 ABC中62共同可评分/时间可比：净Q+5.691、时间−3.632%；2失败保留。',
  relative(NEW/'joint_exchange/MANUAL_NATIVE_FINDINGS_ZH.md')),
 ('V3_JOINT_QT','semi'):('采用：Semi自身结构×QT的条件效率用途',
  '自身Semi输入，非M+S。28 ABC记录时间均下降；净Q+0.153、时间−8.544%，同时保留质量损失尾部。',
  relative(NEW/'joint_exchange/SEMI_NATIVE_FINDINGS_ZH.md')),
 ('MV_QTD_manual','manual'):('保留：Q/T/困难响应分层及连续特征竞争对照',
  '既有全人员多域候选；不等于全部26域组合完成，也不能仅凭分类标签推定互换。',
  'research/workers/personnel_global_composition_20261021/multivariate/README_ZH.md'),
 ('MV_QTD_manual_new','manual'):('保留：新批同来源Q/T/困难响应对照',
  '独立拟合/限制的新批版本，不能与全人员版本拼成同一标签。旧批行属适用人群之外，不记为缺机会。',
  'research/workers/personnel_global_composition_20261021/multivariate/README_ZH.md'),
 ('MV_QTScopeSemi_semi_new','semi'):('保留探索：Semi Q/T/scope/编辑与错误机会行为',
  '四域真实标签与既有结果保留。scope倾向非正确率；缺初始化/错误机会未知。',
  'research/workers/personnel_global_composition_20261021/multivariate/README_ZH.md'),
 ('MV_TDScopeSemi_manual_new','manual'):('保留探索及负结果：Manual T/D/scope + Semi行为辅助',
  '这是既有真正跨条件辅助方案，但Semi域为编辑/错误机会行为，不是本轮双条件几何/QT。',
  'research/workers/personnel_global_composition_20261021/multivariate/README_ZH.md'),
 ('Rnew2','manual'):('采用：新批真实替换关系的条件性风险分区',
  '固定历史10楼形成，目标12楼映射；原大替换实验保留。没有ALL重新拟合标签，不伪造LOBO身份。',
  'research/workers/personnel_useful_taxonomy_v3_20261021/composition/FINAL_FINDINGS_ZH.md'),
 ('F01','manual'):('采用：新批高Q域、简单图的快慢构成效率取舍',
  '固定历史10楼形成、目标12楼映射；困难图仍有成员/结构导致的质量风险。没有ALL标签。',
  'research/workers/personnel_useful_taxonomy_v3_20261021/utility/F01_FINDINGS_ZH.md'),
 ('XCOND_GEOM','manual'):('补充采用：同点数定位/形状相近；部分父内细分',
  '75,193原答对/202图/22楼，细类内外角距差−0.668°；父内细分仅42图/5楼。未进入本轮三法共同锚点融合比较。',relative(X/'REPORT_ZH.md')),
 ('XCOND_GEOM','semi'):('补充采用：相对高度相近、近共线表达预测',
  '高度差类内更小；冗余表达预测较旧自身行为类改善6.38%。不是通用更优质量类。',relative(X/'REPORT_ZH.md')),
 ('XCOND_GEOM_QT','manual'):('保留描述；本轮不替代原单条件联合的换类规则',
  '509共同锚点净Q+0.073、时间+8.305%；可读组合成立，但未形成更有利质量—时间替换。',relative(X/'REPORT_ZH.md')),
 ('XCOND_GEOM_QT','semi'):('保留描述；不作整体替换推荐',
  '157共同锚点净Q+0.910、时间+10.162%；全174锚点净失败+7.630个百分点，需与可评分交集并看。',relative(X/'REPORT_ZH.md')),
 ('XCOND_PAIRED','manual'):('条件采用：相对同构成替换的净效率与较小质量损失',
  '509共同锚点净Q+1.120、时间−5.576%，但C−A仍−0.992；7/16图、5/13楼双优。不是形状相似类。',relative(X/'REPORT_ZH.md')),
 ('XCOND_PAIRED','semi'):('保留明确质量—时间取舍，不作整体换类推荐',
  '157共同锚点净Q−2.089、时间−4.273%；原答类内形状反而更远，稳定成员不等于相似形状。',relative(X/'REPORT_ZH.md'))}

def main():
 source_paths=[X/'OLD_METHOD_REGISTRY.csv',X/'OLD_METHOD_LABELS_ALL.csv',X/'OLD_METHOD_LABELS_TARGET_MAPS.csv.gz',
  X/'CROSS_LABELS_ALL.csv',X/'CROSS_LABELS_LOBO.csv.gz',X/'LABEL_FREEZE.json',X/'PAIRED_INPUT_RECORDS.csv.gz',X/'ADOPTION_MATRIX_FINAL.csv',
  V3/'taxonomy/BEHAVIOR_RECORDS.csv.gz']
 inputs={str(p):sha(p) for p in source_paths}
 registry=pd.read_csv(source_paths[0],keep_default_na=False).set_index('method')
 oldall=pd.read_csv(source_paths[1],keep_default_na=False);oldlo=pd.read_csv(source_paths[2],keep_default_na=False)
 xa=pd.read_csv(source_paths[3],keep_default_na=False,low_memory=False);xl=pd.read_csv(source_paths[4],keep_default_na=False,low_memory=False)
 records=pd.read_csv(source_paths[-1],usecols=['condition','building_id','worker_id','origin','behavior_usable','layer'])
 condition_buildings={c:set(g.building_id) for c,g in records[records.behavior_usable&records.layer.eq('ordinary')].groupby('condition')}
 # Existing behavior inventory may name its ordinary layer with a prefix.
 if not condition_buildings:condition_buildings={c:set(g.building_id) for c,g in records[records.behavior_usable].groupby('condition')}
 roster=set(records.worker_id);assert len(roster)==ROSTER_N
 origin=records.groupby('worker_id').origin.first().to_dict()
 pairb=set(pd.read_csv(X/'PAIRED_INPUT_RECORDS.csv.gz',usecols=['building_id']).building_id)
 filecache={};members=[]
 def source_support(r):
  path=ROOT/r.source_path
  if str(path) not in filecache:
   filecache[str(path)]=pd.read_csv(path,keep_default_na=False,low_memory=False);inputs[str(path)]=sha(path)
  d=filecache[str(path)];g=d[d.worker_id.eq(r.worker_id)]
  if 'condition' in g:g=g[g.condition.eq(r.condition)]
  if 'method' in g and r.method in set(g.method):g=g[g.method.eq(r.method)]
  if 'method_id' in g:g=g[g.method_id.eq(r.source_method)] if r.source_method in set(g.method_id) else g[g.method_id.eq(r.method)]
  if 'heldout_building' in g:g=g[g.heldout_building.isin(['ALL','ALL_DATA'])]
  if g.empty:return dict(support='source_label_record_has_no_direct_support_columns')
  row=g.iloc[0];fields=['support','n_records','n_images','n_buildings','n_quality_usable','n_independent_vote_eligible','geometry_n_train_images',
   'geometry_n_train_buildings','position_n_train_images','position_n_train_buildings','simple_images','simple_buildings','complex_images','complex_buildings',
   'selection_status','label_status','formal_team_eligibility','origin']
  return {f:row[f] for f in fields if f in row.index}
 for (method,cond,w),g in oldall.groupby(['method','condition','worker_id'],sort=True):
  r=g.iloc[0];tier_to=g.set_index('tier');coarse=tier_to.loc['coarse','class_id'] if 'coarse' in tier_to.index else (tier_to.loc['single','class_id'] if 'single' in tier_to.index else '')
  fine=tier_to.loc['fine','class_id'] if 'fine' in tier_to.index else '';known=bool(g.known.all());reason='|'.join(sorted(set(x for x in g.missing_reason if x)))
  support=source_support(r);outside='outside_declared_new_source_population' in reason
  members.append(dict(method=method,condition=cond,worker_id=w,coarse_label=coarse if known else '',fine_label=fine if known else '',
   hierarchy='single' if 'single' in set(g.tier) else 'coarse_fine',known=known,population_status='outside_declared_population' if outside else 'within_declared_population',
   support=jsontext(support),missing_reason=reason or ('' if known else 'source_missing_reason_unspecified'),source_missing_reason=reason,
   origin=origin.get(w,''),input_conditions=r.input_conditions,label_fit_scope=r.label_fit_scope,label_source_path=r.source_path,
   normalized_source_path=relative(X/'OLD_METHOD_LABELS_ALL.csv'),membership_is_not_team_qualification=True,
   n_images=support.get('n_images',''),n_buildings=support.get('n_buildings','')))
 for r in xa.itertuples(index=False):
  dd=r._asdict();fields=[f for f in dd if f.startswith(('m_','s_')) and any(x in f for x in ['images','buildings','records','supported','quality_usable','independent_vote'])]
  fields+=['pair_records','pair_images','pair_buildings','paired_supported','selection_status']
  support={f:dd[f] for f in fields if f in dd}
  members.append(dict(method=r.method,condition=r.condition,worker_id=r.worker_id,coarse_label=r.coarse_label if r.known else '',fine_label=r.fine_label if r.known else '',
   hierarchy='coarse_fine',known=bool(r.known),population_status='within_declared_population',support=jsontext(support),
   missing_reason=r.missing_reason,source_missing_reason=r.missing_reason,origin=origin.get(r.worker_id,''),input_conditions='manual|semi',
   label_fit_scope='all_data_descriptive',label_source_path=relative(X/'CROSS_LABELS_ALL.csv'),normalized_source_path=relative(X/'CROSS_LABELS_ALL.csv'),
   membership_is_not_team_qualification=True,n_images='',n_buildings=''))
 mem=pd.DataFrame(members);savecsv('METHOD_ALL_MEMBERS.csv',mem)
 # Normalize target maps only in memory, keeping old frozen-history identity.
 target=[]
 for (method,cond,b,w),g in oldlo.groupby(['method','condition','heldout_building','worker_id'],sort=False):
  r=g.iloc[0];d=g.set_index('tier');coarse=d.loc['coarse','class_id'] if 'coarse' in d.index else (d.loc['single','class_id'] if 'single' in d.index else '')
  target.append(dict(method=method,condition=cond,heldout_building=b,worker_id=w,known=bool(g.known.all()),coarse_label=coarse,
   fine_label=d.loc['fine','class_id'] if 'fine' in d.index else '',label_fit_scope=r.label_fit_scope,selection_status='source_method_status_preserved'))
 for r in xl.itertuples(index=False):target.append(dict(method=r.method,condition=r.condition,heldout_building=r.heldout_building,worker_id=r.worker_id,
  known=bool(r.known),coarse_label=r.coarse_label,fine_label=r.fine_label,label_fit_scope='outer_both_conditions_excluded_inner_selected',selection_status=r.selection_status))
 target=pd.DataFrame(target);rows=[]
 for (method,cond),lo in target.groupby(['method','condition'],sort=True):
  a=mem[mem.method.eq(method)&mem.condition.eq(cond)];new=method.startswith('XCOND_');fixed=method in ['Rnew2','F01'];known=a[a.known]
  kb=lo[lo.known].groupby('heldout_building').worker_id.nunique();ck=lo[lo.known].groupby('heldout_building').coarse_label.nunique()
  fk=lo[lo.known&lo.fine_label.ne('')].groupby('heldout_building').fine_label.nunique()
  folds=lo.drop_duplicates('heldout_building');all_fine=known.loc[known.fine_label.ne(''),'fine_label'].nunique();all_coarse=known.coarse_label.nunique()
  missing=a[~a.known];outside=missing.population_status.eq('outside_declared_population').sum();available=set(lo.heldout_building)&condition_buildings.get(cond,set())
  statuscounts=folds.selection_status.value_counts().to_dict();adopt,comment,evidence=USES[(method,cond)]
  formation=({'XCOND_GEOM':'同一人Manual+Semi的E/R/G三域等权','XCOND_GEOM_QT':'同一人Manual+Semi的E/R/G/Q/T五域等权',
   'XCOND_PAIRED':'同人同图同参考配对的E/R/G共同水平与Semi−Manual差'}[method] if new else registry.loc[method,'formation_identity_zh'])
  name=({'XCOND_GEOM':'双条件几何类','XCOND_GEOM_QT':'双条件几何×QT','XCOND_PAIRED':'同人同图配对响应类'}[method] if new else registry.loc[method,'name_zh'])
  cross=new or method=='MV_TDScopeSemi_manual_new';inp='manual|semi' if new else ('manual|semi_edit_auxiliary' if cross else cond)
  scheme='frozen_history10_target12' if fixed else ('outer_both_conditions_excluded_inner_selected' if new else '|'.join(sorted(set(lo.label_fit_scope))))
  rows.append(dict(method=method,method_name_zh=name,identity_stage='20261022_cross_condition' if new else 'historical_frozen_method',
   underlying_data_version='v2',formation_identity_zh=formation,input_conditions=inp,evaluation_condition=cond,cross_condition_formation=cross,
   all_label_available=not a.empty,all_label_inventory_n=len(a) if len(a) else '',all_coarse_k=all_coarse if len(a) else '',
   all_fine_k=all_fine if all_fine else '',all_hierarchy='not_available' if a.empty else ('single_partition' if not all_fine else ('independent_fine_split' if all_fine>all_coarse else 'coarse_and_fine_same_partition')),
   all_known_n=len(known) if len(a) else '',all_unknown_within_population_n=len(missing)-int(outside) if len(a) else '',
   all_outside_population_n=int(outside) if len(a) else '',all_absent_from_label_inventory_n=ROSTER_N-len(a) if len(a) else '',
   all_missing_reason_counts=jsontext(missing.missing_reason.value_counts().to_dict()) if len(a) else 'no_ALL_labels; not zero members',
   target_label_scheme=scheme,target_label_map_buildings=lo.heldout_building.nunique(),
   target_buildings_with_evaluation_condition_records=len(available),
   effective_input_deletion_buildings=(len(set(lo.heldout_building)&pairb) if method=='XCOND_PAIRED' else ('' if fixed else (lo.heldout_building.nunique() if cross else len(available)))),
   target_map_known_min=int(kb.min()),target_map_known_max=int(kb.max()),target_map_coarse_k_min=int(ck.min()),target_map_coarse_k_max=int(ck.max()),
   target_map_fine_k_min=int(fk.min()) if len(fk) else '',target_map_fine_k_max=int(fk.max()) if len(fk) else '',
   target_selection_status_counts=jsontext(statuscounts),lobo_support_note=('非LOBO：固定历史10楼形成，12目标楼映射' if fixed else ('22个映射；只有11楼有配对形成输入可删除' if method=='XCOND_PAIRED' else '目标楼外标签；映射数不等于该条件实际终点图/楼数')),
   adoption_zh=adopt,use_and_boundary_zh=comment,evidence_paths=evidence,
   exact_all_members_path=relative(HERE/'METHOD_ALL_MEMBERS.csv') if len(a) else '',exact_all_members_selector=f'method={method};condition={cond}' if len(a) else 'no_ALL_labels',
   original_all_labels_path=(relative(X/'CROSS_LABELS_ALL.csv') if new else relative(X/'OLD_METHOD_LABELS_ALL.csv')) if len(a) else '',
   exact_target_labels_path=relative(X/'CROSS_LABELS_LOBO.csv.gz') if new else relative(X/'OLD_METHOD_LABELS_TARGET_MAPS.csv.gz'),
   exact_target_member_list_path=relative(X/'CLASS_ROLES_LOBO.csv.gz') if new else relative(X/'OLD_METHOD_MEMBERS_TARGET_MAPS.csv.gz'),
   exact_target_selector=f'method={method};condition={cond};heldout_building=<target>',
   original_source_paths=relative(X/'CROSS_LABELS_ALL.csv')+'|'+relative(X/'CROSS_LABELS_LOBO.csv.gz') if new else registry.loc[method,'source_paths']))
 result=pd.DataFrame(rows);savecsv('PERSONNEL_METHODS_AND_USES.csv',result)
 # A concise human-readable index, generated from the same exact counts.
 lines=['# 人员方法、成员与实际用途总表','',
  '本表只整合已经冻结的旧标签、本轮新标签和已完成用途结果。没有重新分类、重新选型、重新计算原答距离或重新融合评分。底层数据仍为v2；旧V3为研究版本。', '',
  '**14种方法、20个方法×评价条件条目分别保留身份，不是一套统一的分类树。** Manual与Semi各自类别的编号不可跨条件直接等同；本轮三个XCOND家族才是同一人的两条件历史共同形成标签，再分别评价两条件。旧Manual T/D/scope+Semi行为方案也是跨条件辅助，但Semi域的含义不同。','',
  '## 方法与ALL标签支持','',
  '|方法|评价条件|ALL粗／细类|已知／域内未知／域外|目标映射楼数|已采用用途|',
  '|---|---|---|---|---|---|']
 for r in result.itertuples():
  k='无ALL标签' if not r.all_label_available else str(r.all_coarse_k)+('/'+str(r.all_fine_k) if r.all_fine_k!='' else '（单层）')
  ns='见固定历史目标标签' if not r.all_label_available else f'{r.all_known_n}／{r.all_unknown_within_population_n}／{r.all_outside_population_n}'
  lines.append(f'|{r.method}|{r.evaluation_condition}|{k}|{ns}|{r.target_label_map_buildings}|{r.adoption_zh}|')
 lines+=['','## 如何读取支持量','',
  '- `ALL`是用于描述当前库存的最终标签，不能替代目标建筑的楼外标签。粗／细类数相同表示ALL没有另选独立细层；A2只有单层，细类列留空。外折K的范围另外保存在CSV中。',
  '- “域内未知”指适用人群中缺机会或字段；“域外”指旧新批专用方法明确排除的旧批人员。两者不同。缺原因的旧源行标为 `source_missing_reason_unspecified`，没有猜测其动机或资格。',
  '- `MV_QTScopeSemi_semi_new` 的旧ALL源表实际只有61名人员，另1名没有源标签行。该缺口单列 `all_absent_from_label_inventory_n=1`，不默默补成零行为或未知标签。',
  '- Rnew2有35名新批、F01有23名高Q域人员的目标标签；均由固定10个历史楼形成并映射到12目标楼，**没有ALL标签，也不是22折LOBO**。ALL人数和类数留空，不能读作0类或0人。精确成员请用对应目标表及筛选键。',
  '- 新XCOND每法有22个目标楼标签映射。配对响应形成输入只覆盖11楼，另外11楼的映射不能增加“删楼稳定性”有效分母。Semi实际原答条件楼通常为12楼；标签映射的22楼也不能充当22个Semi终点评价楼。',
  '- 目标表的known最小／最大人数包含保存的探索折；`selection_status`的容量或稳定性未过门槛身份保留。标签已知不自动恢复历史筛除人员的正式组队资格。',
  '- `METHOD_ALL_MEMBERS.csv`一行对应方法、评价条件和人员，粗细标签同列，含原始缺失原因与支持JSON。新跨条件的支持JSON分别保留Manual、Semi、配对机会，未把缺机会填作零行为；旧支持字段直接摘自原标签源。','',
  '## 按用途读取，避免混成一个排名','',
  'M保留Manual结构补充、质量选择和条件性父内块风险；SP保留Semi尺度与条件风险；A2保留关系与换类风险；Rnew2保留新批真实替换关系；F01保留高Q简单图效率。原V3_JOINT_QT的“联合”是自身条件的结构×QT，其Manual和Semi纯块新实验分别提供具体双优／效率用途。', '',
  '新XCOND_GEOM补充同点数定位、尺度及Semi冗余表达。XCOND_PAIRED在Manual共同锚点中相对同构成替换省时、质量损失较小，但仍不保证高于原队；Semi为质量—时间取舍。XCOND_GEOM_QT保留可读描述，本轮不替代原自身联合的通用换类规则。没有用原答相似证明融合互换，也没有因效率用途成立把类别重命名为形状簇。', '',
  'CSV逐行列出实际用途边界与证据路径；支持数字均为已有标签的汇总，不是新增独立实验次数。原答、团队端点及大缓存不复制到本目录。', '',
  '## 文件','',
  '- `PERSONNEL_METHODS_AND_USES.csv`：方法身份、输入／评价条件、ALL粗细和未知分母、楼外／固定历史支持、用途与精确文件筛选键。',
  '- `METHOD_ALL_MEMBERS.csv`：已有ALL标签的逐人粗细、原支持与缺失原因；没有为Rnew2/F01生成伪ALL标签。',
  '- `PERSONNEL_METHODS_SOURCE_RECEIPT.json`：源文件SHA、输出SHA与“0新增研究计算”身份。',
  '- `build_personnel_methods_and_uses.py`：仅重建本汇总，不调用分类、融合或评分。','']
 atomic(HERE/'PERSONNEL_METHODS_AND_USES_ZH.md','\n'.join(lines).encode())
 for path,h in inputs.items():assert sha(path)==h
 outnames=['PERSONNEL_METHODS_AND_USES.csv','METHOD_ALL_MEMBERS.csv','PERSONNEL_METHODS_AND_USES_ZH.md','build_personnel_methods_and_uses.py']
 receipt=dict(methods=result.method.nunique(),method_condition_rows=len(result),all_member_rows=len(mem),global_roster_n=ROSTER_N,
  identity='integration_only; no new taxonomy, distance, fusion, score, or validation experiment',
  input_hashes=[dict(path=relative(Path(p)),sha256=h) for p,h in sorted(inputs.items())],
  outputs=[dict(path=name,sha256=sha(HERE/name),bytes=(HERE/name).stat().st_size) for name in outnames])
 atomic(HERE/'PERSONNEL_METHODS_SOURCE_RECEIPT.json',jsontext(receipt).encode());print(jsontext({k:v for k,v in receipt.items() if k not in ['input_hashes','outputs']}))

if __name__=='__main__':main()
