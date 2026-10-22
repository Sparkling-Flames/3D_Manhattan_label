"""Standalone numeric research figures from registered, evaluated member sets."""
from __future__ import annotations
from joint_design import *
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_joint_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def run():
    out=HERE/'figures';out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
    im=pd.read_csv(HERE/'NATIVE_PREFERRED_IMAGE_RESPONSES.csv.gz');im=im[im.view.eq('all')&im.scope.eq('ABC_scored_time_common')].copy();im['time_pct']=100*np.expm1(im.net_recorded_time_logratio)
    source=pd.read_csv(HERE/'NATIVE_PREFERRED_DIRECTION_EVENTS.csv.gz');meta=source.groupby('image').agg(difficulty=('difficulty','first'),registered_events=('event_id','size'),C_failures=('C_failure','sum')).reset_index();im=im.merge(meta,on='image');write(out/'MANUAL_IMAGE_SCATTER_VALUES.csv',im)
    fig,ax=plt.subplots(figsize=(9.4,6.3));ax.axhline(0,color='#888',lw=.8);ax.axvline(0,color='#888',lw=.8)
    colors={'简单':'#2878a0','困难':'#b75b35','中等':'#7f6ca7'}
    for _,r in im.iterrows():
        ax.scatter(r.time_pct,r.net_B8L2,s=50+4*r.registered_events,color=colors.get(r.difficulty,'#555'),alpha=.8,edgecolor='white',zorder=3)
        offset=(5,-14) if r.image=='zsNo4HB9uLZ-16' else (5,5)
        ax.annotate(r.image+(" *" if r.C_failures else ''),(r.time_pct,r.net_B8L2),xytext=offset,textcoords='offset points',fontsize=8)
    ax.scatter([-3.632317],[5.690789],marker='D',s=90,color='#222',zorder=4,label='Building-balanced mean (62 scoreable triples)')
    ax.set(xlabel='Net C vs B recorded time change (%)',ylabel='Net C vs B B8L2 change (points)',title='Manual: higher-Q, faster training-center class block\nSame background, same n, actual m = class-seat change = 4 or 6')
    fig.text(.12,.015,'Blue: simple images; orange: difficult images. All 64 triples remain in failure tables.\n* B6-47: 2 additional C invalid-floor endpoints; frozen Q remains missing.',fontsize=9,va='bottom');ax.legend(loc='upper left',frameon=False)
    fig.tight_layout(rect=[0,.085,1,1]);fig.savefig(out/'MANUAL_PURE_BLOCK_IMAGE_EFFECTS.png');fig.savefig(out/'MANUAL_PURE_BLOCK_IMAGE_EFFECTS.pdf');plt.close(fig)
    paths=source[source.image.isin(['wc2JMjhGNzB-56','zsNo4HB9uLZ-16'])&source.m_AB.eq(6)].copy();write(out/'REGISTERED_N_PATH_VALUES.csv',paths)
    fig,axes=plt.subplots(2,2,figsize=(10,6.8),sharex='col')
    for col,img in enumerate(['wc2JMjhGNzB-56','zsNo4HB9uLZ-16']):
        g=paths[paths.image.eq(img)]
        for seed,z in g.groupby('path_seed'):
            z=z.sort_values('n');style=dict(marker='o',lw=1.7,color=['#2878a0','#b75b35'][int(seed)],label=f'Frozen member/background path {int(seed)+1}')
            axes[0,col].plot(z.n,z.net_B8L2,**style);axes[1,col].plot(z.n,z.net_recorded_time_pct,**style)
        axes[0,col].set_title(f'{img}; m = 6')
        for ax in axes[:,col]:ax.axhline(0,color='#888',lw=.8);ax.grid(axis='y',alpha=.2)
        axes[1,col].set_xlabel('Team size n (nested common background)');axes[1,col].set_xticks(sorted(g.n.unique()))
    axes[0,0].set_ylabel('Net C − B B8L2');axes[1,0].set_ylabel('Net C vs B time (%)');axes[0,0].legend(frameon=False,fontsize=8)
    fig.suptitle('Same replacement blocks, changing the common background\nPositive average use does not imply a monotone team-size path',fontsize=12);fig.tight_layout(rect=[0,0,1,.93]);fig.savefig(out/'MANUAL_REGISTERED_N_PATHS.png');fig.savefig(out/'MANUAL_REGISTERED_N_PATHS.pdf');plt.close(fig)
    # Identical source anchors across classifications; use the strict shared
    # scoring/time support rather than separately available outcome subsets.
    summaries=[]
    for c in ['manual','semi']:
        p=HERE/f'CROSS_{c.upper()}_SAME_SUPPORT_SUMMARY.csv'
        if p.exists():
            d=pd.read_csv(p);summaries.append(d[d.source_domain.eq('new_only')&d.scope.eq('all_methods_scored_time_same_anchors')])
    if len(summaries)==2:
        d=pd.concat(summaries);write(out/'CROSS_METHOD_SAME_SUPPORT_PLOT_VALUES.csv',d);fig,axes=plt.subplots(1,2,figsize=(10.4,4.4))
        colors={'V3_JOINT_QT':'#2878a0','XCOND_GEOM_QT':'#b75b35','XCOND_PAIRED':'#60834b'};labels={'V3_JOINT_QT':'Within-condition\njoint QT','XCOND_GEOM_QT':'Cross-condition\ngeometry + QT','XCOND_PAIRED':'Paired Manual/Semi\nresponse'}
        for ax,(c,g) in zip(axes,d.groupby('condition',sort=True)):
            for _,r in g.iterrows():ax.scatter(r.net_recorded_time_geomean_pct,r.net_B8L2,s=90,c=colors[r.method_id]);ax.annotate(labels[r.method_id],(r.net_recorded_time_geomean_pct,r.net_B8L2),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
            ax.axhline(0,c='#888',lw=.8);ax.axvline(0,c='#888',lw=.8);ax.set_title(f'{c.title()}: {int(g.iloc[0].anchors)} common anchors\n{int(g.iloc[0].images)} images / {int(g.iloc[0].buildings)} buildings');ax.set_xlabel('Net C vs B recorded time (%)');ax.margins(.3)
        axes[0].set_ylabel('Net C − B B8L2');fig.suptitle('Three classifications; identical A, background, n and actual m = 4\nCommon class-center selection rule; class-seat change = 2',fontsize=11);fig.tight_layout(rect=[0,0,1,.90]);fig.savefig(out/'CROSS_METHOD_SAME_SUPPORT.png');fig.savefig(out/'CROSS_METHOD_SAME_SUPPORT.pdf');plt.close(fig)

if __name__=='__main__':run()
