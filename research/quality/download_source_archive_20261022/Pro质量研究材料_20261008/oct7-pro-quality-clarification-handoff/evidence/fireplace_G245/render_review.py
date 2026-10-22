from pathlib import Path
import json,sys,numpy as np,pandas as pd,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from matplotlib.font_manager import FontProperties
OUT=Path(__file__).parent; ROOT=OUT.parent
sys.path.insert(0,str(ROOT/'3d_compensation/vendor'))
from arc_excerpt import paired_wall_proxy,footprint,project
panel=json.load(open(OUT/'inputs/panel.json'))
ims={x['code']:x for x in panel['images'] if x['room']=='G245'}
metrics=pd.read_csv(OUT/'family_metrics_by_reference.csv'); font=FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams.update({'font.family':font.get_name(),'font.size':10,'axes.unicode_minus':False})
# Register font explicitly for matplotlib's global font lookup.
from matplotlib import font_manager
font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
records={r['id']:r for im in ims.values() for r in im['annotations']+im['references']}
rendered=[]
def close(v):return np.r_[v,v[:1]]
def overlay(ax,r):
 top,bot=paired_wall_proxy(r)
 for v,color in [(top,'#00ffff'),(bot,'#ffdf30')]:
  for a,b in zip(v,np.roll(v,-1,axis=0)):
   q=project(a[None]+np.linspace(0,1,96)[:,None]*(b-a)[None]);splits=np.where(np.abs(np.diff(q[:,0]))>512)[0]+1
   for q0 in np.split(q,splits):ax.plot(q0[:,0],q0[:,1],color=color,lw=1.7)
 for a,b in zip(top,bot):
  q=project(np.array([a,b]));ax.plot(q[:,0],q[:,1],color='#f78eff',lw=.9)
 ax.scatter(np.asarray(r['points'])[::2,0],np.asarray(r['points'])[::2,1],s=12,c='#00ffff',edgecolor='k',lw=.25)
 ax.scatter(np.asarray(r['points'])[1::2,0],np.asarray(r['points'])[1::2,1],s=12,c='#ffdf30',edgecolor='k',lw=.25)

def selected(code,ids,labels,refid,filename):
 im=ims[code];ref=records[refid]; fg,_=footprint(ref);gr_top,gr_bot=paired_wall_proxy(ref)
 fig=plt.figure(figsize=(18,11));gs=fig.add_gridspec(3,len(ids),height_ratios=[1.1,1,1.1],hspace=.25,wspace=.15)
 image=np.array(Image.open(ROOT/'original_photos'/f'{code}.png'))
 allr=[records[id] for id in ids]+[ref];allv=np.vstack([np.vstack(paired_wall_proxy(r)) for r in allr]);xlo,xhi=allv[:,0].min()-.15,allv[:,0].max()+.15;zlo,zhi=allv[:,2].min()-.15,allv[:,2].max()+.15;ylo,yhi=-1.1,allv[:,1].max()+.15
 for j,(id,label) in enumerate(zip(ids,labels)):
  r=records[id];row=metrics[(metrics.id==id)&(metrics.reference_id==refid)].iloc[0];top,bot=paired_wall_proxy(r);ff,_=footprint(r)
  ax=fig.add_subplot(gs[0,j]);ax.imshow(image,extent=[0,1024,512,0]);overlay(ax,r);ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xticks([]);ax.set_yticks([])
  ax.set_title(f'{id} | {len(r["points"])//2}对点\n{label}',fontsize=12)
  ax=fig.add_subplot(gs[1,j]);ax.plot(*close(fg).T,color='#9ca3af',lw=2,label=f'GT {refid}');ax.plot(*close(ff).T,color='#215bca',marker='o',ms=3,lw=1.5,label=id);ax.scatter([0],[0],c='k',marker='x',s=25);ax.set_aspect('equal',adjustable='box');ax.set_xlim(xlo,xhi);ax.set_ylim(zlo,zhi);ax.grid(alpha=.2);ax.set_xlabel('x / h');ax.set_ylabel('z / h');ax.legend(fontsize=8)
  ax.set_title(f'LC={row.LC_fixed:.3f}   J={row.J_fixed:.3f}   LC+0.3J={row.LCG_fixed:.3f}',fontsize=11)
  ax=fig.add_subplot(gs[2,j],projection='3d')
  for t,b,col,alpha in [(gr_top,gr_bot,'#b4b9c1',.55),(top,bot,'#215bca',1)]:
   for v in [t,b]:q=close(v);ax.plot(q[:,0],q[:,2],q[:,1],c=col,lw=1.5,alpha=alpha)
   for a,b0 in zip(t,b):ax.plot([a[0],b0[0]],[a[2],b0[2]],[a[1],b0[1]],c=col,lw=.9,alpha=alpha)
  ax.set_xlim(xlo,xhi);ax.set_ylim(zlo,zhi);ax.set_zlim(ylo,yhi);ax.set_box_aspect((xhi-xlo,zhi-zlo,yhi-ylo));ax.view_init(24,-58);ax.set_xlabel('x/h');ax.set_ylabel('z/h');ax.set_zlabel('y/h');ax.set_title(f'dir={row.direction_rms_deg:.2f}°   flat={row.flat_top_angular_rms_deg:.2f}°',fontsize=10)
 fig.suptitle(f'{code}：现存点与条件3D | 坐标、点数、连接不变 | 同一相机坐标与轴限',fontsize=16,y=.98)
 fig.text(.025,.018,'黄色=底边；青色=顶边；蓝色=标注；灰色=该版本GT。地面y=-1，相机在原点；h是相机高单位，不是米。\n图示是固定地面及竖直墙假设下的条件重建，不是实测真值或新的人审标签。没有拟合或修复。',fontsize=10)
 fig.subplots_adjust(top=.91,bottom=.08);fig.savefig(OUT/filename,dpi=130);plt.close(fig)

selected('yqstnuAEVhm-09',['R02319','R00985'],['历史原话：除p5/p7偏高，其余近似GT','历史原话：标得很好，空间细节略不同'], 'R02771','yq09_fireplace_detail_comparison.png')
selected('yqstnuAEVhm-32',['R01439','R00264','R00671'],['四对点的整体简化','门口细节获历史肯定，整答未认证','低残差复杂答；未逐人审'], 'R02782','yq32_conditional_3d_comparison.png')
selected('yqstnuAEVhm-31',['R01625','R01109','R01500'],['历史原话：只标最小空间','历史原话：范围一致、已很不错','历史原话：范围一致、已很不错'], 'R02781','yq31_conditional_3d_comparison.png')
selected('yqstnuAEVhm-31',['R01505','R00766'],['8对点；低残差并贴近原始GT','10对点；更贴近修订GT'], 'R02781','yq31_gt_version_review.png')
# Every currently available source array receives an unchanged footprint audit panel.
for code,im in ims.items():
 rs=im['annotations']+im['references'];n=len(rs);ncol=6;nrow=(n+ncol-1)//ncol
 fig,axs=plt.subplots(nrow,ncol,figsize=(18,3*nrow),squeeze=False)
 allf=[]
 for r in rs:
  try:allf.append(footprint(r)[0])
  except Exception:pass
 ff=np.vstack(allf);vmin=ff.min(0)-.15;vmax=ff.max(0)+.15
 for ax,r in zip(axs.flat,rs):
  try:
   f,_=footprint(r);ax.plot(*close(f).T,c='#215bca',marker='o',ms=2);ax.scatter([0],[0],c='k',marker='x',s=15);ax.set_aspect('equal');ax.set_xlim(vmin[0],vmax[0]);ax.set_ylim(vmin[1],vmax[1]);rendered.append({'image':code,'id':r['id'],'status':'conditional_footprint_rendered'})
  except Exception as e:ax.text(.02,.5,'不可作条件重建\n'+str(e),transform=ax.transAxes,fontsize=8,wrap=True);rendered.append({'image':code,'id':r['id'],'status':'unavailable','reason':str(e)})
  ax.set_title(f'{r["id"]} {r.get("worker") or r.get("version")}\n{len(r.get("points") or [])//2} pairs | {r["order_status"]}',fontsize=8);ax.tick_params(labelsize=6);ax.grid(alpha=.15)
 for ax in axs.flat[n:]:ax.axis('off')
 fig.suptitle(code+' | 全部现存标注与GT：条件俯视图；同图共用坐标轴限',fontsize=14);fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(OUT/f'{code}_all_records_bev.png',dpi=120);plt.close(fig)
json.dump(rendered,open(OUT/'render_coverage.json','w'),ensure_ascii=False,indent=2)
print('Rendered',len(rendered),'records',sum(r['status']=='conditional_footprint_rendered' for r in rendered),'available')
