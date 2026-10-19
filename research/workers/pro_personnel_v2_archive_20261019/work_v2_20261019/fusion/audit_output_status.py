"""Keep computable geometric completeness distinct from human-approved output."""
from collections import Counter
from pool_io import OUT,load_pools,read,save,csv

def main():
    statuses=[];counts=[]
    for p in load_pools():
        target=OUT/'pools'/p['pool_id']
        if not (target/'states.json.gz').exists():continue
        rows=read(target/'request_results.json.gz')['results'];by_team={r['team_id']:r for r in rows};multiplicity=Counter(r['team_id'] for r in rows)
        local=Counter()
        for r in read(target/'states.json.gz')['states']:
            state=r['automatic'];row=by_team[r['team_id']];candidate=state['candidate'] if state is not None else {}
            status=dict(pool_id=p['pool_id'],image=p['meta']['image'],building=p['meta']['building'],layer=p['meta']['layer'],
                team_id=r['team_id'],request_multiplicity=multiplicity[r['team_id']],k=row['k'],
                candidate_status=candidate.get('status','fusion_exception'),candidate_reason=candidate.get('reason'),
                output_ring_confirmed=candidate.get('ring_confirmed'),order_status=candidate.get('order_status'),
                geometry_status=candidate.get('geometry_status'),connection_available=row['connection_available'],
                complete_geometry_evaluable=row['complete_evaluable'],B8L2_available=row['B8L2'] is not None,
                human_identity_review_applied=False,human_order_intervention_applied=False)
            statuses.append(status)
            local[(status['candidate_status'],status['output_ring_confirmed'],status['order_status'],status['complete_geometry_evaluable'])]+=1
        for key,n in local.items():counts.append(dict(pool_id=p['pool_id'],building=p['meta']['building'],layer=p['meta']['layer'],
            candidate_status=key[0],output_ring_confirmed=key[1],order_status=key[2],complete_geometry_evaluable=key[3],unique_teams=n))
    csv(OUT/'UNIQUE_TEAM_OUTPUT_STATUS.csv',statuses);csv(OUT/'OUTPUT_STATUS_COVERAGE.csv',counts)
    save(OUT/'OUTPUT_STATUS_AUDIT.json',dict(unique_teams=len(statuses),requests=sum(r['request_multiplicity'] for r in statuses),
        complete_geometry_evaluable=sum(r['complete_geometry_evaluable'] for r in statuses),
        complete_but_not_human_confirmed=sum(r['complete_geometry_evaluable'] and not r['output_ring_confirmed'] for r in statuses),
        human_confirmed_output_rings=sum(r['output_ring_confirmed'] is True for r in statuses),
        statuses=dict(Counter(r['candidate_status'] for r in statuses)),
        interpretation='Complete means computable automatic geometry only. geometry_review/source_suggestion retains unresolved human identity/order judgement; no claimed delivery acceptance or human certification.'))
    print(read(OUT/'OUTPUT_STATUS_AUDIT.json'),flush=True)

if __name__=='__main__':main()
