"""Short source-path witnesses, preserving segmentation and full input roster.

Witnesses constrain endpoint identity hypotheses only. The two boundary curves
are traversed separately. This does NOT infer a common interior paired-parameter
map, semantic target, or a new physical wall. Every source interior point remains.
"""
from __future__ import annotations
import math,json,gzip,copy
from collections import defaultdict,Counter
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from shapely.geometry import Polygon
from baseline import key,center,normalize_blocks,partition
from frechet import rays,arc_length,spherical_check

class PathBank:
    def __init__(self,records,nodes,config):
        self.records={r['id']:r for r in records};self.nodes=nodes;self.config=config
        self.index={key(n):i for i,n in enumerate(nodes)};self.paths={};self.polycache={};self.certcache={}
        self.calls=Counter()
    def get(self,ni,direction,edges):
        node=self.nodes[ni];r=self.records[node['id']];n=len(r['points'])//2
        ix=[(node['pair_index']+direction*k)%n for k in range(edges+1)]
        pid=f"{r['id']}:{node['pair_index']}:{direction}:{edges}"
        if pid not in self.paths:
            q=np.asarray(r['points']).reshape(-1,2,2)[ix]
            rv={s:rays(q[:,j]) for s,j in [('top',0),('bottom',1)]}
            self.paths[pid]=dict(path_id=pid,id=r['id'],worker=r['worker'],processed_pair_indices=ix,
                source_pair_indices=[r['source_pair_indices'][i] for i in ix],
                source_point_indices=[r['source_point_indices'][2*i:2*i+2] for i in ix],
                points=q.reshape(-1,2).tolist(),edge_count=edges,direction_relative_to_source=direction,
                internal_observations=[{'id':r['id'],'pair_index':i,'source_pair_index':r['source_pair_indices'][i]} for i in ix[1:-1]],
                source_ring_confirmed=r.get('ring_confirmed'),
                spherical_lengths_deg={s:arc_length(v) for s,v in rv.items()},_rays=rv,
                start_node=ni,end_node=self.index[(r['id'],ix[-1])])
        return self.paths[pid]
    def compare_side(self,p,q,side,g):
        k=tuple(sorted((p['path_id'],q['path_id'])))+(side,)
        old=self.certcache.get(k,[])
        for res in old:
            if res['status']=='accept' and res['upper_deg']<=g+1e-12:
                self.calls['cached_pass']+=1;return dict(res,cached_from_gate=res['upper_deg'])
            if res['status']=='reject' and res['lower_deg']>g+1e-12:
                self.calls['cached_fail']+=1;return dict(res,cached_from_gate=res['lower_deg'])
        self.calls['kernel']+=1
        try:
            res=spherical_check(p['_rays'][side],q['_rays'][side],g,
                steps=self.config['sphere_approximation_steps_deg'],cache=self.polycache,
                key=((p['path_id'],side),(q['path_id'],side)))
        except ValueError as e:res={'status':'undetermined','reason':str(e),'lower_deg':0.,'upper_deg':None}
        self.certcache.setdefault(k,[]).append(res);return res
    def leg(self,i,j,da,db,ea,eb,metric,g,D):
        p=self.get(i,da,ea);q=self.get(j,db,eb)
        r=dict(paths=[p['path_id'],q['path_id']],steps=[ea,eb],end_nodes=[p['end_node'],q['end_node']],sides={})
        endpoint=float(D[metric][p['end_node'],q['end_node']]);r['anchor_distance_deg']=endpoint
        if endpoint>g+1e-10:return dict(r,status='anchor_outside_gate')
        sides=['bottom','top'] if metric=='pair' else [metric]
        if any(max(p['spherical_lengths_deg'][s],q['spherical_lengths_deg'][s])>
               self.config['maximum_side_path_length_deg'] for s in sides):
            return dict(r,status='path_length_outside_declared_domain')
        status='accept'
        for s in sides:
            z=self.compare_side(p,q,s,g);r['sides'][s]=z
            if z['status']=='reject':return dict(r,status='reject')
            if z['status']=='undetermined':status='undetermined'
        return dict(r,status=status)
    def witness(self,i,j,metric,g,D):
        base=dict(nodes=[i,j],focal_distance_deg=float(D[metric][i,j]),metric=metric,gate_deg=g)
        if self.nodes[i]['worker']==self.nodes[j]['worker']:return dict(base,status='same_person',legs=[],witnesses=[])
        if D[metric][i,j]>g+1e-10:return dict(base,status='focal_outside_gate',legs=[],witnesses=[])
        legs=[];witnesses=[];uncertain=False
        ni=len(self.records[self.nodes[i]['id']]['points'])//2;nj=len(self.records[self.nodes[j]['id']]['points'])//2
        for orient in (1,-1):
            batches={}
            for da in (-1,1):
                batch=[]
                for ea in self.config['source_path_edge_counts']:
                    for eb in self.config['source_path_edge_counts']:
                        res=self.leg(i,j,da,da*orient,ea,eb,metric,g,D)
                        res['orientation']=orient;res['side_of_focal']=da
                        ix=len(legs);legs.append(res);batch.append(ix)
                batches[da]=batch
            for a in batches[-1]:
                for b in batches[1]:
                    left=legs[a];right=legs[b]
                    # A complete cycle is not a local path; outer anchors must differ.
                    if left['steps'][0]+right['steps'][0]>=ni or left['steps'][1]+right['steps'][1]>=nj:continue
                    if (left['status'] in ('accept','undetermined') and right['status'] in ('accept','undetermined')
                        and 'undetermined' in (left['status'],right['status'])):uncertain=True
                    if left['status']=='accept' and right['status']=='accept':
                        witnesses.append({'orientation':orient,'leg_indices':[a,b],
                            'raw_path_donors':[self.nodes[i]['worker'],self.nodes[j]['worker']],
                            'interior_point_identities_inferred':False})
        return dict(base,status='witnessed' if witnesses else 'numerically_unresolved' if uncertain else 'not_witnessed',
            legs=legs,witnesses=witnesses,
            interpretation='geometric_candidate_only; two separate boundary traversals; no semantic equivalence guarantee')
    def public_paths(self):return [{k:v for k,v in p.items() if not k.startswith('_')} for p in self.paths.values()]

def filter_partition(nodes,D,metric,g,ledger):
    a=D[metric].copy();allowed={(r['nodes'][0],r['nodes'][1]) for r in ledger if r['status']=='witnessed'}
    for i in range(len(nodes)):
        for j in range(i+1,len(nodes)):
            if (i,j) not in allowed:a[i,j]=a[j,i]=181.
    return partition(nodes,a,g)[0]

def report_groups(nodes,groups,D,n_people):
    groups=sorted(groups,key=lambda x:min(x));out=[];lookup={}
    for gi,g in enumerate(groups):
        c=center(nodes,g,D['pair']);fid=f'G{gi:03d}'
        out.append(dict(feature_id=fid,node_indices=g,support=len(g),support_workers=[nodes[i]['worker'] for i in g],
            selected=len(g)>=math.ceil(n_people/2),center=c,
            marginal_diameters_deg={s:float(d[np.ix_(g,g)].max()) for s,d in D.items()},
            support_scope='geometric_identity_members; no semantic target or location vote certification'))
        for i in g:lookup[i]=fid
    return out,lookup

def partition_changes(nodes,old,new):
    a={i:k for k,g in enumerate(old) for i in g};b={i:k for k,g in enumerate(new) for i in g}
    removed=[];added=[]
    for i in range(len(nodes)):
        for j in range(i+1,len(nodes)):
            if a[i]==a[j] and b[i]!=b[j]:removed.append([i,j])
            if a[i]!=a[j] and b[i]==b[j]:added.append([i,j])
    return {'lost_comemberships':removed,'new_comemberships':added,
        'affected_nodes':sorted({x for pair in removed+added for x in pair}),
        'no_semantic_harm_claim_for_unreviewed_members':True}

def ring_diagnostics(records,nodes,group_reports,lookup):
    selected={g['feature_id']:g for g in group_reports if g['selected']}
    node_by_key={key(n):i for i,n in enumerate(nodes)}
    centers={k:v['center']['points'] for k,v in selected.items() if v['center']['points'] is not None}
    direct=defaultdict(set);projected=defaultdict(set);cycles=defaultdict(list)
    assignments=[]
    def canon(ring):
        rr=[]
        for q in [ring,list(reversed(ring))]:rr.extend(tuple(q[i:]+q[:i]) for i in range(len(q)))
        return min(rr)
    for r in records:
        cyc=[lookup[node_by_key[(r['id'],i)]] for i in range(len(r['points'])//2)]
        assignments.append({'id':r['id'],'worker':r['worker'],'source_identity_cycle':cyc})
        for a,b in zip(cyc,cyc[1:]+cyc[:1]):direct[tuple(sorted((a,b)))].add(r['worker'])
        kept=[x for x in cyc if x in selected]
        if len(kept)>=3:
            for a,b in zip(kept,kept[1:]+kept[:1]):projected[tuple(sorted((a,b)))].add(r['worker'])
        if len(cyc)==len(selected) and len(cyc)>=3 and len(set(cyc))==len(cyc) and set(cyc)==set(selected):
            cycles[canon(cyc)].append(r['id'])
    ordered=sorted(centers,key=lambda k:(centers[k][0][0],k))
    edges=[{'identity_pair':[a,b],'direct_workers':sorted(direct[tuple(sorted((a,b)))]),
            'deletion_projected_workers':sorted(projected[tuple(sorted((a,b)))]),
            'new_edge_without_direct_source':not bool(direct[tuple(sorted((a,b)))])}
           for a,b in zip(ordered,ordered[1:]+ordered[:1])] if len(ordered)>=2 else []
    def candidate(cycle):
        pts=[p for k in cycle for p in centers[k]]
        rr=rays(np.asarray(pts,float).reshape(-1,2)[1::2]);poly=None;reason=None;xy=None
        if len(cycle)<3:reason='fewer_than_three_geometry_vertices_but_all_MV_nodes_retained'
        elif np.any(rr[:,1]>=-1e-12):reason='bottom_not_below_horizon'
        else:
            xy=(-rr/rr[:,1,None])[:,[0,2]].tolist();poly=Polygon(xy)
            if not poly.is_valid or poly.area<=1e-12:reason='invalid_new_polygon'
        return {'points':pts,'identity_cycle':list(cycle),'ring_confirmed':False,'footprint':xy,
                'geometry_valid':reason is None,'reason':reason,'area_h2':float(poly.area) if reason is None else None}
    x=candidate(ordered);x['role']='unconfirmed_center_x_diagnostic_not_source_ring_reordering'
    observed=[]
    for cyc,rids in cycles.items():
        if not set(cyc)<=set(centers):continue
        observed.append({'source_records':rids,'whole_cycle_incidence':len(rids),'candidate':candidate(list(cyc)),
                         'no_votes_for_new_center_coordinates':True})
    unanimous= (len(observed)==1 and len(observed[0]['source_records'])==len(records)
                and observed[0]['candidate']['geometry_valid'])
    return {'selected_pair_count':len(selected),'minimum_four_pairs_enforced':False,
            'x_diagnostic':x,'x_diagnostic_edges':edges,'all_complete_observed_cycles':observed,
            'primary_ring_available':unanimous,'primary_ring':observed[0]['candidate'] if unanimous else None,
            'assignments':assignments,'local_correspondence_not_full_layout_certification':True}
