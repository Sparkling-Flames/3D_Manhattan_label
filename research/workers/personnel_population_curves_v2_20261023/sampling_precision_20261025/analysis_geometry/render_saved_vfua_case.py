"""Redraw the VFua mechanism figure from its small delivered JSON only.

This route does not require the optional full-state archive or the repository.
"""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from plot_geometry_precision import save_fig


def raw_floor(points):
    a=np.asarray(points,float)[1::2];r=1/np.tan(np.pi*(a[:,1]/512-.5));t=2*np.pi*(a[:,0]/1024-.5)
    return np.c_[r*np.sin(t),-r*np.cos(t)]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    with gzip.open(a.data,'rt') as f:d=json.load(f)
    output=Path(a.out);output.parent.mkdir(parents=True,exist_ok=True)
    rows={r['absent_worker']:r for r in d['selected_endpoints']};geos={r['absent_worker']:r['geometry'] for r in d['geometries']}
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,4,figsize=(15,4.5),constrained_layout=True)
    ref=np.asarray(d['reference']['floor_xz_h']);rr=np.r_[ref,ref[:1]]
    for ax,who in zip(axes,['W103','W113','W134','FULL35']):
        row=rows[who];floor=np.asarray(geos[who]['footprint'])
        ax.fill(rr[:,0],rr[:,1],color='#f0f0f0',zorder=0);ax.plot(rr[:,0],rr[:,1],color='#333333',lw=1.7,label='Frozen reference')
        if who!='FULL35':
            raw=raw_floor(d['selected_raw_answers'][who]['points']);raw=np.r_[raw,raw[:1]];ax.plot(raw[:,0],raw[:,1],':',color='#7856a3',lw=1.2,alpha=.85,label='Absent worker raw answer')
        if row['complete_floor_evaluable']:
            ff=np.r_[floor,floor[:1]];ax.plot(ff[:,0],ff[:,1],'-o',color='#d45d25',lw=2,ms=4,label='Consensus')
        else:ax.scatter(floor[:,0],floor[:,1],c='#bd3030',marker='x',s=55,label='Incomplete selected nodes')
        ax.scatter([0],[0],c='#267a9c',marker='^',s=35,label='Camera')
        label='Full N=35' if who=='FULL35' else 'N=34, absent '+who
        score=f"Q={row['B8L2']:.2f}" if row['B8L2'] is not None else 'Q unavailable (failure)'
        ax.set_title(f"{label}\n{int(row['nodes'])} nodes; {score}");ax.set_aspect('equal');ax.set_xlim(-2.25,2.85);ax.set_ylim(-2.7,1.0);ax.set_xlabel('x / camera height');ax.grid(alpha=.15)
    axes[0].set_ylabel('z / camera height');handles,labels=axes[0].get_legend_handles_labels();h2,l2=axes[-1].get_legend_handles_labels();allleg=dict(zip(labels+l2,handles+h2))
    fig.legend(allleg.values(),allleg.keys(),loc='outside lower center',ncol=3,frameon=False)
    fig.suptitle('VFuaQ6m2Qom-04: one absent member changes which 17-vote group survives',fontsize=14)
    save_fig(fig,output)
    print('Saved',output.with_suffix('.png'),output.with_suffix('.pdf'))


if __name__=='__main__':main()
