from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parent
FONT=ROOT.parent/'personnel_composition_study_20261019/analysis/fonts/NotoSansSC-Regular.ttf'
fp=FontProperties(fname=str(FONT))
plt.rcParams.update({'font.family':fp.get_name(),'axes.unicode_minus':False,'svg.fonttype':'path'})
from matplotlib import font_manager
font_manager.fontManager.addfont(str(FONT))
m=pd.read_csv(ROOT/'structure_followup/FIXED_A_COMMON_DECOMPOSITION.csv')
r=m[(m.source_role=='TURN/K3/E2')&(m.m_to==7)].iloc[0]
g=pd.read_csv(ROOT/'structure_followup/background_gradient/GRADIENT_SUMMARY.csv').iloc[0]
fig,axes=plt.subplots(1,2,figsize=(14,6.8),gridspec_kw={'wspace':.28})
fig.subplots_adjust(top=.77,bottom=.15,left=.07,right=.98)
panels=[
 (axes[0],['C队自身','B队自身','净优势\n(C−B)'],[r.C_change,r.B_change,r.net_advantage_change],['59/76图提高','38/76图提高','56/76图提高'],'固定A：替换4人 → 7人','n=20；151条共同有效路径；76图、16楼'),
 (axes[1],['A队自身','B队自身','C队自身','净优势\n(C−B)'],[g.A_change_B8L2,g.B_change_B8L2,g.C_change_B8L2,g.net_change_B8L2],['26/39图提高','29/39图提高','26/39图提高','23/39图减弱'],'固定X/Y/Z：背景增加1名较多转折成员','n=20、m=7；1,397个共同有效比较；39图、15楼')
]
for ax,names,values,notes,title,subtitle in panels:
 colors=['#168477' if v>=0 else '#BD4B53' for v in values]
 ax.bar(range(len(values)),values,color=colors,width=.60)
 ax.axhline(0,color='#75808A',linewidth=.8)
 ax.set_xticks(range(len(names)),names,fontsize=12)
 ax.set_ylabel('B8L2变化（分）',fontsize=12)
 ax.set_ylim(-1.25,1.95)
 ax.set_title(title,fontsize=13,pad=34,fontweight='bold')
 ax.text(.5,1.03,subtitle,transform=ax.transAxes,ha='center',fontsize=10,color='#4C5964')
 ax.spines[['top','right']].set_visible(False)
 ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
 for i,(v,note) in enumerate(zip(values,notes)):
  ax.text(i,v+(.06 if v>=0 else -.07),f'{v:+.3f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=13,fontweight='bold')
  ax.text(i,1.70,note,ha='center',fontsize=10,color='#4C5964')
fig.suptitle('替换规模与背景：把C队自身变化和净优势分开',fontsize=19,y=.97,fontweight='bold')
fig.text(.5,.025,'真实数据v2 · 冻结B8L2 · 背景/路径→图片→建筑等权 · 两图均采用各自共同可评分样本',ha='center',fontsize=10,color='#4C5964')
out=ROOT/'figures';out.mkdir(exist_ok=True)
for suffix in ['png','svg']:
 fig.savefig(out/f'结构换类_规模与背景效应.{suffix}',dpi=180,bbox_inches='tight',facecolor='white')
print('Saved structural decision figure.')
