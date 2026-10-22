#!/usr/bin/env python3
"""Reaggregate existing same-k geometry distances; never fuse or re-score."""
from pathlib import Path
import argparse,json,os
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_population_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_natural_curves import save,META

def main(a):
    out=Path(a.out);d=pd.read_csv(a.image_curves)
    ms=[m for m in ['V_floor_mean','V_centroid_h_mean','V_height_h_mean','V_turn5_mean','V_nodes_mean'] if m in d]
    curves=[];pairs=[];intervals=[]
    for limit in [0,20]:
        frame=d if not limit else d[d.pool_n.ge(limit)&d.k.le(limit)]
        for axis in ['difficulty','structure_opportunity']:
            keys=['condition','layer',axis,'k']
            for m in ms:
                paircol=m.removesuffix('_mean')+'_valid_pairs'
                for key,g in frame.groupby(keys,dropna=False):
                    r=dict(zip(keys,key));b=g.groupby('building')[m].mean()
                    r.update(metric=m,images=len(g),observed_images=int(g[m].notna().sum()),buildings=g.building.nunique(),observed_buildings=int(b.notna().sum()),mean=g[m].mean(),mean_building_equal=b.mean(),multiple_member_sets_images=int(g.unique_member_sets.gt(1).sum()),valid_pairs=g[paircol].sum() if paircol in g else np.nan,panel='all_available' if not limit else 'fixed_pool_N_ge_20',axis=axis)
                    r['stratum']=r.pop(axis);curves.append(r)
    for ka,kb in [(1,3),(3,6),(6,10),(10,20),(3,20),(20,'full')]:
        f=d[d.pool_n.ge(20)&d.k.eq(ka)]
        t=d[d.pool_n.ge(20)&(d.k.eq(d.pool_n)&d.k.gt(ka) if kb=='full' else d.k.eq(kb))]
        z=f[META+ms].merge(t[META+ms],on=META,suffixes=('_from','_to'),validate='one_to_one')
        z['interval']=f'{ka}_to_{kb}'
        for m in ms:z[m+'_delta']=z[m+'_to']-z[m+'_from']
        pairs.append(z)
        for m in ms:
            for key,g in z.groupby(['condition','layer','difficulty'],dropna=False):
                r=dict(zip(['condition','layer','difficulty'],key));b=g.groupby('building')[m+'_delta'].mean();v=g[m+'_delta']
                r.update(interval=f'{ka}_to_{kb}',metric=m,images=len(g),observed_images=int(v.notna().sum()),reduced_images=int(v.lt(0).sum()),buildings=len(b),observed_buildings=int(b.notna().sum()),reduced_buildings=int(b.lt(0).sum()),mean_from=g[m+'_from'].mean(),mean_to=g[m+'_to'].mean(),mean_delta=v.mean(),mean_delta_building_equal=b.mean(),panel='fixed_pool_N_ge_20');intervals.append(r)
    c=pd.DataFrame(curves);save(c,out/'NATURAL_GEOMETRIC_VARIATION_CURVES.csv')
    save(pd.concat(pairs,ignore_index=True),out/'NATURAL_GEOMETRIC_VARIATION_IMAGE_INTERVALS.csv.gz')
    save(pd.DataFrame(intervals),out/'NATURAL_GEOMETRIC_VARIATION_INTERVAL_SUMMARY.csv')
    fig,axs=plt.subplots(2,3,figsize=(14,7.8),sharex=True)
    palette={'简单':'#288b6d','中等':'#da9225','困难':'#a14c94'};names={'简单':'Easy','中等':'Moderate','困难':'Difficult'}
    titles={'V_floor_mean':'Floor: pairwise 1 - IoU','V_centroid_h_mean':'Centroid distance (camera-height units)','V_height_h_mean':'Mean-height difference (camera-height units)'}
    for i,con in enumerate(['manual','semi']):
        for j,m in enumerate(titles):
            z=c[c.layer.eq('ordinary_'+con)&c.axis.eq('difficulty')&c.panel.eq('fixed_pool_N_ge_20')&c.metric.eq(m)]
            for dif,g in z.groupby('stratum'):
                g=g.sort_values('k');axs[i,j].plot(g.k,g['mean'],color=palette.get(dif,'black'),lw=2,marker='o',markersize=2.5,label=names.get(dif,dif))
            axs[i,j].set_title(titles[m]);axs[i,j].set_xlabel('Prefix size k');axs[i,j].grid(alpha=.22);axs[i,j].set_xlim(.75,20.25);axs[i,j].set_xticks([1,3,6,10,15,20]);axs[i,j].axvspan(1.75,2.25,color='grey',alpha=.12)
            if j==0:axs[i,j].set_ylabel(con.capitalize());axs[i,j].legend(fontsize=8)
    fig.suptitle('Natural mixing: actual geometric variation among same-size teams\nFixed N >= 20 image panel; k=2 sorting deferred; lower variation is not higher accuracy',fontsize=12)
    fig.tight_layout(rect=[0,0,1,.93]);fig.savefig(out/'NATURAL_GEOMETRY_VARIATION.png',dpi=170);plt.close(fig)
    receipt=dict(input=str(a.image_curves),input_pool_k_rows=len(d),metrics=ms,curves=len(c),interval_summaries=len(intervals),new_fusions=0)
    (out/'GEOMETRIC_VARIATION_SUMMARY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--image-curves',required=True);p.add_argument('--out',required=True);main(p.parse_args())
