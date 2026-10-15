"""从已经计算的描述统计表生成中文报告，不重新评分或读取原始标注。"""
from pathlib import Path

import pandas as pd


def markdown(frame):
    """统一显示空值与小数；保留表中的真实分母。"""
    def cell(value):
        if pd.isna(value):
            return '—'
        if isinstance(value, float):
            return str(int(value)) if value.is_integer() else f'{value:.3f}'
        return str(value).replace('|', '\\|').replace('\n', '<br>')
    rows = [[cell(v) for v in row] for row in frame.itertuples(index=False, name=None)]
    return '\n'.join(['| ' + ' | '.join(map(str, frame.columns)) + ' |',
                      '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |'] +
                     ['| ' + ' | '.join(row) + ' |' for row in rows])


def stats_table(frame, labels):
    data = frame.copy()
    data['IQR'] = data.q75 - data.q25
    fields = labels + ['n_records', 'n_valid', 'n_missing', 'n_valid_images',
                       'mean', 'median', 'sd', 'q25', 'q75', 'IQR']
    return markdown(data[fields].rename(columns=dict(panel='集合', metric='指标',
        difficulty_class='难度', comparison='配对差值', axis='分轴', axis_value='状态',
        n_records='集合记录数', n_valid='有效n', n_missing='缺失n', n_valid_images='有效图数',
        mean='均值', median='中位数', sd='样本SD', q25='P25', q75='P75')))


def write_report(tables, out):
    """消费主生成器的同一份tables，写README.md；数值不另设手工副本。"""
    out = Path(out)
    records, images, overview = (tables[k] for k in ['records', 'images', 'overview'])
    sizes = overview[overview.metric.eq('WQ')].set_index('panel')
    inventory = sizes.loc['inventory_3152']
    scored = sizes.loc['scored_1145']
    worker = sizes.loc['worker_931']
    target = sizes.loc['target_836']
    n = lambda row, field='n_records': int(row[field])
    primary = ['WQ', 'A10', 'B8L2', 'IoU3D100', 'active_time_seconds']
    text = [
        '# 现有研究数据详细描述统计（2026-10-15）',
        '后续核验与扩展：[独立审计](INDEPENDENT_AUDIT.md)、[关键数据可视化](figures/FIGURES.md)、'
        '[新增人员／批次及算法版本接入](EXTENSION_GUIDE.md)。本页下方保留原统计快照与分母。',
        '本次接到新的本地整理与统计授权后，已实际执行描述统计并生成明细、汇总及可复用入口。'
        '上一轮“只整理文档、统计暂不执行”是该轮的历史事实，本报告不追改它。'
        '本次不固定论文大纲，不调参、不重新评分、不新增融合实验，不覆盖源标注或人工审核，不推送远端。',
        '## 数据集合及分母',
        f'当前人员库存为 **{n(inventory)} 条**，涉及 **{n(inventory, "n_images")} 张图**、'
        f'**{n(inventory, "n_workers")} 人**、**{records.building_id.nunique()} 栋建筑**。'
        f'库存按人员×图片有 {int(records.duplicated(["worker_id", "image_id"]).sum())} 条超额记录，'
        f'按人员×图片×条件有 {int(records.duplicated(["worker_id", "image_id", "condition"]).sum())} 条超额记录。'
        '这只是重复组合计数，不表示可直接删除；既有版本与资格仍由源记录裁决。',
        markdown(pd.DataFrame([
            dict(集合=key, 记录数=n(row), 人数=n(row, 'n_workers'), 图数=n(row, 'n_images'),
                 WQ有效数=n(row, 'n_valid'), 用途=description)
            for key, row, description in [
                ('inventory_3152', inventory, '全部人员对象库存，保留失败、排除及未评分'),
                ('scored_1145', scored, '已冻结参考下的数值评分；含特殊与范围待定诊断'),
                ('worker_931', worker, '已有人员主画像集合；部分参考与难度目标尚不兼容'),
                ('target_836', target, '普通图且参考与难度目标兼容的条件比较子集')]])),
        f'四个集合各有用途，不能相加，也不能选一个数替代其余分母。'
        f'库存中独立投票资格为真 {int(records.independent_vote_eligible.sum())} 条，'
        '不等于这些记录都可评价、可进入人员画像或已人工认可。'
        '清洗状态、独立票、质量门和共识门在明细中分别保留；评分存在也不授予新资格。',
        markdown(records[records.WQ.notna()].groupby('use_panel').agg(
            评分记录数=('object_id','size'), 图片数=('image_id','nunique'), 人数=('worker_id','nunique')).reset_index()),
        '931主画像包含836条同目标、54条仅底面等价和41条目标底面不同记录。后95条仍是原绑定参考下的人员描述，'
        '不能套用新难度目标解释完整质量。其余214条评分按场景、次层及范围保留；可计算分数不等于目标或资格已解决。',
        markdown(records.groupby(['condition', 'cleaning_disposition'], dropna=False).size()
                 .rename('记录数').reset_index().rename(columns={'condition':'条件', 'cleaning_disposition':'清洗状态'})),
        '以下均值默认作答行等权，`image_equal_mean`另给先逐图平均再图片等权的结果。'
        '库存平均时间会保留库存中不同条件和资格的覆盖；正式比较须筛选相同条件与适用集合。'
        '缺失不是低分，不可计算、参考不适用和未冻结时间均不补零。',
        '库存原评分状态如下；它与独立票或主质量资格不同。',
        markdown(records.groupby('ledger_score_status', dropna=False).size().rename('记录数').reset_index()),
        '原账本已有的部分指标也单独保留在`ledger_*`列和[部分指标覆盖表](ledger_metric_coverage.csv)：'
        '尤其仅底面可算记录的底面IoU、底角误差和原floor_WQ，不因缺少完整WQ而丢弃。'
        '这些值沿用`ledger_reference_id`与原状态，未与1145条完整评分或新难度目标自动合并；floor_WQ不是完整WQ。',
        '## 质量与时间总体分布',
        stats_table(overview[overview.metric.isin(primary)], ['panel', 'metric']),
        'WQ、A10、B8L2沿用已有冻结评分，并列保留版本；用户偏好B8L2不等于已宣布它为唯一最终公式。'
        'IoU3D100为现用均高棱柱3D IoU乘100，不是任意实体的精确IoU。'
        '底面IoU、底角误差、方向与高度分项见各汇总表；其量纲和优劣方向不能直接相加比较。'
        'WQ未覆盖的库存记录应结合`ledger_score_status`、资格及范围状态解释，不解释为已观察到的低质量。',
        markdown(records.groupby('ledger_score_status', dropna=False).agg(
            库存记录数=('object_id', 'size'), 已有WQ数=('WQ', 'count')).reset_index()
            .rename(columns={'ledger_score_status':'评分台账状态'})),
        '## 图片难度：库存覆盖与同目标比较',
        markdown(images.groupby(['difficulty_version', 'difficulty_class'], dropna=False).size()
                 .rename('库存图数').reset_index().rename(columns={'difficulty_version':'版本', 'difficulty_class':'粗类'})),
        '粗类是当前采用目标范围下的分类；“单列”和“待复核”保留独立身份。'
        '不能用旧结构粗类替代当前版本，也不能把同目标子集的图数当成全库图数。',
        stats_table(tables['by_difficulty'][tables['by_difficulty'].panel.eq('target_836') &
                    tables['by_difficulty'].metric.isin(primary)], ['difficulty_class', 'metric']),
        '上表每档的集合记录数、有效数和有效图数同时展示。三档的人员组成、建筑及每图作答数不同；'
        '均值差异只是当前覆盖下的描述，不证明难度的独立作用，也不由结果反向修改难度标签。'
        '时间缺失可能改变比较对象，不能把质量与时间的不同有效分母默认为同一批作答。',
        '## 门洞、OOS、可标性与范围',
        '这些是不同分轴。OOS未知不能认证正常；门洞可标性未决不等于不可标；'
        '非正交但清晰可标也不能与曲面、多层等表示限制合并。范围待定、仅底面参考和顶部待核独立保留。',
    ]
    difficulty = tables['by_difficulty']
    def grade_mean(grade, metric):
        return difficulty.loc[difficulty.panel.eq('target_836') & difficulty.difficulty_class.eq(grade) &
                              difficulty.metric.eq(metric), 'mean'].iloc[0]
    text.insert(text.index('## 门洞、OOS、可标性与范围'),
        f'实际结果并非随三档单调下降：简单、中等、困难的原WQ均值分别为'
        f'{grade_mean("简单", "WQ"):.2f}、{grade_mean("中等", "WQ"):.2f}、{grade_mean("困难", "WQ"):.2f}；'
        f'B8L2分别为{grade_mean("简单", "B8L2"):.2f}、{grade_mean("中等", "B8L2"):.2f}、'
        f'{grade_mean("困难", "B8L2"):.2f}。中等与困难仅覆盖10图和14图，且任务组成不同，不能据此认定中等固有地更难。')
    axis_counts = []
    for axis in ['oos_axis', 'doorway_axis', 'markability_from_explicit_label',
                 'target_floor_relation', 'top_boundary_pending']:
        if axis in images:
            part = images.groupby(axis, dropna=False).size().rename('图数').reset_index()
            part.columns = ['状态', '图数']
            part.insert(0, '分轴', axis)
            axis_counts.append(part)
    text.append(markdown(pd.concat(axis_counts, ignore_index=True)))
    text.append('OOS×门洞的逐图交集如下；unknown/pending原样保留，未记录不推成否。')
    text.append(markdown(images.groupby(['oos_axis', 'doorway_axis'], dropna=False).size()
                         .rename('图数').reset_index()))
    scene = tables['by_scene']
    text.extend([
        stats_table(scene[scene.panel.eq('inventory_3152') & scene.metric.eq('WQ') &
                          scene.axis.isin(['oos_axis', 'doorway_axis', 'special_layer'])],
                    ['axis', 'axis_value', 'metric']),
        '特殊层中有数值分数不自动表示主质量适用；同参考分数、范围未决诊断和正式可评价覆盖必须区分。'
        '完整分轴、难度交集和人员条件差异分别见`by_scene`、`scene_intersections`、'
        '`by_scene_intersections`和`worker_scene`表；稀疏组合保留样本量，不强行形成方向性结论。',
        '## 有效标注时间与来源核对',
        markdown(records.groupby(['condition', 'time_status'], dropna=False).size()
                 .rename('记录数').reset_index().rename(columns={'condition':'条件', 'time_status':'时间状态'})),
        '时间单位为秒。按项目、运行任务、人员连接冻结时间上下文，再经历史canonical身份核对图片、建筑和条件。'
        '`active_time_seconds`仅保留合格时间；`raw_active_time_seconds`保留原值以便审计，不能用于填补有效时间。'
        '`timing_status`、`time_source`、`time_source_file`、`time_rule_version`保留原规则与来源。'
        'lead_time是另一种日志量，未用它替代active_time。已知人工加秒记录排除于有效秒数。',
        '新增项目93/94/95的日志存在，但现有分析明确标为时间未冻结，因此本次继续留空，'
        '不能写成“这些人没有时间日志”。历史时间未重估，也没有重新冻结新增批次。',
        '本次复用既有`worker_behavior_time_20260910.audit_sources`做来源一致性核对：'
        'P1的1128条、C2-B的160条、C2-A-RP两批各40条以及C1的780条，数值和状态均无不一致。'
        'C1的26份冻结与现存日志逐事件一致，字节差异来自表示形式，未据此修改任何时间。'
        '只读扫描active_logs的261份JSONL共78286事件，无JSON解析错误；项目93/94/95共5712事件。'
        '这些是本次核对的审计证据，不是新增有效时间样本。',
        '## 逐图、逐人、建筑与共同参考对照',
        '`by_image`给出逐图质量及时间；`by_worker`给出逐人原始平均；`by_building`给出建筑覆盖。'
        '`worker_difficulty`、`worker_scene`、`worker_room_type`、`worker_building`用于核查个人任务组成，'
        '每项都保留n、中位数、SD、分位数和缺失。原始人员平均不命名为能力排名。'
        '房间类型是已有空间粗类，不是已确认的物理房间ID；建筑也不等于房间。',
        '共同参考对照在同图片×条件×reference_id单元中，比较个人值与其余人员均值。'
        '`peer_records`保存逐项差值，`worker_peer_comparison`汇总该人员有共同对照的单元。'
        '只有一个人的单元保留对照缺失；这比跨不同任务直接比较原始均值更可解释，'
        '仍受共同图覆盖、对照人员组成及稀疏性影响，不自动消除人员选择或建筑差异。',
    ])
    peer = tables['worker_peer_comparison']
    text.append(stats_table(peer[peer.panel.eq('target_836') & peer.original_metric.eq('WQ')]
                            .sort_values('worker_id'), ['worker_id']))
    text.extend([
        '上表为同目标集合的WQ共同参考差值：正数表示比该单元其他人员的均值高，负数表示低。'
        '按稳定人员ID排列，不按分数排序。不能把有限单元的差值称为人员能力或因果效果。',
        '## 同集合的评分版本与时间关联',
        stats_table(tables['score_comparison'], ['panel', 'comparison']),
        '所有配对差值使用同输入、同绑定参考与同资格集合；分数整体升高是公式输出变化，'
        '不是“更正确”的验证，也不据此逐例择高分或调参。',
        markdown(tables['time_quality'][tables['time_quality'].difficulty_class.eq('all')][
            ['panel', 'metric', 'n_valid', 'n_missing', 'n_images', 'spearman']].rename(columns={
                'panel':'集合', 'metric':'质量指标', 'n_valid':'共同有效n', 'n_missing':'缺失n',
                'n_images':'集合图数', 'spearman':'Spearman相关'})),
        '相关只在质量和有效时间均非缺失的记录计算；分难度×条件的结果见`time_quality`。'
        '该表的n_images是原集合图数，共同有效覆盖须结合有效n与明细检查。'
        '重复人员、图片和建筑形成相关结构，因此这里只作描述，不给独立样本显著性推断，'
        '不能从相关推出花时更多使质量提高或降低。',
        '## 已确认同房图片',
        '同房关系、视点差异、每图平均与共同人员的逐对比较见[同房说明](SAME_ROOM_NOTES.md)。'
        '主表以同目标集合为准，旧人员主画像另存后缀`_931`；'
        '后缀`_manual_inventory`使用库存中独立Manual作答观察有效时间，不扩大质量资格。'
        '不靠关系传递新增同房事实，未记录同房不等于确认异房。',
        '## 明细与汇总导航',
        'CSV使用UTF-8 BOM，可按表头在Excel等工具筛选；列表及字典单元格采用JSON。'
        '[tables.json](tables.json)与CSV为同一份计算结果，'
        '[FIELD_CONTRACT.json](FIELD_CONTRACT.json)列出字段、单位、集合、评分版本及缺失约定。',
    ])
    navigation = []
    for name, table in tables.items():
        navigation.append(dict(表=f'[{name}.csv]({name}.csv)', 行数=len(table), 字段数=len(table.columns)))
    text.append(markdown(pd.DataFrame(navigation)))
    text.extend([
        '## 来源、复用及验证',
        '输入沿[当前统一包manifest](../../analysis_results/research_input_20260929/manifest.json)读取，'
        '参考[研究数据说明](../../docs/thesis_main/研究数据说明_来源预处理与用途_20261006.md)；'
        '本次不重建统一包。最新图轴取[图片覆盖表](../difficulty_special_coverage_20261015/image_coverage_259.csv)，'
        '质量与范围绑定取[评分接入表](../difficulty_target_integration_20261015/quality_bindings_1145.csv)，'
        'A10/B8L2取[冻结A/B分数](../quality_ab_feedback_handoff_20261015/prior_AB/results/SCORES_1145.csv)，'
        '人员集合取[四轴人员面板](../worker_four_axis_update_20261015/quality_panel_931.csv)。'
        '全库存评分台账及冻结几何快照取[质量收尾审查包](../quality_joint_closeout_review_20261015/pro_closeout_delta.zip)，'
        '主生成器验证其几何快照与当前loader一致。'
        '时间取[冻结上下文](../../analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/active_time_context.csv.gz)，'
        '身份另核对[annotation_spine](../../analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/annotation_spine.csv.gz)。'
        '这些派生入口只消费其声明用途，不升格为原始标注真源。',
        '可复用生成入口：',
        '```powershell\npython -m tools.thesis_main.analysis.descriptive_statistics_20261015\n```',
        '主生成器读取现有版本化输入，检查稳定身份、评分集合与参考一致性后生成统计；'
        '报告函数直接消费同一份tables，不另行评分。'
        '[工作簿](现有研究数据描述统计.xlsx)是同一快照的筛选查阅版，全部指标与审计字段保留在CSV。'
        '工作簿生成器为[descriptive_statistics_workbook_20261015.mjs](../../tools/thesis_main/analysis/descriptive_statistics_workbook_20261015.mjs)，'
        '从可解析artifact-tool的工作目录使用捆绑Node运行；验证记录见[WORKBOOK_VERIFICATION.json](WORKBOOK_VERIFICATION.json)。',
        '关键边界检查包括：库存对象ID唯一，评分记录与库存身份一致，A/B的对象、人员、图片、条件、参考及WQ一致，'
        '人员与同目标集合包含关系，图片轴一图一行且版本一致；缺失时间不得回填lead_time，'
        '人工加秒记录不得进入有效时间，同房证据不传递扩充。实际测试命令和结果以本次交付记录为准。',
        '实际改动范围、13项测试与定向检查见[交付及验证记录](HANDOFF.md)。',
        '## 剩余边界与最少未决问题',
        '范围或顶部仍待定的图继续保留其原状态，本次不要求用户重复已有审核。'
        '若后续需要把这些记录升级为主质量结论，只需针对尚未确认的目标／参考适用性补证据；'
        '若后续需要新增人员的时间比较，需要单独完成新增批次的时间冻结。'
        '评分最终公式尚未确定，当前并列版本足以继续描述比较，无需为本次报表先选唯一公式。'
        '小样本、未记录图轴和不均衡人员／建筑组成会限制外推；本报告不宣称总体规律或因果效应。',
        '本次未重评分、未运行新融合、未重估旧active_time、未推送远端。'
        '仍需注意：数值可计算与参考适用、独立作答及人工认可各有边界，不能互相替代。',
    ])
    out.mkdir(parents=True, exist_ok=True)
    (out / 'README.md').write_text('\n\n'.join(text) + '\n', encoding='utf-8')
