"""Measure frozen direct A/C events from saved native endpoints, without fusion.

The adapter retains the existing v2.1 scalar metrics and geometry algorithms.
It adds explicit output-state denominators, signed geometric changes, physical
pair identities, and recording-source comparability for equal/unequal teams.
No B team or cross-versus-within claim is created.
"""
from __future__ import annotations
import os
for _name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_name]='1'
import argparse,collections,json,math,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
from ac_endpoint_runtime import digest,finite,read_json,iter_jsonl,sha,workers,write_json,write_csv,merge_csv_shards,verify_csv_shard

RAW_STATUS=['score_status','geometry_status','geometry_reason','order_status','complete_evaluable',
            'complete_floor_evaluable','floor_evaluable','connection_available','below_four','location_unresolved',
            'record_time_by_kind_json','endpoint_acquisition','semantic_identity']
PAIR_GEOMETRY=['geometry_bev_distance','geometry_centroid_distance','geometry_log_area_distance',
               'geometry_pair_angle','geometry_top_angle','geometry_bottom_angle','geometry_unmatched_pairs','geometry_same_pair_count']
FLAGS=['Q_missing','D10_missing','fusion_execution_exception','insufficient_nodes','connection_failure',
       'fusion_structural_failure','output_invalid_geometry','fusion_failure_observed','measurement_exception',
       'reference_floor_only','two_person_deferred','other_Q_missing','floor_geometry_available',
       'complete_output_geometry_available','output_not_complete']

def truth(v):return v is True or (isinstance(v,(float,int)) and v==1) or str(v).lower()=='true'
def output_status(row):
    s=str(row.get('score_status') or '')
    q_missing=not finite(row.get('B8L2'));geometry=row.get('geometry') or {}
    footprint=geometry.get('footprint')
    valid_floor=False
    if footprint is not None and len(footprint)>=3:
        from shapely.geometry import Polygon
        polygon=Polygon(footprint);valid_floor=bool(polygon.is_valid and polygon.area>0)
    exception=s=='fusion_exception';below=s=='below_four' or truth(row.get('below_four'))
    no_connection=s=='no_connection';invalid=s in ('invalid_floor','invalid_full_geometry')
    structural=exception or below or no_connection
    measurement=s=='measurement_exception';floor_ref=s=='floor_only_reference';two=s=='two_person_deferred'
    complete=truth(row.get('complete_evaluable'))
    return dict(Q_missing=q_missing,D10_missing=not finite(row.get('D10')),
        fusion_execution_exception=exception,insufficient_nodes=below,connection_failure=no_connection,
        fusion_structural_failure=structural,output_invalid_geometry=invalid,fusion_failure_observed=structural or invalid,
        measurement_exception=measurement,reference_floor_only=floor_ref,two_person_deferred=two,
        other_Q_missing=q_missing and not(structural or invalid or measurement or floor_ref or two),
        floor_geometry_available=valid_floor,complete_output_geometry_available=valid_floor and complete,
        output_not_complete=not complete,output_state=s if s else 'Q_present_status_unknown' if not q_missing else 'Q_missing_status_unknown')

def time_info(row):
    source=row.get('record_time_by_kind_json') or {}
    if isinstance(source,str):source=json.loads(source)
    active={k:v for k,v in source.items() if int(v.get('n',0))>0}
    known=bool(active) and all(v.get('known_n')==v.get('n') and finite(v.get('total_seconds')) and float(v['total_seconds'])>=0 for v in active.values())
    signature=json.dumps(sorted((k,v['n']) for k,v in active.items()),separators=(',',':'))
    single=next(iter(active)) if len(active)==1 else ''
    total=sum(float(v['total_seconds']) for v in active.values()) if known else np.nan
    return dict(time_source_count_signature=signature,all_time_sources_known=known,
                single_time_source=single,known_record_time_total_seconds=total)

def validate_members(event,A,C,pool):
    aw=set(workers(A['member_workers']));cw=set(workers(C['member_workers']))
    assert A['pool_id']==C['pool_id']==pool['pool_id']==event['pool_id']
    for field in ['reference_id','reference_version']:
        assert A[field]==C[field]==pool['meta'][field],(event['event_id'],field)
    for arm,ws in [('A',aw),('C',cw)]:
        assert len(ws)==int((A if arm=='A' else C)['k'])
        for field in [arm+'_members',arm+'_workers',arm+'_member_workers']:
            if field in event and pd.notna(event[field]) and str(event[field]):assert set(workers(event[field]))==ws,(event['event_id'],field)
        nfield='n_'+arm
        if nfield in event and pd.notna(event[nfield]):assert int(event[nfield])==len(ws),(event['event_id'],nfield)
    d=aw&cw;x=aw-cw;z=cw-aw
    for block,ws in [('D',d),('X',x),('Z',z)]:
        for field in [block,block+'_members',block+'_workers']:
            if field in event and pd.notna(event[field]) and str(event[field]):assert set(workers(event[field]))==ws,(event['event_id'],field)
    if 'm' in event and pd.notna(event['m']) and len(aw)==len(cw):assert int(event['m'])==len(x)==len(z),(event['event_id'],'m')
    return dict(n_A_actual=len(aw),n_C_actual=len(cw),D_n_actual=len(d),X_n_actual=len(x),Z_n_actual=len(z),
                equal_team_size=len(aw)==len(cw),equal_replacement_size=len(x)==len(z),
                actual_D_members='|'.join(sorted(d)),actual_X_members='|'.join(sorted(x)),actual_Z_members='|'.join(sorted(z)),
                replacement_fraction_A=len(x)/len(aw),replacement_fraction_C=len(z)/len(cw),
                actual_A_minimum_support=A.get('minimum_support'),actual_C_minimum_support=C.get('minimum_support'),
                X_can_reach_A_MV50_by_size=finite(A.get('minimum_support')) and len(x)>=A['minimum_support'],
                Z_can_reach_C_MV50_by_size=finite(C.get('minimum_support')) and len(z)>=C['minimum_support'],
                D_can_reach_A_MV50_by_size=finite(A.get('minimum_support')) and len(d)>=A['minimum_support'],
                D_can_reach_C_MV50_by_size=finite(C.get('minimum_support')) and len(d)>=C['minimum_support'])

def compute(events,rows,pool,metrics,refdiagnostic,geometry_metrics):
    assert 'B_team_key' not in events,'Direct AC must not silently inherit an ABC record.'
    for row in rows.values():
        refdiagnostic(row,pool)
        if row.get('nodes') is not None:
            rn=len(pool['reference']['points_1024x512'])//2
            row['reference_node_shortfall']=max(0,rn-row['nodes']);row['reference_node_excess']=max(0,row['nodes']-rn)
        row.update(output_status(row));row.update(time_info(row))
    scal=pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(list,dict))} for r in rows.values()]).set_index('team_key')
    metric_list=list(dict.fromkeys(metrics+['known_record_time_total_seconds','source_time_known_n','source_time_known_sum_seconds']))
    values={};arms={}
    for arm in ['A','C']:
        ar=scal.reindex(events[arm+'_team_key']);ar.index=events.index;arms[arm]=ar
        assert ar.index.equals(events.index)
        for field in metric_list:values[arm+'_'+field]=pd.to_numeric(ar[field],errors='coerce') if field in ar else pd.Series(np.nan,index=events.index)
        for field in RAW_STATUS+FLAGS+['output_state','single_time_source','all_time_sources_known','time_source_count_signature']:
            values[arm+'_'+field]=ar[field] if field in ar else pd.Series(None,index=events.index,dtype=object)
    for field in metric_list:
        delta=values['C_'+field]-values['A_'+field]
        values[field+'_CA']=delta;values[field+'_abs_CA']=delta.abs()
    for field in ['B8L2','D10']:
        delta=values[field+'_CA'];ok=delta.notna()
        values[field+'_pair_valid']=ok
        values[field+'_increase_CA']=(delta>1e-9).astype(float).where(ok)
        values[field+'_decrease_CA']=(delta<-1e-9).astype(float).where(ok)
        values[field+'_nearzero_CA']=(delta.abs()<=1e-9).astype(float).where(ok)
        values[field+'_loss10_CA']=(delta<-10).astype(float).where(ok)
    values['AC_scored']=values['B8L2_pair_valid']
    # Separate missing Q from native failures, including transitions with no Q pair.
    for field in ['Q_missing','fusion_structural_failure','output_invalid_geometry','fusion_failure_observed','measurement_exception','output_not_complete']:
        av=values['A_'+field].astype(bool);cv=values['C_'+field].astype(bool)
        values[field+'_introduced_CA']=(~av&cv).astype(int)
        values[field+'_resolved_CA']=(av&~cv).astype(int)
        values[field+'_risk_change_CA']=cv.astype(int)-av.astype(int)
    values['output_state_transition']=values['A_output_state'].astype(str)+' -> '+values['C_output_state'].astype(str)
    sigA=values['A_time_source_count_signature'];sigC=values['C_time_source_count_signature']
    known=values['A_all_time_sources_known'].astype(bool)&values['C_all_time_sources_known'].astype(bool)
    singleA=values['A_single_time_source'];singleC=values['C_single_time_source']
    matched=known&sigA.eq(sigC);single=known&singleA.ne('')&singleA.eq(singleC)
    values['time_comparable_source_count_AC']=matched
    values['time_comparable_single_source_AC']=single
    values['time_comparable_AC']=matched
    ta,tc=values['A_known_record_time_total_seconds'],values['C_known_record_time_total_seconds']
    raw=100*(tc/ta-1).where(ta>0)
    values['record_time_CA_pct_raw_all_known']=raw
    values['record_time_CA_seconds_source_matched']=(tc-ta).where(matched)
    values['record_time_CA_pct_source_matched']=raw.where(matched)
    values['record_time_CA_seconds_single_source']=(tc-ta).where(single)
    values['record_time_CA_pct_single_source']=raw.where(single)
    geometry=[];pair_cache={};identity=[]
    for event in events.to_dict('records'):
        A,C=rows[event['A_team_key']],rows[event['C_team_key']]
        ids=validate_members(event,A,C,pool);identity.append(ids)
        pair=tuple(sorted([event['A_team_key'],event['C_team_key']]))
        if pair not in pair_cache:pair_cache[pair]=geometry_metrics(rows[pair[0]],rows[pair[1]])
        both_complete=A['complete_output_geometry_available'] and C['complete_output_geometry_available']
        geo={field+'_AC':pair_cache[pair].get(field,np.nan) for field in PAIR_GEOMETRY}
        geo.update({field+'_AC_complete_outputs_only':value if both_complete else np.nan for field,value in pair_cache[pair].items()})
        geo.update(physical_pair_id=digest([pool['pool_id'],pair])[:24],ordered_physical_pair_id=digest([pool['pool_id'],event['A_team_key'],event['C_team_key']])[:24],
                   geometry_complete_pair=both_complete,geometry_floor_pair=A['floor_geometry_available'] and C['floor_geometry_available'])
        geometry.append(geo)
    ids=pd.DataFrame(identity)
    meanA=ta/ids.n_A_actual;meanC=tc/ids.n_C_actual
    values['record_time_per_member_CA_seconds_single_source']=(meanC-meanA).where(single)
    values['record_time_per_member_CA_pct_single_source']=100*(meanC/meanA-1).where(single&(meanA>0))
    for field in ['geometry_area_h2','height_mean_h']:
        av,cv=values['A_'+field],values['C_'+field];valid=(av>0)&(cv>0)
        values[field+'_ratio_CA']=(cv/av).where(valid)
        values[field+'_log_ratio_CA']=np.log((cv/av).where(valid))
        values[field+'_pct_CA']=(100*(cv/av-1)).where(valid)
    # Preserve design metadata but validate duplicate derived fields, rather
    # than concatenating two equal_team_size/physical_pair_id columns.
    derived=pd.concat([pd.DataFrame(values).reset_index(drop=True),ids,pd.DataFrame(geometry)],axis=1)
    original=events.reset_index(drop=True).copy()
    for field in set(original)&set(derived):
        av,bv=original[field],derived[field]
        if field in ('equal_team_size','equal_replacement_size'):
            same=av.map(truth).eq(bv.map(truth))
        else:
            same=av.fillna('').astype(str).eq(bv.fillna('').astype(str))
        assert same.all(),('registered_and_measured_field_disagree',field,original.loc[~same,'event_id'].head().tolist())
        original=original.drop(columns=field)
    result=pd.concat([original,derived],axis=1)
    assert not result.columns.duplicated().any(),list(result.columns[result.columns.duplicated()])
    return result

def dictionary(metrics):
    return {'data_release':'v2.1','difference_orientation':'C minus A; positive is a numerical increase, not universally improvement',
      'missing':'Missing metric remains missing; no Q=0 imputation. Pair deltas require both values; status transitions use all executed pairs.',
      'direct_AC_limit':'No B team: this table does not estimate cross-class amplitude above same-class replacement amplitude.',
      'geometry_bev_distance_AC':{'definition':'1 - intersection-over-union of valid floor polygons','unit':'dimensionless','range':[0,1],'correction':'This is NOT camera-height units; old outputs are preserved.'},
      'geometry_centroid_distance_AC':{'definition':'Distance between floor polygon centroids','unit':'h (normalized camera height)'},
      'geometry_area_h2_CA':{'definition':'C floor area minus A floor area','unit':'h^2'},
      'centroid_x_h_CA / centroid_z_h_CA':{'definition':'Signed change in floor centroid coordinates','unit':'h'},
      'geometry_log_area_distance_AC':{'definition':'Absolute log(C area / A area)','unit':'dimensionless'},
      'geometry_area_h2_log_ratio_CA':{'definition':'Signed log(C area / A area)','unit':'dimensionless'},
      'geometry_pair_angle_AC / geometry_top_angle_AC / geometry_bottom_angle_AC':{'definition':'Unchanged Hungarian-matched ray angular differences','unit':'degree','caution':'Matching is per pair; unmatched cardinality is reported separately.'},
      'geometry_floor_pair':'Both floor polygons valid; includes partial below-four output. Complete-output-only metrics have separate columns.',
      'fusion_structural_failure':'score_status fusion_exception/below_four/no_connection (or explicit below_four flag)',
      'output_invalid_geometry':'score_status invalid_floor or invalid_full_geometry',
      'fusion_failure_observed':'Explicit structural failure or invalid geometry; excludes measurement exception, missing reference and unexplained missing Q.',
      'Q_missing':'B8L2 unavailable, independent of its cause; always report score_status.',
      'other_Q_missing':'Missing B8L2 not explained by defined structural/geometry/measurement/reference/two-person statuses.',
      'source_matched_time':'Both teams have all known logged values and the identical per-source record-count vector.',
      'single_source_time':'Both teams have all known logged values from the same single recording source. For unequal n the total also changes with team size; per-member values accompany it.',
      'recorded_time':'Observed annotation labor, not fusion CPU duration and not a new prospective speed measurement.',
      'MV50_size_flags':'Necessary capacity check only. A block of m persons can independently reach threshold by size if m>=minimum_support; actual vote-group support needs full trace.',
      'physical_pair_id':'Unordered exact A/C pair; common across methods. Do not count repeats as independent evidence.',
      'metrics_retained_from_previous_v21_adapter':metrics,'new_fusions':0,'new_scores':0,'new_labels':0}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--repo',required=True);ap.add_argument('--events',required=True)
    ap.add_argument('--endpoints',required=True);ap.add_argument('--pools',nargs='+',required=True);ap.add_argument('--target-conditions')
    ap.add_argument('--out',required=True);ap.add_argument('--partial',action='store_true')
    ap.add_argument('--watch',action='store_true',help='Measure each finished endpoint pool once, wait for all pools, merge once at the end.')
    ap.add_argument('--shards-only',action='store_true',help='Save verified pool shards without materializing the combined CSV in this pass.')
    a=ap.parse_args()
    sys.path.insert(0,str(Path(a.repo)/'research/workers/personnel_v21_reselection_20261029/analysis'))
    from measure_registered_events import METRICS,save
    from legacy_geometry_diagnostics import refdiagnostic,geometry_metrics
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);events=pd.read_csv(a.events,low_memory=False)
    assert not events.event_id.duplicated().any()
    pools={p['pool_id']:p for fn in a.pools for p in read_json(fn)['images']}
    targets=pd.read_csv(a.target_conditions).set_index('pool_id') if a.target_conditions else None
    contract={'events_sha256':sha(a.events),'pool_sources':{str(Path(p).resolve()):sha(p) for p in a.pools},
              'adapter_sha256':sha(__file__),'geometry_adapter_sha256':sha(Path(a.repo)/'research/workers/personnel_v21_reselection_20261029/analysis/legacy_geometry_diagnostics.py'),
              'metric_adapter_sha256':sha(Path(a.repo)/'research/workers/personnel_v21_reselection_20261029/analysis/measure_registered_events.py')}
    cp=out/'MEASUREMENT_INPUT_CONTRACT.json'
    if cp.exists():assert read_json(cp)==contract,'Resume requires unchanged input events, geometry algorithm and adapter.'
    else:write_json(cp,contract)
    done=[];start=time.monotonic();endpoint_ids=set(events.A_team_key)|set(events.C_team_key);physical_pairs=set();measured_events=0
    group_indices=events.groupby('pool_id',sort=True).indices
    remaining=set(group_indices);write_json(out/'METRIC_DICTIONARY.json',dictionary(METRICS))
    while remaining:
        before=len(remaining)
        for pid in sorted(remaining):
            dest=out/'metric_shards'/(pid+'.csv.gz');source=Path(a.endpoints)/'pools'/pid
            if not dest.exists() and not (source/'CHECKS.json').exists():continue
            g=events.iloc[group_indices[pid]].reset_index(drop=True)
            needed=set(g.A_team_key)|set(g.C_team_key)
            if dest.exists():
                measured=pd.read_csv(dest,usecols=['event_id','physical_pair_id'],low_memory=False)
                assert list(measured.event_id)==list(g.event_id)
                physical_pairs.update(measured.physical_pair_id);measured_events+=len(measured);done.append(dest);remaining.remove(pid);continue
            rows={}
            for p in sorted(source.glob('part_*.jsonl.gz')):
                for row in iter_jsonl(p):
                    if row['team_key'] in needed:
                        assert row['team_key'] not in rows;rows[row['team_key']]=row
            assert set(rows)==needed,(pid,len(rows),len(needed))
            measured=compute(g,rows,pools[pid],METRICS,refdiagnostic,geometry_metrics)
            if targets is not None:
                for field in ['official_difficulty','scope','geometric_challenge','structural_condition','ref_turn5','ref_H','ref_short_edges','legal_targets_in_image_condition']:
                    if field in targets and field not in measured:measured[field]=targets.at[pid,field]
            measured['data_release']='v2.1';save(dest,measured)
            verify_csv_shard(dest,'event_id',set(g.event_id));done.append(dest);remaining.remove(pid)
            physical_pairs.update(measured.physical_pair_id);measured_events+=len(measured)
            write_json(out/'PROGRESS.json',{'pools_done':len(done),'total_pools':len(group_indices),'events_done':measured_events,'pending_pools':sorted(remaining),'seconds':time.monotonic()-start,'watch':a.watch})
            print(json.dumps({'pool_id':pid,'events':len(measured),'AC_scored':int(measured.AC_scored.sum())}),flush=True)
        if not a.watch:break
        if remaining and len(remaining)==before:time.sleep(3)
    pending=sorted(remaining)
    if done and not a.shards_only:
        merged=merge_csv_shards(done,out/'EVENT_METRICS.csv.gz','event_id')
        assert merged['rows']==measured_events
    receipt={'registered_events':len(events),'measured_events':measured_events,'pools':len(done),'pending_pools':pending,'complete':not pending,
             'events_sha256':sha(a.events),'unique_requested_endpoints':len(endpoint_ids),'unique_physical_pairs':len(physical_pairs),
             'new_fusions':0,'new_scores':0,'new_labels':0,'same_vs_cross_amplitude_estimable':False,
             'Q_missing_separate_from_fusion_failure':True,'Q_missing_never_imputed':True,
             'watch':a.watch,'combined_csv_saved':bool(done) and not a.shards_only,
             'seconds':time.monotonic()-start}
    write_json(out/'MEASUREMENT_RECEIPT.json',receipt);print(json.dumps(receipt),flush=True)
    if pending and not a.partial:raise RuntimeError(f'{len(pending)} pools pending; completed shards retained.')

if __name__=='__main__':main()
