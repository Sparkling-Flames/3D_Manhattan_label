#!/usr/bin/env python3
"""Integrate exact event/endpoint identity and measured execution coverage.

Only reads registrations, final event indices and completion receipts. No
fusion, scoring, model fitting or change to qualifications is performed.
"""
from pathlib import Path
import argparse, json, os
import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent

def save(path,obj):
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def run(require_complete):
    ex=STUDY/'expanded_blocks';je=STUDY/'joint_exchange'
    registration=json.load((ex/'DESIGN_FREEZE.json').open())
    completed=[json.load(p.open()) for p in (ex/'results').glob('*/COMPLETION.json')]
    complete=len(completed)==registration['cells'] and sum(x['exported_events'] for x in completed)==registration['oriented_events']
    if require_complete:assert complete,'Registered expansion is not yet complete'
    frames=[]
    cols=['event_id','physical_triple_id','oriented_triple_id','team_A','team_B','team_C','condition','pool_id','building']
    for p in sorted(ex.glob('*_REGISTERED_EVENTS.csv.gz')):
        frames.append(pd.read_csv(p,usecols=cols,dtype=str,keep_default_na=False))
    a=pd.concat(frames,ignore_index=True);assert not a.event_id.duplicated().any()
    b=pd.read_csv(je/'ALL_EVENT_REFERENCE_INDEX.csv.gz',dtype=str,keep_default_na=False)
    assert not b.event_id.duplicated().any()
    # Physical triples are unordered actual team-key sets, not event labels.
    def triples(d):return {tuple(sorted([r.team_A,r.team_B,r.team_C])) for r in d.itertuples()}
    at,bt=triples(a),triples(b)
    akeys=set(a.team_A)|set(a.team_B)|set(a.team_C)
    bkeys=set(b.team_A)|set(b.team_B)|set(b.team_C)
    executions=[]
    for p in sorted((ex/'batches').glob('*/EXECUTION.json')):
        if not (p.parent/'COMPLETION.json').exists():continue
        r=json.load(p.open());c=json.load((p.parent/'COMPLETION.json').open())
        executions.append(dict(batch_id=r['batch_id'],requested=c['requested'],exported=c['exported'],
            new_native=r['new_native'],reused=r['reused'],resumed=r['resumed'],jobs=r['jobs'],
            batch_wall_seconds=r['seconds'],new_native_per_batch_wall_second=r['new_native']/r['seconds'],
            complete_evaluable=sum(x['complete'] for x in r['pools']),
            all_failures_retained=c['failures_retained']))
    native=pd.DataFrame(executions)
    native.to_csv(HERE/'NATIVE_BATCH_EXECUTION.csv',index=False,encoding='utf-8-sig')
    rows=[dict(stage='old_event_screening',identity='old_events_reaggregated_not_new_fusion',
        event_references=85203,registered_raw_rows=85570,complete=True),
        dict(stage='joint_exchange',identity='new_registered_comparisons_reused_and_new_endpoints',
        event_references=len(b),unique_physical_triples=len(bt),unique_endpoints=len(bkeys),complete=True),
        dict(stage='expanded_blocks',identity='new_finite_member_background_expansion',
        event_references=len(a),unique_physical_triples=len(at),unique_endpoints=len(akeys),complete=complete)]
    pd.DataFrame(rows).to_csv(HERE/'STAGE_COVERAGE.csv',index=False,encoding='utf-8-sig')
    result=dict(underlying_data_version='v2',research_round='effective_exchange_conditions_20261022',
        expansion_complete=complete,expanded_cells_complete=len(completed),expanded_cells_registered=registration['cells'],
        expanded_events_complete=sum(x['exported_events'] for x in completed),expanded_events_registered=len(a),
        joint_registered_events=len(b),new_registered_event_ids=len(set(a.event_id)|set(b.event_id)),
        duplicate_event_ids_between_new_studies=len(set(a.event_id)&set(b.event_id)),
        new_study_physical_triples_union=len(at|bt),physical_triples_overlap_between_new_studies=len(at&bt),
        necessary_endpoint_union=len(akeys|bkeys),endpoint_overlap_between_new_studies=len(akeys&bkeys),
        completed_native_batches=len(native),new_native_endpoints=int(native.new_native.sum()),
        exact_cached_endpoints_in_native_batches=int(native.reused.sum()),
        resumed_endpoints_in_execution_log=int(native.resumed.sum()),
        summed_batch_wall_seconds=float(native.batch_wall_seconds.sum()),
        new_native_per_summed_batch_wall_second=float(native.new_native.sum()/native.batch_wall_seconds.sum()),
        throughput_note='Measured executor wall time of sequential batches with up to 3 pool workers; not production annotation time.',
        not_all_full_pool_member_combinations=True,not_all_orders_expanded=True,
        full_space_denominator_sources=['expanded_blocks/EXACT_FULL_SPACE_LEDGER.csv.gz',
            'expanded_blocks/analysis/CANONICAL_CONFIGURATION_MEMBER_COVERAGE.csv.gz',
            'joint_exchange/OPPORTUNITY_COMPLETION.csv'],
        aggregation_unit='background then image then building, separately by condition and layer')
    save(HERE/'ROUND_COVERAGE.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--require-complete',action='store_true');a=p.parse_args();run(a.require_complete)
