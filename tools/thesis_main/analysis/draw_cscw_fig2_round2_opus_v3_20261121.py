"""CSCW Figure 2, round-2 Opus candidate v3 (2026-11-21).

Priorities from the author's 2026-11-21 brief:
1. Semi vs Manual readable without the words: two identical "screen as opened" frames,
   one with a supplied layout drawn on it, one with the photo only.
2. Person <-> tool: click endpoints, the tool renders that person's own 3D layout, revise.
3. Researcher <-> methods: researchers pick one panorama's submissions and decide what is
   kept and what is swapped; consensus and Q then run on the teams they built.
The fireplace stays in Fig. 1. Every geometric element is a vector artist (3D preview included);
only the two panoramas are embedded rasters, each a separate replaceable image.
Data: Semi Z6MFQCViBuw-10 (A3 unchanged, A2 duplicate removed); Manual and teams from
jtcxE69GiFV-13, the published matched-replacement event (3 kept members, 7 swapped; Figs. 5, 8).
"""
from pathlib import Path
import gzip
import json
import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle, Circle
import matplotlib.patheffects as pe
from PIL import Image
from shapely.geometry import Polygon as SPoly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draw_cscw_fig2_round2_opus_20261121 as v1
from draw_cscw_fig2_round2_opus_20261121 import (text, box, arrow, image_ax, pairs, recon, to_pano, footprint,
                                                edge_samples, INK, MUTED, REF, SEMI, EXTRA, BLUE, ORANGE,
                                                PANO_SEMI, PANO_BATH, CONS)

ROOT = v1.ROOT
TRACE = ROOT / 'docs/thesis_main/论文提纲_LaTeX_20261028/editorial_tools/figure_inputs/bathroom_team_trace.json.gz'
IDMAP = ROOT / 'docs/thesis_main/论文提纲_LaTeX_20261028/annotator_id_mapping.csv'
OUT = v1.WORK / 'CSCW图2 候选' / 'CSCW图2第二轮_Opus第三版_20261121'
W, H = 139.7, 151.0
MAN = '#3b4a8c'                     # Manual drawing colour (one person's own clicks)
REC = '#e07b22'                     # recess corners A, B
GOLD, GOLDD, GOLD_BG = '#c9962b', '#8a6412', '#fbf6ea'
KEEP, OUT_C, IN_C = '#7d8a93', '#6a8caf', '#c4652a'   # kept members / Team 1 others / Team 2 others
GREEN = '#11866a'
DUP = '#c0398a'                     # Semi duplicate pair (distinct from recess orange)
plt.rcParams.update(v1.STYLE)
from draw_cscw_fig2_round2_opus_v2_20261121 import person_icon, cursor, badge


def paper_ids():
    rows = [l.split(',') for l in IDMAP.read_text(encoding='utf-8').splitlines()[1:] if l]
    return {r[0]: r[1] for r in rows}


def load_teams():
    case = json.loads(CONS.read_text(encoding='utf-8'))
    ev = json.load(gzip.open(TRACE, 'rt', encoding='utf8'))['event']
    kept, t1_new, t2_new = (ev[k].split('|') for k in ('D', 'Y', 'Z'))
    t1 = {p['person']: p for p in case['teams']['Team 1']['people']}
    t2 = {p['person']: p for p in case['teams']['Team 2']['people']}
    assert set(t1) == set(kept) | set(t1_new) and set(t2) == set(kept) | set(t2_new)
    assert ev['source_class'] == 'C2' and ev['target_class'] == 'C3' and len(kept) == 3 and int(ev['pool_n']) == 35
    return case, ev, kept, t1_new, t2_new, t1, t2


def window(cv, x, y, w, h, photo, xlim, ylim, gid, label=None):
    """Identical tool chrome for every screen: title bar + one replaceable panorama image."""
    bg = cv.bg
    box(bg, x, y, w, h + 2.4, fc='white', ec='#8f9ba3', lw=.5, r=.6, gid=f'{gid}_chrome', z=2)
    bg.add_patch(Rectangle((x + .25, y + .25), w - .5, 1.95, fc='#e7ebee', ec='none', zorder=3))
    for k in range(3):
        bg.add_patch(Circle((x + 1.3 + 1.2 * k, y + 1.2), .38, fc='#b7c0c6', ec='none', zorder=4))
    if label:
        text(bg, x + w - 1.0, y + .35, label, 5.0, MUTED, ha='right', zorder=4)
    return image_ax(cv, x + .35, y + 2.4, w - .7, h - .35, photo, [0, 1024, 512, 0], xlim, ylim, f'{gid}_image')


def preview3d(a, pts, accent=(), accent_walls=(), phi=32, elev=24, col='#5f7f99'):
    """Vector cut-away of one person's own layout: floor, back walls filled, front walls outlined."""
    x, z, top = recon(pts)
    f, e = np.radians(phi), np.radians(elev)
    p0 = -x * np.sin(f) + z * np.cos(f)
    depth = x * np.cos(f) + z * np.sin(f)
    sy = lambda d, y: d * np.sin(e) + y * np.cos(e)
    n = len(x)
    area = sum(x[i] * z[(i + 1) % n] - x[(i + 1) % n] * z[i] for i in range(n))
    a.add_patch(Polygon(np.c_[p0, sy(depth, -1)], closed=True, fc='#eef1f3', ec=col, lw=.5, zorder=1))
    walls = []
    for i in range(n):
        j = (i + 1) % n
        dx, dz = x[j] - x[i], z[j] - z[i]
        nx, nz = (dz, -dx) if area > 0 else (-dz, dx)
        back = nx * np.cos(f) + nz * np.sin(f) > 0
        quad = [(p0[i], sy(depth[i], -1)), (p0[j], sy(depth[j], -1)), (p0[j], sy(depth[j], top[j])), (p0[i], sy(depth[i], top[i]))]
        walls.append((-(depth[i] + depth[j]), back, quad))
    walls = [w for w in walls]
    for k, (_, back, quad) in sorted(enumerate(walls), key=lambda t: t[1][0]):
        if k in accent_walls:
            a.add_patch(Polygon(quad, closed=True, fc=REC, ec=REC, lw=.5, zorder=2.5, alpha=.55))
        elif back:
            a.add_patch(Polygon(quad, closed=True, fc='#d9e3ea', ec=col, lw=.55, zorder=2, alpha=.95))
        else:
            q = np.array(quad)
            a.plot(q[[0, 1], 0], q[[0, 1], 1], color=col, lw=.5, zorder=4)
            a.plot(q[[3, 2], 0], q[[3, 2], 1], color=col, lw=.4, ls=(0, (2, 1.2)), zorder=4)
    for i in range(n):
        c, lw = (REC, 1.6) if i in accent else (col, .55)
        a.plot([p0[i]] * 2, [sy(depth[i], -1), sy(depth[i], top[i])], color=c, lw=lw, zorder=5 if i in accent else 3)
    a.set_aspect('equal'); a.axis('off')
    return p0, depth, sy


# ---------------------------------------------------------------- row 1: individual annotation
SCR_W, SCR_H = 44.0, 22.0          # screen image, 2:1 panorama
TOP_Y = 16.0                        # chrome top of the two "as opened" screens
SEMI_X, MAN_X = 2.0, 52.0
HALO = [pe.withStroke(linewidth=2.0, foreground='white', alpha=.85)]


def draw_layout_on(a, pts, col, lw=1.1):
    n = len(pts) // 2
    for xs, zs, ys in edge_samples(pts, [(i, (i + 1) % n) for i in range(n)]):
        for yy in (ys, np.full_like(xs, -1.)):
            u, v = to_pano(xs, yy, zs)
            br = np.where(np.abs(np.diff(u)) > 500)[0] + 1
            for uu, vv in zip(np.split(u, br), np.split(v, br)):
                a.plot(uu, vv, color=col, lw=lw, zorder=4, path_effects=HALO)


def column_head(bg, x, title, sub, col):
    person_icon(bg, x + 1.6, 14.0, .72, INK)
    text(bg, x + 3.8, 8.6, title, 6.6, col, weight='bold')
    text(bg, x + 3.8, 11.7, sub, 5.8, INK)


def semi_column(cv):
    from render_semi_case_20261107 import load_case, UNCHANGED, EDITED
    plt.rcParams.update(v1.STYLE)
    initial, finals, _ = load_case()
    assert finals[UNCHANGED]['paper_id'] == 'A3' and finals[EDITED]['paper_id'] == 'A2'
    bg = cv.bg
    column_head(bg, SEMI_X, 'Semi  (first phase)', 'The screen opens with a supplied layout', SEMI)
    photo = Image.open(PANO_SEMI); assert photo.size == (2048, 1024)
    a = window(cv, SEMI_X, TOP_Y, SCR_W, SCR_H, photo, (0, 1024), (512, 0), 'semi_open', 'Z6MFQCViBuw-10')
    draw_layout_on(a, initial, SEMI)
    p = pairs(initial)
    for k, ((ut, vt), (ub, vb)) in enumerate(p):
        a.scatter([ut, ub], [vt, vb], s=9, c=DUP if k == 2 else SEMI, edgecolors='white', linewidths=.5, zorder=6)
    CU, CV = (336, 396), (132, 178)
    a.add_patch(Rectangle((CU[0], CV[0]), CU[1] - CU[0], CV[1] - CV[0], fill=False, ec='white', lw=.8, zorder=7))
    arrow(bg, (SEMI_X + 6, 40.9), (SEMI_X + 6, 45.6), color=INK, lw=.8, ms=4.5)
    text(bg, SEMI_X + 7.4, 41.4, 'check the given corners; keep or edit', 5.5, INK)
    for k, (oid, title) in enumerate([(UNCHANGED, 'A3 kept it as given'), (EDITED, 'A2 removed the duplicate')]):
        x0 = SEMI_X + k * 22.6
        b = image_ax(cv, x0, 46.2, 21.4, 14.4, photo, [0, 1024, 512, 0], CU, CV[::-1], f'semi_{finals[oid]["paper_id"]}')
        for ut, vt in pairs(finals[oid]['points'])[:, 0]:
            b.scatter([ut], [vt], s=20, c=DUP if np.isclose(ut, p[2, 0, 0]) else SEMI,
                      edgecolors='white', linewidths=.6, zorder=6)
        text(bg, x0, 61.3, title, 5.6, INK, weight='bold')


MANUAL_WHO = 'W109'     # A37: Team 2 member whose drawing has the reference's 6 turns
RECESS = (1, 2)         # W109 pair indices for recess turns A and B


def manual_column(cv, t2, ids):
    bg = cv.bg
    pts = t2[MANUAL_WHO]['points']
    pid = ids[MANUAL_WHO]
    column_head(bg, MAN_X, 'Manual  (later, other panoramas)', 'The screen opens with the photo only', MAN)
    photo = Image.open(PANO_BATH); assert photo.size == (2048, 1024)
    window(cv, MAN_X, TOP_Y, SCR_W, SCR_H, photo, (0, 1024), (512, 0), 'manual_open', 'jtcxE69GiFV-13')
    arrow(bg, (MAN_X + 6, 40.9), (MAN_X + 6, 45.6), color=INK, lw=.8, ms=4.5)
    text(bg, MAN_X + 7.4, 41.4, 'choose each turn; click its upper and lower end', 5.5, INK)
    a = window(cv, MAN_X, 45.6, 24.0, 12.0, photo, (0, 1024), (512, 0), 'manual_clicked')
    p = pairs(pts)
    for k, ((ut, vt), (ub, vb)) in enumerate(p):
        c = REC if k in RECESS else MAN
        a.plot([ut, ub], [vt, vb], color=c, lw=.9, zorder=5, path_effects=HALO)
        a.scatter([ut, ub], [vt, vb], s=8, c=c, edgecolors='white', linewidths=.4, zorder=6)
    (ut, vt), _ = p[RECESS[0]]
    cursor(a, ut + 6, vt + 6, 3.4)
    text(bg, MAN_X, 61.5, f'{pid}: 6 turns; A, B = recess', 5.4, MUTED)
    # tool response: this person's own layout in 3D
    arrow(bg, (MAN_X + 24.4, 50.4), (MAN_X + 30.6, 50.4), color=BLUE, lw=.9, ms=4.5)
    box(bg, MAN_X + 30.8, 44.6, 20.6, 18.6, fc='#f6f8fa', ec='#b8c6d0', lw=.5, gid='manual_preview_frame')
    text(bg, MAN_X + 31.8, 45.4, 'tool: own 3D preview', 5.4, BLUE, weight='bold')
    pa = cv.ax(MAN_X + 31.2, 47.8, 19.8, 15.0, 'manual_preview_vector')
    p0, depth, sy = preview3d(pa, pts, accent=RECESS, accent_walls=(RECESS[0],), phi=300, elev=65)
    x, z, top = recon(pts)
    pa.text(p0[RECESS[1]] + .06, sy(depth[RECESS[1]], top[RECESS[1]]) + .05, 'A,B', fontsize=5.0, color=REC,
            fontweight='bold', ha='left', va='bottom')
    arrow(bg, (MAN_X + 30.6, 55.2), (MAN_X + 24.4, 55.2), color=MAN, lw=.9, ms=4.5)
    text(bg, MAN_X + 27.5, 55.9, 'revise', 5.2, MAN, weight='bold', ha='center')
    return pts


OTH_X = 107.6
OTHERS = ['W002', 'W102', 'W126']    # further Team 2 members: 6, 4 and 6 turns


def others_column(cv, t2, ids):
    """The same panorama drawn by other people, each alone; their clicks never meet in the tool."""
    bg = cv.bg
    text(bg, OTH_X, 8.6, 'Others, same panorama', 6.2, INK, weight='bold')
    text(bg, OTH_X, 11.7, 'each alone, unseen', 5.6, INK)
    photo = Image.open(PANO_BATH)
    for k, who in enumerate(OTHERS):
        y = TOP_Y + k * 15.6
        person_icon(bg, OTH_X + 1.4, y + 6.4, .62, INK)
        p = pairs(t2[who]['points'])
        a = window(cv, OTH_X + 3.4, y, 26.4, 12.0, photo, (0, 1024), (512, 0), f'other_{ids[who]}',
                   f'{ids[who]}: {len(p)} turns')
        for (ut, vt), (ub, vb) in p:
            rec = 660 < ut < 712
            c = REC if rec else MAN
            a.plot([ut, ub], [vt, vb], color=c, lw=.8, zorder=5, path_effects=HALO)
            a.scatter([ut, ub], [vt, vb], s=5, c=c, edgecolors='white', linewidths=.3, zorder=6)
        if k < 2:
            bg.plot([OTH_X, W - 1.2], [y + 15.1, y + 15.1], color='#c9d2d8', lw=.6)


# ---------------------------------------------------------------- boundary + row 2: researchers
BOUND_Y = 67.0
Y2 = BOUND_Y + 7.0       # top of the offline content


def boundary(cv):
    bg = cv.bg
    box(bg, 0, BOUND_Y, W, H - BOUND_Y, fc=GOLD_BG, ec='none', r=0, gid='band_offline', z=0)
    bg.plot([0, W], [BOUND_Y, BOUND_Y], color=GOLD, lw=1.2, zorder=1)
    for x in (SEMI_X + 22, MAN_X + 13, OTH_X + 15):
        arrow(bg, (x, 64.2), (x, BOUND_Y + .5), color=INK, lw=.9, ms=5, z=6)
    text(bg, MAN_X + 14.2, 64.1, 'submit', 5.4, INK)
    text(bg, SEMI_X + 23.2, 64.1, 'submit', 5.4, INK)
    text(bg, 2.0, BOUND_Y + 1.6, 'After submission: researchers, offline', 6.6, GOLDD, weight='bold')
    text(bg, 47.5, BOUND_Y + 1.85, 'Drawings of one panorama first meet here. No result goes back to annotators.', 5.4, MUTED)


def person_row(ax, x, y, colors, s=.62, dx=2.15):
    for k, c in enumerate(colors):
        person_icon(ax, x + k * dx, y, s, c)


def step_label(bg, x, y, n, title, sub):
    badge(bg, x + 1.3, y + 1.4, n, GOLDD, r=1.3)
    text(bg, x + 3.4, y + .1, title, 6.0, GOLDD, weight='bold')
    if sub:
        text(bg, x + 3.4, y + 3.0, sub, 5.3, INK)


def design_block(cv, ev):
    """Researchers' choice for one comparison: the published RQ3 swap on jtcxE69GiFV-13."""
    bg = cv.bg
    step_label(bg, 2.0, Y2, 1, 'Researchers form teams', 'they choose what stays fixed')
    text(bg, 2.4, Y2 + 7.6, f'All {ev["pool_n"]} Manual drawings of the panorama', 5.3, MUTED)
    for k in range(35):
        r, c = divmod(k, 12)
        col = KEEP if k < 3 else (OUT_C if k < 10 else (IN_C if k < 17 else '#d6dade'))
        bg.add_patch(Rectangle((2.6 + c * 2.55, Y2 + 10.4 + r * 2.4), 1.8, 1.7, fc=col, ec='none', zorder=4))
    for row, (lab, col) in enumerate([('Team 1', OUT_C), ('Team 2', IN_C)]):
        y = Y2 + 25.6 + row * 6.4
        text(bg, 2.4, y - 2.4, lab, 5.6, col, weight='bold')
        person_row(bg, 12.4, y, [KEEP] * 3)
        person_row(bg, 20.0, y, [col] * 7)
    bg.add_patch(FancyBboxPatch((11.0, Y2 + 20.8), 6.6, 12.4, boxstyle='round,pad=0,rounding_size=.8',
                                fill=False, ec=INK, lw=.6, ls=(0, (2, 1)), zorder=5))
    text(bg, 14.3, Y2 + 33.8, 'same 3', 5.3, INK, ha='center', weight='bold')
    text(bg, 27.0, Y2 + 33.8, '7 swapped: typical →\nturn-retaining profile', 5.3, INK, ha='center')


def plan_ax(cv, x, y, w, h, gid):
    a = cv.ax(x, y, w, h, gid)
    a.set(xlim=(-.55, .86), ylim=(-1.02, .74)); a.set_aspect('equal'); a.axis('off')
    return a


def consensus_block(cv, case, t1, t2):
    bg = cv.bg
    X0 = 40.0
    arrow(bg, (36.4, Y2 + 28.6), (X0 + .2, Y2 + 28.6), color=GOLDD, lw=.9, ms=5)
    step_label(bg, X0, Y2, 2, 'Paired-corner structural consensus', None)
    text(bg, X0 + 3.4, Y2 + 3.0, 'match corner pairs across drawings; keep a turn if ≥ half the team\n'
         'marked it; set its upper and lower ends at the supporters’ medians', 5.3, INK)
    sup = {(t, tr['label']): tr['support'] for t, d in case['teams'].items() for tr in d['turns']}
    for row, (team, people, col) in enumerate([('Team 1', t1, OUT_C), ('Team 2', t2, IN_C)]):
        y = Y2 + 10.2 + row * 17.2
        a = plan_ax(cv, X0 + .6, y, 15.2, 15.2, f'consensus_{team.replace(" ", "")}_inputs')
        for p in people.values():
            a.add_patch(Polygon(footprint(p['points']), closed=True, fill=False, ec=col, lw=.45, alpha=.6))
        if row == 0:
            text(bg, X0 + 8.2, y - 2.6, 'each team: 10 own outlines', 5.0, MUTED, ha='center')
        arrow(bg, (X0 + 16.4, y + 7.6), (X0 + 20.2, y + 7.6), color=INK, lw=.7, ms=4)
        for k, lab in enumerate('AB'):
            s = sup[(team, lab)]
            yy = y + 4.0 + k * 5.0
            text(bg, X0 + 20.8, yy - 1.0, lab, 5.6, REC, weight='bold')
            for j in range(10):
                bg.add_patch(Circle((X0 + 23.6 + j * 1.45, yy), .56, fc=col if j < s else '#e1e5e8', ec='none', zorder=4))
            bg.plot([X0 + 23.6 + 4.5 * 1.45 + .72] * 2, [yy - 1.4, yy + 1.4], color=ORANGE, lw=.7, zorder=5)
        text(bg, X0 + 20.8, y + 11.4, 'supporters (line: 5 needed)', 5.0, MUTED)
        arrow(bg, (X0 + 38.4, y + 7.6), (X0 + 42.2, y + 7.6), color=INK, lw=.7, ms=4)
        a = plan_ax(cv, X0 + 42.4, y, 15.2, 15.2, f'consensus_{team.replace(" ", "")}_layout')
        f = footprint(case['teams'][team]['candidate']['points'])
        a.add_patch(Polygon(f, closed=True, fc=GREEN, alpha=.10, ec='none'))
        a.add_patch(Polygon(f, closed=True, fill=False, ec=GREEN, lw=1.1))
        kept = all(sup[(team, l)] >= 5 for l in 'AB')
        text(bg, X0 + 50.0, y + 15.0, 'recess kept' if kept else 'recess dropped', 5.4,
             GREEN if kept else INK, weight='bold', ha='center')


def q_block(cv, case):
    bg = cv.bg
    X0 = 104.2
    arrow(bg, (X0 - 6.0, Y2 + 28.6), (X0 - .2, Y2 + 28.6), color=GOLDD, lw=.9, ms=5)
    step_label(bg, X0 - 1.0, Y2, 3, 'Geometric quality Q', None)
    text(bg, X0 + 2.4, Y2 + 3.0, 'measure how far a team\nlayout (or one drawing)\nis from the reference', 5.3, INK)
    ref = footprint(case['reference']); sref = SPoly(ref)
    for row, team in enumerate(['Team 1', 'Team 2']):
        y = Y2 + 10.2 + row * 17.2
        a = plan_ax(cv, X0, y, 15.2, 15.2, f'q_{team.replace(" ", "")}')
        f = footprint(case['teams'][team]['candidate']['points'])
        diff = sref.symmetric_difference(SPoly(f))
        for g in getattr(diff, 'geoms', [diff]):
            if g.area > 1e-4:
                a.add_patch(Polygon(np.asarray(g.exterior.coords), fc=BLUE, alpha=.38, ec='none'))
        a.add_patch(Polygon(ref, closed=True, fill=False, ec=REF, lw=.75, ls=(0, (3, 1.6))))
        a.add_patch(Polygon(f, closed=True, fill=False, ec=GREEN, lw=.9))
    text(bg, X0 + 16.2, Y2 + 13.0, 'dashed:\nreference', 5.2, MUTED)
    text(bg, X0 + 16.2, Y2 + 20.0, 'blue: floor\nmissed or\nadded', 5.2, BLUE)
    text(bg, X0 + 16.2, Y2 + 31.0, 'also: wall\ndirection,\nheights', 5.2, MUTED)


# ---------------------------------------------------------------- row 3: one split per RQ
RQ_Y = Y2 + 53.4
RQS = [('RQ1', 'Compare people', 'one panorama', 'the person; in Semi, also\ngiven vs submitted'),
       ('RQ2', 'Add people', 'panorama, person pool', 'team size, 3 to 30'),
       ('RQ3', 'Swap members', 'panorama, kept members', 'who fills the other seats'),
       ('RQ4', 'Change viewpoint', 'room; person or members', 'camera position')]


def rq_icons(bg, x, y, k):
    if k == 0:
        for j, c in enumerate([MAN, '#8a6bb0', '#5a9a8c']):
            person_icon(bg, x + 2.4 + j * 5.6, y + 5.0, .8, c)
            bg.add_patch(Rectangle((x + 1.2 + j * 5.6, y + 6.2), 2.4, 1.7, fill=False, ec=c, lw=.55))
    elif k == 1:
        tones = ['#24313a'] * 3 + ['#5b7f99'] * 3 + ['#a8bccb'] * 3
        for j, c in enumerate(tones):
            person_icon(bg, x + 1.4 + j * 2.35, y + 5.6, .6, c)
        bg.add_patch(FancyBboxPatch((x - .1, y + 1.9), 7.1, 4.6, boxstyle='round,pad=0,rounding_size=.7', fill=False, ec=INK, lw=.6))
        bg.add_patch(FancyBboxPatch((x - .5, y + 1.5), 14.6, 5.4, boxstyle='round,pad=0,rounding_size=.9', fill=False, ec='#5b7f99', lw=.6, ls=(0, (2, 1))))
        text(bg, x + 3.5, y + 7.3, '3', 5.0, INK, weight='bold', ha='center')
        text(bg, x + 10.6, y + 7.3, '6', 5.0, '#5b7f99', weight='bold', ha='center')
        text(bg, x + 19.6, y + 7.3, '… 30', 5.0, MUTED, ha='center')
    elif k == 2:
        for r, c in enumerate([OUT_C, IN_C]):
            person_row(bg, x + 1.2, y + 3.4 + r * 4.4, [KEEP] * 3, .6)
            person_row(bg, x + 9.2, y + 3.4 + r * 4.4, [c] * 3, .6)
        arrow(bg, (x + 17.4, y + 2.0), (x + 17.4, y + 6.6), color=MUTED, lw=.6, ms=3.5)
    else:
        bg.add_patch(Polygon([(x + 1, y + .4), (x + 1, y + 7.8), (x + 18, y + 7.8), (x + 18, y + 3.6),
                              (x + 13, y + 3.6), (x + 13, y + .4)], fill=False, ec=INK, lw=.7))
        for cx, cy in [(x + 5.5, y + 4.4), (x + 15.4, y + 5.9)]:
            bg.add_patch(Circle((cx, cy), .75, fc=GOLDD, ec='white', lw=.4, zorder=5))
        arrow(bg, (x + 6.4, y + 4.6), (x + 14.6, y + 5.8), color=GOLDD, lw=.6, ms=3.5, rad=-.3)


def rq_row(cv):
    bg = cv.bg
    step_label(bg, 2.0, RQ_Y - 5.6, 4, 'Same submissions, four ways to split them: one per research question', None)
    w, gap = (W - 4 - 3 * 1.4) / 4, 1.4
    for k, (rq, verb, same, varies) in enumerate(RQS):
        x0 = 2.0 + k * (w + gap)
        box(bg, x0, RQ_Y, w, H - RQ_Y - 1.6, fc='white', ec='#c9d2d8', gid=f'{rq.lower()}_card')
        text(bg, x0 + 1.2, RQ_Y + 1.0, rq, 6.0, BLUE, weight='bold')
        text(bg, x0 + 7.6, RQ_Y + 1.0, verb, 6.0, INK, weight='bold')
        rq_icons(bg, x0 + 3.0, RQ_Y + 3.4, k)
        text(bg, x0 + 1.2, RQ_Y + 13.0, 'same', 5.2, GREEN, weight='bold')
        text(bg, x0 + 8.4, RQ_Y + 13.0, same, 5.2, INK)
        text(bg, x0 + 1.2, RQ_Y + 15.9, 'varies', 5.2, ORANGE, weight='bold')
        text(bg, x0 + 8.4, RQ_Y + 15.9, varies, 5.2, INK)


def _ax(cv, x, y, w, h, gid, z=10):
    a = cv.fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H], zorder=z)
    a.set_gid(gid)
    return a


class Canvas:
    def __init__(self):
        self.fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        self.bg = self.fig.add_axes([0, 0, 1, 1], zorder=0)
        self.bg.set(xlim=(0, W), ylim=(H, 0)); self.bg.axis('off'); self.bg.patch.set_alpha(0)
        self.bg.set_gid('background')

    def ax(self, x, y, w, h, gid, z=10):
        return _ax(self, x, y, w, h, gid, z)


def save(cv):
    OUT.mkdir(parents=True, exist_ok=True)
    stem = OUT / 'Figure2_candidate_Opus_v3'
    for ext, kw in [('svg', {'dpi': 600}), ('pdf', {'dpi': 600}), ('png', {'dpi': 400})]:
        cv.fig.savefig(stem.with_suffix('.' + ext), **kw)
    plt.close(cv.fig)
    return stem


def main():
    case, ev, kept, _, _, t1, t2 = load_teams()
    ids = paper_ids()
    cv = Canvas()
    text(cv.bg, 2.0, 2.0, 'Before submission: each annotator works alone in the annotation tool', 6.6, INK, weight='bold')
    semi_column(cv)
    cv.bg.plot([49.6, 49.6], [7.5, 62.5], color='#c9d2d8', lw=.6, ls=(0, (2, 1.5)))
    manual_column(cv, t2, ids)
    others_column(cv, t2, ids)
    boundary(cv)
    design_block(cv, ev)
    consensus_block(cv, case, t1, t2)
    q_block(cv, case)
    rq_row(cv)
    print(save(cv))


if __name__ == '__main__':
    main()
