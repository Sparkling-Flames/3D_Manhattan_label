"""原作答分歧与人员构成：复用既有楼外分组、两两距离及融合结果。"""
from collections import defaultdict
from itertools import combinations
from math import comb
import json

import numpy as np

from .consensus_response_20261006 import ROOT, SOURCE, OUT, read_csv, write_csv


def expected_pairwise(distance, higher, k, h):
    """固定构成h/(k-h)无放回抽组，平均两两距离的精确期望。"""
    hi, lo = np.flatnonzero(higher), np.flatnonzero(~higher)
    total = 0.
    for indices,draw in ((hi,h),(lo,k-h)):
        if draw >= 2:
            total += comb(draw,2) / comb(len(indices),2) * sum(distance[a,b] for a,b in combinations(indices,2))
    if h and k-h:
        total += h*(k-h)/(len(hi)*len(lo)) * distance[np.ix_(hi,lo)].sum()
    return float(total / comb(k,2))


def run():
    out=OUT/'composition'; out.mkdir(parents=True,exist_ok=True)
    pairs=read_csv(OUT/'pairwise_distances.csv')
    assignments=read_csv(SOURCE/'assignments.csv')
    source=read_csv(SOURCE/'per_image.csv')
    endpoints=read_csv(OUT/'all_pool_summary.csv')
    full={(r['image'],r['condition'],r['method'],r['version']):r for r in endpoints}
    matrices={}
    grouped=defaultdict(list)
    for r in pairs:
        if r['condition']=='manual': grouped[r['image']].append(r)
    for image,rs in grouped.items():
        workers=sorted({r[f] for r in rs for f in ('worker_a','worker_b')})
        index={w:i for i,w in enumerate(workers)}; d=np.zeros((len(workers),len(workers)))
        for r in rs:
            a,b=index[r['worker_a']],index[r['worker_b']]; d[a,b]=d[b,a]=float(r['distance_union'])
        matrices[image]=workers,d
    labels=defaultdict(dict)
    for r in assignments: labels[r['image'],r['policy']][r['worker']]=r['higher']=='True'
    random={(r['image'],r['method'],r['version'],int(r['k'])):r for r in source if r['scenario']=='uniform' and r['condition']=='manual'}
    rows=[]; cache={}
    for r in source:
        if r['scenario']!='composition' or int(r['k']) not in (4,8,12): continue
        image,policy,k,h=r['image'],r['policy'],int(r['k']),int(r['higher_n'])
        key=(image,policy,k,h)
        if key not in cache:
            workers,d=matrices[image]
            cache[key]=expected_pairwise(d,np.array([labels[image,policy][w] for w in workers]),k,h)
        endpoint=full[image,'manual',r['method'],r['version']]
        baseline=random[image,r['method'],r['version'],k]
        rows.append(dict(image=image,building=r['building'],difficulty=endpoint['difficulty'],policy=policy,
            method=r['method'],version=r['version'],k=k,n=int(r['n']),strategy=r['strategy'],
            higher_n=h,higher_total=int(r['higher_total']),higher_fraction=h/k,
            raw_pairwise_union=cache[key],ref_symdiff_ref=float(r['ref_symdiff_ref']),
            omission_ref=float(r['omission_ref']),extension_ref=float(r['extension_ref']),member_symdiff_union=float(r['member_symdiff_union']),
            random_raw_pairwise_union=float(endpoint['raw_pairwise_union']),
            random_error_ref=float(baseline['ref_symdiff_ref']),random_member_symdiff_union=float(baseline['member_symdiff_union']),
            all_error_ref=float(endpoint['all_error_ref']),
            error_minus_random=float(r['ref_symdiff_ref'])-float(baseline['ref_symdiff_ref']),
            error_minus_all=float(r['ref_symdiff_ref'])-float(endpoint['all_error_ref'])))
    write_csv(out/'per_image.csv',rows)
    cells=defaultdict(dict)
    for r in rows: cells[tuple(r[f] for f in ('image','policy','method','version','k'))][r['strategy']]=r
    contrasts=[]
    metrics=('raw_pairwise_union','ref_symdiff_ref','member_symdiff_union','omission_ref','extension_ref')
    for key,cell in cells.items():
        hi,lo=cell['higher_rich'],cell['lower_rich']
        contrast={f:hi[f] for f in ('image','building','difficulty','policy','method','version','k','n')}
        contrast.update(higher_fraction=hi['higher_fraction'],lower_fraction=lo['higher_fraction'],
                        higher_error_minus_random=hi['error_minus_random'],higher_error_minus_all=hi['error_minus_all'])
        for m in metrics: contrast['higher_minus_lower_'+m]=hi[m]-lo[m]
        contrasts.append(contrast)
    write_csv(out/'contrasts.csv',contrasts)
    panels=json.loads((SOURCE/'panels.json').read_text(encoding='utf-8'))
    summary=[]
    for name in ('common10','manual_n16','manual_n20','manual_external_n16'):
        selected=[r for r in contrasts if r['image'] in panels[name]['images']]
        cells=defaultdict(list)
        for r in selected: cells[tuple(r[f] for f in ('policy','method','version','k'))].append(r)
        for key,rs in cells.items():
            for weighting in ('image','building'):
                s=dict(zip(('policy','method','version','k'),key)); s.update(panel=name,weighting=weighting,
                    image_n=len(rs),building_n=len({r['building'] for r in rs}),images='|'.join(sorted(r['image'] for r in rs)))
                for m in ['higher_fraction','lower_fraction','higher_error_minus_random','higher_error_minus_all']+['higher_minus_lower_'+m for m in metrics]:
                    buckets=defaultdict(list)
                    for r in rs: buckets[r['building'] if weighting=='building' else r['image']].append(r[m])
                    s[m]=float(np.mean([np.mean(v) for v in buckets.values()]))
                for m in ('raw_pairwise_union','ref_symdiff_ref','member_symdiff_union'):
                    s['images_reduced_'+m]=sum(r['higher_minus_lower_'+m]<-1e-12 for r in rs)
                    s['images_increased_'+m]=sum(r['higher_minus_lower_'+m]>1e-12 for r in rs)
                summary.append(s)
    write_csv(out/'summary.csv',summary)
    counts=[]
    cells=defaultdict(dict)
    for r in source:
        if r['scenario']=='uniform': cells[tuple(r[f] for f in ('image','condition','method','version'))][int(r['k'])]=r
    for key,cell in cells.items():
        r=full[key]; item={f:r[f] for f in ('image','condition','n','difficulty','method','version','raw_pairwise_union','all_error_ref')}
        for k in (1,4,8,12,16):
            item[f'D{k}']=float(cell[k]['ref_symdiff_ref']); item[f'V{k}']=float(cell[k]['member_symdiff_union'])
        item['D16_minus_D8']=item['D16']-item['D8']; item['V16_minus_V8']=item['V16']-item['V8']
        counts.append(item)
    write_csv(out/'count_response.csv',counts)
    (out/'field_contract.json').write_text(json.dumps(dict(schema='consensus_composition_v1',k=[4,8,12],
        source='Existing assignments and fusion rows; no recalibration or new thresholds.',
        raw_pairwise='E[mean of distinct within-team pair distances]; fixed full-pool union denominator; exact pair inclusion probabilities for given composition.',
        contrast='higher_rich minus lower_rich; negative means smaller difference/error, not necessarily better semantic interpretation.',
        summary='Fixed named panels; images/ buildings weighted separately. Reduction counts always count images; 1e-12 tolerance for floating zero only.',
        references='original and manual_revision separately. policy is calibration reference, version is evaluation reference.',
        count_response='All 57 pools by method/reference. D and V have different denominators. D16-D8 is a fixed interval, not an estimated convergence rate.',
        condition='Composition Manual only; count_response Manual and Semi separately.'),indent=2),encoding='utf-8')
    plot(out,rows,panels['common10']['images'])
    print(json.dumps(dict(composition_rows=len(rows),contrasts=len(contrasts),summary=len(summary),count_rows=len(counts))))


def plot(out,rows,images):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']; plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(1,3,figsize=(15,7),sharey=True)
    specs=[('raw_pairwise_union','原作答平均差异 / 全池并集'),('ref_symdiff_ref','融合参考差 / 原GT面积'),('member_symdiff_union','融合换组差 / 全池并集')]
    for ax,(metric,title) in zip(axes,specs):
        for idx,image in enumerate(images):
            cell={r['strategy']:r for r in rows if r['image']==image and r['policy']=='original' and r['version']=='original' and r['method']=='mv50' and r['k']==8}
            vals=[cell[s][metric] for s in ('lower_rich','balanced','higher_rich')]
            ax.plot([vals[0],vals[-1]],[idx,idx],color='#bbbbbb')
            for v,color,label in zip(vals,['#bf672b','#999999','#196a9b'],['偏下半','混合','偏上半']):
                ax.scatter(v,idx,color=color,label=label if idx==0 else None,s=35)
        ax.set_title(title); ax.grid(axis='x',alpha=.2); ax.legend()
    axes[0].set_yticks(range(len(images)),images); axes[0].invert_yaxis()
    fig.suptitle('同一批24人、同图8人团队、楼外Q分层、MV50；三个量分开读')
    fig.tight_layout(); fig.savefig(out/'common10_composition.png',dpi=160); plt.close(fig)


if __name__=='__main__': run()
