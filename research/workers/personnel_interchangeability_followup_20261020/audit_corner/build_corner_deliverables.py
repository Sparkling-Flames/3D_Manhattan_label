"""Read event outputs, emit applicability cards and continuous building plots."""
import argparse,json,pathlib,textwrap
import numpy as np
import pandas as pd
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/corner_matplotlib')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/corner_cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def agg(v,col):
 return v.groupby(['building','pool_id'])[col].mean().groupby('building').mean()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();out=a.out
 ev=pd.read_csv(out/'CORNER_EVENTS.csv.gz');pair=pd.read_csv(out/'CORNER_PAIRS.csv.gz');cards=[]
 strata=['method_id','domain','context_id','phase','k','m','direction','replay_group']
 for key,g in ev.groupby(strata,dropna=False):
  v=g[g.both_available];card=dict(zip(strata,key));card.update(attempted_events=len(g),attempted_images=g.image.nunique(),attempted_buildings=g.building.nunique(),joint_events=len(v),joint_images=v.image.nunique(),joint_buildings=v.building.nunique(),joint_fraction=len(v)/len(g),interpretation='Conditional continuous geometry estimate, not validated human-nearness success or unseen-person generalization',arms={})
  for arm in ['within','cross']:
   t={'status_counts':g[arm+'_status'].value_counts().to_dict(),'metrics':{},'frozen_pro_flags':{}}
   for metric in ['bev_mean_h','bev_max_h','top_mean_h','top_max_h','bev_max_pairscale','top_max_pairscale','bev_max_local_radius_fraction']:
    col=arm+'_'+metric;t['metrics'][metric]={'building_equal_mean':agg(v,col).mean(),'event_median':v[col].median(),'event_p90':v[col].quantile(.9),'event_max':v[col].max()}
   for flag in ['joint_stable_main','geometry_noQ_main','geometry_shape_main']:
    t['frozen_pro_flags'][flag]={'all_attempts_building_equal_rate':agg(g,arm+'_'+flag).mean(),'joint_candidates_building_equal_rate':agg(v,arm+'_'+flag).mean()}
   for flag in ['ring_reversed','high_angle_correspondence_warning','matched_reflex_disagreement_n']:
    col=arm+'_'+flag;t[flag+'_nonzero_events']=int((g[col].fillna(0)>0).sum())
   card['arms'][arm]=t
  card['distance_difference']={m:agg(v,'cross_'+m).mean()-agg(v,'within_'+m).mean() for m in ['bev_mean_h','bev_max_h','top_mean_h','top_max_h']}
  card['applicability_cautions']=['Same-count unique cyclic correspondence does not establish shared semantic structure.','Failure and changed-count events remain outside continuous-distance estimand but inside attempted denominator.','Class IDs are method-local. A direction can be useful without every pair of classes being separated.']
  cards.append(card)
 (out/'APPLICABILITY_CARDS.json').write_text(json.dumps(clean(cards),ensure_ascii=False,indent=2))
 # Full cross-tab plus continuous tails conditional on old/new flags, not a new pass rule.
 compare=[]
 for keys,g in pair.groupby(['method_id','arm','joint_stable_main','geometry_noQ_main','geometry_shape_main','status'],dropna=False):
  row=dict(zip(['method_id','arm','joint_stable_main','geometry_noQ_main','geometry_shape_main','status'],keys),attempts=len(g),images=g.image.nunique(),buildings=g.building.nunique())
  for m in ['bev_mean_h','bev_max_h','top_max_h']:
   row[m+'_median']=g[m].median();row[m+'_p90']=g[m].quantile(.9);row[m+'_max']=g[m].max()
  compare.append(row)
 pd.DataFrame(compare).to_csv(out/'LEGACY_SHAPE_CORNER_COMPARISON.csv',index=False)
 figs=out/'figures';figs.mkdir(exist_ok=True);index=[]
 groups=list(ev.groupby(['method_id','context_id','phase','k','m','direction','replay_group'],dropna=False))
 for j,(key,g) in enumerate(groups):
  v=g[g.both_available]
  if not len(v):continue
  fig,axs=plt.subplots(2,2,figsize=(11,8));metrics=['bev_mean_h','bev_max_h','top_mean_h','top_max_h']
  for ax,metric in zip(axs.flat,metrics):
   w=agg(v,'within_'+metric);c=agg(v,'cross_'+metric);bs=sorted(set(w.index)&set(c.index))
   for building in bs:ax.plot([0,1],[w[building],c[building]],marker='o',alpha=.6,lw=1,label=building)
   ax.plot([0,1],[w.mean(),c.mean()],marker='D',color='black',lw=3,label='equal-building mean')
   ax.set_ylim(bottom=0);ax.set_xticks([0,1],['Same composition','Changed composition']);ax.set_ylabel(metric+' (camera h)');ax.grid(alpha=.2)
  axs.flat[1].legend(fontsize=6,loc='best')
  role=key[6] if str(key[6])!='nan' else key[0].replace('R_directswap_continuous_partition_b2_K3__ordinary__mixed_history_v1','Mixed composition role')
  title=f'{role} | {key[2]} | n={key[3]}, m={key[4]} | {key[5]}\nJoint correspondence candidates: {len(v)}/{len(g)} events, {v.image.nunique()} images, {v.building.nunique()} buildings'
  fig.suptitle('\n'.join(textwrap.fill(line,110) for line in title.split('\n')),fontsize=9);fig.text(.02,.01,'Distance means: joint-correspondence subset. Structural/failure rates: all attempts. Lines: buildings; no fitted nearness threshold.',fontsize=8);fig.tight_layout(rect=[0,.03,1,.91]);name=f'corner_continuous_{j:03d}.png';fig.savefig(figs/name,dpi=150);plt.close(fig)
  index.append(dict(method_id=key[0],context_id=key[1],phase=key[2],k=key[3],m=key[4],direction=key[5],replay_group=key[6],file='figures/'+name))
 (out/'FIGURE_INDEX.json').write_text(json.dumps(clean(index),indent=2))
 print(json.dumps({'cards':len(cards),'figures':len(index)}))
if __name__=='__main__':main()
