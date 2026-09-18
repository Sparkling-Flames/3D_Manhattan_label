#!/usr/bin/env python3
"""Exploratory geometry clustering. Not semantic gold; frozen source points unmodified.
Requires Python 3.11+, numpy, pandas, scipy, sklearn>=1.3, numba, Pillow.
Run: python clustering_study.py --root /path/to/cluster_study_20260918
The input tree must contain inputs/key39/data.json and inputs/pixels (optional for numerics).
"""
from __future__ import annotations
import os
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(key,'1')
import argparse,json,hashlib,math,itertools,collections,sys,warnings
from pathlib import Path
import numpy as np,pandas as pd
from scipy.cluster.hierarchy import linkage,fcluster
from scipy.spatial.distance import squareform
from scipy.ndimage import gaussian_filter1d,uniform_filter1d
from sklearn.cluster import HDBSCAN,KMeans
from sklearn.metrics import adjusted_rand_score,silhouette_score
from numba import njit
import legacy_reproduction as old

@njit(cache=True)
def cyclic_cost(C,penalty):
    """Exact minimum order-preserving cyclic partial matching cost; deletion cost per item."""
    m,n=C.shape
    if not m or not n:return penalty*(m+n)
    best=1e300
    for s in range(n):
        dp=np.empty((m+1,n+1))
        for i in range(m+1):dp[i,0]=i*penalty
        for j in range(n+1):dp[0,j]=j*penalty
        for i in range(1,m+1):
            for j in range(1,n+1):
                x=C[i-1,(j-1+s)%n]
                dp[i,j]=min(dp[i-1,j-1]+x,dp[i-1,j]+penalty,dp[i,j-1]+penalty)
        best=min(best,dp[m,n])
    return best

def prep(data):
    ns=old.legacy_functions(data);records={};coverage=[]
    for case in data['cases']:
        for r in case['responses']:
            cid=r['canonical_annotation_id'];norm=ns['normalize_geometry'](r['effective_points_1024x512'])
            a={**r,'code':case['code'],'norm':norm};records[cid]=a
            if norm['valid']:
                a['events']=old.pairs3(norm);a['boundary']=old.dense(ns,norm).astype(float)
                try:
                    native,cross=old.native_dense(ns,r['effective_points_1024x512'],norm)
                    a['native']=native.astype(float) if not cross else None
                    a['raw_endpoints']=old.recover_endpoints(r['effective_points_1024x512'],norm)[0]
                except ValueError:a['native']=None;a['raw_endpoints']=None
            coverage.append(dict(code=case['code'],condition=r['raw_condition'],id=cid,worker=r['worker_id'],valid=norm['valid'],reason=norm['reason'],legacy_included=r['calculation_included'],legacy_worker_included=r['main_worker_included'],raw_points=r['raw_point_count'],effective_points=r['effective_point_count']))
    return ns,records,pd.DataFrame(coverage)

def pair_matrices(rr):
    n=len(rr);names=['mask','native_mask','boundary_local','boundary_rms','gospa20','adaptive','events4','events8','events16']
    Ds={name:np.zeros((n,n),float)for name in names};local_scales=[]
    density={s:[]for s in [4,8,16]}
    for r in rr:
        a=r['events'];x=a[:,0];g=np.diff(np.r_[x,x[0]+1024]);local_scales.append(np.clip(.25*np.minimum(g,np.roll(g,1)),4.,24.))
        for s in density:
            dx=np.abs(np.arange(1024)[:,None]-x[None,:]);dx=np.minimum(dx,1024-dx)
            density[s].append(np.exp(-.5*(dx/s)**2).sum(1))
    for i,j in itertools.combinations(range(n),2):
        a,b=rr[i],rr[j];da,db=a['boundary'],b['boundary'];D=Ds
        D['mask'][i,j]=old.dmask(da,db)
        D['native_mask'][i,j]=old.dmask(a['native'],b['native'])if a['native'] is not None and b['native'] is not None else np.nan
        delta=np.abs(da-db);D['boundary_local'][i,j]=float(uniform_filter1d(delta.max(0),64,mode='wrap').max())
        D['boundary_rms'][i,j]=float(np.sqrt(np.mean(delta**2)))
        ea,eb=a['events'],b['events'];diff=np.abs(ea[:,None,:]-eb[None,:,:]);diff[:,:,0]=np.minimum(diff[:,:,0],1024-diff[:,:,0]);C=np.sum(diff**2,axis=2)
        D['gospa20'][i,j]=math.sqrt(cyclic_cost(C,200.)/max(len(ea),len(eb)))
        sx=np.sqrt(local_scales[i][:,None]*local_scales[j][None,:])
        CR=(diff[:,:,0]/sx)**2+np.sum(diff[:,:,1:]**2,axis=2)/20.**2
        D['adaptive'][i,j]=math.sqrt(cyclic_cost(CR,.5)/max(len(ea),len(eb)))
        for s in density:
            va,vb=density[s][i],density[s][j]
            D['events'+str(s)][i,j]=1.-np.minimum(va,vb).sum()/np.maximum(va,vb).sum()
    for d in Ds.values():d+=d.T
    return Ds

def density_labels(D,ms=2):
    n=len(D)
    if n<3:return np.arange(n),np.ones(n,dtype=bool)
    h=HDBSCAN(metric='precomputed',copy=True,min_cluster_size=2,min_samples=ms,allow_single_cluster=True,cluster_selection_method='eom')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore');lab=h.fit_predict(D)
    noise=lab<0;lab=lab.copy();offset=max(lab.max()+1,0)
    for k,ix in enumerate(np.flatnonzero(noise)):lab[ix]=offset+k
    return lab,noise

def spectral(D,knn=3):
    n=len(D)
    if n<3:return np.arange(n),dict(k=n,eigengap=np.nan)
    sigma=np.maximum(np.sort(D,axis=1)[:,min(knn,n-1)],1e-6)
    A=np.exp(-D**2/(sigma[:,None]*sigma[None,:]));np.fill_diagonal(A,0)
    deg=np.maximum(A.sum(1),1e-15);S=A/np.sqrt(deg[:,None]*deg[None,:])
    val,vec=np.linalg.eigh(S);val=val[::-1];vec=vec[:,::-1]
    gaps=val[:min(6,n-1)]-val[1:min(6,n-1)+1];k=int(np.argmax(gaps)+1)
    if k==1:return np.zeros(n,int),dict(k=k,eigengap=float(gaps[k-1]))
    Z=vec[:,:k];Z=Z/np.maximum(np.linalg.norm(Z,axis=1,keepdims=True),1e-15)
    lab=KMeans(n_clusters=k,n_init=30,random_state=20260918).fit_predict(Z)
    return lab,dict(k=k,eigengap=float(gaps[k-1]))

METHODS={
 'A0_legacy':dict(family='legacy',label='Point-count gate + mask complete 0.10'),
 'A1_mask':dict(family='mask',label='No count gate; mask complete 0.10'),
 'A2_local':dict(family='local',label='Mask 0.10 AND local-boundary 20px complete'),
 'A3_cyclic':dict(family='cyclic',label='Cyclic partial RMS; cap20, complete12px'),
 'A4_adaptive':dict(family='adaptive',label='Local-gap scaled cyclic matching complete0.6'),
 'A5_density':dict(family='density',label='HDBSCAN on mask; minsize2,minsample2; noise retained'),
 'A6_spectral':dict(family='spectral',label='Local scale graph kNN3; eigengap1-6 + kmeans'),
 'A7_event':dict(family='event',label='Mask0.10 AND soft event Jaccard0.35; sigma8px'),
}

def apply(method,Ds,counts):
    n=len(counts);noise=np.zeros(n,bool);extra={}
    if method=='A0_legacy':D=Ds['mask'];l=old.clust(D,counts,.1)
    elif method=='A1_mask':D=Ds['mask'];l=old.clust(D,None,.1)
    elif method=='A2_local':D=np.maximum(Ds['mask']/.1,Ds['boundary_local']/20.);l=old.clust(D,None,1.)
    elif method=='A3_cyclic':D=Ds['gospa20'];l=old.clust(D,None,12.)
    elif method=='A4_adaptive':D=Ds['adaptive'];l=old.clust(D,None,.6)
    elif method=='A5_density':D=Ds['mask'];l,noise=density_labels(D)
    elif method=='A6_spectral':D=Ds['mask'];l,extra=spectral(D)
    elif method=='A7_event':D=np.maximum(Ds['mask']/.1,Ds['events8']/.35);l=old.clust(D,None,1.)
    else:raise ValueError(method)
    # Stable display labels by size then medoid canonical order, not semantic identities.
    blocks=sorted([np.flatnonzero(l==v)for v in set(l)],key=lambda ix:(-len(ix),int(ix.min())))
    labels=np.empty(n,int)
    for k,ix in enumerate(blocks):labels[ix]=k+1
    return labels,noise,D,extra

def run(root):
    inp=root/'inputs';out=root/'results';out.mkdir(exist_ok=True)
    data=json.loads((inp/'key39/data.json').read_text());ns,records,cov=prep(data);cov.to_csv(out/'response_coverage.csv',index=False)
    summaries=[];members=[];pairs=[];stabilities=[];native_audit=[];sensitivity=[];cache={};parities=[]
    for ci,case in enumerate(data['cases']):
        for g in case['groups']:
            ids=g['canonical_ids'];rr=[records[i]for i in ids];n=len(rr);counts=np.array(g['point_counts']);Ds=pair_matrices(rr)
            label0=np.zeros(n,int)
            for c in g['display_clusters']:
                for cid in c['canonical_ids']:label0[ids.index(cid)]=c['display_index']
            oldD=np.array(g['distance_matrix']);re=Ds['mask'].copy();re[counts[:,None]!=counts[None,:]]=2.
            assert np.max(np.abs(re-oldD))<1e-10
            common=dict(code=case['code'],image_id=case['image_id'],condition=g['condition'],N=n,building=case['image_id'].split('_')[0])
            labels_store={};nativeix=np.flatnonzero([r['native']is not None for r in rr]);dmn=Ds['native_mask'][np.ix_(nativeix,nativeix)]
            for gate in [False,True]:
                cn=counts[nativeix] if gate else None
                pre=old.clust(Ds['mask'][np.ix_(nativeix,nativeix)],cn,.1);post=old.clust(dmn,cn,.1)
                tri=np.triu_indices(len(nativeix),1);flips=(Ds['mask'][np.ix_(nativeix,nativeix)][tri]<=.1)!=(dmn[tri]<=.1)
                native_audit.append(dict(**common,gate=gate,comparable_n=len(nativeix),comparable_pairs=len(tri[0]),threshold_flips=int(flips.sum()),partition_changed=not np.array_equal(pre[:,None]==pre[None,:],post[:,None]==post[None,:]),before_clusters=len(set(pre)),after_clusters=len(set(post)),ARI=adjusted_rand_score(pre,post),changed_pair_relations=int(np.sum((pre[:,None]==pre[None,:])!=(post[:,None]==post[None,:]))//2)))
            for name in METHODS:
                lab,noise,D,extra=apply(name,Ds,counts);labels_store[name]=lab.tolist()
                if name=='A0_legacy':assert adjusted_rand_score(lab,label0)==1.;parities.append(True)
                k=len(set(lab));ss=silhouette_score(D,lab,metric='precomputed') if 1<k<n else np.nan
                summ=dict(**common,method=name,**old.cluster_stats(lab),noise_n=int(noise.sum()),ARI_vs_legacy=adjusted_rand_score(label0,lab),silhouette=ss,**extra)
                summaries.append(summ)
                for i,cid in enumerate(ids):members.append(dict(**common,method=name,id=cid,worker=rr[i]['worker_id'],cluster=int(lab[i]),density_noise=bool(noise[i]),point_count=int(counts[i])))
                # Exact leave-one-person-out partition stability on common remaining IDs.
                for omitted in range(n):
                    ix=np.delete(np.arange(n),omitted);sub={kk:vv[np.ix_(ix,ix)]for kk,vv in Ds.items()}
                    ll,nn,dd,ee=apply(name,sub,counts[ix]);eq=lab[ix,None]==lab[ix][None,:];eq2=ll[:,None]==ll[None,:]
                    stabilities.append(dict(**common,method=name,omitted_id=ids[omitted],ARI=adjusted_rand_score(lab[ix],ll),changed_relations=int((eq!=eq2).sum()//2),n_pairs=len(ix)*(len(ix)-1)//2))
            for i,j in itertools.combinations(range(n),2):
                pairs.append(dict(**common,id_a=ids[i],id_b=ids[j],worker_a=rr[i]['worker_id'],worker_b=rr[j]['worker_id'],count_a=int(counts[i]),count_b=int(counts[j]),**{key:val[i,j]for key,val in Ds.items()}))
            for cut in [.05,.075,.10,.125,.15,.20]:
                for gate in [False,True]:
                    ll=old.clust(Ds['mask'],counts if gate else None,cut)
                    sensitivity.append(dict(**common,method='mask_gate' if gate else 'mask_nogate',parameter=cut,**old.cluster_stats(ll)))
            for cut in [8.,12.,16.]:
                ll=old.clust(Ds['gospa20'],None,cut);sensitivity.append(dict(**common,method='cyclic',parameter=cut,**old.cluster_stats(ll)))
            for tol in [12.,20.,32.]:
                ll=old.clust(np.maximum(Ds['mask']/.1,Ds['boundary_local']/tol),None,1.)
                sensitivity.append(dict(**common,method='local',parameter=tol,**old.cluster_stats(ll)))
            for s in [4,8,16]:
                ll=old.clust(np.maximum(Ds['mask']/.1,Ds['events'+str(s)]/.35),None,1.)
                sensitivity.append(dict(**common,method='event_sigma',parameter=s,**old.cluster_stats(ll)))
            for knn in [2,3,5,7]:
                ll,ex=spectral(Ds['mask'],knn);sensitivity.append(dict(**common,method='spectral_knn',parameter=knn,**old.cluster_stats(ll)))
            key=case['code']+'|'+g['condition'];cache[key]=dict(ids=ids,workers=g['workers'],counts=counts,Ds=Ds,labels=labels_store)
        print(ci+1,case['code'],flush=True)
    for name,rows in [('group_summary',summaries),('memberships',members),('pairwise_features',pairs),('leave_one_out_stability',stabilities),('native_endpoint_partition_audit',native_audit),('parameter_sensitivity',sensitivity)]:
        pd.DataFrame(rows).to_csv(out/(name+'.csv'),index=False)
    old.save_json(out/'group_cache.json',cache);old.save_json(out/'method_registry.json',METHODS)
    old.save_json(out/'numerical_tests.json',dict(legacy_matrices=len(parities),legacy_partitions_match=all(parities),source_data_blob=old.DATA_BLOB,cases=len(data['cases']),groups=len(cache),records=len(cov),valid_records=int(cov.valid.sum()),legacy_records=sum(len(g['ids'])for g in cache.values()),methods=len(METHODS)))
    print(pd.DataFrame(summaries).groupby('method')[['clusters','singletons','noise_n']].sum())
    print('native',pd.DataFrame(native_audit).groupby('gate')[['threshold_flips','partition_changed']].sum())
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=p.parse_args();run(args.root)
