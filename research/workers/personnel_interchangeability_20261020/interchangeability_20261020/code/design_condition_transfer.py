"""Predeclared same-person Manual/Semi category-block condition comparison.

Uses only pairs of frozen pools with the same image/reference and their actual
worker intersection. Each ABC member set is identical in Manual and Semi, which
separates observed task-condition interaction from a change of sampled people.
This is not randomized assignment or net initialization-error correction.
"""
from __future__ import annotations
import argparse, collections, copy, datetime
from pathlib import Path
from design_history_panel import read, write, digest, team_key
from design_blocks import labels_from,candidate_frame,stratified_sample,event_for

METHODS=[('F20_highQ23_T_qK2','all','new'),
         ('F20_new_Scope_qK2','all','new'),
         ('F20_new_NewNonedit_qK2','all','new'),
         ('F20_new_NewEdit_qK2','all','new'),
         ('F20_semiV1_Edit_qK2','semi_v1','v1')]
SEED=2026102015

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True)
    ap.add_argument('--split',type=Path,required=True);ap.add_argument('--labels',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    split=read(a.split);maps=labels_from([a.labels]);pools=read(a.snapshot)['images']
    groups=collections.defaultdict(dict)
    for p in pools:
        if p['meta']['layer'] not in ['ordinary_manual','ordinary_semi']:continue
        if p['meta']['building'] in split['history_buildings']:continue
        groups[p['meta']['image']][p['meta']['condition']]=p
    requests={};events=[];links=[];ledger=[]
    for image,pair in sorted(groups.items()):
        if set(pair)!= {'manual','semi'}:continue
        manual,semi=pair['manual'],pair['semi']
        if manual['meta']['reference_id']!=semi['meta']['reference_id']:
            ledger.append(dict(image=image,reason='different_frozen_references'));continue
        common=set(r['worker_id'] for r in manual['records']) & set(r['worker_id'] for r in semi['records'])
        phase='discovery' if manual['meta']['building'] in split['discovery_buildings'] else 'assessment'
        for mid,domain,origin in METHODS:
            eligible_common={w for w in common if next(r for r in manual['records'] if r['worker_id']==w)['origin']==origin}
            derived=dict(manual,records=[r for r in manual['records'] if r['worker_id'] in eligible_common])
            method=dict(method_id=mid,domain=domain,family='fixed_condition_transfer',
                        context_id='same_crew_'+origin,allowed_origins=[origin],
                        matching_policies=['source_matched'])
            frame,excluded,caps=candidate_frame(derived,method,maps[mid,domain])
            selected=stratified_sample(frame,24,[SEED,phase,image,mid,domain])
            for rank,candidate in enumerate(selected):
                e,reason=event_for(derived,method,maps[mid,domain],candidate,SEED,phase,rank)
                if reason:continue
                linkid='CT20_'+digest([SEED,phase,image,mid,rank])[:22];ids={}
                for cond,pool in [('manual',manual),('semi',semi)]:
                    x=copy.deepcopy(e);x.update(pool_id=pool['pool_id'],layer=pool['meta']['layer'],condition=cond,
                        event_id=linkid+'_'+cond,condition_link_id=linkid,context_id='same_crew_'+origin+'_'+cond)
                    for arm in 'ABC':
                        tk=team_key(pool['pool_id'],x[arm+'_workers']);x[arm+'_team_key']=tk
                        requests.setdefault(tk,dict(request_id=tk,pool_id=pool['pool_id'],k=x['n'],worker_ids=x[arm+'_workers']))
                    events.append(x);ids[cond]=x['event_id']
                links.append(dict(condition_link_id=linkid,phase=phase,image=image,building=e['building'],method_id=mid,domain=domain,
                    n=e['n'],m=e['m'],direction=e['direction'],reference_id=e['reference_id'],origin=origin,
                    manual_event_id=ids['manual'],semi_event_id=ids['semi']))
            ledger.append(dict(image=image,phase=phase,method_id=mid,domain=domain,origin=origin,common_workers=sorted(eligible_common),
                class_capacities=caps,finite_contexts=len(frame),selected_contexts=len(selected),capacity_exclusions=excluded,
                interpretation='Exact same ABC members and reference in both observed task conditions; no randomized condition assignment.'))
    spec=dict(schema='same_crew_condition_transfer_v1',seed=SEED,registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        methods=METHODS,selection='Five user-motivated fixed variable routes registered without this batch outcomes; both reused-v2 discovery and assessment subsets; no result-based rule selection.',
        sources='New and v1 separately; ordinary Manual/Semi only, shared exact reference; target/source durations separate; missing initial geometry is never fabricated.',
        frame='All feasible integer n,m and ordered pure-class directions, 24 stratified contexts per same-image/source/method; same members in each condition.')
    write(a.out,dict(spec=spec,requests=list(requests.values()),events=events,links=links,ledger=ledger))
    print(dict(events=len(events),linked_ABC=len(links),unique_teams=len(requests),images=len({x['image'] for x in links}),buildings=len({x['building'] for x in links}),n=sorted({x['n'] for x in links}),m=sorted({x['m'] for x in links})))

if __name__=='__main__':main()
