from __future__ import annotations
import json,itertools,gzip
from pathlib import Path
import numpy as np
from core import *
from run_domains import HUMAN,human_probe

def merge_history(nodes,dist,tau,targets,worker_constraint=True):
    groups,z=partition(nodes,dist,tau,worker_constraint)
    members={i:[i] for i in range(len(nodes))}; target_roots={t:t for t in targets};steps=[]; first=None
    for step,(aa,bb,height,count) in enumerate(z):
        a,b=int(aa),int(bb);merged=members[a]+members[b]; newid=len(nodes)+step;members[newid]=merged
        if height>tau:break
        target_in=[v for v in targets if v in merged]
        if not target_in:continue
        for target in target_in:target_roots[target]=newid
        roots=set(target_roots.values());whole=sorted({v for root in roots for v in members[root]})
        blockers=[]
        for i,j in itertools.combinations(whole,2):
            same_worker=nodes[i]['worker']==nodes[j]['worker']
            if dist[i,j]>tau or (worker_constraint and same_worker):
                blockers.append(dict(nodes=[key(nodes[i]),key(nodes[j])],distance_deg=float(dist[i,j]),
                                     same_worker=same_worker,distance_exceeds=bool(dist[i,j]>tau)))
        row=dict(step=step,height_deg=float(height),left=[key(nodes[i]) for i in members[a]],right=[key(nodes[i]) for i in members[b]],
                 target_members=[key(nodes[i]) for i in target_in],
                 current_target_components=[[key(nodes[i]) for i in members[root]] for root in sorted(roots)],
                 obstructions=blockers,
                 definition='first incompatibility anywhere in the union of CURRENT target-bearing clusters, not only a third party versus a requested target')
        steps.append(row)
        if blockers and first is None:first=row
    return dict(worker_constraint=worker_constraint,steps=steps,first_irreversible_obstruction=first,
                final_partition=[g for g in groups if any(i in g for i in targets)],
                same_worker_collision_groups=[[key(nodes[i]) for i in g] for g in groups if len({nodes[i]['worker'] for i in g})<len(g)])

def unb_split(ns,ds,gs,tau):
    seed=next(i for i,n in enumerate(ns) if key(n)==('R00144',0))
    lower=next(g for g in gs if seed in g);rn=[ns[i] for i in lower]
    td=ds['top'][np.ix_(lower,lower)];tg,_=partition(rn,td,tau)
    known={('R00144',0):'low_glass_top',('R00526',0):'glass_to_ceiling',('R02210',0):'glass_to_ceiling'}
    modes=[]
    for group in tg:
        ix=[lower[j] for j in group]
        modes.append(dict(members=[key(ns[i]) for i in ix],geometric_support=len(ix),
            known_semantic_members={name:[key(ns[i]) for i in ix if known.get(key(ns[i]))==name] for name in sorted(set(known.values()))},
            unknown_members=[key(ns[i]) for i in ix if key(ns[i]) not in known],
            center=center(ns,ix,ds['pair']),top_diameter_deg=float(ds['top'][np.ix_(ix,ix)].max()),
            semantic_interpretation='unknown_except_explicitly_reviewed_individuals',majority_gate_applied=False))
    target_nodes={name:[i for i in lower if known.get(key(ns[i]))==name] for name in sorted(set(known.values()))}
    target_nodes['unknown']=[i for i in lower if key(ns[i]) not in known]
    return dict(threshold_deg=tau,roster_denominator=15,bottom_group=lower,bottom_members=[key(ns[i]) for i in lower],
        bottom_support=len(lower),bottom_support_interpretation='geometric group; only three tentative same-corner judgments, rest unreviewed',
        bottom_centroid_full_pair_proxy=center(ns,lower,ds['pair']),geometric_top_subgroups=modes,
        targets=[dict(target=name,members=[key(ns[i]) for i in inds],top_support=len(inds),bottom_marginal_support=len(lower),
              original_pair_incidence=len(inds),center_of_own_sources=center(ns,inds,ds['pair']) if inds and name!='unknown' else None,
              raw_paired_points=[ns[i]['points'] for i in inds],full_roster_fraction=len(inds)/15,has_semantic_label=name!='unknown') for name,inds in target_nodes.items()],
        pairing_policy='retain original incidence; do not duplicate bottom marginal as top or joint support',
        single_upper_target_selected=False,complete_layout_created=False,
        reviewed_members_outside_this_bottom_group=[list(k) for k in known if k not in {key(ns[i]) for i in lower}],
        endpoint_center_alignment='not_applied; conditional top and bottom estimates retain separate longitudes, no new shared-x pair is asserted')

def run(root:Path,out:Path):
    out.mkdir(exist_ok=False,parents=True)
    cfg=json.loads((root/'config.json').read_text());hist=[];unb=[]
    for code in ['rPc6DW4iMge-06','uNb9QFRL6hY-67']:
        ns=nodes_from_records(json.loads((root/'inputs'/f'{code}.json').read_text())['records']);ds=distances(ns)
        if code.startswith('rPc'):
            rv=HUMAN['rpc'];ix=[next(i for i,n in enumerate(ns) if key(n)==tuple(k)) for k in rv['must']]
            for t in cfg['thresholds_deg']:
                for m in cfg['metrics']:
                    for constraint in (True,False):
                        hist.append(dict(threshold=t,metric=m,**merge_history(ns,ds[m],t,ix,constraint)))
        else:
            for t in cfg['thresholds_deg']:
                gs,_=partition(ns,ds['bottom'],t);unb.append(unb_split(ns,ds,gs,t))
    (out/'rpc_merge_histories.json').write_text(json.dumps(hist,ensure_ascii=False,indent=2))
    (out/'unb_target_layers.json').write_text(json.dumps(unb,ensure_ascii=False,indent=2))
    # All feasible human-compatible alternatives, not just the numerically selected one.
    droot=out.parent/'domains';ns=json.loads((droot/'node_lookup.json').read_text())['rPc6DW4iMge-06'];alts=[]
    target=[next(i for i,n in enumerate(ns) if key(n)==tuple(k)) for k in HUMAN['rpc']['must']]
    wrong=next(i for i,n in enumerate(ns) if key(n)==tuple(HUMAN['rpc']['rejected']))
    for f in sorted(droot.glob('rPc*.json')):
        dd=json.loads(f.read_text());dom=dd['domain']; assist=dd['human_assisted'] or {}
        if assist.get('status') in ['constraints_outside_local_domain','infeasible_constraints']:continue
        if not set(target)<=set(dom['union']):continue
        count=0;mi=1000;ma=0;mincost=float('inf');maxcost=0.;histogram={};all_core=None;anymembers=set();best_details=[]
        with gzip.open(droot/dd['all_candidate_ledger'],'rt') as fh:
            for line in fh:
                r=json.loads(line);g=next(g for g in r['blocks'] if target[0] in g)
                if not set(target)<=set(g) or wrong in g:continue
                count+=1;mi=min(mi,len(g));ma=max(ma,len(g));mincost=min(mincost,r['cost']);maxcost=max(maxcost,r['cost']);histogram[len(g)]=histogram.get(len(g),0)+1
                all_core=set(g) if all_core is None else all_core&set(g);anymembers|=set(g)
        alts.append(dict(domain_id=dom['domain_id'],human_feasible_count=count,target_group_size_range=[mi,ma],target_size_histogram=histogram,
            cost_range=[mincost,maxcost],forced_same_group_members=[key(ns[i]) for i in sorted(all_core or [])],
            possible_same_group_members=[key(ns[i]) for i in sorted(anymembers)],
            interpretation='conditional feasible set in this two-block domain, not probabilities or semantic correctness of all members'))
    (out/'rpc_all_assisted_alternatives_summary.json').write_text(json.dumps(alts,ensure_ascii=False,indent=2))
    for h in hist:
        if h['threshold']==5:
            x=h['first_irreversible_obstruction']; print(h['metric'],h['worker_constraint'],'first',x)
    print('UNB5',json.dumps(next(u for u in unb if u['threshold_deg']==5),ensure_ascii=False))
    print('ASSISTED5',[a for a in alts if '_5_' in a['domain_id']])
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.root,a.out)
