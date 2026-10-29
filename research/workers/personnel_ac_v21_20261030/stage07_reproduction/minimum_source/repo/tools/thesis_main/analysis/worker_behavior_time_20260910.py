"""历史人员速度与参考偏差：分开解释、留楼验证，不修改正式人员规则。"""
from pathlib import Path
import json
import tempfile

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from tools.thesis_main.analysis import worker_reference_feasibility_20260909 as ref
from tools.thesis_main.analysis.fit_worker_evidence_strata_20260908 import fit_one, informative, predict_peers
from tools.thesis_main.analysis.validate_worker_reuse_20260909 import adjusted_rand
from tools.thesis_main.analysis.quality_core.active_time import load_active_logs, lookup_active_log_entry
from tools.thesis_main.analysis.full_uncertainty.materialize_uncertainty_substrate import C1_ROOT

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
OUT = ROOT / 'analysis_results/worker_behavior_time_20260910_v1'
SEED = 20260910


def clean_time(d, deviations=False):
    statuses = ['eligible', 'project+task+annotator', 'owner_valid']
    if deviations:
        statuses += ['eligible_partial_session_coverage', 'eligible_with_protocol_deviation']
    return (d.active_time_formal_available & d.timing_status.isin(statuses)
            & d.active_time_source.ne('lead_time_fallback')
            & np.isfinite(d.active_time_seconds) & d.active_time_seconds.gt(0))


def interpret(speed, error):
    a = {'low': '较快', 'high': '较慢'}.get(speed, '速度未分明')
    b = {'low': '参考偏差较低', 'high': '参考偏差较高'}.get(error, '参考偏差未分明')
    return a + '／' + b


def adjusted_time_keys():
    keys=set()
    for relative in ['prescreen/prescreen_active_time_adjustment_audit.json',
            'c1/w018_c1_manual_active_time_adjustment_audit.json',
            'c1/w018_c1_2026-07-28_manual_active_time_adjustment_audit.json']:
        audit=json.loads((ROOT/'active_logs'/relative).read_text(encoding='utf-8'))
        for r in audit['changed_events']:
            keys.add((str(r['project_id']),str(r['task_id']),str(r.get('annotator_id',audit.get('worker_id')))))
    return keys


def speed_quality_prediction(speed, quality):
    """Training-profile association, no target responses or target times used."""
    z = speed[['worker_id', 'effect']].merge(quality[['worker_id', 'effect']], on='worker_id', suffixes=('_t', '_q'))
    x = z.effect_t.to_numpy(); y = z.effect_q.to_numpy()
    x = x-x.mean(); y = y-y.mean()
    slope = float(x@y/(x@x)) if x@x > 1e-12 else 0.
    p = speed.copy(); p['effect'] *= slope
    return p, slope


def audit_sources(t):
    """Recompute log totals with their stage-specific historical rule."""
    from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import materialize_active_time_ledgers
    from tools.thesis_main.data_prep.build_post_block2_analysis_pack_v2 import active_time_block2
    audit = []
    for stage, block, folder in [('P1', 0, 'prescreen'), ('C2-B', 0, 'c2b'), ('C2-A-RP', 1, 'c2a_rp_block1_20260810')]:
        logs = load_active_logs(str(ROOT/'active_logs'/folder))
        g = t[(t.stage == stage) & (t.block_index == block) & t.active_time_formal_available]
        for r in g.to_dict('records'):
            entry, status = lookup_active_log_entry(logs, r['project_id'], r['runtime_task_id'], r['worker_id'])
            assert entry is not None and status == r['timing_status']
            assert np.isclose(entry['active_time_value'], r['active_time_seconds'], atol=1e-8, rtol=0), r
        audit.append(dict(stage=stage, block=block, rows=len(g), numeric_mismatches=0, rule='original_general_log_loader', raw_root='active_logs/'+folder))
    g = t[(t.stage == 'C2-A-RP') & (t.block_index == 2)].copy()
    raw = g.to_dict('records')
    checks = active_time_block2(raw, ROOT/'active_logs/c2a_rp_block2_20260814')
    assert all(c['match'] for c in checks)
    assert np.allclose([r['active_time_seconds'] for r in raw], g.active_time_seconds, atol=1e-8, rtol=0)
    assert [r['active_time_status'] for r in raw] == g.timing_status.tolist()
    audit.append(dict(stage='C2-A-RP', block=2, rows=len(g), numeric_mismatches=0,
        rule='original_block2_session_max_loader', raw_root='active_logs/c2a_rp_block2_20260814'))
    frozen = ROOT/'analysis_results/c1_a_formal_closeout_20260801_r2/frozen_active_logs'
    # The closed C1 snapshot is used verbatim; original live copies are checked as well.
    files = list(frozen.glob('*.jsonl'))
    live = {p.name: p for p in (ROOT/'active_logs/c1').rglob('*.jsonl')}
    comparisons = {p.name: p.name in live and p.read_bytes() == live[p.name].read_bytes() for p in files}
    for p in files:
        assert p.name in live
        read_events = lambda x: [json.loads(line) for line in x.read_text(encoding='utf-8').splitlines() if line.strip()]
        assert read_events(p) == read_events(live[p.name]), 'C1 frozen/live event mismatch: '+p.name
    with tempfile.TemporaryDirectory() as tmp:
        summary = materialize_active_time_ledgers(C1_ROOT/'c1_canonical_meta_observations.csv', frozen, Path(tmp),
            annotation_version_csv=C1_ROOT/'c1_annotation_version_disposition.csv', collection_window_closed=True, formal=True)
        assert summary['parse_error_count'] == 0
        fresh = pd.read_csv(Path(tmp)/'c1_task_worker_active_time.csv', dtype={'worker_id': str, 'project_id': str, 'runtime_task_id': str})
    g = t[t.stage == 'C1'].merge(fresh, on=['project_id','runtime_task_id','worker_id'], validate='one_to_one', suffixes=('', '_fresh'))
    assert len(g) == (t.stage == 'C1').sum()
    assert np.allclose(g.active_time_seconds, g.task_worker_active_seconds, equal_nan=True, atol=1e-8, rtol=0)
    assert g.timing_status.equals(g.timing_status_fresh)
    audit.append(dict(stage='C1', rows=len(g), numeric_mismatches=0, rule='original_owner_valid_task_worker_materializer',
        raw_root=str(frozen.relative_to(ROOT)), frozen_file_count=len(files), live_byte_equal=sum(comparisons.values()),
        live_event_equal=len(files), byte_difference_only_files=[k for k,v in comparisons.items() if not v]))
    (OUT/'SOURCE_AUDIT.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')


def half_stability(d, metric, replicates=100):
    buildings = sorted(d.building_id.unique()); rng = np.random.default_rng(SEED)
    rows = []
    for r in range(replicates):
        order = rng.permutation(buildings); a = set(order[:len(order)//2])
        left = ref.profiles(d[d.building_id.isin(a)].assign(value=d[metric]))
        right = ref.profiles(d[~d.building_id.isin(a)].assign(value=d[metric]))
        z = left[left.fit_status == 'usable'].merge(right[right.fit_status == 'usable'], on='worker_id', suffixes=('_a','_b'))
        assert not a.intersection(set(order[len(order)//2:]))
        if len(z) >= 3:
            # Half-specific medians: diagnostic forced two-way split, not final labels.
            rows.append(dict(replicate=r, workers=len(z), spearman=float(spearmanr(z.effect_a,z.effect_b).statistic),
                median2_ari=adjusted_rand((z.effect_a > z.effect_a.median()).astype(int), (z.effect_b > z.effect_b.median()).astype(int)),
                train_buildings=json.dumps(sorted(a)), test_buildings=json.dumps(sorted(set(buildings)-a))))
    return pd.DataFrame(rows)


def final_profiles():
    """Quality uses all reference-evaluable rows, including workers with no timing."""
    d=pd.read_csv(OUT/'joined_evidence.csv.gz',dtype={'worker_id':str})
    saved=pd.read_csv(OUT/'profiles.csv',dtype={'worker_id':str})
    rows=[]
    for cohort in ['all26','current20']:
        c=d if cohort=='all26' else d[d.current20_member]
        q=informative(c[~c.imputed_point & c.reference_allowed].assign(value=c.ospa30))
        quality,_=fit_one(q,SEED)
        speed=saved[(saved.cohort==cohort)&(saved.variant=='no_known_time_adjustment')&
                    (saved.panel=='all_timed')&(saved.metric=='log_time')]
        members=c[['worker_id','current20_member']].drop_duplicates().merge(
            speed[['worker_id','effect','lower','upper','label','informative_rows','informative_buildings']],on='worker_id',how='left').merge(
            quality[['worker_id','effect','lower','upper','label','informative_rows','informative_buildings']],on='worker_id',how='left',suffixes=('_time','_error'))
        members['label_time']=members.label_time.fillna('unavailable')
        members['behavior_label']=[interpret(s,e) if s!='unavailable' else '无合格时间／'+interpret(s,e).split('／')[1]
                                  for s,e in zip(members.label_time,members.label_error)]
        rows.append(members.assign(cohort=cohort))
    pd.concat(rows,ignore_index=True).to_csv(OUT/'worker_axes.csv',index=False)


def transfer_check():
    d=pd.read_csv(OUT/'joined_evidence.csv.gz',dtype={'worker_id':str})
    d=d[~d.imputed_point & d.clean_timing & ~d.known_manual_time_shift].copy()
    results=[]
    for cohort in ['all26','current20']:
        c=d if cohort=='all26' else d[d.current20_member]
        for source,target in [('P1','C1'),('C1','C2-B'),('C1','C2-A-RP')]:
            train=c[c.stage==source].assign(value=c.log_time)
            test=c[c.stage==target].assign(value=c.log_time)
            pred,audit=ref.cross_validate(test,train)
            sm,_=ref.summarize(pred,dict(cohort=cohort,source=source,target=target,target_available=len(test)))
            results.append(sm)
    pd.DataFrame(results).to_csv(OUT/'stage_transfer.csv',index=False)


def write_report():
    import matplotlib.pyplot as plt
    d=pd.read_csv(OUT/'joined_evidence.csv.gz')
    p=pd.read_csv(OUT/'worker_axes.csv')
    v=pd.read_csv(OUT/'validation.csv')
    h=pd.read_csv(OUT/'half_stability.csv')
    tr=pd.read_csv(OUT/'stage_transfer.csv')
    plt.rcParams['font.sans-serif']=['Microsoft YaHei']
    plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for ax,cohort,title in zip(axes,['all26','current20'],['全部26人：24人有时间画像','后续20人']):
        z=p[(p.cohort==cohort)&p.effect_time.notna()]
        for r in z.itertuples():
            color={'low':'#167c80','high':'#ce693a'}.get(r.label_error,'#77818b')
            ax.plot([r.lower_time,r.upper_time],[r.effect_error]*2,color=color,alpha=.45)
            ax.plot([r.effect_time]*2,[r.lower_error,r.upper_error],color=color,alpha=.45)
            ax.scatter(r.effect_time,r.effect_error,c=color,s=26)
            ax.annotate('W'+str(r.worker_id),(r.effect_time,r.effect_error),xytext=(3,4),textcoords='offset points',fontsize=8)
        ax.axhline(0,color='#999999',linestyle='--',linewidth=.7)
        ax.axvline(0,color='#999999',linestyle='--',linewidth=.7)
        ax.set(title=title,xlabel='校正任务后的 log(1+active seconds)：左快、右慢',ylabel='校正任务后的参考偏差（OSPA30）：下低、上高')
    fig.suptitle('速度与参考偏差分开描述；误差线为楼级 bootstrap 95% 区间',fontsize=13)
    fig.savefig(OUT/'worker_axes.png',dpi=180);plt.close(fig)
    lines=['# 工人粗分类：速度与参考执行偏差的独立验证（2026-09-10）','',
        '**结论：现有数据支持把“相对标注速度”作为可解释的行为轴；速度不能替代参考偏差，尚未证明速度子类能收敛。跨阶段结果不一致，不能把快慢当作永久人员属性。**','',
        '## 1. 分类目的与本轮定位','',
        '交流原文要求以人为单位独立采集，再按人员类型和人数比例离线组合；“认真／不认真”是例子，没有规定必须采用这两个心理标签。可复用的是已有独立标注，不要求每种组合重新采集。理想结果还包括具体子类的分歧分布达到稳定阶段。','',
        '本轮只验证可解释的候选行为轴，不根据目标图的收敛结果反过来选人。速度、参考执行偏差、类内收敛是三个不同问题。上一轮参考偏差粗类的收敛结果不能自动移植到速度分组。','',
        '## 2. 数据与日志审计','',
        '- 延用上一轮已从原始标注和人工复核重建的1887条无辅助标注，包含26人、196图。排除2条补点记录后保留1885条；未补时间、未用lead_time。全部26人均留在人员表，W14、W26没有合格时间画像。',
        '- 按各阶段原规则重算：P1的1128条、C2-B的160条、C2-A-RP两批各40条可用时间，以及C1全部780条时间上下文，数值／状态均与底座一致。C1冻结日志与active_logs/c1的26份文件逐事件一致；字节差异不代表事件差异。上述审计数量包括本轮未使用的Semi等记录。',
        '- P1、C2-B和第一批C2-A-RP沿用历史project–task–worker日志规则；C1使用其owner-valid会话规则；第二批C2-A-RP使用该阶段专门的累计会话规则。规则可重放不等于各阶段测量制度完全等价。',
        '- 审计发现W1、W18部分日志有统一增加20／25／30秒的记录。已标记任务身份，并在主解释中排除受影响行；不直接减去估计值来伪造原始观测。状态干净的1582条中排除82条，剩1500条。后续20人从1373条排除30条，剩1343条。原时间规则版本、缺失／覆盖不足／协议偏离均保留。',
        '- “无已知人工加秒”是在来源审计后增加的解释限制，不是事前预注册假说。历史调整版本和包含覆盖不足／协议偏离的版本作为敏感性并列保留。','',
        '## 3. 怎样计算','',
        '速度使用 log(1+active seconds)，拟合人员效应＋原始图片/阶段/条件上下文截距；先消除任务差异再比较人员。0是本队列人员等权平均的相对基准，不是固定秒数门槛。参考偏差另用OSPA30，低表示较接近当前可评分参考，不能直接解释为完全遵守规则或真实质量。','',
        '每次留出整栋building，训练只使用其他楼，再预测这些已知人员在留出图片中相对同图人员平均值的偏离。目标图的参考结果和时间不参与训练。报告的是相对偏离的MSE改善，**不是分类准确率，也不是新图片绝对需要多少秒的预测**。单人上下文无法提供同图人员对比，不进入该验证；因此1500／1343条中实际验证1461／1304条。','',
        '速度—偏差关联仅在同一批同时有两种观测的响应上计算。用速度预测偏差时，速度画像和速度—偏差映射系数均只在训练楼拟合；不使用测试图自身耗时。最终人员表的参考轴则独立使用全部可评分参考标注，**缺时间不导致质量证据被排除**。','',
        '互斥分半：以building为单位随机分两半，重复100次，每半独立拟合人员效应。bootstrap：按building有放回重采样500次，报告95%百分位区间，图不当作完全独立人员样本。人员不足3栋或有效拟合不足80%不分类；区间跨0保留未分明。未作多重检验校正，标签只供探索。','',
        '## 4. 核心结果','',
        '| 队列 | 速度预测MSE改善 | 同响应面板的参考偏差预测改善 | 仅凭速度画像预测参考偏差 | 速度分半秩相关中位数 |',
        '|---|---:|---:|---:|---:|']
    for cohort,name in [('all26','全部26人（时间可用24人）'),('current20','后续20人')]:
        a=v[(v.cohort==cohort)&(v.variant=='no_known_time_adjustment')]
        val=lambda panel,metric: a[(a.panel==panel)&(a.metric==metric)].building_mse_gain.iloc[0]
        rho=h[(h.cohort==cohort)&(h.panel=='all_timed')].spearman.median()
        lines.append(f'| {name} | {val("all_timed","log_time"):+.2%} | {val("paired","ospa30"):+.2%} | {val("paired","ospa30_from_speed"):+.2%} | {rho:.3f} |')
    lines += ['', '正数表示优于不使用人员差异的基线，负数表示更差。各building等权。结果表明速度差异可复现，但速度对参考偏差的预测增益接近0；不能由“标得快”推断“粗心”。全部人群与20人群的参考偏差可预测性明显不同，不能只用26人结果代表后续20人。','',
        '同响应面板内人员速度效应与参考偏差效应的Spearman为全部人群0.124、20人群0.325；正方向是较慢伴随较高偏差，不是较快伴随较高偏差。这是描述性相关，不能解释成慢导致错误，也没有稳定的样本外预测收益。','',
        '点数净增减倾向的留楼预测改善分别为−2.44%和−1.30%。所以目前也不足以用“稳定少标／稳定多标”作为普遍粗类。点数净差并不等于人工确认的漏标或多标，不能这样命名。','',
        '### 跨阶段转移检验','',
        '| 队列 | 训练→测试 | 可验证人员 | 验证响应 | 速度预测MSE改善（楼等权） |','|---|---|---:|---:|---:|']
    for r in tr.itertuples():
        lines.append(f'| {r.cohort} | {r.source}→{r.target} | {r.workers} | {r.rows} | {r.building_mse_gain:+.2%} |')
    lines += ['', 'P1→C1支持早期速度对后续相近流程的预测；C1→C2-B和C1→C2-A-RP不支持直接转移。目标阶段人数覆盖、每图重叠、任务与时间规则都不同，现有数据不能确定是哪项导致失败。C1→C2-B按记录加权为小幅正收益、按楼等权却为负，更不能只挑有利权重汇报。因此混合历史数据的分半稳定性不等于未来阶段稳定性。','',
        '## 5. 目前可以怎样分','',
        '建议保存两个独立轴：**相对较快／相对较慢／速度未分明**，以及**参考偏差较低／较高／未分明**。前两类是行为描述，中间状态是证据状态，不是第三种人格。不要先聚类再凭直觉命名，不强制分成固定人数。快慢可以服务时间成本研究，执行偏差服务参考符合程度研究；交叉标签可以解释个体，现有证据不支持宣称已经发现四个天然人群。','',
        '下表使用全部合格时间建立速度轴，参考轴使用全部可评分标注（包括缺时间者）；与只用于关联分析的同响应面板不同。两轴都相对于各自队列平均，不能跨队列把相同标签当成相同绝对阈值。','',
        '| 队列 | 速度状态 | 人员 |','|---|---|---|']
    for cohort in ['all26','current20']:
        for label,name in [('low','较快'),('high','较慢'),('uncertain','未分明'),('unavailable','无合格时间')]:
            ids=p[(p.cohort==cohort)&(p.label_time==label)].worker_id.sort_values()
            lines.append(f'| {cohort} | {name} | '+('、'.join('W'+str(w) for w in ids) or '无')+' |')
    lines += ['', '![速度与参考偏差](worker_axes.png)','',
        '横向速度和纵向参考偏差分别使用各自可用证据；参考效应以OSPA30的角距离度数表示，不是错误率。误差线是条件于当前已知人员的楼级区间，未证明可推广到新人。W14、W26没有速度坐标，仍保留在下表。','',
        '### 逐人可解释画像','', '| 队列 | 人员 | 当前描述 | 速度响应数 | 参考响应数 |', '|---|---|---|---:|---:|']
    for r in p.sort_values(['cohort','worker_id']).itertuples():
        lines.append(f'| {r.cohort} | W{r.worker_id} | {r.behavior_label} | {int(r.informative_rows_time) if pd.notna(r.informative_rows_time) else 0} | {int(r.informative_rows_error)} |')
    lines += ['',
        '这些是候选描述，不是正式人员资格或最终分类。例如20人中W2／W17较快且参考偏差较低，W15／W33较慢且参考偏差较低；W30较快且偏差较高，W29／W35／W37较慢且偏差较高。四种组合均能出现，所以快慢与执行偏差应独立。个别人员区间清楚不等于整个偏差分类已通过跨图复现。','',
        '若要使用“粗心”一词，还需要规则明确的独立复核证据，例如可见边界漏标、明确配对错误，以及其重复发生情况。当前点集参考偏差不能区分规则理解差异、空间范围选择、操作错误和注意不足；不从耗时推断动机。','',
        '## 6. 与后续新增标注及子类收敛的关系','',
        '可以把速度作为候选分组因素，但暂不据此宣称某类会收敛。后续在同一版本与流程下，让人员独立完成共同校准图，冻结速度及参考执行画像，再对独立目标图抽取A、B、AAB等真实人员组合。人数保持可比，重复无放回抽取，允许稳定多簇，保留单例新增标法与有限观察窗口。必须比较类内稳定阶段与同人数随机混合人群；类别定义和停止人数不能使用同一批目标标注。','',
        '当前20人的较快8人、较慢10人；按既有至少保留5名未来标注的规则，单类完整验证的候选起点最多只能到k=3或k=5。这不能检验“该类在k≈8稳定”。未分明者不能为了凑人数强塞进某类；需补充能被同一独立校准规则归类的人员，或明确只验证更小k的阶段。','',
        '## 7. 交付、字段与复现','',
        '- `joined_evidence.csv.gz`：1887条逐响应连接，保留原时间状态、规则、来源、人工加秒标记、原始条件、人工补点标记与参考可评分状态。`clean_timing`只表示历史来源状态通过；本轮主解释另要求`known_manual_time_shift=false`。',
        '- `coverage.csv`：两队列逐人覆盖；其`clean_time_rows`仍是排除已知加秒前的历史状态覆盖。实际主解释人数／响应见`worker_axes.csv`和`validation.csv`。',
        '- `profiles.csv`：每队列、敏感性版本、面板和指标的人员效应／95%区间／支持数／拟合状态。`all_timed`只验证速度，`paired`同时要求时间和参考；后者不用于排除人员质量证据。',
        '- `validation.csv`：留楼预测的行数、人员、上下文、楼数及记录等权／楼等权MSE改善；`heldout_predictions.csv.gz`保留逐响应目标、预测、基线和误差；`ospa30_from_speed`只用训练的时间画像预测偏差。',
        '- `half_stability.csv`：100次互斥楼分半的成员秩相关、强制中位数二分ARI、两半楼清单。ARI仅诊断中位数分组，不代表区间分类本身已验证。',
        '- `associations.csv`与`interpretable_members.csv`：同响应面板的关联及两轴描述；`worker_axes.csv`是最终完整人员表，参考轴不受时间缺失限制。`effect/lower/upper`后缀time/error区分两轴；`label`的low/high/uncertain/unavailable为相对低、高、未分明、不可用。',
        '- `stage_transfer.csv`：早期阶段训练、后期阶段验证，仍排除目标整楼；该分析与混合阶段留楼结果分开。`SOURCE_AUDIT.json`记录原日志重放；`PLAN.json`记录分析定义及来源审计后的限制。',
        '', '运行：`.venv/Scripts/python.exe -m tools.thesis_main.analysis.worker_behavior_time_20260910`。所有输出仅用于本次历史探索，不修改原始导出、日志、正式三轴、人员资格、派发或路由。代码复用现有任务效应消除、楼级bootstrap及留楼预测函数。地图与索引只增加探索入口。测试及交付状态另见`VERIFICATION.json`。']
    (OUT/'README_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def run():
    OUT.mkdir(exist_ok=True, parents=True)
    plan = dict(cohorts=['all26','current20'], reference='latest_reviewed_calculation_view; no_imputation; reviewed_reference_sensitivity',
        context='original_image_stage_condition_context; timing_version retained; no comparisons of unmatched tasks',
        metrics=['log_time','ospa30','matched_angle','signed_count_rate'], bootstrap_unit='building', bootstrap_replicates=500,
        split_half_replicates=100, seed=SEED, classification='axis-specific building-bootstrap 95% interval versus equal-worker mean; not natural clusters',
        validation='leave_one_building_out; known workers, target-image relative deviations; speed-to-error slope fit on training-worker profiles only',
        primary='no_known_time_adjustment', sensitivities=['pooled_clean','C1_clean','P1_legacy','pooled_with_deviations','reviewed_reference_only'],
        source_amendment='known manual time shifts discovered during source audit; exclude affected task-worker rows without subtracting estimated seconds',
        claims_excluded=['carelessness','causality','novel_worker_generalization','subgroup_convergence','formal_worker_eligibility'])
    (OUT/'PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    m = pd.read_csv(ROOT/'analysis_results/worker_coarse_validation_20260910_v1/measurements.csv.gz',dtype={'worker_id':str})
    t = pd.read_csv(BASE/'facts/active_time_context.csv.gz',dtype={'worker_id':str,'project_id':str,'runtime_task_id':str})
    audit_sources(t)
    assert m.canonical_annotation_id.is_unique and t.canonical_annotation_id.is_unique
    d = m.merge(t,on='canonical_annotation_id',how='left',validate='one_to_one',suffixes=('','_time'),indicator=True)
    assert d._merge.eq('both').all()
    for col in ['worker_id','stage','raw_condition']:
        assert d[col].equals(d[col+'_time']), col
    d['context_key'] = d.original_context_key
    d['log_time'] = np.log1p(d.active_time_seconds)
    d['signed_count_rate'] = d.extra_count_rate-d.missing_count_rate
    d['clean_timing'] = clean_time(d)
    shifted=adjusted_time_keys()
    d['known_manual_time_shift']=[(p,t,w) in shifted for p,t,w in zip(d.project_id,d.runtime_task_id,d.worker_id)]
    d.to_csv(OUT/'joined_evidence.csv.gz',index=False)
    coverage=[]; all_profiles=[]; scores=[]; halves=[]; preds=[]; associations=[]; members=[]
    for cohort in ['all26','current20']:
        c = d if cohort == 'all26' else d[d.current20_member]
        for worker,g in c.groupby('worker_id'):
            coverage.append(dict(cohort=cohort,worker_id=worker,manual_rows=len(g),imputed_rows=int(g.imputed_point.sum()),
                clean_time_rows=int((g.clean_timing & ~g.imputed_point).sum()),
                excluded_or_missing_time_rows=int((~g.clean_timing & ~g.imputed_point).sum()),
                time_status_counts=json.dumps(g.timing_status.value_counts().to_dict()),
                paired_rows=int((g.clean_timing & ~g.imputed_point & g.reference_allowed).sum())))
        clean=c[~c.imputed_point & c.clean_timing]
        variants={'pooled_clean':clean,'C1_clean':clean[clean.stage=='C1'],'P1_legacy':clean[clean.stage=='P1'],
            'pooled_with_deviations':c[~c.imputed_point & clean_time(c,True)],
            'reviewed_reference_only':clean[(clean.reference_basis=='reviewed_reference') & ~clean.known_manual_time_shift],
            'no_known_time_adjustment':clean[~clean.known_manual_time_shift]}
        for variant,v in variants.items():
            paired=v[v.reference_allowed & np.isfinite(v.ospa30)].copy()
            configs=[('all_timed','log_time',v),('paired','log_time',paired),('paired','ospa30',paired)]
            if variant=='no_known_time_adjustment':
                configs += [('paired','matched_angle',paired),('paired','signed_count_rate',paired)]
            fits={}
            for panel,metric,z in configs:
                z=informative(z.assign(value=z[metric])); meta=dict(cohort=cohort,variant=variant,panel=panel,metric=metric)
                p,diag=fit_one(z,SEED)
                all_profiles.append(p.assign(**meta));fits[panel,metric]=p
                held,folds=ref.cross_validate(z)
                sm,_=ref.summarize(held,meta);scores.append(sm)
                preds.append(held.assign(**meta,model='continuous_worker'))
                if variant=='no_known_time_adjustment' and metric in ['log_time','ospa30']:
                    halves.append(half_stability(z,metric).assign(**meta))
            # Same-response-panel worker association, conditional on task intercepts.
            a=fits['paired','log_time'];b=fits['paired','ospa30']
            z=a.merge(b,on='worker_id',suffixes=('_time','_error'))
            associations.append(dict(cohort=cohort,variant=variant,workers=len(z),paired_rows=len(paired),
                spearman=float(spearmanr(z.effect_time,z.effect_error).statistic)))
            mapped=[]
            for building,test in paired.groupby('building_id'):
                train=paired[paired.building_id!=building]
                tp=ref.profiles(train.assign(value=train.log_time));qp=ref.profiles(train.assign(value=train.ospa30))
                p,slope=speed_quality_prediction(tp[tp.fit_status=='usable'],qp[qp.fit_status=='usable'])
                result=predict_peers(test.assign(value=test.ospa30),p)
                result['training_slope']=slope
                mapped.append(result)
            held=pd.concat(mapped,ignore_index=True)
            meta=dict(cohort=cohort,variant=variant,panel='paired',metric='ospa30_from_speed')
            sm,_=ref.summarize(held,meta);scores.append(sm);preds.append(held.assign(**meta,model='speed_profile_to_error'))
            if variant=='no_known_time_adjustment':
                z['behavior_label']=[interpret(s,e) for s,e in zip(z.label_time,z.label_error)]
                z['adjusted_time_plus1_ratio']=np.exp(z.effect_time)
                z=z.merge(paired.groupby('worker_id').active_time_seconds.median().rename('raw_paired_median_seconds'),on='worker_id')
                members.append(z.assign(cohort=cohort))
            print(json.dumps(dict(cohort=cohort,variant=variant,rows=len(v),paired=len(paired)),ensure_ascii=True),flush=True)
    pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False)
    pd.concat(all_profiles,ignore_index=True).to_csv(OUT/'profiles.csv',index=False)
    pd.DataFrame(scores).to_csv(OUT/'validation.csv',index=False)
    pd.concat(halves,ignore_index=True).to_csv(OUT/'half_stability.csv',index=False)
    pd.concat(preds,ignore_index=True).to_csv(OUT/'heldout_predictions.csv.gz',index=False)
    pd.DataFrame(associations).to_csv(OUT/'associations.csv',index=False)
    pd.concat(members,ignore_index=True).to_csv(OUT/'interpretable_members.csv',index=False)


if __name__=='__main__':
    run()
    final_profiles()
    transfer_check()
    write_report()
