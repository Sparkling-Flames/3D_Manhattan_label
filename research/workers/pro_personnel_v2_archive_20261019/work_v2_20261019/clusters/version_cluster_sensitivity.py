"""Separate fixed-v1, newly eligible old answers, and enlarged-v2 pool effects."""
from __future__ import annotations
import gzip,itertools,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[1]
sys.path.insert(0,str(BASE/'repo_main_20261019'))
from cluster_core import affinity_partition,objective

def cluster_subset(df,matrix,indices,cut):
    counts=df.pair_count.to_numpy();groups=[]
    for c in sorted({counts[i] for i in indices}):
        ids=[i for i in indices if counts[i]==c];d=matrix[np.ix_(ids,ids)]
        gg,ss=affinity_partition(d,cut);assert all(s['optimal'] for s in ss)
        groups.extend([[ids[i] for i in g] for g in gg])
    groups.sort(key=tuple);return {i:gid for gid,g in enumerate(groups,1) for i in g},groups

def main():
    flat=pd.read_csv(HERE.parent/'profiles/records_flat.csv');v1=set(flat.loc[flat.v1_quality_member,'object_id'])
    rec=pd.read_csv(HERE/'records_geometry.csv');rec=rec[rec.layer.eq('ordinary_manual')]
    pairs=pd.read_csv(HERE/'pair_distances.csv.gz');pairs=pairs[pairs.layer.eq('ordinary_manual')]
    old_path=HERE/'historical_v1_reference/cluster_assignments.csv'
    if not old_path.exists():old_path=BASE/'work_20261018/clusters/cluster_assignments.csv'
    old=pd.read_csv(old_path) if old_path.exists() else pd.DataFrame()
    if len(old):old=old[old.method.eq('global_affinity_bound_cyclic') & old.analysis_stratum.eq('ordinary_manual')]
    membership=[];changes=[];prior_checks=[];coverage=[]
    for pid,r in rec.groupby('pool_id'):
        r=r.sort_values(['worker_id','object_id']).reset_index(drop=True);n=len(r)
        p=pairs[pairs.pool_id.eq(pid)];mat=np.full((n,n),np.nan);np.fill_diagonal(mat,0.)
        index=dict(zip(r.object_id,r.index))
        for z in p.itertuples():
            if z.available:mat[index[z.object_id_a],index[z.object_id_b]]=mat[index[z.object_id_b],index[z.object_id_a]]=z.distance_deg
        populations={'v1_fixed':[i for i,o in enumerate(r.object_id) if o in v1],
                     'v2_old_eligible':r.index[r.origin.eq('v1')].tolist(),'v2_all':r.index.tolist()}
        meta={key:r.iloc[0][key] for key in ['pool_id','image_id','image_code','building_id','layer','reference_id','reference_version']}
        coverage.append(dict(**meta,v1_fixed_n=len(populations['v1_fixed']),v2_old_eligible_n=len(populations['v2_old_eligible']),v2_all_n=n))
        for cut in [9,12]:
            labs={}
            for population,ix in populations.items():
                if not ix:continue
                lab,groups=cluster_subset(r,mat,ix,cut);labs[population]=lab
                for i in ix:membership.append(dict(**meta,threshold_deg=cut,population=population,population_n=len(ix),
                    object_id=r.loc[i,'object_id'],worker_id=r.loc[i,'worker_id'],local_cluster_id=lab[i],cluster_size=sum(x==lab[i] for x in lab.values())))
            for first,second in [('v1_fixed','v2_old_eligible'),('v2_old_eligible','v2_all'),('v1_fixed','v2_all')]:
                if first not in labs:continue
                ix=populations[first];changed=[];joined=split=0
                for i,j in itertools.combinations(ix,2):
                    a=labs[first][i]==labs[first][j];b=labs[second][i]==labs[second][j]
                    if a!=b:changed.append((i,j));joined+=int(not a and b);split+=int(a and not b)
                changes.append(dict(**meta,threshold_deg=cut,population_from=first,population_to=second,
                    fixed_old_records=len(ix),added_records=len(populations[second])-len(ix),fixed_old_pairs=len(ix)*(len(ix)-1)//2,
                    changed_pairs=len(changed),joined=joined,split=split,
                    affected_old_records=len(set(i for pair in changed for i in pair)),quality_used_in_clustering=False,coordinates_changed=False))
            if len(old) and populations['v1_fixed']:
                same=old[(old.image_id==meta['image_id']) & (old.condition=='manual') & (old.reference_id==meta['reference_id']) & old.threshold_deg.eq(cut)]
                oo=same.set_index('object_id').cluster_id.to_dict();ids=populations['v1_fixed'];compared=changed=0
                for i,j in itertools.combinations(ids,2):
                    a,b=r.loc[i,'object_id'],r.loc[j,'object_id']
                    if a in oo and b in oo:compared+=1;changed+=int((oo[a]==oo[b])!=(labs['v1_fixed'][i]==labs['v1_fixed'][j]))
                prior_checks.append(dict(**meta,threshold_deg=cut,current_v1_fixed_records=len(ids),prior_records=len(same),
                    same_object_set=set(oo)=={r.loc[i,'object_id'] for i in ids},compared_pairs=compared,changed_coassignment_pairs=changed,
                    prior_file_is_local_unverified_lead=True,recomputed_from_current_main_geometry=True))
    pd.DataFrame(membership).to_csv(HERE/'version_cluster_memberships.csv',index=False)
    pd.DataFrame(changes).to_csv(HERE/'version_cluster_pair_changes.csv',index=False)
    pd.DataFrame(prior_checks).to_csv(HERE/'v1_fixed_prior_cluster_checks.csv',index=False)
    pd.DataFrame(coverage).to_csv(HERE/'version_cluster_coverage.csv',index=False)
    d=pd.DataFrame(changes);summary=d.groupby(['threshold_deg','population_from','population_to']).agg(
        pools=('pool_id','nunique'),buildings=('building_id','nunique'),fixed_records=('fixed_old_records','sum'),old_pairs=('fixed_old_pairs','sum'),
        changed_pairs=('changed_pairs','sum'),joined=('joined','sum'),split=('split','sum'),affected_record_occurrences=('affected_old_records','sum'),
        pools_changed=('changed_pairs',lambda x:int((x>0).sum()))).reset_index()
    summary.to_csv(HERE/'version_cluster_summary.csv',index=False)
    print(summary.to_string(index=False))

if __name__=='__main__':main()
