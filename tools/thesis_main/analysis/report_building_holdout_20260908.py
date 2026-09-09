"""回读已审计输出，生成分母/初始化分层表与静态图；不重新选人或拟合。"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3]
OUTPUT='analysis_results/building_holdout_exploration_20260908_v1'


def build(root,out):
    def read(name):return pd.read_csv(out/name)
    def save(name,frame):frame.to_csv(out/name,index=False,float_format='%.12g')
    assert json.loads((out/'INDEPENDENT_AUDIT.json').read_text(encoding='utf-8'))['status']=='passed'
    a=pd.read_csv(out/'census/canonical_index.csv.gz',dtype=str,keep_default_na=False)
    trace=pd.read_csv(root/'analysis_results/uncertainty_decision_ready_20260908_v1/response_index.csv.gz',dtype=str,keep_default_na=False)
    assert set(trace.canonical_annotation_id)==set(a.canonical_annotation_id)
    assert trace.groupby('context_key').legacy_initialization_source_kind.nunique().eq(1).all()
    init=trace.drop_duplicates('context_key')[['context_key','stage','raw_condition','legacy_initialization_source_kind','initialization_reconstructed_source','initial_trace_interpretation']].copy()
    init['initialization_kind']=init.legacy_initialization_source_kind
    init.loc[init.raw_condition!='semi','initialization_kind']='not_applicable'
    c1=(init.stage=='C1')&(init.raw_condition=='semi')
    assert init.loc[c1,'initialization_reconstructed_source'].str.contains('groudTruth.json',regex=False).all()
    init.loc[c1,'initialization_kind']='c1_reference_derived_reconstruction'
    # C1旧表的missing字段不是当前重建状态；保留原值和来源，不据此宣称历史实际观看事件。
    save('initialization_context_index.csv',init)
    kinds=init.set_index('context_key').initialization_kind
    curves=read('context_curve_summary.csv');gains=read('context_paired_gain_summary.csv');candidates=read('context_precision_candidate_summary.csv')
    for frame in (curves,gains,candidates):
        frame['initialization_kind']=frame.context_key.map(kinds);assert frame.initialization_kind.notna().all()
    full=curves[curves.k_label=='full_history']
    keys=['stage','raw_condition','initialization_kind','metric','cohort','scheme']
    summary=full.groupby(keys).agg(contexts=('context_key','nunique'),buildings=('building_id','nunique'),
        split_context_count=('split_count','sum'),minimum_context_splits=('split_count','min'),maximum_context_splits=('split_count','max'),
        mean_history_n=('history_n_mean','mean'),mean_validation_n=('validation_n_mean','mean'),
        absolute_disagreement_gap=('absolute_disagreement_gap_mean','mean'),medoid_validation_distance=('medoid_validation_distance_mean','mean'),
        count_distribution_tv=('count_distribution_tv_mean','mean')).reset_index()
    save('stage_condition_results.csv',summary)
    gains['gap_gain_positive']=gains.disagreement_gap_improvement_mean>0
    gains['medoid_gain_positive']=gains.medoid_validation_improvement_mean>0
    result=gains.groupby(keys+['start_k']).agg(contexts=('context_key','nunique'),buildings=('building_id','nunique'),
        split_context_count=('split_count','sum'),mean_end_history_n=('end_history_n_mean','mean'),
        gap_improvement=('disagreement_gap_improvement_mean','mean'),medoid_improvement=('medoid_validation_improvement_mean','mean'),
        count_tv_improvement=('count_tv_improvement_mean','mean'),contexts_gap_positive=('gap_gain_positive','sum'),contexts_medoid_positive=('medoid_gain_positive','sum')).reset_index()
    save('paired_gain_results.csv',result)
    core=(gains.metric=='original_floor')&(gains.cohort=='method_available')&(gains.scheme=='two_thirds')&(gains.start_k==5)
    counter=gains[core&((gains.disagreement_gap_improvement_mean<0)|(gains.medoid_validation_improvement_mean<0))]
    save('counterexamples.csv',counter)
    pc=candidates.groupby(keys+['tolerance']).agg(contexts=('context_key','nunique'),fit_split_contexts=('precision_fit_splits','sum'),
        candidate_by20_split_contexts=('candidate_splits','sum'),candidate_within_history=('predicted_k_within_history_splits','sum'),
        candidate_within_validation=('predicted_k_within_validation_splits','sum'),gap_observed=('candidate_gap_observed_splits','sum'),
        gap_within_same_numeric_tolerance=('candidate_gap_within_tolerance_splits','sum')).reset_index()
    save('precision_diagnostic_summary.csv',pc)
    bc=candidates.groupby(['building_id']+keys+['tolerance']).agg(contexts=('context_key','nunique'),
        fit_split_contexts=('precision_fit_splits','sum'),candidate_by20_split_contexts=('candidate_splits','sum'),
        conditional_context_median_k=('predicted_k_median','median'),candidate_within_history=('predicted_k_within_history_splits','sum'),
        candidate_within_validation=('predicted_k_within_validation_splits','sum')).reset_index()
    save('building_precision_diagnostic.csv',bc)
    status=read('response_metric_status.csv.gz')
    valid=status[status.status=='computable'].groupby(['context_key','metric']).size().unstack(fill_value=0)
    ready=a.groupby(['building_id','context_key','image_id','stage','block_index','raw_condition']).agg(raw_workers=('worker_id','nunique')).reset_index()
    for metric in ['original_floor','legacy_linear']:ready[metric+'_workers']=ready.context_key.map(valid[metric]).fillna(0).astype(int)
    floor=full[(full.metric=='original_floor')&(full.cohort=='method_available')&(full.scheme=='two_thirds')].set_index('context_key')
    ready['floor_available_splits_200']=ready.context_key.map(floor.split_count).fillna(0).astype(int)
    ready['initialization_kind']=ready.context_key.map(kinds)
    save('context_readiness.csv',ready)
    b=read('census/building_census.csv')
    counts=ready.groupby('building_id').agg(raw_contexts_at_least20=('raw_workers',lambda s:sum(s>=20)),
        floor_contexts_any_valid_split=('floor_available_splits_200',lambda s:sum(s>0)),
        floor_contexts_all200_valid=('floor_available_splits_200',lambda s:sum(s==200)))
    b=b.merge(counts,on='building_id',validate='one_to_one');save('building_readiness.csv',b)

    # 固定支持曲线：同一context同一分组必须能提供15历史人，全部k使用同一验证集合。
    sample=[]
    for chunk in pd.read_csv(out/'heldout_prefix_draws.csv.gz',chunksize=50000):
        use=chunk[(chunk.metric=='original_floor')&(chunk.cohort=='method_available')&(chunk.scheme=='two_thirds')&
                  (chunk.stage=='P1')&(chunk.raw_condition!='oos')&(chunk.history_n>=15)&chunk.k.isin([2,3,5,8,10,12,15])]
        sample.append(use[['context_key','split_id','stage','raw_condition','k','history_n','validation_n','absolute_disagreement_gap','medoid_validation_distance']])
    fixed=pd.concat(sample,ignore_index=True)
    assert fixed.groupby(['context_key','split_id']).k.nunique().eq(7).all()
    fixed['initialization_kind']=fixed.context_key.map(kinds)
    per=fixed.groupby(['context_key','stage','raw_condition','initialization_kind','k']).agg(
        split_count=('split_id','nunique'),gap=('absolute_disagreement_gap','mean'),risk=('medoid_validation_distance','mean'),
        history_n=('history_n','mean'),validation_n=('validation_n','mean')).reset_index()
    per['building_id']=per.context_key.map(a.drop_duplicates('context_key').set_index('context_key').building_id)
    bfc=per.groupby(['building_id','stage','raw_condition','initialization_kind','k']).agg(contexts=('context_key','nunique'),
        split_contexts=('split_count','sum'),minimum_context_splits=('split_count','min'),maximum_context_splits=('split_count','max'),
        gap=('gap','mean'),risk=('risk','mean'),history_n=('history_n','mean'),validation_n=('validation_n','mean')).reset_index()
    save('building_fixed_support_curves.csv',bfc)
    fc=per.groupby(['stage','raw_condition','initialization_kind','k']).agg(contexts=('context_key','nunique'),
        split_contexts=('split_count','sum'),minimum_context_splits=('split_count','min'),maximum_context_splits=('split_count','max'),
        gap=('gap','mean'),risk=('risk','mean'),history_n=('history_n','mean'),validation_n=('validation_n','mean')).reset_index()
    save('fixed_support_context_curves.csv',per);save('fixed_support_curves.csv',fc)
    figdir=out/'figures';figdir.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
    bb=b.sort_values('canonical_responses')
    fig,ax=plt.subplots(figsize=(11,8));left=np.zeros(len(bb))
    for name,color,label in [('manual_canonical_responses','#3673a3','Manual'),('semi_canonical_responses','#e79f45','Semi'),('oos_canonical_responses','#999999','旧 OOS 条件')]:
        ax.barh(bb.building_id,bb[name],left=left,color=color,label=label);left+=bb[name].to_numpy()
    for y,total in enumerate(left):ax.text(total+3,y,str(int(total)),va='center',fontsize=9)
    ax.set_xlim(0,left.max()*1.1);ax.set_xlabel('canonical 响应份数（修订不重复计数）');ax.legend(loc='lower right')
    ax.set_title('22 个 building 的全部历史响应：2501 份 / 26 人 / 214 图')
    fig.tight_layout();fig.savefig(figdir/'building_counts.png',dpi=180);plt.close(fig)
    labels={'not_applicable':'P1 Manual','control_natural':'P1 Semi 自然 control','trap_natural':'P1 Semi 自然 trap','trap_synthetic_disjoint_source':'P1 Semi 合成 trap'}
    fig,axes=plt.subplots(1,2,figsize=(13,5.7))
    for kind,g in fc.groupby('initialization_kind'):
        label=f'{labels[kind]}（{g.contexts.iloc[0]} 单元；各 {g.minimum_context_splits.iloc[0]}–{g.maximum_context_splits.iloc[0]} 次）'
        axes[0].plot(g.k,g.gap,marker='o',label=label);axes[1].plot(g.k,g.risk,marker='o',label=label)
    for ax in axes:ax.set_xlabel('历史前缀人数 k');ax.set_xticks([2,3,5,8,10,12,15]);ax.grid(alpha=.2);ax.set_ylim(bottom=0)
    axes[0].set_ylabel('历史/验证平均成对差异的绝对差');axes[1].set_ylabel('历史代表到固定验证组的平均距离')
    axes[0].set_title('分歧估计的组间接近程度');axes[1].set_title('代表布局对另一组人的贴近程度')
    axes[0].legend(fontsize=8)
    fig.suptitle('原点序地面 1−IoU：仅保留历史可算人数 ≥15 的同一批划分',fontsize=13)
    rare=per[(per.raw_condition=='manual')&(per.k==15)&(per.split_count==1)].context_key.nunique()
    fig.text(.5,.015,f'仅描述固定历史数据；Manual 中 {rare} 单元仅 1 次划分满足条件。曲线不代表全体图像或未来新人的置信区间。',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.04,1,.94]);fig.savefig(figdir/'fixed_support_curves.png',dpi=180);plt.close(fig)
    qa=dict(status='completed',context_index_rows=len(ready),building_rows=len(b),counterexample_contexts=len(counter),
            initialization_groups=init.groupby(['stage','raw_condition','initialization_kind']).size().reset_index(name='contexts').to_dict('records'),
            fixed_support_contexts=per.context_key.nunique(),fixed_support_unique_context_splits=fixed[['context_key','split_id']].drop_duplicates().shape[0],
            aggregation='context内先平均重复划分，再对context等权；初始化分层为对既有结果的描述性细化，不改变划分或拟合')
    (out/'REPORT_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--out',type=Path)
    a=p.parse_args();build(a.root,a.out or a.root/OUTPUT)
