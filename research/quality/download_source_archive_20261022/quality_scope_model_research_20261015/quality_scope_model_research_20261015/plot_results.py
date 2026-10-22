"""Generate separate analytic figures; no raw panorama or unconfirmed top is fabricated."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def generate(results,output):
    output.mkdir(parents=True,exist_ok=True)
    geom=json.loads((results/'two_image_geometries.json').read_text());rows=pd.read_csv(results/'two_image_floor_updates_28.csv').set_index('record_id')
    limits={}
    for im in {x['image_code'] for x in geom}:
        v=np.concatenate([np.asarray(x[k]) for x in geom if x['image_code']==im for k in ['candidate_floor','old_floor','new_floor']]);span=np.ptp(v,axis=0);margin=np.maximum(.12*span,.25)
        limits[im]=(v.min(axis=0)-margin,v.max(axis=0)+margin)
    for x in geom:
        rid=x['record_id'];r=rows.loc[rid];fig,ax=plt.subplots(figsize=(9.2,5.8))
        for key,label,ls,marker in [('old_floor','Retained original GT','--','o'),('new_floor','New confirmed FLOOR only','-','s'),('candidate_floor','Archived manual answer',':','.')]:
            p=np.asarray(x[key]);p=np.r_[p,p[:1]];ax.plot(p[:,0],p[:,1],linestyle=ls,marker=marker,label=label,linewidth=1.6)
        for i,(xx,zz) in enumerate(x['new_floor']):ax.annotate('N'+str(i),(xx,zz),xytext=(5,5),textcoords='offset points',fontsize=9)
        ax.plot([0],[0],marker='x',markersize=9,linestyle='none',label='Camera')
        lo,hi=limits[x['image_code']];ax.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),xlabel='X / camera height',ylabel='Z / camera height',aspect='equal')
        ax.set_title(f"{x['image_code']} | {rid} | {r.worker_id}\nFloor IoU: old {r.old_IoU2D100:.2f}% / new {r.new_IoU2D100:.2f}%",fontsize=12)
        ax.grid(alpha=.25);fig.legend(*ax.get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.055),ncol=2,fontsize=9)
        fig.text(.5,.025,'Archived coordinates reconciled numerically; current arrays and visual scope unverified. No new ceiling.',ha='center',fontsize=8)
        fig.tight_layout(rect=(0,.17,1,.98));fig.savefig(output/f'floor_{rid}.png',dpi=145);plt.close(fig)
    controls=pd.read_csv(results/'synthetic_controls.csv')
    s=controls[(controls.group=='near_correct_shear')&(controls.amplitude<=.2)].copy();s['wall_angle_deviation']=np.degrees(np.arctan(s.amplitude))
    fig,ax=plt.subplots(figsize=(8.3,5.5))
    for col,label in [('WQ','WQ-LS08'),('Q_half','D coefficient 0.5'),('Q_noD','No D term'),('IoU3D100','Original prism 3D IoU')]:ax.plot(s.wall_angle_deviation,s[col],marker='o',label=label)
    ax.set(xlabel='Actual adjacent-wall angle deviation from 90 degrees',ylabel='Score / 100',ylim=(45,102),title='Smooth shear: small-error asymptotics versus moderate-error cost');ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(output/'smooth_shear_response.png',dpi=180);plt.close(fig)
    s=controls[controls.group=='family_collapse'].sort_values('amplitude',ascending=False)
    fig,ax=plt.subplots(figsize=(8.3,5.5));ax.plot(s.amplitude,s.D,marker='o',label='D: own orthogonal-axis residual');ax.plot(s.amplitude,s.known_corner_angle_rms,marker='s',label='Known corresponding corner-angle error')
    ax.set(xlabel='Rhombus acute angle (90 = reference square)',ylabel='Degrees',xlim=(92,0),title='Axis-family reassignment is not true angle recovery');ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(output/'direction_family_fold.png',dpi=180);plt.close(fig)
    s=controls[controls.group=='same_surface_subdivision']
    fig,ax=plt.subplots(figsize=(8.3,5.5))
    ax.plot(s.amplitude,s.WQ,marker='o',label='WQ-LS08');ax.plot(s.amplitude,s.IoU3D100,marker='s',label='Corner-mean prism 3D IoU')
    ax.set(xlabel='Inserted collinear vertices on one low-height wall',ylabel='Score / 100',ylim=(87,102),title='Exactly the same declared 3D surface; different vertex density');ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(output/'subdivision_response.png',dpi=180);plt.close(fig)
    syn=json.loads((results/'synthetic_geometries.json').read_text());om=next(x for x in syn if x['case']=='orthogonal_branch_omitted');r=controls[controls['case']=='orthogonal_branch_omitted'].iloc[0]
    fig,ax=plt.subplots(figsize=(6.6,6.2))
    for k,label,ls in [('reference','Reference: narrow orthogonal branch','--'),('candidate','Answer: branch omitted','-')]:
        p=np.asarray(om[k]);p=np.r_[p,p[:1]];ax.plot(p[:,0],p[:,1],linestyle=ls,marker='o',label=label)
    ax.plot([0],[0],marker='x',linestyle='none',label='Camera');ax.set(aspect='equal',xlabel='X / camera height',ylabel='Z / camera height',title=f"Omission control: D = 0, IoU = {100*r.I:.2f}%, WQ = {r.WQ:.2f}")
    ax.grid(alpha=.25);ax.legend(loc='upper left',fontsize=8);fig.tight_layout();fig.savefig(output/'narrow_branch_omission.png',dpi=180);plt.close(fig)
    s=controls[controls.group=='uniform_height'];fig,ax=plt.subplots(figsize=(8.3,5.5));ax.plot(s.amplitude,s.WQ,marker='o',label='WQ-LS08');ax.plot(s.amplitude,s.IoU3D100,marker='s',label='Original prism 3D IoU')
    ax.set(xlabel='Answer total room height / reference total height',ylabel='Score / 100',title='Lower priority does not imply a fixed small maximum penalty',ylim=(0,103));ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(output/'global_height_response.png',dpi=180);plt.close(fig)
    return len(list(output.glob('*.png')))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print('Saved figures:',generate(a.results,a.output))
