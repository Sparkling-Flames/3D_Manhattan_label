#!/usr/bin/env python3
"""Actual RGB detail and matched-observation vote mechanism; no synthetic image."""
from pathlib import Path
import sys,json,gzip, numpy as np,pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from render_exact_abc_case import read,erp,save_figure,points3d,save_csv,COLORS,HERE
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
W=HERE.parent;O=W/'stage06_cases';F=O/'local';F.mkdir(exist_ok=True)
structure=read(O/'traces_semantic/ae9bc0bdaf9a5f2119cea910.json.gz');lower=read(O/'traces/164f7e24305914ffb1d8c116.json.gz');higher=read(O/'traces/bbd4c6e7e49cced53ce71301.json.gz')
im=np.asarray(Image.open(HERE/'originals/jtcxE69GiFV-13.png').convert('RGB').resize((1024,512),Image.Resampling.LANCZOS))
fig=plt.figure(figsize=(16,8));gs=fig.add_gridspec(1,4,width_ratios=[1,1,1,1.2],wspace=.32)
ref=structure['reference']['points_1024x512']
for i,title in enumerate(['真实RGB：瓷砖墙与窗帘墙之间\n顶部与侧壁可见短折返','TARGET_DSTRUCT n10/m7\n同一合法目标，补回两个转折','OPPGEOM 固定XYZ：n14→n18\n短折返少一端']):
 ax=fig.add_subplot(gs[0,i]);ax.imshow(im,extent=[0,1024,512,0]);ax.set_xlim(625,730);ax.set_ylim(425,110);ax.set_title(title,fontsize=11);ax.set_xlabel('ERP x / 1024');ax.set_ylabel('ERP y / 512' if i==0 else '')
 if i==1:
  for arm in 'ABC':erp(ax,structure['arms'][arm]['geometry']['points'],COLORS[arm],1.7,.95)
  erp(ax,ref,'black',1.0,.8,'--')
  ax.legend(handles=[Line2D([0],[0],color=COLORS[a],lw=2,label=a)for a in 'ABC'],loc='upper center',bbox_to_anchor=(.5,-.11),ncol=3,frameon=False,fontsize=9,handlelength=1.1,columnspacing=.8)
 elif i==2:
  erp(ax,lower['arms']['C']['geometry']['points'],'#2471a3',1.7,.95)
  erp(ax,higher['arms']['C']['geometry']['points'],'#d95f28',1.7,.95)
  erp(ax,ref,'black',1.0,.7,'--')
  ax.legend(handles=[Line2D([0],[0],color='#2471a3',lw=2,label='n14'),Line2D([0],[0],color='#d95f28',lw=2,label='n18')],loc='upper center',bbox_to_anchor=(.5,-.11),ncol=2,frameon=False,fontsize=9,handlelength=1.1,columnspacing=.8)
 ax.tick_params(labelsize=9)
ax=fig.add_subplot(gs[0,3]);xx=np.array([0,1,3,4]);counts=[]
for case in [lower,higher]:
 groups=case['arms']['C']['full_state']['identity_groups']
 for target_x in [ref[2][0],ref[4][0]]:
  group=min(groups,key=lambda g:abs((g['center'][1][0]-target_x+512)%1024-512));counts.append(group['support'])
bars=ax.bar(xx,counts,color=['#2471a3','#2471a3','#d95f28','#d95f28']);bars[-1].set_alpha(.35)
ax.hlines(lower['arms']['C']['minimum_support'],-.5,1.5,color='#2471a3',linestyle='--');ax.hlines(higher['arms']['C']['minimum_support'],2.5,4.5,color='#d95f28',linestyle='--')
for x,c in zip(xx,counts):ax.text(x,c+.15,str(c),ha='center')
ax.set_ylim(0,11);ax.set_xticks(xx,['n14\n近 r2','n14\n近 r3','n18\n近 r2','n18\n近 r3']);ax.set_ylabel('实际独立人员支持票');ax.set_title('同一原始观察组的票数\n门槛由7升到9；末组8票失选',fontsize=11);ax.grid(axis='y',alpha=.2)
fig.suptitle('jtcxE69GiFV-13：真实短折返、结构补充与人数门槛反转',fontsize=15,y=.98)
fig.text(.5,.025,'底角受浴缸、窗帘和洁具遮挡；RGB支持墙面短折返存在，精确底部定位仍按已确认目标参考评价。\n上图仅为局部放大；完整原答、目标参考和融合环均在配套ERP/BEV/3D图与CSV中保存。',ha='center',fontsize=10)
fig.subplots_adjust(top=.85,bottom=.23);save_figure(fig,F/'STRUCTURE_AND_THRESHOLD_RGB_DETAIL.png',dpi=170);save_figure(fig,F/'STRUCTURE_AND_THRESHOLD_RGB_DETAIL.pdf');plt.close(fig)
# Failure: selected groups need a complete projected source ring, not only separate votes.
failure=read(O/'traces/bac6397542c7a06a9d811694.json.gz');rows=[]
for arm,r in failure['arms'].items():
 selected={g['feature_id']for g in r['full_state']['identity_groups']if g['selected']}
 for a in r['full_state']['assignments']:
  have=set(a['feature_ids']);rows.append(dict(event_id=failure['event']['event_id'],arm=arm,worker=a['worker'],source_object_id=a['id'],all_source_groups='|'.join(a['feature_ids']),selected_groups='|'.join(sorted(selected)),selected_group_n=len(selected),selected_hits=len(have&selected),covers_all_selected=selected<=have))
coverage=pd.DataFrame(rows);save_csv(F/'FAILURE_EXACT_SOURCE_RING_COVERAGE.csv',coverage)
fig,axs=plt.subplots(1,2,figsize=(13,6),gridspec_kw={'width_ratios':[1.4,1]})
c=failure['arms']['C'];selected=[g for g in c['full_state']['identity_groups']if g['selected']];workers=sorted(coverage[coverage.arm=='C'].worker)
mat=np.array([[int(w in {m['worker']for m in g['members']})for g in selected]for w in workers])
ax=axs[0];ax.imshow(mat,cmap='Blues',vmin=0,vmax=1,aspect='auto');ax.set_xticks(range(len(selected)),[g['feature_id'].replace('node_','g')+f'\n{g["support"]}票'for g in selected]);ax.set_yticks(range(len(workers)),workers,fontsize=9);ax.set_title('C队：人员×入选对应组\n没有一人覆盖完整五组',fontsize=12);ax.set_xlabel('实际对应组（蓝色＝有原答观察）')
ax=axs[1];g=coverage.groupby('arm').covers_all_selected.sum().reindex(list('ABC'));ax.bar(range(3),g.values,color=[COLORS[a]for a in 'ABC']);ax.set_xticks(range(3),['A 原队','B 同类换人','C 跨类换人']);ax.set_ylabel('覆盖全部入选组的完整原答数');ax.set_ylim(0,max(g.max(),1)+1)
for i,v in enumerate(g):ax.text(i,v+.1,str(int(v)),ha='center')
ax.set_title('ABC都入选5组，完整连接结果不同\nC没有可用来源环，Q记缺失而非0',fontsize=12);ax.grid(axis='y',alpha=.2)
fig.suptitle('x8F5xyUWy9e-08：分别过票不等于组合后有完整来源环',fontsize=14);fig.tight_layout(rect=[0,0,1,.94]);save_figure(fig,F/'FAILURE_SOURCE_RING_MATRIX.png',dpi=170);save_figure(fig,F/'FAILURE_SOURCE_RING_MATRIX.pdf');plt.close(fig)
print('saved local RGB/threshold and failure co-observation figures')
