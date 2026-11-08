"""Draw the archived AC09 localization case without fusion or geometry edits."""
from pathlib import Path
import copy
import gzip
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from render_manuscript_3d import geometry

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'research/workers/current_dstruct_ac_final_20261104/mechanisms/cases/AC09.json.gz'
OUT = ROOT / 'docs/thesis_main/论文提纲_LaTeX_20261028/figures'
WORK = ROOT / 'docs/thesis_main/论文写作工作资料'
COLORS = {'A': '#437b97', 'C': '#26847b', 'R': '#6c7379', 'D': '#9a9da1'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
                    'axes.titlesize': 8.5, 'axes.labelsize': 8,
                    'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5,
                    'pdf.fonttype': 42, 'axes.linewidth': .6})


def load_and_check():
    with gzip.open(SOURCE, 'rt', encoding='utf-8') as f:
        case = json.load(f)
    event, arms = case['event'], case['arms']
    assert event['n'] == 20 and event['m'] == 7
    common = set(event['D_workers'].split('|'))
    assert len(common) == 13
    assert set(arms['A']['member_workers']) & set(arms['C']['member_workers']) == common
    records = {r['id']: r for r in case['pool']['records']}
    # Equal local names alone do not establish identities across the two teams.
    for link in case['D_anchor_links']:
        assert link['link_type'] == 'exact_same_nonempty_D_observations'
        assert link['common_D_observations'] == 13
        anchors = []
        for side in ['A', 'C']:
            arm = arms[side]
            group = next(g for g in arm['full_state']['identity_groups']
                         if g['feature_id'] == link[side + '_group'])
            assert group['selected'] and group['support'] == 20
            assert arm['minimum_support'] == 10
            for obs in group['members']:
                raw_pair = records[obs['id']]['points'][2*obs['pair_index']:2*obs['pair_index']+2]
                assert np.array_equal(obs['points'], raw_pair)
            anchors.append({(o['id'], o['pair_index']) for o in group['members'] if o['worker'] in common})
        assert anchors[0] == anchors[1] == {tuple(p) for p in json.loads(link['D_observation_keys_json'])}
    identity_map = {r['A_group']: r['C_group'] for r in case['D_anchor_links']}
    order_a = arms['A']['geometry']['feature_ids']
    order_c = arms['C']['geometry']['feature_ids']
    assert [identity_map[n] for n in order_a] == order_c
    for side, arm in arms.items():
        assert arm['nodes'] == 4 and arm['node_supports'] == [20, 20, 20, 20]
        np.testing.assert_allclose(geometry(arm['geometry']['points'])[0, :, :2],
                                   arm['geometry']['footprint'], atol=1e-12)
        assert np.isclose(arm['B8L2'], case['current_metrics'][side + '_B8L2'])
    return case


def axes_style(ax):
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(length=2, pad=2)
    ax.grid(color='#9aa5af', alpha=.19, lw=.35)
    ax.set_axisbelow(True)


def draw_ring(ax, footprint, color, ls='-', lw=1.1):
    points = np.asarray(footprint)
    ax.plot(*points[[0, 1, 2, 3, 0]].T, color=color, ls=ls, lw=lw)


def main():
    case = load_and_check()
    unchanged = copy.deepcopy(case)
    arms = case['arms']
    ref = np.asarray(case['reference']['floor_xz_h'])
    footprints = {s: np.asarray(a['geometry']['footprint']) for s, a in arms.items()}
    centers = {s: np.asarray(a['geometry']['points'])[7] for s, a in arms.items()}
    reference_points = np.asarray(case['reference']['points_1024x512'])
    reference_index = np.argmin(np.linalg.norm(ref - footprints['A'][3], axis=1))
    ref_center = reference_points[2*reference_index+1]
    fig = plt.figure(figsize=(7.2, 4.8))

    # Full outputs share the archived camera-height-normalized coordinate system.
    ax = fig.add_axes([.08, .68, .87, .22])
    axes_style(ax)
    draw_ring(ax, ref, COLORS['R'], (0, (4, 2)), .9)
    for side, foot in footprints.items():
        draw_ring(ax, foot, COLORS[side])
        ax.scatter(*foot.T, s=13, color=COLORS[side], zorder=5)
    for i, p in enumerate(footprints['A']):
        ax.annotate(str(i+1), p, xytext=(0, -11 if i in [0, 3] else 6),
                    textcoords='offset points', ha='center', fontsize=7.5)
    ax.scatter([0], [0], marker='^', s=23, c='#30363b', zorder=7)
    ax.add_patch(Rectangle((-5.88, -.66), .58, 1.18, fill=False, ec='#555e65', lw=.6, ls=':'))
    ax.set(xlim=(-6, 1.75), ylim=(-.85, .8), aspect='equal', xlabel='$x/h$', ylabel='$z/h$')
    ax.set_title('(a) Four selected corners; 20 supporters per corner in both teams', loc='left', pad=8)

    ax = fig.add_axes([.09, .15, .25, .37])
    axes_style(ax)
    common = set(case['event']['D_workers'].split('|'))
    raws = {}
    for side, arm in arms.items():
        group = next(g for g in arm['full_state']['identity_groups'] if g['feature_id'] == 'node_003')
        raws[side] = {o['worker']: np.asarray(o['points'])[1] for o in group['members']}
    samples = [('D', [raws['A'][w] for w in sorted(common)], 'o'),
               ('A', [v for w, v in raws['A'].items() if w not in common], 's'),
               ('C', [v for w, v in raws['C'].items() if w not in common], '^')]
    for side, points, marker in samples:
        xy = np.asarray(points)
        ax.scatter(*xy.T, s=17, marker=marker, c=COLORS[side], alpha=.75, linewidths=.35, edgecolors='white')
    for side, marker in [('A', 's'), ('C', 'D')]:
        ax.scatter(*centers[side], s=55, marker=marker, c=COLORS[side], edgecolors='black', lw=.6, zorder=8)
    ax.scatter(*ref_center, marker='+', color=COLORS['R'], s=60, linewidths=1.1, zorder=7)
    points = np.array([v for group in raws.values() for v in group.values()])
    ax.set(xlim=(points[:, 0].min()-1, points[:, 0].max()+1),
           ylim=(points[:, 1].max()+2, points[:, 1].min()-2),
           xlabel='Panorama $u$ (px)', ylabel='Panorama $v$ (px)')
    ax.set_title('(b) Original observations\nat corner 4', loc='left', pad=8)

    ax = fig.add_axes([.43, .15, .17, .37])
    axes_style(ax)
    draw_ring(ax, ref, COLORS['R'], (0, (4, 2)), .9)
    for side, foot in footprints.items():
        draw_ring(ax, foot, COLORS[side], lw=1.2)
        ax.scatter(*foot[[2, 3]].T, color=COLORS[side], s=22, zorder=6)
    ax.set(xlim=(-5.88, -5.30), ylim=(-.66, .52), aspect='equal', xlabel='$x/h$', ylabel='$z/h$')
    ax.set_xticks([-5.8, -5.5])
    ax.set_title('(c) Far-end footprint\n(detail from a)', loc='left', pad=8)

    ax = fig.add_axes([.68, .15, .30, .37]); ax.axis('off')
    ax.set_title('(d) Whole-layout measures', loc='left', pad=8)
    metrics = case['current_metrics']
    rows = [('Quality Q', 'B8L2', 2), ('Floor IoU', 'iou_2d', 3),
            ('Boundary error (°)', 'S_bottom_deg', 3), ('Direction error (°)', 'dir', 3),
            ('Global height error', 'Hmean', 4), ('Local height error', 'Hcenter', 4)]
    values = [[label] + [f'{metrics[s+"_"+key]:.{nd}f}' for s in ['A', 'C']] for label, key, nd in rows]
    table = ax.table(cellText=values, colLabels=['Measure', 'Before', 'After'],
                     colWidths=[.56, .22, .22], bbox=[0, .08, 1, .88], cellLoc='left')
    table.auto_set_font_size(False); table.set_fontsize(7.5)
    for (r, c), cell in table.get_celld().items():
        cell.visible_edges = 'B' if r == 0 else ''
        cell.set_linewidth(.6); cell.set_edgecolor('#8c969e'); cell.PAD=.04
        if c in [1, 2]:
            cell.get_text().set_color(COLORS['A' if c == 1 else 'C'])
            cell.get_text().set_ha('right')
        if r == 1: cell.get_text().set_weight('bold')

    first = [Line2D([], [], color=COLORS['A'], lw=1.2, label='Before: 13 retained + 7 typical-expression'),
             Line2D([], [], color=COLORS['C'], lw=1.2, label='After: same 13 + 7 more turn-retaining'),
             Line2D([], [], color=COLORS['R'], ls='--', lw=.9, label='Reference')]
    fig.legend(handles=first, loc='upper center', bbox_to_anchor=(.51, 1.02), ncol=2,
               frameon=False, fontsize=7.3, columnspacing=1.7, handlelength=2)
    raw = [Line2D([], [], ls='', marker='o', color=COLORS['D'], markersize=4, label='13 retained observations'),
           Line2D([], [], ls='', marker='s', color=COLORS['A'], markersize=4, label='7 outgoing observations'),
           Line2D([], [], ls='', marker='^', color=COLORS['C'], markersize=4, label='7 incoming observations')]
    fig.legend(handles=raw, loc='lower center', bbox_to_anchor=(.5, .012), ncol=3,
               frameon=False, fontsize=7.3, columnspacing=1.2, handletextpad=.5)
    assert case == unchanged
    for ext in ['pdf', 'png']:
        fig.savefig(OUT/f'localization_mechanism.{ext}', dpi=300, bbox_inches='tight', pad_inches=.06)
    plt.close(fig)
    audit = {'case_id': 'AC09', 'image': case['event']['image'], 'source': str(SOURCE.relative_to(ROOT)),
             'event_id': case['event']['event_id'], 'n': 20, 'm': 7, 'retained_members': 13,
             'stable_identity_anchor_observations_per_node': 13,
             'selected_nodes': 4, 'support_per_node_both_arms': 20, 'threshold': 10,
             'mapped_ring_order_equal': True, 'reference_version': case['event']['reference_version'],
             'raw_point_arrays_equal_to_pool_records': True, 'case_unchanged_after_plotting': case == unchanged,
             'projected_footprints_equal_saved': True,
             'A_points': arms['A']['geometry']['points'], 'C_points': arms['C']['geometry']['points'],
             'A_footprint': arms['A']['geometry']['footprint'], 'C_footprint': arms['C']['geometry']['footprint'],
             'A_Q': metrics['A_B8L2'], 'C_Q': metrics['C_B8L2'],
             'endpoint_status': {s: a['score_status'] for s, a in arms.items()},
             'automatic_ring_status': {s: a['geometry']['order_status'] for s, a in arms.items()},
             'case_selection': 'Post-outcome diagnostic selection; not a prevalence estimate.',
             'new_fusion_runs': 0, 'new_scoring_runs': 0}
    (WORK/'定位机制图来源核对_20261107.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: audit[k] for k in ['case_id','A_Q','C_Q','mapped_ring_order_equal','case_unchanged_after_plotting']}, indent=2))


if __name__ == '__main__':
    main()
