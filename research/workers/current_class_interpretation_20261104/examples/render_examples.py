#!/usr/bin/env python3
"""Render the self-contained frozen example payload; no network or scoring.

Dependencies: numpy, matplotlib, Pillow. Optional --font /path/to/CJK.otf.
The HTML works directly as a file; its only assets are the four original PNGs.
"""
from pathlib import Path
import argparse, html, json, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, patheffects
from PIL import Image

HERE=Path(__file__).resolve().parent
NAMES={'TARGET_DSTRUCT_K3':'DSTRUCT','RFUSE_GEOM_K2':'RFUSE','OPPJOINT_K3':'JOINT','OPPJOINT_K4':'JOINT_K4'}
DISPLAY_NAMES={'TARGET_DSTRUCT_K3':'DSTRUCT K3','RFUSE_GEOM_K2':'RFUSE K2','OPPJOINT_K3':'JOINT K3','OPPJOINT_K4':'JOINT K4'}
ANN='#00d2e9';SHORT='#ffb52e';NEAR='#f14ebd'

def spherical_edge(a,b):
    """A straight spatial edge projects to a great-circle arc; split panorama seam."""
    p=np.array([a,b],float);az=p[:,0]*2*np.pi/1024;el=(.5-p[:,1]/512)*np.pi
    rays=np.column_stack([-np.sin(az)*np.cos(el),np.sin(el),np.cos(az)*np.cos(el)])
    theta=math.acos(float(np.clip(rays[0]@rays[1],-1,1)))
    n=max(16,int(math.degrees(theta)*2.5)+1)
    t=np.linspace(0,1,n)[:,None]
    if theta>1e-8:
        r=np.sin((1-t)*theta)/np.sin(theta)*rays[0]+np.sin(t*theta)/np.sin(theta)*rays[1]
    else:r=(1-t)*rays[0]+t*rays[1]
    r/=np.linalg.norm(r,axis=1)[:,None]
    x=np.mod(np.arctan2(-r[:,0],r[:,2]),2*np.pi)*1024/(2*np.pi)
    y=(.5-np.arctan2(r[:,1],np.hypot(r[:,0],r[:,2]))/np.pi)*512
    xy=np.column_stack([x,y]);segments=[];start=0
    for j in np.flatnonzero(abs(np.diff(x))>512)+1:
        # Interpolate the exact seam crossing in an unwrapped local interval.
        a0=xy[j-1].copy();b0=xy[j].copy();forward=a0[0]>b0[0]
        b0[0]+=1024 if forward else -1024
        boundary=1024 if forward else 0
        f=(boundary-a0[0])/(b0[0]-a0[0]);yy=a0[1]+f*(b0[1]-a0[1])
        segments.append(np.vstack([xy[start:j],[boundary,yy]]))
        xy[j-1]=[0 if forward else 1024,yy]
        start=j-1
    segments.append(xy[start:])
    return [s for s in segments if len(s)>1]

def boundary_segments(points):
    p=np.asarray(points,float);out=[]
    for level in (0,1):
        a=p[level::2]
        for i in range(len(a)):
            for seg in spherical_edge(a[i],a[(i+1)%len(a)]):
                out.append(dict(edge=i+1,level=level,xy=seg.tolist()))
    return out

def enrich(data):
    for r in list(data['objects'].values())+list(data['references'].values()):
        r['panorama_segments']=boundary_segments(r['points_1024x512'])
    return data

def num(x,n=2):return '—' if x is None else f'{float(x):.{n}f}'

def render_static(data):
    figures=HERE/'figures';figures.mkdir(exist_ok=True)
    products=[]
    for im in data['images']:
        original=np.asarray(Image.open(HERE/im['path']))
        for method in data['models']:
            slots=[s for s in data['slots'] if s['image']==im['image_code'] and s['method']==method and s['image_group']!='near_collinear_feature_supplement']
            classes=sorted({s['class_id'] for s in slots})
            fig=plt.figure(figsize=(8.1*len(classes),12.6),facecolor='#f7f8fa')
            grid=fig.add_gridspec(2,len(classes),left=.022,right=.982,bottom=.045,top=.868,wspace=.065,hspace=.12)
            fig.suptitle(f"{DISPLAY_NAMES[method]}  |  {im['image_code']}  ·  {im['difficulty']}  ·  同图、同源原答",fontsize=23,x=.023,ha='left',y=.976,fontweight='bold')
            fig.text(.024,.934,'完整上下边界与原顺序。青色：当前有效原答；黄色：短墙；粉色圈：近共线点；白色虚线：当前采用参考。',fontsize=12,color='#354052')
            capacity_note='每类按几何中位接近度选至多2人；C3本图只有1人，全部展示' if method=='OPPJOINT_K4' else '每类按几何中位接近度选2人'
            fig.text(.024,.911,f"留楼外折 {im['building']}  ·  {capacity_note}；Q/T不参与选例  ·  时间来自用户已处理记录",fontsize=11,color='#5d6470')
            for col,c in enumerate(classes):
                ss=sorted([s for s in slots if s['class_id']==c],key=lambda s:s['selection_rank'])
                for row,s in enumerate(ss):
                    inner=grid[row,col].subgridspec(2,2,height_ratios=[2.25,1.1],width_ratios=[1.03,1.58],hspace=.05,wspace=.03)
                    ax=fig.add_subplot(inner[0,:]);obj=data['objects'][s['object_id']];ref=data['references'][obj['reference_key']]
                    ax.imshow(original,extent=[0,1024,512,0]);ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.axis('off')
                    for sg in ref['panorama_segments']:
                        a=np.array(sg['xy']);ax.plot(a[:,0],a[:,1],color='white',lw=1,ls=(0,(5,4)),alpha=.95,
                            path_effects=[patheffects.Stroke(linewidth=2,foreground='#22222288'),patheffects.Normal()])
                    for a,b in zip(ref['points_1024x512'][::2],ref['points_1024x512'][1::2]):
                        ax.plot([a[0],b[0]],[a[1],b[1]],color='white',lw=.8,ls=(0,(5,4)),alpha=.7)
                    short=set(obj['traits']['short_edge_start_nodes_1based'])
                    for sg in obj['panorama_segments']:
                        a=np.array(sg['xy']);color=SHORT if sg['edge'] in short else ANN
                        ax.plot(a[:,0],a[:,1],color=color,lw=1.4,path_effects=[patheffects.Stroke(linewidth=2.6,foreground='#122331b0'),patheffects.Normal()])
                    p=np.asarray(obj['points_1024x512'])
                    for k,(a,b) in enumerate(zip(p[::2],p[1::2]),1):
                        ax.plot([a[0],b[0]],[a[1],b[1]],color=ANN,lw=1)
                        ax.scatter([a[0],b[0]],[a[1],b[1]],s=13,c=ANN,edgecolors='#152d3b',linewidths=.4,zorder=5)
                        ax.text(min(b[0]+3,1012),b[1]+(12 if k%2 else 22),str(k),fontsize=8,color='white',zorder=6,
                            path_effects=[patheffects.Stroke(linewidth=2,foreground='#152d3b'),patheffects.Normal()])
                        if k in obj['traits']['near_straight_nodes_1based']:
                            ax.scatter([a[0],b[0]],[a[1],b[1]],s=65,facecolors='none',edgecolors=NEAR,lw=1.5,zorder=7)
                    selection_note='本图该类全部 1 / 1 人' if s['class_available']==1 else f"类内典型次序 {s['selection_rank']} / {s['class_available']}"
                    ax.set_title(f"{c} · {s['worker_id']}   |   {selection_note}",loc='left',fontsize=13,pad=7,fontweight='bold')
                    floor=fig.add_subplot(inner[1,0]);floor.set_facecolor('#ffffff')
                    a=np.array(ref['traits']['floor_xz_h']);a=np.vstack([a,a[0]])
                    floor.plot(a[:,0],a[:,1],color='#78828f',ls='--',lw=1)
                    a=np.array(obj['traits']['floor_xz_h']);closed=np.vstack([a,a[0]])
                    floor.plot(closed[:,0],closed[:,1],color='#037d96',lw=1.3)
                    for k in short:
                        pair=closed[k-1:k+1];floor.plot(pair[:,0],pair[:,1],color='#d78c00',lw=2.2)
                    floor.scatter(a[:,0],a[:,1],s=10,c='#037d96');floor.scatter([0],[0],marker='+',color='#333',s=30)
                    for k in obj['traits']['near_straight_nodes_1based']:floor.scatter(*a[k-1],s=70,facecolors='none',edgecolors=NEAR,lw=1.4)
                    x0,x1,z0,z1=im['floor_bounds'];floor.set_xlim(x0,x1);floor.set_ylim(z0,z1);floor.set_aspect('equal')
                    floor.tick_params(labelsize=7,length=2);floor.spines[['top','right']].set_visible(False)
                    floor.set_title('底面：同图统一尺度；+ 为相机',fontsize=8,loc='left',pad=3)
                    textax=fig.add_subplot(inner[1,1]);textax.axis('off')
                    lines=[f"Q {s['B8L2']:.2f}  ·  D10 {s['D10']:.2f}  ·  T {s['source_active_time_seconds']:.3f} 秒",
                        f"{s['pair_count']} 对点 / {int(s['turn_n'])} 转折 / {int(s['short_turn_edges'])} 短墙 / {int(s['near_straight_nodes_5deg'])} 近共线",
                        f"IoU2D {100*s['iou_2d']:.2f}%  ·  IoU3D {s['IoU3D100']:.2f}%",
                        f"S_bottom {s['S_bottom_deg']:.3f}°  ·  dir {s['dir']:.3f}",
                        f"Hmean {s['Hmean']:.4f}  ·  Hcenter {s['Hcenter']:.4f}",
                        f"水平Δ {s['matched_horizontal_bias_deg']:+.2f}° · 上Δ {s['matched_top_bias_deg']:+.2f}° · 下Δ {s['matched_bottom_bias_deg']:+.2f}°",
                        s['object_id']]
                    textax.text(0,.98,'\n'.join(lines),va='top',fontsize=9.2,linespacing=1.55,color='#202a36')
                if len(ss)==1:
                    absent=fig.add_subplot(grid[1,col]);absent.axis('off')
                    absent.text(.08,.73,f"{c} · 本图该类可用 1 人",fontsize=17,fontweight='bold',color='#496174')
                    absent.text(.08,.60,f"{ss[0]['worker_id']} 的完整原答已在上方展示。\n本图该类没有第二位同源人员。",fontsize=13,color='#596b7b',linespacing=1.9)
            fig.text(.024,.016,'底面单位=相机到地板高度；Δ采用全景像素方向（右/下为正）。主目标 ordinary Manual；记录T未经本次原始日志重放。对象、坐标、参考与分项见配套CSV/JSON。',fontsize=10,color='#576271')
            name=f"{im['image_code']}__{NAMES[method]}.png";target=figures/name;tmp=figures/(name+'.partial')
            fig.savefig(tmp,format='png',dpi=130,facecolor=fig.get_facecolor());plt.close(fig)
            with Image.open(tmp) as verify:verify.load()
            tmp.replace(target)
            products.append(dict(image=im['image_code'],method=method,path='figures/'+name))
    return products

def render_near(data):
    near=next(s for s in data['slots'] if s['image_group']=='near_collinear_feature_supplement')
    typical=next(s for s in data['slots'] if s['image']=='jtcxE69GiFV-26' and s['method']=='TARGET_DSTRUCT_K3' and s['worker_id']=='W116')
    im=next(x for x in data['images'] if x['image_code']==near['image'])
    original=np.asarray(Image.open(HERE/im['path']))
    fig=plt.figure(figsize=(16.5,7.8),facecolor='#f7f8fa')
    outer=fig.add_gridspec(1,2,left=.025,right=.98,top=.82,bottom=.075,wspace=.075)
    fig.suptitle('近共线释义：同为 6 对点，实际转折数可以不同',x=.025,ha='left',y=.97,fontsize=21,fontweight='bold')
    fig.text(.025,.912,'jtcxE69GiFV-26 · 当前 DSTRUCT C2 · W114 为特征存在性附例，W116 为已选典型；Q/T 不参与这次对照选择。',fontsize=11)
    fig.text(.025,.877,'青色：完整有效原答；白虚线：当前参考；黄色：短墙；粉色圈：近共线点。',fontsize=11,color='#526476')
    for col,s in enumerate([near,typical]):
        inner=outer[0,col].subgridspec(2,2,height_ratios=[2.5,1.4],width_ratios=[1,1.5],hspace=.09,wspace=.06)
        ax=fig.add_subplot(inner[0,:]);o=data['objects'][s['object_id']];ref=data['references'][o['reference_key']]
        ax.imshow(original,extent=[0,1024,512,0]);ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.axis('off')
        for sg in ref['panorama_segments']:
            xy=np.array(sg['xy']);ax.plot(xy[:,0],xy[:,1],color='white',lw=.9,ls='--',path_effects=[patheffects.Stroke(linewidth=2,foreground='#152b3b88'),patheffects.Normal()])
        for sg in o['panorama_segments']:
            xy=np.array(sg['xy']);ax.plot(xy[:,0],xy[:,1],color=SHORT if sg['edge'] in o['traits']['short_edge_start_nodes_1based'] else ANN,lw=1.6,path_effects=[patheffects.Stroke(linewidth=2.8,foreground='#152b3b99'),patheffects.Normal()])
        for k,(a,b) in enumerate(zip(o['points_1024x512'][::2],o['points_1024x512'][1::2]),1):
            ax.plot([a[0],b[0]],[a[1],b[1]],color=ANN,lw=1.1);ax.scatter([a[0],b[0]],[a[1],b[1]],s=17,c=ANN,edgecolors='#152b3b',linewidths=.5)
            ax.text(min(b[0]+3,1012),b[1]+(13 if k%2 else 23),str(k),fontsize=9,color='white',path_effects=[patheffects.Stroke(linewidth=2,foreground='#152b3b'),patheffects.Normal()])
            if k in o['traits']['near_straight_nodes_1based']:ax.scatter([a[0],b[0]],[a[1],b[1]],s=115,facecolors='none',edgecolors=NEAR,lw=2)
        ax.set_title(f"{s['worker_id']} · C2 · {'特征附例' if col==0 else '预定典型'}",loc='left',fontsize=13,fontweight='bold',pad=6)
        floor=fig.add_subplot(inner[1,0]);a=np.array(ref['traits']['floor_xz_h']);closed=np.vstack([a,a[0]])
        floor.plot(closed[:,0],closed[:,1],color='#7a8693',ls='--',lw=1)
        a=np.array(o['traits']['floor_xz_h']);closed=np.vstack([a,a[0]]);floor.plot(closed[:,0],closed[:,1],color='#087b95',lw=1.6)
        floor.scatter(a[:,0],a[:,1],s=18,c='#087b95');floor.scatter([0],[0],marker='+',c='#273d4b',s=30)
        for k in o['traits']['near_straight_nodes_1based']:floor.scatter(*a[k-1],s=120,facecolors='none',edgecolors=NEAR,lw=2)
        for k in o['traits']['short_edge_start_nodes_1based']:floor.plot(closed[k-1:k+1,0],closed[k-1:k+1,1],color='#d58c00',lw=2.4)
        x0,x1,z0,z1=im['floor_bounds'];floor.set_xlim(x0,x1);floor.set_ylim(z0,z1);floor.set_aspect('equal');floor.tick_params(labelsize=8)
        floor.spines[['top','right']].set_visible(False);floor.set_title('底面同尺度；+ 为相机',fontsize=9,loc='left')
        tx=fig.add_subplot(inner[1,1]);tx.axis('off');nearids=o['traits']['near_straight_nodes_1based']
        content=[f"6 对点 / {int(s['turn_n'])} 转折 / {int(s['near_straight_nodes_5deg'])} 近共线点",
            '近共线点号：'+(', '.join(map(str,nearids)) if nearids else '无'),
            f"Q {s['B8L2']:.2f} · D10 {s['D10']:.2f} · T {s['source_active_time_seconds']:.3f} 秒",
            f"IoU2D {100*s['iou_2d']:.2f}% · IoU3D {s['IoU3D100']:.2f}%",
            f"S_bottom {s['S_bottom_deg']:.3f}° · dir {s['dir']:.3f}",
            f"Hmean {s['Hmean']:.4f} · Hcenter {s['Hcenter']:.4f}",s['object_id']]
        tx.text(0,.98,'\n'.join(content),va='top',fontsize=10,linespacing=1.65)
    fig.text(.025,.025,'近共线沿用原答定义：底面转角 ≤5°。没有删除该点，也没有将附例并入每类两个典型实例。完整坐标、当前参考与合法时间来源随数据表提供。',fontsize=10,color='#526476')
    out=HERE/'figures/near_collinear_W114_W116.png';tmp=out.with_suffix('.png.partial')
    fig.savefig(tmp,format='png',dpi=140,facecolor=fig.get_facecolor());plt.close(fig)
    with Image.open(tmp) as verify:verify.load()
    tmp.replace(out)

HTML_TEMPLATE=r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HOHONET v2.1 · 当前类别真实原答案例</title><style>
:root{--ink:#14283b;--muted:#596b7b;--line:#d9e1e8;--blue:#087b95;--paper:#f3f6f9;--ann:#00d2e9;--short:#ffb52e;--near:#f14ebd}*{box-sizing:border-box}body{font-family:Arial,"Noto Sans CJK SC","Microsoft YaHei",sans-serif;margin:0;color:var(--ink);background:var(--paper);line-height:1.6}header{background:#102b42;color:white;padding:30px max(3vw,24px) 25px}h1{font-size:30px;line-height:1.25;margin:8px 0 14px;letter-spacing:.5px}header p{max-width:1080px;margin:7px 0;color:#d8e6ef;font-size:14px}.eyebrow{color:#87d4e3;font-size:12px;letter-spacing:1.5px}.stats{display:flex;gap:28px;flex-wrap:wrap;margin-top:22px}.stats strong{font-size:26px;color:#fff;margin-right:7px}.stats span{font-size:13px;color:#bfcedb}main{padding:22px max(3vw,24px) 40px;max-width:2300px;margin:auto}.controls{background:white;border:1px solid var(--line);border-radius:8px;padding:16px 20px;position:sticky;top:0;z-index:20;box-shadow:0 3px 12px #102b420b}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.row+.row{margin-top:12px}.row .label{font-size:12px;font-weight:bold;min-width:58px;color:var(--muted)}button,a.linkbutton{font:inherit;border:1px solid #cbd6e0;background:#fff;border-radius:5px;padding:6px 13px;color:var(--ink);cursor:pointer;text-decoration:none}button.active{background:#087b95;color:#fff;border-color:#087b95}button:hover,a.linkbutton:hover{box-shadow:0 0 0 2px #087b9522}.row label{font-size:13px;margin-right:12px}input{accent-color:#087b95}#context{margin:20px 0 14px}.context-title{font-size:23px;font-weight:bold}.small{font-size:12px;color:var(--muted)}.tag{border:1px solid #bdcbd7;border-radius:3px;padding:1px 6px;font-size:11px;white-space:nowrap}.legend{display:flex;gap:18px;font-size:13px;margin:12px 0;flex-wrap:wrap}.swatch{display:inline-block;width:24px;border-top:3px solid var(--ann);margin-right:6px;vertical-align:middle}.reference-swatch{border-color:#7d8793;border-top-style:dashed}.short-swatch{border-color:var(--short)}.near-swatch{display:inline-block;width:10px;height:10px;border:2px solid var(--near);border-radius:50%;margin-right:7px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;align-items:start}.class-heading{padding:14px 16px;background:#e5edf3;border-top:4px solid #087b95;border-radius:6px 6px 0 0;min-height:116px}.class-heading h2{margin:0;font-size:19px}.class-heading p{margin:4px 0 0;font-size:12px;color:#466074}.card{background:#fff;border:1px solid var(--line);border-radius:6px;margin-bottom:18px;overflow:hidden}.card-head{padding:13px 16px 10px;display:flex;align-items:baseline;justify-content:space-between;gap:8px}.worker{font-size:19px;font-weight:bold}.card-head .small{font-size:11px}.pano{width:100%;height:auto;display:block;background:#17212c;cursor:zoom-in}.pano .labels{paint-order:stroke;stroke:#122b3f;stroke-width:2;stroke-linejoin:round;fill:white;font-size:9px;stroke-opacity:.9}.no-points .pointmarks,.no-points .labels{display:none}.no-ref .reference{display:none}.no-special .near,.no-special .short{display:none}.no-special .base{display:block}.card-body{padding:13px 16px 16px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.metric{background:#f0f5f8;padding:8px 10px;border-radius:4px}.metric span{display:block;font-size:11px;color:var(--muted)}.metric strong{font-size:20px;font-variant-numeric:tabular-nums}.traits{font-size:13px;margin:12px 0 10px;font-weight:bold}.bottom{display:grid;grid-template-columns:minmax(130px,.8fr) 1.2fr;gap:12px}.floor{width:100%;max-height:190px;background:#f8fafc;border:1px solid #e6ebef}.details{font-size:12px;font-variant-numeric:tabular-nums;line-height:1.8}.details div{display:flex;justify-content:space-between;gap:5px}.details b{font-weight:normal;color:#284459}.source{padding-top:10px;margin-top:9px;border-top:1px solid #e5ebf0;font-size:11px;overflow-wrap:anywhere;color:#617184}.note{background:#e9f3f5;border-left:4px solid #087b95;padding:14px 18px;font-size:13px;line-height:1.8;margin:18px 0}.section{margin:26px 0 14px}.section h2{font-size:22px;margin:0 0 10px}.downloads{display:flex;gap:10px;flex-wrap:wrap;margin:15px 0}.downloads a{font-size:12px;color:#0c6a82}.docs{background:white;border:1px solid var(--line);padding:20px 24px;border-radius:7px;font-size:13px}.docs h3{margin:18px 0 7px;font-size:16px}.docs p{margin:7px 0}.docs li{margin:5px 0}.docs code{font-size:11px;background:#eef3f6;padding:1px 4px;overflow-wrap:anywhere}details summary{cursor:pointer;font-weight:bold}.pair-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.modal{display:none;position:fixed;inset:0;background:#07121af2;z-index:100;overflow:auto;padding:30px}.modal.open{display:block}.modal-toolbar{color:#e6eef5;display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:18px}.modal-toolbar button{background:#fff}.modal .pano{max-width:2048px;min-width:1000px;margin:auto;cursor:default}.modal .modal-body{overflow:auto}.modal .labels{font-size:9px}.modal-caption{color:#bccbd7;margin:14px 0;font-size:13px}footer{padding:20px 0;color:#6f7c87;font-size:11px}a{color:#087b95}@media(max-width:1100px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.controls{position:static}}@media(max-width:720px){main{padding:16px}.grid,.pair-grid{grid-template-columns:1fr}.class-heading{min-height:auto}.bottom{grid-template-columns:.8fr 1.2fr}h1{font-size:25px}.stats{gap:15px}.modal{padding:15px}}
</style></head><body>
<header><div class="eyebrow">HOHONET v2.1 · ORIGINAL ANSWER EVIDENCE</div><h1>当前类别的人，实际怎样标注？</h1><p>同一张真实全景图，展示当前 DSTRUCT、RFUSE、JOINT 留楼外类别的完整原答、底面结构、质量分项和记录劳动。每类至多两个几何上接近类内典型的实例；K4 的单人类展示本图全部人员。</p><p>主图沿用原三种分区共同覆盖选出的简单 / 中等 / 困难三图及跨建筑附页；JOINT K4 接入同图。Q 与 T 不参与选图、选人。</p><div class="stats"><span><strong>4</strong>真实原图</span><span><strong>4</strong>当前分类分区</span><span><strong>__N_TYPICAL__</strong>典型展示位</span><span><strong>1</strong>近共线释义附例</span><span><strong>__N_OBJECTS__</strong>独立原答对象</span></div></header>
<main><div class="controls"><div class="row" id="imageButtons"><span class="label">场景</span></div><div class="row" id="methodButtons"><span class="label">体系</span></div><div class="row"><span class="label">叠加</span><label><input id="showRef" type="checkbox" checked> 当前采用参考</label><label><input id="showPoints" type="checkbox" checked> 完整点对 / 编号</label><label><input id="showSpecial" type="checkbox" checked> 短墙 / 近共线</label><a class="linkbutton" id="figureLink">下载当前静态图</a></div></div>
<section id="context"></section><div class="legend"><span><i class="swatch"></i>当前有效原答</span><span><i class="swatch reference-swatch"></i>当前采用参考</span><span><i class="swatch short-swatch"></i>依底面识别的短墙段</span><span><i class="near-swatch"></i>转角 ≤ 5° 的近共线点</span></div><div id="cards" class="grid"></div><div id="observation" class="note"></div>
<section class="section"><h2>近共线点：点数与转折数可以不同</h2><p class="small">典型展示位的近共线计数均为 0，因此单独按该特征存在性选取 W114，完整保留主图样本。同图同类 W116 是已经选定的典型实例，两人均有 6 对点。<a href="figures/near_collinear_W114_W116.png" download>下载释义对照图</a></p><div id="nearPair" class="pair-grid"></div></section>
<section class="section docs"><h2>如何读取这些图</h2><p>每个完整标注都来自同一冻结有效输入，使用 <code>points_1024x512</code>，在 2048×1024 原图上等比显示。边界按保存的环序投影，跨全景接缝分开绘制；没有重新排点、删点、合点或修改坐标。点号沿各自保存的环序编号，不表示不同人的第 n 点具有对应关系。</p><h3>分类依据与观察到的差异分开</h3><p>DSTRUCT 类别依训练建筑的原答结构建类；RFUSE 类别依训练建筑的融合响应建类；JOINT 直接包含历史 Q / T。类标题给出的训练中心用来解释当前折的编号。这里照片上的原答、Q / T 都来自被留出的建筑。C1 / C2 / C3 / C4 是模型折内编号，不是永久人物标签。</p><h3>结构与质量</h3><p>转折：底面相邻边方向变化 &gt;5°。近共线：≤5°。短墙：该边长度占底面周长 &lt;4%，且两端转角都 ≥15°。这些定义沿用原答特征代码；RFUSE 用于训练的另一种短边指标没有混入本图。底面按同图统一尺度绘制，单位为相机到地板高度；不是米。</p><p>Q 沿用 B8L2，D10 与 IoU2D、IoU3D、S_bottom、dir、Hmean、Hcenter 直接接入相同对象、参考 ID 与版本的已有质量记录。没有为图示重新计算或重组评分。位置偏差基于当前采用参考的匹配点；全景 x 向右、y 向下为正，未匹配点不进入匹配均值。</p><h3>时间与支持</h3><p>四张图均采用 <code>new</code> 同源记录，T 来源为 <code>user_processed_reported_not_raw_log_replayed</code>：用户已经处理并登记的劳动时间。本次没有把它说成从原始日志重新重放的计时。T 在图中展示秒；完整精度与来源字段保留在 CSV。主图仅为 <code>ordinary_manual / primary</code>，门洞、其它合法目标与半自动标注需在对应范围内另行解释。</p><p>三个主图位于同一建筑，因此共享同一留楼外模型折。跨建筑附页用于展示另一个具体场景；这些实例没有被当作全库统计样本。总体 Q/T、困难响应与类内分布应读取配套同图、建筑汇总分析。图示中没有出现某类处处最优的要求。</p><details><summary>追溯与复现文件</summary><div class="downloads"><a href="JOINT_K4_SUPPLEMENT.html">JOINT K4 补充说明</a><a href="JOINT_K4_SELECTED_RECORDS.csv">K4 全部 28 个展示位及指标</a><a href="SELECTED_RECORDS.csv">所选对象 / Q分项 / T</a><a href="SELECTED_IMAGES.csv">图片 / 支持</a><a href="SELECTION_RULE.md">冻结选例规则</a><a href="SELECTION_RANKS.csv">全部候选及选择距离</a><a href="EXAMPLE_DATA.json">完整坐标与绑定数据</a><a href="SOURCE_OBJECTS.json.gz">原始有效输入对象快照</a><a href="ORIGINAL_IMAGE_RECEIPT.json">原图CRC / SHA-256回执</a><a href="BINDING_AND_VERIFICATION.json">数值 / 版本验证</a><a href="README.md">说明与定性观察</a></div><p>图组来源版本 <code>48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b</code>。原图来自 GitHub Release <code>quality-original-images-20261015</code>，PNG 原始字节保留。</p></details></section>
<footer>HOHONET · 当前类别解释补充 · 2026-11-04。此图组描述个人原答，与 57 组人工融合顺序辅助结果分属不同对象层。</footer></main>
<div id="modal" class="modal" role="dialog" aria-modal="true" aria-label="完整标注大图"><div class="modal-toolbar"><span id="modalTitle"></span><button id="closeModal">关闭 / Esc</button></div><div id="modalBody" class="modal-body"></div><p class="modal-caption">横向滚动可查看原图完整宽度。叠加控制继承主页面；点号仅代表该对象自己的保存环序。</p></div>
<script id="payload" type="application/json">__PAYLOAD__</script><script>
'use strict';const D=JSON.parse(document.getElementById('payload').textContent),names={TARGET_DSTRUCT_K3:'DSTRUCT K3',RFUSE_GEOM_K2:'RFUSE K2',OPPJOINT_K3:'JOINT K3',OPPJOINT_K4:'JOINT K4'};const initial=new URLSearchParams(location.hash.slice(1));let imageId=D.images.some(i=>i.image_code===initial.get('image'))?initial.get('image'):D.images[0].image_code,method=D.models.includes(initial.get('method'))?initial.get('method'):D.models[0];const fmt=(x,n=2)=>x===null||x===undefined?'—':Number(x).toFixed(n);const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const poly=xy=>xy.map(p=>p.map(v=>Number(v).toFixed(3)).join(',')).join(' ');
function pano(s){const o=D.objects[s.object_id],im=D.images.find(i=>i.image_code===s.image),r=D.references[o.reference_key];let g=`<svg class="pano" viewBox="0 0 1024 512" role="img" aria-label="${esc(s.worker_id+' '+s.image+' 完整原答')}" data-object="${esc(s.object_id)}"><image href="${esc(im.path)}" width="1024" height="512"/>`;
const layers=(obj,ref)=>{let t=`<g class="${ref?'reference':'answer'}" fill="none" stroke-linejoin="round" stroke-linecap="round">`;const shorts=new Set(obj.traits.short_edge_start_nodes_1based);for(const sg of obj.panorama_segments){const p=poly(sg.xy);if(ref)t+=`<polyline points="${p}" stroke="#142333" stroke-width="2.7" stroke-dasharray="5 4" opacity=".65"/><polyline points="${p}" stroke="white" stroke-width="1.2" stroke-dasharray="5 4"/>`;else{t+=`<polyline points="${p}" stroke="#102b3f" stroke-width="3.2" opacity=".75"/><polyline points="${p}" stroke="#00d2e9" stroke-width="1.7"/>`;if(shorts.has(sg.edge))t+=`<polyline class="short" points="${p}" stroke="#ffb52e" stroke-width="2.2"/>`;}}
for(let k=0;k<obj.points_1024x512.length;k+=2){const a=obj.points_1024x512[k],b=obj.points_1024x512[k+1];t+=`<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="${ref?'white':'#00d2e9'}" stroke-width="${ref?.8:1.4}" ${ref?'stroke-dasharray="5 4" opacity=".75"':''}/>`;}return t+'</g>';};g+=layers(r,true)+layers(o,false);
for(let k=0;k<o.points_1024x512.length;k+=2){const id=k/2+1,a=o.points_1024x512[k],b=o.points_1024x512[k+1];for(const p of [a,b]){g+=`<circle class="pointmarks" cx="${p[0]}" cy="${p[1]}" r="2.9" fill="#00d2e9" stroke="#142333" stroke-width=".8"/>`;if(o.traits.near_straight_nodes_1based.includes(id))g+=`<circle class="near" cx="${p[0]}" cy="${p[1]}" r="7" fill="none" stroke="#f14ebd" stroke-width="2.2"/>`;}g+=`<text class="labels" x="${Math.min(b[0]+4,1012)}" y="${b[1]+(id%2?12:23)}">${id}</text>`;}return g+'</svg>';}
function floor(s){const o=D.objects[s.object_id],r=D.references[o.reference_key],im=D.images.find(i=>i.image_code===s.image),[x0,x1,z0,z1]=im.floor_bounds;const xy=p=>[16+(p[0]-x0)/(x1-x0)*188,204-(p[1]-z0)/(z1-z0)*188];const points=a=>poly([...a,a[0]].map(xy));let t='<svg class="floor" viewBox="0 0 220 225" role="img" aria-label="统一尺度底面"><path d="M16,16 V204 H204" fill="none" stroke="#c7d2dd"/><g class="reference"><polyline points="'+points(r.traits.floor_xz_h)+'" fill="none" stroke="#7b8794" stroke-width="1.5" stroke-dasharray="5 4"/></g><polyline points="'+points(o.traits.floor_xz_h)+'" fill="none" stroke="#087b95" stroke-width="1.7"/>';
const a=o.traits.floor_xz_h;for(const k of o.traits.short_edge_start_nodes_1based){const p=xy(a[k-1]),q=xy(a[k%a.length]);t+=`<line class="short" x1="${p[0]}" y1="${p[1]}" x2="${q[0]}" y2="${q[1]}" stroke="#d58c00" stroke-width="3"/>`;}a.forEach((p,i)=>{const [x,y]=xy(p);t+=`<circle cx="${x}" cy="${y}" r="2.3" fill="#087b95"/>`;if(o.traits.near_straight_nodes_1based.includes(i+1))t+=`<circle class="near" cx="${x}" cy="${y}" r="6.5" fill="none" stroke="#f14ebd" stroke-width="2"/>`;});const [cx,cy]=xy([0,0]);t+=`<path d="M${cx-4},${cy} h8 M${cx},${cy-4} v8" stroke="#253d50" stroke-width="1.3"/><text x="16" y="220" font-size="9" fill="#5f7485">同图同尺度 · + 相机 · 单位 Hcamera</text></svg>`;return t;}
function card(s,extra=''){const o=D.objects[s.object_id];const h=(s.raw_record?.log_height===null)?null:Math.exp(s.raw_record.log_height);return `<article class="card"><div class="card-head"><span class="worker">${esc(s.worker_id)} <span class="tag">${esc(s.class_id)}</span></span><span class="small">${extra||(s.class_available===1?'本图该类全部 1 / 1 人':`典型次序 ${s.selection_rank} / ${s.class_available}`)}</span></div>${pano(s)}<div class="card-body"><div class="metrics"><div class="metric"><span>Q · B8L2</span><strong>${fmt(s.B8L2)}</strong></div><div class="metric"><span>D10</span><strong>${fmt(s.D10)}</strong></div><div class="metric"><span>记录 T / 秒</span><strong>${fmt(s.source_active_time_seconds,1)}</strong></div></div><p class="traits">${s.pair_count} 对点 · ${s.turn_n} 转折 · ${s.short_turn_edges} 短墙 · ${s.near_straight_nodes_5deg} 近共线</p><div class="bottom">${floor(s)}<div class="details"><div>IoU2D <b>${fmt(100*s.iou_2d)}%</b></div><div>IoU3D <b>${fmt(s.IoU3D100)}%</b></div><div>S_bottom <b>${fmt(s.S_bottom_deg,3)}°</b></div><div>dir <b>${fmt(s.dir,3)}</b></div><div>Hmean / Hcenter <b>${fmt(s.Hmean,4)} / ${fmt(s.Hcenter,4)}</b></div><div>水平 Δ / 上 Δ / 下 Δ <b>${fmt(s.matched_horizontal_bias_deg)} / ${fmt(s.matched_top_bias_deg)} / ${fmt(s.matched_bottom_bias_deg)}°</b></div><div>匹配参考点比例 <b>${fmt(100*s.matched_pair_fraction,1)}%</b></div></div></div><div class="source">对象 ${esc(s.object_id)}<br>参考 ${esc(s.reference_id)}<br>版本 ${esc(s.reference_version)}<br>时间 ${fmt(s.source_active_time_seconds,3)} 秒 · ${esc(s.time_source)}<br>排序状态 ${esc(o.order_status)} · 预处理 ${esc(o.preprocessing_status)}</div></div></article>`;}
const observations={
'jtcxE69GiFV-10':'简单图的全部典型实例都是 4 对点、4 个转折；类别差异并不要求在每张图上都表现为点数不同。仍可查看位置、边界、高度、Q 与记录时间的差异。',
'jtcxE69GiFV-09':'中等图的典型实例同样都是 4 对点，Q 与记录时间在类内也有明显跨度。DSTRUCT C3 在这一图没有显示普遍质量优势；其当前类编号由训练建筑的困难转折结构定义。',
'jtcxE69GiFV-26':'困难图中 DSTRUCT C3 / JOINT K3 C3 与 RFUSE C2 的两个典型实例均保留 8 个转折、3 条短墙；其余典型实例为 5–6 个转折、0–1 条短墙。结构保留、几何位置和记录时间需要一起看，不能只按点数排优劣。',
'yqstnuAEVhm-01':'跨建筑中等图中，DSTRUCT C1 两例是 4 个转折，C2 与 C3 两例均为 8 个转折、2 条短墙。C2 与 C3 即使转折和短墙计数相同，位置和边界偏差仍可不同；同一组实例的质量分项可在图上对照。'};
const k4Observations={
'jtcxE69GiFV-10':'JOINT K4 的七个展示原答均为 4 个转折，差别体现在边界位置、质量分项和记录时间。C3 本图唯一人员 W121 的 Q 为 91.28，T 为 263.866 秒；四类完整指标并列可查。',
'jtcxE69GiFV-09':'JOINT K4 的七个展示原答同样都是 4 个转折。C1 的两例 Q 为 64.49 / 92.73，C2 为 92.10 / 83.41，C3 唯一成员为 59.54，C4 为 63.20 / 88.98。类内位置和劳动差异在相同点数下仍存在。',
'jtcxE69GiFV-26':'JOINT K4 的 C4 两例均保留 8 个转折和 3 条短墙；C1 两例为 9 / 6 个转折，C2 为 5 / 6，C3 唯一成员为 4。更多转折未必对应更完整的局部结构；完整原图与底面可同时检查位置、短墙和 Q 分项。C3 的记录 T 为 2894.746 秒，C4 两例为 3559.413 / 1018.229 秒。',
'yqstnuAEVhm-01':'跨楼 JOINT K4：C2 和 C4 的两例都保留 8 个转折、2 条短墙；C2 的 Q 为 67.26 / 47.77，C4 为 97.75 / 94.38。结构计数相同时，位置、上下边界与质量分项仍有明显不同。本图 C3 仍只覆盖 W121 一人。'};
function render(){const im=D.images.find(i=>i.image_code===imageId);document.querySelectorAll('[data-image]').forEach(b=>b.classList.toggle('active',b.dataset.image===imageId));document.querySelectorAll('[data-method]').forEach(b=>b.classList.toggle('active',b.dataset.method===method));const ss=D.slots.filter(s=>s.image===imageId&&s.method===method&&s.image_group!=='near_collinear_feature_supplement');const classes=[...new Set(ss.map(s=>s.class_id))].sort();const current=document.getElementById('cards');const columns=classes.length===4&&window.innerWidth<1700?2:classes.length;current.style.gridTemplateColumns=window.innerWidth>1100?`repeat(${columns},minmax(0,1fr))`:'';
document.getElementById('context').innerHTML=`<div class="context-title">${esc(imageId)} · ${esc(im.difficulty)} <span class="tag">${im.group==='primary'?'主图':'跨建筑附页'}</span></div><div class="small">${esc(method)} · 留楼外 ${esc(im.building)} · 同源候选 ${im.n} 人 · 本法类别覆盖 ${esc(im[method])} · 每类至多 2 人；单人类全部展示</div>`;
current.innerHTML=classes.map(c=>{const a=ss.filter(s=>s.class_id===c).sort((a,b)=>a.selection_rank-b.selection_rank);const center=D.centers.find(x=>x.image===imageId&&x.method===method&&x.class_id===c);return `<section><div class="class-heading"><h2>${c} <span class="tag">本图可用 ${a[0].class_available} 人</span></h2><p>${esc(center.center_label)} ${fmt(center.center_value,3)}<br>训练人数 ${center.training_workers}；中心用于说明编号，非本图结果</p></div>${a.map(s=>card(s)).join('')}${a.length===1?'<div class="note">本图该类仅 1 位同源人员，已全部展示。</div>':''}</section>`;}).join('');document.getElementById('observation').textContent=(method==='OPPJOINT_K4'?k4Observations[imageId]:observations[imageId]);const product=D.products.find(x=>x.image===imageId&&x.method===method);const link=document.getElementById('figureLink');link.href=product.path;link.download=product.path.split('/').pop();bindPanos();}
function bindPanos(){document.querySelectorAll('.pano[data-object]').forEach(el=>{el.onclick=()=>{const s=D.slots.find(x=>x.object_id===el.dataset.object);document.getElementById('modalTitle').textContent=s.image+' · '+s.worker_id+' · '+s.object_id;document.getElementById('modalBody').innerHTML=pano(s);document.getElementById('modal').classList.add('open');};});}
for(const im of D.images){const b=document.createElement('button');b.textContent=(im.group==='primary'?im.difficulty:'跨楼 · '+im.difficulty)+'  '+im.image_code;b.dataset.image=im.image_code;b.onclick=()=>{imageId=im.image_code;render();};document.getElementById('imageButtons').appendChild(b);}for(const m of D.models){const b=document.createElement('button');b.textContent=names[m];b.dataset.method=m;b.onclick=()=>{method=m;render();};document.getElementById('methodButtons').appendChild(b);}
for(const [id,cls] of [['showRef','no-ref'],['showPoints','no-points'],['showSpecial','no-special']])document.getElementById(id).onchange=e=>document.body.classList.toggle(cls,!e.target.checked);
const near=D.slots.find(s=>s.image_group==='near_collinear_feature_supplement'),same=D.slots.find(s=>s.image==='jtcxE69GiFV-26'&&s.method==='TARGET_DSTRUCT_K3'&&s.worker_id==='W116');document.getElementById('nearPair').innerHTML=card(near,'按近共线特征选取的附例')+card(same,'同图同类、同为6对点的典型实例');document.getElementById('closeModal').onclick=()=>document.getElementById('modal').classList.remove('open');document.addEventListener('keydown',e=>{if(e.key==='Escape')document.getElementById('modal').classList.remove('open');});window.addEventListener('resize',()=>render());render();
</script></body></html>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--font');parser.add_argument('--html-only',action='store_true');args=parser.parse_args()
    font=Path(args.font) if args.font else None
    if font is not None and font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
    else:plt.rcParams['font.family']=['Noto Sans CJK SC','Microsoft YaHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    data=enrich(json.loads((HERE/'EXAMPLE_DATA.json').read_text()))
    if args.html_only:products=json.loads((HERE/'FIGURE_INDEX.json').read_text())
    else:products=render_static(data);(HERE/'FIGURE_INDEX.json').write_text(json.dumps(products,ensure_ascii=False,indent=2)+'\n')
    render_near(data)
    data['products']=products
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('</',r'<\/')
    page=HTML_TEMPLATE.replace('__PAYLOAD__',payload).replace('__N_TYPICAL__',str(sum(s['image_group']!='near_collinear_feature_supplement' for s in data['slots']))).replace('__N_OBJECTS__',str(len(data['objects'])))
    (HERE/'index.html').write_text(page,encoding='utf-8')
    print('rendered',len(products),'static plates and offline index.html')

if __name__=='__main__':main()
