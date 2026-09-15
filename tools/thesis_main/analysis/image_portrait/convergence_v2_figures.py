"""Numerical figures only, never panorama pixels or model inference."""
import numpy as np,pandas as pd
import matplotlib.pyplot as plt
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import OUT,csv,js

def make_figures(show=False):
 dest=OUT/'figures';dest.mkdir(exist_ok=True);inventory=[]
 def save(fig,name,caption,display=False):
  fig.tight_layout();fig.savefig(dest/(name+'.png'),dpi=170);inventory.append(dict(file=name+'.png',caption=caption))
  if show and display:plt.show()
  plt.close(fig)
 curves=pd.read_csv(OUT/'process/image_growth_curves.csv.gz');im='X7HyMhZNoso_987fd31155514f6facb131bd5c14881d';a=curves[(curves.image_id==im)&(curves.condition=='manual')&(curves.cut==.1)]
 fig,ax=plt.subplots(figsize=(8,4.7));ax.plot(a.k,a.n_modes,marker='.',label='All re-clustered modes (singletons retained)');ax.plot(a.k,a.n_supported_modes,marker='.',label='Modes supported by at least two people');ax.plot(a.k,a.supported_topologies,linestyle='--',label='Supported point-count values');ax.set(xlabel='Distinct observed valid annotators',ylabel='Mean number across real-person order replays',title='A diameter-limited numerical partition: 18 + 6 people',ylim=(0,2.2));ax.legend();ax.grid(axis='y',alpha=.2);save(fig,'same_point_modes_growth','24人全部8点，全池被切成18+6；94.4%的跨簇人员对仍满足同一兼容阈值，不能直接解释成自然分离模式。100种顺序不是独立实验。',True)
 win=pd.read_csv(OUT/'sensitivity/window_frequency_image_results.csv');win=win[(win.condition=='manual')&(win.cut==.1)&(win.tolerance==.1)&(win.n>=10)];cols=['tail3_frequency_pass','last_half_frequency_pass','disjoint_halves_frequency_pass'];vals=win[cols].mean().values
 fig,ax=plt.subplots(figsize=(8,4.7));ax.bar(['Last three additions','Entire second half','Disjoint halves'],vals);ax.set(title=f'Frequency stability depends on the question ({len(win)} Manual images)',ylabel='Mean finite-order pass fraction at TV <= 0.10',ylim=(0,1));
 for j,v in enumerate(vals):ax.text(j,v+.025,f'{v:.1%}',ha='center')
 save(fig,'frequency_window_sensitivity','固定全池分区的比例检查，46张Manual图。短尾与半程、独立人员两半回答不同问题；均非未来保证。',True)
 lat=pd.read_csv(OUT/'process/exact_mode_discovery_curves.csv.gz');candidate=lat[(lat.condition=='manual')&(lat.cut==.1)&(lat.n==24)&(lat.mode_people==2)].iloc[0];a=lat[(lat.image_id==candidate.image_id)&(lat.condition=='manual')&(lat.cut==.1)&(lat['mode']==candidate['mode'])]
 fig,ax=plt.subplots(figsize=(8,4.7));ax.plot(a.k,a.P_seen,label='At least one person from this mode');ax.plot(a.k,a.P_supported,label='At least two people from this mode');ax.set(title='A two-person mode in an observed pool of 24',xlabel='Distinct observed annotators',ylabel='Exact fraction of without-replacement subsets',ylim=(0,1.04));ax.legend();ax.grid(axis='y',alpha=.2);save(fig,'minority_discovery_support_delay',f'真实例：{candidate.image_id}，模式{int(candidate["mode"])}。全池2/24模式到k=8获得双人支持的比例仅10.14%；这是固定池精确组合计算，不是未来人群概率。')
 pools=pd.read_csv(OUT/'combinations/actual_class_pool_growth_curves.csv.gz');im='e9zR4mvMWw7_12c84e77f6564013a032220e8f9037e8';a=pools[(pools.image_id==im)&(pools.condition=='semi')&(pools.information=='Q')&(pools.k_classes==2)]
 fig,ax=plt.subplots(figsize=(8,4.7))
 for label,g in a.groupby('pool'):ax.plot(g.k,g.supported_modes,marker='.',label=f'{label}: {int(g.n_pool.iloc[0])} actual people')
 ax.set(title='Class pools and their union: supported modes',xlabel='Distinct observed annotators in the indicated pool',ylabel='Mean number of supported modes');ax.legend();ax.grid(axis='y',alpha=.2);save(fig,'class_pool_union_growth','目标楼外Q二分：14人组本身多模式、10人组统一，合并24人仍为多模式；不是两个单峰组混合产生多峰。')
 a=pd.read_csv(OUT/'prefix/score_summary.csv');fig,ax=plt.subplots(figsize=(8,4.7))
 for feature,label in [('cold_portrait','Portrait, given evaluation horizon'),('prefix_only','Observed first-k people'),('portrait_plus_prefix','Portrait + first-k people')]:
  g=a[(a.condition=='manual')&(a.target=='prefix_future_mass_TV')&(a.feature==feature)].sort_values('prefix_k');ax.plot(g.prefix_k,g.MAE,marker='o',label=label)
 ax.set(title='Updating estimates of subsequent mode-proportion drift',xlabel='Distinct observed prefix annotators',ylabel='Image-macro MAE of subsequent distribution TV',xticks=[2,3,5]);ax.legend();ax.grid(axis='y',alpha=.2);save(fig,'prefix_distribution_update','留楼评价；各方法在每个k共享相同实际后续人员和评价窗口。TV是过程维度，不能代替完整收敛。')
 sub=pd.read_csv(OUT/'subgroups/selected_subgroup_growth.csv.gz');im='yqstnuAEVhm_a93ea1ea5702412c9ef9c82a436c4599';a=sub[(sub.image_id==im)&(sub.condition=='manual')&(sub.candidate=='local_B')];f=curves[(curves.image_id==im)&(curves.condition=='manual')&(curves.cut==.1)]
 fig,ax=plt.subplots(figsize=(8,4.7));ax.plot(f.k,f.n_supported_modes,marker='.',label=f'Full pool: {int(f.n_valid_full.iloc[0])} people');ax.plot(a.k,a.supported_modes,marker='.',label=f'Training-identified local B class: {int(a.n_subgroup.iloc[0])} people');ax.set(title='A locally stable class inside a changing full-pool process',xlabel='Distinct observed annotators in indicated pool',ylabel='Mean number of supported modes');ax.legend();ax.grid(axis='y',alpha=.2);save(fig,'local_class_vs_full','例示目标楼外形成的局部B子类。组与全体人数不同，此图只展示过程；等人数对照另存equal_n表。')
 gap=pd.read_csv(OUT/'process/fixed_partition_vs_reclustered_growth.csv.gz');im='X7HyMhZNoso_987fd31155514f6facb131bd5c14881d';a=gap[(gap.image_id==im)&(gap.condition=='manual')&(gap.cut==.1)]
 fig,ax=plt.subplots(figsize=(8,4.7));ax.plot(a.k,a.P_supported,label='Fix final18+6 labels: exact support discovery');ax.plot(a.k,a.n_supported_modes,label='Re-cluster only the observed prefix',marker='.');ax.set(title='Mode occupancy is not the same as partition discovery',xlabel='Distinct observed annotators',ylabel='Expected number of supported numerical modes',ylim=(0,2.1));ax.legend();ax.grid(axis='y',alpha=.2);save(fig,'fixed_partition_vs_reclustered','k=8时固定全池模式的期望支持簇数1.681，重新聚类实际前缀仅1.05。固定分区重排会遗漏分区识别的不确定性。',True)
 js('figures/figure_manifest.json',dict(figures=inventory,original_images_used=False,all_charts_from_saved_numeric_tables=True,styling='matplotlib defaults, no specified colors',purpose='uncertainty structure, growth and conditional subclass behavior'))
 return inventory
if __name__=='__main__':make_figures()
