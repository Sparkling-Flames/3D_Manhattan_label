"""Inspect one current grouping case; never modify the human review answers."""
from pathlib import Path
import gzip
import json
import zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from tools.thesis_main.analysis.ring_correspondence_20261007 import cyclic_match
from tools.thesis_main.analysis.paired_split_research.study import angular
from tools.label_studio.panorama_studio.geometry import pixel_ray

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/fusion/formal_identity_review_20261117'
OUT = BASE / 'case_VFuaQ6m2Qom-01'


def main():
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/gap75_evidence_20261117.zip') as z:
        name = next(n for n in z.namelist() if '/states/VFuaQ6m2Qom-01__manual' in n)
        d = json.loads(gzip.decompress(z.read(name)))
    nodes, state = d['nodes'], d['states']['7.5']
    p = np.array([n['points'] for n in nodes])
    top = angular(p[:, 0]-.5, p[:, 0]-.5)
    bottom = angular(p[:, 1]-.5, p[:, 1]-.5)
    cost = (top + bottom)/2
    groups = {'G3': state['groups'][2], 'G20': state['groups'][19]}
    edges = {tuple(sorted(e)) for e in state['pairwise_match_edges']}
    records = {n['id']: [i for i, o in enumerate(nodes) if o['id'] == n['id']] for n in nodes}
    # Recompute all 100 cross-group pair decisions using the current original DP.
    for a in groups['G3']:
        for b in groups['G20']:
            aa, bb = records[nodes[a]['id']], records[nodes[b]['id']]
            matched = cyclic_match(cost[np.ix_(aa, bb)], gap=7.5)['matches']
            linked = [aa.index(a), bb.index(b)] in matched
            assert linked == (tuple(sorted((a, b))) in edges)
    stats, xyz = {}, {}
    for label, indices in groups.items():
        q = p[indices]
        rho = 1/np.tan(np.pi*(q[:, 1, 1]/512-.5))
        upper = -rho*np.tan(np.pi*(q[:, 0, 1]/512-.5))
        theta = 2*np.pi*(q[:, 1, 0]/1024-.5)
        floor = np.array([rho*np.sin(theta), -rho*np.cos(theta), np.full(len(q), -1.)]).T
        # Match the reconstruction engine: same continuous pixel convention, floor y=-1.
        for row, f in zip(q, floor):
            ray = pixel_ray(*row[1], 1024, 512, coordinate_convention='continuous')
            expected = -ray/ray[1]
            assert np.allclose(f, expected[[0, 2, 1]])
        xyz[label] = (floor, upper)
        stats[label] = dict(n=len(q), workers=[nodes[i]['worker'] for i in indices],
            center_median=np.median(q, axis=0).tolist(), bottom_y_range=[float(q[:,1,1].min()),float(q[:,1,1].max())],
            radial_distance_median=float(np.median(rho)), radial_distance_range=[float(rho.min()),float(rho.max())],
            local_height_median=float(np.median(upper+1)))
    g3, g20 = groups.values()
    cross = cost[np.ix_(g3, g20)]
    missing = []
    for a in g3:
        for b in g20:
            if tuple(sorted((a,b))) not in edges:
                alternative = [i for i in records[nodes[a]['id']] if tuple(sorted((b,i))) in edges]
                missing.append(dict(g3_worker=nodes[a]['worker'],g20_worker=nodes[b]['worker'],
                    alternative_in_g3_record=[nodes[i] for i in alternative]))
    stats.update(cross_pairs=100,cross_pairs_matched=100-len(missing),missing_matches=missing,
        cross_mean_angle_min_median_max=[float(cross.min()),float(np.median(cross)),float(cross.max())],
        merged29_coordinate_median=np.median(p[g3+g20],axis=0).tolist(),
        geometry_unit='camera height = 1; not measured metres', original_dp_pairs_recomputed=100)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'SUMMARY.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    data=json.loads((BASE/'reviewer/data.js').read_text(encoding='utf-8').removeprefix('const REVIEW_DATA = ').strip().removesuffix(';'))
    scene=next(s for s in data['scenes'] if s['code']=='VFuaQ6m2Qom-01')
    image=np.asarray(Image.open(BASE/'reviewer'/scene['image']))
    colors={'G3':'#007aa6','G20':'#d84927'}
    fig=plt.figure(figsize=(12,5.2));ax=fig.add_subplot(121);ax3=fig.add_subplot(122,projection='3d')
    ax.imshow(image,extent=[0,1024,512,0]);ax.set_xlim(620,745);ax.set_ylim(385,150)
    for label,indices in groups.items():
        c=colors[label]
        for pair in p[indices]:ax.plot(pair[:,0],pair[:,1],color=c,alpha=.35,lw=.8)
        med=np.median(p[indices],axis=0);ax.plot(med[:,0],med[:,1],'-o',color=c,lw=2.5,label=f'{label}: n={len(indices)}')
        ax.scatter(p[indices,1,0],p[indices,1,1],color=c,s=15)
        floor,upper=xyz[label]
        for f,h in zip(floor,upper):ax3.plot([f[0],f[0]],[f[1],f[1]],[-1,h],color=c,alpha=.5,lw=1)
        ax3.scatter(floor[:,0],floor[:,1],floor[:,2],color=c,s=24,label=label)
    ax.legend(loc='upper left');ax.set_xlabel('Panorama x (1024-pixel basis)');ax.set_ylabel('Panorama y (512-pixel basis)')
    ax.set_title('(a) Same azimuth region, distinct lower endpoints')
    ax3.scatter([0],[0],[0],color='black',marker='^',s=40,label='Camera')
    ax3.set_xlabel('X / camera height');ax3.set_ylabel('Z / camera height');ax3.set_zlabel('Y / camera height');ax3.view_init(elev=22,azim=-65)
    ax3.set_title('(b) Point-pair projections (floor Y = -1)');ax3.legend(loc='upper left')
    fig.suptitle('VFuaQ6m2Qom-01 | G3 vs G20',fontsize=15,fontweight='bold')
    fig.tight_layout();fig.savefig(OUT/'G3_G20_comparison.png',dpi=180);plt.close(fig)
    print(json.dumps({k:v for k,v in stats.items() if k!='missing_matches'},ensure_ascii=False))


if __name__=='__main__':
    main()
