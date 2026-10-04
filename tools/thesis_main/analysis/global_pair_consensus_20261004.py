"""全员上下点对多数候选：跨点数身份对应、全员分母和显式新环诊断。

沿用9/26身份策略；不沿用整份标注分支，不读GT，不更改原点或原环。
5°及2.5°/10°均是未校准探索阈值；新环按中心shared-x排序且未确认。
"""
from __future__ import annotations

from collections import defaultdict
import copy
import math

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from .paired_split_research.study import angular
from .point_pattern_demo_20261003 import _pairs
from .research_round_20260929 import reconstruct
from .union_branch_consensus_20260926 import _ring_key

SCHEMA = 'global_pair_consensus_20261004_v1'


def _identities(records, threshold):
    if any(not {'id','worker','points'}<=r.keys() for r in records):
        raise ValueError('missing_annotation_fields')
    rows=sorted(records,key=lambda r:(str(r['worker']),str(r['id'])))
    if len({str(r['worker']) for r in rows})!=len(rows): raise ValueError('duplicate_worker')
    if len({str(r['id']) for r in rows})!=len(rows): raise ValueError('duplicate_annotation_id')
    nodes=[]; issues=[]; assignments=[]
    for r in rows:
        pairs,reason=_pairs(r)
        assignment=dict(id=r['id'],worker=r['worker'],feature_ids=[],
            source_ring_confirmed=r.get('ring_confirmed'),source_order_status=r.get('order_status'),
            input_status='unavailable' if reason else 'ok',reason=reason)
        assignments.append(assignment)
        if reason:
            issues.append(dict(id=r['id'],worker=r['worker'],reason=reason))
            continue
        geometry=reconstruct(r,coordinate_convention='continuous')
        assignment.update(feature_ids=[None]*len(pairs),source_geometry_status=geometry['status'],
                          source_geometry_reason=geometry['reason'])
        for i,pair in enumerate(pairs):
            nodes.append(dict(record=r,assignment=assignment,pair_index=i,pair=pair))
    # Canonical order fixes list/ring reordering; it does not resolve equal-distance merge choices.
    nodes.sort(key=lambda v:(str(v['record']['worker']),str(v['record']['id']),
        float(v['pair'][0,0]%1024),float(v['pair'][0,1]),float(v['pair'][1,1]),v['pair_index']))
    correspondence=dict(policy='deterministic constrained complete-linkage partition; not proven unique global correspondence',
        uniqueness_established=False,observations_with_multiple_matches_to_same_other_worker=0,
        competing_worker_matches=0,competing_match_examples=[],example_limit=20,
        partition_tie_check=dict(probe='reverse_canonical_observation_order',performed=False,
            partition_changed=False,affected_observation_count=0,
            limitation='single order-sensitivity probe; unchanged does not establish unique correspondence'),
        interpretation='threshold-compatible alternatives are ambiguity evidence, not feasible global partitions or posterior probabilities')
    if not nodes:return [],assignments,issues,correspondence
    p=np.array([v['pair'] for v in nodes])
    # angular is the existing pixel-centre formula; C-.5 only in memory makes it continuous ERP.
    distance=np.maximum(angular(p[:,0]-.5,p[:,0]-.5),angular(p[:,1]-.5,p[:,1]-.5))
    workers=np.array([str(v['record']['worker']) for v in nodes])
    constrained=distance.copy()
    constrained[workers[:,None]==workers[None,:]]=181.
    np.fill_diagonal(constrained,0.)
    # ponytail: O(total point-pairs²) per image, matching the existing small-panel implementation.
    labels=fcluster(linkage(squareform(constrained,checks=False),method='complete'),
                    threshold,criterion='distance')
    # Diagnostic only: keep the original partition and geometry, including its tie choice.
    reversed_labels=fcluster(linkage(squareform(constrained[::-1,::-1],checks=False),method='complete'),
                             threshold,criterion='distance')[::-1]
    members={label:frozenset(np.flatnonzero(labels==label)) for label in set(labels)}
    reversed_members={label:frozenset(np.flatnonzero(reversed_labels==label)) for label in set(reversed_labels)}
    affected=sum(members[a]!=reversed_members[b] for a,b in zip(labels,reversed_labels))
    correspondence['partition_tie_check'].update(performed=True,partition_changed=bool(affected),
                                                 affected_observation_count=int(affected))
    groups=[]
    ordered=sorted(set(labels),key=lambda label:int(np.flatnonzero(labels==label)[0]))
    for number,label in enumerate(ordered,1):
        indices=np.flatnonzero(labels==label)
        local=distance[np.ix_(indices,indices)]
        anchor=int(indices[int(np.argmin(local.sum(axis=1)))])
        xs=(p[indices,0,0]-p[anchor,0,0]+512)%1024-512
        ambiguous=bool(np.ptp(xs)>=512-1e-9 or np.any(abs(abs(xs)-512)<1e-9))
        center=None
        if not ambiguous:
            x=float((p[anchor,0,0]+np.median(xs))%1024)
            center=[[x,float(np.median(p[indices,0,1]))],[x,float(np.median(p[indices,1,1]))]]
        fid=f'corner_{number:03d}'; members=[]
        for j in indices:
            node=nodes[int(j)];r=node['record'];i=node['pair_index']
            node['assignment']['feature_ids'][i]=fid
            members.append(dict(id=r['id'],worker=r['worker'],pair_index=i,
                source_pair_index=r['source_pair_indices'][i] if r.get('source_pair_indices') is not None else None,
                source_point_indices=r['source_point_indices'][2*i:2*i+2] if r.get('source_point_indices') is not None else None,
                points=node['pair'].tolist()))
        if len({str(m['worker']) for m in members})!=len(members):
            raise AssertionError('one_person_more_than_one_vote_in_identity')
        groups.append(dict(feature_id=fid,support=len(members),support_workers=[m['worker'] for m in members],
            members=members,center=center,center_status='ambiguous_periodic_center' if ambiguous else 'ok',
            maximum_pair_angle_deg=float(local.max()),center_anchor=dict(id=nodes[anchor]['record']['id'],
            pair_index=nodes[anchor]['pair_index'])))
    ambiguous_nodes=set()
    for i,node in enumerate(nodes):
        alternatives=defaultdict(list)
        for j in np.flatnonzero((distance[i]<=threshold)&(workers!=workers[i])):
            other=nodes[int(j)]
            alternatives[str(other['record']['worker'])].append(dict(id=other['record']['id'],
                pair_index=other['pair_index'],feature_id=other['assignment']['feature_ids'][other['pair_index']],
                distance_deg=float(distance[i,j])))
        for worker,matches in alternatives.items():
            if len(matches)<2:continue
            ambiguous_nodes.add(i);correspondence['competing_worker_matches']+=1
            if len(correspondence['competing_match_examples'])<correspondence['example_limit']:
                correspondence['competing_match_examples'].append(dict(id=node['record']['id'],
                    worker=node['record']['worker'],pair_index=node['pair_index'],other_worker=worker,
                    candidates=matches))
    correspondence['observations_with_multiple_matches_to_same_other_worker']=len(ambiguous_nodes)
    return groups,assignments,issues,correspondence


def _ring_diagnostics(selected, assignments, denominator, minimum):
    ordered=sorted(selected,key=lambda g:(g['center'][0][0],g['feature_id']))
    ids=[g['feature_id'] for g in ordered]; retained=set(ids)
    ambiguous=[]
    for i,a in enumerate(ordered):
        for b in ordered[i+1:]:
            if abs((a['center'][0][0]-b['center'][0][0]+512)%1024-512)<=1e-9:
                ambiguous.append([a['feature_id'],b['feature_id']])
    direct=defaultdict(set); projected=defaultdict(set); comparisons=[]
    for row in assignments:
        ring=row['feature_ids']
        if not ring:continue
        for a,b in zip(ring,ring[1:]+ring[:1]):direct[tuple(sorted((a,b)))].add(str(row['worker']))
        kept=[i for i in ring if i in retained]
        if len(kept)>=3:
            for a,b in zip(kept,kept[1:]+kept[:1]):projected[tuple(sorted((a,b)))].add(str(row['worker']))
        comparable=len(kept)==len(ids) and len(ids)>=3
        comparisons.append(dict(id=row['id'],worker=row['worker'],retained_ring=kept,
            comparable=comparable,agrees=(_ring_key(kept)==_ring_key(ids)) if comparable else None,
            exact_original_ring_agrees=bool(comparable and len(ring)==len(ids) and _ring_key(ring)==_ring_key(ids))))
    edges=[]
    for a,b in zip(ids,ids[1:]+ids[:1]):
        key=tuple(sorted((a,b)));support=sorted(direct[key]); proj=sorted(projected[key])
        edges.append(dict(feature_ids=[a,b],support=len(support),support_workers=support,
            support_fraction=len(support)/denominator if denominator else None,
            meets_point_vote_threshold=len(support)>=minimum,
            projected_source_support=len(proj),projected_source_workers=proj))
    return ordered,dict(order_policy='ascending_periodic_shared_x_of_centers; not source ring confirmation',
        ring_confirmed=False,ambiguous_x_pairs=ambiguous,edges=edges,
        unsupported_edge_count=sum(e['support']==0 for e in edges),
        below_majority_edge_count=sum(not e['meets_point_vote_threshold'] for e in edges),
        source_ring_comparisons=comparisons,
        source_ring_disagreement_count=sum(c['agrees'] is False for c in comparisons),
        exact_source_ring_support=sum(c['exact_original_ring_agrees'] for c in comparisons),
        projected_source_ring_support=sum(c['agrees'] is True for c in comparisons),
        projected_source_rule='only an auxiliary ring after deleting unselected identities; not an observed original edge')


def _result(groups, assignments, issues, correspondence, n, threshold, method):
    minimum=math.ceil(n/2) if method=='mv50' else n//2+1
    groups=copy.deepcopy(groups)
    for g in groups:g.update(selected=g['support']>=minimum,support_fraction=g['support']/n if n else None)
    selected=[g for g in groups if g['selected']]
    candidate=dict(status='unavailable',reason=None,points=None,footprint=None,ring_confirmed=False,
        order_status='default_x_exploratory_unconfirmed',source_pair_indices=None,source_point_indices=None,
        source_point_labels=None,feature_ids=[],point_support_counts=[],source_pair_maps=[],
        center_method='medoid_anchored_periodic_shared_x_and_top_bottom_coordinate_medians')
    ring=dict(ring_confirmed=False,ambiguous_x_pairs=[],edges=[],unsupported_edge_count=0,
              below_majority_edge_count=0,source_ring_disagreement_count=0,source_ring_comparisons=[])
    if not n:candidate['reason']='no_annotations'
    elif len(selected)<3:candidate['reason']='fewer_than_three_majority_pairs'
    elif any(g['center'] is None for g in selected):candidate['reason']='ambiguous_periodic_center'
    else:
        ordered,ring=_ring_diagnostics(selected,assignments,n,minimum)
        if ring['ambiguous_x_pairs']:candidate['reason']='ambiguous_shared_x_order'
        else:
            candidate.update(points=[point for g in ordered for point in g['center']],
                feature_ids=[g['feature_id'] for g in ordered],point_support_counts=[g['support'] for g in ordered],
                source_pair_maps=[dict(feature_id=g['feature_id'],members=g['members']) for g in ordered])
            geometry=reconstruct(candidate,coordinate_convention='continuous')
            candidate.update(footprint=geometry['floor'].tolist() if geometry['floor'] is not None else None,
                geometry_status=geometry['status'],geometry_issues=geometry.get('issues',[]),
                geometry_polygon_valid=geometry['polygon_valid'])
            if geometry['status']!='ok':candidate['reason']='invalid_candidate_ring:'+str(geometry['reason'])
            else:
                flags=[]
                if ring['unsupported_edge_count']:flags.append('candidate_edges_without_source_adjacency')
                if ring['below_majority_edge_count']:flags.append('candidate_edges_below_majority_support')
                if ring['source_ring_disagreement_count']:flags.append('source_ring_disagreement')
                if correspondence['competing_worker_matches']:flags.append('competing_threshold_correspondences')
                if correspondence['partition_tie_check']['partition_changed']:flags.append('complete_linkage_partition_tie')
                if issues:flags.append('unavailable_input_observations_in_denominator')
                candidate.update(status='geometry_review' if flags else 'ok',reason=';'.join(flags) or None)
    return dict(schema_version=SCHEMA,status=candidate['status'],n=n,vote_denominator=n,method=method,
        minimum_support=minimum,threshold_deg=threshold,threshold_calibrated=False,candidate=candidate,
        identity_groups=groups,assignments=copy.deepcopy(assignments),input_issues=copy.deepcopy(issues),
        correspondence_diagnostics=copy.deepcopy(correspondence),
        unmatched_observations=[dict(feature_id=g['feature_id'],**m) for g in groups if g['support']==1 for m in g['members']],
        unselected_feature_ids=[g['feature_id'] for g in groups if not g['selected']],ring_diagnostics=ring,
        method_details=dict(identity='max(top,bottom) spherical endpoint angle; same-person-constrained complete linkage',
            center='observed-coordinate medians, one observation per person per identity; not a vote at the generated coordinate',
            denominator='all supplied independent people, including unavailable observations; missing is not an observed opposition vote',
            source_order='all original orders retained in assignments; new x-order is exploratory and unconfirmed',
            scope='one all-person candidate; no whole-annotation clustering, largest-cluster selection, GT, or geometry fit',
            limitations=['unvalidated_point_identity_tolerance','majority_points_do_not_imply_majority_edges',
                         'not_every_observed_corner_has_correspondence','valid_geometry_does_not_prove_scene_correctness']))


def build_global_pair_consensuses(records, threshold_deg=5.0):
    """同一身份池分别输出 >=50% 与 >50%；所有原观测及分母不变。"""
    threshold=float(threshold_deg)
    if not math.isfinite(threshold) or not 0<threshold<180:raise ValueError('invalid_threshold_deg')
    records=list(records)
    groups,assignments,issues,correspondence=_identities(records,threshold)
    return {method:_result(groups,assignments,issues,correspondence,len(records),threshold,method)
            for method in ('mv50','mv_strict')}


def build_global_pair_consensus(records, threshold_deg=5.0, method='mv50'):
    if method not in ('mv50','mv_strict'):raise ValueError('unknown_vote_method')
    return build_global_pair_consensuses(records,threshold_deg)[method]
