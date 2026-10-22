"""Draw budget results and one exact near-mean G117 addition mechanism.

No new fusion/score.  Input states and scalars are frozen saved results.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_study_paths import WORK,CODE_ROOT,NATIVE,TAXONOMY,MECHANISMS,BUDGET,BUDGET_CASES,BUDGET_FINAL,FIGURES,ENGINE,REPO

from pathlib import Path
import sys,json,gzip
import numpy as np
import pandas as pd

P=BUDGET;M=MECHANISMS;F=BUDGET_FINAL;C=BUDGET_CASES
sys.path.insert(0,str(CODE_ROOT/'mechanisms'))
from render_case import draw,plt
OUT=FIGURES;OUT.mkdir(parents=True,exist_ok=True)
ORANGE='#ec6805';CYAN='#00aabe';BLUE='#276b91';RED='#b34c4c'

def g117():
 data=json.load(gzip.open(C/'G117_LOW_HIGH_REPLAY.json.gz','rt'))
 end=pd.read_csv(C/'G117_LOW_HIGH_ENDPOINTS.csv').set_index(['side','phase'])
 views=[]
 for side in 'ab':
  d={x['phase']:x for x in data if x['side']==side};before,after=[d[p] for p in ['before','after']]
  t0,t1=before['team'],after['team'];teams=[]
  for t,col,n in [(t0,ORANGE,10),(t1,CYAN,19)]:
   teams.append({k:t[k] for k in ['B8L2','D10','nodes']}|dict(points=t['geometry']['points'],
      footprint=t['geometry']['footprint'],color=col,
      label=f"{'橙' if n==10 else '青'} · n={n}：Q {t['B8L2']:.2f} / D10 {t['D10']:.2f} / 转折 {t['fusion_turn_n']}"))
  msg=('两处必要转折：5→8票、6→9票；阈值5→10\n全部原观察保留，新增支持未赶上门槛' if side=='a'
       else 'x908：6→8票未达10；另一身份组同时拆分\n新x890更接近参考，但未补偿必要转折遗漏')
  views.append(dict(image=t0['image'],image_id=t0['image_id'],photo=str(M/'photos'/(t0['image_id']+'.png')),
    reference=before['reference'],teams=teams,subtitle='固定原10人，追加相同9人',
    zoom=[900,963,304,352] if side=='a' else [855,956,318,369],zoom_title='局部：橙 n10 / 青 n19 / 黄参考',
    component_text=f"底点误差 {t0['S_bottom_deg']:.3f}→{t1['S_bottom_deg']:.3f}°\n正交方向残差 dir {t0['dir']:.3f}→{t1['dir']:.3f}°\n"+msg))
 case=dict(case_id='G117_low_high_fusion',title='G117｜人数10→19，局部支持上升仍丢掉必要转折',
    note='同9名背景成员加入两视角；M2:2 / M3:5 / M4:3 → M2:2 / M3:13 / M4:4。平均ΔQ −6.67，接近组均−6.94。',views=views)
 (C/(case['case_id']+'.json')).write_text(json.dumps(case,ensure_ascii=False,indent=2))
 print(draw(case,OUT))
 links=pd.read_csv(C/'G117_LOW_HIGH_WITHIN_VIEW_GROUP_LINKS.csv')
 chosen=[('a','node_007','node_007','necessary_turn_dilution'),
         ('a','node_008','node_008','necessary_turn_dilution'),
         ('b','node_009','node_007','necessary_turn_dilution'),
         ('b','node_001','node_001','identity_split_retained_branch'),
         ('b','node_001','node_005','identity_split_dropped_branch')]
 ledger=[]
 for side,b,a,mechanism in chosen:
  r=links[(links.side==side)&links.before_feature.eq(b)&links.after_feature.eq(a)].iloc[0].to_dict()
  old=set(r['before_members'].split('|'));new=set(r['after_members'].split('|'))
  r.update(mechanism=mechanism,threshold_before=5,threshold_after=10,
      retained_original_members='|'.join(sorted(old&new)),added_support_members='|'.join(sorted(new-old)),
      original_observations_moved_to_other_branch='|'.join(sorted(old-new)))
  ledger.append(r)
 pd.DataFrame(ledger).to_csv(C/'G117_LOW_HIGH_KEY_VOTE_LEDGER.csv',index=False)
 inp=end.reset_index()[[c for c in end.reset_index() if c in ['case_id','side','phase','image','image_id','pool_id','team_key','reference_id','reference_version','repository_commit','members','n','class_vector']]].copy()
 inp['state_file']='cases/G117_LOW_HIGH_REPLAY.json.gz'
 inp['raw_vote_file']='cases/G117_LOW_HIGH_VOTE_OBSERVATIONS.csv'
 inp['source']='saved native endpoints; four full-state explanatory replays; exact score agreement'
 inp.to_csv(C/'G117_LOW_HIGH_INPUT_INDEX.csv',index=False)

def budget():
 b=pd.read_csv(F/'BUDGET_SUMMARY.csv').set_index('budget').loc[['low_third','mid_half','mid_plus_one','high_two_thirds']]
 a=pd.read_csv(F/'ADDITION_GROUP.csv');a=a[a.transition.eq('low_third__high_two_thirds')].sort_values('Q_delta_mean')
 p=pd.read_csv(F/'SINGLE_ADDITION_PARITY_SUMMARY.csv').set_index('parity_step')
 fig=plt.figure(figsize=(15,10.8));gs=fig.add_gridspec(3,2,width_ratios=[1.05,1],hspace=.55,wspace=.30)
 ax=fig.add_subplot(gs[0,0]);x=np.arange(4)
 ax.plot(x,b.B8L2_mean,'o-',color=BLUE,label='B8L2');ax.plot(x,b.D10_mean,'s-',color=CYAN,label='D10')
 ax.set_xticks(x,[f'{n}\n平均n={v:.1f}' for n,v in zip(['约1/3','约1/2','中位+1','约2/3'],b.n)])
 ax.set_ylim(83.9,87.4);ax.set_ylabel('质量均值');ax.legend(frameon=False,ncol=2,fontsize=9)
 ax.set_title('完整性改善，平均质量收益较小',loc='left',fontsize=12)
 for i,q in enumerate(b.B8L2_mean):ax.text(i,q-.28,f'{q:.2f}',ha='center',fontsize=9,color=BLUE)
 ax.spines[['top','right']].set_visible(False)
 ax=fig.add_subplot(gs[1,0])
 for field,label,color in [('Q_lt80','Q<80（可评分）',BLUE),('Q_lt70','Q<70（可评分）',RED),('failure_rate','失败/不完整',ORANGE)]:
  ax.plot(x,100*b[field],'o-',color=color,label=label)
 ax.set_xticks(x,['约1/3','约1/2','中位+1','约2/3']);ax.set_ylabel('比例 %');ax.set_ylim(0,31)
 ax.legend(frameon=False,ncol=2,fontsize=8.6,loc='upper right');ax.spines[['top','right']].set_visible(False)
 ax.set_title('Q<80减少，但较严重低尾未同步改善',loc='left',fontsize=12)
 ax=fig.add_subplot(gs[2,0]);par=['even_to_odd','odd_to_even'];pos=np.arange(2)
 ax.barh(pos-.15,100*p.loc[par,'fusion_turn_n_increase'],height=.29,color=CYAN,label='有效转折增加')
 ax.barh(pos+.15,100*p.loc[par,'fusion_turn_n_decrease'],height=.29,color=ORANGE,label='有效转折减少')
 ax.set_yticks(pos,['偶→奇：门槛+1','奇→偶：门槛不变']);ax.invert_yaxis();ax.set_xlim(0,15)
 ax.set_xlabel('单次实际加1人的结构变化比例 %');ax.legend(frameon=False,ncol=2,fontsize=9,loc='lower right')
 ax.set_title('mid→mid+1：人数奇偶影响结构门槛',loc='left',fontsize=12)
 ax.spines[['top','right']].set_visible(False)
 for i,k in enumerate(par):
  for dy,field in [(-.15,'fusion_turn_n_increase'),(.15,'fusion_turn_n_decrease')]:
   v=100*p.loc[k,field];ax.text(v+.15,i+dy,f'{v:.2f}',va='center',fontsize=8.5)
 ax=fig.add_subplot(gs[:,1]);pos=np.arange(len(a));col=[BLUE if q>0 else RED for q in a.Q_delta_mean]
 ax.barh(pos,a.Q_delta_mean,color=col,height=.65);ax.axvline(0,color='#667085',lw=.8)
 labels=[]
 for _,r in a.iterrows():
  labels.append(f"{r.group_id}（{int(r.n_direct_pairs)}对）")
 ax.set_yticks(pos,labels);ax.invert_yaxis();ax.set_xlim(-8.7,7.7)
 for i,(_,r) in enumerate(a.iterrows()):
  v=r.Q_delta_mean;ax.text(v+(.12 if v>=0 else -.12),i,f'{v:+.2f}',ha='left' if v>=0 else 'right',va='center',fontsize=9)
 ax.set_xlabel('约1/3 → 约2/3 的 ΔB8L2');ax.set_title('17个采用声明组中，13组均值上升',loc='left',fontsize=12)
 ax.spines[['top','right']].set_visible(False)
 fig.suptitle('固定候选成员、只扩展共同背景：增人收益与结构门槛',fontsize=17,y=.985)
 fig.text(.5,.045,'普通Manual；复0；118个直接图对、59图、11建筑。低→高实际增人117对。声明组允许重叠。',ha='center',fontsize=10)
 fig.text(.5,.022,'主汇总按面板内成员集合→图对→采用声明组→建筑等权；失败不填0；图中预算均值与配对ΔQ使用各自明确支持。',ha='center',fontsize=9,color='#475467')
 fig.subplots_adjust(top=.92,bottom=.12);path=OUT/'budget_and_parity_overview.png';fig.savefig(path,dpi=160);plt.close(fig);print(path)

if __name__=='__main__':
 g117();budget()
