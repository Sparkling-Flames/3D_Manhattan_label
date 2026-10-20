"""Plot complete fixed-core paths associated with selected mechanism examples."""
import argparse,os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/personnel_profile_mechanism_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd
import numpy as np


def main():
 p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);p.add_argument('--font',type=Path);a=p.parse_args()
 font=a.font or a.work/'fonts/NotoSansSC-Regular.ttf';font_manager.fontManager.addfont(str(font));plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(font)).get_name(),'font.size':10,'axes.unicode_minus':False})
 df=pd.read_csv(a.work/'path_scores.csv');nd=pd.read_csv(a.work/'path_node_support.csv')
 cfg=[('UwV83HsGsw3-22','H5_addL_0','Manual · Uw-22 · 困难',464.7),('e9zR4mvMWw7-19','H5_addL_1','Manual · e9z-19 · 困难',713.5),('Z6MFQCViBuw-10','H5_addL_1','Semi · Z6-10 · 简单',369.1)]
 fig,axs=plt.subplots(2,3,figsize=(15,8.1),gridspec_kw={'height_ratios':[1.05,1]},sharex='col')
 for j,(image,path,title,cx) in enumerate(cfg):
  sub=df[df.path_id.str.startswith(image+'__') & df.path_id.str.endswith(path)].sort_values('n')
  anchor='W130' if image.startswith('Z6') else 'W102'
  groups=nd[(nd.path_id==sub.path_id.iloc[0]) & ((nd.center_x-cx).abs()<6) & nd.workers.str.split('|').apply(lambda ws:anchor in ws)].sort_values('n')
  assert len(groups)==len(sub),(image,len(groups),len(sub))
  x=sub.L.to_numpy();q=sub.B8L2.to_numpy();d=sub.D10.to_numpy();support=groups.H_support.to_numpy()+groups.L_support.to_numpy();threshold=sub.threshold.to_numpy()
  ax=axs[0,j];ax.plot(x,q,'o-',color='#c72465',lw=2,label='B8L2');ax.plot(x,d,'--',color='#197fa7',lw=1.4,label='D10')
  ax.set_title(title,fontsize=12,pad=12);ax.set_ylim(35,102);ax.set_yticks([40,60,80,100]);ax.grid(axis='y',alpha=.18);ax.spines[['top','right']].set_visible(False)
  if j==0:ax.set_ylabel('融合质量')
  for i in range(len(x)):
   if i==0 or sub.nodes.iloc[i]!=sub.nodes.iloc[i-1]:
    ax.annotate(f'{int(sub.nodes.iloc[i])}点',xy=(x[i],q[i]),xytext=(0,8 if q[i]<85 else -17),textcoords='offset points',ha='center',fontsize=8,color='#7d1943')
  ax=axs[1,j];ax.bar(x,groups.H_support,color='#31aad6',width=.65,label='局部H支持');ax.bar(x,groups.L_support,bottom=groups.H_support,color='#f3a047',width=.65,label='局部L支持');ax.step(x,threshold,where='mid',color='#333a42',ls='--',lw=1.5,label='该团队门槛')
  for xi,si,ti in zip(x,support,threshold):
   if si>=ti:ax.plot(xi,si+.15,'o',color='#19623b',markersize=4)
  ax.set_ylim(0,9);ax.set_yticks(range(0,9,2));ax.grid(axis='y',alpha=.15);ax.spines[['top','right']].set_visible(False);ax.set_xticks(range(11));ax.set_xlabel('追加历史较低Q人数（固定5H核心）')
  ax.set_title('局部参考点的支持' if j<2 else '参考中无对应点的局部额外节点',fontsize=10,pad=8)
  if j==0:ax.set_ylabel('支持票 / 所需票数')
 h1,l1=axs[0,0].get_legend_handles_labels();h2,l2=axs[1,0].get_legend_handles_labels();fig.legend(h1+h2,l1+l2,ncol=5,loc='upper left',bbox_to_anchor=(.04,.918),frameon=False,fontsize=9)
 fig.suptitle('同一条增长路径中，结构支持与质量可能反复切换',fontsize=17,y=.98)
 fig.subplots_adjust(left=.055,right=.985,top=.815,bottom=.16,wspace=.23,hspace=.27)
 fig.text(.055,.075,'数字“点”是最终墙角对数。下图绿色点表示局部节点通过投票。Manual的两个局部点对应参考节点；Semi的额外节点在门槛升高后被去除。',fontsize=9)
 fig.text(.055,.043,'这是三条已固定成员顺序的案例路径，完整展示追加0–10人；不表示随机队伍的平均效应，也不据此选择通用最优配比。对应分组按共同原观察追踪。',fontsize=9)
 out=a.work/'figures/growth_case_paths.png';fig.savefig(out,dpi=155);plt.close(fig);print(out)

if __name__=='__main__':main()
