"""Standalone scientific figures. Every point comes from delivered CSV files."""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':12,'axes.labelsize':11,
 'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white',
 'svg.fonttype':'none','axes.titleweight':'semibold'})
methods=['TARGET_DSTRUCT_K3','RFUSE_GEOM_K2','OPPJOINT_K3','OPPJOINT_K4']
labels=['DSTRUCT K3 / early C3','RFUSE K2 / early C2','JOINT K3 / early C3','JOINT K4 / early C4']
colors=['#126782','#D27A24','#496D43','#754C8D']

def save(fig,name):
 fig.savefig(OUT/(name+'.png'),dpi=220,bbox_inches='tight')
 fig.savefig(OUT/(name+'.svg'),bbox_inches='tight');plt.close(fig)

def main():
 c=pd.read_csv(OUT/'LANDMARK_COMPLETE_PATH_CURVE_SUMMARY.csv');c=c[c.anchor.eq(6)&c.min_arm_paths.eq(16)]
 named=pd.read_csv(OUT/'NAMED_MIXTURE_DIFFICULTY_SUMMARY.csv')
 named=named[named.min_arm_paths.eq(16)&named.method.eq('TARGET_DSTRUCT_K3')&named.metric.eq('Q_mean_complete_paths')]
 fig,axs=plt.subplots(1,2,figsize=(13.5,5.0),gridspec_kw={'width_ratios':[1.3,1]})
 for m,l,col in zip(methods,labels,colors):
  d=c[c.method.eq(m)&c.metric.eq('Q_complete')].sort_values('k');axs[0].plot(d.k,d.mean_image,label=l,color=col,lw=2.3)
 axs[0].axhline(0,color='#7B8793',lw=.8);axs[0].set(xlabel='People included in the saved random path',ylabel='Within-image mean Q difference (points)',xticks=[6,8,10,12,14,16,18,20],ylim=[0,4.0],title='A  Early class presence predicts a quality head start')
 axs[0].legend(frameon=False,loc='upper right',fontsize=9.3);axs[0].grid(axis='y',alpha=.18)
 diffs=['简单','中等','困难'];x=np.arange(3)
 for j,(cs,col,lab) in enumerate([('C2+C3','#126782','C2+C3 vs C1+C2'),('C1+C2+C3','#8FBAB9','C1+C2+C3 vs C1+C2')]):
  d=named[named.with_set.eq(cs)].set_index('difficulty').loc[diffs]
  bars=axs[1].bar(x+(j-.5)*.35,d.mean_image,.33,color=col,label=lab)
  for b,(_,r) in zip(bars,d.iterrows()):axs[1].text(b.get_x()+b.get_width()/2,b.get_height()+.055,f'{r.mean_image:.2f}\n({int(r.images)} images)',ha='center',fontsize=8.5)
 axs[1].set(xticks=x,xticklabels=['Easy','Medium','Hard'],ylabel='Mean Q difference across prefixes 6–20',ylim=[0,3.45],title='B  Named DSTRUCT mixtures: larger gains on hard images')
 axs[1].legend(frameon=False,fontsize=9,loc='upper left');axs[1].grid(axis='y',alpha=.16);axs[1].set_axisbelow(True)
 fig.suptitle('Current held-out-building classes on existing natural random paths',fontsize=15,fontweight='bold',y=1.03)
 fig.text(.02,-.06,'A: first 6 people contain the indicated class vs none; 185–194 paired images, 22 buildings. B: first-six class sets; ratios and identities vary.\nA: each group follows one fixed set of paths with Q at every prefix 6–20. Image-equal estimates. Final full-pool scores are identical; no new priority policy was tested.',fontsize=9,color='#465568')
 fig.tight_layout();save(fig,'FIG01_EARLY_QUALITY_AND_NAMED_MIXTURES')
 d=pd.read_csv(OUT/'LANDMARK_CURVE_DIFFICULTY_SUMMARY.csv');d=d[d.anchor.eq(6)&d.min_arm_paths.eq(16)&d.difficulty.eq('困难')]
 fig,axs=plt.subplots(1,2,figsize=(13.5,4.8),sharey=True)
 for ax,m,lab,col in zip(axs,['TARGET_DSTRUCT_K3','OPPJOINT_K4'],['DSTRUCT K3: early C3','JOINT K4: early C4'],[colors[0],colors[3]]):
  for metric,ls,mlab in [('ever_Q80','-','Reached Q ≥ 80 since n = 6'),('sustained_Q80_through20','--','Q ≥ 80 at every prefix from n to 20'),('ever_Q90',':','Reached Q ≥ 90 since n = 6')]:
   g=d[d.method.eq(m)&d.metric.eq(metric)].sort_values('k');ax.plot(g.k,100*g.mean_image,color=col,ls=ls,lw=2.5,label=mlab)
  ax.axhline(0,color='#7B8793',lw=.8);ax.grid(axis='y',alpha=.18);ax.set(xlabel='People included in the saved random path',xticks=[6,8,10,12,14,16,18,20],title=lab)
  ax.legend(frameon=False,fontsize=9,loc='upper right')
 axs[0].set_ylabel('Within-image probability difference (percentage points)')
 axs[0].set_ylim(-1,20.5)
 fig.suptitle('On hard images, an earlier target crossing and sustained quality are distinct',fontsize=15,fontweight='bold',y=1.03)
 fig.text(.02,-.06,'DSTRUCT: 34 images / 15 buildings. JOINT K4: 33 images / 15 buildings. Same first-six groups are followed through n = 20.\nAll registered paths stay in the probability denominator. Missing Q cannot certify a crossing. Q = 80 and 90 are parallel descriptive cutoffs, not official acceptance standards.',fontsize=9,color='#465568')
 fig.tight_layout();save(fig,'FIG02_FIRST_VS_SUSTAINED_TARGET_CROSSING')
 q=pd.read_csv(OUT/'K4_EARLY_QUALITY_ALL_SUPPORT_SUMMARY.csv');q=q[q.version.eq('manual_order_assisted')]
 t=pd.read_csv(OUT/'K4_EARLY_CURVE_SUMMARY.csv');t=t[t.version.eq('manual_order_assisted')&t.time_source.eq('user_processed_reported_not_raw_log_replayed')]
 pol=['higher_Q_first','more_turn_first','fast_first'];pl=['Higher historical Q','More turns','Faster history'];x=np.arange(3)
 fig,axs=plt.subplots(2,2,figsize=(13.5,9.0))
 for j,(metric,col,lab) in enumerate([('Q','#126782','Mean Q'),('Q_p10','#8FBAB9','10th percentile Q')]):
  g=q[q.metric.eq(metric)].set_index('policy').loc[pol]
  bars=axs[0,0].bar(x+(j-.5)*.34,g.mean_image,.32,label=lab,color=col)
  for b,v in zip(bars,g.mean_image):axs[0,0].text(b.get_x()+b.get_width()/2,v+(.12 if v>=0 else -.22),f'{v:+.2f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=9)
 axs[0,0].set(ylabel='Difference from natural order (Q points)',title='A  Overall early quality: 14 images / 8 buildings',ylim=[-3.8,9.6]);axs[0,0].legend(frameon=False,fontsize=9)
 for j,(metric,col,lab) in enumerate([('ever_Q80','#D27A24','Ever crossed Q ≥ 80'),('sustained_Q80_through_fullN','#E9B56D','Q ≥ 80 through full N')]):
  g=q[q.metric.eq(metric)].set_index('policy').loc[pol];v=100*g.mean_image
  bars=axs[0,1].bar(x+(j-.5)*.34,v,.32,label=lab,color=col)
  for b,vv in zip(bars,v):axs[0,1].text(b.get_x()+b.get_width()/2,vv+(.15 if vv>=0 else -.15),f'{vv:+.2f}',ha='center',va='bottom' if vv>=0 else 'top',fontsize=9)
 axs[0,1].set(ylabel='Mean early-prefix probability difference (pp)',title='B  Better mean Q does not imply universal earlier crossing',ylim=[-7.3,2.2]);axs[0,1].legend(frameon=False,fontsize=9)
 for ax,metric,title,ylab,col in [(axs[1,0],'recorded_seconds','C  Same-source labor support: 9 images / 5 buildings','Recorded labor difference at the same n (seconds)','#754C8D'),(axs[1,1],'Q','D  Quality on the identical 9-image labor support','Mean Q difference at the same n (points)','#496D43')]:
  g=t[t.metric.eq(metric)].set_index('policy').loc[pol];v=g.mean_image;bars=ax.bar(x,v,.55,color=col)
  for b,vv in zip(bars,v):ax.annotate(f'{vv:+.2f}',(b.get_x()+b.get_width()/2,vv),xytext=(0,5 if vv>=0 else -6),textcoords='offset points',ha='center',va='bottom' if vv>=0 else 'top',fontsize=10)
  ax.set(title=title,ylabel=ylab);ax.margins(y=.25)
 for ax in axs.flat:ax.set_xticks(x,pl,rotation=12);ax.axhline(0,color='#7B8793',lw=.8);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
 fig.suptitle('Existing JOINT K4 small-pool priority policies, with two actual assisted endpoints connected',fontsize=15,fontweight='bold',y=1.015)
 fig.text(.02,-.055,'Exact subset probabilities; no simulated or newly fused teams. Average prefixes 3 to N−1 within pool, then within image.\n15 eligible pools / 14 images, N ≤ 9. Panels C–D require all members to have positive records from one time source; this is a different, explicit support.\nThe two new Q values expand support; all 1,046 originally scoreable endpoint values remain unchanged. Full-N endpoint scores are identical across policies.',fontsize=9,color='#465568')
 fig.tight_layout();save(fig,'FIG03_EXISTING_K4_POLICY_SCOPE_AND_TRADEOFFS')
 print('Saved 3 PNG and 3 SVG scientific figures',flush=True)
if __name__=='__main__':main()
