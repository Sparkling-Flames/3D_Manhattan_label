"""Interpret frozen within-Q-parent fine-class events; no new fusion.

Post-hoc directional reading is defined by the entered training T ordering,
not by target time or quality. Fine child 2 is the higher training t_effect
child. Only an unchanged QH vector and a QL.1/QL.2 transfer are compared.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from analyze_global import balanced,write

HERE=Path(__file__).resolve().parent

def count(s):
    return {v.rsplit(':',1)[0]:int(v.rsplit(':',1)[1]) for v in s.split('|')}

def main():
    e=pd.read_csv(HERE/'ABC_ALL_COMPONENT_EVENTS.csv.gz',low_memory=False)
    z=e[(e.method_id=='MV_QTD_manual_new')&(e.layer=='ordinary_manual')&
        (e.event_mode=='within_coarse_fine_change')&e.same_source_counts&
        e.time_population.eq('new_only')].copy()
    rows=[]
    for r in z.to_dict('records'):
        a,c=count(r['composition_A']),count(r['composition_C'])
        if any(a.get(k,0)!=c.get(k,0) for k in a.keys()|c.keys() if k not in ['QL.1','QL.2']):continue
        delta=c.get('QL.2',0)-a.get('QL.2',0)
        if not delta or c.get('QL.1',0)-a.get('QL.1',0)!=-delta:continue
        r['slow_QL_count_change']=delta
        r['direction_QL']='increase_slower_QL2' if delta>0 else 'decrease_slower_QL2'
        r['same_coarse_vector_verified']=True
        # B and A share the same complete fine vector, so B->C is the
        # directly changed fine-count comparison. Its actual m is m_BC.
        r['net_source_time_percent']=100*np.expm1(r['net_source_log_time_ratio'])
        r['net_time_expected_direction']=float(np.sign(r['net_source_log_time_ratio'])==np.sign(delta)) if pd.notna(r['net_source_log_time_ratio']) else np.nan
        r['history_Q_net_within2']=abs(r['net_history_block_Q_change'])<=2
        rows.append(r)
    d=pd.DataFrame(rows)
    base=['event_id','method_id','condition','tier','event_mode','pool_id','image','building','layer','difficulty','n','m_AB','m_BC',
          'composition_A','composition_C','slow_QL_count_change','direction_QL','same_coarse_vector_verified','net_source_time_percent',
          'net_source_log_time_ratio','net_time_expected_direction','net_B8L2','net_D10','net_loss_gt5','net_loss_gt10',
          'net_joint_save20_loss_le2','net_failure_difference','net_history_block_Q_change','history_Q_net_within2']
    write(d[base],'QL_EFFICIENCY_DIRECTION_EVENTS.csv')
    allout=[];bs=[]
    metrics=['slow_QL_count_change','m_BC','net_source_time_percent','net_source_log_time_ratio','net_time_expected_direction',
             'net_B8L2','net_D10','net_loss_gt5','net_loss_gt10','net_joint_save20_loss_le2','net_failure_difference','net_history_block_Q_change']
    for scope,a in [('all_registered',d),('n_ge20_m_ge4',d[d.n.ge(20)&d.m_AB.ge(4)])]:
        for matching,b in [('all_actual_events',a),('history_net_Q_within2',a[a.history_Q_net_within2])]:
            if not len(b):continue
            s,v=balanced(b,metrics,['direction_QL'])
            for frame in (s,v):frame['size_scope']=scope;frame['posthoc_comparison_stratum']=matching
            allout.append(s);bs.append(v)
    write(pd.concat(allout,ignore_index=True),'QL_EFFICIENCY_DIRECTION_SUMMARY.csv')
    write(pd.concat(bs,ignore_index=True),'QL_EFFICIENCY_DIRECTION_BUILDINGS.csv')
    (HERE/'QL_EFFICIENCY_DIRECTION_CONTRACT.json').write_text(json.dumps({
        'selection':'Post-hoc interpretation of already frozen events; target outcomes do not define direction or subset.',
        'class_order':'multivariate/build_multivariate.py ward2 orders each child by first entered T field t_effect; .2 has larger training time effect.',
        'scope':'New-origin Manual, only QL.1/QL.2 count transfers; all other fine counts unchanged. Full Q-parent vector unchanged.',
        'effect':'C-B, hence m_BC is the actual net replacement; m_AB/m_AC describe the original matched ABC experiment.',
        'time':'Reported source active seconds, same origin and source kinds, full-member known only; not wall-clock or intervention causal effect.',
        'quality':'Own-condition frozen B8L2/D10; no score imputation. Source/Q matching is an auxiliary post-hoc stratum, not an inclusion gate for total usefulness.',
        'events':len(d),'new_endpoint_calls':0},ensure_ascii=False,indent=2),encoding='utf8')
    print('Completed directional efficiency reading:',len(d),'existing events')

if __name__=='__main__':main()
