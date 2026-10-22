#!/usr/bin/env python3
"""Lightweight scope integration; real member sets, no fusion or score work."""
from pathlib import Path
from decimal import Decimal
import hashlib,json,gzip,os
import pandas as pd

HERE=Path(__file__).resolve().parent
NEW=HERE.parents[1]
SOURCES={
 'manual_joint_A':'manual_joint/EVENTS_REGISTERED.csv.gz',
 'manual_joint_B':'manual_joint/phase_b_highq_slower/EVENTS_REGISTERED.csv.gz',
 'manual_structure':'structure/ALL_EVENTS_REGISTERED.csv.gz',
 'semi_joint':'semi/EVENTS_REGISTERED_ALL.csv.gz'}
EXPECTED={'manual_joint_A':81221,'manual_joint_B':21000,'manual_structure':29928,'semi_joint':13882}
RECEIPTS={'manual_joint_A':'manual_joint/EVALUATION_RECEIPT.json',
 'manual_joint_B':'manual_joint/phase_b_highq_slower/EVALUATION_RECEIPT.json',
 'manual_structure':'structure/results/COMPLETION.json','semi_joint':'semi/DELIVERY_RECEIPT.json'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ident(*items):return hashlib.sha256(json.dumps(items,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def members(s):return '|'.join(sorted(x for x in str(s).split('|') if x))
def integer(x):return int(Decimal(str(x))) if str(x) not in ['','nan','None'] else 0
def read(f):return pd.read_csv(NEW/f,dtype=str,keep_default_na=False)
def save_csv(name,d):
 p=HERE/name;raw=d.to_csv(index=False).encode('utf-8-sig')
 if name.endswith('.gz'):raw=gzip.compress(raw,compresslevel=5,mtime=0)
 q=p.with_name(p.name+'.partial');q.write_bytes(raw);os.replace(q,p)
 return dict(path=name,rows=len(d),bytes=len(raw),sha256=sha(p))
def summary(name,g):
 eps=set(g.endpoint_A)|set(g.endpoint_B)|set(g.endpoint_C)
 return dict(line=name,registered_events=len(g),completed_registered_events=len(g),
  canonical_physical_ABC=g.canonical_physical_ABC.nunique(),canonical_oriented_ABC=g.canonical_oriented_ABC.nunique(),
  extra_AB_orientation_rows=g.canonical_oriented_ABC.nunique()-g.canonical_physical_ABC.nunique(),
  repeated_same_oriented_registration_rows=len(g)-g.canonical_oriented_ABC.nunique(),
  total_duplicate_registration_rows=len(g)-g.canonical_physical_ABC.nunique(),
  exact_ABC_endpoints=len(eps),pools=g.pool_id.nunique(),images=g.image.nunique(),buildings=g.building.nunique(),
  actual_backgrounds=g.canonical_background.nunique(),registered_class_configurations=g.canonical_config.nunique(),
  n_values='|'.join(map(str,sorted(g.n.astype(int).unique()))),m_values='|'.join(map(str,sorted(g.m_AB.astype(int).unique()))),
  conditions='|'.join(sorted(g.condition.unique())),endpoints_scope='ABC only; continuous-QT/policy control endpoints counted separately',
  independent_evidence_note='events share people/endpoints; image/building support is separate; no new independence from mirrors')

def main():
 inputs=[];frames=[];key_to_endpoint={}
 for line,file in SOURCES.items():
  h=read(file);assert len(h)==EXPECTED[line],(line,len(h))
  done=json.loads((NEW/RECEIPTS[line]).read_text())
  assert done.get('complete',done.get('status')=='complete')
  assert int(done.get('completed_events',done.get('events')))==len(h)
  rows=[]
  for r in h.to_dict('records'):
   pid=r['pool_id'];arm={a:members(r[a+'_member_workers']) for a in 'ABC'}
   ep={a:ident(pid,arm[a]) for a in 'ABC'}
   for a in 'ABC':
    old=key_to_endpoint.setdefault(r['team_'+a],ep[a]);assert old==ep[a]
   ab=sorted([arm['A'],arm['B']])
   counts=sorted([r['A_counts'],r['B_counts']])
   rows.append(dict(line=line,event_id=r['event_id'],input_physical_id=r.get('physical_triple_id',''),
    pool_id=pid,image=r['image'],building=r['building'],condition=r['condition'],n=r['n'],m_AB=r['m_AB'],
    canonical_physical_ABC=ident(pid,ab[0],ab[1],arm['C']),
    canonical_oriented_ABC=ident(pid,arm['A'],arm['B'],arm['C']),
    endpoint_A=ep['A'],endpoint_B=ep['B'],endpoint_C=ep['C'],
    canonical_background=ident(pid,members(r['common_background'])),
    canonical_config=ident(pid,r['method_id'],r['tier'],r['source_domain'],r['n'],r['m_AB'],counts,r['C_counts']),
    stage=r.get('study_group',r.get('stage','')),cell_id=r.get('cell_id',r.get('capacity_id','')),source_domain=r['source_domain']))
  frames.append(pd.DataFrame(rows));inputs.append(dict(path=file,rows=len(h),sha256=sha(NEW/file),
   completion_receipt=RECEIPTS[line],completion_receipt_sha256=sha(NEW/RECEIPTS[line])))
 E=pd.concat(frames,ignore_index=True)
 scopes=[summary(line,g) for line,g in E.groupby('line',sort=False)]
 scopes += [summary('manual_joint_A_plus_B',E[E.line.isin(['manual_joint_A','manual_joint_B'])]),
            summary('all_manual_ABC',E[E.condition.eq('manual')]),summary('all_lines_ABC',E)]
 S=pd.DataFrame(scopes)
 map_fields=['line','event_id','input_physical_id','pool_id','canonical_physical_ABC','canonical_oriented_ABC','stage']
 outputs=[save_csv('NEW_SCOPE_COVERAGE.csv',S),save_csv('PHYSICAL_REGISTRATION_MAP.csv.gz',E[map_fields])]
 # Theoretical spaces are per declared domain. Overlapping lines/domains are
 # never summed into a supposedly global theoretical universe.
 M=read('manual_joint/CAPACITY_ALL_N_M.csv.gz')
 B=read('manual_joint/phase_b_highq_slower/CAPACITY.csv')
 T=read('structure/CAPACITY_AND_COVERAGE.csv.gz')
 F=read('semi/CAPACITY_ALL_ATTEMPTS.csv')
 caps=[]
 def mcap(name,d,registered,selected=True):
  theory=sum(map(integer,d.theoretical_unordered_source_ABC))
  return dict(space=name,condition='Manual',cells=len(d),
   feasible_background_class_vectors=sum(map(integer,d.feasible_background_class_configurations)),
   observed_background_class_vectors=sum(map(integer,d.registered_background_class_configurations)),
   possible_concrete_backgrounds=str(sum(map(integer,d.feasible_concrete_backgrounds))),
   registered_background_references=sum(map(integer,d.registered_backgrounds)),
   theoretical_physical_ABC=str(theory),registered_physical_ABC=registered,
   unregistered_physical_ABC=str(theory-registered),
   full_member_enumeration=False,finite_enumeration='fixed source reservoir complementary partitions x target reservoir subsets, all completed',
   scope_note='same-pool phase B space overlaps these cells; do not add theoretical capacities')
 selected=M[M.selected_for_new_finite_enumeration.eq('True')]
 caps.append(mcap('Manual_A_all_1325_ledger_cells',M,81221))
 caps.append(mcap('Manual_A_selected_249_cells',selected,81221))
 btheory=sum(map(integer,B.theoretical_unordered_source_ABC))
 caps.append(dict(space='Manual_B_20_new_background_cells',condition='Manual',cells=len(B),
  theoretical_physical_ABC=str(btheory),registered_physical_ABC=21000,unregistered_physical_ABC=str(btheory-21000),
  registered_background_references=sum(map(integer,B.new_backgrounds)),full_member_enumeration=False,
  finite_enumeration='two new D per selected n20/m4 cell; all 1050 finite-reservoir ABC per cell completed',
  scope_note='whole-pool denominator includes phase-A backgrounds; unregistered here means not in B, not absent from A+B'))
 for domain,d in T[T.status.eq('available')].groupby('source_domain'):
  theory=sum(map(integer,d.possible_unordered_XY_ABC));reg=sum(map(integer,d.registered_unordered_XY_ABC))
  caps.append(dict(space='Structure_n20_'+domain,condition='Manual',cells=len(d),
   feasible_background_class_vectors=sum(map(integer,d.possible_background_count_vectors)),
   observed_background_class_vectors=sum(map(integer,d.possible_background_count_vectors)),
   possible_concrete_backgrounds=str(sum(map(integer,d.possible_backgrounds))),
   registered_background_references=sum(map(integer,d.registered_backgrounds)),
   theoretical_physical_ABC=str(theory),registered_physical_ABC=reg,unregistered_physical_ABC=str(theory-reg),
   full_member_enumeration=False,finite_enumeration='all selected ABC-feasible count vectors; balanced concrete blocks and D',
   scope_note='new-only domain overlaps all-formal; linked n/m paths are separate and reuse endpoints'))
 ff=F[F.status.isin(['complete_cell','complete_registered_subspace'])]
 fe=E[E.line.eq('semi_joint')]
 ft=sum(map(integer,ff.theoretical_physical_ABC));fr=fe.canonical_physical_ABC.nunique()
 caps.append(dict(space='Semi_69_selected_cells',condition='Semi',cells=len(ff),
  feasible_background_class_vectors=sum(map(integer,ff.feasible_class_count_configs)),
  observed_background_class_vectors=fe.canonical_config.nunique(),
  possible_concrete_backgrounds=str(sum(map(integer,ff.feasible_distinct_background_sets))),
  registered_background_references=sum(g.canonical_background.nunique() for _,g in fe.groupby('cell_id')),
  theoretical_physical_ABC=str(ft),registered_physical_ABC=fr,unregistered_physical_ABC=str(ft-fr),
  full_member_enumeration=False,complete_full_member_cells=int(ff.full_cell_enumeration.eq('True').sum()),
  finite_enumeration='8 full cells; other selected finite member/background subspaces completed; 631/631 class configurations',
  scope_note='final registration used: 13,882 rows/6,941 physical/631 configs; capacity registered_* columns retain initial 6,500/190 stage'))
 C=pd.DataFrame(caps);outputs.append(save_csv('THEORETICAL_AND_FINITE_SPACES.csv',C))
 status=[]
 for reason,g in F.groupby('status'):status.append(dict(topic='Semi attempts',status=reason,units=len(g),unit='requested cell',source='semi/CAPACITY_ALL_ATTEMPTS.csv'))
 status += [dict(topic='Manual A capacity',status='registered_finite_enumeration_complete',units=len(selected),unit='feasible cell',source='manual_joint/CAPACITY_ALL_N_M.csv.gz'),
  dict(topic='Manual A capacity',status='feasible_but_not_selected',units=len(M)-len(selected),unit='feasible cell',source='manual_joint/CAPACITY_ALL_N_M.csv.gz'),
  dict(topic='Structure n20 capacity',status='available_and_registered',units=int(T.status.eq('available').sum()),unit='direction/domain/n/m cell',source='structure/CAPACITY_AND_COVERAGE.csv.gz'),
  dict(topic='Structure n20 capacity',status='insufficient_joint_capacity',units=int(T.status.ne('available').sum()),unit='attempted cell',source='structure/CAPACITY_AND_COVERAGE.csv.gz')]
 outputs.append(save_csv('COMPLETED_REUSED_NOT_DONE_OPPORTUNITY.csv',pd.DataFrame(status)))
 D=read('classification/DOMAIN_SUBSET_COVERAGE_26x2.csv')
 keep=['condition','domain_subset','domain_count','phase1_current_screen_status','phase1_current_screen_supported_workers',
  'phase1_current_composition_status','phase1_current_frozen_methods','phase2_n20_deep_research_status','phase2_n20_method_ids',
  'phase3_status','phase3_method_ids','closure_new_pure_domain_search','closure_new_pure_domain_labels','closure_status','closure_relation']
 outputs.append(save_csv('INHERITED_26_DOMAIN_STATUS.csv',D[keep]))
 hist=json.loads((NEW/'integration/historical/HISTORICAL_INDEX_RECEIPT.json').read_text())
 endpoint=json.loads((NEW/'delivery/endpoints/DELIVERY_RECEIPT.json').read_text())
 # Endpoint delivery receipt already establishes the combined control union.
 allrow=S[S.line.eq('all_lines_ABC')].iloc[0]
 map_small=E.groupby('line').agg(registrations=('event_id','size'),input_id_count=('input_physical_id','nunique'),canonical_count=('canonical_physical_ABC','nunique')).reset_index()
 outputs.append(save_csv('INPUT_ID_CONVENTION_COMPARISON.csv',map_small))
 # Human report generated from these exact small tables, no scientific re-audit.
 lines=['# 本轮完整覆盖账与历史继承身份','',
  '本文件只整合实际登记、完成范围与理论容量，不重算融合、评分或既有科学结论。底层真实数据 v2；v3 是既有研究轮次。',
  '', '## 1. 按真实成员统一去重', '',
  '统一物理ABC键为：`pool_id + 无序{排序后的A成员, 排序后的B成员} + 排序后的C成员`。C保持固定，A/B交换等价。端点键为`pool_id + 排序成员集合`，背景键为`pool_id + 排序D成员集合`。不使用各线不同算法生成的physical_triple_id作为跨线唯一证据；完整对应保存在PHYSICAL_REGISTRATION_MAP.csv.gz。',
  '', '| 研究线 | 登记／完成事件 | 唯一物理ABC | ABC端点 | 图／楼 | 实际D | 重复登记行 |', '|---|---:|---:|---:|---|---:|---:|']
 labels={'manual_joint_A':'Manual联合A','manual_joint_B':'Manual联合B','manual_structure':'Manual结构（含n/m路径）','semi_joint':'Semi联合（含配置补齐）','manual_joint_A_plus_B':'Manual联合A+B去重','all_manual_ABC':'全部Manual去重','all_lines_ABC':'全部条件去重'}
 for r in S.to_dict('records'):
  lines.append(f"| {labels[r['line']]} | {r['registered_events']:,}／{r['completed_registered_events']:,} | {r['canonical_physical_ABC']:,} | {r['exact_ABC_endpoints']:,} | {r['images']}／{r['buildings']} | {r['actual_backgrounds']:,} | {r['total_duplicate_registration_rows']:,} |")
 lines += ['', '表中图数按图片名称去重，Manual/Semi分别作为池和团队评价；同一图在两个条件出现不会混合原答。各行互有重叠，合计采用集合并集，不能相加。背景数也按实际D而非面板ID去重。',
  '', '重复登记有两种明确来源：Semi保留两种A/B朝向用于方向分析，13,882行等于6,941物理ABC；结构人数路径n20行和固定A路径最大m行引用主实验已有三队。重复登记有分析身份，不增加独立样本。阶段A/B及方法之间的重叠同样用真实成员键消除。',
  '', f"主ABC合计使用 **{int(allrow.exact_ABC_endpoints):,}** 个精确端点。连同连续Q/T及策略对照，中央交付共 **{endpoint['required_unique_endpoints']:,}** 个必需端点，其中新原生计算 **{endpoint['unique_new_native']:,}**、历史精确复用 **{endpoint['unique_reused_prior']:,}**。这些总量继承中央交付收据，不与各线请求引用数相加。", 
  '', '## 2. 人数配置、具体成员、背景、顺序分别说明', '',
  '- **Manual联合A**：容量台账完整列出1,325个可行图×方向×n/m单元、42,451个可行背景类别人数向量；实际选择249单元，其可行向量6,895、实际覆盖399个向量、484个登记背景面板。81,221个ABC全部完成。这里“完整配置台账”不等于所有配置均有新团队评价。',
  '- **Manual联合A的有限穷举**：每个登记D及2m人源储备、m至m+2人目标储备内，穷举所有无序互补m/m源分区×所有目标m人子集。全池和全部D仍未穷举。所选249单元的全池物理ABC理论总数为1,335,937,197,428,677，A阶段未覆盖1,335,937,197,347,456。',
  '- **Manual联合B**：目标条件在A结果后选择；20个n20/m4单元另选两个新背景，各完整枚举1,050个有限ABC，共21,000。背景选择不看目标终点评分。B的全池理论分母包含A已有背景，因此A/B理论容量不相加；B为新成员／背景内部检查，不是新建筑盲测。',
  '- **Manual结构**：所选n20条件3,073/3,073个ABC可行背景人数向量均有实际团队，其中全正式2,834、新来源239；有3,796个登记D。具体块和D按固定规则增加覆盖，没有声称全成员穷尽。无约束n20空间另列：全正式3,312/3,712向量、28,108/251,050,935,840成员集合；新来源域与其重叠，分别报告。',
  '- **Semi**：69个选定单元的631/631人数配置完成，8个小单元的全部具体成员与D也完整枚举；其余完成冻结的有限子空间。全池理论为7,081,487,700有向或3,540,743,850物理ABC，实际6,941物理，未覆盖3,540,736,909。CAPACITY_ALL_ATTEMPTS的registered_*列保留初始主层6,500物理／190配置，本整合按完整登记加配置补齐后的6,941／631计数，未改旧阶段列。',
  '- **加入顺序**：仅研究已登记的固定XYZ嵌套n路径、固定A嵌套m路径。相同成员集合的确定性终点只算一次，没有将所有加入排列都展开。',
  '', '各空间的精确整数、可行与未覆盖数见THEORETICAL_AND_FINITE_SPACES.csv及各线原容量表。不同方法、人员域及阶段的理论集合有重叠，故不制造一个可相加的“全球总组合数”。有限枚举优先增加具体成员及背景重复性，选择范围和计算预算已冻结；本轮注册缺口为0，全池未覆盖空间则明确保留。',
  '', '## 3. 已完成、复用、未做与机会不足', '',
  '- **本轮完成**：四份登记文件全部评价，失败仍在完成表中；完成是端点及指标状态已保存，不等于所有融合成功。主ABC、策略／连续对照、具体成员机制各保留身份。',
  '- **历史复用**：分类、楼外标签、旧大块替换、n10/m7结构结果、选队收益与负结果继续保留，不在本覆盖步骤重新核验。旧245候选是方法×适用域，旧QTDS的S是结构；已存在188正向候选、旧768/新1040真实关系候选和直接m2块学习，不能再写未实现。',
  '- **未做**：全部大池成员组合、全部D、全部加入顺序未穷尽；本轮未重新搜索26个纯变量域组合，未重做同房研究，也未将不同分类拼成一个统一层级。',
  '- **机会不足**：Semi容量表133个尝试单元缺类容量／总容量，424个不在登记方向，69个实际完成；结构容量台账的不足单元与其他训练家族单列。容量不足不是算法效果失败，未选方向不是已否定方向。',
  '', '## 4. 26个变量域子集的既有身份', '',
  '继承classification/DOMAIN_SUBSET_COVERAGE_26x2.csv的52行，逐项保持Manual/Semi与各阶段身份。本轮新结构+Q/T类别含结构域，不冒充新增纯Q+T子集；Semi自身分类也不冒充联合Manual+Semi分类。',
  '', '| 评价条件 | 既有筛查 | 机会不足 | 既有实际构成方法关联 | n20后续深入 |', '|---|---|---|---|---|',
  '| Manual | 26/26域子集 | 0个筛查域子集 | Q+T+D；T+D+scope+Semi | Q+T+D配置与匹配完成 |',
  '| Semi | 11/26域子集 | 15个域子集 | Q+T+scope+Semi | 配置及连续对照完成；旧n20/m≥4无容量 |',
  '', 'phase3还关联Q+T及上述QTD／QTscopeSemi方向的多人数／块端点；含结构的V3_JOINT_QT仅作为相关方法身份，不能把它计为新纯五域候选。52行简明继承表见INHERITED_26_DOMAIN_STATUS.csv，完整历史表保留全部方法、标签和阶段支持。',
  '', '## 5. 旧包与可下载数据', '',
  f"直接继承历史索引收据：**{hist['files']}个文件、{hist['complete_event_files']}个完整事件文件、{hist['complete_event_rows']:,}条历史事件记录**；其中expanded {hist['expanded_rows']:,}条、joint {hist['joint_complete_rows']:,}条。它们是历史文件行数，不与新物理ABC简单相加。历史下载链接检查为0缺失，旧56个端点批次文件已恢复；本步骤没有重新解压全部旧事件或复制旧大缓存。", 
  '', '入口：[历史下载索引](../historical/HISTORICAL_DOWNLOAD_INDEX_ZH.md)、[历史逐文件索引](../historical/HISTORICAL_DOWNLOAD_INDEX.csv)。新完整事件、端点和条件表分别在manual_joint、structure、semi及delivery/endpoints目录；用户可单独取得，不仅依赖ZIP。',
  '', '## 6. 本文件复现', '',
  '运行 `python research/workers/personnel_exchange_closure_20261022/integration/coverage/build_final_coverage.py`。只读取4份登记、既有小容量表及完成收据；按真实成员重算集合计数，不调用融合或评分。输入SHA、各线旧ID与规范ID数量、完整登记映射及输出SHA均在本目录保存。']
 (HERE/'COVERAGE_FINAL_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 outputs.append(dict(path='COVERAGE_FINAL_ZH.md',sha256=sha(HERE/'COVERAGE_FINAL_ZH.md')))
 receipt=dict(status='complete',underlying_data='real_v2',fusion_calls=0,scoring_calls=0,
  physical_identity='pool + unordered canonical actual A/B members + fixed canonical actual C members',
  aggregate=allrow.to_dict(),inputs=inputs,outputs=outputs,
  inherited_historical_receipt_sha256=sha(NEW/'integration/historical/HISTORICAL_INDEX_RECEIPT.json'),
  inherited_endpoint_receipt_sha256=sha(NEW/'delivery/endpoints/DELIVERY_RECEIPT.json'),
  prior_complete_event_files_reopened=0,
  mapping_delivery='PHYSICAL_REGISTRATION_MAP is optional regenerated identity mapping; exact original members remain in each full event/registration table',
  code_sha256=sha(Path(__file__)))
 (HERE/'COVERAGE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
 print(S.to_string(index=False));print(C.to_string(index=False))

if __name__=='__main__':main()
