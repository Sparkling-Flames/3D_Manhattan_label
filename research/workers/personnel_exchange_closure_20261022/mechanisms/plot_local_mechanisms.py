"""Scientific overlays of saved observations; no image synthesis or score changes."""
from pathlib import Path
import gzip, importlib.util, json, os, sys
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_closure_mpl')
sys.path.insert(0,'/tmp/hohonet_deps')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sp=importlib.util.spec_from_file_location('visual',ROOT/'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py')
v=importlib.util.module_from_spec(sp);sp.loader.exec_module(v)
COL={'B':'#c7781d','C':'#9850b6','ref':'#f4d548'}

def read(cid):return json.load(gzip.open(HERE/'cases'/(cid+'.json.gz')))
def erp(ax,c,arm,xlim,ylim):
    im=Image.open(HERE/'originals'/(c['image_id']+'.png'))
    ax.imshow(im,extent=(0,1024,512,0))
    v._erp_edges(ax,c['reference']['points_1024x512'],COL['ref'],linewidth=1.7,alpha=1,markers=True)
    t=next(t for t in c['teams'] if t['label']==arm)
    v._erp_edges(ax,t['geometry']['points'],COL[arm],linewidth=1.6,alpha=.95,markers=True)
    ax.set_xlim(*xlim);ax.set_ylim(*ylim);ax.set_aspect('equal');ax.axis('off')
    return t
def ring(ax,pts,color,label,ls='-'):
    p=np.asarray(pts);p=np.vstack([p,p[0]])
    ax.plot(p[:,0],p[:,1],color=color,label=label,lw=2.2,ls=ls,marker='o',ms=3)
def style(ax):
    ax.grid(alpha=.17);ax.set_aspect('equal');ax.set_xlabel('X / camera height');ax.set_ylabel('Z / camera height')
    ax.spines[['top','right']].set_visible(False)
def main():
    out=HERE/'figures';out.mkdir(exist_ok=True)
    c=read('manual_structure');votes=pd.read_csv(HERE/'GROUP_VOTES.csv.gz')
    fig,axs=plt.subplots(2,2,figsize=(12,9),gridspec_kw={'height_ratios':[1.1,1]})
    for ax,arm in zip(axs[0],['B','C']):
        t=erp(ax,c,arm,(220,550),(435,80));ax.set_title(f'{arm}: {t["nodes"]} nodes | Q={t["B8L2"]:.2f}',color=COL[arm],fontsize=14)
        for j in [3,4,7,8]:
            x,y=c['reference']['points_1024x512'][2*j]
            ax.text(x+4,y-8,f'r{j}',color='white',fontsize=10,bbox=dict(fc='#28364c',alpha=.8,ec='none',pad=2))
    q=votes[votes.case_id=='manual_structure'];inds=[3,4,7,8]
    for offset,arm in [(-.18,'B'),(.18,'C')]:
        # Best-supported group within five degrees; never add split groups together.
        vals=[]
        for j in inds:
            g=q[(q.arm==arm)&(q.nearest_reference_corner==j)&(q.paired_bound_distance_deg<=5)].sort_values('support',ascending=False).iloc[0]
            vals.append(int(g.support))
        axs[1,0].bar(np.arange(4)+offset,vals,.34,label=arm,color=COL[arm])
        for x,y in zip(np.arange(4)+offset,vals):axs[1,0].text(x,y+.25,str(y),ha='center',fontsize=11)
    axs[1,0].axhline(10,color='#253448',ls='--',label='n20 threshold = 10')
    axs[1,0].set_xticks(range(4),[f'r{x}' for x in inds]);axs[1,0].set_ylim(0,17);axs[1,0].set_ylabel('Distinct worker support');axs[1,0].legend(frameon=False,loc='upper left');axs[1,0].set_title('Necessary turns gain sufficient support')
    axs[1,0].text(.02,-.21,'Best-supported group within 5 degrees shown.\nSplit groups are retained in the full ledger, not summed.',transform=axs[1,0].transAxes,fontsize=9,color='#596476')
    ring(axs[1,1],c['reference']['floor_xz_h'],'#39485a','Fixed reference','--')
    for t in c['teams'][1:]:ring(axs[1,1],t['geometry']['footprint'],COL[t['label']],t['label'])
    style(axs[1,1]);axs[1,1].legend(frameon=False);axs[1,1].set_title('More complete shape, but extension remains')
    fig.suptitle('B6-47 | Manual n20/m7 | Same D, ordinary-expression block to more-turn block',fontsize=14,y=.98)
    fig.subplots_adjust(top=.92,bottom=.10,hspace=.30,wspace=.25);fig.savefig(out/'STRUCTURE_LOCAL_VOTES.png',dpi=170);plt.close(fig)
    c20,c21=read('manual_threshold20'),read('manual_threshold21')
    fig,axs=plt.subplots(2,2,figsize=(12,9))
    for ax,cx in zip(axs[0],[c20,c21]):
        t=erp(ax,cx,'C',(560,760),(430,105));ax.set_title(f'n={cx["n"]}: {t["nodes"]} nodes | Q={t["B8L2"]:.2f}',fontsize=14,color=COL['C'])
    for i,n in enumerate([20,21]):
        vals=[11,11,10]
        axs[1,0].bar(np.arange(3)+(i-.5)*.32,vals,.30,color=['#6b9fbf','#674b92'][i],label=f'n={n}')
    axs[1,0].axhline(10,color='#6b9fbf',ls='--',label='threshold 10')
    axs[1,0].axhline(11,color='#674b92',ls='--',label='threshold 11')
    axs[1,0].set_xticks(range(3),['A','B','C']);axs[1,0].set_ylim(0,14.3);axs[1,0].set_ylabel('Critical r1 support');axs[1,0].legend(frameon=False,ncol=2);axs[1,0].set_title('Same ten C votes, higher required threshold')
    axs[1,0].text(.02,-.22,'Only W121 joins the common background.\nCritical observations and their grouping are identical.',transform=axs[1,0].transAxes,fontsize=10,color='#596476')
    ring(axs[1,1],c20['reference']['floor_xz_h'],'#39485a','Fixed reference','--')
    ring(axs[1,1],c20['teams'][2]['geometry']['footprint'],'#6b9fbf','C at n20')
    ring(axs[1,1],c21['teams'][2]['geometry']['footprint'],'#674b92','C at n21')
    style(axs[1,1]);axs[1,1].legend(frameon=False);axs[1,1].set_title('The return corner is lost')
    fig.suptitle('7y-03 | Fixed X/Y/Z, m=4 | More-turn to ordinary-expression block',fontsize=14,y=.98)
    fig.subplots_adjust(top=.92,bottom=.10,hspace=.30,wspace=.25);fig.savefig(out/'THRESHOLD_REVERSAL.png',dpi=170);plt.close(fig)
    cf=read('manual_failure');t=cf['teams'][2]
    fig,axs=plt.subplots(1,2,figsize=(11,5))
    erp(axs[0],cf,'C',(405,515),(435,80));axs[0].set_title('One side retained: r7 gets 10 votes\nOpposite side r8 stays below 10')
    ring(axs[1],cf['reference']['floor_xz_h'],'#39485a','Fixed reference','--')
    ring(axs[1],t['geometry']['footprint'],COL['C'],'Invalid C ring')
    axs[1].scatter([-.3482852463],[-1.331797075],s=90,c='#cb3046',marker='x',zorder=5,label='Self-intersection')
    axs[1].set_xlim(-.65,0);axs[1].set_ylim(-1.6,-.4);style(axs[1]);axs[1].legend(frameon=False,fontsize=9,loc='lower left')
    fig.suptitle('B6-47 | Manual n20/m4 | Partial structural support leads to an invalid connection',fontsize=12)
    fig.tight_layout(rect=(0,0,1,.90));fig.savefig(out/'FAILURE_LOCAL_CONNECTION.png',dpi=170);plt.close(fig)
    print('saved 3 local mechanism figures; no fusion or scoring')

if __name__=='__main__':main()
