"""Secondary interpolation study: proper projected straight 3D edges, not a new truth policy.
The extra validity gate is metric-specific. Unavailable geometries remain explicitly unavailable.
Curve formula derived from a camera-plane/3D-line intersection, same convention as pano_connect_points.
"""
import json,itertools,math
from pathlib import Path
import numpy as np,pandas as pd
import clustering_study as st
import legacy_reproduction as old
ROOT=Path(__file__).resolve().parents[1]

def spherical_boundary(events,columns=None):
    e=np.asarray(events,float);e=e[np.argsort(e[:,0])];x=e[:,0];gaps=np.diff(np.r_[x,x[0]+1024])
    if (gaps<=1e-7).any()or(gaps>=512.-1e-7).any():return None,'nonminor_or_duplicate_azimuth_arc'
    # This is a straight horizontal-edge interpolation. It cannot support endpoints on the wrong hemisphere.
    if not ((e[:,1]<255.5).all() and (e[:,2]>255.5).all()):return None,'endpoint_crosses_assumed_horizon'
    cols=np.arange(1024,dtype=float) if columns is None else np.asarray(columns,float)%1024
    ix=np.searchsorted(x,cols,side='right')-1;ix%=len(x);jx=(ix+1)%len(x)
    delta=(cols-x[ix])%1024*2*np.pi/1024;gap=gaps[ix]*2*np.pi/1024
    v=(e[:,1:]+.5)/512*np.pi-np.pi/2
    tanv=(np.tan(v[ix])*np.sin(gap-delta)[:,None]+np.tan(v[jx])*np.sin(delta)[:,None])/np.sin(gap)[:,None]
    y=(np.arctan(tanv)/np.pi+.5)*512-.5
    if not np.isfinite(y).all()or (y[:,0]>=y[:,1]).any():return None,'invalid_dense_projection'
    return y.T,'ok'

def solid_iou(a,b):
    av=np.sin((a+.5)/512*np.pi-np.pi/2);bv=np.sin((b+.5)/512*np.pi-np.pi/2)
    inter=np.maximum(0,np.minimum(av[1],bv[1])-np.maximum(av[0],bv[0]));union=av[1]-av[0]+bv[1]-bv[0]-inter
    d=1-float(inter.sum()/union.sum())
    if d < -1e-12 or d > 1.+1e-12:raise ValueError('Invalid solid-angle distance')
    return float(np.clip(d,0.,1.))

def run():
    data=json.loads((ROOT/'inputs/key39/data.json').read_text());ns,rec,cov=st.prep(data);cache=json.loads((ROOT/'results/group_cache.json').read_text())
    availability=[];curves={};vertexerr=[];rows=[];members=[];pairs=[]
    for r in rec.values():
        y,reason=spherical_boundary(r['events'])if r['norm']['valid']else(None,'legacy_normalization_invalid')
        curves[r['canonical_annotation_id']]=y
        availability.append(dict(code=r['code'],id=r['canonical_annotation_id'],worker=r['worker_id'],condition=r['raw_condition'],available=y is not None,reason=reason))
        if y is not None:
            yp,_=spherical_boundary(r['events'],r['events'][:,0]);vertexerr.append(float(np.abs(yp.T-r['events'][:,1:]).max()))
    for key,g in cache.items():
        code,cond=key.split('|');ids=[cid for cid in g['ids']if curves[cid]is not None];ix=[g['ids'].index(cid)for cid in ids];n=len(ids)
        Ds={k:np.zeros((n,n))for k in ['spherical','solid']}
        for i,j in itertools.combinations(range(n),2):
            a,b=curves[ids[i]],curves[ids[j]];d=old.dmask(np.rint(a).astype(int),np.rint(b).astype(int));s=solid_iou(a,b)
            Ds['spherical'][i,j]=Ds['spherical'][j,i]=d;Ds['solid'][i,j]=Ds['solid'][j,i]=s
            pairs.append(dict(code=code,condition=cond,id_a=ids[i],id_b=ids[j],linear_mask=g['Ds']['mask'][ix[i]][ix[j]],spherical_mask=d,solid_angle_mask=s))
        Ds['linear_common']=np.array(g['Ds']['mask'])[np.ix_(ix,ix)]
        for method,dm in Ds.items():
            for cut in [.075,.1,.125,.15,.2]:
                labels=old.clust(dm,None,cut)
                rows.append(dict(code=code,condition=cond,N_original=len(g['ids']),N_available=n,method=method,cut=cut,**old.cluster_stats(labels)))
                for i,cid in enumerate(ids):members.append(dict(code=code,condition=cond,method=method,cut=cut,id=cid,worker=rec[cid]['worker_id'],cluster=int(labels[i])))
    pd.DataFrame(availability).to_csv(ROOT/'results/spherical_availability.csv',index=False);pd.DataFrame(rows).to_csv(ROOT/'results/spherical_summary.csv',index=False);pd.DataFrame(members).to_csv(ROOT/'results/spherical_memberships.csv',index=False);pd.DataFrame(pairs).to_csv(ROOT/'results/spherical_pairwise.csv',index=False)
    old.save_json(ROOT/'results/spherical_tests.json',dict(vertex_max_abs_px=max(vertexerr),available=int(pd.DataFrame(availability).available.sum()),total=len(availability)))
    print(pd.DataFrame(rows).query('cut==.1').groupby('method')[['clusters','singletons']].sum());print(pd.DataFrame(rows).query('cut==.1 and code=="B6ByNegPMKs-22"').to_string(index=False));print('availability',pd.DataFrame(availability).reason.value_counts().to_dict())
if __name__=='__main__':run()
