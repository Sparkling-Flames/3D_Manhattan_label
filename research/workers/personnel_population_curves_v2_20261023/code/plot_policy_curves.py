"""Fixed-support, image-equal process plots; every displayed point is saved."""
from __future__ import annotations
import argparse,json,os
from pathlib import Path
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_population_matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from register_population_orders import save_csv,write_bytes

POLICIES=['structure_moreturn_first','structure_dominant_first','joint_highq_first','joint_fast_first']
NAMES={'structure_moreturn_first':'More-turn history first',
       'structure_dominant_first':'Largest historical structure class first',
       'joint_highq_first':'High-Q role first','joint_fast_first':'Fast role first'}
COLORS={'structure_moreturn_first':'#c45a24','structure_dominant_first':'#777777',
        'joint_highq_first':'#007a88','joint_fast_first':'#8055a3'}


def aggregate_curves(d):
    rows=[]
    common=set(d.groupby('pool_id').policy.nunique().loc[lambda x:x.eq(4)].index)
    for condition in ['manual','semi']:
        basic=d[(d.condition==condition)&(d.layer=='ordinary_'+condition)&d.pool_n.ge(20)&d.k.le(20)]
        for cohort,g in [('all_four_common_Nge20',basic[basic.pool_id.isin(common)]),
                         ('all_four_common_Nge20_time_complete',basic[basic.pool_id.isin(common)&basic.pool_source_time_complete])]:
            for stratum in ['all','difficulty']:
                keys=['policy','k']+([] if stratum=='all' else ['difficulty'])
                for key,h in g.groupby(keys,dropna=False):
                    meta=dict(zip(keys,key),condition=condition,cohort=cohort,stratum=stratum)
                    row=dict(meta,images=h.image.nunique(),buildings=h.building.nunique(),
                             images_Qpaired=int(h.Q_mean_delta.notna().sum()),
                             images_Qup=int(h.Q_mean_delta.gt(0).sum()),
                             paired_Q=int(h.paired_Q.sum()),paired_paths=int(h.paired_paths.sum()),
                             priority_unique_sets=int(h.priority_unique_teams.sum()),
                             priority_fixed_set_images=int(h.priority_fixed_membership.sum()),
                             priority_variance_estimable_images=int(h.priority_variance_estimable.sum()))
                    for c in ['Q_natural_mean','Q_priority_mean','Q_mean_delta','Q_p10_delta','Q_sd_delta',
                              'Q_natural_p10','Q_priority_p10','Q_natural_sd','Q_priority_sd',
                              'score_failure_nonpolicy_natural_rate','score_failure_nonpolicy_priority_rate',
                              'score_failure_nonpolicy_delta','source_time_logratio','actual_m_mean',
                              'target_seat_change_mean','Q_loss_gt5_fraction']:
                        row[c]=h[c].mean()
                        row[c+'_valid_images']=h[c].notna().sum()
                    row['source_time_pct_change']=100*np.expm1(row['source_time_logratio'])
                    rows.append(row)
    return pd.DataFrame(rows)


def draw(curves,out):
    plt.rcParams.update({'font.size':10,'axes.titlesize':12,'axes.labelsize':10,'figure.dpi':150,
                         'axes.spines.top':False,'axes.spines.right':False,'savefig.bbox':'tight'})
    cohort='all_four_common_Nge20'
    d=curves[(curves.cohort==cohort)&(curves.stratum=='all')]
    fig,axes=plt.subplots(4,2,figsize=(13,13),sharex=True)
    for col,condition in enumerate(['manual','semi']):
        h=d[d.condition==condition]
        timed=curves[(curves.condition==condition)&(curves.cohort=='all_four_common_Nge20_time_complete')&(curves.stratum=='all')]
        for policy in POLICIES:
            g=h[h.policy==policy].sort_values('k')
            for row,yname in enumerate(['Q_mean_delta','Q_p10_delta','score_failure_nonpolicy_delta','source_time_pct_change']):
                source=timed[timed.policy==policy].sort_values('k') if row==3 else g
                x=source.k.to_numpy();y=source[yname].to_numpy().copy()
                if yname=='score_failure_nonpolicy_delta':y*=100
                if yname!='source_time_pct_change':y[x==2]=np.nan
                axes[row,col].plot(x,y,label=NAMES[policy],color=COLORS[policy],lw=2,marker='o',markersize=2.8)
        n=int(h.images.max()) if len(h) else 0;b=int(h.buildings.max()) if len(h) else 0
        axes[0,col].set_title(f'{condition.title()}: fixed {n} images, {b} buildings')
        nt=int(timed.images.max()) if len(timed) else 0;bt=int(timed.buildings.max()) if len(timed) else 0
        axes[3,col].set_title(f'Time-supported subset: {nt} images, {bt} buildings',fontsize=10)
        for row,label in enumerate(['Mean Q change','Empirical P10 Q change','Scoring-failure change (pp)','Recorded-time change (%)']):
            ax=axes[row,col];ax.axhline(0,color='#333333',lw=.7);ax.grid(alpha=.2);ax.set_ylabel(label)
            ax.set_xlim(1,20);ax.set_xticks([1,3,6,10,15,20])
        axes[-1,col].set_xlabel('Prefix size k (same full pool, N >= 20)')
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,ncol=2,loc='upper center',bbox_to_anchor=(.5,1.01),frameon=False)
    fig.suptitle('Category-priority order minus its paired natural order',y=1.045,fontsize=15)
    fig.tight_layout()
    fig.savefig(out/'POLICY_PROCESS_DIFFERENCES.png');fig.savefig(out/'POLICY_PROCESS_DIFFERENCES.pdf');plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(13,4.7),sharex=True)
    for col,condition in enumerate(['manual','semi']):
        h=d[d.condition==condition];baseline=h[h.policy==POLICIES[0]].sort_values('k')
        axes[col].plot(baseline.k,baseline.Q_natural_mean,color='black',ls='--',lw=2.2,marker='o',markersize=2.8,label='Paired natural order')
        for policy in POLICIES:
            g=h[h.policy==policy].sort_values('k')
            axes[col].plot(g.k,g.Q_priority_mean,color=COLORS[policy],lw=2,marker='o',markersize=2.8,label=NAMES[policy])
        axes[col].set(title=condition.title(),xlabel='Prefix size k',ylabel='Mean scorable B8L2 Q',xlim=(1,20))
        axes[col].set_xticks([1,3,6,10,15,20]);axes[col].grid(alpha=.2)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,ncol=2,loc='upper center',bbox_to_anchor=(.5,1.15),frameon=False)
    fig.tight_layout();fig.savefig(out/'POLICY_Q_CURVES.png');fig.savefig(out/'POLICY_Q_CURVES.pdf');plt.close(fig)

    z=curves[(curves.cohort=='all_four_common_Nge20')&(curves.stratum=='difficulty')&(curves.condition=='manual')]
    fig,axes=plt.subplots(1,3,figsize=(14,4.4),sharey=True)
    for ax,level,name in zip(axes,['简单','中等','困难'],['Easy','Medium','Difficult']):
        h=z[z.difficulty==level]
        for policy in POLICIES:
            g=h[h.policy==policy].sort_values('k')
            ax.plot(g.k,g.Q_mean_delta,color=COLORS[policy],lw=2,marker='o',markersize=2.8,label=NAMES[policy])
        n=int(h.images.max()) if len(h) else 0
        ax.set(title=f'{name}: {n} fixed images',xlabel='Prefix size k',xlim=(1,20));ax.axhline(0,color='#333',lw=.7);ax.grid(alpha=.2)
        ax.set_xticks([1,3,6,10,15,20])
    axes[0].set_ylabel('Q change vs paired natural order')
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,ncol=2,loc='upper center',bbox_to_anchor=(.5,1.15),frameon=False)
    fig.tight_layout();fig.savefig(out/'POLICY_MANUAL_DIFFICULTY.png');fig.savefig(out/'POLICY_MANUAL_DIFFICULTY.pdf');plt.close(fig)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--perk',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);d=pd.read_csv(a.perk,low_memory=False)
    curves=aggregate_curves(d);save_csv(curves,out/'POLICY_FIXED_PANEL_CURVES.csv')
    draw(curves,out)
    write_bytes(out/'POLICY_FIGURE_RECEIPT.json',json.dumps(dict(
        fixed_pool_size_support='N>=20, all four policy support; main Q/tail/failure panels use full common quality pool; time panel separately uses full-pool complete source time and prints its smaller support',
        weight='image equal after averaging paired paths per image/k',
        natural_baseline='same paired 8 orders used for each supported policy; N3 paths would be 6, but N>=20 plot has 8',
        full_pool_identity='all paths retain same final pool; early cost differences are not full-inventory time savings',
        k2='frozen deferred, excluded from Q/failed-fusion interpretation',
        tail='empirical 10th percentile of eight paths; not precise rare-event tail estimate'),ensure_ascii=False,indent=2).encode())


if __name__=='__main__':main()
