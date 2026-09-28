"""Paper-ready historical diagnostic charts. No images interpreted. One axes per figure."""
from pathlib import Path
import json
import numpy as np,pandas as pd
import matplotlib.pyplot as plt
from history_analysis import next_uncovered

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/final_run';FIG=ROOT/'report/figures'

def save(fig,name):
    fig.tight_layout();fig.savefig(FIG/(name+'.png'),dpi=180);fig.savefig(FIG/(name+'.svg'));plt.close(fig)

def run():
    FIG.mkdir(parents=True,exist_ok=True)
    curves=pd.read_csv(OUT/'high_support_curve_summary.csv')
    fig,ax=plt.subplots(figsize=(8.4,4.8))
    for cut in [6,9,12]:
        d=curves[(curves.condition=='manual')&(curves.cut==cut)]
        ax.plot(d.k,100*d.next_uncovered,marker='o',markersize=3,label=f'{cut} degree endpoint threshold')
    ax.set(xlabel='Number of previously observed distinct people',ylabel='Next-person geometric noncoverage (%)',title='46 fixed high-support Manual images: threshold sensitivity',ylim=(0,100));ax.legend();ax.grid(alpha=.2);save(fig,'01_manual_growth_sensitivity')
    fig,ax=plt.subplots(figsize=(8.4,4.8))
    for cond in ['manual','semi','oos']:
        d=curves[(curves.condition==cond)&(curves.cut==9)]
        n=int(d.images.iloc[0])
        ax.plot(d.k,100*d.next_uncovered,marker='o',markersize=3,label=f'{cond.title()} ({n} images)')
    ax.set(xlabel='Number of previously observed distinct people',ylabel='Next-person geometric noncoverage (%)',title='Separate historical conditions, not a causal comparison',ylim=(0,100));ax.legend();ax.grid(alpha=.2);save(fig,'02_condition_growth')
    fig,ax=plt.subplots(figsize=(8.4,4.8))
    d=pd.read_csv(OUT/'novelty_decomposition_highN.csv');d=d[(d.condition=='manual')&(d.cut==9)]
    ax.plot(d.k,100*d.new_total_count,marker='o',label='A previously unseen total point count')
    ax.plot(d.k,100*d.new_geometry_or_order_given_known_role_counts,marker='o',label='Geometry/order beyond already seen role counts')
    ax.plot(d.k,100*d.new_role_count_given_known_total,marker='o',label='New role counts at a seen total count')
    ax.set(xlabel='Previously observed distinct people',ylabel='Probability contribution (percentage points)',title='Why another person is not covered: exact finite-pool decomposition');ax.legend();ax.grid(alpha=.2);save(fig,'03_novelty_decomposition')
    fig,ax=plt.subplots(figsize=(8.4,4.8))
    d=curves[(curves.condition=='manual')&(curves.cut==9)]
    ax.plot(d.k,100*d.unseen_mode_mass,marker='o',markersize=3,label='All full-pool groups not yet observed')
    ax.plot(d.k,100*d.minority_unseen_mass,marker='o',markersize=3,label='Repeated minority groups (2+ people, <=20%)')
    ax.set(xlabel='Distinct people sampled from the fixed pool',ylabel='Unseen full-pool response mass (%)',title='Retrospective group discovery; full-pool groups use hindsight');ax.legend();ax.grid(alpha=.2);save(fig,'04_retrospective_minority_coverage')
    cache=json.loads((OUT/'cache.json').read_text());fig,ax=plt.subplots(figsize=(8.4,4.8))
    for code,cond in [('7y3sRwLe3Va-04','manual'),('rPc6DW4iMge-20','manual'),('uNb9QFRL6hY-21','manual'),('B6ByNegPMKs-22','semi')]:
        key=next(k for k,g in cache.items() if g['code']==code and k.endswith('|'+cond));g=cache[key];D=np.array(g['matrices']['split_cyclic']);k=np.arange(1,len(D));ax.plot(k,[100*next_uncovered(D,int(x)) for x in k],label=code+' / '+cond)
    ax.set(xlabel='Previously observed distinct people',ylabel='Next-person geometric noncoverage (%)',title='Different observed trajectories, not certified stopping points',ylim=(-2,102));ax.legend(fontsize=8);ax.grid(alpha=.2);save(fig,'05_named_historical_trajectories')
    # Distinct endpoints avoid visually equating internal agreement with external coverage.
    c=pd.read_csv(OUT/'composition_validation_image_means.csv');c=c[c.cut==9].sort_values('mean_delta_uncovered')
    fig,ax=plt.subplots(figsize=(8.4,4.8));x=np.arange(len(c))
    ax.plot(x,100*c.mean_delta_uncovered,'o',label='Held-out noncoverage: AABC minus ABCD');ax.axhline(0,linewidth=1)
    ax.set(xlabel='Target images, ordered by coverage difference',ylabel='Change (percentage points)',title='Four distinct-person teams; 31–32 common validation splits/image');ax.legend();ax.grid(alpha=.2);save(fig,'06_composition_heldout_coverage')
    fig,ax=plt.subplots(figsize=(8.4,4.8));ax.plot(x,100*c.mean_delta_within,'o',label='Within-team disagreement: AABC minus ABCD');ax.axhline(0,linewidth=1)
    ax.set(xlabel='Same target-image ordering as coverage figure',ylabel='Change (percentage points)',title='Internal agreement changes more than held-out coverage');ax.legend();ax.grid(alpha=.2);save(fig,'07_composition_internal_agreement')
    m=pd.read_csv(OUT/'model_LOBO_summary.csv').set_index('model');order=['train_mean','N_only','N_plus_Bi','N_plus_corners','N_plus_model_feedback'];labels=['Train mean','Pool size','Pool size\n+ Bi gap','Pool size\n+ model counts','Pool size + counts\n+ model gaps']
    fig,ax=plt.subplots(figsize=(8.6,4.8));ax.bar(labels,m.loc[order,'MAE']);ax.set(ylabel='Outer held-building mean absolute error',title='46 Manual images / 15 buildings: historical k=5 noncoverage')
    for i,v in enumerate(m.loc[order,'MAE']):ax.text(i,v+.005,f'{v:.3f}',ha='center',fontsize=9)
    ax.set_ylim(0,.35);save(fig,'08_existing_model_prediction')
    fig,ax=plt.subplots(figsize=(8.4,4.8));u=pd.read_csv(OUT/'uNb21_endpoint_scenarios.csv');u=u[u.role=='top'];ax.plot(u.ordinal_a,u.fixed_error_deg,'o-',label='Nominal x order');ax.plot(u.ordinal_a,u.hypothetical_error_deg,'s--',label='Hypothetical full reciprocal swap (unconfirmed)');ax.axhline(9,linestyle=':',label='Working 9-degree threshold')
    ax.set(xlabel='W006 top ordinal',ylabel='Top endpoint error (degrees)',title='uNb-21: one confirmed anchor is not a confirmed full mapping');ax.legend();ax.grid(alpha=.2);save(fig,'09_partial_correspondence_scope')
    # Same physical-room provenance, common people, no new physical interpretation.
    rr=pd.read_csv(OUT/'same_room_common_people.csv');q=rr[(rr.code_a=='q9vSo1VnCiC-02')&(rr.code_b=='q9vSo1VnCiC-13')&(rr.condition=='manual')].iloc[0]
    fig,ax=plt.subplots(figsize=(8.4,4.8));workers=q.workers.split(';')
    for side in ['a','b']:
        g=cache[q['image_'+side]+'|manual'];ix=[g['workers'].index(w) for w in workers];D=np.array(g['matrices']['split_cyclic'])[np.ix_(ix,ix)];k=np.arange(1,len(ix));ax.plot(k,[100*next_uncovered(D,int(x)) for x in k],label=q['code_'+side])
    ax.set(xlabel='Previously observed common people',ylabel='Next-person geometric noncoverage (%)',title=f'Same-room numerical contrast / {len(workers)} common people',ylim=(-2,102));ax.legend();ax.grid(alpha=.2);save(fig,'10_same_room_common_people')
    return len(list(FIG.glob('*.png')))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path);p.add_argument('--figdir',type=Path);a=p.parse_args()
    if a.data:OUT=a.data.resolve()
    if a.figdir:FIG=a.figdir.resolve()
    run()
