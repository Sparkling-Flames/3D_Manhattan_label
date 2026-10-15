"""由当前快照表生成中文统计报告；不重算评分或覆盖历史快照。"""
import json

import pandas as pd

from .descriptive_pool_gate_20261015 import RULE


def number(value, digits=2):
    return '—' if pd.isna(value) else f'{value:.{digits}f}' if isinstance(value, float) else str(value)


def markdown(frame):
    columns = list(frame.columns)
    rows = ['|' + '|'.join(columns) + '|', '|' + '|'.join(['---'] * len(columns)) + '|']
    for record in frame.itertuples(index=False, name=None):
        rows.append('|' + '|'.join(number(value).replace('|', '／').replace('\n', ' ') for value in record) + '|')
    return '\n'.join(rows)


def items(value):
    return json.loads(value) if isinstance(value, str) else value


def write_report(tables, checks, out):
    t = {name: pd.DataFrame(frame) for name, frame in tables.items()}
    pools, images, audit = t['source_pools'], t['current_images'], t['record_audit']
    quality, overview = t['quality_records'], t['overview']
    occupied = pools[pools.n_annotation_records.gt(0)]
    waiting = t['pending_people']
    stage_rows = []
    for condition, group in occupied.groupby('condition', sort=False):
        stage_rows.append(dict(条件=condition, 有作答来源池=len(group),
            至少3名有效真人=int(group.pool_min3_pass.sum()),
            通过图片门=int(group.pool_analysis_eligible.sum()),
            普通难度来源池=int(group.ordinary_difficulty_eligible.sum())))
    classes = images.groupby('current_class').size().rename('图片数').reset_index().rename(columns={'current_class':'当前类别'})
    holds = occupied[occupied.image_exclusion_reasons.map(lambda value: bool(items(value)))]
    hold_rows = []
    for image, group in holds.groupby('image_code'):
        reasons = sorted({reason for value in group.image_exclusion_reasons for reason in items(value)})
        hold_rows.append(dict(图片=image, 条件='／'.join(group.condition),
            有效真人数='／'.join(map(str, group.n_effective_workers)), 图级暂停原因='；'.join(reasons)))
    qrows = []
    for condition, group in quality.groupby('condition'):
        qrows.append(dict(条件=condition, 当前完整质量记录=len(group), 图片=group.image_id.nunique(), 人员=group.worker_id.nunique()))
    changes = t['historical_panel_changes']
    prior = changes[changes.historical_target_836]
    removed = changes[changes.target_panel_change.eq('removed')]
    removed_reasons = []
    for _, row in removed.iterrows():
        reasons = list(items(row.pool_analysis_exclusion_reasons))
        reasons += [reason for reason in row.reference_audit_reasons.split('|') if reason]
        if not row.legacy_quality_restriction_clear:
            reasons.append('legacy_quality_restrictions')
        removed_reasons.append('；'.join(sorted(set(reasons))) or 'other_current_panel_limit')
    removal_summary = pd.Series(removed_reasons, dtype=str).value_counts().rename_axis('移出原因组合').rename('记录数').reset_index()
    qdetail = t['by_difficulty']
    qdetail = qdetail[qdetail.metric.isin(['WQ','A10','B8L2','IoU3D100'])]
    qdetail = qdetail[['panel','difficulty_class','metric','n_records','n_valid','n_missing','n_valid_images','mean','median','sd']].rename(columns={
        'panel':'条件层','difficulty_class':'难度','metric':'指标','n_records':'来源记录','n_valid':'有效n',
        'n_missing':'缺失n','n_valid_images':'有效图','mean':'均值','median':'中位数','sd':'标准差'})
    times = overview[overview.metric.isin(['active_time_seconds','target_matched_time_seconds'])]
    times = times[['panel','metric','n_records','n_valid','n_missing','n_valid_images','mean','median','sd']].rename(columns={
        'panel':'条件层','metric':'时间口径','n_records':'来源记录','n_valid':'有效n','n_missing':'缺失n',
        'n_valid_images':'有效图','mean':'均值秒','median':'中位秒','sd':'标准差秒'})
    scope = images[images.new_space_target]
    source_summary = scope.groupby('target_source').agg(图片数=('image_id','size'),
        来源坐标已核对=('target_source_verified','sum'), 顶界待完备=('top_boundary_pending','sum')).reset_index().rename(columns={'target_source':'来源'})
    revisions = images[images.target_role.eq('user_revised_gt')]
    revised_rows = audit[audit.target_role.eq('user_revised_gt') & audit.existing_full_quality_available]
    special = overview[overview.panel.str.startswith('special_') & overview.metric.eq('WQ')]
    special_rows = special[['panel','n_records','n_images','n_valid','n_missing']].rename(columns={
        'panel':'专项来源层','n_records':'来源记录','n_images':'图片','n_valid':'当前完整WQ','n_missing':'完整WQ缺失'})
    room = t['same_room_pairs']
    confirmed = room[(room.relation.eq('confirmed_comparable')) & room.n_records_a.gt(0) & room.n_records_b.gt(0)]
    pair_count = len(confirmed[['image_a','image_b']].drop_duplicates())
    room_rows = []
    for metric, group in confirmed.groupby('metric'):
        room_rows.append(dict(指标=metric, 合格来源图对=len(group),
            至少一对有效人员的图对=int(group.n_pairs.gt(0).sum()),
            共同人员仅1或2的图对=int(group.n_common_workers.isin([1,2]).sum()),
            有效人员配对总数=int(group.n_pairs.sum()),
            有效配对数范围=f'{group.n_pairs.min()}—{group.n_pairs.max()}'))
    disagreements = (images.review_disagreement.eq(True) & images.difficulty_analysis_eligible).sum()
    gt_errors = images[images.gt_error_excluded]
    sections = [
        '# 当前口径描述统计与复核结果（2026-10-15）',
        '本报告按用户新授权更新当前统计。旧[3152／1145／931／836报告与图表](../descriptive_statistics_20261015/README.md)保持历史快照，'
        '没有把旧难度标签直接换成新标签继续使用旧范围分数。本次不锁定论文大纲、不选择唯一质量公式、不按预期调参；所有比较首先展示真实覆盖、缺失和限制。',
        f"当前读取CURRENT指向的`{checks['difficulty_version']}`。库存仍为{checks['inventory_rows']}条、"
        f"{checks['inventory_images']}图，当前类别如下。其中{checks['difficulty_candidates']}图只是图片模块的普通难度**候选**，"
        '还必须通过来源人数、继承图片暂停、作答限制及指标参考检查；不能称为最终可分析图片数。',
        markdown(classes),
        '## 来源池人数与实际分析范围',
        f"人数规则版本为`{checks['source_pool_rule']}`：{RULE} 每个来源池是`image_id×condition`，"
        'manual、semi、oos分别计数；同图可以出现在不同条件，不把条件池数量相加当作独立图片。'
        '分数或时间缺失不把真实参与人数改成零，人数合格也不保证每项指标都有3名有效分数。',
        markdown(pd.DataFrame(stage_rows)),
        f"有作答但尚未过人数门的来源池为{len(waiting)}个：有效真人为1—2名的{int(waiting.n_effective_workers.isin([1,2]).sum())}个，"
        f"零名有效真人的{int(waiting.n_effective_workers.eq(0).sum())}个。零有效不代表未采集，而表示已有记录均未通过本次有效作答规则。"
        '空的图×条件组合不列为待补人任务。补人后动态重查，不永久删图；GT、修订GT、重复提交和融合结果不能凑人数。',
        '人数不足与GT／范围／旧暂停可以重叠。下面按原因组合列来源池，不把重叠原因逐项相加：',
        markdown(t['exclusion_intersections'].rename(columns={'condition':'条件','reason_combination':'原因组合',
            'n_source_pools':'来源池数','n_records':'记录数'})),
        f"当前有记录且带图级暂停／未决原因的图片共{len(hold_rows)}张，完整列在下表。当前新增的"
        f"{len(gt_errors)}张GT错误为{'、'.join(gt_errors.image)}；既有GT实质错误、旧quality/consensus暂停继续优先，"
        '不能因新难度候选表未写出就恢复。普通难度排除不等于专项不可研究，但明确GT或图级暂停仍约束专项。',
        markdown(pd.DataFrame(hold_rows)),
        '## 新空间、修订GT与旧分数兼容性',
        f"{len(scope)}张确认新空间逐图追溯来源、JSON指针和底面坐标，分布如下。确认的含义是整个空间体的竖向边界，"
        '同时限定墙、顶、底归属；精确顶角尚未完备是独立状态。即使新旧底面相同，也不能由此认证旧完整WQ或3D质量符合新空间。'
        '没有捏造顶界，也没有把虚拟裁切边界当成实体墙。',
        markdown(source_summary),
        f"两份用户修订GT对应{'、'.join(revisions.image)}，新坐标来源已核对，原GT保留。其旧完整评分共{len(revised_rows)}条，"
        '未迁移为新版目标成绩，保留待重评。当前原始loader数据与评分源ZIP的逐对象几何核对结果、目标来源及每条原因见参考审计明细。',
        f"旧{checks['historical_quality_rows']}条完整分数中，{checks['reusable_geometry_rows']}条仅满足输入／完整参考几何可复用条件，"
        f"{checks['pending_rescore_rows']}条仍需参考处理或重评。几何可复用不授予分析资格；再交人数、图片、角色与旧hold限制后，"
        f"实际当前完整质量为{checks['quality_rows']}条：",
        markdown(pd.DataFrame(qrows)),
        f"旧同目标{len(prior)}条中保留{int(changes.target_panel_change.eq('retained').sum())}条，移出{len(removed)}条，"
        f"新增{int(changes.target_panel_change.eq('added').sum())}条。移出原因组合如下；逐条身份与所有原因保存在"
        '[historical_panel_changes.csv](historical_panel_changes.csv)，不能用总量相近代替集合一致。',
        markdown(removal_summary),
        '## 当前质量与时间的描述分布',
        '下表分条件、难度并列原WQ、A10、B8L2和现用3D IoU百分分。人数、有效图数和缺失与均值、中位数、样本标准差同时报告；'
        '“—”表示无有效值，不能填成低分。B8L2是人工偏好版本，尚未宣布唯一最终公式。IoU3D100采用均高棱柱口径，不是任意实体精确IoU。',
        markdown(qdetail),
        '表中来源记录是该条件和当前难度来源池的分母，指标有效值可能远少于该分母。难度组任务组成不同，'
        '粗均值并不等于难度的独立效应，也不能因某组均值不符合预期而改类。'
        f"普通难度候选内保留的{int(disagreements)}处局部人工难度意见分歧没有批量改写为新等级；未审、空审核不当成认可。"
        '逐人、逐建筑、场景与同参考同伴比较见明细；原始人员平均成绩可展示，但不自动命名为能力排名。',
        '时间单位为秒，只复用已核对active_time及其有效状态、来源文件和规则，不用lead_time补缺。'
        '`active_time_seconds`为通过来源池门后的采集任务有效时间；`target_matched_time_seconds`进一步只保留当前完整质量资格与有效时间共同成立的记录。'
        '新空间及修订目标逐作答匹配未知时，旧采集耗时不能解释为完成新目标所需时间。来源图片条件时间仍可描述，但不声称任务已经按新范围重做。',
        markdown(times),
        '## 特殊场景与同房比较',
        '门洞、OOS、可标性和范围轴继续单列，不能预设一定低质或不可标。专项保留通过人数与图片门的来源池及有效采集时间；'
        '当前完整质量缺失时留空，不把历史分数搬入新空间来补表。各轴交集、分母和缺失见[场景表](by_scene.csv)。',
        markdown(special_rows),
        f"同房比较只用普通manual合格来源池，并坚持已记录关系，不把建筑当房间，也不传递新增同房事实。"
        f"明确可比且两端均有来源记录的图对为{pair_count}对。共同人员只有1—2名的比较仍保留；"
        '来源图片人数门与图对共同人数是两个分母，各指标可配对数如下。',
        markdown(pd.DataFrame(room_rows)),
        '同房明细分别展示两端全体平均、共同人员平均及同人视角差值；小样本不作稳定规律或因果解释。'
        '未记录同房不等于确认异房。本轮没有新融合实验，也没有从合格来源池的已有轨迹中删除k=1/2节点。',
        '## 查阅、复现与后续接入',
        '- [筛选工作簿](现有研究数据描述统计_当前口径.xlsx)、[关键可视化](figures/FIGURES.md)、[独立复核记录](INDEPENDENT_AUDIT.md)。\n'
        '- [当前逐条审计](record_audit.csv)、[当前目标与完整来源指针](current_images.csv)、[来源池与继承暂停](source_pools.csv)。\n'
        '- [当前完整质量](quality_records.csv)、[待重评](pending_rescore.csv)、[待补人](pending_people.csv)、[各指标覆盖](metric_coverage.csv)。\n'
        '- [逐人](by_worker.csv)、[逐建筑](by_building.csv)、[同参考同伴比较](peer_comparisons.csv)、[同房逐指标](same_room_pairs.csv)。\n'
        '- [字段合同](FIELD_CONTRACT.json)、[检查摘要](CHECKS.json)、[全部表](tables.json)。',
        '生成入口为`tools/thesis_main/analysis/descriptive_statistics_current_20261015.py`，'
        '报告模块为`descriptive_statistics_current_report_20261015.py`。在仓库根目录运行：\n\n'
        '```powershell\npython -m tools.thesis_main.analysis.descriptive_statistics_current_20261015\n```',
        '未来新批次、人员及质量版本继续沿[版本化接入说明](../descriptive_statistics_20261015/EXTENSION_GUIDE.md)与manifest机制。'
        '新增数据先走正式loader和必要审核，新质量算法保留独立版本、来源及参考；人数门、旧暂停、目标／时间相容性须动态复核。'
        '登记版本不认证几何语义，也不自动兼容所有未来数据。',
        '原库存仅底面指标仍保留在旧快照ledger_*字段及部分指标覆盖表中，未完成当前目标／逐份参考重绑定者不升级为新目标完整质量。',
        '具体变更范围、18项测试、复现与截图清理见[交付记录](HANDOFF.md)。',
        '未重新评分、调参、采集、融合或推送；参考待完备、缺失和稀疏交叉限制结论外推。',
    ]
    (out / 'README.md').write_text('\n\n'.join(sections) + '\n', encoding='utf-8')
