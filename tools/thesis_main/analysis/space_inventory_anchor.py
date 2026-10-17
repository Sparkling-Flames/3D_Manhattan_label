"""Target-image GT and human geometry enter generation as anchors, never scores."""
from __future__ import annotations
import collections
import json
from pathlib import Path
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from . import simulate_annotators as base
from .difficulty_wild_inputs import DEFAULT_INPUT, DIFFICULTY, read, csv_rows
from .geometry_cluster_v2 import cluster_geometry_records
from .geometry_consensus.pairwise import pairwise_similarity
from .geometry_consensus.representation import normalize_geometry

VERSION='space_inventory_anchor_v1'
CUTOFF=.95
VALID='basic_checks_passed_not_certified'
SCENES=base.ROOT/'analysis_results/difficulty_scope_preferred_20261011/current_259.csv'
DATA='analysis_results/research_input_20261017/data.json'
POLICY='Target-image GT and human geometry first enter generation as anchors. No GT scoring or quality certification. Profiles and time donors retain building holdout.'


def nearest(points, anchors):
    p=np.asarray(points,float);a=np.asarray(anchors,float)
    dx=np.abs((p[:,None,0]-a[None,:,0]+512)%1024-512)
    return np.hypot(dx,p[:,None,1]-a[None,:,1]).min(axis=1)


def canonical(points):
    g=normalize_geometry(points)
    if not g['valid']:return None,g
    p=np.array([[x,y] for x,t,b in zip(g['x_event_positions'],g['top_y'],g['floor_y']) for y in (t,b)],float)
    return p,g


def anchor_eligible(p):
    if p is None or len(p)<6:return False
    q=p.copy();q[::2,1]=np.minimum(q[::2,1],255.95);q[1::2,1]=np.maximum(q[1::2,1],258.)
    return base.geometry_status(q)==VALID and np.linalg.norm(q-p,axis=1).max()<20


def partition(records):
    cache={}
    def pair(a,b):
        key=(json.dumps(a['raw_points']),json.dumps(b['raw_points']))
        if key not in cache:cache[key]=pairwise_similarity(a,b)
        return cache[key]
    result=cluster_geometry_records(records,min_q_boundary=CUTOFF,min_q_wallwall=CUTOFF,minimum_valid_k=1,pairwise_fn=pair)
    groups=json.loads(result['cluster_membership_json']);policy='unique_existing_complete_link'
    if not groups:
        candidates=json.loads(result['candidate_partitions_json'])
        if candidates:groups=candidates[0];policy='first_enumerated_complete_link_partition_ambiguity_reported'
        else:
            n=len(records);matrix=np.zeros((n,n))
            for i in range(n):
                for j in range(i):
                    q=pair(records[i]['geometry'],records[j]['geometry'])
                    matrix[i,j]=matrix[j,i]=1-min(q['q_boundary'],q['q_wallwall']) if q['pointwise_correspondence_compatible'] else 1.
            labels=fcluster(linkage(squareform(matrix),method='complete'),1-CUTOFF,criterion='distance') if n>1 else [1]
            by=collections.defaultdict(list)
            for r,label in zip(records,labels):by[int(label)].append(r['annotation_id'])
            groups=sorted(by.values());policy='complete_link_agglomerative_enumeration_cap'
    return groups,dict(partition_policy=policy,partition_status=result['partition_status'],enumeration_truncated=result['enumeration_truncated'])


def similar(a,b):
    q=pairwise_similarity(normalize_geometry(a),normalize_geometry(b))
    return bool(q['pointwise_correspondence_compatible'] and q['q_boundary']>=CUTOFF and q['q_wallwall']>=CUTOFF)


def continuous_match(child,parent,tolerance=20):
    c=np.asarray(child).reshape(-1,2,2);p=np.asarray(parent).reshape(-1,2,2)
    if len(c)>=len(p):return None
    for start in range(len(p)):
        ix=[(start+j)%len(p) for j in range(len(c))]
        dx=(c[:,:,0]-p[ix,:,0]+512)%1024-512;dy=c[:,:,1]-p[ix,:,1]
        if np.hypot(dx,dy).max()<=tolerance:return ix
    return None


def build_inventory(directory=DEFAULT_INPUT):
    directory=Path(directory);raw=read(directory/DATA)
    difficulty={r['image_id']:r for r in csv_rows(directory/DIFFICULTY/'image_inventory.csv')}
    scenes={r['image_id']:r for r in csv_rows(SCENES)};images={r['image_id']:r for r in raw['images']}
    humans=collections.defaultdict(list);gt={}
    for r in raw['objects']:
        iid=r['image_id']
        if r['object_kind']=='annotation':humans[iid].append(r)
        elif r['object_kind'] in ('gt_original','gt_manual_revision'):
            if iid not in gt or r['object_kind']=='gt_manual_revision':gt[iid]=r
    scope_rows=csv_rows(directory/'research/workers/worker_b8l2_d10_20261017/scope_response_evidence.csv')
    scope={r['object_id']:('oos' if r['worker_scope']=='out_of_scope' else r['worker_scope']) for r in scope_rows}
    inventory=[]
    for iid in sorted(difficulty):
        ds=difficulty[iid];scene=scenes[iid]['scene'];im=images[iid]
        oos=scene in ('oos','oos_and_doorway','oos_pending') or im.get('oos_status')=='confirmed'
        records=[];excluded=[]
        for r in sorted(humans[iid],key=lambda r:r['object_id']):
            p,g=canonical(r['preprocessed_points'])
            if not anchor_eligible(p):
                excluded.append(dict(annotation_id=r['object_id'],reason=g.get('reason') or (base.geometry_status(p) if p is not None else 'invalid')));continue
            records.append(dict(annotation_id=r['object_id'],geometry=g,points=p.tolist(),worker_id=r['worker_id']))
        if not records:raise ValueError('no_valid_human_anchor:'+iid)
        groups,cluster_audit=partition(records);by={r['annotation_id']:r for r in records}
        gtrow=gt.get(iid);gp,gg=canonical(gtrow['points_1024x512']) if gtrow else (None,{})
        use_gt=not oos and ds['gt_error_excluded']!='True' and ds['reference_full_available']=='True' and gp is not None and base.geometry_status(gp)==VALID
        spaces=[]
        if use_gt:spaces.append(dict(space_id=iid+':reference',space_kind='reference',anchor_source=gtrow['object_kind'],anchor_annotation_id=gtrow['object_id'],anchors=gp.tolist(),members=[],scope_expected='in_scope'))
        for k,ids in enumerate(sorted(groups,key=lambda ids:(-len(ids),ids))):
            members=[by[x] for x in ids]
            def cost(r):return sum(.5*(nearest(r['points'],q['points']).mean()+nearest(q['points'],r['points']).mean()) for q in members)
            medoid=min(members,key=lambda r:(cost(r),r['annotation_id']));mp=medoid['points']
            if use_gt and similar(mp,gp) and not spaces[0]['members']:space=spaces[0]
            else:
                space=dict(space_id=iid+f':cluster_{k:02d}',space_kind='alternative',anchor_source='cluster_medoid',anchor_annotation_id=medoid['annotation_id'],anchors=mp,members=[],scope_expected='oos');spaces.append(space)
            space['members'].extend(ids)
        if not oos:
            for s in spaces:
                if s['space_kind']=='reference':continue
                for parent in sorted(spaces,key=lambda r:-len(r['anchors'])):
                    ix=continuous_match(s['anchors'],parent['anchors'])
                    if ix is not None:s.update(space_kind='subrange',parent_space_id=parent['space_id'],parent_pair_indices=ix,scope_expected=parent['scope_expected']);break
        for s in spaces:
            members=[by[x] for x in s['members']];s['human_n']=len(members);s['human_frequency']=len(members)/len(records)
            s['pair_count_histogram']=dict(sorted(collections.Counter(str(len(r['points'])//2) for r in members).items()))
            s['scope_counts']=dict(collections.Counter(scope[x] for x in s['members'] if x in scope));s['anchor_junction_count']=len(s['anchors'])//2
            radii=[]
            for r in members:
                if r['annotation_id']!=s['anchor_annotation_id']:radii.extend(nearest(r['points'],s['anchors']).tolist())
            nonzero=np.array([d for d in radii if d>1e-5]);scale=3/float(np.median(nonzero)) if len(nonzero) else 1.
            fitted=np.clip(nonzero*scale,.5,15) if len(nonzero) else np.array([2.,3.,4.])
            s['jitter_calibration']=dict(method='empirical_radius_quantiles_median_calibrated_3px',raw_count=len(radii),raw_median=float(np.median(radii)) if radii else None,scale=scale,quantiles=np.quantile(fitted,np.linspace(0,1,101)).tolist(),normal_cap_px=15,wild_cap_px=20,source_annotation_ids=[r['annotation_id'] for r in members],fallback='2_3_4px_sparse_evidence' if not len(nonzero) else None)
        inventory.append(dict(image_id=iid,image=ds['image'],scene=scene,oos=oos,gt_used_as_anchor=use_gt,gt_record_id=gtrow['object_id'] if gtrow else None,gt_record_source=gtrow['object_kind'] if gtrow else None,gt_exclusion_reason='oos_policy' if oos else 'gt_error_or_full_unavailable' if not use_gt else None,spaces=spaces,human_valid_n=len(records),human_total_n=len(humans[iid]),excluded_geometry=excluded,**cluster_audit))
    paths=(directory/DATA,directory/DIFFICULTY/'image_inventory.csv',SCENES,directory/'research/workers/worker_b8l2_d10_20261017/scope_response_evidence.csv')
    manifest=dict(version=VERSION,policy_change=POLICY,threshold=dict(q_boundary=CUTOFF,q_wallwall=CUTOFF,require_pointwise_correspondence=True,source='geometry_consensus.loo default similarity_cutoff'),source_sha256={str(p):base.digest(p) for p in paths},frequency_denominator='valid per-image human geometry; invalid records enumerated and retained in population counts',space_inference_limit='Geometry clusters infer spaces. Sparse evidence and nearby distinct rooms require visual review.',scope_policy='Reference expects in_scope; alternative expects oos; subrange inherits parent; observed votes sampled unchanged, conflicts diagnosed.')
    return inventory,manifest
