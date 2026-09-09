"""回读逐人稳定性与全部分图预测；生成黑灰统计图及可追溯实例。"""
import json
import math
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'analysis_results/unb9_scene_transfer_trial_20260909_v1'
OUT=BASE/'stability'


def main():
    prefix=pd.read_csv(OUT/'all_integer_prefixes.csv.gz')
    records=pd.read_csv(OUT/'stability_records.csv.gz')
    curves=pd.read_csv(OUT/'stability_curves.csv')
    onsets=pd.read_csv(OUT/'image_onset_candidates.csv')
    support=pd.read_csv(OUT/'support.csv.gz')
    workers=pd.read_csv(BASE/'worker_splits.csv.gz').set_index(['image_id','scheme','replicate'])
    assert (records.k<=records.horizon-3).all()
    assert not prefix.duplicated(['image_id','scheme','replicate','tau','k']).any()
    assert not records.duplicated(['image_id','scheme','replicate','tau','horizon','k']).any()
    expected={key:json.loads(row.history_ids_json) for key,row in workers.iterrows()}
    parts={}
    for r in prefix.itertuples():
        g=json.loads(r.clusters_json)
        if r.status=='unique':
            flat=[x for group in g for x in group]
            assert len(flat)==len(set(flat))==r.k and set(flat)==set(expected[(r.image_id,r.scheme,r.replicate)][:r.k])
        parts[(r.image_id,r.scheme,r.replicate,r.tau,r.k)]=(r.status,g)
    error=0.
    sample=records.sample(900,random_state=20260909)
    for r in sample.itertuples():
        trajectory=[parts[(r.image_id,r.scheme,r.replicate,r.tau,k)] for k in range(r.k,r.horizon+1)]
        if any(status!='unique' for status,g in trajectory):
            assert r.status=='unresolved';continue
        assert r.status=='evaluated'
        earlier=trajectory[0][1];old={x for g in earlier for x in g}
        before={frozenset((a,b)) for g in earlier for a,b in combinations(g,2)}
        changes=[]
        for j,(_,groups) in enumerate(trajectory[1:],r.k+1):
            after={frozenset((a,b)) for g in groups for a,b in combinations(set(g)&old,2)}
            changes.append((len(before^after)/math.comb(r.k,2) if r.k>1 else 0,
                sum(abs(len(old&set(g))/r.k-len(g)/j) for g in groups)/2,
                sum(len(g)>=2 and not old&set(g) for g in groups)))
        actual=np.max(changes,axis=0)
        observed=np.array([r.max_membership_change,r.max_share_change,r.max_new_supported_clusters])
        error=max(error,float(np.max(abs(actual-observed))))
    assert error<1e-12
    groupkeys=['image_id','scheme','tau','horizon','k']
    for eps in [5,10,20]:
        state=records['state_'+str(eps)];confirmed=records['confirmed_'+str(eps)]
        assert set(state)<={'stable','changing','unknown'}
        assert ((confirmed!='stable')|(state=='stable')).all()
        assert (state.eq('unknown')==records.status.eq('unresolved')).all()
        expected_stable=(records.status.eq('evaluated')&(records.max_membership_change<=eps/100+1e-12)
            &(records.max_share_change<=eps/100+1e-12)&records.max_new_supported_clusters.eq(0))
        assert state.eq('stable').equals(expected_stable)
        expected_confirmed=np.where(state.eq('changing'),'changing',np.where(state.eq('unknown')|records.joint_status.ne('unique'),'unknown',
            np.where((records.joint_membership_change<=eps/100+1e-12)&(records.joint_share_change<=eps/100+1e-12)&records.joint_new_supported_clusters.eq(0),'stable','changing')))
        assert np.array_equal(confirmed,expected_confirmed)
        agg=records.assign(st=state.eq('stable'),un=state.eq('unknown'),co=confirmed.eq('stable')).groupby(groupkeys).agg(
            stable=('st','sum'),unknown=('un','sum'),replicates=('st','size'),confirmed=('co','sum'))
        saved=curves[curves.tolerance_pp==eps].set_index(groupkeys).loc[agg.index]
        assert np.array_equal(agg[['stable','unknown','replicates']],saved[['stable','unknown','replicates']])
        for values,column in [(agg.stable/agg.replicates,'stable_lower'),((agg.stable+agg.unknown)/agg.replicates,'stable_upper'),(agg.confirmed/agg.replicates,'validation_confirmed_lower')]:
            assert np.allclose(values,saved[column],atol=1e-12,rtol=0)
        assert (saved.stable==saved.stable_single+saved.stable_multi).all()
    for r in onsets.itertuples():
        g=curves[(curves.image_id==r.image_id)&(curves.scheme==r.scheme)&(curves.tau==r.tau)&
            (curves.horizon==r.horizon)&(curves.tolerance_pp==r.tolerance_pp)].sort_values('k')
        lower=g[g.stable_lower>=r.repeat_rate-1e-12];upper=g[g.stable_upper>=r.repeat_rate-1e-12]
        if len(lower):assert r.status=='observed_candidate' and r.onset==lower.k.iloc[0]
        elif len(upper):assert r.status=='unresolved_partitions' and pd.isna(r.onset)
        else:assert r.status=='not_reached_in_window' and pd.isna(r.onset)
    print('完成全部前缀身份、曲线汇总、候选人数回读及900个窗口独立复算',flush=True)

    pred=pd.read_csv(OUT/'image_group_stability_predictions.csv.gz')
    folds=pd.read_csv(BASE/'image_splits.csv');folds=folds[folds.panel=='dense12'].set_index('fold_id')
    images=sorted(curves.image_id.unique());pos={im:i for i,im in enumerate(images)}
    source=np.zeros((len(folds),len(images)))
    for n,r in enumerate(folds.itertuples()):
        a,b=json.loads(r.source_images_json),json.loads(r.target_images_json)
        assert not set(a)&set(b) and set(a+b)==set(images)
        source[n,[pos[im] for im in a]]=1
    target=1-source;sn=source.sum(axis=1);tn=target.sum(axis=1)
    count=0;pred_error=0.
    for key,g in pred.groupby(['scheme','tau','horizon','tolerance_pp','repeat_rate']):
        scheme,tau,L,eps,rate=key;g=g.set_index('fold_id').loc[folds.index]
        c=curves[(curves.scheme==scheme)&(curves.tau==tau)&(curves.horizon==L)&(curves.tolerance_pp==eps)]
        lower=c.pivot(index='image_id',columns='k',values='stable_lower').loc[images].to_numpy()
        upper=c.pivot(index='image_id',columns='k',values='stable_upper').loc[images].to_numpy()
        confirmed=c.pivot(index='image_id',columns='k',values='validation_confirmed_lower').loc[images].to_numpy()
        prediction=source@lower/sn[:,None]
        error_each=np.abs(prediction[:,None,:]-lower[None,:,:]).mean(axis=2)
        error_image=(error_each*target).sum(axis=1)/tn
        error_group=np.abs(target@lower/tn[:,None]-prediction).mean(axis=1)
        pred_error=max(pred_error,float(np.max(abs(error_image-g.target_image_curve_MAE))),float(np.max(abs(error_group-g.target_group_curve_MAE))))
        reached=(prediction>=rate-1e-12).any(axis=1);j=(prediction>=rate-1e-12).argmax(axis=1)
        assert np.array_equal(reached,g.predicted_onset.notna())
        assert np.array_equal(j[reached]+1,g.predicted_onset.to_numpy()[reached])
        for matrix,col in [(lower>=rate-1e-12,'target_reached_fraction'),((lower<rate-1e-12)&(upper>=rate-1e-12),'target_unknown_fraction'),
            (lower,'target_stable_lower_at_prediction'),(confirmed,'validation_confirmed_lower_at_prediction')]:
            expected_value=(matrix[:,j].T*target).sum(axis=1)/tn
            if reached.any():pred_error=max(pred_error,float(np.max(abs(expected_value[reached]-g[col].to_numpy()[reached]))))
        actual=np.where((lower>=rate-1e-12).any(axis=1),(lower>=rate-1e-12).argmax(axis=1)+1,np.nan)
        for row,mask in zip(g.itertuples(),target.astype(bool)):
            observed=json.loads(row.target_onsets_json)
            assert observed==[int(n) if np.isfinite(n) else None for n in actual[mask]]
        count+=len(g)
    assert pred_error<1e-12 and count==len(pred)
    print(f'完成全部{count}条分图预测回读',flush=True)

    multi=records.merge(prefix[['image_id','scheme','replicate','tau','k','supported_clusters']],on=['image_id','scheme','replicate','tau','k'],validate='many_to_one')
    detail=[]
    for eps in [5,10,20]:
        g=multi.assign(historical=(multi['state_'+str(eps)]=='stable')&(multi.supported_clusters>=2),
            confirmed=(multi['confirmed_'+str(eps)]=='stable')&(multi.supported_clusters>=2))
        s=g.groupby(groupkeys).agg(replicates=('k','size'),stable_with_two_supported_clusters=('historical','sum'),confirmed_with_two_supported_clusters=('confirmed','sum')).reset_index()
        s['tolerance_pp']=eps;detail.append(s)
    pd.concat(detail).to_csv(OUT/'multicluster_support_counts.csv',index=False)

    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
    figures=OUT/'figures';figures.mkdir(exist_ok=True)
    labels={im:f'{i+1:02d}' for i,im in enumerate(images)}
    main_curves=curves[(curves.scheme=='two_thirds')&(curves.horizon==15)&(curves.tau==6)&(curves.tolerance_pp==10)]
    fig,axes=plt.subplots(3,4,figsize=(13,8.8),sharex=True,sharey=True,layout='constrained')
    for ax,im in zip(axes.flat,images):
        g=main_curves[main_curves.image_id==im].sort_values('k')
        ax.fill_between(g.k,g.stable_lower,g.stable_upper,color='.85',label='含未判定的上界范围')
        ax.plot(g.k,g.stable_lower,'k-',label='历史窗口内确定稳定比例')
        ax.plot(g.k,g.validation_confirmed_lower,'k--',label='加留出人员后仍确定稳定')
        ax.axhline(.8,color='.5',linestyle=':',linewidth=.8)
        ax.set_title(f'{labels[im]} · 可用排列 {g.replicates.iloc[0]} / 200')
        ax.set(ylim=(-.02,1.03),xticks=[1,4,8,12]);ax.grid(alpha=.15)
    handles,names=axes[0,0].get_legend_handles_labels()
    axes[0,0].legend(handles,names,loc='upper left',fontsize=7)
    fig.supxlabel('候选起点人数 k（逐人检查其后至15人，至少保留3人）')
    fig.supylabel('占本图人数合格排列的比例')
    fig.suptitle('12图逐人稳定回放｜2/3历史人员；6度分簇；变化容差10个百分点\n灰带表示分区未唯一确定造成的范围，不是置信区间')
    fig.savefig(figures/'per_image_stability.png',dpi=160);plt.close(fig)

    q=onsets[(onsets.scheme=='two_thirds')&(onsets.horizon==15)&(onsets.repeat_rate==.8)]
    columns=[(tau,eps) for tau in [3,6,12] for eps in [5,10,20]]
    values=np.full((12,9),np.nan);texts=np.empty((12,9),dtype=object)
    for i,im in enumerate(images):
        for j,(tau,eps) in enumerate(columns):
            r=q[(q.image_id==im)&(q.tau==tau)&(q.tolerance_pp==eps)].iloc[0]
            values[i,j]=r.onset
            texts[i,j]=str(int(r.onset)) if pd.notna(r.onset) else '?' if r.status=='unresolved_partitions' else '未达'
    fig,ax=plt.subplots(figsize=(11,6.5),layout='constrained')
    ax.imshow(np.nan_to_num(values,nan=0),cmap='Greys',vmin=0,vmax=28,aspect='auto')
    for i in range(12):
        for j in range(9):ax.text(j,i,texts[i,j],ha='center',va='center',color='black')
    ax.set(xticks=range(9),xticklabels=[f'{tau}度\n容差{eps}pp' for tau,eps in columns],yticks=range(12),yticklabels=[labels[i] for i in images],ylabel='图号')
    ax.set_title('候选稳定起点对参数的敏感性｜2/3历史人员，观察至15人，80%重复率\n数字=历史稳定下界首次达到80%的k；?=分区未定；未达=本窗口上界也未达到')
    fig.savefig(figures/'onset_sensitivity.png',dpi=160);plt.close(fig)

    summary=pd.read_csv(OUT/'transfer_summary.csv')
    fig,axes=plt.subplots(1,2,figsize=(11,4.8),sharey=True,layout='constrained')
    for ax,eps in zip(axes,[10,20]):
        g=summary[(summary.scheme=='two_thirds')&(summary.horizon==15)&(summary.tau==6)&(summary.repeat_rate==.8)&(summary.tolerance_pp==eps)].sort_values('source_n')
        ax.plot(g.source_n,g.prediction_reached_fraction,'ko-',label='全部分图：源组能给出候选人数')
        ax.plot(g.source_n,g.target_reached_fraction,'ks--',label='给出人数时：目标图确定达到比例')
        ax.plot(g.source_n,g.target_unknown_fraction,':',color='.5',label='给出人数时：目标图未判定比例')
        ax.set(title=f'变化容差 {eps} 个百分点',xlabel='源图数量（目标图为其余12−源图数）',ylim=(-.02,1.03),xticks=[1,2,4,6,8,10,11]);ax.grid(alpha=.2)
    axes[0].set_ylabel('比例（实线与虚线分母不同，见图例）');axes[1].legend(fontsize=8,loc='upper right')
    fig.suptitle('同楼跨图人数预测｜6度分簇、2/3历史人员、观察至15人、80%重复率')
    fig.savefig(figures/'image_transfer.png',dpi=160);plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(11,4.7),layout='constrained');examples=[]
    for ax,im,tau,eps,k,kind in zip(axes,[images[1],images[4]],[12,6],[10,10],[1,12],['早期单簇','持续多簇']):
        g=records[(records.image_id==im)&(records.scheme=='two_thirds')&(records.horizon==15)&(records.tau==tau)&(records.k==k)&records['confirmed_'+str(eps)].eq('stable')]
        if kind=='持续多簇':
            g=g[g.apply(lambda r:sum(len(c)>=2 for c in parts[(im,'two_thirds',r.replicate,tau,k)][1])>=2,axis=1)]
        r=g.sort_values('replicate').iloc[0]
        h=expected[(im,'two_thirds',r.replicate)];final=parts[(im,'two_thirds',r.replicate,tau,15)][1]
        shares=np.array([[len(set(h[:j])&set(c))/j for j in range(1,16)] for c in final])
        ax.stackplot(range(1,16),shares,colors=[str(.2+.65*i/max(1,len(final)-1)) for i in range(len(final))],labels=[f'簇{i+1}' for i in range(len(final))])
        ax.axvline(k,color='black',linestyle='--');ax.set(xlim=(1,15),ylim=(0,1),xlabel='人数',ylabel='各簇响应份额',title=f'{kind}：图{labels[im]}，排列{r.replicate}\n分簇{tau}度，候选k={k}（一个已观察排列）')
        ax.legend(loc='lower right',fontsize=8)
        examples.append(dict(image_id=im,plot_id=labels[im],replicate=int(r.replicate),tau=tau,tolerance_pp=eps,k=k,
            selection='在指定图/参数下，已被留出人员确认稳定的所需单/多簇状态中取最小排列编号；多簇须至少两个簇各有两人支持；事后解释实例，未参与主分析筛选',
            clusters_at_15=final,history_ids=h[:15],validation_ids=json.loads(workers.loc[(im,'two_thirds',r.replicate)].validation_ids_json),
            displayed_shares='只为显示比例，采用15人分类回看前缀；稳定判断实际来自各整数前缀独立分簇'))
    fig.suptitle('两条实际回放实例：单簇与多簇都可进入候选稳定状态\n图中按15人时分类显示份额；跨图簇编号不对应，未作布局正确性裁决')
    fig.savefig(figures/'single_multi_examples.png',dpi=160);plt.close(fig)
    (OUT/'EXAMPLES.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2),encoding='utf-8')
    qa=dict(status='passed',prefix_identity_rows=len(prefix),stability_rows=len(records),
        independently_recomputed_envelopes=len(sample),envelope_max_error=error,
        onset_candidates_read=len(onsets),prediction_rows_read=count,prediction_max_error=pred_error,
        curve_rows_read=len(curves),support_rows=len(support),all_source_target_disjoint=True,
        figures_generated=4,figure_visual_review='pending',raw_coordinates_changed=False,formal_protocol_changed=False)
    (OUT/'REVIEW_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
