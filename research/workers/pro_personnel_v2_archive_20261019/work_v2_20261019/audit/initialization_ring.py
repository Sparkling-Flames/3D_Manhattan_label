"""Recover ONLY an already declared, human-confirmed initialization ring.

The v2 container embeds the deployed payload coordinates, while some inherited
paired scores explicitly use a reviewed ring of those exact paired coordinates.
No GT, score optimization, new pairing, coordinate edit, or guessed order is used.
"""
import json
import numpy as np

def recover_declared_initial_ring(row,by_object):
    s=row['semi_evidence'];payload=s['initialization_points']
    h=s.get('historical_paired_scores') or {}
    changed=h.get('initial_ring_changed_from_payload') in (True,'True')
    evidence=dict(method='native_payload_declared_ring',ring_changed_from_payload=changed,
                  source_object_ids=[],pair_permutation=None,coordinate_edit=False,selected_by_score=False)
    if not changed:return payload,evidence
    if h.get('initial_ring_status')!='existing_confirmed_ring_exact_point_identity':
        raise ValueError('Changed initialization ring lacks explicit confirmed-ring provenance: '+row['object_id'])
    ids=h.get('initial_ring_source_object_ids') or []
    if isinstance(ids,str):ids=json.loads(ids)
    if not ids:raise ValueError('No source objects for declared initial ring: '+row['object_id'])
    pairs=np.asarray(payload,dtype=float).reshape(-1,2,2)
    mappings=[]
    for oid in sorted(ids):
        source=by_object[oid]
        if not source['ring_confirmed']:
            raise ValueError('Source ring is not confirmed: '+oid)
        target=np.asarray(source['points_1024x512'],dtype=float).reshape(-1,2,2)
        if target.shape!=pairs.shape:raise ValueError('Initial ring source pair count differs: '+oid)
        mapping=[]
        for p in target:
            options=np.flatnonzero(np.max(np.abs(pairs-p),axis=(1,2))<=1e-6).tolist()
            if len(options)!=1:raise ValueError('Ambiguous or missing exact bound pair in initial ring source: '+oid)
            mapping.append(options[0])
        if len(set(mapping))!=len(pairs):raise ValueError('Nonbijective initial pair permutation: '+oid)
        mappings.append(mapping)
    # Multiple named source declarations must agree up to a shared cyclic start.
    first=mappings[0]
    if any(not any(v==first[k:]+first[:k] for k in range(len(first))) for v in mappings[1:]):
        raise ValueError('Conflicting pre-existing initialization ring sources: '+row['object_id'])
    adopted=pairs[first].reshape(-1,2).tolist()
    evidence.update(method='existing_confirmed_ring_exact_point_identity',source_object_ids=sorted(ids),pair_permutation=first)
    return adopted,evidence
