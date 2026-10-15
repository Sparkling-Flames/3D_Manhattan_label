"""Diagnostic figures. Uses matplotlib default colors; no source annotation edits.
Each chart is a separate figure. Panorama overlays use the exact frozen geometry.
"""
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from core import *

def projected_line(points):
    x=np.asarray(points);r=np.linalg.norm(x[:,[0,2]],axis=1)
    u=(np.arctan2(x[:,0],-x[:,2])/(2*np.pi)+.5)*1024
    v=(.5-np.arctan2(x[:,1],r)/np.pi)*512
    uv=np.c_[u,v];out=[]
    for i,p in enumerate(uv):
        if i and abs(p[0]-uv[i-1,0])>512:out.append([np.nan,np.nan])
        out.append(p)
    return np.array(out)

def sampled_wire(g,n=100):
    a=np.array(g['bottom3d']);b=np.array(g['top3d']);wire=[]
    for ring in [a,b]:
        for p,q in zip(ring,np.roll(ring,-1,axis=0)):
            wire.extend((p[None,:]+np.linspace(0,1,n)[:,None]*(q-p)[None,:]).tolist());wire.append([np.nan]*3)
    for p,q in zip(a,b):wire.extend((p[None,:]+np.linspace(0,1,n)[:,None]*(q-p)[None,:]).tolist());wire.append([np.nan]*3)
    return np.array(wire)

def draw_views(code,records,objects,image_path,labels=None):
    geoms=[geometry(objects[r['object_id']]['points_1024x512']) for r in records]
    refid=records[0].get('reference_object_id') or records[0]['reference']['object_id']
    geoms.append(geometry(objects[refid]['points_1024x512']))
    labels=labels or [r['record_id'] for r in records];labels=labels+['Reference']
    fig,ax=plt.subplots(figsize=(7,7))
    for g,label in zip(geoms,labels):
        p=np.array(g['bottom3d'])[:,[0,2]];p=np.r_[p,p[:1]];ax.plot(p[:,0],p[:,1],'-o',label=label)
    ax.scatter([0],[0],marker='*',s=100,label='Camera');ax.set_aspect('equal',adjustable='box');ax.grid(True);ax.set_xlabel('X / camera height');ax.set_ylabel('Z / camera height');ax.set_title(code+' | BEV (same scale)');ax.legend();fig.tight_layout();fig.savefig(ROOT/'figures'/f'{code}_bev.png',dpi=150);plt.close(fig)
    fig=plt.figure(figsize=(8,7));ax=fig.add_subplot(111,projection='3d')
    allp=np.concatenate([np.array(g[k])[:,[0,2,1]] for g in geoms for k in ['bottom3d','top3d']]+[np.zeros((1,3))]);mid=(allp.min(0)+allp.max(0))/2;rad=np.max(np.ptp(allp,axis=0))*.54
    for g,label in zip(geoms,labels):
        p=sampled_wire(g,2)[:,[0,2,1]];ax.plot(p[:,0],p[:,1],p[:,2],label=label,linewidth=1.5)
    ax.scatter([0],[0],[0],marker='*',s=65,label='Camera');ax.set_xlim(mid[0]-rad,mid[0]+rad);ax.set_ylim(mid[1]-rad,mid[1]+rad);ax.set_zlim(mid[2]-rad,mid[2]+rad);ax.set_box_aspect([1,1,1]);ax.set_xlabel('X / h');ax.set_ylabel('Z / h');ax.set_zlabel('Y / h');ax.set_title(code+' | 3D (same scale; h=camera height)');ax.legend(loc='upper left');ax.view_init(elev=24,azim=-55);fig.tight_layout();fig.savefig(ROOT/'figures'/f'{code}_3d.png',dpi=160);plt.close(fig)
    if image_path.exists():
        im=Image.open(image_path)
        fig,ax=plt.subplots(figsize=(14,7));ax.imshow(im,extent=[0,1024,512,0])
        for g,label in zip(geoms,labels):
            p=projected_line(sampled_wire(g));ax.plot(p[:,0],p[:,1],label=label,linewidth=1.1)
        ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_title(code+' | Fixed processed geometry / original panorama');ax.legend();fig.tight_layout();fig.savefig(ROOT/'figures'/f'{code}_overlay.png',dpi=160);plt.close(fig)

def main():
    c=read(INPUT/'data/cohorts.json');o={r['object_id']:r for r in read(INPUT/'data/objects.json')['objects']};by={r['record_id']:r for k in ['ordinary','doorway','historical_only'] for r in c[k]}
    for code,ids in [('J04',['R03274']),('J01',['R03346','R03347']),('Q03',['R01501','R01191']),('Q01',['R03332','R03329']),('Q02',['R02200','R00990'])]:
        rr=[by[rid] for rid in ids];draw_views(code,rr,o,INPUT/'photos'/f"{rr[0]['image_id']}.png")
    s=read(INPUT/'data/supplement.json')['doorway_images'];selected=[r for r in s if r['counts'].get('complete')]
    for k in range(0,len(selected),4):
        # Source-image contact sheet, not a synthetic image or a metric chart.
        subset=selected[k:k+4];canvas=Image.new('RGB',(2048,1080),'white');d=ImageDraw.Draw(canvas)
        for j,r in enumerate(subset):
            im=Image.open(INPUT/r['photo']).convert('RGB');im=im.resize((1024,512));x=(j%2)*1024;y=(j//2)*540
            canvas.paste(im,(x,y+25));d.text((x+8,y+5),r['image']['image_code']+' | '+r['image']['image_id'],fill='black')
        canvas.save(ROOT/'figures'/f'doorway_originals_{k//4+1}.jpg',quality=93)
    # Each diagnostic curve is its own figure, no multi-panel plots.
    m=read(ROOT/'results/mechanism_controls.json');rr=[r for r in m['dense_bottom'] if r.get('shape')==[1,4] and r['mode']=='distributed_bottom' and r['sign']==-1 and r['status']=='complete']
    fig,ax=plt.subplots(figsize=(8,5))
    for name,label in [('historical_tail12_g1','Historical tail'),('current_hill08','Current hill08'),('loss_sum','WQ-LS08'),('max_floor','Max-floor probe')]:ax.plot([r['budget'] for r in rr],[r['scores'][name]['score'] for r in rr],'-o',label=label)
    ax.set_xlabel('Bottom y RMS perturbation / pixels');ax.set_ylabel('Complete Q');ax.set_title('Narrow rectangle: complete reconstruction');ax.grid(True);ax.legend();fig.tight_layout();fig.savefig(ROOT/'figures/bottom_response.png',dpi=160);plt.close(fig)
    rr=[r for r in m['records'] if r['kind']=='rhombus'];rr=sorted(rr,key=lambda r:r['amplitude'])
    fig,ax=plt.subplots(figsize=(8,5))
    for name,label in [('historical_tail12_g1','Historical tail'),('current_hill08','Current hill08'),('loss_sum','WQ-LS08')]:ax.plot([r['amplitude'] for r in rr],[r['scores'][name]['score'] for r in rr],'-o',label=label)
    ax.set_xlabel('Shear angle deficit: 90 - theta / degrees');ax.set_ylabel('Complete Q');ax.set_title('Unit-edge rhombus: complete Q, not an ablation');ax.grid(True);ax.legend();fig.tight_layout();fig.savefig(ROOT/'figures/rhombus_response.png',dpi=160);plt.close(fig)
    print('Diagnostic views and source-image sheets written to',ROOT/'figures')
if __name__=='__main__':main()
