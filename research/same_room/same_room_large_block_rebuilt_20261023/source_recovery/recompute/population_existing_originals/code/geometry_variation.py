"""Shape variation among independent order prefixes of the same size.

Each sampled permutation retains its weight, including repeated member sets.
The endpoint is only computed once upstream. Invalid or incomplete floors are
excluded from geometric distance but stay in the explicit path denominators.
"""
from __future__ import annotations
import argparse,collections,concurrent.futures,math,sys
from pathlib import Path
if Path('/tmp/hohonet_deps').exists():sys.path.insert(0,'/tmp/hohonet_deps')
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Polygon
from run_prefix_endpoints import read,save,csv

def weighted_quantile(values,weights,q):
    if not len(values):return None
    ix=np.argsort(values);v=np.asarray(values)[ix];w=np.asarray(weights)[ix]
    # A nearest-rank empirical quantile over all unordered sampled-path pairs.
    return float(v[min(np.searchsorted(np.cumsum(w),q*sum(w),side='left'),len(v)-1)])

def pair_summary(rows,counts):
    n=sum(counts);den=n*(n-1)//2
    if not den:return {}
    p=[Polygon(r['geometry']['footprint']) for r in rows];areas=np.asarray([x.area for x in p]);centroids=np.asarray([[x.centroid.x,x.centroid.y] for x in p])
    i,j=np.triu_indices(len(rows),1);weights=np.asarray(counts)[i]*np.asarray(counts)[j]
    duplicate_pairs=sum(c*(c-1)//2 for c in counts)
    metrics={}
    if len(i):
        a=np.asarray(p,dtype=object);inter=shapely.area(shapely.intersection(a[i],a[j]));v=1-inter/(areas[i]+areas[j]-inter)
        metrics['V_floor']=v
        metrics['V_centroid_h']=np.linalg.norm(centroids[i]-centroids[j],axis=1)
        for name,field in [('V_height_h','height_mean_h'),('V_turn5','floor_turn5_n'),('V_nodes','nodes')]:
            x=np.asarray([r.get(field,np.nan) if r.get(field) is not None else np.nan for r in rows],float)
            metrics[name]=np.abs(x[i]-x[j])
    else:metrics={name:np.array([]) for name in ['V_floor','V_centroid_h','V_height_h','V_turn5','V_nodes']}
    out={}
    for name,values in metrics.items():
        ok=np.isfinite(values);ww=weights[ok];vv=values[ok]
        # Identical-team duplicates have zero variation only when that metric exists.
        field={'V_height_h':'height_mean_h','V_turn5':'floor_turn5_n','V_nodes':'nodes'}.get(name)
        zeros=sum(c*(c-1)//2 for r,c in zip(rows,counts) if field is None or r.get(field) is not None)
        if zeros:ww=np.r_[ww,zeros];vv=np.r_[vv,0.]
        if ww.sum():
            out[name+'_mean']=float(np.dot(ww,vv)/ww.sum());out[name+'_p90']=weighted_quantile(vv,ww,.9);out[name+'_valid_pairs']=int(ww.sum())
        else:out[name+'_mean']=None;out[name+'_p90']=None;out[name+'_valid_pairs']=0
    return out

def run_pool(pid,links,folder):
    payload=read(Path(folder)/'endpoints'/(pid+'.json.gz'));rows={r['team_key']:r for r in payload['teams']};valid={}
    for key,r in rows.items():
        g=r.get('geometry') or {};floor=g.get('footprint')
        if not r.get('complete_floor_evaluable') or floor is None or len(floor)<3:continue
        p=Polygon(floor)
        if p.is_valid and p.area>0 and math.isfinite(p.area):valid[key]=r
    result=[]
    for (policy,k),group in links.groupby(['policy','k'],sort=False):
        counts=collections.Counter(group.team_key);use=[key for key in counts if key in valid];n=sum(counts[x] for x in use)
        meta=next(iter(rows.values()));r={f:meta.get(f) for f in ['pool_id','image','condition','layer','building','difficulty','pool_n']}
        r.update(policy=policy,k=int(k),paths=len(group),unique_member_sets=len(counts),geometry_valid_paths=n,geometry_unique_sets=len(use),geometry_possible_pairs=n*(n-1)//2,member_variation_estimable=len(use)>1,full_pool_endpoint=int(k)==meta['pool_n'])
        r.update(pair_summary([valid[x] for x in use],[counts[x] for x in use]));result.append(r)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',required=True);p.add_argument('--jobs',type=int,default=4);a=p.parse_args();folder=Path(a.results)
    links=pd.read_csv(folder/'PREFIX_TEAM_LINKS.csv.gz');out=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        tasks={ex.submit(run_pool,pid,g,folder):pid for pid,g in links.groupby('pool_id',sort=False)}
        for f in concurrent.futures.as_completed(tasks):
            rows=f.result();out.extend(rows);csv(folder/'geometry_variation_shards'/(tasks[f]+'.csv.gz'),pd.DataFrame(rows))
    d=pd.DataFrame(out);csv(folder/'PREFIX_GEOMETRY_VARIATION.csv.gz',d)
    save(folder/'GEOMETRY_VARIATION_RECEIPT.json',dict(groups=len(d),pools=d.pool_id.nunique(),order_weighted=True,full_pool_singleton_flag_retained=True,pair_distance='1-IoU of valid complete floors; dimensionless camera-height centroid and height changes separately',geometry_failure_kept_in_path_denominator=True))
    print('geometry groups',len(d),flush=True)

if __name__=='__main__':main()
