"""Numerical figures, no image assets. Matplotlib default colors and no style."""
from pathlib import Path
import pandas as pd,numpy as np
import matplotlib.pyplot as plt
from tools.thesis_main.analysis.image_portrait.image_links_followup_common import OUT,js

def make_figures(show=False):
 dest=OUT/'figures';dest.mkdir(exist_ok=True);inventory=[]
 def save(fig,name,caption,display=False):
  fig.tight_layout();fig.savefig(dest/(name+'.png'),dpi=165);inventory.append(dict(file=name+'.png',caption=caption))
  if show and display:plt.show()
  plt.close(fig)
 a=pd.read_csv(OUT/'prediction/score_summary.csv');a=a[(a.condition=='manual')&(a.target=='candidate_v2')&a.algorithm.isin(['ridge','baseline'])];names=['constant','scene_frequency','main_frequency','feedback_counts','feedback_all','selected_counts_existing','selected_counts_dino'];v=a.set_index('feature').loc[names]
 fig,ax=plt.subplots(figsize=(8.5,4.5));ax.barh(['Constant','Scene frequency','Main-space frequency','Layout point counts','All simple feedback','Counts + selected task representation','Counts + selected DINO'],v.image_loss);ax.invert_yaxis();ax.set(xlabel='Three-class Brier loss (lower is better)',title='Unreviewed second-round candidates: leave-building prediction');save(fig,'candidate_prediction','第二轮候选，Manual；基线61图，含点数/反馈方案60图。精确配对差值另见预测表；不是审核真值。',True)
 a=pd.read_csv(OUT/'A/adjusted_picture_associations.csv');v=a[(a.condition=='manual')&a.trait.eq('floor_boundary')&a.adjustment.eq('n_scene_building')].set_index('target').loc[['full_p_by_8','core10_p_by_19','late_quarter_new','half_tv_all']]
 fig,ax=plt.subplots(figsize=(8.5,4.5));yy=np.arange(len(v));ax.errorbar(v.coefficient,yy,xerr=np.vstack([v.coefficient-v.lo,v.hi-v.coefficient]),fmt='o',capsize=4);ax.axvline(0,linestyle='--');ax.set(yticks=yy,yticklabels=['Early full-distribution suffix','Core by observed limit <=19','Late-quarter novel geometry','Half-sample mode proportion gap'],xlabel='Partial minus visible boundary: adjusted coefficient',title='Different uncertainty processes, not one difficulty score');save(fig,'boundary_process_associations','Manual133图；调整log人数、类别和楼宇；区间为探索描述，未覆盖多重分析选择；部分边界与遮挡初筛高度共线。')
 a=pd.read_csv(OUT/'oos/geometry_scope_and_process.csv');fig,ax=plt.subplots(figsize=(8.2,5));ax.scatter(a.total_clusters,a.late_quarter_new);labels=['A','B','C','D','E','F','G','H','I']
 for label,(_,r)in zip(labels,a.iterrows()):ax.annotate(label,(r.total_clusters,r.late_quarter_new),xytext=(5,5),textcoords='offset points')
 ax.set(xlabel='Final numerical clusters (singletons retained)',ylabel='Late-quarter novel-geometry rate',title='Nine recovered OOS tasks: cluster number is not growth');save(fig,'oos_clusters_growth','9张OOS任务几何，非in-scope重分类；字母与oos表按image_id排序对应。F同点数、7簇、末段新几何率0，需区分分区变化。')
 a=pd.read_csv(OUT/'prediction/paired_increment.csv');a=a[(a.condition=='manual')&a.new.eq('feedback_all')&a.baseline.eq('feedback_counts')];v=a.set_index('target').loc[['candidate_v2','full_p_by_8','core10_p_by_19','late_quarter_new']]
 fig,ax=plt.subplots(figsize=(8.2,4.5));yy=np.arange(len(v));ax.errorbar(v.delta,yy,xerr=np.vstack([v.delta-v.lo,v.hi-v.delta]),fmt='o',capsize=4);ax.axvline(0,linestyle='--');ax.set(yticks=yy,yticklabels=['Candidate Brier loss','Early full stability MAE','Core stability MAE','Late novelty MAE'],xlabel='All feedback minus point-count feedback (paired loss)',title='Feedback gains are endpoint-specific');save(fig,'feedback_increment','每行在相同图片覆盖配对；楼宇重采样区间。分类Brier与连续MAE尺度不同，不比较行间效果量大小。')
 a=pd.read_csv(OUT/'E/continuous_axis_paired_differences.csv');a=a[(a.condition=='manual')&a.axis.eq('quality')&a.n_people.eq(8)].set_index('metric');v=a.loc[['singleton_share','point_count_disagreement','full_by8','late_quarter_new','heldout_geometry_coverage']]
 fig,ax=plt.subplots(figsize=(8.2,4.5));yy=np.arange(len(v));ax.errorbar(v.delta,yy,xerr=np.vstack([v.delta-v.lo,v.hi-v.delta]),fmt='o',capsize=4);ax.axvline(0,linestyle='--');ax.set(yticks=yy,yticklabels=['Singleton share','Point-count disagreement','Early suffix stability','Late novel geometry','Two-person held-out coverage'],xlabel='Lower reference-error group minus higher-error group',title='Same image, eight real people; profiles learned outside building');save(fig,'person_composition','46张Manual图，Q在目标楼外形成；两组各8名不同真实人员，同一两名未来人员独立于组合。Q是参考偏差，不等于语义真值。')
 a=pd.read_csv(OUT/'E/picture_condition_person_effects.csv');a=a[(a.condition=='manual')&a.axis.eq('quality')&a.n_people.eq(8)&a.field.eq('floor_boundary')&a.metric.eq('full_by8')]
 fig,ax=plt.subplots(figsize=(7.5,4.5));ax.errorbar(a.delta,np.arange(len(a)),xerr=np.vstack([a.delta-a.lo,a.hi-a.delta]),fmt='o',capsize=4);ax.axvline(0,linestyle='--');ax.set(yticks=np.arange(len(a)),yticklabels=[f'{r.label} (n={r.images})'for _,r in a.iterrows()],xlabel='Eight-person early-stability difference',title='Person effect exists in both boundary strata');save(fig,'person_picture_conditions','Q两端对比在边界部分可见32图和可见14图中分别展示；两层效应差异区间跨0，不能宣布专长交互已确认。')
 js('figures/inventory.json',inventory);return inventory
if __name__=='__main__':print(make_figures())
