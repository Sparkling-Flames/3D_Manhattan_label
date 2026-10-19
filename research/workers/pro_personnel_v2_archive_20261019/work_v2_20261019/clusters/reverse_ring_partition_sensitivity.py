"""Side comparison allowing whole-ring reversal, without touching frozen points.

This is a measurement-equivalence diagnostic, not a replacement main partition
or outcome-selected team strategy. The primary 9/12 forward-cyclic run stays fixed.
"""
from __future__ import annotations
import gzip,itertools,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[1]
sys.path.insert(0,str(BASE/'repo_main_20261019'))
from cluster_core import affinity_partition

def main():
    pairs=pd.read_csv(HERE/'pair_distances.csv.gz'); records=pd.read_csv(HERE/'records_geometry.csv')
    assignments=[];summary=[];solvers=[]
    for pid,r in records.groupby('pool_id'):
        r=r.sort_values(['worker_id','object_id']).reset_index(drop=True);n=len(r)
        p=pairs[pairs.pool_id==pid];matrix=np.full((n,n),np.nan);np.fill_diagonal(matrix,0)
        ix=dict(zip(r.object_id,r.index));counts=r.pair_count.to_numpy()
        for row in p.itertuples():
            if row.available:
                i,j=ix[row.object_id_a],ix[row.object_id_b];matrix[i,j]=matrix[j,i]=row.reversal_allowed_diagnostic_deg
        for cut in [9,12]:
            groups=[];statuses=[]
            for count in sorted(set(counts)):
                ids=np.flatnonzero(counts==count);sub=matrix[np.ix_(ids,ids)]
                gg,ss=affinity_partition(sub,cut);groups.extend([[int(ids[k]) for k in g] for g in gg]);statuses.extend(ss)
                for s in ss:
                    z=dict(pool_id=pid,threshold_deg=cut,pair_count=count,**s)
                    for key in ['local_indices','alternative_affected_members']:z[key]=json.dumps(z[key]) if z[key] is not None else ''
                    solvers.append(z)
            groups.sort(key=lambda g:tuple(r.loc[g,'object_id']));lab={i:gid for gid,g in enumerate(groups,1) for i in g}
            changed=[];added_near=0
            for row in p.itertuples():
                i,j=ix[row.object_id_a],ix[row.object_id_b]
                if bool(getattr(row,f'same_affinity_{cut}'))!=(lab[i]==lab[j]):changed.append((i,j))
                added_near += bool(row.available and row.distance_deg>cut and row.reversal_allowed_diagnostic_deg<=cut)
            affected=set(i for pair in changed for i in pair)
            meta={key:r.iloc[0][key] for key in ['image_id','image_code','building_id','layer','difficulty']}
            summary.append(dict(**meta,pool_id=pid,threshold_deg=cut,N=n,clusters=len(groups),singletons=sum(len(g)==1 for g in groups),
                largest_share=max(map(len,groups))/n,changed_coassigned_pairs=len(changed),affected_members=len(affected),additional_near_pairs=added_near,
                all_optimal=all(s['optimal'] for s in statuses),primary_rule_changed=False))
            for gid,g in enumerate(groups,1):
                for i in g:assignments.append(dict(**meta,pool_id=pid,threshold_deg=cut,object_id=r.loc[i,'object_id'],worker_id=r.loc[i,'worker_id'],
                    alternative_local_cluster_id=gid,alternative_size=len(g),affected_by_direction_equivalence=i in affected))
    pd.DataFrame(assignments).to_csv(HERE/'reverse_ring_alternative_assignments.csv',index=False)
    pd.DataFrame(summary).to_csv(HERE/'reverse_ring_partition_summary.csv',index=False)
    pd.DataFrame(solvers).to_csv(HERE/'reverse_ring_solver_status.csv',index=False)
    report=dict(role='orientation-equivalence sensitivity only; no source/primary/team strategy changed',
        pools=len(summary)//2,changed_pool_thresholds=sum(r['changed_coassigned_pairs']>0 for r in summary),
        all_optimal=all(r['all_optimal'] for r in summary),unknown_semantics='Whether opposite declared directions encode any semantic distinction has not been newly visually adjudicated.')
    (HERE/'REVERSE_RING_RECEIPT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report)

if __name__=='__main__':main()
