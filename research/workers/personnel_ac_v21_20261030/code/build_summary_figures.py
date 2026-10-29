"""Scientific plots from finalized tables; points are means, bars are image P10-P90."""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage08_report/figures';OUT.mkdir(parents=True,exist_ok=True)
assert json.loads((ROOT/'stage05_main/SUMMARY_RECEIPT.json').read_text())['complete']
font=ROOT/'stage06_cases/source/NotoSansCJKsc-Regular.otf';font_manager.fontManager.addfont(str(font))
plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(font)).get_name(),'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'font.size':10,'svg.fonttype':'none'})
d=pd.read_csv(ROOT/'stage05_main/CONDITION_METRIC_SUMMARY.csv.gz',dtype={'n_condition':str,'m_condition':str},low_memory=False)
specs=[('TARGET_DSTRUCT_K3','20','7','2->3','TARGET K3  中→高  20/7'),('TARGET_DSTRUCT_K2','20','7','1->2','TARGET K2  粗层  20/7'),
 ('TARGET_DSTRUCT_K3','20','10','1->2','TARGET K3  低→中  20/10'),('V21_DSTRUCT_RAW3_K3','20','8','2->3','RAW3  中→高  20/8'),
 ('V21_DSTRUCT_RAW3_K3','20','10','1->2','RAW3  低→中  20/10'),('V21_DSTRUCT_RAW3_K3','20','10','2->3','RAW3  中→高  20/10'),
 ('V21_DSTRUCT_RAW3_K3','23','12','1->2','RAW3  低→中  23/12'),('OPPJOINT_K3','20','7','1->3','JOINT K3  Q秩1→3  20/7'),
 ('OPPJOINT_K3','20','10','1->2','JOINT K3  Q秩1→2  20/10'),('OPPJOINT_K3','23','12','1->2','JOINT K3  Q秩1→2  23/12'),
 ('OPPJOINT_K4','20','10','1->2','JOINT K4  Q秩1→2  20/10'),('OPPJOINT_K4','23','12','1->2','JOINT K4  Q秩1→2  23/12'),
 ('RFUSE_GEOM_K2','20','4','1->2','RFUSE K2  响应秩1→2  20/4')]
rows=[]
for method,n,m,role,label in specs:
    x=d[(d.scope=='primary')&(d.condition=='manual')&(d.analysis_view=='A_fixed_n')&(d.method==method)&(d.n_condition==n)&(d.m_condition==m)&(d.role_direction==role)&(d.metric=='B8L2_CA')]
    assert len(x)==1
    row=x.iloc[0].to_dict();row['label']=label;rows.append(row)
f=pd.DataFrame(rows);f.to_csv(OUT/'FIG01_EXACT_DATA.csv',index=False,encoding='utf-8-sig')
colors=['#286695' if x.startswith('TARGET') else '#B76A24' if 'RAW3' in x else '#147B72' if x.startswith('OPP') else '#8755A2' for x in f.method]
fig,ax=plt.subplots(figsize=(11.7,7.6));fig.subplots_adjust(left=.31,right=.80,top=.87,bottom=.12)
ax.axvline(0,color='#888',lw=1,ls='--')
for y,(row,color) in enumerate(zip(f.to_dict('records'),colors)):
    ax.plot([row['image_p10'],row['image_p90']],[y,y],color=color,lw=2.4,alpha=.7)
    ax.scatter([row['image_mean']],[y],c=color,s=36,zorder=3)
    ax.text(1.025,y,f"{row['image_mean']:+.2f}   {int(row['positive_images'])}/{int(row['valid_images'])} 图   {int(row['valid_buildings'])} 楼",transform=ax.get_yaxis_transform(),va='center',fontsize=9)
ax.set_yticks(range(len(f)),f.label);ax.invert_yaxis();ax.set_xlabel('B8L2 变化  C−A（分）')
ax.grid(axis='x',alpha=.15);ax.set_xlim(-21,18)
fig.suptitle('固定人数与替换规模的直接 AC 结果',fontsize=17,y=.97)
fig.text(.31,.915,'点：图片等权均值；线：各图片均值的 P10–P90，非置信区间',fontsize=10)
fig.text(.01,.025,'均使用预注册 neutral_members_0 背景路径；各行是各方法实际可覆盖范围，人员与类别意义不同。\nRAW3 23/12 的 4 张图仅来自 1 栋楼；直接 AC 没有同类 B 对照。',fontsize=9)
for ext in ['png','svg']:fig.savefig(OUT/('FIG01_EQUAL_SIZE_EFFECTS.'+ext),dpi=180,bbox_inches='tight')
plt.close(fig)

context=pd.read_csv(ROOT/'stage05_context_common/FROZEN_CONTEXT_EFFECT_SUMMARY.csv.gz',dtype={'n_condition':str,'m_condition':str},low_memory=False)
c=context[(context.method=='TARGET_DSTRUCT_K3')&(context.analysis_view=='A_fixed_n')&(context.n_condition=='20')&(context.m_condition=='7')&(context.role_direction=='2->3')&(context.context_axis=='official_difficulty')]
c.to_csv(OUT/'FIG02_EXACT_CONTEXT_DATA.csv',index=False,encoding='utf-8-sig')
fig,axes=plt.subplots(1,2,figsize=(10.5,4.2));labels=['简单','中等','困难'];palette=['#85B5C8','#3D87A0','#205A78']
for ax,metric,title in [(axes[0],'B8L2_CA','B8L2 平均变化'),(axes[1],'fusion_turn_n_CA','有效转折平均变化')]:
    sub=c[c.metric==metric].set_index('context_value').loc[labels]
    ax.bar(labels,sub.image_mean,color=palette,width=.6);ax.axhline(0,color='#888',lw=.8)
    for i,(_,row) in enumerate(sub.iterrows()):ax.text(i,row.image_mean+max(sub.image_mean)*.035,f"{row.image_mean:+.2f}\n{int(row.positive_images)}/{int(row.valid_images)} 图增加",ha='center',fontsize=9)
    ax.set_ylim(0,max(sub.image_mean)*1.35);ax.set_title(title,fontsize=12);ax.grid(axis='y',alpha=.12)
fig.suptitle('TARGET K3 20/7 中结构→高结构：响应随既有难度改变',fontsize=14)
fig.text(.02,.01,'正式难度标签保持不变。三层分别 60、15、10 图；Q 正向与转折增加采用各自分母和方向。',fontsize=9)
fig.tight_layout(rect=[0,.06,1,.94])
for ext in ['png','svg']:fig.savefig(OUT/('FIG02_FROZEN_DIFFICULTY_RESPONSE.'+ext),dpi=180,bbox_inches='tight')
plt.close(fig)
print(json.dumps({'figures':2,'source_main_complete':True,'new_scores':0,'new_teams':0},ensure_ascii=False))
