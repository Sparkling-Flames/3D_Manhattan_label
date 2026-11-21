"""CSCW Figure 2 round-2 independent candidate (Opus), 2026-11-21.

Draws one editable overview figure from original study assets only:
- Semi: Z6MFQCViBuw-10 supplied layout, A3 unchanged / A2 duplicate removed
  (loaded through render_semi_case_20261107.load_case, which asserts raw provenance).
- Manual: 7y3sRwLe3Va-19 fireplace, A29 (W101, 4 pairs) and A59 (W131, 8 pairs),
  original clicks, original Blender response renders and the stored Q values.
- Consensus: jtcxE69GiFV-13, the two published 10-person teams (supports 4/2 and 8/8).
Outputs SVG (text kept as text), vector PDF and a PNG preview. No score or team is recomputed.
"""
from pathlib import Path
import json
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon, Rectangle, Circle
from PIL import Image
from scipy.spatial.transform import Rotation
from shapely.geometry import Polygon as SPoly

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
WORK = ROOT / 'docs/thesis_main/论文写作工作资料'
F6 = WORK / 'Dot交付审查_20261106/Paper_Figures_4_5_6_10_CURRENT_ONLY_20261106/02_Figure6_latest'
CONS = ROOT / 'docs/thesis_main/论文提纲_LaTeX_20261028/figure_package/source/consensus_actual/data/consensus_case.json'
PANO_FIRE = F6 / 'inputs/7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f.png'
PANO_SEMI = ROOT / 'data/mp3d_layout/test/img/Z6MFQCViBuw_fbef2c9afec642c88d01cf09c90aec12.png'
PANO_BATH = ROOT / 'data/mp3d_layout/valid/img/jtcxE69GiFV_5d3af9ad575b4be88587967ff8114c36.png'
RENDERS = {'A29': F6 / 'output/renders/Fig6_4_corners_complete_walls.png',
           'A59': F6 / 'output/renders/Fig6_8_corners_complete_walls.png'}
PROJ = F6 / 'output/fig6_complete_walls_projection.json'
OUT = WORK / 'CSCW图2 候选' / 'CSCW图2第二轮_Opus独立候选_20261121'

W, H = 139.7, 169.5  # mm; CSCW (acmsmall) text width is 5.5 in
INK, MUTED, REF = '#24313a', '#5d6a73', '#5f6b73'
C29, C59 = '#168c87', '#df732f'          # Figure 1 colours
SEMI, EXTRA = '#007d91', '#d16a24'       # Semi case colours
FIRE = '#7a3fa0'                         # fireplace wall marker
BLUE, ORANGE = '#0072B2', '#D55E00'      # Figure 5 clicks / consensus endpoints
BAND1, BAND2 = '#eef3f6', '#f5f2ea'
STYLE = {'font.family': 'Arial', 'font.size': 6.5, 'pdf.fonttype': 42,
         'svg.fonttype': 'none', 'axes.linewidth': .5, 'savefig.facecolor': 'white'}
plt.rcParams.update(STYLE)


# ---------------------------------------------------------------- geometry
def pairs(points):
    """1024x512 click list -> (n, 2, 2) upper/lower pairs aligned to the shorter-arc midpoint."""
    p = np.asarray(points, float).reshape(-1, 2, 2).copy()
    du = (p[:, 1, 0] - p[:, 0, 0] + 512) % 1024 - 512
    p[:, :, 0] = ((p[:, 0, 0] + du / 2) % 1024)[:, None]
    return p


def recon(points):
    """Floor y = -1 (camera-height units). Returns floor x, z and upper-corner height y."""
    p = pairs(points)
    az = 2 * np.pi * (p[:, 0, 0] / 1024 - .5)
    el = np.pi * (.5 - p[:, :, 1] / 512)
    r = -1 / np.tan(el[:, 1])
    return r * np.sin(az), -r * np.cos(az), r * np.tan(el[:, 0])


def to_pano(x, y, z):
    az = np.arctan2(x, -z)
    el = np.arctan2(y, np.hypot(x, z))
    return (az / (2 * np.pi) + .5) * 1024, (.5 - el / np.pi) * 512


def edge_samples(points, edges, n=60):
    """Upper/lower 3D samples along the listed ring edges (heights interpolated linearly)."""
    x, z, top = recon(points)
    out = []
    for i, j in edges:
        t = np.linspace(0, 1, n)
        xs, zs = x[i] + t * (x[j] - x[i]), z[i] + t * (z[j] - z[i])
        out.append((xs, zs, top[i] + t * (top[j] - top[i])))
    return out


def footprint(points):
    x, z, _ = recon(points)
    poly = SPoly(np.c_[x, z])
    assert poly.is_valid and poly.area > 0, 'ring order must give a simple floor polygon'
    return np.c_[x, z]


def load_fireplace():
    src = json.loads((F6 / 'inputs/fig6_geometry_inputs.json').read_text(encoding='utf-8'))
    ref, a29, a59 = src['cases']
    assert ref['label'] == 'GT' and a29['record']['worker'] == 'W101' and a59['record']['worker'] == 'W131'
    assert len(a29['record']['points']) == 8 and len(a59['record']['points']) == 16
    return {'REF': ref['reference']['points_1024x512'],
            'A29': a29['record']['points'], 'A59': a59['record']['points'],
            'Q': {'A29': a29['Q'], 'A59': a59['Q']}}


# ---------------------------------------------------------------- canvas (mm, origin top-left)
class Canvas:
    def __init__(self):
        self.fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        self.bg = self._overlay('background', 0)
        self.fg = None

    def _overlay(self, gid, z):
        ax = self.fig.add_axes([0, 0, 1, 1], zorder=z)
        ax.set(xlim=(0, W), ylim=(H, 0)); ax.axis('off'); ax.set_gid(gid)
        ax.patch.set_alpha(0)
        return ax

    def top(self):
        if self.fg is None:
            self.fg = self._overlay('annotations', 50)
        return self.fg

    def ax(self, x, y, w, h, gid, z=10):
        a = self.fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H], zorder=z)
        a.set_gid(gid)
        return a


def text(ax, x, y, s, size=6.5, color=INK, weight='normal', ha='left', va='top', gid=None, **kw):
    t = ax.text(x, y, s, fontsize=size, color=color, fontweight=weight, ha=ha, va=va,
                linespacing=1.18, **kw)
    if gid:
        t.set_gid(gid)
    return t


def box(ax, x, y, w, h, fc='white', ec='#c3ccd2', lw=.5, r=1.2, gid=None, z=1):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={r}',
                       fc=fc, ec=ec, lw=lw, zorder=z)
    if gid:
        p.set_gid(gid)
    ax.add_patch(p)
    return p


def arrow(ax, a, b, color=INK, lw=.8, rad=0., style='-|>', ms=5, ls='-', gid=None, z=5):
    p = FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=ms, color=color, lw=lw,
                        connectionstyle=f'arc3,rad={rad}', linestyle=ls, zorder=z,
                        shrinkA=0, shrinkB=0)
    if gid:
        p.set_gid(gid)
    ax.add_patch(p)
    return p


def step(ax, x, y, n, label, color=INK, size=7.2, num_color='white'):
    ax.add_patch(Circle((x + 1.8, y + 1.8), 1.8, fc=color, ec='none', zorder=6))
    text(ax, x + 1.8, y + 1.85, str(n), size=6.4, color=num_color, weight='bold', ha='center',
         va='center', zorder=7)
    if label:
        text(ax, x + 4.6, y + .3, label, size=size, weight='bold', color=color)


def image_ax(cv, x, y, w, h, img, extent, xlim, ylim, gid):
    a = cv.ax(x, y, w, h, gid)
    a.imshow(img, extent=extent, interpolation='lanczos')
    a.set(xlim=xlim, ylim=ylim); a.set_xticks([]); a.set_yticks([])
    for s in a.spines.values():
        s.set_color('#9aa6ae'); s.set_linewidth(.4)
    return a


# ---------------------------------------------------------------- band 1: individual work
def draw_dots(a, pts, color, s=9, lw_pair=.5, alpha_pair=.75, z=6):
    p = pairs(pts)
    for (ut, vt), (ub, vb) in p:
        a.plot([ut, ub], [vt, vb], color=color, lw=lw_pair, alpha=alpha_pair, zorder=z - 1)
    a.scatter(p[:, :, 0].ravel(), p[:, :, 1].ravel(), s=s, c=color, edgecolors='white',
              linewidths=.45, zorder=z)


def semi_panel(cv):
    from render_semi_case_20261107 import load_case, UNCHANGED, EDITED
    plt.rcParams.update(STYLE)   # the imported module sets its own font
    initial, finals, _ = load_case()
    assert finals[UNCHANGED]['paper_id'] == 'A3' and finals[EDITED]['paper_id'] == 'A2'
    bg = cv.bg
    box(bg, 2, 7, 44, 65, gid='semi_card')
    text(bg, 3.5, 8.3, 'Semi: supplied layout', 6.9, weight='bold')
    text(bg, 3.5, 11.6, 'First phase: keep or edit given corner pairs', 6.0, MUTED)
    text(bg, 3.5, 14.4, 'Panorama Z6MFQCViBuw-10', 5.4, MUTED)
    photo = Image.open(PANO_SEMI); assert photo.size == (2048, 1024)
    a = image_ax(cv, 3.5, 18, 41, 20.5, photo, [0, 1024, 512, 0], (0, 1024), (512, 0), 'semi_supplied_layout')
    ring = [(i, (i + 1) % 5) for i in range(5)]
    for xs, zs, ys in edge_samples(initial, ring):
        for yy in (ys, np.full_like(xs, -1.)):
            u, v = to_pano(xs, yy, zs)
            br = np.where(np.abs(np.diff(u)) > 500)[0] + 1      # split at the panorama seam
            for uu, vv in zip(np.split(u, br), np.split(v, br)):
                a.plot(uu, vv, color=SEMI, lw=.7, zorder=4)
    p = pairs(initial)
    for k, ((ut, vt), (ub, vb)) in enumerate(p):
        c = EXTRA if k == 2 else SEMI
        a.scatter([ut, ub], [vt, vb], s=10, c=c, edgecolors='white', linewidths=.45, zorder=6)
    CU, CV = (336, 396), (132, 178)
    a.add_patch(Rectangle((CU[0], CV[0]), CU[1] - CU[0], CV[1] - CV[0], fill=False, ec='white', lw=.7, zorder=7))
    text(bg, 3.5, 39.4, '5 supplied corner pairs; 2 nearly coincide', 5.7, INK)
    text(bg, 3.5, 42.1, '(orange = duplicate pair; box enlarged below)', 5.4, MUTED)
    for k, (oid, title, note) in enumerate([(UNCHANGED, 'A3: unchanged', '5 pairs; duplicate kept'),
                                            (EDITED, 'A2: duplicate removed', '4 pairs; rest untouched')]):
        x0 = 3.5 + k * 21.0
        b = image_ax(cv, x0, 46.5, 19.5, 15, photo, [0, 1024, 512, 0], CU, CV[::-1], f'semi_{finals[oid]["paper_id"]}')
        q = pairs(finals[oid]['points'])
        for ut, vt in q[:, 0]:
            c = EXTRA if np.isclose(ut, p[2, 0, 0]) else SEMI
            b.scatter([ut], [vt], s=22, c=c, edgecolors='white', linewidths=.6, zorder=6)
        text(bg, x0, 62.3, title, 5.7, INK, weight='bold')
        text(bg, x0, 65.1, note, 5.5, MUTED)
    text(bg, 3.5, 68.2, 'Ceiling endpoints shown; floor endpoints alike', 5.5, MUTED)


def render_px(name, xs, ys, zs):
    """Project layout coordinates into the stored orthographic Blender camera (Blender = x, z, y)."""
    cam = json.loads(PROJ.read_text(encoding='utf-8'))[name]
    c, w, h = cam['camera'], cam['width'], cam['height']
    q = c['rotation']
    R = Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_matrix()
    P = np.c_[xs, zs, ys] - np.asarray(c['location'])
    cc = P @ R
    return w / 2 + cc[:, 0] / c['ortho_scale'] * w, h / 2 - cc[:, 1] / c['ortho_scale'] * w


def load_renders(aspect):
    ims = {k: np.asarray(Image.open(v).convert('RGBA')) for k, v in RENDERS.items()}
    boxes = [Image.fromarray(im[:, :, 3]).getbbox() for im in ims.values()]
    x0, y0 = min(b[0] for b in boxes) - 25, min(b[1] for b in boxes) - 25
    x1, y1 = max(b[2] for b in boxes) + 25, max(b[3] for b in boxes) + 25
    cx, cy, bw, bh = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    bw, bh = max(bw, bh * aspect), max(bh, bw / aspect)
    lim = (cx - bw / 2, cx + bw / 2), (cy + bh / 2, cy - bh / 2)
    out = {}
    for k, im in ims.items():
        a = im[:, :, 3:4] / 255.
        out[k] = (im[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)
    return out, lim


FIRE_EDGES = {'A29': [(1, 2)], 'A59': [(0, 1), (1, 2), (2, 3)], 'REF': [(0, 1), (1, 2), (2, 3)]}
FIRE_U = (384, 638)   # A59's two outer fireplace corners on the panorama


def fire_segments(points, who):
    """Fireplace part of the wall: whole traced protrusion, or the bridged span inside FIRE_U."""
    segs = []
    for xs, zs, ys in edge_samples(points, FIRE_EDGES[who], 200):
        if who == 'A29':
            u, _ = to_pano(xs, ys, zs)
            keep = (u >= FIRE_U[0]) & (u <= FIRE_U[1])
            xs, zs, ys = xs[keep], zs[keep], ys[keep]
        segs.append((xs, zs, ys))
    return segs


def manual_panel(cv, fp):
    bg = cv.bg
    box(bg, 48, 7, 89.7, 65, gid='manual_card')
    text(bg, 49.5, 8.3, 'Manual: start from an empty layout', 6.9, weight='bold')
    text(bg, 49.5, 11.6, 'Click the upper and lower end of each wall corner, check the 3D preview, revise, submit',
         6.0, MUTED)
    text(bg, 49.5, 14.4, 'Later phase, other panoramas. Shown: 7y3sRwLe3Va-19, two annotators working alone', 5.4, MUTED)
    text(bg, 50, 18.0, 'Own clicks on the panorama', 5.8, INK, weight='bold')
    text(bg, 88.5, 18.0, 'Own 3D preview from the tool', 5.8, INK, weight='bold')
    photo = Image.open(PANO_FIRE); assert photo.size == (2048, 1024)
    PW, PH, RW = 28.2, 21.6, 25.5
    renders, (rx, ry) = load_renders(RW / PH)
    rows = [('A29', C29, 'A29', ['4 corner pairs;', 'one straight wall', 'across the fireplace']),
            ('A59', C59, 'A59', ['8 corner pairs;', 'wall turns around', 'both fireplace sides'])]
    for k, (who, col, label, lines) in enumerate(rows):
        y = 21.2 + k * 25.2
        a = image_ax(cv, 50, y, PW, PH, photo, [0, 1024, 512, 0], (300, 730), (430, 100), f'manual_{who}_clicks')
        draw_dots(a, fp[who], col, s=11)
        a.annotate('', xy=(FIRE_U[0], 124), xytext=(FIRE_U[1], 124),
                   arrowprops=dict(arrowstyle='|-|,widthA=.25,widthB=.25', color=FIRE, lw=.8))
        a.text(sum(FIRE_U) / 2, 121.0, 'fireplace', color=FIRE, fontsize=5.5, ha='center', va='bottom')
        r = image_ax(cv, 88.5, y, RW, PH, renders[who], None, rx, ry, f'manual_{who}_preview')
        r.images[0].set_extent([0, renders[who].shape[1], renders[who].shape[0], 0]); r.set(xlim=rx, ylim=ry)
        for s in r.spines.values():
            s.set_color('#d5dbdf')
        for xs, zs, ys in fire_segments(fp[who], who):
            px, py = render_px(f'Fig6_{"4" if who == "A29" else "8"}_corners_complete_walls', xs, ys, zs)
            r.plot(px, py, color=FIRE, lw=2.2, alpha=.85, solid_capstyle='round', zorder=6)
        arrow(bg, (79.8, y + 7.5), (87.8, y + 7.5), color=INK, lw=.7)
        text(bg, 83.8, y + 6.6, 'renders', 5.5, MUTED, ha='center', va='bottom')
        arrow(bg, (87.8, y + 14.0), (79.8, y + 14.0), color=col, lw=.7, rad=-.45)
        text(bg, 83.8, y + 16.9, 'revise', 5.5, col, ha='center')
        text(bg, 115.8, y + 1.0, label, 7.0, col, weight='bold')
        text(bg, 115.8, y + 4.5, '\n'.join(lines), 5.6, INK)


# ---------------------------------------------------------------- hand-over and band 2: offline methods
def handover(cv):
    bg = cv.bg
    for x in (24, 92.8):
        arrow(bg, (x, 72.2), (x, 76.6), color=INK, lw=.9)
    text(bg, 26, 73.0, 'independent submission', 5.4, MUTED)
    text(bg, 94.8, 73.0, 'independent submissions', 5.4, MUTED)
    box(bg, 2, 77, W - 4, 8.2, fc=INK, ec=INK, r=1.2, gid='first_meeting')
    step(bg, 3.4, 79.3, 2, '', color='white', num_color=INK)
    text(bg, 8.4, 78.6, 'Submissions first meet here: researchers group the submissions of one panorama into teams offline',
         6.4, 'white', weight='bold')
    text(bg, 8.4, 81.9, 'Annotators never see one another\u2019s drawings or any team layout; the team layout exists only in the analysis.',
         5.6, '#d9e2e7')


def q_panel(cv, fp):
    bg = cv.bg
    box(bg, 2, 93, 47, 41, gid='q_card')
    text(bg, 3.5, 94.3, 'Geometric quality Q', 6.9, BLUE, weight='bold')
    text(bg, 3.5, 97.6, 'Compares one layout, individual or team,\nwith the assigned reference', 5.9, INK)
    ref = footprint(fp['REF']); sref = SPoly(ref)
    for k, who in enumerate(['A29', 'A59']):
        col = C29 if who == 'A29' else C59
        a = cv.ax(4.5 + k * 22.8, 103.4, 19, 19, f'q_{who}_footprint')
        f = footprint(fp[who]); diff = sref.symmetric_difference(SPoly(f))
        for g in getattr(diff, 'geoms', [diff]):
            a.add_patch(Polygon(np.asarray(g.exterior.coords), fc=col, alpha=.22, ec='none'))
        a.add_patch(Polygon(ref, closed=True, fill=False, ec=REF, lw=.8, ls=(0, (3, 1.6))))
        a.add_patch(Polygon(f, closed=True, fill=False, ec=col, lw=1.1))
        for xs, zs, _ in fire_segments(fp['REF'], 'REF'):
            a.plot(xs, zs - .17, color=FIRE, lw=1.6, alpha=.85, solid_capstyle='round')
        a.plot([0], [0], marker='+', color=INK, ms=3.5, mew=.6)
        a.text(0.02, -1.62, 'fireplace', color=FIRE, fontsize=5.4, ha='center', va='bottom')
        a.set(xlim=(-2.15, 2.3), ylim=(-1.65, 3.3)); a.set_aspect('equal'); a.axis('off')
        text(bg, 14.0 + k * 22.8, 122.8, f'{who}  Q = {fp["Q"][who]:.1f}', 6.3, col, weight='bold', ha='center')
    text(bg, 3.5, 126.6, 'Dashed: reference.  Shaded: floor added or missed.', 5.4, MUTED)
    text(bg, 3.5, 129.3, 'Q also weighs boundary position, wall direction\nand heights. It does not choose corners.', 5.4, MUTED)


GREEN = '#11866a'


def consensus_panel(cv):
    bg = cv.bg
    case = json.loads(CONS.read_text(encoding='utf-8'))
    assert case['image'] == 'jtcxE69GiFV-13'
    t1, t2 = case['teams']['Team 1'], case['teams']['Team 2']
    assert (t1['n'], t1['threshold'], t2['n'], t2['threshold']) == (10, 5, 10, 5)
    sup = {(t, tr['label']): tr['support'] for t, d in case['teams'].items() for tr in d['turns']}
    assert sup == {('Team 1', 'A'): 4, ('Team 1', 'B'): 2, ('Team 2', 'A'): 8, ('Team 2', 'B'): 8}
    shared = {p['person'] for p in t1['people']} & {p['person'] for p in t2['people']}
    box(bg, 51, 93, W - 53, 41, gid='consensus_card')
    text(bg, 52.5, 94.3, 'Paired-corner structural consensus', 6.9, GREEN, weight='bold')
    text(bg, 52.5, 97.6, 'Finds who marked the same corner; keeps it if at least half the team did',
         5.9, INK)
    text(bg, 52.5, 100.5, 'Panorama jtcxE69GiFV-13: two published 10-person teams, wall-recess corners A and B',
         5.4, MUTED)
    photo = Image.open(PANO_BATH); assert photo.size == (2048, 1024)
    text(bg, 52.5, 104.3, 'Team 2: who marked A, B', 5.8, INK, weight='bold')
    marks = {'A': 'o', 'B': '^'}
    for k, (vv, lab) in enumerate([((132, 176), 'ceiling'), ((381, 425), 'floor')]):
        a = image_ax(cv, 52.5, 108 + k * 11.3, 21, 10.3, photo, [0, 1024, 512, 0], (660, 712), vv[::-1],
                     f'consensus_{lab}_clicks')
        a.text(.03, .05 if k == 0 else .95, lab, transform=a.transAxes, fontsize=5.4, color='white',
               fontweight='bold', va='bottom' if k == 0 else 'top')
        for tr in t2['turns']:
            m = np.array([mm['pair'][k] for mm in tr['members']])
            a.scatter(m[:, 0], m[:, 1], s=9, marker=marks[tr['label']], c=BLUE, edgecolors='white', linewidths=.4, zorder=5)
            a.scatter(*tr['pair'][k], s=26, marker='D', c=ORANGE, edgecolors='white', linewidths=.5, zorder=6)
            if k == 0:
                a.text(tr['pair'][0][0] + (-4 if tr['label'] == 'A' else 4), vv[0] + 3, tr['label'],
                       ha='center', va='top', fontsize=5.6, color='white', fontweight='bold')
    for x, m, c, lab in [(53.4, 'o', BLUE, 'A'), (56.6, '^', BLUE, 'B clicks'), (67.0, 'D', ORANGE, 'medians')]:
        bg.scatter([x], [131.5], s=8, marker=m, c=c, edgecolors='white', linewidths=.3, zorder=6)
        text(bg, x + 1.0, 130.6, lab, 5.5, MUTED)
    return case, sup, shared


def consensus_outcome(cv, case, sup, shared):
    bg = cv.bg
    text(bg, 79, 104.3, 'Supporters per corner', 5.8, INK, weight='bold')
    a = cv.ax(84.5, 108.5, 19, 19.5, 'consensus_support_bars')
    rows = [('Team 1', 'A'), ('Team 1', 'B'), ('Team 2', 'A'), ('Team 2', 'B')]
    for i, key in enumerate(rows):
        y = 3.4 - i - (.35 if i > 1 else 0)
        kept = sup[key] >= 5
        a.barh(y, 10, height=.56, color='#edf0f2', zorder=1)
        a.barh(y, sup[key], height=.56, color=GREEN if kept else '#a9b3ba', zorder=2)
        a.text(sup[key] + .3, y, str(sup[key]), va='center', fontsize=5.6, color=INK)
        a.text(-.4, y, f'{key[0]}  {key[1]}', va='center', ha='right', fontsize=5.6, color=INK)
    a.axvline(5, color=ORANGE, lw=.8, ls=(0, (2, 1.2)), zorder=3)
    a.text(5, 4.05, '5 of 10 needed', ha='center', va='bottom', fontsize=5.5, color=ORANGE)
    a.set(xlim=(0, 10), ylim=(-.25, 4.0)); a.axis('off')
    text(bg, 79, 129.0, f'{len(shared)} people belong to both teams', 5.5, MUTED)
    text(bg, 106.5, 104.3, 'Team layouts (offline)', 5.8, INK, weight='bold')
    ref = footprint(case['reference'])
    for k, (team, col, note) in enumerate([('Team 1', '#7f8b93', 'A, B dropped:\nno recess'),
                                           ('Team 2', GREEN, 'A, B kept:\nrecess drawn')]):
        a = cv.ax(106.5 + k * 15.3, 108.5, 14.2, 15, f'consensus_{team.replace(" ", "")}_layout')
        f = footprint(case['teams'][team]['candidate']['points'])
        a.add_patch(Polygon(ref, closed=True, fill=False, ec=REF, lw=.7, ls=(0, (3, 1.6))))
        a.add_patch(Polygon(f, closed=True, fill=True, fc=col, alpha=.10, ec='none'))
        a.add_patch(Polygon(f, closed=True, fill=False, ec=col, lw=1.2))
        a.set(xlim=(.40, .90), ylim=(-.72, -.02)); a.set_aspect('equal')
        a.set_xticks([]); a.set_yticks([])
        for s in a.spines.values():
            s.set_color('#c3ccd2'); s.set_linewidth(.4)
        a.text(.5, 1.02, team, transform=a.transAxes, ha='center', va='bottom', fontsize=5.8, color=col, fontweight='bold')
        text(bg, 106.5 + k * 15.3, 124.3, note, 5.3, INK)
    text(bg, 106.5, 130.6, 'Dashed: reference, display only', 5.5, MUTED)
    arrow(bg, (74.0, 118.2), (78.4, 118.2), color=INK, lw=.7)
    arrow(bg, (104.0, 118.2), (106.2, 118.2), color=INK, lw=.7)


# ---------------------------------------------------------------- band 3: comparisons
def person(a, x, y, c, s=1.0, z=3):
    a.add_patch(Circle((x, y + .55 * s), .28 * s, fc=c, ec='none', zorder=z))
    a.add_patch(FancyBboxPatch((x - .38 * s, y - .35 * s), .76 * s, .62 * s,
                               boxstyle=f'round,pad=0,rounding_size={.3 * s}', fc=c, ec='none', zorder=z))


def rq_glyphs(cv, fp, x0s, y0, w):
    photo = Image.open(PANO_FIRE).resize((512, 256))
    # RQ1: one panorama -> two individual footprints
    a = cv.ax(x0s[0] + 1.2, y0, w - 2.4, 12, 'rq1_glyph'); a.set(xlim=(0, 30), ylim=(0, 12)); a.axis('off')
    a.imshow(photo, extent=[0, 12, 3, 9], zorder=1)
    arrow(a, (12.6, 6), (16.2, 6), color=MUTED, lw=.6, ms=3.5)
    for k, (who, col) in enumerate([('A29', C29), ('A59', C59)]):
        f = footprint(fp[who]); f = (f - [-1.9, -1.1]) / 4.4 * 6.2 + [16.8 + k * 6.8, 2.9]
        a.add_patch(Polygon(f, closed=True, fill=False, ec=col, lw=.9))
        a.text(19.9 + k * 6.8, 1.6, who, ha='center', va='center', fontsize=5.4, color=col, fontweight='bold')
    # RQ2: fixed pool, nested teams
    a = cv.ax(x0s[1] + 1.2, y0, w - 2.4, 12, 'rq2_glyph'); a.set(xlim=(0, 30), ylim=(0, 12)); a.axis('off')
    a.add_patch(FancyBboxPatch((.4, .4), 29.2, 11.0, boxstyle='round,pad=0,rounding_size=1.5', fc='#f4f6f7', ec='#c3ccd2', lw=.5))
    order = [(3.0 + 4.8 * i, 7.9 - 4.6 * j) for j in range(2) for i in range(6)]
    order = [(px, py - .5) for px, py in order]
    tone = ['#24313a'] * 3 + ['#5b7f99'] * 3 + ['#a8bccb'] * 6
    for (px, py), c in zip(order, tone):
        person(a, px, py - .3, c, 1.7)
    a.add_patch(FancyBboxPatch((.9, 5.0), 13.2, 4.9, boxstyle='round,pad=0,rounding_size=1.2', fill=False, ec=INK, lw=.7))
    a.add_patch(FancyBboxPatch((.7, 4.7), 27.8, 5.6, boxstyle='round,pad=0,rounding_size=1.4', fill=False, ec='#5b7f99', lw=.7, ls=(0, (2, 1))))
    a.text(7.5, 11.9, 'first 3', ha='center', va='center', fontsize=5.4, color=INK, fontweight='bold')
    a.text(21.5, 11.9, 'then 6', ha='center', va='center', fontsize=5.4, color='#5b7f99', fontweight='bold')
    # RQ3: retained members fixed, the rest replaced
    a = cv.ax(x0s[2] + 1.2, y0, w - 2.4, 12, 'rq3_glyph'); a.set(xlim=(0, 30), ylim=(0, 12)); a.axis('off')
    for row, (c, lab) in enumerate([('#6a8caf', 'C2'), ('#c4652a', 'C3')]):
        y = 8.4 - row * 4.9
        for i in range(3):
            person(a, 2.4 + 3.5 * i, y, '#8a959c', 1.45)
        for i in range(3):
            person(a, 15.4 + 3.5 * i, y, c, 1.45)
        a.text(26.6, y + .2, lab, va='center', fontsize=5.4, color=c, fontweight='bold')
    a.add_patch(Rectangle((.5, 2.2), 11.6, 9.4, fill=False, ec=INK, lw=.6, ls=(0, (2, 1))))
    a.text(6.3, 1.0, 'kept', ha='center', va='center', fontsize=5.4, color=INK)
    a.text(18.9, 1.0, 'replaced', ha='center', va='center', fontsize=5.4, color=INK)
    arrow(a, (24.6, 8.6), (24.6, 4.6), color=MUTED, lw=.6, ms=3.5)
    # RQ4: same room, two viewpoints
    a = cv.ax(x0s[3] + 1.2, y0, w - 2.4, 12, 'rq4_glyph'); a.set(xlim=(0, 30), ylim=(0, 12)); a.axis('off')
    a.add_patch(Polygon([(4, 1.2), (4, 10.8), (26, 10.8), (26, 5.2), (20, 5.2), (20, 1.2)], fill=False, ec=INK, lw=.8))
    for (cx, cy, lab) in [(9.5, 6.0, 'view 1'), (21.5, 8.3, 'view 2')]:
        a.add_patch(Circle((cx, cy), .75, fc=FIRE, ec='white', lw=.5, zorder=4))
        a.text(cx, cy - 1.3, lab, ha='center', va='top', fontsize=5.5, color=FIRE)
        person(a, cx + 2.4, cy - .2, INK, 1.25)
    arrow(a, (10.6, 6.4), (20.4, 8.0), color=FIRE, lw=.6, ms=3.5, rad=-.25)


RQS = [('RQ1', 'Compare individuals', 'One panorama', 'Person; in Semi, also the\nsupplied vs submitted layout'),
       ('RQ2', 'Add people', 'Panorama, person pool', 'Team size, 3 to 30'),
       ('RQ3', 'Swap members', 'Panorama, kept members', 'Replacements from the\nsame or another profile'),
       ('RQ4', 'Change viewpoint', 'Room; person or members', 'Viewpoint in the room')]


def rq_panel(cv, fp):
    bg = cv.bg
    step(bg, 2, 137.0, 4, 'Researchers compare layouts in four ways, one per research question')
    w, gap = (W - 4 - 3 * 1.6) / 4, 1.6
    x0s = [2 + i * (w + gap) for i in range(4)]
    for x0, (rq, verb, same, varies) in zip(x0s, RQS):
        box(bg, x0, 142.3, w, 26.2, gid=f'{rq.lower()}_card')
        text(bg, x0 + 1.4, 143.4, rq, 6.3, BLUE, weight='bold')
        text(bg, x0 + 8.3, 143.4, verb, 6.3, INK, weight='bold')
        text(bg, x0 + 1.4, 160.6, 'Same', 5.4, GREEN, weight='bold')
        text(bg, x0 + 8.0, 160.6, same, 5.4, INK)
        text(bg, x0 + 1.4, 163.6, 'Varies', 5.4, ORANGE, weight='bold')
        text(bg, x0 + 8.0, 163.6, varies, 5.4, INK)
    rq_glyphs(cv, fp, x0s, 147.2, w)


def save(cv):
    OUT.mkdir(parents=True, exist_ok=True)
    stem = OUT / 'Figure2_overview_candidate_Opus'
    for ext, kw in [('svg', {'dpi': 600}), ('pdf', {'dpi': 600}), ('png', {'dpi': 400})]:  # dpi sets embedded raster resolution
        cv.fig.savefig(stem.with_suffix('.' + ext), **kw)
    plt.close(cv.fig)
    return stem


def main():
    fp = load_fireplace()
    cv = Canvas()
    box(cv.bg, 0, 0, W, 74.6, fc=BAND1, ec='none', r=0, gid='band_individual', z=0)
    box(cv.bg, 0, 87.0, W, 48.6, fc=BAND2, ec='none', r=0, gid='band_offline', z=0)
    step(cv.bg, 2, 1.6, 1, 'Each annotator works alone in the annotation tool')
    step(cv.bg, 2, 88.2, 3, 'Two methods analyse the submitted layouts (after submission, in the background)')
    semi_panel(cv)
    manual_panel(cv, fp)
    handover(cv)
    q_panel(cv, fp)
    consensus_outcome(cv, *consensus_panel(cv))
    rq_panel(cv, fp)
    print(save(cv))


if __name__ == '__main__':
    main()
