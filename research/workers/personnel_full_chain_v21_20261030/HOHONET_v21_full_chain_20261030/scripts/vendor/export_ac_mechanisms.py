"""Export selected, already executed AC endpoints with complete native traces.

Selections are supplied externally after full study comparison (or explicitly
marked as capacity preselection). This script does not select outcomes, create
teams, fit labels, change references, or repair rings. Trace-only replay must
agree with the saved endpoint's scores, status and full geometry.
"""
from __future__ import annotations
import os
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
import argparse,collections,gzip,itertools,json,math,sys
from pathlib import Path
import numpy as np
import pandas as pd

def install_runtime(work):
    sys.path.insert(0,str(Path(work)/'HOHONET_v21_AC_population_20261029/stage02_engine/code'))
    import ac_endpoint_runtime as rt
    return rt

def write_gzip_json(path,data,rt):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.writing')
    with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=5) as f:
        json.dump(rt.clean(data),f,ensure_ascii=False,separators=(',',':'),allow_nan=False);f.flush()
    tmp.replace(path)
    with gzip.open(path,'rt') as f:json.load(f)

def selected_events(path,ids):
    found={}
    for chunk in pd.read_csv(path,chunksize=5000,dtype=str,keep_default_na=False):
        for row in chunk[chunk.event_id.isin(ids)].to_dict('records'):found[row['event_id']]=row
    assert set(found)==set(ids),(set(ids)-set(found))
    return found

def load_saved_endpoints(folder,events,rt):
    wanted=collections.defaultdict(set)
    for event in events.values():wanted[event['pool_id']].update([event['A_team_key'],event['C_team_key']])
    rows={}
    for pid,keys in wanted.items():
        source=Path(folder)/'pools'/pid;assert (source/'CHECKS.json').exists(),('unfinished_pool',pid)
        for path in sorted(source.glob('part_*.jsonl.gz')):
            for row in rt.iter_jsonl(path):
                if row['team_key'] in keys:
                    assert row['team_key'] not in rows;rows[row['team_key']]=row
        assert keys<=set(rows),(pid,keys-set(rows))
    return rows

def existing_traces(work,wanted,rt):
    cache={};root=Path(work)
    sources=[root/'HOHONET_v21_reaudit_20261029/stage04_cases/six_cases/traces',
             root/'HOHONET_v21_reaudit_20261029/stage04_cases/vfua_case/traces']
    for folder in sources:
        for path in folder.glob('*.json.gz'):
            case=rt.read_json(path)
            for row in case.get('arms',{}).values():
                if row.get('team_key') in wanted and row.get('full_state'):
                    cache[row['team_key']]=(row,str(path))
    return cache

def validate_trace(before,after,pool,rt):
    assert after['pool_id']==pool['pool_id'] and after['team_key']==before['team_key']
    assert rt.workers(after['member_workers'])==rt.workers(before['member_workers'])
    assert rt.workers(after['member_object_ids'])==rt.workers(before['member_object_ids'])
    for field in ['reference_id','reference_version']:assert after[field]==before[field]==pool['meta'][field]
    check=rt.replay_difference(before,after)
    g0,g1=before.get('geometry'),after.get('geometry');h0,h1=rt.digest(g0),rt.digest(g1);roundoff=[]
    exact=h0==h1
    if not exact:
        # A derived floor coordinate can differ by one binary floating-point
        # ULP while all ERP observations, output points, IDs/order and other
        # candidate fields remain bit-for-bit identical. Preserve both hashes
        # and exact difference paths; never allow an ERP/topology difference.
        assert isinstance(g0,dict) and isinstance(g1,dict)
        assert rt.digest({k:v for k,v in g0.items() if k!='footprint'})==rt.digest({k:v for k,v in g1.items() if k!='footprint'}),('non_footprint_geometry_changed',before['team_key'])
        f0,f1=g0.get('footprint'),g1.get('footprint');assert isinstance(f0,list) and isinstance(f1,list) and len(f0)==len(f1)
        for i,(p,q) in enumerate(zip(f0,f1)):
            assert len(p)==len(q)
            for j,(u,v) in enumerate(zip(p,q)):
                if u==v:continue
                assert math.isfinite(u) and math.isfinite(v)
                difference=abs(u-v);ulp=max(math.ulp(u),math.ulp(v))
                assert difference<=ulp,('derived_footprint_more_than_one_ulp',before['team_key'],i,j,u,v)
                roundoff.append({'path':f'geometry.footprint[{i}][{j}]','saved':u,'trace_replay':v,'absolute_difference':difference,'maximum_single_ulp':ulp})
    assert after.get('score_status')==before.get('score_status')
    state=after.get('full_state')
    if after.get('score_status')!='fusion_exception':
        assert state is not None and int(state['n'])==int(before['k'])
        assert int(state['minimum_support'])==math.ceil(int(before['k'])/2)
    return dict(check,full_geometry_json_hash_identical=exact,saved_geometry_sha256=h0,trace_geometry_sha256=h1,
                output_ERP_points_topology_ids_and_other_geometry_fields_exact=True,score_status_identical=True,
                derived_footprint_one_ulp_roundoff_only=bool(roundoff),derived_footprint_roundoff_differences=roundoff,
                maximum_derived_footprint_difference=max((x['absolute_difference'] for x in roundoff),default=0.))

def preserve_saved_endpoint_with_trace(before,after,check,rt):
    """Keep core study scalars/geometry untouched; attach the replay state.

    The raw replay candidate is retained inside full_state and separately when
    derived footprint rounding differs. It is never silently rewritten.
    """
    row=dict(before);row['full_state']=after.get('full_state')
    row['trace_replay_parity']=check
    row['trace_replay_scalar_values']={field:after.get(field) for field in rt.SCORE_PARITY_FIELDS}
    if not check['full_geometry_json_hash_identical']:
        row['trace_replay_geometry']=after.get('geometry')
        row['trace_replay_scalar_differences']=check['differences']
    return rt.clean(row)

def diagnose_case(case,median_pair,rt):
    event=case['event'];eid=event['event_id'];pool=case['pool'];armrows=case['arms']
    own={str(r['object_id']):r['worker_id'] for r in pool['records']}
    D=set(rt.workers(event.get('D_workers')));blocks={'A':set(rt.workers(event.get('X_workers'))),'C':set(rt.workers(event.get('Z_workers')))}
    output=collections.defaultdict(list);background_maps={};ref=np.array(case['reference']['points_1024x512'],float).reshape(-1,2,2)
    for arm,row in armrows.items():
        state=row.get('full_state') or {};groups=state.get('identity_groups',[]);selected={g['feature_id'] for g in groups if g['selected']}
        threshold=row.get('minimum_support');replacement=blocks[arm];which='X' if arm=='A' else 'Z';obsmap={};supporters={}
        assert set(row['member_workers'])==D|replacement
        for group in groups:
            members=group['members'];who={m.get('worker') or own[str(m['id'])] for m in members}
            assert len(who)==int(group['support']) and who<=set(row['member_workers'])
            assert bool(group['selected'])==(len(who)>=threshold)
            supporters[group['feature_id']]=who
            dm=[m for m in members if (m.get('worker') or own[str(m['id'])]) in D]
            xm=[m for m in members if (m.get('worker') or own[str(m['id'])]) in replacement]
            center=np.asarray(group.get('center') or [],float);located=center.shape==(2,2) and np.isfinite(center).all()
            if located:
                az=center[1,0];offsets=((az-ref[:,1,0]+512)%1024-512)*360/1024;nearest=int(np.argmin(abs(offsets)))
            else:nearest=None
            output['VOTE_GROUPS_BY_EVENT'].append(dict(event_id=eid,arm=arm,team_key=row['team_key'],feature_id=group['feature_id'],
                selected=bool(group['selected']),support=len(who),minimum_support=threshold,D_support=len(dm),replacement_support=len(xm),
                D_reaches_threshold_given_group=len(dm)>=threshold,replacement_reaches_threshold_given_group=len(xm)>=threshold,
                D_workers='|'.join(sorted(who&D)),replacement_workers='|'.join(sorted(who&replacement)),
                center_json=json.dumps(group['center'],separators=(',',':')),
                D_only_conditional_median_json=json.dumps(rt.clean(median_pair(dm)),separators=(',',':')) if dm else '',
                replacement_only_conditional_median_json=json.dumps(rt.clean(median_pair(xm)),separators=(',',':')) if xm else '',
                group_location_resolved=bool(located),nearest_reference_index_1based=nearest+1 if located else None,nearest_reference_horizontal_abs_deg=float(abs(offsets[nearest])) if located else None,
                nearest_reference_top_signed_offset_deg=float((center[0,1]-ref[nearest,0,1])*180/512) if located else None,
                nearest_reference_bottom_signed_offset_deg=float((center[1,1]-ref[nearest,1,1])*180/512) if located else None,
                all_group_fields_json=json.dumps(group,ensure_ascii=False,separators=(',',':'))))
            for member in members:
                worker=member.get('worker') or own[str(member['id'])];points=member['points'];block='D' if worker in D else which
                output['VOTE_MEMBERS_BY_EVENT'].append(dict(event_id=eid,arm=arm,team_key=row['team_key'],feature_id=group['feature_id'],selected=bool(group['selected']),
                    block=block,worker_id=worker,object_id=member['id'],source_pair_index=member['source_pair_index'],
                    top_x_px=points[0][0],top_y_px=points[0][1],bottom_x_px=points[1][0],bottom_y_px=points[1][1]))
                if block=='D':
                    key=(str(member['id']),int(member['source_pair_index']));assert key not in obsmap
                    obsmap[key]={'feature_id':group['feature_id'],'selected':bool(group['selected']),'center':group['center']}
        covering=[]
        for assignment in state.get('assignments',[]):
            features=assignment['feature_ids'];projection=[f for f in features if f in selected]
            # Match the frozen source_ring criterion exactly; subset coverage
            # alone would overlook duplicate projected features or <3 nodes.
            covers=len(selected)>=3 and len(projection)==len(selected) and set(projection)==selected
            if covers:covering.append(assignment['worker'])
            output['SOURCE_ASSIGNMENTS_BY_EVENT'].append(dict(event_id=eid,arm=arm,team_key=row['team_key'],worker_id=assignment['worker'],object_id=assignment['id'],
                source_ring_covers_all_selected=covers,source_feature_ids_json=json.dumps(features,separators=(',',':')),
                selected_projection_json=json.dumps(projection,separators=(',',':')),
                source_order_status=assignment.get('source_order_status'),source_ring_confirmed=assignment.get('source_ring_confirmed')))
        for edge in state.get('ring_diagnostics',{}).get('edges',[]):
            fields={k:(json.dumps(v,separators=(',',':')) if isinstance(v,(list,dict)) else v) for k,v in edge.items()}
            output['CONNECTION_EDGES_BY_EVENT'].append(dict(event_id=eid,arm=arm,team_key=row['team_key'],**fields))
        for index,alternative in enumerate(state.get('ring_diagnostics',{}).get('alternatives',[])):
            output['RING_ALTERNATIVES_BY_EVENT'].append(dict(event_id=eid,arm=arm,team_key=row['team_key'],alternative_index=index,alternative_json=json.dumps(alternative,separators=(',',':'))))
        for x,z in itertools.combinations(sorted(selected),2):
            shared=supporters[x]&supporters[z]
            output['SELECTED_GROUP_COOCCURRENCE'].append(dict(event_id=eid,arm=arm,team_key=row['team_key'],first_group=x,second_group=z,
                first_support=len(supporters[x]),second_support=len(supporters[z]),joint_observers_n=len(shared),joint_observers='|'.join(sorted(shared)),
                disjoint_support=not shared,note='No common observer is not by itself proof of mutually exclusive physical structures.'))
        summary={k:v for k,v in row.items() if not isinstance(v,(list,dict)) and k!='record_time_by_kind_json'}
        unresolved=sum(g['selected'] and g['center'] is None for g in groups)
        mechanism=('no_source_complete_projected_ring' if not covering else 'unresolved_selected_node_location' if unresolved else 'other_candidate_unavailable') if row.get('score_status')=='no_connection' else ''
        summary.update(event_id=eid,arm=arm,source_ring_covering_all_selected_n=len(covering),source_ring_covering_all_selected_workers='|'.join(sorted(covering)),
                       selected_unresolved_location_groups_n=unresolved,native_ring_reason=(state.get('ring_diagnostics') or {}).get('reason'),
                       native_candidate_reason=(state.get('candidate') or {}).get('reason'),no_connected_points_mechanism=mechanism)
        output['CASE_ARM_METRICS_AND_RING_COVERAGE'].append(summary);background_maps[arm]=obsmap
    a,c=background_maps['A'],background_maps['C']
    both_states=all(row.get('full_state') is not None for row in armrows.values())
    if both_states:assert set(a)==set(c)
    common=set(a)&set(c)
    changed=0;total=0
    for obs in sorted(common):
        output['COMMON_D_OBSERVATION_LINKS'].append(dict(event_id=eid,object_id=obs[0],source_pair_index=obs[1],A_group=a[obs]['feature_id'],C_group=c[obs]['feature_id'],
            A_selected=a[obs]['selected'],C_selected=c[obs]['selected'],A_center_json=json.dumps(a[obs]['center']),C_center_json=json.dumps(c[obs]['center'])))
    for u,v in itertools.combinations(sorted(common),2):
        total+=1;changed+=(a[u]['feature_id']==a[v]['feature_id'])!=(c[u]['feature_id']==c[v]['feature_id'])
    output['COMMON_D_COASSIGNMENT'].append(dict(event_id=eid,background_observations_n=len(common),A_background_observations_n=len(a),C_background_observations_n=len(c),both_full_states_available=both_states,
        observation_pairs_n=total,coassignment_changed_pairs_n=changed,
        coassignment_changed_fraction=changed/total if total else None,comparison_uses_original_observations_not_local_group_names=True))
    return output

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--repo',required=True);ap.add_argument('--work',required=True);ap.add_argument('--pools',nargs='+',required=True)
    ap.add_argument('--events',required=True);ap.add_argument('--selection',required=True);ap.add_argument('--endpoints',required=True);ap.add_argument('--metrics',required=True)
    ap.add_argument('--out',required=True);ap.add_argument('--labels');a=ap.parse_args();rt=install_runtime(a.work);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    selection=pd.read_csv(a.selection,dtype=str,keep_default_na=False);assert not selection.event_id.duplicated().any()
    choices={r['event_id']:r for r in selection.to_dict('records')};events=selected_events(a.events,choices)
    label_file=Path(a.labels) if a.labels else Path(a.work)/'HOHONET_v21_AC_population_20261029/stage00_intake/FINAL_LABELS_FOR_AC_ALL_LOBO.csv.gz'
    labels=pd.read_csv(label_file,dtype=str,keep_default_na=False)
    assert not labels.duplicated(['method','heldout_building','worker_id']).any()
    label_lookup={(r['method'],r['heldout_building'],r['worker_id']):r for r in labels.to_dict('records')}
    pools={p['pool_id']:p for fn in a.pools for p in rt.read_json(fn)['images']};saved=load_saved_endpoints(a.endpoints,events,rt)
    prior=existing_traces(a.work,set(saved),rt);traces={};parity=[];native=None;replays=0;reused=0
    bypool=collections.defaultdict(list)
    for key,row in saved.items():bypool[row['pool_id']].append(key)
    for pid,keys in bypool.items():
        pool=pools[pid];missing=[]
        for key in keys:
            local=out/'trace_endpoints'/(key+'.json.gz')
            if local.exists():row=rt.read_json(local);source=str(local)
            elif key in prior:row,source=prior[key]
            else:missing.append(key);continue
            validation_row=dict(row)
            if row.get('trace_replay_geometry') is not None:validation_row['geometry']=row['trace_replay_geometry']
            if row.get('trace_replay_scalar_values'):validation_row.update(row['trace_replay_scalar_values'])
            check=validate_trace(saved[key],validation_row,pool,rt);check.update(trace_acquisition='reused_full_trace',trace_source=source);parity.append(check)
            traces[key]=preserve_saved_endpoint_with_trace(saved[key],validation_row,check,rt);reused+=1
            if not local.exists():write_gzip_json(local,traces[key],rt)
        if missing:
            if native is None:native=rt.load_engine(a.repo)
            with native.Engine(full_state=True) as engine:
                for key in missing:
                    row=engine.evaluate(pool,rt.workers(saved[key]['member_workers']));geometry=row.get('geometry')
                    if geometry is not None:
                        extra=engine.scorecache.get(engine.fr.digest([row['k']==2,row.get('nodes'),geometry]))
                        if extra:row.update(extra)
                    check=validate_trace(saved[key],row,pool,rt);check.update(trace_acquisition='trace_only_replay_existing_team');parity.append(check)
                    for field in ['data_release','underlying_data_version','repository_commit','current_repository_commit','engine_digest','input_pool_sha256','reference_sha256','semantic_identity']:
                        if field in saved[key]:row[field]=saved[key][field]
                    row.update(trace_only_replay_existing_team=True,additional_new_physical_team=False)
                    traces[key]=preserve_saved_endpoint_with_trace(saved[key],row,check,rt)
                    traces[key].update(trace_only_replay_existing_team=True,additional_new_physical_team=False)
                    write_gzip_json(out/'trace_endpoints'/(key+'.json.gz'),traces[key],rt);replays+=1
    if native is None:native=rt.load_engine(a.repo)
    sys.path.insert(0,str(Path(a.repo).resolve()))
    from tools.thesis_main.analysis.fixed_identity_location_20261007 import median_pair
    all_tables=collections.defaultdict(list);index=[]
    for eid,event in events.items():
        pool=pools[event['pool_id']];metric_path=Path(a.metrics)/'metric_shards'/(event['pool_id']+'.csv.gz')
        metric=pd.read_csv(metric_path,low_memory=False);metric=metric[metric.event_id.eq(eid)];assert len(metric)==1
        case={'event':event,'selection':choices[eid],'pool':pool,'reference':pool['reference'],'metrics':rt.clean(metric.iloc[0].to_dict()),
              'arms':{arm:traces[event[arm+'_team_key']] for arm in ['A','C']},
              'frozen_lobo_labels':{r['worker_id']:label_lookup.get((event['method'],event['building'],r['worker_id']),{'known':'False','missing_reason':'no_frozen_fold_label'}) for r in pool['records']},
              'interpretation_limits':'Direct AC has no same-class B. Conditional subgroup medians keep the full-team identity grouping fixed, and are not D-only fusion outputs.'}
        write_gzip_json(out/'traces'/(eid+'.json.gz'),case,rt)
        for name,rows in diagnose_case(case,median_pair,rt).items():all_tables[name]+=rows
        index.append(dict(choices[eid],pool_id=event['pool_id'],image=event['image'],method=event['method'],n_A=event['n_A'],n_C=event['n_C'],m_X=event['m_X'],m_Z=event['m_Z'],
                          A_team_key=event['A_team_key'],C_team_key=event['C_team_key'],trace_file='traces/'+eid+'.json.gz'))
    for name,rows in all_tables.items():rt.write_csv(out/'tables'/(name+'.csv.gz'),rows)
    rt.write_csv(out/'CASE_INDEX.csv',index);rt.write_json(out/'TRACE_SCALAR_GEOMETRY_PARITY.json',parity)
    receipt={'cases':len(events),'unique_registered_endpoints':len(traces),'reused_full_traces':reused,'trace_only_replays_existing_teams':replays,'additional_new_physical_teams':0,
             'all_output_ERP_points_topology_ids_and_status_exact':True,'all_saved_core_endpoint_scalars_and_geometry_preserved':True,
             'full_geometry_json_hash_exact_endpoints':sum(x['full_geometry_json_hash_identical'] for x in parity),
             'derived_footprint_one_ulp_roundoff_only_endpoints':[x['team_key'] for x in parity if x['derived_footprint_one_ulp_roundoff_only']],
             'maximum_derived_footprint_roundoff':max((x['maximum_derived_footprint_difference'] for x in parity),default=0.),
             'all_score_values_status_and_Q_availability_passed_native_scalar_parity':True,
             'all_unselected_groups_preserved':True,'all_ring_diagnostics_and_source_assignments_preserved':True,
             'events_sha256':rt.sha(a.events),'selection_sha256':rt.sha(a.selection),'no_reference_label_or_fusion_rule_changes':True,
             'frozen_labels_sha256':rt.sha(label_file),
             'tables':{k:len(v) for k,v in all_tables.items()}}
    rt.write_json(out/'MECHANISM_EXPORT_RECEIPT.json',receipt);print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
