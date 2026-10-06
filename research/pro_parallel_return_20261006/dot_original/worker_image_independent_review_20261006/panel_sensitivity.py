#!/usr/bin/env python3
"""Independent, descriptive matrix checks; no population or causal inference.
Input canonical records columns: policy,image,worker,O,E,D,gt_area_h2,building.
Every policy must describe the same balanced image x worker panel.
"""
from pathlib import Path
import argparse,json
from itertools import combinations
import numpy as np
import pandas as pd
from scipy.stats import rankdata


def parts(x):
    nimg,nworker=x.shape
    grand=x.mean(); ie=x.mean(axis=1)-grand; we=x.mean(axis=0)-grand
    residual=x-grand-ie[:,None]-we[None,:]
    ss_image=nworker*np.square(ie).sum(); ss_worker=nimg*np.square(we).sum()
    ss_residual=np.square(residual).sum(); ss_total=np.square(x-grand).sum()
    assert np.isclose(ss_image+ss_worker+ss_residual,ss_total,rtol=2e-13,atol=1e-12)
    ss=dict(image=ss_image,worker=ss_worker,residual=ss_residual,total=ss_total)
    result={'n_images':nimg,'n_workers':nworker,'grand_mean':grand,**{f'SS_{k}':float(v) for k,v in ss.items()},**{f'{k}_pct':float(100*v/ss_total) if ss_total else None for k,v in ss.items() if k!='total'},'worker_share_after_image_centering_pct':float(100*ss_worker/(ss_worker+ss_residual)) if ss_worker+ss_residual else None}
    ranks=np.array([rankdata(row,method='average') for row in x])
    corrs=[]
    for i,j in combinations(range(nimg),2):
        if ranks[i].std()>0 and ranks[j].std()>0:
            corrs.append(float(np.corrcoef(ranks[i],ranks[j])[0,1]))
    result.update(rank_correlation_median=float(np.median(corrs)) if corrs else None, rank_correlation_min=min(corrs) if corrs else None,rank_correlation_max=max(corrs) if corrs else None,rank_correlation_negative=sum(r<0 for r in corrs),rank_correlation_positive=sum(r>0 for r in corrs),rank_correlation_zero=sum(r==0 for r in corrs),n_image_pairs=len(corrs),workers_above_and_below_image_mean=int(((x>x.mean(axis=1)[:,None]).any(axis=0)&(x<x.mean(axis=1)[:,None]).any(axis=0)).sum()))
    # Centering subtracts the same grand mean from every worker's mean.
    assert np.allclose((x-x.mean(axis=1)[:,None]).mean(axis=0),x.mean(axis=0)-grand,atol=1e-14)
    return result


def analyze(df,outdir):
    outdir.mkdir(parents=True,exist_ok=True)
    reports=[]; worker_rows=[]; pair_rows=[]; perimage_rows=[]; covariance_rows=[]
    for policy,f in df.groupby('policy',sort=False):
        images=sorted(f.image.unique()); workers=sorted(f.worker.unique())
        if len(f)!=len(images)*len(workers) or f.duplicated(['image','worker']).any():
            raise ValueError(f'{policy}: not one record per balanced image x worker cell')
        if not np.allclose(f.D,f.O+f.E,rtol=1e-13,atol=1e-13):
            raise ValueError(f'{policy}: D differs from O+E')
        for image,g in f.groupby('image'):
            if g.gt_area_h2.nunique()!=1 or g.building.nunique()!=1:
                raise ValueError(f'{policy}/{image}: inconsistent image metadata')
        areas=f.groupby('image').gt_area_h2.first().reindex(images).to_numpy()
        buildings=f.groupby('image').building.first().reindex(images).to_numpy()
        mats={metric:f.pivot(index='image',columns='worker',values=metric).loc[images,workers].to_numpy() for metric in ['O','E','D']}
        for scale, multiplier in [('GT_normalized',np.ones(len(images))),('raw_h2',areas)]:
            components={}
            for metric in ['O','E','D']:
                x=mats[metric]*multiplier[:,None]
                grand=x.mean(); ie=np.broadcast_to((x.mean(axis=1)-grand)[:,None],x.shape)
                we=np.broadcast_to((x.mean(axis=0)-grand)[None,:],x.shape)
                components[metric]={'total':x-grand,'image':ie,'worker':we,'residual':x-grand-ie-we}
            for name in ['total','image','worker','residual']:
                o,e,d=(components[metric][name] for metric in ['O','E','D'])
                soo=float(np.square(o).sum()); see=float(np.square(e).sum()); sdd=float(np.square(d).sum()); cross=float(2*(o*e).sum())
                assert np.isclose(soo+see+cross,sdd,rtol=2e-13,atol=1e-12)
                covariance_rows.append({'policy':policy,'scale':scale,'component':name,'SS_O':soo,'SS_E':see,'twice_cross_O_E':cross,'SS_D':sdd,'O_E_correlation':float((o*e).sum()/np.sqrt(soo*see)) if soo*see else None})
        for metric in ['O','E','D']:
            raw=mats[metric]
            for scale,x in [('GT_normalized',raw),('raw_h2',raw*areas[:,None])]:
                variants=[('full','',np.ones(len(images),dtype=bool),np.ones(len(workers),dtype=bool))]
                variants += [('leave_image_out',im,np.array(images)!=im,np.ones(len(workers),dtype=bool)) for im in images]
                variants += [('leave_building_out',b,buildings!=b,np.ones(len(workers),dtype=bool)) for b in sorted(set(buildings))]
                if 'P017' in workers:
                    variants.append(('leave_P017_out','P017',np.ones(len(images),dtype=bool),np.array(workers)!='P017'))
                for kind,removed,imask,wmask in variants:
                    if not imask.any() or not wmask.any(): continue
                    reports.append({'policy':policy,'metric':metric,'scale':scale,'variant':kind,'removed':removed,**parts(x[np.ix_(imask,wmask)])})
                ranks=np.array([rankdata(row,method='average') for row in x])
                for i,image in enumerate(images):
                    perimage_rows.append({'policy':policy,'metric':metric,'scale':scale,'image':image,'building':buildings[i],'gt_area_h2':areas[i],'mean':x[i].mean(),'sd_workers':x[i].std(ddof=0),'min':x[i].min(),'max':x[i].max()})
                overallranks=rankdata(x.mean(axis=0),method='average')
                for j,worker in enumerate(workers):
                    worker_rows.append({'policy':policy,'metric':metric,'scale':scale,'worker':worker,'mean_error':x[:,j].mean(),'overall_mean_error_rank':overallranks[j],'mean_image_rank':ranks[:,j].mean(),'best_image_rank':ranks[:,j].min(),'worst_image_rank':ranks[:,j].max(),'above_image_mean_count':int((x[:,j]>x.mean(axis=1)).sum()),'below_image_mean_count':int((x[:,j]<x.mean(axis=1)).sum())})
                for i,j in combinations(range(len(images)),2):
                    pair_rows.append({'policy':policy,'metric':metric,'scale':scale,'image1':images[i],'image2':images[j],'spearman':np.corrcoef(ranks[i],ranks[j])[0,1]})
    report=pd.DataFrame(reports)
    report.to_csv(outdir/'sensitivity.csv',index=False)
    pd.DataFrame(worker_rows).to_csv(outdir/'worker_summary.csv',index=False)
    pd.DataFrame(pair_rows).to_csv(outdir/'image_pair_spearman.csv',index=False)
    pd.DataFrame(perimage_rows).to_csv(outdir/'image_summary.csv',index=False)
    pd.DataFrame(covariance_rows).to_csv(outdir/'O_E_covariance_components.csv',index=False)
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('canonical_csv');p.add_argument('output_dir')
    a=p.parse_args();df=pd.read_csv(a.canonical_csv,float_precision='round_trip',dtype={'policy':str,'image':str,'worker':str,'building':str})
    out=analyze(df,Path(a.output_dir))
    print(out[out.variant.isin(['full','leave_P017_out'])].to_csv(index=False))

if __name__=='__main__':main()
