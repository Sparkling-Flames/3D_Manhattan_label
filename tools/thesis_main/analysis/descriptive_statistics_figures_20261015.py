"""从描述统计快照生成可复用科研图；不重评分、不改变面板或关系。"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ROOT / 'research/descriptive_statistics_20261015'
DIFFICULTIES = ['简单', '中等', '困难']
COLORS = ['#3a8c94', '#d9a441', '#aa5778']
METRICS = ['WQ', 'A10', 'B8L2', 'IoU3D100']


def figure_manifest(contract, source):
    metrics = {
        metric: dict(version=contract['score_versions'][metric],
                     source=f'{source.as_posix()}/records.csv:{metric}', unit='0-100',
                     reference_column='reference_id')
        for metric in ['WQ', 'A10', 'B8L2']
    }
    metrics['IoU3D100'] = dict(version=None, version_note='原字段合同未单独声明IoU算法版本，不借用WQ版本',
                               source=f'{source.as_posix()}/records.csv:IoU3D100',
                               unit=contract['iou_units']['IoU3D100'], reference_column='reference_id')
    metrics['active_time_seconds'] = dict(version_column='time_rule_version',
                                          source=f'{source.as_posix()}/records.csv:active_time_seconds',
                                          unit=contract['time_unit'], valid_status='usable')
    return dict(version='descriptive_statistics_figures_20261015_v1',
                source_contract=f'{source.as_posix()}/FIELD_CONTRACT.json',
                source_schema_version=contract['version'], protocol=contract['protocol'],
                upstream_sources=contract['sources'], metrics=metrics,
                score_version_column_semantics='records.csv及图表CSV的score_version仅为原WQ版本；不是A10/B8L2版本。',
                same_room_score_version_semantics='同房CSV的score_version_a/b及score_versions_a/b沿用原WQ绑定上下文；指标版本按本manifest.metrics读取。',
                same_room_iou_3d_unit=contract['iou_units']['same_room_iou_3d'],
                reuse_scope='八图支持当前描述统计schema的快照目录替换，样本数从数据读取；质量面板当前固定WQ/A10/B8L2/IoU3D100四指标。',
                long_score_interface_consumed=False,
                future_algorithm_path='新算法可由新的long-score接入口表接入绘图；当前八图不自动消费该入口，也不自动扩展算法面板。')


def select_panels(records):
    """保留用途集合与缺失，拒绝快照中的重复主键或错误有效时间。"""
    assert records.inventory_record_id.is_unique, 'duplicate inventory_record_id'
    assert records.loc[records.active_time_seconds.notna(), 'time_status'].eq('usable').all()
    assert records.loc[records.active_time_seconds.notna(), 'active_time_seconds'].gt(0).all()
    return {
        '全部库存': records,
        '已有完整评分': records[records.WQ.notna()],
        '人员主画像': records[records.in_worker_931.eq(True)],
        '同目标条件': records[records.in_target_836.eq(True)],
    }


def primary_pairs(pairs):
    selected = pairs[(pairs.relation == 'confirmed_comparable') &
                     (pairs.metric == 'WQ') & (pairs.n_pairs >= 4)].copy()
    assert not selected.duplicated(['image_a', 'image_b']).any()
    return selected


def export(fig, out, name, data, note):
    fig.text(.02, .018, note, fontsize=9, color='#444444', va='bottom')
    fig.tight_layout(rect=(0, .07, 1, .96))
    fig.savefig(out / f'{name}.png', dpi=160, facecolor='white')
    fig.savefig(out / f'{name}.svg', facecolor='white')
    data.to_csv(out / f'{name}.csv', index=False, encoding='utf-8-sig')
    plt.close(fig)


def build(source, out):
    out.mkdir(parents=True, exist_ok=True)
    available = {font.name for font in font_manager.fontManager.ttflist}
    chosen = next(name for name in ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC'] if name in available)
    plt.rcParams.update({'font.family': chosen, 'axes.unicode_minus': False,
                         'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'svg.fonttype': 'none'})
    records = pd.read_csv(source / 'records.csv', encoding='utf-8-sig')
    images = pd.read_csv(source / 'images.csv', encoding='utf-8-sig')
    pairs = pd.read_csv(source / 'same_room_pair_metrics.csv', encoding='utf-8-sig')
    wp = pd.read_csv(source / 'same_room_worker_pairs.csv', encoding='utf-8-sig')
    contract = json.loads((source/'FIELD_CONTRACT.json').read_text(encoding='utf-8'))
    (out/'FIGURE_MANIFEST.json').write_text(json.dumps(figure_manifest(contract, source),
                                                     ensure_ascii=False, indent=2), encoding='utf-8')
    assert images.image_id.is_unique
    assert set(records.image_id) <= set(images.image_id)
    panels = select_panels(records)
    target = panels['同目标条件']

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))
    coverage = pd.DataFrame([dict(panel=k, n_records=len(v), n_images=v.image_id.nunique(),
                                 n_workers=v.worker_id.nunique(),
                                 n_valid_time=v.active_time_seconds.notna().sum()) for k, v in panels.items()])
    axes[0].barh(coverage.panel, coverage.n_records, color='#447b9d')
    for i, row in coverage.iterrows():
        axes[0].text(row.n_records + len(records)*.012, i,
                     f'{row.n_records}行 / {row.n_images}图 / {row.n_workers}人', va='center', fontsize=9)
    axes[0].set_xlim(0, len(records)*1.5)
    axes[0].invert_yaxis()
    axes[0].set(title='不同用途集合（重叠，不可相加）', xlabel='作答行数')
    status = records.time_status.value_counts().rename_axis('time_status').reset_index(name='n')
    labels = {'usable': '有效 active_time', 'new_collection_time_unfrozen': '新采集时间未冻结',
              'lead_time_fallback': '仅 lead_time，未替代', 'historical_time_ineligible': '历史时间不合资格',
              'known_manual_adjustment': '已知人工调整'}
    axes[1].barh(status.time_status.map(labels).fillna(status.time_status), status.n,
                 color=['#3a8c94' if value == 'usable' else '#b8bec4' for value in status.time_status])
    for i, n in enumerate(status.n): axes[1].text(n+20, i, str(n), va='center')
    axes[1].invert_yaxis()
    axes[1].set(title=f'库存时间状态（n={len(records)}）', xlabel='作答行数', xlim=(0, status.n.max()*1.2))
    coverage_data = pd.concat([coverage.assign(table='panel_coverage'),
                               status.assign(table='inventory_time_status')], ignore_index=True)
    export(fig, out, '01_集合与时间覆盖', coverage_data,
           '有效时间仅使用已绑定来源的秒数；缺失、未冻结及 lead_time 不补零。图为库存描述，不授予评价资格。')

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    counts = images.difficulty_class.fillna('未记录').value_counts().rename_axis('difficulty_class').reset_index(name='n_images')
    axes[0].bar(counts.difficulty_class, counts.n_images, color='#447b9d')
    for i, n in enumerate(counts.n_images): axes[0].text(i, n+2, str(n), ha='center')
    axes[0].set(title=f'全图片难度标签（{len(images)}图）', ylabel='图片数', ylim=(0, counts.n_images.max()*1.18))
    axes[1].axis('off')
    axes[1].text(.01, .88, '难度与特殊场景保持分轴', size=15, weight='bold')
    axis_counts = []
    lines = []
    axis_labels = {'unknown': '未知', 'yes': '是', 'no': '否', 'pending': '待定',
                   'unknown_not_inferred_from_difficulty': '未显式记录（不从难度推断）',
                   'recorded_doorway_annotatable': '门洞已记录可标',
                   'conditional_nonorthogonal_annotatable': '非正交条件可标'}
    for column, label in [('doorway_axis', '门洞轴'), ('oos_axis', 'OOS轴'),
                          ('markability_from_explicit_label', '显式可标性')]:
        for value, n in images[column].fillna('未记录').value_counts().items():
            axis_counts.append(dict(axis=column, status=value, n_images=n))
            lines.append(f'{label} · {axis_labels.get(value, value)}: {n}图')
    axes[1].text(.01, .76, '\n'.join(lines), size=10, va='top', linespacing=1.7)
    export(fig, out, '02_全图难度与分轴覆盖', pd.concat([counts, pd.DataFrame(axis_counts)], ignore_index=True),
           '全图标签不意味着均可评价；门洞、OOS、可标性与难度不互相推断。各轴内部计数可核对，各轴之间不可相加。')

    fig, axes = plt.subplots(1, 4, figsize=(15, 5.5), sharey=True)
    dist = target[['inventory_record_id', 'image_id', 'worker_id', 'conditional_difficulty', 'reference_id', 'score_version'] + METRICS].copy()
    for ax, metric in zip(axes, METRICS):
        groups = [target[target.conditional_difficulty == d] for d in DIFFICULTIES]
        ax.boxplot([g[metric].dropna() for g in groups], positions=np.arange(3), widths=.5,
                   showfliers=False, medianprops={'color': 'black'})
        for i, (group, color) in enumerate(zip(groups, COLORS)):
            ordered = group.sort_values('inventory_record_id')[metric].dropna()
            jitter = np.random.default_rng(15).uniform(-.18, .18, len(ordered))
            ax.scatter(i+jitter, ordered, s=5, alpha=.2, color=color, rasterized=True)
        ax.set_xticks(range(3), [f'{d}\nn={g[metric].notna().sum()} / {g.image_id.nunique()}图'
                                for d, g in zip(DIFFICULTIES, groups)])
        ax.set(title=metric if metric != 'IoU3D100' else '均高棱柱3D IoU ×100', ylim=(0, 103))
        ax.grid(axis='y', alpha=.2)
    axes[0].set_ylabel('分数（0—100）')
    fig.suptitle(f'同目标条件面板：按难度保留真实作答分布（{len(target)}行 / {target.image_id.nunique()}图）', fontsize=14)
    export(fig, out, '03_同目标难度质量分布', dist,
           '点为作答，箱体为P25—P75、线为中位数、须为1.5 IQR内范围；重复人员/图片不独立，无显著性或能力推断。')

    scored = panels['已有完整评分']
    matrix = scored.pivot_table(index='worker_id', columns='image_code', values='WQ', aggfunc='mean').sort_index().sort_index(axis=1)
    matrix = matrix.reindex(sorted(records.worker_id.unique()))
    fig, ax = plt.subplots(figsize=(17, 7))
    cmap = plt.colormaps['viridis'].copy(); cmap.set_bad('#e4e4e4')
    artist = ax.imshow(matrix, aspect='auto', vmin=0, vmax=100, cmap=cmap, interpolation='nearest')
    ax.set_yticks(range(len(matrix)), matrix.index)
    ticks = list(range(0, len(matrix.columns), 5))
    ax.set_xticks(ticks, matrix.columns[ticks], rotation=65, ha='right', fontsize=7)
    ax.set(title=f'原WQ覆盖矩阵：按稳定ID排序（{matrix.shape[0]}人 × {matrix.shape[1]}张已评分图）', xlabel='图片代码（完整列见CSV）', ylabel='人员ID（非能力排名）')
    fig.colorbar(artist, ax=ax, label='原WQ', pad=.01, shrink=.8)
    export(fig, out, '04_人员图片WQ覆盖矩阵', matrix.rename_axis('worker_id').reset_index(),
           '灰色为该人员在该图无完整评分，不是0分；同人同图若有多条记录取描述均值。不同任务/参考组成不支持直接能力排名。')

    fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharey='row')
    comp = scored[['inventory_record_id', 'image_id', 'worker_id', 'reference_id', 'score_version'] + METRICS].copy()
    deltas = []
    for col, metric in enumerate(METRICS[1:]):
        paired = scored.dropna(subset=['WQ', metric])
        delta = paired[metric] - paired.WQ
        axes[0, col].scatter(paired.WQ, paired[metric], s=6, alpha=.25, color='#447b9d', rasterized=True)
        axes[0, col].plot([0, 100], [0, 100], color='#888888', lw=1)
        axes[0, col].set(xlim=(0, 100), ylim=(0, 100), xlabel='原WQ', ylabel=metric,
                         title=f'{metric}：同作答同参考 n={len(paired)}')
        axes[1, col].hist(delta, bins=32, color='#3a8c94', alpha=.85)
        axes[1, col].axvline(0, color='#777777', lw=1)
        axes[1, col].set(xlabel=f'{metric} − WQ', ylabel='作答行数',
                         title=f'差值中位数 {delta.median():.2f} / IQR {delta.quantile(.75)-delta.quantile(.25):.2f}')
        comp[f'{metric}_minus_WQ'] = comp[metric] - comp.WQ
        deltas.append(f'{metric}差值中位数{delta.median():.2f}')
    export(fig, out, '05_同集合公式差异', comp,
           '各算法保留原版本；同输入/同参考的数值比较不验证优劣。均高棱柱IoU度量对象与复合质量分数不同。')

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.5), sharex=True, sharey=True)
    time_data = target[['inventory_record_id', 'image_id', 'worker_id', 'reference_id', 'conditional_difficulty', 'active_time_seconds', 'time_status', 'WQ']].copy()
    for ax, difficulty, color in zip(axes, DIFFICULTIES, COLORS):
        group = target[target.conditional_difficulty == difficulty]
        valid = group.dropna(subset=['active_time_seconds', 'WQ'])
        ax.scatter(valid.active_time_seconds, valid.WQ, s=12, color=color, alpha=.4, rasterized=True)
        ax.set_xscale('log')
        ax.set(xlabel='有效 active_time（秒，对数轴）', ylim=(0, 103),
               title=f'{difficulty}\n双有效n={len(valid)} / {valid.image_id.nunique()}图；时间缺失{group.active_time_seconds.isna().sum()}')
        ax.grid(alpha=.2)
    axes[0].set_ylabel('原WQ（0—100）')
    fig.suptitle('同目标条件面板：时间与质量的观测分布', fontsize=14)
    export(fig, out, '06_有效时间质量分层', time_data,
           '每点为作答；未冻结/无资格/仅lead_time不进入横轴。任务组成、人员与图片重复共同影响分布，不解释因果或速度能力。')

    primary = primary_pairs(pairs).sort_values(['candidate_ids', 'image_code_a', 'image_code_b'])
    fig, axes = plt.subplots(1, 3, figsize=(16, max(7, len(primary)*.29)), sharey=True)
    y = np.arange(len(primary))
    labels = [f'{r.candidate_ids} · {r.image_code_a.split("-")[-1]}—{r.image_code_b.split("-")[-1]} (n={r.n_pairs})'
              for r in primary.itertuples()]
    pdata = []
    for ax, metric in zip(axes[:2], ['WQ', 'B8L2']):
        rows = primary[['image_a', 'image_b']].merge(pairs[pairs.metric == metric], on=['image_a', 'image_b'], validate='one_to_one')
        ax.hlines(y, rows.paired_a_mean, rows.paired_b_mean, color='#aaaaaa', lw=1.5)
        ax.scatter(rows.paired_a_mean, y, label='视角A', s=28, color='#447b9d')
        ax.scatter(rows.paired_b_mean, y, label='视角B', s=28, marker='s', color='#ba6657')
        ax.set(xlim=(0,100), xlabel='共同人员均值（0—100）', title=metric)
        ax.legend(loc='lower left', frameon=False)
        pdata.append(rows)
    times = primary[['image_a', 'image_b']].merge(pairs[pairs.metric == 'active_time_seconds'], on=['image_a', 'image_b'], validate='one_to_one')
    axes[2].barh(y, times.n_pairs, color='#3a8c94', label='双侧有效时间配对')
    for i, (n, total) in enumerate(zip(times.n_pairs, primary.n_pairs)):
        axes[2].text(n+.1, i, f'{n}/{total}', va='center', fontsize=9)
    axes[2].set(xlim=(0,max(primary.n_pairs)+2), xlabel='双侧有效时间数 / 质量配对数', title='同一共同人员池的时间覆盖')
    axes[0].set_yticks(y, labels, fontsize=9)
    axes[0].invert_yaxis()
    fig.suptitle(f'确认可比且≥4名共同人员：{len(primary)}个直接图对（不等于独立房间）', fontsize=14)
    pdata.append(times)
    export(fig, out, '07_同房共同人员视角与时间', pd.concat(pdata, ignore_index=True),
           'A/B按稳定图片ID定义；G057、G178为直接关系证据。多对共享人员和视角；每对共同人员不同，不串成固定池视角排名。')
    chosen_pairs = primary[['image_a','image_b']]
    paired_rows = wp.merge(chosen_pairs, on=['image_a','image_b'], validate='many_to_one')
    paired_rows.to_csv(out/'07_同房逐人配对图表数据.csv', index=False, encoding='utf-8-sig')
    fig, axes = plt.subplots(1, 2, figsize=(13, max(7, len(primary)*.29)), sharey=True, sharex=True)
    for ax, metric in zip(axes, ['WQ', 'B8L2']):
        for i, row in enumerate(primary.itertuples()):
            values = paired_rows[(paired_rows.image_a == row.image_a) &
                                 (paired_rows.image_b == row.image_b) &
                                 (paired_rows.metric == metric) & paired_rows.paired.eq(True)].delta_b_minus_a
            jitter = np.random.default_rng(15).uniform(-.16,.16,len(values))
            ax.scatter(values, i+jitter, s=18, alpha=.6, color='#447b9d')
            ax.plot([values.mean()], [i], marker='D', ms=5, color='#ba6657')
        ax.axvline(0, color='#888888', lw=1)
        ax.set(title=metric, xlabel='同一人员：视角B − 视角A（分）')
        ax.grid(axis='x', alpha=.2)
    axes[0].set_yticks(y, labels, fontsize=9)
    axes[0].invert_yaxis()
    fig.suptitle('同房视角：均值接近是否掩盖逐人变化', fontsize=14)
    export(fig, out, '08_同房逐人质量变化', paired_rows[paired_rows.metric.isin(['WQ','B8L2'])],
           '圆点为同一人员的双侧配对差值，菱形为图对均值差。多对共享人员/视角，点不可当独立样本；同房不预设质量一致。')
    notes = f'''# 关键数据可视化

生成入口：`python tools/thesis_main/analysis/descriptive_statistics_figures_20261015.py --source-dir {source.as_posix()} --out {out.as_posix()}`。
输入为既有描述统计快照，不重评分；更换快照目录可复用。每图附PNG、可编辑SVG及CSV，缺失不补零。

指标版本、来源和单位见同目录 `FIGURE_MANIFEST.json`，由输入 `FIELD_CONTRACT.json` 生成。CSV中原有的 `score_version`（同房表的 `score_version_a/b`、`score_versions_a/b`同理）仅表示原WQ绑定上下文，不能当作A10/B8L2版本。当前原WQ为 `{contract['score_versions']['WQ']}`、A10为 `{contract['score_versions']['A10']}`、B8L2为 `{contract['score_versions']['B8L2']}`；IoU原合同未单列算法版本，不借用WQ版本。

这八图是当前描述统计schema的可复用绘图，分母从输入读取，质量面板当前固定四指标。当前不自动消费新long-score接入口；未来新算法可从该long表接图，本轮未实现通用算法面板或UI。

|图|阅读目的与当前数据观察|
|---|---|
|01 集合与时间覆盖|{len(records)}条库存与{len(scored)}条完整评分、{len(panels['人员主画像'])}条主画像、{len(target)}条同目标各有用途；有效时间{records.active_time_seconds.notna().sum()}条。集合不可相加。|
|02 全图难度与分轴覆盖|{len(images)}图的完整难度分母；门洞、OOS、显式可标性各自保留未知与独立状态。|
|03 同目标难度质量分布|四种指标在相同{len(target)}条面板中展示作答、箱体、中位与图数；不要求难度均值单调，不把重复作答当独立图片。|
|04 人员图片WQ覆盖矩阵|按稳定ID展示不平衡任务覆盖及缺失。灰格不是低分，原均值不是能力排名；矩阵没有加入未评分图片列，全部图片覆盖见图02。|
|05 同集合公式差异|{'; '.join(deltas)}；同输入/同参考的数值移动不是算法更正确的证据，IoU仍为均高棱柱口径。|
|06 有效时间质量分层|同目标面板时间双有效{target.active_time_seconds.notna().sum()}条；对数秒轴，按难度保留时间缺失。散点不说明时间影响质量。|
|07 同房共同人员视角与时间|{len(primary)}个≥4人直接图对，质量配对{primary.n_pairs.sum()}个，双侧时间配对{times.n_pairs.sum()}个；共享人员/视角，不能当独立房间或独立配对样本。|
|08 同房逐人质量变化|同一批直接图对展示每人的两视角差值及图对均值差；均值相近时仍可有明显逐人变化，不以平均值掩盖个体差异。|

图03与06使用同目标条件面板；图04与05使用已有完整评分面板，不混用分母。图03点透明叠加及图04灰格显示覆盖，不补齐缺失。主质量图07仅确认可比关系；其它支持与未确认层仍见原关系表，没有被删除或升级。最终图为正式交付，不作为临时检查截图清理。
'''
    notes += '\n## 查看与导出\n\n'
    for picture in sorted(out.glob('[0-9][0-9]_*.png')):
        name = picture.stem
        notes += f'- {name}：[查看PNG]({name}.png) · [矢量SVG]({name}.svg) · [图表数据]({name}.csv)\n'
    (out/'FIGURES.md').write_text(notes, encoding='utf-8')
    return coverage


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=DEFAULT)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    build(args.source_dir, args.out or args.source_dir/'figures')
