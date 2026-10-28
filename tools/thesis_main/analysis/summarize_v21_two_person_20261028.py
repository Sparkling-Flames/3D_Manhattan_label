"""Summarize two-person paths and paired adjacent steps using saved endpoints."""
import gzip
import json
import numpy as np
import pandas as pd
from .compute_v21_two_person_20261028 import TARGET, prepare
from .prepare_v21_natural_inputs_20261028 import BASE, PRIOR, EXT


def main():
    payloads=prepare()
    links=pd.read_csv(TARGET/'PATH_LINKS.csv.gz',keep_default_na=False)
    all_paths=[]; needed=set(); unchanged=[]
    for pool, requests in payloads:
        pid=pool['pool_id']; path=TARGET/'pools'/(pid+'.json.gz')
        with gzip.open(path,'rt',encoding='utf8') as f: saved=json.load(f)
        assert saved['complete']
        teams={tuple(r['member_workers']):r for r in saved['teams']}
        group=links[links.pool_id.eq(pid)].copy()
        outcomes=[]
        for x in group.itertuples():
            r=teams[tuple(sorted([x.first,x.entrant_worker]))]
            if x.team_key: assert x.team_key==r['team_key']
            outcomes.append(r)
        for k in ['team_key','B8L2','D10','score_status','single_support_nodes','joint_support_nodes','single_support_fraction','nodes','floor_turn5_n','floor_redundant5_n','connection_available','geometry_reason']:
            group['k2_'+k]=[r.get(k) for r in outcomes]
        group['image']=pool['meta']['image'];group['building']=pool['meta']['building'];group['layer']=pool['meta']['layer'];group['pool_n']=len(pool['records'])
        source=TARGET.parent/'natural_inputs'/(pid+'.csv.gz')
        if source.exists():
            d=pd.read_csv(source,usecols=['path_id','stratum','k','team_key','B8L2','D10'],low_memory=False)
            for k in [1,3]:
                z=d[d.k.eq(k)][['path_id','stratum','team_key','B8L2','D10']]
                z=z.rename(columns={'team_key':'saved_key_'+str(k),'B8L2':'Q'+str(k),'D10':'D'+str(k)})
                group=group.merge(z,on=['path_id','stratum'],how='left',validate='one_to_one',indicator='_merge'+str(k))
                assert group['_merge'+str(k)].eq('both').all(),(pid,k)
                has=group['team_key_'+str(k)].ne('')
                assert (group.loc[has,'team_key_'+str(k)]==group.loc[has,'saved_key_'+str(k)]).all()
                group=group.drop(columns='_merge'+str(k))
        else:
            unchanged.append(pid);needed.update(group.team_key_1);needed.update(group.team_key_3)
        all_paths.append(group)
    paths=pd.concat(all_paths,ignore_index=True)
    score={}
    sources=[BASE/'stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz', BASE/'results/ENDPOINT_SCALARS.csv.gz']
    sources+=sorted((PRIOR/'new_endpoints/table_shards/NEW_PREFIX_VALUES_COMPACT').glob('*.csv.gz'))
    sources+=sorted((PRIOR/'new_endpoints/table_shards/NEW_ENDPOINT_SCALARS').glob('*.csv.gz'))
    idx=pd.read_csv(EXT/'new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz')
    sources += [EXT/p for p in idx.loc[idx.pool_id.isin(unchanged),'scalar_file']]
    for source in sources:
        for d in pd.read_csv(source,usecols=['team_key','B8L2','D10'],chunksize=50000,low_memory=False):
            for row in d[d.team_key.isin(needed)].itertuples(index=False):
                old=score.get(row.team_key)
                values=(row.B8L2,row.D10)
                if old is not None:
                    assert all((pd.isna(a) and pd.isna(b)) or np.isclose(a,b,atol=1e-8) for a,b in zip(old,values)),row.team_key
                score[row.team_key]=values
    missing=needed-set(score);assert not missing,('missing k1/k3 endpoint',len(missing),list(missing)[:3])
    mask=paths.pool_id.isin(unchanged)
    for k in (1,3):
        for j,col in enumerate(('Q','D')):
            paths.loc[mask,col+str(k)]=paths.loc[mask,'team_key_'+str(k)].map({key:value[j] for key,value in score.items()})
    paths['Q2']=pd.to_numeric(paths.k2_B8L2,errors='coerce')
    paths['delta_1_2']=paths.Q2-paths.Q1; paths['delta_2_3']=paths.Q3-paths.Q2
    paths.to_csv(TARGET/'PAIRED_PATH_RESULTS.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    def per_image(g):
        n=len(g);s=g.k2_score_status; q=g.Q2.dropna().sort_values(); ref=s.isin(['floor_only_reference','missing_reference'])
        return pd.Series(dict(paths=n,unique_teams=g.k2_team_key.nunique(),Q2=g.Q2.mean(),D10_2=pd.to_numeric(g.k2_D10,errors='coerce').mean(),Q2_valid=g.Q2.notna().sum(),
            Q2_sd=g.Q2.std(ddof=1),Q2_p10=float(q.quantile(.1,interpolation='lower')) if len(q) else np.nan,
            consensus_failure_rate=s.isin(['below_four','no_connection','fusion_exception']).mean(),unscoreable_rate=(g.Q2.isna() & ~ref & ~s.isin(['below_four','no_connection','fusion_exception'])).mean(),
            reference_unavailable_rate=ref.mean(),nodes_mean=pd.to_numeric(g.k2_nodes,errors='coerce').mean(),
            single_support_fraction=pd.to_numeric(g.k2_single_support_fraction,errors='coerce').mean(),
            delta_1_2=g.delta_1_2.mean(),paired_1_2=g.delta_1_2.notna().sum(),delta_2_3=g.delta_2_3.mean(),paired_2_3=g.delta_2_3.notna().sum()))
    images=paths.groupby(['pool_id','image','building','layer','pool_n'],dropna=False).apply(per_image,include_groups=False).reset_index()
    images.to_csv(TARGET/'IMAGE_RESULTS.csv',index=False)
    images.assign(k=2,cohort='pooled256_or_new_space256',estimator='uniform_path_MC_256',data_release='v2.1_two_person_supplement').to_csv(TARGET/'K2_CURVE_OVERLAY.csv',index=False)
    rows=[]
    for label,subset in [('available',images),('N_ge_30',images[images.pool_n.ge(30)]),('N_ge_35',images[images.pool_n.ge(35)])]:
        for layer,g in subset.groupby('layer'):
            for metric in ['Q2','D10_2','consensus_failure_rate','unscoreable_rate','single_support_fraction','delta_1_2','delta_2_3']:
                d=g[g[metric].notna()]; b=d.groupby('building')[metric].mean()
                for weighting,value in [('image_equal',d[metric].mean()),('building_equal',b.mean())]:
                    rows.append(dict(panel=label,layer=layer,metric=metric,weighting=weighting,estimate=value,images=len(d),eligible_images=len(g),buildings=len(b)))
    pd.DataFrame(rows).to_csv(TARGET/'SUMMARY.csv',index=False)
    receipt=dict(pools=len(images),paths=len(paths),unique_teams=sum(images.unique_teams),scored_paths=int(paths.Q2.notna().sum()),paired_1_2=int(paths.delta_1_2.notna().sum()),paired_2_3=int(paths.delta_2_3.notna().sum()),source='original 256 path frequencies',scope='eligible source pools with at least three workers',rule='MV50, original location/connection, k2 deferral lifted',new_algorithm=False)
    (TARGET/'SUMMARY_CHECKS.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt),flush=True)


if __name__=='__main__': main()
