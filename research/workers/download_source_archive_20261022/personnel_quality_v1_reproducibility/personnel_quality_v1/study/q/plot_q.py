#!/usr/bin/env python3
"""Standalone scientific figures from frozen personnel outputs (no fitting)."""
import argparse
import os
from pathlib import Path
import tempfile

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'personnel_q_matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
        'axes.spines.right': False, 'axes.labelsize': 11, 'axes.titlesize': 13,
        'savefig.dpi': 180, 'pdf.fonttype': 42, 'svg.fonttype': 'none'})


def main(args):
    source = Path(args.input); out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(source / 'worker_profiles_enriched.csv')
    q = d[d.axis.eq('B8L2')].set_index('worker_id')
    style()
    fig, ax = plt.subplots(figsize=(9, 6.5), constrained_layout=True)
    ax.axhspan(-2, 2, color='#dfe5eb', alpha=.5, zorder=0)
    ax.axhline(0, lw=.8, color='#666666')
    x = np.linspace(53, 87, 100)
    ax.plot(x, x-q.common_task_intercept.iloc[0], '--', color='#9b9b9b', lw=1,
        label='Common task baseline + personnel effect')
    ax.errorbar(q['mean'], q.effect,
        yerr=np.vstack([q.effect-q.effect_ci95_low, q.effect_ci95_high-q.effect]),
        fmt='none', ecolor='#9ca5ad', alpha=.55, elinewidth=.8, capsize=2, zorder=1)
    sc = ax.scatter(q['mean'], q.effect, c=q.actual_task_intercept_mean, cmap='viridis',
        s=58, edgecolor='white', linewidth=.6, zorder=3, vmin=64, vmax=69)
    offsets = {'W027': (7, 3), 'W002': (7, 2), 'W018': (6, 7), 'W015': (5, -16),
        'W013': (-33, 5), 'W031': (5, -17), 'W017': (6, 7), 'W014': (-32, -16),
        'W012': (6, 8), 'W037': (-18, -18), 'W001': (-34, -16)}
    for w, off in offsets.items():
        r = q.loc[w]
        ax.annotate(w, (r['mean'], r.effect), xytext=off, textcoords='offset points',
            fontsize=9, color='#263238', arrowprops={'arrowstyle': '-', 'color': '#9aa0a6', 'lw': .5})
    cb = fig.colorbar(sc, ax=ax, fraction=.047, pad=.025)
    cb.set_label('Mean fitted task baseline in each worker\'s observed assignment')
    ax.set(xlim=(53, 87), ylim=(-18, 34), xlabel='Observed ordinary Manual mean (B8L2 points)',
        ylabel='Task-adjusted personnel effect (B8L2 points)',
        title='Absolute output and relative performance answer different questions')
    ax.legend(frameon=False, loc='upper left', fontsize=9)
    ax.text(.02, .90, '24 workers | 1,048 records | 87 exact task contexts | 19 buildings',
        transform=ax.transAxes, va='top', fontsize=9, color='#555555')
    ax.text(.02, .025, 'Bars: 95% building bootstrap intervals (2,000 draws).\nShading: prespecified ±2-point diagnostic band, not an acceptance threshold.',
        transform=ax.transAxes, va='bottom', fontsize=8.5, color='#555555')
    for ext in ['png', 'svg']: fig.savefig(out / ('absolute_vs_relative_quality.'+ext), bbox_inches='tight')
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 7))
    fig.subplots_adjust(left=.11, right=.98, bottom=.19, top=.90)
    t = q[q.T_supported.eq(True)]
    ax.axvspan(-2, 2, color='#dfe5eb', alpha=.5, zorder=0)
    ax.axvline(0, color='#666666', lw=.8); ax.axhline(0, color='#666666', lw=.8)
    ax.scatter(t.effect, t.T_effect, s=65, c=np.where(t.effect > 0, '#147d80', '#bd633e'), edgecolor='white', linewidth=.6, zorder=3)
    offsets = {w: (6, 4) for w in t.index}
    offsets.update({'W011': (-32, 9), 'W029': (-37, 8), 'W030': (7, -15), 'W035': (9, -6),
        'W008': (7, 7), 'W015': (7, -14), 'W010': (-37, -6), 'W001': (-33, -12),
        'W017': (10, 9), 'W033': (6, 6), 'W037': (6, 6), 'W028': (-37, -13), 'W006': (-36, -9)})
    for w, r in t.iterrows():
        ax.annotate(w, (r.effect, r.T_effect), xytext=offsets[w], textcoords='offset points', fontsize=9,
            arrowprops={'arrowstyle': '-', 'color': '#afb4b9', 'lw': .5})
    ax.text(.03, .95, 'Lower relative Q / slower', transform=ax.transAxes, fontsize=10, color='#6d6d6d')
    ax.text(.64, .95, 'Higher relative Q / slower', transform=ax.transAxes, fontsize=10, color='#6d6d6d')
    ax.text(.03, .08, 'Lower relative Q / faster', transform=ax.transAxes, fontsize=10, color='#6d6d6d')
    ax.text(.64, .08, 'Higher relative Q / faster', transform=ax.transAxes, fontsize=10, color='#6d6d6d')
    ax.set(xlim=(-15, 24), ylim=(-1.7, 2.23), xlabel='Task-adjusted personnel quality effect (B8L2 points)',
        ylabel='Task-adjusted time effect [log(1 + active seconds)]',
        title='Quality and efficiency: full-data descriptive Q × T classes')
    fig.text(.11, .035, '21 workers with supported time effects; W014 has no T training data, W018 and W034 lack task support.\nW011 crosses the time zero line in 9/20 leave-building-out folds. Faster is an efficiency label, not a quality judgment.', fontsize=9, color='#555555')
    for ext in ['png', 'svg']: fig.savefig(out / ('quality_time_profile.'+ext), bbox_inches='tight')
    plt.close(fig)
    print('Saved absolute_vs_relative_quality and quality_time_profile as PNG + SVG.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default=str(Path(__file__).resolve().parent))
    parser.add_argument('--out', default=str(Path(__file__).resolve().parent))
    main(parser.parse_args())
