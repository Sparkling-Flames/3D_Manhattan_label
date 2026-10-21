"""Exact K / team-n / member-sample scope ledger, without outcome selection.

Counts the concrete-member universe by inclusion-exclusion across eligible
method domains within each pool. These are endpoint sets, not method references.
The existing global class-vector ledger remains a sum of method-specific cells.
"""
from __future__ import annotations
import collections, itertools, json, math, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
OUT = HERE / 'coverage'
sys.path.insert(0, str(STUDY / 'composition'))
import global_study as gs
from prepare_n20_design import atomic_frame, METHODS, N, DRAWS


def choose(n, k):
    return math.comb(n, k) if n >= k else 0


def md_table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(map(str, headers)) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(str, r)) + ' |' for r in rows])


def main():
    completion = gs.read(OUT / 'N20_COMPLETION.json')
    if completion['status'] != 'complete':
        raise ValueError('Computed scope may only be published after completion')
    pools, maps = gs.pool_lookup(), gs.method_maps()
    labels = gs.pd.read_csv(STUDY / 'composition/FROZEN_LABELS.csv')
    fold = labels.groupby(['method_id', 'tier', 'condition', 'heldout_building'], as_index=False).agg(
        fitted_class_count=('class_id', 'nunique'), labelled_workers=('worker_id', 'nunique'))
    ksummary = fold.groupby(['method_id', 'tier', 'condition'], as_index=False).agg(
        fitted_K_min=('fitted_class_count', 'min'), fitted_K_max=('fitted_class_count', 'max'),
        heldout_buildings=('heldout_building', 'nunique'),
        labelled_workers_min=('labelled_workers', 'min'), labelled_workers_max=('labelled_workers', 'max'))
    ksummary['selected_for_current_n20_stage'] = ksummary.apply(
        lambda r: (r.method_id, r.tier, r.condition) in METHODS, axis=1)
    atomic_frame(OUT / 'FROZEN_METHOD_K_SUMMARY.csv', ksummary, ('method_id', 'tier', 'condition'))
    pm = gs.pd.read_csv(HERE / 'candidate_n20/POOL_METHOD_COVERAGE.csv')
    cells = gs.pd.read_csv(HERE / 'candidate_n20/CONFIG_CELLS.csv.gz', dtype={'possible_member_sets': str})
    req = {r['team_key']: r for r in gs.read(STUDY / 'composition/ENDPOINT_REQUESTS.json.gz')['requests']}
    req.update({r['team_key']: r for r in gs.read(HERE / 'candidate_n20/ENDPOINT_REQUESTS.json.gz')['requests']})
    by_pool = collections.defaultdict(list)
    for r in req.values():
        if len(r['member_workers']) == N:
            by_pool[r['pool_id']].append((r['team_key'], frozenset(r['member_workers'])))
    domains = collections.defaultdict(list)
    poolrows = []
    for r in pm.itertuples(index=False):
        formal = {q['worker_id'] for q in pools[r.pool_id]['records']}
        mapping = maps[(r.method_id, r.tier, r.condition, r.building)]
        domain = formal & mapping.keys()
        domains[r.pool_id].append(frozenset(domain))
        owncells = cells[(cells.pool_id == r.pool_id) & (cells.method_id == r.method_id) & (cells.tier == r.tier)]
        member_universe = choose(len(domain), N)
        if sum(map(int, owncells.possible_member_sets)) != member_universe:
            raise ValueError(('member_partition_does_not_equal_binomial', r.pool_id, r.method_id))
        computed = sum(ws <= domain for _, ws in by_pool[r.pool_id])
        poolrows.append(dict(pool_id=r.pool_id, image=r.image, image_id=r.image_id, building=r.building,
            condition=r.condition, method_id=r.method_id, tier=r.tier,
            fitted_K=len(set(mapping.values())), available_K=len({mapping[w] for w in domain}),
            n=N, max_sampled_members_per_cell=DRAWS, formal_pool_n=len(formal), labelled_pool_n=len(domain),
            class_capacities=r.class_capacities, all_class_vectors=len(owncells),
            all_actual_member_sets=str(member_universe), computed_actual_member_sets=computed,
            remaining_actual_member_sets=str(member_universe-computed),
            selected_member_references=int(owncells.sampled_member_sets.sum()),
            member_exhaustive_selected_cells=int(owncells.exhaustive_members.sum()),
            singleton_cells=int(owncells.singleton.sum()),
            sampled_member_count_min=int(owncells.sampled_member_sets.min()),
            sampled_member_count_max=int(owncells.sampled_member_sets.max())))
    atomic_frame(OUT / 'N20_POOL_K_AND_MEMBER_UNIVERSE.csv', gs.pd.DataFrame(poolrows),
                 ('pool_id', 'method_id', 'tier'))
    unionrows = []
    for pid, domain_list in sorted(domains.items()):
        # Remove duplicate worker domains before exact inclusion-exclusion.
        unique_domains = sorted(set(domain_list), key=lambda x: tuple(sorted(x)))
        possible = 0
        for k in range(1, len(unique_domains)+1):
            for subset in itertools.combinations(unique_domains, k):
                intersection = set.intersection(*(set(x) for x in subset))
                possible += (-1)**(k+1) * choose(len(intersection), N)
        computed = sum(any(ws <= d for d in unique_domains) for _, ws in by_pool[pid])
        if not 0 <= computed <= possible:
            raise ValueError(('invalid_member_union', pid, computed, possible))
        meta = pools[pid]['meta']
        unionrows.append(dict(pool_id=pid, condition=meta['condition'], building=meta['building'], n=N,
            eligible_method_domains=len(domain_list), distinct_worker_domains=len(unique_domains),
            all_distinct_actual_member_sets=str(possible), computed_distinct_actual_member_sets=computed,
            remaining_distinct_actual_member_sets=str(possible-computed),
            all_full_length_addition_orders=str(possible * math.factorial(N)),
            order_processes_enumerated=False))
    atomic_frame(OUT / 'N20_DISTINCT_MEMBER_UNION_BY_POOL.csv', gs.pd.DataFrame(unionrows), ('pool_id',))
    possible_total = sum(int(r['all_distinct_actual_member_sets']) for r in unionrows)
    computed_total = sum(r['computed_distinct_actual_member_sets'] for r in unionrows)
    condition_universe = []
    for condition in sorted({r['condition'] for r in unionrows}):
        selected_rows = [r for r in unionrows if r['condition'] == condition]
        capacities = [r['formal_pool_n'] for r in poolrows if r['condition'] == condition]
        possibilities = sum(int(r['all_distinct_actual_member_sets']) for r in selected_rows)
        computed = sum(r['computed_distinct_actual_member_sets'] for r in selected_rows)
        condition_universe.append(dict(condition=condition, pools=len(selected_rows),
            formal_pool_n_min=min(capacities), formal_pool_n_max=max(capacities),
            all_distinct_actual_member_sets=str(possibilities),
            computed_distinct_actual_member_sets=computed,
            remaining_distinct_actual_member_sets=str(possibilities-computed)))
    atomic_frame(OUT / 'N20_DISTINCT_MEMBER_UNION_BY_CONDITION.csv', gs.pd.DataFrame(condition_universe), ('condition',))
    summary = dict(status='complete',
        class_number_rule='Actual building-excluded method labels; no fixed K cap',
        n=N, n_is_stage_scope_not_global_limit=True,
        member_sampling_budget_per_cell=DRAWS, sampling_budget_is_not_class_number=True,
        legacy_ABC='Names of comparison teams; composition_A/B/C store their full K-dimensional class counts',
        selected_method_condition_pairs=len(METHODS), selected_pool_method_rows=len(poolrows), pools=len(unionrows),
        selected_method_vector_cells=len(cells), selected_member_references=int(cells.sampled_member_sets.sum()),
        selected_member_exhaustive_cells=int(cells.exhaustive_members.sum()),
        selected_singleton_cells=int(cells.singleton.sum()),
        selected_non_singleton_member_exhaustive_cells=int((cells.exhaustive_members & ~cells.singleton).sum()),
        method_member_universe_reference_sum=str(sum(int(r['all_actual_member_sets']) for r in poolrows)),
        all_distinct_actual_member_sets=str(possible_total),
        computed_distinct_actual_member_sets=computed_total,
        remaining_distinct_actual_member_sets=str(possible_total-computed_total),
        condition_member_universes=condition_universe,
        all_full_length_addition_orders=str(possible_total * math.factorial(N)),
        order_processes_enumerated=False,
        exact_member_union_method='Inclusion-exclusion of eligible labelled worker domains separately within each task pool',
        counts_use_previous_plus_continuation_endpoints=True,
        singleton_variation='Unestimable; zero numeric variance is not classification evidence')
    execution_rows = []
    for batch in gs.read(HERE / 'DESIGN_FREEZE.json')['batches']:
        base = HERE / 'batches' / batch['batch_id']
        ex, co = gs.read(base / 'EXECUTION.json'), gs.read(base / 'COMPLETION.json')
        execution_rows.append(dict(batch_id=batch['batch_id'], condition=batch['condition'],
            requested=batch['requested'], new_native=ex['new_native'], resumed=ex['resumed'],
            configured_worker_processes=ex['jobs'], main_wall_seconds=ex['seconds'],
            worker_pool_elapsed_seconds_sum=sum(p['seconds'] for p in ex['pools']),
            process_cpu_seconds=None, measured_cpu_core_count=None,
            cpu_measurement_status='Not recorded; worker elapsed seconds are not CPU time',
            processes=ex['jobs'], elapsed_seconds=ex['seconds'],
            native_endpoints_per_second=ex['new_native']/ex['seconds'],
            complete_conditional=co['score_status_counts'].get('complete_conditional',0),
            below_four=co['score_status_counts'].get('below_four',0),
            no_connection=co['score_status_counts'].get('no_connection',0),
            missing=co['missing']))
    atomic_frame(OUT / 'BATCH_EXECUTION_SUMMARY.csv', gs.pd.DataFrame(execution_rows), ('batch_id',))
    summary['native_execution_seconds_sum'] = sum(r['elapsed_seconds'] for r in execution_rows)
    summary['native_execution_new_endpoints'] = sum(r['new_native'] for r in execution_rows)
    summary['native_execution_endpoints_per_second'] = summary['native_execution_new_endpoints']/summary['native_execution_seconds_sum']
    summary['worker_pool_elapsed_seconds_sum'] = sum(r['worker_pool_elapsed_seconds_sum'] for r in execution_rows)
    summary['worker_time_definition'] = 'Sum of per-pool worker elapsed times, overlapping in parallel; not CPU time and not batch wall time'
    summary['process_cpu_seconds_recorded'] = False
    summary['actual_cpu_core_count_recorded'] = False
    summary['throughput_scope'] = 'Observed six-process batch wall time; excludes checkpoint packaging, manual pauses and analysis; not a forecast for other team sizes'
    estimate_rows = []
    for condition, remaining in [(r['condition'], int(r['remaining_distinct_actual_member_sets'])) for r in condition_universe] + [('all_selected_n20',possible_total-computed_total)]:
        seconds = remaining/summary['native_execution_endpoints_per_second']
        estimate_rows.append(dict(scope=condition, remaining_distinct_member_sets=str(remaining),
            observed_endpoints_per_batch_wall_second=summary['native_execution_endpoints_per_second'],
            configured_worker_processes=6, mechanically_estimated_seconds=seconds,
            mechanically_estimated_days=seconds/86400,
            mechanically_estimated_years=seconds/(365.25*86400),
            assumption='Constant observed six-process rate; no acceleration, no further deduplication, no storage expansion cost; scale illustration only'))
    summary['remaining_scale_estimate'] = estimate_rows
    atomic_frame(OUT / 'N20_REMAINING_SCALE_ESTIMATE.csv', gs.pd.DataFrame(estimate_rows), ('scope',))
    gs.save(OUT / 'N20_SCOPE_COUNTS.json', summary)
    method_completion = gs.pd.read_csv(OUT / 'N20_METHOD_COMPLETION.csv')
    K = {(r.method_id, r.tier, r.condition): (r.fitted_K_min, r.fitted_K_max)
         for r in ksummary.itertuples(index=False)}
    available = collections.defaultdict(list)
    for r in poolrows:
        available[(r['method_id'], r['tier'], r['condition'])].append(r['available_K'])
    method_rows = []
    for r in method_completion.itertuples(index=False):
        key = (r.method_id, r.tier, r.condition)
        lo, hi = K[key]
        aks = available[key]
        method_rows.append([r.condition, r.method_id, str(lo) if lo == hi else f'{lo}–{hi}',
            str(min(aks)) if min(aks) == max(aks) else f'{min(aks)}–{max(aks)}',
            r.pools, r.images, r.buildings, r.all_class_vectors, r.prior_touched_vectors, r.new_vectors])
    statuses = sorted(set(completion['score_status_counts']) |
                      set(completion['continuation_new_score_status_counts']) |
                      set(completion['combined_score_status_counts']))
    status_rows = [[s, completion['continuation_new_score_status_counts'].get(s, 0),
                   completion['score_status_counts'].get(s, 0),
                   completion['combined_score_status_counts'].get(s, 0)] for s in statuses]
    report = f'''# 续研第二阶段：n=20 的配置与计算覆盖回执

本批已经完成六个方法×条件在全部适用普通任务池中的 **48,321 个类别人数向量**，新增 **126,268 个不同实际成员集合**的原生融合与评分。上一阶段已有 291,904 个集合，与本批合并去重后为 **{completion['combined_distinct_endpoint_sets']:,} 个**；相对已恢复历史索引，其中 {completion['combined_new_sets_against_recovered_history']:,} 个为新集合，{completion['combined_historical_geometry_restorations']:,} 个为旧几何恢复。构成覆盖完成后，质量、几何与成本结论由对应的类别效用分析报告解释；本回执本身不把覆盖增加当作分类有效性证据。

## 1. 类别数、人数与成员抽样分别记录

类别数 K 沿用各方法在目标建筑之外形成的实际标签，没有“三类”上限。n=20 是本批团队人数；每个类别人数配置最多抽取 r=3 个不同具体成员集合，是本批成员覆盖预算。旧事件表 A/B/C 是共同背景下三个对照团队的名字，每个团队可以含全部 K 类；其类别人数向量单列在 composition_A/B/C。

下表的“拟合 K”来自冻结标签的完整适用人群，“池内 K”是目标图片正式人员中实际出现的类别数；成员不足的类别不会被虚构补齐。

{md_table(['条件', '方法', '拟合 K', '池内 K', '池', '图片', '建筑', '全部配置', '此前触及', '本批新增触及'], method_rows)}

六方法合计为 190 个任务池、168 张不同图片、22 个建筑。每方法的图片/池范围不相同；某方法标注人员不足 20 人时，不进入该方法的 n=20 研究域。门洞和特殊范围继续沿用原有分层，本批没有扩大资格。

## 2. 三种组合空间的精确覆盖

1. **类别人数配置**：六方法全部 {len(cells):,} 格已计算。本批新增触及 42,168 格。全方法、全部原登记人数的配置宇宙为 {completion['global_method_vector_universe']:,} 格；把新增实际集合按每个合法方法重新映射后，已计算从 {completion['old_global_computed_vectors']:,} 增至 {completion['new_global_computed_vectors']:,} 格，实际增量 {completion['newly_touched_vectors_all_eligible_methods']:,}，剩余 {completion['remaining_global_uncomputed_vectors']:,} 格。这里包括父类和其他合法方法的附带覆盖，不能用 54,853+42,168 代替。
2. **具体成员集合**：本批选定 144,666 条方法/配置/成员引用，去重为 144,642 个集合，其中 18,374 个复用旧结果、126,268 个新增。六方法所有合法 n=20 成员集合在各池去重后的精确宇宙为 **{possible_total:,} 个**；加上旧阶段所有符合本域的 n=20 终点，已计算 **{computed_total:,} 个**，剩余 **{possible_total-computed_total:,} 个**。每格最多 3 组不能表述为穷尽成员；只有 168 格成员穷尽，其中 148 格是单集合，剩余 20 格是可变成员但已穷尽的小格。
3. **加入顺序及前缀过程**：该 n=20 成员宇宙对应的长度 20 有序成员序列共有 **{possible_total * math.factorial(N):,} 条**，本批没有展开这些过程。相同具体成员集合的确定性终点只计算一次。全员唯一集合或单格唯一成员没有类内替换波动估计资格。

具体成员的去重宇宙按各池合法人员域的包含排除公式计算，不把多个方法共享的团队重复相加。方法×配置格保留各方法身份，因此它们的计数与不同实际团队数是两种分母。

{md_table(['条件', '任务池', '正式池人数范围', '不同实际 n=20 集合宇宙', '已计算', '剩余'], [[r['condition'], r['pools'], f"{r['formal_pool_n_min']}–{r['formal_pool_n_max']}", f"{int(r['all_distinct_actual_member_sets']):,}", f"{r['computed_distinct_actual_member_sets']:,}", f"{int(r['remaining_distinct_actual_member_sets']):,}"] for r in condition_universe])}

Semi 部分正式任务池有 46 人，单个全标签人员域的 20 人集合数即为 C(46,20)=5,608,233,007,146。这解释了具体成员空间远大于类别配置空间的数量级；该范围沿用原人员资格，没有为增加覆盖恢复历史被筛除人员。

## 3. 失败与实测计算量

{md_table(['原生状态', '本批新增终点', '本批选定终点含复用', '旧阶段与本批去重合并'], status_rows)}

失败终点保留在请求和标量中，没有删去或补成零分。新增原生计算分 6 批、每批 6 个进程；实测批次执行时间合计 {summary['native_execution_seconds_sum']:.2f} 秒，平均 {summary['native_execution_endpoints_per_second']:.2f} 个终点/秒。该吞吐量包含当批执行过程，未包含人为停顿、打包保存及后续统计，不能直接推为其他人数或更大空间的固定速率。每批独立完整保存请求、98 列标量、精简几何和完成回执；大运行缓存不进入交付包。

{md_table(['批次', '条件', '新终点', '主进程墙钟秒', 'worker 经过秒数累加', '配置进程数', '终点/墙钟秒'], [[r['batch_id'],r['condition'],r['new_native'],f"{r['main_wall_seconds']:.2f}",f"{r['worker_pool_elapsed_seconds_sum']:.2f}",r['configured_worker_processes'],f"{r['native_endpoints_per_second']:.2f}"] for r in execution_rows])}

批次墙钟来自原 `EXECUTION.json` 中主进程的 `time.monotonic()` 区间，截止便携表导出完成；worker 经过秒数是多个并发任务的时间相加，合计 {summary['worker_pool_elapsed_seconds_sum']:.2f} 秒，不能当作墙钟。6 表示配置的 worker 进程数；原日志没有记录进程 CPU time 或实际 CPU 核占用，因此不将 worker 秒数称为 CPU 工作秒。

在“六进程持续维持本次平均吞吐、无额外优化”的机械假设下，全部剩余 n=20 具体成员集合约需 {estimate_rows[-1]['mechanically_estimated_years']:,.1f} 年。这个量级计算不是完成时间承诺，也没有包括存储增长；各来源/构成的实际代价可能不同。准确剩余数仍是 {possible_total-computed_total:,} 个，没有将每格抽样冒充全成员穷尽。逐条件估算见 `N20_REMAINING_SCALE_ESTIMATE.csv`。

## 4. 复现和证据入口

- `N20_COMPLETION.json`：逐批完整键集合核对、合并去重、失败分母、全局实际覆盖。
- `N20_METHOD_COMPLETION.csv`：六方法每条件完整配置覆盖。
- `UNIVERSE_FINAL_COVERAGE_AFTER_N20.csv.gz`：全方法、全部原登记人数的逐池覆盖与精确剩余。
- `FROZEN_METHOD_K_SUMMARY.csv`：全部冻结方法 K 范围；`N20_POOL_K_AND_MEMBER_UNIVERSE.csv`：每池 K、成员容量与全部具体成员规模。
- `N20_DISTINCT_MEMBER_UNION_BY_POOL.csv`、`N20_DISTINCT_MEMBER_UNION_BY_CONDITION.csv`、`N20_SCOPE_COUNTS.json`：多方法实际成员空间去重和加入顺序规模。
- `BATCH_EXECUTION_SUMMARY.csv`：逐批实测执行时间与失败分母。
- `N20_REMAINING_SCALE_ESTIMATE.csv`：精确剩余集合数和明确假设的吞吐量级计算。
- 上级目录 `finalize_n20_coverage.py`、`summarize_n20_scope.py`：从冻结请求、已完成分批结果及上一阶段覆盖重建本回执，不运行融合。

保留目标楼外冻结标签、参考绑定、环序、正式资格、原生融合和 B8L2/D10 合同。旧阶段文件没有覆盖。曾发现配置成员表 gzip 末尾不完整，已按同 seed、同 cell_id 重建并以原子发布替代；请求 JSON 和标签 SHA256 保持不变，原生计算没有重做。详见上级目录 `SERIALIZATION_REPAIR_RECEIPT.json`。当前表均通过完整 gzip 解压、行数、唯一键和冻结请求集合核对。

本批新增终点用于大团队构成总作用、细类增量与连续 Q/T 对照。本覆盖包不承担匹配事件；续研另由 `n20_abc` 对预登记团队做新匹配对照，按共同背景、总人数与实际替换人数 m 分别检验。一般跨配置变化不能替代该对照。v2 和本批均处在有记录的积极探索之后，不宣称全新盲测。
'''
    report_path = OUT / '本批计算与组合覆盖回执_20261021.md'
    temp = report_path.with_suffix('.md.tmp')
    temp.write_text(report, encoding='utf-8')
    temp.replace(report_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
