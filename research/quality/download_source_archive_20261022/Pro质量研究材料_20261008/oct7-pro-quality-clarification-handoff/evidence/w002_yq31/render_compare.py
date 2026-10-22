"""Read-only visualization and exact-definition recomputation of selected source arrays.
Run: python render_compare.py. Requires numpy/pandas/scipy/shapely/matplotlib/Pillow.
No optimizer that changes annotation coordinates is invoked.
"""
from pathlib import Path
import os,tempfile
os.environ.setdefault("MPLCONFIGDIR",str(Path(tempfile.gettempdir())/"w002-matplotlib"))
import json,sys,numpy as np,pandas as pd,matplotlib,hashlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'3d_compensation/vendor'))
from arc_excerpt import paired_wall_proxy,footprint,project
from components_reused import intrinsic,compare
fontpath=Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
if fontpath.exists():font_manager.fontManager.addfont(str(fontpath));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(fontpath)).get_name()
plt.rcParams.update({'font.size':10,'axes.unicode_minus':False})
d=json.loads((O/'inputs/selected_records.json').read_text());rs={r['id']:r for r in d['annotations']+d['references']}
sL=.14707940277528614;sD=2.7126745183041483;sF=.8990282772073596
rows=[]
for r in d['annotations']:
 it=intrinsic(r)
 for g in d['references']:
  st=compare(r,g);LC=1-st['iou']+.5*st['centroid_distance_normalized'];J=sL*(it['direction_rms_deg']/sD+it['flat_top_angular_rms_deg']/sF)/2
  rows.append({'id':r['id'],'worker':r['worker'],'reference_id':g['id'],'reference_version':g['version'],**it,**st,'LC':LC,'J':J,'LCG':LC+.3*J})
m=pd.DataFrame(rows);m.to_csv(O/'metrics_recomputed.csv',index=False)
prior=pd.read_csv(O/'inputs/prior_metrics_selected.csv'); checks=[]
for _,r in m.iterrows():
 old=prior[(prior.id==r.id)&(prior.reference_id==r.reference_id)].iloc[0]
 for new,oldkey in [('LC','LC_fixed'),('J','J_fixed'),('LCG','LCG_fixed'),('iou','iou'),('direction_rms_deg','direction_rms_deg'),('flat_top_angular_rms_deg','flat_top_angular_rms_deg')]:
  err=abs(r[new]-old[oldkey]);checks.append({'id':r.id,'reference':r.reference_id,'metric':new,'absolute_difference':err});assert err<1e-10,(r.id,new,err)
pd.DataFrame(checks).to_csv(O/'reproduction_checks.csv',index=False)

def close(x):return np.concatenate([x,x[:1]])
def overlay(ax,r):
 t,b=paired_wall_proxy(r)
 for v,c in [(t,'#00ffff'),(b,'#ffe135')]:
  for a,b0 in zip(v,np.roll(v,-1,axis=0)):
   q=project(a[None]+np.linspace(0,1,160)[:,None]*(b0-a)[None]);splits=np.where(np.abs(np.diff(q[:,0]))>512)[0]+1
   for q0 in np.split(q,splits):ax.plot(q0[:,0],q0[:,1],c=c,lw=1.9)
 for a,b0 in zip(t,b):
  q=project(np.array([a,b0]));ax.plot(q[:,0],q[:,1],c='#f78eff',lw=.9)
 p=np.asarray(r['points']);ax.scatter(p[::2,0],p[::2,1],s=10,c='#00ffff',edgecolor='black',lw=.3,zorder=4);ax.scatter(p[1::2,0],p[1::2,1],s=10,c='#ffe135',edgecolor='black',lw=.3,zorder=4)

def draw3(ax,r,color,lw,alpha=1,ls='-'):
 t,b=paired_wall_proxy(r)
 for v in (t,b):q=close(v);ax.plot(q[:,0],q[:,2],q[:,1],c=color,lw=lw,alpha=alpha,ls=ls)
 for a,b0 in zip(t,b):ax.plot([a[0],b0[0]],[a[2],b0[2]],[a[1],b0[1]],c=color,lw=lw*.7,alpha=alpha,ls=ls)

ids=['R00766','R01505','R01500'];labels=[
 'W002 / P002 · R00766 | 10对点\n完整主空间，保留左侧折墙',
 'P017 · R01505 | 8对点\n左侧折墙简化；主体房间仍保留',
 'P006 · R01500 | 10对点\n完整范围意图；用户本轮评价：标得不好']
allv=np.vstack([np.vstack(paired_wall_proxy(r)) for r in rs.values()]);lo=allv.min(0)-.18;hi=allv.max(0)+.18
fig=plt.figure(figsize=(19.2,13.4)); gs=fig.add_gridspec(3,3,height_ratios=[1.04,1.18,1.3],hspace=.31,wspace=.14)
img=np.asarray(Image.open(O.parent/'original_photos/yqstnuAEVhm-31.png'))
for j,(id,label) in enumerate(zip(ids,labels)):
 r=rs[id];score=m[m.id==id].set_index('reference_id');a=score.loc['R02780'];b=score.loc['R02781']
 ax=fig.add_subplot(gs[0,j]);ax.imshow(img,extent=(0,1024,512,0));overlay(ax,r);ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xticks([]);ax.set_yticks([]);ax.set_title(label,fontsize=12.5,pad=9)
 ax=fig.add_subplot(gs[1,j]);
 for g,c,ls in [('R02780','#c48335','--'),('R02781','#858b96','-')]:
  f,_=footprint(rs[g]);ax.plot(*close(f).T,c=c,lw=1.8,ls=ls,label=('原GT · 8对' if g=='R02780' else '修订GT · 10对'))
 f,_=footprint(r);ax.plot(*close(f).T,c='#195cce',marker='o',ms=3.5,lw=1.8,label=id);ax.scatter([0],[0],c='k',marker='x',s=28,label='相机');ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[2],hi[2]);ax.set_aspect('equal',adjustable='box');ax.set_xlabel('x / h');ax.set_ylabel('z / h');ax.grid(alpha=.2);ax.legend(fontsize=8,loc='upper left')
 ax.set_title(f'原GT：IoU={a.iou:.3f}  LC={a.LC:.3f}  LC+0.3J={a.LCG:.3f}\n修订GT：IoU={b.iou:.3f}  LC={b.LC:.3f}  LC+0.3J={b.LCG:.3f}',fontsize=10.5,pad=10)
 ax=fig.add_subplot(gs[2,j],projection='3d');draw3(ax,rs['R02780'],'#c48335',1,.35,'--');draw3(ax,rs['R02781'],'#858b96',1.15,.5);draw3(ax,r,'#195cce',1.8)
 ax.scatter([0],[0],[0],c='k',marker='x',s=22);ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[2],hi[2]);ax.set_zlim(lo[1],hi[1]);ax.set_box_aspect((hi-lo)[[0,2,1]]);ax.view_init(elev=24,azim=-58);ax.set_xlabel('x/h');ax.set_ylabel('z/h');ax.set_zlabel('y/h');ax.tick_params(labelsize=8)
 ax.set_title(f'dir={b.direction_rms_deg:.2f}°  flat={b.flat_top_angular_rms_deg:.2f}°  J={b.J:.3f}\n条件总墙高={b.height_min_h:.3f}–{b.height_max_h:.3f}h',fontsize=10.5,pad=8)
fig.suptitle('yqstnuAEVhm-31：完整表达、几何实现和GT版本分别看',fontsize=18,y=.983)
fig.text(.5,.951,'三排：原图叠线 / 俯视BEV / 条件3D。三列共用相机、视角、轴限与单位；所有现存点及连接保持不变',ha='center',fontsize=11)
fig.text(.03,.079,'关键取舍：修订GT下，W002的LC更好（0.09244 < 0.11660）；加0.3J后，简化答略占优（0.12678 < 0.12889），差仅0.00211。',fontsize=11)
fig.text(.03,.057,'黄色=底边，青色=顶边；蓝色=标注，橙虚线=原GT R02780（8对），灰线=修订GT R02781（10对）。两个GT都用全部来源点与原连接。',fontsize=10)
fig.text(.03,.036,'固定地面y=-1、竖直墙；h为相机高单位，不是米。3D是条件重建；不修点、不调参、不新增语义认证。现存camera_visibility_unresolved状态保留。',fontsize=10)
fig.subplots_adjust(left=.055,right=.965,top=.902,bottom=.123)
fig.savefig(O/'W002_yq31_scope_geometry_comparison.png',dpi=165);plt.close(fig)
# Verify every source vertex remains within every shared-axis comparison view.
render={'ids':ids,'references':['R02780','R02781'],'axis_order':'x,z,y','axis_limits_xyz':{'x':[float(lo[0]),float(hi[0])],'y':[float(lo[1]),float(hi[1])],'z':[float(lo[2]),float(hi[2])]},'view':{'elevation':24,'azimuth':-58},'all_vertices_within_shared_limits':bool(np.all(allv>lo)&np.all(allv<hi)),'all_source_points_preserved':True,'GT_all_source_points_preserved':True,'recomputation_max_abs_error':max(c['absolute_difference'] for c in checks)}
(O/'render_manifest.json').write_text(json.dumps(render,indent=2))
a=m[(m.id=='R00766')&(m.reference_id=='R02781')].iloc[0];b=m[(m.id=='R01505')&(m.reference_id=='R02781')].iloc[0]
summary={'formula':{'LC':'1-IoU+0.5*C','C':'BEV centroid distance / sqrt(reference area)','J':'sL * (dir/sDir + flat/sFlat) / 2','LCG':'LC + lambda*J','sL':sL,'sDir':sD,'sFlat':sF,'lambda':.3},'W002_vs_simplified_revision_GT':{'LC_difference_W002_minus_simplified':a.LC-b.LC,'J_difference_W002_minus_simplified':a.J-b.J,'LCG_difference_W002_minus_simplified':a.LCG-b.LCG,'descriptive_crossing_lambda':(b.LC-a.LC)/(a.J-b.J),'threshold_is_not_recommended_weight':True},'counts':{'annotations':3,'references':2,'metric_rows':6}}
(O/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(render,ensure_ascii=False));print(m[['id','reference_id','iou','LC','J','LCG','direction_rms_deg','flat_top_angular_rms_deg']].to_string(index=False))
