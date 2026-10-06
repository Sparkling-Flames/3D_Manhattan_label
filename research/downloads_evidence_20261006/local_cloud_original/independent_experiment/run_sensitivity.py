"""Finite exact-coordinate preservation sensitivity. No imports from source solver.

Run against original delivered snapshot. Every node remains a separate worker vote.
Equality preservation is a hypothetical constraint, never a semantic label.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, itertools, json, math, os, sys
from pathlib import Path
import numpy as np

IMAGE='rPc6DW4iMge-06'
TOL=1e-10

def dump(p,v):
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def key(n):return n['id']+':'+str(n['pair_index'])
def canonical_mask(blocks,u):
    a=set(blocks[0]); lab=[int(i not in a) for i in u]
    if lab[0]:lab=[1-v for v in lab]
    return sum(v<<j for j,v in enumerate(lab))
def decode(masks,n):
    return ((np.asarray(masks,dtype=np.uint64)[:,None]>>np.arange(n,dtype=np.uint64)[None,:])&1).astype(np.int8)

class ParityDSU:
    def __init__(self,n):self.p=list(range(n));self.x=[0]*n;self.s=[1]*n
    def find(self,a):
        if self.p[a]!=a:
            p,x=self.find(self.p[a]);self.x[a]^=x;self.p[a]=p
        return self.p[a],self.x[a]
    def constrain(self,a,b,value):
        aa,xa=self.find(a);bb,xb=self.find(b)
        if aa==bb:return (xa^xb)==value
        if self.s[aa]<self.s[bb]:aa,bb=bb,aa
        self.p[bb]=aa;self.x[bb]=xa^xb^value;self.s[aa]+=self.s[bb]
        return True

def solve(n,constraints,max_states=262144):
    d=ParityDSU(n)
    for a,b,value in constraints:
        if not d.constrain(a,b,value):return [],{'status':'infeasible','contradiction_edge':[a,b,value]}
    roots=[d.find(i) for i in range(n)];root0,x0=roots[0]
    free=sorted(set(r for r,x in roots)-{root0});states=2**len(free)
    if n>32 or states>max_states:return [],{'status':'budget_exceeded','orientation_states':states}
    idx={r:j for j,r in enumerate(free)};masks=[]
    for start in range(0,states,4096):
        ints=np.arange(start,min(states,start+4096),dtype=np.uint64);m=np.zeros(len(ints),np.uint64)
        for j,(r,x) in enumerate(roots):
            vals=np.full(len(ints),x^x0,np.uint64) if r==root0 else ((ints>>idx[r])&1)^x
            m|=vals<<j
        masks.extend(int(v) for v in m if v!=0 and v!=(1<<n)-1)
    return sorted(masks),{'status':'ok','orientation_states':states,'components':len(free)+1}

def nodes_and_distances(records):
    ns=[]
    for r in records:
        assert r['independent'] is True and r['consensus_eligible'] is True
        for j in range(len(r['points'])//2):
            ns.append(dict(id=r['id'],worker=r['worker'],pair_index=j,points=r['points'][2*j:2*j+2],source_pair_index=r.get('source_pair_indices',[None]*(len(r['points'])//2))[j]))
    ns.sort(key=lambda n:(str(n['worker']),str(n['id']),n['points'][0][0]%1024,n['points'][0][1],n['points'][1][1],n['pair_index']))
    p=np.array([n['points'] for n in ns],float); ds={}
    for name,k in [('top',0),('bottom',1)]:
        lon=p[:,k,0]*2*np.pi/1024;lat=np.pi/2-p[:,k,1]*np.pi/512
        xyz=np.c_[np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)]
        cross=np.cross(xyz[:,None,:],xyz[None,:,:]);dot=np.einsum('ik,jk->ij',xyz,xyz)
        ds[name]=np.arctan2(np.linalg.norm(cross,axis=2),dot)*180/np.pi;np.fill_diagonal(ds[name],0)
    ds['pair']=np.maximum(ds['top'],ds['bottom'])
    return ns,ds

def coordinates_signature(n):return tuple(v for p in n['points'] for v in p)
def summary(masks,u,ns,dist,tau,base,targets,eqblocks,source_ids):
    if not masks:return {'feasible_count':0}
    n=len(u);labels=decode(masks,n);old=np.array([int(i in base[1]) for i in u]);edit0=(labels!=old).sum(1);edits=np.minimum(edit0,n-edit0)
    costs=np.zeros(len(masks));sizes=labels.sum(1);w=(dist[np.ix_(u,u)]/tau)**2
    for i,j in itertools.combinations(range(n),2):
        same=labels[:,i]==labels[:,j]
        costs+=np.where(same,w[i,j]/np.where(labels[:,i],sizes,n-sizes),0.)
    mine=int(edits.min());minc=float(costs[edits==mine].min());best=np.flatnonzero((edits==mine)&(costs<=minc+TOL))
    oldrelations={tuple(sorted((a,b))) for g in base for a,b in itertools.combinations(g,2)}
    selected=[]
    for row in best:
        lab=labels[row];blocks=[[u[j] for j in range(n) if lab[j]==c] for c in (0,1)]
        changed={tuple(sorted((a,b))) for g in blocks for a,b in itertools.combinations(g,2)}
        lost=oldrelations-changed;added=changed-oldrelations
        align=[f for f,e in [(0,edit0[row]),(1,n-edit0[row])] if e==edits[row]]
        all_points=[ns[i]['points'] for i in u]
        moved=[[key(ns[u[j]]) for j in range(n) if (lab[j]^f)!=old[j]] for f in align]
        selected.append({'canonical_mask':int(masks[row]),'upstream_candidate_id':source_ids[int(masks[row])],
          'blocks':[[key(ns[i]) for i in g] for g in blocks], 'support':[len(g) for g in blocks],
          'edit_count':int(edits[row]),'cost':float(costs[row]),'moved_alternative_alignments':moved,
          'target_group_members':next(([key(ns[i]) for i in g] for g in blocks if set(targets)<=set(g)),None),
          'target_group_support':next((len(g) for g in blocks if set(targets)<=set(g)),None),
          'diameters_deg':[float(dist[np.ix_(g,g)].max()) for g in blocks],
          'lost_relations':[[key(ns[a]),key(ns[b])] for a,b in sorted(lost)],
          'added_relations':[[key(ns[a]),key(ns[b])] for a,b in sorted(added)],
          'identical_full_coordinates_split':[[key(ns[a]),key(ns[b])] for a,b in sorted(lost) if coordinates_signature(ns[a])==coordinates_signature(ns[b])],
          'worker_unique':all(len({ns[i]['worker'] for i in g})==len(g) for g in blocks),
          'observation_cover_exact':sorted(sum(blocks,[]))==u})
    out={'feasible_count':len(masks),'minimum_edit':mine,'minimum_edit_then_cost':minc,'selection_status':'numerically_unique' if len(selected)==1 else 'multiple_tied','selected_count':len(selected),'selected':selected,'cost_range':[float(costs.min()),float(costs.max())]}
    if set(targets)<=set(u):
        a=u.index(targets[0]);in_target=labels==labels[:,a,None];together=np.ones(len(masks),bool)
        for b in targets[1:]:together&=in_target[:,u.index(b)]
        out['reviewed_triple_together_count']=int(together.sum())
        members=in_target[together]
        if len(members):
            support=members.sum(1);forced=members.all(0);possible=members.any(0)
            out.update(target_support_range=[int(support.min()),int(support.max())],target_support_histogram={str(int(k)):int(v) for k,v in zip(*np.unique(support,return_counts=True))},
              support_at_least_12_count=int((support>=12).sum()),support_greater_than_12_count=int((support>12).sum()),
              forced_members=[key(ns[u[j]]) for j in np.flatnonzero(forced)],possible_members=[key(ns[u[j]]) for j in np.flatnonzero(possible)],
              variable_members=[key(ns[u[j]]) for j in np.flatnonzero(possible&~forced)])
            pts=np.array([ns[i]['points'] for i in u]);x0=ns[targets[0]]['points'][0][0];dx=(pts[:,0,0]-x0+512)%1024-512
            # A domain-wide span under half a turn certifies common local circular unwrap.
            if np.ptp(dx)<512-1e-9 and np.max(abs(dx))<512-1e-9:
                xyz=np.c_[x0+dx,pts[:,0,1],pts[:,1,1]]; centers=np.empty((len(members),3))
                for k in range(3):centers[:,k]=np.nanmedian(np.where(members,xyz[None,:,k],np.nan),axis=1)
                out['conditional_center_extrema']={name:[float(centers[:,j].min()),float(centers[:,j].max())] for j,name in enumerate(['x_unwrapped_px','top_y_px','bottom_y_px'])}
                out['conditional_center_extrema']['x_anchor_px']=x0
                out['conditional_center_extrema']['interpretation']='Coordinate-median extrema over target assignments, not confidence intervals; x can be reduced modulo 1024. No top/bottom semantic target is newly established.'
            else:out['conditional_center_extrema']={'status':'ambiguous_unwrap_not_reported'}
    return out

def tests():
    assert len(solve(4,[])[0])==7
    assert len(solve(4,[(0,1,0)])[0])==3
    assert solve(3,[(0,1,0),(0,1,1)])[1]['status']=='infeasible'
    assert solve(3,[(0,1,1),(1,2,1),(0,2,1)])[1]['status']=='infeasible'
    assert len(solve(4,[(0,1,1),(2,3,1)])[0])==2
    assert solve(4,[],2)[1]['status']=='budget_exceeded'
    # Exhaustive all parity-constraint subsets on three nodes against brute force.
    possible=[(i,j,p) for i,j in itertools.combinations(range(3),2) for p in (0,1)]
    for flags in range(2**len(possible)):
        cs=[v for k,v in enumerate(possible) if flags>>k&1]
        observed=solve(3,cs)[0]; expected=[m for m in (2,4,6) if all(((m>>a&1)^(m>>b&1))==p for a,b,p in cs)]
        assert observed==expected
    return {'unit_assertions':6,'exhaustive_three_node_constraint_systems':64,'all_passed':True}

def main(src,out):
    out.mkdir(parents=True,exist_ok=False); dump(out/'unit_tests.json',tests())
    rec=json.loads((src/'inputs'/f'{IMAGE}.json').read_text())['records'];ns,ds=nodes_and_distances(rec)
    lookup=json.loads((src/'results/domains/node_lookup.json').read_text())[IMAGE]
    assert len(rec)==24 and len({r['worker'] for r in rec})==24 and len(ns)==224
    assert [(key(n),n['points'],n['worker']) for n in ns]==[(key(n),n['points'],n['worker']) for n in lookup]
    reviews=json.loads((src/'inputs/human_review.json').read_text())['reviews'];rv=next(r for r in reviews if r['case_id']=='rpc_lower')
    targets=[next(i for i,n in enumerate(ns) if n['id']==rid and n['pair_index']==j) for rid,j in zip(rv['record_ids'],rv['processed_pair_indices'])]
    wrong=next(i for i,n in enumerate(ns) if n['id']==rv['record_ids'][2] and n['pair_index']==rv['rejected_previous_purple_processed_pair_index'])
    index=json.loads((src/'results/domains/domains_summary.json').read_text());domains=[s for s in index if s['image']==IMAGE and s.get('domain_id')]
    assert len(domains)==30;rows=[];source_hashes={};tot=0
    for s in domains:
        name=s['domain_id'];fp=src/'results/domains'/f'{name}.json';obj=json.loads(fp.read_text());dm=obj['domain'];u=dm['union'];n=len(u);base=dm['baseline_blocks'];tau=s['threshold'];dist=ds[s['metric']];position={i:j for j,i in enumerate(u)}
        original=sorted(sum(base,[]));assert original==u
        bad=[(position[a],position[b],1) for a,b in itertools.combinations(u,2) if ns[a]['worker']==ns[b]['worker'] or dist[a,b]>tau]
        original_bad={tuple(v['nodes']) for v in dm['forbidden_pairs']}
        assert {(u[a],u[b]) for a,b,_ in bad}==original_bad
        equal=[]
        for block in base:
            buckets=collections.defaultdict(list)
            for i in block:buckets[coordinates_signature(ns[i])].append(i)
            equal.extend(v for v in buckets.values() if len(v)>1)
        eq=[(position[g[0]],position[j],0) for g in equal for j in g[1:]]
        ledger=src/'results/domains'/obj['all_candidate_ledger']
        if ledger.exists():
            triples=[]
            for line in gzip.open(ledger,'rt'):
                r=json.loads(line);triples.append((canonical_mask(r['blocks'],u),r['local_id'],r['cost']))
            mm=np.asarray([v[0] for v in triples],np.uint64)
            ids=np.asarray([v[1] for v in triples],np.uint32)
            savedcost=np.asarray([v[2] for v in triples],float)
        else:
            ledger=src/'results/domains'/obj['compact_reference']
            with np.load(ledger,allow_pickle=False) as data:mm=data['mask'].astype(np.uint64);ids=data['id'];savedcost=data['cost']
        source_ids={int(m):int(i) for m,i in zip(mm,ids)}
        source_cost={int(m):float(c) for m,c in zip(mm,savedcost)}
        assert len(source_ids)==len(mm), 'duplicate_reference_partitions'
        keep_eq=np.ones(len(mm),bool)
        for a,b,_ in eq:keep_eq&=((mm>>a)&1)==((mm>>b)&1)
        keep_human=np.full(len(mm),set(targets)<=set(u),bool)
        if set(targets)<=set(u):
            a=position[targets[0]]
            for node in targets[1:]:keep_human&=((mm>>a)&1)==((mm>>position[node])&1)
            if wrong in u:keep_human&=((mm>>a)&1)!=((mm>>position[wrong])&1)
        refs={'geometry':set(source_ids),'geometry_equal':set(map(int,mm[keep_eq])),
              'human':set(map(int,mm[keep_human])),'human_equal':set(map(int,mm[keep_eq&keep_human]))}
        human=[]
        if set(targets)<=set(u):
            human=[(position[targets[0]],position[b],0) for b in targets[1:]]
            if wrong in u:human.append((position[targets[0]],position[wrong],1))
        row={'domain_id':name,'threshold':tau,'metric':s['metric'],'union_nodes':n,'baseline_support':[len(g) for g in base],
             'equal_blocks':[[key(ns[i]) for i in g] for g in equal], 'equal_block_node_counts':[len(g) for g in equal],
             'independent_forbidden_edges_match':True,'full_roster':24,'all_input_observations':224,'outside_groups_unchanged':True,'conditions':{}}
        arrays={}
        for condition,extra in [('geometry',[]),('geometry_equal',eq),('human',human),('human_equal',human+eq)]:
            if condition.startswith('human') and not set(targets)<=set(u):
                row['conditions'][condition]={'status':'constraints_outside_local_domain','feasible_count':None};continue
            masks,meta=solve(n,bad+extra)
            assert set(masks)==refs[condition],(name,condition,'independent_solver_ledger_mismatch')
            arrays[condition]=np.array(masks,np.uint64)
            q=summary(masks,u,ns,dist,tau,base,targets,equal,source_ids);q.update(meta,exact_assignment_set_matches_upstream_filter=True)
            if masks:
                for sel in q['selected']:assert abs(sel['cost']-source_cost[sel['canonical_mask']])<1e-10
            row['conditions'][condition]=q
        if name==f'{IMAGE}_pair_5_d0':
            # Completely independent direct assignment check (not parity component search).
            allm=np.arange(0,1<<(n-1),dtype=np.uint64)<<1;labs=decode(allm,n);ok=(labs.sum(1)>0)
            for a,b,_ in bad:ok&=labs[:,a]!=labs[:,b]
            direct=set(int(m) for m in allm[ok]);assert direct==refs['geometry'];row['direct_bruteforce']={'canonical_assignments_including_empty':len(allm),'legal_nonempty':len(direct),'exact_set_match':True}
            assert n==18
        np.savez_compressed(out/f'{name}_masks.npz',union=np.asarray(u),**arrays)
        dump(out/f'{name}.json',row);rows.append(row);tot+=len(source_ids)
        source_hashes[str(fp.relative_to(src))]=hashlib.sha256(fp.read_bytes()).hexdigest();source_hashes[str(ledger.relative_to(src))]=hashlib.sha256(ledger.read_bytes()).hexdigest()
        print(json.dumps({'domain':name,'equal_blocks':row['equal_block_node_counts'],'conditions':{k:{z:v.get(z) for z in ['status','feasible_count','minimum_edit','target_support_range','support_at_least_12_count','support_greater_than_12_count']} for k,v in row['conditions'].items()}}),flush=True)
    dump(out/'all_domains.json',rows);dump(out/'node_lookup.json',ns);dump(out/'source_ledger_sha256.json',source_hashes)
    verification={'domains':len(rows),'source_candidates_compared':tot,'all_exact_set_comparisons_passed':True,'all_forbidden_edge_sets_match':True,
        'independently_reconstructed_nodes_match':True,'roster':24,'observations':224,'no_gt_used':True,'input_modified':False,'new_semantics_propagated':False,'complete_layout_created':False,'preserve_equality_is_sensitivity_only':True,
        'aided_complete_domains':sum(r['conditions']['human']['status']!='constraints_outside_local_domain' for r in rows),
        'aided_equal_feasible_domains':sum((r['conditions']['human_equal']['feasible_count'] or 0)>0 for r in rows)}
    dump(out/'verification.json',verification);print(json.dumps(verification),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.source,a.out)
