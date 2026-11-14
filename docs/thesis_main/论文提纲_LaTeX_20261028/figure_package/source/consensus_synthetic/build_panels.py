#!/usr/bin/env python3
"""Illustrative example for the paired-corner structural-consensus method figure.

Synthetic input (one simple room with a recess, six annotators, fixed seed) is
passed through the method as described in Section 4.2 of the manuscript:
cyclic dynamic-programming matching with skips, complete-linkage corner groups
(at most one observation per annotator), the at-least-half support rule (MV50),
median positions (azimuth unwrapped around an observed anchor, upper and lower
elevations separately) and connection through a source ring that covers every
retained corner. Nothing in the output panels is drawn by hand: every marker,
count and layout comes from the pipeline run below.

Outputs: five title-free PDF/SVG/PNG panels in figure_package/panels/consensus_method
and a trace JSON. Native LaTeX supplies subcaptions and the main caption.

Usage:  python draw_consensus_method_illustration_20261114.py [--out DIR]
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

DEFAULT_OUT = Path(__file__).resolve().parents[3] / "docs/thesis_main/论文提纲_LaTeX_20261028/figure_package/panels/consensus_method"
SEED = 20261114
G_SKIP = 7.5  # Fixed per-observation skip penalty used in the manuscript.
N_ANN = 6

# ----------------------------------------------------------------------------
# Synthetic scene (camera-height units, camera at the origin, floor plane y = -1)
# ----------------------------------------------------------------------------
TRUE = {  # label: (x, z, y_top relative to camera)
    "BL": (-2.4, -1.8, 0.95),
    "S": (-2.25, 0.25, 0.95),  # small extra detail on the left wall, drawn by two annotators only
    "TL": (-2.4, 1.8, 0.95),
    "R1": (-1.0, 1.8, 0.72),
    "R2": (-1.0, 2.7, 0.72),
    "R3": (1.0, 2.7, 0.72),
    "R4": (1.0, 1.8, 0.72),
    "TR": (2.4, 1.8, 0.95),
    "BR": (2.4, -1.8, 0.95),
}
ANNOTATORS = {  # who draws which corners (ring order)
    "A1": ["BL", "TL", "R1", "R2", "R3", "R4", "TR", "BR"],
    "A2": ["BL", "TL", "R1", "R2", "R3", "R4", "TR", "BR"],
    "A3": ["BL", "TL", "R1", "R2", "R3", "R4", "TR", "BR"],
    "A4": ["BL", "TL", "TR", "BR"],
    "A5": ["BL", "S", "TL", "TR", "BR"],
    "A6": ["BL", "S", "TL", "TR", "BR"],
}
NAMES = list(ANNOTATORS)
SHAPES = dict(zip(NAMES, ["o", "s", "^", "D", "v", "P"]))
SIGMA = dict(az=1.3, low=0.8, up=1.2)
UP_BIAS = {"A2": 1.0}  # a person who tends to click the ceiling line higher
LOW_BIAS = {"A5": -0.8}
EXTRA_AZ = {"S": 1.5}


def wrap(a):
    return (np.asarray(a, float) + 180.0) % 360.0 - 180.0


def polar(label):
    x, z, yt = TRUE[label]
    r = math.hypot(x, z)
    return dict(az=math.degrees(math.atan2(x, z)), low=-math.degrees(math.atan(1.0 / r)),
                up=math.degrees(math.atan(yt / r)))


def simulate():
    rng = np.random.default_rng(SEED)
    obs = []
    for name, labels in ANNOTATORS.items():
        rows = []
        for lab in labels:
            p = polar(lab)
            az = p["az"] + rng.normal(0, SIGMA["az"] * EXTRA_AZ.get(lab, 1.0))
            low = p["low"] + rng.normal(0, SIGMA["low"]) + LOW_BIAS.get(name, 0.0)
            up = p["up"] + rng.normal(0, SIGMA["up"]) + UP_BIAS.get(name, 0.0)
            rows.append(dict(annotator=name, truth=lab, az=float(wrap(az)), low=float(low), up=float(up)))
        rows.sort(key=lambda r: r["az"])  # each annotator's cyclic wall order
        obs.append(rows)
    return obs


# ----------------------------------------------------------------------------
# The method
# ----------------------------------------------------------------------------
def unit(az, el):
    a, e = math.radians(az), math.radians(el)
    return np.array([math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a)])


def ang(az1, el1, az2, el2):
    return math.degrees(math.acos(float(np.clip(unit(az1, el1) @ unit(az2, el2), -1, 1))))


def pair_cost(a, b):
    return 0.5 * (ang(a["az"], a["up"], b["az"], b["up"]) + ang(a["az"], a["low"], b["az"], b["low"]))


def align(U, V, g):
    """Linear alignment with skip penalty g; returns (cost, [(i, j)])."""
    m, n = len(U), len(V)
    C = np.array([[pair_cost(a, b) for b in V] for a in U]) if m and n else np.zeros((m, n))
    dp = np.zeros((m + 1, n + 1))
    dp[:, 0] = g * np.arange(m + 1)
    dp[0, :] = g * np.arange(n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            dp[i, j] = min(dp[i - 1, j - 1] + C[i - 1, j - 1], dp[i - 1, j] + g, dp[i, j - 1] + g)
    i, j, pairs = m, n, []
    while i > 0 and j > 0:
        if abs(dp[i, j] - (dp[i - 1, j - 1] + C[i - 1, j - 1])) < 1e-12:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif abs(dp[i, j] - (dp[i - 1, j] + g)) < 1e-12:
            i -= 1
        else:
            j -= 1
    return dp[m, n], pairs[::-1]


def cyclic_match(U, V, g):
    """Best partial one-to-one match over all cyclic starts and both traversal directions."""
    n = len(V)
    best = None
    for direction in ("forward", "reverse"):
        order = list(range(n)) if direction == "forward" else list(range(n))[::-1]
        for shift in range(n):
            idx = order[shift:] + order[:shift]
            cost, pairs = align(U, [V[k] for k in idx], g)
            if best is None or cost < best[0] - 1e-12:
                best = (cost, [(i, idx[j]) for i, j in pairs], direction, shift)
    return best


def run_pipeline(obs, g):
    flat = [o for rows in obs for o in rows]
    index = {(o["annotator"], k): t for t, o in enumerate(flat)
             for k in [next(k for k, r in enumerate(obs[NAMES.index(o["annotator"])]) if r is o)]}
    D = np.full((len(flat), len(flat)), 2.0)
    np.fill_diagonal(D, 0.0)
    matches = {}
    for u, v in itertools.combinations(range(N_ANN), 2):
        cost, pairs, direction, shift = cyclic_match(obs[u], obs[v], g)
        matches[f"{NAMES[u]}-{NAMES[v]}"] = [[i, j] for i, j in pairs]
        for i, j in pairs:
            a, b = index[(NAMES[u], i)], index[(NAMES[v], j)]
            D[a, b] = D[b, a] = 0.0
    lab = fcluster(linkage(squareform(D, checks=False), method="complete"), t=1.0, criterion="distance")
    groups = {}
    for t, c in enumerate(lab):
        groups.setdefault(int(c), []).append(t)

    def median_az(members):
        costs = np.array([[max(ang(flat[i]["az"], flat[i]["up"], flat[j]["az"], flat[j]["up"]),
                                   ang(flat[i]["az"], flat[i]["low"], flat[j]["az"], flat[j]["low"]))
                           for j in members] for i in members])
        anchor = flat[members[int(np.argmin(costs.sum(axis=1)))]]['az']
        d = wrap([flat[t]['az'] - anchor for t in members])
        assert np.ptp(d) < 180 and not np.any(np.isclose(abs(d), 180)), 'unresolved circular position'
        return float(wrap(anchor + np.median(d)))

    rows = []
    for members in groups.values():
        assert len({flat[t]["annotator"] for t in members}) == len(members), "two observations by one annotator"
        rows.append(dict(members=members, az=median_az(members),
                         up=float(np.median([flat[t]["up"] for t in members])),
                         low=float(np.median([flat[t]["low"] for t in members])),
                         support=len(members)))
    rows.sort(key=lambda r: r["az"])
    for k, r in enumerate(rows, 1):
        r["id"] = k
        r["retained"] = bool(2 * r["support"] >= N_ANN)  # MV50, exact half retained
        r["truth"] = Counter(flat[t]["truth"] for t in r["members"]).most_common(1)[0][0]
    member_group = {t: r["id"] for r in rows for t in r["members"]}
    kept = sorted(r["id"] for r in rows if r["retained"])

    # source ring: an annotator's ring projected to the retained groups must cover each of them exactly once
    def canon(seq):
        opts = []
        for s in (seq, seq[::-1]):
            for k in range(len(s)):
                opts.append(tuple(s[k:] + s[:k]))
        return min(opts)

    candidates = Counter()
    for u, rows_u in enumerate(obs):
        seq = [member_group[index[(NAMES[u], k)]] for k in range(len(rows_u))]
        proj = [x for x in seq if x in kept]
        if sorted(proj) == kept:
            candidates[canon(proj)] += 1
    assert candidates, "no source ring covers the retained corners"
    ring = list(max(candidates.items(), key=lambda kv: (kv[1], [-x for x in kv[0]]))[0])
    return dict(flat=flat, index=index, matches=matches, groups=rows, ring=ring,
                ring_votes={" ".join(map(str, k)): v for k, v in candidates.items()}, kept=kept)


def floor_point(az, low):
    r = 1.0 / math.tan(math.radians(-low))
    return r * math.sin(math.radians(az)), r * math.cos(math.radians(az)), r


def layout(res):
    by = {g["id"]: g for g in res["groups"]}
    pts = []
    for i in res["ring"]:
        g = by[i]
        x, z, r = floor_point(g["az"], g["low"])
        pts.append(dict(id=i, x=x, z=z, top=r * math.tan(math.radians(g["up"]))))
    return pts


def simple_polygon(P):
    def inter(p1, p2, p3, p4):
        def o(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return o(p1, p2, p3) * o(p1, p2, p4) < 0 and o(p3, p4, p1) * o(p3, p4, p2) < 0
    n = len(P)
    for i in range(n):
        for j in range(i + 1, n):
            if abs(i - j) in (1, n - 1):
                continue
            if inter(P[i], P[(i + 1) % n], P[j], P[(j + 1) % n]):
                return False
    return True


def signature(res):
    return frozenset(frozenset((res["flat"][t]["annotator"], res["flat"][t]["truth"]) for t in g["members"])
                     for g in res["groups"])


# ----------------------------------------------------------------------------
# Drawing
# ----------------------------------------------------------------------------
BLUE, ORANGE, GRAY = '#0072B2', '#D55E00', '#93999E'

def draw(res, out):
    """Export computed geometry and qualitative median diagrams; captions belong to LaTeX."""
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'pdf.fonttype':42,
                         'svg.fonttype':'none','axes.linewidth':.6})
    flat, groups = res['flat'], res['groups']
    focus = next(g for g in groups if g['id']==5)
    extra = next(g for g in groups if g['truth']=='S')
    people = {'A1':BLUE, 'A2':'#009E73', 'A3':'#9566A9'}
    def save(fig,name):
        for ext in ['pdf','svg','png']: fig.savefig(out/(name+'.'+ext),dpi=360)
        plt.close(fig)
    def project(x,z,y): return np.array([x+.48*z,.48*z+1.5*y])
    def observation_point(o):
        x,z,r=floor_point(o['az'],o['low'])
        return x,z,r*math.tan(math.radians(o['up']))

    # Complete inputs establish where K is, without preassigned numeric corner IDs.
    fig=plt.figure(figsize=(2.5,1.85))
    for i,person in enumerate(NAMES):
        ax=fig.add_axes([.015+(i%3)*.33,.52-(i//3)*.49,.30,.43])
        obs=[o for o in flat if o['annotator']==person]
        xy=np.array([floor_point(o['az'],o['low'])[:2] for o in obs])
        ax.plot(*np.vstack([xy,xy[0]]).T,color=GRAY,lw=.9)
        recess=[j for j,o in enumerate(obs) if o['truth'].startswith('R')]
        if recess:
            ax.plot(*xy[recess].T,color=BLUE,lw=1.3)
            k=next(j for j,o in enumerate(obs) if o['truth']==focus['truth'])
            ax.plot(*xy[k],'o',ms=5,mfc='white',mec=ORANGE,mew=1)
            ax.annotate('K',xy[k],(3,5),textcoords='offset points',fontsize=7,color=ORANGE)
        if person in ('A5','A6'):
            k=next(j for j,o in enumerate(obs) if o['truth']=='S')
            ax.plot(*xy[k],'s',ms=4,mfc='white',mec=GRAY)
        ax.text(.02,.02,person,transform=ax.transAxes,fontsize=8,
                bbox=dict(facecolor='white',edgecolor='none',pad=.3))
        ax.set(xlim=(-3.1,3.1),ylim=(-2.4,3.5),aspect='equal');ax.axis('off')
    save(fig,'a_inputs')

    # Local walls from each submitted ring make the same corner physically recognizable.
    fig=plt.figure(figsize=(2.5,1.85))
    for i,person in enumerate(people):
        ax=fig.add_axes([.01+i*.33,.15,.32,.77])
        obs=[o for o in flat if o['annotator']==person]
        k=next(j for j,o in enumerate(obs) if o['truth']==focus['truth'])
        selected=[obs[(k-1)%len(obs)],obs[k],obs[(k+1)%len(obs)]]
        xyz=[observation_point(o) for o in selected]
        bottom=np.array([project(x,z,-1) for x,z,h in xyz])
        top=np.array([project(x,z,h) for x,z,h in xyz])
        center=(bottom[1]+top[1])/2
        bottom-=center;top-=center
        for j in [0,1]:
            ax.add_patch(Polygon([bottom[j],bottom[j+1],top[j+1],top[j]],
                                 fc='#F1F3F4',ec='#BBC0C4',lw=.6))
        ax.plot([bottom[1,0],top[1,0]],[bottom[1,1],top[1,1]],color=people[person],lw=1.7)
        for point in [bottom[1],top[1]]:
            ax.plot(*point,SHAPES[person],ms=5,mfc='white',mec=people[person],mew=1.2)
        ax.annotate('K',top[1],(3,7),textcoords='offset points',color=ORANGE,fontsize=8)
        ax.text(.5,-.08,person,transform=ax.transAxes,ha='center',color=people[person],fontsize=8)
        ax.set(xlim=(-1.3,1.8),ylim=(-2,2),aspect='equal');ax.axis('off')
    save(fig,'e_matching')

    # Layout columns explain absence; support bars share the half-team threshold.
    fig=plt.figure(figsize=(4.55,1.95))
    ax=fig.add_axes([.01,.11,.98,.87]);ax.set(xlim=(0,100),ylim=(0,100));ax.axis('off')
    rows=[('BL','W',BLUE,55),('R2','K',ORANGE,34),('S','E',GRAY,13)]
    xs=np.linspace(29,61,6)
    def footprint(person, x, y, w, h, focus_truth=None):
        local=ax.inset_axes([x/100,y/100,w/100,h/100])
        obs=[o for o in flat if o['annotator']==person]
        xy=np.array([floor_point(o['az'],o['low'])[:2] for o in obs])
        local.plot(*np.vstack([xy,xy[0]]).T,color=GRAY,lw=.7)
        for truth,tag,col,_ in rows:
            if focus_truth is not None and truth!=focus_truth:continue
            found=[i for i,o in enumerate(obs) if o['truth']==truth]
            if found:local.plot(*xy[found[0]],'o',ms=3,mfc='white',mec=col,mew=.8)
        local.set(xlim=(-3,3),ylim=(-2.3,3.4),aspect='equal');local.axis('off')
    ax.text(10,97,'Corner',ha='center',fontsize=7.5)
    for x,person in zip(xs,NAMES):
        ax.text(x,97,person,ha='center',fontsize=7.5)
        footprint(person,x-3,68,6,25)
    ax.text(79,97,'Support',ha='center',fontsize=7.5)
    ax.text(95,97,'Result',ha='center',fontsize=7.5)
    ax.text(79,79,'Keep ≥ 3 of 6',ha='center',fontsize=7.5)
    ax.plot([0,100],[66,66],color='#CBD1D5',lw=.6)
    ax.add_patch(Rectangle((0,23),100,22,fc='#FFF5ED',ec='none',zorder=-2))
    threshold=77.5
    ax.plot([threshold,threshold],[5,61],ls='--',color='#30373C',lw=.8,zorder=4)
    for truth,tag,col,y in rows:
        group=next(g for g in groups if g['truth']==truth)
        supporters={flat[t]['annotator'] for t in group['members']}
        assert len(supporters)==group['support']
        assert group['retained']==(2*len(supporters)>=len(NAMES))
        footprint('A5' if truth=='S' else 'A1',0,y-9,10,19,truth)
        label={'W':'Main wall','K':'Recess','E':'Extra detail'}[tag]
        ax.text(10,y+2,tag+'  '+label,fontsize=7,va='center',color=col)
        for x,person in zip(xs,NAMES):
            if person in supporters:
                ax.plot([x-.7,x-.15,x+.8],[y,y-1.5,y+2],color='#30373C',lw=1.1,solid_capstyle='round')
            else:ax.plot(x,y,'.',color='#C9CFD3',ms=2.5)
        ax.add_patch(Rectangle((68,y-2.5),19,5,fc='#EFF1F3',ec='none'))
        length=19*len(supporters)/len(NAMES)
        ax.add_patch(Rectangle((68,y-2.5),length,5,fc=col,ec='none'))
        ax.text(68+length+1,y,str(len(supporters)),fontsize=7.5,va='center')
        ax.text(93,y,'Keep' if group['retained'] else 'Omit',fontsize=7.5,va='center',color=col)
        if tag=='K':ax.text(77.5,y-8.5,'Exactly half: kept',ha='center',fontsize=6.8,color=col,
                            bbox=dict(fc='#FFF5ED',ec='none',pad=.2),zorder=5)
    fig.text(.02,.015,'✓ Drawn     · Not drawn      One vote per person and corner',fontsize=7.5)
    save(fig,'b_support')

    # Sorted coordinates communicate the median without a table of angle values.
    fig,ax=plt.subplots(figsize=(4.1,1.85));fig.subplots_adjust(left=.01,right=.99,bottom=.03,top=.97)
    members=[flat[t] for t in focus['members']]
    for key,yy,label in [('up',.78,'Upper elevation'),('az',.48,'Azimuth'),('low',.18,'Lower elevation')]:
        # Horizontal coordinates are unwrapped about the selected group's position.
        value=lambda o: float(wrap(o[key]-focus[key])) if key=='az' else o[key]
        ordered=sorted(members,key=value)
        vals=[value(o) for o in ordered]
        assert abs(np.median(vals)-(0 if key=='az' else focus[key]))<1e-9
        ax.text(.01,yy,label,ha='left',va='center',fontsize=8)
        ax.plot([.34,.60],[yy,yy],color='#C5CACF',lw=.8)
        for x,o in zip([.35,.47,.59],ordered):
            ax.plot(x,yy,SHAPES[o['annotator']],ms=6,mfc='white',mec=people[o['annotator']],mew=1.2)
            ax.text(x,yy-.11,o['annotator'],ha='center',fontsize=6.5,color=people[o['annotator']])
        ax.add_patch(FancyBboxPatch((.437,yy-.055),.066,.11,boxstyle='round,pad=.004,rounding_size=.01',
                                    fc='none',ec=ORANGE,lw=1))
        ax.annotate('',(.84,yy),(.64,yy),arrowprops=dict(arrowstyle='->',lw=.9,color=ORANGE))
    ax.text(.47,.97,'Sort each coordinate; take the middle',ha='center',fontsize=8)
    ax.plot([.87,.87],[.18,.78],color=ORANGE,lw=2)
    for yy in [.18,.78]:ax.plot(.87,yy,'o',ms=6,color=ORANGE)
    ax.text(.90,.80,'Upper',fontsize=7,va='center')
    ax.text(.90,.48,'Shared\nazimuth',fontsize=7,va='center')
    ax.text(.90,.18,'Lower',fontsize=7,va='center')
    ax.text(.87,.04,'New pair K',ha='center',fontsize=8,color=ORANGE)
    ax.set(xlim=(0,1.08),ylim=(-.03,1.05));ax.axis('off');save(fig,'c_position')

    # The same highlighted K returns to the complete layout, with computed local heights.
    pts=layout(res);fig,ax=plt.subplots(figsize=(2.25,1.85));fig.subplots_adjust(left=.01,right=.99,bottom=.01,top=.98)
    low=np.array([project(p['x'],p['z'],-1) for p in pts]);top=np.array([project(p['x'],p['z'],p['top']) for p in pts])
    by={g['id']:g for g in groups};ax.fill(*low.T,color='#F0F2F3',zorder=0)
    for j in range(len(pts)):
        k=(j+1)%len(pts)
        if by[pts[j]['id']]['truth'].startswith('R') and by[pts[k]['id']]['truth'].startswith('R'):
            ax.add_patch(Polygon([low[j],low[k],top[k],top[j]],fc=BLUE,alpha=.12,ec='none'))
    for ring in [low,top]:ax.plot(*np.vstack([ring,ring[0]]).T,color='#626A70',lw=.9)
    for p,b,t in zip(pts,low,top):
        col=ORANGE if p['id']==focus['id'] else BLUE if by[p['id']]['truth'].startswith('R') else GRAY
        ax.plot([b[0],t[0]],[b[1],t[1]],color=col,lw=1.5)
        if p['id']==focus['id']:
            for xy in [b,t]:ax.plot(*xy,'o',color=ORANGE,ms=4)
            ax.annotate('K',t,(2,6),textcoords='offset points',color=ORANGE,fontsize=9)
    ax.set_aspect('equal');ax.margins(.15);ax.axis('off');save(fig,'d_layout')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    obs = simulate()
    res = run_pipeline(obs, G_SKIP)

    # sanity: every group is one true corner, one group per true corner, S is the only dropped group
    labels = [g["truth"] for g in res["groups"]]
    assert sorted(labels) == sorted(TRUE), labels
    for g in res["groups"]:
        assert {res["flat"][t]["truth"] for t in g["members"]} == {g["truth"]}
    assert [g["truth"] for g in res["groups"] if not g["retained"]] == ["S"]
    L = layout(res)
    valid = simple_polygon([(p["x"], p["z"]) for p in L]) and all(p["top"] > 0 for p in L)
    assert valid, "connected layout is not valid"
    draw(res, args.out)
    trace = dict(
        note="Illustrative synthetic example; outputs computed by the method, not drawn by hand.",
        seed=SEED, skip_penalty_deg=G_SKIP, annotators=ANNOTATORS, observations=[
            {k: (round(v, 4) if isinstance(v, float) else v) for k, v in o.items()} for o in res["flat"]],
        pair_matches=res["matches"],
        groups=[dict(id=g["id"], truth=g["truth"], support=g["support"], retained=g["retained"],
                     members=[[res["flat"][t]["annotator"], res["flat"][t]["truth"]] for t in g["members"]],
                     az=round(g["az"], 3), upper_elev=round(g["up"], 3), lower_elev=round(g["low"], 3))
                for g in res["groups"]],
        source_ring=res["ring"], source_ring_votes=res["ring_votes"], retained_ids=res["kept"],
        layout=[{k: round(v, 4) if isinstance(v, float) else v for k, v in p.items()} for p in L],
        layout_valid=valid)
    (args.out / "consensus_method_illustration_trace.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    print("groups:", [(g["id"], g["truth"], g["support"], g["retained"]) for g in res["groups"]])
    print("source ring:", res["ring"], res["ring_votes"])
    print("written to", args.out)


if __name__ == "__main__":
    main()
