"""Finite global screening frame fixed by history/inputs, not fusion outcomes."""
import argparse,collections,itertools,json,math
from pathlib import Path
from capacity_space import read_json,read_labels,capacities,exact_counts,canonical_hash,write_csv
from register_adaptive import write_json

GRID=[(6,2),(8,4),(10,3),(10,7),(12,4),(12,6),(12,8),(14,7),(16,4),(18,7),(20,5),(20,6),(24,4),(26,3)]

def select_frame(pools,phases,deps,new_primary_limit=17):
    phase={r['pool_id']:r for r in phases};changed={r['pool_id'] for r in deps if r['action']=='new_or_changed_pool'}
    selected={p['pool_id']:'legacy_screen_fixed_image_frame' for p in pools if p['pool_id'] in phase and phase[p['pool_id']]['phase']=='screen'}
    selected.update({p['pool_id']:'all_admitted_other_targets' for p in pools if p['meta'].get('analysis_scope')=='admitted_other_target'})
    # Actual extension marks analysis_scope with another explicit name in some
    # stages; caller supplies the separately admitted target file membership.
    byid={p['pool_id']:p for p in pools}
    candidates=[p for p in pools if p['pool_id'] in changed and p['pool_id'] not in selected and p['meta']['layer']=='ordinary_manual']
    groups=collections.defaultdict(list)
    for p in candidates:groups[p['meta']['building'],p['meta']['difficulty']].append(p)
    for g in groups.values():g.sort(key=lambda p:canonical_hash(['v21_screen_new',p['pool_id']]))
    existing={byid[pid]['meta']['building'] for pid in selected};added=[]
    order=sorted(groups,key=lambda g:(g[0] in existing,canonical_hash(['group',g])))
    while len(added)<new_primary_limit and any(groups.values()):
        for g in order:
            if groups[g] and len(added)<new_primary_limit:added.append(groups[g].pop(0))
    selected.update({p['pool_id']:'v21_changed_primary_balanced_building_difficulty' for p in added})
    return selected

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--primary-pools',required=True);ap.add_argument('--other-pools',required=True)
    ap.add_argument('--labels',required=True);ap.add_argument('--phases',required=True);ap.add_argument('--dependencies',required=True)
    ap.add_argument('--output',required=True);ap.add_argument('--new-primary-limit',type=int,default=17)
    a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    primary=read_json(a.primary_pools)['images'];other=read_json(a.other_pools)['images'];pools=primary+other
    selected=select_frame(pools,read_labels(a.phases),read_json(a.dependencies),a.new_primary_limit)
    selected.update({p['pool_id']:'all_admitted_other_targets' for p in other})
    inventory=[dict(p['meta'],pool_id=p['pool_id'],selected=p['pool_id'] in selected,selection_reason=selected.get(p['pool_id'],'outside_finite_screen_retained_in_capacity_inventory')) for p in pools]
    write_csv(out/'SCREEN_POOL_FRAME.csv',inventory)
    lookup=collections.defaultdict(list)
    for r in read_labels(a.labels):
        if r['heldout_building']=='ALL' or r.get('condition','manual') not in ('manual','joint','both',''):continue
        lookup[r['method'],r['heldout_building']].append(r)
    cells=[];opportunities=[]
    for p in pools:
        pid=p['pool_id'];meta=p['meta'];N=len(p['records'])
        if pid not in selected or meta['condition']!='manual':continue
        grids=GRID if N>=12 else [(n,m) for n in range(3,N+1) for m in range(1,N//3+1) if n>=m and n+2*m<=N]
        for (meth,b),ll in lookup.items():
            if b!=meta['building']:continue
            groups=capacities(p,ll);known={c:ws for c,ws in groups.items() if c!='unknown'}
            for s,t in itertools.permutations(sorted(known),2):
                S,T=len(groups[s]),len(groups[t]);legal=0
                for n,m in grids:
                    if m<=n and S>=2*m and T>=m and N>=n+2*m:
                        legal+=1;cells.append(dict(pool_id=pid,image=meta['image'],building=b,condition='manual',layer=meta['layer'],
                            analysis_scope=meta.get('analysis_scope','primary_target'),difficulty=meta.get('difficulty'),method=meth,source_class=s,target_class=t,
                            n=n,m=m,pool_n=N,source_capacity=S,target_capacity=T,replacement_fraction=m/n,source_candidate_fraction=m/S,
                            selection_phase='v21_global_internal_screen',frame_reason=selected[pid],**exact_counts(N,S,T,n,m)))
                opportunities.append(dict(pool_id=pid,method=meth,source_class=s,target_class=t,source_capacity=S,target_capacity=T,grid_cells=legal,
                    eligibility_reason='feasible_grid' if legal else 'no_strict_ABC_capacity_in_screen_grid'))
    write_csv(out/'SCREEN_CELLS.csv.gz',cells);write_csv(out/'SCREEN_CAPACITY_BY_DIRECTION.csv.gz',opportunities)
    report=dict(labels=a.labels,frozen_public_grid=GRID,small_pool_rule='N<12: every feasible integer n>=3,m>=1',
        selected_pools=len(selected),selected_manual=sum(r['selected'] and r['condition']=='manual' for r in inventory),
        buildings=len({r['building'] for r in inventory if r['selected']}),methods=len({r['method'] for r in cells}),cells=len(cells),
        max_events_1XYZ_1D=len(cells),naive_max_endpoints=3*len(cells),
        selection_excludes_target_fusion_results=True,full_member_enumeration=False,
        scope='All viable class directions within the finite input-selected pool frame and fixed n/m grid. Full capacity space retained separately.')
    write_json(out/'SCREEN_PLAN.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
