"""Expose already-frozen ALL rosters; never use them to form per-image teams."""
import hashlib,json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage08_report';OUT.mkdir(exist_ok=True)
source=ROOT/'stage00_intake/FINAL_LABELS_FOR_AC_ALL_LOBO.csv.gz'
d=pd.read_csv(source,low_memory=False);a=d[d.heldout_building.eq('ALL')].copy()
a.to_csv(OUT/'FROZEN_ALL_DESCRIPTIVE_PERSONNEL.csv',index=False,encoding='utf-8-sig')
rows=[]
for (method,cls),g in a.groupby(['method','class_id'],dropna=False):
    rows.append({'method':method,'class_id':cls if pd.notna(cls) else 'UNCLASSIFIED',
      'people':len(g),'workers':'|'.join(sorted(g.worker_id)),
      'use':'descriptive ALL only; actual pool capacity uses target-building-held-out labels and eligible originals'})
pd.DataFrame(rows).to_csv(OUT/'FROZEN_ALL_DESCRIPTIVE_CLASS_MEMBERS.csv',index=False,encoding='utf-8-sig')
(OUT/'ROSTER_READING_GUIDE_ZH.md').write_text('''# 名单和角色的读取方式

`FROZEN_ALL_DESCRIPTIVE_PERSONNEL.csv` 与 `FROZEN_ALL_DESCRIPTIVE_CLASS_MEMBERS.csv`
只从已经冻结的 ALL 标签抽取五种配置的描述名单，没有重新分类。
ALL 的类别编号与某个楼外折的编号、容量、人员身份不保证相同。

实际组队必须查 `stage01_capacity/POOL_CLASS_MEMBERS.csv.gz`：每行固定图片、目标、
条件、heldout_building、方法及类别，列出该图有合格原答的具体人员与原答 ID。
`FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv` 是本轮实际使用的 22 个楼外折角色与父类表；
文件名中的 ALL_LOBO 表示全部楼外折，它不含 ALL 描述行。
`FROZEN_LABELS_USED_ALL_LOBO.csv.gz` 同样只含 22 折，共 9,548 行。
完整入口 `stage00_intake/FINAL_LABELS_FOR_AC_ALL_LOBO.csv.gz` 则含 9,548 折内行
及五种方法的 ALL 310 行，共 9,858 行。

人员类别只是按冻结历史形成的解释角色，不是永久能力等级。
正文普通 Manual 的 TARGET/RAW3 方向按困难转折残差秩，OPPSTRUCT 按结构机会转折秩，
OPPJOINT 按历史 Q 秩，RFUSE 按其已冻结的响应角色。
所有事件也保存原 class_id、role_axis、source_role_rank、target_role_rank 和原方向。
Semi 使用已有自身标签，类别编号不直接等同普通 Manual 的角色秩。

真正采用某个替换组合时，最终身份以 `stage01_registered/AC_EVENTS.csv.gz` 的 D/X/Z、
两队 team_key 与 `TEAM_REQUESTS.csv.gz` 的精确人员和原答 ID 为准。
全历史的 10、12 或 17 人名单不能替代逐图容量。
''',encoding='utf-8')
receipt={'source':str(source.relative_to(ROOT)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'ALL_rows':len(a),'ALL_methods':sorted(a.method.unique()),'new_labels':0,'used_for_team_selection':False}
(OUT/'ROSTER_EXPORT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(receipt,ensure_ascii=False))
