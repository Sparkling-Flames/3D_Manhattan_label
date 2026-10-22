#!/usr/bin/env python3
"""Exact, score-free review images. No unshared-x 3-D room is constructed."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from mpl_toolkits.mplot3d.art3d import Line3DCollection

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pixels(v):
    v=np.asarray(v,float)
    x=((np.arctan2(v[:,0],-v[:,2])/(2*np.pi)+.5)*1024)%1024
    y=(.5-np.arctan2(v[:,1],np.linalg.norm(v[:,[0,2]],axis=1))/np.pi)*512
    return np.c_[x,y]
def rays(p):
    p=np.asarray(p,float);u=(p[:,0]/1024-.5)*2*np.pi;v=(.5-p[:,1]/512)*np.pi
    return np.c_[np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)]
def arc(a,b,n=192):
    a=np.asarray(a,float);a=a/np.linalg.norm(a);b=np.asarray(b,float);b=b/np.linalg.norm(b)
    theta=np.arctan2(np.linalg.norm(np.cross(a,b)),np.dot(a,b))
    if theta<1e-12:return np.tile(a,(n,1))
    assert theta<np.pi-1e-10,'Ambiguous antipodal arc must not be inferred.'
    t=np.linspace(0,1,n)
    return (np.sin((1-t)*theta)[:,None]*a+np.sin(t*theta)[:,None]*b)/np.sin(theta)
def draw_segment(ax,a,b,color,lw=1.2,alpha=1,ls='-'):
    p=pixels(arc(a,b));xx=np.unwrap(p[:,0]*2*np.pi/1024)*1024/(2*np.pi)
    for off in [-1024,0,1024]:ax.plot(xx+off,p[:,1],color=color,lw=lw,alpha=alpha,ls=ls,zorder=3)
def draw_rings(ax,top,bottom,color,lw=1.25,pair_ls='-',alpha=1):
    for q in [top,bottom]:
        for i in range(len(q)):draw_segment(ax,q[i],q[(i+1)%len(q)],color,lw,alpha)
    for t,b in zip(top,bottom):draw_segment(ax,t,b,color,lw*.6,alpha,pair_ls)
def draw_geometry_erp(ax,g,color,lw=1.2):
    draw_rings(ax,np.asarray(g['top3d']),np.asarray(g['bottom3d']),color,lw)
def draw_current(ax,c,color,lw=1.1):
    o=c['current_formal_input'];idx=o.get('ordered_source_point_indices');before=o.get('before_preprocessing_points')
    if idx and before:
        p=np.asarray(before)[idx];r=rays(p);draw_rings(ax,r[::2],r[1::2],color,lw,pair_ls='--')
    elif before:p=np.asarray(before)
    else:p=np.asarray(o['original_export_points'])
    for off in [-1024,0,1024]:ax.scatter(p[:,0]+off,p[:,1],s=24,marker='o',facecolor=color,edgecolor='#1f1f1f',lw=.4,zorder=6)
def draw_processed_points(ax,c,color):
    p=c['current_formal_input'].get('points_1024x512')
    if not p:return
    p=np.asarray(p)
    for off in [-1024,0,1024]:ax.scatter(p[:,0]+off,p[:,1],s=37,marker='x',color=color,lw=1.2,zorder=7)
def background(ax,img,repeat=False):
    for off in [-1024,0,1024] if repeat else [0]:ax.imshow(img,extent=(off,1024+off,512,0),interpolation='nearest',zorder=0)
def full_axes(ax):
    ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_aspect('equal')
    ax.set_xticks([0,256,512,768,1024]);ax.set_yticks([0,128,256,384,512]);ax.tick_params(labelsize=9)
    ax.set_xlabel('ERP x (1024-coordinate domain)',fontsize=9);ax.set_ylabel('ERP y',fontsize=9)
def limits_for(records):
    groups={}
    for c in records:
        key=c['scale_group'];groups.setdefault(key,[])
        for g in [c['fixed_reference_geometry'],c['frozen_annotation_geometry']]:
            if g:
                for k in ['top3d','bottom3d']:groups[key].append(np.asarray(g[k])[:,[0,2,1]])
    ans={}
    for key,qs in groups.items():
        q=np.vstack(qs+[np.zeros((1,3))]);lo=q.min(0);hi=q.max(0);span=np.maximum(hi-lo,.2);pad=.08*span
        ans[key]={'lo':(lo-pad).tolist(),'hi':(hi+pad).tolist(),'physical_axis_range':(hi-lo+2*pad).tolist()}
    return ans
def geometry_axes(fig,gs,c,limits,col,views):
    lo=np.asarray(limits['lo']);hi=np.asarray(limits['hi']);span=hi-lo
    ax=fig.add_subplot(gs[0]);handles=[]
    for g,color,label in [(c['fixed_reference_geometry'],col['ref'],'Fixed reference'),(c['frozen_annotation_geometry'],col['processed'],'Processed annotation')]:
        if not g:continue
        q=np.asarray(g['bottom3d'])[:,[0,2]];q=np.r_[q,q[:1]]
        line,=ax.plot(q[:,0],q[:,1],'-o',color=color,ms=3,lw=1.65,label=label);handles.append(line)
    ax.scatter([0],[0],marker='+',color='#20242a',s=60,zorder=5)
    ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.18)
    ax.set_xlabel('x/h',fontsize=9);ax.set_ylabel('z/h',fontsize=9);ax.set_title(c['blind_id']+'  |  Floor',fontsize=11)
    ax.tick_params(labelsize=8);ax.xaxis.set_major_locator(MaxNLocator(4));ax.yaxis.set_major_locator(MaxNLocator(4))
    for j,(elev,azim) in enumerate(views,1):
        ax=fig.add_subplot(gs[j],projection='3d');ax.set_proj_type('ortho')
        for g,color in [(c['fixed_reference_geometry'],col['ref']),(c['frozen_annotation_geometry'],col['processed'])]:
            if not g:continue
            t=np.asarray(g['top3d'])[:,[0,2,1]];b=np.asarray(g['bottom3d'])[:,[0,2,1]];segments=[]
            for q in [t,b]:segments.extend([[q[i],q[(i+1)%len(q)]] for i in range(len(q))])
            segments.extend(zip(t,b));ax.add_collection3d(Line3DCollection(segments,colors=color,linewidths=1.45))
        ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_zlim(lo[2],hi[2]);ax.set_box_aspect(span)
        ax.view_init(elev,azim);ax.set_xlabel('x/h',fontsize=8,labelpad=2);ax.set_ylabel('z/h',fontsize=8,labelpad=2);ax.set_zlabel('vertical/h',fontsize=8,labelpad=3)
        for axis in [ax.xaxis,ax.yaxis,ax.zaxis]:axis.set_major_locator(MaxNLocator(3))
        ax.tick_params(labelsize=7,pad=0);ax.set_title(c['blind_id']+f'  |  3D view {j}',fontsize=11)
    return handles
def save(fig,path,manifest,kind,cases):
    fig.savefig(path,dpi=160,facecolor='white',pil_kwargs={'quality':92});plt.close(fig)
    manifest.append({'filename':path.name,'kind':kind,'blind_ids':cases,'sha256':sha(path),'bytes':path.stat().st_size,
                     'no_quality_scores_or_expected_answers':True})

def main():
    a=argparse.ArgumentParser();a.add_argument('--review-dir',type=Path,default=Path(__file__).resolve().parent);a.add_argument('--cases',help='Optional comma-separated blind IDs to draw; existing other images are preserved.');args=a.parse_args()
    root=args.review_dir.resolve();cfg=read(root/'review_config.json');data=read(root/'inputs/review_inputs.json');records=data['records']
    out=root/'figures';out.mkdir(parents=True,exist_ok=True);manifest=read(out/'manifest.json') if args.cases and (out/'manifest.json').exists() else []
    col={'ref':cfg['color_reference'],'raw':cfg['color_current_before'],'processed':cfg['color_processed']};limits=limits_for(records)
    if args.cases:records=[c for c in records if c['blind_id'] in args.cases.split(',')]
    for c in records:
        image_path=root/c['photo']['relative_path'];assert sha(image_path)==c['photo']['sha256'];im=np.asarray(Image.open(image_path).convert('RGB'))
        bid=c['blind_id'];ref=c['fixed_reference_geometry'];g=c['frozen_annotation_geometry']
        # Two complete ERP plots share the exact coordinate frame. This prevents
        # a clipped local region or differently scaled panorama implying quality.
        fig,axes=plt.subplots(2,1,figsize=(13.5,14.35));fig.subplots_adjust(left=.06,right=.985,bottom=.035,top=.967,hspace=.16)
        for ax in axes:background(ax,im);draw_geometry_erp(ax,ref,col['ref']);full_axes(ax)
        draw_current(axes[0],c,col['raw']);axes[0].set_title(bid+'  |  Current edited input, before shared x',fontsize=12)
        if g:draw_geometry_erp(axes[1],g,col['processed'],1.45);draw_processed_points(axes[1],c,col['processed'])
        else:draw_current(axes[1],c,col['raw'])
        axes[1].set_title(bid+'  |  Existing processed reconstruction' if g else bid+'  |  No annotation reconstruction',fontsize=12)
        save(fig,out/f'{bid}_input_processed.jpg',manifest,'input_and_processed_erp',[bid])
        # Identical crop coordinates for the same-image pair are fixed in config.
        fig,axes=plt.subplots(1,len(c['crops']),figsize=(12.5,6.5));axes=np.atleast_1d(axes)
        for k,(ax,box) in enumerate(zip(axes,c['crops']),1):
            background(ax,im,True);draw_geometry_erp(ax,ref,col['ref'],1.45);draw_current(ax,c,col['raw'],1.3)
            if g:draw_geometry_erp(ax,g,col['processed'],1.2);draw_processed_points(ax,c,col['processed'])
            x0,y0,x1,y1=box;ax.set_xlim(x0,x1);ax.set_ylim(y1,y0);ax.set_aspect('equal')
            ax.set_title(bid+f'  |  Detail {k}',fontsize=11);ax.set_xlabel('ERP x',fontsize=9);ax.set_ylabel('ERP y',fontsize=9)
            ax.tick_params(labelsize=8);ax.xaxis.set_major_locator(MaxNLocator(4));ax.yaxis.set_major_locator(MaxNLocator(5))
        fig.subplots_adjust(left=.07,right=.97,top=.93,bottom=.1,wspace=.22)
        save(fig,out/f'{bid}_details.jpg',manifest,'fixed_local_crops',[bid])
        fig=plt.figure(figsize=(15.5,5.65));gs=fig.add_gridspec(1,3,width_ratios=[1,1.12,1.12],left=.05,right=.96,top=.9,bottom=.1,wspace=.21)
        handles=geometry_axes(fig,[gs[0,i] for i in range(3)],c,limits[c['scale_group']],col,cfg['camera_views_degrees'])
        fig.legend(handles,[h.get_label() for h in handles],loc='lower center',ncol=2,fontsize=10,bbox_to_anchor=(.5,.006),frameon=False)
        save(fig,out/f'{bid}_geometry.jpg',manifest,'floor_and_orthographic_3d',[bid])
    # Compact side-by-side judgement board for the existing same-image conflict.
    pair=[c for c in records if c['scale_group']=='same_corridor']
    if len(pair)==2:
        assert pair[0]['image_id']==pair[1]['image_id'] and pair[0]['reference_object_id']==pair[1]['reference_object_id']
        fig=plt.figure(figsize=(15.5,10.6));gs=fig.add_gridspec(2,3,width_ratios=[1,1.12,1.12],left=.05,right=.96,top=.94,bottom=.07,wspace=.21,hspace=.28)
        for row,c in enumerate(pair):handles=geometry_axes(fig,[gs[row,i] for i in range(3)],c,limits[c['scale_group']],col,cfg['camera_views_degrees'])
        fig.legend(handles,[h.get_label() for h in handles],loc='lower center',ncol=2,fontsize=10,bbox_to_anchor=(.5,.005),frameon=False)
        save(fig,out/'B01_B02_same_scale_geometry.jpg',manifest,'same_image_pair_shared_limits',[c['blind_id'] for c in pair])
    manifest=list({m['filename']:m for m in manifest}.values())
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (root/'results/render_geometry_limits.json').write_text(json.dumps({'projection':'orthographic','view_angles':cfg['camera_views_degrees'],
        'no_registration_or_rescaling_of_coordinates':True,'limits_by_scale_group':limits,'quality_scores_in_figures':False},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'figures':len(manifest),'cases':len(records),'score_free':True}))

if __name__=='__main__':main()
