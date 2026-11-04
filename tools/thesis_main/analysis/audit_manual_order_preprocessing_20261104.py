"""Read-only preprocessing audit from the explicit v2.1 bundle to 57 saved nodes.

Re-evaluates preprocessing invariants and saved group centers; no fusion or
re-selection and no writes to the original input bundle.
"""
from __future__ import annotations
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .apply_manual_ring_orders_20261104 import ROOT, SOURCE, RETURN, OUT, BASE_COMMIT, read
from .shared_x_reanalysis_20260922 import shared_x
from .paired_split_research.study import angular


def maximum(a,b):
    if a is None or b is None:return 0. if a is None and b is None else np.inf
    a=np.asarray(a,float);b=np.asarray(b,float)
    return float(np.max(np.abs(a-b))) if a.shape==b.shape and a.size else 0. if a.shape==b.shape else np.inf


def main():
    out=OUT.parent/'preprocessing_audit';out.mkdir(parents=True,exist_ok=True)
    data_path=ROOT/'research/data/releases/v2.1/analysis_input/data.json.gz'
    bundle=read(data_path);objects={o['object_id']:o for o in bundle['objects']}
    inventory=[]
    for o in objects.values():
        ready=o.get('preprocessing_status')=='ready'
        row=dict(object_id=o['object_id'],object_kind=o['object_kind'],image=o.get('image_code'),
                 preprocessing_status=o.get('preprocessing_status'),ready=ready,
                 before_preprocessing_available=o.get('before_preprocessing_points') is not None,
                 original_export_available=o.get('original_export_points') is not None,
                 original_export_is_before_preprocessing=o.get('original_export_points')==o.get('before_preprocessing_points'))
        if ready:
            before=o['before_preprocessing_points'];after=o['preprocessed_points'];links=o['links_zero_based']
            calculated=shared_x(before,links).tolist()
            row.update(preprocessing_max_difference=maximum(calculated,after),
                y_unchanged=[p[1] for p in before]==[p[1] for p in after],
                point_count_unchanged=len(before)==len(after),
                shared_x_max_difference=max(abs(after[a][0]-after[b][0]) for a,b in links),
                idempotence_max_difference=maximum(shared_x(after,links),after),
                ordered_view_max_difference=maximum([after[i] for i in o['ordered_source_point_indices']],o['points_1024x512']),
                source_point_mapping_complete=sorted(o['ordered_source_point_indices'])==list(range(len(after))))
        else:
            row.update(unavailable_points_stay_null=o.get('points_1024x512') is None,
                       blocked_not_replaced_by_raw=True)
        inventory.append(row)
    inv=pd.DataFrame(inventory);inv.to_csv(out/'ALL_INVENTORY_PREPROCESSING_CHECKS.csv.gz',index=False)
    failed=inv[inv.ready & ((inv.preprocessing_max_difference>1e-8)|(inv.shared_x_max_difference>1e-8)|
        (inv.idempotence_max_difference>1e-8)|(inv.ordered_view_max_difference>1e-8)|
        ~inv.y_unchanged.fillna(True).astype(bool)|~inv.point_count_unchanged.fillna(True).astype(bool)|
        ~inv.source_point_mapping_complete.fillna(True).astype(bool))]
    failed.to_csv(out/'INVENTORY_EXCEPTIONS.csv',index=False)
    assert inv.loc[~inv.ready,'unavailable_points_stay_null'].all()
    # The current input is authoritative: documented point edits may happen after
    # the first preprocessing. Exceptions must be inspected, not silently undone.
    records=[];centers=[];refs=[]
    catalog={ (r['target_id'],r['reference_version']):r for r in read(ROOT/'research/data/releases/v2.1/reference_catalog.json') }
    orders=pd.read_csv(RETURN/'VALIDATED_ENDPOINT_ORDERS.csv.gz')
    for order in orders.to_dict('records'):
        case=read(SOURCE/'prepared'/(order['review_id']+'.json.gz'))
        source={r['id']:r for r in case['records']}
        for r in source.values():
            o=objects[r['id']]
            pair=np.asarray(r['points'],float).reshape(-1,2,2)
            records.append(dict(review_id=case['review_id'],team_key=case['team_key'],object_id=r['id'],worker=r['worker'],
                origin=r.get('origin'),preprocessing_status=o.get('preprocessing_status'),
                points_match_explicit_v21_bundle=maximum(r['points'],o['points_1024x512'])<1e-8,
                max_coordinate_difference=maximum(r['points'],o['points_1024x512']),
                top_bottom_shared_x_max_difference=float(np.abs(pair[:,0,0]-pair[:,1,0]).max()),
                pair_y_order_valid=bool((pair[:,0,1]<pair[:,1,1]).all()),
                finite_coordinates=bool(np.isfinite(pair).all()),
                source_mapping_comparison=('not_stored_in_saved_record' if r.get('source_point_indices') is None else
                    'equal' if r['source_point_indices']==o.get('ordered_source_point_indices') else 'different_nonnull'),
                original_export_available=o.get('original_export_points') is not None,
                source_input_changed_by_this_run=False))
        for node in case['nodes']:
            points=np.array([np.asarray(source[m['id']]['points']).reshape(-1,2,2)[m['pair_index']] for m in node['members']],float)
            top=angular(points[:,0]-.5,points[:,0]-.5);bottom=angular(points[:,1]-.5,points[:,1]-.5)
            anchor=int(np.argmin(np.maximum(top,bottom).sum(axis=1)))
            dx=(points[:,0,0]-points[anchor,0,0]+512)%1024-512
            x=float((points[anchor,0,0]+np.median(dx))%1024)
            center=[[x,float(np.median(points[:,0,1]))],[x,float(np.median(points[:,1,1]))]]
            centers.append(dict(team_key=case['team_key'],feature_id=node['feature_id'],support=node['support'],
                source_count=len(points),center_rule='same_identity_medoid_anchored_periodic_median',
                center_max_difference=maximum(center,node['points']),
                own_pair_shared_x=node['points'][0][0]==node['points'][1][0],
                vote_threshold_valid=2*node['support']>=case['k'],
                unique_workers_valid=len({m['worker'] for m in node['members']})==len(points),
                recentered=False))
        reference=catalog[(case['reference_id'],case['reference_version'])]
        refs.append(dict(team_key=case['team_key'],reference_id=case['reference_id'],reference_version=case['reference_version'],
                         reference_points_sha256=hashlib.sha256(json.dumps(reference['points_1024x512'],separators=(',',':')).encode()).hexdigest(),
                         reference_not_reprocessed=True,reference_not_chosen_by_score=True))
    records=pd.DataFrame(records);centers=pd.DataFrame(centers)
    records.to_csv(out/'57_TEAM_SOURCE_COORDINATE_CHAIN.csv.gz',index=False)
    centers.to_csv(out/'57_TEAM_NODE_CENTER_CHECKS.csv',index=False)
    pd.DataFrame(refs).to_csv(out/'REFERENCE_PROCESSING_BOUNDARY.csv',index=False)
    assert records.points_match_explicit_v21_bundle.all()
    assert records.finite_coordinates.all() and records.pair_y_order_valid.all()
    assert not records.source_mapping_comparison.eq('different_nonnull').any()
    assert records.top_bottom_shared_x_max_difference.max()<1e-8
    assert centers.center_max_difference.max()<1e-8
    assert centers.vote_threshold_valid.all() and centers.unique_workers_valid.all()
    receipt=dict(source_commit=BASE_COMMIT,explicit_manifest='research/data/releases/v2.1/analysis_input/manifest.json',
        bundle_objects=len(inv),annotation_inventory=int(inv.object_kind.eq('annotation').sum()),
        preprocessing_ready=int(inv.ready.sum()),blocked_or_unavailable=int((~inv.ready).sum()),
        preprocessing_exceptions=len(failed),ready_max_shared_x_replay_difference=float(inv.preprocessing_max_difference.max()),
        source_team_record_links=len(records),unique_source_objects=records.object_id.nunique(),
        source_mapping_statuses=records.source_mapping_comparison.value_counts().to_dict(),
        source_coordinate_chain_max_difference=float(records.max_coordinate_difference.max()),
        frozen_nodes=len(centers),saved_center_replay_max_difference=float(centers.center_max_difference.max()),
        all_source_records_already_shared_x=True,all57_centers_already_frozen_medians=True,
        raw_exports_used_as_replacement=False,source_preprocessing_reapplied_to_outputs=False,
        whole_library_fusion_replayed=False,reference_reselected=False,
        cross_node_F2_F9_mean_is_standard_preprocessing=False)
    (out/'CHECKS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2));print(failed.to_string(index=False))


if __name__=='__main__':main()
