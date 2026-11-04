"""Traceable illustrative ABC footprints, with full polygons and actual Q.

Images are chosen to explain an observed strong effect, a quality exception,
and a negative-GS condition. Within each image, the displayed valid event is
closest to that image's mean (GS, signed quality shift); never the best event.
All inference still uses the entire frozen design.
"""
from __future__ import annotations
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from design import OUT,csv,write_json
from run_native import read_gz

def main():
    ev=pd.read_csv(OUT/'analysis/EVENT_METRICS.csv.gz',low_memory=False);im=pd.read_csv(OUT/'analysis/IMAGE_METRICS.csv.gz')
    pools={p['pool_id']:p for p in read_gz(OUT/'inputs/SELECTED_POOLS.json.gz')['images']}
    rows={r['team_key']:r for p in (OUT/'endpoints/pools').glob('*.json.gz') for r in read_gz(p)['teams']}
    cases=[('uNb9QFRL6hY-50','C1_to_C3','Large quality gain / hard image'),('uNb9QFRL6hY-65','C1_to_C3','Quality exception / easy image'),('jtcxE69GiFV-13','C3_to_C1','Within-class variability exceeds cross-class change')]
    picked=[];records=[]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axes=plt.subplots(1,3,figsize=(15,6.3));fig.subplots_adjust(top=.78,bottom=.28,wspace=.28)
    for ax,(image,direction,title) in zip(axes,cases):
        cell=im[(im.study=='main_8_4')&(im.direction==direction)&(im.image==image)].iloc[0]
        g=ev[(ev.study=='main_8_4')&(ev.direction==direction)&(ev.image==image)&ev.ABC_scored].copy()
        g['case_distance_squared']=(g.Q_GS-cell.Q_GS)**2+(g.Q_class_shift-cell.Q_class_shift)**2
        e=g.sort_values(['case_distance_squared','event_id']).iloc[0];p=pools[e.pool_id]
        f=np.asarray(p['reference']['floor_xz_h']);f=np.vstack([f,f[0]])
        ax.plot(f[:,0],f[:,1],color='black',ls='--',lw=1.7,label='GT')
        for arm,col in zip('ABC',['#3279A1','#58A8AB','#C55155']):
            r=rows[e[arm+'_team_key']];q=np.asarray(r['geometry']['footprint']);q=np.vstack([q,q[0]])
            ax.plot(q[:,0],q[:,1],'-o',lw=1.25,ms=3.6,alpha=.9,color=col,label=f'{arm}: Q={r["B8L2"]:.1f}, {r["nodes"]} nodes')
        ax.scatter([0],[0],marker='+',s=65,c='#333333',linewidth=1.6,zorder=5,label='Camera')
        ax.set_aspect('equal',adjustable='datalim');ax.set_title(image+'\n'+title,fontsize=10,pad=13)
        ax.set_xlabel('x / camera height');ax.set_ylabel('z / camera height');ax.grid(color='#EEEEEE',linewidth=.6)
        ax.legend(loc='best',fontsize=8,frameon=True,facecolor='white',edgecolor='#DDDDDD')
        ax.text(.5,-.22,f'Image mean: GS={cell.Q_GS:+.2f}, shift={cell.Q_class_shift:+.2f}\nShown event: GS={e.Q_GS:+.2f}, shift={e.Q_class_shift:+.2f}',transform=ax.transAxes,ha='center',va='top',fontsize=9)
        picked.append(e)
        records.append(dict(image=image,direction=direction,title=title,event_id=e.event_id,selection_rule='Closest valid event to image mean in (GS,Q_class_shift), unscaled Euclidean Q-point distance',
                            image_mean_GS=cell.Q_GS,image_mean_Q_class_shift=cell.Q_class_shift,
                            pool_id=e.pool_id,reference_id=e.reference_id,reference_version=e.reference_version,
                            endpoints={a:{k:rows[e[a+'_team_key']].get(k) for k in ['team_key','member_workers','member_object_ids','B8L2','D10','nodes','geometry']} for a in 'ABC'},reference=p['reference']))
    fig.suptitle('Exact saved consensus footprints explain both the prevailing pattern and its exceptions',fontsize=14,fontweight='bold',y=.97)
    fig.text(.07,.025,'These are illustrative events from the fixed 8/4 study, selected near each image mean. Full polygons are retained; no coordinates or orders are edited.\nThe hard-image GT itself is not camera-star-shaped. It remains a valid frozen reference under the official research scoring contract.',fontsize=9,color='#444444')
    for ext in ['png','svg','pdf']:fig.savefig(OUT/f'figures/C13_TRACEABLE_ABC_CASES.{ext}',bbox_inches='tight',dpi=200)
    plt.close(fig)
    csv(OUT/'analysis/ILLUSTRATIVE_EVENT_TRACE.csv.gz',pd.DataFrame(picked))
    write_json(OUT/'analysis/ILLUSTRATIVE_CASES.json.gz',records)

if __name__=='__main__':main()
