import pandas as pd
import pytest
from tools.thesis_main.data_prep.inventory_annotation_research_assets_20260905 import _aligned_pano_region_records


def test_train_single_and_pano_identity_and_alignment(tmp_path):
    images=tmp_path/'train_room_single_image.txt';labels=tmp_path/'train_room_single_label.txt'
    images.write_text('/data/H1/undistorted_color_images/abc_i1_0.jpg\n/data/H2/undistorted_color_images/abc_i2_1.jpg\n')
    labels.write_text('2\n3\n')
    records,status=_aligned_pano_region_records(images,labels)
    assert records==[('H1_abc','region_class:2'),('H2_abc','region_class:3')]
    images.write_text('./data/mp_sb/H1/abc.jpg\n');labels.write_text('2\n')
    assert _aligned_pano_region_records(images,labels)[0]==[('H1_abc','region_class:2')]
    labels.write_text('2\n3\n');assert 'mismatch' in _aligned_pano_region_records(images,labels)[1]
    images.write_text('./data/mp_sb/H1/abc.jpg\n\n');labels.write_text('2\n3\n')
    assert _aligned_pano_region_records(images,labels)[0]==[]


def test_conflict_missing_and_class_are_not_instance():
    from tools.thesis_main.data_prep.prepare_scene_similarity_revision_20260909 import mapping_row
    a=mapping_row('H_abc',{'2','3'})
    assert a['mapping_status']=='conflict' and a['class_code']=='' and a['room_instance_id']==''
    b=mapping_row('H_abc',{'2'})
    assert b['class_code']=='2' and b['class_name']=='' and b['room_instance_id']==''
    assert mapping_row('H_none',set())['mapping_status']=='missing'


def test_pair_matching_uses_common_replicates_and_retains_no_support():
    from tools.thesis_main.data_prep.prepare_scene_similarity_revision_20260909 import compare_pair
    a=pd.DataFrame(dict(replicate=[0,0,1,1],k=[3,15,3,15],value=[0,0,1,1]))
    b=pd.DataFrame(dict(replicate=[0,0],k=[3,15],value=[.2,.2]))
    assert compare_pair(a,b)['curve_distance']==pytest.approx(.2)
    b['replicate']=2
    assert compare_pair(a,b)['status']=='no_shared_replicates'


def test_original_dispatcher_reads_all_four_pairs_and_preserves_conflict(tmp_path,monkeypatch):
    import tools.thesis_main.data_prep.inventory_annotation_research_assets_20260905 as module
    paths=[]
    for split in ['train','test']:
        for kind in ['pano','single']:
            image=tmp_path/f'{split}_room_{kind}_image.txt';label=tmp_path/f'{split}_room_{kind}_label.txt'
            image.write_text(f'./data/mp_sb/H/{split}.jpg\n' if kind=='pano' else f'/H/undistorted_color_images/{split}_i1_0.jpg\n')
            label.write_text('2\n' if kind=='pano' else '3\n')
            paths.extend([str(label),str(image)])
    monkeypatch.setattr(module,'ROOM_REGION_FILENAME_CANDIDATES',paths)
    monkeypatch.setattr(module,'ROOM_REGION_LOCAL_CHECKS',[])
    monkeypatch.setattr(module,'BI_ROOT',tmp_path/'missing')
    _,meta,rows=module._room_region_mapping_audit(tmp_path,{'H_train','H_test','H_missing'},set(),set(),set(),set())
    assert {r['image_id'] for r in rows}=={'H_train','H_test'} and len(rows)==4
    assert all(r['mapping_conflict_status']=='conflict' and r['source_is_instance_mapping']=='false' for r in rows)
    assert sum(r['status']=='aligned_pano_region_class' for r in meta['file_status'])==4
