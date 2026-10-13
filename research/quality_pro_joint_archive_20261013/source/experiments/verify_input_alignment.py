#!/usr/bin/env python3
"""Compare the actual local X field against Pro's endpoint intervention definition."""
import argparse,json,math
from pathlib import Path
import numpy as np
from export_real_descriptors import read,write,digest,sha


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--local-results',required=True,type=Path)
    ap.add_argument('--out',type=Path,default=Path(__file__).parent/'results');args=ap.parse_args()
    data=read(args.source/'inputs/calibration_records.json')
    raw=read(args.source/'input_quality/results/source_layers_922.json');rawby={r['object_id']:r for r in raw}
    local=read(args.local_results);localby={r['record_id']:r for r in local['rows']};rows=[]
    for r in data['rows']:
        layer=rawby[r['object_id']];points=np.asarray(layer['before_preprocessing_points'],float)
        meanx=np.asarray(layer['preprocessed_points'],float);pairs=np.asarray(layer['links_zero_based'],int)
        source=localby.get(r['id']);row={'record_id':r['id'],'object_id':r['object_id'],
            'current_points_sha256':r['current_points_sha256'],
            'raw_before_preprocessing_sha256_canonical':digest(layer['before_preprocessing_points']),
            'mean_x_preprocessed_sha256_canonical':digest(layer['preprocessed_points'])}
        if source is None:row['status']='missing_local_result';rows.append(row);continue
        gap=(points[pairs[:,0],0]-points[pairs[:,1],0]+512)%1024-512
        X=float(np.sqrt(np.mean((gap*360/1024)**2)))
        # This E is obtained from all actual stored endpoint movements, not
        # calculated as X/2; equality therefore checks the stored preprocessing.
        displacement=(meanx[:,0]-points[:,0]+512)%1024-512
        E=float(np.sqrt(np.mean((displacement*360/1024)**2)))
        old_local=source['raw_input']['X_rms_deg']
        mid=(points[pairs[:,0],0]+points[pairs[:,1],0])/2
        midpoint_error=max(float(abs(meanx[pairs[:,0],0]-mid).max()),float(abs(meanx[pairs[:,1],0]-mid).max()))
        row.update(status='available',local_X_rms_deg=old_local,recomputed_pair_gap_rms_deg=X,
            independently_computed_endpoint_intervention_Eperp_deg=E,
            abs_local_X_minus_recomputed_X_deg=abs(old_local-X),abs_local_X_minus_2E_deg=abs(old_local-2*E),
            input_version=source['input_version'],reference_version=source['reference_version'],
            input_version_matches_frozen_point_hash=source['input_version'].endswith(':'+r['current_points_sha256']),
            object_id_matches=source['object_id']==r['object_id'],
            local_coordinate_group_matches=source['coordinate_group']==r['coordinate_hash'],
            maximum_midpoint_difference_px=midpoint_error,
            maximum_changed_latitude_px=float(abs(meanx[:,1]-points[:,1]).max()),
            all_source_points_used_once=sorted(pairs.ravel().tolist())==list(range(len(points))),
            result_is_mechanical_diagnostic_not_pairing_semantic_approval=True)
        rows.append(row)
    valid=[r for r in rows if r['status']=='available']
    summary={'n_rows':len(rows),'n_available':len(valid),
        'max_abs_local_X_minus_recomputed_X_deg':max(r['abs_local_X_minus_recomputed_X_deg'] for r in valid),
        'max_abs_local_X_minus_2_direct_intervention_E_deg':max(r['abs_local_X_minus_2E_deg'] for r in valid),
        'max_midpoint_error_px':max(r['maximum_midpoint_difference_px'] for r in valid),
        'max_changed_latitude_px':max(r['maximum_changed_latitude_px'] for r in valid),
        'all_versions_object_ids_and_coordinate_groups_match':all(r['input_version_matches_frozen_point_hash'] and r['object_id_matches'] and r['local_coordinate_group_matches'] for r in valid),
        'all_source_points_used_once':all(r['all_source_points_used_once'] for r in valid),
        'source_calibration_sha256':sha(args.source/'inputs/calibration_records.json'),
        'source_raw_layers_sha256':sha(args.source/'input_quality/results/source_layers_922.json'),
        'local_results_sha256':sha(args.local_results),
        'X_and_Eperp_units':'degrees_longitude_not_geodesic_distance',
        'no_quality_threshold_inferred':True}
    assert summary['all_versions_object_ids_and_coordinate_groups_match']
    assert summary['max_abs_local_X_minus_2_direct_intervention_E_deg']<1e-10
    write(args.out/'input_alignment_cross_version_verification.json',{'summary':summary,'rows':rows})
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
