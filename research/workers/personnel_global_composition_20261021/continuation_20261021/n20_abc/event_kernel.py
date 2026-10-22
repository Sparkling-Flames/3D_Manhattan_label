"""Reusable single-event evaluator, exact kernel of frozen Semi evaluator.

The computational block is kept identical; checkpoint orchestration imports it.
"""
from evaluate_n20_abc import *

def evaluate_one(request,teams,pairs,signatures,hist,sg,corner,condition):
    def history(ws,building,field):
        values=[getattr(hist.get((condition,building,w)),field,np.nan) for w in ws]
        return float(np.mean(values)) if values and np.isfinite(values).all() else None
    r=typed(request)
    # Hexadecimal IDs can by chance contain digits only. They remain opaque
    # strings even in that case; numeric coercion would lose leading zeroes.
    for key in ['event_id','physical_triple_id','oriented_triple_id','team_A','team_B','team_C']:
        r[key]=request[key]
    for k in ('A_member_workers','B_member_workers','C_member_workers','common_background','outgoing_block_X','same_count_block_Y','changed_count_block_Z'):
        r[k]=request[k]
    ids=[r['team_'+a] for a in 'ABC']
    assert all(k in teams for k in ids), 'incomplete endpoint batch'
    endpoints=[teams[k] for k in ids]
    a,b,c=endpoints;r['computed_all_arms']=True
    r['all_scored']=all(t.get('B8L2') is not None for t in endpoints)
    r['all_complete']=all(bool(t.get('complete_evaluable')) for t in endpoints)
    r['same_source_counts']=a['new_n']==b['new_n']==c['new_n']
    r['time_population']='new_only' if all(t['old_n']==0 for t in endpoints) else ('old_only' if all(t['new_n']==0 for t in endpoints) else 'mixed_origin')
    for arm,t in zip('ABC',endpoints):
        assert t['pool_id']==r['pool_id'] and t['k']==r['n']
        assert '|'.join(t['member_workers'])==r[arm+'_member_workers']
        r[arm+'_failure']=not bool(t.get('complete_evaluable'))
        r[arm+'_score_status']=t.get('score_status')
        for k,v in t.items():
            if k=='geometry':continue
            r['endpoint_'+arm+'__'+k]='|'.join(map(str,v)) if isinstance(v,list) else v
        for k in ['B8L2','D10','nodes','source_time_total_seconds']:r[arm+'_'+k]=t.get(k)
    for block,col in [('X','outgoing_block_X'),('Y','same_count_block_Y'),('Z','changed_count_block_Z')]:
        for feature in ['q_effect','t_effect','q_downside','hard_minus_easy']:
            r[block+'_history_'+feature]=history(r[col].split('|'),r['building'],feature)
    for name,left,right in [('same','X','Y'),('cross','X','Z'),('net','Y','Z')]:
        x,y=r[left+'_history_q_effect'],r[right+'_history_q_effect']
        r[name+'_history_block_Q_change']=y-x if x is not None and y is not None else None
    for threshold in [2,5]:
        r['source_and_historyQ'+str(threshold)+'_matched']=bool(r['same_source_counts'] and
          r['same_history_block_Q_change'] is not None and r['cross_history_block_Q_change'] is not None and
          abs(r['same_history_block_Q_change'])<=threshold and abs(r['cross_history_block_Q_change'])<=threshold)
    for prefix,ia,ib in [('same',0,1),('cross',0,2),('net',1,2)]:
        left,right=endpoints[ia],endpoints[ib]
        for k in COMPONENTS:r[prefix+'_'+k]=safe_delta(left,right,k)
        q=r[prefix+'_B8L2'];r[prefix+'_abs_B8L2']=abs(q) if q is not None else None
        r[prefix+'_loss_gt5']=float(q < -5) if q is not None else None
        r[prefix+'_loss_gt10']=float(q < -10) if q is not None else None
        r[prefix+'_quality_comparable']=q is not None
        lt,rt=left.get('source_time_total_seconds'),right.get('source_time_total_seconds')
        tc=lt is not None and rt is not None and lt>0 and rt>0 and left.get('time_source_kinds')==right.get('time_source_kinds')
        r[prefix+'_source_log_time_ratio']=math.log(rt/lt) if tc else None
        r[prefix+'_time_comparable']=bool(tc)
        pair=(ids[ia],ids[ib]);gp='within' if prefix=='same' else prefix
        if pair not in pairs:
            for key in pair:
                if key not in signatures:signatures[key]=sg.signature(teams[key])
            va,vb=signatures[pair[0]],signatures[pair[1]]
            values=sg.pair_metrics(left,right,va,vb)
            co,_=corner(left,right);values.update({'corner_'+k:v for k,v in co.items()})
            if values['mean_height_prism_pair_iou'] is not None:values['mean_height_prism_pair_difference']=1-values['mean_height_prism_pair_iou']
            pa,pb=va['floor'],vb['floor']
            if values['both_complete'] and pa is not None and pb is not None:
                values['centroid_distance_h']=math.hypot(pb.centroid.x-pa.centroid.x,pb.centroid.y-pa.centroid.y)
                values['floor_area_abs_log_ratio']=abs(math.log(pb.area/pa.area))
            values['joint_stable_D10_main']=bool(values['both_complete'] and values['abs_D10_change'] is not None and values['abs_D10_change']<=2 and values['node_count_difference']==0 and
                values['floor_jaccard_difference'] is not None and values['floor_jaccard_difference']<=.05 and
                values['structure_bound_cyclic_deg'] is not None and values['structure_bound_cyclic_deg']<=3)
            pairs[pair]=values
        assert pairs[pair]['turnover']==r['m_'+('AB' if prefix=='same' else 'AC' if prefix=='cross' else 'BC')]
        r.update({gp+'_'+k:v for k,v in pairs[pair].items()})
    r['common_quality_within_abs']=r['same_abs_B8L2'] if r['all_scored'] else None
    r['common_quality_cross_abs']=r['cross_abs_B8L2'] if r['all_scored'] else None
    r['abs_Q_change_advantage']=r['cross_abs_B8L2']-r['same_abs_B8L2'] if r['all_scored'] else None
    r['stable_advantage']=int(r['within_joint_stable_main'])-int(r['cross_joint_stable_main'])
    r['stable_D10_advantage']=int(r['within_joint_stable_D10_main'])-int(r['cross_joint_stable_D10_main'])
    r['net_failure_difference']=int(r['C_failure'])-int(r['B_failure'])
    return r
