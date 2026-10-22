#!/usr/bin/env python3
"""Draw unchanged native endpoints and frozen raw answers on the Release image."""
import shutil
import numpy as np
import pandas as pd
from PIL import Image
import export_cases as e
from analyze_mechanism import load_viewer
HERE=e.HERE
PHOTO=e.NEW/'mechanisms/originals/B6ByNegPMKs_e26e2cb761894264a4a34b1046701f6b.png'

def font():
 path=HERE/'assets/NotoSansCJKsc-B6Subset.ttf'
 if not path.exists():
  from fontTools.ttLib import TTFont
  from fontTools import subset
  from fontTools.varLib.instancer import instantiateVariableFont
  f=TTFont('/tmp/HOHONET_NotoSansCJKsc-VF.ttf');o=subset.Options();o.layout_features=['*'];s=subset.Subsetter(options=o)
  s.populate(text=''.join(p.read_text() for p in HERE.glob('*.py'))+''.join(chr(i) for i in range(32,127))+'−°✓×→')
  s.subset(f);f=instantiateVariableFont(f,{'wght':400},inplace=False);path.parent.mkdir(exist_ok=True);f.save(path)
  license_source=e.V3/'evidence/fusion_jtc28_pure_8/assets/FONT_LICENSE.txt'
  if license_source.exists():shutil.copyfile(license_source,path.parent/'FONT_LICENSE.txt')
 return path

def main():
 v=load_viewer();v._configure_font(font());v.plt.rcParams['font.family']=[v.plt.rcParams['font.family'][0],'DejaVu Sans']
 photo=np.asarray(Image.open(PHOTO).convert('RGB'));cases=[e.gs.read(p) for p in sorted((HERE/'cases').glob('*.json.gz'))]
 c=cases[0];ref=np.asarray(c['reference']['points_1024x512']);refg=v.viewer_geometry(ref);out=HERE/'figures';out.mkdir(exist_ok=True)
 colors={'A':'#d78333','B':'#237da5','C':'#c2374b'}
 fig=v.plt.figure(figsize=(19,11.5));grid=fig.add_gridspec(2,3,height_ratios=[.90,1.18],hspace=.32,wspace=.20)
 for j,t in enumerate(c['teams']):
  color=colors[t['label']];ax=fig.add_subplot(grid[0,j]);v._erp_background(ax,photo)
  v._erp_edges(ax,ref,'#ffe476',1.35,reference=True,markers=False);v._erp_edges(ax,t['geometry']['points'],color,1.7,markers=True)
  ax.set_title({'A':'A 原块 X · 7个节点','B':'B 同类换人 Y · 6个节点','C':'C 改类换人 Z · 8个节点'}[t['label']],loc='left',fontsize=15)
  for k in [6,7,8,9]:
   x,y=ref[2*k+1];ax.text(x,y+15,f'r{k}',fontsize=10,color='#fff18e',ha='center',bbox=dict(facecolor='#17202a',alpha=.68,edgecolor='none',pad=.3))
  counts=' / '.join(f'{cl}={n}' for cl,n in t['counts'].items() if n)
  ax.text(.01,-.14,counts,transform=ax.transAxes,fontsize=10,color='#42536a')
  bx=fig.add_subplot(grid[1,j]);v._bev_ring(bx,refg['floor'],'#303741',1.5,reference=True)
  floor=np.asarray(t['geometry']['footprint']);v._bev_ring(bx,floor,color,2.0);bx.scatter(floor[:,0],floor[:,1],color=color,s=22,zorder=6)
  v._style_bev(bx,[-4.65,1.55,-6.10,1.0]);bx.set_aspect('equal',adjustable='box')
  q='invalid_floor · 不提供质量分数' if t['B8L2'] is None else f'B8L2 {t["B8L2"]:.3f} / D10 {t["D10"]:.3f}'
  bx.set_title(q,fontsize=12,loc='left',pad=11)
  if t['label']=='C':
   intersection=pd.read_csv(HERE/'SELF_INTERSECTIONS.csv').iloc[0];xy=(intersection.intersection_x_h,intersection.intersection_z_h)
   bx.scatter(*xy,s=100,marker='x',linewidths=2.5,color='#951936',zorder=10)
   bx.annotate('r7 已入选，r8 未入选\nr7→r9 与 r5→r6 相交',xy,xytext=(-4.30,-2.25),fontsize=11,color='#a12038',
    arrowprops=dict(arrowstyle='->',color='#a12038'),bbox=dict(facecolor='white',edgecolor='#e4c8ce',alpha=.94))
   for k in [6,7,8,9]:
    x,z=refg['floor'][k];bx.annotate(f'r{k}',(x,z),xytext=((7 if k%2 else -20),(8 if k<8 else -14)),textcoords='offset points',fontsize=10,color='#263449')
   bx.text(.02,.02,'红线是原生失败候选；未修补连接',transform=bx.transAxes,fontsize=10,color='#9d2940')
  else:bx.text(.02,.02,f'IoU {t["iou_2d"]:.4f} · 节点召回 {t["ref_node_recall_9"]:.1f}',transform=bx.transAxes,fontsize=10,color='#42536a')
 fig.suptitle('B6-47 · 好的个人结构表达，也可能只在融合中保留一半而导致失败',x=.035,ha='left',fontsize=20,y=.985)
 fig.text(.035,.935,'Manual n20，三个团队共同背景16人，A↔B、A↔C、B↔C均实际换4人。类别来自排除B6建筑的原 V3_JOINT_QT；J2四席改为J5。',fontsize=11,color='#42536a')
 fig.text(.035,.035,'黄色ERP线、黑色BEV虚线为冻结参考。原图中的中央凸出墙两侧对应 r7 与 r8；C 的节点召回更高，但底面自交，分数保留缺失。\n这些是原生未人工确认源环的条件结果；图示不改环序、不修补失败，也不把未知质量填0。n22重复了同类局部失败，完整状态与票账另表保存。',fontsize=10,color='#42536a')
 fig.subplots_adjust(left=.035,right=.985,top=.88,bottom=.10);fig.savefig(out/'B6_NATIVE_ERP_BEV.png',dpi=155,facecolor='white');v.plt.close(fig)

 # Actual four-person target block: ERP / BEV / 3D and matched local vote counts.
 mm={m['worker_id']:m for m in c['members']};workers=['W102','W109','W115','W126'];wc=['#116c92','#a3548e','#3c8b63','#bf7530']
 fig=v.plt.figure(figsize=(20,13));grid=fig.add_gridspec(2,3,height_ratios=[1,1.0],hspace=.45,wspace=.30)
 ax=fig.add_subplot(grid[0,0]);v._erp_background(ax,photo,bounds=[385,515,70,450]);v._erp_edges(ax,ref,'#ffe476',1.7,reference=True)
 for w,col in zip(workers,wc):v._erp_edges(ax,mm[w]['points'],col,1.35,alpha=.86,markers=True)
 for k in [6,7,8,9]:
  x,y=ref[2*k+1];ax.text(x,y+8,f'r{k}',color='#fff18e',fontsize=11,ha='center',bbox=dict(facecolor='#17202a',alpha=.65,edgecolor='none',pad=.25))
 ax.set_title('四位换入者的同图原答\n中央凸出墙的前后两角均保留',loc='left',fontsize=13)
 bx=fig.add_subplot(grid[0,1]);v._bev_ring(bx,refg['floor'],'#303741',1.5,reference=True)
 for w,col in zip(workers,wc):v._bev_ring(bx,v.viewer_geometry(mm[w]['points'])['floor'],col,1.5,alpha=.88)
 v._style_bev(bx,[-.70,.03,-1.65,-.27]);bx.set_aspect('equal',adjustable='box')
 for k in [6,7,8]:
  x,z=refg['floor'][k];bx.annotate(f'r{k}',(x,z),xytext=(5,5),textcoords='offset points',fontsize=12,color='#303741')
 bx.set_title('原答局部 BEV：10点底面均有效\n原答位置略有差异，结构表达一致',loc='left',fontsize=13)
 cx=fig.add_subplot(grid[0,2],projection='3d');v._wire3d(cx,refg,'#303741',reference=True)
 for w,col in zip(workers,wc):v._wire3d(cx,v.viewer_geometry(mm[w]['points']),col)
 v._style3d(cx,[-4.65,1.55,-6.10,1.0],[-1.05,1.4],{'elev':24,'azim':44});cx.set_title('同一四人原答的3D代理\n相机高度归一化，非实测深度',loc='left',fontsize=13)
 from matplotlib.lines import Line2D
 fig.legend([Line2D([0],[0],color=col,lw=2) for col in wc],workers,loc='upper center',bbox_to_anchor=(.53,.94),ncol=4,frameon=False)
 fg=pd.read_csv(HERE/'FOCUS_GROUPS.csv')
 for ci,case in enumerate(cases):
  ax=fig.add_subplot(grid[1,ci]);d=fg[fg.case_id.eq(case['case_id'])];rows=[d[d.arm.eq(a)&d.role.eq(role)].iloc[0] for role in ['r7','r8_primary'] for a in 'ABC'];z=pd.DataFrame(rows);x=np.arange(6)
  ax.bar(x,z.background_votes,color='#95a9b9',width=.66,label='共同背景票');ax.bar(x,z.variable_block_votes,bottom=z.background_votes,color=['#d78333','#237da5','#c2374b']*2,width=.66,label='本队4人块票')
  th=case['teams'][0]['minimum_support'];ax.axhline(th,color='#ad3348',ls='--',lw=1.4,label=f'本队门槛 {th}')
  for i,r in enumerate(z.itertuples()):ax.text(i,r.support+.18,f'{r.support}'+(' ✓' if r.selected else ''),ha='center',fontsize=11)
  ax.set_xticks(x,['A','B','C','A','B','C']);ax.set_ylim(0,14);ax.set_ylabel('人员票数');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
  ax.text(1,-1.45,'r7：前角',ha='center',fontsize=11);ax.text(4,-1.45,'r8：后角主对应组',ha='center',fontsize=11)
  ax.set_title(f'n={case["n"]}：配套两角只让一角通过',loc='left',fontsize=13,pad=12)
  ax.text(.02,-.25,('r8另有1票单独对应组，不能直接算成10票。' if ci==0 else 'r8另有2票单独对应组，不能直接算成11票。'),transform=ax.transAxes,fontsize=10,color='#42536a')
  if ci==0:ax.legend(loc='upper left',fontsize=9,frameon=False)
 ax=fig.add_subplot(grid[1,2]);ax.axis('off')
 lines=[('完整原答：','r6 → r7 → r8 → r9'),('投影后：','r6 → r7 → r9'),('只过r7：','r7→r9 横穿 r5→r6'),('n20 源环支持：','4位换入者 + W112'),('n22 源环支持：','上述5人 + W130'),('A→C 背景重新归组：','114 / 127 个观察均无变化')]
 for i,(a,b) in enumerate(lines):
  y=.92-i*.14;ax.text(.01,y,a,fontsize=11,color='#536477');ax.text(.01,y-.055,b,fontsize=12,color='#9e2941' if i in [1,2] else '#263449')
 fig.suptitle('同类原答的有效补充，如何在局部投票和投影环中变成不完整结构',x=.035,ha='left',fontsize=20,y=.99)
 fig.text(.035,.04,'全部线条来自冻结原答、参考或原生融合；没有重新评分。两种人数使用嵌套但不同背景，不能用两例估计总体失败率。\nr8单独对应组中的 W133 与主组部分原答在完整环匹配中被对应到r7侧；不能只凭局部近邻把票相加。7.5°为融合遗漏代价参数，非原答9°/12°分簇阈值。',fontsize=10,color='#42536a')
 fig.subplots_adjust(left=.05,right=.98,top=.88,bottom=.15);fig.savefig(out/'B6_RAW_PAIR_AND_VOTES.png',dpi=155,facecolor='white');v.plt.close(fig)
 e.save(HERE/'FIGURE_RECEIPT.json',dict(photo_path=str(PHOTO.relative_to(e.ROOT)),photo_sha256=e.sha(PHOTO),figures=[dict(path=str(p.relative_to(HERE)),sha256=e.sha(p),bytes=p.stat().st_size) for p in sorted(out.glob('*.png'))],
  frozen_candidate_geometry_unchanged=True,invalid_candidate_shown_as_diagnostic_only=True,new_fusion_calls=0,score_calls=0))
 print('Saved original-image ERP/BEV and raw ERP/BEV/3D plus exact local vote figures.',flush=True)

if __name__=='__main__':main()
