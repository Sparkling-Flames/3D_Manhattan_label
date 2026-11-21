"""CSCW Figure 2, round-2 Opus candidate v2 (layout modelled on the advisor's reference figure).

Borrowed from the reference: a top study-arrangement strip, a rules box on the left, one central
interaction loop drawn on a disc, a concrete example column on the right, and role colours
(annotator / annotation tool / researchers offline). Not borrowed: its feedback mechanism. Here the
only response a person receives is the tool's 3D preview of their own layout; all team work happens
in the bottom band after submission, and no arrow returns from it to an annotator.
Data helpers and every geometric input come from draw_cscw_fig2_round2_opus_20261121 (v1).
"""
from pathlib import Path
import json
import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle, Circle
from PIL import Image
from shapely.geometry import Polygon as SPoly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draw_cscw_fig2_round2_opus_20261121 as v1
from draw_cscw_fig2_round2_opus_20261121 import (text, box, arrow, image_ax, pairs, footprint, edge_samples,
                                                to_pano, render_px, load_renders, fire_segments, FIRE_U,
                                                INK, MUTED, REF, C29, C59, SEMI, EXTRA, FIRE, BLUE, ORANGE,
                                                PANO_SEMI, PANO_FIRE, PANO_BATH, CONS)

OUT = v1.WORK / 'CSCW图2 候选' / 'CSCW图2第二轮_Opus参考图版_20261121'
W, H = 139.7, 178.0
TOOL, GOLD, GOLDD = '#2f78a6', '#c9962b', '#8a6412'
GREEN = '#11866a'
GOLD_BG, TOOL_BG, DISC = '#fbf5e6', '#eef4f8', '#e6eff4'


class Canvas(v1.Canvas):
    def __init__(self):
        self.fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        self.bg = self._overlay('background', 0)
        self.fg = None

    def _overlay(self, gid, z):
        ax = self.fig.add_axes([0, 0, 1, 1], zorder=z)
        ax.set(xlim=(0, W), ylim=(H, 0)); ax.axis('off'); ax.set_gid(gid); ax.patch.set_alpha(0)
        return ax

    def ax(self, x, y, w, h, gid, z=10):
        a = self.fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H], zorder=z)
        a.set_gid(gid)
        return a


# ---------------------------------------------------------------- icons (mm coordinates, y down)
def person_icon(ax, x, y, s=1.0, c=INK, z=6):
    """Head-and-shoulders glyph; (x, y) is the bottom centre."""
    ax.add_patch(Circle((x, y - 2.35 * s), .75 * s, fc=c, ec='none', zorder=z))
    ax.add_patch(FancyBboxPatch((x - 1.15 * s, y - 1.45 * s), 2.3 * s, 1.45 * s,
                                boxstyle=f'round,pad=0,rounding_size={.6 * s}', fc=c, ec='none', zorder=z))


def screen_icon(ax, x, y, w=4.6, h=3.2, c=TOOL, z=5):
    """Monitor outline; (x, y) is the top-left corner."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=.35',
                                fc='white', ec=c, lw=.7, zorder=z))
    ax.plot([x + w / 2, x + w / 2], [y + h, y + h + .7], color=c, lw=.7, zorder=z)
    ax.plot([x + w / 2 - .9, x + w / 2 + .9], [y + h + .7, y + h + .7], color=c, lw=.7, zorder=z)


def annotator_at_screen(ax, x, y, s=1.0):
    screen_icon(ax, x + 1.4 * s, y - 5.6 * s, 4.8 * s, 3.4 * s)
    person_icon(ax, x, y, s)


def cube_icon(ax, x, y, s=1.6, c=TOOL, z=6):
    """Small isometric box standing for the tool's 3D rendering; (x, y) is the centre."""
    a, b = .87 * s, .5 * s
    top = [(x, y - s), (x + a, y - s + b), (x, y - s + 2 * b), (x - a, y - s + b)]
    ax.add_patch(Polygon(top, closed=True, fc='white', ec=c, lw=.6, zorder=z))
    for px, py in top[1:]:
        ax.plot([px, px], [py, py + s], color=c, lw=.6, zorder=z)
    ax.plot([top[1][0], top[2][0], top[3][0]], [top[1][1] + s, top[2][1] + s, top[3][1] + s], color=c, lw=.6, zorder=z)


def stack_icon(ax, x, y, w=5.0, h=6.2, c='#7d8a93', n=3, z=6):
    """Stack of submitted drawings; (x, y) is the top-left of the front sheet."""
    for k in reversed(range(n)):
        dx = dy = -1.0 * k
        ax.add_patch(FancyBboxPatch((x + dx + 1.0 * (n - 1), y + dy + 1.0 * (n - 1)), w, h,
                                    boxstyle='round,pad=0,rounding_size=.4', fc='white', ec=c, lw=.55, zorder=z))
    fx, fy = x + 1.0 * (n - 1), y + 1.0 * (n - 1)
    ax.add_patch(Polygon([(fx + 1, fy + 4.6), (fx + 1.2, fy + 1.3), (fx + 4, fy + 1.4), (fx + 3.8, fy + 4.7)],
                         closed=True, fill=False, ec=c, lw=.55, zorder=z + 1))


def badge(ax, x, y, n, c=GOLDD, r=1.25, size=5.6):
    ax.add_patch(Circle((x, y), r, fc=c, ec='none', zorder=7))
    text(ax, x, y + .05, str(n), size, 'white', weight='bold', ha='center', va='center', zorder=8)


def cursor(a, u, v, scale=1.0, c=INK):
    """Mouse pointer drawn in panorama pixel units (v grows downward); tip at (u, v)."""
    pts = np.array([(0, 0), (0, 17), (4.2, 13.2), (7.3, 20), (9.6, 19), (6.6, 12.4), (12, 12.4)]) * scale
    a.add_patch(Polygon(pts + [u, v], closed=True, fc='white', ec=c, lw=.6, zorder=9))


# ---------------------------------------------------------------- top strip and legend
def tiles(ax, x, y, labels, c, w=3.6, gap=.8):
    for k, lab in enumerate(labels):
        if lab == '\u2026':
            text(ax, x + .9, y + 1.6, lab, 6.0, c, ha='center', va='center')
            x += 2.2
            continue
        ax.add_patch(FancyBboxPatch((x, y), w, 3.0, boxstyle='round,pad=0,rounding_size=.4',
                                    fc='white', ec=c, lw=.6, zorder=4))
        text(ax, x + w / 2, y + 1.55, lab, 5.0, c, weight='bold', ha='center', va='center', zorder=6)
        x += w + gap


def top_strip(cv):
    bg = cv.bg
    box(bg, 2, 2, W - 4, 11.6, fc='#f2f4f5', ec='#d9dee2', gid='study_arrangement')
    text(bg, 4, 3.7, 'Study arrangement', 6.6, GOLDD, weight='bold')
    text(bg, 4, 7.3, 'Every person works alone;\nmodes use separate panoramas', 5.4, MUTED)
    text(bg, 39.5, 3.7, 'Instruction\n+ practice', 5.6, INK, ha='center')
    arrow(bg, (46.3, 7.5), (50.5, 7.5), color=MUTED, lw=.6, ms=4)
    for x0, title, labs, c, note in [(51.5, 'Semi', ['S1', 'S2', '\u2026', 'Sn'], SEMI, 'supplied layout'),
                                     (83.5, 'Manual', ['M1', 'M2', '\u2026', 'Mn'], INK, 'empty layout')]:
        text(bg, x0, 3.7, title, 6.3, c, weight='bold')
        text(bg, x0 + (7.3 if title == 'Semi' else 10.4), 4.0, note, 5.4, MUTED)
        tiles(bg, x0, 8.0, labs, c)
    arrow(bg, (77.5, 7.5), (82.3, 7.5), color=MUTED, lw=.6, ms=4)
    text(bg, 80.0, 9.0, 'then', 5.0, MUTED, ha='center')
    text(bg, 109.2, 7.6, 'each panorama\n= one task', 5.0, MUTED, va='center')
    arrow(bg, (121.0, 7.6), (124.6, 7.6), color=MUTED, lw=.6, ms=4)
    text(bg, 130.6, 4.0, 'submit', 5.4, INK, ha='center')
    text(bg, 130.6, 7.0, 'one\ndrawing', 5.0, MUTED, ha='center')


def legend(cv, y=15.0):
    bg = cv.bg
    x = 79.0
    person_icon(bg, x, y + 1.2, .62); text(bg, x + 1.6, y - .4, 'Annotator', 5.6, INK)
    x += 14.5
    bg.add_patch(Rectangle((x - .9, y - .9), 1.9, 1.9, fc=TOOL, ec='none')); text(bg, x + 1.6, y - .4, 'Annotation tool', 5.6, TOOL)
    x += 21.5
    bg.add_patch(Rectangle((x - .9, y - .9), 1.9, 1.9, fc=GOLD, ec='none')); text(bg, x + 1.6, y - .4, 'Researchers, offline', 5.6, GOLDD)


# ---------------------------------------------------------------- left column: task and Semi
RULES = ['Outline the room that\nencloses the camera', 'Vertical walls on two\northogonal axes',
         'Keep recesses; ignore\nfurniture and decor', 'Close openings at\ndoorframes']


def task_box(cv):
    bg = cv.bg
    box(bg, 2, 17, 33, 28.4, fc=GOLD_BG, ec='#e3cd98', gid='task_rules')
    text(bg, 18.5, 18.2, 'Task rules', 6.6, GOLDD, weight='bold', ha='center')
    text(bg, 18.5, 21.3, 'set by researchers, same for all', 5.2, MUTED, ha='center')
    for k, rule in enumerate(RULES):
        y = 24.6 + k * 5.1
        badge(bg, 5.0, y + 1.2, k + 1, GOLD, r=1.1, size=5.2)
        text(bg, 7.2, y, rule, 5.5, INK)
    arrow(bg, (35.3, 31.0), (41.6, 31.0), color=GOLDD, lw=.7, ms=4.5)
    text(bg, 38.4, 30.4, 'assigns\npanorama', 5.0, GOLDD, ha='center', va='bottom')
    arrow(bg, (18.5, 45.5), (18.5, 47.4), color=GOLDD, lw=.6, ms=3.5)


def semi_box(cv):
    from render_semi_case_20261107 import load_case, UNCHANGED, EDITED
    plt.rcParams.update(v1.STYLE)
    initial, finals, _ = load_case()
    assert finals[UNCHANGED]['paper_id'] == 'A3' and finals[EDITED]['paper_id'] == 'A2'
    bg = cv.bg
    box(bg, 2, 47.5, 33, 45.5, gid='semi_card')
    text(bg, 3.4, 48.7, 'Semi: supplied layout', 6.3, SEMI, weight='bold')
    text(bg, 3.4, 51.9, 'Keep or edit given corners', 5.5, INK)
    text(bg, 3.4, 54.5, 'Z6MFQCViBuw-10', 5.2, MUTED)
    photo = Image.open(PANO_SEMI); assert photo.size == (2048, 1024)
    a = image_ax(cv, 3.4, 57.3, 30.2, 15.1, photo, [0, 1024, 512, 0], (0, 1024), (512, 0), 'semi_supplied_layout')
    for xs, zs, ys in edge_samples(initial, [(i, (i + 1) % 5) for i in range(5)]):
        for yy in (ys, np.full_like(xs, -1.)):
            u, v = to_pano(xs, yy, zs)
            br = np.where(np.abs(np.diff(u)) > 500)[0] + 1
            for uu, vv in zip(np.split(u, br), np.split(v, br)):
                a.plot(uu, vv, color=SEMI, lw=.6, zorder=4)
    p = pairs(initial)
    for k, ((ut, vt), (ub, vb)) in enumerate(p):
        a.scatter([ut, ub], [vt, vb], s=6, c=EXTRA if k == 2 else SEMI, edgecolors='white', linewidths=.35, zorder=6)
    CU, CV = (336, 396), (132, 178)
    a.add_patch(Rectangle((CU[0], CV[0]), CU[1] - CU[0], CV[1] - CV[0], fill=False, ec='white', lw=.6, zorder=7))
    text(bg, 3.4, 73.0, '5 supplied pairs; 2 nearly coincide', 5.2, INK)
    return photo, p, finals, (UNCHANGED, EDITED), (CU, CV)


def semi_outcomes(cv, photo, p, finals, ids, crop):
    bg = cv.bg
    (CU, CV) = crop
    for k, (oid, title, note) in enumerate([(ids[0], 'A3: as given', '5 pairs kept'),
                                            (ids[1], 'A2: edited', 'duplicate removed')]):
        x0 = 3.4 + k * 15.6
        b = image_ax(cv, x0, 76.3, 14.6, 10.6, photo, [0, 1024, 512, 0], CU, CV[::-1], f'semi_{finals[oid]["paper_id"]}')
        for ut, vt in pairs(finals[oid]['points'])[:, 0]:
            c = EXTRA if np.isclose(ut, p[2, 0, 0]) else SEMI
            b.scatter([ut], [vt], s=14, c=c, edgecolors='white', linewidths=.5, zorder=6)
        text(bg, x0, 87.4, title, 5.5, INK, weight='bold')
        text(bg, x0, 90.0, note, 5.2, MUTED)
    arrow(bg, (18.5, 93.2), (18.5, 98.4), color=INK, lw=.8, ms=4.5)
    text(bg, 19.8, 94.2, 'submit', 5.4, INK)


# ---------------------------------------------------------------- centre: one Manual episode
CROP_U, CROP_V = (300, 730), (430, 100)
CORNER_A = 1    # A59 pair index at the left outer side of the fireplace


def clicks_ax(cv, x, y, w, h, photo, pts, col, gid):
    a = image_ax(cv, x, y, w, h, photo, [0, 1024, 512, 0], CROP_U, CROP_V, gid)
    v1.draw_dots(a, pts, col, s=10)
    a.annotate('', xy=(FIRE_U[0], 124), xytext=(FIRE_U[1], 124),
               arrowprops=dict(arrowstyle='|-|,widthA=.25,widthB=.25', color=FIRE, lw=.8))
    a.text(sum(FIRE_U) / 2, 129.0, 'fireplace', color=FIRE, fontsize=5.4, fontweight='bold',
           ha='center', va='top')
    return a


def preview_ax(cv, x, y, w, h, renders, lim, who, pts, gid):
    r = image_ax(cv, x, y, w, h, renders[who], None, *lim, gid)
    r.images[0].set_extent([0, renders[who].shape[1], renders[who].shape[0], 0]); r.set(xlim=lim[0], ylim=lim[1])
    for s in r.spines.values():
        s.set_color('#d5dbdf')
    name = f'Fig6_{"4" if who == "A29" else "8"}_corners_complete_walls'
    for xs, zs, ys in fire_segments(pts, who):
        px, py = render_px(name, xs, ys, zs)
        r.plot(px, py, color=FIRE, lw=2.2, alpha=.85, solid_capstyle='round', zorder=6)
    return r, name


def mark_corner_on_preview(r, name, pts, idx):
    x, z, top = v1.recon(pts)
    px, py = render_px(name, np.r_[x[idx], x[idx]], np.r_[top[idx], -1.], np.r_[z[idx], z[idx]])
    r.plot(px, py, color=INK, lw=.6, ls=(0, (1.5, 1)), zorder=7)
    r.scatter(px, py, s=11, c=C59, edgecolors=INK, linewidths=.5, zorder=8)
    r.text(px[1] - 40, py[1] - 10, 'a', color=INK, fontsize=6.0, fontweight='bold', ha='right', va='center', zorder=9)


PANEL = (31.3, 24.0)    # click crop, 430 x 330 panorama px
PREV = (25.0, 21.2)     # preview crop


def episode(cv, fp, photo, renders, lim):
    bg = cv.bg
    bg.add_patch(Circle((69.0, 57.5), 30.0, fc=DISC, ec='none', zorder=0, gid='episode_disc'))
    # station 1: look and decide
    annotator_at_screen(bg, 44.0, 56.0, 1.55)
    badge(bg, 40.6, 60.4, 1, INK)
    text(bg, 39.8, 62.4, 'Look; decide\nwhich turns\nto mark', 5.5, INK)
    arrow(bg, (45.5, 46.6), (50.2, 37.0), color=INK, lw=.8, rad=-.25)
    # station 2: click endpoints (A59's original clicks)
    badge(bg, 51.7, 19.2, 2, INK)
    text(bg, 53.6, 18.1, 'Click the upper and lower end of each turn', 5.6, INK)
    a = clicks_ax(cv, 50.5, 21.2, *PANEL, photo, fp['A59'], C59, 'episode_A59_clicks')
    (ut, vt), (ub, vb) = pairs(fp['A59'])[CORNER_A]
    for v in (vt, vb):
        a.add_patch(Circle((ut, v), 12, fill=False, ec='white', lw=.8, zorder=8))
    a.text(ut - 16, (vt + vb) / 2, 'a', color='white', fontsize=6.0, fontweight='bold', ha='right', va='center', zorder=9)
    cursor(a, ut + 2, vt + 3, 2.0)
    # station 3: the tool renders this person's own layout
    badge(bg, 86.2, 46.2, 3, TOOL)
    text(bg, 88.0, 45.0, 'Tool renders\nown 3D preview', 5.5, TOOL)
    arrow(bg, (82.0, 37.0), (87.6, 51.6), color=TOOL, lw=.8, rad=-.2)
    r, name = preview_ax(cv, 75.6, 52.0, *PREV, renders, lim, 'A59', fp['A59'], 'episode_A59_preview')
    mark_corner_on_preview(r, name, fp['A59'], CORNER_A)
    # station 4: inspect and revise (the only feedback loop a person has)
    arrow(bg, (75.2, 66.5), (64.0, 45.6), color=C59, lw=.8, rad=-.35)
    badge(bg, 51.6, 55.6, 4, C59)
    text(bg, 53.4, 54.4, 'Inspect;\nmove an\nendpoint', 5.5, C59)
    text(bg, 75.6, 73.8, 'A59: 8 pairs; the wall turns\naround both fireplace sides', 5.5, INK)
    text(bg, 50.0, 79.6, 'Manual annotation episode', 6.6, INK, weight='bold')
    text(bg, 50.0, 82.9, 'one person, one panorama, empty start;\nonly feedback: the own 3D preview', 5.3, MUTED)
    arrow(bg, (88.1, 81.0), (88.1, 98.4), color=INK, lw=.8, ms=4.5)
    text(bg, 89.4, 89.2, 'submit', 5.4, INK)


def contrast_column(cv, fp, photo, renders, lim):
    bg = cv.bg
    box(bg, 103.0, 17.0, 34.7, 76.0, gid='contrast_card')
    text(bg, 104.4, 18.2, 'Same panorama,', 6.0, INK, weight='bold')
    text(bg, 104.4, 21.0, 'another annotator', 6.0, INK, weight='bold')
    text(bg, 104.4, 24.2, '7y3sRwLe3Va-19; A29 never\nsees A59’s drawing', 5.2, MUTED)
    clicks_ax(cv, 104.6, 30.4, *PANEL, photo, fp['A29'], C29, 'contrast_A29_clicks')
    arrow(bg, (120.3, 54.8), (120.3, 58.4), color=TOOL, lw=.7, ms=4)
    preview_ax(cv, 107.8, 58.8, *PREV, renders, lim, 'A29', fp['A29'], 'contrast_A29_preview')
    text(bg, 104.4, 81.0, 'A29: 4 pairs; one straight\nwall across the fireplace', 5.5, INK)
    text(bg, 104.4, 87.4, 'Purple: the same fireplace\nwall in clicks and 3D', 5.2, FIRE)
    arrow(bg, (120.3, 93.2), (120.3, 98.4), color=INK, lw=.8, ms=4.5)
    text(bg, 121.6, 94.2, 'submit', 5.4, INK)


# ---------------------------------------------------------------- bottom: researchers, offline
def offline_band(cv):
    bg = cv.bg
    box(bg, 0, 98.6, W, H - 98.6, fc=GOLD_BG, ec='none', r=0, gid='band_offline', z=0)
    bg.plot([0, W], [98.6, 98.6], color=GOLD, lw=1.2, zorder=1)
    text(bg, 2.5, 100.0, 'After submission: researchers, offline', 6.8, GOLDD, weight='bold')
    text(bg, 58.5, 100.25, 'No arrow returns to annotators: nobody sees a team layout.', 5.4, MUTED)
    # stack of independent submissions -> teams
    stack_icon(bg, 3.2, 106.4)
    text(bg, 12.6, 106.0, 'All independent\nsubmissions for\none panorama', 5.4, INK)
    arrow(bg, (8.0, 116.2), (8.0, 119.6), color=GOLDD, lw=.7, ms=4)
    text(bg, 3.0, 120.6, 'Form teams', 6.0, GOLDD, weight='bold')
    text(bg, 3.0, 123.6, 'Drawings first meet\nhere: group those of\none panorama', 5.3, INK)
    for k in range(3):
        for j in range(2):
            person_icon(bg, 4.6 + 2.9 * j + 8.2 * k, 136.3 - 0.0, .58, ['#9aa6ae', '#5b7f99', GOLDD][k])
        bg.add_patch(FancyBboxPatch((2.6 + 8.2 * k, 131.4), 7.0, 5.6, boxstyle='round,pad=0,rounding_size=.8',
                                    fill=False, ec='#b7a274', lw=.5))
    text(bg, 3.0, 138.2, 'Team = submissions\ncombined offline', 5.2, MUTED)
    arrow(bg, (26.6, 121.0), (30.0, 121.0), color=GOLDD, lw=.8, ms=4.5)


def q_mini(cv, fp):
    """Q: individual or team layout vs. the assigned reference (A29, A59 footprints)."""
    bg = cv.bg
    box(bg, 30.4, 104.6, 33.0, 38.4, gid='q_card')
    text(bg, 31.8, 105.7, 'Geometric quality Q', 6.3, BLUE, weight='bold')
    text(bg, 31.8, 108.9, 'Where does a layout depart\nfrom the assigned reference?', 5.3, INK)
    ref = footprint(fp['REF']); sref = SPoly(ref)
    for k, who in enumerate(['A29', 'A59']):
        col = C29 if who == 'A29' else C59
        a = cv.ax(31.4 + k * 15.8, 115.4, 15.2, 16.8, f'q_{who}_footprint')
        f = footprint(fp[who]); diff = sref.symmetric_difference(SPoly(f))
        for g in getattr(diff, 'geoms', [diff]):
            a.add_patch(Polygon(np.asarray(g.exterior.coords), fc=col, alpha=.22, ec='none'))
        a.add_patch(Polygon(ref, closed=True, fill=False, ec=REF, lw=.7, ls=(0, (3, 1.6))))
        a.add_patch(Polygon(f, closed=True, fill=False, ec=col, lw=1.0))
        for xs, zs, _ in fire_segments(fp['REF'], 'REF'):
            a.plot(xs, zs - .17, color=FIRE, lw=1.4, alpha=.85, solid_capstyle='round')
        a.set(xlim=(-2.0, 2.15), ylim=(-1.4, 3.3)); a.set_aspect('equal'); a.axis('off')
        text(bg, 39.0 + k * 15.8, 132.6, f'{who}  Q = {fp["Q"][who]:.1f}', 5.7, col, weight='bold', ha='center')
    text(bg, 31.8, 136.6, 'Dashed: reference. Shaded: floor\nadded or missed. Q picks no corner.', 5.1, MUTED)


def consensus_mini(cv):
    bg = cv.bg
    case = json.loads(CONS.read_text(encoding='utf-8'))
    assert case['image'] == 'jtcxE69GiFV-13'
    t2 = case['teams']['Team 2']
    sup = {(t, tr['label']): tr['support'] for t, d in case['teams'].items() for tr in d['turns']}
    assert sup == {('Team 1', 'A'): 4, ('Team 1', 'B'): 2, ('Team 2', 'A'): 8, ('Team 2', 'B'): 8}
    assert all(d['n'] == 10 and d['threshold'] == 5 for d in case['teams'].values())
    box(bg, 64.8, 104.6, 72.9, 38.4, gid='consensus_card')
    text(bg, 66.2, 105.7, 'Paired-corner structural consensus', 6.3, GREEN, weight='bold')
    text(bg, 66.2, 108.9, 'Who marked the same turn? Keep it if at least half the team did;\n'
         'place its ends at the supporters’ median clicks. jtcxE69GiFV-13, 10-person teams.', 5.3, INK)
    photo = Image.open(PANO_BATH); assert photo.size == (2048, 1024)
    marks = {'A': 'o', 'B': '^'}
    for k, (vv, lab) in enumerate([((132, 176), 'ceiling'), ((381, 425), 'floor')]):
        a = image_ax(cv, 66.2, 116.4 + k * 10.0, 19.5, 9.2, photo, [0, 1024, 512, 0], (660, 712), vv[::-1],
                     f'consensus_{lab}_clicks')
        a.text(.03, .06 if k == 0 else .94, lab, transform=a.transAxes, fontsize=5.0, color='white',
               fontweight='bold', va='bottom' if k == 0 else 'top')
        for tr in t2['turns']:
            m = np.array([mm['pair'][k] for mm in tr['members']])
            a.scatter(m[:, 0], m[:, 1], s=8, marker=marks[tr['label']], c=BLUE, edgecolors='white', linewidths=.35, zorder=5)
            a.scatter(*tr['pair'][k], s=22, marker='D', c=ORANGE, edgecolors='white', linewidths=.5, zorder=6)
            if k == 0:
                a.text(tr['pair'][0][0] + (-4 if tr['label'] == 'A' else 4), vv[0] + 3, tr['label'],
                       ha='center', va='top', fontsize=5.4, color='white', fontweight='bold')
    text(bg, 66.2, 136.4, 'Team 2: 8 people\nmarked A and B', 5.1, MUTED)
    for x, m, c, lab in [(67.0, 'o', BLUE, 'A'), (70.2, '^', BLUE, 'B clicks'), (80.2, 'D', ORANGE, 'median')]:
        bg.scatter([x], [141.4], s=7, marker=m, c=c, edgecolors='white', linewidths=.3, zorder=6)
        text(bg, x + .9, 140.5, lab, 5.0, MUTED)
    return case, sup


def consensus_result(cv, case, sup):
    bg = cv.bg
    arrow(bg, (86.4, 125.5), (89.2, 125.5), color=INK, lw=.7, ms=4)
    a = cv.ax(98.0, 116.8, 13.0, 16.8, 'consensus_support_bars')
    rows = [('Team 1', 'A'), ('Team 1', 'B'), ('Team 2', 'A'), ('Team 2', 'B')]
    for i, key in enumerate(rows):
        y = 3.4 - i - (.35 if i > 1 else 0)
        a.barh(y, 10, height=.56, color='#edf0f2', zorder=1)
        a.barh(y, sup[key], height=.56, color=GREEN if sup[key] >= 5 else '#a9b3ba', zorder=2)
        a.text(sup[key] + .3, y, str(sup[key]), va='center', fontsize=5.2, color=INK)
        a.text(-.4, y, f'{key[0]} {key[1]}', va='center', ha='right', fontsize=5.2, color=INK)
    a.axvline(5, color=ORANGE, lw=.8, ls=(0, (2, 1.2)), zorder=3)
    a.text(5, 4.0, '5 of 10', ha='center', va='bottom', fontsize=5.2, color=ORANGE)
    a.set(xlim=(0, 10), ylim=(-.25, 4.0)); a.axis('off')
    text(bg, 89.2, 136.4, 'Supporters\nper turn', 5.1, MUTED)
    arrow(bg, (111.6, 125.5), (114.2, 125.5), color=INK, lw=.7, ms=4)
    ref = footprint(case['reference'])
    for k, (team, col, note) in enumerate([('Team 1', '#7f8b93', 'dropped'), ('Team 2', GREEN, 'kept')]):
        a = cv.ax(114.6 + k * 11.4, 118.6, 10.6, 13.4, f'consensus_{team.replace(" ", "")}_layout')
        f = footprint(case['teams'][team]['candidate']['points'])
        a.add_patch(Polygon(ref, closed=True, fill=False, ec=REF, lw=.6, ls=(0, (3, 1.6))))
        a.add_patch(Polygon(f, closed=True, fill=True, fc=col, alpha=.10, ec='none'))
        a.add_patch(Polygon(f, closed=True, fill=False, ec=col, lw=1.1))
        a.set(xlim=(.40, .90), ylim=(-.72, -.02)); a.set_aspect('equal'); a.set_xticks([]); a.set_yticks([])
        for s in a.spines.values():
            s.set_color('#c3ccd2'); s.set_linewidth(.4)
        text(bg, 119.9 + k * 11.4, 115.6, team, 5.4, col, weight='bold', ha='center')
        text(bg, 119.9 + k * 11.4, 132.6, f'recess\n{note}', 5.1, INK, ha='center')
    text(bg, 114.6, 138.8, 'Team layout; dashed =\nreference, display only', 5.0, MUTED)


# ---------------------------------------------------------------- comparisons (RQ1-RQ4)
RQS = [('RQ1', 'Compare people', 'panorama', 'person; in Semi, also\ngiven vs submitted'),
       ('RQ2', 'Add people', 'panorama, pool', 'team size 3 to 30'),
       ('RQ3', 'Swap members', 'panorama, kept members', 'replacements’ profile'),
       ('RQ4', 'Change viewpoint', 'room; person or members', 'camera position')]


def rq_row(cv, fp):
    bg = cv.bg
    text(bg, 2.5, 146.0, 'Researchers then compare layouts, one comparison per research question', 6.3, GOLDD, weight='bold')
    w, gap = (W - 5 - 3 * 1.4) / 4, 1.4
    x0s = [2.5 + i * (w + gap) for i in range(4)]
    for x0, (rq, verb, same, varies) in zip(x0s, RQS):
        box(bg, x0, 150.0, w, 26.0, gid=f'{rq.lower()}_card')
        text(bg, x0 + 1.3, 151.1, rq, 6.0, BLUE, weight='bold')
        text(bg, x0 + 7.6, 151.1, verb, 6.0, INK, weight='bold')
        text(bg, x0 + 1.3, 167.4, 'Same', 5.2, GREEN, weight='bold')
        text(bg, x0 + 8.3, 167.4, same, 5.2, INK)
        text(bg, x0 + 1.3, 170.4, 'Varies', 5.2, ORANGE, weight='bold')
        text(bg, x0 + 8.3, 170.4, varies, 5.2, INK)
    v1.rq_glyphs(cv, fp, x0s, 154.4, w)


def save(cv):
    OUT.mkdir(parents=True, exist_ok=True)
    stem = OUT / 'Figure2_reference_style_candidate_Opus'
    for ext, kw in [('svg', {'dpi': 600}), ('pdf', {'dpi': 600}), ('png', {'dpi': 400})]:
        cv.fig.savefig(stem.with_suffix('.' + ext), **kw)
    plt.close(cv.fig)
    return stem


def main():
    fp = v1.load_fireplace()
    cv = Canvas()
    top_strip(cv)
    legend(cv)
    task_box(cv)
    photo_semi, p, finals, ids, crop = semi_box(cv)
    semi_outcomes(cv, photo_semi, p, finals, ids, crop)
    photo = Image.open(PANO_FIRE); assert photo.size == (2048, 1024)
    renders, lim = load_renders(PREV[0] / PREV[1])
    episode(cv, fp, photo, renders, lim)
    contrast_column(cv, fp, photo, renders, lim)
    offline_band(cv)
    q_mini(cv, fp)
    consensus_result(cv, *consensus_mini(cv))
    rq_row(cv, fp)
    print(save(cv))


if __name__ == '__main__':
    main()
