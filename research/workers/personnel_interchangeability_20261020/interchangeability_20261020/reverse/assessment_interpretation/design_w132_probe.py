#!/usr/bin/env python3
"""Post-assessment W132 mechanism probe; exact same-class substitutions only."""
from __future__ import annotations
import collections
import copy
import datetime
import gzip
import hashlib
import json
import sys
from pathlib import Path
import pandas as pd
from assessment_summary_common import BASE,ROOT,HERE,sha,stream_events,write_json

sys.path.insert(0,str(BASE/'code'))
from design_history_panel import team_key,digest
from design_nested_new2 import metadata_pools,SNAPSHOT

METHOD='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1'
FOCAL='W132'


def main():
    out=HERE/'w132_probe';out.mkdir(exist_ok=True)
    request=BASE/'assessment/nested_new2_requests.json.gz'
    lab=BASE/'reverse/mixed_fit/worker_labels.csv.gz'
    freeze=json.load(open(BASE/'assessment/ASSESSMENT_FREEZE.json'))
    assert sha(lab)==freeze['file_sha256']['reverse/mixed_fit/worker_labels.csv.gz']
    register=dict(schema='post_assessment_W132_same_class_probe_v1',registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        reason='Selected after the frozen assessment primary n13/m5 C02-to-C01 person-exclusion description: excluding any replaceable-block event containing W132 left 12 events/10 images/5 buildings and mean net Q about -0.078. That exclusion changes support; this probe holds each original event context fixed.',
        status='Post hoc mechanism probe, not a new independent validation and not used to redefine classes or primary rules.',
        universe='Exactly the 116 already frozen nested n13/m5 original ABC events, two directions and two fixed draws per supported pool.',
        intervention='If W132 occurs in the union of original A/B/C, enumerate every available pool worker with the same frozen C02 label who is not in that entire union; replace W132 by that same worker in every occurrence, leaving all other people unchanged.',
        roles=['A_outgoing_only','B_within_incoming_only','C_cross_incoming_only','shared_core','absent'],
        capacity='Retain no-eligible-replacement originals as such. W132-absent events contribute their baseline only. No change to n=13,m=5,source,reference,classes or memberships outside this one identity substitution.',
        aggregation='For each original event, equal all feasible replacements; then original events within pool, reference pools within true image, true images within building, buildings equally. Compare original and replacement on exactly the same supported original events. Both direction and W132 role strata; natural original panel remains separate.',
        outcomes=['C-minus-B B8L2 and D10','within/cross old joint, noQ, rich shape','quality tail and completeness','floor,prism,node,wall/corner diagnostics'],
        invariants=['A-only replacement leaves B/C and net quality exactly unchanged.','B/C/common-core substitutions keep composition and actual turnover unchanged.'],
        expansion='Exhaustive eligible same-C02 alternatives inside this fixed 116-event frame; not an exhaustive person or team study.',
        additional_selection='No further people, n/m, class definitions or rules may be chosen from these probe results.',
        original_request_sha256=sha(request),labels_sha256=sha(lab),snapshot_sha256=sha(SNAPSHOT),
        source_primary_removal_sha256=sha(HERE/'nested_new2/PERSON_REMOVAL_DESCRIPTIVE.csv.gz'))
    regpath=out/'REGISTER.json'
    if regpath.exists():
        prior=json.load(open(regpath))
        for key in register:
            if key!='registered_utc':assert prior[key]==register[key]
        register=prior
    else:write_json(regpath,register)
    # Registration is committed before generating alternatives or reading any new fusion.
    labels=pd.read_csv(lab);labels=labels[labels.method_id.eq(METHOD)&labels.known.astype(str).str.lower().isin(['true','1','1.0'])]
    mapping=dict(zip(labels.worker_id,labels.class_id));assert mapping[FOCAL]=='C02'
    pools={p['pool_id']:p for p in metadata_pools(SNAPSHOT,set(freeze['assessment_buildings']))}
    original=[e for e in stream_events(request) if e['method_id']==METHOD and e['n']==13 and e['m']==5]
    assert len(original)==116
    events=[];reqs={};ledger=[];links=[]
    listfields=['A_workers','B_workers','C_workers','core_workers','outgoing_workers','within_incoming','cross_incoming']
    def add(e):
        A,B,C=[set(e[a+'_workers']) for a in 'ABC'];core=set(e['core_workers'])
        assert len(A)==len(B)==len(C)==13 and A&B==A&C==B&C==core and len(core)==8
        assert len(A-B)==len(A-C)==len(B-C)==5
        for arm,ws in zip('ABC',[A,B,C]):
            assert collections.Counter(mapping[w] for w in ws)==collections.Counter(e[arm+'_counts'])
            tk=team_key(e['pool_id'],sorted(ws));e[arm+'_team_key']=tk
            req=dict(request_id=tk,pool_id=e['pool_id'],k=13,worker_ids=sorted(ws),reference_id=e['reference_id'],reference_version=e.get('reference_version'))
            if tk in reqs:assert reqs[tk]==req
            reqs[tk]=req
        events.append(e)
    for original_event in original:
        e=copy.deepcopy(original_event);pid=e['pool_id'];p=pools[pid]
        universe=set(e['A_workers'])|set(e['B_workers'])|set(e['C_workers'])
        if FOCAL in e['core_workers']:role='shared_core'
        elif FOCAL in e['outgoing_workers']:role='A_outgoing_only'
        elif FOCAL in e['within_incoming']:role='B_within_incoming_only'
        elif FOCAL in e['cross_incoming']:role='C_cross_incoming_only'
        else:role='absent'
        eligible=sorted(r['worker_id'] for r in p['records'] if r['origin']=='new' and mapping.get(r['worker_id'])=='C02' and r['worker_id'] not in universe) if role!='absent' else []
        assert len(eligible)==len(set(eligible))
        status='baseline_W132_absent' if role=='absent' else 'has_same_class_alternatives' if eligible else 'no_same_class_alternative_capacity'
        for key in ['path_id','added_core_worker','path_step','primary_role']:e.pop(key,None)
        e.update(parent_path_id=original_event['path_id'],parent_event_id=e['event_id'],
            context_id='posthoc_W132_same_class_substitution',probe_variant='original',probe_role=role,
            probe_replacement_worker=None,probe_status=status,probe_alternatives_n=len(eligible),
            analysis_status='post_assessment_mechanism_only')
        add(e)
        ledger.append(dict(parent_event_id=e['event_id'],pool_id=pid,image_id=e['image_id'],image=e['image'],building=e['building'],
            outgoing_class=e['outgoing_class'],incoming_class=e['incoming_class'],n=13,m=5,probe_role=role,status=status,
            alternatives=eligible,alternatives_n=len(eligible)))
        for repl in eligible:
            z=copy.deepcopy(e);z.update(event_id='P132_'+digest([e['event_id'],FOCAL,repl])[:22],probe_variant='same_class_replacement',probe_replacement_worker=repl)
            for field in listfields:z[field]=sorted(repl if w==FOCAL else w for w in z[field])
            assert all(FOCAL not in z[field] for field in listfields)
            if role=='A_outgoing_only':assert z['B_workers']==e['B_workers'] and z['C_workers']==e['C_workers']
            add(z)
            links.append(dict(parent_event_id=e['event_id'],probe_event_id=z['event_id'],replacement_worker=repl,probe_role=role,
                original_team_keys={a:e[a+'_team_key'] for a in 'ABC'},probe_team_keys={a:z[a+'_team_key'] for a in 'ABC'}))
    output=BASE/'assessment/w132_probe_requests.json.gz'
    write_json(output,dict(events=events,requests=list(reqs.values()),ledger=ledger,links=links,
        schema='same_class_post_assessment_probe_requests_v1',register_sha256=sha(regpath),original_request_sha256=sha(request)))
    receipt=dict(register_sha256=sha(regpath),request_sha256=sha(output),code_sha256=sha(Path(__file__)),
        original_events=len(original),probe_events=len(links),total_metric_events=len(events),unique_teams=len(reqs),
        pools=len({e['pool_id'] for e in events}),true_images=len({e['image_id'] for e in events}),buildings=len({e['building'] for e in events}),
        original_events_with_alternatives=sum(x['alternatives_n']>0 for x in ledger),
        original_absent=sum(x['probe_role']=='absent' for x in ledger),original_no_replacement_capacity=sum(x['status']=='no_same_class_alternative_capacity' for x in ledger),
        roles=dict(collections.Counter(e['probe_role'] for e in ledger)),
        exhaustive_only_within_registered_frame=True,no_probe_fusion_outcomes_opened_at_design=True)
    write_json(out/'DESIGN_RECEIPT.json',receipt);write_json(out/'CAPACITY_AND_EXACT_LINKS.json',dict(ledger=ledger,links=links))
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
