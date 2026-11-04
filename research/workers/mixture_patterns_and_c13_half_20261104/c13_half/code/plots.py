"""Publication-style scientific figures from saved image-level statistics."""
from __future__ import annotations
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from design import OUT,SEED

COLORS={'简单':'#337A9E','中等':'#D38B25','困难':'#B44750','未分级':'#777777'}
EN={'简单':'Easy','中等':'Medium','困难':'Hard','未分级':'Unrated'}

def setup():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'figure.facecolor':'white','axes.facecolor':'white','svg.fonttype':'none','axes.titleweight':'bold',
                         'savefig.dpi':200})

def save(fig,name):
    p=OUT/'figures';p.mkdir(parents=True,exist_ok=True)
    for ext in ('png','svg','pdf'):fig.savefig(p/(name+'.'+ext),bbox_inches='tight',facecolor='white')
    plt.close(fig)

def main():
    setup();im=pd.read_csv(OUT/'analysis/IMAGE_METRICS.csv.gz');s=pd.read_csv(OUT/'analysis/SUMMARY.csv')
    s=s[s.stratum_type=='all'];fig,axes=plt.subplots(1,2,figsize=(12.3,6.8),sharey=True,gridspec_kw={'wspace':.14})
    fig.subplots_adjust(top=.81,bottom=.23)
    rng=np.random.default_rng(SEED)
    for ax,study,support,title in zip(axes,['main_8_4','paired_6_3'],['ABC_valid','all_four_valid'],
                                      ['8 people / replace 4\nDistinct feasible image sets','6 people / replace 3\nSame images, same D, all four endpoints valid']):
        tick_labels=[]
        for j,direction in enumerate(['C1_to_C3','C3_to_C1']):
            z=im[(im.study==study)&(im.support==support)&(im.direction==direction)]
            for difficulty,g in z.groupby('official_difficulty'):
                x=j+rng.uniform(-.13,.13,len(g));ax.scatter(x,g.Q_GS,color=COLORS.get(difficulty,'#777777'),alpha=.75,s=31,edgecolor='white',linewidth=.4,zorder=3)
            r=s[(s.study==study)&(s.support==support)&(s.direction==direction)&(s.metric=='Q_GS')].iloc[0]
            mean,lo,hi=r.image_equal_mean,r.cluster_bootstrap_low,r.cluster_bootstrap_high
            ax.errorbar(j+.24,mean,yerr=[[mean-lo],[hi-mean]],fmt='D',color='#172B3A',markersize=6,capsize=4,elinewidth=1.8,zorder=4)
            tick_labels.append(f"{direction.replace('_to_',' → ')}\n{int(r.images)} images / {int(r.buildings)} buildings\nGS = {mean:+.2f}")
        ax.axhline(0,color='#333333',linestyle='--',linewidth=1);ax.set_xticks([0,1],tick_labels);ax.set_xlim(-.4,1.5)
        ax.set_title(title,fontsize=12,pad=13);ax.grid(axis='y',color='#E6E6E6',linewidth=.7,zorder=0)
    axes[0].set_ylabel('Symmetric cross-class excess change GS (Q points)')
    for difficulty in ['简单','中等','困难']:axes[1].scatter([],[],color=COLORS[difficulty],s=32,label=EN[difficulty])
    axes[1].legend(title='Individual images',loc='upper right',frameon=True,facecolor='white',edgecolor='#EEEEEE')
    fig.suptitle('DSTRUCT K3 C1 ↔ C3: strict 50% replacement',fontsize=15,fontweight='bold',y=.97)
    fig.text(.08,.025,'Dots: image means. Diamonds / bars: equal-image mean and 95% building-cluster bootstrap.\nGS = (|QC−QA| + |QC−QB|)/2 − |QB−QA|; positive values mean greater cross-class change, not necessarily higher quality.',fontsize=9,color='#444444')
    save(fig,'C13_STRICT_50PCT_GS')

    fig,axes=plt.subplots(1,3,figsize=(15,6.1),gridspec_kw={'wspace':.35})
    fig.subplots_adjust(top=.82,bottom=.23)
    cells=[('main_8_4','ABC_valid','C1_to_C3','8/4: C1 → C3'),('main_8_4','ABC_valid','C3_to_C1','8/4: C3 → C1'),('paired_6_3','all_four_valid','C1_to_C3','6/3 common domain: C1 → C3')]
    for ax,(study,support,direction,title) in zip(axes,cells):
        z=im[(im.study==study)&(im.support==support)&(im.direction==direction)]
        for difficulty,g in z.groupby('official_difficulty'):
            ax.scatter(g.Q_GS,g.Q_class_shift,s=42,c=COLORS.get(difficulty,'#777777'),alpha=.85,edgecolors='white',linewidths=.6,label=EN.get(difficulty,difficulty))
        ax.axhline(0,color='#777777',linestyle='--',linewidth=.8);ax.axvline(0,color='#777777',linestyle='--',linewidth=.8)
        ax.grid(color='#EBEBEB',linewidth=.6);ax.set_title(title);ax.set_xlabel('GS: cross-class excess change (Q points)')
        ax.text(.03,.97,f'{len(z)} images',transform=ax.transAxes,ha='left',va='top',fontsize=9)
        # Show all images; labels on at most three large movements aid traceability.
        for _,r in z.assign(mag=np.hypot(z.Q_GS,z.Q_class_shift)).nlargest(3,'mag').iterrows():
            ax.annotate(r.image,(r.Q_GS,r.Q_class_shift),xytext=(4,4),textcoords='offset points',fontsize=6.5,color='#555555')
    axes[0].set_ylabel('Signed quality shift QC − (QA+QB)/2 (Q points)')
    axes[-1].legend(loc='best',frameon=True,edgecolor='#EEEEEE',fontsize=8)
    fig.suptitle('Greater change and better quality answer different questions',fontsize=14,fontweight='bold',y=.97)
    fig.text(.07,.025,'Each point is one image after target-slot, background and block averaging. Positive vertical values favor the incoming class.\nThe two 8/4 directions use different images; the 6/3 panel uses a shared four-endpoint domain.',fontsize=9,color='#444444')
    save(fig,'C13_CHANGE_VS_QUALITY')

if __name__=='__main__':main()
