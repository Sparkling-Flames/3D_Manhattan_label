"""难度×人数：固定面板的起点、区间变化、全员残留；可标门洞扩展，OOS单列。"""
import json
from collections import defaultdict
from statistics import mean, median

import numpy as np
from shapely.geometry import Polygon, shape

from .consensus_response_20261006 import ROOT, read_csv, write_csv
from .lee_tile_precision_20261003 import integration_basis
from .worker_count_composition_20261006 import probabilities
from .worker_count_metrics_20261006 import area_summary

OUT=ROOT/'analysis_results/difficulty_consensus_20261006/trajectory'
PRO=ROOT/'research/pro_parallel_return_20261006/pro_original'
LABELS=('简单','中等','困难')


def in_panel(scene, include_door):
    return scene in ('clear','unflagged') or (include_door and scene=='doorway_annotatable')


def trajectory(curve):
    n=max(curve)
    result={f'D{k}':curve[k]['D'] if k in curve else None for k in (1,4,8,16,20,24)}
    result.update(n=n,D_all=curve[n]['D'])
    for a,b in ((1,4),(4,8),(8,16),(16,20)):
        result[f'gain_{a}_{b}']=curve[a]['D']-curve[b]['D'] if b in curve else None
    return result


def run():
    previous=ROOT/'analysis_results/difficulty_consensus_20261006'
    meta={r['image']:r for r in read_csv(previous/'updated/difficulty_roster.csv')}
    meta.update({r['image']:r for r in read_csv(previous/'special_scenes.csv')})
    curves={}
    for r in read_csv(ROOT/'analysis_results/lee_expanded_20261003/image_curves.csv'):
        if r['condition']!='manual' or r['version']!='original': continue
        curves[r['image'],r['method'],r['version'],int(r['k'])]=dict(image=r['image'],method=r['method'],version=r['version'],k=int(r['k']),n=int(r['n']),
            O=float(r['omission_fraction']),E=float(r['extension_fraction']),D=float(r['omission_fraction'])+float(r['extension_fraction']),V=None,source='existing_expanded')
    for r in read_csv(ROOT/'analysis_results/worker_count_composition_20261006/per_image.csv'):
        if r['condition']!='manual' or r['scenario']!='uniform' or r['policy']!='none': continue
        curves[r['image'],r['method'],r['version'],int(r['k'])]=dict(image=r['image'],method=r['method'],version=r['version'],k=int(r['k']),n=int(r['n']),
            O=float(r['omission_ref']),E=float(r['extension_ref']),D=float(r['ref_symdiff_ref']),V=float(r['member_symdiff_union']),source='existing_high_count')
    cases=json.loads((PRO/'inputs/cases.json').read_text(encoding='utf-8'))['images']
    saved=json.loads((PRO/'results/full_consensus.geojson').read_text(encoding='utf-8'))['features']
    special=('uNb9QFRL6hY-47','jtcxE69GiFV-12','x8F5xyUWy9e-01','x8F5xyUWy9e-09')
    sources=[]; checks=[]
    for im in cases:
        code=im['code']
        if code not in special: continue
        gate='stable_nonorthogonal_separate' if code.startswith('x8F') else 'main_candidate'
        records=[r for r in im['annotations'] if r['independent'] and r['consensus_eligible'] and r['condition']=='manual' and r['main_consensus_gate']['status']==gate]
        refs={r['version']:r['footprint'] for r in im['references']}
        basis=integration_basis(records,refs); n=len(records)
        sources.append(dict(image=code,n=n,records=[r['id'] for r in records],workers=[r['worker'] for r in records],gate=gate,warnings=basis['warnings']))
        for method in ('mv50','mv_strict'):
            for k in range(1,n+1):
                q=probabilities(basis['patterns'],((1<<n)-1,),(n,),(k,),method)
                for version,g in basis['references'].items():
                    m=area_summary(basis['area'],basis['overlap'][version],g.area,q)
                    row=dict(image=code,method=method,version=version,k=k,n=n,O=m['omission_ref'],E=m['extension_ref'],D=m['ref_symdiff_ref'],V=m['member_symdiff_union'],source='new_special_count')
                    curves[code,method,version,k]=row
                    if k==1:
                        checks.append(abs(row['D']-mean(Polygon(r['footprint']).symmetric_difference(g).area/g.area for r in records)))
                    if k==n:
                        f=next(f for f in saved if f['properties']['image']==code and f['properties']['method']==method)
                        checks.append(abs(row['D']-shape(f['geometry']).symmetric_difference(g).area/g.area))
                        assert row['V']<1e-12
    assert max(checks)<1e-10,max(checks)
    kept=[dict(r,difficulty=meta[r['image']]['difficulty'],scene=meta[r['image']]['scene'],building=meta[r['image']]['building']) for r in curves.values() if r['image'] in meta]
    grouped=defaultdict(dict)
    for r in kept: grouped[r['image'],r['method'],r['version']][r['k']]=r
    per=[]
    for key,c in sorted(grouped.items()):
        r=c[1]; assert len(c)==max(c),(key,len(c),max(c))
        per.append(dict(image=key[0],method=key[1],version=key[2],difficulty=r['difficulty'],scene=r['scene'],building=r['building'],**trajectory(c)))
    common=set(json.loads((ROOT/'analysis_results/worker_profiles_20261003/block.json').read_text(encoding='utf-8'))['images'])
    summary=[]
    for panel,limit in [('n8',8),('n16',16),('n20',20),('common10',24)]:
        for include in (False,True):
            if panel=='common10' and include: continue
            eligible={r['image'] for r in per if r['version']=='original' and r['n']>=limit and r['difficulty'] in LABELS and in_panel(r['scene'],include) and (panel!='common10' or r['image'] in common)}
            for policy in ('original','revised_where_available'):
                for method in ('mv50','mv_strict'):
                    for label in LABELS:
                        ims=sorted(i for i in eligible if meta[i]['difficulty']==label)
                        for k in range(1,limit+1):
                            selected=[]
                            for i in ims:
                                v='manual_revision' if policy!='original' and (i,method,'manual_revision') in grouped else 'original'
                                selected.append(grouped[i,method,v][k])
                            buildings=defaultdict(list)
                            for r in selected: buildings[r['building']].append(r['D'])
                            summary.append(dict(panel=panel,include_door=include,evaluation=policy,method=method,difficulty=label,k=k,image_n=len(ims),building_n=len(buildings),
                                D=mean(r['D'] for r in selected),median_D=median(r['D'] for r in selected),building_D=mean(mean(x) for x in buildings.values()),
                                O=mean(r['O'] for r in selected),E=mean(r['E'] for r in selected),images='|'.join(ims)))
    intervals=[]
    batches=defaultdict(dict)
    for r in summary:
        batches[tuple(r[k] for k in ('panel','include_door','evaluation','method','difficulty'))][r['k']]=r
    for key,c in batches.items():
        for a,b in ((1,4),(4,8),(8,16),(16,20),(9,17)):
            if b not in c: continue
            gains=[]
            for im in c[a]['images'].split('|'):
                v='manual_revision' if key[2]!='original' and (im,key[3],'manual_revision') in grouped else 'original'
                ic=grouped[im,key[3],v]
                gains.append(ic[a]['D']-ic[b]['D'])
            intervals.append(dict(zip(('panel','include_door','evaluation','method','difficulty'),key),
                start_k=a,end_k=b,image_n=len(gains),start_D=c[a]['D'],end_D=c[b]['D'],mean_gain=mean(gains),
                median_gain=median(gains),building_gain=c[a]['building_D']-c[b]['building_D'],
                improved_n=sum(g>1e-12 for g in gains),worsened_n=sum(g < -1e-12 for g in gains),images=c[a]['images']))
    OUT.mkdir(parents=True,exist_ok=True)
    write_csv(OUT/'per_image.csv',per); write_csv(OUT/'curves.csv',kept); write_csv(OUT/'summary.csv',summary)
    write_csv(OUT/'intervals.csv',intervals)
    (OUT/'field_contract.json').write_text(json.dumps(dict(schema='difficulty_trajectory_v1',date='2026-10-07',
        input='Existing preprocessed rosters and derived curves; new geometry/count only for four frozen Pro cases. Same source coordinates, pool and thresholds.',
        definitions='D=O+E=expected symmetric difference/GT area; gains=D(a)-D(b), positive improves. D_all uses actual full pool, not a common-N comparison; no fast/slow cutoff.',
        panels='n8/n16/n20 each fixed image set, common10 same 24 workers. include_door adds only existing annotatable-doorway cases, not OOS. No formal quality-gate change.',
        evaluation='Original or revision where already available; actual reference recorded per_image/curves. Old-only images retain original under revised policy; not independent datasets.',
        caveats='Doorway inclusion is reference-conditional descriptive difficulty analysis, not worker scoring. uNb-47 reference orientation unresolved. Same-room OOS views are not an N experiment.',
        coverage='per_image includes available legacy curves; only eligible labeled sets enter summary. OOS separately in plots/report. Missing k left empty, not imputed. intervals stores same-panel gains, median and improvement/worsening counts; 9->17 is an odd-endpoint comparison where voting rules coincide, not chosen as a replacement main window.',
        specials=sources,max_endpoint_or_singleton_difference=max(checks)),ensure_ascii=False,indent=2),encoding='utf-8')
    plot(summary,grouped,special)
    print(json.dumps(dict(per_image=len(per),summary=len(summary),special_check=max(checks))))


def plot(summary,grouped,special):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']; plt.rcParams['axes.unicode_minus']=False
    fig,axs=plt.subplots(1,3,figsize=(14,4))
    for ax,panel in zip(axs,['n8','n16','n20']):
        for label,color in zip(LABELS,['#2879a5','#bd862a','#ab4260']):
            for include,style in [(False,'-'),(True,'--')]:
                rr=[r for r in summary if r['panel']==panel and r['method']=='mv50' and r['evaluation']=='original' and r['difficulty']==label and r['include_door']==include]
                ax.plot([r['k'] for r in rr],[r['D'] for r in rr],style,color=color,label=f"{label} {'含门洞' if include else '原面板'} n={rr[0]['image_n']}")
        ax.set(title=panel,xlabel='人数',ylabel='参考差 D'); ax.legend(fontsize=7); ax.grid(alpha=.2)
    fig.suptitle('各面板固定图片、原GT、MV50；实线原面板，虚线加入可标门洞'); fig.tight_layout(); fig.savefig(OUT/'difficulty_curves.png',dpi=160);plt.close(fig)
    fig,axs=plt.subplots(2,2,figsize=(11,7))
    for ax,im in zip(axs.flat,special):
        for (image,method,v),c in grouped.items():
            if image!=im:continue
            ax.plot(list(c),[c[k]['D'] for k in c],'-' if method=='mv50' else '--',label=f'{method} / {v}')
            ax.scatter(max(c),c[max(c)]['D'],s=20)
        ax.set(title=im,xlabel='人数（末点实际全员）',ylabel='参考差 D');ax.legend(fontsize=7);ax.grid(alpha=.2)
    fig.suptitle('上：可标门洞；下：非正交可标OOS，同房两视角单列');fig.tight_layout();fig.savefig(OUT/'special_curves.png',dpi=160);plt.close(fig)


if __name__=='__main__': run()
