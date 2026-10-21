"""All finite F01 count cells: actual quality/time and member-set intervals."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from prepare_training import HERE,atomic_csv

def main():
    d=pd.read_csv(HERE/'F01_COMPLETE_CONFIGURATION_CURVE.csv')
    d['x_time_percent']=100*(d.time_seconds/d.ordinary_time_seconds-1)
    d['x_time_p10_percent']=100*(d.time_seconds_p10/d.ordinary_time_seconds-1)
    d['x_time_p90_percent']=100*(d.time_seconds_p90/d.ordinary_time_seconds-1)
    d['y_B8L2']=d.B8L2-d.ordinary_B8L2
    d['y_B8L2_p10']=d.B8L2_p10-d.ordinary_B8L2
    d['y_B8L2_p90']=d.B8L2_p90-d.ordinary_B8L2
    atomic_csv(d,HERE/'F01_FIGURE_POINTS.csv')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
        'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(14.5,8.3))
    fig.subplots_adjust(left=.067,right=.98,top=.85,bottom=.31,wspace=.23)
    for ax,difficulty,title in zip(axes,['简单','困难'],['Simple images','Difficult images']):
        z=d[d.difficulty.eq(difficulty)];images=sorted(z.image.unique())
        colors=plt.get_cmap('tab10')(np.linspace(0,.9,len(images)))
        handles=[]
        ax.axhline(0,color='#777777',linewidth=.75);ax.axvline(0,color='#777777',linewidth=.75)
        for i,(im,g) in enumerate(z.groupby('image',sort=True)):
            g=g.sort_values('fast_C01_n');color=colors[i]
            if not g.has_class_count_opportunity.any():
                ax.scatter(g.x_time_percent,g.y_B8L2,s=52,facecolors='none',edgecolors=color,marker='s',linewidth=1.4,zorder=4)
                handles.append(Line2D([],[],color=color,marker='s',markerfacecolor='none',linestyle='None',label=im+' (one set)'))
            else:
                ax.plot(g.x_time_percent,g.y_B8L2,color=color,linewidth=1.5,marker='o',markersize=4,zorder=3)
                handles.append(Line2D([],[],color=color,marker='o',markersize=4,label=im))
            for j,r in enumerate(g.itertuples()):
                # Quantile bars describe the finite member distribution, not a
                # confidence interval for the mean. Means need not lie between
                # central quantiles, so draw endpoints explicitly.
                ax.plot([r.x_time_p10_percent,r.x_time_p90_percent],[r.y_B8L2,r.y_B8L2],color=color,alpha=.28,linewidth=.8,zorder=1)
                ax.plot([r.x_time_percent,r.x_time_percent],[r.y_B8L2_p10,r.y_B8L2_p90],color=color,alpha=.28,linewidth=.8,zorder=1)
                label=str(r.fast_C01_n)
                if r.complete_failures:label+='*'
                if len(g)>1:
                    offset=(4,5 if (i+j)%2==0 else -11)
                    ax.annotate(label,(r.x_time_percent,r.y_B8L2),xytext=offset,textcoords='offset points',fontsize=8,color=color)
                if r.complete_failures:
                    ax.scatter(r.x_time_percent,r.y_B8L2,s=58,facecolors='none',edgecolors='black',linewidth=.8,zorder=5)
        ax.set_title(f'{title}: {len(z)} complete count cells / {len(images)} images',fontsize=12,fontweight='bold')
        ax.set_xlabel('Total recorded seconds relative to uniform member sets (%)')
        ax.set_ylabel('B8L2 relative to uniform successful member sets (points)')
        ax.grid(alpha=.15)
        ax.legend(handles=handles,loc='upper left',bbox_to_anchor=(0,-.16),ncol=2,fontsize=7.6,frameon=False,handlelength=1.7,columnspacing=1.2)
    fig.suptitle('F01 high-Q population: all feasible n = 12 class compositions',fontsize=16,fontweight='bold',y=.97)
    fig.text(.5,.911,'Each line connects an image’s feasible faster-class counts. Labels show C01 count out of 12; the remaining members are C02.',
             ha='center',fontsize=10)
    fig.text(.067,.065,'Dots: exact composition means. Pale bars: member-set 10th–90th percentiles, not confidence intervals.\n'
        'Quality is conditional on successful fusion; * marks a cell with failures (jtcx-28: 5/9 and 2/4 failed teams).\n'
        'Open squares are the two one-set inventories, with no composition or member-choice opportunity. All 37 cells and 1,874 teams are retained.',
        fontsize=9,linespacing=1.5)
    fig.savefig(HERE/'FIGURE_F01_COMPLETE_CONFIGURATION_QUALITY_TIME.png',dpi=220)
    fig.savefig(HERE/'FIGURE_F01_COMPLETE_CONFIGURATION_QUALITY_TIME.svg')
    plt.close(fig)

if __name__=='__main__':main()
