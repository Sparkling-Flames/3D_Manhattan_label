"""Scientific figure from hierarchy-balanced paired-geometry summaries."""
from pathlib import Path
import argparse
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_geometry_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    src,out=Path(a.input),Path(a.output);out.mkdir(parents=True,exist_ok=True)
    summary=pd.read_csv(src/'GEOMETRY_SUMMARY_BUILDING_EQUAL.csv')
    building=pd.read_csv(src/'GEOMETRY_BY_BUILDING.csv')
    subset='ordinary_mid_common_m1_panels'
    s=summary[(summary.subset==subset)&(summary.actual_m==1)].set_index('net_high_count_change')
    b=building[(building.subset==subset)&(building.actual_m==1)]
    cols=['both_position_small_rate','one_view_position_large_rate','both_position_large_rate']
    colors=['#c8d9e5','#e3ad58','#376b8f']
    labels=['Both small','Only one view > 0.02 h','Both views > 0.02 h']
    fig,(ax,bx)=plt.subplots(1,2,figsize=(11,6),gridspec_kw={'width_ratios':[1.25,1]})
    for r,y in [(0,1),(1,0)]:
        left=0.
        for c,color in zip(cols,colors):
            value=s.loc[r,c]*100
            ax.barh(y,value,left=left,height=.36,color=color,edgecolor='white')
            if value>=8:ax.text(left+value/2,y,f'{value:.1f}%',ha='center',va='center',fontsize=10,color='white' if color==colors[2] else '#1b2730')
            left+=value
        availability=s.loc[r,'joint_distance_available_rate']*100
        ax.text(0,y-.27,f'Distance available: {availability:.1f}% of attempted adjustments',fontsize=9,color='#52606b')
    ax.set_yticks([1,0],['Same class counts\n(change member)','One class count changes\n(change member)'])
    ax.set_xlim(0,100);ax.set_ylim(-.6,1.55);ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('Within jointly comparable geometry (%)')
    ax.set_title('A  Position-change states',loc='left',fontweight='bold',fontsize=12)
    from matplotlib.patches import Patch
    ax.legend([Patch(facecolor=c) for c in colors],labels,loc='upper left',bbox_to_anchor=(-.02,-.20),frameon=False,fontsize=9)
    pivot=b.pivot(index='building',columns='net_high_count_change',values='both_position_large_rate').dropna(subset=[0,1])
    pivot=pivot.sort_values(1)
    for y,(name,row) in enumerate(pivot.iterrows()):
        v0,v1=row[0]*100,row[1]*100
        bx.plot([v0,v1],[y,y],color='#b9c3ca',lw=2,zorder=1)
        bx.scatter(v0,y,color='#8fa9b8',s=34,zorder=2)
        bx.scatter(v1,y,color='#264e70',s=34,zorder=3)
    bx.set_yticks(range(len(pivot)),pivot.index);bx.tick_params(axis='y',labelsize=8)
    bx.set_xlabel('Both views > 0.02 h (%)');bx.set_xlim(left=0)
    bx.set_title('B  Building-specific effects',loc='left',fontweight='bold',fontsize=12)
    bx.scatter([],[],color='#8fa9b8',label='Same class counts');bx.scatter([],[],color='#264e70',label='One class count changes')
    bx.legend(loc='upper left',bbox_to_anchor=(-.03,-.20),frameon=False,fontsize=9)
    for axis in [ax,bx]:
        axis.spines[['top','right']].set_visible(False);axis.grid(axis='x',alpha=.15);axis.set_axisbelow(True)
    counts=s.loc[1]
    fig.suptitle('Exact one-member adjustments repeated in two adopted room views',x=.02,y=.99,ha='left',fontsize=13,fontweight='bold')
    fig.text(.02,.93,f'Ordinary Manual; middle budget; same {int(counts.panels)} panels | {int(counts.pairs)} direct pairs, {int(counts.groups_n)} adopted groups, {int(counts.buildings)} buildings',fontsize=10,color='#52606b')
    fig.text(.02,.015,'Within-view cyclic corresponding bottom-corner distance, in camera-height units h. Unequal corner counts and failures remain unavailable.\nPanel → direct pair → adopted group → building equal weights; overlapping groups are retained. Threshold is descriptive, not a success guarantee.',fontsize=8,color='#52606b')
    fig.subplots_adjust(left=.19,right=.98,top=.83,bottom=.30,wspace=.52)
    fig.savefig(out/'POSITION_CHANGE_REPETITION.png',dpi=210,bbox_inches='tight')
    fig.savefig(out/'POSITION_CHANGE_REPETITION.svg',bbox_inches='tight')
    plt.close(fig)


if __name__=='__main__':main()
