"""Render manuscript geometry and group-size figures from archived sources."""
from pathlib import Path
import gzip
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / 'docs/thesis_main/论文提纲_LaTeX_20261028'
OUT = PAPER / 'figures'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'pdf.fonttype': 42})


def geometry(points, flatten=False):
    p = np.asarray(points, float)
    radius = 1 / np.tan(np.pi * (p[1::2, 1] / 512 - .5))
    theta = 2 * np.pi * (p[::2, 0] / 1024 - .5)
    foot = np.c_[radius * np.sin(theta), -radius * np.cos(theta), -np.ones(len(radius))]
    top = foot.copy()
    top[:, 2] = radius * np.tan(np.pi * (.5 - p[::2, 1] / 512))
    if flatten:
        top[:, 2] = np.median(top[:, 2])
    return np.array([foot, top])


def shift(group, anchor, corner):
    # Explicit rear-left floor vertex, verified in the common camera view.
    origin = anchor[0, corner].copy()
    shifted = [g - origin for g in group]
    assert np.any(np.all(np.isclose(anchor[0] - origin, 0), axis=1))
    # A common translation preserves all annotation/reference offsets.
    for before, after in zip(group, shifted):
        assert np.allclose(before[1] - before[0], after[1] - after[0])
        assert np.allclose(np.diff(before, axis=1), np.diff(after, axis=1))
    for before, after in zip(group[1:], shifted[1:]):
        if before.shape == group[0].shape:
            assert np.allclose(before - group[0], after - shifted[0])
    return shifted, origin


def wire(ax, g, color, ls='-', lw=1.2):
    for ring in g:
        ring = np.vstack([ring, ring[0]])
        ax.plot(*ring.T, color=color, ls=ls, lw=lw)
    for a, b in zip(*g):
        ax.plot(*np.array([a, b]).T, color=color, ls=ls, lw=lw)


def frame(ax, group, step):
    pts = np.concatenate([g.reshape(-1, 3) for g in group])
    low = np.floor(np.minimum(pts.min(0), 0) / step) * step
    high = np.ceil(pts.max(0) / step) * step
    ticks = [np.arange(a, b + step / 2, step) for a, b in zip(low, high)]
    ax.set_proj_type('ortho')
    ax.patch.set_alpha(0)
    ax.view_init(elev=24, azim=-60)
    ax.grid(False)
    for k, axis in enumerate([ax.xaxis, ax.yaxis, ax.zaxis]):
        axis.set_pane_color((1, 1, 1, 0))
        axis.line.set_color((1, 1, 1, 0))
        getattr(ax, 'set_' + 'xyz'[k] + 'lim')(low[k] - step * .12, high[k] + step * .12)
        getattr(ax, 'set_' + 'xyz'[k] + 'ticks')([])
    # Grid lines lie on the coordinate planes, with the same unit spacing.
    for fixed in range(3):
        a, b = [k for k in range(3) if k != fixed]
        for direction, other in [(a, b), (b, a)]:
            for t in ticks[other]:
                ends = np.zeros((2, 3))
                ends[:, direction] = [low[direction], high[direction]]
                ends[:, other] = t
                ax.plot(*ends.T, color='#8c98a3', alpha=.19, lw=.3, zorder=0)
    for k in range(3):
        ends = np.zeros((2, 3))
        ends[:, k] = [low[k], high[k]]
        ax.plot(*ends.T, color='#646b73', lw=.65, alpha=.75)
        pos = np.zeros(3)
        # Horizontal z runs towards the viewer from the rear origin.
        pos[k] = (low[k] - 1.8 * step) if k == 1 else (high[k] + .45 * step)
        ax.text(*pos, ["$x'/h$", "$z'/h$", "$y'/h$"][k], fontsize=8, ha='center')
    ax.scatter([0], [0], [0], s=9, color='#343a40', depthshade=False)
    ax.text(-.18 * step, .08 * step, -.12 * step, 'O', fontsize=7, ha='right')
    ax.set_box_aspect(high - low + step * .24)



def save(fig, name):
    for suffix in ['pdf', 'png']:
        fig.savefig(OUT / f'{name}.{suffix}', dpi=240, bbox_inches='tight', pad_inches=.08)
    plt.close(fig)


def group_size_figure():
    import pandas as pd
    base = ROOT / 'research/workers/image_response_v21_20261101/HOHONET_v21_image_response_20261101'
    panel = 'ordinary_manual_main__capacity_ge30'
    curves = pd.read_csv(base / 'stage07_summary/manual/FIXED_PANEL_CURVES.csv.gz')
    curves = curves[curves.panel == panel]
    q = curves[(curves.stratum == 'all') & (curves.metric == 'B8L2_mean')].set_index('k').mean_image_equal
    assert abs(q[6] - q[3] - 4.7388816524) < 1e-8
    assert abs(q[30] - q[20] - .5001017822) < 1e-8
    members = pd.read_csv(base / 'stage07_summary/manual/FIXED_PANEL_MEMBERS.csv')
    members = members[members.panel == panel]
    assert members.image.nunique() == 171
    geom = pd.read_csv(base / 'stage04_geometry/ordinary_cached/GEOMETRY_U_CURVES.csv.gz', low_memory=False)
    geom = geom[(geom.pool_id.isin(members.pool_id)) & (geom.metric == 'V_floor') & (geom.k.between(3, 30))]
    assert not geom.duplicated(['pool_id', 'k']).any()
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 6.0))
    fig.subplots_adjust(left=.09, right=.985, top=.96, bottom=.08, hspace=.58, wspace=.30)
    groups = [('all', 'All (171 images)', '#34495e', '-'), ('Easy', 'Easy (116)', '#348abd', '--'), ('Medium', 'Moderate (28)', '#c78216', '-.'), ('Hard', 'Difficult (27)', '#b95174', ':')]
    for ax, metric, title, ylabel in zip(axes.flat, ['B8L2_mean','B8L2_p10','B8L2_sd','V_floor','complete_evaluable_rate'], ['(a) Mean quality','(b) Lower-tail quality','(c) Variation across teams','(d) Floor-layout diversity','(e) Complete and evaluable outputs'], ['Mean Q','Mean image-specific P10 Q','Mean within-image SD of Q','Mean pairwise 1 - IoU','Complete and evaluable (%)']):
        for key, label, color, ls in groups:
            if metric == 'V_floor':
                d = geom if key == 'all' else geom[geom.difficulty_en == key]
                y = d.groupby(['image','k'])['mean'].mean().groupby('k').mean()
            else:
                d = curves[(curves.stratum == key) & (curves.metric == metric)].sort_values('k')
                y = d.set_index('k').mean_image_equal
            assert y.index.is_unique and len(y) == 28 and np.isfinite(y).all()
            if metric == 'complete_evaluable_rate':
                assert y.between(0, 1).all()
                assert (d.valid_path_rows == d.capacity_images * 256).all()
                if key == 'all':
                    assert np.isclose(100 * (y[6] - y[3]), -1.857, atol=.0005)
                    assert np.isclose(100 * (y[30] - y[20]), .420, atol=.0005)
                y = y * 100
            ax.plot(y.index, y.values, color=color, ls=ls, lw=1.15, label=label)
        for start, end in [(3, 6), (20, 30)]:
            ax.axvspan(start, end, color='#536879', alpha=.065, lw=0, zorder=0)
        ax.set_title(title, fontsize=8, loc='left')
        ax.set_xlabel('Annotators', fontsize=8); ax.set_ylabel(ylabel, fontsize=8)
        ax.set_xlim(3,30); ax.set_xticks([3,6,10,15,20,25,30])
        ax.tick_params(labelsize=7, width=.5, length=2)
        ax.grid(alpha=.16, lw=.3); ax.spines[['top','right']].set_visible(False)
    axes[2, 1].axis('off')
    axes[2, 1].legend(*axes[0,0].get_legend_handles_labels(), loc='upper left', frameon=False, fontsize=8, borderaxespad=0)
    axes[2, 1].text(0, .26, 'Same 171 images at every group size\n256 entry orders per image\n43,776 attempts per size in panel (e)\nShaded ranges: 3–6 and 20–30 annotators',
                    transform=axes[2, 1].transAxes, fontsize=7.5, va='top', linespacing=1.45)
    save(fig, 'group_size_171')


def main():
    snapshot = json.loads((ROOT / 'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json').read_text(encoding='utf8'))
    pool = next(p for p in snapshot['images'] if p['meta']['image'] == '7y3sRwLe3Va-11' and p['meta']['condition'] == 'manual')
    originals = [geometry(next(r['points'] for r in pool['records'] if r['worker'] == w), True) for w in ['W028', 'W032']]
    assert [g.shape[1] for g in originals] == [4, 8]
    layouts = [shift([g], g, 0)[0][0] for g in originals]
    fig = plt.figure(figsize=(7.2, 3.5))
    ax = fig.add_axes([.005, .33, .30, .4])
    ax.imshow(Image.open(ROOT / 'data/mp3d_layout/test/img/7y3sRwLe3Va_606f9842b8af48daa28f10df8b69d861.png'))
    ax.axis('off'); ax.set_title('(a) Panorama', fontsize=8)
    for x, g, color, name in zip([.33, .66], layouts, ['#bf5b00', '#007f8b'], ['(b) A18: 4 corners', '(c) A22: 8 corners']):
        ax = fig.add_axes([x+.02, .64, .26, .30])
        ring = np.vstack([g[0], g[0, 0]])
        ax.plot(ring[:, 0], ring[:, 1], '-o', color=color, lw=1.5, ms=2.5)
        ax.set_aspect('equal'); ax.set_xlim(-1, 5); ax.set_ylim(-4, 1)
        ax.set_xticks(range(-1, 6)); ax.set_yticks(range(-4, 2)); ax.grid(alpha=.19, lw=.3)
        ax.set_xlabel("$x'/h$", labelpad=0); ax.set_ylabel("$z'/h$", labelpad=0)
        ax.tick_params(labelsize=7, pad=1); ax.set_title(name, fontsize=8)
        ax = fig.add_axes([x-.025, .005, .35, .55], projection='3d')
        frame(ax, layouts, 1); wire(ax, g, color)
    save(fig, 'individual_fireplace')

    tracepath = ROOT / 'research/workers/personnel_v21_reselection_20261029/stage06_cases/traces_semantic/ae9bc0bdaf9a5f2119cea910.json.gz'
    with gzip.open(tracepath, 'rt', encoding='utf8') as f:
        trace = json.load(f)
    ref = geometry(trace['reference']['points_1024x512'], True)
    teams = []
    for arm in ['B', 'C']:
        cand = trace['arms'][arm]['full_state']['candidate']
        g = geometry(cand['points'], True)
        g[:, :, :2] = np.array(cand['footprint'])
        teams.append(g)
    shifted, origin = shift([ref] + teams, ref, 4)
    # Preserve the existing annotated panorama panel; regenerate only the geometry.
    panel = Image.open(OUT / 'bathroom_observations_panel.png').convert('RGB')
    fig = plt.figure(figsize=(7.2, 2.65))
    ax = fig.add_axes([0, .21, .39, .69]); ax.imshow(panel); ax.axis('off')
    fig.text(.195, .955, '(a) Local observations', ha='center', fontsize=8)
    for x, g, color, title, desc in zip([.39, .695], shifted[1:], ['#009688', '#e76520'], ['(b) Team 1 (10 people)', '(c) Team 2 (10 people)'], ['4 and 2 votes: neither turn retained', '8 and 8 votes: both turns retained']):
        ax = fig.add_axes([x-.01, .21, .315, .72], projection='3d')
        frame(ax, shifted, .5); wire(ax, shifted[0], '#515962', '--', .8); wire(ax, g, color)
        ax.set_title(title, fontsize=8, pad=0)
        fig.text(x+.14, .14, desc, fontsize=7, ha='center')
    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([], [], color='#555', lw=1.2, label='Team layout'), Line2D([], [], color='#515962', ls='--', lw=.8, label='Reference')], loc='lower center', ncol=2, frameon=False, fontsize=8)
    save(fig, 'bathroom_turn_votes')

    d = json.loads((ROOT / 'research/quality/quality_pro_return_review_20261014/evidence/J04_interventions.json').read_text(encoding='utf8'))
    ref = geometry(d['reference_points'])
    layouts, origin = shift([geometry(d['original_points']), ref], ref, 2)

    fig = plt.figure(figsize=(7.2, 2.8))
    ax = fig.add_axes([.035, .23, .52, .60])
    photo = Image.open(ROOT / 'data/mp3d_layout/test/img/yqstnuAEVhm_2b3fb4746d414cc6a31729b222ed79b2.png')
    ax.imshow(photo, extent=[0, 1024, 512, 0])
    # Project the same 3D edges used in the right panel onto the panorama.
    for points, color, ls in [(d['original_points'], '#2587bd', '-'), (d['reference_points'], '#515962', '--')]:
        g = geometry(points)
        for ring in g:
            for v, w in zip(ring, np.roll(ring, -1, axis=0)):
                xyz = np.linspace(v, w, 150)
                u = (np.arctan2(xyz[:, 0], -xyz[:, 1]) / (2*np.pi) + .5) * 1024
                v = (.5 - np.arctan2(xyz[:, 2], np.hypot(xyz[:, 0], xyz[:, 1])) / np.pi) * 512
                u[np.r_[False, np.abs(np.diff(u)) > 512]] = np.nan
                ax.plot(u, v, color=color, ls=ls, lw=.85)
        p = np.asarray(points)
        for i in range(0, len(p), 2): ax.plot(p[i:i+2, 0], p[i:i+2, 1], color=color, ls=ls, lw=.85)
    ax.set_xlim(0,1024); ax.set_ylim(512,0)
    ax.set_xticks([0,256,512,768,1024]); ax.set_yticks([0,256,512])
    ax.tick_params(labelsize=7, pad=1)
    ax.set_xlabel('Horizontal pixel', fontsize=8, labelpad=1)
    ax.set_ylabel('Vertical pixel', fontsize=8, labelpad=1)
    ax.set_title('(a) Panorama overlay', fontsize=8)
    ax = fig.add_axes([.58, .13, .42, .82], projection='3d')
    frame(ax, layouts, 1)
    for g, color, ls in zip(layouts, ['#2587bd', '#515962'], ['-', '--']): wire(ax, g, color, ls)
    camera = -origin
    ax.scatter(*camera, marker='*', color='#2587bd', s=35, label='Camera')
    ax.plot([], [], [], color='#2587bd', label='R03274'); ax.plot([], [], [], color='#515962', ls='--', label='Reference')
    fig.legend(*ax.get_legend_handles_labels(), loc='lower center', ncol=3, fontsize=8, frameon=False)
    ax.set_title('(b) Layout comparison', fontsize=8, pad=0)
    save(fig, 'observed_corner_geometry')
    group_size_figure()
    print('Rendered 4 figures. Origin, corner counts and translation invariance verified.')


if __name__ == '__main__':
    main()

