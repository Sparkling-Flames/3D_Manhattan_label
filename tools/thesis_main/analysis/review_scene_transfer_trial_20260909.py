"""独立回读单楼预测，补等图数楼外对照和朴素统计图。"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linprog
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.trial_scene_transfer_20260909 import OUT, BUILDING


def reference_errors(predictions,targets):
    return np.abs(np.asarray(predictions)[:,None,:]-np.asarray(targets)[None,:,:]).mean(axis=2)


def main():
    inventory=pd.read_csv(OUT/'image_inventory.csv')
    external=pd.read_csv(OUT/'reference_image_inventory.csv')
    curves=pd.read_csv(OUT/'mean_curves.csv')
    folds=pd.read_csv(OUT/'image_splits.csv').set_index('fold_id')
    source={i:json.loads(r.source_images_json) for i,r in folds.iterrows()}
    target={i:json.loads(r.target_images_json) for i,r in folds.iterrows()}
    assert all(not set(source[i])&set(target[i]) for i in folds.index)
    assert len(folds[folds.panel=='dense12'])==4094
    pred=pd.read_csv(OUT/'group_predictions.csv.gz')
    supplements=[];reference_groups=[];error_max=0.
    for (scheme,window),p in pred.groupby(['scheme','window']):
        c=curves[(curves.scheme==scheme)&(curves.window==window)]
        vectors={i:g.sort_values('k')['mean'].to_numpy() for i,g in c.groupby('image_id')}
        ext=sorted(set(external.image_id)&set(vectors));local=sorted(set(inventory.image_id)&set(vectors))
        assert not set(ext)&set(local)
        ext_matrix=np.array([vectors[i] for i in ext]);local_matrix=np.array([vectors[i] for i in local])
        local_pos={i:j for j,i in enumerate(local)}
        for n,q in p.groupby('source_n'):
            rng=np.random.default_rng(20260909+1000*window+int(n))
            selected=np.array([rng.choice(len(ext),int(n),replace=False) for _ in range(200)])
            sampled_predictions=ext_matrix[selected].mean(axis=1)
            errors=reference_errors(sampled_predictions,local_matrix)
            for r,idx in enumerate(selected):
                reference_groups.append(dict(scheme=scheme,window=window,source_n=int(n),reference_repeat=r,
                    source_images_json=json.dumps([ext[j] for j in idx])))
            for row in q.itertuples():
                s,t=source[row.fold_id],target[row.fold_id]
                expected=np.mean([vectors[i] for i in s],axis=0)
                observed=np.array([vectors[i] for i in t])
                actual_error=np.abs(observed-expected).mean()
                base=np.mean(ext_matrix,axis=0)
                error_max=max(error_max,abs(actual_error-row.target_image_MAE),
                    abs(np.abs(observed-base).mean()-row.baseline_image_MAE),
                    float(np.max(abs(expected-json.loads(row.source_prediction_json)))))
                pos=[local_pos[i] for i in t]
                matched=errors[:,pos].mean(axis=1)
                group_errors=np.abs(sampled_predictions-observed.mean(axis=0)).mean(axis=1)
                supplements.append(dict(fold_id=row.fold_id,panel=row.panel,source_n=n,target_n=len(t),scheme=scheme,window=window,
                    same_building_image_MAE=actual_error,matched_external_image_MAE=matched.mean(),
                    matched_mae_gain=matched.mean()-actual_error,
                    same_building_group_MAE=row.target_group_MAE,matched_external_group_MAE=group_errors.mean(),
                    matched_reference_q10=float(np.quantile(matched,.1)),matched_reference_q90=float(np.quantile(matched,.9))))
    assert error_max<1e-10
    comparison=pd.DataFrame(supplements)
    comparison.to_csv(OUT/'matched_reference_predictions.csv.gz',index=False)
    pd.DataFrame(reference_groups).to_csv(OUT/'matched_reference_image_groups.csv.gz',index=False)
    comparison['better_than_matched_mean']=comparison.matched_mae_gain>0
    summary=comparison.groupby(['panel','source_n','target_n','scheme','window']).agg(
        image_splits=('fold_id','size'),same_building_image_MAE=('same_building_image_MAE','mean'),
        matched_external_image_MAE=('matched_external_image_MAE','mean'),matched_mae_gain=('matched_mae_gain','mean'),
        same_building_group_MAE=('same_building_group_MAE','mean'),matched_external_group_MAE=('matched_external_group_MAE','mean'),
        better_fraction=('better_than_matched_mean','mean')).reset_index()
    summary.to_csv(OUT/'matched_reference_summary.csv',index=False)

    # Separate LP solver checks observed transport values, not the expansion implementation.
    raw=pd.read_csv(OUT/'resampled_curves.csv.gz')
    people=pd.read_csv(OUT/'worker_splits.csv.gz').set_index(['image_id','scheme','replicate'])
    pairs=pd.read_csv(ROOT/'analysis_results/order_free_cluster_holdout_20260908_v1/pairwise_point_distances.csv.gz')
    d={(r.left_canonical,r.right_canonical):r.ospa30 for r in pairs.itertuples()}
    lp_max=0.
    for row in raw[raw.image_id.isin(inventory.image_id)].sample(24,random_state=20260909).itertuples():
        r=people.loc[row.image_id,row.scheme,row.replicate]
        h=json.loads(r.history_ids_json)[:row.k];v=json.loads(r.validation_ids_json)
        cost=np.array([[d[(x,y)] if (x,y) in d else d[(y,x)] for y in v] for x in h])
        n,m=cost.shape
        a=np.zeros((n+m,n*m))
        for i in range(n):a[i,i*m:(i+1)*m]=1
        for j in range(m):a[n+j,j::m]=1
        answer=linprog(cost.ravel(),A_eq=a,b_eq=[1/n]*n+[1/m]*m,bounds=(0,None),method='highs')
        assert answer.success
        lp_max=max(lp_max,abs(answer.fun-row.transport_degrees))
    assert lp_max<1e-9

    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
    figures=OUT/'figures';figures.mkdir(exist_ok=True)
    dense=inventory[inventory.dense].sort_values('image_id')
    image_labels={i:f'{j+1:02d}' for j,i in enumerate(dense.image_id)}
    dense=dense.assign(plot_id=dense.image_id.map(image_labels))
    dense.to_csv(OUT/'figure_image_key.csv',index=False)
    fig,axes=plt.subplots(3,4,figsize=(13,8),sharex=True,sharey=True,layout='constrained')
    scheme_labels={'two_thirds':'2/3历史','sixty_percent':'60%历史','half':'50%历史'}
    for ax,im in zip(axes.flat,dense.image_id):
        for scheme,style in [('two_thirds','-'),('sixty_percent','--'),('half',':')]:
            g=curves[(curves.image_id==im)&(curves.scheme==scheme)&(curves.window==10)].sort_values('k')
            ax.plot(g.k,g['mean'],style,color='black',label=scheme_labels[scheme])
        ax.set_title(f'{image_labels[im]} · {im[-6:]}');ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8)
    fig.supxlabel('前缀人数 k（共同检查到10人）');fig.supylabel('与验证回答分布的平均运输差异（度）')
    fig.suptitle('同楼12张高人数图：各图均使用200次人数合格排列；不按阶段分组')
    fig.savefig(figures/'twelve_image_curves.png',dpi=160);plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
    q=summary[(summary.panel=='dense12')&(summary.scheme=='two_thirds')&(summary.window==10)].sort_values('source_n')
    original=pd.read_csv(OUT/'prediction_summary.csv')
    old=original[(original.panel=='dense12')&(original.scheme=='two_thirds')&(original.window==10)].sort_values('source_n')
    for ax,outcome,title in [(axes[0],'image','逐张目标图误差'),(axes[1],'group','目标组平均曲线误差')]:
        ax.plot(q.source_n,q['same_building_'+outcome+'_MAE'],'o-',color='black',label='同楼源图均值')
        ax.plot(q.source_n,q['matched_external_'+outcome+'_MAE'],'s--',color='.4',label='同图数楼外抽样（200组）')
        ax.plot(old.source_n,old['baseline_'+outcome+'_MAE'],':',color='.6',label='全部有支持的楼外图均值')
        ax.set(xlabel='源图数量（目标图为其余12−源图数）',ylabel='平均绝对误差（度）',title=title);ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('2/3历史人员、2–10人窗口；相同源图数比较，全部有向分图等权')
    fig.savefig(figures/'prediction_error_comparison.png',dpi=160);plt.close(fig)

    q=comparison[(comparison.panel=='dense12')&(comparison.scheme=='two_thirds')&(comparison.window==10)&(comparison.source_n==6)].copy()
    q=q.sort_values(['same_building_group_MAE','fold_id'])
    chosen=[q.iloc[0],q.iloc[len(q)//2],q.iloc[-1]]
    fig,axes=plt.subplots(1,3,figsize=(12,4.5),sharey=True,layout='constrained')
    ex=[]
    for ax,r,label in zip(axes,chosen,['组均值误差最小','组均值误差居中','组均值误差最大']):
        fid=int(r.fold_id);s=source[fid];t=target[fid]
        c=curves[(curves.scheme=='two_thirds')&(curves.window==10)]
        vm={i:g.sort_values('k')['mean'].to_numpy() for i,g in c.groupby('image_id')}
        nodes=sorted(c.k.unique())
        for im in t:ax.plot(nodes,vm[im],color='.75',linewidth=.7)
        ax.plot(nodes,np.mean([vm[i] for i in s],axis=0),'k--',linewidth=2,label='源组给出的预测')
        ax.plot(nodes,np.mean([vm[i] for i in t],axis=0),'k-',linewidth=2,label='目标组实际均值')
        ax.set_title(label+f'\n组误差 {r.same_building_group_MAE:.3f}，逐图误差 {r.same_building_image_MAE:.3f}')
        ax.set_xlabel('人数 k');ax.grid(alpha=.2)
        ex.append(dict(selection=label,fold_id=fid,source=[image_labels[i] for i in s],target=[image_labels[i] for i in t]))
    axes[0].set_ylabel('分布差异（度）');axes[0].legend(fontsize=8)
    fig.suptitle('6图→6图：按已观察到的组误差选取三个说明实例，不用于筛选主结果')
    fig.savefig(figures/'group_examples.png',dpi=160);plt.close(fig)
    (OUT/'FIGURE_EXAMPLES.json').write_text(json.dumps(ex,ensure_ascii=False,indent=2),encoding='utf-8')
    qa=dict(status='passed',prediction_rows_read_back=len(pred),prediction_max_error=error_max,
        independent_LP_checks=24,transport_max_error=lp_max,reference_groups=len(reference_groups),
        reference_source_count_matched=True,stage_used_for_reference_selection=False,figures_generated=3,
        figure_selection='6/6组均值误差最小/居中/最大，仅解释性事后示例，非主结果筛选')
    (OUT/'REVIEW_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=True))


if __name__=='__main__':main()
