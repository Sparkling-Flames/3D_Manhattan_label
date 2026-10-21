"""Plot saved independent results; no refitting or target-based selection."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/same_room/same_room_independent_followup_20261021'
def main():
    c=pd.read_csv(OUT/'calibration/summary.csv')
    c=c[(c.metric=='B8L2')&(c.origin=='all')&(c.stage=='maximum_history')]
    methods=['same_person_source','observed_peer_plus_relative_clipped']
    fig,axs=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for ax,sub,title in zip(axs,['all','target_Q_below_50'],['All eligible targets','Retrospective target Q < 50']):
        p=c[c.subset==sub].set_index('method'); vals=[p.loc[m,'mae'] for m in methods]
        ax.bar(['Own source Q','Peer source +\nexternal relative Q'],vals,color=['#8396ad','#147d92'])
        for i,v in enumerate(vals):ax.text(i,v+.25,f'{v:.3f}',ha='center')
        ax.set_ylim(0,max(vals)*1.15);ax.set_ylabel('Mean absolute error (lower is better)');ax.set_title(title)
    fig.suptitle('Matched source-history calibration: mean gain does not imply low-tail detection')
    fig.savefig(OUT/'calibration_mean_and_lowtail.png',dpi=160);plt.close(fig)
    s=pd.read_csv(OUT/'stopping/summary.csv')
    s=s[(s.panel=='whole_group')&(s.horizon=='full_pool')&(s.history_budget=='minimum_majority')&(s.weighting=='building_equal')]
    fig,axs=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,support,title in zip(axs,['all_attempts','common_complete'],['All attempts: available-case Q + coverage','Conditional all-prefix-complete paths (75.52%)']):
        p=s[s.support==support].set_index('policy')
        for policy,label,col in [('source_within_0','within 0','#5c64a3'),('source_within_1','within 1','#467b63'),('source_within_2','within 2','#147d92'),('source_within_5','within 5','#b27624'),('fixed_7','fixed 7','#b94e48'),('terminal_pool','full pool','#505050')]:
            assert policy in p.index
            r=p.loc[policy];ax.scatter(r.mean_k,r.target_q_mean,color=col,s=50)
            suffix=f' ({r.target_complete_fraction*100:.1f}%)' if support=='all_attempts' else ''
            ax.annotate(label+suffix,(r.mean_k,r.target_q_mean),xytext=(3,5),textcoords='offset points',fontsize=8)
        ax.set_xlabel('Mean target persons (not labor time)');ax.set_ylabel('B8L2');ax.set_title(title);ax.grid(alpha=.2);ax.margins(.18)
    fig.suptitle('Source-only stopping; no target completion fallback; source acquisition cost excluded')
    fig.savefig(OUT/'stopping_budget_and_coverage.png',dpi=160);plt.close(fig)
if __name__=='__main__':main()

