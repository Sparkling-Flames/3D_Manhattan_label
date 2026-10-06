"""共同24人十图：描述图片、人员平均差及剩余人图差异；不作噪声归因。"""
from itertools import combinations
import json

import numpy as np
from scipy.stats import rankdata

from .consensus_response_20261006 import ROOT, OUT, read_csv, write_csv

DEST = OUT/'worker_image'
POLICIES = ('original','revised_where_available')


def centered_parts(matrix):
    mean=matrix.mean()
    image=matrix.mean(axis=1)-mean
    worker=matrix.mean(axis=0)-mean
    return mean,image,worker,matrix-mean-image[:,None]-worker[None,:]


def run():
    DEST.mkdir(parents=True,exist_ok=True)
    block=json.loads((ROOT/'analysis_results/worker_profiles_20261003/block.json').read_text(encoding='utf-8'))
    images=block['images']; workers=block['workers'].split('|')
    raw=read_csv(OUT/'individual_reference.csv')
    indexed={(r['image'],r['worker'],r['version']):r for r in raw if r['condition']=='manual'}
    endpoints=read_csv(OUT/'all_pool_summary.csv')
    context={r['image']:r for r in endpoints if r['condition']=='manual' and r['method']=='mv50' and r['version']=='original'}
    cells=[]; summaries=[]; people=[]; pairs=[]; picture=[]
    for policy in POLICIES:
        versions=[('manual_revision' if policy!='original' and (im,workers[0],'manual_revision') in indexed else 'original') for im in images]
        for metric in ('omission_ref','extension_ref','ref_symdiff_ref'):
            matrix=np.array([[float(indexed[im,w,v][metric]) for w in workers] for im,v in zip(images,versions)])
            mu,ia,wa,res=centered_parts(matrix)
            total=float(np.sum((matrix-mu)**2))
            ss=dict(image_mean=float(len(workers)*np.sum(ia**2)),worker_mean=float(len(images)*np.sum(wa**2)),remaining=float(np.sum(res**2)))
            assert abs(sum(ss.values())-total)<1e-10
            assert np.max(abs(res.mean(axis=0)))<1e-10 and np.max(abs(res.mean(axis=1)))<1e-10
            summaries.append(dict(policy=policy,metric=metric,mean=float(mu),total_ss=total,
                **{k+'_ss_fraction':v/total for k,v in ss.items()}))
            ranks=np.array([rankdata(row) for row in matrix])
            for j,w in enumerate(workers):
                people.append(dict(policy=policy,metric=metric,worker=w,mean_error=float(mu+wa[j]),
                    image_centered_mean=float(wa[j]),remaining_rms=float(np.sqrt(np.mean(res[:,j]**2))),
                    best_image_rank=float(ranks[:,j].min()),worst_image_rank=float(ranks[:,j].max()),
                    above_image_mean_n=int(np.sum(matrix[:,j]>matrix.mean(axis=1)))))
            if metric!='ref_symdiff_ref': continue
            for i,(im,version) in enumerate(zip(images,versions)):
                picture.append(dict(policy=policy,image=im,version=version,difficulty=context[im]['difficulty'],
                    mean_D=float(matrix[i].mean()),sd_D=float(matrix[i].std()),
                    raw_R=float(context[im]['raw_pairwise_union']),
                    higher_error_worker=workers[int(matrix[i].argmax())],lower_error_worker=workers[int(matrix[i].argmin())]))
                for j,w in enumerate(workers):
                    cells.append(dict(policy=policy,image=im,version=version,worker=w,record=indexed[im,w,version]['record'],
                        error=float(matrix[i,j]),image_centered_error=float(matrix[i,j]-matrix[i].mean()),
                        worker_mean_effect=float(wa[j]),image_mean_effect=float(ia[i]),remaining=float(res[i,j]),
                        image_rank=float(ranks[i,j])))
            for i,j in combinations(range(len(images)),2):
                pairs.append(dict(policy=policy,image_a=images[i],image_b=images[j],
                    same_building=images[i].rsplit('-',1)[0]==images[j].rsplit('-',1)[0],
                    rank_spearman=float(np.corrcoef(ranks[i],ranks[j])[0,1])))
    for name,rows in [('cells',cells),('decomposition',summaries),('workers',people),('image_pairs',pairs),('images',picture)]:
        write_csv(DEST/(name+'.csv'),rows)
    (DEST/'field_contract.json').write_text(json.dumps(dict(schema='worker_image_response_v1',
        population='Existing balanced 24 Manual workers x 10 images; no new selection or quality tier.',
        loss='D=omission_ref+extension_ref, each normalized by that image/reference area; original vs existing revision where available.',
        decomposition='Descriptive two-way centering: e=mean+image_mean_effect+worker_mean_effect+remaining. SS fractions describe this matrix, not independent uncertainty sources, causal effects, measurement error or variance components.',
        remaining='Includes person-image interaction, target differences and one-off errors. No repeated same-person same-image trials.',
        ranks='Within-image error rank; ties averaged, 1=lower reference area error. 45 pairs share images/workers; not independent tests.',
        prediction='In-sample centering only, no new predictor; existing building-held-out Q predictions remain separate.',
        references='revised_where_available uses same 4 revised and 6 original references as existing panel.',
        check='Orthogonal SS identity and zero row/column residual means; no raw geometry recomputation.'),indent=2),encoding='utf-8')
    plot(cells,images,workers)
    print(json.dumps(dict(cells=len(cells),ss=len(summaries),pairs=len(pairs))))


def plot(cells,images,workers):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']; plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(1,2,figsize=(16,5))
    for ax,policy in zip(axes,POLICIES):
        rows={(r['image'],r['worker']):r for r in cells if r['policy']==policy}
        z=np.array([[rows[im,w]['image_rank'] for w in workers] for im in images])
        obj=ax.imshow(z,vmin=1,vmax=24,aspect='auto',cmap='viridis_r')
        ax.set(yticks=range(10),yticklabels=images,xticks=range(24),xticklabels=workers,
               title='原GT' if policy=='original' else '修订优先（4图修订＋6图原GT）')
        ax.tick_params(axis='x',labelrotation=90)
    fig.suptitle('同一人员在不同图片上的参考范围排名；人员顺序固定，无聚类或选人')
    fig.subplots_adjust(left=.14,right=.91,bottom=.18,wspace=.47,top=.85)
    fig.colorbar(obj,cax=fig.add_axes([.93,.18,.012,.67]),label='该图D排名（1为参考差最小）')
    fig.savefig(DEST/'within_image_ranks.png',dpi=170); plt.close(fig)


if __name__=='__main__': run()
