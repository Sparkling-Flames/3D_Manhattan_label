#!/usr/bin/env python3
"""Plot completed historical policy32 summaries; no fitting or resampling."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument('--font', type=Path)
    args = ap.parse_args()
    base = args.base.resolve()
    out = base / 'report26/figures'
    out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(out / '.matplotlib_cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.lines import Line2D
    import pandas as pd

    receipt = json.loads((base / 'analysis_policy26/results/RECEIPT.json').read_text())
    assert receipt['completed'] and receipt['images'] == 157
    font = args.font or base / 'assets/NotoSansCJKsc-Regular.otf'
    if not font.exists():
        raise FileNotFoundError(f'Chinese plotting font missing: {font}; provide --font')
    font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({
        'font.family': font_manager.FontProperties(fname=str(font)).get_name(),
        'font.size': 12.5, 'axes.unicode_minus': False,
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'path',
    })
    src = base / 'analysis_policy26/results/POLICY_PRECISION_SUMMARY.csv'
    data = pd.read_csv(src)
    metrics = ['paired_Q_delta', 'QT_paired_Q_delta', 'labor_ratio_legal']
    data = data.loc[data.phase.eq('early_3_to_half') & data.difficulty.eq('全部')
                    & data.weighting.eq('image_equal') & data.metric.isin(metrics)].copy()
    assert len(data) == 36 and not data.duplicated(['policy', 'version', 'metric']).any()
    roles = [
        ('joint_highq_first', '联合高Q优先'),
        ('structure_moreturn_first', '较多转折优先'),
        ('joint_fast_first', '联合快速优先'),
        ('structure_dominant_first', '人数最多结构类优先'),
    ]
    versions = [
        ('old16', '旧16对', '#667583', 'o', .19),
        ('new16', '独立新16对', '#2677A2', 's', 0),
        ('pooled32', '合32对', '#167653', 'D', -.19),
    ]
    role_map = dict(roles)
    panel_map = dict(zip(metrics, ['A_all_quality', 'B_same_QT_quality', 'C_same_QT_labor']))
    data['role_zh'] = data.policy.map(role_map)
    data['figure_panel'] = data.metric.map(panel_map)
    data['source_commit'] = 'b9bcec809fbaec8ab055931a1abb7baa5db44dac'
    data['source_table'] = str(src.relative_to(base))
    for policy, _ in roles:
        q = data.loc[data.policy.eq(policy) & data.metric.eq(metrics[0])]
        assert q.images.eq(157).all() and q.buildings.eq(22).all()
        qt = data.loc[data.policy.eq(policy) & data.metric.eq(metrics[1])]
        t = data.loc[data.policy.eq(policy) & data.metric.eq(metrics[2])]
        assert qt.images.nunique() == qt.buildings.nunique() == 1
        assert qt.set_index('version').images.equals(t.set_index('version').images)
        assert qt.set_index('version').buildings.equals(t.set_index('version').buildings)

    fig = plt.figure(figsize=(17.8, 7.45), facecolor='white')
    axes = [fig.add_axes([.190, .285, .233, .455]),
            fig.add_axes([.471, .285, .233, .455]),
            fig.add_axes([.754, .285, .228, .455])]
    limits = [(-4.4, 10.0), (-5.2, 11.7), (.72, 1.255)]
    ticks = [[-4, 0, 4, 8], [-4, 0, 4, 8], [.8, 1.0, 1.2]]
    headings = ['A  平均Q：全部157图 / 22楼',
                'B  平均Q：合法Q/T共同支持',
                'C  劳动比：与B相同支持']
    for j, (ax, metric) in enumerate(zip(axes, metrics)):
        ax.set_xlim(*limits[j]); ax.set_ylim(-.52, 3.52)
        ax.set_xticks(ticks[j]); ax.set_yticks([])
        ax.spines[['top', 'left', 'right']].set_visible(False)
        ax.spines['bottom'].set_color('#A7B0B7')
        ax.tick_params(axis='x', length=0, pad=8, colors='#394A55')
        ax.grid(axis='x', color='#E7EBEE', lw=.7, zorder=0)
        baseline = 1 if j == 2 else 0
        ax.axvline(baseline, color='#6C777F', linestyle=(0, (3, 3)), lw=1.25, zorder=1)
        ax.set_title(headings[j], loc='left', pad=24, fontsize=13.3, fontweight='bold')
        for i, (policy, _) in enumerate(roles):
            y = 3 - i
            if i % 2 == 0:
                ax.axhspan(y-.43, y+.43, color='#F5F7F8', zorder=-1)
            for version, _, color, marker, off in versions:
                row = data.loc[data.policy.eq(policy) & data.version.eq(version) & data.metric.eq(metric)].iloc[0]
                value = float(row.estimate)
                ax.plot(value, y+off, marker=marker, ms=7.4 if version != 'pooled32' else 7.7,
                        color=color, markeredgecolor='white', markeredgewidth=.65, zorder=3)
                if version == 'pooled32':
                    label = f'{value:.4f}' if j == 2 else f'{value:+.3f}'
                    ax.annotate(label, (value, y+off), xytext=(8, 0), textcoords='offset points',
                                ha='left', va='center', fontsize=12, color=color, fontweight='bold')
        ax.set_xlabel('Q差（策略 − 同基准自然顺序）' if j < 2 else '劳动比（策略 / 同基准自然顺序）',
                      labelpad=14, fontsize=11.7)

    for i, (policy, label) in enumerate(roles):
        y = 3-i
        fy = fig.transFigure.inverted().transform(axes[0].transData.transform((0, y)))[1]
        q = data.loc[data.policy.eq(policy) & data.metric.eq(metrics[1])].iloc[0]
        fig.text(.022, fy+.012, label, ha='left', va='center', fontsize=13.5, color='#203641')
        fig.text(.022, fy-.026, f'B、C：{int(q.images)}图 / {int(q.buildings)}楼',
                 ha='left', va='center', fontsize=11.2, color='#5D6C75')

    fig.text(.022, .957, '历史进入策略：独立追加后的质量与劳动取舍', fontsize=20.5,
             fontweight='bold', color='#173542', ha='left', va='top')
    fig.text(.022, .896, '前段为3人至半池；三版本固定共同人数点，先逐图平均再图片等权。',
             fontsize=12.3, color='#455D69', ha='left', va='top')
    handles = [Line2D([0], [0], marker=m, color=c, linestyle='none', markersize=7.5, label=lab)
               for _, lab, c, m, _ in versions]
    fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.019, .858),
               ncol=3, frameon=False, fontsize=12, handletextpad=.5, columnspacing=1.9)
    fig.text(.985, .832, '绿色数字为合32估计', ha='right', va='center', fontsize=11.4, color='#167653')
    fig.text(.022, .168,
             'Q差以0为参照；劳动比以1为参照：小于1节时，大于1费时。B与C可联合解读，A与C不可混成同一支持。',
             fontsize=11.5, ha='left', va='top', color='#344F5E')
    fig.text(.022, .116,
             '劳动比是同来源完整活动时间的逐路径比值，经同k、同图分层平均；不是总劳动之和的比值、交付时间或金钱成本。',
             fontsize=11.0, ha='left', va='top', color='#506570')
    fig.text(.022, .067,
             '点为实际估计，图中不画区间；路径精度与建筑差异分别见配套表。沿用历史V3角色，并非DSTRUCT / RFUSE策略验证。',
             fontsize=11.0, ha='left', va='top', color='#506570')
    stem = 'P02_policy32_Q_labor_support'
    for ext in ['png', 'pdf', 'svg']:
        fig.savefig(out/f'{stem}.{ext}', dpi=190 if ext == 'png' else 160,
                    facecolor='white', bbox_inches='tight', pad_inches=.18)
    plt.close(fig)
    source = out/f'{stem}_SOURCE.csv'
    data.to_csv(source, index=False, lineterminator='\n')
    with source.open(encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))
    assert len(rows)-1 == 36 and all(len(r) == len(rows[0]) for r in rows)
    files = []
    for p in sorted(out.glob(stem+'.*')) + [source, Path(__file__).resolve()]:
        raw=p.read_bytes();files.append({'path':str(p.relative_to(base)), 'bytes':len(raw),
                                        'sha256':hashlib.sha256(raw).hexdigest()})
    (out/f'{stem}_MANIFEST.json').write_text(json.dumps({
        'source_commit':'b9bcec809fbaec8ab055931a1abb7baa5db44dac',
        'completed_policy_substudy_only':True, 'no_new_fusion':True,
        'no_new_resampling':True, 'no_new_model':True, 'source_rows':36,
        'CSV_read_to_EOF':True, 'files':files,
    },ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'figure':str(out/f'{stem}.png'),'source_rows':36,'outputs':len(files)},ensure_ascii=False))


if __name__ == '__main__':
    main()
