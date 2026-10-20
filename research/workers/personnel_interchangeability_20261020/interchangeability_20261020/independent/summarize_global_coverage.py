"""Write a compact Chinese coverage note from the audited small tables only."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    a = ap.parse_args()
    root = a.root.resolve()
    out = root/'interchangeability_20261020/independent/global_coverage'
    audit = json.loads((out/'GLOBAL_COVERAGE_AUDIT.json').read_text())
    assert audit['all_passed'] and not audit['warnings']
    batch = pd.read_csv(out/'BATCH_COVERAGE.csv')
    bpool = pd.read_csv(out/'BATCH_POOL_COVERAGE.csv')
    gp = pd.read_csv(out/'GLOBAL_POOL_COVERAGE.csv')
    gp = gp.rename(columns={'unique_pool_crew':'requested_unique_teams'})
    gp['batch_id'] = 'GLOBAL_DEDUP'
    combined = pd.concat([bpool,gp], ignore_index=True)
    result = []
    for bid, d in combined.groupby('batch_id', sort=False):
        groups = [('all', d)] + [('layer:'+k,g) for k,g in d.groupby('layer')] + [('phase:'+k,g) for k,g in d.groupby('actual_phase')]
        for group, g in groups:
            good = g[g.complete_evaluable.gt(0)]
            scored = g[g.finite_B8L2.gt(0)]
            result.append(dict(batch_id=bid,group=group,requested_unique_tasks=int(g.requested_unique_teams.sum()),
                attempted_pools=g.pool_id.nunique(),attempted_true_images=g.image_id.nunique(),attempted_buildings=g.building.nunique(),
                complete_teams=int(g.complete_evaluable.sum()),pools_with_complete_teams=good.pool_id.nunique(),
                true_images_with_complete_teams=good.image_id.nunique(),buildings_with_complete_teams=good.building.nunique(),
                pools_with_finite_Q=scored.pool_id.nunique(),true_images_with_finite_Q=scored.image_id.nunique(),
                attempted_pools_without_complete_teams=sorted(set(g.pool_id)-set(good.pool_id))))
    support = pd.DataFrame(result)
    support['attempted_pools_without_complete_teams'] = support.attempted_pools_without_complete_teams.map(lambda v:json.dumps(v,ensure_ascii=False))
    support.to_csv(out/'QUALIFIED_SUPPORT.csv',index=False)
    subset=support[(support.batch_id=='GLOBAL_DEDUP')&support.group.str.startswith('layer:')]
    name={
        'history_panel':'历史建筑新 entrant 面板', 'known_GR_integer_baseline':'已知 G/R 全整数 n/m 基线',
        'common_panel_discovery':'共同团队面板：发现','common_panel_assessment':'共同团队面板：评估',
        'forward_discovery':'正向类别块：发现','reverse_discovery':'反向类别块：发现',
        'condition_discovery':'同班 Manual/Semi：发现','condition_assessment':'同班 Manual/Semi：评估',
        'mixed_discovery':'混合构成／整队挑战：发现','mixed_assessment':'混合构成／整队挑战：评估',
        'ratio_grid_discovery':'纯混配比网格：发现','ratio_same_image_replication':'五比例同图新成员复查',
        'ratio_assessment':'五比例：评估','ratio_P05_local_census':'P05 单图固定有限总体普查',
        'fixed_direction_assessment':'冻结方向：评估','new2_nested_assessment':'new2 固定块嵌套人数：评估',
        'W132_postassessment_probe':'评估后 W132 同类替代机制探针'}
    text=[]
    text.append('# 本轮全部正式融合的覆盖与重复审计\n')
    text.append('**17 个正式原生运行批次共记录 573,428 次新融合调用，跨批去重后为 569,529 个“冻结图片池 × 精确成员集合”任务。** 它们覆盖 195 个池、181 张真图片、22 栋建筑、60 位人员和 6,244 份不同冻结作答记录。图片和建筑才是跨图规律的独立支持；几十万支高度重叠团队不能换算成同等数量的独立样本。\n')
    text.append('## 1. 这些数怎样对应\n')
    text.append('| 计数 | 数量 | 定义 |\n|---|---:|---|')
    for label, n, explanation in [
        ('请求行',audit['total_request_rows'],'每份请求文件中的全部行；同一精确任务可能出现在不同事件'),
        ('批内唯一任务的加和',audit['sum_of_within_batch_unique_tasks'],'每批先按池与真实成员去重，再加和，尚未跨批去重'),
        ('正式 native 新融合调用',audit['native_new_fusion_calls_from_run_receipts'],'17 份运行 receipt 的 new_fusions 加和；不同输出目录可能重算同一任务'),
        ('全局唯一池×成员任务',audit['global_unique_pool_crew'],'全 17 批按同一冻结池和完整成员集合去重'),
        ('真图片×成员集合',audit['global_unique_true_image_crew'],'忽略同图不同冻结条件池的区别，保留真 image_id'),
        ('纯人员集合',audit['global_distinct_crews_ignoring_all_pool_and_image_identity'],'完全忽略池与图片，仅数具体人员集合'),
        ('批内重复请求行',audit['within_manifest_repeated_request_rows'],'同一任务在请求中重复出现；不再融合'),
        ('跨批重复任务出现次数',audit['cross_batch_repeated_unique_task_occurrences'],'批内唯一任务的加和减全局唯一任务'),
        ('出现在多批中的任务',audit['global_tasks_occurring_in_multiple_batches'],'3,899 次额外出现涉及 3,534 个真实任务')]:
        text.append(f'| {label} | {n:,} | {explanation} |')
    text.append('\n所有 573,645 请求行的真实成员、k、有效池资格与精确成员哈希都已核对；所有请求任务都在对应原生池中。原生文件的冻结 pool_digest、参考 ID／版本、来源人数、objectID、科学代码版本和 wrapper SHA 一致。3,899 次跨批重复的全部科学字段指纹逐字一致，最大数值差为 0；没有未请求缓存队被计入。本审查不重新运行融合。\n')
    text.append('## 2. 正式评分资格与失败\n')
    text.append('全局完整可评价且 B8L2／D10 有限的任务为 **557,111**。n=2 的 **7,039** 个任务沿用 `two_person_deferred`，不当成普通融合失败，也不进入 n≥3 的主均分。n≥3 共 **562,490** 个任务，其中 **5,379** 个不完整：894 个 `below_four`、200 个 `invalid_floor`、4,285 个 `no_connection`。没有补零。完整融合比例与同构成几何稳定率是不同指标：一队完整可评分，不意味着换人后仍同形。\n')
    text.append('| 条件 | 实际请求池／真图 | 至少一队完整的池／真图 | 唯一任务 | 完整任务 |\n|---|---:|---:|---:|---:|')
    labels={'layer:ordinary_manual':'普通 Manual','layer:ordinary_semi':'普通 Semi','layer:doorway_manual':'门洞 Manual'}
    for _,r in subset.iterrows():
        text.append(f"| {labels.get(r.group,r.group)} | {int(r.attempted_pools)}／{int(r.attempted_true_images)} | {int(r.pools_with_complete_teams)}／{int(r.true_images_with_complete_teams)} | {int(r.requested_unique_tasks):,} | {int(r.complete_teams):,} |")
    text.append('\nSemi 的 `7y3sRwLe3Va-21` 和 `yqstnuAEVhm-27` 各只有 6 个请求任务、零完整评分，因此 14 是 attempted Semi 图片数，正式有评分的只有 12 图。它们并未被删除。总体 181 张真图的去重不把同图的 Manual 与 Semi 当成两张图。\n')
    text.append('## 3. 全部正式批次\n')
    text.append('| 批次 | 批内唯一池×成员任务 | 真图／楼 | 实际人员 | 完整队 |\n|---|---:|---:|---:|---:|')
    for _,r in batch.iterrows():
        text.append(f"| {name[r.batch_id]} | {int(r.unique_pool_crew):,} | {int(r.true_images)}／{int(r.buildings)} | {int(r.workers)} | {int(r.complete_evaluable):,} |")
    text.append('\n这张批次表各行允许共享池和成员，不能将图片、人员或任务列直接相加当全局唯一量。具体共享量见 `CROSS_BATCH_OVERLAP.csv`；每池／真图／人员的小表均保存实际支持。历史新面板覆盖 81 图／10 楼；非历史发现任务全局为 399,892、55 图／6 楼；评估任务为 138,098、45 图／6 楼。二者均是既有 v2 图片，并非新的外部盲测。\n')
    text.append('## 4. 排除与遗漏\n')
    text.append('冻结 snapshot 共 229 池、196 张真图。普通 Manual 的 177 池全部有本轮请求；未请求 34 池包括 13 个门洞 Manual、18 个普通 Semi、2 个特殊 Manual、1 个特殊 Semi。它们没有被当成零效果，也不能据未请求就判为数学上没有可行组合。逐池资格、方法容量及抽样遗漏以各批冻结台账为准；本覆盖审计不新造失败原因。`UNREQUESTED_FROZEN_POOLS.csv` 给出完整列表。\n')
    text.append('旧 A 保留的 122,082 个历史替换对观察属于训练／复用输入，不计本轮新融合。条件实验的全 phase union 请求、各重建目录副本、共同团队面板的竞争分类器和额外指标汇总都没有重复计成 native 批次。所有 17 个运行 receipt 均已定位，未发现漏记的新原生批次。\n')
    text.append('独立重放另列 `SUPPLEMENTARY_REPLAY_COUNTS.json`：旧 follow-up 抽样 30 队、基线机制 2,814 次仅状态重放、当时已有的案例重放 receipt。它们用于一致性和机制核验，不增加独立图片支持；这个补充表记录的是具名 receipt 中可核实的次数，不是对每次临时调试、标题重导出或绘图调用的累计性能剖析。正式科学运行的 573,428 次与这些重放分开。\n')
    text.append('## 5. 复现和交付依赖\n')
    text.append('`BATCH_REGISTRY.json` 给出全部精确请求、native 目录、运行 receipt、生成器及冻结文件路径和 SHA。`audit_global_coverage.py` 按批顺序读一份请求、按池读一个原生结果，核全部成员与全局去重；不需复制或保存全距离矩阵。精简交付可保留这组小表与 receipt，通过登记的生成代码／参数／种子重建大请求和原生缓存。若只重绘覆盖说明，运行 `summarize_global_coverage.py` 即可，输入仅本目录审计 JSON 与小 CSV。\n')
    text.append('全局精确任务成员 SHA-256：`'+audit['global_task_member_sha256']+'`。其排序和无损人员编码规则保存在 `GLOBAL_COVERAGE_AUDIT.json`，不依赖集合迭代顺序或截断的展示名称。\n')
    (out/'FINDINGS_ZH.md').write_text('\n'.join(text))
    code=Path(__file__).resolve()
    receipt=dict(code_sha256=hashlib.sha256(code.read_bytes()).hexdigest(),
        input_sha256={f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in ['GLOBAL_COVERAGE_AUDIT.json','BATCH_COVERAGE.csv','BATCH_POOL_COVERAGE.csv','GLOBAL_POOL_COVERAGE.csv']},
        outputs={f:dict(bytes=(out/f).stat().st_size,sha256=hashlib.sha256((out/f).read_bytes()).hexdigest()) for f in ['QUALIFIED_SUPPORT.csv','FINDINGS_ZH.md']},
        no_native_or_request_manifests_read=True)
    (out/'SMALL_TABLE_SUMMARY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2))
    print(json.dumps(dict(support_rows=len(support),output=str(out/'FINDINGS_ZH.md')),ensure_ascii=False))


if __name__=='__main__':main()
