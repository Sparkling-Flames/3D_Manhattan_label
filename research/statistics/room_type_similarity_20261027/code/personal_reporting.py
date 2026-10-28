#!/usr/bin/env python3
"""Readable worker-by-purpose evidence from completed fixed LOBO predictions."""
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from scipy.stats import spearmanr

def save(d,p):d.to_csv(p,index=False,compression={'method':'gzip','mtime':0} if str(p).endswith('.gz') else None)
def wcorr(a,b,w):
 a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float);w=np.asarray(w,dtype=float)
 ok=np.isfinite(a)&np.isfinite(b)&np.isfinite(w)&(w>0);a=a[ok];b=b[ok];w=w[ok]
 if len(a)<3:return np.nan
 aa=a-np.average(a,weights=w);bb=b-np.average(b,weights=w)
 den=np.sqrt(np.average(aa*aa,weights=w)*np.average(bb*bb,weights=w))
 return np.average(aa*bb,weights=w)/den if den>1e-12 else np.nan

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--figures',type=Path);ap.add_argument('--font',type=Path);a=ap.parse_args();p=a.results
 ps=[]
 for f in sorted(p.glob('OOF_*.csv.gz')):ps.append(pd.read_csv(f,dtype={'object_id':str}))
 d=pd.concat(ps,ignore_index=True)
 keys=['outcome','object_id','image_key','image','building','worker_id','room_type_model','difficulty']
 m=d.pivot(index=keys,columns='method',values='predicted_relative').reset_index()
 actual=d[d.method=='zero'][keys+['actual_relative','same_purpose_history_buildings','history_buildings']]
 m=m.merge(actual,on=keys,validate='one_to_one')
 for method in ['person_history','person_ridge','person_geometry','person_purpose','person_geometry_purpose']:
  m['ae_'+method]=abs(m[method]-m.actual_relative)
 m['purpose_increment']=m.person_geometry_purpose-m.person_geometry
 m['after_general']=m.actual_relative-m.person_history
 m['after_geometry']=m.actual_relative-m.person_geometry
 m['mae_gain_purpose_after_geometry']=m.ae_person_geometry-m.ae_person_geometry_purpose
 m['mae_gain_purpose_vs_general']=m.ae_person_history-m.ae_person_geometry_purpose
 save(m,p/'READABLE_EXACT_PERSON_PREDICTIONS.csv.gz')
 rows=[]
 for key,g in m.groupby(['outcome','worker_id','room_type_model']):
  b=g.groupby('building').agg(relative=('actual_relative','mean'),after_general=('after_general','mean'),after_geometry=('after_geometry','mean'),purpose_increment=('purpose_increment','mean'),mae_gain=('mae_gain_purpose_after_geometry','mean'))
  rows.append(dict(zip(['outcome','worker_id','room_type_model'],key))|dict(images=g.image_key.nunique(),buildings=len(b),records=len(g),
   actual_relative_mean=g.actual_relative.mean(),actual_relative_building_mean=b.relative.mean(),
   general_adjusted_mean=g.after_general.mean(),general_adjusted_building_mean=b.after_general.mean(),
   condition_adjusted_mean=g.after_geometry.mean(),condition_adjusted_building_mean=b.after_geometry.mean(),
   predicted_purpose_increment=g.purpose_increment.mean(),
   condition_adjusted_positive_buildings=int((b.after_geometry>0).sum()),condition_adjusted_negative_buildings=int((b.after_geometry<0).sum()),
   purpose_increment_mae_gain=g.mae_gain_purpose_after_geometry.mean(),purpose_increment_vs_general_mae_gain=g.mae_gain_purpose_vs_general.mean(),
   purpose_increment_better_buildings=int((b.mae_gain>0).sum()),purpose_increment_worse_buildings=int((b.mae_gain<0).sum()),
   same_purpose_history_buildings_min=g.same_purpose_history_buildings.min(),same_purpose_history_buildings_median=g.same_purpose_history_buildings.median(),
   same_purpose_history_ge2_buildings_rows=int((g.same_purpose_history_buildings>=2).sum()),
   sign_agree_purpose_increment_after_condition=np.mean(np.sign(g.purpose_increment)==np.sign(g.after_geometry))))
 cards=pd.DataFrame(rows);save(cards,p/'PERSON_PURPOSE_EVIDENCE_CARDS.csv')
 byb=m.groupby(['outcome','worker_id','room_type_model','building'],as_index=False).agg(images=('image_key','nunique'),records=('object_id','size'),actual_relative=('actual_relative','mean'),after_general=('after_general','mean'),after_geometry=('after_geometry','mean'),purpose_increment=('purpose_increment','mean'),mae_gain_purpose=('mae_gain_purpose_after_geometry','mean'),mae_gain_vs_general=('mae_gain_purpose_vs_general','mean'))
 save(byb,p/'PERSON_PURPOSE_BUILDING_EVIDENCE.csv.gz')
 support=[]
 for (oc,room),g in cards.groupby(['outcome','room_type_model']):
  for nb in [2,3]:
   z=g[g.buildings>=nb]
   support.append(dict(outcome=oc,room_type=room,min_buildings=nb,people=len(z),people_mae_better=int((z.purpose_increment_mae_gain>0).sum()),people_mae_worse=int((z.purpose_increment_mae_gain<0).sum()),mean_person_mae_gain=z.purpose_increment_mae_gain.mean(),mean_person_mae_gain_vs_general=z.purpose_increment_vs_general_mae_gain.mean(),median_images=z.images.median(),median_buildings=z.buildings.median()))
 save(pd.DataFrame(support),p/'PERSON_PURPOSE_GAIN_SUPPORT.csv')
 # Actual predictions can also support known/unknown-use and history-budget comparisons.
 coverage=[]
 for (oc,room),g in m.groupby(['outcome','room_type_model']):
  for nb in [0,1,2,3]:
   z=g[g.same_purpose_history_buildings>=nb]
   for method in ['person_history','person_geometry','person_geometry_purpose']:
    im=z.groupby(['image_key','building']).agg(mae=('ae_'+method,'mean')) if len(z) else pd.DataFrame()
    coverage.append(dict(outcome=oc,room_type=room,min_other_building_history=nb,method=method,records=len(z),images=z.image_key.nunique(),buildings=z.building.nunique(),workers=z.worker_id.nunique(),image_equal_mae=im.mae.mean() if len(im) else np.nan))
 save(pd.DataFrame(coverage),p/'HISTORY_BUDGET_MATCHED_SUPPORT.csv')
 R=pd.read_csv(p/'CROSS_BUILDING_REPEATABILITY_ROWS.csv.gz')
 rws=[]
 for (oc,room),g in R.groupby(['outcome','room_type_model']):
  for nb in [1,2]:
   z=g[g.same_purpose_n_buildings>=nb]
   if not len(z):continue
   wi=1/z.groupby('image_key').image_key.transform('size')
   ni=z[['building','image_key']].drop_duplicates().groupby('building').size()
   wb=wi/z.building.map(ni)
   for weighting,wt in [('record_equal',np.ones(len(z))),('image_equal',wi),('building_equal',wb)]:
    rws.append(dict(outcome=oc,room_type=room,min_history_buildings=nb,weighting=weighting,records=len(z),images=z.image_key.nunique(),buildings=z.building.nunique(),people=z.worker_id.nunique(),
     same_purpose_history_corr=wcorr(z.history_same_purpose_mean,z.actual_relative,wt),general_history_corr=wcorr(z.history_person_mean,z.actual_relative,wt),
     purpose_deviation_after_general_corr=wcorr(z.history_type_deviation,z.target_after_general,wt)))
 save(pd.DataFrame(rws),p/'REPEATABILITY_WEIGHTED.csv')
 counts=pd.read_csv(p/'PER_IMAGE_METHODS.csv.gz').groupby(['outcome','method']).agg(images=('image_key','size'),spearman_valid_images=('spearman','count'),pearson_valid_images=('pearson','count')).reset_index()
 save(counts,p/'RANK_CORRELATION_SUPPORT.csv')

 if a.figures:
  a.figures.mkdir(parents=True,exist_ok=True)
  import matplotlib;matplotlib.use('Agg')
  import matplotlib.pyplot as plt
  from matplotlib.font_manager import FontProperties
  fp=FontProperties(fname=str(a.font)) if a.font and a.font.exists() else FontProperties()
  summary=pd.read_csv(p/'METHOD_SUMMARY.csv')
  methods=['zero','person_history','person_ridge','person_purpose','person_geometry','person_geometry_purpose']
  names=['无个人历史\n相对值预测为0','楼外个人\n历史均值','人员主效应\n收缩估计','人员主效应\n加用途','人员×难度\n与参考几何','难度/几何基础\n再加用途']
  cols=[('Q','image_equal_mae','个人相对 Q：平均绝对误差'),('Q','image_equal_rmse','个人相对 Q：均方根误差'),('annotation_turn5','image_equal_rmse','个人相对转折：均方根误差')]
  fig,axs=plt.subplots(1,3,figsize=(16,5.6),constrained_layout=True)
  for ax,(oc,col,title) in zip(axs,cols):
   vals=[summary[(summary.outcome==oc)&(summary.method==me)][col].iloc[0] for me in methods]
   bars=ax.barh(np.arange(6),vals,color=['#aeb8c2','#567793','#6d90a8','#b7a6b2','#267d88','#d58b4f'])
   ax.set_yticks(np.arange(6),names,fontproperties=fp,fontsize=10);ax.invert_yaxis();ax.set_xlim(0,max(vals)*1.15)
   ax.set_title(title,fontproperties=fp,fontsize=13);ax.set_xlabel('误差越小越好',fontproperties=fp)
   for b,v in zip(bars,vals):ax.text(v+max(vals)*.02,b.get_y()+b.get_height()/2,f'{v:.3f}',va='center',fontsize=10)
   ax.spines[['right','top']].set_visible(False)
  fig.suptitle('同用途个人表现：一般历史有信息，用途未提供稳定的额外改善\n普通 Manual 5719 份 · 177 图 · 22 栋楼；整栋楼留出，目标同图同行基准排除本人',fontproperties=fp,fontsize=15)
  fig.savefig(a.figures/'F_PERSONAL_CROSS_BUILDING_MODELS.png',dpi=180)
  plt.close(fig)
 print(json.dumps({'directory':str(p),'prediction_records':len(m),'person_purpose_cards':len(cards),'building_cells':len(byb),'success':True},ensure_ascii=False))
if __name__=='__main__':main()
