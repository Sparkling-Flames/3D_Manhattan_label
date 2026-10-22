#!/usr/bin/env python3
"""Save common-building contrasts, concise figures and exact existing case links.

No geometry recomputation, fusion replay, quality change or semantic GT change.
"""
from pathlib import Path
import gzip
import hashlib
import io
import json
import os
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_difficulty_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
KEY=['method','condition','tier','role','source']
METRICS=['turn_n','short_turn_edges','near_straight_nodes_5deg','B8L2','D10',
    'log_time_peer_delta','unmatched_ref_9','reference_reduced','abs_bottom_bias_9',
    'omission','extension','log_area','log_height']

def save(d,n):
    atomic_bytes(HERE/n,d.to_csv(index=False).encode('utf-8-sig'))

def atomic_bytes(path,data):
    tmp=path.with_name(path.name+'.partial')
    with open(tmp,'wb') as f:
        assert f.write(data)==len(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    assert path.read_bytes()==data

def savefig(fig,name):
    p=HERE/name;fmt=p.suffix.lstrip('.')
    buf=io.BytesIO();fig.savefig(buf,format=fmt,dpi=175);data=buf.getvalue()
    if fmt=='png':Image.open(io.BytesIO(data)).load()
    atomic_bytes(p,data)
    if fmt=='png':Image.open(p).load()

def load_json(path):
    with gzip.open(path,'rt') if str(path).endswith('.gz') else open(path) as f:return json.load(f)

def main():
    r=pd.read_csv(HERE/'role_image_contrasts.csv.gz')
    paired=[]
    for key,g in r.groupby(KEY+['building_id']):
        easy=g[g.current_difficulty.eq('简单')];hard=g[g.current_difficulty.eq('困难')]
        if not len(easy) or not len(hard):continue
        for m in METRICS:
            a=easy[m+'_difference'].dropna();b=hard[m+'_difference'].dropna()
            if not len(a) or not len(b):continue
            paired.append(dict(zip(KEY+['building_id'],key))|dict(metric=m,easy_images=len(a),hard_images=len(b),
                easy_mean=a.mean(),hard_mean=b.mean(),hard_minus_easy=b.mean()-a.mean()))
    d=pd.DataFrame(paired);save(d,'same_building_easy_hard.csv')
    s=d.groupby(KEY+['metric'],dropna=False).agg(buildings=('building_id','nunique'),
        easy_mean=('easy_mean','mean'),hard_mean=('hard_mean','mean'),hard_minus_easy=('hard_minus_easy','mean'),
        increased_buildings=('hard_minus_easy',lambda x:int(x.gt(1e-9).sum())),
        decreased_buildings=('hard_minus_easy',lambda x:int(x.lt(-1e-9).sum())),
        equal_buildings=('hard_minus_easy',lambda x:int(x.abs().le(1e-9).sum()))).reset_index()
    save(s,'same_building_easy_hard_summary.csv')

    fixed=[]
    for key,g in r[r.ref_turn5.eq(6)].groupby(KEY+['reference_opportunity']):
        for m in METRICS:
            a=g[g[m+'_difference'].notna()]
            bs=a.groupby('building_id')[m+'_difference'].mean()
            fixed.append(dict(zip(KEY+['reference_opportunity'],key))|dict(metric=m,
                images=a.image_id.nunique(),buildings=len(bs),building_equal_mean=bs.mean(),
                positive_images=int(a[m+'_difference'].gt(1e-9).sum()),
                negative_images=int(a[m+'_difference'].lt(-1e-9).sum()),
                zero_images=int(a[m+'_difference'].abs().le(1e-9).sum())))
    save(pd.DataFrame(fixed),'fixed_reference_six_turn_opportunities.csv')

    p=pd.read_csv(HERE/'same_people_speed_difficulty.csv')
    k=['condition','tier','origin','metric']
    s=p.groupby(k,dropna=False).agg(member_pairs=('hard_minus_easy','count'),
        easy_mean=('easy_mean','mean'),hard_mean=('hard_mean','mean'),hard_minus_easy=('hard_minus_easy','mean'),
        increased_pairs=('hard_minus_easy',lambda x:int(x.gt(1e-9).sum())),
        decreased_pairs=('hard_minus_easy',lambda x:int(x.lt(-1e-9).sum())),
        equal_pairs=('hard_minus_easy',lambda x:int(x.abs().le(1e-9).sum()))).reset_index()
    save(s,'same_people_speed_difficulty_summary.csv')
    speed=pd.read_csv(HERE/'same_class_nearQ_speed_pairs.csv.gz')
    ex=speed[speed.worker_pair.eq('W109|W112')&speed.tier.eq('fine_label')&speed.condition.eq('manual')&
        speed.image_code.isin(['b8cTxDM8gDG-07','yqstnuAEVhm-29','jh4fc5c5qoQ-04'])]
    save(ex,'profile_case_lobo_links.csv')

    # New aggregate figure. All quantities are descriptive means with explicit supports.
    q=pd.read_csv(HERE/'role_difficulty_summary.csv')
    q=q[q.method.eq('V3_BEHAVIOR')&q.condition.eq('manual')&q.tier.eq('coarse_label')&
        q.role.eq('turn_expression')&q.stratification.eq('current_difficulty')]
    t=pd.read_csv(HERE/'same_class_nearQ_speed_summary.csv')
    t=t[t.condition.eq('manual')&t.origin.eq('new')&t.tier.eq('fine_label')&t.stratification.eq('current_difficulty')]
    diff=['简单','中等','困难'];names=['Easy','Medium','Difficult'];xs=np.arange(3)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for ax,metric,title,ylabel in [(axes[0,0],'turn_n','A. Structure class contrast','More-turn class minus fewer-turn class'),
                                 (axes[0,1],'B8L2','B. Quality contrast and source','B8L2 points: more-turn minus fewer-turn')]:
        for source,color,label in [('all','#007F90','All origins'),('v1','#D87B22','Within earlier origin')]:
            z=q[q.source.eq(source)&q.metric.eq(metric)].set_index('current_difficulty').reindex(diff)
            vals=z.building_equal_mean.to_numpy();ax.plot(xs,vals,'o-',c=color,label=label,lw=2)
            for i,v in enumerate(vals):ax.annotate(f'{v:+.2f}\n{int(z.images.iloc[i])} images', (i,v),xytext=(0,9 if source=='all' else -28),textcoords='offset points',ha='center',fontsize=8,color=color)
        ax.axhline(0,c='#777',lw=.8);ax.set_title(title,loc='left',weight='bold');ax.set_ylabel(ylabel);ax.set_xticks(xs,names);ax.margins(x=.1,y=.28);ax.legend(frameon=False,loc='upper left')
    ax=axes[1,0]
    for metric,color,label in [('turn_n','#007F90','Non-collinear turns'),('short_turn_edges','#9A4FB0','Short turn edges')]:
        z=t[t.metric.eq(metric)].set_index('current_difficulty').reindex(diff)
        ax.plot(xs,z.building_equal_mean,'o-',c=color,label=label,lw=2)
    ax.axhline(0,c='#777',lw=.8);ax.set_xticks(xs,names);ax.set_ylabel('Slower minus faster (count)')
    ax.set_title('C. Within class + near historical Q',loc='left',weight='bold');ax.legend(frameon=False)
    ax.text(.02,.03,'Same origin; historical Q gap <= 3; time ratio >= 1.5\n130 / 36 / 30 images',transform=ax.transAxes,fontsize=9)
    ax.set_ylim(-.18,.07)
    ax=axes[1,1];z=t[t.metric.eq('log_time_peer_delta')].set_index('current_difficulty').reindex(diff)
    vals=np.exp(z.building_equal_mean.to_numpy());bars=ax.bar(xs,vals,color=['#91C8CE','#49A6B1','#007F90'],width=.5)
    ax.axhline(1,c='#777',lw=.8);ax.set_xticks(xs,names);ax.set_ylim(0,2.5)
    ax.set_title('D. Time difference persists within class',loc='left',weight='bold');ax.set_ylabel('Exp(mean source-log-time gap)')
    for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+.05,f'{v:.2f} x',ha='center')
    fig.suptitle('Frozen outer-building personnel classes × image difficulty\nReal v2 raw answers; equal buildings; no new fusion or scoring',fontsize=14,weight='bold')
    savefig(fig,'raw_answer_difficulty.png');savefig(fig,'raw_answer_difficulty.svg');plt.close(fig)

    # Cases retain their original stage, exact members and files, without copying large evidence caches.
    cases=[]
    entries=[
      ('position_same_count','research/workers/personnel_effective_exchange_conditions_20261022/mechanisms/positive_cases/cases/E20261022_wc2_56_n20_m6.json',
       'research/workers/personnel_effective_exchange_conditions_20261022/mechanisms/positive_cases/figures/E20261022_wc2_56_n20_m6/comparison.png',
       'All four corners receive 20 votes in every arm; changing members moves median positions and Q.'),
      ('threshold_n20','research/workers/personnel_effective_exchange_conditions_20261022/mechanisms/positive_cases/cases/E20261022_zs16_n20_m6.json',
       'research/workers/personnel_effective_exchange_conditions_20261022/mechanisms/positive_cases/figures/Zs16_THRESHOLD_AND_BACKGROUND.png',
       'Same six-person blocks as n21; B support 10 passes threshold 10 and C-B Q is negative.'),
      ('threshold_n21','research/workers/personnel_effective_exchange_conditions_20261022/mechanisms/positive_cases/cases/E20261022_zs16_n21_m6.json',
       'research/workers/personnel_effective_exchange_conditions_20261022/mechanisms/positive_cases/figures/Zs16_THRESHOLD_AND_BACKGROUND.png',
       'Only W125 added to common background; threshold 11 removes B corner while C retains it. C itself does not improve.'),
      ('joint_structure_complement','research/workers/personnel_exchange_closure_20261022/manual_joint/mechanism_case/case.json.gz',
       'research/workers/personnel_exchange_closure_20261022/manual_joint/mechanism_case/figures/raw_three_views.png',
       'B6-47 distinct valid event: reference r4/r7 receive sufficient replacement votes; C-B Q positive, C-A Q negative and footprint IoU lower.'),
      ('semi_null_geometry_efficiency','research/workers/personnel_exchange_closure_20261022/semi/mechanism_cases/cases/semi_pure_efficiency.json.gz',
       'research/workers/personnel_exchange_closure_20261022/semi/mechanism_cases/figures/semi_pure_efficiency/comparison.png',
       'B and C share the same stored endpoint geometry and Q; C source-record time is lower.'),
      ('semi_member_risk','research/workers/personnel_exchange_closure_20261022/semi/mechanism_cases/cases/semi_member_loss_qt_repair.json.gz',
       'research/workers/personnel_exchange_closure_20261022/semi/mechanism_cases/figures/semi_member_loss_qt_repair/comparison.png',
       'Four-corner outputs differ in far-wall localization; cross-class C loses Q vs B. One within-target-class replacement partially repairs it.'),
      ('joint_failure','research/workers/personnel_effective_exchange_conditions_20261022/mechanisms/b6_47_failure/cases/B6_47_invalid_floor_n20_m4.json',
       'research/workers/personnel_effective_exchange_conditions_20261022/mechanisms/b6_47_failure/figures/B6_RAW_PAIR_AND_VOTES.png',
       'B6-47 invalid event distinct from complement case: paired real details have uneven support; projected connection and position create self-intersection.')]
    component=[]
    for name,src,img,why in entries:
        assert (ROOT/src).is_file(),src;assert (ROOT/img).is_file(),img
        c=load_json(ROOT/src);e=c.get('event',{});teams=c.get('teams',[])
        row=dict(case_id=name,source_case_id=c.get('case_id'),source_file=src,figure_file=img,
            source_sha256=hashlib.sha256((ROOT/src).read_bytes()).hexdigest(),event_id=e.get('event_id',c.get('event_id')),
            method=c.get('method_id',e.get('method_id')),condition=e.get('condition',c.get('pool_meta',{}).get('condition')),
            image=e.get('image',c.get('pool_meta',{}).get('image')),n=c.get('n',e.get('n')),
            actual_m=e.get('m_AC'),source_class=e.get('source_class'),target_class=e.get('target_class'),
            common_background=e.get('common_background'),block_X=e.get('outgoing_block_X'),
            block_Y=e.get('same_count_block_Y'),block_Z=e.get('changed_count_block_Z'),
            selection='previously selected explanatory case; new link to difficulty module; not a new effect estimate',
            rationale=why,stage='historical_reuse_new_explanation',new_fusion=0,new_score=0)
        for team in teams:
            rr=dict(case_id=name,team=team.get('label'),team_key=team.get('team_key'),member_workers=team.get('member_workers'))
            for metric in ['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension',
                           'nodes','minimum_support','source_time_total_seconds','geometry_status','score_status','time_source_kinds']:
                rr[metric]=team.get(metric)
            component.append(rr)
            if team.get('label') in ['A','B','C']:
                row[team['label']+'_Q']=team.get('B8L2');row[team['label']+'_nodes']=team.get('nodes')
        cases.append(row)
    save(pd.DataFrame(cases),'CASE_SELECTION.csv');save(pd.DataFrame(component),'CASE_ENDPOINT_COMPONENTS.csv')
    # Exact old profile case has now been connected to the current LOBO pair analysis.
    checks=dict(numerical_stage='complete',n_role_panels=len(r),n_exact_speed_pair_rows=len(speed),
        common_building_rows=len(d),case_links=len(cases),profile_lobo_case_rows=len(ex),
        outputs=['same_building_easy_hard.csv','same_building_easy_hard_summary.csv',
                 'fixed_reference_six_turn_opportunities.csv','same_people_speed_difficulty_summary.csv',
                 'profile_case_lobo_links.csv','raw_answer_difficulty.png','raw_answer_difficulty.svg',
                 'CASE_SELECTION.csv','CASE_ENDPOINT_COMPONENTS.csv'],new_fusion=0,new_score=0)
    (HERE/'STAGE_02.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
