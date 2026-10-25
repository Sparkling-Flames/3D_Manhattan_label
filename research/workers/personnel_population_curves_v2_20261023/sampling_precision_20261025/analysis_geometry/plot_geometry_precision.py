"""Static scientific figures; exact plot data are exported alongside the figure."""
from __future__ import annotations
import argparse
import io
import os
from pathlib import Path
import numpy as np
import pandas as pd
from safe_io import install_safe_csv_writer
install_safe_csv_writer()
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image


def save_fig(fig,path):
    for extension in ['png','pdf']:
        target=path.with_suffix('.'+extension);temp=target.with_name(target.name+'.tmp')
        buff=io.BytesIO();fig.savefig(buff,format=extension,dpi=180,bbox_inches='tight');body=buff.getvalue()
        with temp.open('wb') as f:f.write(body);f.flush();os.fsync(f.fileno())
        assert temp.read_bytes()==body
        if extension=='png':
            with Image.open(temp) as im:im.load()
        temp.replace(target)
    plt.close(fig)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    results=Path(a.results);out=Path(a.out);out.mkdir(exist_ok=True,parents=True)
    d=pd.read_csv(results/'GEOMETRY_CURVE_MC_SUMMARY.csv')
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(11,7.2),constrained_layout=True)
    spec=[('ordinary_manual',30,'简单','Easy: fixed 105 images',30),('ordinary_manual',30,'中等','Medium: fixed 25 images',30),('ordinary_manual',30,'困难','Difficult: fixed 27 images',30),('doorway_manual',0,'ALL','Doorway: fixed 17 images',20)]
    colors={'old24':'#375c9c','new24':'#c97839','combined48':'#25765b'}
    labels={'old24':'Original 24','new24':'Independent new 24','combined48':'Combined 48'}
    plot=[]
    for ax,(layer,minimum,difficulty,title,limit) in zip(axes.flat,spec):
        for cohort in ['old24','new24','combined48']:
            x=d[d.layer.eq(layer)&d.minimum_pool_n.eq(minimum)&d.difficulty.eq(difficulty)&d.metric.eq('V_floor')&d.cohort.eq(cohort)&d.k.between(3,limit)].sort_values('k')
            if x.empty:continue
            ax.plot(x.k,x.estimate,label=labels[cohort],color=colors[cohort],lw=1.7,ls='--' if cohort=='new24' else '-')
            if cohort=='combined48':ax.fill_between(x.k,x.estimate-x.half_width_95_mc,x.estimate+x.half_width_95_mc,color=colors[cohort],alpha=.16)
            plot.append(x)
        ax.set_title(title);ax.set_xlabel('Team size k');ax.set_ylabel('V: expected floor 1 - IoU');ax.grid(alpha=.18);ax.set_ylim(bottom=0)
    axes[0,0].legend(frameon=False,fontsize=9)
    fig.suptitle('Geometric variation across independent random-order batches\nShade: combined-48 Monte Carlo uncertainty; fixed images and worker pools',fontsize=13)
    save_fig(fig,out/'GEOMETRY_INDEPENDENT_BATCH_CURVES')
    pd.concat(plot).to_csv(out/'GEOMETRY_INDEPENDENT_BATCH_PLOT_DATA.csv',index=False)
    if not (results/'GEOMETRY_OLD_ADDED_IMAGE_COMPARISONS.csv.gz').exists():return
    j=pd.read_csv(results/'GEOMETRY_OLD_ADDED_IMAGE_COMPARISONS.csv.gz')
    j=j[j.metric.eq('V_floor') & j.k.isin([3,10,20,30]) & j.comparison.isin(['combined48','combined96'])]
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.6),constrained_layout=True)
    labels={'ordinary_manual':'Ordinary Manual','doorway_manual':'Doorway Manual'}
    colors={'ordinary_manual':'#375c9c','doorway_manual':'#b65137'}
    for ax,comp in zip(axes,['combined48','combined96']):
        own=j[j.comparison.eq(comp) & j.mcse_old.notna() & j.mcse_new.notna()]
        limit=max(own.mcse_old.max(),own.mcse_new.max())*1.05
        for layer,g in own.groupby('layer_old'):
            ax.scatter(g.mcse_old,g.mcse_new,c=colors[layer],s=11,alpha=.4,label=labels[layer],edgecolors='none')
        ax.plot([0,limit],[0,limit],color='#777777',lw=1,ls=':');ax.plot([0,limit],[0,limit*np.sqrt(24/(48 if comp=='combined48' else 96))],color='#777777',lw=1,ls='--')
        ax.set_xlim(0,limit);ax.set_ylim(0,limit);ax.set_aspect('equal');ax.set_xlabel('Original-24 MCSE');ax.set_ylabel(('Combined 48' if comp=='combined48' else 'Focused combined 96')+' MCSE');ax.grid(alpha=.15)
        ax.set_title(f'{comp}: {own.pool_id.nunique()} pools; {len(own)} image-size cells')
    axes[0].legend(frameon=False,fontsize=9)
    fig.suptitle('Single-image geometry precision improves with more independent orders\nDotted: equal precision; dashed: ideal 1/sqrt(R) scaling',fontsize=12)
    save_fig(fig,out/'GEOMETRY_SINGLE_IMAGE_MCSE')
    j.to_csv(out/'GEOMETRY_MCSE_PLOT_DATA.csv.gz',index=False)


if __name__=='__main__':main()
