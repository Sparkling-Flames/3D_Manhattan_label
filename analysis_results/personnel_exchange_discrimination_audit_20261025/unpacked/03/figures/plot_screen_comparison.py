#!/usr/bin/env python3
"""Export all-candidate scientific plots from saved screen summaries only.
No fusion, classification refit or outcome-driven filtering occurs here.
"""
from pathlib import Path
import argparse,hashlib,io,json,os
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(OUT/'.mpl')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import colors,font_manager
from matplotlib.patches import Rectangle,Patch
from matplotlib.lines import Line2D
from PIL import Image
METHODS=[
'DSTRUCT_AXIS2','DSTRUCT_K2','DSTRUCT_K3','DSTRUCT_K4',
'DBOUNDARY_AXIS2','DBOUNDARY_K2','DBOUNDARY_K3','DBOUNDARY_K4',
'DJOINT_K2','DJOINT_K3','DJOINT_K4',
'MSDGEOM_K2','MSDGEOM_K3','MSDGEOM_K4',
'MSDGEOM_SCOPE_AXIS2','MSDGEOM_SCOPE_K2','MSDGEOM_SCOPE_K3','MSDGEOM_SCOPE_K4',
'Q_MEDIAN2','Q_HARD_MEDIAN2',
'V3_BEHAVIOR_coarse','V3_BEHAVIOR_fine','V3_JOINT_QT_coarse','V3_JOINT_QT_fine',
'XCOND_GEOM_coarse','XCOND_GEOM_QT_coarse','XCOND_PAIRED_coarse']
NMS=[(10,7),(12,8),(12,10),(14,9),(16,8),(17,9),(18,7),(20,6),(24,5)]
GROUPS=[(0,4,'难度结构'),(4,8,'难度边界'),(8,11,'难度结构＋Q/T'),(11,14,'Manual＋Semi'),(14,18,'跨条件＋scope'),(18,20,'历史 Q 阈值对照'),(20,24,'既有结构／联合'),(24,27,'既有跨条件')]
CAPTIONS={}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def savefig(fig,name):
 for fmt in ['png','svg']:
  stream=io.BytesIO();fig.savefig(stream,format=fmt,dpi=180,facecolor='white',bbox_inches='tight',pad_inches=.14)
  raw=stream.getvalue()
  if fmt=='png':Image.open(io.BytesIO(raw)).verify()
  p=OUT/(name+'.'+fmt);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_bytes(raw);tmp.replace(p)
 plt.close(fig)

def configure_font():
 p=OUT/'fonts/NotoSansCJKsc-Subset.otf'
 if not p.exists():p=OUT/'fonts/NotoSansCJKsc-Regular.otf'
 if not p.exists():raise FileNotFoundError('Install Noto Sans CJK SC or place font at figures/fonts; see FONT_SOURCE.json')
 font_manager.fontManager.addfont(p);name=font_manager.FontProperties(fname=p).get_name()
 plt.rcParams.update({'font.family':name,'font.size':10,'axes.titlesize':12,'axes.unicode_minus':False,'svg.fonttype':'path','axes.spines.top':False,'axes.spines.right':False})
 return p

def heatmaps(summary,capacity,phase):
 assert set(summary.method.unique())==set(METHODS)
 capacity=capacity.loc[capacity.phase.eq(phase)]
 cells=[]
 for metric,stem,title,unit,digits in [
  ('B8L2','01_Q_GAP_ALL_METHODS','同类与跨类替换的 Q 幅度区分','Q 分',2),
  ('geometry_bev_distance','02_BEV_SHAPE_GAP_ALL_METHODS','同类与跨类替换的融合底面形状区分','1−BEV IoU',3)]:
  f=summary.loc[summary.metric.eq(metric)];assert not f.duplicated(['method','n','m']).any();lookup={(r.method,int(r.n),int(r.m)):r for r in f.itertuples()}
  vals=np.full((len(METHODS),len(NMS)),np.nan);nvalid=np.zeros_like(vals);states={}
  for i,meth in enumerate(METHODS):
   for j,(n,m) in enumerate(NMS):
    r=lookup.get((meth,n,m));cc=capacity.loc[capacity.method.eq(meth)&capacity.n.eq(n)&capacity.m.eq(m)];feasible=cc.loc[cc.feasible.eq(True)]
    status='available' if r is not None and r.valid_images>0 and pd.notna(r.gap_image_equal) else 'not_evaluable' if r is not None else 'no_capacity' if len(feasible)==0 else 'not_aggregated'
    states[(i,j)]=status
    if status=='available':vals[i,j]=r.gap_image_equal;nvalid[i,j]=r.valid_images
    cells.append({'metric':metric,'method':meth,'n':n,'m':m,'status':status,'gap_image_equal':vals[i,j],'valid_images':int(nvalid[i,j]),'attempted_images':getattr(r,'attempted_images',0),'feasible_images':feasible.image.nunique(),'feasible_directions':len(feasible),'positive_images':getattr(r,'gap_positive_images',np.nan),'within_image_equal':getattr(r,'within_image_equal',np.nan),'cross_image_equal':getattr(r,'cross_image_equal',np.nan)})
  vmax=float(np.nanmax(np.abs(vals)));norm=colors.TwoSlopeNorm(vmin=-vmax,vcenter=0,vmax=vmax)
  cmap=colors.LinearSegmentedColormap.from_list('gap',['#175882','#f7f7f4','#be482f'])
  fig=plt.figure(figsize=(17.8,18.2));ax=fig.add_axes([.33,.12,.57,.78]);im=ax.imshow(vals,cmap=cmap,norm=norm,aspect='auto',interpolation='nearest')
  ax.set_xticks(range(len(NMS)),[f'n={n}\nm={m}（{m/n:.0%}）'for n,m in NMS],fontsize=10);ax.xaxis.tick_top();ax.tick_params(axis='x',length=0,pad=10)
  ax.set_yticks(range(len(METHODS)),METHODS,fontsize=10);ax.tick_params(axis='y',length=0,pad=10)
  for (i,j),status in states.items():
   if status=='available':
    val=vals[i,j];rgba=cmap(norm(val));luminance=.2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2];color='white'if luminance<.50 else'#1c2732'
    ax.text(j,i-.10,f'{val:+.{digits}f}',ha='center',va='center',fontsize=9.4,color=color)
    ax.text(j,i+.22,f'{int(nvalid[i,j])} 图',ha='center',va='center',fontsize=7.7,color=color,alpha=.95)
   else:
    color={'no_capacity':'#e4e7e9','not_evaluable':'#d1cadf','not_aggregated':'#fff0cc'}[status];hatch={'no_capacity':'','not_evaluable':'///','not_aggregated':'...'}[status]
    ax.add_patch(Rectangle((j-.5,i-.5),1,1,facecolor=color,edgecolor='#b7bec5',lw=.3,hatch=hatch))
    ax.text(j,i,{'no_capacity':'无容量','not_evaluable':'无可评','not_aggregated':'未汇总'}[status],ha='center',va='center',fontsize=8.2,color='#65707a')
  ax.set_xticks(np.arange(-.5,len(NMS),1),minor=True);ax.set_yticks(np.arange(-.5,len(METHODS),1),minor=True);ax.grid(which='minor',color='white',lw=.8);ax.tick_params(which='minor',length=0)
  for start,end,label in GROUPS:
   if start:ax.axhline(start-.5,c='#88939d',lw=1.2)
   ypos=.12+.78*(1-(start+end)/(2*len(METHODS)));fig.text(.035,ypos,label,ha='left',va='center',fontsize=11,color='#394b59')
  cb=fig.colorbar(im,cax=fig.add_axes([.915,.20,.018,.62]));cb.set_label('跨类幅度 − 同类幅度（'+unit+'）',labelpad=12,fontsize=11)
  available=sum(v=='available'for v in states.values());missing=sum(v=='no_capacity'for v in states.values());unsc=sum(v=='not_evaluable'for v in states.values())
  fig.suptitle(title+'｜完整探索比较',x=.035,ha='left',y=.982,fontsize=20)
  fig.text(.035,.951,f'Manual；真实 v2；27 个方法／层级实例 × 9 个 n/m；{available} 格有可评量，{missing} 格无严格 ABC 容量，{unsc} 格无可评量。',fontsize=11.2)
  fig.text(.035,.071,'同类 = d(A,B)；跨类 = [d(A,C)+d(B,C)]/2。各队的图片、总人数、共同背景及实际换人数均相同。',fontsize=11)
  fig.text(.035,.048,'正值表示跨类更不同，不表示质量更好。格内为图等权均值差和该指标实际可评图片数；负向格全部保留。',fontsize=11)
  fig.text(.035,.025,'不同方法／规模的可行图片并不完全相同；该图呈现全部候选，不将其当作共同图片下的优劣排名。',fontsize=11,color='#4d5964')
  savefig(fig,stem)
  CAPTIONS[stem]=dict(title=title,metric=metric,available_cells=available,no_capacity_cells=missing,not_evaluable_cells=unsc,zero_fill_missing=False,definition='distance cross mean minus within, then saved hierarchical image-equal aggregation',source='analysis/'+phase+'/METHOD_N_M_COMPARISON.csv')
 pd.DataFrame(cells).to_csv(OUT/'HEATMAP_CELL_DATA.csv',index=False)

def difficulty_plot(diff,pool,phase):
 selected=[('DSTRUCT_K3',10,7,'新难度结构三类'),('V3_BEHAVIOR_coarse',12,8,'既有结构粗类'),('Q_MEDIAN2',12,8,'历史 Q 中位数二分')];order=['简单','中等','困难'];fig,axs=plt.subplots(1,3,figsize=(17.7,7),sharey=True);fig.subplots_adjust(left=.065,right=.985,bottom=.25,top=.77,wspace=.15);data=[]
 sub=pool.loc[pool.phase.eq(phase)];allvals=[]
 for method,n,m,_ in selected:
  z=sub.loc[sub.method.eq(method)&sub.n.eq(n)&sub.m.eq(m)];allvals.extend(z.B8L2_within.dropna());allvals.extend(z.B8L2_cross.dropna())
 ymax=max(allvals)*1.13; rng=np.random.default_rng(20261025)
 for ax,(method,n,m,label) in zip(axs,selected):
  df=diff.loc[diff.method.eq(method)&diff.n.eq(n)&diff.m.eq(m)&diff.metric.eq('B8L2')].set_index('difficulty')
  pp=sub.loc[sub.method.eq(method)&sub.n.eq(n)&sub.m.eq(m)]
  for j,difficulty in enumerate(order):
   if difficulty not in df.index:continue
   r=df.loc[difficulty];data.append(r.to_dict()|{'method':method,'n':n,'m':m,'difficulty':difficulty})
   p=pp.loc[pp.difficulty.eq(difficulty)].dropna(subset=['B8L2_within','B8L2_cross']);jit=rng.uniform(-.035,.035,len(p))
   for offset,field,color in [(-.18,'within','#337c9b'),(.18,'cross','#d36740')]:
    ax.bar(j+offset,r[field+'_image_equal'],width=.30,color=color,alpha=.88,zorder=2)
    ax.scatter(j+offset+jit,p['B8L2_'+field],s=14,facecolor='white',edgecolor=color,linewidth=.6,alpha=.8,zorder=3)
    ax.text(j+offset,r[field+'_image_equal']+.9,f'{r[field+"_image_equal"]:.2f}',ha='center',va='bottom',fontsize=10,color='#25313b',bbox={'facecolor':'white','alpha':.65,'edgecolor':'none','pad':.6})
   ax.text(j,-ymax*.09,f'跨>同 {int(r.gap_positive_images)}/{int(r.valid_images)} 图\n{int(r.gap_positive_buildings)}/{int(r.valid_buildings)} 楼',ha='center',va='top',fontsize=10)
  ax.set_xticks(range(3),order,fontsize=12);ax.set_ylim(0,ymax);ax.set_title(label+'\n'+method+f'；n={n}，m={m}',fontsize=12,pad=16);ax.set_axisbelow(True);ax.grid(axis='y',color='#d8dee3',alpha=.7);ax.tick_params(axis='y',length=0)
 axs[0].set_ylabel('绝对 Q 变化（B8L2 分）',fontsize=12)
 fig.suptitle('难度怎样改变同类／跨类大块替换的幅度？',x=.065,ha='left',y=.975,fontsize=21)
 fig.legend(handles=[Patch(facecolor='#337c9b',label='同类 |B−A|'),Patch(facecolor='#d36740',label='对称跨类（|C−A|+|C−B|）/2'),Line2D([0],[0],marker='o',lw=0,markerfacecolor='white',markeredgecolor='#65707a',label='每张图的已聚合结果')],loc='upper left',bbox_to_anchor=(.06,.92),ncol=3,frameon=False,fontsize=11)
 fig.text(.065,.055,'探索样本；柱为图等权均值，点保留图片间差异。分母是各方法、规模、难度的实际可评图片／建筑；非共同图片排名。',fontsize=11)
 fig.text(.065,.025,'下方“跨>同”只表示幅度关系，不表示跨类升质。困难图支持量较小，原有难度标签不作重新归类。',fontsize=11,color='#4d5964')
 savefig(fig,'03_DIFFICULTY_WITHIN_CROSS_Q');pd.DataFrame(data).to_csv(OUT/'DIFFICULTY_PLOT_DATA.csv',index=False)
 CAPTIONS['03_DIFFICULTY_WITHIN_CROSS_Q']=dict(title='难度与同类／跨类变化',sample='screen exploratory',units='absolute B8L2 points',points='individual image-level hierarchical means',source='analysis/'+phase+'/DIFFICULTY_COMPARISON.csv')

def explanation_plot():
 features=pd.read_csv(ROOT/'features/HISTORY_FEATURES_ALL_LOBO.csv.gz');features=features.loc[features.heldout_building.eq('ALL')]
 labels=pd.read_csv(ROOT/'classifications/NEW_METHOD_LABELS_ALL.csv');labels=labels.loc[labels.method.eq('DSTRUCT_K3')]
 cols=['worker_id','heldout_building','m_hard_turn_n','m_hard_short_turn_edges','m_hard_near_straight_nodes_5deg','m_hard_matched_top_bias_deg','m_hard_matched_bottom_bias_deg','m_hard_images','m_hard_buildings','m_all_images','m_all_buildings']
 d=labels[['worker_id','class_id','known','missing_reason','origin']].merge(features[cols],on='worker_id',how='left',validate='one_to_one');d.to_csv(OUT/'DSTRUCT_K3_ALL_PERSON_FEATURES.csv',index=False)
 z=d.loc[d.known.eq(True)];centers=z.groupby('class_id')[cols[2:]].mean();centers['people']=z.groupby('class_id').size();centers.to_csv(OUT/'DSTRUCT_K3_ALL_CLASS_CENTERS.csv')
 defs=pd.read_csv(ROOT/'classifications/NEW_CLASS_DEFINITIONS_ALL.csv').query("method=='DSTRUCT_K3'").set_index('class_id')
 for k in ['m_hard_turn_n','m_hard_near_straight_nodes_5deg','m_hard_matched_top_bias_deg','m_hard_matched_bottom_bias_deg']:assert np.max(abs(centers[k]-defs[k]))<1e-9
 roles={'C1':'转折较少／冗余较多','C2':'常规／较简化表达','C3':'困难结构保留较多'};cc={'C1':'#b65770','C2':'#397c9f','C3':'#2b9072'};classes=['C1','C2','C3']
 fig,axs=plt.subplots(1,3,figsize=(17.5,7.8));fig.subplots_adjust(left=.065,right=.985,top=.76,bottom=.26,wspace=.24);rng=np.random.default_rng(9)
 for ax,col,title,ylabel in [
  (axs[0],'m_hard_turn_n','困难图的非冗余转折表达','相对同图中位数的转折差'),
  (axs[1],'m_hard_near_straight_nodes_5deg','困难图的近共线冗余表达','相对同图中位数的冗余点差')]:
  for j,cl in enumerate(classes):
   values=z.loc[z.class_id.eq(cl),col].dropna();ax.scatter(j+rng.uniform(-.16,.16,len(values)),values,c=cc[cl],s=24,alpha=.65,edgecolor='white',linewidth=.3)
   mean=values.mean();ax.plot([j-.22,j+.22],[mean,mean],color='#192c3c',lw=3);ax.text(j+.25,mean,f'{mean:+.3f}',va='center',fontsize=10,fontweight='bold')
  ax.axhline(0,c='#8e9aa4',lw=1,ls=':');ax.set_xticks(range(3),[f'{cl}\n{int(centers.loc[cl,"people"])} 人'for cl in classes]);ax.set_ylabel(ylabel);ax.set_title(title,pad=14);ax.grid(axis='y',alpha=.2);ax.set_xlim(-.5,2.9)
 ax=axs[2]
 for off,k,col,lbl in [(-.16,'m_hard_matched_top_bias_deg','#8359a1','顶界'),(.16,'m_hard_matched_bottom_bias_deg','#d19a43','底界')]:
  vals=[centers.loc[c,k]for c in classes];ax.bar(np.arange(3)+off,vals,width=.28,color=col,alpha=.85,label=lbl)
  for j,val in enumerate(vals):ax.text(j+off,val+(.018 if val>=0 else-.018),f'{val:+.3f}',ha='center',va='bottom'if val>=0 else'top',fontsize=9)
 ax.axhline(0,c='#8e9aa4',lw=1,ls=':');ax.set_xticks(range(3),[f'{cl}\n{int(centers.loc[cl,"people"])} 人'for cl in classes]);ax.set_ylabel('历史有符号偏移的同图相对值（度）');ax.set_title('上下界：解释变量，未作为本分类输入',pad=14);ax.set_ylim(-.34,.38);ax.legend(frameon=False,ncol=2,loc='upper right');ax.grid(axis='y',alpha=.2)
 fig.suptitle('DSTRUCT_K3：全数据描述标签对应怎样的历史标法？',x=.065,ha='left',y=.975,fontsize=21)
 fig.text(.065,.917,'C1：转折较少、冗余较多（8 人）　　C2：常规／较简化表达（39 人）　　C3：困难结构保留较多（12 人）',fontsize=12)
 fig.text(.065,.867,'点 = 实际人员；短横线 = 类内人员均值。类别仅由 Manual 结构水平及简单／困难响应形成，未用 Q/T 或边界位置建类。',fontsize=11)
 fig.text(.065,.15,'这些是人员历史中“相对同图、同条件中位数”的差值，再先按建筑均值、后按人员汇总；不是原始角点数。',fontsize=11)
 fig.text(.065,.112,'上下界正值表示相对同图人员更向 ERP 下方偏移；不等同绝对偏差或正确率。非冗余转折与近共线点分别保留。',fontsize=11)
 fig.text(.065,.074,'ALL 仅用于描述 59 名有支持人员；W019、W022、W026 因历史几何支持不足保留未知。替换实验使用相应建筑外标签。',fontsize=11,color='#4d5964')
 savefig(fig,'04_DSTRUCT_K3_ALL_FEATURES')
 CAPTIONS['04_DSTRUCT_K3_ALL_FEATURES']=dict(title='ALL DSTRUCT_K3 历史特征解释',label_stage='ALL descriptive only',known_people=59,unknown_people=3,feature_units='image-condition peer-median residuals, building-equal within worker',formation_inputs='Manual structure level and difficulty-conditioned structure, not Q/T or position',comparison_columns=list(centers.columns))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--analysis',type=Path,default=ROOT/'analysis/screen');ap.add_argument('--design',type=Path,default=ROOT/'design/screen');ap.add_argument('--phase',default='screen');a=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True);font=configure_font()
 paths=[a.analysis/'METHOD_N_M_COMPARISON.csv',a.analysis/'DIFFICULTY_COMPARISON.csv',a.analysis/'POOL_METHOD_N_M_SUMMARY.csv.gz',a.design/'CAPACITY_AND_ATTEMPTS.csv.gz']
 s=pd.read_csv(paths[0]);s=s.loc[s.phase.eq(a.phase)];d=pd.read_csv(paths[1]);d=d.loc[d.phase.eq(a.phase)];p=pd.read_csv(paths[2],low_memory=False);c=pd.read_csv(paths[3],low_memory=False)
 heatmaps(s,c,a.phase);difficulty_plot(d,p,a.phase);explanation_plot()
 (OUT/'FIGURE_CAPTIONS.json').write_text(json.dumps(CAPTIONS,ensure_ascii=False,indent=2))
 paths += [ROOT/'features/HISTORY_FEATURES_ALL_LOBO.csv.gz',ROOT/'classifications/NEW_METHOD_LABELS_ALL.csv',ROOT/'classifications/NEW_CLASS_DEFINITIONS_ALL.csv']
 inputs=[dict(path=str(x.relative_to(ROOT)),sha256=sha(x))for x in paths];(OUT/'PROVENANCE.json').write_text(json.dumps({'data':'v2','source_commit':'972857b2b3f548316be215400e42d6ef6e639250','stage':a.phase,'inputs':inputs,'plot_code_sha256':sha(__file__),'font':str(font.relative_to(OUT)),'no_new_fusion':True,'all_candidates_retained':True},ensure_ascii=False,indent=2))
 print('Saved four PNG/SVG figures, exact plotting tables and captions',flush=True)
if __name__=='__main__':main()
