"""Render the capacity-preselected four-case report from saved complete results."""
from pathlib import Path
import argparse, json
import pandas as pd


def md_table(headers, rows):
    return '\n'.join(['|'+'|'.join(headers)+'|', '|'+'|'.join(['---']*len(headers))+'|']+
        ['|'+'|'.join(str(v) for v in row)+'|' for row in rows])


def f(v, digits=3):
    return '不可评' if pd.isna(v) else f'{float(v):.{digits}f}'


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--base', required=True); args=ap.parse_args()
    b=Path(args.base); c=b/'preselected_four_complete'; compact=c/'compact_tables_v2'
    teams=pd.read_csv(c/'PRESELECTED_8_17_10_TEAMS.csv.gz')
    edges=pd.read_csv(c/'PRESELECTED_8_17_10_CONTRASTS.csv.gz')
    pure=pd.read_csv(compact/'PURE_WHOLE_EQUAL_ANCHOR_SUMMARY.csv.gz')
    decomposition=pd.read_csv(compact/'TWELVE_PARENT_DECOMPOSITION_SUMMARY.csv.gz')
    selection=json.loads((b/'PRESELECTED_8_17_10_CASES.json').read_text())
    assert len(teams)==28 and len(edges)==84 and len(pure)==12 and len(decomposition)==12
    assert teams.team_key.nunique()==28 and edges.event_id.nunique()==84
    images=sorted(teams.image.unique())
    ordered=['C3','C2','C1','C2|C3','C1|C3','C1|C2','C1|C2|C3']
    names=['C3 (8)','C2 (10)','C1 (17)','C2+C3 (18)','C1+C3 (25)','C1+C2 (27)','全部 (35)']
    qt=[]; dt=[]
    for image in images:
        x=teams[teams.image.eq(image)].set_index('alliance_classes')
        qt.append([image]+[f(x.loc[a,'B8L2']) for a in ordered])
        dt.append([image]+[f(x.loc[a,'D10']) for a in ordered])
    pure_rows=[]; labor_rows=[]
    for r in pure.sort_values(['image','source_class','target_class']).to_dict('records'):
        pure_rows.append([r['image'],r['source_class']+'→'+r['target_class'],int(r['n']),
            f(r['B8L2_CA__mean']),f(r['D10_CA__mean']),
            f(r['B8L2_CA__min'])+' ～ '+f(r['B8L2_CA__max']),
            str(int(r['B8L2_CA__positive_pairs']))+'/8',
            f(r['geometry_bev_distance_AC__mean'],4)])
        valid=int(r['record_time_CA_seconds_source_matched__valid'])
        labor_rows.append([r['image'],r['source_class']+'→'+r['target_class'],valid,
            f(r['record_time_CA_seconds_source_matched__mean']),
            f(r['record_time_CA_seconds_source_matched__median']),
            str(int(r['record_time_CA_seconds_source_matched__positive_pairs']))+'/'+str(valid),
            str(int(r['record_time_CA_seconds_source_matched__negative_pairs']))+'/'+str(valid),
            f(r['record_time_CA_pct_source_matched__mean'])])
    decomp_rows=[]
    for r in decomposition.sort_values(['image','role_direction']).to_dict('records'):
        decomp_rows.append([r['image'],r['role_direction'].replace('->','→'),
            str(int(r['n_small']))+'→'+str(int(r['n_large'])),
            f(r['B8L2_CA__total_mean']),f(r['B8L2_CA__equal_mean']),
            f(r['B8L2_CA__equal_min'])+' ～ '+f(r['B8L2_CA__equal_max']),
            f(r['B8L2_CA__addition_mean']),r['parent_contrast_id']])
    roster=[]
    for p in selection['pools']:
        for class_id, members in p['class_members'].items():
            roster.append([p['image'],class_id,len(members),', '.join(members)])
    closures=pd.read_csv(c/'PRESELECTED_ALLIANCE_WHOLE_DECOMPOSITION.csv.gz')
    valid=closures.B8L2_CA__closure_error.dropna()
    assert len(valid)==48 and valid.abs().max()<1e-6
    doc='''# 35 人、17/10/8 三类的完整联盟与整类替换：四张预选图

## 1. 选择依据与本例能回答的问题

四图是 `pa4otMbVnkk-06、-11、-42、-44`，同属一栋楼，普通 Manual、原主目标、该楼外折的冻结 `OPPJOINT_K3` 标签。它们在本轮读取新结果之前，因容量恰为 C1=17、C2=10、C3=8 而被预选；没有依据目标图 Q 或替换收益筛选。每图实际有 35 个合格成员，未知标签为 0。

每图三个完整类别的七种非空联盟全部保留：8、10、17、18、25、27、35 人；七队全部 21 对比较均计算。四图合计 28 个端点、84 个无向对。三条双类联盟互换边，另连到每条四个已登记的等人数中间队，共 12 条父对照、48 条路径。补充的同人数纯类锚点共有 12 个条件、96 个物理对。所有结果均来自本轮已经执行的团队，没有为此新造分类、参考、目标空间或额外融合。

这一组主要回答：接近实际人员池时，完整类别与混合联盟怎样改变共识；某条不等人数的整类变化，沿明确的等人数中间队可以怎样拆开。四图仅一栋楼，C3 八人完全相同；它不能替代跨楼覆盖，也不能把四图或 48 条路径当作相互独立的人员重复。

标签的解释来自楼外历史：C1 人数多、历史 Q 较低、来源内记录劳动较短；C2 转折和复杂机会转折较少、相对面积较小；C3 转折和复杂机会转折较多、历史 Q 较高、来源内劳动较长、面积和高度较大。这些是历史群体画像，并非承诺本图必然按 Q 排序。

## 2. 七种完整联盟：所有结果一起看

以下 B8L2 与 D10 均为保存的正式评分，不把缺分填零。28 队均为 `complete_conditional`，并均有这两个分数。06、42、44 的七队各有四个节点和四个有效转折；11 的七队各有八个节点和八个有效转折。因此，本组联盟间的主要变化不能解释成这七队之间的节点数增减。

### B8L2

'''+md_table(['图片']+names,qt)+'''

### D10

'''+md_table(['图片']+names,dt)+'''

06、42、44 的 C3 单类及含 C3 联盟多处于高分区间，但增加其余成员并不保证继续升高。11 的七队共同低分，C3 较高也只达到约 29.73。全 35 人并未消除这类共同响应；不能由“人数很多、节点全员支持”推导参考一致。

原始 84 对逐边文件还保留面积百分比、高度百分比、重心位移、底面形状距离、质量分项及输出状态，位于 `preselected_four_complete/PRESELECTED_8_17_10_CONTRASTS.csv.gz`。其中 `geometry_bev_distance_AC` 是底面多边形的 1−IoU，非米制距离；重心距离使用 h，面积使用 h²。对称几何距离没有改善/恶化方向，不能与 Q 的有符号差混读。

## 3. 相同人数的纯类锚点：保留成员变化

这三种等人数锚点的 D 为空：C1 抽 10 人换成完整 C2 十人；C1 抽 8 人换成完整 C3 八人；C2 抽 8 人换成完整 C3 八人。每图每方向均有八种来源成员组合，目标完整小类固定。它们支持观察具体成员的不确定性，但没有同类 B，不能写成“跨类一定比同类变化大”。

'''+md_table(['图片','方向','n=m','ΔB8L2 均值','ΔD10 均值','ΔB8L2 范围','Q 上升对数','平均底面 1−IoU'],pure_rows)+'''

这张表有两个互补结论。C3 整类换入在本组所有八种来源组合中均提高 B8L2；与此同时，幅度明显依赖被换出的具体成员，例如 44 的 C1→C3 从约 +2.20 到 +22.53。历史 Q 中间角色也不会在每图占优：06 的 C1→C2 八对全部降 Q，42、44 的同一方向则同时有正和负成员组合。这些反例应保留在联合画像的使用边界中。

### 记录劳动有独立的有效分母

下表只用双方全部记录时间已知、来源计数向量一致的对。它是合格原答的记录劳动总量，不是融合计算时长或并行团队墙钟时间。不同来源的原始总和不视作合法可比劳动；有效对数不足八的原因保存在端点来源签名中。

'''+md_table(['图片','方向','合法对数','Δ秒均值','Δ秒中位数','增加对数','减少对数','每对 Δ% 的均值'],labor_rows)+'''

11 的 C2→C3 尤其说明均值和多数方向必须并列：八对 Q 全部提高，但劳动六对减少、两对增加；Δ秒中位数约 −26.175，均值却为 +10.6445，范围 −125.130 到 +376.622 秒。06、42、44 的同一方向则八对全部增加劳动。因此，“本组 C3 往往升 Q”与“劳动响应受图片和被替换成员影响”可以同时成立。

完整联盟端点的劳动限制更严格。C1 含一份旧来源原答，其余主要为新来源；七队人数全不相等，因此每图 21 对中来源计数严格匹配为零。仅 C2、C3、C2+C3 三个同一单来源团队之间的三对，可在 `*_single_source` 字段下研究不等人数的记录劳动，即每图 3/21、四图合计 12/84；这仍与等人数来源计数匹配不是同一口径。

## 4. 双类联盟两两比较：明确的三段路径

三种父对照的 D 分别是整个第三类：

- D=C1 的 17 人，完整 C3 八人→完整 C2 十人，团队 25→27 人。
- D=C2 的 10 人，完整 C3 八人→完整 C1 十七人，团队 18→27 人。
- D=C3 的 8 人，完整 C2 十人→完整 C1 十七人，团队 18→25 人。

对每个父对照，从人数较大的目标类抽等量成员构成四个中间队。先等人数换类，再加入该目标类的剩余成员。每条路径的质量标量满足“总差=等人数差+追加成员差”；下表的父对照总差只计一次，中间两段取四条路径均值。各路径的成员、团队 key、父 ID、实际公共成员全部保留。追加段的实际公共成员包含已经换入的目标子集，不能把父 D 当作追加段的完整交集。

'''+md_table(['图片','被换整类方向','团队人数','总 ΔQ','等人数 ΔQ 均值','等人数 ΔQ 范围','追加成员 ΔQ 均值','父对照 ID'],decomp_rows)+f'''

48 条路径的 B8L2 加法闭合误差最大为 {valid.abs().max():.3g}，支持精确回连。这里的加法关系适用于有符号质量标量；百分比需要按端点比值复合，底面 1−IoU 等距离不满足该加法关系。

42 和 44 的 C2→C1（D=C3，18→25 人）最能说明为什么需要中间队：最终均降 Q，但等人数段的平均值分别约 +0.012 与 +0.091，成员路径内部有正有负；追加七位具体 C1 成员的平均差分别约 −0.528 与 −0.571。不能把整条结果简单归因于类别，也不能把第二段叫作与身份无关的纯人数效应。它是该目标类、这些剩余成员及这条加入顺序下的明确路径。

06 的同一路径总差仅约 +0.081，却由等人数 +0.274 与追加 −0.193 抵消而成。小总差不等于没有可解释的内部变化。其余双类联盟的 C3 换出多数降低 Q；正负分量、成员范围和完整父对照全部保留。

## 5. 原答、参考、票账对机制的限制

### 06：高分区间的位置和尺度响应

原图和 35 份完整原答、七队完整融合几何与票账已在 `../stage06_cases/alliance_pa4_06/` 保存。35 份原答均为四对角点；七队的 28 个身份组均为全员支持，连接有效。这不是因部分结构节点落选造成的差异，而是相同结构表达下的位置、尺度、顶部及评分分项响应。Q 高并不意味着每个端点完全相同；也不宜把约 98～99 的小变化推广为所有图都近乎不变。

### 11：共同八点表达与当前四点参考不一致

`../stage06_cases/alliance_pa4_11/PA4_11_ALLIANCE_VIEWER_ZH.html` 可直接查看原图、完整原答、七队、参考和票账。当前参考是四角点矩形；35 份完整原答全是八角点，都表达右侧凸出/入口轮廓。七队共 56 个身份组全员支持，八节点环及连接均有效，没有未选节点或融合失败。这张图的低 Q 不能解释为融合漏掉了应过票的结构。

C3 对当前参考的底面边界较接近，故 Q 较高，但它仍保留同一个八点轮廓。C3 的 IoU3D×100≈69.635，底面角距离≈7.897°，参考节点/边在 5° 内保留率为 1.0/0.75；其他联盟多数更低。该差异可以解释评分变化，却不能仅凭当前参考判定所有八点原答都错。

**需要人工判断的具体问题**：查看 11 原图 ERP 横向约 x=525～1010 的右侧凸出/入口，以及参考 r2–r3 的闭合线段，判断此轮目标空间是否应包含该轮廓。此次研究不更改正式参考、目标归属或人员资格。若目标语义必须保持当前四点边界，这是一例多数成员共享的偏差；若语义判断支持凸出轮廓，则需要另行处理参考与目标表达的关系，不能通过本轮重新选高 Q 参考消除它。

七队的节点支持均超过 MV50；替换块人数能否单独达到阈值只是必要容量说明，并不在这两个案例中产生“某类独立决定节点入选”的证据。全员节点票也不能替代位置估计和连接过程；两例已检查完整状态，未仅使用被选节点票数推断机制。

## 6. 精确人员与数据入口

C3 的固定八人为 W102、W109、W112、W115、W121、W122、W126、W130；完整换入时八人每次都出现，属于固定核心。这组没有更多同类成员可供对这八人本身做同图同类扰动。C1 四图共享 16 人；C2 任意两图共享 9～10 人，四图共同 8 人；全部类别合计四图共同 32 人。各图全 35 人集合并不相同。

'''+md_table(['图片','类别','人数','实际成员'],roster)+'''

完整可回连文件：

- `PRESELECTED_8_17_10_CASES.json`：算前选型、各图人员池和两图间身份差异。
- `PRESELECTED_8_17_10_REGISTERED_TEAMS.csv` 与 `PRESELECTED_8_17_10_REGISTERED_CONTRASTS.csv`：冻结登记与方向。
- `preselected_four_complete/PRESELECTED_8_17_10_TEAMS.csv.gz`：28 队分数、分项、结构、几何、劳动来源、状态。
- `preselected_four_complete/PRESELECTED_8_17_10_CONTRASTS.csv.gz`：84 对完整指标。
- `preselected_four_complete/PRESELECTED_ALLIANCE_WHOLE_DECOMPOSITION.csv.gz`：48 条路径与端点 ID。
- `preselected_four_complete/compact_tables_v2/PURE_WHOLE_EQUAL_ANCHOR_EVENTS.csv.gz`：96 条等人数纯类事件；同目录两个 SUMMARY 是本报告表格来源。
- `../stage06_cases/alliance_pa4_06/`、`../stage06_cases/alliance_pa4_11/`：原图、完整原答、参考、七队几何与完整票账。

上述数据文件均保留 CSV 宽度和 gzip 读至 EOF 的可读性回执。完整全范围结论应与本轮 206 个原主目标 Manual 图、固定成员/固定背景敏感性和严格 ABC 共同解读；本报告只是按容量预选的一栋楼完整案例组。
'''
    (b/'PRESELECTED_FOUR_CASES_REPORT_ZH.md').write_text(doc,encoding='utf-8')
    print(json.dumps({'report':str(b/'PRESELECTED_FOUR_CASES_REPORT_ZH.md'),'teams':28,'contrasts':84,'decomposition_paths':48,'pure_equal_events':96},ensure_ascii=False))


if __name__=='__main__':main()
