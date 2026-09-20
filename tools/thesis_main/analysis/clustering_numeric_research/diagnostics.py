"""Small predeclared diagnostics: tie handling, minority definition, and finite-pool limits."""
import collections,itertools,json,math,hashlib
import numpy as np,pandas as pd
from common import *
from prefix_replay import PrefixEngine

def main():
    groups=load_groups();raw,by=rawdata();ties=[];variants=[];minor=[];floor=[]
    rng=np.random.default_rng(20260920)
    for key,g in groups.items():
        n=len(g['ids']);N=g['N']
        for metric,d0 in g['matrices']['automatic'].items():
            d=np.round(d0,8);t=nominal_cut(metric,9);base=np.array(g['labels'][f'automatic:{metric}:complete:9']);tri=np.triu_indices(n,1)
            seen={};changed_runs=0;maxchange=0
            for rep in range(50):
                order=rng.permutation(n)
                ll=fcluster(linkage(squareform(d[np.ix_(order,order)]),method='complete'),t,criterion='distance') if n>1 else np.ones(1,int)
                lab=np.empty(n,int);lab[order]=ll;lab=canonical_labels(lab)
                changed=int((coassign(base)[tri]!=coassign(lab)[tri]).sum());changed_runs+=changed>0;maxchange=max(maxchange,changed)
                signature=hashlib.sha256(coassign(lab).tobytes()).hexdigest()
                if signature not in seen:seen[signature]=dict(labels=lab.tolist(),example_permutation=order.tolist())
            ties.append(dict(key=key,code=g['code'],condition=g['condition'],metric=metric,N=n,nominal_cut=9,permutations=50,unique_partitions_observed=len(seen),changed_runs=changed_runs,max_changed_pair_relations=maxchange,interpretation='row-order tie alternatives, not semantic alternatives validated'))
            if len(seen)>1:variants.append(dict(key=key,metric=metric,ids=g['ids'],workers=g['workers'],variants=list(seen.values())))
            near=d<=t
            samecount=np.array([by[x]['effective_point_count'] for x in g['ids']]);same=(samecount[:,None]==samecount[None,:]);deg=near.sum(1)-1;cp=same.sum(1)-1
            floor.append(dict(key=key,code=g['code'],condition=g['condition'],metric=metric,N=n,geometrically_isolated_people=int((deg==0).sum()),no_samecount_people=int((cp==0).sum()),isolated_despite_samecount_people=int(((deg==0)&(cp>0)).sum()),finite_pool_final_next_uncovered=float((deg==0).mean()) if n>1 else np.nan))
            for kind in ['complete','representative']:
                l=g['labels'][f'automatic:{metric}:{kind}:9'];sizes=list(collections.Counter(l).values())
                for minimum_support in [1,2]:
                    for fraction in [.1,.2,1/3]:
                        allowed=[s for s in sizes if s>=minimum_support and s/N<=fraction];total=sum(allowed)/N
                        for k in [3,5,8,12,16]:
                            if k>N:continue
                            den=math.comb(N,k);missing=sum(s/N*(math.comb(N-s,k)/den if k<=N-s else 0) for s in allowed)
                            minor.append(dict(key=key,code=g['code'],condition=g['condition'],metric=metric,partition=kind,N=N,k=k,minimum_support=minimum_support,maximum_fraction=fraction,total_minority_mass=total,expected_unseen_minority_pool_mass=missing,expected_covered_minority_fraction=1-missing/total if total else np.nan,threshold_is_descriptive_sensitivity_not_truth=True))
    td=save('diagnostics/equal_distance_roworder_sensitivity.csv',ties);dump('diagnostics/equal_distance_partition_variants.json',variants);md=save('diagnostics/minority_definition_sensitivity.csv.gz',minor);save('diagnostics/finite_pool_isolation_floor.csv',floor)
    # Concrete observed prefix events, rebuilt from coordinates/masks rather than
    # reading a hindsight full-pool partition or guessing from cluster counts.
    ev=pd.read_csv(OUT/'prefix_churn_events.csv.gz');byunit={g['unit']:g for g in groups.values()};examples=[]
    for method_index in [8,9]:
        z=ev[(ev.pool=='effective_history')&(ev.view=='automatic')&(ev.method_index==method_index)&(ev.cluster_count_delta<0)]
        if not len(z):continue
        e=z.sort_values(['cluster_count_delta','changed_old_pairs'],ascending=[True,False]).iloc[0];g=byunit[int(e.unit)];eng=PrefixEngine(g['matrices']['automatic'],g['ids'])
        oldmask=int(e.old_mask);newmask=int(e.new_mask);a=eng.node(oldmask);b=eng.node(newmask);oldix=eng.indices(oldmask);newix=eng.indices(newmask)
        def encode(ix,l):return [dict(id=g['ids'][i],worker=g['workers'][i],cluster=int(c)) for i,c in zip(ix,l)]
        examples.append(dict(code=g['code'],key=g['key'],replicate=int(e.replicate),k=int(e.k),method=eng.methods[method_index],changed_old_pairs=int(e.changed_old_pairs),old_pair_denominator=int(e.old_pair_denominator),before=encode(oldix,a[1][method_index]),after=encode(newix,b[1][method_index]),added_workers=[g['workers'][i] for i in newix if i not in set(oldix)],before_clusters=int(a[0][method_index,0]),after_clusters=int(b[0][method_index,0]),meaning='algorithmic re-partition after adding a real response, not people retracting earlier opinions'))
    dump('diagnostics/prefix_cluster_count_drop_examples.json',examples)
    # Reproduce pre-existing RC2 composition summaries on the identical sphere pool.
    a=pd.read_csv(OUT/'personnel/compositions_by_exact_subtype.csv.gz');a=a[a.metric=='sphere'].rename(columns={'nominal_cut':'cut','signature':'subtype_counts'})
    b=pd.read_csv(SOURCE/'rc2_received/results/personnel_real_fourperson_compositions.csv');keys=['key','config','cut','pattern','subtype_counts'];a=a.set_index(keys).sort_index();b=b.set_index(keys).sort_index();assert a.index.equals(b.index);assert (a.teams==b.teams).all()
    err={c:float((a[c]-b[c]).abs().max()) for c in ['team_pair_incompatible','validation_uncovered']}
    dump('DIAGNOSTIC_AUDIT.json',dict(tie_experiment_permutations=50,unit_metric_comparisons=len(td),unit_metric_pairs_with_roworder_tie_alternatives=int((td.unique_partitions_observed>1).sum()),units_with_any_roworder_tie_alternatives=int(td[td.unique_partitions_observed>1].key.nunique()),production_order_still_canonical=True,minority_sensitivity_rows=len(md),existing_RC2_composition_rows_reproduced=len(a),existing_RC2_composition_max_error=err,preexisting_team_count_mismatches=0,no_new_threshold_selected=True))
    print(td[td.unique_partitions_observed>1].to_string(index=False),flush=True)
if __name__=='__main__':main()
