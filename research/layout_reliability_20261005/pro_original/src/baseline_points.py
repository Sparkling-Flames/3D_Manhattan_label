"""Independent numerical replica of current global point aggregation steps.
Reproduces max-endpoint constrained complete linkage, periodic coordinate
medians and x-ordered new ring. NOT the original module or its full status/guard
implementation. Used only as a like-input comparison, never as a certificate.
"""
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from arc_consensus import pairs,rays,footprint,W

def point_baseline(records,threshold=5.):
    nodes=[]
    for r in sorted(records,key=lambda r:(r['worker'],r['id'])):
        for j,p in enumerate(pairs(r)):nodes.append((r,j,p))
    nodes.sort(key=lambda v:(v[0]['worker'],v[0]['id'],v[2][0,0]%W,v[2][0,1],v[2][1,1],v[1]))
    p=np.array([x[2] for x in nodes]); w=np.array([x[0]['worker'] for x in nodes]);d=[]
    for k in (0,1):
        q=rays(p[:,k]);d.append(np.degrees(np.arctan2(np.linalg.norm(np.cross(q[:,None],q[None,:]),axis=-1),q@q.T)))
    raw=np.maximum(*d);D=raw.copy();D[w[:,None]==w[None,:]]=181;np.fill_diagonal(D,0.)
    labels=fcluster(linkage(squareform(D,checks=False),method='complete'),threshold,criterion='distance')
    centers=[];counts=[]
    for label in np.unique(labels):
        ids=np.flatnonzero(labels==label);sub=raw[np.ix_(ids,ids)];a=ids[np.argmin(sub.sum(axis=1))]
        dx=(p[ids,0,0]-p[a,0,0]+W/2)%W-W/2
        x=(p[a,0,0]+np.median(dx))%W
        centers.append([[x,np.median(p[ids,0,1])],[x,np.median(p[ids,1,1])]]);counts.append(len(ids))
    methods={};n=len(records)
    for rule,t in [('mv50',(n+1)//2),('mv_strict',n//2+1)]:
        selected=[(p,c) for p,c in zip(centers,counts) if c>=t];selected.sort(key=lambda v:v[0][0][0])
        if len(selected)<3:methods[rule]=dict(status='unavailable',reason='fewer_than_three_selected_pairs');continue
        out=dict(points=[list(q) for p,c in selected for q in p],pair_support=[c for p,c in selected],pair_count=len(selected),
                 source_record_ids=[r['id'] for r in records],source_workers=[r['worker'] for r in records],ring_confirmed=False,
                 threshold_deg=threshold,status='unconfirmed_point_baseline')
        try:out['footprint']=footprint(out)[0].tolist()
        except ValueError as e:out.update(status='unavailable',reason=str(e))
        methods[rule]=out
    return methods
