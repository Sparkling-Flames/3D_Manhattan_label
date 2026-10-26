"""Figures and per-image precision of the four inherited entry policies.

Uses completed paired old16/new16/pooled32 analysis only. No new classification,
ordering, policy search, endpoint evaluation, or bootstrap is performed here.
"""
from pathlib import Path
import argparse,sys,os,json
for env in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[env]='1'
import numpy as np
import pandas as pd
import analyze_policy32 as P

LABELS={'joint_highq_first':'历史联合高Q优先','structure_moreturn_first':'历史较多转折优先',
        'joint_fast_first':'历史联合快速优先','structure_dominant_first':'历史主流表达优先'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    args=ap.parse_args();base=args.base.resolve();root=base/'analysis_policy26'
    summary=pd.read_csv(root/'results/POLICY_PRECISION_SUMMARY.csv')
    meta=pd.read_csv(root/'COMMON_IMAGES.csv');assert len(meta)==157
    out=root/'presentation';out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for row in meta.itertuples(index=False):
        with np.load(root/'parts'/row.pool_id/'PATH_BOOTSTRAP_CACHE.npz') as z:
            for policy in P.F.POLICIES:
                for version in P.VERSIONS:
                    point=z[policy+'__'+version+'__point']
                    b=z[policy+'__'+version+'__boot']
                    for ph,phase in enumerate(P.F.PHASES):
                        x=b[:,ph,0];x=x[np.isfinite(x)]
                        lo,hi=np.quantile(x,[.025,.975]) if len(x) else (np.nan,np.nan)
                        rows.append(dict(**row._asdict(),policy=policy,role_zh=LABELS[policy],
                            role_version='historical V3 roles; not DSTRUCT/RFUSE',version=version,phase=phase,
                            paired_Q_delta=float(point[ph,0]),Q_path_MCSE=float(np.std(x,ddof=1)) if len(x)>1 else np.nan,
                            Q_path95_low=lo,Q_path95_high=hi,Q_path95_halfwidth=(hi-lo)/2,
                            valid_path_resamples=len(x),requested_path_resamples=b.shape[0],
                            interval_complete_support=len(x)==b.shape[0],
                            Q_interval_positive=bool(lo>0),Q_interval_negative=bool(hi<0)))
    per=pd.DataFrame(rows);P.save(per,out/'POLICY_PER_IMAGE_Q_PRECISION.csv.gz')
    compare=[];counts=[]
    for policy in P.F.POLICIES:
        for phase in P.F.PHASES:
            h=per[per.policy.eq(policy)&per.phase.eq(phase)]
            for version in P.VERSIONS:
                g=h[h.version.eq(version)];q=g[g.paired_Q_delta.notna()]
                counts.append(dict(policy=policy,role_zh=LABELS[policy],phase=phase,version=version,
                    candidate_images=len(g),Q_images=len(q),buildings=q.building.nunique(),
                    median_Q_path_MCSE=q.Q_path_MCSE.median(),P90_Q_path_MCSE=q.Q_path_MCSE.quantile(.9),
                    images_MCSE_gt1=int(q.Q_path_MCSE.gt(1).sum()),
                    median_Q_path95_halfwidth=q.Q_path95_halfwidth.median(),
                    images_incomplete_bootstrap_support=int((~q.interval_complete_support).sum()),
                    positive_point_images=int(q.paired_Q_delta.gt(1e-9).sum()),
                    negative_point_images=int(q.paired_Q_delta.lt(-1e-9).sum()),
                    nearzero_point_images=int(q.paired_Q_delta.abs().le(1e-9).sum()),
                    positive_interval_images_complete_draws=int((q.Q_interval_positive&q.interval_complete_support).sum()),
                    negative_interval_images_complete_draws=int((q.Q_interval_negative&q.interval_complete_support).sum())))
            a=h[h.version.eq('old16')].set_index('pool_id');b=h[h.version.eq('new16')].set_index('pool_id')
            c=h[h.version.eq('pooled32')].set_index('pool_id');ids=a.index.intersection(b.index).intersection(c.index)
            for pid in ids:
                x,y,z=a.loc[pid],b.loc[pid],c.loc[pid]
                if not np.isfinite([x.paired_Q_delta,y.paired_Q_delta,z.paired_Q_delta]).all():continue
                sx=0 if abs(x.paired_Q_delta)<=1e-9 else np.sign(x.paired_Q_delta)
                sy=0 if abs(y.paired_Q_delta)<=1e-9 else np.sign(y.paired_Q_delta)
                status=('both_nearzero' if abs(x.paired_Q_delta)<=1e-9 and abs(y.paired_Q_delta)<=1e-9 else
                        'both_change_same_direction' if sx==sy and abs(x.paired_Q_delta)>1e-9 and abs(y.paired_Q_delta)>1e-9 else
                        'opposite_nonzero' if sx*sy<0 else 'one_nearzero')
                compare.append(dict(pool_id=pid,image=x.image,building=x.building,difficulty=x.difficulty,
                    policy=policy,role_zh=LABELS[policy],phase=phase,old16_Q=x.paired_Q_delta,new16_Q=y.paired_Q_delta,
                    pooled32_Q=z.paired_Q_delta,independent_new_minus_old=y.paired_Q_delta-x.paired_Q_delta,
                    sign_status_zero_tolerance_1e_9=status,
                    old16_MCSE=x.Q_path_MCSE,pooled32_MCSE=z.Q_path_MCSE,
                    MCSE_ratio_32_over16=z.Q_path_MCSE/x.Q_path_MCSE if x.Q_path_MCSE>0 else np.nan))
    P.save(pd.DataFrame(counts),out/'POLICY_PRECISION_COUNTS.csv')
    compare=pd.DataFrame(compare);P.save(compare,out/'POLICY_INDEPENDENT_BATCH_PER_IMAGE.csv.gz')
    cs=[]
    for (policy,phase),g in compare.groupby(['policy','phase']):
        s=g.sign_status_zero_tolerance_1e_9.value_counts().to_dict()
        cs.append(dict(policy=policy,role_zh=LABELS[policy],phase=phase,images=len(g),buildings=g.building.nunique(),
            old16_mean=g.old16_Q.mean(),new16_mean=g.new16_Q.mean(),pooled32_mean=g.pooled32_Q.mean(),
            median_MCSE_ratio_32_over16=g.MCSE_ratio_32_over16.median(),
            mean_abs_independent_batch_Q_difference=g.independent_new_minus_old.abs().mean(),
            P90_abs_independent_batch_Q_difference=g.independent_new_minus_old.abs().quantile(.9),
            both_positive_images=int((g.old16_Q.gt(1e-9)&g.new16_Q.gt(1e-9)).sum()),
            both_negative_images=int((g.old16_Q.lt(-1e-9)&g.new16_Q.lt(-1e-9)).sum()),
            opposite_nonzero_images=s.get('opposite_nonzero',0),both_nearzero_images=s.get('both_nearzero',0),
            one_nearzero_images=s.get('one_nearzero',0),
            old_new_both_abs_gt1_opposite_images=int(((g.old16_Q*g.new16_Q<0)&g.old16_Q.abs().gt(1)&g.new16_Q.abs().gt(1)).sum())))
    P.save(pd.DataFrame(cs),out/'POLICY_INDEPENDENT_BATCH_SUMMARY.csv')
    # Compact display; all source rows remain downloadable.
    sys.path.insert(0,str(base/'analysis_precision26'))
    from plot_natural_precision import style,export
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    style(base)
    metrics=[('paired_Q_delta','Q：策略−同基准自然顺序',0,1),
        ('Q_p10_delta_common','同路径可评支持上的P10差',0,1),
        ('actual_consensus_failure_delta','共识未形成率差（百分点）',0,100),
        ('Q_sd_delta_common_ddof1','换队Q标准差之差',0,1),
        ('QT_paired_Q_delta','合法Q/T共同支持上的Q差',0,1),
        ('labor_ratio_legal','合法Q/T共同支持上的劳动比',1,1)]
    fig,axes=plt.subplots(2,3,figsize=(15,8.7));colors={'old16':'#66717e','new16':'#247ba0','pooled32':'#28784b'}
    legends={'old16':'旧16对','new16':'独立新16对','pooled32':'合并32对'}
    used=[]
    for ax,(metric,title,ref,scale) in zip(axes.ravel(),metrics):
        for vi,version in enumerate(P.VERSIONS):
            g=summary[summary.version.eq(version)&summary.phase.eq('early_3_to_half')&summary.difficulty.eq('全部')&
                summary.weighting.eq('image_equal')&summary.metric.eq(metric)].set_index('policy').reindex(P.F.POLICIES)
            if g.empty:continue
            used.append(g.reset_index());y=np.arange(4)+(vi-1)*.19
            # Building intervals (pale, broad) and conditional path ranges
            # (coloured) are separate uncertainty sources, not a combined CI.
            for j,(pol,r) in enumerate(g.iterrows()):
                ax.hlines(y[j],r.building_lo*scale,r.building_hi*scale,color=colors[version],alpha=.18,lw=5)
                ax.hlines(y[j],r.path_lo*scale,r.path_hi*scale,color=colors[version],lw=1.6)
            ax.scatter(g.estimate*scale,y,s=24,color=colors[version],label=legends[version],zorder=3)
        ax.axvline(ref,color='#737373',ls=':',lw=1);ax.set_title(title)
        ax.set_yticks(np.arange(4),[LABELS[x] for x in P.F.POLICIES]);ax.invert_yaxis();ax.grid(axis='y',visible=False)
    axes[0,0].legend(loc='best',fontsize=8)
    fig.suptitle('历史进入策略：前段3人至半池，16→32对完整配对路径',fontsize=16,y=.995)
    fig.text(.015,.012,'157个既有策略池、22栋楼；不同指标使用各自固定共同支持，精确图数见附表。各策略来自旧V3角色，不是新DSTRUCT/RFUSE验证。\n'
        '彩色细线：固定图片中的配对路径重抽95%范围；浅色宽线：整栋建筑重抽范围。两种范围分别解释，不叠加为一个区间。\n'
        '自然与优先策略共享同一基础顺序，四策略共用该配对抽样。劳动比是合资格逐路径比值均值，不是交付时间比或金钱成本比。',fontsize=9,va='bottom')
    fig.tight_layout(rect=[0,.115,1,.955]);paths=export(fig,out,'P01_历史策略独立追加与精度')
    P.save(pd.concat(used,ignore_index=True),out/'P01_SOURCE_ROWS.csv')
    P.atomic_bytes(out/'RECEIPT.json',json.dumps(dict(complete=True,images=len(meta),new_orders=0,new_endpoints=0,
        source_analysis='analysis_policy26/results and original bootstrap caches',figures=paths,
        no_claim_of_new_DSTRUCT_or_RFUSE_validation=True,zero_sign_tolerance=1e-9)).encode())
    print('Policy precision presentation complete',flush=True)


if __name__=='__main__':main()
