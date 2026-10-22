"""Exact G015 composition/member response from saved paired native endpoints."""
from pathlib import Path
import argparse, json, gzip, os
os.environ.setdefault("MPLCONFIGDIR","/tmp/hohonet_mpl")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

p=argparse.ArgumentParser();p.add_argument('--responses',type=Path,required=True);p.add_argument('--design',type=Path,required=True);p.add_argument('--repo',type=Path);p.add_argument('--native-scalars',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--font',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
font=FontProperties(fname=a.font)
plt.rcParams.update({'font.family':font.get_name(),'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','figure.facecolor':'white','axes.labelcolor':'#273442','text.color':'#273442','axes.unicode_minus':False})
from matplotlib import font_manager
font_manager.fontManager.addfont(a.font)
meta=pd.read_csv(a.design/'PANELS.csv');meta=meta[meta.groups=='G015']
r=pd.read_csv(a.responses,low_memory=False);r=r[r.panel_id.isin(meta.panel_id)].merge(meta,on='panel_id',how='left')
if a.native_scalars:
 native=pd.read_csv(a.native_scalars,usecols=['team_key','member_object_ids']).set_index('team_key');object_map=native.member_object_ids.to_dict()
else:
 if a.repo is None:raise ValueError('Provide --native-scalars or --repo for exact source object identifiers')
 with gzip.open(a.repo/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz','rt') as f:snapshot=json.load(f)
 poolmap={p['pool_id']:{q['worker_id']:q['object_id'] for q in p['records']} for p in snapshot['images']}
for view in ['a','b']:
 r['member_object_ids_'+view]=r['team_key_'+view].map(object_map) if a.native_scalars else r.apply(lambda z:'|'.join(poolmap[z['pool_id_'+view]][w] for w in z.member_set_key.split('|')),axis=1)
 r['composition_mean_B8L2_'+view]=r.groupby(['panel_id','structure_vector'])['B8L2_'+view].transform('mean')
 r['composition_n_B8L2_'+view]=r.groupby(['panel_id','structure_vector'])['B8L2_'+view].transform('count')
 r['member_residual_B8L2_'+view]=r['B8L2_'+view]-r['composition_mean_B8L2_'+view]
 r['recorded_time_total_seconds_'+view]=np.exp(r['log_recorded_time_'+view])
r['source_composition_prediction_b_from_a']=r.composition_mean_B8L2_a
r['source_composition_prediction_a_from_b']=r.composition_mean_B8L2_b
r['prediction_information']='source_view_GT_and_complete_source_panel; target_view_for_evaluation_only'
r.to_csv(a.out/'CASE_G015_COMPOSITION_MEMBERS.csv',index=False)
summary=[]
for pid,z in r.groupby('panel_id'):
 ma=z.iloc[0];q=z.groupby('hi_selected')[['B8L2_a','B8L2_b']].mean()
 summary.append(dict(panel_id=pid,n=ma.n,replicate=ma.replicate,core=ma.core,lo_candidates=ma.lo_candidates,hi_candidates=ma.hi_candidates,
  composition_rho=np.corrcoef(z.composition_mean_B8L2_a,z.composition_mean_B8L2_b)[0,1],member_residual_rho=np.corrcoef(z.member_residual_B8L2_a,z.member_residual_B8L2_b)[0,1],
  pure_hi_minus_pure_lo_a=q.B8L2_a.iloc[-1]-q.B8L2_a.iloc[0],pure_hi_minus_pure_lo_b=q.B8L2_b.iloc[-1]-q.B8L2_b.iloc[0]))
pd.DataFrame(summary).to_csv(a.out/'CASE_G015_PANEL_SUMMARY.csv',index=False)
C=['#236E9A','#C8623A'];z=r[(r.n==7)&(r.replicate==0)].copy();q=z.groupby('hi_selected')[['B8L2_a','B8L2_b']].mean()
fig,axes=plt.subplots(2,2,figsize=(13.5,9.4));fig.subplots_adjust(top=.85,bottom=.13,left=.08,right=.96,hspace=.38,wspace=.27)
fig.suptitle('G015：配比作用可以跨视角重复，具体成员的作用仍会反向',fontsize=17,x=.08,ha='left',y=.965)
fig.text(.08,.916,'当前楼外结构类 M2 → M3；7y3-11 / 7y3-19；固定评分和各自参考。每个面板完整枚举 6 选 3 的 20 队。',fontsize=10.5)
ax=axes[0,0]
for v,col,label,off in [('a',C[0],'7y3-11',-.055),('b',C[1],'7y3-19',.055)]:
 for count,g in z.groupby('hi_selected'):
  jit=np.linspace(-.10,.10,len(g)) if len(g)>1 else np.array([0.])
  ax.scatter(count+jit+off,g['B8L2_'+v],s=20,color=col,alpha=.35,zorder=2)
 ax.plot(q.index,q['B8L2_'+v],'-o',lw=2.3,color=col,label=label,zorder=3)
ax.set(title='A  n7：同配比均值同向，个别团队仍分散',xlabel='7 人队中 M3 人数（其余均为 M2）',ylabel='B8L2');ax.set_xticks(range(4));ax.set_ylim(78,101);ax.legend(frameon=False,loc='lower right');ax.text(.02,.95,'配比均值相关 r = 0.996',transform=ax.transAxes,va='top',fontsize=10.5);ax.grid(axis='y',alpha=.18)
ax=axes[0,1]
palette={0:'#A3B1BA',1:'#5675B9',2:'#B37B35',3:'#6E9D80'}
for count,g in z.groupby('hi_selected'):
 ax.scatter(g.member_residual_B8L2_a,g.member_residual_B8L2_b,s=42,c=palette[count],label=f'{count} 名 M3',alpha=.9,edgecolor='white',linewidth=.5)
ax.axhline(0,color='#B5BCC4',lw=.8);ax.axvline(0,color='#B5BCC4',lw=.8);ax.set(title='B  n7：扣除配比均值后，成员残差反向',xlabel='7y3-11：团队 Q − 同配比均值',ylabel='7y3-19：团队 Q − 同配比均值');ax.text(.02,.04,'同配比成员残差 r = −0.785',transform=ax.transAxes,fontsize=10.5)
for sel,xytext in [('W104|W122|W128',(12,-12)),('W120|W122|W128',(-80,-18))]:
 rr=z[z.selected==sel].iloc[0];ax.annotate(sel.replace('|',' / '),(rr.member_residual_B8L2_a,rr.member_residual_B8L2_b),xytext=xytext,textcoords='offset points',fontsize=8.5)
ax.legend(frameon=False,ncol=2,loc='upper right',fontsize=8)
ax=axes[1,0];ss=pd.DataFrame(summary);ss=ss[ss.replicate==0].sort_values('n')
for v,col,label in [('a',C[0],'7y3-11'),('b',C[1],'7y3-19')]:
 ax.plot(ss.n,ss['pure_hi_minus_pure_lo_'+v],'-o',lw=2,color=col,label=label)
ax.axhline(0,color='#A4ADB5',lw=.8);ax.set(title='C  同一候选块、逐步增大固定核心',xlabel='团队人数 n',ylabel='全 3 名 M3 − 全 3 名 M2 的 Q 差');ax.set_xticks(ss.n);ax.grid(axis='y',alpha=.18);ax.text(.02,.94,'所有队在两视角分别保持 4 / 8 个转折',transform=ax.transAxes,va='top',fontsize=9);ax.legend(frameon=False)
ax=axes[1,1]
for rep,marker,alpha in [(0,'o',.8),(1,'s',.9)]:
 zz=r[(r.n==10)&(r.replicate==rep)].copy()
 ax.scatter(zz.member_residual_B8L2_a,zz.member_residual_B8L2_b,s=35,marker=marker,color=['#526B8A','#B55262'][rep],alpha=alpha,label=f'成员面板 {rep}：r = '+f'{np.corrcoef(zz.member_residual_B8L2_a,zz.member_residual_B8L2_b)[0,1]:.3f}')
ax.axhline(0,color='#B5BCC4',lw=.8);ax.axvline(0,color='#B5BCC4',lw=.8);ax.set(title='D  n10：配比相同，换核心与低类候选',xlabel='7y3-11：同配比成员残差',ylabel='7y3-19：同配比成员残差');ax.legend(frameon=False,fontsize=9,loc='lower left')
fig.text(.08,.065,'n7 固定核心：W110 / W113 / W118 / W119；M2 候选：W104 / W120 / W128；M3 候选：W109 / W112 / W122。',fontsize=9)
fig.text(.08,.038,'一个同类替换：W104 → W120（均为当前 M2，联合类也相同），固定其余 6 人，Q 在两个视角分别 +8.015 / −16.191。',fontsize=9)
fig.savefig(a.out/'CASE_G015_COMPOSITION_MEMBERS.png',dpi=180)
fig.savefig(a.out/'CASE_G015_COMPOSITION_MEMBERS.svg')
print('saved',len(r),'team-pair rows')
