#!/usr/bin/env python3
"""Render exact computed research figures; no external resources or AI images."""
from __future__ import annotations
import argparse,io,json,math,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from export_real_descriptors import read,write,sha

NAMES={'baseline_quad08':'Baseline','J_main_hill_tail12_g1_l025':'Recommended',
       'J_simple_power8_g1_l025':'Simple quadratic','J_local_joint_hinge10_w2_s8':'Joint hinge'}
COLORS={'baseline_quad08':'#65758b','J_main_hill_tail12_g1_l025':'#115e83',
        'J_simple_power8_g1_l025':'#bd6f21','J_local_joint_hinge10_w2_s8':'#745597'}


def save(fig,path):
    fig.tight_layout(pad=1.6);buf=io.BytesIO();fig.savefig(buf,format='png',dpi=160,facecolor='white')
    data=buf.getvalue()
    with Image.open(io.BytesIO(data)) as im:im.load()
    tmp=path.with_suffix('.pending');tmp.write_bytes(data);tmp.replace(path)
    fig.savefig(path.with_suffix('.svg'),facecolor='white',metadata={'Date':None});plt.close(fig)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,default=Path(__file__).parent/'results')
    ap.add_argument('--out',type=Path,default=Path(__file__).parent/'figures');args=ap.parse_args()
    results=args.results;out=args.out;out.mkdir(parents=True,exist_ok=True)
    val=read(results/'candidate_validation_controls.json');rows=val['rows'];by={r['case_id']:r for r in rows}
    raw=read(results/'targeted_metrics.json');geom=read(results/'targeted_constructed_cases.json')['cases'];gby={r['case_id']:r for r in geom}
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold',
                         'svg.hashsalt':'quality-experiments-20261013'})
    fig,axs=plt.subplots(1,3,figsize=(16,4.8))
    d=np.linspace(0,90/math.sqrt(12),500);base=1.5*d*d/(d*d+37.5)
    for name,q in [('baseline_quad08',100/(1+base)),('J_main_hill_tail12_g1_l025',100/(1+base+(d/12)**4)),('J_simple_power8_g1_l025',100/(1+(d/8)**2))]:
        axs[0].plot(d,q,label=NAMES[name],color=COLORS[name],lw=2)
    axs[0].set(title='Direction-only response',xlabel='Common-axis D (degrees)',ylabel='Score with I=1, other errors=0',ylim=(0,102));axs[0].legend(fontsize=8)
    short=sorted([r for r in rows if r['family']=='vanishing_short_oblique_edge'],key=lambda r:r['metadata']['cut_h'])
    for name in NAMES:
        axs[1].plot([r['metadata']['cut_h'] for r in short],[r['scores'][name]['score'] for r in short],marker='o',ms=3,lw=1.5,color=COLORS[name],label=NAMES[name])
    axs[1].set_xscale('log');axs[1].set(title='Vanishing oblique edge',xlabel='Chamfer cut / camera height',ylabel='Full geometry score',ylim=(0,102));axs[1].legend(fontsize=8)
    switch=read(results/'axis_switch_counterexample.json')['cases']
    # The exact switching construction provides six orders of perturbation;
    # use an ordered categorical axis so the near-zero jump remains visible.
    near=[c for c in switch if abs(c['epsilon'])<=1e-7]
    x=np.arange(len(near))
    axs[2].plot(x,[c['jointly_optimized_hinge']['L2_selected_axis_value_deg2']/64 for c in near],'o-',label='Hinge on L2-selected axis',color='#a84731')
    axs[2].plot(x,[c['jointly_optimized_hinge']['value_deg2']/64 for c in near],'o-',label='Jointly minimized hinge',color='#115e83')
    axs[2].set_xticks(x,[f'{c["epsilon"]:+.0e}' for c in near],rotation=30)
    axs[2].set(title='L2-axis switch counterexample',xlabel='Perturbation of one length weight',ylabel='Direction loss (degrees squared / 64)');axs[2].legend(fontsize=8)
    save(fig,out/'direction_tail_and_axis_switch.png')
    anchors=raw['reference_bindings'];fig,axs=plt.subplots(2,3,figsize=(14,8),sharex=True,sharey=True)
    kinds=['floor_shear','local_height','global_height'];cols=['#a84731','#bd8b23','#167280'];main='J_main_hill_tail12_g1_l025'
    for ax,binding in zip(axs.ravel(),anchors):
        triple=[r for r in val['matched_priority'] if r['anchor_record_id']==binding['anchor_record_id']]
        for kind,col in zip(kinds,cols):
            ax.plot([r['endpoint_rms_budget_deg'] for r in triple],[r['scores'][main][kind] for r in triple],marker='o',lw=2,color=col,label=kind.replace('_',' '))
        ax.set_title(binding['image_code']+f'\nclosest horizon: {binding["min_floor_elevation_deg"]:.2f} deg',fontsize=10)
        ax.set_ylim(0,102);ax.grid(alpha=.18);ax.set_xticks([.5,1,2,4,8])
    axs[0,0].legend(fontsize=8);fig.suptitle('Equal corner-ray RMS budget: response check, not perceptual equivalence',fontsize=13,y=.99)
    fig.supxlabel('RMS geodesic displacement across all top and bottom vertices (degrees)');fig.supylabel('Recommended score')
    save(fig,out/'matched_angular_budget.png')
    fig,axs=plt.subplots(1,2,figsize=(13,4.8))
    pairs=val['projection_height_attribution']
    for name in ('baseline_quad08',main,'J_simple_power8_g1_l025'):
        x=sorted(set(r['bottom_px'] for r in pairs));y=[max(r['extra_height_score_drop'][name] for r in pairs if r['bottom_px']==p) for p in x]
        axs[0].plot(x,y,marker='o',label=NAMES[name],color=COLORS[name],lw=2)
    axs[0].set(title='Largest extra height deduction by input error',xlabel='Floor vertical shift at ERP height 512 (pixels)',ylabel='Q(fixed world ceiling) - Q(fixed top ray)');axs[0].legend(fontsize=8);axs[0].axvline(0,color='#ddd',lw=1)
    far=[r for r in rows if r['family'] in ('projection_coupling','extreme_projection_coupling') and r['status']=='available' and r['metadata']['anchor_record_id']=='R03345' and r['metadata']['corner_selection']=='farthest_one']
    for policy,style in [('fixed_world_top_height','-'),('fixed_top_ray','--')]:
        rr=sorted([r for r in far if r['metadata']['top_policy']==policy],key=lambda r:r['metadata']['bottom_vertical_displacement_px_ERP512'])
        for name in ('baseline_quad08',main):
            axs[1].plot([r['metadata']['bottom_vertical_displacement_px_ERP512'] for r in rr],[r['scores'][name]['score'] for r in rr],style,label=NAMES[name]+'; '+('fixed height' if policy=='fixed_world_top_height' else 'fixed top ray'),color=COLORS[name],lw=2)
    axs[1].set(title='Far reference: one floor corner moved',xlabel='Floor vertical shift at ERP height 512 (pixels)',ylabel='Full score');axs[1].legend(fontsize=7)
    fig.suptitle('Negative shift approaches horizon; invalid horizon crossings remain unavailable',fontsize=12,y=.99)
    save(fig,out/'projection_coupling_range.png')
    show=['orthogonal_omission_w0.1_d4','narrow_deep_spike_0.002','equal_area_shift_1','equal_area_stretch']
    fig,axs=plt.subplots(2,2,figsize=(12,8))
    for ax,cid in zip(axs.ravel(),show):
        c=gby[cid];r=by[cid]
        for layer,col,label in [('reference','#176b88','Fixed reference'),('annotation','#c66b35','Constructed annotation')]:
            p=np.asarray(c[layer]['bottom3d'])[:,[0,2]];p=np.vstack([p,p[0]])
            ax.fill(p[:,0],p[:,1],color=col,alpha=.12);ax.plot(p[:,0],p[:,1],'o-',color=col,lw=1.5,ms=3,label=label)
        q=r['scores'][main]['score'];rawr=next(x for x in raw['rows'] if x['case_id']==cid)
        ax.set_title(cid.replace('_',' ')+f'\nI={rawr["metrics"]["iou_2d"]:.4f}; D={rawr["metrics"]["dir"]:.4f} deg; Q={q:.2f}',fontsize=10)
        ax.set_aspect('equal');ax.set_xlabel('x / camera height');ax.set_ylabel('z / camera height');ax.grid(alpha=.18)
    axs[0,0].legend(fontsize=8)
    save(fig,out/'floor_metric_blindspots.png')
    manifest=[]
    for p in sorted(out.glob('*.png')):
        with Image.open(p) as im:im.load();size=list(im.size)
        manifest.append({'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size,'decoded_dimensions':size})
    write(out/'FIGURE_VERIFICATION.json',{'figures':manifest,'all_fully_decoded':True})
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
