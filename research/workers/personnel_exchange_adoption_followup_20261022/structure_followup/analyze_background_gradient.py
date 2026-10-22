#!/usr/bin/env python3
"""Evaluate finite background census and compare exact fixed-XYZ gradients."""
from pathlib import Path
import itertools,json,sys,math
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
OLD=HERE.parents[1]/'personnel_exchange_closure_20261022'
sys.path[:0]=[str(OLD/'structure'),str(OLD)]

METRICS=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension',
    'nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','ref_node_recall_5','ref_edge_recall_5',
    'height_mean_h','geometry_area_h2','top_y_mean_px','bottom_y_mean_px']
META=['anchor_id','image','building','pool_id','difficulty','n','m']

def endpoint_folders(out,native):
    names=('ENDPOINT_SCALARS.csv.gz','ENDPOINT_GEOMETRY.csv.gz')
    # The portable package keeps batch receipts and the complete merged tables.
    if all((out/name).is_file() for name in names):
        return [out]
    folders=[f for f in sorted((native/'batches').glob('background_*')) if (f/'COMPLETION.json').exists()]
    if not folders or any(not (f/name).is_file() for f in folders for name in names):
        raise FileNotFoundError('Need the merged endpoint tables or complete endpoint CSVs for every completed batch')
    return folders

def summarize(g,values,keys=()):
    keys=list(keys)
    anchors=g.groupby(keys+['building','image','anchor_id'],dropna=False)[values].mean().reset_index()
    images=anchors.groupby(keys+['building','image'],dropna=False)[values].mean().reset_index()
    buildings=images.groupby(keys+['building'],dropna=False)[values].mean().reset_index()
    if not keys:
        groups=[((),g)]
    else:groups=g.groupby(keys,dropna=False)
    rows=[]
    for k,d in groups:
        if not isinstance(k,tuple):k=(k,)
        I=images;B=buildings;A=anchors
        for kk,v in zip(keys,k):I=I[I[kk].eq(v)];B=B[B[kk].eq(v)];A=A[A[kk].eq(v)]
        r=dict(zip(keys,k))|dict(registered_rows=len(d),registered_anchors=d.anchor_id.nunique(),registered_images=d.image.nunique(),registered_buildings=d.building.nunique())
        for met in values:
            r[met]=B[met].mean();r[met+'_images_valid']=I[met].notna().sum();r[met+'_images_positive']=I[met].gt(0).sum();r[met+'_buildings_valid']=B[met].notna().sum();r[met+'_buildings_positive']=B[met].gt(0).sum();r[met+'_rows_valid']=d[met].notna().sum();r[met+'_anchors_positive']=A[met].gt(0).sum();r[met+'_anchors_valid']=A[met].notna().sum()
        rows.append(r)
    return anchors,images,buildings,pd.DataFrame(rows)

def main():
    import evaluate_structure as es
    from analyze_existing import save
    from run_background_gradient import OUT,NATIVE,gs,write_json

    requests=pd.read_csv(OUT/'EVENTS_REGISTERED.csv.gz',dtype=str,keep_default_na=False)
    endpoints={};scalars=[];geos=[];ledger=[]
    folders=endpoint_folders(OUT,NATIVE)
    for folder in folders:
        s=pd.read_csv(folder/'ENDPOINT_SCALARS.csv.gz',dtype=str,keep_default_na=False)
        g=pd.read_csv(folder/'ENDPOINT_GEOMETRY.csv.gz',dtype=str,keep_default_na=False)
        if 'adapter_origin' not in s:s['adapter_origin']=s.endpoint_origin
        s['endpoint_origin']=np.where(s.endpoint_origin.str.startswith('new_native'),'new_native_adoption_followup_20261022','reused_exact_prior_closure_endpoint')
        s['research_stage']='personnel_exchange_adoption_followup_20261022'
        for r in s.to_dict('records'):endpoints[r['team_key']]=es.typed(r)
        for r in g.to_dict('records'):endpoints[r['team_key']]['geometry']=json.loads(r['geometry_json']) if r['geometry_json'] else None
        scalars.append(s);geos.append(g)
        if (folder/'COMPLETION.json').exists():ledger.append(json.loads((folder/'COMPLETION.json').read_text()))
    for t in endpoints.values():t.update(dict(zip(es.EXTRA,es.expression(t['geometry']))))
    save('background_gradient/ENDPOINT_SCALARS.csv.gz',pd.concat(scalars,ignore_index=True))
    save('background_gradient/ENDPOINT_GEOMETRY.csv.gz',pd.concat(geos,ignore_index=True))
    _,_,sg,corner=gs.setup_engine()
    histdf=pd.read_csv(es.HIST);hist={(r.condition,r.heldout_building,r.worker_id):r for r in histdf.itertuples()}
    f=pd.read_csv(OLD/'structure/CLASS_LABELS_REUSED.csv.gz',keep_default_na=False)
    features={(r['heldout_building'],r['worker_id']):r for r in f.to_dict('records') if r['heldout_building']!='ALL'}
    frames=[]
    for pid,g in requests.groupby('pool_id',sort=True):
        need=set(g.team_A)|set(g.team_B)|set(g.team_C)
        if not need<=endpoints.keys():continue
        dest=OUT/'events_by_pool'/(gs.digest(pid)[:20]+'.csv.gz')
        if dest.exists():E=pd.read_csv(dest,low_memory=False)
        else:
            pairs={};signatures={};events=[]
            for req in g.to_dict('records'):
                e=es.complete_event(req,endpoints,pairs,signatures,hist,sg,corner,'manual')
                e=es.add_structure_histories(e,req,features)
                # Opaque IDs and the new scope explicitly retained.
                for k in ['anchor_id','panel_id','old_anchor_event','cell_id']:e[k]=req[k]
                e['research_stage']='personnel_exchange_adoption_followup_20261022'
                for arm in 'ABC':
                    t=endpoints[req['team_'+arm]]
                    for field in ['node_supports','geometry_status','connection_available','half_vote_nodes']:
                        e[arm+'_'+field]=t.get(field)
                events.append(e)
            E=pd.DataFrame(events)
            save(str(dest.relative_to(HERE)),E)
        frames.append(E)
    E=pd.concat(frames,ignore_index=True)
    save('background_gradient/EVENTS_COMPLETE.csv.gz',E)
    # Exact-pair background gradients: omit target -> omit source means a
    # single source background member is replaced by a target member.
    comparisons=[];within=[]
    for aid,g in E.groupby('anchor_id'):
        lo=g[g.omitted_class.eq(g.target_class.iloc[0])]
        hi=g[g.omitted_class.eq(g.source_class.iloc[0])]
        for l,h in itertools.product(lo.to_dict('records'),hi.to_dict('records')):
            r={k:l[k] for k in META}|dict(pair_id=gs.digest([aid,l['event_id'],h['event_id']])[:24],event_low=l['event_id'],event_high=h['event_id'],
                low_D=l['common_background'],high_D=h['common_background'],background_common_members='|'.join(sorted(set(l['common_background'].split('|'))&set(h['common_background'].split('|')))),
                background_removed_source=h['omitted_worker'],background_added_target=l['omitted_worker'],background_actual_m=1,
                target_seats_low=l['background_target_seats'],target_seats_high=h['background_target_seats'],
                foreground_m=7,shared_X=l['outgoing_block_X'],shared_Y=l['same_count_block_Y'],shared_Z=l['changed_count_block_Z'])
            assert len(r['background_common_members'].split('|'))==12
            for arm in 'ABC':
                r['team_'+arm+'_low']=l['team_'+arm];r['team_'+arm+'_high']=h['team_'+arm]
                r[arm+'_failure_low']=l[arm+'_failure'];r[arm+'_failure_high']=h[arm+'_failure']
            for met in METRICS:
                vals=[endpoints[l['team_'+a]].get(met) for a in 'ABC']+[endpoints[h['team_'+a]].get(met) for a in 'ABC']
                valid=all(v is not None and np.isfinite(v) for v in vals)
                for j,a in enumerate('ABC'):
                    r[a+'_low_'+met]=vals[j] if valid else np.nan
                    r[a+'_high_'+met]=vals[j+3] if valid else np.nan
                    r[a+'_change_'+met]=vals[j+3]-vals[j] if valid else np.nan
                r['net_low_'+met]=vals[2]-vals[1] if valid else np.nan
                r['net_high_'+met]=vals[5]-vals[4] if valid else np.nan
                r['net_change_'+met]=r['C_change_'+met]-r['B_change_'+met]
            r['common_six_endpoint_Q']=pd.notna(r['net_change_B8L2'])
            six=[endpoints[r['team_'+a+'_'+st]] for st in ['low','high'] for a in 'ABC']
            kinds=[t.get('time_source_kinds') for t in six]
            time_ok=len(set(kinds))==1 and all(k and '|' not in k for k in kinds) and all(t.get('source_time_known_n')==20 and t.get('source_time_total_seconds') is not None and t['source_time_total_seconds']>0 for t in six)
            r['common_six_recorded_time']=time_ok
            for j,a in enumerate('ABC'):
                r[a+'_background_recorded_time_pct']=100*(six[j+3]['source_time_total_seconds']/six[j]['source_time_total_seconds']-1) if time_ok else np.nan
            r['net_recorded_time_pct_low']=100*(six[2]['source_time_total_seconds']/six[1]['source_time_total_seconds']-1) if time_ok else np.nan
            r['net_recorded_time_pct_high']=100*(six[5]['source_time_total_seconds']/six[4]['source_time_total_seconds']-1) if time_ok else np.nan
            r['net_recorded_time_pct_difference_pp']=r['net_recorded_time_pct_high']-r['net_recorded_time_pct_low']
            r['any_failure']=any(r[a+'_failure_'+b] for a in 'ABC' for b in ['low','high'])
            r['cross_class_loss_gt5_low']=float(r['net_low_B8L2'] < -5) if pd.notna(r['net_low_B8L2']) else np.nan
            r['cross_class_loss_gt5_high']=float(r['net_high_B8L2'] < -5) if pd.notna(r['net_high_B8L2']) else np.nan
            comparisons.append(r)
        for cl,cg in g.groupby('omitted_class'):
            role='source' if cl==g.source_class.iloc[0] else 'target' if cl==g.target_class.iloc[0] else 'other'
            for x,y in itertools.combinations(cg.to_dict('records'),2):
                r={k:x[k] for k in META}|dict(omitted_role=role,event_1=x['event_id'],event_2=y['event_id'],actual_background_m=1,
                    same_background_class_counts=x['background_stratum']==y['background_stratum'])
                ok=all(pd.notna(v) for v in [x[a+'_B8L2'] for a in 'ABC']+[y[a+'_B8L2'] for a in 'ABC'])
                for arm in 'ABC':r[arm+'_absolute_Q_change']=abs(y[arm+'_B8L2']-x[arm+'_B8L2']) if ok else np.nan
                r['net_absolute_Q_change']=abs(y['net_B8L2']-x['net_B8L2']) if ok else np.nan
                within.append(r)
    C=pd.DataFrame(comparisons);W=pd.DataFrame(within)
    save('background_gradient/MATCHED_BACKGROUND_GRADIENT_PAIRS.csv.gz',C)
    save('background_gradient/SAME_COMPOSITION_BACKGROUND_PAIRS.csv.gz',W)
    values=[x for x in C.columns if x.startswith(('A_change_','B_change_','C_change_','net_low_','net_high_','net_change_'))]
    values+=['cross_class_loss_gt5_low','cross_class_loss_gt5_high']
    A,I,B,S=summarize(C,values)
    for tag,df in [('ANCHOR',A),('IMAGE',I),('BUILDING',B),('SUMMARY',S)]:save('background_gradient/GRADIENT_'+tag+'.csv',df)
    CW=C.copy();CW['seat_transition']=CW.target_seats_low.astype(int).astype(str)+'_to_'+CW.target_seats_high.astype(int).astype(str)
    for keys,tag in [(['difficulty'],'DIFFICULTY'),(['seat_transition'],'SEAT_TRANSITION')]:
        aa,ii,bb,ss=summarize(CW,values,keys)
        save('background_gradient/GRADIENT_'+tag+'_SUMMARY.csv',ss)
        save('background_gradient/GRADIENT_'+tag+'_IMAGES.csv',ii)
    qt=C[C.common_six_endpoint_Q&C.common_six_recorded_time]
    qvals=['A_change_B8L2','B_change_B8L2','C_change_B8L2','net_low_B8L2','net_high_B8L2','net_change_B8L2',
        'A_background_recorded_time_pct','B_background_recorded_time_pct','C_background_recorded_time_pct',
        'net_recorded_time_pct_low','net_recorded_time_pct_high','net_recorded_time_pct_difference_pp']
    if len(qt):
        qa,qi,qb,qs=summarize(qt,qvals)
        save('background_gradient/GRADIENT_QT_SUMMARY.csv',qs)
        save('background_gradient/GRADIENT_QT_IMAGES.csv',qi)
    vals=['A_absolute_Q_change','B_absolute_Q_change','C_absolute_Q_change','net_absolute_Q_change']
    a,i,b,s=summarize(W,vals,['omitted_role'])
    save('background_gradient/SAME_COMPOSITION_BACKGROUND_SUMMARY.csv',s)
    # ABC conclusions on this finite additional member/background support.
    ee=E.copy();qmask=ee[['A_B8L2','B_B8L2','C_B8L2']].notna().all(axis=1)
    for met in ['same_B8L2','cross_B8L2','net_B8L2','same_D10','cross_D10','net_D10','common_quality_within_abs','common_quality_cross_abs']:
        ee[met]=ee[met].where(qmask)
    values=['same_B8L2','cross_B8L2','net_B8L2','same_D10','cross_D10','net_D10','common_quality_within_abs','common_quality_cross_abs','A_failure','B_failure','C_failure','net_loss_gt5','net_loss_gt10']
    values += [x for x in ee.columns if x.startswith('net_') and x.removeprefix('net_') in METRICS and x not in values]
    aa,ii,bb,ss=summarize(ee,values)
    for tag,df in [('ANCHOR',aa),('IMAGE',ii),('BUILDING',bb),('SUMMARY',ss)]:save('background_gradient/ABC_'+tag+'.csv',df)
    risks=dict(registered_physical_ABC=len(E),common_ABC_scored=int(qmask.sum()),any_arm_failed_events=int(E[['A_failure','B_failure','C_failure']].any(axis=1).sum()),
        images_cross_absolute_Q_larger=int(ii.common_quality_cross_abs.gt(ii.common_quality_within_abs).sum()),images_evaluable=len(ii),
        buildings_cross_absolute_Q_larger=int(bb.common_quality_cross_abs.gt(bb.common_quality_within_abs).sum()),buildings_evaluable=len(bb))
    for arm in 'ABC':
        risks[arm+'_unique_failed_endpoints']=E.loc[E[arm+'_failure'],'team_'+arm].nunique()
        risks[arm+'_unique_endpoints']=E['team_'+arm].nunique()
        risks[arm+'_raw_failure_pct']=100*risks[arm+'_unique_failed_endpoints']/risks[arm+'_unique_endpoints']
        risks[arm+'_building_weighted_failure_pct']=100*ss[arm+'_failure'].iloc[0]
    for cutoff in [5,10]:
        col='net_loss_gt'+str(cutoff)
        risks[col+'_events']=int(E[col].sum());risks[col+'_evaluable']=int(E[col].notna().sum())
        risks[col+'_raw_pct']=100*risks[col+'_events']/risks[col+'_evaluable']
        risks[col+'_building_weighted_pct']=100*ss[col].iloc[0]
    save('background_gradient/ABC_RISK_AND_MAGNITUDE.csv',pd.DataFrame([risks]))
    time=ee[ee.recorded_time_single_source&qmask]
    if len(time):
        ta,ti,tb,ts=summarize(time,['same_B8L2','cross_B8L2','net_B8L2','net_recorded_time_pct'])
        save('background_gradient/ABC_QT_SUMMARY.csv',ts);save('background_gradient/ABC_QT_IMAGES.csv',ti)
    # Per-stage cumulative, endpoints are unique, A/B mirror cases not added.
    states=pd.DataFrame(scalars[0]) if False else pd.concat(scalars,ignore_index=True)
    assert not states.team_key.duplicated().any()
    receipt=dict(status='complete' if len(E)==len(requests) else 'partial',underlying_data='real_v2',registered_events=len(requests),completed_events=len(E),
        unique_physical_triples=E.physical_triple_id.nunique(),unique_endpoints=len(endpoints),new_native=int(states.endpoint_origin.str.startswith('new_native').sum()),
        reused=int(states.endpoint_origin.str.startswith('reused').sum()),images=E.image.nunique(),buildings=E.building.nunique(),anchors=E.anchor_id.nunique(),
        endpoint_states=states.score_status.value_counts().to_dict(),gradient_pairs=len(C),common_six_endpoint_gradient_pairs=int(C.common_six_endpoint_Q.sum()),
        same_composition_background_pairs=len(W),all_D_per_registered_XYZ_complete=bool(E.groupby('anchor_id').size().eq(14).all()),
        aggregation='pair/variant -> XYZ anchor -> image -> building, equal at each level',
        phase_identity='New fixed-XYZ background census; native adapter original literal closure strings are retained as adapter_origin, research_stage distinguishes this actual new calculation.',
        missing_new_endpoints=len(set(requests.team_A)|set(requests.team_B)|set(requests.team_C))-len(endpoints))
    old_physical=set(pd.read_csv(OLD/'structure/EVENTS_COMPLETE.csv.gz',usecols=['physical_triple_id']).physical_triple_id)
    receipt['prior_exact_physical_triples']=int(E.physical_triple_id.isin(old_physical).sum())
    receipt['new_physical_triples']=int((~E.physical_triple_id.isin(old_physical)).sum())
    write_json(OUT/'COMPLETION.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False))
    print('Gradient',S[[x for x in S if x.endswith('_B8L2') or x.startswith('net_change_B8L2_')]].to_dict('records'))
    print('ABC',ss[[x for x in ss if x in values[:8] or x.startswith('net_B8L2_')]].to_dict('records'))

if __name__=='__main__':main()
