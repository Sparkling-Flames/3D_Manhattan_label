"""Numeric figures; call from a visible Python plotting tool or local Python."""
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_prepare import O
import pandas as pd,numpy as np,json

def make_figures(show=False):
 import matplotlib.pyplot as plt
 out=O/'figures';out.mkdir(exist_ok=True);inventory=[]
 def save(fig,name,caption,display=False):
  fig.tight_layout();fig.savefig(out/(name+'.png'),dpi=170);inventory.append(dict(file=name+'.png',caption_zh=caption))
  if show and display:plt.show()
  plt.close(fig)
 s=pd.read_csv(O/'results/all_candidate_scores.csv');c=pd.read_csv(O/'controls/matched_intercept_scores.csv')
 def score(name,design='pooled',base='main',alg='ridge'):
  q=s[(s.feature==name)&(s.design==design)&(s.baseline==base)&(s.algorithm==alg)];return q.rps_mean.iloc[0]
 labels=['Global label frequency','Coarse category','Main-space function','Main-stratum intercept only','Main-stratified existing models','Main-stratified DINO','Main-stratified existing + DINO']
 values=[score('baseline__global',base='none',alg='frequency'),score('baseline__coarse',base='none',alg='frequency'),score('baseline__main',base='none',alg='frequency'),c.query("design=='within_main' and baseline=='main'").rps_mean.iloc[0],score('selected__existing','within_main'),score('selected__dinov3','within_main'),score('selected__existing_plus_dino','within_main')]
 fig,ax=plt.subplots(figsize=(10,5));bars=ax.barh(labels,values);ax.invert_yaxis();ax.set(xlabel='Held-out cumulative probability error (RPS; lower is better)',title='Subjective difficulty tags: all 106 images, fixed leave-building folds');ax.bar_label(bars,fmt='%.3f',padding=3);ax.set_xlim(0,max(values)*1.15);save(fig,'tag_prediction_mainspace','106张已填人工标签的共同覆盖；这是难易判断的概率误差，不是收敛误差。',True)
 n=pd.read_csv(O/'similarity/neighbor_summary.csv');blocks=[3,6,9,11,12];q=n[n.rule=='all_labelled106'].set_index('feature');vals=q.loc[[f'dinov3__block{k}__panorama_mean'for k in blocks]]
 fig,ax=plt.subplots(figsize=(8,5))
 for col,l,m in [('same_building','Same building','o'),('same_main','Same main-space function','s'),('same_tag','Same subjective tag','^')]:ax.plot(blocks,vals[col],label=l,marker=m)
 ax.set(xlabel='DINO one-based block',ylabel='Fraction among five cosine-nearest labelled images',title='Deeper DINO neighborhoods also concentrate building context',ylim=(0,1),xticks=blocks);ax.legend();save(fig,'dino_neighbor_context','同一106张选中标签图内的描述性近邻；不是648总体，也不把近邻当独立验证。')
 fig,ax=plt.subplots(figsize=(8,5))
 for pool,label,mark in [('panorama_global','Panorama global','o'),('panorama_local16','Panorama local 16','s'),('faces_global','Six-face global mean','^'),('faces_local96','Six-face ordered local 96','d')]:
  vals=[score(f'dinov3__block{k}__{pool}')for k in blocks];ax.plot(blocks,vals,marker=mark,label=label)
 ax.axhline(score('baseline__main',base='none',alg='frequency'),ls='--',label='Main-space baseline');ax.set(xlabel='DINO one-based block',ylabel='Held-out RPS',title='Fixed layer/pooling candidates; pooled fit with main-space baseline',xticks=blocks);ax.legend();save(fig,'dino_layers_pooling','固定各层的结果全部保留；不能用图中最低点反向宣称事前最佳层。')
 hs=pd.read_csv(O/'historical_bridge/confirmation_sensitivity_counts.csv')
 for arm in ['manual','semi']:
  fig,ax=plt.subplots(figsize=(8,5))
  for rule,confirm,label,mark in [('P_pattern','suffix_only','Pattern: stable suffix','o'),('G10_geometry','suffix_only','Geometry: stable suffix','s'),('G10_geometry','suffix_and_tail','Geometry: suffix + tail confirmation','^')]:
   q=hs[(hs.condition==arm)&(hs.cut==.1)&(hs.rule==rule)&(hs.confirmation==confirm)&(hs.late_h==19)&(hs.process_tier=='early_one_or_two_supported_modes')].set_index('early_k').reindex(range(2,8));ax.plot(range(2,8),q.images.fillna(0),marker=mark,label=label)
  ax.set(xlabel='Early-onset threshold k (all tested k < 8)',ylabel='Number of historical image-condition candidates',title=arm.capitalize()+': early one/two supported modes, actual image n retained',xticks=range(2,8),ylim=(0,None));ax.legend();save(fig,'history_early_k_'+arm,'真实人数不放回重排的规则敏感性；没有新增独立人员，不是停止保证。')
 a=pd.read_csv(O/'rooms/same_room_tag_scores.csv').set_index('feature');outside=pd.read_csv(O/'rooms/same_coverage_tag_transfer.csv');v=outside.loc[outside.comparison=='same-room tag history vs baseline__main outside building','rps_b'].iloc[0]
 names=['Outside-building main baseline','Other-view tag frequency','DINO block 3 nearest view','DINO block 12 nearest view','Model point-count feedback']
 vals=[v,a.loc['same_room_frequency','rps_mean'],a.loc['dinov3__block3__panorama_mean__nn1','rps_mean'],a.loc['dinov3__block12__panorama_mean__nn1','rps_mean'],a.loc['feedback__point_counts__fixed_ridge','rps_mean']]
 fig,ax=plt.subplots(figsize=(10,4.5));b=ax.barh(names,vals);ax.invert_yaxis();ax.set(xlabel='Subjective tag RPS (54 matched target views)',title='Same-room tag transfer: 9 supported components, 8 buildings');ax.bar_label(b,fmt='%.3f',padding=3);ax.set_xlim(0,max(vals)*1.15);save(fig,'same_room_tag_transfer','允许读取同支持组件其他图的人工难度；不能等同于纯图片预测或收敛迁移。')
 (out/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8');return inventory
if __name__=='__main__':make_figures()
