"""Post-assessment full composition strata of the frozen n=13, m=5 panel.

No native fusion, relabelling, rule selection, or target-driven re-sampling occurs.
Run from any working directory with the recovered study root intact.
"""
from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from assessment_summary_common import (
    BASE, HERE, METRICS, load_exact, sha, summarize, write_csv, write_json,
)

METHOD = 'R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1'
CLASSES = ('C01', 'C02')
KEYS = ['vector_id', 'outgoing_class', 'incoming_class',
        'A_B_full_counts', 'C_full_counts', 'core_full_counts']


def canonical_counts(counts):
    assert not (set(counts) - set(CLASSES)), counts
    return json.dumps({c: int(counts.get(c, 0)) for c in CLASSES}, separators=(',', ':'))


def worker_tuple(values):
    return tuple(sorted(values))


def members(series):
    return set(itertools.chain.from_iterable(series))


def physical_support(g):
    """Raw support is counted, never averaged with building weights."""
    core_sets = [worker_tuple(x) for x in g.core_workers]
    core_pool = set(zip(g.pool_id, core_sets))
    teams = {(row.pool_id, getattr(row, arm + '_team_key'))
             for row in g.itertuples() for arm in 'ABC'}
    team_sets = {worker_tuple(getattr(row, arm + '_workers'))
                 for row in g.itertuples() for arm in 'ABC'}
    abc = {(row.pool_id, row.A_team_key, row.B_team_key, row.C_team_key)
           for row in g.itertuples()}
    block_a = {worker_tuple(x) for x in g.outgoing_workers}
    block_b = {worker_tuple(x) for x in g.within_incoming}
    block_c = {worker_tuple(x) for x in g.cross_incoming}
    people_a = members(g.outgoing_workers)
    people_b = members(g.within_incoming)
    people_c = members(g.cross_incoming)
    people_core = members(g.core_workers)
    image_core = g.assign(_core=[json.dumps(x) for x in core_sets]).groupby(
        ['building', 'image_id'], dropna=False)._core.nunique()
    multi = image_core[image_core >= 2]
    out = dict(
        actual_outgoing_A_people=len(people_a),
        actual_same_class_incoming_B_people=len(people_b),
        actual_outgoing_class_AB_people=len(people_a | people_b),
        actual_cross_class_incoming_C_people=len(people_c),
        actual_core_people=len(people_core),
        unique_core_worker_sets=len(set(core_sets)),
        unique_pool_core_worker_sets=len(core_pool),
        unique_pool_teams=len(teams),
        unique_global_team_worker_sets=len(team_sets),
        unique_exact_ABC_triples=len(abc),
        unique_outgoing_A_blocks=len(block_a),
        unique_same_class_incoming_B_blocks=len(block_b),
        unique_AB_class_blocks=len(block_a | block_b),
        unique_cross_class_incoming_C_blocks=len(block_c),
        true_images_with_at_least_two_distinct_cores=len(multi),
        buildings_with_at_least_two_cores_in_same_true_image=len(set(multi.index.get_level_values(0))),
        raw_finite_netQ_events=int(g.net_B8L2_change.notna().sum()),
        raw_worsen_gt5_events=int(g.net_Q_worsen_gt5.eq(1).sum()),
        raw_within_absQ_gt5_events=int(g.within_absQ_gt5.eq(1).sum()),
        raw_within_finite_absQ_events=int(g.within_abs_B8L2_change.notna().sum()),
        raw_cross_absQ_gt5_events=int(g.cross_absQ_gt5.eq(1).sum()),
        raw_cross_finite_absQ_events=int(g.cross_abs_B8L2_change.notna().sum()),
        raw_worst_event_netQ=g.net_B8L2_change.min(),
        raw_largest_event_within_absQ=g.within_abs_B8L2_change.max(),
        raw_largest_event_cross_absQ=g.cross_abs_B8L2_change.max(),
        raw_minimum_scored_B_Q=g.B_B8L2.min(),
        raw_minimum_scored_C_Q=g.C_B8L2.min(),
    )
    for arm in 'ABC':
        out[arm + '_incomplete_events'] = int((~g[arm + '_complete'].astype(bool)).sum())
        out[arm + '_unscored_events'] = int(g[arm + '_B8L2'].isna().sum())
        out[arm + '_complete_but_unscored_events'] = int((g[arm + '_complete'].astype(bool) & g[arm + '_B8L2'].isna()).sum())
        out[arm + '_unique_scored_teams'] = len(set(zip(g.loc[g[arm + '_B8L2'].notna(), 'pool_id'], g.loc[g[arm + '_B8L2'].notna(), arm + '_team_key'])))
        out[arm + '_unique_incomplete_teams'] = len(set(zip(g.loc[~g[arm + '_complete'].astype(bool), 'pool_id'], g.loc[~g[arm + '_complete'].astype(bool), arm + '_team_key'])))
    assert out['unique_pool_teams'] == 3 * len(g)
    assert out['unique_exact_ABC_triples'] == len(g)
    return out


def add_physical_support(table, frame, keys):
    rows = []
    for key, g in frame.groupby(keys, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        rows.append(dict(zip(keys, key)) | physical_support(g))
    return table.merge(pd.DataFrame(rows), on=keys, validate='one_to_one')


def composition_name(value):
    v = json.loads(value)
    return f"{v['C01']}C01 + {v['C02']}C02"


def make_note(ag):
    lines = [
        '# 13 人换 5 人：完整构成向量的事后分层',
        '',
        '本表只重新汇总已冻结评估的两方向各 58 个事件：共 116 个 ABC、348 个不同实际团队、29 张真实图片、29 个参考池、6 栋建筑、35 名新批人员。没有新融合、改类、改方向或重新采样。这是既有评估的事后构成分层，不是新的独立验证。10 个实际向量全部保留，低支持的 NV01、NV06 没有补数。',
        '',
        '每个事件的 A/B 完整类别构成相同；二者保留同一 8 人核心、用 5 名同类成员相互替换。C 保留这个核心，改用另一类的 5 人。主稳定与 shape 的“同/跨”分别指 A–B、A–C；质量 ΔQ 指 C−B。每个完整向量先在固定参考池内平均，再按真实图片、建筑汇总，最后各建筑等权。比率分母的可评分支持与失败次数另列，质量缺失不补零。',
        '',
        '| ID | A/B 完整构成 → C 完整构成 | 事件 / 图 / 楼 | 同/跨主稳定 | 同/跨 shape | ΔQ（C−B） | 同构成绝对 Q 波动>5 | 净恶化>5 |',
        '|---|---|---:|---:|---:|---:|---:|---:|',
    ]
    for r in ag.itertuples():
        lines.append(f'| {r.vector_id} | {composition_name(r.A_B_full_counts)} → {composition_name(r.C_full_counts)} | '
                     f'{r.events}/{r.true_images}/{r.buildings} | '
                     f'{100*r.within_joint_stable_main:.1f}% / {100*r.cross_joint_stable_main:.1f}% | '
                     f'{100*r.within_geometry_shape_main:.1f}% / {100*r.cross_geometry_shape_main:.1f}% | '
                     f'{r.net_B8L2_change:+.3f} | {100*r.within_absQ_gt5:.1f}% | {100*r.net_Q_worsen_gt5:.1f}% |')
    lines += [
        '',
        '## 可供正文解释的三个配比',
        '',
        '**NV04，10C01+3C02 → 5C01+8C02。** 13 图、5 楼的 15 个不同核心、45 队提供了质量下降与形状改变同时出现的例子。楼等权 ΔQ 为 −10.633，13 图中 10 图下降，5 楼中 4 楼下降；同/跨 shape 稳定率为 83.33%/56.67%。同构成换人 |ΔQ|>5 的比例仍达 23.33%，所以只能说改变构成增加了变化与下降风险。全部 45 队完整且可评分；实际最差单事件 ΔQ 为 −39.933。',
        '',
        '**NV09，7C01+6C02 → 12C01+1C02。** 21 图、6 楼的 26 个不同核心、78 队是覆盖最广的一种完整向量变化。楼等权 ΔQ 为 +4.330；15 图、4 楼为正，6 图、2 楼为负。同/跨主稳定为 56.90%/46.19%，shape 为 78.73%/64.84%。C 有 1 个不完整/不可评分团队，净质量按其余 25 个事件计算，仍覆盖全部 21 图、6 楼。净恶化超过 5 分为 7.94%；最差单事件为 −15.305。相同完整配比并不保证同等收益。',
        '',
        '**NV10，8C01+5C02 → 13C01+0C02。** 11 图、5 楼的 13 个不同核心、39 队均完整可评分。楼等权 ΔQ 为 +12.923，9 图为正、2 图为负，各楼均值均为正；但 A–B 主稳定只有 20%，甚至低于 A–C 的 35%，同构成换人 |ΔQ|>5 为 25%。因此该组支持“换后质量较好”的条件规律，不能用来宣称 C02 人员可互换。必要结构的辅助诊断方向也改善：参考墙覆盖平均 +0.111、参考角点召回 +0.180；这些是冻结参考诊断，不是独立的必要结构裁定。',
        '',
        '## 同一配比、不同实际核心的证据',
        '',
        'NV04、NV09、NV10 分别有 2、5、2 张图在同一完整向量内出现两组不同实际核心；相应全部核心集合分别为 15、26、13 个。同构成稳定率是各实际核心内 A–B 比较的汇总，不是把所有不同核心团队两两混在一起计算的概率。不同核心/不同团队的增加不能当成新图片。',
        '',
        'NV09 的 UwV83HsGsw3-12 提供一对直接反例：事件 I20_a6156da6a162584540585e 的 A/B/C 质量为 55.065/56.878/96.082，A–B 主稳定和 shape 均通过，C 明显改善并改变形状；同图、同完整构成的另一组实际核心 I20_194b6e79cd6871602b77c8 为 96.995/96.890/98.318，A–B 与 A–C 的 shape 均稳定。两组都属于 7C01+6C02 → 12C01+1C02，但背景成员/具体块不同，获益规模不同。它们是同图机制证据，不能计作两张独立图片。',
        '',
        'NV10 的 q9vSo1VnCiC-30（I20_7c2bb302842255defff2ae）更清楚地提醒类内风险：A/B/C 为 90.123/37.683/93.417，A 与 B 完整构成一样且共用 8 人核心，但质量相差 52.440，shape 也不稳定。',
        '',
        '## 解释边界与文件',
        '',
        '各向量覆盖的图片、建筑和人员组合不同。不得用各行 +12.923、+4.330、−10.633 的大小直接推断最优配比、单调比例效应或跨图普遍互补。方向在实际事件内对照；向量分层是事后描述。类别仅由 10 栋历史建筑的真实替换关系学习，目标建筑质量没有用于分型。所有团队为同一新批次，但历史 Q 不匹配；因此此表不能单独证明超出 Q 的独立效应。',
        '',
        '`FULL_VECTOR_SMALL.csv` 是完整的 10 行核心表；`full_vector_aggregate.csv.gz` 保留均值、坏尾、辅助几何、成员/核心/团队与有限分母；`full_vector_per_true_image.csv.gz` 和 `full_vector_per_building.csv.gz` 可复算楼等权结果；`exact_events_and_members.csv.gz` 保留每个事件的完整人数向量、参考、核心、A/B/C 成员、团队键、精确事件哈希与实际主要结果。`FULL_VECTOR_RECEIPT.json` 记录输入 SHA 与检验。',
        '',
        '所有 *_per_pool_p10/p90 都是每池事件分位后再按图片、建筑等权；每个向量每池通常只有 1–2 条事件，仅作坏尾描述。原始最差值和原始失败次数另列，不进行楼权平均。真实人员/团队计数必须去重，跨行累加不是总支持。',
        '',
        '复现：`runtime_env/bin/python interchangeability_20261020/reverse/assessment_interpretation/summarize_full_vectors.py`。只读既有精确请求、冻结标签及官方完成的评估指标文件；没有原生融合调用。',
        '',
    ]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=HERE/'nested_new2/full_vectors')
    args = parser.parse_args()
    out = args.out
    frame, exact, provenance = load_exact('nested_new2', [METHOD])
    frame = frame.loc[(frame.n == 13) & (frame.m == 5)].copy()
    exact = exact.loc[exact.event_id.isin(frame.event_id)].copy()
    assert len(frame) == len(exact) == 116
    assert frame.pool_id.nunique() == frame.image_id.nunique() == 29
    assert frame.building.nunique() == 6
    assert frame.groupby('outgoing_class').size().to_dict() == {'C01': 58, 'C02': 58}
    assert frame.groupby('outgoing_class').image_id.nunique().eq(29).all()
    assert frame.A_new_n.eq(13).all() and frame.B_new_n.eq(13).all() and frame.C_new_n.eq(13).all()
    assert frame.actual_source_match.eq(True).all()
    assert exact.allowed_origins.map(lambda x: x == ['new']).all()

    for e in exact.itertuples():
        assert canonical_counts(e.A_counts) == canonical_counts(e.B_counts)
        assert sum(e.A_counts.values()) == sum(e.B_counts.values()) == sum(e.C_counts.values()) == 13
        assert sum(e.core_counts.values()) == 8
        before = Counter(e.core_counts); before[e.outgoing_class] += 5
        after = Counter(e.core_counts); after[e.incoming_class] += 5
        assert canonical_counts(before) == canonical_counts(e.A_counts)
        assert canonical_counts(after) == canonical_counts(e.C_counts)
        assert len(set(e.core_workers)) == 8
    attrs = exact[['event_id', 'A_counts', 'B_counts', 'C_counts', 'core_counts']].copy()
    attrs['A_B_full_counts'] = attrs.A_counts.map(canonical_counts)
    attrs['C_full_counts'] = attrs.C_counts.map(canonical_counts)
    attrs['core_full_counts'] = attrs.core_counts.map(canonical_counts)
    frame = frame.merge(attrs[['event_id', 'A_B_full_counts', 'C_full_counts', 'core_full_counts']],
                        on='event_id', validate='one_to_one')
    for metric_col, full_col in [('A_composition', 'A_B_full_counts'), ('C_composition', 'C_full_counts'), ('core_composition', 'core_full_counts')]:
        assert frame[metric_col].map(lambda x: canonical_counts(json.loads(x))).eq(frame[full_col]).all()
    vectors = frame[KEYS[1:]].drop_duplicates().copy()
    vectors['_n'] = vectors.A_B_full_counts.map(lambda x: json.loads(x)['C01'])
    vectors = vectors.sort_values(['outgoing_class', '_n']).drop(columns='_n').reset_index(drop=True)
    vectors['vector_id'] = [f'NV{i+1:02d}' for i in range(len(vectors))]
    assert len(vectors) == 10
    frame = frame.merge(vectors, on=KEYS[1:], validate='many_to_one').sort_values(['vector_id','building','image_id','event_id'])

    im, bu, ag = summarize(frame, KEYS, METRICS, tails=True)
    im = add_physical_support(im, frame, KEYS + ['building','image_id'])
    bu = add_physical_support(bu, frame, KEYS + ['building'])
    ag = add_physical_support(ag, frame, KEYS)
    ag['descriptive_support_ge3_images_ge2_buildings'] = (ag.true_images >= 3) & (ag.buildings >= 2)
    for table in [im,bu,ag]:
        for source, prefix in [('A_B_full_counts','A_B'),('C_full_counts','C'),('core_full_counts','core')]:
            for cl in CLASSES: table[f'{prefix}_{cl}_n'] = table[source].map(lambda x: json.loads(x)[cl])
    write_csv(out/'full_vector_aggregate.csv.gz', ag)
    write_csv(out/'full_vector_per_true_image.csv.gz', im)
    write_csv(out/'full_vector_per_building.csv.gz', bu)

    smallcols = KEYS + [
        'events','pools','true_images','buildings','actual_people','actual_outgoing_class_AB_people',
        'actual_cross_class_incoming_C_people','actual_core_people','unique_core_worker_sets',
        'unique_pool_teams','unique_global_team_worker_sets','unique_exact_ABC_triples','unique_AB_pairs',
        'true_images_with_at_least_two_distinct_cores',
        'within_joint_stable_main','cross_joint_stable_main','gap_joint_stable_main',
        'within_geometry_shape_main','cross_geometry_shape_main','gap_geometry_shape_main',
        'within_abs_B8L2_change','cross_abs_B8L2_change','net_B8L2_change','net_D10_change',
        'within_absQ_gt5','cross_absQ_gt5','net_Q_worsen_gt5',
        'net_B8L2_change_per_pool_p10','within_abs_B8L2_change_per_pool_p90',
        'within_floor_jaccard_difference','cross_floor_jaccard_difference',
        'net_diag_wall_coverage_05_delta','net_diag_corner_recall_05_delta',
        'raw_finite_netQ_events','net_B8L2_change_finite_true_images','net_B8L2_change_finite_buildings',
        'A_incomplete_events','B_incomplete_events','C_incomplete_events',
        'A_unscored_events','B_unscored_events','C_unscored_events',
        'raw_worst_event_netQ','raw_largest_event_within_absQ',
        'net_B8L2_change_positive_true_images','net_B8L2_change_negative_true_images',
        'net_B8L2_change_positive_buildings','net_B8L2_change_negative_buildings',
        'descriptive_support_ge3_images_ge2_buildings',
    ]
    write_csv(out/'FULL_VECTOR_SMALL.csv', ag[smallcols])
    exactcols = ['event_id','pool_id','image_id','image','building','reference_id','difficulty'] + KEYS + [
        'n','m','path_id','A_team_key','B_team_key','C_team_key',
        'core_workers','outgoing_workers','within_incoming','cross_incoming','A_workers','B_workers','C_workers',
        'A_complete','B_complete','C_complete','A_B8L2','B_B8L2','C_B8L2',
        'within_joint_stable_main','cross_joint_stable_main','within_geometry_shape_main','cross_geometry_shape_main',
        'within_abs_B8L2_change','cross_abs_B8L2_change','net_B8L2_change','net_D10_change',
        'within_floor_jaccard_difference','cross_floor_jaccard_difference','event_definition_sha256']
    ef = frame[exactcols].copy()
    for column in ['core_workers','outgoing_workers','within_incoming','cross_incoming','A_workers','B_workers','C_workers']:
        ef[column] = ef[column].map(lambda x: json.dumps(sorted(x), separators=(',', ':')))
    write_csv(out/'exact_events_and_members.csv.gz', ef)

    # Independent aggregate spot-check: with one reference pool per true image,
    # nested raw group means give exactly the same building-equal point estimate.
    for metric in ['net_B8L2_change','within_joint_stable_main','cross_joint_stable_main',
                   'within_geometry_shape_main','cross_geometry_shape_main']:
        alt = frame.groupby(['vector_id','building','image_id'])[metric].mean().groupby(['vector_id','building']).mean().groupby('vector_id').mean()
        assert np.allclose(ag.set_index('vector_id')[metric].reindex(alt.index), alt, equal_nan=True)
    (out/'FULL_VECTOR_FINDINGS_ZH.md').write_text(make_note(ag), encoding='utf-8')
    outputs = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(out.glob('*')) if p.is_file() and p.name != 'FULL_VECTOR_RECEIPT.json'}
    receipt = dict(
        purpose_zh='已冻结评估的事后完整类别构成分层；没有新融合、改类、改方向或独立新验证。',
        provenance=provenance, script_sha256=sha(__file__), exact_n=13, exact_m=5,
        pooled_support=dict(events=116, directions=2, pools=29, true_images=29, buildings=6,
                            actual_people=35, unique_teams=348, full_vector_transitions=10),
        hierarchy='event -> frozen-reference pool -> true image ID -> building -> equal buildings',
        metric_definitions_zh={
            'within':'A 与 B：同一图片/参考、相同8人核心、相同完整构成，替换同类5人。',
            'cross':'A 与 C：同一核心、相同5人替换规模，换入另一类；完整构成改变。',
            'net_B8L2_change':'C质量减B质量，不是C减A；坏尾 net_Q_worsen_gt5 指C-B<-5。',
            'stability_gap':'同类稳定率减跨类稳定率；正值意味着该配比中换另一类更容易改变结果。',
            'tails':'*_per_pool_p10/p90为每池事件分位后图内/楼等权，非全体事件分位；每池通常仅1或2条，属描述量。',
            'raw_support':'人员、团队、核心、失败次数为真实去重计数，不经楼权平均。',
            'raw_worst_event':'实际最差单事件，不是楼等权平均。',
            'missing':'失败保留；Q缺失不补零。有限分母另列。',
            'ratio_comparison':'各完整向量的图片/楼和成员支持不同，禁止将跨向量均分差直接解释为纯配比因果效应。',
            'class_boundary':'类别仅历史10楼真实替换关系学习；目标楼Q未用于分类。当前所有团队为同一新批次，但历史Q未匹配。',
            'support_threshold':'至少3真实图片且2楼仅用于突出可读描述，不改预冻结评估规则；全10向量保留。',
            'independence':'相同图的多个核心/成员组合不是独立新图片；两方向也不是相互独立的新图。',
        },
        output_files=outputs,
    )
    # Counts are recomputed rather than asserted from number of requested arms.
    receipt['pooled_support'].update(physical_support(frame))
    assert receipt['pooled_support']['unique_pool_teams'] == 348
    assert ag.events.sum() == 116
    write_json(out/'FULL_VECTOR_RECEIPT.json', receipt)
    print(ag[KEYS[:3]+['A_B_full_counts','C_full_counts','events','true_images','buildings',
          'within_joint_stable_main','cross_joint_stable_main','within_geometry_shape_main',
          'cross_geometry_shape_main','net_B8L2_change','within_absQ_gt5','net_Q_worsen_gt5',
          'raw_finite_netQ_events','raw_worst_event_netQ','unique_core_worker_sets','unique_pool_teams']].to_string(index=False))


if __name__ == '__main__':
    main()
