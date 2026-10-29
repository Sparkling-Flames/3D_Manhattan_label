"""Readable complete example tables from saved distributions; no new experiment."""
from pathlib import Path
import pandas as pd
W=Path(__file__).resolve().parents[1]
O=W/'composition/OPPJOINT_K4_complete_configuration_cases'
d=pd.read_csv(O/'ALL_CONFIGURATIONS_Q_READABLE.csv')
notes={
'material_variation_median':('pa4-18：有实际均值差异，格内具体成员仍关键','该例来自构成间Q方差≥1的30个面板，选构成间方差占比最接近其中中位数的面板。924队、6个完整配比，0个失败。构成均值54.99—65.03，构成间方差占12.06%。q4有5人的两格均值61.32/65.03，但中位数55.30/55.62；均值改善包含部分具体成员得到较高分输出的作用，不代表每组都均匀改善。'),
'weak_separation':('yqst-29：完整弱区分对照','在总Q方差≥1的48个面板中，选构成间方差占比接近第10百分位者。924队、8个完整配比，0个失败。构成均值56.65—60.94，构成间方差仅占1.71%；具体成员仍能造成5.77—12.04的格内标准差。这张图没有随q4人数增加而一致改善的关系。'),
'all_panel_median':('VLz-02：全部可用面板的中位代表','在共同标签支持、n≥20、924队均可评分且至少3格的95个面板中，按构成间Q方差选中位面板。924队、18个完整配比，0个失败。总方差很小，均值96.09—97.70；构成间方差占39.16%与绝对质量变化较小同时成立。')}
text=['# OPPJOINT K4：三个有限成员面板的全部配比格','',
'下列n均为20，人数向量包含固定背景D。q1—q4是该目标建筑之外历史Q中心的顺序，逐折原类号、真实人员及D可在同目录关联表定位。每个面板固定14人，变量池12人选6，完整覆盖924个成员集合；不扩写为全人员池所有20人团队。所有分布来自现有v2.1端点，0新增融合。','',
'同格的均值、低尾和标准差描述具体成员变化；不同格没有人为平衡为同样团队数。汇总方差按真实集合频率计权。','']
for key,(title,note) in notes.items():
 z=d[d.case_id.eq(key)]
 text+=['## '+title,'',note,'','| q1/q2/q3/q4 | 团队数 | Q均值 | Q的5%分位 | Q中位 | 同格SD | 失败数 |','|---|---:|---:|---:|---:|---:|---:|']
 for r in z.itertuples():
  counts='/'.join(t.split(':')[1] for t in r.q_rank_counts.split('|'))
  text.append(f'| {counts} | {r.teams} | {r.Q_mean:.3f} | {r.Q_p05:.3f} | {r.Q_median:.3f} | {r.Q_within_sd:.3f} | {r.failed_teams} |')
 text+=['']
text+=['完整数值见 `ALL_CONFIGURATIONS_Q_READABLE.csv`；每队成员与端点见 `ALL_EXACT_TEAMS_AND_ENDPOINTS.csv.gz`；所有分项和时间按来源保存在 `ALL_CONFIGURATIONS_ALL_METRIC_DISTRIBUTIONS.csv.gz`。上述对比用于解释构成与成员两层变动，主分类的跨粗类严格ABC结论另由广筛与扩展实验支持。','']
(O/'CASE_TABLES.md').write_text('\n'.join(text),encoding='utf-8')
print({'cases':len(notes),'complete_cells':len(d),'output':str(O/'CASE_TABLES.md')})
