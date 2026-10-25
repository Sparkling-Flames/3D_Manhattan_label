#!/usr/bin/env python3
"""Prepare report excerpts/member linkage from saved results; writes only here."""
from pathlib import Path
import csv, hashlib, json
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
DOC_COMMIT = 'e88d1d443f4000715a50475e085a773661be9c04'
DATA_COMMIT = '972857b2b3f548316be215400e42d6ef6e639250'
OLD_BASE = OUT/'sources/research/workers/personnel_main_figures_v2_20261023/data'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def md_table(headers, rows):
    def cell(v):
        if pd.isna(v): return '未知'
        return str(v).replace('|', '、').replace('\n', ' ')
    return '| ' + ' | '.join(headers) + ' |\n|' + '|'.join(['---']*len(headers)) + '|\n' + '\n'.join('| ' + ' | '.join(cell(x) for x in row) + ' |' for row in rows)

def main():
    new = pd.read_csv(WORK/'classifications/CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz', low_memory=False)
    new_all = new.loc[new.heldout_building.eq('ALL')]
    rev = pd.read_csv(WORK/'reverse/REVERSE_LABELS_ALL.csv')
    defs = pd.read_csv(WORK/'classifications/CANDIDATE_CLASS_DEFINITIONS_COMPLETE_ALL.csv')
    rdefs = pd.read_csv(WORK/'reverse/REVERSE_CLASS_CENTERS_ALL.csv')
    histories = pd.read_csv(WORK/'features/HISTORY_FEATURES_ALL_LOBO.csv.gz')
    histories = histories.loc[histories.heldout_building.eq('ALL')]
    old = pd.read_csv(OLD_BASE/'CLASSIFICATION_MEMBERS.csv')
    inventory = []
    for stage, frame, src in [('new_original_features',new_all,'classifications/CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz'),('new_fusion_response',rev,'reverse/REVERSE_LABELS_ALL.csv')]:
        for method, z in frame.groupby('method',sort=True):
            known = z.loc[z.known.eq(True)]
            inventory.append({'method':method,'candidate_stage':stage,'family':z.family.iloc[0], 'input_conditions':z.input_conditions.iloc[0], 'k':z.k.iloc[0], 'all_known_people':len(known),'all_unknown_people':len(z)-len(known),'all_class_sizes':'|'.join(f'{cl}:{len(p)}' for cl,p in known.groupby('class_id')), 'all_unknown_members':'|'.join(sorted(z.loc[~z.known,'worker_id'])), 'label_source':src,'label_use':'ALL descriptive; evaluation uses matching heldout_building'})
    pd.DataFrame(inventory).to_csv(OUT/'FEATURE_AND_REVERSE_CANDIDATE_INVENTORY.csv',index=False)

    d = new_all.loc[new_all.method.eq('DSTRUCT_K3')].copy()
    d['label_source'] = 'classifications/CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz'
    d = d.merge(histories[['worker_id','m_all_images','m_all_buildings','m_easy_images','m_easy_buildings','m_hard_images','m_hard_buildings']],on='worker_id',how='left',validate='one_to_one')
    r = rev.copy();r['label_source']='reverse/REVERSE_LABELS_ALL.csv'
    cols=['method','worker_id','class_id','known','missing_reason','origin','heldout_building','label_stage','input_conditions','label_source']
    together=pd.concat([d[cols+['m_all_images','m_all_buildings','m_easy_images','m_easy_buildings','m_hard_images','m_hard_buildings']],r[cols+['all_images','all_buildings','easy_images','easy_buildings','hard_images','hard_buildings']]],ignore_index=True)
    together.to_csv(OUT/'CLASS_MEMBERS_ALL.csv',index=False)
    dd = defs.loc[defs.method.eq('DSTRUCT_K3')]
    dd.to_csv(OUT/'DSTRUCT_K3_CLASS_CENTERS_ALL.csv',index=False)
    rdefs.to_csv(OUT/'REVERSE_CLASS_CENTERS_ALL.csv',index=False)

    cross = d[['worker_id','class_id','known','missing_reason']].rename(columns={'class_id':'dstruct_k3_all_class','known':'dstruct_known'})
    for scheme,prefix in [('manual_structure','old_structure'),('manual_joint_qt','old_joint')]:
        z=old.loc[old.scheme_id.eq(scheme),['worker_id','coarse_label','fine_label','name_zh','known']].rename(columns={c:prefix+'_'+c for c in ['coarse_label','fine_label','name_zh','known']})
        cross=cross.merge(z,on='worker_id',validate='one_to_one')
    cross.to_csv(OUT/'DSTRUCT_K3_OLD_ALL_MEMBERS.csv',index=False)
    cw=[]
    for prefix in ['old_structure','old_joint']:
        for (nc,oc),z in cross.groupby(['dstruct_k3_all_class',prefix+'_coarse_label'],dropna=False):
            cw.append({'new_method':'DSTRUCT_K3','new_all_class':nc,'old_scheme':prefix,'old_all_class':oc,'people':len(z),'members':'|'.join(sorted(z.worker_id))})
    pd.DataFrame(cw).to_csv(OUT/'DSTRUCT_K3_OLD_ALL_CROSSTAB.csv',index=False)
    old_lobo=pd.read_csv(WORK/'classifications/NEW_OLD_LABEL_CROSSWALK_SUMMARY.csv')
    old_lobo.loc[old_lobo.method.eq('DSTRUCT_K3')].to_csv(OUT/'DSTRUCT_K3_OLD_LOBO_CORRESPONDENCE.csv',index=False)
    frozen=pd.read_csv(WORK/'design/screen/FROZEN_LABELS.csv.gz')
    oldf=frozen.loc[frozen.candidate_origin.ne('new_20261025')]
    oldf.groupby(['method','tier','candidate_origin','label_source'],dropna=False).agg(label_rows=('worker_id','size'),folds=('heldout_building','nunique'),distinct_people=('worker_id','nunique')).reset_index().to_csv(OUT/'SCREEN_REUSED_BASELINE_INVENTORY.csv',index=False)

    methods=pd.read_csv(WORK/'analysis/screen/METHOD_N_M_COMPARISON.csv')
    methods.loc[methods.metric.isin(['B8L2','D10','geometry_bev_distance'])].to_csv(OUT/'SCREEN_Q_D10_SHAPE_COMPLETE_EXCERPT.csv',index=False)
    design=json.loads((WORK/'design/screen/DESIGN.json').read_text())
    design.update({'documentation_commit':DOC_COMMIT,'experiment_input_commit':DATA_COMMIT,'outcome_stage':'screen completed, confirmation not incorporated by this integration task','coverage_claim':'Finite candidate grid in fixed screen images; sampled XYZ and D, not exhaustive member universe','result_source':'analysis/screen/METHOD_N_M_COMPARISON.csv'})
    (OUT/'SCREEN_STAGE_COVERAGE.json').write_text(json.dumps(design,ensure_ascii=False,indent=2))

    roles={'C1':'困难转折较少、近共线冗余较多','C2':'常规／较简化表达','C3':'困难时保留较多非冗余转折'}
    role_rows=[]
    for row in dd.itertuples():
        role_rows.append([row.class_id,roles[row.class_id],row.people,row.members,f'{row.m_hard_turn_n:+.3f}',f'{row.m_hard_near_straight_nodes_5deg:+.3f}',f'{row.m_hard_matched_top_bias_deg:+.3f} / {row.m_hard_matched_bottom_bias_deg:+.3f}'])
    unknown_rows=[]
    for row in d.loc[~d.known].itertuples():
        detail='当前输入没有正式几何历史；不恢复既有筛除/组队资格' if row.m_all_images==0 else '仅2张图、1栋楼，均为简单；没有困难支持'
        unknown_rows.append([row.worker_id,row.missing_reason,f'{row.m_all_images}/{row.m_all_buildings}',f'{row.m_easy_images}/{row.m_easy_buildings}',f'{row.m_hard_images}/{row.m_hard_buildings}',detail])
    xt=pd.crosstab(cross.dstruct_k3_all_class,cross.old_structure_coarse_label).reindex(index=['C1','C2','C3','unknown'],columns=['M1','M2','M3','unknown'],fill_value=0)
    xt_rows=[[idx]+[int(v)for v in row]for idx,row in xt.iterrows()]
    reverse_rows=[[row.method,row.class_id,row.people,row.members]for row in rdefs.itertuples()]
    members_text=f'''# 新 DSTRUCT_K3 与真实融合反推类：准确名单及其解释

本文件用于更新现有人员主报告的分类说明，不另立人员主结论。旧标签来源为 main `{DOC_COMMIT}` 的完整 ALL 名单；本轮新标签和实算输入源提交为 `{DATA_COMMIT}`，底层均为真人 v2。所有下面的 C1/C2/C3 均明确属于 **ALL 描述标签**。

## 1. DSTRUCT_K3 是怎样的三类

形成域为 Manual 全历史结构水平、困难结构和困难−简单响应：非冗余转折、短边、近共线节点、参考对应缺失。Ward 同一树切 K2/K3/K4；DSTRUCT_K3 未把 Q/T、上下界定位或当前团队结果作为建类输入。上下界列是事后解释。

{md_table(['ALL类','描述角色','人数','实际成员','困难转折相对值','困难近共线相对值','困难顶/底界相对值（°）'],role_rows)}

转折、冗余、上下界数值都是相对同图×同条件人员中位数的残差，再在人员历史内按建筑等权，**不是原始角点数、不是绝对定位误差、不是正确率**。ERP纵坐标的正方向向下。近共线冗余和非冗余转折分开，因此 C3 的“较多转折”不是多堆近共线点；真实必要性继续由具体结构机会说明。

支持门槛为总体至少12图/3楼，简单至少5图/2楼，困难至少4图/2楼。冻结历史含普通非门洞正式原答，也含已明确列出的两张辅助特殊范围图；普通效果不混入特殊范围。完整新历史范围见 `../classifications/README.md`，不能称本轮覆盖全部非 OOS 行为库存。

### 未知不是低能力或零特征

{md_table(['人员','原始缺失原因','总体图/楼','简单图/楼','困难图/楼','解释'],unknown_rows)}

W019/W026 的“当前输入无正式历史”不等于他们从未作答。此前可用于行为观察的历史标签仍保存；未知不会补成常规类，也不因本轮制表恢复组队资格。

## 2. 与既有 Manual 结构三类有什么关系

这里旧结构是 V3_BEHAVIOR 的 ALL M1/M2/M3（6/34/19人），不是更早的旧 M 方法族。精确相交如下：

{md_table(['新 DSTRUCT_K3','旧 M1：明显简化','旧 M2：常规','旧 M3：较多转折','旧未知'],xt_rows)}

新 C3 的12人全部来自旧 M3 的19人；旧 M3 中另外7人分别进入新 C1（W001/W028/W032）和新 C2（W011/W012/W013/W036）。因此它是在加入明确的困难响应、冗余及对应特征后缩小了“困难时更多非冗余表达”的核心群体。新 C1 仍混合旧 M1/M2/M3 的2/3/3人，新 C2 混合4/31/4人，所以**整套新分区不是旧三类的纯细分，也不是仅改名字**。

在 DSTRUCT 自身的 Ward 层级内，K3 C1（8人）与C2（39人）合为 K2 C1（47人），K3 C3（12人）等于 K2 C2（12人）。这种严格父子关系只限同一树和同一折；不能扩展为所有旧方法的统一层级。22个楼外折与旧 V3_BEHAVIOR 粗层的平均 ARI 为0.466，最低0.266；这是分区对应程度，不是换类效果或验证成功率。

## 3. 四个真实融合反推候选：全部 ALL 人员

{md_table(['方法','ALL类','人数','实际成员'],reverse_rows)}

四方法均保留 W019/W022/W026 为未知，原因字段为 `insufficient_natural_fusion_response_history`。W022只有2图/1楼，困难0图；W019/W026没有本次正式随机团队训练支持。反推门槛为总体8图/3楼、简单5图/2楼、困难3图/2楼，与原答 DSTRUCT 的门槛不同。

**4人结构响应类**为 W109/W112/W126/W130；在 RFUSE_GEOM_K2 是C2，在K3是C3。**7人结构＋质量响应类**为 W002/W102/W109/W112/W115/W126/W130；在 RFUSE_GEOMQ_K2 是C2，在K3是C3。ALL中二者均为 DSTRUCT_K3 C3 的子集，但反推的是自然混合团队真实输出的人员响应，不是直接沿用 DSTRUCT 的标签；跨折关系需查该折名单。

反推训练复用24,237个去重自然随机端点，24,004个满足模型输出/同图同n变化支持；结构、边界/尺度、质量三域分别建模。系数来自同图×n中心化后的成员份额与真实融合输出关系，经过楼/图/n权重平衡、ridge及训练楼内lambda选择。几何家族不把Q域用于聚类，GEOMQ把Q作为单独域。这里的较高Q响应不是该人个人原答Q，也不是该人换入必然提高若干分；实际用途仍以严格ABC结果说明。

K3将其余大类进一步分开（31/24/4及20/32/7），可以为大块替换提供容量；4人或7人类则按目标图真实人数形成可行m。小类没有全块同类对照时，不能虚造可互换性分母。原始总体/简单/困难响应中心见 `REVERSE_CLASS_CENTERS_ALL.csv`，系数单位不得改写为个人原始角点数。

## 4. 论文里怎样使用 ALL 与楼外名单

1. 主报告描述“类里是谁”时用本文件的 ALL 名单，并写明形成范围。
2. 报告某图的换类事件时，按 `heldout_building + method + class_id` 查对应 LOBO 名单；Manual/Semi/scope 联合特征的目标建筑在两条件中同时排除。反推同样排除目标建筑全部自然训练团队。
3. 跨楼对齐使用困难转折、边界或历史Q/T等实际角色中心；不能将每折的 C3 自动视为同一个固定12人/4人/7人集合。
4. ALL成员重合说明两套方法如何相关，不等同两套方法实验独立，也不用于声称目标建筑外性能。

精确逐人表：`CLASS_MEMBERS_ALL.csv`（DSTRUCT_K3与4个反推方法，共310行）；新旧对应：`DSTRUCT_K3_OLD_ALL_MEMBERS.csv`、`DSTRUCT_K3_OLD_ALL_CROSSTAB.csv`；楼外对应汇总：`DSTRUCT_K3_OLD_LOBO_CORRESPONDENCE.csv`。完整20候选与4反推候选身份见 `FEATURE_AND_REVERSE_CANDIDATE_INVENTORY.csv`。
'''
    (OUT/'DSTRUCT_K3_AND_REVERSE_MEMBERS_ZH.md').write_text(members_text)

    main_path=OUT/'sources/docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md'
    extracts=[('旧分类与ALL/LOBO责任','### 1.3 当前四套方案的准确身份','### 1.4 分类固定到哪一层'),('旧有限构成已完成账','## 5. G1—G7完成账与实际覆盖边界','## 6. 难度、类别构成与随机人数曲线怎样连接'),('原收尾判断不删除','## 7. 本轮收尾判断与后续维护方式','## 8. 人员图表与研究台接入（2026-10-23）')]
    source=main_path.read_text();lines=['# 最新主报告原文摘录与整合位置','',f'固定源提交：`{DOC_COMMIT}`。完整原文字节保存在 `sources/`，SHA256：`{sha(main_path)}`。以下按原文边界截取，未改写旧数值。']
    for title,start,end in extracts:
        piece=source[source.index(start):source.index(end)].strip()
        lines += ['', '## '+title,'', f'源文件：`{main_path.relative_to(OUT)}`；起点 `{start}`，止于 `{end}` 前。','', '```markdown',piece,'```']
    lines += ['', '## 入口状态提示（解释，不改写原文）','', 'Pro下一轮任务文件顶部仍有“任务尚未发送或执行”的历史状态；主报告第6.3节已明确同房大块补充完成并接入。按当前主报告解释既有完成范围，本轮不重开同房任务。','', '最新用户主动提出寻找更强的同图大块分类区分，是新用途增量。主报告中此前“已完成核心研究”的旧成果和数字继续有效；新候选、新端点和本轮选择单独记账，不能把旧章节0次融合的身份套到本轮。']
    (OUT/'SOURCE_EXCERPTS.md').write_text('\n'.join(lines)+'\n')

    referenced=['classifications/CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz','classifications/CANDIDATE_CLASS_DEFINITIONS_COMPLETE_ALL.csv','classifications/NEW_OLD_LABEL_CROSSWALK_SUMMARY.csv','features/HISTORY_FEATURES_ALL_LOBO.csv.gz','reverse/REVERSE_LABELS_ALL.csv','reverse/REVERSE_CLASS_CENTERS_ALL.csv','design/screen/FROZEN_LABELS.csv.gz','design/screen/DESIGN.json','analysis/screen/METHOD_N_M_COMPARISON.csv','cases/CASE_SELECTION.csv','cases/CASE_MECHANISM_SUMMARY.csv']
    prov={'documentation_commit':DOC_COMMIT,'experiment_input_commit':DATA_COMMIT,'underlying_data':'v2','source_snapshot_manifest':'SOURCE_SNAPSHOT_MANIFEST.csv','new_computation':'table joins, memberships and exact text excerpts only; no fusion, scoring, classification fit','inputs':[{'path':x,'sha256':sha(WORK/x)}for x in referenced]}
    (OUT/'INTEGRATION_PROVENANCE.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2))
    print('Prepared 24-candidate inventory; 310 exact member rows; ALL/LOBO old-class linkage; screen excerpts; source snippets.')

if __name__=='__main__':main()
