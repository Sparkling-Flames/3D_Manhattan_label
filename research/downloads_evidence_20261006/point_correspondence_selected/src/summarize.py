"""Human-readable, deterministic summaries of saved research results; no policy selection."""
from pathlib import Path
from collections import Counter
import csv,json

def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def run(root,out):
    result=out.parent;domain=result/'domains';look=json.loads((domain/'node_lookup.json').read_text())
    states=json.loads((domain/'domains_summary.json').read_text());out.mkdir(parents=True,exist_ok=False)
    def node(ns,i):return {k:ns[i].get(k) for k in ['id','worker','pair_index','source_pair_index','source_point_indices','points','source_ring_confirmed']}
    moves=[];details=[];roster=[]
    for code,ns in look.items():
        for n in ns:roster.append(dict(image=code,**n))
    for s in states:
        if not s.get('domain_id'):continue
        d=json.loads((domain/(s['domain_id']+'.json')).read_text());ns=look[s['image']]
        for policy,p in [('automatic',d['automatic']),('human_assisted',d['human_assisted'])]:
            if p is None:continue
            if not p.get('selected_ids'):
                moves.append(dict(domain_id=s['domain_id'],image=s['image'],threshold=s['threshold'],metric=s['metric'],policy=policy,status=p['status'],candidate_id=None,moved_records='',old_new_sizes='',lost_relations=None,new_relations=None,identical_pairs_split=None,correct_triple_together=None,wrong_triple_together=None,dispersion=None,edit_count=None))
            for c in d['selected_details']:
                if c['local_id'] not in p['selected_ids']:continue
                change=[[node(ns,i) for i in v] for v in c['moved_nodes_alternative_alignments']]
                dr=dict(domain_id=s['domain_id'],image=s['image'],threshold=s['threshold'],metric=s['metric'],policy=policy,status=p['status'],candidate_id=c['local_id'],moved=change,
                    baseline_groups=[[node(ns,i) for i in g] for g in d['domain']['baseline_blocks']],new_groups=[[node(ns,i) for i in g] for g in c['blocks']],
                    lost_coassignment_pairs=[[node(ns,i) for i in pair] for pair in c['lost_coassignments']],added_coassignment_pairs=[[node(ns,i) for i in pair] for pair in c['added_coassignments']],
                    identical_coordinates_newly_split=[[node(ns,i) for i in pair] for pair in c['newly_split_identical_coordinates']],
                    centers=c['centers'],diameters_deg=c['diameters_checked_deg'],full_roster_denominator=c['roster_denominator'],
                    full_observation_count=c['full_observation_count'],full_unique_observations=c['full_unique_observations'],outside_groups_unchanged=c['outside_groups_unchanged'],
                    same_worker_collisions=c['new_same_worker_collisions'],diameter_violations=c['new_diameter_violations'],human_development_probe=c.get('human_development_probe'),
                    interpretation='changed coassignment is not a semantic error or correction for unreviewed members; no new ring')
                details.append(dr)
                hp=c.get('human_development_probe',{})
                moves.append(dict(domain_id=s['domain_id'],image=s['image'],threshold=s['threshold'],metric=s['metric'],policy=policy,status=p['status'],candidate_id=c['local_id'],
                    moved_records=' | '.join(','.join(x['id']+':'+str(x['pair_index']) for x in a) for a in change),old_new_sizes=f"{[len(g) for g in d['domain']['baseline_blocks']]} -> {c['supports']}",lost_relations=len(c['lost_coassignments']),new_relations=len(c['added_coassignments']),identical_pairs_split=len(c['newly_split_identical_coordinates']),correct_triple_together=hp.get('same_group'),wrong_triple_together=hp.get('wrong_triple_same_group'),dispersion=c['cost'],edit_count=c['edit_count']))
    write_csv(out/'selected_movement_summary.csv',moves)
    (out/'selected_movements_full.json').write_text(json.dumps(details,ensure_ascii=False,indent=2))
    write_csv(out/'all_original_observations.csv',[{**r,'points':json.dumps(r['points']),'source_point_indices':json.dumps(r['source_point_indices'])} for r in roster])
    probes=json.loads((domain/'development_probes.json').read_text());expect=json.loads((root/'upstream/reported_checks.json').read_text());checks=[]
    for a in expect['items']:
        p=next(p for p in probes if all(p[k]==a[k] for k in ['image','threshold','metric']))
        tol=5e-7 if a.get('rounded_source') else 1e-10
        local=p['local_diameters_deg'][a['metric']];ok=abs(local-a['local_max'])<=tol and p['supports']==a['supports']
        if 'union_max' in a:ok=ok and abs(p['whole_union_diameter']-a['union_max'])<=1e-10
        checks.append(dict(expected=a,observed=p,passed=bool(ok),tolerance=tol))
    (out/'source_scalar_crosschecks.json').write_text(json.dumps(dict(scope=expect['scope'],checks=checks),ensure_ascii=False,indent=2))
    summary=dict(full_records=sum(len(json.loads(p.read_text())['records']) for p in (root/'inputs').glob('*-*.json')),
        pair_observations=sum(map(len,look.values())),baseline_metric_threshold_states=len(json.loads((domain/'baseline_partitions.json').read_text())),
        development_probes=len(probes),local_domains=sum(s.get('domain_id') is not None for s in states),no_local_domain_states=sum(s.get('domain_id') is None for s in states),
        enumerated_feasible_partitions=sum(s.get('feasible',0) for s in states),automatic_statuses=dict(Counter(s['automatic']['status'] for s in states if s.get('automatic'))),
        assisted_statuses=dict(Counter(s['assisted']['status'] for s in states if s.get('assisted'))),
        rpc_automatic_correct=any(any(s.get('automatic_triple_same',[])) for s in states if s['image'].startswith('rPc')),
        all_source_scalar_crosschecks_passed=all(x['passed'] for x in checks),
        all_selected_outside_memberships_fixed=all(d['outside_groups_unchanged'] for d in details),
        all_selected_valid_constraints=all(not d['same_worker_collisions'] and not d['diameter_violations'] for d in details),
        complete_layout_created=False,reference_used=False,visual_validation=False)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));return summary
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(run(a.root,a.out))
