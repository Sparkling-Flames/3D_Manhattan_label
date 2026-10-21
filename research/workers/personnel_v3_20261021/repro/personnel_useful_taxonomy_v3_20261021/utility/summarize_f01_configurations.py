"""Complete F01 n12 class-count curves, not sampled class configurations.

Each point averages all concrete member sets at that class count. The extreme
contrast is a descriptive finite-domain composition change, not a matched
background intervention or a target-outcome-selected policy.
"""
from __future__ import annotations
import json,math
import numpy as np
import pandas as pd
from prepare_training import HERE,atomic_csv,atomic_json,sha
from policy_study import COMP,METRICS,inclusion_probabilities
from summarize_policy import macro_many

def summarize(g):
    r=dict(member_sets=len(g),successful_member_sets=int(g.B8L2.notna().sum()),
           complete_failures=int((~g.complete_evaluable.astype(bool)).sum()),
           failure_rate=float((~g.complete_evaluable.astype(bool)).mean()))
    for f in METRICS:
        if f in g:r[f]=float(g[f].mean())
    q=g.B8L2.dropna().to_numpy(float)
    for name,p in [('p10',.1),('p50',.5),('p90',.9)]:
        r['B8L2_'+name]=float(np.quantile(q,p)) if len(q) else np.nan
    r['B8L2_std']=float(np.std(q)) if len(q) else np.nan
    known=g.source_time_known_n.eq(g.k)&g.source_time_total_seconds.gt(0)&g.time_source_kinds.fillna('').ne('')&~g.time_source_kinds.fillna('').str.contains('|',regex=False)
    r['all_member_sets_time_compatible']=bool(known.all())
    r['time_seconds']=float(g.source_time_total_seconds.mean()) if known.all() else np.nan
    for name,p in [('p10',.1),('p90',.9)]:
        r['time_seconds_'+name]=float(np.quantile(g.source_time_total_seconds,p)) if known.all() else np.nan
    r['time_source_kinds']=';'.join(sorted(g.time_source_kinds.fillna('unknown').unique()))
    r['worker_inclusion_probabilities']=json.dumps(inclusion_probabilities(g.member_workers,np.ones(len(g))/len(g)),sort_keys=True)
    return r

def main():
    epfile=COMP/'batches/f01_001/ENDPOINT_SCALARS.csv.gz'
    ep=pd.read_csv(epfile,low_memory=False)
    mem=pd.read_csv(COMP/'F01_PANEL_MEMBERSHIP.csv.gz')
    panels=pd.read_csv(COMP/'F01_PANELS.csv')
    labels=pd.read_csv(COMP/'F01_FROZEN_LABELS_LOBO.csv.gz')
    assert not ep.team_key.duplicated().any()
    assert set(mem.team_key)==set(ep.team_key)
    d=mem[['panel_id','team_key','F01_counts']].merge(ep,on='team_key',validate='one_to_one')
    d['fast_C01_n']=d.F01_counts.map(lambda s:int(dict(v.split(':') for v in s.split('|')).get('C01',0)))
    d['slow_C02_n']=d.k-d.fast_C01_n
    member_fields=['panel_id','team_key','F01_counts','building','image','difficulty','k','member_workers',
        'fast_C01_n','slow_C02_n','B8L2','D10','complete_evaluable','score_status','nodes',
        'connection_available','source_time_known_n','source_time_total_seconds','time_source_kinds']
    atomic_csv(d[member_fields],HERE/'F01_CONFIGURATION_MEMBERS.csv.gz')
    rows=[];contrasts=[]
    for pid,g in d.groupby('panel_id'):
        meta=panels.set_index('panel_id').loc[pid]
        lab=labels[labels.heldout_building.eq(meta.building)].set_index('worker_id').class_id
        capacity=lab.loc[meta.domain_workers.split('|')].value_counts().to_dict()
        n=meta.n;minimum=max(0,n-capacity.get('C02',0));maximum=min(n,capacity.get('C01',0))
        assert set(g.fast_C01_n)==set(range(minimum,maximum+1))
        ordinary=summarize(g);this=[]
        for k,z in g.groupby('fast_C01_n'):
            expected=math.comb(capacity['C01'],int(k))*math.comb(capacity['C02'],int(n-k))
            assert len(z)==expected
            r=dict(panel_id=pid,condition='manual',family='F01_fixed_history',building=meta.building,
                image=meta.image,difficulty=meta.difficulty,n=n,domain_pool_n=meta.domain_pool_n,
                fast_C01_capacity=capacity.get('C01',0),slow_C02_capacity=capacity.get('C02',0),
                fast_C01_n=int(k),slow_C02_n=int(n-k),fast_C01_min=minimum,fast_C01_max=maximum,
                possible_member_sets=expected,complete_member_enumeration=True,
                within_configuration_member_variation_estimable=expected>1,
                has_class_count_opportunity=minimum<maximum,**summarize(z))
            r.update({'ordinary_'+f:v for f,v in ordinary.items() if f!='worker_inclusion_probabilities'})
            for f in METRICS+['B8L2_p10','B8L2_std']:
                if f in r:r['delta_'+f]=r[f]-ordinary[f]
            r['failure_delta_pp']=100*(r['failure_rate']-ordinary['failure_rate'])
            r['time_percent_vs_uniform']=100*(r['time_seconds']/ordinary['time_seconds']-1)
            rows.append(r);this.append(r)
        if minimum==maximum:continue
        lo=this[0];hi=this[-1]
        low=json.loads(lo['worker_inclusion_probabilities']);high=json.loads(hi['worker_inclusion_probabilities'])
        c=dict(panel_id=pid,building=meta.building,image=meta.image,difficulty=meta.difficulty,n=n,
            domain_pool_n=meta.domain_pool_n,fast_C01_n_low=minimum,fast_C01_n_high=maximum,
            actual_class_count_change=maximum-minimum,low_member_sets=lo['member_sets'],high_member_sets=hi['member_sets'],
            expected_changed_members_independent_draws=n-sum(v*high.get(w,0) for w,v in low.items()),
            strict_background_matched=False,descriptive_complete_configuration_contrast=True)
        for f in METRICS+['B8L2_p10','B8L2_std','time_seconds']:
            if f in hi:c['high_fast_minus_low_fast_'+f]=hi[f]-lo[f]
        c['failure_delta_pp']=100*(hi['failure_rate']-lo['failure_rate'])
        c['relative_time_percent_high_vs_low']=100*(hi['time_seconds']/lo['time_seconds']-1)
        c['all_candidates_time_compatible']=lo['all_member_sets_time_compatible'] and hi['all_member_sets_time_compatible']
        contrasts.append(c)
    curve=pd.DataFrame(rows);contrast=pd.DataFrame(contrasts)
    atomic_csv(curve,HERE/'F01_COMPLETE_CONFIGURATION_CURVE.csv')
    atomic_csv(contrast,HERE/'F01_EXTREME_CONFIGURATION_CONTRASTS.csv')
    stats=[]
    for sk,sv,g in [('all','all',contrast)]+[('difficulty',str(v),g) for v,g in contrast.groupby('difficulty')]:
        fields=[c for c in g if c.startswith('high_fast_minus_low_fast_')]+['failure_delta_pp','relative_time_percent_high_vs_low','expected_changed_members_independent_draws']
        summary,_=macro_many(g,fields)
        for field,details in summary.items():stats.append(dict(slice_kind=sk,slice_value=sv,outcome=field,**details))
    atomic_csv(pd.DataFrame(stats),HERE/'F01_EXTREME_CONFIGURATION_SUMMARY.csv')
    atomic_json(dict(endpoints_sha256=sha(epfile),native_endpoint_count=len(ep),panels=len(panels),
        complete_configuration_cells=len(curve),within_cell_all_members_complete=True,
        panels_with_class_count_opportunity=curve.loc[curve.has_class_count_opportunity,'panel_id'].nunique(),
        all_time_complete=bool(curve.all_member_sets_time_compatible.all()),
        class_semantics='C01 historical faster; C02 historical slower, within frozen high-Q23 population',
        contrast_scope='all feasible counts at n12; finite-domain conditional means, not matched-background causal effects',
        singleton_warning='one-set panels retained in curve, excluded from composition-shift evidence'),HERE/'F01_CONFIGURATION_RECEIPT.json')
    print('F01 curves',len(curve),'extreme contrasts',len(contrast),flush=True)

if __name__=='__main__':main()
