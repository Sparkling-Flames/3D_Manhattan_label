"""Finite two-block correspondence alternatives; no human labels or GT in core.

Input records must already be preprocessed. Memberships, points and source rings
are separate objects. No source mutation, cross-person deduplication or ring fitting.
"""
from __future__ import annotations
import itertools, math
from collections import Counter
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

W,H=1024.,512.

def key(node): return (str(node['id']), int(node['pair_index']))
def nodes_from_records(records):
    if len({r['id'] for r in records})!=len(records): raise ValueError('duplicate_record_id')
    if len({r['worker'] for r in records})!=len(records): raise ValueError('duplicate_worker_record')
    if any(r.get('independent') is not True or r.get('consensus_eligible') is not True for r in records):
        raise ValueError('preselected_roster_eligibility_mismatch_no_filter')
    for field in ('image','condition','evidence_kind'):
        if len({r.get(field) for r in records})>1:raise ValueError('mixed_roster_'+field)
    nodes=[]
    for r in records:
        p=np.asarray(r.get('points'),float)
        if p.ndim!=2 or p.shape[1]!=2 or len(p)<6 or len(p)%2 or not np.isfinite(p).all():
            raise ValueError('invalid_preprocessed_points:'+r['id'])
        if np.any(p[:,0]<0) or np.any(p[:,0]>W) or np.any(p[:,1]<0) or np.any(p[:,1]>H):raise ValueError('out_of_canvas_no_repair')
        q=p.reshape(-1,2,2)
        if np.any(np.abs((q[:,0,0]-q[:,1,0]+W/2)%W-W/2)>1e-8):
            raise ValueError('nonshared_x_no_repair:'+r['id'])
        for i,pts in enumerate(q):
            pi=r.get('source_pair_indices'); si=r.get('source_point_indices')
            nodes.append(dict(id=r['id'],worker=r['worker'],pair_index=i,
                source_pair_index=None if pi is None else pi[i],source_point_indices=None if si is None else si[2*i:2*i+2],
                points=pts.tolist(),source_ring_confirmed=r.get('ring_confirmed'),source_order_status=r.get('order_status')))
    return sorted(nodes,key=lambda v:(str(v['worker']),str(v['id']),v['points'][0][0]%W,v['points'][0][1],v['points'][1][1],v['pair_index']))

def distances(nodes, independent=False):
    p=np.asarray([x['points'] for x in nodes],float)
    out={}
    for side,j in [('top',0),('bottom',1)]:
        a=p[:,j]
        if independent:
            u=(a[:,0]/W-.5)*2*np.pi; v=(.5-a[:,1]/H)*np.pi
            z=np.c_[np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)]
            out[side]=np.degrees(np.arctan2(np.linalg.norm(np.cross(z[:,None],z[None,:]),axis=-1),z@z.T))
        else:
            du=((a[:,None,0]-a[None,:,0]+512)%1024-512)*2*np.pi/1024
            v=(a[:,1]/512-.5)*np.pi
            h=np.sin((v[:,None]-v[None,:])/2)**2+np.cos(v[:,None])*np.cos(v[None,:])*np.sin(du/2)**2
            h=np.clip(h,0,1); out[side]=np.degrees(2*np.arctan2(np.sqrt(h),np.sqrt(1-h)))
        np.fill_diagonal(out[side],0.)
    out['pair']=np.maximum(out['top'],out['bottom']);return out

def partition(nodes,d,tau,worker_constraint=True):
    a=d.copy();workers=np.array([n['worker'] for n in nodes])
    if worker_constraint: a[workers[:,None]==workers[None,:]]=181.
    np.fill_diagonal(a,0)
    if len(nodes)<2:return [list(range(len(nodes)))],np.empty((0,4))
    z=linkage(squareform(a,checks=False),method='complete')
    lab=fcluster(z,tau,criterion='distance')
    groups=sorted([np.flatnonzero(lab==x).tolist() for x in set(lab)],key=lambda g:min(g))
    return groups,z

def center(nodes,indices,pair_d):
    q=np.array([nodes[i]['points'] for i in indices]); d=pair_d[np.ix_(indices,indices)]
    s=d.sum(axis=1); anchors=np.flatnonzero(np.abs(s-s.min())<=1e-10)
    candidates=[]
    for a in anchors:
        x0=q[a,0,0]; dx=(q[:,0,0]-x0+512)%1024-512
        if np.ptp(dx)>=512-1e-9 or np.any(abs(abs(dx)-512)<1e-9):continue
        x=float((x0+np.median(dx))%1024)
        c=[[x,float(np.median(q[:,0,1]))],[x,float(np.median(q[:,1,1]))]]
        if not any(np.allclose(c,prev,rtol=0,atol=1e-9) for prev in candidates):candidates.append(c)
    return dict(points=candidates[0] if len(candidates)==1 else None,alternatives=candidates,
        status='ok' if len(candidates)==1 else 'ambiguous',anchor_count=len(anchors),
        warning='coordinate estimate conditional on correspondence, not votes at generated location')

def normalize_blocks(blocks): return tuple(sorted(tuple(sorted(g)) for g in blocks))

def candidate_domains(nodes,groups,d,tau,seed_key):
    seed=next(i for i,n in enumerate(nodes) if key(n)==tuple(seed_key))
    gidx=next(i for i,g in enumerate(groups) if seed in g)
    domains=[]
    for j,h in enumerate(groups):
        if j==gidx:continue
        g=groups[gidx]
        close=[(a,b) for a in g for b in h if nodes[a]['worker']!=nodes[b]['worker'] and d[a,b]<=tau]
        if close:domains.append(dict(group_indices=[gidx,j],blocks=[g,h],compatible_cross_pairs=close))
    return domains

def enumerate_two_blocks(nodes,d,tau,base_blocks,max_nodes=32,max_states=262144):
    """Exact feasible partitions via connected components of incompatibility graph.

    Because each old block is feasible, all incompatibility edges run across the
    old blocks. Thus each connected component has two color orientations. Fixing
    node zero to block 0 removes exchange-equivalent copies. Empty blocks excluded.
    """
    union=sorted(set().union(*map(set,base_blocks))); n=len(union)
    if sum(map(len,base_blocks))!=n:raise ValueError('overlapping_baseline_blocks')
    dist=d[np.ix_(union,union)];workers=np.array([nodes[i]['worker'] for i in union])
    bad=(dist>tau)|(workers[:,None]==workers[None,:]);np.fill_diagonal(bad,False)
    b0=np.array([i in base_blocks[1] for i in union],dtype=int)
    if any(bad[i,j] and b0[i]==b0[j] for i in range(n) for j in range(i+1,n)):
        raise ValueError('baseline_not_feasible')
    colors=np.full(n,-1,int); components=[]
    for start in range(n):
        if colors[start]>=0:continue
        colors[start]=0;comp=[];stack=[start]
        while stack:
            i=stack.pop();comp.append(i)
            for j in np.flatnonzero(bad[i]):
                if colors[j]<0:colors[j]=1-colors[i];stack.append(int(j))
                elif colors[j]==colors[i]:raise AssertionError('nonbipartite_union_of_two_feasible_blocks')
        components.append(sorted(comp))
    states=2**(len(components)-1)
    meta=dict(union=union,baseline_blocks=base_blocks,union_nodes=n,incompatibility_components=[
        dict(nodes=[union[i] for i in c],colors=colors[c].tolist()) for c in components],
        forbidden_pairs=[dict(nodes=[union[i],union[j]],distance_deg=float(dist[i,j]),same_worker=bool(workers[i]==workers[j]))
            for i in range(n) for j in range(i+1,n) if bad[i,j]],
        orientation_states=states,all_unordered_two_nonempty_partitions=2**(n-1)-1,
        status='ok',exhaustive_within_declared_domain=True)
    if n>max_nodes or states>max_states:
        meta.update(status='budget_exceeded',exhaustive_within_declared_domain=False);return meta,[]
    weights=(dist/tau)**2;results=[]
    compidx=np.empty(n,int)
    for j,c in enumerate(components): compidx[c]=j
    m=len(components)-1
    for start in range(0,states,4096):
        integers=np.arange(start,min(states,start+4096),dtype=np.uint64)
        flags=np.zeros((len(integers),m+1),np.int8)
        if m:flags[:,1:]=((integers[:,None]>>np.arange(m-1,-1,-1,dtype=np.uint64))&1).astype(np.int8)
        labels=colors[None,:]^flags[:,compidx]
        counts=labels.sum(axis=1);valid=(counts>0)&(counts<n)
        labels=labels[valid];counts=counts[valid]
        x=labels.astype(float);xx=1-x
        costs=np.einsum('ij,ij->i',x@weights,x)/2/counts+np.einsum('ij,ij->i',xx@weights,xx)/2/(n-counts)
        for lab,cost in zip(labels,costs):
            loc=[np.flatnonzero(lab==s) for s in (0,1)]
            blocks=[[union[i] for i in g] for g in loc]
            edit0=int(np.count_nonzero(lab!=b0)); ed=min(edit0,n-edit0)
            align=[f for f,e in [(0,edit0),(1,n-edit0)] if e==ed]
            moved=[[union[i] for i in range(n) if (lab[i]^f)!=b0[i]] for f in align]
            results.append(dict(local_id=len(results),blocks=blocks,edit_count=ed,cost=float(cost),
                moved_nodes_alternative_alignments=moved,block_label_alignments=align,
                diameters_deg=None,supports=list(map(len,loc))))
    meta['feasible_count']=len(results);meta['infeasible_partition_count']=meta['all_unordered_two_nonempty_partitions']-len(results)
    return meta,results

def choose(results,mode='automatic',must=(),cannot=(),tol=1e-10):
    if not results:return dict(status='no_enumerated_candidates',selected_ids=[])
    old=next((r for r in results if r['edit_count']==0),None)
    if old is None:raise ValueError('baseline_not_preserved')
    candidates=results
    if mode=='automatic':
        candidates=[r for r in results if r['cost']<old['cost']-tol]
        if not candidates:return dict(status='unchanged',selected_ids=[old['local_id']],baseline_cost=old['cost'])
    elif mode=='human_assisted':
        allnodes=set(sum(results[0]['blocks'],[]))
        if any(x not in allnodes for rel in list(must)+list(cannot) for x in rel):
            return dict(status='constraints_outside_local_domain',selected_ids=[])
        def ok(r):
            label={i:j for j,g in enumerate(r['blocks']) for i in g}
            return all(len({label[i] for i in rel})==1 for rel in must) and all(label[a]!=label[b] for a,b in cannot)
        candidates=[r for r in results if ok(r)]
        if not candidates:return dict(status='infeasible_constraints',selected_ids=[])
    else:raise ValueError('unknown_policy')
    e=min(r['edit_count'] for r in candidates); cc=[r for r in candidates if r['edit_count']==e]
    c=min(r['cost'] for r in cc); best=[r for r in cc if r['cost']<=c+tol]
    return dict(status='numerically_unique' if len(best)==1 else 'multiple_tied',selected_ids=[r['local_id'] for r in best],
        edit_count=e,cost=c,baseline_cost=old['cost'],no_semantic_uniqueness_claim=True)

def frontier(results,tol=1e-10):
    out=[];best=float('inf')
    for e in sorted(set(r['edit_count'] for r in results)):
        rr=[r for r in results if r['edit_count']==e];c=min(r['cost'] for r in rr)
        if c<best-tol:
            out.extend(r['local_id'] for r in rr if r['cost']<=c+tol);best=c
    return out
