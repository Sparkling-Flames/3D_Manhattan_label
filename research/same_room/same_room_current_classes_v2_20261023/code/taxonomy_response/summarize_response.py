"""Small interpretable group/model tables and scientific response figure."""
from pathlib import Path
import argparse,json,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_mpl')
import numpy as np
import pandas as pd
from analyze_response import write_csv,numeric_indicators,hierarchy,derive_pooled


def group_patterns(a):
    d=pd.read_csv(a.results/'DECOMPOSITION_GROUP.csv')
    d=d[(d.scheme=='structure')&(d.support_domain=='structure_all_known')]
    keys=['budget','analysis_layer','building','group_id']
    fields=['pooled_between_fraction','pooled_composition_rho','pooled_member_residual_rho','pooled_total_rho',
      'composition_rho','member_residual_rho','total_rho',
      'total_var_a','total_var_b','between_var_a','between_var_b','within_var_a','within_var_b',
      'composition_range_a','composition_range_b','both_composition_Q_range_ge2',
      'n_joint_finite','n_direct_pairs','both_total_invariant','both_within_invariant']
    wide=d.set_index(keys+['metric'])[fields].unstack('metric')
    wide.columns=[metric+'__'+field for field,metric in wide.columns];wide=wide.reset_index()
    direction=pd.read_csv(a.results/'COMPOSITION_DIRECTION_GROUP.csv')
    direction=direction[(direction.scheme=='structure')&(direction.support_domain=='structure_all_known')&(direction.metric=='B8L2')]
    for rule,tag in [('all_panels','all'),('both_ends_range_ge2_descriptive','both_active'),('source_only_range_ge2','source_active')]:
        s=direction[direction.eligibility_rule==rule].copy()
        f=['positive_rho','negative_rho','both_near_zero','only_one_active','target_near_zero','target_active_positive','target_active_negative','n_direct_pairs']
        s=s[keys+f].rename(columns={c:'Q_'+tag+'__'+c for c in f})
        wide=wide.merge(s,on=keys,how='left')
    wide['Q_positive_composition_weak_member_descriptive']=(wide['B8L2__pooled_composition_rho']>=.3)&(wide['B8L2__pooled_member_residual_rho']<=.2)
    wide['Q_positive_composition_negative_member_descriptive']=(wide['B8L2__pooled_composition_rho']>0)&(wide['B8L2__pooled_member_residual_rho']<0)
    write_csv(a.out/'GROUP_PATTERN_SUMMARY.csv',wide)
    primary=wide[(wide.budget=='mid_n_rep0')&(wide.analysis_layer=='ordinary_comparable')].copy()
    write_csv(a.out/'GROUP_PATTERN_PRIMARY.csv',primary)
    if a.font and len(primary):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.font_manager import FontProperties
        from matplotlib.colors import TwoSlopeNorm
        font=FontProperties(fname=str(a.font));plt.rcParams['axes.unicode_minus']=False
        primary=primary.sort_values(['building','group_id'])
        columns=[('B8L2','composition_rho','质量配比\n面板ρ均值'),('B8L2','pooled_composition_rho','质量配比\n合并方差ρ'),
          ('B8L2','member_residual_rho','质量成员\n面板ρ均值'),('B8L2','pooled_member_residual_rho','质量成员\n合并方差ρ'),
          ('fusion_turn_n','pooled_composition_rho','转折数\n配比曲线'),('fusion_turn_n','pooled_member_residual_rho','转折数\n同配比成员'),
          ('log_recorded_time','pooled_composition_rho','劳动时间\n配比曲线'),('log_recorded_time','pooled_member_residual_rho','劳动时间\n同配比成员')]
        vals=np.column_stack([primary[m+'__'+f].to_numpy(float) for m,f,_ in columns])
        fig,ax=plt.subplots(figsize=(13.4,10.2))
        cm=plt.get_cmap('RdBu_r').copy();cm.set_bad('#e6e6e6')
        im=ax.imshow(vals,vmin=-1,vmax=1,cmap=cm,aspect='auto')
        ax.set_xticks(np.arange(len(columns)),[lab for _,_,lab in columns],fontproperties=font,fontsize=11)
        labels=[f"{r.group_id}  ({int(r['B8L2__n_direct_pairs'])} 对)" for _,r in primary.iterrows()]
        ax.set_yticks(np.arange(len(primary)),labels,fontproperties=font,fontsize=10)
        for i in range(len(primary)):
            for j in range(len(columns)):
                v=vals[i,j];s='—' if not np.isfinite(v) else f'{v:+.2f}'
                ax.text(j,i,s,ha='center',va='center',fontsize=10,color='white' if np.isfinite(v) and abs(v)>.6 else '#1f2937')
        ax.set_xticks(np.arange(-.5,len(columns),1),minor=True);ax.set_yticks(np.arange(-.5,len(primary),1),minor=True)
        ax.grid(which='minor',color='white',linewidth=1.5);ax.tick_params(which='both',length=0)
        for spine in ax.spines.values():spine.set_visible(False)
        ax.set_title('同房跨视角：配比趋势与具体成员剩余作用分开看',fontproperties=font,fontsize=16,pad=21)
        cb=fig.colorbar(im,ax=ax,fraction=.035,pad=.025);cb.set_label('跨视角相关 ρ',fontproperties=font,fontsize=11)
        fig.text(.08,.035,'普通 Manual；主预算为共同已知人员的一半（按容量裁剪），replicate 0。\n'
          '面板ρ均值：各面板相关先汇总到图对；合并方差ρ：先汇总方差/协方差，响应幅度大的面板影响更大。\n'
          '转折数、劳动时间列均为合并方差ρ。灰格为恒定/不可计算；原声明组允许重叠。\n'
          '同配比成员项＝实际团队结果 − 该视角同完整配比均值。正相关不等于两端都明显变化，活跃分母另见表。',fontproperties=font,fontsize=10,linespacing=1.45)
        fig.subplots_adjust(left=.18,right=.90,top=.90,bottom=.205)
        fig.savefig(a.out/'GROUP_COMPOSITION_MEMBER_REPEATABILITY.png',dpi=190,bbox_inches='tight')
        fig.savefig(a.out/'GROUP_COMPOSITION_MEMBER_REPEATABILITY.svg',bbox_inches='tight');plt.close(fig)
    return primary


def model_comparisons(a):
    p=a.calibration/'CALIBRATED_SUMMARY.csv'
    if not p.exists():return
    d=pd.read_csv(p)
    continuous=['source_mean','source_linear_calibration','source_plus_continuous','source_continuous_response','source_full_continuous']
    rows=[]
    for (layer,metric),z in d.groupby(['analysis_layer','metric']):
        c=z[z.model.isin(continuous)]
        if not len(c):continue
        bestmae=c.loc[c.mae.idxmin()];bestcontrast=c.loc[c.contrast_mse.idxmin()]
        fixed=z[z.model=='source_full_continuous'].iloc[0]
        for r in z.to_dict('records'):
            rows.append(r|dict(strongest_observed_continuous_MAE_model=bestmae.model,
              strongest_observed_continuous_MAE=bestmae.mae,MAE_minus_best_continuous=r['mae']-bestmae.mae,
              strongest_observed_continuous_contrast_model=bestcontrast.model,
              contrast_MSE_minus_best_continuous=r['contrast_mse']-bestcontrast.contrast_mse,
              MAE_minus_fixed_full_continuous=r['mae']-fixed.mae,
              contrast_MSE_minus_fixed_full_continuous=r['contrast_mse']-fixed.contrast_mse,
              best_comparator_status='observed minimum of registered continuous comparisons; not a newly fitted or externally validated selector'))
    write_csv(a.out/'MODEL_COMMON_SUPPORT_COMPARISON.csv',pd.DataFrame(rows))
    group=pd.read_csv(a.calibration/'CALIBRATED_GROUP.csv')
    piv=group.pivot(index=['analysis_layer','metric','building','group_id'],columns='model',values=['mae','contrast_mse','contrast_R2'])
    piv.columns=[met+'__'+model for met,model in piv.columns];piv=piv.reset_index()
    for model in ['source_continuous_plus_structure','source_continuous_plus_joint']:
        piv['MAE_gain_'+model]=piv['mae__source_full_continuous']-piv['mae__'+model]
        piv['contrast_MSE_gain_'+model]=piv['contrast_mse__source_full_continuous']-piv['contrast_mse__'+model]
    write_csv(a.out/'MODEL_INCREMENT_BY_GROUP.csv',piv)


def repeated_member_support(a):
    """Keep single-candidate contrasts while identifying actual class repeats."""
    all_m=numeric_indicators(pd.read_csv(a.results/'PANEL_DECOMPOSITION_PRIMARY.csv.gz',low_memory=False))
    m=all_m[(all_m.n_joint_finite>=6)&(all_m.n_member_residual_df>=3)]
    exclude=['n','replicate','k_selected','ordinary_comparable','scope_comparable','known_common_n','mid_n','is_primary_budget']
    num=[c for c in m if pd.api.types.is_numeric_dtype(m[c]) and c not in exclude]
    keys=['analysis_layer','support_domain','scheme','metric']
    for name,z in zip(['PAIR','GROUP','BUILDING','SUMMARY'],hierarchy(m,keys,num)):
        write_csv(a.out/('DECOMPOSITION_MEMBER_SUPPORTED_'+name+'.csv'),derive_pooled(z))
    one=all_m[(all_m.analysis_layer=='ordinary_comparable')&(all_m.support_domain=='structure_all_known')&(all_m.metric=='B8L2')&(all_m.k_selected==1)]
    strongest=one.sort_values('between_cov').head(3)
    teams=pd.read_csv(a.results/'PAIRED_TEAM_RESPONSES_PRIMARY.csv.gz',low_memory=False)
    teams=teams[teams.panel_id.isin(strongest.panel_id)]
    meta=['panel_id','pair_key','building','groups','image_a','image_b','selected_family','class_lo','class_hi','n','k_selected','n_joint_finite','composition_rho','between_cov']
    teams=teams.merge(strongest[meta],on='panel_id',how='left')
    teams['selection']='three most negative composition covariance panels among registered primary k=1; exact-member contrasts, one actual team per class proportion'
    write_csv(a.out/'SINGLE_MEMBER_CLASS_STRONG_REVERSALS.csv',teams)


def replicate_support(a):
    d=pd.read_csv(a.results/'REPLICATE_COMPOSITION_CURVES.csv');rows=[]
    keys=['analysis_layer','scheme','metric','comparison']
    for key,z in d.groupby(keys,dropna=False):
        f=z[z.composition_curve_rho.notna()]
        rows.append(dict(zip(keys,key))|dict(curve_rows=len(z),both_constant_rows=int(z.both_curves_constant.sum()),
          finite_correlation_rows=len(f),all_pairs=z.pair_key.nunique(),finite_correlation_pairs=f.pair_key.nunique(),
          finite_correlation_buildings=f.building.nunique(),finite_correlation_groups=len(set('|'.join(f.groups).split('|'))) if len(f) else 0))
    write_csv(a.out/'REPLICATE_CORRELATION_SUPPORT.csv',pd.DataFrame(rows))
    source=pd.read_csv(a.results/'SOURCE_TRANSFER_SUMMARY.csv')
    time=source[(source.budget=='mid_n_rep0')&(source.analysis_layer=='ordinary_comparable')&(source.metric=='log_recorded_time')]
    write_csv(a.out/'TIME_PREDICTION_PRIMARY.csv',time)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--calibration',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--font',type=Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    g=group_patterns(a);model_comparisons(a);repeated_member_support(a);replicate_support(a);print('group summary rows',len(g),flush=True)
