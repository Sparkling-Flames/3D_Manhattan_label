"""Observed 2-vs-3-pair path candidates; not extra votes or a full-pool consensus.

All local positive matches are logged. Full source-context alternatives are made
only when both endpoint identity groups coincide in the frozen raw partition.
Anchors use the same global coordinate-center estimator as the point baseline.
All source records stay immutable. Alternative rings are checked, not repaired.
"""
from __future__ import annotations
import json,gzip,copy,hashlib,math
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from shapely.geometry import Polygon,Point
from baseline import key
from frechet import rays,spherical_check
from run import ROOT,dump,text_gzip

def footprint(points):
    q=np.asarray(points,float).reshape(-1,2,2);v=rays(q[:,1])
    if len(q)<3 or np.any(v[:,1]>=-1e-12):return None,None,'bottom_or_cardinality_failure'
    xy=(-v/v[:,1,None])[:,[0,2]];p=Polygon(xy)
    return xy.tolist(),p,None if p.is_valid and p.area>1e-12 else 'invalid_polygon'

def edge_key(a,b):
    aa=tuple(np.round(np.asarray(a).flatten(),9));bb=tuple(np.round(np.asarray(b).flatten(),9))
    return tuple(sorted((aa,bb)))

def run_patches(out):
    out=Path(out);dest=out/'patches';dest.mkdir(exist_ok=False)
    summary=[]
    for f in sorted((ROOT/'inputs').glob('*.json')):
        if f.name=='human_review.json':continue
        im=json.loads(f.read_text());rs={r['id']:r for r in im['records']};folder=out/im['image']
        ns=json.loads((folder/'nodes.json').read_text());paths={p['path_id']:p for p in json.loads((folder/'source_path_catalogue.json').read_text())}
        direct=defaultdict(set)
        for r in rs.values():
            q=np.asarray(r['points']).reshape(-1,2,2)
            for a,b in zip(q,np.roll(q,-1,axis=0)):direct[edge_key(a,b)].add(r['worker'])
        for tau in [5,9,12]:
            state=json.loads((folder/f'pair_{tau}.json').read_text());groups=state['raw_MV']['groups']
            lut={i:g for g in groups for i in g['node_indices']}
            legs={}
            for line in gzip.open(folder/f'pair_{tau}_path_evidence.jsonl.gz','rt'):
                z=json.loads(line)
                for l in z['legs']:
                    if sorted(l['steps'])==[1,2] and l['status']=='accept':
                        k=tuple(sorted(l['paths']));legs[k]=l
            matches=[];candidates=[]
            for num,(pid,qid) in enumerate(sorted(legs)):
                p=paths[pid];q=paths[qid]
                sameanchors=(lut[p['start_node']]['feature_id']==lut[q['start_node']]['feature_id'] and
                             lut[p['end_node']]['feature_id']==lut[q['end_node']]['feature_id'])
                rec={'id':f"{im['image']}_{tau}_L{num}",'paths':[pid,qid],'path_sizes':[p['edge_count']+1,q['edge_count']+1],
                     'source_records':[p['id'],q['id']],'endpoint_correspondence_hypothesis':[[p['start_node'],q['start_node']],[p['end_node'],q['end_node']]],
                     'same_raw_endpoint_groups':sameanchors,'gate_deg':tau,'status':'same_raw_anchor_identities' if sameanchors else 'competing_anchor_identity_hypothesis',
                     'continuous_path_evidence':legs[(pid,qid)],'all_internal_observations_retained':True,
                     'coarse_endpoint_support_not_inherited_by_internal_structure':True}
                matches.append(rec)
                if not sameanchors:continue
                for bpath,dpath in [(p,q),(q,p)]:
                    base=rs[bpath['id']];B=np.asarray(base['points']).reshape(-1,2,2)
                    ids=bpath['processed_pair_indices'];donor=np.asarray(dpath['points']).reshape(-1,2,2).copy()
                    if bpath['direction_relative_to_source']==-1:ids=list(reversed(ids));donor=donor[::-1].copy()
                    start=ids[0];end=ids[-1];n=len(B)
                    # Reverse orientation changes which raw anchor center is at each end.
                    bs=bpath['start_node'] if bpath['direction_relative_to_source']==1 else bpath['end_node']
                    be=bpath['end_node'] if bpath['direction_relative_to_source']==1 else bpath['start_node']
                    c0=lut[bs]['center']['points'];c1=lut[be]['center']['points']
                    if c0 is None or c1 is None:
                        candidates.append({'id':rec['id']+'_'+base['id'],'status':'ambiguous_anchor_center','local_match':rec['id']});continue
                    olddonor=donor.copy();donor[0]=c0;donor[-1]=c1
                    rest=[];j=(end+1)%n
                    while j!=start:rest.append(j);j=(j+1)%n
                    new=np.concatenate([donor,B[rest]],axis=0)
                    anchor_only=B.copy();anchor_only[start]=c0;anchor_only[end]=c1
                    anchor_xy,anchor_poly,anchor_reason=footprint(anchor_only.reshape(-1,2).tolist())
                    raw_base_path=B[ids]
                    checks={}
                    for origin,rawpath in [('base',raw_base_path),('donor',olddonor)]:
                        checks[origin]={side:spherical_check(rays(donor[:,j]),rays(rawpath[:,j]),tau)
                                        for side,j in [('top',0),('bottom',1)]}
                    pts=new.reshape(-1,2).tolist();xy,poly,reason=footprint(pts);oldxy,oldpoly,_=footprint(base['points'])
                    edges=[]
                    for ei,(a,b) in enumerate(zip(new,np.roll(new,-1,axis=0))):
                        workers=sorted(direct.get(edge_key(a,b),[]))
                        edges.append({'index':ei,'exact_endpoint_original_edge_workers':workers,
                                      'new_edge_not_exact_original':len(workers)==0})
                    candidates.append({'id':rec['id']+'_'+base['id'],'image':im['image'],'threshold_deg':tau,
                        'role':'single_observed_path_replacement_with_frozen_raw_anchor_centers_not_all_person_consensus',
                        'voting_role':'not_an_independent_vote','vote_denominator_unchanged':len(rs),
                        'local_match':rec['id'],'base_record':base['id'],'donor_record':dpath['id'],
                        'base_processed_path':ids,'donor_processed_path':dpath['processed_pair_indices'],
                        'donor_path_used_order':dpath['processed_pair_indices'] if bpath['direction_relative_to_source']==1 else list(reversed(dpath['processed_pair_indices'])),
                        'new_anchor_group_member_node_indices':[lut[bs]['node_indices'],lut[be]['node_indices']],
                        'base_internal_vertices_removed_in_candidate_only':ids[1:-1],
                        'donor_internal_vertices_retained':dpath['processed_pair_indices'][1:-1],
                        'base_context_retained_indices':rest,'anchor_group_ids':[lut[bs]['feature_id'],lut[be]['feature_id']],
                        'anchor_supports':[lut[bs]['support'],lut[be]['support']],
                        'exact_local_path_donor_before_anchor_movement':dpath['worker'],
                        'candidate_path_has_new_anchor_endpoints':not np.allclose(donor,olddonor,atol=1e-9,rtol=0),
                        'whole_candidate_support':'not_established','ring_confirmed':False,
                        'points':pts,'footprint':xy,'status':'geometry_candidate_unreviewed' if reason is None else reason,
                        'camera_inside':bool(poly.contains(Point(0,0))) if reason is None else None,
                        'anchor_only_control_points':anchor_only.reshape(-1,2).tolist(),
                        'anchor_only_control_geometry_status':anchor_reason or 'ok',
                        'added_relative_to_anchor_only_h2':float(poly.difference(anchor_poly).area) if reason is None and anchor_reason is None else None,
                        'lost_relative_to_anchor_only_h2':float(anchor_poly.difference(poly).area) if reason is None and anchor_reason is None else None,
                        'post_center_path_comparison':checks,
                        'post_center_compatibility_status':'outside_previous_local_gate' if any(v['status']=='reject' for side in checks.values() for v in side.values()) else 'within_previous_local_gate' if all(v['status']=='accept' for side in checks.values() for v in side.values()) else 'numerically_undetermined',
                        'new_edges':edges,'added_relative_to_base_h2':float(poly.difference(oldpoly).area) if reason is None else None,
                        'lost_relative_to_base_h2':float(oldpoly.difference(poly).area) if reason is None else None,
                        'fewer_than_four_pairs_allowed':True})
            dump(dest/f'{im["image"]}_{tau}_local_matches.json',matches)
            with text_gzip(dest/f'{im["image"]}_{tau}_candidate_rings.jsonl.gz') as z:
                for c in candidates:z.write(json.dumps(c,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
            summary.append({'image':im['image'],'threshold_deg':tau,'all_2v3_positive_path_matches':len(matches),
                'same_raw_anchor_identity_matches':sum(m['same_raw_endpoint_groups'] for m in matches),
                'candidate_rings':len(candidates),'statuses':dict(Counter(c['status'] for c in candidates)),
                'new_edge_count':sum(sum(e['new_edge_not_exact_original'] for e in c.get('new_edges',[])) for c in candidates),
                'interpretation':'finite alternative catalogue not extra workers; repeated output candidates are not independent samples'})
    dump(dest/'summary.json',summary)
if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--out',required=True);run_patches(a.parse_args().out)
