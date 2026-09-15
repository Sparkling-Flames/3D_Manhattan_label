"""Independent numerical figures; no original images and no custom colour style."""
import json
from pathlib import Path
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import OUT

def make_figures(show=False):
 import matplotlib.pyplot as plt
 dest=OUT/'figures';dest.mkdir(parents=True,exist_ok=True);items=[]
 def save(fig,name,caption,df):
  fig.tight_layout();fig.savefig(dest/(name+'.png'),dpi=175)
  df.to_csv(dest/(name+'_data.csv'),index=False)
  items.append(dict(file=name+'.png',data=name+'_data.csv',caption=caption))
  if show:plt.show()
  plt.close(fig)
 x=pd.read_csv(OUT/'expert/anchor_support_ceiling.csv');x=x.sort_values(['expert_tag','image_id']).reset_index(drop=True);x['code']=['M'+str(j+1)if x.expert_tag[j]=='中等'else'H'+str(j-3) for j in range(len(x))]
 fig,ax=plt.subplots(figsize=(9,4.8));pos=np.arange(len(x));ax.bar(pos,x.supported_clusters,label='Supported clusters (>=2 people)');ax.bar(pos,x.singletons,bottom=x.supported_clusters,label='Singleton clusters')
 ax.set_xticks(pos,[f'{r.code}\nn={r.n_valid}' for _,r in x.iterrows()]);ax.set_ylabel('Total numerical clusters');ax.set_title('Expert medium / hard anchors: full observed people, distance = 0.10');ax.legend();ax.grid(axis='y',alpha=.2)
 save(fig,'anchor_cluster_counts','8张高人数人工中等/困难图：柱高为总簇数，重复支持簇和单人簇分开。M1–M4、H1–H4的完整ID见同名data.csv。不是独立随机样本。',x)
 f=pd.read_csv(OUT/'proposal/singleton_threshold_by_n.csv');fig,ax=plt.subplots(figsize=(8,4.6));ax.step(f.n,f.fixed10pct,where='mid',label='Old 10% maximum');ax.step(f.n,f.count_band,where='mid',label='Proposed count bands (unfrozen)');ax.plot(f.n,1/f.n*0+2,linestyle=':',label='Absolute count <= 2 sensitivity');ax.set(xlabel='Actual valid distinct people',ylabel='Allowed singleton count',title='A percentage gate implies a discontinuous integer threshold',xticks=[4,6,8,10,16,19,20,24]);ax.legend();ax.grid(axis='y',alpha=.2)
 save(fig,'singleton_thresholds','10%换算为整数后，19人仅允许1个单人簇，20人却允许2个。分段计数也只是待裁决试行表，不是统计上校准的替代标准。',f)
 a=pd.read_csv(OUT/'extra/exact_common18_panel.csv');a=a[a.cut==.1].merge(x[['image_id','code']],on='image_id').sort_values('code');fig,ax=plt.subplots(figsize=(9,4.8));pos=np.arange(len(a));ax.bar(pos,a.supported_clusters,label='Supported clusters');ax.bar(pos,a.singletons,bottom=a.supported_clusters,label='Singletons');ax.set_xticks(pos,a.code);ax.set_ylabel('Clusters from the same 18 real people');ax.set_title('Exact shared-person comparison: composition and count held fixed');ax.legend();ax.grid(axis='y',alpha=.2)
 save(fig,'common18_cluster_counts','8图使用完全相同的18名真实人员重算，总簇数中位数中等5.5、困难8.5；仍有重叠。控制人数/名单不等于消除楼宇、阶段、选图差异。',a)
 d=pd.read_csv(OUT/'process/support_discovery_vs_conditional_stability.csv');i='uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e';d=d[(d.image_id==i)&(d.condition=='manual')&(d.cut==.1)].sort_values('observed_k');fig,ax=plt.subplots(figsize=(8.4,4.8));ax.plot(d.observed_k,d.p_all_modes_seen_twice_exact,linestyle='--',marker='o',label='Exact ceiling: all supported modes seen twice');ax.plot(d.observed_k,d.p_stable_core15_unconditional,marker='s',label='Reclustered stable core through observed end');ax.set(xlabel='Distinct observed people in the prefix',ylabel='Fraction of orders / exact finite-pool probability',ylim=(0,1.02),title='Rare supported modes can delay a cumulative stability threshold');ax.legend(loc='upper left');ax.grid(axis='y',alpha=.2)
 save(fig,'support_discovery_ceiling','该图23人、18/2/2/1模式：即使模式完全固定，前19人同时看到两个双人模式的全部4人，概率上限仅43.77%。故“80%顺序到19人稳定”混入发现稀有模式的等待；不是收敛失败证明。',d)
 s=pd.read_csv(OUT/'structure/per_image_all_cuts.csv');ids=[i,'uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97','VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d','uNb9QFRL6hY_9f199750b00c4f5484a546d79e06a0f8'];dat=s[(s.image_id.isin(ids))&(s.condition=='manual')].merge(x[['image_id','code']],on='image_id');fig,ax=plt.subplots(figsize=(8.4,4.8))
 for image,g in dat.groupby('image_id'):
  g=g.sort_values('cut');ax.plot(g.cut,g.total_clusters,marker='o',label=g.code.iloc[0]+' total')
 ax.set(xlabel='d_mask threshold (1 - image-region IoU)',ylabel='Total clusters',title='Cluster counts depend on numerical resolution, not only the image');ax.legend();ax.grid(axis='y',alpha=.2)
 save(fig,'geometry_cut_sensitivity','总簇数同时依赖几何尺度；不能选一个恰好贴合人工tag的阈值，再宣称它得到独立验证。',dat)
 (dest/'FIGURES.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8');return items

if __name__=='__main__':make_figures()
