"""复用57池积分基底，连接原作答分歧、人数曲线与实际全员终点。"""
import csv
import json
from pathlib import Path

import numpy as np

from .worker_count_metrics_20261006 import area_summary

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'analysis_results/worker_count_composition_20261006'
OUT = ROOT / 'analysis_results/consensus_response_20261006'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def raw_distances(patterns, area, n):
    votes = (patterns[None, :] & (1 << np.arange(n, dtype=np.uint32))[:, None]) != 0
    distances = np.array([(votes != person) @ area / area.sum() for person in votes])
    return votes, distances


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads((SOURCE/'input.json').read_text(encoding='utf-8'))
    groups = [g for g in data['groups'] if g['status'] == 'selected']
    bases = np.load(SOURCE/'integration_bases.npz')
    existing = read_csv(SOURCE/'per_image.csv')
    curves = [r for r in existing if r['scenario'] == 'uniform']
    inventory = json.loads((ROOT/'analysis_results/review_source_audit_20261004/corrected_inventory/input.json').read_text(encoding='utf-8'))
    labels = {r['image']: r for r in inventory['images']}
    labels.update({r['image']: r for r in read_csv(ROOT/'analysis_results/difficulty_consensus_20261006/updated/difficulty_roster.csv')})
    common = set(json.loads((ROOT/'analysis_results/worker_profiles_20261003/block.json').read_text(encoding='utf-8'))['images'])
    people, pairs, ends, checks = [], [], [], []
    for ix, g in enumerate(groups):
        key = f'g{ix}'
        area, patterns = bases[key+'_area'], bases[key+'_patterns']
        n = len(g['records'])
        votes, distance = raw_distances(patterns, area, n)
        raw_r = float(distance[np.triu_indices(n, 1)].mean())
        ident = dict(image=g['image'], condition=g['condition'], n=n,
                     difficulty=labels[g['image']]['difficulty'], basis_key=key)
        for a in range(n):
            for b in range(a+1, n):
                pairs.append(dict(**ident, worker_a=g['records'][a]['worker'], worker_b=g['records'][b]['worker'],
                                  distance_union=float(distance[a,b]), distance_h2=float(distance[a,b]*area.sum())))
        relevant = [r for r in curves if r['basis_key'] == key]
        versions = sorted({r['version'] for r in relevant})
        by_version = {}
        for v in versions:
            individual = []
            for r, vote in zip(g['records'], votes):
                measured = area_summary(area, bases[key+'_'+v+'_overlap'], float(bases[key+'_'+v+'_area']), vote)
                individual.append(measured['ref_symdiff_ref'])
                people.append(dict(**ident, worker=r['worker'], record=r['id'], version=v,
                                   omission_ref=measured['omission_ref'], extension_ref=measured['extension_ref'],
                                   ref_symdiff_ref=measured['ref_symdiff_ref']))
            by_version[v] = individual
        for r in relevant:
            if int(r['k']) == 1:
                checks.append(abs(raw_r - n/(n-1)*float(r['member_symdiff_union'])))
                checks.append(abs(np.mean(by_version[r['version']])-float(r['ref_symdiff_ref'])))
            if int(r['k']) == n:
                ends.append(dict(**ident, method=r['method'], version=r['version'], union_area_h2=float(area.sum()),
                    raw_pairwise_union=raw_r, individual_mean_error_ref=float(np.mean(by_version[r['version']])),
                    individual_median_error_ref=float(np.median(by_version[r['version']])),
                    all_error_ref=float(r['ref_symdiff_ref']), all_omission_ref=float(r['omission_ref']),
                    all_extension_ref=float(r['extension_ref']), all_minus_individual_mean=float(r['ref_symdiff_ref'])-np.mean(by_version[r['version']])) )
    assert max(checks) < 1e-10, max(checks)
    write_csv(OUT/'all_pool_summary.csv', ends)
    write_csv(OUT/'individual_reference.csv', people)
    write_csv(OUT/'pairwise_distances.csv', pairs)
    write_csv(OUT/'uniform_curves.csv', curves)
    # Restore each full-pool output once; count/composition probabilities stay cached.
    from .lee_tile_stage1_20261002 import tile_consensus
    from shapely.geometry import mapping, Polygon
    features, geometry_checks, notices = [], [], []
    endpoint_lookup={(r['image'],r['condition'],r['method'],r['version']):r for r in ends}
    for g in groups:
        result = tile_consensus(g['records'])
        notices.extend(dict(image=g['image'],condition=g['condition'],message=w) for w in result['warnings'])
        for method, geometry in result['regions'].items():
            features.append(dict(type='Feature', geometry=mapping(geometry), properties=dict(
                image=g['image'], condition=g['condition'], method=method, n=len(g['records']), workers=[r['worker'] for r in g['records']],
                records=[r['id'] for r in g['records']], output_type='BEV_region_only')))
            for r in g['references']:
                if r['footprint'] is None: continue
                ref=Polygon(r['footprint'])
                expected=endpoint_lookup[g['image'],g['condition'],method,r['version']]['all_error_ref']
                geometry_checks.append(abs(geometry.symmetric_difference(ref).area/ref.area-expected))
    assert max(geometry_checks)<1e-10, max(geometry_checks)
    (OUT/'all_pool_consensus.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features)),encoding='utf-8')
    common_features=[f for f in features if f['properties']['image'] in common and f['properties']['condition']=='manual']
    (OUT/'common10_all_consensus.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=common_features)), encoding='utf-8')
    (OUT/'field_contract.json').write_text(json.dumps(dict(schema='consensus_response_v2', source=str(SOURCE.relative_to(ROOT)),
        pairwise_distances='每图每条件不重复人员对；固定全员并集面积归一化，distance_h2为未归一化面积',
        individual_reference='每份作答、每版参考；对称差/参考面积=遗漏+外扩，不是1-IoU',
        all_pool_summary='全员终点，原/修参考及两规则分别列；R和单人误差重复用于同条件比较，非独立新样本',
        uniform_curves='复用原实验uniform行；期望误差，不是每组结果的分位数',
        geometry='57池两规则共114份全员底面；common10保留十图子集；按image+condition+method识别，无顶面输出',
        checks=dict(max_identity_error=max(checks),max_geometry_endpoint_error=max(geometry_checks)),
        geometry_warnings=notices,pool_n=len(groups)), ensure_ascii=False, indent=2),encoding='utf-8')
    plot(groups, common, curves, common_features)
    atlas(groups,features)
    raw_plot(groups,common,pairs,people)
    print(json.dumps(dict(pools=len(groups), summary_rows=len(ends), people_rows=len(people), pairs=len(pairs),
                         geometries=len(features), max_identity_error=max(checks))))


def plot(groups, common, curves, features):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from shapely.geometry import Polygon, shape
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    panel = [g for g in groups if g['condition']=='manual' and g['image'] in common]
    fig, axes = plt.subplots(5,2,figsize=(12,17))
    for ax,g in zip(axes.flat,panel):
        for method,color in [('mv50','#196a9b'),('mv_strict','#bf672b')]:
            rows=[r for r in curves if r['image']==g['image'] and r['condition']=='manual' and r['version']=='original' and r['method']==method]
            ax.plot([int(r['k']) for r in rows],[float(r['ref_symdiff_ref']) for r in rows],label=method,color=color)
            ax.scatter(int(rows[-1]['k']),float(rows[-1]['ref_symdiff_ref']),color=color,s=35)
        ax.set(title=g['image'],xlabel='人数（末点为实际全员）',ylabel='期望范围差 / 原GT面积')
        ax.grid(alpha=.2); ax.legend()
    fig.tight_layout(); fig.savefig(OUT/'common10_reference_curves.png',dpi=140); plt.close(fig)
    fig, axes = plt.subplots(5,2,figsize=(12,19))
    for ax,g in zip(axes.flat,panel):
        for r in g['records']:
            xy=np.array(r['footprint']); ax.plot(*np.vstack([xy,xy[0]]).T,color='#bbbbbb',alpha=.35,linewidth=.5)
        layers=[('原GT',Polygon(next(r for r in g['references'] if r['version']=='original')['footprint']),'#222222')]
        layers += [(f['properties']['method'],shape(f['geometry']), '#196a9b' if f['properties']['method']=='mv50' else '#bf672b') for f in features if f['properties']['image']==g['image']]
        for label,geometry,color in layers:
            for ix,p in enumerate([geometry] if geometry.geom_type=='Polygon' else geometry.geoms):
                ax.plot(*p.exterior.xy,color=color,label=label if ix==0 else None)
                for hole in p.interiors: ax.plot(*hole.xy,color=color,linestyle=':')
        ax.set_title(g['image']+' 全员24人'); ax.set_aspect('equal'); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(OUT/'common10_all_consensus.png',dpi=140); plt.close(fig)


def atlas(groups,features):
    import matplotlib.pyplot as plt
    from shapely.geometry import Polygon,shape
    pages=[]
    for start in range(0,len(groups),6):
        batch=groups[start:start+6]
        nrows=(len(batch)+1)//2
        fig,axes=plt.subplots(nrows,2,figsize=(12,5*nrows),squeeze=False)
        for ax,g in zip(axes.flat,batch):
            for r in g['records']:
                xy=np.array(r['footprint']); ax.plot(*np.vstack([xy,xy[0]]).T,color='#bbbbbb',alpha=.35,linewidth=.5)
            layers=[(r['version'],Polygon(r['footprint']),'#222222' if r['version']=='original' else '#9d418a') for r in g['references'] if r['footprint'] is not None]
            layers += [(f['properties']['method'],shape(f['geometry']),'#196a9b' if f['properties']['method']=='mv50' else '#bf672b') for f in features if f['properties']['image']==g['image'] and f['properties']['condition']==g['condition']]
            for label,geometry,color in layers:
                if geometry.is_empty: continue
                for ix,p in enumerate([geometry] if geometry.geom_type=='Polygon' else geometry.geoms):
                    ax.plot(*p.exterior.xy,color=color,label=label if ix==0 else None)
                    for hole in p.interiors: ax.plot(*hole.xy,color=color,linestyle=':')
            ax.set_title(f"{g['image']} · {g['condition']} · N={len(g['records'])}")
            ax.set_aspect('equal'); ax.legend(fontsize=7)
        for ax in list(axes.flat)[len(batch):]: ax.set_visible(False)
        name=f'all_pool_atlas_{start//6+1:02}.png'; pages.append((name,batch))
        fig.tight_layout(); fig.savefig(OUT/name,dpi=130); plt.close(fig)
    lines=['# 57个人员池：实际全员范围图集','',
           '灰线为当前完整池原作答；黑色原GT、紫色已有修订GT；蓝／橙为两投票规则。每图坐标单位h，各自轴范围不同；仅底面，不含上界。','']
    for name,batch in pages:
        lines += [', '.join(f"{g['image']} ({g['condition']})" for g in batch),'',f'![全员范围]({name})','']
    (OUT/'ATLAS.md').write_text('\n'.join(lines),encoding='utf-8')


def raw_plot(groups,common,pairs,people):
    import matplotlib.pyplot as plt
    panel=[g for g in groups if g['condition']=='manual' and g['image'] in common]
    fig,axes=plt.subplots(5,2,figsize=(12,19),layout='constrained')
    for ax,g in zip(axes.flat,panel):
        workers=[r['worker'] for r in g['records']]; idx={w:i for i,w in enumerate(workers)}; d=np.zeros((len(workers),len(workers)))
        for r in pairs:
            if r['image']==g['image'] and r['condition']=='manual':
                a,b=idx[r['worker_a']],idx[r['worker_b']]; d[a,b]=d[b,a]=r['distance_union']
        im=ax.imshow(d,vmin=0,vmax=1,cmap='viridis'); ax.set_title(g['image'])
        ax.set_xticks(range(0,24,3),[workers[j] for j in range(0,24,3)],rotation=45,fontsize=7)
        ax.set_yticks(range(0,24,3),[workers[j] for j in range(0,24,3)],fontsize=7)
    fig.colorbar(im,ax=axes.ravel().tolist(),shrink=.5,label='两人范围差 / 固定全池并集')
    fig.savefig(OUT/'common10_pairwise.png',dpi=130); plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,6))
    values=[[r['ref_symdiff_ref'] for r in people if r['image']==g['image'] and r['condition']=='manual' and r['version']=='original'] for g in panel]
    ax.boxplot(values,showfliers=True)
    ax.set_xticks(range(1,len(panel)+1),[g['image'] for g in panel],rotation=35,ha='right')
    ax.set_ylabel('单人范围差 / 原GT面积'); ax.set_title('共同24人：逐图原作答参考误差分布（保留离群值）')
    fig.tight_layout(); fig.savefig(OUT/'common10_individual_reference.png',dpi=150); plt.close(fig)


if __name__ == '__main__':
    run()
