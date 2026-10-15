from tools.thesis_main.analysis.wall_consensus_quality_20261015 import classify_output, matched_changes
import pandas as pd
from tools.thesis_main.analysis.wall_consensus_special_20261015 import special_use, restrict
from tools.thesis_main.analysis.wall_consensus_quality_20261015 import measured,POP,ARCHIVE
from tools.thesis_main.analysis.worker_wq_integration_20261015 import frozen_engine,read
import gzip
import json
import zipfile


def test_incomplete_and_two_person_are_not_zero_quality():
    assert classify_output(2, 6, True, True) == 'two_person_deferred'
    assert classify_output(8, 3, True, True) == 'below_four'
    assert classify_output(8, 4, False, True) == 'no_connection'
    assert classify_output(8, 4, True, False) == 'floor_only_reference'


def test_matched_paths_do_not_replace_missing_with_other_paths():
    df = pd.DataFrame([dict(image='a', reference_axis='selected_target', path=p, k=k, WQ=q)
                       for p,k,q in [(0,8,10),(0,16,20),(1,8,90),(1,16,None)]])
    r = matched_changes(df, 8, 16)[0]
    assert r['matched_paths'] == 1 and r['mean_change'] == 10
    assert r['total_paths'] == 2


def test_nonorthogonal_does_not_become_manhattan_quality_error():
    assert special_use('oos','nonorthogonal_annotatable',None)=='nonorthogonal_no_direction_quality'
    assert special_use('oos','nonorthogonal_annotatable','reference_issue')=='reference_hold'
    r=restrict(dict(WQ=10,IoU3D100=80,WQ_no_D=70,floor_WQ_upper_bound=20), 'nonorthogonal_no_direction_quality')
    assert r['WQ'] is None and r['floor_WQ_upper_bound'] is None
    assert r['IoU3D100']==80 and r['WQ_no_D']==70


def test_real_floor_only_target_never_borrows_top():
    im=read(POP/'input_snapshot.json')['images'][0]
    with gzip.open(POP/'states'/f"{im['image']}.json.gz",'rt',encoding='utf-8') as handle:
        state=json.load(handle)['states'][-1]['automatic']
    ref=dict(im['references'][0],points=None)
    with zipfile.ZipFile(ARCHIVE) as archive,frozen_engine(archive) as engine:
        value=measured(engine,state,ref)
    assert value['score_status']=='floor_only_reference'
    assert value['WQ'] is None and value['IoU3D100'] is None
    assert value['iou_2d']>0 and value['floor_WQ_upper_bound'] is not None
