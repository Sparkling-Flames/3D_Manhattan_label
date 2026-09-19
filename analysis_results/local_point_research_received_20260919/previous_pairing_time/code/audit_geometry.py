"""Read-only audit: old pairing versus opposite-hemisphere pairing and point-set comparisons.
Opposite-hemisphere validity is a conditional geometry check, not scene truth.
All coordinates, source IDs and old snapshots remain unchanged.
"""
from pathlib import Path
import sys, json, gzip, itertools, hashlib, collections, math
import numpy as np, pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import squareform
from scipy.cluster.hierarchy import linkage, fcluster
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'inputs/base'
sys.path.insert(0,str(BASE/'code'))
import legacy_reproduction as old
import clustering_study as st
D=json.loads((BASE/'inputs/frozen/key39/data.json').read_text())
NS=old.legacy_functions(D)
ROWS=[json.loads(l) for l in gzip.open(BASE/'inputs/frozen/human/responses.jsonl.gz','rt')]
RECS={r['canonical_annotation_id']:r for r in ROWS}
AUD=pd.read_csv(BASE/'results/all_response_audit.csv').set_index('id')
OUT=ROOT/'results'

def save(name,x):
    (OUT/name).write_text(json.dumps(old.safe_json(x),ensure_ascii=False,indent=2))

def sensible(points,horizon=255.5):
    p=np.asarray(points,float)
    if p.ndim!=2 or p.shape[1:]!=(2,) or len(p)<4 or len(p)%2 or not np.isfinite(p).all():return None,'shape_or_count',None
    if (p[:,0]<0).any() or (p[:,0]>1024).any() or (p[:,1]<0).any() or (p[:,1]>=512).any():return None,'range',None
    up=np.flatnonzero(p[:,1]<horizon);dn=np.flatnonzero(p[:,1]>horizon)
    if len(up)!=len(p)//2 or len(dn)!=len(up):return None,'unequal_hemisphere_counts',None
    up=up[np.argsort(p[up,0]%1024,kind='stable')];dn=dn[np.argsort(p[dn,0]%1024,kind='stable')]
    dx=abs(p[up,None,0]-p[dn,0][None,:]);dx=np.minimum(dx,1024-dx)
    constrained=dx.copy();constrained[dx>=51.2]=1e9
    ii,jj=linear_sum_assignment(constrained)
    if np.max(dx[ii,jj])>=51.2:return None,'no_vertical_matching_within_51_2px',None
    optimal=float(dx[ii,jj].sum()); second=np.inf
    for i,j in zip(ii,jj):
        cc=constrained.copy();cc[i,j]=1e9
        ia,ja=linear_sum_assignment(cc)
        if np.max(cc[ia,ja])<1e9:second=min(second,float(cc[ia,ja].sum()))
    pi=np.array([(int(up[i]),int(dn[j]))for i,j in zip(ii,jj)])
    a=p[pi];xx=(a[:,0,0]+((a[:,1,0]-a[:,0,0]+512)%1024-512)/2)%1024
    events=np.column_stack([xx,a[:,0,1],a[:,1,1]]); order=np.argsort(events[:,0],kind='stable');events=events[order];pi=pi[order]
    z={'valid':True,'pairs':[dict(x=x,y_ceiling=y1,y_floor=y2) for x,y1,y2 in events]}
    meta=dict(indices=pi.tolist(),x_cost=optimal,second_cost=second,margin=second-optimal,tied=bool(second-optimal<1e-8))
    return z,'available',meta

def native_without_pair(points):
    p=np.asarray(points,float);up=p[p[:,1]<255.5];dn=p[p[:,1]>255.5]
    if min(len(up),len(dn))<2:return None
    z=np.stack([NS['_interp_periodic'](a[:,0],a[:,1],1024) for a in [up,dn]])
    z=np.clip(np.rint(z),0,511).astype(int)
    if np.any(z[0]>z[1]):return None
    return z

def spherical_pts(p):
    p=np.asarray(p,float);u=((p[:,0]+.5)/1024-.5)*2*np.pi;v=((p[:,1]+.5)/512-.5)*np.pi
    return np.column_stack([np.cos(v)*np.cos(u),np.cos(v)*np.sin(u),np.sin(v)])

def point_distance_matrix(a,b):
    return np.rad2deg(np.arccos(np.clip(spherical_pts(a)@spherical_pts(b).T,-1,1)))

def rms_and_bottleneck(C):
    m,n=C.shape
    if m!=n:return np.nan,np.nan
    ii,jj=linear_sum_assignment(C*C);rms=float(np.sqrt(np.mean(C[ii,jj]**2)))
    vals=np.unique(C);lo,hi=0,len(vals)-1
    while lo<hi:
        mid=(lo+hi)//2;ii,jj=linear_sum_assignment((C>vals[mid]).astype(int))
        if np.all(C[ii,jj]<=vals[mid]):hi=mid
        else:lo=mid+1
    return rms,float(vals[lo])

def complete(d,cut,counts=None):return old.clust(d,counts,cut)

def run_audit():
    rows=[];oldn={};newn={};groups=collections.defaultdict(list)
    for r in ROWS:
        cid=r['canonical_annotation_id'];p=r['effective_points_1024x512'];nn=NS['normalize_geometry'](p);oldn[cid]=nn
        new,status,meta=sensible(p);newn[cid]=(new,status,meta)
        a=dict(id=cid,code=AUD.loc[cid,'code'],image_id=r['image_id'],worker=r['worker_id'],condition=r['raw_condition'],stage=r['stage'],excluded_worker=r['worker_id']in{'W019','W026'},old_valid=nn['valid'],old_reason=nn['reason'],old_method=nn['pairing_method'],opposite_hemisphere_status=status,opposite_matching_tied=meta['tied']if meta else None,opposite_matching_margin=meta['margin']if meta else None)
        if nn['valid']:
            e=old.pairs3(nn); same=((e[:,1]<255.5)&(e[:,2]<255.5))|((e[:,1]>255.5)&(e[:,2]>255.5))
            a.update(same_hemisphere_pairs=int(same.sum()),short_spans_lt10=int(((e[:,2]-e[:,1])<10).sum()))
            if new:
                e2=old.pairs3(new); a['event_values_changed']=not np.allclose(e,e2,atol=1e-8,rtol=0)
                a['self_boundary_distance']=old.dmask(old.dense(NS,nn),old.dense(NS,new))
                try:
                    rawidx=old.recover_endpoints(p,nn)[1];previous={tuple(sorted(x))for x in rawidx};nxt={tuple(sorted(x))for x in meta['indices']};a['pair_indices_changed']=previous!=nxt
                except Exception:a['pair_indices_changed']=None
            if not a['excluded_worker'] and r['calculation_included']:groups[(r['image_id'],r['raw_condition'])].append(cid)
        rows.append(a)
    df=pd.DataFrame(rows);df.to_csv(OUT/'pairing_audit_all2501.csv',index=False)
    core=df[~df.excluded_worker & df.old_valid]
    print('CORE',len(core),'same hemi',int((core.same_hemisphere_pairs>0).sum()),'images',core.loc[core.same_hemisphere_pairs>0,'image_id'].nunique())
    print('OPPOSITE',core.opposite_hemisphere_status.value_counts().to_dict())
    print('CHANGED',core.pair_indices_changed.value_counts().to_dict());print('METHOD FLAGS',core.groupby('old_method').same_hemisphere_pairs.agg(['count','sum']).to_dict())
    # Pairwise recomputation only on the COMMON usable set. No reinterpretation of missing values.
    pairs=[];gs=[];members=[]
    for key,ids0 in groups.items():
        ids=[cid for cid in ids0 if newn[cid][0]is not None];n=len(ids)
        if not n:continue
        rawcounts=np.array([RECS[cid]['effective_point_count']for cid in ids])
        bd0=[old.dense(NS,oldn[cid])for cid in ids];bd1=[old.dense(NS,newn[cid][0])for cid in ids]
        mats={k:np.zeros((n,n))for k in ['old_mask','opposite_mask','old_cyclic','opposite_cyclic']}
        for i,j in itertools.combinations(range(n),2):
            a,b=ids[i],ids[j];mats['old_mask'][i,j]=old.dmask(bd0[i],bd0[j]);mats['opposite_mask'][i,j]=old.dmask(bd1[i],bd1[j])
            for ver,norms in [('old',oldn),('opposite',{a:newn[a][0],b:newn[b][0]})]:
                ea,eb=old.pairs3(norms[a]),old.pairs3(norms[b]);dd=abs(ea[:,None,:]-eb[None,:,:]);dd[:,:,0]=np.minimum(dd[:,:,0],1024-dd[:,:,0]);C=(dd*dd).sum(2)
                mats[ver+'_cyclic'][i,j]=math.sqrt(st.cyclic_cost(C,200.)/max(len(ea),len(eb)))
            pairs.append(dict(image_id=key[0],condition=key[1],code=AUD.loc[a,'code'],id_a=a,id_b=b,worker_a=RECS[a]['worker_id'],worker_b=RECS[b]['worker_id'],**{k:v[i,j]for k,v in mats.items()}))
        for v in mats.values():v+=v.T
        for name,cut,gate in [('mask',.1,False),('mask',.1,True),('cyclic',8.,False),('cyclic',12.,False)]:
            p0=complete(mats['old_'+name],cut,rawcounts if gate else None);p1=complete(mats['opposite_'+name],cut,rawcounts if gate else None)
            eq0=p0[:,None]==p0[None,:];eq1=p1[:,None]==p1[None,:];changed=int((eq0!=eq1).sum()//2)
            gs.append(dict(image_id=key[0],code=AUD.loc[ids[0],'code'],condition=key[1],metric=name,cut=cut,count_gate=gate,N_old=len(ids0),N_common=n,old_k=len(set(p0)),alternative_k=len(set(p1)),changed_pair_relations=changed,partition_changed=changed>0))
            for i,cid in enumerate(ids):members.append(dict(id=cid,image_id=key[0],condition=key[1],worker=RECS[cid]['worker_id'],metric=name,cut=cut,count_gate=gate,old_cluster=int(p0[i]),alternative_cluster=int(p1[i])))
    pd.DataFrame(pairs).to_csv(OUT/'pairing_common_pairwise.csv',index=False);pd.DataFrame(gs).to_csv(OUT/'pairing_partition_impact.csv',index=False);pd.DataFrame(members).to_csv(OUT/'pairing_common_memberships.csv',index=False)
    summary=dict(raw=len(df),main_old_valid=len(core),flagged_responses=int((core.same_hemisphere_pairs>0).sum()),flagged_images=int(core.loc[core.same_hemisphere_pairs>0,'image_id'].nunique()),new_status=core.opposite_hemisphere_status.value_counts().to_dict(),common=int((core.opposite_hemisphere_status=='available').sum()),pair_indices_changed=int((core.pair_indices_changed==True).sum()),partitions=pd.DataFrame(gs).groupby(['metric','cut','count_gate']).agg(groups=('N_common','size'),changed=('partition_changed','sum'),changed_relations=('changed_pair_relations','sum')).reset_index().to_dict('records'))
    save('pairing_summary.json',summary);print(json.dumps(old.safe_json(summary),indent=2))
if __name__=='__main__':run_audit()
