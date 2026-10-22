from pathlib import Path
import json,sys,numpy as np,pandas as pd,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'3d_compensation/vendor'))
from arc_excerpt import paired_wall_proxy,footprint,project
font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams.update({'font.family':'Noto Sans CJK JP','font.size':10,'axes.unicode_minus':False,'savefig.facecolor':'white'})
src=json.loads((OUT/'selected_source.json').read_text());ims={x['code']:x for x in src['images']};records={r['id']:r for im in ims.values() for r in im['annotations']+im['references']};metrics=pd.read_csv(OUT/'selected_metrics.csv');checks=[]
def close(x):return np.concatenate([x,x[:1]])
def overlay(ax,r):
 top,bot=paired_wall_proxy(r)
 for v,col in [(top,'#00ffff'),(bot,'#ffee16')]:
  for a,b in zip(v,np.roll(v,-1,axis=0)):
   q=project(a[None]+np.linspace(0,1,160)[:,None]*(b-a)[None]);cuts=np.where(np.abs(np.diff(q[:,0]))>512)[0]+1
   for seg in np.split(q,cuts):ax.plot(seg[:,0],seg[:,1],color=col,lw=1.6)
 for a,b in zip(top,bot):
  q=project(np.array([a,b]));ax.plot(q[:,0],q[:,1],c='#fb83e0',lw=.9)
 q=np.asarray(r['points']);ax.scatter(q[::2,0],q[::2,1],s=15,c='#00ffff',edgecolor='k',lw=.35);ax.scatter(q[1::2,0],q[1::2,1],s=15,c='#ffee16',edgecolor='k',lw=.35)

def render(code,ids,labels,title,name):
 im=ims[code];refs=im['references'];assert len(refs)==1
 gt=refs[0];fg,_=footprint(gt);tg,bg=paired_wall_proxy(gt)
 rs=[records[x] for x in ids];verts=np.vstack([np.vstack(paired_wall_proxy(r)) for r in rs+[gt]])
 low=verts.min(0);high=verts.max(0);pad=np.maximum((high-low)*.035,.1);low-=pad;high+=pad
 fig=plt.figure(figsize=(6.5*len(ids),12.6));gs=fig.add_gridspec(3,len(ids),height_ratios=[.98,1.0,1.32],hspace=.29,wspace=.20)
 pixels=np.asarray(Image.open(ROOT/'original_photos'/f'{code}.png'))
 for j,(r,label) in enumerate(zip(rs,labels)):
  row=metrics[(metrics.id==r['id']) & (metrics.reference_id==gt['id'])].iloc[0];top,bot=paired_wall_proxy(r);ff,_=footprint(r)
  ax=fig.add_subplot(gs[0,j]);ax.imshow(pixels,extent=[0,1024,512,0]);overlay(ax,r);ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xticks([]);ax.set_yticks([])
  tag='原始GT' if r['id']==gt['id'] else '现存标注'
  ax.set_title(f'{r["id"]} · {len(r["points"])//2}对点 · {tag}\n{label}',fontsize=12,pad=10)
  ax=fig.add_subplot(gs[1,j]);ax.plot(*close(fg).T,c='#9a9da4',lw=2.2,label=f'原GT {gt["id"]}');ax.plot(*close(ff).T,c='#2461c6',lw=1.7,marker='o',ms=4,label=r['id']);ax.scatter([0],[0],c='#20252b',marker='x',s=40,zorder=6,label='相机')
  ax.set_aspect('equal',adjustable='box');ax.set_xlim(low[0],high[0]);ax.set_ylim(low[2],high[2]);ax.grid(alpha=.2);ax.set_xlabel('x / h');ax.set_ylabel('z / h')
  ax.set_title(f'IoU {row.iou:.3f}   C {row.C:.3f}   面积/GT {row.area_ratio_to_GT:.3f}\nLC {row.LC_fixed:.3f}   J {row.J_fixed:.3f}   LC+0.3J {row.LCG_fixed:.3f}',fontsize=11)
  ax=fig.add_subplot(gs[2,j],projection='3d')
  for t,b,col,alpha,ls in [(tg,bg,'#9fa4ad',.65,'--'),(top,bot,'#2461c6',1,'-')]:
   for v in [t,b]:q=close(v);ax.plot(q[:,0],q[:,2],q[:,1],c=col,lw=1.7,alpha=alpha,ls=ls)
   for a,b0 in zip(t,b):ax.plot([a[0],b0[0]],[a[2],b0[2]],[a[1],b0[1]],c=col,lw=.95,alpha=alpha,ls=ls)
  ax.scatter([0],[0],[0],c='k',marker='x',s=22)
  ax.set_xlim(low[0],high[0]);ax.set_ylim(low[2],high[2]);ax.set_zlim(low[1],high[1]);ax.set_box_aspect((high[0]-low[0],high[2]-low[2],high[1]-low[1]));ax.view_init(elev=25,azim=-58);ax.set_xlabel('x / h',labelpad=4);ax.set_ylabel('z / h',labelpad=4);ax.set_zlabel('y / h',labelpad=4);ax.tick_params(labelsize=8,pad=0)
  prec=4 if r['id']==gt['id'] else 2
  ax.set_title(f'dir {row.direction_rms_deg:.{prec}f}°   flat {row.flat_top_angular_rms_deg:.{prec}f}°\n条件墙高 {row.height_min_h:.3f}–{row.height_max_h:.3f} h',fontsize=11,pad=1)
  checks.append({'figure':name,'image':code,'record':r['id'],'same_axes_for_all_columns':True,'axis_low_xyz':low.tolist(),'axis_high_xyz':high.tolist(),'vertices_xyz_inside_axes':bool(np.all(top>=low) and np.all(top<=high) and np.all(bot>=low) and np.all(bot<=high)),'single_valued':row.single_valued,'rendered_without_reordering':True})
 fig.suptitle(f'{code} · {title}',fontsize=18,y=.975)
 status={'uNb9QFRL6hY-26':'各标注仍为 default_unreviewed，环序未人审确认；原GT模型基线 dir=.0028°、flat=.00074°。','uNb9QFRL6hY-50':'R02344与GT保留 camera_visibility_unresolved；二者非单值一周环，对GT的单值ERP距离为NA。','uNb9QFRL6hY-88':'R03262与GT保留 camera_visibility_unresolved；二者非单值一周环，对GT的单值ERP距离为NA。'}[code]
 fig.text(.03,.034,'上：原图叠现存点与连接；黄=底边，青=顶边。中/下：蓝=本列对象，灰=原始GT。相机固定在原点，各列共用坐标轴限。\n地面 y=-1，墙竖直；h 为相机高度单位，不是米。条件3D不是实测屋顶，未拟合、修复、重排或补点。\n'+status+' 各标注保留 candidate_pending_geometry；范围变化保留，不据图修改资格或语义评价。',fontsize=10,linespacing=1.7)
 fig.subplots_adjust(top=.905,bottom=.112,left=.04,right=.976)
 fig.savefig(OUT/name,dpi=145);plt.close(fig)
render('uNb9QFRL6hY-26',['R00532','R02483','R03095','R02861'],['历史：较小空间，省略一些范围','历史：较小空间，但“标得更怪”','历史：与GT有“小空间的不同”','历史：大体还行，玻璃处范围不同'],'三个“小范围”案例，并非同一种几何结果','01_uNb26_scope_and_geometry.png')
render('uNb9QFRL6hY-50',['R02153','R02344','R02708'],['历史：最小空间，大部分区域没标','历史：含马桶区，另一范围，标得还行','本视角唯一现存GT版本'],'极小范围、另一范围与原始GT','02_uNb50_minimum_and_fuller_scope.png')
render('uNb9QFRL6hY-88',['R03263','R03262','R02736'],['历史：极简，很多正常细节也忽略','历史：略小范围，标得很不错','历史图评：GT范围偏大，含两侧走廊'],'范围取舍与规整度可能指向不同方向','03_uNb88_scope_and_simplification.png')
(OUT/'render_validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n');assert all(x['vertices_xyz_inside_axes'] for x in checks)
print('rendered and axis checked:',len(checks))
