"""Validate AC interface on previously saved endpoints; no new scientific runs."""
import argparse,collections,copy,gzip,json,sys,tempfile
from pathlib import Path
import pandas as pd
from ac_endpoint_runtime import digest,write_json,merge_csv_shards
import ac_measure_events as adapter

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--work',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    repo=Path(a.repo);work=Path(a.work)
    sys.path.insert(0,str(repo/'research/workers/personnel_v21_reselection_20261029/analysis'))
    from measure_registered_events import METRICS
    from legacy_geometry_diagnostics import refdiagnostic,geometry_metrics
    poolfiles=[repo/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',repo/'research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json']
    pools={p['pool_id']:p for fn in poolfiles for p in json.load(open(fn))['images']}
    by=collections.defaultdict(list)
    with gzip.open(work/'HOHONET_v21_reaudit_20261029/stage03_completed_abc/ENDPOINT_GEOMETRY.jsonl.gz','rt') as f:
        for line in f:
            row=json.loads(line);by[row['pool_id']].append(row)
    tested=[]
    for status in ['complete_conditional','no_connection','below_four','invalid_floor']:
        for pid,rows in by.items():
            selected=[r for r in rows if r.get('score_status')==status]
            if not selected:continue
            C=selected[0];A=next(r for r in rows if r['team_key']!=C['team_key'] and r.get('score_status')=='complete_conditional')
            event=pd.DataFrame([{'event_id':'offline_'+status,'pool_id':pid,'A_team_key':A['team_key'],'C_team_key':C['team_key']}])
            result=adapter.compute(event,{r['team_key']:copy.deepcopy(r) for r in [A,C]},pools[pid],METRICS,refdiagnostic,geometry_metrics)
            assert bool(result.iloc[0].C_Q_missing)==(status!='complete_conditional')
            if status!='complete_conditional':assert pd.isna(result.iloc[0].B8L2_CA)
            assert not result.columns.duplicated().any()
            tested.append({'target_status':status,'Q_missing':bool(result.iloc[0].C_Q_missing),'floor_geometry_pair':bool(result.iloc[0].geometry_floor_pair)})
            break
    # Fill the actual registered column schema with one archived exact A/C
    # relation. This is interface validation, not a newly registered study event.
    preview=work/'HOHONET_v21_AC_population_20261029/stage01_design_review/AC_EVENT_SCHEMA_PREVIEW.csv'
    cols=list(pd.read_csv(preview,nrows=0).columns)
    old=pd.read_csv(work/'HOHONET_v21_reaudit_20261029/stage03_completed_abc/EVENTS_EXACT.csv.gz',nrows=1).iloc[0].to_dict()
    event={k:old.get(k,None) for k in cols};pid=old['pool_id']
    rows={r['team_key']:copy.deepcopy(r) for r in by[pid] if r['team_key'] in [old['A_team_key'],old['C_team_key']]}
    event.update(A_workers=old['A_members'],C_workers=old['C_members'],D_workers=old['D'],X_workers=old['X'],Z_workers=old['Z'],
                 n_A=old['n'],n_C=old['n'],m_X=old['m'],m_Z=old['m'],D_n=old['n']-old['m'],delta_n=0,equal_team_size=True,
                 event_id='offline_full_registered_schema',physical_pair_id=digest([pid,sorted([old['A_team_key'],old['C_team_key']])])[:24])
    result=adapter.compute(pd.DataFrame([event]),rows,pools[pid],METRICS,refdiagnostic,geometry_metrics)
    assert not result.columns.duplicated().any()
    bad=dict(event,physical_pair_id='deliberate_interface_mismatch')
    mismatch_rejected=False
    try:adapter.compute(pd.DataFrame([bad]),copy.deepcopy(rows),pools[pid],METRICS,refdiagnostic,geometry_metrics)
    except AssertionError as exc:mismatch_rejected='registered_and_measured_field_disagree' in str(exc)
    assert mismatch_rejected
    with tempfile.TemporaryDirectory(prefix='ac_interface_') as tmp:
        tmp=Path(tmp)
        pd.DataFrame([{'id':'a','x':1}]).to_csv(tmp/'a.csv.gz',index=False)
        pd.DataFrame([{'id':'b','y':2}]).to_csv(tmp/'b.csv.gz',index=False)
        receipt=merge_csv_shards([tmp/'a.csv.gz',tmp/'b.csv.gz'],tmp/'all.csv.gz','id',{'a','b'})
        actual=pd.read_csv(tmp/'all.csv.gz');assert len(actual)==2 and list(actual.columns)==['id','x','y']
    report={'passed':True,'cases':tested,'actual_design_schema_columns':len(cols),'measured_columns_with_full_schema':len(result.columns),
            'duplicate_registered_derived_fields_checked':True,'deliberate_pair_id_disagreement_rejected':mismatch_rejected,
            'streaming_column_union_gzip_verified':receipt,'fusion_calls':0,'score_calls':0,'classification_fits':0,'new_teams':0,
            'scope':'Interface validation using archived exact endpoints; these synthetic validation metadata are excluded from study events.'}
    write_json(Path(a.out).parent/'MEASUREMENT_SCHEMA_WITH_DEFINITIONS.json',{'columns':list(result.columns),'definitions':adapter.dictionary(METRICS),'source':'Interface schema only; no new study outcomes.'})
    write_json(a.out,report);print(json.dumps(report),flush=True)

if __name__=='__main__':main()
