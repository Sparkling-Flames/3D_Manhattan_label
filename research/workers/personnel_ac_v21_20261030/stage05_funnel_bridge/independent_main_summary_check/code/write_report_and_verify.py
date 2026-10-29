"""Document the narrow independent checks and the three whole-class definitions."""
from pathlib import Path
import csv,gzip,hashlib,json
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parents[1];BASE=OUT.parents[1]
MODES=['whole_source_out_only','whole_target_in_only','both_whole_equal']
NAMES={'whole_source_out_only':'整来源换出（仅来源全类）','whole_target_in_only':'整目标换入（仅目标全类）','both_whole_equal':'两类等人数全部互换'}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def table(d):
 def cell(x):
  if pd.isna(x):return '—'
  if isinstance(x,float):return str(int(x)) if x.is_integer() else f'{x:.6f}'
  return str(x).replace('|','\\|')
 return '\n'.join(['| '+' | '.join(cell(c) for c in d.columns)+' |','| '+' | '.join(['---']*len(d.columns))+' |']+
   ['| '+' | '.join(cell(x) for x in r)+' |' for r in d.itertuples(index=False,name=None)])
def save(d,name):
 with open(OUT/name,'w',encoding='utf-8-sig',newline='') as f:d.to_csv(f,index=False)
def main():
 a=pd.read_csv(OUT/'INDEPENDENT_REPRESENTATIVE_SUMMARY.csv');s=pd.read_csv(OUT/'WHOLE_DEFINITION_SPLIT_SUMMARY.csv');par=pd.read_csv(OUT/'PARENT_SUMMARY_PARITY_BY_FIELD.csv')
 assert par.passed.all()
 keys=['analysis_view','scope','condition','layer','method','role_direction','n_condition','m_condition','pure_n_equals_m','metric']
 grid=[]
 counts=['registered_pools','registered_images','registered_buildings','registered_pairs','valid_pairs','valid_pools','valid_images','valid_buildings',
         'positive_images','negative_images','tied_images','positive_buildings','negative_buildings','tied_buildings']
 for key,g in s.groupby(keys,dropna=False,sort=True):
  for mode in MODES:
   row=g[g.whole_definition.eq(mode)]
   if len(row):r=row.iloc[0].to_dict();r['registered_stratum_present']=True
   else:r=dict(zip(keys,key),whole_definition=mode,registered_stratum_present=False,**{k:0 for k in counts})
   r['whole_definition_zh']=NAMES[mode];grid.append(r)
 grid=pd.DataFrame(grid);save(grid,'WHOLE_DEFINITION_COMPLETE_SUPPORT_GRID.csv')
 pick=(grid.method.eq('TARGET_DSTRUCT_K3')&grid.role_direction.isin(['1->2','1->3','2->3']))|(grid.method.eq('OPPJOINT_K3')&grid.role_direction.isin(['1->2','1->3','2->3']))
 brief=grid[pick&grid.scope.eq('primary')&grid.metric.eq('B8L2_CA')&~grid.pure_n_equals_m].copy()
 cols=['method','role_direction','n_condition','whole_definition_zh','registered_images','valid_images','valid_buildings','registered_pairs','valid_pairs',
       'actual_n_A_min','actual_n_A_max','actual_m_X_min','actual_m_X_max','image_mean','image_balanced_mean_absolute','positive_images','negative_images','positive_buildings','negative_buildings']
 save(brief[cols],'MAIN_WHOLE_DEFINITION_BRIEF_B8L2.csv')
 selected=brief[brief.n_condition.astype(str).eq('20')][['method','role_direction','whole_definition_zh','registered_images','valid_images','valid_buildings',
   'actual_m_X_min','actual_m_X_max','image_mean','image_balanced_mean_absolute','positive_images','negative_images']]
 selected.columns=['方法','角色方向','整类定义','登记图','可评图','可评楼','m最小','m最大','均值ΔQ','平均绝对ΔQ','正图','负图']
 ae=a[['method','role_direction','n_condition','m_condition','metric','registered_pairs','valid_pairs','valid_images','valid_buildings','image_mean','image_balanced_mean_absolute','positive_images','negative_images']]
 diff=pd.read_csv(OUT/'NEUTRAL_A_VS_BROAD_FUNNEL_EXPLANATION.csv')
 ds=diff[['method','role_direction','n','m','metric','neutral_A_mean','broad_funnel_mean','mean_difference_neutral_minus_broad','neutral_A_registered_pairs','broad_funnel_registered_pairs']]
 receipt=json.loads((OUT/'INDEPENDENT_REBUILD_RECEIPT.json').read_text())
 report=f'''# 定向独立核验与等人数整类定义拆分

## 1. 核验结论

直接从最终 `stage01_registered/AC_EVENTS.csv.gz`、`DESIGN_LINKS.csv.gz` 和
`stage04_metrics/metric_shards/` 重建了三个指定 neutral_members_0 条件。
没有导入主分析实现，而用独立 Python 字典及 math.fsum 计算事件→池→图→楼的等权均值。
主汇总已发表的 6 个条件×指标行全部复现；加上整类三种定义重新合并后的主表核验，
共比较 **{len(par):,} 个数值字段**，分母及正负计数全部相同，最大绝对差
**{par.difference.abs().max():.3g}**，仅为浮点加总顺序差。

{table(ae)}

普通 Manual、primary、同 n/m、同角色方向、A_equal_AC、neutral_members_0，缺Q保留NaN。
valid_pairs 是两端该质量指标均可评的事件数，valid_images/buildings 使用其自身有效分母。
图片方向依据逐图均值，不以事件多数替代图片多数；楼方向依据等权图片形成的逐楼均值。
平均绝对变化先在池内计算事件绝对变化，再等权池与图片，并非对最终均值再取绝对值。

## 2. 为什么与较宽漏斗的数值不同

本核验的主口径只使用 A_equal_AC 的 neutral_members_0。
既有容量漏斗汇总全部已登记的等人数纯类块事件，包括额外背景策略与符合条件的其它设计族，
先在精确 X/Z 内平均登记背景，再平均块。研究范围和权重不同，二者不应数值相同。
以下逐行对照保留差值，没有覆盖任一旧结果。

{table(ds)}

例如 TARGET n20/m7、2→3，neutral0 为680个登记事件，较宽漏斗为2,144个；
JOINT3 n20/m10、1→2 分别为656与3,263个；RAW n23/m12、1→2 分别为32与48个。
主口径适合清楚的统一背景策略比较，较宽漏斗说明全部登记范围，不能把这两种均值混成同一估计量。

## 3. 三种等人数整类定义

新增分析限定 B_equal_whole_class + neutral_members_0，保持原 frozen canonical A→C 方向。
“整类”使用该池该LOBO折的实际可用人员，三类互斥：

- **整来源换出**：whole_source=true、whole_target=false，X为整个来源类，Z为目标类等量子集；C中不再保留来源类。
- **整目标换入**：whole_source=false、whole_target=true，Z为整个目标类，X为来源类等量子集；A中没有目标类，C中加入全部目标类。
- **两类等人数全部互换**：两标记均true，两个类别在该池容量相同，X/Z各为整类，D只来自两类以外人员。

第一类可以在D中已有目标类成员；第二类可以在D中保留来源类成员。
因此，“整来源换出”与“整目标换入”不能合成同一句人员操作。
若把 A/C 方向反过来，前两种定义相互转换、效果符号反转，但仍是同一物理端点对，不增加独立证据。
不等人数的两整类交换属于原有 B_unequal_whole_classes，此处没有将其混入等人数结果。

分析覆盖 **{receipt['whole_definition_selected_unique_events']:,} 个不同方法事件**，
由于部分事件既满足 n20 又位于 N−m 前沿，视图行共 **{receipt['whole_definition_selected_view_events']:,}**，
不能把两个视图直接累加。指标只计算 B8L2、D10，保存各自分母。
主目标与其他准入空间分别汇总。N−m 前沿的 n=m 无共同背景情形独立命名 `_pure_class`，没有混入有背景结果。

### n20 的主分类与 JOINT3 示例

下表给出三种定义的完整格子，0登记表示该固定方向/条件没有这一模式的登记事件，Q留空。
全部七方法、角色方向、n20/前沿、两种质量指标在 `WHOLE_DEFINITION_COMPLETE_SUPPORT_GRID.csv`。

{table(selected)}

其中 TARGET 2→3 的185图全部是“整目标换入”，m为1–8；不是把整块较大的来源类别全部换掉。
TARGET 1→2 的186图全部是“整来源换出”，m为1–11。
TARGET 1→3则分为来源全出122图、目标全入57图、两边全换7图（其中6图Q可评）。
这种区分是本轮对原合并“整类”结论的语义补充，而不是改动原事件。

### N−m前沿与实际人数

每个池选择 n=N−m，此时固定X/Z以后D为全部剩余人员。
这在不同池仍可有不同n、m，不等于固定团队人数实验。
例如 TARGET 2→3 整目标换入在前沿登记205图、可评200图、22楼，n为5–32，m为1–8；
图片均值ΔB8L2=2.390479，平均绝对变化4.895582，156正、44负。
该范围与n20的185图不同，不能仅对比两行总体均值就断言背景人数的纯作用。
固定精确X/Z改变n/D的解释应接续成员背景敏感性分析。

## 4. 怎样使用三类结果

原 `whole_equal_fixed_n_all_m` 与 `whole_equal_pool_frontier` 合并表仍然有用途：它们描述所有合法等人数整类调整的广覆盖。
新增拆分表回答具体把哪一类全部换出/换入。
每个分层有自己的类别容量、图片集、m范围和具体成员，不能把三种模式的均值差直接当成随机分配的模式因果效应。
也不能把source-only、target-only和both的均值简单平均来还原主表；应回到原事件重新经过池→图→楼聚合。
本目录已这样重新合并，并逐字段复现原主表，证明分层没有丢失或新增事件。

## 5. 文件及复现

- `INDEPENDENT_REPRESENTATIVE_SUMMARY.csv`、`INDEPENDENT_REPRESENTATIVE_IMAGE_METRICS.csv`：三个代表口径及逐图证据。
- `REPRESENTATIVE_EXACT_SELECTED_EVENT_METRICS.csv.gz`：1,368个精确事件、成员与原两端质量。
- `WHOLE_DEFINITION_SELECTED_EVENT_METRICS.csv.gz`：整类分层的精确事件与两个分析视图。
- `WHOLE_DEFINITION_SPLIT_SUMMARY.csv`：实际存在分层的288个指标汇总行。
- `WHOLE_DEFINITION_COMPLETE_SUPPORT_GRID.csv`：补齐每个实际方向/条件的三定义空格，缺模式不填Q=0。
- `WHOLE_DEFINITION_POOL_METRICS.csv.gz`、`WHOLE_DEFINITION_IMAGE_METRICS.csv`、`WHOLE_DEFINITION_BUILDING_METRICS.csv`：池、图、楼的完整聚合链。
- `PARENT_SUMMARY_PARITY_BY_FIELD.csv`：主汇总逐字段差值；包括将三定义重新合并后的验证。
- `NEUTRAL_A_VS_BROAD_FUNNEL_EXPLANATION.csv`：与原宽漏斗逐项范围差异。
- `INDEPENDENT_REBUILD_RECEIPT.json`：源文件和所有使用分片的SHA-256、计算定义及完整计数。
- `code/`：独立复现代码；无新增融合、评分、分类或资格审查。

本子目录是新增定向核验，原正式漏斗目录中的结果及回执保持不变；本子目录有单独文件完整性清单。
'''
 (OUT/'README_ZH.md').write_text(report,encoding='utf-8')
 # The old final manifest is a fixed list, so adding this subdirectory does not
 # alter or silently expand the previous verification scope.
 old=pd.read_csv(OUT.parent/'FINAL_STAGE05_MANIFEST.csv');oldchecks=[]
 for row in old.itertuples():
  p=OUT.parent/row.path;actual=sha(p);oldchecks.append(dict(path=row.path,expected_sha256=row.sha256,actual_sha256=actual,unchanged=actual==row.sha256))
 assert all(r['unchanged'] for r in oldchecks);save(pd.DataFrame(oldchecks),'ORIGINAL_FUNNEL_MANIFEST_UNCHANGED.csv')
 manifest=[]
 for p in sorted(OUT.rglob('*')):
  if not p.is_file() or '__pycache__' in p.parts or p.name in ['SUBDIRECTORY_MANIFEST.csv','READABILITY_RECEIPT.json']:continue
  row={'path':str(p.relative_to(OUT)),'sha256':sha(p),'bytes':p.stat().st_size,'rows':None,'columns':None}
  if p.name.endswith('.csv') or p.name.endswith('.csv.gz'):
   with (gzip.open(p,'rt',encoding='utf-8-sig',newline='') if p.name.endswith('.gz') else open(p,'r',encoding='utf-8-sig',newline='')) as f:
    rr=csv.reader(f);head=next(rr);assert len(head)==len(set(head));n=0
    for line in rr:assert len(line)==len(head),(p,n);n+=1
   row.update(rows=n,columns=len(head))
  elif p.name.endswith('.json'):json.loads(p.read_text())
  elif p.name.endswith('.py'):compile(p.read_text(),str(p),'exec')
  else:p.read_text(encoding='utf-8')
  manifest.append(row)
 save(pd.DataFrame(manifest),'SUBDIRECTORY_MANIFEST.csv')
 proof={'status':'passed','files':len(manifest),'bytes':sum(r['bytes'] for r in manifest),'all_csv_gzip_fully_read_to_EOF':True,
  'all_json_fully_parsed':True,'all_python_compiled':True,'original_formal_funnel_files_unchanged':len(oldchecks),
  'whole_definition_support_grid_rows':len(grid),'absent_mode_rows_Q_not_imputed':int((~grid.registered_stratum_present).sum()),
  'no_new_fusion_or_scores':True,'archive_internal_readability_not_claimed':True}
 (OUT/'READABILITY_RECEIPT.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False));print(json.dumps(proof,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
