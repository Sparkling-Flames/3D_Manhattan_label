from copy import deepcopy
import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.build_order_gt_screened_20260928 import screen_gt_ring, queue_state, ordered_layout


def test_gt_screen_ignores_start_direction_and_seam_but_keeps_backtracking_and_ties():
    for xs in ([761.29,776.53,248.37,262], [262,248.37,776.53,761.29], [0,200,500,900]):
        assert screen_gt_ring(xs)['reason']=='cyclic_monotonic'
    assert screen_gt_ring([100,400,350,700])['reason']=='local_backtracking'
    assert screen_gt_ring([100,400,400,700])['reason']=='same_x_pairs'
    with pytest.raises(ValueError):
        screen_gt_ring([10,float('nan'),500])


def test_queue_keeps_confirmations_and_separates_pairing_and_exclusions():
    obj=dict(object_kind='annotation',cleaning_disposition='retained',preprocessing_status='ready',image_code='x')
    assert queue_state(obj,{},True,False)=='pending'
    assert queue_state(obj,{},False,True)=='pending'
    assert queue_state(obj,{},False,False)=='not_selected'
    assert queue_state(obj,{'status':'confirmed'},False,False)=='confirmed'
    assert queue_state(obj,{'status':'pairing'},True,True)=='pairing_deferred'
    assert queue_state({**obj,'preprocessing_status':'unavailable'},{'status':'confirmed'},True,True)=='pairing_deferred'
    assert queue_state({**obj,'cleaning_disposition':'excluded_by_review'},{'status':'confirmed'},True,True)=='excluded'
    assert queue_state({**obj,'image_code':'B6ByNegPMKs-40'},{},True,True)=='not_selected'
    assert queue_state({**obj,'object_kind':'gt_original'},{},True,True)=='reference_only'
    assert queue_state({**obj,'object_kind':'gt_manual_revision'},{},False,False)=='pending'


def test_matterport_export_is_a_connected_copy_and_preserves_fixed_ids():
    obj=dict(object_id='a',object_kind='annotation',image_id='image',source={'path':'raw.json'},
             preprocessed_points=[[100,90],[100,410],[700,120],[700,390],[300,100],[300,400]],
             links_zero_based=[[0,1],[4,5],[2,3]],point_labels=['p1','p2','p3','p4','p5','p6'],
             preprocessing='shared_x_periodic_shortest_arc_v1')
    before=deepcopy(obj); out=ordered_layout(obj,[2,0,1])
    assert obj==before and out['closed'] is True
    assert out['ordered_source_pair_indices']==[2,0,1]
    assert out['ordered_source_point_indices']==[2,3,0,1,4,5]
    assert out['points_1024x512']==[obj['preprocessed_points'][i] for i in [2,3,0,1,4,5]]
    assert out['links_zero_based']==[[0,1],[2,3],[4,5]]
    with pytest.raises(ValueError):
        ordered_layout(obj,[0,0,1])


def test_generated_inventory_preserves_scope_confirmations_and_export_identity():
    root=Path(__file__).resolve().parents[1]/'analysis_results/order_gt_screened_20260928'
    load=lambda name:json.loads((root/name).read_text(encoding='utf-8'))
    summary=load('summary.json')
    with (root/'逐对象筛选.csv').open(encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    with (root/'原始与人工GT审计.csv').open(encoding='utf-8-sig') as f:
        audit=list(csv.DictReader(f))
    objects={o['object_id']:o for o in load('source_objects.json')['objects']}
    records=load('received_orders.json')['records']
    assert len(rows)==3152+30 and len(audit)==648
    assert summary['pending']==1098 and summary['confirmed']==63
    assert summary['original_gt_review_tasks']==0
    assert sum(r['manual_change'] in {'point_count_changed','coordinates_changed'} for r in audit)==30
    assert sum(r['manual_change']=='order_only' for r in audit)==1
    assert set(objects)=={r['object_id'] for r in rows if r['state'] in {'pending','confirmed'}}
    assert all(o['object_kind']!='gt_original' and o['preprocessing_status']=='ready' for o in objects.values())
    assert not any(r['state']=='pending' and r['image_code'] in {'B6ByNegPMKs-40','X7HyMhZNoso-05'} for r in rows)
    for r in rows:
        if r['state']=='pending':
            assert records.get(r['object_id'],{}).get('status') not in {'confirmed','pairing'}
            assert r['cleaning_disposition'] not in {'excluded_by_review','historical_not_accepted'}
    exported=load('confirmed_layouts.json')['objects']
    assert len(exported)==63
    for result in exported:
        oid=result['object_id']
        assert result==ordered_layout(objects[oid],records[oid]['order'])
