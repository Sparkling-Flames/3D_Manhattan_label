"""Render exact neighboring prefixes on the same original-image crop."""
import sys, os, io
sys.path.insert(0, '/tmp/hohonet_deps')
from build_cases import OUT, read, atomic, np, pd, curve3d
os.environ['MPLCONFIGDIR'] = str(OUT/'.mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib import patheffects

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
CASES = [
    ('UwV83HsGsw3-12', 4, [3, 4, 5, 6], (0, 205), 'Entry wall return',
     [('More turns', 'M3.1'), ('Regular', 'M2.1')]),
    ('uNb9QFRL6hY-60', 8, [8, 9, 10, 11], (780, 1024),
     'Reference corner beside the shower / wall boundary',
     [('More turns', 'M3.1'), ('Regular', 'M2.1'), ('Simplifying', 'M1.1')]),
]
for image, corner, ks, xlim, semantic, support in CASES:
    folder = OUT/image
    obj = read(folder/'CASE_GEOMETRY.json.gz')
    path = pd.read_csv(folder/'PATH_SCALARS.csv')
    path = path[path.path_id.eq(obj['case']['path_id'])].set_index('k')
    votes = pd.read_csv(folder/'CASE_VOTES.csv')
    votes = votes[votes.reference_corner.eq(corner)].set_index('k')
    local = pd.read_csv(folder/'CLASS_LOCAL_SUPPORT.csv')
    local = local[local.method.eq('V3_BEHAVIOR') & local.reference_corner.eq(corner)].set_index('fine_label')
    support = [(name, int(local.loc[lab,'class_supporting_n']),
                int(local.loc[lab,'class_available_n'])) for name,lab in support]
    ref = obj['pool']['reference']['points_1024x512']
    orig = plt.imread(OUT/'originals'/(image+'.png'))
    pair = np.asarray(ref).reshape(-1, 2, 2)[corner-1]
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 4, height_ratios=[2.25, 1], left=.05,
        right=.98, top=.87, bottom=.14, hspace=.34, wspace=.38)
    used_votes, needs = [], []
    for col, k in enumerate(ks):
        ax = fig.add_subplot(gs[0, col])
        state = obj['states'][str(k)]
        color = '#0072b2' if votes.loc[k, 'selected'] else '#d55e00'
        ax.imshow(orig, extent=[0, 1024, 512, 0])
        for pp, co, ls, lw in [(ref, '#171717', '--', 1.6),
                (state['candidate']['points'], color, '-', 2.3)]:
            for top in [False, True]:
                for q in curve3d(pp, top):
                    ax.plot(q[:, 0], q[:, 1], color=co, ls=ls, lw=lw,
                        path_effects=[patheffects.Stroke(linewidth=lw+1,
                            foreground='white', alpha=.8), patheffects.Normal()])
            for pr in np.array(pp).reshape(-1, 2, 2):
                ax.plot(pr[:, 0], pr[:, 1], color=co, ls=ls, lw=lw*.6)
        # The reference pair is the same fixed visible position in every panel.
        ax.scatter(pair[:, 0], pair[:, 1], s=70, facecolors='none',
            edgecolors='#ad1457', linewidths=2.0, zorder=10)
        ax.text(pair[0, 0]+9, 255, 'R'+str(corner), color='#ad1457',
            fontsize=14, weight='bold',
            path_effects=[patheffects.withStroke(linewidth=3, foreground='white')])
        ax.set_xlim(*xlim); ax.set_ylim(512, 0)
        ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect('equal')
        vote, need = int(votes.loc[k, 'support']), int(votes.loc[k, 'threshold'])
        used_votes.append(vote); needs.append(need)
        prev = set(path.loc[k-1, 'member_workers'].split('|')) if k-1 in path.index else set()
        added = sorted(set(path.loc[k, 'member_workers'].split('|'))-prev)
        assert len(added)==1 and len(set(path.loc[k,'member_workers'].split('|')))==k
        entry_text = 'Initial 3-person prefix' if k==3 else 'Added '+', '.join(added)
        ax.set_title(f'n={k}: {vote} '+('vote' if vote==1 else 'votes')+f' / need {need}\nQ={path.loc[k,"B8L2"]:.2f}; '
            + ('selected' if votes.loc[k, 'selected'] else 'omitted')
            + '\n'+entry_text, fontsize=12, color=color)
    va = fig.add_subplot(gs[1, :2])
    xx = np.arange(len(ks))
    bars = va.bar(xx, used_votes, width=.58, color=['#0072b2' if v>=t else '#d55e00'
        for v, t in zip(used_votes, needs)])
    va.plot(xx, needs, color='#303030', marker='o', ls='--', lw=1.8, label='Required votes')
    for bar, v in zip(bars, used_votes):
        va.text(bar.get_x()+bar.get_width()/2, v+.13, str(v), ha='center')
    va.set_xticks(xx, [f'n={k}' for k in ks]); va.set_ylabel('Votes for the same local corner')
    va.set_ylim(0, max(needs)+1.6); va.legend(loc='upper left', frameon=False)
    va.set_title('Same source observations remain in the same groups')
    va.grid(axis='y', alpha=.2)
    ca = fig.add_subplot(gs[1, 2:])
    names = [a for a, _, _ in support]
    vals = [b/c for a,b,c in support]
    yy = np.arange(len(support))
    ca.barh(yy, vals, color=['#0072b2', '#8a8a8a', '#b5b5b5'][:len(vals)])
    for y,(lab,a,b) in zip(yy,support):
        ca.text(a/b+.025, y, f'{a}/{b}', va='center', fontsize=12)
    ca.set_yticks(yy, names); ca.set_xlim(0, 1.16); ca.invert_yaxis()
    ca.set_xlabel('Actual full-pool members supporting this corner')
    ca.set_title('Historical structure class formed outside this building')
    ca.grid(axis='x', alpha=.15)
    fig.suptitle(f'{image} | R{corner}: vote support and the changing threshold',
        fontsize=19, x=.05, ha='left', y=.975)
    fig.text(.05, .935, semantic+'.  Original image and reference stay fixed across prefixes.', fontsize=12)
    fig.legend(handles=[Line2D([0],[0],color='#171717',ls='--',label='Adopted reference'),
        Line2D([0],[0],color='#0072b2',label='Fused output: local corner selected'),
        Line2D([0],[0],color='#d55e00',label='Fused output: local corner omitted')],
        loc='lower center', bbox_to_anchor=(.5,.04), ncol=3, fontsize=11, frameon=False)
    fig.text(.05,.012,'Exploratory exact-order mechanism; full-pool class fractions describe this local opportunity, not every corner or every image.',fontsize=10,color='#444444')
    buf=io.BytesIO();fig.savefig(buf,format='png',dpi=160,facecolor='white')
    atomic(folder/'KEY_CORNER_THRESHOLD_SEQUENCE.png',buf.getvalue());plt.close(fig)
    print('Saved threshold sequence '+image, flush=True)
