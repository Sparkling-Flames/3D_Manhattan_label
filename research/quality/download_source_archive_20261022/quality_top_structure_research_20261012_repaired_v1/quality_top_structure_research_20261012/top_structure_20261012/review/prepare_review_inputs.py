#!/usr/bin/env python3
"""Create a portable, exact source subset; preserve current/source point versions."""
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path
import numpy as np
from PIL import Image

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def project(v):
    q=np.asarray(v,float)
    return np.c_[((np.arctan2(q[:,0],-q[:,2])/(2*np.pi)+.5)*1024)%1024,
                 (.5-np.arctan2(q[:,1],np.linalg.norm(q[:,[0,2]],axis=1))/np.pi)*512]

def main():
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,default=Path.cwd());a.add_argument('--out',type=Path)
    args=a.parse_args();root=args.root.resolve();out=(args.out or root/'top_structure_20261012/review').resolve()
    cfg=read(out/'review_config.json')
    old=root/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    files={'formal':old/'inputs/current_formal_loader_data.json','geometry':old/'inputs/current_geometry_compact.json',
           'components':old/'results/current_components.json','photos':root/'study_data/original_image_index.json',
           'ledger':root/'study_severe/results/ledger_115.json'}
    objects={o['object_id']:o for o in read(files['formal'])['objects']}
    geoms=read(files['geometry'])['geometries']; comps={c['record_id']:c for c in read(files['components'])}
    photos={i['image_id']:i for i in read(files['photos'])};ledger={c['case_id']:c for c in read(files['ledger'])}
    inputs=out/'inputs';(inputs/'originals').mkdir(parents=True,exist_ok=True)
    records=[];copied={};checks=[]
    selected_fields=['object_id','object_kind','image_id','image_code','worker_id','condition','source','original_export_points',
        'before_preprocessing_points','preprocessed_points','points_1024x512','point_labels','links_zero_based','ordered_source_point_indices',
        'ordered_source_pair_indices','ordered_source_point_labels','pairing_basis','preprocessing_status','preprocessing','repair_evidence',
        'cleaning_disposition','worker_quality_gate','consensus_group','scene_category','scene_oos_status','scene_doorway_status','ring_confirmed',
        'order_status','order_record','order_origins','original_export_indices','deleted_previous_point_indices','building_id','room_id']
    for spec in cfg['cases']:
        c=comps[spec['record_id']];o=objects[c['object_id']];ref_id=c['reference_object_id'];ref=geoms[ref_id];g=geoms.get(c['object_id'])
        idx=o.get('ordered_source_point_indices');before=o.get('before_preprocessing_points');p=o.get('points_1024x512')
        current_available=bool(before)
        if g:
            assert idx is not None and before and p
            assert len(idx)==len(before)==len(p)
            assert sorted(idx)==list(range(len(before)))
            current=np.asarray(before)[idx];processed=np.asarray(p)
            assert np.array_equal(np.asarray(o['preprocessed_points'])[idx],processed)
            assert np.array_equal(current[:,1],processed[:,1])
            ordered_pairs=list(zip(idx[::2],idx[1::2]))
            assert all(list(x) in o['links_zero_based'] for x in ordered_pairs)
            assert o['pairing_basis']=='existing_verified'
            projected=np.empty_like(processed);projected[::2]=project(g['top3d']);projected[1::2]=project(g['bottom3d'])
            dx=(projected[:,0]-processed[:,0]+512)%1024-512
            error=float(max(np.max(abs(dx)),np.max(abs(projected[:,1]-processed[:,1]))))
            assert error<1e-9,error
            check={'blind_id':spec['blind_id'],'point_layer_mapping_exact':True,'source_pairing_preserved':True,
                   'frozen_geometry_projection_max_px':error,'ring_human_confirmation':bool(o.get('ring_confirmed'))}
        else:
            assert not idx and not p, 'Do not silently replace an existing reconstruction'
            check={'blind_id':spec['blind_id'],'frozen_geometry_projection_max_px':None,'annotation_3d_omitted':True}
        ref_points=np.asarray(objects[ref_id]['points_1024x512'])
        ref_projected=np.empty_like(ref_points);ref_projected[::2]=project(ref['top3d']);ref_projected[1::2]=project(ref['bottom3d'])
        ref_error=float(max(np.max(abs((ref_projected[:,0]-ref_points[:,0]+512)%1024-512)),np.max(abs(ref_projected[:,1]-ref_points[:,1]))))
        assert ref_error<1e-9
        check['fixed_reference_projection_max_px']=ref_error
        photo=photos[c['image_id']];src=Path(photo['local_path']);assert src.is_file(),src
        assert sha(src)==photo['sha256']
        im=Image.open(src);im.load();assert im.size==(2048,1024),im.size
        dest=inputs/'originals'/f'{c["image_code"]}.png'
        if c['image_id'] not in copied:
            shutil.copyfile(src,dest);assert sha(dest)==photo['sha256']
            copied[c['image_id']]={'image_id':c['image_id'],'image_code':c['image_code'],'source_library_zip':photo['image_zip'],
                'archive_internal_path':photo['internal_path'],'relative_path':str(dest.relative_to(out)),
                'sha256':photo['sha256'],'bytes':dest.stat().st_size,'resolution':[2048,1024]}
        record={**spec,'object_id':o['object_id'],'reference_object_id':ref_id,'image_id':c['image_id'],'image_code':c['image_code'],
            'current_formal_input':{k:o.get(k) for k in selected_fields},'reference_formal_input':{k:objects[ref_id].get(k) for k in selected_fields},
            'frozen_annotation_geometry':g,'fixed_reference_geometry':ref,'photo':copied[c['image_id']],
            'reference_was_not_reselected':True,'new_geometry_inferred':False,'source_equals_current_before':o['original_export_points']==before,
            'visual_inspection_record':'research_selection_notes.json; semantic review is not inferred by this script','current_input_exists':current_available,
            'screen_eligibility_record':ledger.get(spec['case_id']),
            'research_only_component_snapshot':{k:c.get(k) for k in ['iou_2d','iou_3d_corner_mean','Hmean','Hlocal','Hstar','dir','flat','S_top_deg','S_bottom_deg','Q']}}
        records.append(record);checks.append(check)
    data={'schema_version':1,'study':cfg['study'],'no_source_mutations':True,'records':records,
          'provenance':{k:{'path':str(p.relative_to(root)),'sha256':sha(p)} for k,p in files.items()}}
    (inputs/'review_inputs.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    (inputs/'selected_original_images.json').write_text(json.dumps(list(copied.values()),ensure_ascii=False,indent=2)+'\n')
    (out/'results/source_checks.json').write_text(json.dumps({'case_count':len(records),'unique_originals':len(copied),'checks':checks},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cases':len(records),'unique_originals':len(copied),'all_source_checks_passed':True}))

if __name__=='__main__':main()
